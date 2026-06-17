"""Live pipeline: polls discord_messages.db for new messages and routes
them through parse -> risk -> broker in real time.

Two ingestion sources write to discord_messages.db:
  1. ingestion/windows_watcher.py  -- Windows toast notifications (no bot token)
  2. ingestion/discord_db bot      -- discord.py bot (full messages, requires token)

This module reads from that DB and runs the full pipeline on each new row.

Channel -> Trader routing uses CHANNEL_ANALYST_MAP in .env:
  CHANNEL_ANALYST_MAP=1234567890:Grizzlies,grizzlies-signals:Grizzlies
  Supports both channel IDs (from bot) and channel names (from watcher), case-insensitive.

Run:
  python ingestion/live_pipeline.py Grizzlies       # standalone
  python dev.py --watch Grizzlies                    # via dev.py
"""
from __future__ import annotations

import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT))


def _load_channel_map() -> dict[str, str]:
    """Returns {channel_id_or_name_lower: TraderName} from .env."""
    raw = os.getenv("CHANNEL_ANALYST_MAP", "")
    mapping: dict[str, str] = {}
    for pair in raw.split(","):
        if ":" in pair:
            k, v = pair.strip().split(":", 1)
            mapping[k.strip().lower()] = v.strip()
    return mapping


def _route(channel_id: str, channel_name: str, channel_map: dict[str, str]) -> str | None:
    return (
        channel_map.get(channel_id.lower())
        or channel_map.get(channel_name.lower())
    )


def run(
    traders: list[str] | None = None,
    poll_interval: float = 1.0,
    dry_run: bool = True,
    verbose: bool = True,
    stop_event=None,
    log_fn=None,
):
    """Poll discord_messages.db and push new messages through the pipeline.

    traders:    only process messages routing to these traders (None = all mapped).
    stop_event: threading.Event — set to stop the loop cleanly.
    log_fn:     callable(str) — if provided, captures log lines instead of print().
    """
    def _log(msg: str):
        if log_fn:
            log_fn(msg)
        elif verbose:
            print(msg)

    try:
        from dotenv import load_dotenv
        load_dotenv(PROJECT / ".env")
    except ImportError:
        pass

    from ingestion.discord_db import init_db, fetch_after
    from parsing.parser import parse_message
    from data.paper_db import DB
    from risk.rules import evaluate
    from execution.broker import submit_order

    init_db()

    channel_map = _load_channel_map()
    if not channel_map:
        _log("[live] WARNING: CHANNEL_ANALYST_MAP not set in .env")
        _log("[live] Add: CHANNEL_ANALYST_MAP=channel_name:TraderName")

    _log(f"[live] Pipeline running (dry_run={dry_run})")
    _log(f"[live] Channel map: {channel_map}")

    db = DB()
    last_id = 0
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")

    while True:
        if stop_event and stop_event.is_set():
            _log("[live] stopped.")
            break
        try:
            rows = fetch_after(last_id)
            for row in rows:
                last_id = row["id"]
                channel_id   = row["channel_id"]
                channel_name = row["channel_name"]
                content      = row["content"]
                created_at   = row["created_at"]

                if not content.strip():
                    continue

                trader = _route(channel_id, channel_name, channel_map)
                if not trader:
                    _log(f"[live] UNMAPPED channel=#{channel_name} — add to CHANNEL_ANALYST_MAP")
                    continue
                if traders and trader not in traders:
                    continue

                sig = parse_message(trader, created_at, content)
                ok, reason = evaluate(sig, db)

                verdict = "TRADE" if ok else f"SKIP ({reason})"
                _log(
                    f"[live] {trader} | {sig.action} {sig.symbol or '?'} "
                    f"conf={sig.confidence:.2f} | {verdict} | "
                    f"{content[:60].replace(chr(10), ' ')}"
                )

                if ok:
                    submit_order(sig, db, run_id=run_id, dry_run=dry_run)

                    if not dry_run:
                        try:
                            from config.loader import get_config
                            from execution.alpaca_adapter import get_adapter
                            notional = get_config(trader).get("broker", {}).get("trade_notional", 100.0)
                            adapter = get_adapter()
                            result = adapter.submit_order(sig, run_id, notional)
                            _log(f"[alpaca] {result}")
                        except Exception as e:
                            _log(f"[alpaca] error: {e}")

        except KeyboardInterrupt:
            _log("[live] Stopped.")
            break
        except Exception as e:
            _log(f"[live] error: {e}")

        time.sleep(poll_interval)

    db.close()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("traders", nargs="*", help="Trader names to process (default: all mapped)")
    parser.add_argument("--live", action="store_true", help="Set dry_run=False (CAUTION: sends real orders)")
    parser.add_argument("--interval", type=float, default=1.0, help="Poll interval in seconds")
    args = parser.parse_args()

    run(
        traders=args.traders or None,
        poll_interval=args.interval,
        dry_run=not args.live,
    )
