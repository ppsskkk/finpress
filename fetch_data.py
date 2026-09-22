"""抓取当日公开市场数据，写入 facts.json。任何一步失败都不致命，只记录到 notes。"""
import json
from datetime import datetime

facts = {
    "date": datetime.now().strftime("%Y-%m-%d"),
    "weekday": datetime.now().weekday(),  # 0=周一
    "index": {},
    "news_pool": [],
    "notes": [],
}

# ---- A股主要指数（akshare 聚合公开行情；接口偶有变动，失败会记录）----
try:
    import akshare as ak
    spot = ak.stock_zh_index_spot_em()
    targets = ["上证指数", "深证成指", "创业板指", "科创50", "沪深300"]
    for name in targets:
        row = spot[spot["名称"] == name]
        if row.empty:
            row = spot[spot["名称"].str.contains(name[:2], na=False)]
        if not row.empty:
            r = row.iloc[0]
            facts["index"][name] = {
                "收盘": round(float(r["最新价"]), 2),
                "涨跌幅%": round(float(r["涨跌幅"]), 2),
            }
    # 两市成交额（亿元）
    try:
        sh = spot[spot["名称"] == "上证指数"]["成交额"].iloc[0]
        sz = spot[spot["名称"].str.contains("深证", na=False)]["成交额"].iloc[0]
        facts["total_turnover_yi"] = round((float(sh) + float(sz)) / 1e8)
    except Exception:
        pass
except Exception as e:
    facts["notes"].append(f"行情抓取失败（可能为周末休市或接口变动）：{e}")

# ---- 新闻池：在此追加你自己的官方 RSS/栏目源（可选，v1 可留空）----
# 推荐源（均为官方公开发布）：央行、证监会、工信部、统计局、上交所、深交所
# facts["news_pool"].append({"title": "...", "source": "央行", "url": "..."})

with open("facts.json", "w", encoding="utf-8") as f:
    json.dump(facts, f, ensure_ascii=False, indent=2)

print(json.dumps(facts, ensure_ascii=False, indent=2))
