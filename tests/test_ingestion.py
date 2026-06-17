"""Tests for ingestion/to_jsonl.py output correctness."""
import json
from pathlib import Path
import pytest

PROJECT = Path(__file__).resolve().parent.parent
DATA = PROJECT / "data"

EXPECTED_TRADERS = ["ECS", "Eva", "Grizzlies", "Waxui", "Zabes", "Nando", "Ace"]


def _load_jsonl(trader: str) -> list[dict]:
    path = DATA / trader / "messages.jsonl"
    if not path.exists():
        pytest.skip(f"{path} not found — run main.py first")
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


@pytest.mark.parametrize("trader", EXPECTED_TRADERS)
def test_jsonl_exists(trader):
    assert (DATA / trader / "messages.jsonl").exists(), f"missing messages.jsonl for {trader}"


@pytest.mark.parametrize("trader", EXPECTED_TRADERS)
def test_csv_exists(trader):
    assert (DATA / trader / "messages.csv").exists(), f"missing messages.csv for {trader}"


@pytest.mark.parametrize("trader", EXPECTED_TRADERS)
def test_schema_fields(trader):
    rows = _load_jsonl(trader)
    assert rows, f"{trader} has zero messages"
    for i, row in enumerate(rows[:20]):
        assert "analyst" in row, f"row {i} missing 'analyst'"
        assert "timestamp" in row, f"row {i} missing 'timestamp'"
        assert "content" in row, f"row {i} missing 'content'"
        extra = set(row.keys()) - {"analyst", "timestamp", "content"}
        assert not extra, f"row {i} has unexpected keys: {extra}"


@pytest.mark.parametrize("trader", EXPECTED_TRADERS)
def test_analyst_matches_trader(trader):
    rows = _load_jsonl(trader)
    wrong = [r for r in rows if r.get("analyst") != trader]
    assert not wrong, f"{len(wrong)} rows have wrong analyst in {trader}"


@pytest.mark.parametrize("trader", EXPECTED_TRADERS)
def test_timestamps_sorted(trader):
    rows = _load_jsonl(trader)
    ts = [r["timestamp"] for r in rows]
    assert ts == sorted(ts), f"{trader} messages are not sorted by timestamp"


@pytest.mark.parametrize("trader", EXPECTED_TRADERS)
def test_empty_content_rate(trader):
    # Some rows have genuinely empty content (images, stickers, reactions from Discord).
    # We allow up to 10% empty — more than that suggests a parsing bug.
    rows = _load_jsonl(trader)
    empty = [r for r in rows if not r.get("content", "").strip()]
    rate = len(empty) / len(rows) if rows else 0
    assert rate <= 0.10, (
        f"{trader} has {len(empty)}/{len(rows)} ({rate:.1%}) empty-content rows — "
        "exceeds 10% threshold, likely a parsing issue"
    )


def test_total_message_count():
    total = 0
    for trader in EXPECTED_TRADERS:
        path = DATA / trader / "messages.jsonl"
        if not path.exists():
            pytest.skip("messages not generated yet")
        total += sum(1 for line in path.read_text(encoding="utf-8").splitlines() if line.strip())
    assert total > 3000, f"expected >3000 total messages across all traders, got {total}"
