"""Language profiler.

Reads `data/<trader>/messages.jsonl` and writes:
  - data/<trader>/profile/profile.json     (machine-readable: all stats + %s)
  - data/<trader>/profile/dashboard.png    (overview: counts + time/volume)
  - data/<trader>/profile/frequencies.png  (top n-grams)
  - data/<trader>/profile/tickers.png      (validated crypto + other candidates)
  - data/<trader>/profile/numbers.png      (number-format classes)
  - data/<trader>/profile/structure.png    (line prefixes + action keywords w/ %)
  - data/<trader>/profile/unknown_samples.txt

Reads `data/_ref/crypto_symbols.json` to validate tickers. Run
`python ingestion/fetch_crypto_symbols.py` first to populate that.

Usage:
    python profiling/profile.py <trader>
"""
import json
import random
import re
import statistics
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

PROJECT = Path(__file__).resolve().parent.parent
DATA = PROJECT / "data"
CRYPTO_DB_PATH = DATA / "_ref" / "crypto_symbols.json"
STOCK_DB_PATH = DATA / "_ref" / "stock_symbols.json"
BAR_COLOR = "#3a7bd5"
STOCK_BAR_COLOR = "#7a3ad5"
WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

STOPWORDS = {
    "a", "an", "the", "and", "or", "but", "of", "to", "in", "on", "at", "for",
    "with", "from", "by", "is", "are", "was", "were", "be", "been", "being",
    "it", "its", "this", "that", "these", "those", "i", "you", "we", "they",
    "he", "she", "him", "her", "us", "them", "my", "your", "our", "their",
    "as", "if", "then", "so", "do", "does", "did", "have", "has", "had",
    "will", "would", "can", "could", "should", "may", "might", "just", "not",
    "no", "up", "down", "out", "over", "under", "now", "here", "there",
    "what", "when", "where", "who", "why", "how", "all", "any", "some",
    "more", "most", "much", "very", "still", "also", "than", "into", "about",
    "im", "ive", "ill", "dont", "didnt", "wont", "cant", "thats",
    "back", "lol", "yeah", "yes", "ok", "okay", "go", "get", "got", "good",
    "well", "see", "looks", "look", "like", "really", "too",
}

ACTION_KEYWORDS = [
    "entry", "entries", "target", "targets", "stop",
    "tp", "trim", "trimming", "long", "short", "buy",
    "sell", "bought", "sold", "hit", "exit", "stopped", "filled",
]

# A symbol from the crypto DB is "usable" only if it's not a common English
# word that would cause massive false positives. Built conservatively from
# observed Grizzlies false positives + general English commons.
CRYPTO_SYMBOL_BLOCKLIST = STOPWORDS | set(ACTION_KEYWORDS) | {
    "you", "me", "us", "is", "as", "at", "in", "on", "of", "to",
    "the", "and", "or", "if", "be", "do", "go", "we", "he", "she",
    "ai", "vr", "ar", "id", "pa", "ok", "fy", "im", "ya", "yo",
    # trading-message commons that collide with crypto symbols
    "set", "play", "high", "risk", "hype", "hold", "pump", "day", "one",
    "all", "same", "good", "like", "coin", "crypto", "low", "top",
    "fan", "fun", "joy", "key", "lot", "mid", "new", "old", "pay", "raw",
    "run", "see", "sky", "sub", "sun", "war", "win", "lotto", "don",
    "avg", "sl", "tp", "ll", "pt", "sl",
    "long", "short", "calls", "puts", "stop", "stops",
    "again", "ago", "also", "any", "around", "below", "above", "best",
    "big", "by", "came", "card", "case", "challenge", "check", "close",
    "come", "coming", "cut", "data", "deep", "down", "due", "easy", "eod",
    "end", "even", "ever", "every", "extra", "few", "first", "found",
    "free", "given", "great", "guys", "half", "hand", "hard", "hold",
    "hope", "ifs", "issue", "knew", "know", "last", "late", "lead", "left",
    "less", "letter", "level", "line", "list", "live", "load", "long",
    "loop", "made", "main", "make", "max", "min", "miss", "money", "month",
    "move", "name", "need", "next", "nice", "note", "off", "once", "only",
    "open", "opt", "part", "pass", "past", "peak", "perp", "plus", "post",
    "power", "price", "pull", "push", "put", "quick", "rate", "real",
    "reason", "report", "rest", "right", "risk", "room", "same", "save",
    "say", "second", "seen", "send", "short", "side", "since", "size",
    "small", "sort", "soon", "speed", "stack", "stage", "start", "state",
    "stay", "step", "stop", "such", "sure", "swing", "take", "talk",
    "term", "test", "thank", "thing", "think", "third", "though", "three",
    "thru", "till", "time", "today", "told", "took", "total", "trade",
    "true", "try", "tweet", "two", "type", "until", "upon", "use", "used",
    "user", "value", "view", "wait", "want", "warn", "watch", "way", "week",
    "went", "while", "white", "whole", "wide", "word", "work", "world",
    "year", "yet", "you", "yours", "zone",
    # confirmed false positives from Grizzlies corpus (English words in top-500 crypto DB)
    "tag", "baby", "night", "show", "safe", "bill", "ath", "cake", "gram", "cash", "prime",
}

