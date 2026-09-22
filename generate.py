"""按版本生成公众号排好版的 HTML：article_{版本}_{日期}.html。
流程：先探活 API（链路不通快速失败）→ 再生成（长超时，正常生成需4-6分钟）。"""
import json, os, sys, time

import requests
from openai import OpenAI

API_KEY = os.environ["MOONSHOT_API_KEY"]

client = OpenAI(
    api_key=API_KEY,
    base_url="https://api.moonshot.cn/v1",
    timeout=600,       # 正常生成本身需 4-6 分钟，不能用短超时
    max_retries=0,     # 重试由本脚本自己控制
)

BLOCK_PATTERNS = [w.lower() for w in [
    "填入触发词1", "填入触发词2",
]]

def is_blocked(text):
    return any(w in (text or "").lower() for w in BLOCK_PATTERNS)

def ping_api():
    """短探活：最多试 6 次（每次 10 秒超时，间隔 30 秒），确认链路通畅"""
    for i in range(6):
        try:
            r = requests.get(
                "https://api.moonshot.cn/v1/models",
                headers={"Authorization": f"Bearer {API_KEY}"},
                timeout=10,
            )
            if r.status_code == 200:
                print(f"API 连通正常（第 {i+1} 次探活）")
                return True
            print(f"第 {i+1} 次探活 HTTP {r.status_code}，30 秒后重试…")
        except Exception as e:
            print(f"第 {i+1} 次探活失败：{e}，30 秒后重试…")
        time.sleep(30)
    return False

STYLE = """【输出格式】只输出一段 HTML 片段：不要 markdown 标记、不要代码块围栏、不要任何解释性文字，粘贴进微信公众号编辑器后应直接呈现排版效果。全部样式用内联 style，禁止 class。
主题色 #0F4C81（深蓝），辅助灰 #7a7a7a / #b0b0b0，白底，财经媒体风格，禁止花哨配色、渐变、emoji、花哨字体。
排版规范：
- 最外层 <section style="font-size:15px;color:#2b2b2b;line-height:1.9;letter-spacing:0.5px;">
- 顶部标题区：<h2 style="font-size:20px;color:#0F4C81;border-bottom:2px solid #0F4C81;padding-bottom:10px;margin:0 0 8px;">选定的主标题</h2>，其下导语 <p style="color:#7a7a7a;font-size:13px;margin:0 0 4px;">
- 板块标题（市场概览/国内篇/国际篇/今日看点/明日看点/下周看点）：<h3 style="font-size:16px;color:#0F4C81;border-left:5px solid #0F4C81;padding-left:10px;margin:28px 0 14px;">
- 小节标签（经济/科技/社会/本周要闻等）：<p style="margin:18px 0 10px;"><strong style="background:#0F4C81;color:#ffffff;font-size:13px;padding:3px 10px;border-radius:3px;">标签</strong></p>
- 每条新闻：标题 <p style="font-size:15.5px;margin:16px 0 6px;"><strong>标题</strong></p>；正文 <p style="margin:0 0 6px;">；点评 <p style="color:#8a8a8a;font-size:13px;margin:0 0 4px;">点评：…</p>；来源 <p style="color:#b0b0b0;font-size:12px;margin:0 0 16px;">来源：xx</p>
- 配图：仅 image 字段非空的条目可配图，全文配图不超过 4 张，放在该条标题之前：<p style="margin:12px 0;"><img src="图片URL" style="width:100%;border-radius:6px;display:block;" /></p>
- 表格（周报用）：<table style="width:100%;border-collapse:collapse;font-size:13.5px;">，表头单元格 <td style="background:#0F4C81;color:#fff;padding:8px;border:1px solid #e5e5e5;">，普通单元格 <td style="padding:8px;border:1px solid #e5e5e5;">
- 板块之间 <hr style="border:none;border-top:1px solid #eeeeee;margin:24px 0;" />
- 看点列表：每条 <p style="margin:0 0 10px;"><strong style="color:#0F4C81;">01&nbsp;&nbsp;</strong>内容</p>（序号递增）
- 结尾免责：<p style="color:#b0b0b0;font-size:12px;text-align:center;margin-top:32px;">本文基于公开信息整理，不构成投资建议。</p>
</section> 闭合。"""

