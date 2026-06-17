"""Event-driven Discord listener — real-time signal ingestion.

Replaces discord_poller.py for live operation. Uses Discord's gateway
(websocket) so messages arrive instantly when posted, with no polling lag.

vs. discord_poller.py:
  - discord_poller  : replays existing corpus; no real Discord connection
  - discord_listener: real-time bot; fires on every new message in watched channels

Architecture:
  Discord gateway (websocket push)
    -> on_message(message)
    -> parse_message(analyst, timestamp, content) -> Signal
    -> risk.evaluate(signal, db)
    -> broker.submit_order(signal, db)

Setup (one-time):
  1. Go to discord.com/developers/applications → New Application → Bot
  2. Under Bot: enable "Message Content Intent"
  3. Copy the bot token → add to .env as DISCORD_BOT_TOKEN
  4. Invite the bot to your server with Manage Messages + Read Message History
  5. Copy channel IDs (right-click channel → Copy ID with Developer Mode on)
     → add to .env as comma-separated: DISCORD_CHANNEL_IDS=123456,789012
  6. pip install discord.py
  7. Map channel IDs to analyst names in CHANNEL_ANALYST_MAP below

Event-driven vs polling:
  - Event-driven (this file): sub-second latency, no rate limit concerns,
    requires bot token + server invite. Preferred for production.
  - Polling (discord_poller.py): works without a bot (REST API + user token),
    but has rate limits and minimum ~1s lag. Use as fallback only.

To run:
  python ingestion/discord_listener.py          # standalone
  (future) python dev.py --listen               # wired into dev.py
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT))

# ---- Config ------------------------------------------------------------------

# Map Discord channel IDs (int) -> analyst name
# Override by adding to .env: CHANNEL_ANALYST_MAP=123456:Grizzlies,789012:ECS
CHANNEL_ANALYST_MAP: dict[int, str] = {
    # 1234567890123456789: "Grizzlies",
    # 9876543210987654321: "ECS",
}


def _load_env():
    try:
        from dotenv import load_dotenv
        load_dotenv(PROJECT / ".env")
    except ImportError:
        pass


def _channel_map() -> dict[int, str]:
    mapping = dict(CHANNEL_ANALYST_MAP)
    raw = os.getenv("CHANNEL_ANALYST_MAP", "")
    if raw:
        for pair in raw.split(","):
            if ":" in pair:
                cid, name = pair.strip().split(":", 1)
                mapping[int(cid.strip())] = name.strip()
    return mapping


def _watched_channels() -> set[int]:
    raw = os.getenv("DISCORD_CHANNEL_IDS", "")
    if not raw:
        return set(_channel_map().keys())
    return {int(c.strip()) for c in raw.split(",") if c.strip()}


# ---- Bot client --------------------------------------------------------------

def create_bot(callback: Callable[[str, str, str], None] | None = None,
               dry_run: bool = True):
    """Create and return a discord.Client configured for signal ingestion.

    callback(analyst, timestamp, content) is fired for every message
    in a watched channel — same signature as discord_poller.poll().

    If callback is None, the default pipeline (parse → risk → broker) runs.
    """
    try:
        import discord
    except ImportError:
        raise ImportError(
            "discord.py is required for the live listener.\n"
            "Run: pip install discord.py"
        )

    intents = discord.Intents.default()
    intents.message_content = True   # required to read message text
    client = discord.Client(intents=intents)

    channel_map = _channel_map()
    watched     = _watched_channels()

    @client.event
    async def on_ready():
        print(f"[discord] logged in as {client.user} | watching {len(watched)} channel(s)")

    @client.event
    async def on_message(message: discord.Message):
        # Ignore DMs and bot messages
        if message.author.bot:
            return
        if message.channel.id not in watched:
            return

        analyst   = channel_map.get(message.channel.id, "unknown")
        timestamp = message.created_at.replace(tzinfo=timezone.utc).isoformat()
        content   = message.content or ""

        if not content.strip():
            return

        if callback:
            callback(analyst, timestamp, content)
        else:
            _default_pipeline(analyst, timestamp, content, dry_run)

    return client


def _default_pipeline(analyst: str, timestamp: str, content: str, dry_run: bool):
    """Parse → risk filter → broker. Called for each live message."""
    from parsing.parser import parse_message
    from data.paper_db import DB
    from risk.rules import evaluate
    from execution.broker import submit_order
    from execution.alpaca_adapter import get_adapter

    sig    = parse_message(analyst, timestamp, content)
    db     = DB()
    ok, reason = evaluate(sig, db)

    if not ok:
        db.close()
        return

    # Log to DB
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    submit_order(sig, db, run_id=run_id, dry_run=dry_run)

    # Submit to Alpaca if not dry-run
    if not dry_run:
        from config.loader import get_config
        notional = get_config(analyst).get("broker", {}).get("trade_notional", 100.0)
        adapter  = get_adapter()
        result   = adapter.submit_order(sig, run_id, notional)
        print(f"[alpaca] {result}")

    db.close()


def run(token: str | None = None, dry_run: bool = True):
    """Start the Discord listener. Blocks until Ctrl+C."""
    _load_env()
    token = token or os.getenv("DISCORD_BOT_TOKEN")
    if not token:
        print(
            "[discord] ERROR: DISCORD_BOT_TOKEN not set in .env\n"
            "  See ingestion/discord_listener.py for setup instructions."
        )
        return

    bot = create_bot(dry_run=dry_run)
    print(f"[discord] starting listener (dry_run={dry_run})...")
    bot.run(token)


if __name__ == "__main__":
    run()
