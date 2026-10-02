"""Index public Digital Policy Alert event headings with their event dates.

The index stores titles, event dates and direct links only. DPA's event date is
not treated as the page's publication date, and event records stay attributed
to Digital Policy Alert.
"""

import argparse
import hashlib
import html
import json
import re
import time
import urllib.parse
from datetime import datetime
from html.parser import HTMLParser
from zoneinfo import ZoneInfo

from collector import classify, clean_text, read_url
from config import COLLECTION_START_DATE
from storage import connect, initialize, utc_now


COUNTRIES = {
    "European Union": "欧盟", "EU": "欧盟", "United States of America": "美国",
    "United States": "美国", "United Kingdom": "英国", "France": "法国",
    "Germany": "德国", "Spain": "西班牙", "Italy": "意大利",
    "Netherlands": "荷兰", "Ireland": "爱尔兰", "Belgium": "比利时",
    "Denmark": "丹麦", "Sweden": "瑞典", "Finland": "芬兰",
    "Norway": "挪威", "Switzerland": "瑞士", "Poland": "波兰",
    "Austria": "奥地利", "Portugal": "葡萄牙", "Greece": "希腊",
    "Bulgaria": "保加利亚",
    "Czech Republic": "捷克", "Hungary": "匈牙利", "Romania": "罗马尼亚",
    "Canada": "加拿大", "Australia": "澳大利亚", "New Zealand": "新西兰",
    "China": "中国", "Japan": "日本", "South Korea": "韩国", "Republic of Korea": "韩国",
    "India": "印度", "Indonesia": "印度尼西亚", "Malaysia": "马来西亚",
    "Singapore": "新加坡", "Thailand": "泰国", "Vietnam": "越南",
    "Philippines": "菲律宾", "Pakistan": "巴基斯坦", "Bangladesh": "孟加拉国",
    "Brazil": "巴西", "Mexico": "墨西哥", "Argentina": "阿根廷",
    "Chile": "智利", "Colombia": "哥伦比亚", "Peru": "秘鲁",
    "South Africa": "南非", "Kenya": "肯尼亚", "Nigeria": "尼日利亚",
    "Egypt": "埃及", "Saudi Arabia": "沙特阿拉伯", "United Arab Emirates": "阿联酋",
    "Israel": "以色列", "Turkey": "土耳其", "Türkiye": "土耳其",
    "Russia": "俄罗斯", "Ukraine": "乌克兰", "Global": "国际组织",
}

EU_INSTITUTIONS = ("European Commission", "European Data Protection Board",
                   "European Union", "Court of Justice", "Advocate General")


class EventParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.items = []
        self.date = ""
        self.current_a = ""
        self.in_h3 = False
        self.in_h4 = False
        self.in_span = False
        self.heading = ""
        self.buffer = []
        self.span_buffer = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "span":
            self.in_span = True
            self.span_buffer = []
        elif tag == "a":
            href = attrs.get("href", "")
            self.current_a = href if href.startswith("/event/") else ""
        elif tag == "h3":
            self.in_h3 = True
            self.buffer = []
        elif tag == "h4" and self.current_a:
            self.in_h4 = True
            self.buffer = []

    def handle_data(self, data):
        if self.in_span:
            self.span_buffer.append(data)
        if self.in_h3 or self.in_h4:
            self.buffer.append(data)

    def handle_endtag(self, tag):
        if tag == "span" and self.in_span:
            value = "".join(self.span_buffer).strip()
            if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
                self.date = value
            self.in_span = False
        elif tag == "h3" and self.in_h3:
            self.heading = clean_text("".join(self.buffer))
            self.in_h3 = False
        elif tag == "h4" and self.in_h4:
            title = clean_text("".join(self.buffer))
            if self.date and title and self.current_a:
                prefix = self.heading.split(":", 1)[0].strip()
                if prefix in COUNTRIES and not title.startswith(prefix + ":"):
                    title = prefix + ": " + title
                self.items.append({"date": self.date, "title": title,
                                   "url": "https://digitalpolicyalert.org" + self.current_a})
            self.in_h4 = False
        elif tag == "a":
            self.current_a = ""