# English words / trading slang that are valid SEC tickers but never used as stock symbols
# in this corpus. Confirmed false-positive by reading actual message context.
STOCK_SYMBOL_BLOCKLIST = CRYPTO_SYMBOL_BLOCKLIST | {
    # options/trading jargon used as plain words
    "con", "bid", "gap", "tap", "spot", "pre", "bit",
    # common English words
    "am", "gm", "man", "fast", "love", "gift", "give", "grab", "hour",
    "onto", "leg", "mind", "luck", "www",
    # abbreviations / slang
    "ain", "tho", "tbh", "ima",
    # crypto tickers misrouted into stock DB (traded as crypto, not as stock)
    "zkp",
    # stablecoins — never tradeable positions
    "usdt", "usdc", "busd", "dai", "tusd", "usdp",
    # confirmed false positives — English words that are valid tickers but used as plain speech
    "eat", "mac", "road", "fly", "wave", "pure",
}

KNOWN_MARKERS = [
    "entry", "target", "stop", "tp", "sl", "trim", "long", "short",
    "buy", "sell", "bought", "sold", "hit", "exit", "stopped", "filled",
    "average", "avg ", "@", "calls", "puts", " c ", " p ",
]


def load_crypto_symbols() -> set:
    if not CRYPTO_DB_PATH.exists():
        print(f"WARN: {CRYPTO_DB_PATH} missing - run ingestion/fetch_crypto_symbols.py", file=sys.stderr)
        return set()
    coins = json.loads(CRYPTO_DB_PATH.read_text(encoding="utf-8"))
    return {c["symbol"].lower() for c in coins
            if c.get("symbol") and 3 <= len(c["symbol"]) <= 7
            and c["symbol"].lower() not in CRYPTO_SYMBOL_BLOCKLIST}


def load_stock_symbols() -> set:
    if not STOCK_DB_PATH.exists():
        print(f"WARN: {STOCK_DB_PATH} missing - run ingestion/fetch_stock_symbols.py", file=sys.stderr)
        return set()
    stocks = json.loads(STOCK_DB_PATH.read_text(encoding="utf-8"))
    return {s["ticker"].lower() for s in stocks
            if s.get("ticker") and 3 <= len(s["ticker"]) <= 5
            and s["ticker"].lower() not in STOCK_SYMBOL_BLOCKLIST}


CRYPTO_SYMBOLS = load_crypto_symbols()
STOCK_SYMBOLS = load_stock_symbols()
# Crypto wins ties (someone says "BTC" → crypto, not the stock "BTC" if any)
STOCK_SYMBOLS_NOT_CRYPTO = STOCK_SYMBOLS - CRYPTO_SYMBOLS


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def parse_ts(s: str) -> datetime:
    return datetime.fromisoformat(s)


def percentile(sorted_vals, p: float):
    k = (len(sorted_vals) - 1) * p / 100
    f = int(k)
    c = min(f + 1, len(sorted_vals) - 1)
    if f == c:
        return sorted_vals[f]
    return sorted_vals[f] + (sorted_vals[c] - sorted_vals[f]) * (k - f)


def length_stats(values):
    s = sorted(values)
    return {
        "min": s[0],
        "p25": round(percentile(s, 25), 2),
        "median": round(percentile(s, 50), 2),
        "mean": round(statistics.mean(s), 2),
        "p75": round(percentile(s, 75), 2),
        "p95": round(percentile(s, 95), 2),
        "max": s[-1],
    }


def strip_discord_noise(text: str) -> str:
    text = re.sub(r"<@&?\d+>", " ", text)
    text = re.sub(r"<#\d+>", " ", text)
    text = re.sub(r"<:[^:]+:\d+>", " ", text)
    return text


