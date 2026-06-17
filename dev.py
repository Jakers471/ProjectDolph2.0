"""Developer debug runner — central hub for the full pipeline.

Parser:
    python dev.py                              # run all 15 fixtures, one-line pass/fail
    python dev.py --trace                      # full rule-by-rule trace for every fixture
    python dev.py --trace f01 f03              # trace specific fixture IDs
    python dev.py --msg "Long\\nCoin: BTC\\nEntry: 1)94500" --trace
    python dev.py --corpus Grizzlies           # parse corpus, show action stats + UNSURE samples
    python dev.py --corpus Grizzlies --save    # also write signals JSONL + HTML report

Mock pipeline (parse -> risk -> broker -> SQLite):
    python dev.py --paper Grizzlies            # run corpus through full pipeline (dry-run)
    python dev.py --paper Grizzlies --save     # also write JSONL + HTML report with equity tab

Polling simulation (replays corpus in timestamp order):
    python dev.py --poll Grizzlies             # instant replay (no delay)
    python dev.py --poll Grizzlies --speed 10  # 10x real-time speed

Equity curve (from DB trades):
    python dev.py --equity Grizzlies           # print trade table + write equity_curve.png

Open report without browser security warnings:
    python dev.py --serve Grizzlies            # serves latest report at http://localhost:8765
    python dev.py --serve Grizzlies --port 9000

Live ingestion (Windows toast watcher + pipeline):
    python dev.py --watch Grizzlies            # captures Discord toasts -> parse -> risk -> broker (dry-run)
    python dev.py --watch Grizzlies --live     # same but dry_run=False (CAUTION: real orders)

Every run shows: action fired, symbol found, price extracted, confidence score.
"""
import json
import os
import sys
import time
from pathlib import Path

PROJECT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT))

if sys.platform == "win32":
    os.system("")

# ---- Colors ------------------------------------------------------------------
R = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
GRAY = "\033[90m"
BLUE = "\033[34m"
CYAN = "\033[36m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
RED = "\033[31m"
BR_GREEN = "\033[92m"
BR_RED = "\033[91m"
BR_CYAN = "\033[96m"
BR_YELLOW = "\033[93m"
MAGENTA = "\033[35m"

ACTION_COLOR = {
    "ENTRY":  BR_GREEN + BOLD,
    "TRIM":   CYAN + BOLD,
    "EXIT":   YELLOW + BOLD,
    "ADD":    BLUE + BOLD,
    "UNSURE": BR_YELLOW,
    "NOISE":  GRAY,
}


def _ac(action: str) -> str:
    return ACTION_COLOR.get(action, R) + action + R


def _conf_color(c: float) -> str:
    if c >= 0.75:
        return BR_GREEN
    if c >= 0.50:
        return YELLOW
    return BR_RED


def _bar(c: float, width: int = 20) -> str:
    filled = int(c * width)
    bar = "#" * filled + "." * (width - filled)
    return _conf_color(c) + bar + R


# ---- Trace a single message --------------------------------------------------

