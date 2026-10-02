"""Small built-in account and session layer for private cloud deployments."""

import hashlib
import hmac
import os
import re
import secrets
from datetime import datetime, timedelta, timezone
from http.cookies import SimpleCookie

from storage import connect, utc_now

SESSION_COOKIE = "tracker_session"
SESSION_DAYS = 14
EMAIL_PATTERN = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


def initialize_auth():
    with connect() as db:
        db.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT NOT NULL UNIQUE COLLATE NOCASE,
            password_hash TEXT NOT NULL,
            salt TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'reader',
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS sessions (
            token_hash TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            expires_at TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_sessions_expires ON sessions(expires_at);
        """)
    email = os.environ.get("ADMIN_EMAIL", "").strip().lower()
    password = os.environ.get("ADMIN_PASSWORD", "")
    if email and password:
        with connect() as db:
            exists = db.execute("SELECT 1 FROM users WHERE email=?", (email,)).fetchone()
        if not exists:
            create_user(email, password, "admin")


def password_digest(password, salt):
    return hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), 260_000).hex()


def validate_credentials(email, password):
    email = email.strip().lower()
    if not EMAIL_PATTERN.fullmatch(email) or len(email) > 180:
        raise ValueError("请输入有效邮箱")
    if len(password) < 10 or len(password) > 200:
        raise ValueError("密码至少需要 10 位")
    return email


def create_user(email, password, role="reader"):
    email = validate_credentials(email, password)
    salt = secrets.token_hex(16)
    try:
        with connect() as db:
            user_id = db.execute(
                "INSERT INTO users(email,password_hash,salt,role,created_at) VALUES (?,?,?,?,?)",
                (email, password_digest(password, salt), salt, role, utc_now()),
            ).lastrowid
    except Exception as exc:
        if "UNIQUE" in str(exc).upper():
            raise ValueError("该邮箱已注册") from exc
        raise
    return {"id": user_id, "email": email, "role": role}


def authenticate(email, password):
    email = email.strip().lower()
    with connect() as db:
        row = db.execute("SELECT id,email,password_hash,salt,role FROM users WHERE email=?", (email,)).fetchone()
    if not row or not hmac.compare_digest(password_digest(password, row["salt"]), row["password_hash"]):
        return None
    return {"id": row["id"], "email": row["email"], "role": row["role"]}


def create_session(user_id):
    token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    expires = datetime.now(timezone.utc) + timedelta(days=SESSION_DAYS)
    with connect() as db:
        db.execute("DELETE FROM sessions WHERE expires_at<?", (utc_now(),))
        db.execute("INSERT INTO sessions(token_hash,user_id,expires_at,created_at) VALUES (?,?,?,?)",
                   (token_hash, user_id, expires.isoformat(timespec="seconds"), utc_now()))
    return token


def token_from_headers(headers):
    cookie = SimpleCookie()
    cookie.load(headers.get("Cookie", ""))
    morsel = cookie.get(SESSION_COOKIE)
    return morsel.value if morsel else ""


def user_for_token(token):
    if not token:
        return None
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    with connect() as db:
        row = db.execute("""SELECT users.id,users.email,users.role,sessions.expires_at
            FROM sessions JOIN users ON users.id=sessions.user_id
            WHERE sessions.token_hash=? AND sessions.expires_at>?""", (token_hash, utc_now())).fetchone()
    return {"id": row["id"], "email": row["email"], "role": row["role"]} if row else None


def delete_session(token):
    if token:
        with connect() as db:
            db.execute("DELETE FROM sessions WHERE token_hash=?", (hashlib.sha256(token.encode()).hexdigest(),))


def session_cookie(token):
    secure = "; Secure" if os.environ.get("COOKIE_SECURE", "1") == "1" else ""
    return (f"{SESSION_COOKIE}={token}; Path=/; HttpOnly; SameSite=Lax; "
            f"Max-Age={SESSION_DAYS * 86400}{secure}")


def clear_cookie():
    secure = "; Secure" if os.environ.get("COOKIE_SECURE", "1") == "1" else ""
    return f"{SESSION_COOKIE}=; Path=/; HttpOnly; SameSite=Lax; Max-Age=0{secure}"