def tokenize_words(text: str):
    text = strip_discord_noise(text)
    return [w.lower() for w in re.findall(r"[A-Za-z][A-Za-z']{1,}", text)]


def pct(n: int, total: int) -> float:
    return round(n / total * 100, 2) if total else 0.0


def horiz_bar(ax, items, title, xlabel="count", annotate_pct_of_total=None):
    items = list(items)
    labels = [i[0] for i in items][::-1]
    values = [i[1] for i in items][::-1]
    ax.barh(labels, values, color=BAR_COLOR)
    ax.set_title(title, fontsize=11)
    ax.set_xlabel(xlabel)
    ax.tick_params(axis="y", labelsize=9)
    if annotate_pct_of_total:
        for i, v in enumerate(values):
            if v > 0:
                p = v / annotate_pct_of_total * 100
                ax.text(v, i, f"  {p:.1f}%", va="center", fontsize=8, color="#444")


# ---------------------------------------------------------------------------
# Step 1 — Foundation
# ---------------------------------------------------------------------------

def step1_foundation(records):
    contents = [r["content"] for r in records]
    timestamps = [parse_ts(r["timestamp"]) for r in records]
    first, last = min(timestamps), max(timestamps)
    span_days = round((last - first).total_seconds() / 86400, 2)

    char_lengths = [len(c) for c in contents]
    line_counts = [c.count("\n") + 1 for c in contents]
    total = len(records)

    def surface(p):
        n = sum(1 for c in contents if p(c))
        return {"count": n, "pct": pct(n, total)}

    return {
        "total_messages": total,
        "first_timestamp": first.isoformat(),
        "last_timestamp": last.isoformat(),
        "span_days": span_days,
        "avg_messages_per_day": round(total / span_days, 2) if span_days else None,
        "char_length": length_stats(char_lengths),
        "line_count": length_stats(line_counts),
        "surface_counts": {
            "multiline": surface(lambda c: "\n" in c),
            "has_url": surface(lambda c: "http" in c),
            "has_digit": surface(lambda c: any(ch.isdigit() for ch in c)),
            "has_dollar": surface(lambda c: "$" in c),
            "has_hash": surface(lambda c: "#" in c),
            "has_nonascii": surface(lambda c: any(ord(ch) > 127 for ch in c)),
        },
    }


# ---------------------------------------------------------------------------
# Step 2 — Time / Volume
# ---------------------------------------------------------------------------

def step2_time_volume(records):
    timestamps = [parse_ts(r["timestamp"]) for r in records]

    per_day = Counter(t.date().isoformat() for t in timestamps)
    first_day = min(timestamps).date()
    last_day = max(timestamps).date()
    days = []
    d = first_day
    while d <= last_day:
        iso = d.isoformat()
        days.append({"date": iso, "count": per_day.get(iso, 0)})
        d = d + timedelta(days=1)

    hour_of_day = {str(h): 0 for h in range(24)}
    for t in timestamps:
        hour_of_day[str(t.hour)] += 1

    weekday_counts = {w: 0 for w in WEEKDAYS}
    for t in timestamps:
        weekday_counts[WEEKDAYS[t.weekday()]] += 1

    ts_sorted = sorted(timestamps)
    gaps = [(ts_sorted[i + 1] - ts_sorted[i]).total_seconds() / 3600 for i in range(len(ts_sorted) - 1)]
    if gaps:
        longest_idx = max(range(len(gaps)), key=lambda i: gaps[i])
        gap_stats = {
            "longest_gap_hours": round(gaps[longest_idx], 2),
            "longest_gap_start": ts_sorted[longest_idx].isoformat(),
            "longest_gap_end": ts_sorted[longest_idx + 1].isoformat(),
            "median_gap_hours": round(statistics.median(gaps), 2),
            "mean_gap_hours": round(statistics.mean(gaps), 2),
        }
    else:
        gap_stats = {"longest_gap_hours": None}

    return {
        "messages_per_day": days,
        "hour_of_day_utc": hour_of_day,
        "weekday_counts": weekday_counts,
        "zero_message_days": sum(1 for x in days if x["count"] == 0),
        "total_days_in_span": len(days),
        "gaps": gap_stats,
    }


# ---------------------------------------------------------------------------
# Step 3 — Frequencies (n-grams)
# ---------------------------------------------------------------------------

def messages_containing(records, token: str, ngram_n: int = 1) -> int:
    n = 0
    for r in records:
        toks = tokenize_words(r["content"])
        if ngram_n == 1:
            if token in toks:
                n += 1
        else:
            target = tuple(token.split(" "))
            for i in range(len(toks) - ngram_n + 1):
                if tuple(toks[i:i + ngram_n]) == target:
                    n += 1
                    break
    return n


