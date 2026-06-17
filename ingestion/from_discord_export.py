"""Convert a DiscordChatExporter export into messages.jsonl for a trader.

Supports both export formats from DiscordChatExporter:
  JSON:  python ingestion/from_discord_export.py export.json Grizzlies
  CSV:   python ingestion/from_discord_export.py export.csv  Grizzlies

The trader name maps the messages to data/<Trader>/messages.jsonl.
Existing messages are merged and deduplicated by (timestamp, content).
Run `python main.py <Trader>` after importing to re-profile.
"""
import csv
import json
import re
import sys
from pathlib import Path

_HAS_TZ = re.compile(r'[+-]\d{2}:?\d{2}$|Z$')

def _normalize_ts(ts: str) -> str:
    """Ensure timestamp has exactly one timezone offset."""
    ts = ts.strip()
    if not ts:
        return ts
    if ts.endswith('Z'):
        return ts[:-1] + '+00:00'
    if not _HAS_TZ.search(ts):
        ts += '+00:00'
    return ts

PROJECT = Path(__file__).resolve().parent.parent
DATA = PROJECT / "data"


def _parse_json(path: Path, trader: str) -> list[dict]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    messages = raw.get("messages", raw) if isinstance(raw, dict) else raw
    out = []
    for m in messages:
        content = (m.get("content") or "").strip()
        if not content:
            continue
        ts = _normalize_ts(m.get("timestamp", ""))
        out.append({"analyst": trader, "timestamp": ts, "content": content})
    return out


def _parse_csv(path: Path, trader: str) -> list[dict]:
    out = []
    with path.open(encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            content = (row.get("Content") or row.get("content") or "").strip()
            if not content:
                continue
            ts = _normalize_ts(row.get("Date") or row.get("date") or row.get("Timestamp") or "")
            out.append({"analyst": trader, "timestamp": ts, "content": content})
    return out


def _load_existing(jsonl_path: Path) -> list[dict]:
    if not jsonl_path.exists():
        return []
    out = []
    for line in jsonl_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            out.append(json.loads(line))
    return out


def _dedup_merge(existing: list[dict], new: list[dict]) -> list[dict]:
    seen = {(m["timestamp"], m["content"]) for m in existing}
    added = 0
    for m in new:
        key = (m["timestamp"], m["content"])
        if key not in seen:
            existing.append(m)
            seen.add(key)
            added += 1
    existing.sort(key=lambda m: m["timestamp"])
    return existing, added


def main():
    if len(sys.argv) < 3:
        print("Usage: python ingestion/from_discord_export.py <export.json|export.csv> <TraderName>")
        sys.exit(1)

    export_path = Path(sys.argv[1])
    trader = sys.argv[2]

    if not export_path.exists():
        print(f"ERROR: file not found: {export_path}")
        sys.exit(1)

    print(f"Importing {export_path.name} -> trader={trader}")

    if export_path.suffix.lower() == ".json":
        new_msgs = _parse_json(export_path, trader)
    elif export_path.suffix.lower() == ".csv":
        new_msgs = _parse_csv(export_path, trader)
    else:
        print("ERROR: file must be .json or .csv")
        sys.exit(1)

    print(f"  Parsed {len(new_msgs)} messages from export")

    out_dir = DATA / trader
    out_dir.mkdir(parents=True, exist_ok=True)
    jsonl_path = out_dir / "messages.jsonl"
    csv_path = out_dir / "messages.csv"

    existing = _load_existing(jsonl_path)
    merged, added = _dedup_merge(existing, new_msgs)

    # write jsonl
    jsonl_path.write_text(
        "\n".join(json.dumps(m, ensure_ascii=False) for m in merged) + "\n",
        encoding="utf-8",
    )

    # write csv mirror
    with csv_path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["analyst", "timestamp", "content"])
        w.writeheader()
        w.writerows(merged)

    print(f"  Added {added} new messages ({len(existing) - added} already existed)")
    print(f"  Total: {len(merged)} messages in {jsonl_path}")
    print(f"\nNext step: python dev.py --paper {trader} --save")


if __name__ == "__main__":
    main()
