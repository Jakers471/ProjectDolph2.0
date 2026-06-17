"""Price extractor: entry price, targets, stop, and size hint.

Handles Grizzlies' main formats:
  Template:  Entry: 1)94500 2)93500 / Targets: 1)95000 2)96000 / Stop: 92000
  Options:   @1.50 / $92 to $110 / 0.50 to 0.70
  Leverage:  Leverage: 20x / Margin: $500 / 15 contracts
"""
import re
from parsing.signals_schema import RuleResult

# ---- Helpers -----------------------------------------------------------------

def _parse_num(s: str) -> float | None:
    try:
        return float(s.replace(",", ""))
    except (ValueError, AttributeError):
        return None


# ---- Entry price -------------------------------------------------------------

# "Entry: 1)94500 2)93500" or "Entries: 1)94500"
_ENTRY_SECTION = re.compile(
    r'entr(?:y|ies?)\s*:?\s*(.*?)(?=\n[A-Za-z]|\ntargets?|\nstop|\nleverag|\nmargin|$)',
    re.IGNORECASE | re.DOTALL,
)
_NUMBERED = re.compile(r'\d+\)\s*\$?([\d,]+(?:\.\d+)?)')
# Plain number fallback: "Entry: 15" or "Entry: $15.50"
_PLAIN_PRICE = re.compile(r'^\s*\$?([\d,]+(?:\.\d+)?)', re.MULTILINE)

# "@1.50" or "@ $1.50"
# Negative lookahead: don't match "@$120 a con" (per-contract price, not per-share)
_AT_PRICE = re.compile(r'@\s*\$?([\d.]+)(?![\d.]*\s+a\s+(?:con|contract))', re.IGNORECASE)

# "TICKER: $19" or "Mara: $19" or "Riot: $11.50" — per-ticker bid/price list
_TICKER_PRICE = re.compile(r'\b[A-Za-z]{2,6}\s*:\s*\$?([\d,]+(?:\.\d+)?)', re.IGNORECASE)

# ---- Targets -----------------------------------------------------------------

_TARGET_SECTION = re.compile(
    r'targets?\s*:?\s*(.*?)(?=\nstop|\nleverag|\nmargin|\ncoin|\nentry|$)',
    re.IGNORECASE | re.DOTALL,
)
# "TP1: 95000" style
_TP_LABEL = re.compile(r'\btp\s*[1-9]\s*:?\s*\$?([\d,]+(?:\.\d+)?)', re.IGNORECASE)

# "$92 to $110" — options profit report (entry→exit)
_TO_RANGE = re.compile(r'\$?([\d.]+)\s+to\s+\$?([\d.]+)', re.IGNORECASE)

# ---- Stop --------------------------------------------------------------------

_STOP = re.compile(
    r'(?:stop|sl)\s*:?\s*\$?([\d,]+(?:\.\d+)?)',
    re.IGNORECASE,
)
_STOP_AT_ENTRY = re.compile(r'\bstop(?:s)?\s+(?:at|on)\s+entry\b', re.IGNORECASE)

# ---- Size / leverage ---------------------------------------------------------

# ---- Exit percentage ---------------------------------------------------------
# "up 25%" / "calls up 13%" / "puts up 40%" (positive)
_UP_PCT   = re.compile(r'\bup\s+(?:about\s+)?(\d+(?:\.\d+)?)\s*%', re.IGNORECASE)
# "down 10%" (negative)
_DOWN_PCT = re.compile(r'\bdown\s+(?:about\s+)?(\d+(?:\.\d+)?)\s*%', re.IGNORECASE)
# "-20%" or "+30%" with explicit sign
_SIGN_PCT = re.compile(r'(?<!\d)([-+]\d+(?:\.\d+)?)\s*%')

# ---- Size / leverage ---------------------------------------------------------
_LEVERAGE = re.compile(r'leverage\s*:?\s*(\d+x)', re.IGNORECASE)
_MARGIN   = re.compile(r'margin\s*:?\s*\$?([\d,]+(?:\.\d+)?)', re.IGNORECASE)
_CONTRACTS = re.compile(r'(\d+)\s*(?:contracts?|cons?)\b', re.IGNORECASE)
_AT_CONTRACTS = re.compile(r'\$?([\d.]+)\s+a\s+(?:contract|con)\b', re.IGNORECASE)


