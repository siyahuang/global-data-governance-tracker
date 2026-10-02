"""Read-only public tracker. Start with: python3 server.py"""

import json
import mimetypes
import os
import re
import csv
import io
from collections import Counter
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit
from zoneinfo import ZoneInfo

from auth import (clear_cookie, create_session, create_user, delete_session,
                  initialize_auth, session_cookie, token_from_headers,
                  user_for_token, authenticate)
from config import BASE_DIR, COLLECTION_START_DATE, SECTIONS, SOURCES, SECTION_BY_CATEGORY
from weekly_reports import load_report
from cloud_scheduler import start_scheduler
from storage import connect, initialize

STATIC_DIR = BASE_DIR / "static"
REQUIRE_LOGIN = os.environ.get("REQUIRE_LOGIN", "0") == "1"
ALLOW_REGISTRATION = os.environ.get("ALLOW_REGISTRATION", "1") == "1"
VISIBLE = ("status NOT IN ('排除', '暂缓') AND "
           f"date(published_at, '+8 hours') >= '{COLLECTION_START_DATE}'")
MEDIA_VISIBLE = ("status='published' AND (language IN ('zh','en') OR title_zh!='') AND "
                 f"date(published_at, '+8 hours') >= '{COLLECTION_START_DATE}' AND "
                 "NOT EXISTS (SELECT 1 FROM articles a WHERE a.url=media_index.url "
                 "AND a.status NOT IN ('排除','暂缓'))")

# The original taxonomy stays in the database. Readers see shorter names.
PUBLIC_NAMES = {
    "law": "法律与政策", "plan": "战略与行动", "scope": "开放范围",
    "platform": "平台与基础设施", "service": "服务与标准",
    "activity": "交流与活动", "outcome": "应用与成效",
    "international": "国际组织", "dataspace": "数据空间",
    "intermediary": "数据中介", "commons": "数据公地",
    "crossborder": "跨境数据流动", "privacy": "隐私与个人信息", "ai": "人工智能与数据",
}
PUBLIC_SECTIONS = [
    {"id": section["id"], "name": "数据开放" if section["id"] == "open" else "相关议题",
     "categories": [{"id": item["id"], "name": PUBLIC_NAMES[item["id"]]}
                    for item in section["categories"]]}
    for section in SECTIONS
]


def query_arg(query, name, default=""):
    return query.get(name, [default])[0]


def public_article(row):
    return {key: row[key] for key in (
        "id", "title", "title_zh", "summary", "brief_zh", "url",
        "source_id", "source_name", "source_region", "source_country", "province", "published_at",
        "collected_at", "section_id", "category_id", "date_kind", "record_type",
    )}


FEED_CTE = f"""WITH feed AS (
    SELECT id,title,title_zh,summary,brief_zh,url,source_id,source_name,
           source_region,source_country,province,published_at,collected_at,
           section_id,category_id,'published' AS date_kind,relevance,'机构发布' AS record_type
    FROM articles WHERE {VISIBLE}
    UNION ALL
    SELECT id,title,title_zh,'' AS summary,'' AS brief_zh,url,
           'media:' || publisher AS source_id,publisher AS source_name,
           CASE WHEN scope='china' THEN '中国' ELSE '国际' END AS source_region,
           CASE WHEN scope='china' THEN '中国' WHEN country!='' THEN country
                ELSE '未定位' END AS source_country,
           province,published_at,collected_at,
           CASE WHEN category_id IN ('law','plan','scope','platform','service','activity','outcome','international')
                THEN 'open' ELSE 'related' END AS section_id,
           category_id,date_kind,0 AS relevance,
           CASE WHEN date_kind='event' THEN '政策事件' ELSE '公开报道' END AS record_type
    FROM media_index WHERE {MEDIA_VISIBLE}
)"""