def trace(analyst: str, timestamp: str, content: str, label: str = "") -> "Signal":
    from parsing.rules import action as action_mod
    from parsing.rules import side as side_mod
    from parsing.rules import symbol as symbol_mod
    from parsing.rules import price as price_mod
    from parsing import confidence as conf_mod
    from parsing.parser import parse_message, _strip

    clean = _strip(content)

    print(f"\n{BR_CYAN}{'='*68}{R}")
    if label:
        print(f"{BR_CYAN}{BOLD}  {label}{R}")
    preview = clean[:120].replace("\n", "  |  ")
    print(f"{GRAY}  {preview}{R}")
    print(f"{BR_CYAN}{'-'*68}{R}")

    action_r  = action_mod.detect(clean)
    side_r    = side_mod.detect(clean)
    symbol_r  = symbol_mod.detect(clean)
    price_r   = price_mod.detect(clean)

    final_action, final_conf, reasons = conf_mod.score(action_r, side_r, symbol_r, price_r)

    # Print rule results
    def _ev(r):
        return f"{GRAY}{'; '.join(r.evidence)}{R}" if r.evidence else ""

    print(f"  {BOLD}[ACTION]{R} {_ac(action_r.value or 'UNSURE'):30} conf={_conf_color(action_r.confidence)}{action_r.confidence:.2f}{R}  {_ev(action_r)}")
    print(f"  {BOLD}[SIDE  ]{R} {str(side_r.value or '-'):30} conf={_conf_color(side_r.confidence)}{side_r.confidence:.2f}{R}  {_ev(side_r)}")

    sym, atype = symbol_r.value if isinstance(symbol_r.value, tuple) else (None, None)
    sym_str = f"{sym or '-'} ({atype or '-'})"
    print(f"  {BOLD}[SYMBOL]{R} {sym_str:30} conf={_conf_color(symbol_r.confidence)}{symbol_r.confidence:.2f}{R}  {_ev(symbol_r)}")

    pd = price_r.value or {}
    price_str = (
        f"entry={pd.get('entry_price') or '-'}  "
        f"targets={pd.get('targets') or '[]'}  "
        f"stop={pd.get('stop') or '-'}  "
        f"size={pd.get('size_hint') or '-'}"
    )
    print(f"  {BOLD}[PRICE ]{R} {GRAY}{price_str}{R}")
    if price_r.evidence:
        print(f"           {GRAY}{'; '.join(price_r.evidence)}{R}")

    print(f"  {BOLD}[CONF  ]{R} {_bar(final_conf)} {_conf_color(final_conf)}{final_conf:.3f}{R}  -> {_ac(final_action)}")
    if reasons:
        print(f"           {YELLOW}reasons: {', '.join(reasons)}{R}")

    print(f"{BR_CYAN}{'-'*68}{R}")
    print(f"  {BOLD}SIGNAL{R}  action={_ac(final_action)}  side={side_r.value or '-'}  "
          f"symbol={sym or '-'}  asset={atype or '-'}")
    if pd.get("entry_price") or pd.get("targets"):
        print(f"          entry={pd.get('entry_price') or '-'}  "
              f"targets={pd.get('targets') or []}  stop={pd.get('stop') or '-'}  "
              f"size={pd.get('size_hint') or '-'}")

    sig = parse_message(analyst, timestamp, content)
    return sig


# ---- Fixtures ----------------------------------------------------------------

FIXTURES_PATH = PROJECT / "tests" / "fixtures" / "mock_messages.jsonl"


def load_fixtures() -> list[dict]:
    if not FIXTURES_PATH.exists():
        print(f"{RED}fixtures not found: {FIXTURES_PATH}{R}")
        return []
    return [json.loads(l) for l in FIXTURES_PATH.read_text(encoding="utf-8").splitlines() if l.strip()]


def run_fixtures(ids: list[str] | None, do_trace: bool) -> None:
    fixtures = load_fixtures()
    if ids:
        fixtures = [f for f in fixtures if f["id"] in ids]

    passed = 0
    print(f"\n{BOLD}Running {len(fixtures)} fixture(s)...{R}\n")

    for fx in fixtures:
        expected = fx.get("expected", {})

        if do_trace:
            sig = trace("fixture", "2026-01-01T00:00:00", fx["content"], label=f"{fx['id']} - {fx['label']}")
        else:
            from parsing.parser import parse_message
            sig = parse_message("fixture", "2026-01-01T00:00:00", fx["content"])

        checks = []
        for k, v in expected.items():
            actual = getattr(sig, k, None)
            ok = str(actual).upper() == str(v).upper() if actual else False
            checks.append((k, v, actual, ok))

        all_ok = all(c[3] for c in checks)
        passed += int(all_ok)

        status = f"{BR_GREEN}PASS{R}" if all_ok else f"{BR_RED}FAIL{R}"
        sig_str = f"{_ac(sig.action)}/{sig.side or '-'}/{sig.symbol or '-'}/{sig.asset_type or '-'}"
        print(f"  {status}  {fx['id']:4}  {fx['label']:35} {sig_str:40} conf={_conf_color(sig.confidence)}{sig.confidence:.2f}{R}")

        if not all_ok:
            for k, exp, got, ok in checks:
                if not ok:
                    print(f"         {RED}X {k}: expected={exp!r} got={got!r}{R}")

    print(f"\n{BOLD}{passed}/{len(fixtures)} passed{R}")


# ---- Corpus ------------------------------------------------------------------

