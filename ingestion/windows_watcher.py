"""Windows toast notification watcher for Discord.

Polls the Windows UI tree every POLL_INTERVAL seconds for Discord toast
notifications, extracts message content, and saves to discord_messages.db.

No bot token needed. Requires Discord's desktop app to be running and
notifications to be enabled. Works even without bot permissions.

Requires: pip install uiautomation

Toast format Discord uses:
  "New notification from Discord, AUTHOR (#CHANNEL, SERVER), CONTENT  N of N"

Run:
  python ingestion/windows_watcher.py           # standalone
  python dev.py --watch Grizzlies               # wired into dev.py (starts watcher + pipeline)
"""
from __future__ import annotations

import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT))

from ingestion.discord_db import init_db, save_message

POLL_INTERVAL = 0.5
TOAST_WINDOW_NAME = "New notification"
TOAST_WINDOW_CLASS = "Windows.UI.Core.CoreWindow"

# Discord wraps names in Unicode bidi-isolate characters
_BIDI = re.compile(r"[⁨⁩]")

# "New notification from Discord, AUTHOR (#CHANNEL, SERVER), CONTENT  N of N"
_PATTERN = re.compile(
    r"New notification from Discord,\s+"
    r"(.+?)"            # group 1: author
    r"\s+\(#(.+?),\s*"  # group 2: channel name
    r"(.+?)\),\s*"      # group 3: server name
    r"(.*?)"            # group 4: content
    r"(?:\s+\d+ of \d+)?$",
    re.DOTALL,
)


def _parse_notification(text: str) -> dict | None:
    text = _BIDI.sub("", text).strip()
    m = _PATTERN.match(text)
    if not m:
        return None
    return {
        "author":  m.group(1).strip(),
        "channel": m.group(2).strip(),
        "server":  m.group(3).strip(),
        "content": m.group(4).strip(),
    }


def _find_toast_text() -> str | None:
    try:
        import uiautomation as auto
        root = auto.GetRootControl()
        for ctrl in root.GetChildren():
            if ctrl.Name == TOAST_WINDOW_NAME and ctrl.ClassName == TOAST_WINDOW_CLASS:
                for child in ctrl.GetChildren():
                    for gc in child.GetChildren():
                        name = gc.Name or ""
                        if "New notification from Discord" in name:
                            return name
    except Exception:
        pass
    return None


def watch(verbose: bool = True, stop_event=None, log_fn=None):
    """Block until stop_event is set, capturing Discord toast notifications.

    stop_event: threading.Event — set it to stop the loop cleanly.
    log_fn:     callable(str) — if provided, receives log lines instead of print().
    """
    def _log(msg: str):
        if log_fn:
            log_fn(msg)
        elif verbose:
            print(msg)

    try:
        import uiautomation  # noqa: F401
    except ImportError:
        _log("[watcher] ERROR: uiautomation not installed. Run: pip install uiautomation")
        return

    init_db()
    seen: set[str] = set()

    _log("[watcher] UI Automation toast watcher running.")
    _log("[watcher] Make sure Discord desktop notifications are ON.")

    while True:
        if stop_event and stop_event.is_set():
            _log("[watcher] stopped.")
            break
        try:
            text = _find_toast_text()
            if text and text not in seen:
                seen.add(text)
                parsed = _parse_notification(text)
                if parsed:
                    saved = save_message(
                        message_id=f"toast_{hash(text)}",
                        author_id="unknown",
                        author_name=parsed["author"],
                        channel_id=parsed["channel"],
                        channel_name=parsed["channel"],
                        guild_id=parsed["server"],
                        guild_name=parsed["server"],
                        content=parsed["content"],
                        created_at=datetime.now(timezone.utc),
                    )
                    status = "saved" if saved else "dup"
                    _log(
                        f"[watcher] {status} | {parsed['server']} "
                        f"#{parsed['channel']} | {parsed['author']}: "
                        f"{parsed['content'][:80]}"
                    )
                else:
                    _log(f"[watcher] unrecognized toast: {text[:120]}")

            if len(seen) > 500:
                seen.clear()

        except Exception as e:
            _log(f"[watcher] error: {e}")

        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    watch()