def article_where(query):
    clauses, params = [], []
    for key, column in (("category", "category_id"), ("source", "source_id"),
                        ("region", "source_region"), ("country", "source_country"),
                        ("province", "province")):
        value = query_arg(query, key)
        if value:
            clauses.append(column + "=?")
            params.append(value)
    scope = query_arg(query, "scope")
    if scope == "china":
        clauses.append("source_country='中国'")
    elif scope == "international":
        clauses.append("source_country!='中国'")
    elif scope:
        raise ValueError("范围无效")
    text = query_arg(query, "q").strip()
    if text:
        clauses.append("(title LIKE ? OR title_zh LIKE ? OR summary LIKE ? OR brief_zh LIKE ?)")
        params.extend(["%" + text + "%"] * 4)
    month = query_arg(query, "month")
    if month:
        if not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", month):
            raise ValueError("月份格式无效")
        clauses.append("published_at LIKE ?")
        params.append(month + "%")
    return (" WHERE " + " AND ".join(clauses)) if clauses else "", params


def get_articles(query):
    where, params = article_where(query)
    limit = min(max(int(query_arg(query, "limit", "20")), 1), 100)
    offset = min(max(int(query_arg(query, "offset", "0")), 0), 100000)
    with connect() as db:
        total = db.execute(FEED_CTE + " SELECT COUNT(*) FROM feed" + where, params).fetchone()[0]
        rows = db.execute(
            FEED_CTE + " SELECT * FROM feed" + where +
            " ORDER BY published_at DESC, collected_at DESC LIMIT ? OFFSET ?",
            params + [limit, offset],
        ).fetchall()
    return {"total": total, "items": [public_article(row) for row in rows]}


def export_articles(query):
    where, params = article_where(query)
    with connect() as db:
        rows = db.execute(
            FEED_CTE + " SELECT * FROM feed" + where +
            " ORDER BY published_at DESC,collected_at DESC LIMIT 5000", params).fetchall()
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(["标题", "原文标题", "主题", "记录类型", "国家或地区", "省市", "日期类型", "日期", "来源", "原文链接"])
    for row in rows:
        item = public_article(row)
        writer.writerow([
            item["title_zh"] or item["title"], item["title"], PUBLIC_NAMES.get(item["category_id"], "数据治理"),
            item["record_type"], item["source_country"], item["province"],
            "事件日期" if item["date_kind"] == "event" else "发布日期", item["published_at"],
            item["source_name"], item["url"],
        ])
    return output.getvalue().encode("utf-8-sig")


def get_media_index(query):
    clauses = [MEDIA_VISIBLE]
    params = []
    search = query_arg(query, "q").strip()
    if search:
        clauses.append("(title LIKE ? OR title_zh LIKE ? OR publisher LIKE ?)")
        params.extend(["%" + search + "%"] * 3)
    category = query_arg(query, "category")
    if category:
        if category not in PUBLIC_NAMES:
            raise ValueError("主题无效")
        clauses.append("category_id=?")
        params.append(category)
    month = query_arg(query, "month")
    if month:
        if not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", month):
            raise ValueError("月份格式无效")
        clauses.append("published_at LIKE ?")
        params.append(month + "%")
    limit = min(max(int(query_arg(query, "limit", "20")), 1), 100)
    offset = min(max(int(query_arg(query, "offset", "0")), 0), 100000)
    where = " WHERE " + " AND ".join(clauses)
    with connect() as db:
        total = db.execute("SELECT COUNT(*) FROM media_index" + where, params).fetchone()[0]
        rows = [dict(row) for row in db.execute(
            "SELECT id,title,title_zh,url,publisher,published_at,category_id,language FROM media_index" + where +
            " ORDER BY published_at DESC LIMIT ? OFFSET ?", params + [limit, offset])]
    return {"total": total, "items": rows}