def step3_frequencies(records, out_dir: Path, trader: str):
    total = len(records)
    all_uni, all_bi, all_tri = [], [], []
    for r in records:
        toks = [t for t in tokenize_words(r["content"]) if t not in STOPWORDS and len(t) > 1]
        all_uni.extend(toks)
        all_bi.extend(f"{toks[i]} {toks[i + 1]}" for i in range(len(toks) - 1))
        all_tri.extend(f"{toks[i]} {toks[i + 1]} {toks[i + 2]}" for i in range(len(toks) - 2))

    top_uni = Counter(all_uni).most_common(30)
    top_bi = Counter(all_bi).most_common(30)
    top_tri = Counter(all_tri).most_common(20)

    fig, axes = plt.subplots(1, 3, figsize=(22, 11))
    horiz_bar(axes[0], top_uni, "Top 30 unigrams (stopwords filtered)", annotate_pct_of_total=total)
    horiz_bar(axes[1], top_bi, "Top 30 bigrams", annotate_pct_of_total=total)
    horiz_bar(axes[2], top_tri, "Top 20 trigrams", annotate_pct_of_total=total)
    fig.suptitle(f"{trader} — Frequency Patterns  (annotations = occurrences ÷ total messages)",
                 fontsize=15, weight="bold")
    fig.tight_layout(rect=[0, 0, 1, 0.96])
    fig.savefig(out_dir / "frequencies.png", dpi=120, bbox_inches="tight")
    plt.close(fig)

    return {
        "unigrams": [{"token": t, "occurrences": c, "msg_pct_proxy": pct(c, total)} for t, c in top_uni],
        "bigrams": [{"token": t, "occurrences": c, "msg_pct_proxy": pct(c, total)} for t, c in top_bi],
        "trigrams": [{"token": t, "occurrences": c, "msg_pct_proxy": pct(c, total)} for t, c in top_tri],
    }


# ---------------------------------------------------------------------------
# Step 3b — Tickers (validated vs candidates)
# ---------------------------------------------------------------------------

def step3b_tickers(records, out_dir: Path, trader: str):
    total = len(records)
    crypto = Counter(); crypto_msg = Counter()
    stock = Counter(); stock_msg = Counter()
    other = Counter(); other_msg = Counter()

    prefix_patterns = [
        re.compile(r"\$([A-Za-z][A-Za-z0-9]{1,5})\b"),
        re.compile(r"\b([A-Za-z][A-Za-z0-9]{1,5})/[A-Za-z]+\b"),
        re.compile(r"#([A-Za-z][A-Za-z0-9]{1,9})\b"),
    ]

    for r in records:
        text = strip_discord_noise(r["content"])
        msg_crypto, msg_stock, msg_other = set(), set(), set()

        for t in tokenize_words(r["content"]):
            if t in CRYPTO_SYMBOLS:
                crypto[t.upper()] += 1
                msg_crypto.add(t.upper())
            elif t in STOCK_SYMBOLS_NOT_CRYPTO:
                stock[t.upper()] += 1
                msg_stock.add(t.upper())

        for pat in prefix_patterns:
            for m in pat.finditer(text):
                tok = m.group(1)
                low = tok.lower()
                if low in CRYPTO_SYMBOLS or low in STOCK_SYMBOLS_NOT_CRYPTO:
                    continue  # already caught via word path
                other[tok.upper()] += 1
                msg_other.add(tok.upper())

        for tk in msg_crypto: crypto_msg[tk] += 1
        for tk in msg_stock: stock_msg[tk] += 1
        for tk in msg_other: other_msg[tk] += 1

    top_crypto = crypto.most_common(30)
    top_stock = stock.most_common(30)
    top_other = other.most_common(30)

    fig, axes = plt.subplots(1, 3, figsize=(24, 11))
    horiz_bar(axes[0], top_crypto,
              f"Validated CRYPTO tickers  (DB: {len(CRYPTO_SYMBOLS)} symbols)",
              annotate_pct_of_total=total)
    # Style stock chart differently to visually separate
    items = list(top_stock)
    labels = [i[0] for i in items][::-1]
    values = [i[1] for i in items][::-1]
    axes[1].barh(labels, values, color=STOCK_BAR_COLOR)
    axes[1].set_title(f"Validated STOCK / ETF tickers  (DB: {len(STOCK_SYMBOLS)} symbols)", fontsize=11)
    axes[1].set_xlabel("count")
    axes[1].tick_params(axis="y", labelsize=9)
    if total:
        for i, v in enumerate(values):
            axes[1].text(v, i, f"  {v / total * 100:.1f}%", va="center", fontsize=8, color="#444")
    horiz_bar(axes[2], top_other,
              "Other candidates ($X / #X / X/Y - in neither DB)",
              annotate_pct_of_total=total)
    fig.suptitle(f"{trader} - Tickers  (annotations = % of messages mentioning)",
                 fontsize=15, weight="bold")
    fig.tight_layout(rect=[0, 0, 1, 0.96])
    fig.savefig(out_dir / "tickers.png", dpi=120, bbox_inches="tight")
    plt.close(fig)

    return {
        "crypto_db_size": len(CRYPTO_SYMBOLS),
        "stock_db_size": len(STOCK_SYMBOLS),
        "validated_crypto_tickers": [
            {"token": t, "occurrences": c, "messages": crypto_msg[t],
             "msg_pct": pct(crypto_msg[t], total)} for t, c in top_crypto
        ],
        "validated_stock_tickers": [
            {"token": t, "occurrences": c, "messages": stock_msg[t],
             "msg_pct": pct(stock_msg[t], total)} for t, c in top_stock
        ],
        "other_ticker_candidates": [
            {"token": t, "occurrences": c, "messages": other_msg[t],
             "msg_pct": pct(other_msg[t], total)} for t, c in top_other
        ],
    }


