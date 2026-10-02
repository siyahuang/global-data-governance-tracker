"""Source-bound weekly analysis storage and validation."""

import hashlib
import json
from pathlib import Path

from config import DATA_DIR

REPORT_DIR = DATA_DIR / "weekly-reports"


def fingerprint(items):
    relevant = [{key: item.get(key, "") for key in
                 ("id", "title", "title_zh", "summary", "brief_zh", "category_id")}
                for item in sorted(items, key=lambda row: row["id"])]
    raw = json.dumps(relevant, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def validate(report, items):
    if not isinstance(report, dict):
        raise ValueError("周报必须是 JSON 对象")
    valid_ids = {item["id"] for item in items}
    if not valid_ids:
        raise ValueError("该周没有可用资讯")
    for field, maximum in (("headline", 120), ("overview", 1000)):
        value = report.get(field)
        if not isinstance(value, str) or not value.strip() or len(value) > maximum:
            raise ValueError(field + " 为空或过长")
    events = report.get("events")
    if not isinstance(events, list) or not 1 <= len(events) <= 10:
        raise ValueError("events 应为 1 至 10 条主要事件")
    for event in events:
        if not isinstance(event, dict):
            raise ValueError("event 格式无效")
        for field, maximum in (("title", 120), ("summary", 700)):
            value = event.get(field)
            if not isinstance(value, str) or not value.strip() or len(value) > maximum:
                raise ValueError("event." + field + " 为空或过长")
        ids = event.get("article_ids")
        if not isinstance(ids, list) or not ids or not all(
                isinstance(value, str) and value in valid_ids for value in ids):
            raise ValueError("event.article_ids 必须引用本周资讯")
    insights = report.get("insights")
    if not isinstance(insights, list) or not 1 <= len(insights) <= 5:
        raise ValueError("insights 应为 1 至 5 条")
    for insight in insights:
        if not isinstance(insight, dict):
            raise ValueError("insight 格式无效")
        for field, maximum in (("title", 100), ("analysis", 800)):
            value = insight.get(field)
            if not isinstance(value, str) or not value.strip() or len(value) > maximum:
                raise ValueError("insight." + field + " 为空或过长")
        ids = insight.get("article_ids")
        if not isinstance(ids, list) or not ids or not all(
                isinstance(value, str) and value in valid_ids for value in ids):
            raise ValueError("insight.article_ids 必须引用本周资讯")
    cited = {item_id for section in events + insights for item_id in section["article_ids"]}
    if len(items) > 1 and len(cited) < min(len(items), 3):
        raise ValueError("多条资讯的周报至少引用三条来源")


def load_report(week_start, items):
    path = REPORT_DIR / (week_start + ".json")
    if not path.is_file():
        return None
    try:
        stored = json.loads(path.read_text(encoding="utf-8"))
        if stored.get("fingerprint") != fingerprint(items):
            return None
        validate(stored, items)
        return {key: stored[key] for key in ("headline", "overview", "events", "insights")}
    except (ValueError, KeyError, TypeError):
        return None


def save_report(week_start, report, items):
    validate(report, items)
    stored = {key: report[key] for key in ("headline", "overview", "events", "insights")}
    stored["week_start"] = week_start
    stored["fingerprint"] = fingerprint(items)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    (REPORT_DIR / (week_start + ".json")).write_text(
        json.dumps(stored, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