def collect(backfill=False, max_pages=None, dry_run=False, start_page=0):
    initialize()
    today = datetime.now(ZoneInfo("Asia/Shanghai")).date().isoformat()
    page_limit = max_pages or (50 if backfill else 2)
    added = checked = 0
    errors = []
    for page in range(start_page, start_page + page_limit):
        params = urllib.parse.urlencode({"offset": page * 100, "limit": 100,
                                         "period": f"{COLLECTION_START_DATE},{today}"})
        url = "https://digitalpolicyalert.org/activity-tracker?" + params
        try:
            parser = EventParser()
            parser.feed(read_url(url, "text/html").decode("utf-8", "replace"))
        except Exception as exc:
            errors.append(f"page {page + 1}: {type(exc).__name__}: {str(exc)[:120]}")
            break
        page_items = [item for item in parser.items
                      if COLLECTION_START_DATE <= item["date"] <= today]
        checked += len(page_items)
        page_added = 0
        with connect() as db:
            for item in page_items:
                category = classify(item["title"], "")
                if not category:
                    continue
                prefix = item["title"].split(":", 1)[0].strip()
                country = COUNTRIES.get(prefix, "")
                item_id = hashlib.sha256(item["url"].encode()).hexdigest()[:24]
                if dry_run:
                    page_added += 1
                    continue
                if db.execute("SELECT 1 FROM media_index WHERE id=?", (item_id,)).fetchone():
                    continue
                if item["title"].startswith(EU_INSTITUTIONS):
                    country = "欧盟"
                elif not country:
                    country = event_country(item["url"])
                scope = "china" if country == "中国" else "international"
                cursor = db.execute("""INSERT OR IGNORE INTO media_index
                    (id,title,url,publisher,published_at,category_id,language,scope,
                     province,country,date_kind,status,collected_at)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (item_id, item["title"], item["url"], "Digital Policy Alert",
                     item["date"] + "T12:00:00+00:00", category[0], "en", scope,
                     "", country, "event", "published", utc_now()))
                page_added += cursor.rowcount
        added += page_added
        print(f"DPA page {page + 1}: {len(page_items)} dated, +{page_added} relevant", flush=True)
        if len(parser.items) < 100:
            break
        time.sleep(1)
    result = {"added": added, "checked": checked, "errors": errors,
              "date_kind": "event"}
    print(json.dumps(result, ensure_ascii=False), flush=True)
    return result


def event_country(url):
    """Read only the public page title; it prefixes the event with its jurisdiction."""
    try:
        page = read_url(url, "text/html").decode("utf-8", "replace")
        match = re.search(r"<title[^>]*>(.*?)</title>", page, re.I | re.S)
        if match:
            prefix = html.unescape(match.group(1)).split(":", 1)[0].strip()
            return COUNTRIES.get(prefix, "")
    except Exception:
        pass
    return ""


def enrich_countries():
    initialize()
    with connect() as db:
        rows = db.execute("SELECT id,url,title,country FROM media_index WHERE date_kind='event' ORDER BY published_at DESC").fetchall()
    updated = 0
    for row in rows:
        country = "欧盟" if row["title"].startswith(EU_INSTITUTIONS) else (
            event_country(row["url"]) if not row["country"] else row["country"])
        if country and country != row["country"]:
            with connect() as db:
                db.execute("UPDATE media_index SET country=?, scope=? WHERE id=?",
                           (country, "china" if country == "中国" else "international", row["id"]))
            updated += 1
        if not row["country"]:
            time.sleep(0.4)
    print(json.dumps({"checked": len(rows), "updated": updated}, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--backfill", action="store_true")
    parser.add_argument("--max-pages", type=int)
    parser.add_argument("--start-page", type=int, default=0,
                        help="从 0 开始的公开活动页偏移，用于分批回填")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--enrich-countries", action="store_true")
    args = parser.parse_args()
    if args.enrich_countries:
        enrich_countries()
    else:
        if args.start_page < 0:
            raise ValueError("start-page 不能为负数")
        collect(args.backfill, args.max_pages, args.dry_run, args.start_page)
