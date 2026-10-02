"""Translation handoff for the multilingual public search index.

    python3 media_cli.py pending --limit 100
    python3 media_cli.py apply data/media-translations.json
"""

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from collector import classify, normalize_url
from config import COLLECTION_START_DATE, SECTION_BY_CATEGORY
from geography import infer_province
from media_index import is_china_publisher, publisher_country, title_key
from storage import connect, initialize, utc_now


def pending(limit):
    initialize()
    with connect() as db:
        rows = [dict(row) for row in db.execute("""SELECT id,title,language,publisher,
            published_at,url,date_kind FROM media_index WHERE
            (language NOT IN ('zh','en') OR date_kind='event') AND title_zh=''
            AND status='published'
            ORDER BY published_at DESC LIMIT ?""", (limit,))]
    return {"items": rows}


def apply(path):
    initialize()
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("输入必须是数组")
    count = 0
    with connect() as db:
        for item in payload:
            if not isinstance(item, dict):
                continue
            item_id = item.get("id")
            title_zh = item.get("title_zh")
            if not isinstance(item_id, str) or len(item_id) != 24:
                continue
            if item.get("exclude") is True:
                cursor = db.execute("UPDATE media_index SET status='excluded' WHERE id=?", (item_id,))
                count += cursor.rowcount
                continue
            if not isinstance(title_zh, str) or not title_zh.strip() or len(title_zh) > 180:
                continue
            cursor = db.execute("""UPDATE media_index SET title_zh=? WHERE id=?
                AND (language NOT IN ('zh','en') OR date_kind='event') AND title_zh=''""",
                (title_zh.strip(), item_id))
            count += cursor.rowcount
    return {"updated": count, "submitted": len(payload)}


def add_verified(path):
    """Import only leads already checked against a direct original article URL."""
    initialize()
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("输入必须是数组")
    cutoff = datetime.fromisoformat(COLLECTION_START_DATE).replace(
        tzinfo=ZoneInfo("Asia/Shanghai")).astimezone(timezone.utc)
    added = 0
    skipped = []
    with connect() as db:
        seen = {title_key(row[0]) for row in db.execute(
            "SELECT title FROM articles UNION ALL SELECT title FROM media_index")}
        seen_urls = {row[0] for row in db.execute(
            "SELECT url FROM articles UNION ALL SELECT url FROM media_index")}
        for index, item in enumerate(payload, 1):
            if not isinstance(item, dict):
                skipped.append([index, "invalid item"])
                continue
            title = str(item.get("title", "")).strip()
            title_zh = str(item.get("title_zh", "")).strip()
            publisher = str(item.get("publisher", "")).strip()[:120]
            language = str(item.get("language", "en")).strip().lower()
            url = normalize_url(str(item.get("url", "")))
            host = url.split("/", 3)[2].lower() if url else ""
            try:
                published = datetime.fromisoformat(str(item.get("published_at", "")))
                if published.tzinfo is None:
                    raise ValueError("timezone required")
            except ValueError:
                skipped.append([index, "invalid publication date"])
                continue
            category_id = str(item.get("category", "")).strip()
            if category_id and category_id not in SECTION_BY_CATEGORY:
                skipped.append([index, "invalid category"])
                continue
            if not category_id:
                classified = classify(title, title_zh)
                category_id = classified[0] if classified else ""
            key = title_key(title)
            if (not title or not publisher or not url or host in ("news.google.com", "www.bing.com")
                    or language not in ("zh", "en") and not title_zh
                    or published.astimezone(timezone.utc) < cutoff or not category_id
                    or key in seen or url in seen_urls):
                skipped.append([index, "unverified, duplicate, or out of scope"])
                continue
            country = str(item.get("country", "")).strip() or publisher_country(url, language)
            scope = "china" if country == "中国" or is_china_publisher(url, language) else "international"
            if scope == "china":
                country = "中国"
            province = str(item.get("province", "")).strip() if scope == "china" else ""
            if not province and scope == "china":
                province = infer_province(title_zh or title, "", {"country": "中国"})
            item_id = hashlib.sha256(url.encode()).hexdigest()[:24]
            cursor = db.execute("""INSERT OR IGNORE INTO media_index
                (id,title,title_zh,url,publisher,published_at,category_id,language,
                 scope,province,country,date_kind,status,collected_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (item_id, title, title_zh, url, publisher, published.isoformat(),
                 category_id, language, scope, province, country, "published", "published", utc_now()))
            if cursor.rowcount:
                added += 1
                seen.add(key)
                seen_urls.add(url)
            else:
                skipped.append([index, "duplicate URL"])
    return {"added": added, "submitted": len(payload), "skipped": skipped}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    read = sub.add_parser("pending")
    read.add_argument("--limit", type=int, default=100)
    write = sub.add_parser("apply")
    write.add_argument("file")
    verified = sub.add_parser("add-verified")
    verified.add_argument("file")
    args = parser.parse_args()
    result = (pending(min(max(args.limit, 1), 500)) if args.command == "pending"
              else apply(args.file) if args.command == "apply" else add_verified(args.file))
    print(json.dumps(result, ensure_ascii=False, indent=2))