def dashboard():
    today_start = datetime.now(ZoneInfo("Asia/Shanghai")).replace(
        hour=0, minute=0, second=0, microsecond=0)
    utc_start = today_start.astimezone(timezone.utc).isoformat(timespec="seconds")
    utc_end = (today_start + timedelta(days=1)).astimezone(timezone.utc).isoformat(timespec="seconds")
    with connect() as db:
        total = db.execute(FEED_CTE + " SELECT COUNT(*) FROM feed").fetchone()[0]
        institution_total = db.execute(f"SELECT COUNT(*) FROM articles WHERE {VISIBLE}").fetchone()[0]
        media_total = db.execute(f"SELECT COUNT(*) FROM media_index WHERE {MEDIA_VISIBLE}").fetchone()[0]
        media_publishers = db.execute(f"SELECT COUNT(DISTINCT publisher) FROM media_index WHERE {MEDIA_VISIBLE}").fetchone()[0]
        today = db.execute(
            FEED_CTE + " SELECT COUNT(*) FROM feed WHERE collected_at>=? AND collected_at<?",
            (utc_start, utc_end),
        ).fetchone()[0]
        groups = [dict(row) for row in db.execute(
            FEED_CTE + " SELECT category_id, COUNT(*) AS count FROM feed "
            "GROUP BY category_id ORDER BY count DESC")]
        countries = [dict(row) for row in db.execute(
            FEED_CTE + " SELECT source_country AS name, COUNT(*) AS count FROM feed "
            "WHERE source_country NOT IN ('','未定位') GROUP BY source_country ORDER BY count DESC")]
        china_count = db.execute(FEED_CTE + " SELECT COUNT(*) FROM feed WHERE source_country='中国'").fetchone()[0]
        provinces = [dict(row) for row in db.execute(
            FEED_CTE + " SELECT province AS name, COUNT(*) AS count FROM feed WHERE "
            "source_country='中国' AND province!='' GROUP BY province ORDER BY count DESC")]
        daily_rows = [dict(row) for row in db.execute(
            FEED_CTE + " SELECT date(published_at, '+8 hours') AS day, COUNT(*) AS count "
            "FROM feed WHERE published_at IS NOT NULL "
            "GROUP BY day ORDER BY day DESC LIMIT 30")]
        latest = db.execute(
            "SELECT MAX(updated_at) AS finished_at FROM ("
            "SELECT MAX(finished_at) AS updated_at FROM runs "
            "UNION ALL SELECT MAX(collected_at) AS updated_at FROM articles "
            f"WHERE {VISIBLE} "
            "UNION ALL SELECT MAX(collected_at) AS updated_at FROM media_index "
            f"WHERE {MEDIA_VISIBLE})").fetchone()
    daily = {row["day"]: row["count"] for row in daily_rows if row["day"]}
    days = [(today_start.date() - timedelta(days=offset)).isoformat() for offset in range(13, -1, -1)]
    return {"total": total, "institution_total": institution_total,
            "media_total": media_total, "media_publishers": media_publishers,
            "today": today, "source_count": len(SOURCES),
            "topic_count": len(PUBLIC_NAMES), "category_counts": groups,
            "country_counts": countries, "province_counts": provinces,
            "country_count": sum(row["name"] not in ("欧盟", "国际组织") for row in countries),
            "province_count": len(provinces),
            "china_count": china_count,
            "trend": [{"day": day, "count": daily.get(day, 0)} for day in days],
            "last_updated": latest["finished_at"] if latest else None}


def heatmap(query):
    period = query_arg(query, "period", "week")
    if period not in ("week", "previous", "all"):
        raise ValueError("时间范围无效")
    today = datetime.now(ZoneInfo("Asia/Shanghai")).date()
    this_monday = today - timedelta(days=today.weekday())
    if period == "week":
        first_date, through_date = this_monday, today
    elif period == "previous":
        first_date = this_monday - timedelta(days=7)
        through_date = this_monday - timedelta(days=1)
    else:
        first_date = datetime.fromisoformat(COLLECTION_START_DATE).date()
        through_date = today
    first = max(first_date.isoformat(), COLLECTION_START_DATE)
    constraint = "date(published_at, '+8 hours') BETWEEN ? AND ?"
    with connect() as db:
        world_rows = [dict(row) for row in db.execute(
            FEED_CTE + " SELECT source_country AS name,COUNT(*) AS count FROM feed WHERE " +
            constraint + " AND source_country NOT IN ('中国','未定位','') " +
            "GROUP BY source_country ORDER BY count DESC", (first, through_date.isoformat()))]
        china_rows = [dict(row) for row in db.execute(
            FEED_CTE + " SELECT province AS name,COUNT(*) AS count FROM feed WHERE " +
            constraint + " AND source_country='中国' AND province!='' " +
            "GROUP BY province ORDER BY count DESC", (first, through_date.isoformat()))]
        unmatched = db.execute(FEED_CTE + " SELECT COUNT(*) FROM feed WHERE " + constraint +
                               " AND source_country='未定位'", (first, through_date.isoformat())).fetchone()[0]
    def indexed(rows):
        maximum = max((row["count"] for row in rows), default=0)
        return [{**row, "index": round(row["count"] / maximum * 100) if maximum else 0}
                for row in rows]
    return {"period": period, "from_date": first, "through_date": through_date.isoformat(),
            "world": indexed(world_rows), "china": indexed(china_rows),
            "unlocated": unmatched,
            "method": "指数=该范围收录条数÷本图最高地区条数×100；仅表示本平台检出的资讯密度。"}


