"""调用 Moonshot API，根据 facts.json 生成公众号稿 article_YYYYMMDD.md"""
import json, os, sys
from datetime import datetime
from openai import OpenAI

client = OpenAI(
    api_key=os.environ["MOONSHOT_API_KEY"],
    base_url="https://api.moonshot.cn/v1",
)

SYSTEM = """你是「每日财经简报」公众号编辑。严格遵守：
1. 结构：3个标题备选 → 80字导语 → 【国内篇】【国际篇】→ 明日看点 → 免责声明；
2. 每条100-150字，写法=事实+一句中性点评，禁止整段转载原文，禁止编造素材中没有的数字；
3. 若素材中的行情数据为空，正文中不得出现任何具体点位/涨跌幅数字，并注明"行情数据获取受限"；
4. 语气中性克制，结尾固定附：本文基于公开信息整理，不构成投资建议。"""

def main():
    facts = json.load(open("facts.json", encoding="utf-8"))
    user = "今日素材（JSON）：" + json.dumps(facts, ensure_ascii=False)

    resp = client.chat.completions.create(
        model="kimi-k3",  # 如不可用，到 platform.moonshot.cn 控制台查看可用模型名
        messages=[
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": user},
        ],
        temperature=0.3,
    )
    md = resp.choices[0].message.content
    fname = f"article_{facts['date']}.md"
    with open(fname, "w", encoding="utf-8") as f:
        f.write(md)
    print(f"已生成 {fname}")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"生成失败：{e}", file=sys.stderr)
        sys.exit(1)
