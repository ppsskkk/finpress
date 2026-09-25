"""抓取行情 + 新闻素材，输出 facts.json。edition 由北京时间自动判断。"""
import json, os, re, urllib.request
from datetime import datetime, timezone, timedelta

import requests
import feedparser

CN = timezone(timedelta(hours=8))
now = datetime.now(CN)

if now.weekday() == 6:
    EDITION = "weekly"
elif now.hour < 18:
    EDITION = "morning"
else:
    EDITION = "evening"

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

def quote_detail(f):
    prev = float(f[4]); price = float(f[3])
    return {
        "开盘": round(float(f[5]), 2),
        "最高": round(float(f[6]), 2),
        "最低": round(float(f[7]), 2),
        "收盘": round(price, 2),
        "昨收": round(prev, 2),
        "涨跌幅%": round((price - prev) / prev * 100, 2),
        "振幅%": round((float(f[6]) - float(f[7])) / prev * 100, 2),
    }

try:
    quotes = fetch_quotes(list(A_SHARES.values()) + list(US_INDEX.values()) + list(TURNOVER.values()))
    for name, code in {**A_SHARES, **US_INDEX}.items():
        f = quotes.get(code)
        if f:
            facts["index"][name] = quote_detail(f)
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
    for name, code in {**A_SHARES, **US_INDEX}.items():
        c = weekly_change(code)
        if c is not None:
            facts["weekly_change"][name] = c

# ============ 新闻（经济 / 科技 / 社会 / 国际）============
# 维护提示：运行日志会打印每个源的抓取条数；连续为 0 的源，注释掉或换 url
RSS_SOURCES = [
    {"name": "BBC英文·财经", "url": "https://feeds.bbci.co.uk/news/business/rss.xml", "cat": "国际"},
    {"name": "FT中文网",     "url": "http://www.ftchinese.com/rss/news",            "cat": "国际"},
    {"name": "华尔街见闻",   "url": "https://dedicated.wallstreetcn.com/rss.xml",   "cat": "经济"},
    {"name": "钛媒体",       "url": "https://www.tmtpost.com/rss.xml",              "cat": "经济"},  # ⚠️ 新增，待验证
    {"name": "少数派",       "url": "https://sspai.com/feed",                       "cat": "科技"},
    {"name": "爱范儿",       "url": "https://www.ifanr.com/feed",                   "cat": "科技"},
]
MAX_PER_SOURCE = 4
MAX_TOTAL = 24

def strip_html(s):
    return re.sub(r"<[^>]+>", "", s or "").strip()

# 内容安全预过滤：命中即剔除该条。遇到 content_filter 报错时，
# 看运行日志里 facts.json 中的标题，把触发词补充到下面列表。
# 领导人相关词为公众号合规红线，请勿删除。
BLOCK_PATTERNS = [w.lower() for w in [
    "习近平", "李强", "赵乐际", "王沪宁", "蔡奇", "丁薛祥", "李希",
    "韩正", "王毅", "总书记", "国家主席",
]]

def is_blocked(text):
    return any(w in (text or "").lower() for w in BLOCK_PATTERNS)

def pick_image(e):
    for m in e.get("media_content", []):
        u = m.get("url", "")
        if u.startswith("http"):
            return u
    for l in e.get("enclosures", []):
        if str(l.get("type", "")).startswith("image") and l.get("href"):
            return l["href"]
    return ""

seen, count = set(), 0
for src in RSS_SOURCES:
    try:
        r = requests.get(src["url"], headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
        feed = feedparser.parse(r.content)
        got = 0
        for e in feed.entries:
            if got >= MAX_PER_SOURCE or count >= MAX_TOTAL:
                break
            title = (e.get("title") or "").strip()
            if not title or title in seen:
                continue
            summary = strip_html(e.get("summary", ""))
            full = title + " " + summary
            if is_blocked(full):
                continue
            seen.add(title)
            facts["news_pool"].append({
                "title": title,
                "source": src["name"],
                "cat": src["cat"],
                "link": e.get("link", ""),
                "summary": summary[:200],
                "image": pick_image(e),
            })
            got += 1
            count += 1
        if got == 0:
            facts["notes"].append(f"源无内容：{src['name']}（考虑更换）")
    except Exception as ex:
        facts["notes"].append(f"源抓取失败：{src['name']}：{ex}")

with open("facts.json", "w", encoding="utf-8") as fp:
    json.dump(facts, fp, ensure_ascii=False, indent=2)
print(json.dumps(facts, ensure_ascii=False, indent=2))
