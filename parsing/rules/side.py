"""Side classifier: LONG or SHORT.

Only relevant for ENTRY and ADD signals. Returns None for trim/exit/noise.
"""
import re
from parsing.signals_schema import RuleResult

# Explicit LONG signals
_LONG = re.compile(
    r'(?:^|\n)\s*long\b'           # "Long" on its own line (Grizzlies template)
    r'|\blong\s*\n'
    r'|\bbtc\s+long\b'
    r'|\beth\s+long\b'
    r'|\b\w+\s+long\b'             # "[symbol] long"
    r'|\bcalls?\b'                 # options calls = bullish
    r'|\b[A-Z]{2,5}\s+\d+(?:\.\d+)?c\b'   # "IBIT 42c" shorthand
    r'|\bbullish\b'
    r'|\bbuying\b'
    r'|\bbuy\s+bids?\b'              # "buy bid", "buy bids"
    r'|\bbid(?:ding)?\s+(?:on|for)\b' # "bidding on", "bid for"
    r'|\bgoing\s+long\b',
    re.IGNORECASE | re.MULTILINE,
)

# Explicit SHORT signals
_SHORT = re.compile(
    r'(?:^|\n)\s*short\b'          # "Short" on its own line (Grizzlies template)
    r'|\bshort\s*\n'
    r'|\bbtc\s+short\b'
    r'|\b\w+\s+short\b'            # "[symbol] short"
    r'|\b[A-Z]{2,5}\s+puts?\b'     # "[TICKER] puts" — options puts
    r'|\b[A-Z]{2,5}\s+\d+(?:\.\d+)?p\b'   # "IBIT 42p" shorthand
    r'|(?:^|\n)\s*puts?\s*\n'              # "Puts" on its own line
    r'|\bbearish\b'
    r'|\bselling\s+short\b'
    r'|\bgoing\s+short\b',
    re.IGNORECASE | re.MULTILINE,
)


def detect(text: str) -> RuleResult:
    long_match = _LONG.search(text)
    short_match = _SHORT.search(text)

    if long_match and not short_match:
        return RuleResult("LONG", 0.90, [f"long signal: '{long_match.group().strip()}'"])

    if short_match and not long_match:
        return RuleResult("SHORT", 0.90, [f"short signal: '{short_match.group().strip()}'"])

    if long_match and short_match:
        # Both present (e.g., "trimmed long, now short") — defer to action context
        return RuleResult(None, 0.30, ["both long and short signals present — ambiguous"])

    return RuleResult(None, 0.50, ["no explicit side signal"])