def run_corpus(trader: str, save: bool) -> None:
    from parsing.parser import parse_corpus, write_signals
    from collections import Counter
    from datetime import datetime, timezone

    print(f"\n{BOLD}Parsing corpus: {trader}{R}")
    t0 = time.perf_counter()
    signals = parse_corpus(trader)
    elapsed = time.perf_counter() - t0

    total = len(signals)
    counts = Counter(s.action for s in signals)
    sym_counts = Counter(s.symbol for s in signals if s.symbol)

    print(f"  {total} messages parsed in {elapsed:.2f}s\n")

    print(f"  {'Action':<10} {'Count':>6}  {'%':>6}  bar")
    print(f"  {'-'*50}")
    for act in ("ENTRY", "TRIM", "EXIT", "ADD", "UNSURE", "NOISE"):
        n = counts.get(act, 0)
        pct = n / total * 100
        bar = "#" * int(pct / 2)
        print(f"  {_ac(act):<10} {n:>6}  {pct:>5.1f}%  {GRAY}{bar}{R}")

    print(f"\n  Top symbols:")
    for sym, n in sym_counts.most_common(10):
        sigs = [s for s in signals if s.symbol == sym]
        actions = Counter(s.action for s in sigs)
        a_str = "  ".join(f"{_ac(a)}×{c}" for a, c in actions.most_common())
        print(f"    {sym:6} {n:4} msgs   {a_str}")

    avg_conf = sum(s.confidence for s in signals) / total if total else 0
    print(f"\n  avg confidence: {_conf_color(avg_conf)}{avg_conf:.3f}{R}")

    unsure = [s for s in signals if s.action == "UNSURE"]
    if unsure:
        print(f"\n  {YELLOW}UNSURE samples (first 5):{R}")
        for s in unsure[:5]:
            preview = s.raw_content[:80].replace("\n", " ").encode("ascii", "replace").decode()
            print(f"    [{', '.join(s.unsure_reasons)}]")
            print(f"    {GRAY}{preview}{R}\n")

    if save:
        from parsing.report import write_report
        from data.paper_db import DB
        from analytics.equity import chart_data, order_book_data
        run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
        db = DB()
        eq = chart_data(trader, db)
        ob = order_book_data(trader, db)
        db.close()
        out  = write_signals(trader, signals, run_id)
        html = write_report(trader, signals, run_id, equity_data=eq, order_book=ob)
        print(f"\n  {BR_GREEN}wrote {out}{R}")
        print(f"  {BR_GREEN}wrote {html}{R}")


# ---- Paper pipeline (parse -> risk -> broker -> DB) --------------------------

def _reset_trader_db(db, trader: str):
    """Wipe all signals/trades/positions/equity for this trader so a fresh run starts clean."""
    db.con.execute("DELETE FROM equity_snapshots WHERE analyst=?", (trader,))
    db.con.execute("DELETE FROM positions      WHERE analyst=?", (trader,))
    db.con.execute("DELETE FROM trades         WHERE analyst=?", (trader,))
    db.con.execute("DELETE FROM signals        WHERE analyst=?", (trader,))
    db.con.commit()


def run_paper(trader: str, save: bool) -> None:
    from parsing.parser import parse_corpus, write_signals
    from parsing.report import write_report
    from data.paper_db import DB
    from risk.rules import evaluate
    from execution.broker import submit_order, force_close_all
    from analytics.equity import chart_data
    from collections import Counter
    from datetime import datetime, timezone

    print(f"\n{BOLD}Paper pipeline: {trader}{R}")
    t0 = time.perf_counter()
    signals = parse_corpus(trader)
    elapsed = time.perf_counter() - t0
    print(f"  {len(signals)} signals parsed in {elapsed:.2f}s")

    db = DB()
    _reset_trader_db(db, trader)
    print(f"  {GRAY}DB reset for {trader}{R}")
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")

    approved_n = rejected_n = traded_n = 0
    reject_reasons: list[str] = []
    last_ts = signals[-1].timestamp if signals else run_id

    print(f"\n  {BOLD}Running risk filter + broker...{R}")
    for sig in signals:
        # Pre-insert ALL signals so Trace tab can show every message
        sig_id = db.insert_signal(sig, run_id)
        ok, reason = evaluate(sig, db)
        if not ok:
            rejected_n += 1
            reject_reasons.append(reason)
            continue
        approved_n += 1
        trade_id = submit_order(sig, db, run_id=run_id, dry_run=True, sig_id=sig_id)
        if trade_id:
            traded_n += 1

    # Force-close any positions with no exit in corpus (break-even, $0 P&L)
    auto_closed = force_close_all(trader, db, timestamp=str(last_ts),
                                  run_id=run_id, dry_run=True)
    if auto_closed:
        print(f"\n  {GRAY}[corpus-end] auto-closed {auto_closed} positions with no exit signal{R}")

    # Summary
    print(f"\n  {BR_GREEN}approved{R}  {approved_n}")
    print(f"  {BR_RED}rejected{R}  {rejected_n}")
    print(f"  {CYAN}orders   {R}  {traded_n}")

    top_reasons = Counter(reject_reasons).most_common(5)
    if top_reasons:
        print(f"\n  {YELLOW}Top reject reasons:{R}")
        for r, n in top_reasons:
            print(f"    {n:4}x  {GRAY}{r}{R}")

    # Equity curve
    eq = chart_data(trader, db)
    if eq["trades"]:
        start     = eq.get("starting_balance", 7000)
        final_bal = eq["equity"][-1] if eq["equity"] else start
        final_pnl = final_bal - start
        wins  = sum(1 for t in eq["trades"] if t["pnl"] > 0)
        total = len(eq["trades"])
        color = BR_GREEN if final_pnl >= 0 else BR_RED
        print(f"\n  {BOLD}Equity{R}  closed trades={total}  "
              f"win rate={wins/total*100:.1f}%  "
              f"total pnl={color}{final_pnl:+.4f}{R}  "
              f"balance=${final_bal:,.2f}")
    else:
        print(f"\n  {YELLOW}No closed positions yet (need EXIT/TRIM signals with matching ENTRYs){R}")

    db.close()

    if save:
        from analytics.equity import order_book_data
        db2   = DB()
        eq2   = chart_data(trader, db2)
        ob    = order_book_data(trader, db2)
        db2.close()
        out  = write_signals(trader, signals, run_id)
        html = write_report(trader, signals, run_id, equity_data=eq2, order_book=ob)
        print(f"\n  {BR_GREEN}wrote {out}{R}")
        print(f"  {BR_GREEN}wrote {html}{R}")


