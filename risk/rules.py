"""Risk rules: gate signals before they reach the broker.

evaluate(signal, db) -> (approved: bool, reason: str)

Rules applied in order — first rejection wins:
  1. KILL_SWITCH  — global off switch (set KILL_SWITCH = True to halt all trading)
  2. Action gate  — only ENTRY/TRIM/EXIT/ADD pass; UNSURE/NOISE are always rejected
  3. Min confidence — signal.confidence must be >= MIN_CONFIDENCE
  4. Symbol required — ENTRY signals must have a known symbol
  5. Max positions — analyst cannot exceed MAX_OPEN_POSITIONS open positions
  6. Duplicate guard — no second ENTRY for same analyst+symbol while position is open
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from parsing.signals_schema import Signal
    from data.paper_db import DB

# ---- Evaluate ------------------------------------------------------------------

def evaluate(signal: "Signal", db: "DB") -> tuple[bool, str]:
    from config.loader import get_config
    cfg  = get_config(signal.analyst)
    risk = cfg["risk"]

    kill_switch        = risk.get("kill_switch", False)
    min_confidence     = risk.get("min_confidence", 0.55)
    max_open_positions = risk.get("max_open_positions", 3)
    actionable         = set(risk.get("allowed_actions", ["ENTRY", "TRIM", "EXIT", "ADD"]))

    if kill_switch:
        return False, f"kill_switch active for {signal.analyst}"

    if signal.action not in actionable:
        return False, f"action={signal.action} is not actionable"

    if signal.confidence < min_confidence:
        return False, (f"confidence {signal.confidence:.2f} < "
                       f"min_confidence {min_confidence} for {signal.analyst}")

    if signal.action == "ENTRY":
        if not signal.symbol:
            return False, "ENTRY signal missing symbol"

        open_count = db.open_position_count(signal.analyst)
        if open_count >= max_open_positions:
            return False, (f"max open positions ({max_open_positions}) "
                           f"reached for {signal.analyst}")

        existing = db.get_open_position(signal.analyst, signal.symbol)
        if existing:
            return False, f"position already open: {signal.analyst} {signal.symbol}"

    if signal.action in ("TRIM", "EXIT", "ADD"):
        if signal.symbol:
            existing = db.get_open_position(signal.analyst, signal.symbol)
            if not existing:
                return False, (f"no open position to {signal.action}: "
                               f"{signal.analyst} {signal.symbol}")

    return True, "approved"