# ---------------------------------------------------------------------------
# Step 4 — Number formats
# ---------------------------------------------------------------------------

NUMBER_PATTERNS = [
    ("number_list",   re.compile(r"\$?\d+(?:\.\d+)?(?:\s*[-–]\s*\d+(?:\.\d+)?){2,}")),
    ("number_range",  re.compile(r"\$?\d+(?:\.\d+)?\s*[-–]\s*\d+(?:\.\d+)?")),
    ("dollar_amount", re.compile(r"\$\d+(?:\.\d+)?[kKmM]?")),
    ("percentage",    re.compile(r"\d+(?:\.\d+)?%")),
    ("k_or_M_suffix", re.compile(r"\b\d+(?:\.\d+)?[kKmM]\b")),
    ("decimal_long",  re.compile(r"\b\d+\.\d{3,}\b")),
    ("decimal_short", re.compile(r"\b\d+\.\d{1,2}\b")),
    ("int_large",     re.compile(r"\b\d{4,}\b")),
    ("int_small",     re.compile(r"\b\d{1,3}\b")),
]


def classify_numbers(text: str):
    text = strip_discord_noise(text)
    consumed = [False] * len(text)
    found = []
    for cls, pat in NUMBER_PATTERNS:
        for m in pat.finditer(text):
            if any(consumed[m.start():m.end()]):
                continue
            found.append((m.group(0).strip(), cls))
            for i in range(m.start(), m.end()):
                consumed[i] = True
    return found


def step4_numbers(records, out_dir: Path, trader: str):
    total = len(records)
    counts = Counter()
    msg_with_class = Counter()
    examples = {}
    for r in records:
        seen = set()
        for tok, cls in classify_numbers(r["content"]):
            counts[cls] += 1
            seen.add(cls)
            examples.setdefault(cls, [])
            if len(examples[cls]) < 8 and tok not in examples[cls]:
                examples[cls].append(tok)
        for cls in seen:
            msg_with_class[cls] += 1

    ordered = [(cls, counts.get(cls, 0)) for cls, _ in NUMBER_PATTERNS]

    fig, ax = plt.subplots(figsize=(14, 6))
    labels = [c for c, _ in ordered]
    values = [v for _, v in ordered]
    ax.bar(labels, values, color=BAR_COLOR)
    ax.set_title(f"{trader} — Number-format classes  (annotation: % of messages with this class)",
                 fontsize=13, weight="bold")
    ax.set_ylabel("occurrences")
    ax.tick_params(axis="x", rotation=20)
    for i, (cls, v) in enumerate(ordered):
        if v:
            mp = pct(msg_with_class.get(cls, 0), total)
            ax.text(i, v, f"{v}\n({mp:.1f}%)", ha="center", va="bottom", fontsize=9)
    fig.tight_layout()
    fig.savefig(out_dir / "numbers.png", dpi=120, bbox_inches="tight")
    plt.close(fig)

    return {
        "total_numbers_found": sum(counts.values()),
        "by_class": {
            cls: {
                "occurrences": counts.get(cls, 0),
                "messages": msg_with_class.get(cls, 0),
                "msg_pct": pct(msg_with_class.get(cls, 0), total),
            } for cls, _ in NUMBER_PATTERNS
        },
        "examples_by_class": {cls: examples.get(cls, []) for cls, _ in NUMBER_PATTERNS},
    }


