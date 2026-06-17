"""Action classifier: what kind of trade event is this message?

Returns one of: ENTRY | TRIM | EXIT | ADD | NOISE | UNSURE

Priority order (checked top-down, first match wins):
  1. NOISE  — social chat, URLs, no trade content
  2. EXIT   — stopped out, closed, cutting
  3. ADD    — DCA, adding, averaging
  4. TRIM   — tp hit, trimming, setting stops (on an open position)
  5. ENTRY  — coin:/entry: template, long/short setup
  6. UNSURE — something trade-like but can't classify cleanly
"""
import re
from parsing.signals_schema import RuleResult

# ---- Noise -------------------------------------------------------------------
_NOISE = re.compile(
    r'https?://'
    r'|instagram\.com'
    r'|\bgiveaway\b'
    r'|\bfollow\s+me\b'
    r'|\blike\s+and\s+comment\b'
    r"|valentine'?s\s+day",
    re.IGNORECASE,
)
# A message is NOISE if it has no numbers at all AND no action vocabulary
_HAS_NUMBERS = re.compile(r'\d')
_HAS_TRADE_WORDS = re.compile(
    r'\b(entry|entries|enter|coin|long|short|buy|sell|trim|trimming|trimmed|'
    r'stop|stopped|target|tps?|sl|calls?|leverage|margin|contracts?|cons?|'
    r'closed?|closing|cutting|cut|sold|hit|shorts?|longs?)\b',
    re.IGNORECASE,
)

# ---- Exit --------------------------------------------------------------------
_EXIT = re.compile(
    r'\bstopped?\s+out\b'
    r'|\bstop\s+(loss\s+)?hit\b'
    r'|\bsl\s+hit\b'
    r'|\bhit\s+(?:sl|stop(?:\s+loss)?)\b'      # "hit SL", "hit stop loss"
    r'|\bclosed?\s+out\b'
    r'|\bclosed?\s+(the\s+)?position\b'
    r'|\bclosed?\s+(my|the|here)\b'             # "closed my long", "closed here"
    r'|\bclose\s+\w{1,10}\s+here\b'            # "close ibit here", "close hood here"
    r'|\bclosing\b'                             # "closing btc long here"
    r'|\bcutting\b'
    r'|\bcut\s+(\w+\s+)?(?:here|-?\$?\d|it\b|them\b|this\b)\b'
    r'|\bno\s+longer\s+in\b'
    r'|\bexiting?\b'
    r'|\bfull\s+exit\b'
    r'|\ball\s+out\b'
    r'|\btaking\s+(a\s+)?loss\b'
    r'|\bsold\s+(the\s+)?(rest|entire|all)\b'
    r'|\bsold\s+(half\s+of\s+my|my|the)\s+\w+\s+position\b'  # "sold half of my position"
    r'|\bsold\s+half\b'                         # "sold half" (without "of position")
    r'|\bstops?\s+got\s+hit\b'
    r'|\ball\s+tps?\s+hit\b',
    re.IGNORECASE,
)

# ---- Add / DCA ---------------------------------------------------------------
_ADD = re.compile(
    r'\badding\s+(onto|more|to|here)\b'
    r'|\bdca\b'
    r'|\baveraging\s+(down|up)\b'
    r'|\bavg\s+(down|up)\b'
    r'|\bloaded\s+more\b'
    r'|\bbought\s+more\b'
    r'|\badded\s+(more|onto|to)\b'
    r'|\badded\s+\$?\d[\d,.]*\s+more\b',    # "added $500 more"
    re.IGNORECASE,
)

# ---- Trim --------------------------------------------------------------------
_TRIM = re.compile(
    r'\btrimm?(?:ing|ed)\b'
    r'|\btook\s+\d+\s*%'
    r'|\btp\s*[1-9]\b'                    # "tp3", "tp2 for btc", "tp5 did hit" — any numbered TP
    r'|\btp\s*(hit|filled)\b'
    r'|\bset\s+stops?\b'
    r'|\bsetting\s+stops?\b'
    r'|\bstops?\s+placed\b'
    r'|\bstops?\s+set\b'
    r'|\btaking\s+(profits?|partials?)\b'
    r'|\bcalls?\s+up\s+\d+\s*%'           # "calls up 20%"
    r'|\bputs?\s+up\s+\d+\s*%'            # "puts up 40%"
    r'|\bup\s+\d+\s*%\b'                  # "up 20%"
    r'|\btook\s+(half|some|profits?)\b'
    r'|\bsell(?:ing)?\s+half\b'           # "sell half", "selling half"
    r'|\bcollected\s+(?:another\s+)?\d+\s*%'  # "collected another 50%"
    r'|\bsecured\s+\$?\d[\d,.]*'          # "secured $76", "secured $155"
    r'|\b(bang\s*){2,}'                   # "bang bang" = celebration = tps hit
    r'|\bwhat\s+a\s+(gift|monday|week)\b',
    re.IGNORECASE,
)

