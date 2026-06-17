"""Symbol extractor: find the traded ticker and classify asset type.

Asset types:
  CRYPTO  — matched against crypto DB (CoinGecko top 500)
  STOCK   — matched against stock DB (SEC EDGAR)
  OPTION  — stock/ETF underlying with calls/puts language or strike notation

Detection priority:
  1. "Coin: XYZ"       — Grizzlies crypto template (highest confidence)
  2. "XYZ [STRIKE]c/p" — options contract notation, e.g. "IBIT 42c"
  3. "[XYZ] calls/puts" — options language with known ticker
  4. Plain ticker mention in crypto DB
  5. Plain ticker mention in stock DB
"""
import json
import re
import sys
from pathlib import Path
from parsing.signals_schema import RuleResult

PROJECT = Path(__file__).resolve().parent.parent.parent
_CRYPTO_DB = PROJECT / "data" / "_ref" / "crypto_symbols.json"
_STOCK_DB  = PROJECT / "data" / "_ref" / "stock_symbols.json"

# Import blocklists from profiling so we stay in sync
try:
    from profiling.profile import CRYPTO_SYMBOL_BLOCKLIST, STOCK_SYMBOL_BLOCKLIST
except ImportError:
    CRYPTO_SYMBOL_BLOCKLIST = set()
    STOCK_SYMBOL_BLOCKLIST = set()


def _load_sets():
    crypto, stock = set(), set()
    if _CRYPTO_DB.exists():
        coins = json.loads(_CRYPTO_DB.read_text(encoding="utf-8"))
        crypto = {c["symbol"].lower() for c in coins
                  if c.get("symbol") and 3 <= len(c["symbol"]) <= 7
                  and c["symbol"].lower() not in CRYPTO_SYMBOL_BLOCKLIST}
    if _STOCK_DB.exists():
        stocks = json.loads(_STOCK_DB.read_text(encoding="utf-8"))
        stock = {s["ticker"].lower() for s in stocks
                 if s.get("ticker") and 3 <= len(s["ticker"]) <= 5
                 and s["ticker"].lower() not in STOCK_SYMBOL_BLOCKLIST}
    return crypto, stock - crypto  # crypto wins ties


_CRYPTO_SYMBOLS, _STOCK_SYMBOLS = _load_sets()

# ---- Patterns ----------------------------------------------------------------

# "Coin: BTC" or "Coin: River"
_COIN_LABEL = re.compile(r'\bcoin\s*:\s*([A-Za-z]{2,10})', re.IGNORECASE)

# Options contract: "IBIT 42c", "Hood 106p", "CLSK 10c 2/20/26"
_OPTION_CONTRACT = re.compile(
    r'\b([A-Z]{2,5})\s+(\d+(?:\.\d+)?)\s*(c|p|call|put)s?\b',
    re.IGNORECASE,
)

# "[TICKER] calls" or "[TICKER] puts" — options position report
_OPTION_LANG = re.compile(
    r'\b([A-Z]{2,5})\s+(calls?|puts?)\b',
    re.IGNORECASE,
)

# Any word that could be a ticker — case-insensitive, filter by DB
_BARE_TICKER = re.compile(r'\b([A-Za-z]{2,6})\b')