# ---------------------------------------------------------------------------
# Step 5 — Structure (line prefixes + action contexts)
# ---------------------------------------------------------------------------

def line_prefix(line: str, n_words: int = 3) -> str:
    line = line.strip().lower()
    if not line:
        return ""
    parts = re.split(r"\s+", line)
    return " ".join(parts[:n_words])


def step5_structure(records, out_dir: Path, trader: str):
    total = len(records)
    prefix_counts = Counter()
    prefix_msg = Counter()
    action_occ = Counter()
    action_msg = Counter()
    neighbors = {kw: Counter() for kw in ACTION_KEYWORDS}

    for r in records:
        clean = strip_discord_noise(r["content"])
        seen_prefixes = set()
        for line in clean.splitlines():
            p = line_prefix(line, 3)
            if p:
                prefix_counts[p] += 1
                seen_prefixes.add(p)
        for p in seen_prefixes:
            prefix_msg[p] += 1

        toks = tokenize_words(r["content"])
        seen_actions = set()
        for i, t in enumerate(toks):
            if t in ACTION_KEYWORDS:
                action_occ[t] += 1
                seen_actions.add(t)
                lo = max(0, i - 5)
                hi = min(len(toks), i + 6)
                for j in range(lo, hi):
                    if j == i:
                        continue
                    n = toks[j]
                    if n in STOPWORDS or len(n) < 2 or n in ACTION_KEYWORDS:
                        continue
                    neighbors[t][n] += 1
        for kw in seen_actions:
            action_msg[kw] += 1

    top_prefixes = prefix_counts.most_common(25)
    top_actions_sorted = sorted(ACTION_KEYWORDS, key=lambda k: -action_msg.get(k, 0))

    fig, axes = plt.subplots(1, 2, figsize=(20, 10))
    # Line prefixes — annotate with % of messages
    items_pref = [(p, c) for p, c in top_prefixes]
    horiz_bar(axes[0], items_pref, "Top 25 line prefixes")
    # annotate with msg pct
    for i, (p, _) in enumerate(items_pref[::-1]):
        mp = pct(prefix_msg.get(p, 0), total)
        v = prefix_counts[p]
        axes[0].text(v, i, f"  {mp:.1f}%", va="center", fontsize=8, color="#444")

    # Actions — sort by msg presence, show % of messages prominently
    labels = top_actions_sorted[::-1]
    vals = [action_occ.get(k, 0) for k in labels]
    pcts = [pct(action_msg.get(k, 0), total) for k in labels]
    axes[1].barh(labels, vals, color=BAR_COLOR)
    axes[1].set_title("Action keywords  (annotation = % of messages mentioning)", fontsize=11)
    axes[1].set_xlabel("occurrences")
    for i, (v, p) in enumerate(zip(vals, pcts)):
        if v > 0:
            axes[1].text(v, i, f"  {v}  ({p:.1f}% of msgs)", va="center", fontsize=9)
    fig.suptitle(f"{trader} — Structural Patterns", fontsize=16, weight="bold")
    fig.tight_layout(rect=[0, 0, 1, 0.96])
    fig.savefig(out_dir / "structure.png", dpi=120, bbox_inches="tight")
    plt.close(fig)

    return {
        "top_line_prefixes": [
            {"prefix": p, "occurrences": c, "messages": prefix_msg[p],
             "msg_pct": pct(prefix_msg[p], total)}
            for p, c in top_prefixes
        ],
        "action_keywords": {
            kw: {
                "occurrences": action_occ.get(kw, 0),
                "messages": action_msg.get(kw, 0),
                "msg_pct": pct(action_msg.get(kw, 0), total),
            } for kw in ACTION_KEYWORDS
        },
        "action_top_neighbors": {
            kw: [{"token": n, "count": c} for n, c in neighbors[kw].most_common(10)]
            for kw in ACTION_KEYWORDS
        },
    }


# ---------------------------------------------------------------------------
# Step 6 — Unknown samples
# ---------------------------------------------------------------------------