def location_spotlight(query):
    kind = query_arg(query, "kind")
    name = query_arg(query, "name").strip()
    if kind not in ("country", "province") or not name or len(name) > 60:
        raise ValueError("地区参数无效")
    if kind == "country":
        where, params = "source_country=?", [name]
    else:
        where, params = "source_country='中国' AND province=?", [name]
    with connect() as db:
        total = db.execute(FEED_CTE + " SELECT COUNT(*) FROM feed WHERE " + where, params).fetchone()[0]
        topics = [dict(row) for row in db.execute(
            FEED_CTE + " SELECT category_id,COUNT(*) AS count FROM feed WHERE " + where +
            " GROUP BY category_id ORDER BY count DESC,category_id LIMIT 4", params)]
        sources = [dict(row) for row in db.execute(
            FEED_CTE + " SELECT source_name,COUNT(*) AS count FROM feed WHERE " + where +
            " GROUP BY source_name ORDER BY count DESC,source_name LIMIT 4", params)]
        latest = db.execute(
            FEED_CTE + " SELECT * FROM feed WHERE " + where +
            " ORDER BY published_at DESC,collected_at DESC LIMIT 1", params).fetchone()
    return {"kind": kind, "name": name, "total": total,
            "topics": [{"id": row["category_id"], "name": PUBLIC_NAMES.get(row["category_id"], "数据治理"),
                        "count": row["count"]} for row in topics],
            "sources": sources, "latest": public_article(latest) if latest else None}


def source_list():
    with connect() as db:
        counts = {row["source_id"]: row["count"] for row in db.execute(
            f"SELECT source_id, COUNT(*) AS count FROM articles WHERE {VISIBLE} GROUP BY source_id")}
        publishers = [dict(row) for row in db.execute(
            "SELECT publisher,COUNT(*) AS total,COUNT(DISTINCT scope) AS scope_count,"
            "MAX(scope) AS scope FROM media_index WHERE " + MEDIA_VISIBLE +
            " GROUP BY publisher ORDER BY total DESC,publisher")]
    direct = [{"id": source["id"], "name": source["name"],
             "region": source["region"], "country": source["country"],
             "province": source.get("province", ""), "url": source["url"],
             "scope": "china" if source["country"] == "中国" else "international",
             "total": counts.get(source["id"], 0)} for source in SOURCES]
    media = [{"id": "media:" + row["publisher"], "name": row["publisher"],
              "region": "", "country": "中国" if row["scope"] == "china" and row["scope_count"] == 1 else "",
              "province": "", "url": "", "scope": row["scope"] if row["scope_count"] == 1 else "mixed",
              "total": row["total"]} for row in publishers]
    return direct + media


def digest_weeks():
    with connect() as db:
        rows = db.execute(
            FEED_CTE + " SELECT date(published_at, '+8 hours') AS day, COUNT(*) AS count "
            "FROM feed WHERE published_at IS NOT NULL GROUP BY day HAVING day IS NOT NULL"
        ).fetchall()
    totals = Counter()
    for row in rows:
        day = datetime.strptime(row["day"], "%Y-%m-%d").date()
        monday = day - timedelta(days=day.weekday())
        totals[monday.isoformat()] += row["count"]
    today = datetime.now(ZoneInfo("Asia/Shanghai")).date()
    return [{"week_start": start, "week_end": min(
                datetime.fromisoformat(start).date() + timedelta(days=6), today).isoformat(),
             "count": count}
            for start, count in sorted(totals.items(), reverse=True)]