# ---- Entry -------------------------------------------------------------------
_ENTRY = re.compile(
    r'(?:^|\n)\s*(long|short|crypto\s+play)\b'        # "Long" / "Short" leading a line
    r'|(?:^|\n)\s*(long|short)\s*\n'
    r'|(?:^|\n)\s*\w+\s+(long|short)\s*\n'            # "BTC long\n"
    r'|(?:^|\n)\s*\w+\s+(long|short)\s+[@$#\d]'       # "Btc long @68553" — price on same line
    r'|\bhigh\s+risk\s+(long|short)\b'                 # "High risk Short" Grizzlies template
    r'|\bentr(?:y|ies?)\s*:?\s*\d'                    # "Entry: 90000" or "Entry 1)"
    r'|\bentr(?:y|ies?)\s+targets?\b'                  # "Entry Targets:" template
    r'|\bentr(?:y|ies?)\s+zones?\b'                    # "Entry Zone:"
    r'|\bcoin\s*:'                                     # "Coin:" label
    r'|\bsetup\b.*\d'                                  # "setup" + numbers
    r'|\bloaded\s+(long|short)\b'
    r'|\bopened?\s+(a\s+)?(long|short|position)\b'
    r'|\bentering\b'
    r'|\bbuy\s+bids?\b'                              # "buy bids", "buy bid"
    r'|\bbids?\s+set\b'                              # "bids set"
    r'|\bgot\s+buy\s+bids?\s+set\b'                 # "got buy bids set"
    r'|\bwill\s+keep\s+setting\b'                   # "will keep setting"
    r'|\bwait(?:ing)?\s+to\s+get\s+filled\b'        # "waiting to get filled"
    r'|\bget\s+filled\b'                             # "get filled" = limit order pending
    r'|\blimit\s+order\b'
    r'|\b[A-Z]{2,5}\s+\d+(?:\.\d+)?\s*[cp]\b'
    r'|\b[A-Z]{2,5}\s+\d+(?:\.\d+)?\s*(call|put)s?\b',
    re.IGNORECASE | re.MULTILINE,
)


def detect(text: str) -> RuleResult:
    # 1. Explicit noise pattern
    if _NOISE.search(text):
        return RuleResult("NOISE", 0.95, [f"noise pattern matched"])

    has_numbers = bool(_HAS_NUMBERS.search(text))
    has_trade = bool(_HAS_TRADE_WORDS.search(text))

    # Pure social — no numbers, no trade words
    if not has_numbers and not has_trade:
        return RuleResult("NOISE", 0.85, ["no numbers, no trade vocabulary"])

    # 2. Exit (strong, specific phrases — check before trim)
    m = _EXIT.search(text)
    if m:
        return RuleResult("EXIT", 0.90, [f"exit phrase: '{m.group().strip()}'"])

    # 3. Add / DCA
    m = _ADD.search(text)
    if m:
        return RuleResult("ADD", 0.88, [f"add phrase: '{m.group().strip()}'"])

    # 4. Trim
    m = _TRIM.search(text)
    if m:
        return RuleResult("TRIM", 0.85, [f"trim phrase: '{m.group().strip()}'"])

    # 5. Entry
    m = _ENTRY.search(text)
    if m:
        return RuleResult("ENTRY", 0.85, [f"entry phrase: '{m.group().strip()}'"])

    # 6. Has trade words / numbers but can't classify → UNSURE
    if has_trade or has_numbers:
        return RuleResult("UNSURE", 0.35, ["trade content detected but action unclear"])

    return RuleResult("NOISE", 0.70, ["no classifiable content"])
