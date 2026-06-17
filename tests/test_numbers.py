"""Unit tests for the number classifier in profiling/profile.py."""
import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from profiling.profile import classify_numbers


def _classes(text: str) -> set[str]:
    # classify_numbers returns list of (matched_text, class_name) tuples
    return {cls for _, cls in classify_numbers(text)}


def test_pct_class():
    assert "percentage" in _classes("up 3.5% on the day")


def test_dollar_class():
    assert "dollar_amount" in _classes("entry at $94,500")


def test_int_large_class():
    assert "int_large" in _classes("stop at 88000")


def test_int_small_class():
    assert "int_small" in _classes("20x leverage, 3 targets")


def test_decimal_short_class():
    assert "decimal_short" in _classes("entry 94.5 target 96.0")


def test_range_class():
    assert "number_range" in _classes("90000-91500 zone")


def test_list_class():
    # number_list = dash-separated sequence of 3+ numbers, e.g. multi-target chains
    assert "number_list" in _classes("targets 91000-92500-94000")


def test_km_suffix_class():
    assert "k_or_M_suffix" in _classes("volume hit 1.2M today")


def test_no_discord_noise():
    # Discord role IDs must not be classified as int_large
    result = _classes("<@&697950067285295115> entry long")
    assert "int_large" not in result, "Discord snowflake IDs should not be classified as numbers"


def test_empty_string():
    assert classify_numbers("") == []


def test_no_numbers():
    assert classify_numbers("just some words here") == []