def week_bounds(week_start):
    if not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01])", week_start):
        raise ValueError("周起始日期格式无效")
    try:
        start = datetime.strptime(week_start, "%Y-%m-%d").date()
    except ValueError as exc:
        raise ValueError("周起始日期无效") from exc
    if start.weekday() != 0:
        raise ValueError("周起始日期必须是周一")
    today = datetime.now(ZoneInfo("Asia/Shanghai")).date()
    first = max(start.isoformat(), COLLECTION_START_DATE)
    end = min(start + timedelta(days=6), today).isoformat()
    return first, end


def automatic_weekly_analysis(items, topic_counts, country_counts):
    if not items:
        return None
    selected, seen = [], set()
    for item in items:
        identity = item["source_id"]
        if identity in seen and len(selected) < 3:
            continue
        selected.append(item)
        seen.add(identity)
        if len(selected) >= 5:
            break
    top_topic = topic_counts[0] if topic_counts else {"name": "数据治理", "count": len(items)}
    international = [item for item in items if item["source_country"] != "中国"]
    china = [item for item in items if item["source_country"] == "中国"]
    named_places = [entry["name"] for entry in country_counts if entry["name"] not in ("", "未定位")][:4]
    events = [{
        "title": item["title_zh"] or item["title"],
        "summary": item["brief_zh"] or item["summary"] or "本周公开来源记录了这项数据治理动态，详情可通过所附原文核对。",
        "article_ids": [item["id"]],
    } for item in selected]
    evidence = [item["id"] for item in selected[:3]]
    insights = [{
        "title": "本周议题重心",
        "analysis": f"{top_topic['name']}是本周收录最多的议题，共 {top_topic['count']} 条。该分布反映公开发布的资讯密度，可用来识别近期政策与实践关注点。",
        "article_ids": evidence,
    }]
    if international and china:
        insights.append({
            "title": "国际与国内进展并行",
            "analysis": f"本周收录国际动态 {len(international)} 条、国内动态 {len(china)} 条。国际部分覆盖监管和跨境规则，国内部分呈现公共数据与地方实践，两类进展共同构成本周观察窗口。",
            "article_ids": [international[0]["id"], china[0]["id"]],
        })
    return {
        "headline": f"{top_topic['name']}成为本周高频议题，多地数据治理动态持续推进",
        "overview": f"本周共收录 {len(items)} 条公开动态，涉及 {len(country_counts)} 个可识别国家或地区。" +
                    (("较活跃地区包括" + "、".join(named_places) + "。") if named_places else "") +
                    "以下先梳理代表性事件，再依据本周已收录来源归纳共同趋势。",
        "events": events,
        "insights": insights,
        "generated_by": "statistics",
    }


def weekly_digest(week_start):
    first, end = week_bounds(week_start)
    with connect() as db:
        rows = db.execute(
            FEED_CTE + " SELECT * FROM feed WHERE "
            "date(published_at, '+8 hours') BETWEEN ? AND ? "
            "ORDER BY relevance DESC, published_at DESC",
            (first, end),
        ).fetchall()
    items = [public_article(row) for row in rows]
    topics = Counter(item["category_id"] for item in items)
    countries = Counter(item["source_country"] for item in items if item["source_country"])
    provinces = Counter(item["province"] for item in items if item["province"])
    topic_counts = [{"id": key, "name": PUBLIC_NAMES[key], "count": count}
                    for key, count in topics.most_common()]
    country_counts = [{"name": key, "count": count} for key, count in countries.most_common()]
    analysis = load_report(week_start, items) or automatic_weekly_analysis(items, topic_counts, country_counts)
    return {"week_start": week_start, "from_date": first, "through_date": end, "total": len(items),
            "source_count": len({item["source_id"] for item in items}),
            "topic_counts": topic_counts,
            "country_counts": country_counts,
            "province_counts": [{"name": key, "count": count} for key, count in provinces.most_common()],
            "items": items, "analysis": analysis}


