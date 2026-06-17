"""Tests for profiling output correctness (profile.json + PNG files).

profile.json schema (actual):
  trader, generated_at, source, crypto_db_size, stock_db_size,
  step1_foundation, step2_time_volume, step3_frequencies,
  step3b_tickers, step4_numbers, step5_structure, step6_unknowns

step1_foundation: total_messages, first_timestamp, last_timestamp, span_days, ...
step3b_tickers: validated_crypto_tickers, validated_stock_tickers, other_ticker_candidates
step4_numbers: total_numbers_found, by_class, examples_by_class
  by_class keys: number_list, number_range, dollar_amount, percentage,
                 k_or_M_suffix, decimal_long, decimal_short, int_large, int_small
"""
import json
from pathlib import Path
import pytest

PROJECT = Path(__file__).resolve().parent.parent
DATA = PROJECT / "data"

TRADERS = ["ECS", "Eva", "Grizzlies", "Waxui", "Zabes", "Nando", "Ace"]

EXPECTED_PNGS = [
    "dashboard.png",
    "frequencies.png",
    "tickers.png",
    "numbers.png",
    "structure.png",
]

PROFILE_TOP_KEYS = [
    "trader", "generated_at", "source",
    "step1_foundation", "step2_time_volume", "step3_frequencies",
    "step3b_tickers", "step4_numbers", "step5_structure", "step6_unknowns",
]

NUMBER_CLASSES = {
    "number_list", "number_range", "dollar_amount", "percentage",
    "k_or_M_suffix", "decimal_long", "decimal_short", "int_large", "int_small",
}


def _profile_dir(trader: str) -> Path:
    d = DATA / trader / "profile"
    if not d.exists():
        pytest.skip(f"{d} not found — run main.py first")
    return d


def _load_profile(trader: str) -> dict:
    path = _profile_dir(trader) / "profile.json"
    if not path.exists():
        pytest.skip(f"profile.json not found for {trader}")
    return json.loads(path.read_text(encoding="utf-8"))


# ---- File existence ----------------------------------------------------------

@pytest.mark.parametrize("trader", TRADERS)
@pytest.mark.parametrize("png", EXPECTED_PNGS)
def test_png_exists(trader, png):
    d = _profile_dir(trader)
    assert (d / png).exists(), f"{trader}/profile/{png} not found"


@pytest.mark.parametrize("trader", TRADERS)
@pytest.mark.parametrize("png", EXPECTED_PNGS)
def test_png_nonzero(trader, png):
    d = _profile_dir(trader)
    p = d / png
    if not p.exists():
        pytest.skip(f"{p} not found")
    assert p.stat().st_size > 1024, f"{trader}/profile/{png} is suspiciously small (<1KB)"


@pytest.mark.parametrize("trader", TRADERS)
def test_unknown_samples_exists(trader):
    d = _profile_dir(trader)
    assert (d / "unknown_samples.txt").exists(), f"{trader}/profile/unknown_samples.txt not found"


# ---- profile.json schema -----------------------------------------------------

@pytest.mark.parametrize("trader", TRADERS)
def test_profile_json_top_keys(trader):
    p = _load_profile(trader)
    for key in PROFILE_TOP_KEYS:
        assert key in p, f"profile.json for {trader} missing key '{key}'"


@pytest.mark.parametrize("trader", TRADERS)
def test_profile_message_count_positive(trader):
    p = _load_profile(trader)
    count = p.get("step1_foundation", {}).get("total_messages", 0)
    assert count > 0, f"{trader} profile shows 0 messages"


@pytest.mark.parametrize("trader", TRADERS)
def test_profile_tickers_structure(trader):
    p = _load_profile(trader)
    tickers = p.get("step3b_tickers", {})
    for section in ("validated_crypto_tickers", "validated_stock_tickers", "other_ticker_candidates"):
        assert section in tickers, f"{trader} step3b_tickers missing '{section}'"


@pytest.mark.parametrize("trader", TRADERS)
def test_profile_numbers_by_class(trader):
    p = _load_profile(trader)
    by_class = p.get("step4_numbers", {}).get("by_class", {})
    assert set(by_class.keys()) == NUMBER_CLASSES, \
        f"{trader} step4_numbers.by_class has unexpected keys: {set(by_class.keys())}"


# ---- Grizzlies spot-checks (known-good values from profiling run) ------------

def test_grizzlies_message_count():
    p = _load_profile("Grizzlies")
    count = p["step1_foundation"]["total_messages"]
    assert count >= 400, f"Grizzlies should have >=400 messages, got {count}"


def test_grizzlies_ibit_in_stocks():
    p = _load_profile("Grizzlies")
    stock_tickers = {e["token"].upper() for e in p["step3b_tickers"]["validated_stock_tickers"]}
    assert "IBIT" in stock_tickers, "IBIT should appear in Grizzlies stock tickers"


def test_grizzlies_btc_in_crypto():
    p = _load_profile("Grizzlies")
    crypto_tickers = {e["token"].upper() for e in p["step3b_tickers"]["validated_crypto_tickers"]}
    assert "BTC" in crypto_tickers, "BTC should appear in Grizzlies crypto tickers"