# ---- Poll (replay corpus through full pipeline in time order) ----------------

def run_poll(trader: str, speed: float) -> None:
    from ingestion.discord_poller import poll
    from parsing.parser import parse_message
    from data.paper_db import DB
    from risk.rules import evaluate
    from execution.broker import submit_order
    from datetime import datetime, timezone

    db = DB()
    _reset_trader_db(db, trader)
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    count = [0]

    print(f"\n{BOLD}Polling corpus: {trader}  speed={speed}x{R}")
    print(f"  Each message fires through: parser -> risk -> broker\n")

    def on_message(analyst: str, timestamp: str, content: str):
        count[0] += 1
        sig = parse_message(analyst, timestamp, content)
        ok, reason = evaluate(sig, db)
        ts_short = timestamp[:16] if timestamp else "?"
        sym  = sig.symbol or "-"
        act  = _ac(sig.action)
        conf = f"{_conf_color(sig.confidence)}{sig.confidence:.2f}{R}"

        if ok:
            trade_id = submit_order(sig, db, run_id=run_id, dry_run=True)
            gate = f"{BR_GREEN}APPROVED{R}"
        else:
            gate = f"{BR_RED}REJECTED{R} {GRAY}({reason}){R}"

        print(f"  {GRAY}{ts_short}{R}  {act:<25} {sym:<6}  conf={conf}  {gate}")

    n = poll(trader, speed=speed, callback=on_message)
    db.close()
    print(f"\n{BOLD}Replayed {n} messages.{R}")


# ---- Equity curve from DB ----------------------------------------------------

def run_equity(trader: str) -> None:
    from data.paper_db import DB
    from analytics.equity import build_equity_curve, generate_chart

    db = DB()
    curve = build_equity_curve(trader, db)
    db.close()

    if not curve:
        print(f"\n{YELLOW}No closed trades in DB for {trader}.")
        print(f"Run: python dev.py --paper {trader} --save{R}")
        return

    print(f"\n{BOLD}Equity curve: {trader}  ({len(curve)} closed trades){R}\n")
    print(f"  {'Date':<12} {'Symbol':<6} {'Side':<5} {'Entry':>10} {'Exit':>10} {'PnL':>10}  {'Running':>10}")
    print(f"  {'-'*68}")

    for pt in curve:
        pnl_color = BR_GREEN if pt["trade_pnl"] >= 0 else BR_RED
        cum_color = BR_GREEN if pt["cumulative_pnl"] >= 0 else BR_RED
        print(f"  {pt['timestamp'][:10]:<12} "
              f"{pt['symbol']:<6} "
              f"{pt['side']:<5} "
              f"{str(pt['entry_price'] or '')[:10]:>10} "
              f"{str(pt['exit_price'] or '')[:10]:>10} "
              f"{pnl_color}{pt['trade_pnl']:>+10.4f}{R}  "
              f"{cum_color}{pt['cumulative_pnl']:>+10.4f}{R}")

    db2 = DB()
    png = generate_chart(trader, db2)
    db2.close()
    if png:
        print(f"\n  {BR_GREEN}wrote {png}{R}")


# ---- Serve HTML report via local HTTP server ---------------------------------