def step6_unknowns(records, out_dir: Path, trader: str):
    total = len(records)
    unknowns = []
    for r in records:
        c = r["content"]
        if not c or not any(ch.isdigit() for ch in c):
            continue
        low = c.lower()
        if any(marker in low for marker in KNOWN_MARKERS):
            continue
        unknowns.append(r)

    rng = random.Random(42)
    sample = rng.sample(unknowns, min(50, len(unknowns)))

    out_file = out_dir / "unknown_samples.txt"
    lines = [
        f"# {trader} — Unknown-format samples",
        f"# Criterion: contains digit, no known structural marker substring",
        f"# Known markers: {', '.join(KNOWN_MARKERS)}",
        f"# Total unknown: {len(unknowns)} of {total} messages ({pct(len(unknowns), total)}%)",
        f"# Showing {len(sample)} random samples below.",
        "",
    ]
    for r in sample:
        lines.append("=" * 70)
        lines.append(f"[{r['timestamp']}]")
        lines.append(r["content"])
        lines.append("")
    out_file.write_text("\n".join(lines), encoding="utf-8")

    digit_msgs = sum(1 for r in records if any(ch.isdigit() for ch in r["content"]))
    return {
        "total_unknown_messages": len(unknowns),
        "total_messages_with_digit": digit_msgs,
        "unknown_pct_of_total": pct(len(unknowns), total),
        "unknown_pct_of_digit_msgs": pct(len(unknowns), digit_msgs),
        "criterion": "contains digit AND no known structural marker substring",
        "known_markers_checked": KNOWN_MARKERS,
        "sample_file": "unknown_samples.txt",
        "sample_count": len(sample),
    }


# ---------------------------------------------------------------------------
# Dashboard (step 1+2 overview with %)
# ---------------------------------------------------------------------------

