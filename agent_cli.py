"""Apply curated Chinese metadata to the local news database.

    python3 agent_cli.py pending --run-id latest
    python3 agent_cli.py apply /path/to/reviewed.json

The apply command updates title, summary, and category metadata only.
"""

import argparse
import json
from pathlib import Path

from config import CATEGORY_NAMES, SECTION_BY_CATEGORY
from storage import connect, initialize


def pending(run_id):
    initialize()
    with connect() as db:
        if run_id == "latest":
            row = db.execute("SELECT id,started_at,finished_at FROM runs ORDER BY id DESC LIMIT 1").fetchone()
            if row is None:
                return {"run_id": None, "items": []}
            run_id = row["id"]
        else:
            row = db.execute("SELECT id,started_at,finished_at FROM runs WHERE id=?", (int(run_id),)).fetchone()
            if row is None:
                raise ValueError("运行记录不存在")
        items = [dict(item) for item in db.execute("""SELECT id,title,summary,category_id,source_name,published_at,url
            FROM articles WHERE collected_at>=? AND collected_at<=? AND enrichment_model=''
            ORDER BY relevance DESC,published_at DESC LIMIT 60""",
            (row["started_at"], row["finished_at"] or "9999"))]
    return {"run_id": run_id, "categories": CATEGORY_NAMES, "items": items}


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
            item_id = item.get("id", "")
            category = item.get("category_id", "")
            title_zh = str(item.get("title_zh", "")).strip()
            brief_zh = str(item.get("brief_zh", "")).strip()
            if not isinstance(item_id, str) or len(item_id) != 24 or category not in CATEGORY_NAMES:
                continue
            if not title_zh or not brief_zh or len(title_zh) > 140 or len(brief_zh) > 200:
                continue
            cursor = db.execute("""UPDATE articles SET category_id=?,section_id=?,title_zh=?,brief_zh=?,
                enrichment_model='中文整理',classification_reason='自动分类与中文整理'
                WHERE id=? AND status='待审核'""",
                (category, SECTION_BY_CATEGORY[category], title_zh, brief_zh, item_id))
            count += cursor.rowcount
    return {"updated": count, "submitted": len(payload)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    read = sub.add_parser("pending")
    read.add_argument("--run-id", default="latest")
    write = sub.add_parser("apply")
    write.add_argument("file")
    args = parser.parse_args()
    print(json.dumps(pending(args.run_id) if args.command == "pending" else apply(args.file), ensure_ascii=False, indent=2))