def digest_markdown(report):
    period = report["from_date"] + "—" + report["through_date"]
    lines = [f"# 全球数据治理周报｜{period}", "", "按本周报道发布日期或政策事件日期汇总公开资讯。", "",
             f"本期共 {report['total']} 条动态，来自 {report['source_count']} 个记录来源。", ""]
    if not report["items"]:
        lines.extend(["本周暂无新收录动态。", ""])
    analysis = report.get("analysis")
    if analysis:
        by_id = {item["id"]: item for item in report["items"]}
        lines.extend(["## 本周概览", "", "### " + analysis["headline"], "", analysis["overview"], "", "## 主要事件", ""])
        for event in analysis["events"]:
            lines.extend(["### " + event["title"], "", event["summary"], "", "依据："])
            for item_id in event["article_ids"]:
                item = by_id[item_id]
                lines.append(f"- [{item['title_zh'] or item['title']}]({item['url']})｜{item['source_name']}")
            lines.append("")
        lines.extend(["## 整合分析", ""])
        for insight in analysis["insights"]:
            lines.extend(["### " + insight["title"], "", insight["analysis"], "", "依据："])
            for item_id in insight["article_ids"]:
                item = by_id[item_id]
                lines.append(f"- [{item['title_zh'] or item['title']}]({item['url']})｜{item['source_name']}")
            lines.append("")
        lines.extend(["## 资讯索引", ""])
    for scope, group_name in (("international", "国际动态"), ("china", "国内动态")):
        group_items = [item for item in report["items"]
                       if (item["source_country"] == "中国") == (scope == "china")]
        if not group_items:
            continue
        lines.extend(["## " + group_name, ""])
        for section in PUBLIC_SECTIONS:
            section_items = [item for item in group_items if item["section_id"] == section["id"]]
            if not section_items:
                continue
            lines.extend(["### " + section["name"], ""])
            for category in section["categories"]:
                entries = [item for item in section_items if item["category_id"] == category["id"]]
                for item in entries:
                    title = item["title_zh"] or item["title"]
                    place = item["province"] or item["source_country"]
                    date_label = "事件日期" if item["date_kind"] == "event" else "发布日期"
                    lines.append(f"- [{title}]({item['url']})｜{item['source_name']} · {place} · {date_label} {item['published_at'][:10]}")
                    brief = item["brief_zh"] or item["summary"]
                    if brief:
                        lines.append("  - " + brief)
            lines.append("")
    lines.extend(["---", "内容以链接中的来源原文为准；政策事件日期与报道发布日期分别标注。", ""])
    return "\n".join(lines)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        print("[%s] %s" % (self.log_date_time_string(), format % args), flush=True)

    def send_json(self, data, status=200, headers=None):
        raw = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        for name, value in (headers or {}).items():
            self.send_header(name, value)
        self.end_headers()
        self.wfile.write(raw)

    def read_json(self):
        try:
            length = min(int(self.headers.get("Content-Length", "0")), 20_000)
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
            if not isinstance(payload, dict):
                raise ValueError
            return payload
        except (ValueError, json.JSONDecodeError, UnicodeDecodeError):
            return None

    def current_user(self):
        return user_for_token(token_from_headers(self.headers))

    def redirect(self, location):
        self.send_response(303)
        self.send_header("Location", location)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def send_file(self, path):
        path = path.resolve()
        if not path.is_file() or STATIC_DIR.resolve() not in path.parents:
            self.send_error(404)
            return
        raw = path.read_bytes()
        content_type = ("application/geo+json" if path.suffix == ".geojson"
                        else mimetypes.guess_type(path.name)[0] or "application/octet-stream")
        self.send_response(200)
        self.send_header("Content-Type", content_type + ("; charset=utf-8" if content_type.startswith("text/") else ""))
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        parsed = urlsplit(self.path)
        query = parse_qs(parsed.query)
        path = parsed.path
        if path == "/api/health":
            return self.send_json({"ok": True})
        if path == "/api/auth/config":
            return self.send_json({"required": REQUIRE_LOGIN, "allow_registration": ALLOW_REGISTRATION})
        if path == "/api/auth/me":
            user = self.current_user()
            return self.send_json({"authenticated": bool(user), "user": user})
        if path == "/login":
            if self.current_user():
                return self.redirect("/")
            return self.send_file(STATIC_DIR / "login.html")
        if REQUIRE_LOGIN and not self.current_user():
            if path.startswith("/api/"):
                return self.send_json({"error": "请先登录"}, 401)
            if path not in ("/login.js", "/login.css"):
                return self.redirect("/login")
        if path == "/api/config":
            return self.send_json({"sections": PUBLIC_SECTIONS, "categories": PUBLIC_NAMES,
                                   "start_date": COLLECTION_START_DATE})
        if path == "/api/dashboard":
            return self.send_json(dashboard())
        if path == "/api/heatmap":
            try:
                return self.send_json(heatmap(query))
            except ValueError:
                return self.send_json({"error": "时间范围无效"}, 400)
        if path == "/api/spotlight":
            try:
                return self.send_json(location_spotlight(query))
            except ValueError:
                return self.send_json({"error": "地区参数无效"}, 400)
        if path == "/api/articles":
            try:
                return self.send_json(get_articles(query))
            except ValueError:
                return self.send_json({"error": "筛选或分页参数无效"}, 400)
        if path == "/api/articles.csv":
            try:
                raw = export_articles(query)
            except ValueError:
                return self.send_json({"error": "筛选参数无效"}, 400)
            self.send_response(200)
            self.send_header("Content-Type", "text/csv; charset=utf-8")
            self.send_header("Content-Disposition", 'attachment; filename="data-governance-updates.csv"')
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            return self.wfile.write(raw)
        if path == "/api/media":
            try:
                return self.send_json(get_media_index(query))
            except ValueError:
                return self.send_json({"error": "筛选或分页参数无效"}, 400)
        if path == "/api/sources":
            return self.send_json({"items": source_list()})
        if path == "/api/digests":
            return self.send_json({"items": digest_weeks()})
        if path in ("/api/digest", "/api/digest.md"):
            weeks = digest_weeks()
            default_week = weeks[0]["week_start"] if weeks else (
                datetime.now(ZoneInfo("Asia/Shanghai")).date() - timedelta(
                    days=datetime.now(ZoneInfo("Asia/Shanghai")).date().weekday())).isoformat()
            week_start = query_arg(query, "week", default_week)
            try:
                report = weekly_digest(week_start)
            except ValueError:
                return self.send_json({"error": "周起始日期格式无效"}, 400)
            if path == "/api/digest":
                return self.send_json(report)
            raw = digest_markdown(report).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/markdown; charset=utf-8")
            self.send_header("Content-Disposition", f'attachment; filename="data-governance-weekly-{week_start}.md"')
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            return self.wfile.write(raw)
        if path == "/":
            return self.send_file(STATIC_DIR / "index.html")
        if path.startswith("/api/"):
            return self.send_json({"error": "未找到接口"}, 404)
        return self.send_file(STATIC_DIR / path.lstrip("/"))

    def do_POST(self):
        path = urlsplit(self.path).path
        if path == "/api/auth/logout":
            delete_session(token_from_headers(self.headers))
            return self.send_json({"ok": True}, headers={"Set-Cookie": clear_cookie()})
        if path not in ("/api/auth/login", "/api/auth/register"):
            return self.send_json({"error": "此页面仅提供公开资讯浏览"}, 405)
        payload = self.read_json()
        if payload is None:
            return self.send_json({"error": "请求格式无效"}, 400)
        email = str(payload.get("email", ""))
        password = str(payload.get("password", ""))
        try:
            if path.endswith("register"):
                if not ALLOW_REGISTRATION:
                    return self.send_json({"error": "当前未开放注册"}, 403)
                user = create_user(email, password)
            else:
                user = authenticate(email, password)
                if not user:
                    return self.send_json({"error": "邮箱或密码不正确"}, 401)
            token = create_session(user["id"])
            return self.send_json({"ok": True, "user": user},
                                  headers={"Set-Cookie": session_cookie(token)})
        except ValueError as exc:
            return self.send_json({"error": str(exc)}, 400)

    def do_PATCH(self):
        return self.send_json({"error": "此页面仅提供公开资讯浏览"}, 405)


if __name__ == "__main__":
    initialize()
    initialize_auth()
    start_scheduler()
    host = os.environ.get("MONITOR_HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", os.environ.get("MONITOR_PORT", "8765")))
    print(f"全球数据治理追踪器：http://{host}:{port}", flush=True)
    ThreadingHTTPServer((host, port), Handler).serve_forever()
