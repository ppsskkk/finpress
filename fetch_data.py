"""抓取行情 + 新闻素材，写入 facts.json。行情：腾讯接口；新闻：RSS 源清单（源需定期维护）。"""
import json, os, re, urllib.request
from datetime import datetime, timezone, timedelta

import requests
import feedparser

EDITION = os.environ.get("EDITION", "morning")

CN = timezone(timedelta(hours=8))
now = datetime.now(CN)
facts = {
    "edition": EDITION,
    "date": now.strftime("%Y-%m-%d"),
    "time_beijing": now.strftime("%H:%M"),
    "weekday": ["周一","周二","周三","周四","周五","周六","周日"][now.weekday()],
    "index": {},
    "weekly_change": {},
    "news_pool": [],
    "notes": [],
}

# ============ 行情 ============
A_SHARES = {"上证指数": "sh000001", "深证成指": "sz399001", "创业板指": "sz399006",
            "科创50": "sh000688", "沪深300": "sh000300"}
US_INDEX = {"道琼斯": "usDJI", "纳斯达克": "usIXIC", "标普500": "usINX"}
TURNOVER = {"沪市": "sh000001", "深市": "sz399106"}

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

def pct(f):
    return round((float(f[3]) - float(f[4])) / float(f[4]) * 100, 2)

try:
    quotes = fetch_quotes(list(A_SHARES.values()) + list(US_INDEX.values()) + list(TURNOVER.values()))
    for name, code in {**A_SHARES, **US_INDEX}.items():
        f = quotes.get(code)
        if f:
            facts["index"][name] = {"收盘": round(float(f[3]), 2), "涨跌幅%": pct(f)}
    try:
        facts["total_turnover_yi"] = round(float(quotes["sh000001"][37]) / 1e4 + float(quotes["sz399106"][37]) / 1e4)
    except Exception:
        pass
except Exception as e:
    facts["notes"].append(f"行情抓取失败：{e}")

def weekly_change(code):
    try:
        url = f"https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={code},day,,,10,qfq"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15) as r:
            d = json.loads(r.read().decode("utf-8"))["data"][code]
        days = d.get("qfqday") or d.get("day")
        if days and len(days) >= 6:
            return round((float(days[-1][2]) - float(days[-6][2])) / float(days[-6][2]) * 100, 2)
    except Exception:
        return None

if EDITION == "weekly":
    for name, code in {**A_SHARES, **US_INDEX}.items
