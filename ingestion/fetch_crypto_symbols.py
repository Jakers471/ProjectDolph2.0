"""Fetch the top crypto coins by market cap from CoinGecko and cache locally.

Output: data/_ref/crypto_symbols.json (list of {id, symbol, name, market_cap_rank}).

Why top-N by market cap instead of the full ~17k list: the long tail is full of
meme tokens with English-word symbols (BELIEVE, RIVER, PROFIT, ...) that cause
massive false positives when matched against trading-chat language. Top 500
covers every coin a serious trader is likely to mention while keeping the
English-word collision risk low.

Usage:
    python ingestion/fetch_crypto_symbols.py
"""
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
DEST = PROJECT / "data" / "_ref" / "crypto_symbols.json"
SUMMARY = PROJECT / "data" / "_ref" / "crypto_symbols.md"
PAGES = 2  # 2 pages * 250 = 500 coins
PER_PAGE = 250
URL_TMPL = (
    "https://api.coingecko.com/api/v3/coins/markets"
    "?vs_currency=usd&order=market_cap_desc&per_page={per_page}&page={page}"
)

# Fallback if the API is unreachable — top symbols so the profiler still has *something*.
FALLBACK = [
    {"id": "bitcoin", "symbol": "btc", "name": "Bitcoin"},
    {"id": "ethereum", "symbol": "eth", "name": "Ethereum"},
    {"id": "solana", "symbol": "sol", "name": "Solana"},
    {"id": "ripple", "symbol": "xrp", "name": "XRP"},
    {"id": "dogecoin", "symbol": "doge", "name": "Dogecoin"},
    {"id": "cardano", "symbol": "ada", "name": "Cardano"},
    {"id": "avalanche-2", "symbol": "avax", "name": "Avalanche"},
    {"id": "polkadot", "symbol": "dot", "name": "Polkadot"},
    {"id": "chainlink", "symbol": "link", "name": "Chainlink"},
    {"id": "litecoin", "symbol": "ltc", "name": "Litecoin"},
    {"id": "matic-network", "symbol": "matic", "name": "Polygon"},
    {"id": "binancecoin", "symbol": "bnb", "name": "BNB"},
    {"id": "tron", "symbol": "trx", "name": "Tron"},
    {"id": "shiba-inu", "symbol": "shib", "name": "Shiba Inu"},
    {"id": "cosmos", "symbol": "atom", "name": "Cosmos"},
    {"id": "uniswap", "symbol": "uni", "name": "Uniswap"},
    {"id": "near", "symbol": "near", "name": "NEAR"},
    {"id": "apecoin", "symbol": "ape", "name": "ApeCoin"},
    {"id": "filecoin", "symbol": "fil", "name": "Filecoin"},
    {"id": "the-sandbox", "symbol": "sand", "name": "Sandbox"},
    {"id": "pepe", "symbol": "pepe", "name": "Pepe"},
    {"id": "bittensor", "symbol": "tao", "name": "Bittensor"},
    {"id": "gala", "symbol": "gala", "name": "GALA"},
    {"id": "quant", "symbol": "qnt", "name": "Quant"},
    {"id": "polyhedra-network", "symbol": "zkj", "name": "Polyhedra Network"},
]


def fetch_page(page: int):
    url = URL_TMPL.format(per_page=PER_PAGE, page=page)
    req = urllib.request.Request(url, headers={"User-Agent": "ProjectDolph2.0/0.1"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())


def main() -> None:
    DEST.parent.mkdir(parents=True, exist_ok=True)
    coins = []
    try:
        for page in range(1, PAGES + 1):
            chunk = fetch_page(page)
            coins.extend(chunk)
            print(f"fetched page {page}: {len(chunk)} coins (running total {len(coins)})")
            if page < PAGES:
                time.sleep(2)  # be polite to free API
    except (urllib.error.URLError, TimeoutError) as e:
        print(f"WARN: CoinGecko fetch failed ({e}); using {len(FALLBACK)}-coin fallback list",
              file=sys.stderr)
        coins = FALLBACK

    slim = [
        {"id": c.get("id"), "symbol": c.get("symbol"), "name": c.get("name"),
         "market_cap_rank": c.get("market_cap_rank")}
        for c in coins if c.get("symbol")
    ]
    DEST.write_text(json.dumps(slim, ensure_ascii=False), encoding="utf-8")
    print(f"wrote {DEST}  ({len(slim)} coins, {DEST.stat().st_size // 1024} KB)")

    lines = [
        "# Crypto Symbols Reference (CoinGecko — top 500 by market cap)",
        "",
        f"Total: {len(slim)} coins",
        "",
        "| Rank | Symbol | Name | ID |",
        "|------|--------|------|----|",
    ]
    for c in slim:
        rank = c.get("market_cap_rank") or ""
        lines.append(f"| {rank} | {(c['symbol'] or '').upper()} | {c.get('name', '')} | {c.get('id', '')} |")
    SUMMARY.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {SUMMARY}")


if __name__ == "__main__":
    main()
