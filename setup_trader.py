"""Add a new trader to the project.

Usage:
    python setup_trader.py <TraderName>

Creates:
    config/<TraderName>.json     -- copy of default config to customize
    data/<TraderName>/           -- data directory (messages go here)

After running:
    1. Edit config/<TraderName>.json to tune risk rules
    2. Add messages.jsonl to data/<TraderName>/
       (or re-run ingestion to pull from the workbook)
    3. python main.py <TraderName>       to profile
    4. python dev.py --corpus <TraderName>   to test the parser
    5. python dev.py --paper <TraderName> --save   to run mock pipeline
"""
import json
import shutil
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parent
CONFIG_DIR = PROJECT / "config"
DATA_DIR   = PROJECT / "data"


def setup(trader: str) -> None:
    if not trader or not trader.isidentifier():
        print(f"ERROR: '{trader}' is not a valid trader name (use letters/numbers/underscore).")
        sys.exit(1)

    config_path = CONFIG_DIR / f"{trader}.json"
    data_path   = DATA_DIR / trader

    created = []

    if not config_path.exists():
        default = json.loads((CONFIG_DIR / "default.json").read_text(encoding="utf-8"))
        default["_comment"] = f"{trader} — customize risk and parser settings here."
        config_path.write_text(json.dumps(default, indent=2), encoding="utf-8")
        created.append(str(config_path))
    else:
        print(f"  config already exists: {config_path}")

    for sub in ("signals", "profile"):
        (data_path / sub).mkdir(parents=True, exist_ok=True)
    if data_path not in [Path(str(p)) for p in created]:
        created.append(str(data_path))

    if created:
        print(f"\nCreated for trader '{trader}':")
        for p in created:
            print(f"  {p}")

    print(f"""
Next steps:
  1. Edit   config/{trader}.json            (tune risk rules)
  2. Add    data/{trader}/messages.jsonl    (or re-run ingestion)
  3. Run    python main.py {trader}         (profile)
  4. Run    python dev.py --corpus {trader} (test parser)
  5. Run    python dev.py --paper {trader} --save   (mock pipeline)
""")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python setup_trader.py <TraderName>")
        sys.exit(1)
    setup(sys.argv[1])
