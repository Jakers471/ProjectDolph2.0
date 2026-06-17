"""Main parser entry point.

parse_message()  — single message → Signal
parse_corpus()   — all messages for a trader → list[Signal], writes signals JSONL
"""
import json
import re
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT))

from parsing.signals_schema import Signal
from parsing.rules import action, side, symbol, price
from parsing import confidence as conf_mod


_DISCORD_NOISE = re.compile(
    r'<@[!&]?\d+>'      # user/role mentions
    r'|<#\d+>'          # channel links
    r'|<:\w+:\d+>'      # custom emoji
    r'|<a:\w+:\d+>',    # animated emoji
)


def _strip(text: str) -> str:
    return _DISCORD_NOISE.sub("", text).strip()


def parse_message(
    analyst: str,
    timestamp: str,
    content: str,
    message_id: str | None = None,
) -> Signal:
    clean = _strip(content)

    action_r  = action.detect(clean)
    side_r    = side.detect(clean)
    symbol_r  = symbol.detect(clean)
    price_r   = price.detect(clean)

    final_action, final_conf, reasons = conf_mod.score(action_r, side_r, symbol_r, price_r)

    sym, asset_type = symbol_r.value if isinstance(symbol_r.value, tuple) else (None, None)
    price_data = price_r.value or {}

    return Signal(
        analyst=analyst,
        timestamp=timestamp,
        raw_content=content,
        action=final_action,
        confidence=final_conf,
        side=side_r.value if side_r.value else None,
        asset_type=asset_type,
        symbol=sym,
        entry_price=price_data.get("entry_price"),
        exit_pct=price_data.get("exit_pct"),
        targets=price_data.get("targets", []),
        stop=price_data.get("stop"),
        size_hint=price_data.get("size_hint"),
        unsure_reasons=reasons,
        source_message_id=message_id,
    )


def parse_corpus(trader: str) -> list[Signal]:
    messages_path = PROJECT / "data" / trader / "messages.jsonl"
    if not messages_path.exists():
        raise FileNotFoundError(f"{messages_path} not found — run ingestion first")

    signals = []
    for line in messages_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        sig = parse_message(
            analyst=row["analyst"],
            timestamp=row["timestamp"],
            content=row["content"],
            message_id=row.get("source_message_id"),
        )
        signals.append(sig)
    return signals


def write_signals(trader: str, signals: list[Signal], run_id: str) -> Path:
    out_dir = PROJECT / "data" / trader / "signals"
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"{run_id}.jsonl"
    lines = [json.dumps(s.to_dict(), ensure_ascii=False) for s in signals]
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out