def render_dashboard(trader, profile, records, out_path):
    s1 = profile["step1_foundation"]
    s2 = profile["step2_time_volume"]
    s5 = profile["step5_structure"]
    cl = s1["char_length"]
    lc = s1["line_count"]
    sc = s1["surface_counts"]

    fig = plt.figure(figsize=(20, 13))
    gs = fig.add_gridspec(4, 3, height_ratios=[0.35, 1.4, 1.4, 1.6], hspace=0.55, wspace=0.3)

    ax_header = fig.add_subplot(gs[0, :])
    ax_header.axis("off")
    header_text = (
        f"{trader} — Language Profile\n"
        f"{s1['total_messages']} messages  •  {s1['span_days']:.0f} days "
        f"({s1['first_timestamp'][:10]} to {s1['last_timestamp'][:10]})  -  "
        f"{s1['avg_messages_per_day']:.2f} msgs/day  •  "
        f"median: {cl['median']:.0f} chars / {lc['median']:.0f} lines"
    )
    ax_header.text(0.5, 0.5, header_text, ha="center", va="center", fontsize=15, weight="bold")

    ax_mpd = fig.add_subplot(gs[1, :])
    dates = [x["date"] for x in s2["messages_per_day"]]
    counts = [x["count"] for x in s2["messages_per_day"]]
    ax_mpd.bar(range(len(dates)), counts, color=BAR_COLOR)
    ax_mpd.set_title("Messages per day", fontsize=13)
    ax_mpd.set_ylabel("messages")
    tick_step = max(1, len(dates) // 14)
    ax_mpd.set_xticks(range(0, len(dates), tick_step))
    ax_mpd.set_xticklabels([dates[i] for i in range(0, len(dates), tick_step)], rotation=45, ha="right", fontsize=9)

    ax_hour = fig.add_subplot(gs[2, 0])
    hours = list(range(24))
    ax_hour.bar(hours, [s2["hour_of_day_utc"][str(h)] for h in hours], color=BAR_COLOR)
    ax_hour.set_title("Hour of day (UTC)", fontsize=12)
    ax_hour.set_xticks([0, 4, 8, 12, 16, 20, 23])
    ax_hour.set_xlabel("hour")

    ax_wd = fig.add_subplot(gs[2, 1])
    ax_wd.bar(WEEKDAYS, [s2["weekday_counts"][w] for w in WEEKDAYS], color=BAR_COLOR)
    ax_wd.set_title("Weekday", fontsize=12)

    ax_len = fig.add_subplot(gs[2, 2])
    char_lens = [len(r["content"]) for r in records]
    ax_len.hist(char_lens, bins=30, color=BAR_COLOR)
    ax_len.set_title("Message length (chars)", fontsize=12)
    ax_len.set_xlabel("characters")

    def panel(ax, title, lines):
        ax.axis("off")
        ax.text(0, 1, title, fontsize=12, weight="bold", va="top")
        ax.text(0, 0.88, "\n".join(lines), family="monospace", fontsize=10, va="top")

    panel(fig.add_subplot(gs[3, 0]), "Surface traits (% of messages)", [
        f"multi-line:     {sc['multiline']['pct']:>5.1f}%  ({sc['multiline']['count']})",
        f"contains URL:   {sc['has_url']['pct']:>5.1f}%  ({sc['has_url']['count']})",
        f"contains digit: {sc['has_digit']['pct']:>5.1f}%  ({sc['has_digit']['count']})",
        f"contains $:     {sc['has_dollar']['pct']:>5.1f}%  ({sc['has_dollar']['count']})",
        f"contains #:     {sc['has_hash']['pct']:>5.1f}%  ({sc['has_hash']['count']})",
        f"non-ASCII:      {sc['has_nonascii']['pct']:>5.1f}%  ({sc['has_nonascii']['count']})",
    ])

    # Action keyword % panel — direct answer to "how often does buy/sell come up"
    ak = s5["action_keywords"]
    sorted_kws = sorted(ACTION_KEYWORDS, key=lambda k: -ak[k]["msg_pct"])[:10]
    panel(fig.add_subplot(gs[3, 1]), "Action keywords (% of messages)",
          [f"{k:<10s} {ak[k]['msg_pct']:>5.1f}%  ({ak[k]['messages']} msgs)" for k in sorted_kws])

    busiest = max(s2["messages_per_day"], key=lambda x: x["count"])
    peak_h = max(s2["hour_of_day_utc"], key=lambda h: s2["hour_of_day_utc"][h])
    peak_wd = max(s2["weekday_counts"], key=lambda w: s2["weekday_counts"][w])
    g = s2["gaps"]
    panel(fig.add_subplot(gs[3, 2]), "Time / volume highlights", [
        f"busiest day:    {busiest['date']} ({busiest['count']} msgs)",
        f"zero-msg days:  {s2['zero_message_days']} of {s2['total_days_in_span']}",
        f"peak hour UTC:  {peak_h}:00 ({s2['hour_of_day_utc'][peak_h]} msgs)",
        f"peak weekday:   {peak_wd} ({s2['weekday_counts'][peak_wd]} msgs)",
        f"longest gap:    {g.get('longest_gap_hours')}h",
        f"median gap:     {g.get('median_gap_hours')}h",
        f"mean gap:       {g.get('mean_gap_hours')}h",
    ])

    fig.savefig(out_path, dpi=120, bbox_inches="tight")
    plt.close(fig)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def profile_trader(trader: str, verbose: bool = True) -> dict:
    """Run all six profiling steps for one trader. Returns a small result summary."""
    src = DATA / trader / "messages.jsonl"
    if not src.exists():
        raise FileNotFoundError(f"no such corpus: {src}")
    out_dir = DATA / trader / "profile"
    out_dir.mkdir(parents=True, exist_ok=True)

    records = [json.loads(line) for line in src.read_text(encoding="utf-8").splitlines() if line.strip()]
    if not records:
        raise ValueError(f"empty corpus: {trader}")

    profile = {
        "trader": trader,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": f"data/{trader}/messages.jsonl",
        "crypto_db_size": len(CRYPTO_SYMBOLS),
        "stock_db_size": len(STOCK_SYMBOLS),
        "step1_foundation": step1_foundation(records),
        "step2_time_volume": step2_time_volume(records),
        "step3_frequencies": step3_frequencies(records, out_dir, trader),
        "step3b_tickers": step3b_tickers(records, out_dir, trader),
        "step4_numbers": step4_numbers(records, out_dir, trader),
        "step5_structure": step5_structure(records, out_dir, trader),
        "step6_unknowns": step6_unknowns(records, out_dir, trader),
    }

    render_dashboard(trader, profile, records, out_dir / "dashboard.png")
    (out_dir / "profile.json").write_text(json.dumps(profile, indent=2, ensure_ascii=False), encoding="utf-8")

    files = [
        "profile.json", "dashboard.png", "frequencies.png", "tickers.png",
        "numbers.png", "structure.png", "unknown_samples.txt",
    ]
    if verbose:
        for f in files:
            print(f"wrote {out_dir / f}")
        print(f"\ntip: run `python profiling/show.py {trader}` for a text-only data dump")

    return {
        "trader": trader,
        "out_dir": out_dir,
        "messages": len(records),
        "files": files,
    }


def main():
    if len(sys.argv) < 2:
        sys.exit("usage: python profiling/profile.py <trader>")
    profile_trader(sys.argv[1], verbose=True)


if __name__ == "__main__":
    main()
