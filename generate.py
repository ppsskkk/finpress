"""按版本生成公众号稿：article_{版本}_{日期}.md"""
import json, os, sys
from openai import OpenAI

client = OpenAI(
    api_key=os.environ["MOONSHOT_API_KEY"],
    base_url="https://api.moonshot.cn/v1",
)

EDITION = os.environ.get("EDITION", "morning")

BASE = """素材 news_pool 每条含 cat：国际→【国际篇】；国内-时政/国内-财经/国内-社会→【国内篇】。
每条=100-150字摘要+一句中性点评，末尾标注（来源：xx）。只能用素材中有的新闻，禁止编造；
同一事件多源报道合并为一条；国际篇中涉中国素材优先归入国内篇。
涉时政内容仅限官方政策与会议通稿摘要，不做评论与解读延伸。
结尾固定：本文基于公开信息整理，不构成投资建议。"""

PROMPTS = {
    "morning": "你是「每日新闻简报」公众号编辑，写【早间版】。结构：3个标题备选→导语80字内→【国内篇】（分 时政/财经/社会 小节，共6-10条）→【国际篇】（5-8条）→【今日看点】3-4条→免责声明。" + BASE,
    "evening": "你是「每日新闻简报」公众号编辑，写【晚间版】。结构：3个标题备选→导语80字内→【国内篇】（分 时政/财经/社会 小节，共6-10条）→【国际篇】（5-8条）→【明日看点】3-4条→免责声明。" + BASE,
    "weekly":  "你是「每周新闻盘点」公众号编辑，写【周末版】。结构：3个标题备选→导语120字内→【国内篇·本周要闻】（8-12条）→【国际篇·本周要闻】（6-8条）→【下周看点】表格（日期|事件，4-6条）→免责声明。" + BASE,
}

def main():
    facts = json.load(open("facts.json", encoding="utf-8"))
    edition = facts.get("edition", EDITION)
    user = "今日素材（JSON）：" + json.dumps(facts, ensure_ascii=False)

    resp = client.chat.completions.create(
        model="kimi-k2.6",
        messages=[
            {"role": "system", "content": PROMPTS.get(edition, PROMPTS["morning"])},
            {"role": "user", "content": user},
        ],
    )
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
