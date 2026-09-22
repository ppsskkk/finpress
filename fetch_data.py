"""抓取当日公开市场数据，写入 facts.json。数据源：腾讯行情接口（对海外网络友好，无需密钥）。"""
import json, re, urllib.request
from datetime import datetime, timezone, timedelta

CN = timezone(timedelta(hours=8))
now = datetime.now(CN)
facts = {
    "date": now.strftime("%Y-%m-%d"),
    "time_beijing": now.strftime("%H:%M"),
    "weekday": ["周一","周二","周三","周四","周五","周六","周日"][now.weekday()],
    "index": {},
    "news_pool": [],
    "notes": [],
}

SYMBOLS = {
    "上证指数": "sh000001",
    "深证成指": "sz399001",
    "创业板指": "sz399006",
    "科创50": "sh000688",
    "沪深300": "sh000300",
}
TURNOVER = {"沪市": "sh000001", "深市": "sz399106"}  # 两市合计成交额

def fetch_quotes(codes):
    url = "https://qt.gtimg.cn/q=" + ",".join(codes)
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=15) as r:
        text = r.read().decode("gbk", errors="ignore")
    out = {}
    for code, val in re.findall(r'v_(\w+)="([^"]*)"', text):
        f = val.split("~")
        if len(f) > 4 and f[3]:
            out[code] = f
    return out

try:
    quotes = fetch_quotes(list(SYMBOLS.values()) + list(TURNOVER.values()))
    for name, code in SYMBOLS.items():
        f = quotes.get(code)
        if not f:
            continue
        price, prev = float(f[3]), float(f[4])
        facts["index"][name] = {
            "收盘": round(price, 2),
            "涨跌幅%": round((price - prev) / prev * 100, 2),
        }
    try:
        sh = float(quotes["sh000001"][37]) / 1e4  # 成交额：万元→亿元
        sz = float(quotes["sz399106"][37]) / 1e4
        facts["total_turnover_yi"] = round(sh + sz)
    except Exception:
        pass
    if not facts["index"]:
        facts["notes"].append("行情接口返回为空（可能为非交易时段）")
except Exception as e:
    facts["notes"].append(f"行情抓取失败：{e}")

with open("facts.json", "w", encoding="utf-8") as fp:
    json.dump(facts, fp, ensure_ascii=False, indent=2)
print(json.dumps(facts, ensure_ascii=False, indent=2))
