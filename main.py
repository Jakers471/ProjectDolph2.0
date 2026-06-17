"""End-to-end pipeline sweep.

One command to:
  1. Ingest the source workbook -> per-trader messages.{csv,jsonl}
  2. Refresh reference DBs (crypto coins, US stocks/ETFs) if missing
  3. Profile every trader (all 6 steps -> PNGs + profile.json)

Usage:
    python main.py                  # full sweep on all traders found under data/
    python main.py Grizzlies        # full sweep but only profile Grizzlies
    python main.py --refresh-refs   # force re-fetch of crypto+stock DBs

Colored output uses ANSI escape codes. On Windows 10+ the os.system("") call
below enables the virtual-terminal sequence processing automatically.
"""
import os
import sys
import time
from pathlib import Path

PROJECT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT))

if sys.platform == "win32":
    os.system("")  # enable ANSI escape sequences on Windows


# ---- Colors / logger ------------------------------------------------------

RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
RED = "\033[31m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
BLUE = "\033[34m"
MAGENTA = "\033[35m"
CYAN = "\033[36m"
GRAY = "\033[90m"
BR_GREEN = "\033[92m"
BR_RED = "\033[91m"
BR_CYAN = "\033[96m"
BR_YELLOW = "\033[93m"

LEVEL_COLOR = {
    "STEP":   BR_CYAN + BOLD,
    "INFO":   BLUE,
    "DETAIL": GRAY,
    "WARN":   YELLOW,
    "ERROR":  BR_RED + BOLD,
    "DONE":   BR_GREEN + BOLD,
    "TIMING": DIM + CYAN,
}


def log(level: str, msg: str) -> None:
    color = LEVEL_COLOR.get(level, "")
    print(f"{color}[{level:6}]{RESET} {msg}", flush=True)


def banner(text: str) -> None:
    bar = "=" * 72
    print(f"\n{BR_CYAN}{BOLD}{bar}{RESET}")
    print(f"{BR_CYAN}{BOLD}  {text}{RESET}")
    print(f"{BR_CYAN}{BOLD}{bar}{RESET}\n")


# ---- Pipeline steps -------------------------------------------------------

def step_ingest() -> float:
    banner("STEP 1: Ingest source workbook")
    log("STEP", "Reading data/_full_workbook.xlsx and writing per-trader files")
    t0 = time.perf_counter()
    from ingestion.to_jsonl import main as ingest_main
    ingest_main()
    elapsed = time.perf_counter() - t0
    log("TIMING", f"ingestion finished in {elapsed:.2f}s")
    return elapsed


def _show_ref_db(label: str, path: Path, sample_key: str, sample_count: int = 8) -> None:
    import json as _json
    data = _json.loads(path.read_text(encoding="utf-8"))
    total = len(data)
    samples = [str(r.get(sample_key, "")).upper() for r in data[:sample_count]]
    log("INFO", f"{label}: {total:,} symbols  ->  {path.relative_to(PROJECT)}")
    log("DETAIL", f"  first {sample_count}: {', '.join(samples)}")
    md = path.with_suffix(".md")
    if md.exists():
        log("DETAIL", f"  browsable: {md.relative_to(PROJECT)}")


def step_refresh_refs(force: bool) -> float:
    banner("STEP 2: Reference databases (crypto + stocks)")
    crypto_path = PROJECT / "data" / "_ref" / "crypto_symbols.json"
    stock_path = PROJECT / "data" / "_ref" / "stock_symbols.json"

    t0 = time.perf_counter()
    if force or not crypto_path.exists():
        log("STEP", "Fetching crypto symbols from CoinGecko (top 500 by mcap)")
        from ingestion.fetch_crypto_symbols import main as fetch_crypto_main
        fetch_crypto_main()
    else:
        log("INFO", "crypto DB cached - skipping fetch  (--refresh-refs to force)")
    _show_ref_db("Crypto DB", crypto_path, sample_key="symbol")

    if force or not stock_path.exists():
        log("STEP", "Fetching US stocks + ETFs from SEC EDGAR")
        from ingestion.fetch_stock_symbols import main as fetch_stock_main
        fetch_stock_main()
    else:
        log("INFO", "stock DB cached - skipping fetch  (--refresh-refs to force)")
    _show_ref_db("Stock DB", stock_path, sample_key="ticker")

    elapsed = time.perf_counter() - t0
    log("TIMING", f"reference refresh finished in {elapsed:.2f}s")
    return elapsed


def discover_traders() -> list:
    data_dir = PROJECT / "data"
    traders = []
    for path in sorted(data_dir.iterdir()):
        if path.is_dir() and not path.name.startswith("_") and (path / "messages.jsonl").exists():
            traders.append(path.name)
    return traders


def step_profile(traders: list) -> float:
    banner(f"STEP 3: Profile {len(traders)} trader(s)")
    # Import here so the reference DBs load AFTER step 2 ran
    from profiling.profile import profile_trader

    t0 = time.perf_counter()
    for i, trader in enumerate(traders, start=1):
        log("STEP", f"({i}/{len(traders)}) profiling {trader}")
        try:
            t_one = time.perf_counter()
            result = profile_trader(trader, verbose=False)
            dur = time.perf_counter() - t_one
            log("DONE", f"{trader}: {result['messages']} messages -> "
                       f"data/{trader}/profile/  ({dur:.2f}s)")
            log("DETAIL", "  wrote: " + ", ".join(result["files"]))
        except (FileNotFoundError, ValueError) as e:
            log("ERROR", f"{trader}: {e}")
    return time.perf_counter() - t0


# ---- Main ------------------------------------------------------------------

def main() -> None:
    args = sys.argv[1:]
    refresh = "--refresh-refs" in args
    args = [a for a in args if a != "--refresh-refs"]
    one_trader = args[0] if args else None

    banner("ProjectDolph2.0  -  end-to-end pipeline sweep")
    log("INFO", f"project root: {PROJECT}")
    if one_trader:
        log("INFO", f"profiling only: {one_trader}")
    if refresh:
        log("INFO", "force-refreshing reference databases")

    t_total = time.perf_counter()

    t1 = step_ingest()
    t2 = step_refresh_refs(force=refresh)

    traders = [one_trader] if one_trader else discover_traders()
    if not traders:
        log("ERROR", "no traders found under data/ - did ingestion run?")
        sys.exit(1)

    t3 = step_profile(traders)

    total = time.perf_counter() - t_total
    banner("SWEEP COMPLETE")
    log("DONE", f"total: {total:.2f}s   (ingest {t1:.2f}s, refs {t2:.2f}s, profile {t3:.2f}s)")
    log("INFO", f"traders profiled: {', '.join(traders)}")
    log("INFO", "open data/<trader>/profile/dashboard.png for a visual,")
    log("INFO", "or run `python profiling/show.py <trader>` for a text dump.")


if __name__ == "__main__":
    main()
