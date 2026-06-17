"""Text-only profile reader. Prints %s and numbers from profile.json - no graphs.

Run after profile.py to see all findings in your terminal without opening PNGs.

Usage:
    python profiling/show.py <trader>
    e.g. python profiling/show.py Grizzlies
"""
import json
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
DATA = PROJECT / "data"


def hr(char="-", width=72):
    return char * width


def section(title):
    print()
    print(hr("="))
    print(title)
    print(hr("="))


def kv(label, value, width=28):
    print(f"  {label:<{width}} {value}")


def load_db_samples():
    """Return (crypto_sample, stock_sample) from data/_ref/ for display."""
    crypto_path = DATA / "_ref" / "crypto_symbols.json"
    stock_path = DATA / "_ref" / "stock_symbols.json"
    crypto, stocks = [], []
    if crypto_path.exists():
        coins = json.loads(crypto_path.read_text(encoding="utf-8"))
        crypto = [c["symbol"].upper() for c in coins if c.get("symbol")]
    if stock_path.exists():
        rows = json.loads(stock_path.read_text(encoding="utf-8"))
        stocks = [s["ticker"].upper() for s in rows if s.get("ticker")]
    return crypto, stocks


def main():
    if len(sys.argv) < 2:
        sys.exit("usage: python profiling/show.py <trader>")
    trader = sys.argv[1]
    src = DATA / trader / "profile" / "profile.json"
    if not src.exists():
        sys.exit(f"no profile yet - run `python profiling/profile.py {trader}` first")

    p = json.loads(src.read_text(encoding="utf-8"))
    total = p["step1_foundation"]["total_messages"]

    section(f"{trader} - PROFILE SUMMARY")
    kv("generated", p["generated_at"])
    kv("source", p["source"])
    kv("crypto DB size", f"{p['crypto_db_size']} symbols")
    kv("stock DB size", f"{p.get('stock_db_size', 0)} symbols")

    # DB samples — let the user verify what we pulled
    crypto_all, stock_all = load_db_samples()
    section("REFERENCE DATABASES (what we pulled)")
    print(f"  Crypto DB - top 40 of {len(crypto_all)} symbols (by market cap):")
    for chunk_start in range(0, min(40, len(crypto_all)), 10):
        print("    " + "  ".join(f"{s:<6}" for s in crypto_all[chunk_start:chunk_start + 10]))
    print(f"\n  Stock/ETF DB - first 40 of {len(stock_all)} symbols (alphabetical):")
    for chunk_start in range(0, min(40, len(stock_all)), 10):
        print("    " + "  ".join(f"{s:<6}" for s in stock_all[chunk_start:chunk_start + 10]))
    print(f"\n  Full lists: data/_ref/crypto_symbols.json, data/_ref/stock_symbols.json")

    # Step 1
    s1 = p["step1_foundation"]
    section("STEP 1 - Foundation")
    kv("total messages", total)
    kv("first message", s1["first_timestamp"])
    kv("last message", s1["last_timestamp"])
    kv("span (days)", s1["span_days"])
    kv("avg messages/day", s1["avg_messages_per_day"])

    print("\n  Message length (characters):")
    cl = s1["char_length"]
    for k in ["min", "p25", "median", "mean", "p75", "p95", "max"]:
        kv(f"  {k}", cl[k], width=14)

    print("\n  Message length (lines):")
    lc = s1["line_count"]
    for k in ["min", "p25", "median", "mean", "p75", "p95", "max"]:
        kv(f"  {k}", lc[k], width=14)

    print("\n  Surface traits (% of messages):")
    sc = s1["surface_counts"]
    for k, label in [
        ("multiline", "multi-line"),
        ("has_url", "contains URL"),
        ("has_digit", "contains digit"),
        ("has_dollar", "contains $"),
        ("has_hash", "contains #"),
        ("has_nonascii", "non-ASCII chars"),
    ]:
        kv(f"  {label}", f"{sc[k]['pct']:>5.1f}%  ({sc[k]['count']} msgs)")

    # Step 2
    s2 = p["step2_time_volume"]
    section("STEP 2 - Time / Volume")
    busiest = max(s2["messages_per_day"], key=lambda x: x["count"])
    peak_h = max(s2["hour_of_day_utc"], key=lambda h: s2["hour_of_day_utc"][h])
    peak_wd = max(s2["weekday_counts"], key=lambda w: s2["weekday_counts"][w])
    g = s2["gaps"]
    kv("busiest day", f"{busiest['date']}  ({busiest['count']} msgs)")
    kv("zero-msg days", f"{s2['zero_message_days']} of {s2['total_days_in_span']}")
    kv("peak hour (UTC)", f"{peak_h}:00  ({s2['hour_of_day_utc'][peak_h]} msgs)")
    kv("peak weekday", f"{peak_wd}  ({s2['weekday_counts'][peak_wd]} msgs)")
    kv("longest silence", f"{g.get('longest_gap_hours')}h")
    kv("median gap", f"{g.get('median_gap_hours')}h")
    kv("mean gap", f"{g.get('mean_gap_hours')}h")

    # Step 3 - frequencies
    s3 = p["step3_frequencies"]
    section("STEP 3 - Top n-grams")
    for label, key in [("UNIGRAMS (top 20)", "unigrams"),
                       ("BIGRAMS  (top 15)", "bigrams"),
                       ("TRIGRAMS (top 10)", "trigrams")]:
        limit = 20 if key == "unigrams" else (15 if key == "bigrams" else 10)
        print(f"\n  {label}:")
        for item in s3[key][:limit]:
            print(f"    {item['token']:<35s} {item['occurrences']:>5d} occurrences "
                  f"({item['msg_pct_proxy']:>5.1f}% of msgs)")

    # Step 3b - tickers
    s3b = p["step3b_tickers"]
    section("STEP 3b - Tickers")
    kv("crypto DB", f"{s3b['crypto_db_size']} symbols")
    kv("stock DB",  f"{s3b.get('stock_db_size', 0)} symbols")
    print("\n  VALIDATED CRYPTO TICKERS (top 20):")
    for item in s3b["validated_crypto_tickers"][:20]:
        print(f"    {item['token']:<10s} {item['occurrences']:>4d} occurrences   "
              f"in {item['messages']:>3d} msgs  ({item['msg_pct']:>5.1f}%)")
    print("\n  VALIDATED STOCK / ETF TICKERS (top 20):")
    for item in s3b.get("validated_stock_tickers", [])[:20]:
        print(f"    {item['token']:<10s} {item['occurrences']:>4d} occurrences   "
              f"in {item['messages']:>3d} msgs  ({item['msg_pct']:>5.1f}%)")
    print("\n  OTHER TICKER CANDIDATES ($X / #X / X/Y - in neither DB) (top 20):")
    for item in s3b["other_ticker_candidates"][:20]:
        print(f"    {item['token']:<10s} {item['occurrences']:>4d} occurrences   "
              f"in {item['messages']:>3d} msgs  ({item['msg_pct']:>5.1f}%)")

    # Step 4 - numbers
    s4 = p["step4_numbers"]
    section("STEP 4 - Number formats")
    kv("total numbers found", s4["total_numbers_found"])
    print("\n  By class:")
    for cls, info in s4["by_class"].items():
        ex = s4["examples_by_class"].get(cls, [])
        print(f"    {cls:<15s} {info['occurrences']:>5d} occurrences   "
              f"in {info['messages']:>3d} msgs ({info['msg_pct']:>5.1f}%)   "
              f"e.g. {', '.join(ex[:3])}")

    # Step 5 - structure
    s5 = p["step5_structure"]
    section("STEP 5 - Structural patterns")
    print("  LINE PREFIXES (top 15) - first 3 words of each line:")
    for item in s5["top_line_prefixes"][:15]:
        print(f"    {item['prefix']:<35s} {item['occurrences']:>4d} lines   "
              f"in {item['messages']:>3d} msgs ({item['msg_pct']:>5.1f}%)")

    print("\n  ACTION KEYWORDS - % of messages mentioning each:")
    sorted_kws = sorted(s5["action_keywords"].items(), key=lambda x: -x[1]["msg_pct"])
    for kw, info in sorted_kws:
        print(f"    {kw:<10s} {info['msg_pct']:>5.1f}%   "
              f"({info['messages']:>3d} msgs, {info['occurrences']:>4d} occurrences)")

    print("\n  ACTION KEYWORD CONTEXTS (top 5 neighbors each, in +/-5 word window):")
    for kw, neigh in s5["action_top_neighbors"].items():
        if not neigh:
            continue
        top5 = ", ".join(f"{n['token']}({n['count']})" for n in neigh[:5])
        print(f"    {kw:<10s} -> {top5}")

    # Step 6
    s6 = p["step6_unknowns"]
    section("STEP 6 - Unknown samples")
    kv("messages with a digit", s6["total_messages_with_digit"])
    kv("unknown messages", f"{s6['total_unknown_messages']}")
    kv("  as % of all msgs", f"{s6['unknown_pct_of_total']:.1f}%")
    kv("  as % of digit msgs", f"{s6['unknown_pct_of_digit_msgs']:.1f}%")
    kv("sample file", s6["sample_file"])

    print()
    print(hr("="))


if __name__ == "__main__":
    main()
