"""Run the collector pipeline every six hours inside a single cloud service."""

import json
import os
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone

from config import BASE_DIR, DATA_DIR

INTERVAL_SECONDS = int(os.environ.get("UPDATE_INTERVAL_SECONDS", str(6 * 60 * 60)))
STATE_PATH = DATA_DIR / "scheduler-state.json"
LOCK_PATH = DATA_DIR / "scheduler.lock"


def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def write_state(status, detail=""):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps({"status": status, "updated_at": now_iso(), "detail": detail},
                                     ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def due():
    if not STATE_PATH.is_file():
        return True
    return time.time() - STATE_PATH.stat().st_mtime >= INTERVAL_SECONDS


def acquire_lock():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    try:
        descriptor = os.open(LOCK_PATH, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        os.write(descriptor, str(os.getpid()).encode())
        os.close(descriptor)
        return True
    except FileExistsError:
        if time.time() - LOCK_PATH.stat().st_mtime > 3 * 60 * 60:
            LOCK_PATH.unlink(missing_ok=True)
            return acquire_lock()
        return False


def run_pipeline():
    if not acquire_lock():
        return
    commands = [
        [sys.executable, "collector.py"],
        [sys.executable, "media_index.py", "--languages", "all"],
        [sys.executable, "media_index.py", "--repair-locations"],
        [sys.executable, "dpa_index.py"],
    ]
    if os.environ.get("DEEPSEEK_API_KEY", "").strip():
        commands.append([sys.executable, "report_cli.py", "generate-pending"])
    try:
        write_state("running")
        summaries = []
        for command in commands:
            result = subprocess.run(command, cwd=BASE_DIR, text=True, capture_output=True,
                                    timeout=45 * 60, check=False)
            tail = (result.stdout or result.stderr).strip().splitlines()[-1:] or [""]
            summaries.append(f"{' '.join(command[1:])}: {result.returncode} {tail[0][:180]}")
            if result.returncode:
                raise RuntimeError(summaries[-1])
        write_state("success", " | ".join(summaries))
    except Exception as exc:
        write_state("failed", type(exc).__name__ + ": " + str(exc)[:500])
    finally:
        LOCK_PATH.unlink(missing_ok=True)


def start_scheduler():
    if os.environ.get("ENABLE_SCHEDULER", "0") != "1":
        return None

    def loop():
        while True:
            if due():
                run_pipeline()
            time.sleep(min(300, max(30, INTERVAL_SECONDS // 12)))

    thread = threading.Thread(target=loop, name="six-hour-collector", daemon=True)
    thread.start()
    return thread
