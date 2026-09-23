"""按版本生成公众号排版稿：article_{版本}_{日期}.html。含内容过滤降级与超时重试。"""
import json, os, sys, time
from openai import OpenAI

client = OpenAI(
    api_key=os.environ["MOONSHOT_API_KEY"],
    base_url="https://api.moonshot.cn/v1",
)

EDITION = os.environ.get("EDITION", "morning")

BLOCK_PATTERNS = [w.lower() for w in [
    "填入触发词1", "填入触发词2",
]]

def is_blocked(text):
    return any(w in (text or "").lower() for w in BLOCK_PATTERNS)

HEADER = """你是「每日新闻简报」公众号编辑。输出要求：只输出一段 HTML 片段，不要 markdown 标记、不要代码块、不要任何解释性文字，粘贴进微信公众号编辑器后应直接呈现排版效果。
排版规范（全部使用内联 style，禁止 class）：
最外层：<section style="font-size:15px; color:#2b2b2b; line-height:1.8; letter-spacing:0.5px;">
标题备选区：3 个备选标题各一行 <p style="font-size:15px;margin:2px 0;">，前缀"标题1/2/3："，区域末尾一条分隔线。
板块标题（市场概览/国内篇/国际篇/深度解读/今日看点等）：<h3 style="font-size:17px;color:#0F4C81;border-left:5px solid #0F4C81;padding-left:10px;margin:24px 0 12px;">
小节标签（经济/科技/社会）：<p style="margin:16px 0 8px;"><strong style="background:#0F4C81;color:#fff;padding:2px 8px;border-radius:3px;font-size:13px;">
每条新闻：标题 <p style="font-size:15.5px;margin:14px 0 4px;"><strong>；正文 <p style="margin:0 0 4px;">；点评 <p style="color:#8a8a8a;font-size:13px;margin:0 0 4px;">；来源 <p style="color:#b0b0b0;font-size:12px;margin:0 0 14px;">
配图：素材 image 非空的重要条目（全文最多4张），在标题前插入 <p style="margin:10px 0;"><img src="图片地址" style="max-width:100%;border-radius:6px;" /></p>
分隔线：板块之间 <hr style="border:none;border-top:1px solid #eee;margin:20px 0;" />
看点列表：每条 <p style="margin:6px 0;"> 前缀序号。
免责声明：<p style="color:#b0b0b0;font-size:12px;text-align:center;margin-top:24px;">
主题色：#0F4C81（深蓝），辅助灰 #7a7a7a / #b0b0b0。全文白底、克制、财经媒体风格，禁止花哨配色、渐变、emoji。"""

BASE = """分栏标准（严格执行）：国内篇=新闻主体是中国（中国企业、中国市场、中国监管、中国经济数据、中国科技产业、中国社会民生；港澳台归国内）；国际篇=新闻主体是中国以外的国家、地区、企业与人物；中外双边关系（中美对话、中欧贸易这类）归国际篇，点评中注明双边属性。忽略 cat 字段的偏差，按主体标准归类。
国内篇按内容性质分入「经济」「科技」「社会」小节：社会类=消费、生活方式、民生、趣闻，可来自任意来源。
标题备选必须正确体现当前版本（早间版/晚间版/周末版）与日期。
内容要求（重点）：
- 每条新闻 150-220 字，三段式：①核心事实——谁、做了什么，素材 summary 里的关键数字、名称、时间必须写出来；②背景或原因——这条新闻为什么发生、和什么趋势相关；③影响或看点——对投资者、行业或普通消费者意味着什么。
- 点评必须含信息增量：一个具体的关联、对比、趋势或风险点。严禁"引发关注""值得期待""影响深远""引发热议"这类无信息空话。
- 只能用素材中有的新闻与事实，禁止编造；素材没有的细节（具体金额、数据、引语）不得虚构。同一事件多源报道合并为一条。
- 国际条目的 title 与 summary 可能为英文，请翻译改写为中文。
时间口径：index 行情为最近收盘数据，美股为隔夜收盘；news_pool 快讯中的盘中表述（如"高开""盘初"）发生时点可能晚于指数收盘，引用时保留"盘中/截至发稿"表述，不得当作收盘数据。
市场概览：逐一列出指数数据（点位、涨跌幅），并分析量能与结构特征（大小盘分化、风格差异、与隔夜外盘联动）；数据均在 index 字段中，禁止出现素材未提供的数字（如涨跌家数、板块涨幅）。
深度解读：从素材中自选当天最重要的 1 条，写 250-350 字：来龙去脉、关键数据、影响分析。同样禁止编造素材外的事实。
社会类仅限民生、消费、生活方式、趣闻类正向内容；不碰突发事件、事故、案件、争议事件；涉时政的一律不写。
若 news_pool 为空，仅基于 index 行情数据写盘面简评，并注明"今日新闻条目因内容安全过滤未收录"，不得虚构新闻。
结尾固定：本文基于公开信息整理，不构成投资建议。"""