def run_serve(trader: str, port: int = 8765) -> None:
    try:
        from daemon.server import run as server_run
    except ImportError:
        print(f"{RED}FastAPI/uvicorn not installed. Run: pip install fastapi uvicorn{R}")
        return

    print(f"\n{BOLD}Dashboard:{R}  {BR_CYAN}http://localhost:{port}{R}")
    print(f"  API docs:   {BR_CYAN}http://localhost:{port}/docs{R}")
    print(f"  Press Ctrl+C to stop.\n")

    import webbrowser, threading, time as _t
    def _open():
        _t.sleep(0.8)
        webbrowser.open(f"http://localhost:{port}")
    threading.Thread(target=_open, daemon=True).start()

    server_run(trader=trader, port=port)


def _run_watch(trader: str, dry_run: bool = True) -> None:
    """Start the Windows toast watcher + live pipeline in parallel threads.

    The watcher captures Discord notifications into discord_messages.db.
    The live pipeline reads that DB and routes messages through parse -> risk -> broker.
    """
    import threading

    print(f"\n{BOLD}Live mode — trader: {BR_CYAN}{trader}{R}")
    print(f"  dry_run = {BR_YELLOW}{dry_run}{R}")
    if dry_run:
        print(f"  {DIM}Trades are simulated — no real orders sent.{R}")
    else:
        print(f"  {BR_RED}{BOLD}WARNING: dry_run=False — real orders will be sent!{R}")
    print(f"  Ctrl+C to stop.\n")

    from ingestion.windows_watcher import watch as watcher_watch
    from ingestion.live_pipeline import run as pipeline_run

    # Watcher thread — captures toasts into discord_messages.db
    watcher_thread = threading.Thread(
        target=watcher_watch,
        kwargs={"verbose": True},
        daemon=True,
        name="toast-watcher",
    )
    watcher_thread.start()
    print(f"[watch] Toast watcher started.")

    # Live pipeline — reads DB and runs through pipeline (blocks until Ctrl+C)
    pipeline_run(traders=[trader], dry_run=dry_run)


# ---- Main --------------------------------------------------------------------

def main() -> None:
    args = sys.argv[1:]

    do_trace   = "--trace"  in args;  args = [a for a in args if a != "--trace"]
    do_save    = "--save"   in args;  args = [a for a in args if a != "--save"]
    do_live    = "--live"   in args;  args = [a for a in args if a != "--live"]
    corpus_idx = args.index("--corpus") if "--corpus" in args else -1
    msg_idx    = args.index("--msg")    if "--msg"    in args else -1
    paper_idx  = args.index("--paper")  if "--paper"  in args else -1
    poll_idx   = args.index("--poll")   if "--poll"   in args else -1
    equity_idx = args.index("--equity") if "--equity" in args else -1
    speed_idx  = args.index("--speed")  if "--speed"  in args else -1
    serve_idx  = args.index("--serve")  if "--serve"  in args else -1
    port_idx   = args.index("--port")   if "--port"   in args else -1
    watch_idx  = args.index("--watch")  if "--watch"  in args else -1

    speed = float(args[speed_idx + 1]) if speed_idx >= 0 and speed_idx + 1 < len(args) else 0.0
    port  = int(args[port_idx + 1])    if port_idx  >= 0 and port_idx  + 1 < len(args) else 8765

    if watch_idx >= 0:
        trader = args[watch_idx + 1] if watch_idx + 1 < len(args) else "Grizzlies"
        _run_watch(trader, dry_run=not do_live)
        return

    if serve_idx >= 0:
        trader = args[serve_idx + 1] if serve_idx + 1 < len(args) else "Grizzlies"
        run_serve(trader, port=port)
        return

    if paper_idx >= 0:
        trader = args[paper_idx + 1] if paper_idx + 1 < len(args) else "Grizzlies"
        run_paper(trader, save=do_save)
        return

    if poll_idx >= 0:
        trader = args[poll_idx + 1] if poll_idx + 1 < len(args) else "Grizzlies"
        run_poll(trader, speed=speed)
        return

    if equity_idx >= 0:
        trader = args[equity_idx + 1] if equity_idx + 1 < len(args) else "Grizzlies"
        run_equity(trader)
        return

    if corpus_idx >= 0:
        trader = args[corpus_idx + 1] if corpus_idx + 1 < len(args) else "Grizzlies"
        run_corpus(trader, save=do_save)
        return

    if msg_idx >= 0:
        msg = args[msg_idx + 1] if msg_idx + 1 < len(args) else ""
        msg = msg.replace("\\n", "\n")
        trace("manual", "2026-01-01T00:00:00", msg, label="--msg input")
        return

    # Default: run fixtures (with optional ID filter)
    fixture_ids = [a for a in args if not a.startswith("--")]
    run_fixtures(fixture_ids or None, do_trace=do_trace)


if __name__ == "__main__":
    main()
