"""Mock Discord poller — replays corpus messages in timestamp order.

Usage (programmatic):
    from ingestion.discord_poller import poll
    poll("Grizzlies", speed=50.0, callback=my_fn)

Usage (dev.py --poll):
    Imported and called by dev.py; callback fires the full pipeline per message.

`speed` is a time multiplier: speed=1 replays at real wall-clock intervals,
speed=10 is 10x faster, speed=0 skips all delays (instant replay).

When Discord live ingestion is ready, replace this with a websocket listener
that fires the same callback signature: callback(analyst, timestamp, content).
"""
from __future__ import annotations

import time
from pathlib import Path
from typing import Callable
import json

PROJECT = Path(__file__).resolve().parent.parent
_DATA = PROJECT / "data"


def _load_messages(trader: str) -> list[dict]:
    path = _DATA / trader / "messages.jsonl"
    if not path.exists():
        raise FileNotFoundError(f"No messages for trader: {trader} (expected {path})")
    lines = path.read_text(encoding="utf-8").splitlines()
    msgs = [json.loads(l) for l in lines if l.strip()]
    # sort by timestamp ascending (should already be sorted, but ensure it)
    msgs.sort(key=lambda m: m.get("timestamp", ""))
    return msgs


def poll(trader: str, speed: float = 0.0,
         callback: Callable[[str, str, str], None] | None = None,
         limit: int | None = None) -> int:
    """Replay corpus messages for `trader` in timestamp order.

    Args:
        trader:   trader name (matches data/<trader>/messages.jsonl)
        speed:    time compression factor (0 = no delay, 1 = real time, 50 = 50x faster)
        callback: fn(analyst, timestamp, content) called for each message
        limit:    max messages to replay (None = all)

    Returns:
        number of messages replayed
    """
    msgs = _load_messages(trader)
    if limit:
        msgs = msgs[:limit]

    prev_ts: str | None = None
    count = 0

    for msg in msgs:
        analyst   = msg.get("analyst", trader)
        timestamp = msg.get("timestamp", "")
        content   = msg.get("content", "")

        # Simulate inter-message delay
        if speed > 0 and prev_ts and timestamp:
            try:
                from datetime import datetime, timezone
                fmt = "%Y-%m-%dT%H:%M:%S"
                t0 = datetime.fromisoformat(prev_ts.replace("Z", "+00:00"))
                t1 = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                delta = (t1 - t0).total_seconds()
                if 0 < delta < 3600:  # skip gaps > 1h
                    sleep_s = delta / speed
                    if sleep_s > 0.005:
                        time.sleep(sleep_s)
            except Exception:
                pass

        if callback:
            callback(analyst, timestamp, content)

        prev_ts = timestamp
        count += 1

    return count
