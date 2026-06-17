"""Fetch US stock + ETF tickers from SEC EDGAR and cache locally.

Output: data/_ref/stock_symbols.json (list of {ticker, title}, ~10k records).

Why SEC EDGAR: it's authoritative, free, no API key, covers every US-listed
public company. ETFs like SPY, QQQ, IBIT are included alongside ordinary stocks.

Usage:
    python ingestion/fetch_stock_symbols.py
"""
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
DEST = PROJECT / "data" / "_ref" / "stock_symbols.json"
SUMMARY = PROJECT / "data" / "_ref" / "stock_symbols.md"
URL = "https://www.sec.gov/files/company_tickers.json"

FALLBACK = [
    {"ticker": "AAPL", "title": "Apple Inc."},
    {"ticker": "MSFT", "title": "Microsoft Corporation"},
    {"ticker": "NVDA", "title": "NVIDIA Corporation"},
    {"ticker": "GOOGL", "title": "Alphabet Inc."},
    {"ticker": "AMZN", "title": "Amazon.com Inc."},
    {"ticker": "META", "title": "Meta Platforms Inc."},
    {"ticker": "TSLA", "title": "Tesla Inc."},
    {"ticker": "AMD", "title": "Advanced Micro Devices"},
    {"ticker": "NFLX", "title": "Netflix Inc."},
    {"ticker": "PLTR", "title": "Palantir Technologies"},
    {"ticker": "SPY", "title": "SPDR S&P 500 ETF Trust"},
    {"ticker": "QQQ", "title": "Invesco QQQ Trust"},
    {"ticker": "IWM", "title": "iShares Russell 2000 ETF"},
    {"ticker": "DIA", "title": "SPDR Dow Jones Industrial Average ETF"},
    {"ticker": "IBIT", "title": "iShares Bitcoin Trust ETF"},
    {"ticker": "FBTC", "title": "Fidelity Wise Origin Bitcoin Fund"},
    {"ticker": "HOOD", "title": "Robinhood Markets Inc."},
    {"ticker": "CLSK", "title": "CleanSpark Inc."},
    {"ticker": "COIN", "title": "Coinbase Global Inc."},
    {"ticker": "MSTR", "title": "MicroStrategy Inc."},
    {"ticker": "MARA", "title": "Marathon Digital Holdings"},
    {"ticker": "RIOT", "title": "Riot Platforms Inc."},
]


def main() -> None:
    DEST.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(URL, headers={
        "User-Agent": "ProjectDolph2.0 contact@example.com",
    })
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            payload = json.loads(resp.read())
        # SEC returns {"0": {ticker, title, cik_str}, "1": {...}, ...}
        records = []
        for v in payload.values():
            t = v.get("ticker")
            if t:
                records.append({"ticker": t, "title": v.get("title", "")})
        print(f"fetched {len(records)} stocks/ETFs from SEC EDGAR")
    except (urllib.error.URLError, TimeoutError) as e:
        print(f"WARN: SEC EDGAR fetch failed ({e}); using {len(FALLBACK)}-stock fallback",
              file=sys.stderr)
        records = FALLBACK

    records_sorted = sorted(records, key=lambda r: r["ticker"])
    DEST.write_text(json.dumps(records_sorted, ensure_ascii=False), encoding="utf-8")
    print(f"wrote {DEST}  ({len(records_sorted)} symbols, {DEST.stat().st_size // 1024} KB)")

    lines = [
        "# Stock & ETF Symbols Reference (SEC EDGAR)",
        "",
        f"Total: {len(records_sorted)} symbols (alphabetical)",
        "",
        "| Ticker | Company / Fund Name |",
        "|--------|---------------------|",
    ]
    for r in records_sorted:
        lines.append(f"| {r['ticker']} | {r['title']} |")
    SUMMARY.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {SUMMARY}")


if __name__ == "__main__":
    main()