PROMPTS = {
    "morning": HEADER + "写【早间版】。结构：3个标题备选→导语80字内→【市场概览】（先隔夜美股：道指/纳指/标普点位与涨跌幅、结构特征；再昨日A股：5指数点位与涨跌幅、两市成交额、盘面结构，200-300字）→【国内篇】（经济3-5条、科技2-3条、社会2-3条）→【国际篇】3-5条→【深度解读】1条→【今日看点】3-4条（每条写清事件+时间+具体关注什么）→免责声明。" + BASE,
    "evening": HEADER + "写【晚间版】。结构：3个标题备选→导语80字内→【市场概览】（先今日A股：5指数点位与涨跌幅、两市成交额、盘面结构；再隔夜美股，200-300字）→【国内篇】（经济3-5条、科技2-3条、社会2-3条）→【国际篇】3-5条→【深度解读】1条→【明日看点】3-4条（每条写清事件+时间+具体关注什么）→免责声明。" + BASE,
    "weekly":  HEADER + "写【周末版】。结构：3个标题备选→导语120字内→【市场概览】用表格列出各指数本周涨跌幅（weekly_change 字段，table 用内联样式，表头深蓝底白字），并概括本周全球市场与A股特征→【国内篇·本周要闻】（经济/科技/社会分组，8-12条）→【国际篇·本周要闻】5-8条→【深度解读】1-2条→【下周看点】表格（日期|事件，4-6条）→免责声明。" + BASE,
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
        timeout=480,
    )

def call_with_retry(facts, pool, edition, attempts=3):
    """网络类错误（超时/连接失败）自动重试，其他错误直接抛出。"""
    for i in range(attempts):
        try:
            return call(facts, pool, edition)
        except Exception as e:
            msg = str(e).lower()
            transient = ("timeout" in msg or "timed out" in msg
                         or "connection" in msg or "connect" in msg)
            if not transient or i == attempts - 1:
                raise
            print(f"第 {i + 1} 次调用遇到网络问题（{e}），60 秒后重试…")
            time.sleep(60)

def main():
    facts = json.load(open("facts.json", encoding="utf-8"))
    edition = facts.get("edition", EDITION)
    pool = facts["news_pool"]

    try:
        print(f"开始生成 {edition} 版稿件（长文生成约需 4-8 分钟，请耐心等待）…")
        resp = call_with_retry(facts, pool, edition)
    except Exception as e:
        msg = str(e)
        if "high risk" in msg or "content_filter" in msg:
            print("被内容过滤拦截，剔除国际条目重试…")
            try:
                resp = call_with_retry(facts, [n for n in pool if n["cat"] != "国际"], edition)
            except Exception:
                print("仍被拦截，再剔除疑似条目重试…")
                try:
                    resp = call_with_retry(facts, [n for n in pool if n["cat"] != "国际" and not is_blocked(n["title"])], edition)
                except Exception:
                    print("仍被拦截，降级为行情简评稿")
                    resp = call_with_retry(facts, [], edition)
        else:
            raise

    html = resp.choices[0].message.content
    fname = f"article_{edition}_{facts['date']}.html"
    with open(fname, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"已生成 {fname}")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"生成失败：{e}", file=sys.stderr)
        sys.exit(1)
