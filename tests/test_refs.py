"""Tests for reference DBs: crypto_symbols.json and stock_symbols.json."""
import json
from pathlib import Path
import pytest

PROJECT = Path(__file__).resolve().parent.parent
REF = PROJECT / "data" / "_ref"

CRYPTO_PATH = REF / "crypto_symbols.json"
STOCK_PATH = REF / "stock_symbols.json"


def _load(path: Path) -> list[dict]:
    if not path.exists():
        pytest.skip(f"{path} not found — run main.py first")
    return json.loads(path.read_text(encoding="utf-8"))


# ---- Crypto DB ---------------------------------------------------------------

def test_crypto_db_size():
    coins = _load(CRYPTO_PATH)
    assert len(coins) >= 400, f"expected >=400 crypto symbols, got {len(coins)}"


def test_crypto_known_symbols_present():
    coins = _load(CRYPTO_PATH)
    symbols = {c["symbol"].upper() for c in coins}
    for expected in ("BTC", "ETH", "SOL", "XRP", "BNB"):
        assert expected in symbols, f"{expected} missing from crypto DB"


def test_crypto_schema():
    coins = _load(CRYPTO_PATH)
    for i, c in enumerate(coins[:20]):
        assert "id" in c, f"coin {i} missing 'id'"
        assert "symbol" in c, f"coin {i} missing 'symbol'"
        assert "name" in c, f"coin {i} missing 'name'"


def test_crypto_md_exists():
    if not CRYPTO_PATH.exists():
        pytest.skip("crypto DB not generated yet")
    assert (REF / "crypto_symbols.md").exists(), \
        "crypto_symbols.md not written — run `python ingestion/fetch_crypto_symbols.py` or `python main.py --refresh-refs`"


# ---- Stock DB ----------------------------------------------------------------

def test_stock_db_size():
    stocks = _load(STOCK_PATH)
    assert len(stocks) >= 5000, f"expected >=5000 stock symbols, got {len(stocks)}"


def test_stock_known_symbols_present():
    stocks = _load(STOCK_PATH)
    tickers = {r["ticker"].upper() for r in stocks}
    for expected in ("IBIT", "SPY", "QQQ", "HOOD", "NVDA", "TSLA"):
        assert expected in tickers, f"{expected} missing from stock DB"


def test_stock_schema():
    stocks = _load(STOCK_PATH)
    for i, r in enumerate(stocks[:20]):
        assert "ticker" in r, f"record {i} missing 'ticker'"
        assert "title" in r, f"record {i} missing 'title'"


def test_stock_sorted_alphabetically():
    stocks = _load(STOCK_PATH)
    if len(stocks) <= 22:
        pytest.skip("using fallback list — only generated after full refresh")
    tickers = [r["ticker"] for r in stocks]
    assert tickers == sorted(tickers), \
        "stock_symbols.json is not sorted alphabetically — run `python main.py --refresh-refs`"


def test_stock_md_exists():
    if not STOCK_PATH.exists():
        pytest.skip("stock DB not generated yet")
    if len(_load(STOCK_PATH)) <= 22:
        pytest.skip("using fallback list — run --refresh-refs to generate full DB + .md")
    assert (REF / "stock_symbols.md").exists(), \
        "stock_symbols.md not written — run `python main.py --refresh-refs`"
