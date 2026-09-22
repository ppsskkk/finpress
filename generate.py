"""按版本生成公众号稿：article_{版本}_{日期}.md。含内容过滤自动重试与降级。"""
import json, os, sys
from openai import OpenAI

client = OpenAI(
    api_key=os.environ["MOONSHOT_API_KEY"],
    base_url="https://api.moonshot.cn/v1",
)

BLOCK_PATTERNS = [w.lower() for w in [
    "填入触发词1", "填入触发词2",
]]

def is_blocked(text):
    return any(w in (text or "").lower() for w in BLOCK_PATTERNS)

BASE = """【分栏标准】严格执行，忽略素材 cat 字段，按新闻主体归类：
- 国内篇：新闻主体是中国——中国企业与公司人物、中国市场与监管政策、中国经济数据、中国科技产业、中国社会民生；港澳台事务归入国内篇。
- 国际篇：新闻主体是中国以外的国家、地区、企业与人物；中外双边关系（如中美对话、中欧贸易、中外企业合作）归入国际篇，并在点评中注明其双边属性。
国内篇内部按内容性质分入「经济」「科技」「社会」小节：社会类=消费、生活方式、民生、趣闻，可来自任意来源。
标题备选必须正确体现当前版本（早间版/晚间版/周末版）与日期。
每条=100-150字摘要+一句中性点评，末尾标注（来源：xx）。只能用素材中有的新闻，禁止编造；同一事件多源报道合并为一条。国际条目 title 可能为英文，请翻译改写为中文摘要。
市场概览的全部数字必须来自 index 字段（点位、涨跌幅、振幅、成交额）；素材未提供的数据（涨跌家数、板块涨跌幅、北向资金等）一律不得出现，结构特征只能作定性描述。
时间口径：index 行情为最近收盘数据，美股为隔夜收盘；news_pool 快讯中的盘中表述（如"高开""盘初"）发生时点可能晚于指数收盘，引用时保留"盘中/截至发稿"表述，不得当作收盘数据。
社会类仅限民生、消费、生活方式、趣闻类正向内容；不碰突发事件、事故、案件、争议事件；涉时政的一律不写。
若 news_pool 为空，仅基于 index 行情数据写盘面简评，并注明"今日新闻条目因内容安全过滤未收录"，不得虚构新闻。
结尾固定：本文基于公开信息整理，不构成投资建议。"""

OVERVIEW = "【市场概览】（200-300字：逐一点名列出各指数的收盘点位与涨跌幅；描述量能（成交额）与盘面结构特征，如大小盘分化、成长与价值风格差异；结尾一句点评）"

PROMPTS = {
    "morning": "你是「每日新闻简报」公众号编辑，写【早间版】。结构：3个标题备选→导语80字内→" + OVERVIEW + "（先隔夜美股三大指数，再昨日A股五大指数与两市成交额）→【国内篇】（分「经济」3-5条、「科技」2-3条、「社会」2-3条）→【国际篇】3-5条→【今日看点】3-4条→免责声明。" + BASE,
    "evening": "你是「每日新闻简报」公众号编辑，写【晚间版】。结构：3个标题备选→导语80字内→" + OVERVIEW + "（先今日A股五大指数与两市成交额，再隔夜美股三大指数）→【国内篇】（分「经济」3-5条、「科技」2-3条、「社会」2-3条）→【国际篇】3-5条→【明日看点】3-4条→免责声明。" + BASE,
    "weekly":  "你是「每周新闻盘点」公众号编辑，写【周末版】。结构：3个标题备选→导语120字内→【市场概览】（用表格列出 weekly_change 中各指数本周涨跌幅，150字内概括本周全球市场特征）→【国内篇·本周要闻】（经济/科技/社会分组，8-12条）→【国际篇·本周要闻】5-8条→【下周看点】表格（日期|事件，4-6条）→免责声明。" + BASE,
}

def call(facts, pool, edition):
    f2 = dict(facts)
    f2["news_pool"] = pool
    return client.chat.completions.create(
        model="kimi-k2.6",
        messages=[
            {"role": "system", "content": PROMPTS.get(edition, PROMPTS["morning"])},
            {"role": "user", "content": "今日素材（JSON）：" + json.dumps(f2, ensure_ascii=False)},
        ],
    )

def main():
    facts = json.load(open("facts.json", encoding="utf-8"))
    edition = facts.get("edition", "morning")
    pool = facts["news_pool"]

    try:
        resp = call(facts, pool, edition)
    except Exception as e:
        msg = str(e)
        if "high risk" in msg or "content_filter" in msg:
            print("被内容过滤拦截，剔除国际条目重试…")
            try:
                resp = call(facts, [n for n in pool if n["cat"] != "国际"], edition)
            except Exception:
                print("仍被拦截，再剔除疑似条目重试…")
                try:
                    resp = call(facts, [n for n in pool if n["cat"] != "国际" and not is_blocked(n["title"])], edition)
                except Exception:
                    print("仍被拦截，降级为行情简评稿")
                    resp = call(facts, [], edition)
        else:
            raise

    md = resp.choices[0].message.content
    fname = f"article_{edition}_{facts['date']}.md"
    with open(fname, "w", encoding="utf-8") as f:
        f.write(md)
    print(f"已生成 {fname}")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"生成失败：{e}", file=sys.stderr)
        sys.exit(1)
