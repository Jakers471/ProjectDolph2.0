"""Combine rule results into a final confidence score and resolved action.

Scoring model:
  action rule fired clearly     +0.35
  symbol found                  +0.25
  price data found              +0.20
  side found                    +0.10
  size hint found               +0.10
  ─────────────────────────────────────
  max possible                   1.00

Thresholds:
  >= 0.65  → use detected action as-is
  0.35–0.65 → UNSURE (action detected but missing key pieces)
  < 0.35   → NOISE  (nothing useful found)

NOISE action always stays NOISE regardless of score.
"""
from parsing.signals_schema import RuleResult


def score(
    action_r: RuleResult,
    side_r: RuleResult,
    symbol_r: RuleResult,
    price_r: RuleResult,
) -> tuple[str, float, list[str]]:
    """Return (final_action, confidence, unsure_reasons)."""

    action = action_r.value
    reasons: list[str] = []

    # NOISE is terminal — don't bother scoring further
    if action == "NOISE":
        return "NOISE", action_r.confidence, []

    total = 0.0

    # Action rule weight — base varies by action type
    # EXIT/TRIM are self-contained: the phrase alone is enough to be useful
    # ENTRY needs corroboration (symbol + price)
    if action not in (None, "UNSURE"):
        if action in ("EXIT", "TRIM", "ADD"):
            # These stand on their own — give higher base weight
            total += 0.65 * action_r.confidence
        else:
            total += 0.35 * action_r.confidence
    else:
        total += 0.10
        reasons.append("action unclear")

    # Symbol weight
    sym, _ = symbol_r.value if isinstance(symbol_r.value, tuple) else (None, None)
    if sym:
        total += 0.25 * symbol_r.confidence
    else:
        if action in ("ENTRY",):
            reasons.append("no symbol found")

    # Price weight
    price = price_r.value or {}
    has_price = (price.get("entry_price") or price.get("targets") or price.get("stop"))
    if has_price:
        total += 0.20 * price_r.confidence
    else:
        if action in ("ENTRY",):
            reasons.append("no price data for ENTRY")

    # Side weight (bonus — not required for TRIM/EXIT)
    if side_r.value:
        total += 0.10 * side_r.confidence

    # Size hint bonus
    if price.get("size_hint"):
        total += 0.05

    total = round(min(total, 1.0), 3)

    # Resolve final action
    if total >= 0.55:
        final = action if action not in (None, "UNSURE") else "UNSURE"
    elif total >= 0.25:
        final = "UNSURE"
        if action not in (None, "UNSURE"):
            reasons.insert(0, f"low confidence for {action}")
    else:
        final = "NOISE"

    return final, total, reasons