def detect(text: str) -> RuleResult:
    # 1. "Coin: XYZ" — highest confidence, explicit crypto template
    m = _COIN_LABEL.search(text)
    if m:
        sym = m.group(1).upper()
        sym_lo = sym.lower()
        if sym_lo in _CRYPTO_SYMBOLS:
            return RuleResult((sym, "CRYPTO"), 0.95,
                              [f'"Coin: {sym}" template -> CRYPTO DB match'])
        # Not in DB but explicitly labelled as coin — still call it crypto
        return RuleResult((sym, "CRYPTO"), 0.80,
                          [f'"Coin: {sym}" template -> not in top-500 DB, treating as CRYPTO'])

    # 2. Options contract notation: "IBIT 42c"
    for m in _OPTION_CONTRACT.finditer(text):
        sym = m.group(1).upper()
        if sym.lower() not in STOCK_SYMBOL_BLOCKLIST:
            return RuleResult((sym, "OPTION"), 0.92,
                              [f'option contract notation: "{m.group().strip()}"'])

    # 3. "[TICKER] calls/puts"
    for m in _OPTION_LANG.finditer(text):
        sym = m.group(1).upper()
        if sym.lower() not in STOCK_SYMBOL_BLOCKLIST:
            opt_type = m.group(2).lower()
            return RuleResult((sym, "OPTION"), 0.88,
                              [f'options language: "{m.group().strip()}"'])

    # 3b. "verb TICKER" grammar: "cut CAN here", "close IBIT", "sold SPY" — catches
    #     symbols not in DB when they appear directly after an action word.
    _VERB_SYM = re.compile(
        r'\b(?:cut|close[ds]?|closing|trim(?:med|ming)?|exit(?:ed|ing)?'
        r'|sold?|adding|load(?:ed|ing)?)\s+([A-Z]{2,6})\b',
        re.IGNORECASE,
    )
    for m in _VERB_SYM.finditer(text):
        sym = m.group(1).upper()
        sym_lo = sym.lower()
        original_caps = m.group(1)  # preserve original casing
        is_all_caps = original_caps == original_caps.upper() and len(original_caps) >= 2
        # Skip blocklisted words UNLESS they appear all-caps (e.g. "cut CAN" vs "cut can")
        if not is_all_caps and (sym_lo in STOCK_SYMBOL_BLOCKLIST or sym_lo in CRYPTO_SYMBOL_BLOCKLIST):
            continue
        # Skip obvious non-tickers
        if sym_lo in {'the','my','all','out','it','here','them','this','half','more','some','now','not'}:
            continue
        if sym_lo in _CRYPTO_SYMBOLS:
            return RuleResult((sym, "CRYPTO"), 0.88,
                              [f'verb-symbol grammar: "{m.group().strip()}" -> CRYPTO DB'])
        if sym_lo in _STOCK_SYMBOLS:
            return RuleResult((sym, "STOCK"), 0.85,
                              [f'verb-symbol grammar: "{m.group().strip()}" -> STOCK DB'])
        # Not in DB but grammar is very strong signal — treat as unknown stock
        return RuleResult((sym, "STOCK"), 0.72,
                          [f'verb-symbol grammar: "{m.group().strip()}" -> not in DB, assumed STOCK'])

    # 4 & 5. Scan ALL ticker mentions, then pick the one closest to an action phrase.
    # This prevents a contextually-mentioned ticker (e.g. "BTC was at 46k") from
    # winning over the actually-traded one ("cut CAN here").
    _ACTION_PHRASES = re.compile(
        r'\b(cut|cutting|close[ds]?|closing|trim(?:med|ming)?|exit(?:ed|ing)?'
        r'|stopped?\s+out|sold?|entry|entries|long|short|added?|loading)\b',
        re.IGNORECASE,
    )

    candidates = []  # (position_in_text, sym_upper, asset_type, confidence)
    for m in _BARE_TICKER.finditer(text):
        tok = m.group(1).lower()
        if tok in _CRYPTO_SYMBOLS:
            candidates.append((m.start(), tok.upper(), "CRYPTO", 0.75))
        elif tok in _STOCK_SYMBOLS:
            candidates.append((m.start(), tok.upper(), "STOCK", 0.70))

    if not candidates:
        return RuleResult((None, None), 0.0, ["no recognisable ticker found"])

    # Find position of first action phrase in text
    action_pos = None
    am = _ACTION_PHRASES.search(text)
    if am:
        action_pos = am.start()

    if action_pos is not None and len(candidates) > 1:
        # Pick the candidate whose position is closest to the action phrase
        best = min(candidates, key=lambda c: abs(c[0] - action_pos))
    else:
        # No action phrase or only one candidate — take first mention
        best = candidates[0]

    _, best_sym, best_type, best_conf = best
    return RuleResult((best_sym, best_type), best_conf,
                      [f'ticker mention: {best_sym} -> {best_type} DB match (nearest to action)'])