BASE = """【分栏标准】严格执行，忽略素材 cat 字段，按新闻主体归类：
- 国内篇：新闻主体是中国——中国企业与公司人物、中国市场与监管政策、中国经济数据、中国科技产业、中国社会民生；港澳台事务归入国内篇。
- 国际篇：新闻主体是中国以外的国家、地区、企业与人物；中外双边关系归入国际篇，并在点评中注明其双边属性。
国内篇内部按内容性质分入「经济」「科技」「社会」小节：社会类=消费、生活方式、民生、趣闻，可来自任意来源。
每条=100-150字摘要+一句中性点评。只能用素材中有的新闻，禁止编造；同一事件多源报道合并为一条。国际条目 title 可能为英文，请翻译改写为中文摘要。
市场概览的全部数字必须来自 index 字段（点位、涨跌幅、振幅、成交额）；素材未提供的数据（涨跌家数、板块涨跌幅、北向资金等）一律不得出现，结构特征只能作定性描述。
时间口径：index 行情为最近收盘数据，美股为隔夜收盘；news_pool 快讯中的盘中表述（如"高开""盘初"）发生时点可能晚于指数收盘，引用时保留"盘中/截至发稿"表述，不得当作收盘数据。
【微信发布合规（最高优先级，违反将导致发送失败）】
- 严禁出现：政府、国务院、部委名称、中外领导人姓名与职务（主席、总统、总理、部长、大臣）、会晤、峰会、条约、制裁等表述；
- 涉中外关系的素材只写产业与市场影响，不得出现"政府间""双方高层"等政治框架表述；
- 如某条素材只有政治角度可写，放弃该条。
社会类仅限民生、消费、生活方式、趣闻类正向内容；不碰突发事件、事故、案件、争议事件；涉时政的一律不写。
若 news_pool 为空，仅基于 index 行情数据写盘面简评，并注明"今日新闻条目因内容安全过滤未收录"，不得虚构新闻。"""

OVERVIEW = "【市场概览】（200-300字：逐一点名列出各指数的收盘点位与涨跌幅；描述量能（成交额）与盘面结构特征，如大小盘分化、成长与价值风格差异；结尾一句点评）"

PROMPTS = {
    "morning": "你是「每日新闻简报」公众号编辑，写【早间版】。结构：顶部标题区（从三个标题备选中选最佳一个作为主标题，其余两个不用输出）→导语80字内→" + OVERVIEW + "（先隔夜美股三大指数，再昨日A股五大指数与两市成交额）→【国内篇】（分「经济」3-5条、「科技」2-3条、「社会」2-3条）→【国际篇】3-5条→【今日看点】3-4条→免责声明。" + STYLE + BASE,
    "evening": "你是「每日新闻简报」公众号编辑，写【晚间版】。结构：顶部标题区→导语80字内→" + OVERVIEW + "（先今日A股五大指数与两市成交额，再隔夜美股三大指数）→【国内篇】（分「经济」3-5条、「科技」2-3条、「社会」2-3条）→【国际篇】3-5条→【明日看点】3-4条→免责声明。" + STYLE + BASE,
    "weekly":  "你是「每周新闻盘点」公众号编辑，写【周末版】。结构：顶部标题区→导语120字内→【市场概览】（表格列出 weekly_change 各指数本周涨跌幅，150字内概括本周全球市场特征）→【国内篇·本周要闻】（经济/科技/社会分组，8-12条）→【国际篇·本周要闻】5-8条→【下周看点】表格（日期|事件，4-6条）→免责声明。" + STYLE + BASE,
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

def call_with_fallback(facts, pool, edition):
    try:
        return call(facts, pool, edition)
    except Exception as e:
        msg = str(e).lower()
        if "high risk" in msg or "content_filter" in msg:
            print("被内容过滤拦截，剔除国际条目重试…")
            try:
                return call(facts, [n for n in pool if n["cat"] != "国际"], edition)
            except Exception:
                print("仍被拦截，再剔除疑似条目重试…")
                try:
                    return call(facts, [n for n in pool if n["cat"] != "国际" and not is_blocked(n["title"])], edition)
                except Exception:
                    print("仍被拦截，降级为行情简评稿")
                    return call(facts, [], edition)
        raise

def main():
    if not ping_api():
        print("API 持续不可达，本次生成放弃（下次定时任务会重试）")
        sys.exit(1)

    facts = json.load(open("facts.json", encoding="utf-8"))
    edition = facts.get("edition", "morning")
    resp = call_with_fallback(facts, facts["news_pool"], edition)

    md = resp.choices[0].message.content
    fname = f"article_{edition}_{facts['date']}.html"
    with open(fname, "w", encoding="utf-8") as f:
        f.write(md)
    print(f"已生成 {fname}")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"生成失败：{e}", file=sys.stderr)
        sys.exit(1)