def detect(text: str) -> RuleResult:
    evidence = []
    entry_price: float | None = None
    exit_pct: float | None = None
    targets: list[float] = []
    stop: float | None = None
    size_hint: str | None = None

    # --- Entry price ---
    # Try "Entry: 1)..." numbered list first, then plain number fallback
    m = _ENTRY_SECTION.search(text)
    if m:
        section = m.group(1)
        nums = [_parse_num(x) for x in _NUMBERED.findall(section)]
        nums = [n for n in nums if n is not None]
        if nums:
            entry_price = nums[0]  # first listed = primary entry
            evidence.append(f"entry from template: {nums}")
        else:
            # Plain number: "Entry: 15" or "Entry: $15.50"
            pm = _PLAIN_PRICE.search(section)
            if pm:
                v = _parse_num(pm.group(1))
                if v is not None and v > 0:
                    entry_price = v
                    evidence.append(f"entry plain number: {v}")

    # "@price" for options
    if entry_price is None:
        m = _AT_PRICE.search(text)
        if m:
            entry_price = _parse_num(m.group(1))
            if entry_price is not None:
                evidence.append(f"entry @price: {entry_price}")

    # "TICKER: $19" per-ticker price list (e.g. "Mara: $19 \n Riot: $11.50")
    if entry_price is None:
        nums = [_parse_num(x) for x in _TICKER_PRICE.findall(text)]
        nums = [n for n in nums if n is not None and n > 0]
        if nums:
            entry_price = nums[0]
            if len(nums) > 1:
                targets = nums[1:]
            evidence.append(f"ticker price list: {nums}")

    # "$X to $Y" range — entry is the lower number
    # Guard: skip if both values look like stock prices (>$20) — that's a stock
    # price report in a TRIM message (e.g. "calls up 30%, $150 to $195"), not an
    # option premium range. Option premiums are almost always sub-$20.
    if entry_price is None:
        m = _TO_RANGE.search(text)
        if m:
            a, b = _parse_num(m.group(1)), _parse_num(m.group(2))
            if a is not None and b is not None:
                if a > 20 and b > 20:
                    evidence.append(f"skipped stock-price range {a}→{b} (both >$20, not option premium)")
                else:
                    entry_price = min(a, b)
                    evidence.append(f"entry from range {a}→{b}: entry={entry_price}")

    # --- Targets ---
    m = _TARGET_SECTION.search(text)
    if m:
        nums = [_parse_num(x) for x in _NUMBERED.findall(m.group(1))]
        targets = [n for n in nums if n is not None]
        if targets:
            evidence.append(f"targets from template: {targets}")

    # TP label fallback
    if not targets:
        nums = [_parse_num(x) for x in _TP_LABEL.findall(text)]
        targets = [n for n in nums if n is not None]
        if targets:
            evidence.append(f"targets from TP labels: {targets}")

    # --- Stop ---
    m = _STOP.search(text)
    if m:
        stop = _parse_num(m.group(1))
        if stop is not None:
            evidence.append(f"stop: {stop}")
    elif _STOP_AT_ENTRY.search(text):
        # "stops at entry" — stop equals entry price (resolved later)
        stop = entry_price
        evidence.append("stop at entry price")

    # --- Exit percentage ---
    m = _UP_PCT.search(text)
    if m:
        exit_pct = _parse_num(m.group(1))
        if exit_pct is not None:
            evidence.append(f"exit pct: +{exit_pct}%")
    if exit_pct is None:
        m = _DOWN_PCT.search(text)
        if m:
            v = _parse_num(m.group(1))
            if v is not None:
                exit_pct = -v
                evidence.append(f"exit pct: -{v}%")
    if exit_pct is None:
        m = _SIGN_PCT.search(text)
        if m:
            exit_pct = _parse_num(m.group(1))
            if exit_pct is not None:
                evidence.append(f"exit pct (signed): {exit_pct}%")

    # --- Size hint ---
    m = _LEVERAGE.search(text)
    if m:
        size_hint = m.group(1)
        evidence.append(f"leverage: {size_hint}")
    else:
        m = _MARGIN.search(text)
        if m:
            size_hint = f"${m.group(1)} margin"
            evidence.append(f"margin: {size_hint}")
        else:
            m = _CONTRACTS.search(text)
            if m:
                size_hint = f"{m.group(1)} contracts"
                evidence.append(f"contracts: {size_hint}")
            else:
                m = _AT_CONTRACTS.search(text)
                if m:
                    size_hint = f"${m.group(1)}/contract"
                    evidence.append(f"price per contract: {size_hint}")

    found_something = entry_price is not None or exit_pct is not None or targets or stop is not None or size_hint
    conf = 0.85 if found_something else 0.0

    return RuleResult(
        {"entry_price": entry_price, "exit_pct": exit_pct, "targets": targets, "stop": stop, "size_hint": size_hint},
        conf,
        evidence or ["no price data found"],
    )
