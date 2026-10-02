"""SQLite persistence shared by collector and web app."""

import shutil
import sqlite3
from datetime import datetime, timezone

from config import BASE_DIR, DB_PATH, SOURCES


def utc_now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def connect():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(DB_PATH, timeout=20)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA foreign_keys=ON")
    return db


def initialize():
    seed = BASE_DIR / "data" / "news.sqlite3"
    if DB_PATH != seed and not DB_PATH.exists() and seed.is_file():
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(seed, DB_PATH)
    with connect() as db:
        db.executescript("""
        CREATE TABLE IF NOT EXISTS articles (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            title_zh TEXT NOT NULL DEFAULT '',
            summary TEXT NOT NULL DEFAULT '',
            brief_zh TEXT NOT NULL DEFAULT '',
            url TEXT NOT NULL UNIQUE,
            source_id TEXT NOT NULL,
            source_name TEXT NOT NULL,
            source_region TEXT NOT NULL,
            source_country TEXT NOT NULL DEFAULT '',
            province TEXT NOT NULL DEFAULT '',
            published_at TEXT,
            collected_at TEXT NOT NULL,
            section_id TEXT NOT NULL,
            category_id TEXT NOT NULL,
            relevance INTEGER NOT NULL DEFAULT 0,
            classification_reason TEXT NOT NULL DEFAULT '',
            enrichment_model TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT '待审核',
            starred INTEGER NOT NULL DEFAULT 0
        );
        CREATE INDEX IF NOT EXISTS idx_articles_published ON articles(published_at DESC);
        CREATE INDEX IF NOT EXISTS idx_articles_category ON articles(category_id);
        CREATE TABLE IF NOT EXISTS runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            started_at TEXT NOT NULL,
            finished_at TEXT,
            status TEXT NOT NULL,
            added INTEGER NOT NULL DEFAULT 0,
            checked INTEGER NOT NULL DEFAULT 0,
            errors TEXT NOT NULL DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS source_state (
            source_id TEXT PRIMARY KEY,
            last_checked TEXT,
            last_success TEXT,
            last_error TEXT,
            last_count INTEGER NOT NULL DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS media_index (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            title_zh TEXT NOT NULL DEFAULT '',
            url TEXT NOT NULL UNIQUE,
            publisher TEXT NOT NULL,
            published_at TEXT NOT NULL,
            category_id TEXT NOT NULL,
            language TEXT NOT NULL DEFAULT 'en',
            scope TEXT NOT NULL DEFAULT 'international',
            province TEXT NOT NULL DEFAULT '',
            country TEXT NOT NULL DEFAULT '',
            date_kind TEXT NOT NULL DEFAULT 'published',
            status TEXT NOT NULL DEFAULT 'published',
            collected_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_media_index_published ON media_index(published_at DESC);
        """)
        columns = {row["name"] for row in db.execute("PRAGMA table_info(articles)")}
        media_columns = {row["name"] for row in db.execute("PRAGMA table_info(media_index)")}
        if "title_zh" not in media_columns:
            db.execute("ALTER TABLE media_index ADD COLUMN title_zh TEXT NOT NULL DEFAULT ''")
        if "language" not in media_columns:
            db.execute("ALTER TABLE media_index ADD COLUMN language TEXT NOT NULL DEFAULT 'en'")
        if "status" not in media_columns:
            db.execute("ALTER TABLE media_index ADD COLUMN status TEXT NOT NULL DEFAULT 'published'")
        if "scope" not in media_columns:
            db.execute("ALTER TABLE media_index ADD COLUMN scope TEXT NOT NULL DEFAULT 'international'")
        if "province" not in media_columns:
            db.execute("ALTER TABLE media_index ADD COLUMN province TEXT NOT NULL DEFAULT ''")
        if "country" not in media_columns:
            db.execute("ALTER TABLE media_index ADD COLUMN country TEXT NOT NULL DEFAULT ''")
        if "date_kind" not in media_columns:
            db.execute("ALTER TABLE media_index ADD COLUMN date_kind TEXT NOT NULL DEFAULT 'published'")
        if "source_country" not in columns:
            db.execute("ALTER TABLE articles ADD COLUMN source_country TEXT NOT NULL DEFAULT ''")
        if "province" not in columns:
            db.execute("ALTER TABLE articles ADD COLUMN province TEXT NOT NULL DEFAULT ''")
        for source in SOURCES:
            db.execute("UPDATE articles SET source_country=? WHERE source_id=? AND source_country=''",
                       (source["country"], source["id"]))
            if source.get("province"):
                db.execute("UPDATE articles SET province=? WHERE source_id=? AND province=''",
                           (source["province"], source["id"]))
        for source in SOURCES:
            db.execute("INSERT OR IGNORE INTO source_state(source_id) VALUES (?)", (source["id"],))


def article_dict(row):
    item = dict(row)
    item["starred"] = bool(item["starred"])
    return item
