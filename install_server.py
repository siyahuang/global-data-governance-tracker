"""Keep the loopback-only dashboard available after signing in to macOS.

Run: python3 install_server.py
Remove: python3 install_server.py --remove
"""

import argparse
import plistlib
import subprocess
import sys
from pathlib import Path

from config import BASE_DIR, DB_PATH

LABEL = "com.dmg.global-data-governance-workbench"
PLIST = Path.home() / "Library" / "LaunchAgents" / (LABEL + ".plist")
LOG_DIR = Path.home() / "Library" / "Logs"


def run(*args):
    return subprocess.run(args, check=False, capture_output=True, text=True)


def install():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    PLIST.parent.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "Label": LABEL,
        "ProgramArguments": [sys.executable, str(BASE_DIR / "server.py")],
        "RunAtLoad": True,
        "KeepAlive": True,
        "StandardOutPath": str(LOG_DIR / (LABEL + ".log")),
        "StandardErrorPath": str(LOG_DIR / (LABEL + "-error.log")),
    }
    PLIST.write_bytes(plistlib.dumps(payload))
    domain = "gui/" + str(__import__("os").getuid())
    run("launchctl", "bootout", domain, str(PLIST))
    result = run("launchctl", "bootstrap", domain, str(PLIST))
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip())
    print("已安装并启动：" + str(PLIST))
    print("工作台：http://127.0.0.1:8765")


def remove():
    domain = "gui/" + str(__import__("os").getuid())
    run("launchctl", "bootout", domain, str(PLIST))
    if PLIST.exists():
        PLIST.unlink()
    print("已移除常驻工作台。")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--remove", action="store_true")
    args = parser.parse_args()
    remove() if args.remove else install()
