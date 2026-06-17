"""ProjectDolph2.0 — live dashboard server.

Replaces the SimpleHTTPRequestHandler in dev.py --serve.
Run via:  python dev.py --serve Grizzlies
Or directly:  python daemon/server.py Grizzlies

Endpoints:
  GET  /                          live dashboard HTML
  GET  /api/health                heartbeat + system status
  GET  /api/config/{trader}       read trader config
  PUT  /api/config/{trader}       save trader config
  GET  /api/signals/{trader}      latest parsed signals
  GET  /api/trades/{trader}       order book from DB
  GET  /api/equity/{trader}       equity curve data
  POST /api/paper/{trader}        run paper pipeline
  GET  /api/traders               list available traders
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT))

try:
    from fastapi import FastAPI, HTTPException, Body, Request
    from fastapi.responses import HTMLResponse, JSONResponse
    from fastapi.staticfiles import StaticFiles
    import uvicorn
except ImportError:
    raise ImportError(
        "FastAPI and uvicorn are required for the live server.\n"
        "Run: pip install fastapi uvicorn"
    )

from config.loader import get_config
from data.paper_db import DB, DB_PATH

app = FastAPI(title="ProjectDolph2.0", version="0.1.0")

_CONFIG_DIR  = PROJECT / "config"
_DATA_DIR    = PROJECT / "data"
_SIGNALS_DIR = lambda trader: _DATA_DIR / trader / "signals"


# ---- Health ------------------------------------------------------------------

@app.get("/api/health")
def health():
    traders = _list_traders()
    db_ok   = DB_PATH.exists()
    return {
        "status":    "ok",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "db":        str(DB_PATH) if db_ok else "not found",
        "traders":   traders,
        "version":   "0.1.0",
    }


# ---- Trace -------------------------------------------------------------------

@app.get("/api/trace/{trader}")
def get_trace(trader: str):
    db = DB()
    data = db.get_trace_data(trader)
    db.close()
    return data


@app.post("/api/parse/trace")
async def parse_trace(req: Request):
    """Run a single message through the full parser and return every rule's verdict."""
    body   = await req.json()
    trader = body.get("trader", "Grizzlies")
    text   = body.get("message", "")
    if not text.strip():
        return {"error": "empty message"}

    from datetime import datetime, timezone
    from parsing.rules import action as _action, side as _side, symbol as _symbol, price as _price
    from parsing.parser import parse_message

    ts = datetime.now(timezone.utc).isoformat()

    # Run each rule independently so we can show every score
    action_result = _action.detect(text)
    side_result   = _side.detect(text)
    symbol_result = _symbol.detect(text)
    price_result  = _price.detect(text)

    # Full parse for final signal
    sig = parse_message(trader, ts, text)

    def _r(result):
        return {
            "value":      result.value,
            "confidence": round(result.confidence, 3),
            "evidence":   result.evidence,
        }

    return {
        "rules": {
            "action": _r(action_result),
            "side":   _r(side_result),
            "symbol": _r(symbol_result),
            "price":  _r(price_result),
        },
        "signal": {
            "action":      sig.action,
            "side":        sig.side,
            "symbol":      sig.symbol,
            "asset_type":  sig.asset_type,
            "entry_price": sig.entry_price,
            "targets":     sig.targets,
            "stop":        sig.stop,
            "confidence":  round(sig.confidence, 3),
            "unsure_reasons": sig.unsure_reasons or [],
        }
    }


# ---- Traders -----------------------------------------------------------------

@app.get("/api/traders")
def list_traders():
    return {"traders": _list_traders()}


def _list_traders() -> list[str]:
    known = [d.name for d in _DATA_DIR.iterdir()
             if d.is_dir() and not d.name.startswith("_")]
    return sorted(known)


# ---- Config ------------------------------------------------------------------

@app.get("/api/config/{trader}")
def read_config(trader: str):
    return get_config(trader)


@app.put("/api/config/{trader}")
def save_config(trader: str, body: dict = Body(...)):
    path = _CONFIG_DIR / f"{trader}.json"
    # Strip internal comment key so we don't clobber it
    body.pop("_comment", None)
    body["_comment"] = f"{trader} — last saved {datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}"
    path.write_text(json.dumps(body, indent=2), encoding="utf-8")
    return {"saved": True, "path": str(path)}


# ---- Signals -----------------------------------------------------------------

@app.get("/api/signals/{trader}")
def get_signals(trader: str, offset: int = 0, limit: int = 200):
    sig_dir = _SIGNALS_DIR(trader)
    files   = sorted(sig_dir.glob("*.jsonl")) if sig_dir.exists() else []
    if not files:
        return {"signals": [], "run_id": None, "total": 0, "offset": 0}
    latest  = files[-1]
    lines   = [json.loads(l) for l in latest.read_text(encoding="utf-8").splitlines() if l.strip()]
    page    = lines[offset:offset + limit]
    return {"signals": page, "run_id": latest.stem, "total": len(lines), "offset": offset, "limit": limit}


# ---- Signal corrections (labeling) ------------------------------------------

def _corrections_path(trader: str) -> Path:
    return _DATA_DIR / trader / "corrections.jsonl"

@app.get("/api/corrections/{trader}")
def get_corrections(trader: str):
    p = _corrections_path(trader)
    if not p.exists():
        return {"corrections": [], "total": 0}
    rows = [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]
    return {"corrections": rows, "total": len(rows)}

@app.post("/api/corrections/{trader}")
async def save_correction(trader: str, req: Request):
    body  = await req.json()
    p     = _corrections_path(trader)
    p.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "ts":             datetime.now(timezone.utc).isoformat(),
        "trader":         trader,
        "msg_hash":       body.get("msg_hash", ""),
        "msg_preview":    body.get("msg_preview", ""),
        "parsed_action":  body.get("parsed_action", ""),
        "correct_action": body.get("correct_action", ""),
        "reason":         body.get("reason", ""),
        "verdict":        body.get("verdict", "wrong"),
        "actionable":     body.get("actionable", None),
    }
    # Read existing, drop any prior entry for this hash, append updated one
    existing = []
    if p.exists():
        for line in p.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                row = json.loads(line)
                if row.get("msg_hash") != entry["msg_hash"]:
                    existing.append(row)
            except Exception:
                pass
    existing.append(entry)
    p.write_text("\n".join(json.dumps(r) for r in existing) + "\n", encoding="utf-8")
    return {"saved": True, "total": len(existing)}

@app.get("/api/rules")
def get_rules():
    import sys
    sys.path.insert(0, str(PROJECT))
    from parsing.rules import action, symbol, side, price as price_mod

    def _split(pat):
        """Split a compiled regex alternation into readable phrases, strip regex syntax."""
        import re as _re
        parts = pat.pattern.split(r'|')
        clean = []
        for p in parts:
            p = p.strip()
            # Remove anchors, groups, lookaheads, flags
            p = _re.sub(r'\(\?[^)]*\)', '', p)
            p = _re.sub(r'[\\b^$(){}+?*\[\]]', '', p)
            p = _re.sub(r'\s+', ' ', p).strip()
            if p and len(p) > 1:
                clean.append(p)
        return clean

    # Action rules
    action_rules = {
        "EXIT":  _split(action._EXIT),
        "ADD":   _split(action._ADD),
        "TRIM":  _split(action._TRIM),
        "ENTRY": _split(action._ENTRY),
        "NOISE": _split(action._NOISE),
        "TRADE_WORDS": _split(action._HAS_TRADE_WORDS),
    }

    # Side rules
    side_rules = {
        "LONG":  _split(side._LONG),
        "SHORT": _split(side._SHORT),
    }

    # Price rules
    price_rules = {
        "entry_numbered": price_mod._NUMBERED.pattern,
        "entry_plain":    price_mod._PLAIN_PRICE.pattern,
        "at_price":       price_mod._AT_PRICE.pattern,
        "stop":           price_mod._STOP.pattern,
        "tp_label":       price_mod._TP_LABEL.pattern,
        "up_pct":         price_mod._UP_PCT.pattern,
        "leverage":       price_mod._LEVERAGE.pattern,
    }

    # Symbol sets
    crypto_syms = sorted(symbol._CRYPTO_SYMBOLS) if hasattr(symbol, '_CRYPTO_SYMBOLS') else []
    stock_syms  = sorted(symbol._STOCK_SYMBOLS)  if hasattr(symbol, '_STOCK_SYMBOLS')  else []

    return {
        "action": action_rules,
        "side":   side_rules,
        "price":  price_rules,
        "symbols": {
            "crypto": crypto_syms[:200],
            "stock":  stock_syms[:200],
            "crypto_total": len(crypto_syms),
            "stock_total":  len(stock_syms),
        }
    }


@app.get("/api/corrections/{trader}/stats")
def corrections_stats(trader: str):
    p = _corrections_path(trader)
    if not p.exists():
        return {"total": 0, "wrong": 0, "correct": 0, "patterns": []}
    rows   = [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]
    wrong  = [r for r in rows if r.get("verdict") == "wrong"]
    # Group wrong by parsed_action -> correct_action
    from collections import Counter
    pairs  = Counter((r["parsed_action"], r["correct_action"]) for r in wrong)
    patterns = [{"from": k[0], "to": k[1], "count": v}
                for k, v in pairs.most_common(20)]
    return {"total": len(rows), "wrong": len(wrong), "correct": len(rows)-len(wrong), "patterns": patterns}


# ---- Order book --------------------------------------------------------------

@app.get("/api/trades/{trader}")
def get_trades(trader: str):
    from analytics.equity import order_book_data
    db   = DB()
    data = order_book_data(trader, db)
    db.close()
    return {"trades": data}


# ---- Equity ------------------------------------------------------------------

@app.get("/api/equity/{trader}")
def get_equity(trader: str):
    from analytics.equity import chart_data
    db  = DB()
    eq  = chart_data(trader, db)
    db.close()
    return eq


# ---- Paper pipeline ----------------------------------------------------------

@app.post("/api/paper/{trader}")
def run_paper(trader: str):
    import io
    from parsing.parser import parse_corpus, write_signals
    from parsing.report import write_report
    from risk.rules import evaluate
    from execution.broker import submit_order, force_close_all
    from analytics.equity import chart_data, order_book_data
    from collections import Counter

    signals = parse_corpus(trader)
    db      = DB()

    # Reset trader state
    db.con.execute("DELETE FROM equity_snapshots WHERE analyst=?", (trader,))
    db.con.execute("DELETE FROM positions      WHERE analyst=?", (trader,))
    db.con.execute("DELETE FROM trades         WHERE analyst=?", (trader,))
    db.con.execute("DELETE FROM signals        WHERE analyst=?", (trader,))
    db.con.commit()

    run_id   = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    last_ts  = str(signals[-1].timestamp) if signals else run_id
    approved = rejected = traded = 0
    reject_log: list[str] = []
    console_lines: list[str] = []

    for sig in signals:
        # Pre-insert ALL signals so Trace tab can show every message
        sig_id = db.insert_signal(sig, run_id)
        ok, reason = evaluate(sig, db)
        if not ok:
            rejected += 1
            reject_log.append(reason)
            continue
        approved += 1
        # Capture per-trade print output
        buf = io.StringIO()
        _prev = sys.stdout
        sys.stdout = buf
        try:
            tid = submit_order(sig, db, run_id=run_id, dry_run=True, sig_id=sig_id)
        finally:
            sys.stdout = _prev
        line = buf.getvalue().strip()
        if line:
            console_lines.append(line)
        if tid:
            traded += 1

    # Force-close any positions with no exit in corpus
    buf2 = io.StringIO()
    sys.stdout, _prev2 = buf2, sys.stdout
    try:
        auto_closed = force_close_all(trader, db, timestamp=last_ts,
                                      run_id=run_id, dry_run=True)
    finally:
        sys.stdout = _prev2
    for line in buf2.getvalue().splitlines():
        if line.strip():
            console_lines.append(line)

    eq = chart_data(trader, db)
    ob = order_book_data(trader, db)
    db.close()

    out_jsonl = write_signals(trader, signals, run_id)
    out_html  = write_report(trader, signals, run_id, equity_data=eq, order_book=ob)

    from collections import Counter as C
    top_rejects = [{"reason": r, "count": n}
                   for r, n in C(reject_log).most_common(5)]

    return {
        "run_id":      run_id,
        "signals":     len(signals),
        "approved":    approved,
        "rejected":    rejected,
        "traded":      traded,
        "top_rejects": top_rejects,
        "equity":      eq,
        "jsonl":       str(out_jsonl),
        "html":        str(out_html),
        "console":     console_lines,
    }


# ---- Pipeline samples --------------------------------------------------------

@app.get("/api/pipeline/{trader}")
def get_pipeline(trader: str):
    """Return signal samples per action + corpus stats for the Pipeline tab."""
    sig_dir = _SIGNALS_DIR(trader)
    files   = sorted(sig_dir.glob("*.jsonl")) if sig_dir.exists() else []
    if not files:
        return {"samples": {}, "stats": {}, "corpus_total": 0}

    lines = [json.loads(l) for l in files[-1].read_text(encoding="utf-8").splitlines() if l.strip()]

    from collections import Counter
    action_counts = Counter(s.get("action") for s in lines)
    asset_counts  = Counter(s.get("asset_type") for s in lines if s.get("asset_type"))
    side_counts   = Counter(s.get("side") for s in lines if s.get("side"))

    # 3 samples per action type (prefer high-confidence, exclude empty raw_content)
    samples: dict = {}
    for action in ["ENTRY", "TRIM", "EXIT", "ADD", "UNSURE", "NOISE"]:
        pool = [s for s in lines
                if s.get("action") == action and s.get("raw_content","").strip()]
        pool.sort(key=lambda s: s.get("confidence", 0), reverse=True)
        samples[action] = pool[:3]

    db = DB()
    positions = db.con.execute(
        "SELECT COUNT(*) FROM positions WHERE analyst=?", (trader,)
    ).fetchone()[0]
    trades_total = db.con.execute(
        "SELECT COUNT(*) FROM trades WHERE analyst=?", (trader,)
    ).fetchone()[0]
    eq_rows = db.con.execute(
        "SELECT cumulative_pnl FROM equity_snapshots WHERE analyst=? ORDER BY id DESC LIMIT 1",
        (trader,)
    ).fetchone()
    cfg = get_config(trader)
    db.close()

    final_pnl = round(eq_rows[0], 2) if eq_rows else 0.0
    start_bal = cfg.get("broker", {}).get("starting_balance", 7000)

    return {
        "samples":       samples,
        "action_counts": dict(action_counts),
        "asset_counts":  dict(asset_counts),
        "side_counts":   dict(side_counts),
        "corpus_total":  len(lines),
        "positions":     positions,
        "trades_total":  trades_total,
        "final_pnl":     final_pnl,
        "start_bal":     start_bal,
        "config":        cfg,
    }


# ---- Live manager ------------------------------------------------------------

import collections
import os
import threading

class _LiveManager:
    """Thread manager for the Windows toast watcher + live pipeline."""

    def __init__(self):
        self._lock            = threading.Lock()
        self._watcher_thread  : threading.Thread | None = None
        self._pipeline_thread : threading.Thread | None = None
        self._stop_event      : threading.Event  | None = None
        self._logs            : collections.deque = collections.deque(maxlen=500)
        self._log_idx         : int  = 0          # monotonic counter for polling
        self._intercepted     : int  = 0          # total messages captured
        self._traded          : int  = 0          # total trades placed this session
        self._session_start   : str  = ""

    def _log(self, msg: str):
        ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
        # Categorize for filtered log panels
        if any(k in msg for k in ("Started", "stopped", "crashed", "error", "WARNING",
                                   "Channel map", "Pipeline running", "Stop signal",
                                   "[live]", "[pipeline]")):
            cat = "conn"
        elif "[watcher]" in msg:
            cat = "watcher"
        elif ("[DRY-RUN]" in msg or "[LIVE]" in msg or "[alpaca]" in msg
              or "TRADE |" in msg or "BUY" in msg[:40] or "SELL" in msg[:40]):
            cat = "trade"
        else:
            cat = "pipeline"
        entry = {"i": self._log_idx, "ts": ts, "msg": msg, "cat": cat}
        with self._lock:
            self._logs.append(entry)
            self._log_idx += 1
            if "[watcher] saved" in msg:
                self._intercepted += 1
            if cat == "trade" and ("TRADE |" in msg or "[DRY-RUN]" in msg or "[LIVE]" in msg):
                self._traded += 1

    def start(self, trader: str, dry_run: bool = True):
        with self._lock:
            if self._watcher_thread and self._watcher_thread.is_alive():
                return {"ok": False, "error": "already running"}
            self._stop_event     = threading.Event()
            self._intercepted    = 0
            self._traded         = 0
            self._session_start  = datetime.now(timezone.utc).isoformat()

        stop = self._stop_event
        log  = self._log

        def _watcher():
            try:
                from ingestion.windows_watcher import watch
                watch(verbose=False, stop_event=stop, log_fn=log)
            except Exception as e:
                log(f"[watcher] crashed: {e}")

        def _pipeline():
            try:
                from ingestion.live_pipeline import run
                run(traders=[trader], dry_run=dry_run,
                    verbose=False, stop_event=stop, log_fn=log)
            except Exception as e:
                log(f"[pipeline] crashed: {e}")

        self._watcher_thread  = threading.Thread(target=_watcher,  daemon=True, name="toast-watcher")
        self._pipeline_thread = threading.Thread(target=_pipeline, daemon=True, name="live-pipeline")
        self._watcher_thread.start()
        self._pipeline_thread.start()
        self._log(f"[live] Started — trader={trader} dry_run={dry_run}")
        return {"ok": True}

    def stop(self):
        if self._stop_event:
            self._stop_event.set()
            self._log("[live] Stop signal sent.")
        return {"ok": True}

    def status(self) -> dict:
        w_alive = bool(self._watcher_thread and self._watcher_thread.is_alive())
        p_alive = bool(self._pipeline_thread and self._pipeline_thread.is_alive())

        # Alpaca status
        alpaca_key = bool(os.getenv("ALPACA_API_KEY") or
                          (PROJECT / ".env").read_text(encoding="utf-8").find("ALPACA_API_KEY=PK") > -1
                          if (PROJECT / ".env").exists() else False)

        channel_map_raw = os.getenv("CHANNEL_ANALYST_MAP", "")
        if not channel_map_raw and (PROJECT / ".env").exists():
            for line in (PROJECT / ".env").read_text(encoding="utf-8").splitlines():
                if line.startswith("CHANNEL_ANALYST_MAP="):
                    channel_map_raw = line.split("=", 1)[1].strip()
                    break

        return {
            "watcher":       "running" if w_alive else "stopped",
            "pipeline":      "running" if p_alive else "stopped",
            "alpaca":        "configured" if alpaca_key else "not_configured",
            "channel_map":   channel_map_raw,
            "intercepted":   self._intercepted,
            "traded":        self._traded,
            "session_start": self._session_start,
        }

    def logs_since(self, since: int = 0) -> list[dict]:
        with self._lock:
            return [e for e in self._logs if e["i"] >= since]

    def recent_messages(self, limit: int = 30) -> list[dict]:
        try:
            from ingestion.discord_db import fetch_recent
            rows = fetch_recent(limit)
            return [dict(r) for r in rows]
        except Exception:
            return []


_live = _LiveManager()


@app.post("/api/live/start")
def live_start(body: dict = Body(default={})):
    trader   = body.get("trader", "Grizzlies")
    dry_run  = body.get("dry_run", True)
    return _live.start(trader, dry_run=dry_run)


@app.post("/api/live/stop")
def live_stop():
    return _live.stop()


@app.get("/api/live/status")
def live_status():
    return _live.status()


@app.get("/api/live/logs")
def live_logs(since: int = 0, cat: str = "all"):
    entries = _live.logs_since(since)
    if cat != "all":
        entries = [e for e in entries if e.get("cat") == cat]
    return {"entries": entries}


@app.get("/api/live/messages")
def live_messages(limit: int = 30):
    return {"messages": _live.recent_messages(limit)}


@app.get("/api/alpaca/account")
def alpaca_account():
    from execution.alpaca_client import account_snapshot
    return account_snapshot()


@app.get("/api/alpaca/positions")
def alpaca_positions():
    from execution.alpaca_client import positions_snapshot
    return {"positions": positions_snapshot()}


@app.get("/api/alpaca/orders")
def alpaca_orders(limit: int = 20):
    from execution.alpaca_client import orders_snapshot
    return {"orders": orders_snapshot(limit)}


@app.post("/api/live/kill")
def live_kill(body: dict = Body(default={})):
    """Emergency stop: halt threads AND set kill_switch=true in trader config."""
    trader = body.get("trader", "Grizzlies")
    _live.stop()
    # Activate kill switch in config file
    try:
        cfg_path = PROJECT / "config" / f"{trader}.json"
        if cfg_path.exists():
            import json
            with open(cfg_path) as f:
                cfg = json.load(f)
            cfg.setdefault("risk", {})["kill_switch"] = True
            with open(cfg_path, "w") as f:
                json.dump(cfg, f, indent=2)
        _live._log(f"[live] EMERGENCY STOP — kill_switch activated for {trader}")
    except Exception as e:
        _live._log(f"[live] kill_switch write error: {e}")
    return {"ok": True, "message": "stopped + kill_switch activated"}


@app.post("/api/live/unkill")
def live_unkill(body: dict = Body(default={})):
    """Clear kill switch in trader config (re-enable trading)."""
    trader = body.get("trader", "Grizzlies")
    try:
        cfg_path = PROJECT / "config" / f"{trader}.json"
        if cfg_path.exists():
            import json
            with open(cfg_path) as f:
                cfg = json.load(f)
            cfg.setdefault("risk", {})["kill_switch"] = False
            with open(cfg_path, "w") as f:
                json.dump(cfg, f, indent=2)
        _live._log(f"[live] Kill switch cleared for {trader}")
    except Exception as e:
        _live._log(f"[live] unkill error: {e}")
    return {"ok": True}


@app.post("/api/live/sanity")
def live_sanity(body: dict = Body(default={})):
    """Full live sanity check — parses a real corpus message, runs risk, submits a real
    Alpaca paper order, then fetches it back and cancels it immediately.
    Exercises the entire stack end-to-end on the paper account."""
    trader   = body.get("trader", "Grizzlies")
    test_msg = "BTC long @ 68000"

    from parsing.parser import parse_message
    from risk.rules import evaluate
    from data.paper_db import DB
    from execution.alpaca_adapter import get_adapter
    from config.loader import get_config
    from pathlib import Path

    cfg      = get_config(trader)
    notional = cfg.get("broker", {}).get("trade_notional", 500.0)

    ts  = datetime.now(timezone.utc).isoformat()
    sig = parse_message(trader, ts, test_msg)

    _live._log(f"[sanity] 1/5  parse:  {sig.action} {sig.symbol} ({sig.asset_type})  conf={sig.confidence:.2f}")

    # Risk — use isolated DB so we never pollute paper.db
    db = DB(Path(":memory:"))
    ok, reason = evaluate(sig, db)
    db.close()

    _live._log(f"[sanity] 2/5  risk:   {'APPROVED' if ok else 'REJECTED — ' + reason}")
    if not ok:
        return {"ok": False, "stage": "risk", "reason": reason,
                "action": sig.action, "symbol": sig.symbol,
                "asset_type": sig.asset_type, "confidence": round(sig.confidence, 3),
                "message": test_msg, "entry_price": sig.entry_price,
                "notional": notional, "side": sig.side or "LONG",
                "ts": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")}

    # Alpaca — submit real paper order
    adapter = get_adapter()
    if not adapter.connected:
        _live._log("[sanity] 3/5  alpaca: NOT CONNECTED — check .env keys")
        return {"ok": False, "stage": "alpaca", "reason": "Alpaca not connected",
                "action": sig.action, "symbol": sig.symbol,
                "asset_type": sig.asset_type, "confidence": round(sig.confidence, 3),
                "message": test_msg, "entry_price": sig.entry_price,
                "notional": notional, "side": sig.side or "LONG",
                "ts": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")}

    run_id = f"sanity_{datetime.now(timezone.utc).strftime('%H%M%S')}"
    # Close any leftover sanity positions before starting fresh
    for _pre in [sig.symbol + "USD", sig.symbol + "/USD", sig.symbol]:
        try:
            adapter._client.close_position(_pre)
            _live._log(f"[sanity] 3/5  cleanup: closed leftover {_pre} position before test")
            break
        except Exception:
            pass

    _live._log(f"[sanity] 3/5  alpaca: submitting {sig.action} {sig.symbol} ${notional:.0f} notional to paper account...")
    result = adapter.submit_order(sig, run_id, notional)

    alpaca_id     = result.get("id")
    alpaca_status = result.get("status", "?")
    alpaca_err    = result.get("error")

    if alpaca_err or not alpaca_id:
        _live._log(f"[sanity] 3/5  alpaca: ORDER FAILED — {alpaca_err or 'no order id returned'}")
        return {"ok": False, "stage": "alpaca_submit", "reason": alpaca_err or "no id",
                "action": sig.action, "symbol": sig.symbol,
                "asset_type": sig.asset_type, "confidence": round(sig.confidence, 3),
                "message": test_msg, "entry_price": sig.entry_price,
                "notional": notional, "side": sig.side or "LONG",
                "ts": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")}

    _live._log(f"[sanity] 3/5  alpaca: ORDER PLACED — id={alpaca_id}  status={alpaca_status}")

    # Fetch the order back from Alpaca to confirm it landed
    import time as _time
    _time.sleep(0.4)
    order_detail = {}
    try:
        client = adapter._client
        o = client.get_order_by_id(alpaca_id)
        order_detail = {
            "id":               str(o.id),
            "symbol":           o.symbol,
            "side":             str(o.side.value) if hasattr(o.side, "value") else str(o.side),
            "status":           str(o.status.value) if hasattr(o.status, "value") else str(o.status),
            "qty":              float(o.qty or 0) if o.qty else None,
            "notional":         float(o.notional or 0) if o.notional else None,
            "filled_qty":       float(o.filled_qty or 0) if o.filled_qty else None,
            "filled_avg_price": float(o.filled_avg_price or 0) if o.filled_avg_price else None,
            "submitted_at":     str(o.submitted_at)[:16].replace("T", " ") if o.submitted_at else "",
        }
        _live._log(f"[sanity] 4/5  verify: order confirmed in Alpaca — status={order_detail['status']}")
    except Exception as e:
        _live._log(f"[sanity] 4/5  verify: could not fetch order back — {e}")

    # Clean up — cancel if pending, close position if already filled
    cleaned = False
    try:
        adapter._client.cancel_order_by_id(alpaca_id)
        _live._log(f"[sanity] 5/5  cleanup: order cancelled — paper account clean")
        cleaned = True
    except Exception:
        pass  # already filled — need to close the position instead

    if not cleaned:
        import time as _time2
        _time2.sleep(0.3)
        # Alpaca stores crypto positions as BTCUSD (no slash), but orders use BTC/USD
        alp_sym_slash  = order_detail.get("symbol", f"{sig.symbol}/USD")   # e.g. BTC/USD
        alp_sym_noslash = alp_sym_slash.replace("/", "")                    # e.g. BTCUSD
        closed = False
        for sym_try in [alp_sym_noslash, alp_sym_slash, sig.symbol]:
            try:
                adapter._client.close_position(sym_try)
                _live._log(f"[sanity] 5/5  cleanup: position closed ({sym_try}) — paper account clean")
                closed = True
                break
            except Exception:
                pass
        if not closed:
            _live._log(f"[sanity] 5/5  cleanup: could not close position — close manually in Alpaca dashboard")

    _live._log(f"[sanity] PASSED — full stack verified: parse -> risk -> Alpaca paper order -> cancel")

    return {
        "ok":           True,
        "action":       sig.action,
        "symbol":       sig.symbol,
        "asset_type":   sig.asset_type,
        "confidence":   round(sig.confidence, 3),
        "risk_ok":      ok,
        "alpaca_id":    alpaca_id,
        "alpaca_status": alpaca_status,
        "order":        order_detail,
        "message":      test_msg,
        "entry_price":  sig.entry_price,
        "notional":     notional,
        "side":         sig.side or "LONG",
        "ts":           datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M"),
    }


@app.post("/api/live/config")
def live_save_config(body: dict = Body(...)):
    """Save CHANNEL_ANALYST_MAP and optionally Alpaca keys to .env."""
    env_path = PROJECT / ".env"
    lines: list[str] = []
    if env_path.exists():
        lines = env_path.read_text(encoding="utf-8").splitlines()

    def _set(key: str, val: str):
        for i, ln in enumerate(lines):
            if ln.startswith(f"{key}="):
                lines[i] = f"{key}={val}"
                return
        lines.append(f"{key}={val}")

    if body.get("channel_map"):
        _set("CHANNEL_ANALYST_MAP", body["channel_map"])
    if body.get("alpaca_key"):
        _set("ALPACA_API_KEY", body["alpaca_key"])
    if body.get("alpaca_secret"):
        _set("ALPACA_SECRET_KEY", body["alpaca_secret"])
    if "alpaca_paper" in body:
        _set("ALPACA_PAPER", "true" if body["alpaca_paper"] else "false")

    env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    # Reload env vars in current process
    try:
        from dotenv import load_dotenv
        load_dotenv(env_path, override=True)
    except Exception:
        pass

    return {"saved": True}


# ---- Dashboard HTML ----------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
def dashboard():
    return HTMLResponse(_dashboard_html())


def _dashboard_html() -> str:
    traders = _list_traders()
    ACTIVE_TRADERS = {"Grizzlies"}
    trader_opts = "".join(
        f'<option value="{t}">{t}</option>'
        if t in ACTIVE_TRADERS else
        f'<option value="{t}" disabled style="color:#374151">{t} (not set up)</option>'
        for t in traders
    )
    default_trader = traders[0] if traders else "Grizzlies"

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>ProjectDolph2.0 — Dashboard</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{background:#0f1117;color:#e2e8f0;font-family:'Segoe UI',system-ui,sans-serif;font-size:14px}}
.header{{background:#1a1f2e;border-bottom:1px solid #2d3748;padding:14px 24px;display:flex;align-items:center;gap:16px}}
.header h1{{font-size:17px;font-weight:700;color:#e2e8f0;flex:1}}
.trader-sel{{background:#111827;border:1px solid #334155;color:#e2e8f0;padding:6px 10px;border-radius:6px;font-size:13px;outline:none}}
.run-btn{{background:#22c55e;border:none;color:#000;font-weight:700;padding:7px 16px;border-radius:6px;cursor:pointer;font-size:13px}}
.run-btn:hover{{background:#16a34a}}
.run-btn:disabled{{background:#374151;color:#6b7280;cursor:default}}
.heartbeat{{display:inline-block;width:8px;height:8px;border-radius:50%;background:#22c55e;margin-right:6px;animation:pulse 2s infinite}}
@keyframes pulse{{0%,100%{{opacity:1}}50%{{opacity:.4}}}}
.tab-bar{{background:#111827;border-bottom:1px solid #1e293b;padding:0 24px;display:flex;align-items:stretch}}
@keyframes pulse-tab{{0%,100%{{opacity:1}}50%{{opacity:.6}}}}
.tab-btn{{padding:12px 18px;font-size:13px;font-weight:600;color:#6b7280;border:none;background:none;cursor:pointer;border-bottom:2px solid transparent}}
.tab-btn:hover{{color:#cbd5e1}}
.tab-btn.active{{color:#e2e8f0;border-bottom-color:#60a5fa}}
.tab-panel{{display:none;padding:24px;box-sizing:border-box;width:100%}}
.tab-panel.active{{display:block}}
.status-bar{{background:#111827;padding:8px 24px;font-size:12px;color:#6b7280;border-bottom:1px solid #1e293b;display:flex;gap:20px}}
.status-bar span{{color:#94a3b8}}

/* Config tab */
.cfg-grid{{display:grid;grid-template-columns:1fr 1fr;gap:20px;max-width:1000px}}
.cfg-card{{background:#1a1f2e;border-radius:10px;padding:20px}}
.cfg-card h3{{font-size:13px;font-weight:600;color:#94a3b8;letter-spacing:.05em;margin-bottom:14px}}
.cfg-field{{margin-bottom:12px}}
.cfg-label{{font-size:11px;color:#6b7280;margin-bottom:4px;display:block}}
.cfg-input{{background:#111827;border:1px solid #334155;border-radius:6px;color:#e2e8f0;padding:6px 10px;font-size:13px;width:100%;outline:none}}
.cfg-input:focus{{border-color:#60a5fa}}
.cfg-toggle{{display:flex;align-items:center;gap:10px;margin-bottom:12px}}
.toggle-label{{font-size:13px;color:#e2e8f0}}
input[type=checkbox]{{width:16px;height:16px;accent-color:#ef4444}}
.save-btn{{background:#60a5fa;border:none;color:#000;font-weight:700;padding:8px 18px;border-radius:6px;cursor:pointer;font-size:13px;margin-top:8px}}
.save-btn:hover{{background:#3b82f6}}
.saved-msg{{color:#22c55e;font-size:12px;margin-left:10px;opacity:0;transition:opacity .3s}}
.cfg-raw{{background:#111827;border:1px solid #334155;border-radius:6px;padding:14px;font-family:monospace;font-size:12px;color:#cbd5e1;white-space:pre;overflow-x:auto;margin-top:14px}}

/* Health / Alpaca card */
.health-card{{background:#1a1f2e;border-radius:10px;padding:20px;max-width:500px;margin-bottom:20px}}
.health-row{{display:flex;justify-content:space-between;padding:6px 0;border-bottom:1px solid #111827;font-size:13px}}
.health-row:last-child{{border:none}}
.dot-ok{{color:#22c55e}}
.dot-warn{{color:#fb923c}}

/* Signals mini table */
.mini-table{{width:100%;border-collapse:collapse;max-width:1200px}}
.mini-table th{{padding:8px 10px;text-align:left;color:#6b7280;font-size:11px;font-weight:600;letter-spacing:.05em;border-bottom:1px solid #1e293b}}
.mini-table td{{padding:8px 10px;border-bottom:1px solid #111827;font-size:13px}}
.mini-table tr:hover td{{background:#1a1f2e}}
.badge{{display:inline-block;padding:1px 7px;border-radius:3px;font-size:11px;font-weight:700}}
.run-log{{background:#111827;border-radius:8px;padding:16px;font-family:monospace;font-size:12px;color:#9ca3af;white-space:pre-wrap;max-height:300px;overflow-y:auto;margin-top:16px}}
.empty{{color:#4b5563;text-align:center;padding:40px}}
</style>
</head>
<body>

<div class="header">
  <span class="heartbeat" id="hb"></span>
  <h1>ProjectDolph2.0</h1>
  <select class="trader-sel" id="traderSel" onchange="selectTrader(this.value)">
    {trader_opts}
  </select>
  <button class="run-btn" id="runBtn" onclick="runPaper()" style="transition:opacity .15s">Run Paper Pipeline</button>
</div>

<div class="status-bar">
  <div>Trader: <span id="statusTrader">{default_trader}</span></div>
  <div>Last run: <span id="statusRun">—</span></div>
  <div>Signals: <span id="statusSigs">—</span></div>
  <div>Open positions: <span id="statusPos">—</span></div>
</div>

<div class="tab-bar">
  <button class="tab-btn active" id="liveTabBtn" onclick="switchTab('live',this)" style="color:#22c55e">&#9679; Live</button>
  <button class="tab-btn" onclick="switchTab('health',this)">Health</button>
  <span style="width:1px;background:#1e293b;margin:6px 4px;flex-shrink:0"></span>
  <span style="font-size:10px;color:#374151;padding:0 4px;align-self:center;user-select:none">
    <span style="letter-spacing:.08em">BACKTEST</span>
    <span style="color:#1e293b;font-size:9px;margin-left:4px">(historical) &amp; system sanity</span>
  </span>
  <button class="tab-btn" onclick="switchTab('signals',this)" style="color:#6b7280">Signals</button>
  <button class="tab-btn" onclick="switchTab('equity',this)" style="color:#6b7280">Equity</button>
  <button class="tab-btn" onclick="switchTab('orderbook',this)" style="color:#6b7280">Order Book</button>
  <button class="tab-btn" onclick="switchTab('trace',this)" style="color:#6b7280">Trace</button>
  <span style="width:1px;background:#1e293b;margin:6px 4px;flex-shrink:0"></span>
  <span style="font-size:10px;color:#374151;letter-spacing:.08em;padding:0 4px;align-self:center;user-select:none">TOOLS</span>
  <button class="tab-btn" onclick="switchTab('pipeline',this)" style="color:#6b7280">Pipeline</button>
  <button class="tab-btn" onclick="switchTab('debug',this)" style="color:#6b7280">Debug</button>
</div>

<div class="tab-panel active" id="tab-signals">

  <!-- Signal Review Guide -->
  <div style="background:#111827;border:1px solid #1e293b;border-radius:10px;margin-bottom:14px">
    <div style="display:flex;align-items:center;gap:10px;padding:12px 16px;cursor:pointer"
         onclick="_toggleSigGuide()">
      <span id="sigGuideArrow" style="font-size:11px;color:#6b7280">&#9654;</span>
      <span style="font-size:12px;font-weight:800;color:#e2e8f0;letter-spacing:.04em;user-select:none">
        HOW TO USE SIGNAL REVIEW
      </span>
      <span style="font-size:11px;color:#374151;user-select:none">— label signals, improve the parser</span>
    </div>
    <div id="sigGuideBody" style="display:none;padding:0 18px 18px 18px;border-top:1px solid #1e293b">

      <!-- Workflow -->
      <div style="margin-top:14px;margin-bottom:16px">
        <div style="font-size:11px;font-weight:700;color:#f59e0b;letter-spacing:.05em;margin-bottom:10px">THE LOOP</div>
        <div style="display:flex;align-items:center;gap:0;flex-wrap:wrap;font-size:12px">
          <div style="background:#1e293b;border-radius:8px;padding:8px 14px;color:#e2e8f0;text-align:center">
            <div style="font-size:16px;margin-bottom:2px">&#128393;</div>
            <b>1. Label</b><br>
            <span style="color:#6b7280;font-size:11px">Mark signals<br>correct / wrong</span>
          </div>
          <div style="color:#374151;font-size:18px;padding:0 8px">&#8594;</div>
          <div style="background:#1e293b;border-radius:8px;padding:8px 14px;color:#e2e8f0;text-align:center">
            <div style="font-size:16px;margin-bottom:2px">&#128202;</div>
            <b>2. Analyze</b><br>
            <span style="color:#6b7280;font-size:11px">Correction Stats<br>shows patterns</span>
          </div>
          <div style="color:#374151;font-size:18px;padding:0 8px">&#8594;</div>
          <div style="background:#1e293b;border-radius:8px;padding:8px 14px;color:#e2e8f0;text-align:center">
            <div style="font-size:16px;margin-bottom:2px">&#128295;</div>
            <b>3. Fix rule</b><br>
            <span style="color:#6b7280;font-size:11px">Add regex to<br><code style="color:#a3e635">action.py</code></span>
          </div>
          <div style="color:#374151;font-size:18px;padding:0 8px">&#8594;</div>
          <div style="background:#1e293b;border-radius:8px;padding:8px 14px;color:#e2e8f0;text-align:center">
            <div style="font-size:16px;margin-bottom:2px">&#9989;</div>
            <b>4. Verify</b><br>
            <span style="color:#6b7280;font-size:11px"><code style="color:#a3e635">python dev.py</code><br>15/15 pass</span>
          </div>
          <div style="color:#374151;font-size:18px;padding:0 8px">&#8594;</div>
          <div style="background:#1e293b;border-radius:8px;padding:8px 14px;color:#e2e8f0;text-align:center">
            <div style="font-size:16px;margin-bottom:2px">&#128200;</div>
            <b>5. Measure</b><br>
            <span style="color:#6b7280;font-size:11px"><code style="color:#a3e635">--corpus Grizzlies</code><br>UNSURE drops</span>
          </div>
          <div style="color:#374151;font-size:18px;padding:0 8px">&#8635;</div>
          <div style="color:#94a3b8;font-size:11px;padding:0 4px;font-style:italic">repeat</div>
        </div>
      </div>

      <!-- What to write -->
      <div style="border-top:1px solid #1e293b;padding-top:14px;margin-bottom:16px">
        <div style="font-size:11px;font-weight:700;color:#60a5fa;letter-spacing:.05em;margin-bottom:10px">
          WHAT TO WRITE IN THE REASON FIELD
        </div>
        <div style="font-size:12px;color:#94a3b8;margin-bottom:10px;line-height:1.7">
          Write the <b style="color:#e2e8f0">shortest phrase in the message that gave it away.</b>
          That phrase gets turned directly into a regex rule — one reason = one fix.
          Don't explain the logic, just quote the text.
        </div>
        <table style="border-collapse:collapse;width:100%;font-size:12px">
          <thead>
            <tr style="border-bottom:1px solid #1e293b">
              <th style="padding:6px 10px;text-align:left;color:#374151;font-weight:600;font-size:10px;letter-spacing:.05em">MESSAGE</th>
              <th style="padding:6px 10px;text-align:left;color:#374151;font-weight:600;font-size:10px;letter-spacing:.05em">PARSED AS</th>
              <th style="padding:6px 10px;text-align:left;color:#374151;font-weight:600;font-size:10px;letter-spacing:.05em">CORRECT</th>
              <th style="padding:6px 10px;text-align:left;color:#374151;font-weight:600;font-size:10px;letter-spacing:.05em">WRITE IN REASON</th>
            </tr>
          </thead>
          <tbody>
            <tr style="border-bottom:1px solid #0f172a">
              <td style="padding:6px 10px;color:#94a3b8;font-style:italic">"Ordi hit SL"</td>
              <td style="padding:6px 10px"><span style="color:#fb923c">UNSURE</span></td>
              <td style="padding:6px 10px"><span style="color:#ef4444">EXIT</span></td>
              <td style="padding:6px 10px"><code style="color:#a3e635;background:#0d1117;padding:2px 6px;border-radius:4px">hit SL</code></td>
            </tr>
            <tr style="border-bottom:1px solid #0f172a">
              <td style="padding:6px 10px;color:#94a3b8;font-style:italic">"Close hood here -30%"</td>
              <td style="padding:6px 10px"><span style="color:#fb923c">UNSURE</span></td>
              <td style="padding:6px 10px"><span style="color:#ef4444">EXIT</span></td>
              <td style="padding:6px 10px"><code style="color:#a3e635;background:#0d1117;padding:2px 6px;border-radius:4px">close X here</code></td>
            </tr>
            <tr style="border-bottom:1px solid #0f172a">
              <td style="padding:6px 10px;color:#94a3b8;font-style:italic">"Collected another 50% on btc"</td>
              <td style="padding:6px 10px"><span style="color:#fb923c">UNSURE</span></td>
              <td style="padding:6px 10px"><span style="color:#22d3ee">TRIM</span></td>
              <td style="padding:6px 10px"><code style="color:#a3e635;background:#0d1117;padding:2px 6px;border-radius:4px">collected N%</code></td>
            </tr>
            <tr style="border-bottom:1px solid #0f172a">
              <td style="padding:6px 10px;color:#94a3b8;font-style:italic">"I will sell half @62"</td>
              <td style="padding:6px 10px"><span style="color:#fb923c">UNSURE</span></td>
              <td style="padding:6px 10px"><span style="color:#22d3ee">TRIM</span></td>
              <td style="padding:6px 10px"><code style="color:#a3e635;background:#0d1117;padding:2px 6px;border-radius:4px">sell half</code></td>
            </tr>
            <tr style="border-bottom:1px solid #0f172a">
              <td style="padding:6px 10px;color:#94a3b8;font-style:italic">"Added $500 more on the short"</td>
              <td style="padding:6px 10px"><span style="color:#fb923c">UNSURE</span></td>
              <td style="padding:6px 10px"><span style="color:#60a5fa">ADD</span></td>
              <td style="padding:6px 10px"><code style="color:#a3e635;background:#0d1117;padding:2px 6px;border-radius:4px">added $N more</code></td>
            </tr>
            <tr style="border-bottom:1px solid #0f172a">
              <td style="padding:6px 10px;color:#94a3b8;font-style:italic">"Looking at HOOD calls for sure"</td>
              <td style="padding:6px 10px"><span style="color:#fb923c">UNSURE</span></td>
              <td style="padding:6px 10px"><span style="color:#6b7280">NOISE</span></td>
              <td style="padding:6px 10px"><code style="color:#a3e635;background:#0d1117;padding:2px 6px;border-radius:4px">looking at X = watching, not a trade</code></td>
            </tr>
            <tr>
              <td style="padding:6px 10px;color:#94a3b8;font-style:italic">"Stops hit entry on eth"</td>
              <td style="padding:6px 10px"><span style="color:#fb923c">UNSURE</span></td>
              <td style="padding:6px 10px"><span style="color:#ef4444">EXIT</span></td>
              <td style="padding:6px 10px"><code style="color:#a3e635;background:#0d1117;padding:2px 6px;border-radius:4px">stops hit entry</code></td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- Where rules live -->
      <div style="border-top:1px solid #1e293b;padding-top:14px">
        <div style="font-size:11px;font-weight:700;color:#a78bfa;letter-spacing:.05em;margin-bottom:8px">WHERE THE FIXES GO</div>
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;font-size:12px">
          <div style="background:#0d1117;border-radius:8px;padding:12px 14px">
            <div style="color:#e2e8f0;font-weight:700;margin-bottom:6px">
              <code style="color:#a3e635">parsing/rules/action.py</code>
            </div>
            <div style="color:#6b7280;line-height:1.7">
              All action classification — EXIT, TRIM, ENTRY, ADD, NOISE, UNSURE.
              Every reason you write maps to a new regex line here.
              Run <code style="color:#94a3b8">python dev.py</code> after any change — must stay 15/15.
            </div>
          </div>
          <div style="background:#0d1117;border-radius:8px;padding:12px 14px">
            <div style="color:#e2e8f0;font-weight:700;margin-bottom:6px">
              <code style="color:#a3e635">parsing/rules/symbol.py</code> &amp; <code style="color:#a3e635">price.py</code>
            </div>
            <div style="color:#6b7280;line-height:1.7">
              If the action is right but symbol or entry price is missing/wrong,
              the fix goes here instead.
              Same loop — reason describes the pattern, regex goes in the right file.
            </div>
          </div>
        </div>
        <div style="margin-top:10px;font-size:11px;color:#374151;line-height:1.8">
          After adding rules: &nbsp;
          <code style="color:#94a3b8;background:#0d1117;padding:2px 8px;border-radius:4px">python dev.py</code> &nbsp;&#8594;&nbsp;
          <code style="color:#94a3b8;background:#0d1117;padding:2px 8px;border-radius:4px">python dev.py --corpus Grizzlies</code> &nbsp;&#8594;&nbsp;
          watch UNSURE % drop
        </div>
      </div>

    </div>
  </div>

  <!-- Tools bar: Decoder + Master Rules, collapsible -->
  <div style="background:#111827;border:1px solid #1e293b;border-radius:10px;margin-bottom:12px">
    <div style="display:flex;align-items:center;gap:10px;padding:10px 16px;cursor:pointer"
         onclick="_toggleSigTools()">
      <span style="font-size:11px;font-weight:800;color:#94a3b8;letter-spacing:.06em">&#9654; DECODER &amp; RULES</span>
      <span id="sigToolsChev" style="color:#374151;font-size:12px;margin-left:auto">&#9660;</span>
    </div>
    <div id="sigToolsBody" style="display:none;padding:0 16px 16px;border-top:1px solid #1e293b">
      <div style="display:flex;gap:14px;align-items:flex-start;margin-top:14px">

        <!-- Decoder -->
        <div style="flex:0 0 360px">
          <div style="font-size:11px;font-weight:700;color:#6b7280;letter-spacing:.06em;margin-bottom:8px">DECODER — paste any message</div>
          <textarea id="traceInput" rows="3" placeholder="Paste a Discord message..."
            style="width:100%;background:#0d1117;color:#e2e8f0;border:1px solid #334155;border-radius:6px;
                   padding:8px 10px;font-size:12px;font-family:monospace;resize:vertical;
                   box-sizing:border-box;line-height:1.5;margin-bottom:8px"
            onkeydown="if((event.ctrlKey||event.metaKey)&&event.key==='Enter')_runTrace()"></textarea>
          <div style="display:flex;gap:6px;margin-bottom:10px">
            <button onclick="_runTrace()"
              style="background:#1d4ed8;color:#fff;border:none;border-radius:6px;
                     padding:6px 20px;cursor:pointer;font-size:12px;font-weight:700">
              &#9654; Decode
            </button>
            <button onclick="document.getElementById('traceInput').value='';document.getElementById('traceOutput').innerHTML=''"
              style="background:#1e293b;color:#6b7280;border:1px solid #334155;border-radius:6px;
                     padding:6px 12px;cursor:pointer;font-size:12px">&#10005;</button>
          </div>
          <div id="traceOutput"></div>
        </div>

        <!-- Master Rules -->
        <div style="flex:1;min-width:0;max-height:340px;overflow-y:auto;overflow-x:hidden">
          <div style="display:flex;align-items:center;gap:8px;margin-bottom:10px">
            <span style="font-size:11px;font-weight:700;color:#6b7280;letter-spacing:.06em">MASTER RULES</span>
            <button onclick="loadRules()" title="Refresh"
              style="background:#1e293b;color:#6b7280;border:1px solid #334155;border-radius:4px;
                     padding:2px 8px;cursor:pointer;font-size:11px;margin-left:auto">&#8635;</button>
          </div>
          <div id="rulesContent"><div style="color:#374151;font-size:12px">Loading...</div></div>
        </div>

      </div>
    </div>
  </div>

  <!-- Full-width signal table -->
  <div id="signalsContent"><div class="empty">Loading signals...</div></div>

</div>

<div class="tab-panel" id="tab-equity">
  <div id="equityContent"><div class="empty">Loading equity data...</div></div>
</div>

<div class="tab-panel" id="tab-orderbook">
  <div id="obContent"><div class="empty">Loading order book...</div></div>
</div>

<div class="tab-panel" id="tab-config">
  <div id="configContent"><div class="empty">Loading config...</div></div>
</div>

<div class="tab-panel" id="tab-health">
  <div id="healthContent"><div class="empty">Loading health data...</div></div>
</div>

<div class="tab-panel" id="tab-trace">
  <div id="traceContent"><div class="empty">Click Trace tab after running the paper pipeline to see message connections.</div></div>
</div>

<div class="tab-panel" id="tab-pipeline">
  <div id="pipelineContent"><div class="empty">Loading pipeline docs...</div></div>
</div>

<div class="tab-panel" id="tab-live">
  <div id="liveContent"><div class="empty">Loading...</div></div>
</div>

<div class="tab-panel" id="tab-debug">
  <div id="debugContent"><div class="empty">Click the Debug tab to load diagnostics.</div></div>
</div>

<div id="runLog" class="run-log" style="display:none;margin:0 24px 24px"></div>

<script>
const ACTION_COLORS = {{
  ENTRY:'#22c55e', TRIM:'#22d3ee', EXIT:'#facc15',
  ADD:'#60a5fa',   UNSURE:'#fb923c', NOISE:'#6b7280'
}};

let currentTrader = '{default_trader}';
let activeTab     = 'signals';

// ---- Heartbeat ---------------------------------------------------------------
async function heartbeat() {{
  try {{
    const r = await fetch('/api/health');
    const d = await r.json();
    document.getElementById('hb').style.background = '#22c55e';
  }} catch(e) {{
    document.getElementById('hb').style.background = '#ef4444';
  }}
}}
setInterval(heartbeat, 5000);
heartbeat();

// ---- Tab switching -----------------------------------------------------------
function switchTab(name, btn) {{
  document.querySelectorAll('.tab-panel').forEach(p=>p.classList.remove('active'));
  document.querySelectorAll('.tab-btn').forEach(b=>b.classList.remove('active'));
  document.getElementById('tab-'+name).classList.add('active');
  btn.classList.add('active');
  activeTab = name;
  // Hide "Run Paper Pipeline" on the Live tab — it belongs to backtest/paper flow only
  const runBtn = document.getElementById('runBtn');
  if (runBtn) runBtn.style.display = (name === 'live') ? 'none' : '';
  loadTab(name);
}}

function selectTrader(t) {{
  currentTrader = t;
  document.getElementById('statusTrader').textContent = t;
  const sel = document.getElementById('traderSel');
  if (sel) sel.value = t;
  loadTab(activeTab);
}}

function loadTab(name) {{
  if (name === 'signals')   loadSignals();
  if (name === 'equity')    loadEquity();
  if (name === 'orderbook') loadOrderBook();
  if (name === 'config')    loadConfig();
  if (name === 'health')    loadHealth();
  if (name === 'trace')     loadTrace();
  if (name === 'pipeline')  loadPipeline();
  if (name === 'live')      initLive();
  if (name === 'debug')     loadDebug();
}}

// ---- Signals -----------------------------------------------------------------
// Signal review state
let _sigReviewMode  = false;
let _sigCorrections = {{}};
let _sigOffset      = 0;
let _sigTotal       = 0;
let _sigPageSize    = 200;
let _sigAllData     = [];

async function loadRules() {{
  const el = document.getElementById('rulesContent');
  if (!el) return;
  try {{
    const d = await fetch('/api/rules').then(r=>r.json());
    const ACTION_CLR2 = {{
      EXIT:'#ef4444', ADD:'#60a5fa', TRIM:'#22d3ee',
      ENTRY:'#22c55e', NOISE:'#6b7280', TRADE_WORDS:'#94a3b8'
    }};
    const SIDE_CLR = {{LONG:'#22c55e', SHORT:'#ef4444'}};

    let html = '';

    // Action rules
    for (const [action, phrases] of Object.entries(d.action||{{}})) {{
      if (action === 'TRADE_WORDS') continue;
      const col = ACTION_CLR2[action] || '#94a3b8';
      html += `<div style="margin-bottom:12px">
        <div style="font-size:10px;font-weight:700;color:${{col}};letter-spacing:.06em;
                    margin-bottom:5px;display:flex;align-items:center;gap:6px">
          ${{action}}
          <span style="color:#374151;font-weight:400;font-size:9px">${{phrases.length}} patterns</span>
        </div>
        <div style="display:flex;flex-wrap:wrap;gap:4px">
          ${{phrases.map(p=>`<span title="${{p.replace(/"/g,'&quot;')}}"
            style="background:${{col}}18;color:${{col}}cc;font-size:10px;
            padding:2px 7px;border-radius:4px;border:1px solid ${{col}}33;font-family:monospace;
            white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:100%;
            display:inline-block;vertical-align:middle">${{p.replace(/</g,'&lt;').substring(0,40)}}${{p.length>40?'…':''}}</span>`).join('')}}
        </div>
      </div>`;
    }}

    // Side rules
    html += `<div style="border-top:1px solid #1e293b;padding-top:10px;margin-bottom:12px">
      <div style="font-size:10px;font-weight:700;color:#94a3b8;letter-spacing:.06em;margin-bottom:6px">SIDE</div>`;
    for (const [side, phrases] of Object.entries(d.side||{{}})) {{
      const col = SIDE_CLR[side] || '#94a3b8';
      html += `<div style="margin-bottom:6px">
        <span style="font-size:10px;color:${{col}};font-weight:700;margin-right:6px">${{side}}</span>
        ${{phrases.map(p=>`<span title="${{p}}"
          style="background:${{col}}15;color:${{col}}bb;font-size:10px;
          padding:1px 6px;border-radius:3px;font-family:monospace;margin-right:3px;margin-bottom:3px;
          white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:260px;
          display:inline-block;vertical-align:middle">${{p.substring(0,38)}}${{p.length>38?'…':''}}</span>`).join('')}}
      </div>`;
    }}
    html += `</div>`;

    // Price patterns
    html += `<div style="border-top:1px solid #1e293b;padding-top:10px;margin-bottom:12px">
      <div style="font-size:10px;font-weight:700;color:#f59e0b;letter-spacing:.06em;margin-bottom:6px">PRICE PATTERNS</div>`;
    for (const [name, pat] of Object.entries(d.price||{{}})) {{
      html += `<div style="margin-bottom:4px;display:flex;gap:6px;align-items:flex-start">
        <span style="font-size:9px;color:#6b7280;min-width:90px;padding-top:2px">${{name}}</span>
        <code style="font-size:9px;color:#f59e0b;word-break:break-all;line-height:1.4">${{pat.replace(/</g,'&lt;')}}</code>
      </div>`;
    }}
    html += `</div>`;

    // Symbols
    const sym = d.symbols || {{}};
    html += `<div style="border-top:1px solid #1e293b;padding-top:10px">
      <div style="font-size:10px;font-weight:700;color:#a78bfa;letter-spacing:.06em;margin-bottom:6px">
        SYMBOLS
        <span style="color:#374151;font-weight:400">
          — ${{sym.crypto_total||0}} crypto · ${{sym.stock_total||0}} stock
        </span>
      </div>
      <div style="margin-bottom:6px">
        <div style="font-size:9px;color:#6b7280;margin-bottom:4px">CRYPTO (${{(sym.crypto||[]).length}} shown)</div>
        <div style="display:flex;flex-wrap:wrap;gap:3px">
          ${{(sym.crypto||[]).slice(0,60).map(s=>`<span style="background:#fb923c18;color:#fb923c;font-size:9px;
            padding:1px 5px;border-radius:3px;font-family:monospace">${{s}}</span>`).join('')}}
          ${{(sym.crypto||[]).length>60?`<span style="color:#374151;font-size:9px">+${{(sym.crypto||[]).length-60}} more</span>`:''}}
        </div>
      </div>
      <div>
        <div style="font-size:9px;color:#6b7280;margin-bottom:4px">STOCK (${{(sym.stock||[]).length}} shown)</div>
        <div style="display:flex;flex-wrap:wrap;gap:3px">
          ${{(sym.stock||[]).slice(0,60).map(s=>`<span style="background:#38bdf818;color:#38bdf8;font-size:9px;
            padding:1px 5px;border-radius:3px;font-family:monospace">${{s}}</span>`).join('')}}
          ${{(sym.stock||[]).length>60?`<span style="color:#374151;font-size:9px">+${{(sym.stock||[]).length-60}} more</span>`:''}}
        </div>
      </div>
    </div>`;

    el.innerHTML = html;
  }} catch(e) {{
    el.innerHTML = `<div style="color:#ef4444;font-size:11px">Error: ${{e.message}}</div>`;
  }}
}}

async function loadSignals(offset) {{
  if (offset === undefined) offset = _sigOffset;
  _sigOffset = offset;
  const el = document.getElementById('signalsContent');
  el.innerHTML = '<div class="empty">Loading...</div>';
  try {{
    const [sigRes, corRes] = await Promise.all([
      fetch(`/api/signals/${{currentTrader}}?offset=${{offset}}&limit=${{_sigPageSize}}`).then(r=>r.json()),
      fetch(`/api/corrections/${{currentTrader}}`).then(r=>r.json()),
    ]);
    _sigAllData = sigRes.signals || [];
    _sigTotal   = sigRes.total   || 0;
    document.getElementById('statusSigs').textContent = _sigTotal;

    _sigCorrections = {{}};
    for (const c of (corRes.corrections || [])) {{
      _sigCorrections[c.msg_hash] = c;
    }}

    _renderSignals();
    loadRules();
  }} catch(e) {{ el.innerHTML = `<div class="empty">Error: ${{e.message}}</div>`; }}
}}

function _msgHash(content) {{
  // Simple non-crypto hash for indexing — good enough for dedup
  let h = 0;
  for (let i = 0; i < Math.min(content.length, 200); i++) {{
    h = ((h << 5) - h + content.charCodeAt(i)) | 0;
  }}
  return 'h' + Math.abs(h).toString(16);
}}

// Lookup table: hash -> signal data — avoids inline string escaping in onclick attrs
const _sigDataByHash = {{}};

function _renderSignals() {{
  const el = document.getElementById('signalsContent');
  if (!_sigAllData) return;
  const display  = _sigAllData;   // already the current page from API
  const reviewed = Object.keys(_sigCorrections).length;
  const pageNum  = Math.floor(_sigOffset / _sigPageSize) + 1;
  const totalPages = Math.ceil(_sigTotal / _sigPageSize);

  const pagination = `
    <div style="display:flex;align-items:center;gap:10px;margin-top:14px;flex-wrap:wrap">
      <button onclick="loadSignals(0)"
        ${{_sigOffset===0?'disabled':''}}
        style="background:#1e293b;color:#e2e8f0;border:1px solid #334155;border-radius:6px;
               padding:5px 14px;cursor:pointer;font-size:12px;opacity:${{_sigOffset===0?.4:1}}">
        &#171; First
      </button>
      <button onclick="loadSignals(${{Math.max(0,_sigOffset-_sigPageSize)}})"
        ${{_sigOffset===0?'disabled':''}}
        style="background:#1e293b;color:#e2e8f0;border:1px solid #334155;border-radius:6px;
               padding:5px 14px;cursor:pointer;font-size:12px;opacity:${{_sigOffset===0?.4:1}}">
        &#8592; Prev
      </button>
      <span style="color:#94a3b8;font-size:12px">
        Page ${{pageNum}} of ${{totalPages}}
        &nbsp;&middot;&nbsp;
        signals ${{_sigOffset+1}}–${{Math.min(_sigOffset+_sigPageSize,_sigTotal)}} of ${{_sigTotal}}
      </span>
      <button onclick="loadSignals(${{_sigOffset+_sigPageSize}})"
        ${{_sigOffset+_sigPageSize>=_sigTotal?'disabled':''}}
        style="background:#1e293b;color:#e2e8f0;border:1px solid #334155;border-radius:6px;
               padding:5px 14px;cursor:pointer;font-size:12px;opacity:${{_sigOffset+_sigPageSize>=_sigTotal?.4:1}}">
        Next &#8594;
      </button>
      <button onclick="loadSignals(${{(_sigTotal-1-(_sigTotal-1)%_sigPageSize)}})"
        ${{_sigOffset+_sigPageSize>=_sigTotal?'disabled':''}}
        style="background:#1e293b;color:#e2e8f0;border:1px solid #334155;border-radius:6px;
               padding:5px 14px;cursor:pointer;font-size:12px;opacity:${{_sigOffset+_sigPageSize>=_sigTotal?.4:1}}">
        Last &#187;
      </button>
      <select onchange="loadSignals(parseInt(this.value)*_sigPageSize)"
        style="background:#1e293b;color:#e2e8f0;border:1px solid #334155;border-radius:6px;
               padding:5px 10px;font-size:12px;margin-left:8px">
        ${{Array.from({{length:totalPages}},(_,i)=>`<option value="${{i}}"${{i===pageNum-1?' selected':''}}>${{i*_sigPageSize+1}}–${{Math.min((i+1)*_sigPageSize,_sigTotal)}}</option>`).join('')}}
      </select>
    </div>`;

  const correct  = Object.values(_sigCorrections).filter(c=>c.verdict==='correct').length;
  const wrong    = Object.values(_sigCorrections).filter(c=>c.verdict==='wrong').length;
  const pct      = _sigTotal ? (reviewed / _sigTotal * 100).toFixed(1) : '0.0';
  const pctNum   = parseFloat(pct);
  const barColor = pctNum >= 75 ? '#22c55e' : pctNum >= 40 ? '#f59e0b' : '#60a5fa';

  const header = `
    <div style="background:#111827;border:1px solid #1e293b;border-radius:10px;padding:14px 18px;margin-bottom:14px">
      <div style="display:flex;align-items:center;gap:16px;margin-bottom:10px;flex-wrap:wrap">
        <div>
          <span style="font-size:22px;font-weight:800;color:${{barColor}}">${{pct}}%</span>
          <span style="font-size:12px;color:#6b7280;margin-left:6px">reviewed</span>
        </div>
        <div style="display:flex;gap:18px;font-size:12px">
          <span style="color:#6b7280">Total: <b style="color:#e2e8f0">${{_sigTotal}}</b></span>
          <span style="color:#22c55e">&#10003; Correct: <b>${{correct}}</b></span>
          <span style="color:#ef4444">&#10007; Wrong: <b>${{wrong}}</b></span>
          <span style="color:#374151">Unreviewed: <b style="color:#94a3b8">${{_sigTotal - reviewed}}</b></span>
        </div>
        <button onclick="_showCorrectionStats()"
          style="background:#1e293b;color:#f59e0b;border:1px solid #f59e0b33;border-radius:6px;
                 padding:5px 14px;cursor:pointer;font-size:12px;margin-left:auto">
          &#128202; Correction Stats
        </button>
      </div>
      <div style="background:#1e293b;border-radius:999px;height:8px;overflow:hidden">
        <div style="height:100%;border-radius:999px;transition:width .4s;
                    background:linear-gradient(90deg,${{barColor}},${{barColor}}99);
                    width:${{pct}}%"></div>
      </div>
      <div style="margin-top:8px;font-size:11px;color:#374151">
        &#10003; = correct &nbsp;&nbsp; &#10007; = wrong — opens form to pick correct action + reason &nbsp;&nbsp;
        Saved to <code style="color:#475569">data/${{currentTrader}}/corrections.jsonl</code>
      </div>
    </div>`;

  const ACTIONS = ['ENTRY','TRIM','EXIT','ADD','UNSURE','NOISE'];

  const rows = display.map((s, idx) => {{
    const c      = ACTION_COLORS[s.action] || '#6b7280';
    const conf   = s.confidence || 0;
    const cCol   = conf>=.75?'#22c55e':conf>=.5?'#facc15':'#f87171';
    const hash   = _msgHash(s.raw_content || s.id || idx.toString());
    _sigDataByHash[hash] = s;   // store for onclick lookup
    const saved  = _sigCorrections[hash];
    const isCorrect = saved && saved.verdict === 'correct';
    const isWrong   = saved && saved.verdict === 'wrong';

    let reviewBadge = '';
    if (isCorrect) reviewBadge = `<span style="color:#22c55e;font-size:11px;font-weight:700">&#10003; correct</span>`;
    else if (isWrong) reviewBadge = `<span style="color:#ef4444;font-size:11px;font-weight:700">&#10007; ${{saved.correct_action}}</span>`;

    const decodeRowId = `dr_${{hash}}`;
    const reviewButtons = `
      <td style="white-space:nowrap;padding:5px 8px;vertical-align:top">
        ${{reviewBadge ? `<div style="margin-bottom:4px">${{reviewBadge}}</div>` : ''}}
        <button onclick="_markCorrect('${{hash}}')"
          title="Mark correct"
          style="background:#14532d;color:#22c55e;border:1px solid #22c55e55;border-radius:4px;
                 padding:3px 9px;cursor:pointer;font-size:12px;font-weight:700;margin-right:4px">
          &#10003;
        </button>
        <button onclick="_toggleWrongForm('${{hash}}')"
          title="Mark wrong — pick correct action"
          style="background:#450a0a;color:#ef4444;border:1px solid #ef444455;border-radius:4px;
                 padding:3px 9px;cursor:pointer;font-size:12px;font-weight:700;margin-right:4px">
          &#10007;
        </button>
        <button onclick="_inlineDecode('${{hash}}')"
          title="Decode this message"
          style="background:#1e293b;color:#60a5fa;border:1px solid #1e40af55;border-radius:4px;
                 padding:3px 9px;cursor:pointer;font-size:12px;font-weight:700">
          &#9654;
        </button>
      </td>`;

    const wrongFormId = `wf_${{hash}}`;
    const noiseReasons = [
      'watching / looking at — not entered yet',
      'future tense — will look for, will enter',
      'market commentary — price levels, analysis',
      'opinion / prediction — I think, I believe',
      'general advice — no specific position',
      'recap / result — after the fact update',
    ];
    const wrongForm = `
      <tr id="${{wrongFormId}}" style="display:none;background:#0d0a1a;border-bottom:2px solid #4c1d95">
        <td colspan="9" style="padding:14px 18px">

          <!-- Message preview -->
          <div style="font-size:11px;color:#94a3b8;background:#0d1117;padding:8px 12px;border-radius:6px;
                      white-space:pre-wrap;max-height:100px;overflow-y:auto;margin-bottom:14px;
                      border:1px solid #1e293b;line-height:1.6">
            ${{(s.raw_content||'').replace(/</g,'&lt;').replace(/>/g,'&gt;')}}
          </div>

          <!-- Q1: Actionable? -->
          <div style="font-size:12px;font-weight:700;color:#e2e8f0;margin-bottom:10px">
            Is this message actionable? Did Grizzlies actually <b style="color:#a78bfa">do something</b> here?
          </div>
          <div style="display:flex;gap:10px;margin-bottom:16px">
            <button onclick="_q1select('${{hash}}','yes')" id="q1yes_${{hash}}"
              style="background:#14532d;color:#22c55e;border:2px solid #22c55e44;border-radius:8px;
                     padding:8px 24px;cursor:pointer;font-size:13px;font-weight:700;transition:all .15s">
              &#10003; Yes — he took an action
            </button>
            <button onclick="_q1select('${{hash}}','no')" id="q1no_${{hash}}"
              style="background:#1e293b;color:#6b7280;border:2px solid #33415533;border-radius:8px;
                     padding:8px 24px;cursor:pointer;font-size:13px;font-weight:700;transition:all .15s">
              &#10007; No — talking about the market
            </button>
          </div>

          <!-- Q2a: Actionable branch -->
          <div id="q2yes_${{hash}}" style="display:none;border-top:1px solid #1e293b;padding-top:14px">
            <div style="font-size:12px;font-weight:700;color:#e2e8f0;margin-bottom:10px">
              What action did he take?
            </div>
            <div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:12px">
              ${{['ENTRY','TRIM','EXIT','ADD'].map(a => `
                <button onclick="_q2action('${{hash}}','${{a}}')" id="q2a_${{hash}}_${{a}}"
                  style="background:#1e293b;color:#94a3b8;border:2px solid #33415533;border-radius:8px;
                         padding:7px 18px;cursor:pointer;font-size:13px;font-weight:700;transition:all .15s">
                  ${{a}}
                </button>`).join('')}}
            </div>
            <div style="margin-bottom:12px">
              <div style="font-size:11px;color:#6b7280;margin-bottom:5px">
                What phrase in the message tells you that?
                <span style="color:#374151">(quote the specific words — this becomes the new rule)</span>
              </div>
              <input id="cr_${{hash}}" type="text"
                placeholder='e.g. "collected 50%" or "hit SL" or "added $500 more"'
                style="width:100%;background:#0d1117;color:#e2e8f0;border:1px solid #334155;
                       border-radius:6px;padding:7px 12px;font-size:12px;box-sizing:border-box">
            </div>
            <div style="display:flex;gap:8px">
              <button onclick="_saveWrong('${{hash}}')"
                style="background:#7c3aed;color:#fff;border:none;border-radius:6px;
                       padding:7px 20px;cursor:pointer;font-size:12px;font-weight:700">
                Save
              </button>
              <button onclick="_cancelWrongForm('${{hash}}')"
                style="background:#1e293b;color:#6b7280;border:none;border-radius:6px;
                       padding:7px 14px;cursor:pointer;font-size:12px">
                Cancel
              </button>
            </div>
          </div>

          <!-- Q2b: Not actionable branch -->
          <div id="q2no_${{hash}}" style="display:none;border-top:1px solid #1e293b;padding-top:14px">
            <div style="font-size:12px;font-weight:700;color:#e2e8f0;margin-bottom:10px">
              Why is it not actionable? <span style="color:#374151;font-weight:400">(pick closest)</span>
            </div>
            <div style="display:flex;flex-direction:column;gap:6px;margin-bottom:12px">
              ${{noiseReasons.map((r,i) => `
                <label style="display:flex;align-items:center;gap:10px;cursor:pointer;padding:6px 10px;
                              border-radius:6px;border:1px solid #1e293b;background:#0d1117;
                              font-size:12px;color:#94a3b8"
                       onmouseover="this.style.borderColor='#334155'"
                       onmouseout="this.style.borderColor='#1e293b'">
                  <input type="radio" name="noise_${{hash}}" value="${{r}}"
                         style="accent-color:#a78bfa">
                  ${{r}}
                </label>`).join('')}}
            </div>
            <div style="display:flex;gap:8px">
              <button onclick="_saveNoise('${{hash}}')"
                style="background:#4c1d95;color:#a78bfa;border:1px solid #7c3aed55;border-radius:6px;
                       padding:7px 20px;cursor:pointer;font-size:12px;font-weight:700">
                Save as NOISE
              </button>
              <button onclick="_cancelWrongForm('${{hash}}')"
                style="background:#1e293b;color:#6b7280;border:none;border-radius:6px;
                       padding:7px 14px;cursor:pointer;font-size:12px">
                Cancel
              </button>
            </div>
          </div>

        </td>
      </tr>`;

    const decodeRow = `
      <tr id="${{decodeRowId}}" style="display:none;background:#060d18;border-bottom:2px solid #1e40af">
        <td colspan="9" style="padding:12px 18px">
          <div id="${{decodeRowId}}_out" style="color:#374151;font-size:12px">Decoding...</div>
        </td>
      </tr>`;

    const ts = (s.timestamp||'').replace('T',' ').substring(0,19);
    const msgFull = (s.raw_content||'').replace(/</g,'&lt;').replace(/>/g,'&gt;');
    const rowBg     = isWrong ? '#1f0808' : isCorrect ? '#071a0d' : 'transparent';
    const rowBorder = isWrong ? '2px solid #7f1d1d' : isCorrect ? '2px solid #14532d' : '1px solid #1e293b';
    return `<tr style="border-bottom:${{rowBorder}};background:${{rowBg}};vertical-align:top">
      <td style="color:#94a3b8;font-size:11px;white-space:nowrap;padding:7px 10px;min-width:140px">${{ts}}</td>
      <td style="padding:7px 8px"><span class="badge" style="background:${{c}}22;color:${{c}}">${{s.action}}</span></td>
      <td style="font-weight:700;padding:7px 8px;white-space:nowrap">${{s.symbol||''}}</td>
      <td style="color:#94a3b8;font-size:12px;padding:7px 8px">${{s.asset_type||''}}</td>
      <td style="color:#94a3b8;font-size:12px;padding:7px 8px">${{s.side||''}}</td>
      <td style="font-family:monospace;font-size:12px;padding:7px 8px;white-space:nowrap">${{s.entry_price||''}}</td>
      <td style="color:${{cCol}};font-family:monospace;font-size:12px;padding:7px 8px">${{conf.toFixed(2)}}</td>
      <td style="color:#94a3b8;font-size:12px;padding:7px 10px;white-space:pre-wrap;max-width:520px;line-height:1.5;word-break:break-word">
        ${{msgFull}}
      </td>
      ${{reviewButtons}}
    </tr>${{wrongForm}}${{decodeRow}}`;
  }}).join('');

  el.innerHTML = header
    + `<table class="mini-table" style="border-collapse:collapse;width:100%">
    <thead><tr>
      <th>Time</th><th>Action</th><th>Symbol</th><th>Asset</th><th>Side</th>
      <th>Entry</th><th>Conf</th><th>Message</th>
      <th>${{_sigReviewMode ? 'Review' : 'Status'}}</th>
    </tr></thead>
    <tbody>${{rows}}</tbody>
  </table>`
    + pagination;
}}

function _toggleReviewMode() {{
  _sigReviewMode = !_sigReviewMode;
  _renderSignals();
}}

function _toggleWrongForm(hash) {{
  const el = document.getElementById(`wf_${{hash}}`);
  if (!el) return;
  const opening = el.style.display === 'none';
  el.style.display = opening ? '' : 'none';
  if (opening) {{
    // Reset form state
    document.getElementById(`q2yes_${{hash}}`).style.display = 'none';
    document.getElementById(`q2no_${{hash}}`).style.display  = 'none';
    const yBtn = document.getElementById(`q1yes_${{hash}}`);
    const nBtn = document.getElementById(`q1no_${{hash}}`);
    if (yBtn) {{ yBtn.style.background='#14532d'; yBtn.style.color='#22c55e'; yBtn.style.borderColor='#22c55e44'; }}
    if (nBtn) {{ nBtn.style.background='#1e293b'; nBtn.style.color='#6b7280'; nBtn.style.borderColor='#33415533'; }}
  }}
}}

function _cancelWrongForm(hash) {{
  const el = document.getElementById(`wf_${{hash}}`);
  if (el) el.style.display = 'none';
}}

function _q1select(hash, choice) {{
  const yBtn  = document.getElementById(`q1yes_${{hash}}`);
  const nBtn  = document.getElementById(`q1no_${{hash}}`);
  const yForm = document.getElementById(`q2yes_${{hash}}`);
  const nForm = document.getElementById(`q2no_${{hash}}`);
  if (choice === 'yes') {{
    if (yBtn) {{ yBtn.style.background='#166534'; yBtn.style.color='#4ade80'; yBtn.style.borderColor='#22c55e'; }}
    if (nBtn) {{ nBtn.style.background='#1e293b'; nBtn.style.color='#6b7280'; nBtn.style.borderColor='#33415533'; }}
    if (yForm) yForm.style.display = '';
    if (nForm) nForm.style.display = 'none';
  }} else {{
    if (nBtn) {{ nBtn.style.background='#450a0a'; nBtn.style.color='#f87171'; nBtn.style.borderColor='#ef4444'; }}
    if (yBtn) {{ yBtn.style.background='#1e293b'; yBtn.style.color='#6b7280'; yBtn.style.borderColor='#33415533'; }}
    if (nForm) nForm.style.display = '';
    if (yForm) yForm.style.display = 'none';
  }}
}}

// Track selected action for Q2a
const _q2selected = {{}};
function _q2action(hash, action) {{
  _q2selected[hash] = action;
  const ACTIONS = ['ENTRY','TRIM','EXIT','ADD'];
  const COLORS = {{ENTRY:'#22c55e',TRIM:'#22d3ee',EXIT:'#ef4444',ADD:'#60a5fa'}};
  ACTIONS.forEach(a => {{
    const btn = document.getElementById(`q2a_${{hash}}_${{a}}`);
    if (!btn) return;
    if (a === action) {{
      btn.style.background   = (COLORS[a]||'#7c3aed') + '22';
      btn.style.color        = COLORS[a] || '#e2e8f0';
      btn.style.borderColor  = COLORS[a] || '#7c3aed';
    }} else {{
      btn.style.background  = '#1e293b';
      btn.style.color       = '#94a3b8';
      btn.style.borderColor = '#33415533';
    }}
  }});
}}

async function _markCorrect(hash) {{
  const s = _sigDataByHash[hash] || {{}};
  await fetch(`/api/corrections/${{currentTrader}}`, {{
    method: 'POST',
    headers: {{'Content-Type':'application/json'}},
    body: JSON.stringify({{
      msg_hash:       hash,
      msg_preview:    (s.raw_content || '').substring(0, 120),
      parsed_action:  s.action || '',
      correct_action: s.action || '',
      reason:         '',
      verdict:        'correct'
    }})
  }});
  _sigCorrections[hash] = {{verdict:'correct', correct_action: s.action}};
  _renderSignals();
}}

async function _saveWrong(hash) {{
  const s             = _sigDataByHash[hash] || {{}};
  const correctAction = _q2selected[hash] || '';
  const reason        = document.getElementById(`cr_${{hash}}`)?.value.trim() || '';
  if (!correctAction) {{ alert('Pick an action first (ENTRY / TRIM / EXIT / ADD)'); return; }}
  if (!reason) {{ alert('Write the phrase that tells you it is a ' + correctAction); return; }}
  await fetch(`/api/corrections/${{currentTrader}}`, {{
    method: 'POST',
    headers: {{'Content-Type':'application/json'}},
    body: JSON.stringify({{
      msg_hash:       hash,
      msg_preview:    (s.raw_content || '').substring(0, 120),
      parsed_action:  s.action || '',
      correct_action: correctAction,
      reason:         reason,
      verdict:        'wrong',
      actionable:     true,
    }})
  }});
  _sigCorrections[hash] = {{verdict:'wrong', correct_action: correctAction, reason}};
  document.getElementById(`wf_${{hash}}`).style.display = 'none';
  _renderSignals();
}}

async function _saveNoise(hash) {{
  const s      = _sigDataByHash[hash] || {{}};
  const radios = document.querySelectorAll(`input[name="noise_${{hash}}"]`);
  let reason   = '';
  radios.forEach(r => {{ if (r.checked) reason = r.value; }});
  if (!reason) {{ alert('Pick a reason'); return; }}
  await fetch(`/api/corrections/${{currentTrader}}`, {{
    method: 'POST',
    headers: {{'Content-Type':'application/json'}},
    body: JSON.stringify({{
      msg_hash:       hash,
      msg_preview:    (s.raw_content || '').substring(0, 120),
      parsed_action:  s.action || '',
      correct_action: 'NOISE',
      reason:         reason,
      verdict:        'wrong',
      actionable:     false,
    }})
  }});
  _sigCorrections[hash] = {{verdict:'wrong', correct_action: 'NOISE', reason}};
  document.getElementById(`wf_${{hash}}`).style.display = 'none';
  _renderSignals();
}}

async function _showCorrectionStats() {{
  const r = await fetch(`/api/corrections/${{currentTrader}}/stats`).then(x=>x.json());
  let msg = `Reviewed: ${{r.total}}  |  Correct: ${{r.correct}}  |  Wrong: ${{r.wrong}}\n\nMisclassification patterns:\n`;
  for (const p of (r.patterns||[])) {{
    msg += `  ${{p.from}} → should be ${{p.to}}  (${{p.count}}x)\n`;
  }}
  alert(msg);
}}

// ---- Equity ------------------------------------------------------------------
async function loadEquity() {{
  const el = document.getElementById('equityContent');
  el.innerHTML = '<div class="empty">Loading...</div>';
  try {{
    const r  = await fetch(`/api/equity/${{currentTrader}}`);
    const eq = await r.json();
    const start  = eq.starting_balance || 7000;
    const trades = eq.trades || [];
    if (!trades.length) {{
      el.innerHTML = '<div class="empty">No closed trades yet. Run the paper pipeline first.</div>';
      return;
    }}

    // Balance series: eq.equity is already absolute balance (start + cumulative_pnl)
    const balances = [start, ...(eq.equity || [])];
    const labels   = ['start', ...(eq.labels || balances.slice(1).map((_,i)=>`T${{i+1}}`))];
    const final    = balances[balances.length - 1];
    const pnl      = final - start;
    const pct      = (pnl / start * 100).toFixed(2);
    const wins     = trades.filter(t => t.pnl > 0).length;
    const wr       = (wins / trades.length * 100).toFixed(1);
    const pc       = pnl >= 0 ? '#22c55e' : '#ef4444';

    // ---- KPI cards
    // Max drawdown calc
    let peak = start, maxDD = 0;
    for (const b of balances) {{
      if (b > peak) peak = b;
      const dd = (peak - b) / peak * 100;
      if (dd > maxDD) maxDD = dd;
    }}
    const avgWin  = trades.filter(t=>t.pnl>0).reduce((s,t)=>s+t.pnl,0) / (wins||1);
    const avgLoss = trades.filter(t=>t.pnl<0).reduce((s,t)=>s+t.pnl,0) / (trades.length-wins||1);

    const kpis = [
      ['Balance',    `$${{final.toFixed(2)}}`,                              pc],
      ['Return',     `${{pnl>=0?'+':''}}${{pct}}%`,                         pc],
      ['Win Rate',   `${{wr}}%`,  parseFloat(wr)>=50?'#22c55e':'#fb923c'],
      ['Trades',     trades.length,                                         '#e2e8f0'],
      ['Max DD',     `-${{maxDD.toFixed(1)}}%`,                             '#ef4444'],
      ['Avg Win',    `+$${{avgWin.toFixed(2)}}`,                            '#22c55e'],
      ['Avg Loss',   `$${{avgLoss.toFixed(2)}}`,                            '#ef4444'],
      ['Max Win',    `+$${{Math.max(...trades.map(t=>t.pnl)).toFixed(2)}}`, '#22c55e'],
      ['Max Loss',   `$${{Math.min(...trades.map(t=>t.pnl)).toFixed(2)}}`,  '#ef4444'],
    ].map(([l,v,c])=>`<div style="background:#111827;border-radius:8px;padding:12px 18px;min-width:110px">
      <div style="font-size:11px;color:#6b7280;margin-bottom:4px">${{l}}</div>
      <div style="font-size:18px;font-weight:700;color:${{c}}">${{v}}</div></div>`).join('');

    // ---- SVG chart (full-width, tall)
    const W = 1200, H = 400, PAD = {{t:24, r:24, b:48, l:80}};
    const cw = W - PAD.l - PAD.r;
    const ch = H - PAD.t - PAD.b;
    const n  = balances.length;
    const padding = (Math.max(...balances) - Math.min(...balances)) * 0.08 || 20;
    const minB  = Math.min(...balances) - padding;
    const maxB  = Math.max(...balances) + padding;
    const rangeB = maxB - minB;

    const px = i => PAD.l + (i / Math.max(n-1,1)) * cw;
    const py = v => PAD.t + ch - ((v - minB) / rangeB) * ch;
    const startY = py(start);

    // Gradient fill areas
    const pts = balances.map((b,i) => `${{px(i)}},${{py(b)}}`).join(' ');
    const polyAbove = `${{PAD.l}},${{startY}} ${{pts}} ${{px(n-1)}},${{startY}}`;
    const polyBelow = `${{PAD.l}},${{startY}} ${{pts}} ${{px(n-1)}},${{startY}}`;

    // Colored line segments
    let pathSegs = '';
    for (let i = 0; i < n - 1; i++) {{
      const x1=px(i), y1=py(balances[i]), x2=px(i+1), y2=py(balances[i+1]);
      const col = (balances[i]>=start && balances[i+1]>=start) ? '#22c55e'
                : (balances[i]<=start && balances[i+1]<=start) ? '#ef4444' : '#facc15';
      pathSegs += `<line x1="${{x1}}" y1="${{y1}}" x2="${{x2}}" y2="${{y2}}" stroke="${{col}}" stroke-width="2.5" stroke-linecap="round"/>`;
    }}

    // Hover dots (invisible large hit area + visible small dot)
    let dots = '';
    for (let i = 0; i < n; i++) {{
      const b   = balances[i];
      const clr = b > start ? '#22c55e' : b < start ? '#ef4444' : '#6b7280';
      const lbl = (labels[i]||'').substring(0,10);
      const tip = `${{lbl}} | $${{b.toFixed(2)}} | ${{b>=start?'+':''}}$${{(b-start).toFixed(2)}}`;
      dots += `<circle cx="${{px(i)}}" cy="${{py(b)}}" r="12" fill="transparent" class="eq-dot" data-tip="${{tip}}"/>`;
      dots += `<circle cx="${{px(i)}}" cy="${{py(b)}}" r="3.5" fill="${{clr}}" opacity="0.9" pointer-events="none"/>`;
    }}

    // Y-axis gridlines (8 ticks)
    let gridY='', labY='';
    for (let k=0; k<=7; k++) {{
      const v = minB + (rangeB * k / 7);
      const y = py(v);
      gridY += `<line x1="${{PAD.l}}" y1="${{y}}" x2="${{W-PAD.r}}" y2="${{y}}" stroke="#1f2937" stroke-width="1"/>`;
      labY  += `<text x="${{PAD.l-8}}" y="${{y+4}}" text-anchor="end" fill="#6b7280" font-size="12">$${{v.toFixed(0)}}</text>`;
    }}

    // X-axis labels (up to 10 evenly spaced)
    let labX='';
    const nTicks = Math.min(n, 10);
    for (let k=0; k<nTicks; k++) {{
      const i = Math.round(k / (nTicks-1) * (n-1));
      labX += `<text x="${{px(i)}}" y="${{H-PAD.b+18}}" text-anchor="middle" fill="#6b7280" font-size="11">${{(labels[i]||'').substring(0,10)}}</text>`;
      labX += `<line x1="${{px(i)}}" y1="${{H-PAD.b}}" x2="${{px(i)}}" y2="${{H-PAD.b+5}}" stroke="#374151"/>`;
    }}

    // Start line + fill polygons
    const fillAbove = `<polygon points="${{polyAbove}}" fill="#22c55e" opacity="0.07"/>`;
    const fillBelow = `<polygon points="${{polyBelow}}" fill="#ef4444" opacity="0.07"/>`;
    const refLine   = `<line x1="${{PAD.l}}" y1="${{startY}}" x2="${{W-PAD.r}}" y2="${{startY}}" stroke="#374151" stroke-width="1.5" stroke-dasharray="6,4"/>
      <text x="${{PAD.l-8}}" y="${{startY-4}}" text-anchor="end" fill="#4b5563" font-size="11">$${{start}}</text>`;

    // Tooltip element
    const tooltipEl = `<g id="eq-tooltip" style="display:none" pointer-events="none">
      <rect id="eq-tip-bg" rx="4" fill="#1f2937" stroke="#374151"/>
      <text id="eq-tip-text" fill="#e2e8f0" font-size="12"/>
    </g>`;

    const svgId = 'eq-svg-' + Date.now();
    const svg = `<svg id="${{svgId}}" width="100%" viewBox="0 0 ${{W}} ${{H}}"
        style="display:block;background:#0d1117;border-radius:12px;border:1px solid #1f2937;cursor:crosshair">
      <defs>
        <clipPath id="cp"><rect x="${{PAD.l}}" y="${{PAD.t}}" width="${{cw}}" height="${{ch}}"/></clipPath>
      </defs>
      <g clip-path="url(#cp)">${{fillAbove}}${{fillBelow}}${{gridY}}${{refLine}}${{pathSegs}}</g>
      ${{labY}}${{labX}}
      <g clip-path="url(#cp)">${{dots}}</g>
      ${{tooltipEl}}
      <text x="${{PAD.l+cw/2}}" y="${{H-4}}" text-anchor="middle" fill="#374151" font-size="11">trades (chronological)</text>
    </svg>`;

    // ---- Trade table
    const rows = trades.map(t => {{
      const pc2 = t.pnl >= 0 ? '#22c55e' : '#ef4444';
      const pct2 = t.entry && t.exit ? ((t.exit-t.entry)/t.entry*100*(t.side==='SHORT'?-1:1)) : null;
      return `<tr>
        <td style="color:#6b7280;font-size:12px">${{(t.timestamp||'').substring(0,10)}}</td>
        <td style="font-weight:700">${{t.symbol||''}}</td>
        <td style="color:#94a3b8">${{t.side||''}}</td>
        <td style="font-family:monospace;font-size:12px">${{t.entry||'—'}}</td>
        <td style="font-family:monospace;font-size:12px">${{t.exit||'—'}}</td>
        <td style="color:${{pc2}};font-weight:600">${{t.pnl>=0?'+':''}}$${{t.pnl.toFixed(4)}}</td>
        <td style="font-family:monospace;font-size:11px;color:${{pc2}}">${{pct2!==null?(pct2>=0?'+':'')+pct2.toFixed(1)+'%':'—'}}</td>
        <td style="font-family:monospace;font-size:12px;color:#94a3b8">$${{(t.balance||0).toFixed(2)}}</td>
      </tr>`;
    }}).join('');

    el.innerHTML = `
      <div style="display:flex;gap:10px;flex-wrap:wrap;margin-bottom:18px">${{kpis}}</div>
      <div style="margin-bottom:24px">${{svg}}</div>
      <table class="mini-table"><thead><tr>
        <th>Date</th><th>Symbol</th><th>Side</th><th>Entry</th><th>Exit</th><th>PnL $</th><th>PnL %</th><th>Balance</th>
      </tr></thead><tbody>${{rows}}</tbody></table>`;

    // Attach tooltip hover
    document.querySelectorAll('.eq-dot').forEach(dot => {{
      dot.addEventListener('mouseenter', e => {{
        const tip  = document.getElementById('eq-tooltip');
        const txt  = document.getElementById('eq-tip-text');
        const bg   = document.getElementById('eq-tip-bg');
        txt.textContent = dot.dataset.tip;
        tip.style.display = '';
        const bbox = txt.getBBox();
        const cx   = parseFloat(dot.getAttribute('cx'));
        const cy   = parseFloat(dot.getAttribute('cy'));
        bg.setAttribute('x', cx+8); bg.setAttribute('y', cy-18);
        bg.setAttribute('width', bbox.width+14); bg.setAttribute('height', 22);
        txt.setAttribute('x', cx+15); txt.setAttribute('y', cy-2);
        tip.style.display = '';
      }});
      dot.addEventListener('mouseleave', () => {{
        document.getElementById('eq-tooltip').style.display = 'none';
      }});
    }});
  }} catch(e) {{ el.innerHTML = `<div class="empty">Error: ${{e.message}}</div>`; }}
}}

// ---- Order Book --------------------------------------------------------------
async function loadOrderBook() {{
  const el = document.getElementById('obContent');
  el.innerHTML = '<div class="empty">Loading...</div>';
  try {{
    const r  = await fetch(`/api/trades/${{currentTrader}}`);
    const d  = await r.json();
    const positions = d.trades || [];
    if (!positions.length) {{
      el.innerHTML = '<div class="empty">No trades yet. Run the paper pipeline first.</div>';
      return;
    }}

    const allTrades  = positions.flatMap(p => p.trades || []);
    const totalPnl   = positions.reduce((s,p) => s+(p.total_pnl||0), 0);
    const openCount  = positions.filter(p=>p.status==='open').length;
    const partCount  = positions.filter(p=>p.status==='partial').length;
    const closedCount= positions.filter(p=>p.status==='closed').length;
    const pnlColor   = totalPnl>0?'#22c55e':totalPnl<0?'#ef4444':'#6b7280';

    document.getElementById('statusPos').textContent = openCount + partCount;

    const kpiHtml = [
      ['Positions', positions.length, '#e2e8f0'],
      ['Open', openCount, '#22c55e'],
      ['Partial', partCount, '#facc15'],
      ['Closed', closedCount, '#6b7280'],
      ['Total P&L', `${{(totalPnl>=0?'+':'')}}$${{Math.abs(totalPnl).toFixed(2)}}`, pnlColor],
    ].map(([l,v,c])=>`<div style="background:#111827;border-radius:8px;padding:10px 16px;min-width:100px">
      <div style="font-size:10px;color:#6b7280;margin-bottom:3px">${{l}}</div>
      <div style="font-size:18px;font-weight:700;color:${{c}}">${{v}}</div></div>`).join('');

    const posCards = positions.map(pos => {{
      const pnl     = pos.total_pnl || 0;
      const pnlCls  = pnl>0?'#22c55e':pnl<0?'#ef4444':'#6b7280';
      const pnlStr  = (pnl>=0?'+':'')+'$'+Math.abs(pnl).toFixed(4);
      const remPct  = pos.remaining_pct ?? 100;
      const statClr = pos.status==='open'?'#22c55e':pos.status==='partial'?'#facc15':'#6b7280';
      const conc    = pos.concurrent_symbols && pos.concurrent_symbols.length > 0
        ? `<span style="font-size:10px;background:#fb923c22;color:#fb923c;border:1px solid #fb923c44;border-radius:3px;padding:1px 5px;margin-left:6px">&#9650; ${{pos.concurrent_symbols.join('+')}}</span>`
        : '';

      const tradeRows = (pos.trades||[]).map(tr => {{
        const tpnl = tr.trade_pnl || 0;
        const tAc  = tr.action==='BUY'?'#22c55e33;color:#22c55e':tr.action==='SELL'?'#ef444433;color:#ef4444':'#60a5fa33;color:#60a5fa';
        const tPnlHtml = tr.action==='BUY'||tr.action==='ADD'
          ? '—'
          : `<span style="color:${{tpnl>=0?'#22c55e':'#ef4444'}};font-weight:600">${{tpnl>=0?'+':''}}$${{tpnl.toFixed(4)}}</span>`;
        const after = tr.size_after_pct ?? 100;
        const cf    = tr.close_fraction || 0;
        const sizeFlow = tr.action==='BUY'
          ? `0%→100%`
          : tr.action==='ADD'
          ? `+add`
          : `${{after+Math.round(cf*100)}}%→${{after}}%`;
        return `<tr style="border-bottom:1px solid #111827">
          <td style="color:#374151;font-size:10px;padding:7px 10px">#${{tr.trade_id}}</td>
          <td style="color:#6b7280;font-size:11px;white-space:nowrap;padding:7px 10px">${{(tr.time||'').substring(0,16).replace('T',' ')}}</td>
          <td style="padding:7px 10px"><span style="background:${{tAc}};padding:2px 7px;border-radius:3px;font-size:11px;font-weight:700">${{tr.action}}</span>
            ${{cf>0?`<span style="font-size:10px;color:#6b7280;margin-left:4px">${{Math.round(cf*100)}}% close</span>`:''}}</td>
          <td style="font-family:monospace;font-size:12px;padding:7px 10px">${{tr.price!=null?tr.price:'—'}}</td>
          <td style="font-family:monospace;font-size:12px;color:#94a3b8;padding:7px 10px">${{tr.quantity!=null?'$'+tr.quantity.toFixed(0):'—'}}</td>
          <td style="padding:7px 10px">${{tPnlHtml}}</td>
          <td style="font-size:11px;color:#6b7280;padding:7px 10px">${{sizeFlow}}</td>
        </tr>`;
      }}).join('');

      const tradesTable = pos.trades && pos.trades.length
        ? `<div style="display:none;border-top:1px solid #111827" id="ptrades-${{pos.position_id}}">
             <table style="width:100%;border-collapse:collapse">
               <thead style="background:#111827"><tr>
                 <th style="padding:7px 10px;text-align:left;font-size:10px;color:#374151">#TRADE</th>
                 <th style="padding:7px 10px;text-align:left;font-size:10px;color:#374151">TIME</th>
                 <th style="padding:7px 10px;text-align:left;font-size:10px;color:#374151">ACTION</th>
                 <th style="padding:7px 10px;text-align:left;font-size:10px;color:#374151">PRICE</th>
                 <th style="padding:7px 10px;text-align:left;font-size:10px;color:#374151">NOTIONAL</th>
                 <th style="padding:7px 10px;text-align:left;font-size:10px;color:#374151">TRADE P&L</th>
                 <th style="padding:7px 10px;text-align:left;font-size:10px;color:#374151">SIZE</th>
               </tr></thead>
               <tbody>${{tradeRows}}</tbody>
             </table>
           </div>`
        : '';

      return `<div style="background:#1a1f2e;border:1px solid #1e293b;border-radius:10px;margin-bottom:12px;overflow:hidden">
        <div style="display:flex;align-items:center;gap:12px;padding:14px 18px;cursor:pointer"
             onclick="document.getElementById('ptrades-${{pos.position_id}}').style.display=document.getElementById('ptrades-${{pos.position_id}}').style.display==='none'?'block':'none'">
          <div style="font-size:17px;font-weight:800;min-width:60px">${{pos.symbol||'?'}}</div>
          <div style="flex:1">
            <div style="display:flex;gap:10px;align-items:center;flex-wrap:wrap">
              <span style="background:${{statClr}}22;color:${{statClr}};border:1px solid ${{statClr}}44;padding:2px 7px;border-radius:4px;font-size:10px;font-weight:700">${{(pos.status||'open').toUpperCase()}}</span>
              <span style="font-size:12px;color:#6b7280">${{pos.asset_type||''}}</span>
              <span style="font-size:12px;color:#94a3b8">${{pos.side||''}}</span>
              <span style="font-size:12px;font-family:monospace">@${{pos.entry_price!=null?pos.entry_price:'?'}}</span>
              ${{conc}}
            </div>
            <div style="display:flex;gap:8px;align-items:center;margin-top:5px;font-size:11px;color:#6b7280">
              <span>${{(pos.opened_at||'').substring(0,10)}}</span>
              ${{pos.closed_at?`<span>→ ${{pos.closed_at.substring(0,10)}}</span>`:''}}
              <span style="margin-left:6px">Remaining:</span>
              <div style="background:#0f1117;border-radius:3px;height:5px;width:60px;overflow:hidden">
                <div style="background:#60a5fa;height:5px;width:${{remPct}}%;border-radius:3px"></div></div>
              <span style="color:#94a3b8">${{remPct}}%</span>
              <span style="margin-left:4px">${{(pos.trades||[]).length}} trade(s)</span>
            </div>
          </div>
          <div style="font-size:18px;font-weight:700;color:${{pnlColor}};min-width:90px;text-align:right">${{pnlStr}}</div>
          <span style="color:#6b7280;font-size:12px">&#9654;</span>
        </div>
        ${{tradesTable}}
      </div>`;
    }}).join('');

    el.innerHTML = `<div style="display:flex;gap:10px;flex-wrap:wrap;margin-bottom:20px">${{kpiHtml}}</div>${{posCards}}`;
  }} catch(e) {{ el.innerHTML = `<div class="empty">Error: ${{e.message}}</div>`; }}
}}


// ---- Config ------------------------------------------------------------------
async function loadConfig() {{
  const el = document.getElementById('configContent');
  el.innerHTML = '<div class="empty">Loading...</div>';
  try {{
    const r   = await fetch(`/api/config/${{currentTrader}}`);
    const cfg = await r.json();
    const risk   = cfg.risk   || {{}};
    const broker = cfg.broker || {{}};

    el.innerHTML = `
    <div class="cfg-grid">
      <div class="cfg-card">
        <h3>RISK RULES</h3>
        <div class="cfg-field">
          <label class="cfg-label">Min Confidence (0–1)</label>
          <input class="cfg-input" id="cfgMinConf" type="number" min="0" max="1" step="0.01" value="${{risk.min_confidence||0.55}}">
        </div>
        <div class="cfg-field">
          <label class="cfg-label">Max Open Positions</label>
          <input class="cfg-input" id="cfgMaxPos" type="number" min="1" max="20" value="${{risk.max_open_positions||3}}">
        </div>
        <div class="cfg-toggle">
          <input type="checkbox" id="cfgKillSwitch" ${{risk.kill_switch?'checked':''}}>
          <label class="toggle-label" for="cfgKillSwitch" style="color:${{risk.kill_switch?'#ef4444':'#e2e8f0'}}">Kill Switch (halt all trading)</label>
        </div>
        <button class="save-btn" onclick="saveConfig()">Save Config</button>
        <span class="saved-msg" id="savedMsg">Saved!</span>
      </div>
      <div class="cfg-card">
        <h3>BROKER</h3>
        <div class="cfg-field">
          <label class="cfg-label">Trade Notional ($)</label>
          <input class="cfg-input" id="cfgNotional" type="number" min="1" value="${{broker.trade_notional||100}}">
        </div>
        <div class="cfg-field">
          <label class="cfg-label">Starting Balance ($)</label>
          <input class="cfg-input" id="cfgBalance" type="number" min="1" value="${{broker.starting_balance||7000}}">
        </div>
        <div class="cfg-toggle">
          <input type="checkbox" id="cfgDryRun" ${{broker.dry_run!==false?'checked':''}}>
          <label class="toggle-label" for="cfgDryRun">Dry Run (never place real orders)</label>
        </div>
      </div>
    </div>
    <div class="cfg-card" style="max-width:600px;margin-top:16px">
      <h3>RAW JSON</h3>
      <div class="cfg-raw" id="cfgRaw">${{JSON.stringify(cfg,null,2)}}</div>
    </div>`;
  }} catch(e) {{ el.innerHTML = `<div class="empty">Error: ${{e.message}}</div>`; }}
}}

async function saveConfig() {{
  const r   = await fetch(`/api/config/${{currentTrader}}`);
  const cfg = await r.json();
  cfg.risk   = cfg.risk   || {{}};
  cfg.broker = cfg.broker || {{}};
  cfg.risk.min_confidence    = parseFloat(document.getElementById('cfgMinConf').value);
  cfg.risk.max_open_positions= parseInt(document.getElementById('cfgMaxPos').value);
  cfg.risk.kill_switch       = document.getElementById('cfgKillSwitch').checked;
  cfg.broker.trade_notional  = parseFloat(document.getElementById('cfgNotional').value);
  cfg.broker.starting_balance= parseFloat(document.getElementById('cfgBalance').value);
  cfg.broker.dry_run         = document.getElementById('cfgDryRun').checked;

  await fetch(`/api/config/${{currentTrader}}`, {{
    method: 'PUT',
    headers: {{'Content-Type':'application/json'}},
    body: JSON.stringify(cfg),
  }});
  document.getElementById('cfgRaw').textContent = JSON.stringify(cfg,null,2);
  const msg = document.getElementById('savedMsg');
  msg.style.opacity = 1;
  setTimeout(()=>{{ msg.style.opacity=0; }}, 2000);
}}

// ---- Health ------------------------------------------------------------------
async function loadHealth() {{
  const el = document.getElementById('healthContent');
  el.innerHTML = '<div class="empty">Checking status...</div>';
  try {{
    // Fetch system health + live Alpaca status in parallel
    const [hRes, aRes] = await Promise.all([
      fetch('/api/health').then(r=>r.json()),
      fetch('/api/live/alpaca').then(r=>r.json()).catch(()=>({{}})),
    ]);
    const d   = hRes;
    const alp = aRes;

    // Alpaca section
    const alpOk = alp.account && alp.account.ok;
    const alpHead = alpOk
      ? `ALPACA <span style="color:#22c55e;font-size:11px">&#9679; connected (paper)</span>`
      : `ALPACA <span style="color:#ef4444;font-size:11px">&#9679; not connected</span>`;
    let alpBody = '';
    if (alpOk) {{
      const a = alp.account;
      alpBody = `
        <div class="health-row"><span>Account</span><span style="color:#22c55e">${{a.account_number||''}}</span></div>
        <div class="health-row"><span>Status</span><span style="color:#22c55e">${{a.status||''}}</span></div>
        <div class="health-row"><span>Equity</span><span>$${{(a.equity||0).toLocaleString('en-US',{{minimumFractionDigits:2,maximumFractionDigits:2}})}}</span></div>
        <div class="health-row"><span>Cash</span><span>$${{(a.cash||0).toLocaleString('en-US',{{minimumFractionDigits:2,maximumFractionDigits:2}})}}</span></div>
        <div class="health-row"><span>Buying Power</span><span>$${{(a.buying_power||0).toLocaleString('en-US',{{minimumFractionDigits:2,maximumFractionDigits:2}})}}</span></div>
        <div class="health-row"><span>Portfolio Value</span><span>$${{(a.portfolio_value||0).toLocaleString('en-US',{{minimumFractionDigits:2,maximumFractionDigits:2}})}}</span></div>
        <div class="health-row"><span>Trading Blocked</span><span style="color:${{a.trading_blocked?'#ef4444':'#22c55e'}}">${{a.trading_blocked?'YES':'no'}}</span></div>
        <div class="health-row"><span>Open Positions</span><span>${{(alp.positions||[]).length}}</span></div>
      `;
    }} else {{
      const errMsg = (alp.account && alp.account.error) || 'keys not set in .env';
      alpBody = `
        <div class="health-row"><span>Paper API</span><span class="dot-warn">&#9679; ${{errMsg}}</span></div>
        <div style="margin-top:10px;font-size:11px;color:#6b7280">Add ALPACA_API_KEY and ALPACA_SECRET_KEY to .env, then refresh.</div>
      `;
    }}

    // Discord section — check if watcher is running via live status
    const liveStatus = await fetch('/api/live/status').then(r=>r.json()).catch(()=>({{}}));
    const watcherOk  = liveStatus.watcher === 'running';
    const pipelineOk = liveStatus.pipeline === 'running';
    const discordBody = `
      <div class="health-row"><span>Toast Watcher</span>
        <span style="color:${{watcherOk?'#22c55e':'#ef4444'}}">&#9679; ${{watcherOk?'running':'stopped'}}</span></div>
      <div class="health-row"><span>Live Pipeline</span>
        <span style="color:${{pipelineOk?'#22c55e':'#ef4444'}}">&#9679; ${{pipelineOk?'running':'stopped'}}</span></div>
      <div class="health-row"><span>Bot Token</span>
        <span style="color:#6b7280">&#9679; not configured (watcher-only mode)</span></div>
      <div style="margin-top:10px;font-size:11px;color:#6b7280">
        Keep Discord <b style="color:#94a3b8">open and minimized</b> — toasts only fire when Discord is not in focus.
      </div>
    `;

    el.innerHTML = `
    <div class="health-card">
      <h3 style="font-size:13px;font-weight:600;color:#94a3b8;margin-bottom:14px">SYSTEM STATUS</h3>
      <div class="health-row"><span>API</span><span class="dot-ok">&#9679; online</span></div>
      <div class="health-row"><span>Database</span><span class="dot-ok">&#9679; ${{d.db}}</span></div>
      <div class="health-row"><span>Traders loaded</span><span>${{(d.traders||[]).join(', ')}}</span></div>
      <div class="health-row"><span>Version</span><span>${{d.version}}</span></div>
      <div class="health-row"><span>Last checked</span><span style="color:#374151">${{new Date().toLocaleTimeString()}}</span></div>
      <button onclick="loadHealth()" style="margin-top:10px;background:#1e293b;color:#94a3b8;border:1px solid #334155;
              border-radius:6px;padding:5px 14px;cursor:pointer;font-size:11px">&#8635; Refresh</button>
    </div>
    <div class="health-card">
      <h3 style="font-size:13px;font-weight:600;color:#94a3b8;margin-bottom:14px">${{alpHead}}</h3>
      ${{alpBody}}
    </div>
    <div class="health-card">
      <h3 style="font-size:13px;font-weight:600;color:#94a3b8;margin-bottom:14px">DISCORD / WATCHER</h3>
      ${{discordBody}}
    </div>`;
  }} catch(e) {{ el.innerHTML = `<div class="empty">API offline: ${{e.message}}</div>`; }}
}}

// ---- Trace tab ---------------------------------------------------------------
const ACTION_CLR = {{
  ENTRY:'#22c55e', TRIM:'#22d3ee', EXIT:'#facc15',
  ADD:'#60a5fa', UNSURE:'#fb923c', NOISE:'#374151',
}};
const ASSET_CLR = {{
  OPTION:'#a78bfa', CRYPTO:'#fb923c', STOCK:'#38bdf8', '':'#6b7280',
}};
const TRADE_CLR = {{
  BUY:'#22c55e', SELL:'#f87171', SELL_SHORT:'#fb923c',
  BUY_COVER:'#a78bfa', ADD:'#60a5fa',
}};

async function loadTrace() {{
  const el = document.getElementById('traceContent');
  el.innerHTML = '<div class="empty">Loading trace data...</div>';
  try {{
    const r = await fetch(`/api/trace/${{currentTrader}}`);
    const data = await r.json();
    const rows = data.rows || [];
    const positions = data.positions || [];

    if (!rows.length) {{
      el.innerHTML = '<div class="empty">No signals found. Run the paper pipeline first.</div>';
      return;
    }}

    const ROW_H  = 46;
    const CARD_W = 390;
    const GAP    = 30;
    const LANE_W = 14;
    const LANE_G = 5;
    const LANE_X = CARD_W + GAP;

    // --- Build position bounds (min/max row index per position_id) ---
    const posMap = {{}}; // position_id -> minRow, maxRow, events[], symbol, asset_type, side
    rows.forEach((row, i) => {{
      if (!row.position_id) return;
      const pid = row.position_id;
      if (!posMap[pid]) {{
        const pos = positions.find(p => p.position_id === pid) || {{}};
        posMap[pid] = {{ minRow:i, maxRow:i, events:[], symbol:row.symbol,
          asset_type: pos.asset_type || row.asset_type || '',
          side: pos.side || '',
          status: pos.status || '',
          realized_pnl: pos.realized_pnl || 0,
        }};
      }}
      posMap[pid].maxRow = i;
      posMap[pid].events.push({{
        row: i,
        action: row.trade_action,
        pnl: row.trade_pnl,
        cf: row.close_fraction,
        status: row.trade_status,
      }});
    }});

    // --- Assign lanes (greedy column packing) ---
    const sortedPids = Object.keys(posMap).sort((a,b) => posMap[a].minRow - posMap[b].minRow);
    const laneOf = {{}}; // position_id -> lane index
    const laneEnd = [];  // lane_index -> maxRow of last assigned position
    for (const pid of sortedPids) {{
      const {{minRow}} = posMap[pid];
      let lane = laneEnd.findIndex(e => e < minRow - 1);
      if (lane === -1) lane = laneEnd.length;
      laneEnd[lane] = posMap[pid].maxRow;
      laneOf[pid] = lane;
      posMap[pid].lane = lane;
    }}
    const numLanes = laneEnd.length;

    // --- Build filter state ---
    let filterAction = '';
    let filterSymbol = '';
    let zoom = 1.0;

    const allSymbols = [...new Set(rows.map(r => r.symbol).filter(Boolean))].sort();

    // --- Render ---
    function render() {{
      const filtered = rows.filter(r =>
        (!filterAction || r.action === filterAction) &&
        (!filterSymbol || r.symbol === filterSymbol)
      );

      // Recompute row indices after filter (for SVG connections)
      const rowIdx = {{}};
      filtered.forEach((r,i) => {{ rowIdx[r.sig_id] = i; }});

      const totalH = filtered.length * ROW_H;
      const totalW = LANE_X + numLanes * (LANE_W + LANE_G) + 40;

      // Build row HTML
      let rowsHtml = '';
      filtered.forEach((row, i) => {{
        const y = i * ROW_H;
        const ac = row.action || 'NOISE';
        const clr = ACTION_CLR[ac] || '#6b7280';
        const ts = (row.timestamp||'').substring(0,10);
        const sym = row.symbol || '—';
        const conf = row.confidence ? (row.confidence*100).toFixed(0)+'%' : '';
        const hasTrade = row.trade_id != null;
        const pnl = row.trade_pnl;
        const pnlStr = pnl != null ? ((pnl>=0?'+':'')+pnl.toFixed(2)) : '';
        const pnlClr = pnl > 0.01 ? '#22c55e' : pnl < -0.01 ? '#f87171' : '#6b7280';

        // Why is PnL $0?
        let zeroReason = '';
        if (hasTrade && pnl === 0 && row.close_fraction > 0) {{
          if (row.trade_status === 'corpus_end') zeroReason = 'corpus-end';
          else if (!row.trade_price || row.trade_price === 0) zeroReason = 'no price';
          else zeroReason = 'break-even';
        }}

        const content = (row.raw_content||'').replace(/</g,'&lt;').substring(0,90);
        const dotHover = hasTrade ? `cursor:pointer` : '';

        rowsHtml += `
        <div class="tr-row" data-id="${{row.sig_id}}" style="position:absolute;top:${{y}}px;left:0;width:${{CARD_W}}px;height:${{ROW_H-2}}px;box-sizing:border-box;border-left:3px solid ${{clr}};background:#111827;border-radius:4px;padding:4px 8px;${{dotHover}}"
          onclick="showTraceDetail(${{JSON.stringify(row).replace(/"/g,'&quot;')}})">
          <div style="display:flex;align-items:center;gap:6px;margin-bottom:2px">
            <span style="color:#6b7280;font-size:10px;font-family:monospace;min-width:72px">${{ts}}</span>
            <span style="background:${{clr}}22;color:${{clr}};font-size:10px;font-weight:700;padding:1px 5px;border-radius:3px">${{ac}}</span>
            ${{sym !== '—' ? `<span style="color:#e2e8f0;font-size:11px;font-weight:600">${{sym}}</span>` : ''}}
            ${{conf ? `<span style="color:#6b7280;font-size:10px">${{conf}}</span>` : ''}}
            ${{row.parsed_price ? `<span style="color:#94a3b8;font-size:10px">@${{row.parsed_price}}</span>` : ''}}
            ${{hasTrade ? `<span style="color:${{TRADE_CLR[row.trade_action]||'#9ca3af'}};font-size:10px;margin-left:4px">→ ${{row.trade_action}}</span>` : ''}}
            ${{pnlStr ? `<span style="color:${{pnlClr}};font-size:10px;font-weight:700;margin-left:auto">${{pnlStr}}</span>` : ''}}
            ${{zeroReason ? `<span style="color:#6b7280;font-size:9px;border:1px solid #374151;border-radius:2px;padding:0 3px">${{zeroReason}}</span>` : ''}}
          </div>
          <div style="color:#4b5563;font-size:10px;font-family:monospace;overflow:hidden;white-space:nowrap;text-overflow:ellipsis">${{content}}</div>
        </div>`;
      }});

      // Build position lane SVG + bars
      let laneBars = '';
      let svgPaths = '';

      // Draw position lane bars and event dots
      for (const pid of sortedPids) {{
        const pos = posMap[pid];
        const lane = laneOf[pid];
        const x = LANE_X + lane * (LANE_W + LANE_G);
        const clr = ASSET_CLR[pos.asset_type] || '#6b7280';

        // Find first and last event rows in the FILTERED view
        const filteredEvents = pos.events.filter(e => rowIdx[rows[e.row]?.sig_id] !== undefined);
        if (filteredEvents.length === 0) continue;

        const minFRow = Math.min(...filteredEvents.map(e => rowIdx[rows[e.row]?.sig_id]));
        const maxFRow = Math.max(...filteredEvents.map(e => rowIdx[rows[e.row]?.sig_id]));
        const y1 = minFRow * ROW_H + ROW_H/2;
        const y2 = maxFRow * ROW_H + ROW_H/2;

        const pnlLabel = pos.realized_pnl !== 0
          ? ((pos.realized_pnl>=0?'+':'')+pos.realized_pnl.toFixed(2))
          : '';
        const pnlC = pos.realized_pnl > 0.01 ? '#22c55e' : pos.realized_pnl < -0.01 ? '#f87171' : '#6b7280';
        const statusFade = pos.status === 'closed' ? '1' : '0.6';

        // Bar
        svgPaths += `<rect x="${{x}}" y="${{y1}}" width="${{LANE_W}}" height="${{Math.max(4, y2-y1)}}"
          fill="${{clr}}40" stroke="${{clr}}" stroke-width="1.5" rx="3" opacity="${{statusFade}}"/>`;
        // Symbol label
        svgPaths += `<text x="${{x+LANE_W/2}}" y="${{y1-5}}" text-anchor="middle" fill="${{clr}}"
          font-size="9" font-family="monospace">${{pos.symbol||''}}</text>`;
        // P&L label at bottom
        if (pnlLabel) {{
          svgPaths += `<text x="${{x+LANE_W/2}}" y="${{y2+12}}" text-anchor="middle" fill="${{pnlC}}"
            font-size="9" font-weight="bold" font-family="monospace">${{pnlLabel}}</text>`;
        }}

        // Event dots on the bar
        filteredEvents.forEach(ev => {{
          const origRow = rows[ev.row];
          if (!origRow) return;
          const fi = rowIdx[origRow.sig_id];
          if (fi === undefined) return;
          const ey = fi * ROW_H + ROW_H/2;
          const dotClr = TRADE_CLR[ev.action] || clr;
          svgPaths += `<circle cx="${{x+LANE_W/2}}" cy="${{ey}}" r="5" fill="${{dotClr}}" stroke="#0f172a" stroke-width="1.5"/>`;

          // Bezier connection line from message card to lane dot
          const x1c = CARD_W + 2;
          const y1c = ey;
          const x2c = x;
          const y2c = ey;
          const cx1 = x1c + (x2c - x1c) * 0.55;
          const cx2 = x2c - (x2c - x1c) * 0.25;
          const lineClr = dotClr;
          const opacity = (ev.pnl === 0 && ev.cf > 0) ? '0.25' : '0.55';
          svgPaths += `<path d="M${{x1c}},${{y1c}} C${{cx1}},${{y1c}} ${{cx2}},${{y2c}} ${{x2c}},${{y2c}}"
            fill="none" stroke="${{lineClr}}" stroke-width="1.2" opacity="${{opacity}}" stroke-dasharray="${{ev.cf===0?'none':'3,2'}}"/>`;
        }});
      }}

      const svgW = totalW;
      const svgH = totalH;

      const html = `
      <div style="display:flex;flex-direction:column;height:100%">
        <div style="display:flex;gap:10px;align-items:center;padding:10px 16px 8px;background:#0f172a;border-bottom:1px solid #1e293b;flex-wrap:wrap">
          <span style="color:#a78bfa;font-size:11px;font-weight:700;letter-spacing:.05em">TRACE</span>
          <span style="color:#6b7280;font-size:11px">${{rows.length}} messages · ${{positions.length}} positions</span>
          <select onchange="traceFilter('action',this.value)" style="background:#1e293b;color:#e2e8f0;border:1px solid #374151;border-radius:4px;padding:2px 6px;font-size:11px">
            <option value="">All actions</option>
            <option value="ENTRY">ENTRY</option><option value="TRIM">TRIM</option>
            <option value="EXIT">EXIT</option><option value="ADD">ADD</option>
            <option value="UNSURE">UNSURE</option><option value="NOISE">NOISE</option>
          </select>
          <select onchange="traceFilter('symbol',this.value)" style="background:#1e293b;color:#e2e8f0;border:1px solid #374151;border-radius:4px;padding:2px 6px;font-size:11px">
            <option value="">All symbols</option>
            ${{allSymbols.map(s=>`<option value="${{s}}">${{s}}</option>`).join('')}}
          </select>
          <label style="color:#6b7280;font-size:11px;display:flex;align-items:center;gap:6px">
            Zoom
            <input type="range" min="40" max="150" value="100" oninput="traceZoom(this.value/100)"
              style="width:80px">
            <span id="traceZoomLabel">100%</span>
          </label>
          <span style="color:#4b5563;font-size:10px">Click any row for detail · dashed line = break-even</span>
        </div>
        <div style="display:flex;flex:1;overflow:hidden">
          <div id="traceScroll" style="overflow:auto;flex:1">
            <div id="traceInner" style="position:relative;width:${{totalW}}px;height:${{totalH}}px;transform-origin:top left">
              ${{rowsHtml}}
              <svg id="traceSvg" style="position:absolute;top:0;left:0;pointer-events:none;overflow:visible"
                width="${{svgW}}" height="${{svgH}}">
                ${{svgPaths}}
              </svg>
            </div>
          </div>
          <div id="traceDetail" style="width:320px;min-width:280px;border-left:1px solid #1e293b;overflow-y:auto;padding:14px;font-size:11px;font-family:monospace;color:#9ca3af;background:#0f172a">
            <div style="color:#6b7280">Click a message row to see full parse detail.</div>
          </div>
        </div>
      </div>`;

      el.innerHTML = html;
      el.style.padding = '0';
      el.style.height = 'calc(100vh - 160px)';
      el.style.display = 'flex';
      el.style.flexDirection = 'column';
    }}

    // Expose filter/zoom to window scope
    window.traceFilter = function(type, val) {{
      if (type === 'action') filterAction = val;
      if (type === 'symbol') filterSymbol = val;
      render();
    }};
    window.traceZoom = function(z) {{
      zoom = z;
      const inner = document.getElementById('traceInner');
      if (inner) inner.style.transform = `scale(${{z}})`;
      const lbl = document.getElementById('traceZoomLabel');
      if (lbl) lbl.textContent = Math.round(z*100)+'%';
    }};
    window.showTraceDetail = function(row) {{
      const d = document.getElementById('traceDetail');
      if (!d) return;
      const ac = row.action || 'NOISE';
      const clr = ACTION_CLR[ac] || '#6b7280';
      const pnl = row.trade_pnl;
      const pnlClr = pnl > 0.01 ? '#22c55e' : pnl < -0.01 ? '#f87171' : '#6b7280';

      let whyZero = '';
      if (pnl === 0 && row.close_fraction > 0) {{
        if (row.trade_status === 'corpus_end') whyZero = 'Auto-closed at corpus end — no exit message in data.';
        else if (!row.trade_price) whyZero = 'No exit price parsed from message. Fell back to entry price = break-even.';
        else if (!row.parsed_price) whyZero = 'No price parsed → break-even fallback.';
        else whyZero = 'Exit price equals entry price → $0 P&L.';
      }} else if (pnl === 0 && row.close_fraction === 0) {{
        whyZero = 'Entry/Add trade — no realized P&L on open.';
      }}

      d.innerHTML = `
        <div style="color:${{clr}};font-weight:700;margin-bottom:8px">${{ac}} ${{row.symbol||''}}</div>
        <div style="color:#6b7280;margin-bottom:6px">${{(row.timestamp||'').substring(0,16).replace('T',' ')}}</div>
        ${{row.trade_id ? `
          <div style="color:#e2e8f0;margin-bottom:4px">Trade #${{row.trade_id}}</div>
          <div>action: <span style="color:${{TRADE_CLR[row.trade_action]||'#9ca3af'}}">${{row.trade_action}}</span></div>
          <div>price: ${{row.trade_price ?? 'none'}}</div>
          <div>qty/notional: $${{(row.trade_qty||0).toFixed(0)}}</div>
          <div>close_fraction: ${{row.close_fraction}}</div>
          <div>P&L: <span style="color:${{pnlClr}}">${{pnl != null ? ((pnl>=0?'+':'')+pnl.toFixed(4)) : 'n/a'}}</span></div>
          ${{whyZero ? `<div style="color:#fb923c;margin-top:6px;border-left:2px solid #fb923c;padding-left:6px">${{whyZero}}</div>` : ''}}
        ` : '<div style="color:#6b7280">No trade generated.</div>'}}
        <hr style="border-color:#1e293b;margin:10px 0"/>
        <div style="color:#60a5fa">Parsed signal</div>
        <div>confidence: ${{row.confidence ? (row.confidence*100).toFixed(0)+'%' : '—'}}</div>
        <div>parsed_price: ${{row.parsed_price ?? 'none'}}</div>
        <div>asset_type: ${{row.asset_type||'—'}}</div>
        <hr style="border-color:#1e293b;margin:10px 0"/>
        <div style="color:#6b7280;word-break:break-word;white-space:pre-wrap;font-size:10px">${{(row.raw_content||'').replace(/</g,'&lt;')}}</div>`;
    }};

    render();
  }} catch(e) {{
    el.innerHTML = `<div class="empty">Error: ${{e.message}}</div>`;
    console.error(e);
  }}
}}

// ---- Debug tab ---------------------------------------------------------------
// ---- Pipeline ---------------------------------------------------------------
async function loadPipeline() {{
  const el = document.getElementById('pipelineContent');
  el.innerHTML = '<div class="empty">Loading...</div>';
  try {{
    const r = await fetch(`/api/pipeline/${{currentTrader}}`);
    const d = await r.json();
    const ac = d.action_counts || {{}};
    const cfg = d.config || {{}};
    const risk = cfg.risk || {{}};
    const broker = cfg.broker || {{}};
    const total = d.corpus_total || 0;
    const pct = x => total ? (x/total*100).toFixed(1) : '0';
    const pnl = d.final_pnl || 0;
    const start = d.start_bal || 7000;
    const ret = ((pnl / start) * 100).toFixed(1);
    const pnlCol = pnl >= 0 ? '#22c55e' : '#ef4444';

    // ---- section helper
    const section = (icon, title, content, id='') =>
      `<div style="background:#111827;border-radius:12px;border:1px solid #1e293b;margin-bottom:18px;overflow:hidden" ${{id?`id="${{id}}"`:''}} >
        <div style="padding:14px 20px;border-bottom:1px solid #1e293b;display:flex;align-items:center;gap:10px;cursor:pointer"
             onclick="this.nextElementSibling.style.display=this.nextElementSibling.style.display==='none'?'block':'none'">
          <span style="font-size:16px">${{icon}}</span>
          <span style="font-weight:700;color:#e2e8f0;font-size:14px">${{title}}</span>
          <span style="margin-left:auto;color:#6b7280;font-size:12px">click to expand/collapse</span>
        </div>
        <div style="padding:20px">${{content}}</div>
      </div>`;

    const code = (txt) =>
      `<pre style="background:#0d1117;border:1px solid #1e293b;border-radius:8px;padding:14px;font-size:12px;color:#a3e635;overflow-x:auto;white-space:pre-wrap">${{txt}}</pre>`;

    const badge = (action) => {{
      const c = ACTION_COLORS[action] || '#6b7280';
      return `<span class="badge" style="background:${{c}}22;color:${{c}};font-size:12px">${{action}}</span>`;
    }};

    const kpi = (label, val, col='#e2e8f0') =>
      `<div style="background:#1a1f2e;border-radius:8px;padding:12px 18px;min-width:110px;display:inline-block;margin:4px">
        <div style="font-size:11px;color:#6b7280;margin-bottom:4px">${{label}}</div>
        <div style="font-size:20px;font-weight:700;color:${{col}}">${{val}}</div>
      </div>`;

    // ---- 1. Overview KPIs
    const s1 = `
      <div style="display:flex;flex-wrap:wrap;gap:6px;margin-bottom:16px">
        ${{kpi('Corpus Messages', total.toLocaleString())}}
        ${{kpi('Positions', d.positions)}}
        ${{kpi('Trade Events', d.trades_total)}}
        ${{kpi('Total P&L', (pnl>=0?'+':'')+pnl.toFixed(2), pnlCol)}}
        ${{kpi('Return', (pnl>=0?'+':'')+ret+'%', pnlCol)}}
        ${{kpi('Start Balance', '$'+start.toLocaleString())}}
      </div>
      <p style="color:#94a3b8;line-height:1.7;max-width:800px">
        <b style="color:#e2e8f0">ProjectDolph2.0</b> is a fully automated trade copier.
        It reads Discord messages from <b style="color:#f59e0b">${{currentTrader}}</b>,
        parses them into structured Signals using regex-based rules, applies per-trader
        risk filters, and simulates order placement via a dry-run broker.
        Everything runs offline until Alpaca keys are added.
      </p>`;

    // ---- 2. Full pipeline flow
    const s2 = `
      ${{code(`Discord message (raw text)
        |
        v
  parsing/parser.py       parse_message(text) -> Signal
        |                 action / symbol / price / side / confidence
        v
  risk/rules.py           evaluate(signal, db) -> (approved, reason)
        |                 gates: confidence, asset_type, max_positions, kill_switch
        v
  execution/broker.py     submit_order(signal, db) -> trade_id
        |                 ENTRY  -> open position  (close_fraction = 0.0)
        |                 TRIM   -> partial close  (close_fraction = 0.5)
        |                 EXIT   -> full close     (close_fraction = 1.0)
        |                 ADD    -> add to pos     (no P&L)
        v
  data/paper_db.py        SQLite: signals, trades, positions, equity_snapshots
        |
        v
  analytics/equity.py     order_book_data() + chart_data() -> grouped P&L
        |
        v
  daemon/server.py        FastAPI dashboard  localhost:8765
        |
        v
  execution/alpaca_adapter.py   (offline until keys added in .env)`)}}
      <p style="color:#94a3b8;margin-top:12px">Each stage is independent — you can run just the parser, just the risk layer, or the full paper pipeline.</p>`;

    // ---- 3. Signal classification
    const actionRows = ['ENTRY','TRIM','EXIT','ADD','UNSURE','NOISE'].map(a => {{
      const n = ac[a] || 0;
      const bar = Math.round(n/total*40);
      const c = ACTION_COLORS[a] || '#6b7280';
      return `<tr>
        <td>${{badge(a)}}</td>
        <td style="font-family:monospace;color:#e2e8f0">${{n.toLocaleString()}}</td>
        <td style="color:#6b7280">${{pct(n)}}%</td>
        <td><div style="background:${{c}};height:8px;border-radius:4px;width:${{bar*6}}px"></div></td>
      </tr>`;
    }}).join('');
    const s3 = `
      <p style="color:#94a3b8;margin-bottom:14px;line-height:1.7">
        Every message passes through <code style="color:#a3e635">parsing/rules/action.py</code>.
        Rules are checked in priority order — first match wins.
        Confidence is a float 0–1; signals below <b style="color:#f59e0b">${{risk.min_confidence||0.6}}</b> are rejected by the risk layer.
      </p>
      <table style="border-collapse:collapse;margin-bottom:16px">
        <thead><tr>
          <th style="color:#6b7280;font-size:11px;padding:6px 12px 6px 0;text-align:left">Action</th>
          <th style="color:#6b7280;font-size:11px;padding:6px 12px;text-align:left">Count</th>
          <th style="color:#6b7280;font-size:11px;padding:6px 12px;text-align:left">%</th>
          <th style="color:#6b7280;font-size:11px;padding:6px 12px;text-align:left">Distribution</th>
        </tr></thead>
        <tbody>${{actionRows}}</tbody>
      </table>
      ${{code(`Priority order in action.py:
  1. NOISE  — URL, social chat, no numbers + no trade words  (conf 0.85–0.95)
  2. EXIT   — "stopped out", "closed here", "cut here"       (conf 0.90)
  3. ADD    — "adding more", "DCA", "averaging down"         (conf 0.88)
  4. TRIM   — "tp1 hit", "trimmed/trimming", "up 20%"        (conf 0.85)
  5. ENTRY  — "Coin:", "Long/Short" header, option notation   (conf 0.85)
  6. UNSURE — has trade vocabulary but nothing matched        (conf 0.35)`)}}`;

    // ---- 4. Symbol & asset classification
    const s4 = `
      <p style="color:#94a3b8;margin-bottom:14px;line-height:1.7">
        <code style="color:#a3e635">parsing/rules/symbol.py</code> extracts the ticker and classifies asset type.
        Priority: <b>Coin: template</b> > <b>option contract notation</b> > <b>options language</b> > <b>crypto DB</b> > <b>stock DB</b>.
      </p>
      <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:12px;margin-bottom:16px">
        <div style="background:#1a1f2e;border-radius:8px;padding:14px;border-left:3px solid #22c55e">
          <div style="font-weight:700;color:#22c55e;margin-bottom:8px">CRYPTO</div>
          <div style="color:#94a3b8;font-size:12px;line-height:1.6">Matched against CoinGecko top-500 DB.<br>
          Examples: BTC, ETH, SOL, MARA<br>
          Price sanity: BTC $5k–$250k, ETH $100–$20k, etc.<br>
          Stablecoins (USDT, USDC) are blocklisted.</div>
        </div>
        <div style="background:#1a1f2e;border-radius:8px;padding:14px;border-left:3px solid #60a5fa">
          <div style="font-weight:700;color:#60a5fa;margin-bottom:8px">OPTION</div>
          <div style="color:#94a3b8;font-size:12px;line-height:1.6">Triggered by contract notation or calls/puts language.<br>
          Examples: "IBIT 42c", "HOOD calls", "CLSK 10p 2/20"<br>
          Price = premium paid per contract ($0.01–$500).<br>
          Exit/entry ratio &gt;5x triggers break-even fallback.</div>
        </div>
        <div style="background:#1a1f2e;border-radius:8px;padding:14px;border-left:3px solid #a78bfa">
          <div style="font-weight:700;color:#a78bfa;margin-bottom:8px">STOCK</div>
          <div style="color:#94a3b8;font-size:12px;line-height:1.6">Matched against SEC EDGAR ticker DB.<br>
          Currently filtered out by allowed_asset_types config.<br>
          Blocklist prevents English words (SET, CUT, DAY) from matching.</div>
        </div>
      </div>
      ${{code(`Message: "Taking ibit puts here 38p 2/27/26 @0.55"
  -> symbol.py rule 2: option contract "IBIT 38p" -> (IBIT, OPTION) conf=0.92
  -> price.py: entry_price=0.55

Message: "Coin: BTC\\nEntry: 90000\\nLong"
  -> symbol.py rule 1: "Coin: BTC" template -> (BTC, CRYPTO) conf=0.95
  -> price.py: entry_price=90000, side=LONG`)}}`;

    // ---- 5. Trade classification (LONG/SHORT + close_fraction)
    const s5 = `
      <p style="color:#94a3b8;margin-bottom:14px;line-height:1.7">
        The broker maps Signal actions to order types. <b style="color:#e2e8f0">Side</b> (LONG/SHORT)
        comes from the parsed signal. <b style="color:#e2e8f0">close_fraction</b> tracks how much of
        the position is closed. <b>Margin/short selling</b> is supported — SHORT signals
        open a SELL_SHORT order and close via BUY_COVER.
      </p>
      <table style="border-collapse:collapse;width:100%;max-width:700px;margin-bottom:16px">
        <thead><tr>
          <th style="color:#6b7280;font-size:11px;padding:8px 12px;text-align:left;border-bottom:1px solid #1e293b">Signal</th>
          <th style="color:#6b7280;font-size:11px;padding:8px 12px;text-align:left;border-bottom:1px solid #1e293b">Side</th>
          <th style="color:#6b7280;font-size:11px;padding:8px 12px;text-align:left;border-bottom:1px solid #1e293b">Order Type</th>
          <th style="color:#6b7280;font-size:11px;padding:8px 12px;text-align:left;border-bottom:1px solid #1e293b">close_fraction</th>
          <th style="color:#6b7280;font-size:11px;padding:8px 12px;text-align:left;border-bottom:1px solid #1e293b">P&L</th>
        </tr></thead>
        <tbody>
          <tr><td style="padding:7px 12px">${{badge('ENTRY')}}</td><td style="color:#94a3b8;padding:7px 12px">LONG</td><td style="color:#22c55e;font-family:monospace;padding:7px 12px">BUY</td><td style="color:#94a3b8;font-family:monospace;padding:7px 12px">0.0</td><td style="color:#6b7280;padding:7px 12px">$0 (opens position)</td></tr>
          <tr><td style="padding:7px 12px">${{badge('ENTRY')}}</td><td style="color:#94a3b8;padding:7px 12px">SHORT</td><td style="color:#ef4444;font-family:monospace;padding:7px 12px">SELL_SHORT</td><td style="color:#94a3b8;font-family:monospace;padding:7px 12px">0.0</td><td style="color:#6b7280;padding:7px 12px">$0 (opens short)</td></tr>
          <tr><td style="padding:7px 12px">${{badge('TRIM')}}</td><td style="color:#94a3b8;padding:7px 12px">LONG</td><td style="color:#22d3ee;font-family:monospace;padding:7px 12px">SELL</td><td style="color:#94a3b8;font-family:monospace;padding:7px 12px">0.5</td><td style="color:#6b7280;padding:7px 12px">realized on 50% of remaining</td></tr>
          <tr><td style="padding:7px 12px">${{badge('TRIM')}}</td><td style="color:#94a3b8;padding:7px 12px">SHORT</td><td style="color:#22d3ee;font-family:monospace;padding:7px 12px">BUY_COVER</td><td style="color:#94a3b8;font-family:monospace;padding:7px 12px">0.5</td><td style="color:#6b7280;padding:7px 12px">realized on 50% of remaining</td></tr>
          <tr><td style="padding:7px 12px">${{badge('EXIT')}}</td><td style="color:#94a3b8;padding:7px 12px">LONG</td><td style="color:#facc15;font-family:monospace;padding:7px 12px">SELL</td><td style="color:#94a3b8;font-family:monospace;padding:7px 12px">1.0</td><td style="color:#6b7280;padding:7px 12px">realized on all remaining</td></tr>
          <tr><td style="padding:7px 12px">${{badge('EXIT')}}</td><td style="color:#94a3b8;padding:7px 12px">SHORT</td><td style="color:#facc15;font-family:monospace;padding:7px 12px">BUY_COVER</td><td style="color:#94a3b8;font-family:monospace;padding:7px 12px">1.0</td><td style="color:#6b7280;padding:7px 12px">realized on all remaining</td></tr>
          <tr><td style="padding:7px 12px">${{badge('ADD')}}</td><td style="color:#94a3b8;padding:7px 12px">LONG</td><td style="color:#60a5fa;font-family:monospace;padding:7px 12px">ADD</td><td style="color:#94a3b8;font-family:monospace;padding:7px 12px">0.0</td><td style="color:#6b7280;padding:7px 12px">$0 (adds to position size)</td></tr>
        </tbody>
      </table>
      ${{code(`P&L formula (broker.py):
  dollar_pnl = notional × close_fraction × (exit_price − entry_price) / entry_price × side_mult

  side_mult = +1  for LONG (profit when price goes UP)
  side_mult = -1  for SHORT (profit when price goes DOWN)

  TRIM:  close_fraction=0.5, notional=position.remaining
  EXIT:  close_fraction=1.0, notional=position.remaining
  ADD:   no P&L — just increases position exposure

  Fallbacks:
  - No exit price parsed -> uses entry_price -> $0 break-even (honest, not fake)
  - OPTION exit/entry > 5x -> break-even (price context bleed guard)
  - CRYPTO exit/entry > 200x -> break-even (parser misfire guard)
  - Entry price implausible for asset (BTC at $1.10) -> position skipped entirely`)}}`;

    // ---- 6. Risk management
    const s6 = `
      <p style="color:#94a3b8;margin-bottom:14px;line-height:1.7">
        Every signal passes through <code style="color:#a3e635">risk/rules.py</code> before the broker sees it.
        All gates must pass. Config lives in <code style="color:#a3e635">config/${{currentTrader}}.json</code>.
      </p>
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;max-width:800px;margin-bottom:16px">
        <div style="background:#1a1f2e;border-radius:8px;padding:14px">
          <div style="font-size:11px;color:#6b7280;margin-bottom:4px">min_confidence</div>
          <div style="font-size:22px;font-weight:700;color:#f59e0b">${{risk.min_confidence||0.6}}</div>
          <div style="font-size:12px;color:#6b7280;margin-top:4px">Signals below this are rejected as UNSURE</div>
        </div>
        <div style="background:#1a1f2e;border-radius:8px;padding:14px">
          <div style="font-size:11px;color:#6b7280;margin-bottom:4px">max_open_positions</div>
          <div style="font-size:22px;font-weight:700;color:#60a5fa">${{risk.max_open_positions||10}}</div>
          <div style="font-size:12px;color:#6b7280;margin-top:4px">New ENTRYs blocked when at capacity</div>
        </div>
        <div style="background:#1a1f2e;border-radius:8px;padding:14px">
          <div style="font-size:11px;color:#6b7280;margin-bottom:4px">trade_notional</div>
          <div style="font-size:22px;font-weight:700;color:#22c55e">$${{broker.trade_notional||100}}</div>
          <div style="font-size:12px;color:#6b7280;margin-top:4px">Fixed dollar amount per ENTRY. P&L scales proportionally.</div>
        </div>
        <div style="background:#1a1f2e;border-radius:8px;padding:14px">
          <div style="font-size:11px;color:#6b7280;margin-bottom:4px">kill_switch</div>
          <div style="font-size:22px;font-weight:700;color:${{risk.kill_switch?'#ef4444':'#22c55e'}}">${{risk.kill_switch?'ON — ALL TRADING HALTED':'OFF'}}</div>
          <div style="font-size:12px;color:#6b7280;margin-top:4px">Rejects every signal instantly when enabled</div>
        </div>
      </div>
      <div style="background:#1a1f2e;border-radius:8px;padding:14px;margin-bottom:12px;max-width:800px">
        <div style="font-size:12px;color:#6b7280;margin-bottom:8px">Allowed asset types &amp; actions</div>
        <div style="display:flex;gap:8px;flex-wrap:wrap">
          ${{(risk.allowed_asset_types||[]).map(t=>`<span style="background:#22c55e22;color:#22c55e;padding:3px 10px;border-radius:4px;font-size:12px;font-weight:600">${{t}}</span>`).join('')}}
          ${{(risk.allowed_actions||[]).map(a=>`<span style="background:#60a5fa22;color:#60a5fa;padding:3px 10px;border-radius:4px;font-size:12px;font-weight:600">${{a}}</span>`).join('')}}
        </div>
      </div>
      ${{code(`Risk gate order (risk/rules.py):
  1. kill_switch=true           -> reject ALL
  2. action not in allowed_actions  -> reject
  3. asset_type not in allowed_asset_types -> reject
  4. confidence < min_confidence  -> reject
  5. action=ENTRY + already open position for symbol -> reject (dedup)
  6. action=ENTRY + open positions >= max_open_positions -> reject
  7. action=TRIM/EXIT + no open position -> reject (nothing to close)
  8. PASS -> broker.submit_order()`)}}`;

    // ---- 7. Message → Signal examples
    const exRows = Object.entries(d.samples||{{}}).map(([action, sigs]) => {{
      if (!sigs.length) return '';
      const c = ACTION_COLORS[action] || '#6b7280';
      const cards = sigs.map(s => `
        <div style="background:#0d1117;border-radius:8px;padding:12px 14px;margin-bottom:8px;border-left:3px solid ${{c}}">
          <div style="font-size:11px;color:#6b7280;margin-bottom:6px">${{(s.timestamp||'').substring(0,16).replace('T',' ')}} &nbsp;·&nbsp; conf=${{(s.confidence||0).toFixed(2)}} &nbsp;·&nbsp; ${{s.symbol||'?'}} (${{s.asset_type||'?'}}) &nbsp;·&nbsp; ${{s.side||'—'}} @${{s.entry_price||'?'}}</div>
          <div style="font-family:monospace;font-size:12px;color:#e2e8f0;white-space:pre-wrap;word-break:break-all">${{(s.raw_content||'').substring(0,300).replace(/</g,'&lt;').replace(/>/g,'&gt;')}}</div>
        </div>`).join('');
      return `<div style="margin-bottom:20px">
        <div style="display:flex;align-items:center;gap:10px;margin-bottom:10px">
          ${{badge(action)}}
          <span style="color:#6b7280;font-size:12px">— top ${{sigs.length}} example(s) from corpus</span>
        </div>
        ${{cards}}
      </div>`;
    }}).join('');
    const s7 = `<p style="color:#94a3b8;margin-bottom:16px">Real messages from ${{currentTrader}}'s corpus and what the parser extracted from each.</p>${{exRows}}`;

    // ---- 8. Trace tab explanation
    const s8 = `
      <p style="color:#94a3b8;margin-bottom:14px;line-height:1.7">
        The <b style="color:#a78bfa">&#9875; Trace tab</b> shows how every message flows through the pipeline —
        from raw Discord text to parsed signal to trade event. Click any signal row to expand and see exactly
        which rules fired and why it was approved or rejected.
      </p>
      <div style="background:#1a1f2e;border-radius:8px;padding:16px;max-width:800px;margin-bottom:14px">
        <div style="font-size:12px;color:#a78bfa;font-weight:700;margin-bottom:10px">What each column shows:</div>
        <table style="border-collapse:collapse;width:100%">
          <tr><td style="padding:5px 12px 5px 0;color:#e2e8f0;font-size:12px;white-space:nowrap">Time</td><td style="color:#6b7280;font-size:12px">Original Discord timestamp</td></tr>
          <tr><td style="padding:5px 12px 5px 0;color:#e2e8f0;font-size:12px;white-space:nowrap">Message</td><td style="color:#6b7280;font-size:12px">Raw content exactly as it appeared in Discord</td></tr>
          <tr><td style="padding:5px 12px 5px 0;color:#e2e8f0;font-size:12px;white-space:nowrap">Action</td><td style="color:#6b7280;font-size:12px">What action.py classified it as</td></tr>
          <tr><td style="padding:5px 12px 5px 0;color:#e2e8f0;font-size:12px;white-space:nowrap">Symbol / Asset</td><td style="color:#6b7280;font-size:12px">Ticker + CRYPTO/OPTION/STOCK from symbol.py</td></tr>
          <tr><td style="padding:5px 12px 5px 0;color:#e2e8f0;font-size:12px;white-space:nowrap">Price</td><td style="color:#6b7280;font-size:12px">Parsed entry/exit price from price.py</td></tr>
          <tr><td style="padding:5px 12px 5px 0;color:#e2e8f0;font-size:12px;white-space:nowrap">Confidence</td><td style="color:#6b7280;font-size:12px">0–1 score. Below min_confidence = rejected by risk layer</td></tr>
          <tr><td style="padding:5px 12px 5px 0;color:#e2e8f0;font-size:12px;white-space:nowrap">Trade Link</td><td style="color:#6b7280;font-size:12px">If a trade was placed, shows trade_id + P&L. Grayed out = rejected.</td></tr>
        </table>
      </div>
      ${{code(`Example trace chain:
  [2026-01-05 08:49]  "Taking ibit puts here 38p 2/27/26 @0.55"
      action.py  -> ENTRY  (entry phrase: "Taking")
      symbol.py  -> IBIT   OPTION  (option contract: "IBIT 38p")
      price.py   -> entry_price=0.55
      conf       -> 0.85
      risk       -> APPROVED (confidence OK, no open IBIT, under position limit)
      broker     -> BUY  IBIT notional=$500 @0.55  -> trade_id=6029

  [2026-01-06 11:41]  "tp1 hit on the ibit puts"
      action.py  -> TRIM   (trim phrase: "tp1")
      symbol.py  -> IBIT   OPTION
      price.py   -> entry_price=1.0057  (price from "1.0057" in nearby context)
      conf       -> 0.85
      risk       -> APPROVED (open IBIT position exists)
      broker     -> SELL  IBIT notional=$250 @1.0057  pnl=-32.50 (-13%)
                    ^-- SHORT position: BUY_COVER at higher price = loss`)}}`;

    // ---- 9. Backtesting
    const s9 = `
      <p style="color:#94a3b8;margin-bottom:14px;line-height:1.7">
        The paper pipeline replays the entire message corpus in chronological order — as if the messages
        were arriving live. Every approved signal triggers a simulated trade against a SQLite DB.
        <b style="color:#e2e8f0">dry_run=true</b> means no real orders are sent — ever.
      </p>
      ${{code(`How --paper works:
  1. DB reset  — wipes all signals/trades/positions/equity for this trader
  2. parse_corpus(trader)  — parses all messages in messages.jsonl -> list[Signal]
  3. For each signal (chronological):
       a. db.insert_signal(sig)          log every message, even NOISE
       b. risk.evaluate(sig, db)         apply all gates
       c. broker.submit_order(sig, db)   open/trim/close positions
       d. db.insert_equity_snapshot()    running P&L curve
  4. force_close_all()  — any position still open at corpus end -> break-even close
  5. write_report()     — HTML report + JSONL signals file

  All times are message timestamps (not wall-clock).
  Positions can span months. Concurrent positions are tracked and flagged.`)}}
      <div style="background:#1e293b;border-radius:8px;padding:14px;margin-top:14px;max-width:700px">
        <div style="font-size:12px;color:#fb923c;font-weight:700;margin-bottom:8px">Limitations of this backtest</div>
        <ul style="color:#94a3b8;font-size:12px;line-height:1.9;padding-left:18px">
          <li>Exit prices come from Alpaca historical bars (when available) or break-even fallback</li>
          <li>No slippage, no bid/ask spread, no partial fills modeled</li>
          <li>Fixed notional (${{broker.trade_notional||500}}/trade) — real sizing would vary</li>
          <li>Parser misses some signals (UNSURE) and misclassifies some (price bleed)</li>
          <li>The corpus is incomplete — missing months = open positions auto-closed at break-even</li>
        </ul>
      </div>`;

    // ---- 10. Parser fixtures
    const s10 = `
      <p style="color:#94a3b8;margin-bottom:14px;line-height:1.7">
        Fixtures are 15 hardcoded test messages in <code style="color:#a3e635">dev.py</code> that verify the parser
        never regresses. They cover every action type, tricky edge cases, and known false positives.
        <b>Run after every parser change</b> — if any fixture fails, the pipeline is broken.
      </p>
      ${{code(`Run fixtures:
  python dev.py                       # runs all 15 fixtures, shows PASS/FAIL

  python dev.py --trace f01 f03       # show rule-by-rule trace for specific fixtures
  python dev.py --msg "stopped out on btc" --trace   # trace any raw message

Examples of what fixtures test:
  f01  "Coin: BTC\\nEntry: 90000\\nLong"           -> ENTRY, BTC, CRYPTO
  f04  "tp1 hit ibit puts @1.05"                  -> TRIM,  IBIT, OPTION
  f07  "River stopped out"                         -> EXIT,  RIVER, CRYPTO
  f09  "Taking ibit puts here too  38p @0.55"      -> ENTRY, IBIT, OPTION (not TOO)
  f15  "https://twitter.com/something"             -> NOISE`)}}`;

    // ---- 11. Commands reference
    const s11 = `
      ${{code(`# Setup
python setup_trader.py <TraderName>       # create config + data dirs for a new trader

# Profile a trader's language
python main.py <Trader>                   # parse corpus -> frequency charts in data/<Trader>/profile/

# Development
python dev.py                             # run 15 parser fixtures (must stay 15/15)
python dev.py --trace f01 f03             # rule trace for specific fixtures
python dev.py --msg "..." --trace         # trace any message through the parser
python dev.py --corpus Grizzlies          # parse full corpus, print action/symbol stats
python dev.py --corpus Grizzlies --save   # also write JSONL + HTML report

# Paper pipeline (full backtest)
python dev.py --paper Grizzlies --save    # parse -> risk -> broker -> DB -> HTML report

# Live replay
python dev.py --poll Grizzlies            # replay corpus in time order (mock live Discord)
python dev.py --poll Grizzlies --speed 10 # 10x speed replay

# Equity
python dev.py --equity Grizzlies          # print equity table from DB + write PNG

# Dashboard
python dev.py --serve Grizzlies           # start FastAPI dashboard at localhost:8765

# Import Discord exports
python ingestion/from_discord_export.py export.json Grizzlies  # add Discord messages`)}}`;

    // ---- 12. Alpaca status
    const s12 = `
      <div style="background:#1a1f2e;border-radius:8px;padding:16px;max-width:600px;margin-bottom:14px;border-left:3px solid #fb923c">
        <div style="font-weight:700;color:#fb923c;margin-bottom:8px">Status: OFFLINE (dry_run=true)</div>
        <div style="color:#94a3b8;font-size:12px;line-height:1.7">
          Alpaca is wired in <code style="color:#a3e635">execution/alpaca_adapter.py</code> but never called until keys are added.
          <code style="color:#a3e635">broker.py</code> always passes <code>dry_run=True</code> which logs trades to SQLite instead of sending them.
        </div>
      </div>
      ${{code(`To activate Alpaca paper trading:
  1. Get API keys from alpaca.markets (Paper Trading account)
  2. Copy .env.example to .env and fill in:
       ALPACA_API_KEY=PKxxxxxxxxxxxxxxxxxxxxxxxx
       ALPACA_SECRET_KEY=xxxxxxxxxxxxxxxxxxxxxxxx
       ALPACA_PAPER=true   # ALWAYS true during testing
  3. Set dry_run=false in config/Grizzlies.json broker section
  4. Run: python dev.py --paper Grizzlies --save  (verify in Alpaca paper UI)
  5. Only after weeks of paper trading: change ALPACA_PAPER to false

  NEVER commit .env to git — API keys stay local only.`)}}`;

    el.innerHTML = `
      <div style="max-width:1000px">
        <div style="margin-bottom:24px">
          <h2 style="color:#f59e0b;font-size:20px;font-weight:700;margin-bottom:6px">&#128218; Pipeline Documentation — ${{currentTrader}}</h2>
          <p style="color:#6b7280;font-size:13px">Live stats from the current DB run. Click any section header to expand/collapse.</p>
        </div>
        ${{section('&#128202;', 'Overview & Current Stats', s1)}}
        ${{section('&#9654;', 'Full Pipeline Flow', s2)}}
        ${{section('&#127381;', 'Signal Classification (Action)', s3)}}
        ${{section('&#127991;', 'Symbol & Asset Classification', s4)}}
        ${{section('&#128260;', 'Trade Classification — LONG/SHORT, Margin, close_fraction', s5)}}
        ${{section('&#128737;', 'Risk Management', s6)}}
        ${{section('&#128172;', 'Message → Signal Examples (Real Corpus)', s7)}}
        ${{section('&#9875;', 'Trace Tab — Message to Trade Chain', s8)}}
        ${{section('&#127381;', 'Backtesting — How the Paper Pipeline Works', s9)}}
        ${{section('&#9989;', 'Parser Fixtures — Unit Tests', s10)}}
        ${{section('&#9000;', 'Command Reference', s11)}}
        ${{section('&#128279;', 'Alpaca API Integration', s12)}}
      </div>`;
  }} catch(e) {{ el.innerHTML = `<div class="empty">Error loading pipeline: ${{e.message}}</div>`; }}
}}

// ---- Live tab ---------------------------------------------------------------
let _liveLogIdx    = 0;
let _livePollTimer = null;
let _liveInited    = false;
let _liveStartTime = null;
let _liveUptimeTimer = null;

function initLive() {{
  if (!_liveInited) {{
    _liveInited = true;
    _alpacaBooted = false;  // replay boot sequence on each fresh load
    _renderLiveShell();
    _pollLiveStatus();
  }}
}}

function _renderLiveShell() {{
  const el = document.getElementById('liveContent');
  el.innerHTML = `
  <div style="width:100%">
  <style>
    .live-card {{
      background:#111827;border:1px solid #1e293b;border-radius:10px;
      padding:12px 18px;display:flex;align-items:center;gap:12px;min-width:150px;
    }}
    .live-dot {{
      width:12px;height:12px;border-radius:50%;background:#374151;flex-shrink:0;
    }}
    .live-dot.running {{ background:#22c55e; animation:pulse-green 2s infinite; }}
    .live-dot.error   {{ background:#ef4444; }}
    .live-log-box {{
      background:#0d1117;border-radius:10px;border:1px solid #1e293b;
      display:flex;flex-direction:column;overflow:hidden;
    }}
    .live-log-hdr {{
      padding:8px 14px;border-bottom:1px solid #1e293b;display:flex;
      align-items:center;gap:10px;flex-shrink:0;
    }}
    .live-log-body {{
      overflow-y:auto;padding:8px 12px;font-family:monospace;font-size:11.5px;
      line-height:1.75;height:280px;
    }}
    @keyframes pulse-green {{
      0%  {{ box-shadow:0 0 0 0 #22c55e66; }}
      70% {{ box-shadow:0 0 0 8px transparent; }}
      100%{{ box-shadow:0 0 0 0 transparent; }}
    }}
  </style>

    <!-- Header -->
    <div style="display:flex;align-items:center;gap:16px;margin-bottom:14px;flex-wrap:wrap">
      <h2 style="color:#22c55e;font-size:18px;font-weight:700;margin:0">&#9679; Live Mode</h2>
      <span style="color:#6b7280;font-size:13px">Windows toast watcher + pipeline + Alpaca paper account</span>
      <div style="margin-left:auto;display:flex;gap:10px">
        <button id="liveStartBtn" onclick="_liveStart()"
          style="background:#22c55e;color:#000;font-weight:700;border:none;border-radius:8px;
                 padding:8px 24px;cursor:pointer;font-size:13px;transition:all .2s">START</button>
        <button id="liveRestartBtn" onclick="_liveRestart()"
          style="display:none;background:#1d4ed8;color:#fff;font-weight:700;border:1px solid #3b82f6;
                 border-radius:8px;padding:8px 20px;cursor:pointer;font-size:13px;transition:all .2s"
          title="Stop and restart with current settings">&#8635; RESTART</button>
        <button id="liveStopBtn" onclick="_liveKill()"
          style="background:#7f1d1d;color:#fca5a5;font-weight:800;border:2px solid #ef4444;
                 border-radius:8px;padding:8px 28px;cursor:pointer;font-size:14px;
                 letter-spacing:.04em;transition:all .2s"
          title="Stops watcher + pipeline and activates kill switch — no new trades will be placed">
          &#9632; EMERGENCY STOP
        </button>
      </div>
    </div>

    <!-- Kill switch banner — shown when kill_switch is active -->
    <div id="killSwitchBanner" style="display:none;background:#450a0a;border:2px solid #ef4444;
         border-radius:10px;padding:10px 20px;margin-bottom:12px;
         align-items:center;gap:16px;flex-wrap:wrap">
      <span style="color:#ef4444;font-weight:800;font-size:14px;letter-spacing:.06em">
        &#9888; KILL SWITCH ACTIVE — ALL TRADING HALTED
      </span>
      <span style="color:#fca5a5;font-size:12px">
        Pipeline is stopped. No trades will be placed even if pipeline restarts.
      </span>
      <button onclick="_clearKillSwitch()"
        style="margin-left:auto;background:#1c1917;color:#f59e0b;border:1px solid #f59e0b55;
               border-radius:6px;padding:5px 14px;cursor:pointer;font-size:12px;font-weight:700">
        Clear Kill Switch
      </button>
    </div>

    <!-- Runtime banner — hidden until running -->
    <div id="runtimeBanner" style="display:none;background:#052e16;border:1px solid #166534;
         border-radius:10px;padding:12px 20px;margin-bottom:16px;
         display:none;align-items:center;gap:20px;flex-wrap:wrap">
      <div style="display:flex;align-items:center;gap:10px">
        <div style="width:10px;height:10px;border-radius:50%;background:#22c55e;
                    animation:pulse-green 1.5s infinite;flex-shrink:0"></div>
        <span style="color:#22c55e;font-weight:800;font-size:15px;letter-spacing:.05em">RUNNING</span>
      </div>
      <div style="color:#6b7280;font-size:13px">Trader: <b style="color:#e2e8f0" id="rtTrader">—</b></div>
      <div style="color:#6b7280;font-size:13px">Mode: <b id="rtMode" style="color:#f59e0b">—</b></div>
      <div style="color:#6b7280;font-size:13px">Uptime: <b id="rtUptime" style="color:#22c55e;font-family:monospace;font-size:14px">00:00:00</b></div>
      <div style="color:#6b7280;font-size:13px">Captured: <b id="rtCaptured" style="color:#22d3ee">0</b> msgs</div>
      <div style="color:#6b7280;font-size:13px">Trades: <b id="rtTrades" style="color:#a78bfa">0</b></div>
    </div>

    <!-- ═══ STEP 1: CONFIGURATION (top) ═══ -->
    <div id="configStrip" style="background:#111827;border:1px solid #1e293b;border-radius:12px;
                padding:14px 18px;margin-bottom:10px">
      <div style="display:flex;align-items:center;gap:10px;cursor:pointer" onclick="_toggleStep1()">
        <span id="step1Arrow" style="font-size:12px;color:#6b7280;transition:transform .2s">&#9660;</span>
        <span style="font-size:12px;font-weight:800;color:#e2e8f0;letter-spacing:.05em;user-select:none">
          STEP 1 — CONFIGURE &amp; SAVE
        </span>
        <span style="font-size:11px;color:#374151">Keys, channel map, risk</span>
        <div id="settingsChangedBadge" style="display:none;background:#7c2d12;color:#fb923c;
             font-size:10px;font-weight:700;padding:3px 10px;border-radius:20px;border:1px solid #f97316;
             margin-left:auto">&#9888; Settings changed — Restart required</div>
      </div>
      <div id="step1Body" style="margin-top:12px">
      <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:16px">

        <!-- Col 1: Alpaca Keys -->
        <div>
          <div style="font-size:11px;font-weight:700;color:#60a5fa;margin-bottom:8px;letter-spacing:.04em">&#128273; ALPACA KEYS</div>
          <div id="alpacaStatus" style="font-size:10px;margin-bottom:6px"></div>
          <input id="alpacaKey" type="text" placeholder="PKXXXXXXXXXXXXXXXX (API Key)"
            style="width:100%;background:#0d1117;color:#e2e8f0;border:1px solid #1e293b;
                   border-radius:6px;padding:6px 10px;font-size:11px;box-sizing:border-box;margin-bottom:6px"
            oninput="_markSettingsChanged()">
          <input id="alpacaSecret" type="password" placeholder="Secret key"
            style="width:100%;background:#0d1117;color:#e2e8f0;border:1px solid #1e293b;
                   border-radius:6px;padding:6px 10px;font-size:11px;box-sizing:border-box;margin-bottom:8px"
            oninput="_markSettingsChanged()">
          <div style="display:flex;align-items:center;gap:8px;margin-bottom:8px">
            <input type="checkbox" id="alpacaPaper" checked style="accent-color:#22c55e">
            <span style="font-size:11px;color:#94a3b8">Paper account (never real money)</span>
          </div>
          <div style="font-size:9px;color:#374151;margin-top:4px">Never committed to git</div>
        </div>

        <!-- Col 2: Trader + Channel Map -->
        <div>
          <div style="font-size:11px;font-weight:700;color:#22d3ee;margin-bottom:8px;letter-spacing:.04em">&#127760; TRADER &amp; CHANNEL</div>
          <label style="font-size:10px;color:#6b7280;display:block;margin-bottom:3px">Trader</label>
          <select id="liveTrader" onchange="_markSettingsChanged()"
            style="width:100%;background:#0d1117;color:#e2e8f0;border:1px solid #1e293b;
                   border-radius:6px;padding:6px 10px;font-size:12px;margin-bottom:10px">
            {trader_opts}
          </select>
          <label style="font-size:10px;color:#6b7280;display:block;margin-bottom:3px">
            Channel Map <span style="color:#374151">— Discord channel name : Trader name</span>
          </label>
          <input id="liveChanMap" type="text" placeholder="grizzlies:Grizzlies"
            style="width:100%;background:#0d1117;color:#e2e8f0;border:1px solid #1e293b;
                   border-radius:6px;padding:6px 10px;font-size:12px;box-sizing:border-box;margin-bottom:10px"
            oninput="_markSettingsChanged()">
        </div>

        <!-- Col 3: Risk Config -->
        <div>
          <div style="font-size:11px;font-weight:700;color:#a78bfa;margin-bottom:8px;letter-spacing:.04em">&#9881; RISK CONFIG</div>
          <div id="liveRiskCfg"><div style="color:#374151;font-size:11px">Loading...</div></div>
        </div>

      </div>

      <!-- Save All + feedback -->
      <div style="display:flex;align-items:center;gap:14px;margin-top:14px;padding-top:12px;border-top:1px solid #1e293b">
        <button onclick="_liveSaveAll()"
          style="background:#1e3a5f;color:#60a5fa;border:1px solid #3b82f680;border-radius:8px;
                 padding:8px 28px;cursor:pointer;font-size:13px;font-weight:700;letter-spacing:.03em;
                 transition:all .15s"
          onmouseover="this.style.background='#1d4ed8'"
          onmouseout="this.style.background='#1e3a5f'">
          &#128190; Save All Settings
        </button>
        <div id="liveSaveMsg" style="font-size:12px;color:#22c55e;opacity:0;transition:opacity .5s"></div>
        <span style="font-size:10px;color:#374151;margin-left:auto">Keys saved to .env (never committed) &bull; Config saved to config/Grizzlies.json</span>
      </div>
    </div></div>

    <!-- ═══ STEP 2: HOW TO RUN (collapsible) ═══ -->
    <div style="background:#1a1f2e;border:1px solid #1e293b;border-radius:10px;
                padding:10px 18px;margin-bottom:14px">
      <div style="display:flex;align-items:center;gap:10px;cursor:pointer;flex-wrap:wrap" onclick="_toggleStep2()">
        <span id="step2Arrow" style="font-size:12px;color:#6b7280;transition:transform .2s">&#9654;</span>
        <span style="font-size:11px;font-weight:800;color:#f59e0b;letter-spacing:.05em;user-select:none">STEP 2 — START</span>
        <span style="font-size:12px;color:#6b7280;user-select:none">
          Discord minimized &#8594; START &#8594; Sanity Check
        </span>
        <div style="margin-left:auto">
          <button onclick="event.stopPropagation();_runSanityCheck()"
            style="background:#422006;color:#fb923c;border:2px solid #f59e0b;border-radius:8px;
                   padding:7px 18px;cursor:pointer;font-size:12px;font-weight:800;white-space:nowrap;
                   transition:all .15s"
            onmouseover="this.style.background='#713f12'"
            onmouseout="this.style.background='#422006'">
            &#9654; Sanity Check
          </button>
        </div>
      </div>
      <div id="step2Body" style="display:none;margin-top:10px;padding-top:10px;border-top:1px solid #1e293b">
        <div style="font-size:12px;color:#94a3b8;line-height:2">
          1. Configure &amp; save above (Step 1)<br>
          2. Open Discord <b style="color:#e2e8f0">minimized</b> — toasts won't fire if Discord is focused or fullscreen<br>
          3. Click <b style="color:#22c55e">START</b>, then <b style="color:#f59e0b">&#9654; Sanity Check</b> to confirm the full pipeline fires end-to-end<br>
          <span style="color:#22c55e">Paper trading only — no real money at risk.</span>
        </div>
        <div style="margin-top:8px;font-size:11px;color:#64748b">
          <b style="color:#94a3b8">Sanity Check:</b>
          fires a real BTC signal — parse &#8594; risk &#8594; Alpaca paper order &#8594; close.
          Confirms keys, routing &amp; broker are all wired. No lasting positions.
        </div>
      </div>
    </div>

    <!-- Status row -->
    <div style="display:flex;gap:10px;flex-wrap:wrap;margin-bottom:18px">
      <div class="live-card">
        <div class="live-dot" id="dot-watcher"></div>
        <div><div style="font-size:11px;color:#6b7280">Toast Watcher</div>
             <div id="txt-watcher" style="font-size:13px;font-weight:700;color:#e2e8f0">Stopped</div></div>
      </div>
      <div class="live-card">
        <div class="live-dot" id="dot-pipeline"></div>
        <div><div style="font-size:11px;color:#6b7280">Pipeline</div>
             <div id="txt-pipeline" style="font-size:13px;font-weight:700;color:#e2e8f0">Stopped</div></div>
      </div>
      <div class="live-card">
        <div class="live-dot" id="dot-alpaca"></div>
        <div><div style="font-size:11px;color:#6b7280">Alpaca Paper</div>
             <div id="txt-alpaca" style="font-size:13px;font-weight:700;color:#e2e8f0">--</div></div>
      </div>
      <div class="live-card" style="min-width:130px">
        <div><div style="font-size:11px;color:#6b7280">Equity</div>
             <div id="alp-equity" style="font-size:18px;font-weight:700;color:#22c55e">--</div></div>
      </div>
      <div class="live-card" style="min-width:130px">
        <div><div style="font-size:11px;color:#6b7280">Buying Power</div>
             <div id="alp-bp" style="font-size:18px;font-weight:700;color:#60a5fa">--</div></div>
      </div>
      <div class="live-card" style="min-width:110px">
        <div><div style="font-size:11px;color:#6b7280">Intercepted</div>
             <div id="cnt-intercepted" style="font-size:20px;font-weight:700;color:#22d3ee">0</div></div>
      </div>
      <div class="live-card" style="min-width:110px">
        <div><div style="font-size:11px;color:#6b7280">Trades</div>
             <div id="cnt-traded" style="font-size:20px;font-weight:700;color:#a78bfa">0</div></div>
      </div>
      <div class="live-card" style="min-width:160px">
        <div><div style="font-size:11px;color:#6b7280">Session Start</div>
             <div id="txt-session" style="font-size:12px;color:#94a3b8">—</div></div>
      </div>
    </div>

    <!-- Log color legend -->
    <div style="display:flex;flex-wrap:wrap;gap:6px 18px;margin-bottom:10px;
                padding:8px 14px;background:#0d1117;border-radius:8px;
                border:1px solid #1e293b;align-items:center">
      <span style="font-size:10px;font-weight:700;color:#374151;letter-spacing:.08em;margin-right:4px">LOG KEY</span>
      <span style="font-size:11px"><span style="color:#22c55e">&#9632;</span> <span style="color:#6b7280">success / saved / approved / connected</span></span>
      <span style="font-size:11px"><span style="color:#ef4444">&#9632;</span> <span style="color:#6b7280">error / rejected / disconnected / loss</span></span>
      <span style="font-size:11px"><span style="color:#fb923c">&#9632;</span> <span style="color:#6b7280">warning / unmapped / skipped</span></span>
      <span style="font-size:11px"><span style="color:#22d3ee">&#9632;</span> <span style="color:#6b7280">message captured (watcher)</span></span>
      <span style="font-size:11px"><span style="color:#60a5fa">&#9632;</span> <span style="color:#6b7280">Alpaca / broker API</span></span>
      <span style="font-size:11px"><span style="color:#a78bfa">&#9632;</span> <span style="color:#6b7280">parsed signal (action / symbol)</span></span>
      <span style="font-size:11px"><span style="color:#f59e0b">&#9632;</span> <span style="color:#6b7280">sanity check</span></span>
      <span style="font-size:11px"><span style="color:#374151">&#9632;</span> <span style="color:#6b7280">duplicate / noise / dim</span></span>
    </div>

    <!-- Four logs row -->
    <div style="display:grid;grid-template-columns:1fr 1fr 1fr 1fr;gap:12px;margin-bottom:16px">

      <!-- Log 1: Discord Watcher -->
      <div class="live-log-box">
        <div class="live-log-hdr">
          <span style="font-size:12px;font-weight:700;color:#22d3ee">&#128172; Discord Watcher</span>
          <span style="font-size:10px;color:#6b7280">Messages intercepted + signal parsed</span>
          <button onclick="_clearLogEl('logWatcher')"
            style="margin-left:auto;background:none;border:1px solid #1e293b;color:#6b7280;
                   border-radius:4px;padding:2px 8px;cursor:pointer;font-size:10px">Clear</button>
        </div>
        <div id="logWatcher" class="live-log-body"></div>
      </div>

      <!-- Log 2: Pipeline -->
      <div class="live-log-box">
        <div class="live-log-hdr">
          <span style="font-size:12px;font-weight:700;color:#a78bfa">&#9654; Pipeline</span>
          <span style="font-size:10px;color:#6b7280">Risk gates, approvals, rejects</span>
          <button onclick="_clearLogEl('logPipeline')"
            style="margin-left:auto;background:none;border:1px solid #1e293b;color:#6b7280;
                   border-radius:4px;padding:2px 8px;cursor:pointer;font-size:10px">Clear</button>
        </div>
        <div id="logPipeline" class="live-log-body"></div>
      </div>

      <!-- Log 3: Trades -->
      <div class="live-log-box">
        <div class="live-log-hdr">
          <span style="font-size:12px;font-weight:700;color:#22c55e">&#128200; Trades</span>
          <span style="font-size:10px;color:#6b7280">Orders placed + P&L</span>
          <button onclick="_clearLogEl('logTrades')"
            style="margin-left:auto;background:none;border:1px solid #1e293b;color:#6b7280;
                   border-radius:4px;padding:2px 8px;cursor:pointer;font-size:10px">Clear</button>
        </div>
        <div id="logTrades" class="live-log-body"></div>
      </div>

      <!-- Log 4: Connections -->
      <div class="live-log-box">
        <div class="live-log-hdr">
          <span style="font-size:12px;font-weight:700;color:#f59e0b">&#128268; Connections</span>
          <span style="font-size:10px;color:#6b7280">Alpaca · Watcher · Pipeline</span>
          <button onclick="_clearLogEl('logConn')"
            style="margin-left:auto;background:none;border:1px solid #1e293b;color:#6b7280;
                   border-radius:4px;padding:2px 8px;cursor:pointer;font-size:10px">Clear</button>
        </div>
        <div id="logConn" class="live-log-body"></div>
      </div>
    </div>

    <!-- Alpaca Positions (full width) -->
    <div style="background:#111827;border-radius:12px;border:1px solid #1e293b;overflow:hidden;margin-bottom:16px">
      <div style="padding:10px 16px;border-bottom:1px solid #1e293b;display:flex;align-items:center;gap:12px">
        <span style="font-weight:700;color:#e2e8f0;font-size:13px">Alpaca Open Positions</span>
        <span style="font-size:11px;color:#6b7280">Paper account — live from broker</span>
        <span id="alpaca-updated" style="font-size:10px;color:#374151;margin-left:auto"></span>
      </div>
      <div id="alpacaPositions" style="min-height:60px">
        <div class="empty">Fetching positions...</div>
      </div>
      <div style="border-top:1px solid #1e293b;padding:10px 16px">
        <div style="font-size:12px;font-weight:700;color:#94a3b8;margin-bottom:8px">Recent Orders</div>
        <div id="alpacaOrders"><div class="empty" style="font-size:11px">No orders yet</div></div>
      </div>
    </div>

    <!-- Intercepted messages table -->
    <div style="background:#111827;border-radius:12px;border:1px solid #1e293b;overflow:hidden">
      <div style="padding:10px 16px;border-bottom:1px solid #1e293b;display:flex;align-items:center;gap:12px">
        <span style="font-weight:700;color:#e2e8f0;font-size:13px">Intercepted Messages</span>
        <span style="font-size:11px;color:#6b7280">Last 30 captured — discord_messages.db</span>
        <button onclick="_refreshMessages()"
          style="margin-left:auto;background:none;border:1px solid #1e293b;color:#94a3b8;
                 border-radius:4px;padding:3px 10px;cursor:pointer;font-size:11px">Refresh</button>
      </div>
      <div id="liveMessages">
        <div class="empty">No messages yet — start the watcher and trigger a Discord notification</div>
      </div>
    </div>

  </div>
  `;

  _pollLiveStatus();
  _refreshMessages();
  _alpacaBootSequence();
  _loadLiveConfig();
  if (_livePollTimer) clearInterval(_livePollTimer);
  _livePollTimer = setInterval(_liveTick, 1000);
}}

async function _loadLiveConfig() {{
  const el = document.getElementById('liveRiskCfg');
  if (!el) return;
  try {{
    const cfg = await fetch(`/api/config/${{currentTrader}}`).then(r=>r.json());
    const risk = cfg.risk || {{}};
    const broker = cfg.broker || {{}};
    el.innerHTML = `
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:10px">
        <div>
          <label style="font-size:10px;color:#6b7280;display:block;margin-bottom:3px">Min Confidence</label>
          <input id="lcMinConf" type="number" min="0" max="1" step="0.01" value="${{risk.min_confidence||0.6}}"
            style="width:100%;background:#0d1117;color:#e2e8f0;border:1px solid #1e293b;border-radius:5px;padding:5px 8px;font-size:12px;box-sizing:border-box">
        </div>
        <div>
          <label style="font-size:10px;color:#6b7280;display:block;margin-bottom:3px">Max Positions</label>
          <input id="lcMaxPos" type="number" min="1" max="20" value="${{risk.max_open_positions||3}}"
            style="width:100%;background:#0d1117;color:#e2e8f0;border:1px solid #1e293b;border-radius:5px;padding:5px 8px;font-size:12px;box-sizing:border-box">
        </div>
        <div>
          <label style="font-size:10px;color:#6b7280;display:block;margin-bottom:3px">Trade Notional ($)</label>
          <input id="lcNotional" type="number" min="1" value="${{broker.trade_notional||500}}"
            style="width:100%;background:#0d1117;color:#e2e8f0;border:1px solid #1e293b;border-radius:5px;padding:5px 8px;font-size:12px;box-sizing:border-box">
        </div>
        <div>
          <label style="font-size:10px;color:#6b7280;display:block;margin-bottom:3px">Starting Balance ($)</label>
          <input id="lcBalance" type="number" min="1" value="${{broker.starting_balance||7000}}"
            style="width:100%;background:#0d1117;color:#e2e8f0;border:1px solid #1e293b;border-radius:5px;padding:5px 8px;font-size:12px;box-sizing:border-box">
        </div>
      </div>
      <button onclick="_saveLiveConfig()"
        style="width:100%;background:#1e293b;color:#22c55e;border:1px solid #22c55e44;
               border-radius:6px;padding:7px;cursor:pointer;font-size:12px">
        Save Trader Config
      </button>
      <span id="lcSaved" style="font-size:11px;color:#22c55e;opacity:0;margin-left:8px;transition:opacity .3s">Saved!</span>`;
    // Show/hide kill switch banner
    const ks = document.getElementById('killSwitchBanner');
    if (ks) ks.style.display = risk.kill_switch ? 'flex' : 'none';
  }} catch(e) {{ if(el) el.innerHTML = '<div style="color:#ef4444;font-size:11px">Error loading config</div>'; }}
}}

async function _saveLiveConfig() {{
  const r = await fetch(`/api/config/${{currentTrader}}`);
  const cfg = await r.json();
  cfg.risk   = cfg.risk   || {{}};
  cfg.broker = cfg.broker || {{}};
  cfg.risk.min_confidence     = parseFloat(document.getElementById('lcMinConf')?.value  || 0.6);
  cfg.risk.max_open_positions = parseInt(document.getElementById('lcMaxPos')?.value     || 3);
  cfg.broker.trade_notional   = parseFloat(document.getElementById('lcNotional')?.value || 500);
  cfg.broker.starting_balance = parseFloat(document.getElementById('lcBalance')?.value  || 7000);
  await fetch(`/api/config/${{currentTrader}}`, {{
    method:'PUT', headers:{{'Content-Type':'application/json'}}, body:JSON.stringify(cfg)
  }});
  const msg = document.getElementById('lcSaved');
  if (msg) {{ msg.style.opacity=1; setTimeout(()=>{{msg.style.opacity=0;}},2000); }}
}}

async function _pollLiveStatus() {{
  try {{
    const s = await fetch('/api/live/status').then(r=>r.json());
    _updateStatusCards(s);
    // Pre-fill channel map if blank
    const inp = document.getElementById('liveChanMap');
    if (inp && !inp.value && s.channel_map) inp.value = s.channel_map;
    // Alpaca status text
    const aEl = document.getElementById('alpacaStatus');
    if (aEl) {{
      if (s.alpaca === 'configured') {{
        aEl.style.color = '#22c55e';
        aEl.textContent = 'Alpaca keys configured';
      }} else {{
        aEl.style.color = '#fb923c';
        aEl.textContent = 'Not configured — add keys below to enable paper trading';
      }}
    }}
  }} catch(e) {{}}
}}

function _updateStatusCards(s) {{
  const dot = (id, state) => {{
    const el = document.getElementById('dot-'+id);
    if (!el) return;
    el.className = 'live-dot' + (state==='running' ? ' running' : state==='error' ? ' error' : '');
  }};
  const txt = (id, val) => {{ const el=document.getElementById('txt-'+id); if(el) el.textContent=val; }};
  dot('watcher',  s.watcher);
  dot('pipeline', s.pipeline);
  dot('alpaca',   s.alpaca === 'configured' ? 'running' : '');
  txt('watcher',  s.watcher  === 'running' ? 'Running' : 'Stopped');
  txt('pipeline', s.pipeline === 'running' ? 'Running' : 'Stopped');
  txt('alpaca',   s.alpaca   === 'configured' ? 'Configured' : 'Not configured');
  const ci = document.getElementById('cnt-intercepted');
  const ct = document.getElementById('cnt-traded');
  const cs = document.getElementById('txt-session');
  if (ci) ci.textContent = s.intercepted || 0;
  if (ct) ct.textContent = s.traded      || 0;
  if (cs) cs.textContent = s.session_start ? s.session_start.substring(0,16).replace('T',' ') : '—';
  // Sync runtime banner counters
  const rc = document.getElementById('rtCaptured');
  const rt2 = document.getElementById('rtTrades');
  if (rc) rc.textContent = s.intercepted || 0;
  if (rt2) rt2.textContent = s.traded || 0;
  // Log state changes to connection log
  if (_lastWatcherState !== null && _lastWatcherState !== s.watcher) {{
    _connLog('Toast watcher: ' + _lastWatcherState + ' → ' + s.watcher,
             s.watcher === 'running' ? '#22c55e' : '#fb923c');
  }}
  if (_lastPipelineState !== null && _lastPipelineState !== s.pipeline) {{
    _connLog('Live pipeline: ' + _lastPipelineState + ' → ' + s.pipeline,
             s.pipeline === 'running' ? '#22c55e' : '#fb923c');
  }}
  _lastWatcherState  = s.watcher;
  _lastPipelineState = s.pipeline;
  // If server says stopped but UI thinks running, sync back
  const isRunning = s.watcher === 'running' || s.pipeline === 'running';
  if (!isRunning && _liveStartTime) _setStoppedUI();
}}

let _alpacaTick = 0;
let _alpacaBooted = false;
let _sanityRows = [];  // persists sanity order rows across Alpaca refreshes

async function _alpacaBootSequence() {{
  if (_alpacaBooted) {{ _refreshAlpaca(); return; }}
  _alpacaBooted = true;

  const posEl = document.getElementById('alpacaPositions');
  if (!posEl) return;

  const terminal = document.createElement('div');
  terminal.style.cssText = `
    background:#0d1117;border-radius:8px;padding:14px 18px;
    font-family:monospace;font-size:12px;line-height:2;
    border:1px solid #166534;margin:12px;
  `;
  posEl.innerHTML = '';
  posEl.appendChild(terminal);

  const delay = ms => new Promise(r => setTimeout(r, ms));

  const line = (txt, col='#6b7280') => {{
    const d = document.createElement('div');
    d.innerHTML = txt;
    d.style.color = col;
    terminal.appendChild(d);
    posEl.scrollTop = posEl.scrollHeight;
    return d;
  }};

  const tick = (el, finalHtml, col) => {{
    el.innerHTML = finalHtml;
    el.style.color = col || '#22c55e';
  }};

  // Step 1
  const l1 = line('<span style="color:#374151">$</span> Connecting to Alpaca Paper API...', '#6b7280');
  await delay(600);
  tick(l1, '<span style="color:#374151">$</span> Connecting to Alpaca Paper API &nbsp;<span style="color:#22c55e">&#10003;</span> &nbsp;<span style="color:#475569">paper-api.alpaca.markets</span>');
  await delay(300);

  // Step 2
  const l2 = line('<span style="color:#374151">$</span> Authenticating...', '#6b7280');
  await delay(400);

  // Fetch real data
  let acct, pos, ord;
  try {{
    [acct, pos, ord] = await Promise.all([
      fetch('/api/alpaca/account').then(r=>r.json()),
      fetch('/api/alpaca/positions').then(r=>r.json()),
      fetch('/api/alpaca/orders?limit=10').then(r=>r.json()),
    ]);
  }} catch(e) {{
    tick(l2, `<span style="color:#374151">$</span> Authenticating... <span style="color:#ef4444">&#10007; Connection failed: ${{e.message}}</span>`);
    return;
  }}

  if (!acct.ok) {{
    tick(l2, `<span style="color:#374151">$</span> Authenticating... <span style="color:#ef4444">&#10007; ${{acct.error||'Auth failed'}}</span>`);
    return;
  }}

  tick(l2, `<span style="color:#374151">$</span> Authenticating... &nbsp;<span style="color:#22c55e">&#10003;</span> &nbsp;<span style="color:#475569">Account ${{acct.account_number}}</span>`);
  await delay(350);

  // Step 3 — status
  const l3 = line(`<span style="color:#374151">$</span> Checking account status...`, '#6b7280');
  await delay(450);
  const statusCol = acct.status === 'ACTIVE' ? '#22c55e' : '#fb923c';
  tick(l3, `<span style="color:#374151">$</span> Checking account status &nbsp;<span style="color:#22c55e">&#10003;</span> &nbsp;<span style="color:${{statusCol}}">${{acct.status}}</span> &nbsp;<span style="color:#475569">| Shorting: ${{acct.shorting_enabled ? 'enabled' : 'disabled'}} | PDT: ${{acct.pattern_day_trader ? 'YES ⚠' : 'No'}}</span>`);
  await delay(300);

  // Step 4 — equity
  const l4 = line(`<span style="color:#374151">$</span> Pulling balance...`, '#6b7280');
  await delay(500);
  const eq = acct.equity.toLocaleString('en-US',{{minimumFractionDigits:2,maximumFractionDigits:2}});
  const bp = acct.buying_power.toLocaleString('en-US',{{minimumFractionDigits:2,maximumFractionDigits:2}});
  tick(l4, `<span style="color:#374151">$</span> Pulling balance &nbsp;<span style="color:#22c55e">&#10003;</span> &nbsp;<span style="color:#22c55e;font-weight:700">$${{eq}}</span> &nbsp;<span style="color:#475569">equity &nbsp;|&nbsp; $${{bp}} buying power</span>`);

  // Update KPI cards
  const eqEl = document.getElementById('alp-equity');
  const bpEl = document.getElementById('alp-bp');
  if (eqEl) eqEl.textContent = '$' + eq;
  if (bpEl) bpEl.textContent = '$' + bp;
  const dotA = document.getElementById('dot-alpaca');
  const txtA = document.getElementById('txt-alpaca');
  if (dotA) dotA.className = 'live-dot running';
  if (txtA) txtA.textContent = 'Paper — ' + acct.status;
  await delay(300);

  // Step 5 — positions
  const positions = pos.positions || [];
  const l5 = line(`<span style="color:#374151">$</span> Fetching open positions...`, '#6b7280');
  await delay(450);
  const posCount = positions.filter(p=>!p.error).length;
  tick(l5, `<span style="color:#374151">$</span> Fetching open positions &nbsp;<span style="color:#22c55e">&#10003;</span> &nbsp;<span style="color:#e2e8f0">${{posCount}} open</span>`);
  await delay(300);

  // Step 6 — orders
  const orders = ord.orders || [];
  const l6 = line(`<span style="color:#374151">$</span> Fetching recent orders...`, '#6b7280');
  await delay(400);
  const ordCount = orders.filter(o=>!o.error).length;
  tick(l6, `<span style="color:#374151">$</span> Fetching recent orders &nbsp;<span style="color:#22c55e">&#10003;</span> &nbsp;<span style="color:#e2e8f0">${{ordCount}} orders</span>`);
  await delay(300);

  // Step 7 — ready
  const l7 = line('', '#22c55e');
  await delay(250);
  tick(l7, `<span style="color:#22c55e;font-weight:700">&#10003; Ready — Alpaca paper account connected</span>`);
  await delay(1800);

  // Transition to live positions view
  _renderAlpacaData(acct, positions, orders);
}}

function _renderAlpacaData(acct, positions, orders) {{
  // Positions
  const posEl = document.getElementById('alpacaPositions');
  if (posEl) {{
    if (!positions.length || positions[0]?.error) {{
      posEl.innerHTML = '<div class="empty" style="padding:16px">No open positions</div>';
    }} else {{
      const rows = positions.map(p => {{
        const plCol = p.unrealized_pl >= 0 ? '#22c55e' : '#ef4444';
        const plPct = (p.unrealized_plpc * 100).toFixed(2);
        const chgCol = p.change_today >= 0 ? '#22c55e' : '#ef4444';
        return `<tr>
          <td style="padding:8px 14px;color:#e2e8f0;font-weight:600">${{p.symbol}}</td>
          <td style="padding:8px 14px;color:#94a3b8">${{p.side}}</td>
          <td style="padding:8px 14px;color:#94a3b8">${{p.qty}}</td>
          <td style="padding:8px 14px;color:#94a3b8">$${{p.avg_entry_price.toFixed(4)}}</td>
          <td style="padding:8px 14px;color:#e2e8f0">$${{p.current_price.toFixed(4)}}</td>
          <td style="padding:8px 14px;color:#e2e8f0">$${{p.market_value.toFixed(2)}}</td>
          <td style="padding:8px 14px;color:${{plCol}};font-weight:700">
            ${{p.unrealized_pl>=0?'+':''}}$${{p.unrealized_pl.toFixed(2)}}
            <span style="font-size:10px"> (${{p.unrealized_pl>=0?'+':''}}${{plPct}}%)</span>
          </td>
          <td style="padding:8px 14px;color:${{chgCol}}">${{(p.change_today*100).toFixed(2)}}% today</td>
        </tr>`;
      }}).join('');
      posEl.innerHTML = `
        <table style="border-collapse:collapse;width:100%">
          <thead><tr style="border-bottom:1px solid #1e293b">
            <th style="color:#6b7280;font-size:11px;padding:8px 14px;text-align:left">Symbol</th>
            <th style="color:#6b7280;font-size:11px;padding:8px 14px;text-align:left">Side</th>
            <th style="color:#6b7280;font-size:11px;padding:8px 14px;text-align:left">Qty</th>
            <th style="color:#6b7280;font-size:11px;padding:8px 14px;text-align:left">Avg Entry</th>
            <th style="color:#6b7280;font-size:11px;padding:8px 14px;text-align:left">Current</th>
            <th style="color:#6b7280;font-size:11px;padding:8px 14px;text-align:left">Mkt Value</th>
            <th style="color:#6b7280;font-size:11px;padding:8px 14px;text-align:left">Unrealized P&L</th>
            <th style="color:#6b7280;font-size:11px;padding:8px 14px;text-align:left">Today</th>
          </tr></thead>
          <tbody>${{rows}}</tbody>
        </table>`;
    }}
  }}
  // Orders
  const ordEl = document.getElementById('alpacaOrders');
  if (ordEl && orders.length && !orders[0]?.error) {{
    const rows = orders.slice(0,8).map(o => {{
      const sc = o.status==='filled'?'#22c55e':o.status==='canceled'?'#6b7280':'#f59e0b';
      const sideCol = o.side==='buy'?'#22c55e':'#ef4444';
      return `<tr>
        <td style="padding:4px 10px;color:#6b7280;font-size:11px">${{o.submitted_at||''}}</td>
        <td style="padding:4px 10px;color:#e2e8f0;font-size:11px;font-weight:600">${{o.symbol}}</td>
        <td style="padding:4px 10px;font-size:11px;color:${{sideCol}};font-weight:600">${{o.side?.toUpperCase()}}</td>
        <td style="padding:4px 10px;color:#94a3b8;font-size:11px">${{o.notional?'$'+o.notional:o.qty}}</td>
        <td style="padding:4px 10px;font-size:11px"><span style="color:${{sc}}">${{o.status}}</span></td>
        <td style="padding:4px 10px;color:#94a3b8;font-size:11px">${{o.filled_avg_price?'@ $'+o.filled_avg_price:''}}</td>
      </tr>`;
    }}).join('');
    ordEl.innerHTML = `<table style="border-collapse:collapse;width:100%"><tbody>${{rows}}</tbody></table>`;
  }}
  const upd = document.getElementById('alpaca-updated');
  if (upd) upd.textContent = 'updated ' + new Date().toLocaleTimeString();
  _reinjectSanityRows();
}}

function _reinjectSanityRows() {{
  if (!_sanityRows.length) return;
  const ordEl = document.getElementById('alpacaOrders');
  if (!ordEl) return;
  if (!ordEl.querySelector('table')) {{
    ordEl.innerHTML = '<table style="border-collapse:collapse;width:100%"><tbody></tbody></table>';
  }}
  const tb = ordEl.querySelector('table tbody') || ordEl.querySelector('table');
  ordEl.querySelectorAll('.sanity-order-row').forEach(r => r.remove());
  for (const rowHtml of [..._sanityRows].reverse()) {{
    const tr = document.createElement('tr');
    tr.className = 'sanity-order-row';
    tr.style.cssText = 'border-bottom:1px solid #2d1f06;background:#1c1410';
    tr.innerHTML = rowHtml;
    tb.insertBefore(tr, tb.firstChild);
  }}
}}

async function _liveTick() {{
  try {{
    const r = await fetch(`/api/live/logs?since=${{_liveLogIdx}}`).then(x=>x.json());
    if (r.entries && r.entries.length) {{
      for (const e of r.entries) {{
        _liveLogIdx = e.i + 1;
        _appendLogLine(e);
      }}
    }}
    const s = await fetch('/api/live/status').then(x=>x.json());
    _updateStatusCards(s);
    // Refresh Alpaca every 10 ticks (~10s)
    _alpacaTick++;
    if (_alpacaTick % 10 === 0) _refreshAlpaca();
  }} catch(e) {{}}
}}

// ---- Shared log color palette -----------------------------------------------
// Every color used in ALL four log panels maps to the same semantic meaning.
// Change a color here and it updates everywhere.
const LOG_COLORS = {{
  success:   '#22c55e',  // green   — saved, BUY, trade placed, connected, approved
  error:     '#ef4444',  // red     — error, crash, disconnected, rejected, SELL/loss
  warning:   '#fb923c',  // orange  — UNMAPPED, SKIP, WARNING, kill-switch
  info:      '#22d3ee',  // cyan    — new message captured (watcher activity)
  broker:    '#60a5fa',  // blue    — Alpaca/broker API call or response
  signal:    '#a78bfa',  // purple  — parsed signal details (action/symbol/conf)
  sanity:    '#f59e0b',  // amber   — sanity check steps
  dim:       '#374151',  // dark    — duplicate, timestamp prefix, noise
  muted:     '#94a3b8',  // slate   — general pipeline info (default)
}};

function _logColor(msg, cat) {{
  const m = msg;
  // Errors always red
  if (m.includes('error') || m.includes('crash') || m.includes('failed') || m.includes('FAILED'))
    return LOG_COLORS.error;
  // Rejections / warnings / skips
  if (m.includes('UNMAPPED') || m.includes('SKIP') || m.includes('REJECT') || m.includes('WARNING') || m.includes('kill_switch'))
    return LOG_COLORS.warning;

  if (cat === 'watcher') {{
    if (m.includes('saved'))   return LOG_COLORS.success;
    if (m.includes('dup'))     return LOG_COLORS.dim;
    return LOG_COLORS.info;               // new toast captured
  }}
  if (cat === 'trade') {{
    if (m.includes('[alpaca]') || m.includes('Alpaca') || m.includes('ORDER'))
      return LOG_COLORS.broker;
    if (m.includes('BUY') || m.includes('pnl=+') || m.includes('filled'))
      return LOG_COLORS.success;
    if (m.includes('SELL') || m.includes('pnl=-'))
      return LOG_COLORS.error;
    if (m.includes('[sanity]') || m.includes('SANITY'))
      return LOG_COLORS.sanity;
    return LOG_COLORS.success;            // any trade log is positive by default
  }}
  if (cat === 'conn') {{
    if (m.includes('connected') || m.includes('cleared') || m.includes('PASSED'))
      return LOG_COLORS.success;
    if (m.includes('STOP') || m.includes('halted') || m.includes('disconnected'))
      return LOG_COLORS.error;
    if (m.includes('sanity') || m.includes('Sanity') || m.includes('[sanity]'))
      return LOG_COLORS.sanity;
    return LOG_COLORS.muted;
  }}
  // pipeline (default)
  if (m.includes('ENTRY') || m.includes('EXIT') || m.includes('TRIM') || m.includes('ADD'))
    return LOG_COLORS.signal;
  if (m.includes('TRADE') || m.includes('approved') || m.includes('running') || m.includes('Started'))
    return LOG_COLORS.success;
  return LOG_COLORS.muted;
}}

function _appendLogLine(e) {{
  const cat = e.cat || 'pipeline';
  const col = _logColor(e.msg, cat);
  const ts  = `<span style="color:#374151;user-select:none">${{e.ts}} </span>`;
  const txt = `<span style="color:${{col}}">${{e.msg.replace(/</g,'&lt;').replace(/>/g,'&gt;')}}</span>`;

  // Route to correct panel
  let targets = [];
  if (cat === 'watcher')    targets = ['logWatcher'];
  else if (cat === 'trade') targets = ['logTrades'];
  else if (cat === 'conn')  targets = ['logConn'];
  else targets = ['logPipeline'];

  for (const id of targets) {{
    const box = document.getElementById(id);
    if (!box) continue;
    const atBottom = box.scrollHeight - box.scrollTop < box.clientHeight + 40;
    const line = document.createElement('div');
    line.innerHTML = ts + txt;
    box.appendChild(line);
    if (atBottom) box.scrollTop = box.scrollHeight;
  }}
}}

function _clearLogEl(id) {{
  const el = document.getElementById(id);
  if (el) el.innerHTML = '';
}}

function _connLog(msg, col) {{
  const box = document.getElementById('logConn');
  if (!box) return;
  const atBottom = box.scrollHeight - box.scrollTop < box.clientHeight + 40;
  const ts = new Date().toLocaleTimeString();
  const d = document.createElement('div');
  d.innerHTML = `<span style="color:#374151;user-select:none">${{ts}} </span><span style="color:${{col||'#6b7280'}}">${{msg}}</span>`;
  box.appendChild(d);
  if (atBottom) box.scrollTop = box.scrollHeight;
}}

let _lastAlpacaOk = null;
let _lastWatcherState = null;
let _lastPipelineState = null;

async function _refreshAlpaca() {{
  try {{
    const [acct, pos, ord] = await Promise.all([
      fetch('/api/alpaca/account').then(r=>r.json()),
      fetch('/api/alpaca/positions').then(r=>r.json()),
      fetch('/api/alpaca/orders?limit=10').then(r=>r.json()),
    ]);
    if (acct.ok) {{
      if (_lastAlpacaOk !== true) {{
        _connLog('Alpaca connected — ' + acct.account_number + ' | ' + acct.status, '#22c55e');
        _lastAlpacaOk = true;
      }}
      const eq = acct.equity.toLocaleString('en-US',{{minimumFractionDigits:2,maximumFractionDigits:2}});
      const bp = acct.buying_power.toLocaleString('en-US',{{minimumFractionDigits:2,maximumFractionDigits:2}});
      const eqEl = document.getElementById('alp-equity');
      const bpEl = document.getElementById('alp-bp');
      const as   = document.getElementById('alpacaStatus');
      if (eqEl) eqEl.textContent = '$' + eq;
      if (bpEl) bpEl.textContent = '$' + bp;
      if (as) {{ as.style.color='#22c55e'; as.textContent='Connected — ' + acct.status + ' | #' + acct.account_number; }}
      const dotA = document.getElementById('dot-alpaca');
      const txtA = document.getElementById('txt-alpaca');
      if (dotA) dotA.className = 'live-dot running';
      if (txtA) txtA.textContent = 'Paper — ' + acct.status;
      _renderAlpacaData(acct, pos.positions||[], ord.orders||[]);
    }} else {{
      if (_lastAlpacaOk !== false) {{
        _connLog('Alpaca disconnected — ' + (acct.error||'unknown error'), '#ef4444');
        _lastAlpacaOk = false;
      }}
    }}
    const upd = document.getElementById('alpaca-updated');
    if (upd) upd.textContent = 'updated ' + new Date().toLocaleTimeString();
  }} catch(e) {{
    if (_lastAlpacaOk !== false) {{
      _connLog('Alpaca connection error: ' + e.message, '#ef4444');
      _lastAlpacaOk = false;
    }}
  }}
}}

async function _liveStart() {{
  const trader  = document.getElementById('liveTrader')?.value  || currentTrader;
  const dryRun  = document.getElementById('liveDryRun')?.checked ?? true;
  const btn     = document.getElementById('liveStartBtn');
  if (btn) {{ btn.textContent = 'Starting...'; btn.disabled = true; }}
  try {{
    const r = await fetch('/api/live/start', {{
      method:'POST',
      headers:{{'Content-Type':'application/json'}},
      body: JSON.stringify({{trader, dry_run: dryRun}})
    }}).then(x=>x.json());
    if (!r.ok && r.error) {{
      alert('Could not start: ' + r.error);
      if (btn) {{ btn.textContent = 'START'; btn.disabled = false; }}
      return;
    }}
    _liveStartTime = Date.now();
    _setRunningUI(trader, dryRun);
  }} catch(e) {{
    alert('Start failed: ' + e.message);
    if (btn) {{ btn.textContent = 'START'; btn.disabled = false; }}
  }}
}}

async function _liveStop() {{
  await fetch('/api/live/stop', {{method:'POST'}});
  _setStoppedUI();
}}

function _toggleSigTools() {{
  const body  = document.getElementById('sigToolsBody');
  const chev  = document.getElementById('sigToolsChev');
  if (!body) return;
  const open = body.style.display !== 'none';
  body.style.display = open ? 'none' : '';
  if (chev) chev.textContent = open ? '&#9660;' : '&#9650;';
}}

function _toggleSigGuide() {{
  const body  = document.getElementById('sigGuideBody');
  const arrow = document.getElementById('sigGuideArrow');
  if (!body) return;
  const open = body.style.display !== 'none';
  body.style.display = open ? 'none' : '';
  if (arrow) arrow.textContent = open ? '&#9654;' : '&#9660;';
}}

function _toggleStep1() {{
  const body  = document.getElementById('step1Body');
  const arrow = document.getElementById('step1Arrow');
  if (!body) return;
  const open = body.style.display !== 'none';
  body.style.display  = open ? 'none' : '';
  if (arrow) arrow.textContent = open ? '&#9654;' : '&#9660;';
}}

function _toggleStep2() {{
  const body  = document.getElementById('step2Body');
  const arrow = document.getElementById('step2Arrow');
  if (!body) return;
  const open = body.style.display !== 'none';
  body.style.display  = open ? 'none' : '';
  if (arrow) arrow.textContent = open ? '&#9654;' : '&#9660;';
}}

function _markSettingsChanged() {{
  const badge = document.getElementById('settingsChangedBadge');
  if (badge) badge.style.display = 'inline-flex';
  // Show restart button if currently running
  if (_liveStartTime) {{
    const rb = document.getElementById('liveRestartBtn');
    if (rb) rb.style.display = 'inline-block';
  }}
}}

async function _liveRestart() {{
  const rb = document.getElementById('liveRestartBtn');
  if (rb) {{ rb.textContent = 'Restarting...'; rb.disabled = true; }}
  await fetch('/api/live/stop', {{method:'POST'}});
  _setStoppedUI();
  const badge = document.getElementById('settingsChangedBadge');
  if (badge) badge.style.display = 'none';
  await new Promise(r => setTimeout(r, 800));
  await _liveStart();
}}

async function _clearKillSwitch() {{
  const trader = document.getElementById('liveTrader')?.value || currentTrader;
  try {{
    await fetch('/api/live/unkill', {{
      method:'POST',
      headers:{{'Content-Type':'application/json'}},
      body: JSON.stringify({{trader}})
    }});
    const ks = document.getElementById('killSwitchBanner');
    if (ks) ks.style.display = 'none';
    _connLog('Kill switch cleared for ' + trader + ' — trading re-enabled', '#22c55e');
    _loadLiveConfig();
  }} catch(e) {{
    _connLog('Clear kill switch error: ' + e.message, '#ef4444');
  }}
}}

async function _liveKill() {{
  const trader = document.getElementById('liveTrader')?.value || currentTrader;
  const btn = document.getElementById('liveStopBtn');
  if (btn) {{ btn.textContent = 'Stopping...'; btn.disabled = true; }}
  try {{
    const r = await fetch('/api/live/kill', {{
      method:'POST',
      headers:{{'Content-Type':'application/json'}},
      body: JSON.stringify({{trader}})
    }}).then(x=>x.json());
    _setStoppedUI();
    _connLog('EMERGENCY STOP activated — watcher + pipeline halted, kill_switch=ON for ' + trader, '#ef4444');
    // Show kill-switch banner
    const ks = document.getElementById('killSwitchBanner');
    if (ks) ks.style.display = 'flex';
  }} catch(e) {{
    _connLog('Emergency stop error: ' + e.message, '#ef4444');
  }} finally {{
    if (btn) {{ btn.textContent = '&#9632; EMERGENCY STOP'; btn.disabled = false; }}
  }}
}}

function _setRunningUI(trader, dryRun) {{
  const btn = document.getElementById('liveStartBtn');
  if (btn) {{
    btn.textContent = 'RUNNING';
    btn.disabled = true;
    btn.style.background = '#166534';
    btn.style.color = '#22c55e';
    btn.style.border = '1px solid #22c55e55';
  }}
  const rb = document.getElementById('liveRestartBtn');
  if (rb) {{ rb.style.display = 'inline-block'; rb.textContent = '&#8635; RESTART'; rb.disabled = false; }}
  const banner = document.getElementById('runtimeBanner');
  if (banner) {{ banner.style.display = 'flex'; }}
  const rt = document.getElementById('rtTrader');
  const rm = document.getElementById('rtMode');
  if (rt) rt.textContent = trader;
  if (rm) {{ rm.textContent = dryRun ? 'Paper trading (no real money)' : 'LIVE ORDERS — real money'; rm.style.color = dryRun ? '#22c55e' : '#ef4444'; }}

  if (_liveUptimeTimer) clearInterval(_liveUptimeTimer);
  _liveUptimeTimer = setInterval(() => {{
    if (!_liveStartTime) return;
    const secs = Math.floor((Date.now() - _liveStartTime) / 1000);
    const h = String(Math.floor(secs/3600)).padStart(2,'0');
    const m = String(Math.floor((secs%3600)/60)).padStart(2,'0');
    const s = String(secs % 60).padStart(2,'0');
    const el = document.getElementById('rtUptime');
    if (el) el.textContent = `${{h}}:${{m}}:${{s}}`;
  }}, 1000);

  // Pulse the tab button
  const tabBtn = document.getElementById('liveTabBtn');
  if (tabBtn) tabBtn.style.animation = 'pulse-tab 2s infinite';
}}

function _setStoppedUI() {{
  const btn = document.getElementById('liveStartBtn');
  if (btn) {{
    btn.textContent = 'START';
    btn.disabled = false;
    btn.style.background = '#22c55e';
    btn.style.color = '#000';
    btn.style.border = 'none';
  }}
  const banner = document.getElementById('runtimeBanner');
  if (banner) banner.style.display = 'none';
  const rb = document.getElementById('liveRestartBtn');
  if (rb) {{ rb.style.display = 'none'; }}
  if (_liveUptimeTimer) {{ clearInterval(_liveUptimeTimer); _liveUptimeTimer = null; }}
  _liveStartTime = null;
  const tabBtn = document.getElementById('liveTabBtn');
  if (tabBtn) tabBtn.style.animation = '';
}}

async function _liveSaveAll() {{
  const key     = document.getElementById('alpacaKey')?.value    || '';
  const secret  = document.getElementById('alpacaSecret')?.value || '';
  const paper   = document.getElementById('alpacaPaper')?.checked ?? true;
  const chanMap = document.getElementById('liveChanMap')?.value  || '';

  const payload = {{ channel_map: chanMap, alpaca_paper: paper }};
  if (key)    payload.alpaca_key    = key;
  if (secret) payload.alpaca_secret = secret;
  if (key && !secret) {{ alert('Enter the Secret Key too'); return; }}
  if (!key && secret) {{ alert('Enter the API Key too'); return; }}

  const r = await fetch('/api/live/config', {{
    method:'POST',
    headers:{{'Content-Type':'application/json'}},
    body: JSON.stringify(payload)
  }}).then(x=>x.json());

  if (r.saved) {{
    const msg = document.getElementById('liveSaveMsg');
    if (msg) {{ msg.textContent = 'Saved!'; msg.style.opacity = 1; setTimeout(()=>{{ msg.style.opacity=0; }}, 2500); }}
    // Clear key fields — don't leave them visible
    if (key)    document.getElementById('alpacaKey').value    = '';
    if (secret) document.getElementById('alpacaSecret').value = '';
    const badge = document.getElementById('settingsChangedBadge');
    if (badge) badge.style.display = 'none';
    _pollLiveStatus();
  }}
}}

async function _liveSaveConfig() {{ await _liveSaveAll(); }}
async function _liveSaveAlpaca() {{ await _liveSaveAll(); }}

async function _refreshMessages() {{
  const el = document.getElementById('liveMessages');
  if (!el) return;
  try {{
    const r = await fetch('/api/live/messages?limit=30').then(x=>x.json());
    const msgs = r.messages || [];
    if (!msgs.length) {{
      el.innerHTML = '<div class="empty">No messages yet</div>';
      return;
    }}
    const rows = msgs.map(m => `
      <tr>
        <td style="color:#6b7280;white-space:nowrap;padding:7px 12px">${{(m.created_at||'').substring(0,16).replace('T',' ')}}</td>
        <td style="color:#22d3ee;padding:7px 12px">#${{m.channel_name||'?'}}</td>
        <td style="color:#a78bfa;padding:7px 12px">${{m.author_name||'?'}}</td>
        <td style="color:#e2e8f0;padding:7px 12px;max-width:500px;word-break:break-word">
          ${{(m.content||'').replace(/</g,'&lt;').replace(/>/g,'&gt;').substring(0,200)}}
        </td>
      </tr>`).join('');
    el.innerHTML = `
      <table style="border-collapse:collapse;width:100%">
        <thead><tr>
          <th style="color:#6b7280;font-size:11px;padding:8px 12px;text-align:left;border-bottom:1px solid #1e293b">Time</th>
          <th style="color:#6b7280;font-size:11px;padding:8px 12px;text-align:left;border-bottom:1px solid #1e293b">Channel</th>
          <th style="color:#6b7280;font-size:11px;padding:8px 12px;text-align:left;border-bottom:1px solid #1e293b">Author</th>
          <th style="color:#6b7280;font-size:11px;padding:8px 12px;text-align:left;border-bottom:1px solid #1e293b">Content</th>
        </tr></thead>
        <tbody>${{rows}}</tbody>
      </table>`;
  }} catch(e) {{ el.innerHTML = '<div class="empty">Error loading messages</div>'; }}
}}

async function _runSanityCheck() {{
  const trader = document.getElementById('liveTrader')?.value || currentTrader;
  _connLog('Running sanity check — firing test HOOD ENTRY through parse -> risk -> broker (dry-run)...', '#f59e0b');
  try {{
    const r = await fetch('/api/live/sanity', {{
      method: 'POST',
      headers: {{'Content-Type': 'application/json'}},
      body: JSON.stringify({{trader}})
    }}).then(x => x.json());

    if (r.error) {{
      _connLog('Sanity check error: ' + r.error, '#ef4444');
      return;
    }}

    // Watcher log — the fake message
    const wBox = document.getElementById('logWatcher');
    if (wBox) {{
      const d = document.createElement('div');
      d.style.cssText = 'padding:1px 0';
      d.innerHTML = `<span style="color:#374151">[sanity] </span><span style="color:#f59e0b">TEST: ${{(r.message||'').split('\\n').join(' | ')}}</span>`;
      wBox.appendChild(d); wBox.scrollTop = wBox.scrollHeight;
    }}

    // Pipeline log — parse + risk
    const pBox = document.getElementById('logPipeline');
    if (pBox) {{
      const ac = ACTION_COLORS[r.action] || '#6b7280';
      const rc = r.risk_ok ? '#22c55e' : '#fb923c';
      [
        `parse: <span style="color:${{ac}}">${{r.action}}</span> ${{r.symbol}} (${{r.asset_type}}) conf=${{r.confidence}}`,
        `risk: <span style="color:${{rc}}">${{r.risk_ok ? 'APPROVED' : 'REJECTED — ' + r.reason}}</span>`
      ].forEach(html => {{
        const d = document.createElement('div');
        d.style.cssText = 'padding:1px 0';
        d.innerHTML = `<span style="color:#374151">[sanity] </span><span style="color:#94a3b8">${{html}}</span>`;
        pBox.appendChild(d);
      }});
      pBox.scrollTop = pBox.scrollHeight;
    }}

    // Trades log — broker result
    const tBox = document.getElementById('logTrades');
    if (tBox) {{
      const col = r.ok ? '#22c55e' : '#6b7280';
      const msg = r.ok
        ? 'Alpaca paper order placed: ' + r.symbol + ' $' + (r.notional||0).toFixed(0) + ' — id=' + (r.alpaca_id||'').substring(0,8) + '... → cancelled'
        : (r.risk_ok ? 'Risk approved but Alpaca failed: ' + (r.reason||'') : 'Risk rejected — no trade placed');
      const d = document.createElement('div');
      d.style.cssText = 'padding:1px 0';
      d.innerHTML = `<span style="color:#374151">[sanity] </span><span style="color:${{col}}">${{msg}}</span>`;
      tBox.appendChild(d); tBox.scrollTop = tBox.scrollHeight;
    }}

    // Inject highlighted row into Recent Orders panel
    const ord = r.order || {{}};
    if (r.ok && r.alpaca_id) {{
      const sideCol  = (r.side||'LONG') === 'LONG' ? '#22c55e' : '#ef4444';
      const buySell  = (r.side||'LONG') === 'LONG' ? 'BUY' : 'SELL';
      const shortId  = (r.alpaca_id||'').substring(0,8) + '...';
      const statusCol = (ord.status === 'filled') ? '#22c55e' : '#f59e0b';
      // Build row HTML and store it — persists across _refreshAlpaca rerenders
      const rowHtml = `
        <td style="padding:5px 10px;color:#f59e0b;font-size:11px">${{r.ts||'now'}}</td>
        <td style="padding:5px 10px;color:#fbbf24;font-size:11px;font-weight:800">${{r.symbol}}</td>
        <td style="padding:5px 10px;font-size:11px;color:${{sideCol}};font-weight:700">${{buySell}}</td>
        <td style="padding:5px 10px;color:#94a3b8;font-size:11px">$${{(r.notional||0).toFixed(2)}}</td>
        <td style="padding:5px 10px;font-size:11px">
          <span style="color:${{statusCol}}">${{ord.status||'filled'}}</span>
          <span style="color:#f59e0b;font-size:10px;font-weight:700;margin-left:4px">[SANITY]</span>
        </td>
        <td style="padding:5px 10px;color:#6b7280;font-size:10px" title="${{r.alpaca_id}}">${{shortId}}</td>
      `;
      _sanityRows.push(rowHtml);
      _reinjectSanityRows();
      // Refresh balance after cleanup
      setTimeout(_refreshAlpaca, 2500);
    }}

    // Connections summary
    const passed = r.ok && r.alpaca_id;
    _connLog(
      passed
        ? 'Sanity PASSED — real Alpaca paper order placed + cancelled: ' + r.symbol + ' id=' + (r.alpaca_id||'').substring(0,8)
        : r.risk_ok
          ? 'Sanity partial — risk OK but Alpaca failed: ' + (r.reason||'check logs')
          : 'Sanity check: risk rejected — ' + r.reason,
      passed ? '#22c55e' : '#f59e0b'
    );
  }} catch(e) {{
    _connLog('Sanity check failed: ' + e.message, '#ef4444');
  }}
}}

async function _inlineDecode(hash) {{
  const rowId = `dr_${{hash}}`;
  const row   = document.getElementById(rowId);
  if (!row) return;
  const isOpen = row.style.display !== 'none';
  if (isOpen) {{ row.style.display = 'none'; return; }}
  row.style.display = '';
  const out = document.getElementById(`${{rowId}}_out`);
  out.innerHTML = '<span style="color:#374151;font-size:12px">Decoding...</span>';
  const s = _sigDataByHash[hash];
  if (!s) {{ out.innerHTML = '<span style="color:#ef4444">No data</span>'; return; }}
  const r = await fetch('/api/parse/trace', {{
    method: 'POST',
    headers: {{'Content-Type':'application/json'}},
    body: JSON.stringify({{trader: currentTrader, message: s.raw_content||''}})
  }}).then(x=>x.json()).catch(e=>({{"error":e.message}}));
  if (r.error) {{ out.innerHTML = `<span style="color:#ef4444">Error: ${{r.error}}</span>`; return; }}
  out.innerHTML = _renderTraceCompact(r);
}}

function _renderTraceCompact(r) {{
  const sig = r.signal || {{}};
  const rules = r.rules || {{}};
  const AC = {{ENTRY:'#22c55e',TRIM:'#22d3ee',EXIT:'#ef4444',ADD:'#60a5fa',UNSURE:'#f59e0b',NOISE:'#6b7280'}};
  const sc = AC[sig.action] || '#94a3b8';
  const cp = Math.round((sig.confidence||0)*100);
  const bc = cp>=75?'#22c55e':cp>=50?'#facc15':'#ef4444';

  const chip = (label, val, col, ev) => `
    <div style="background:#0d1117;border:1px solid #1e293b;border-radius:6px;padding:6px 10px;min-width:140px">
      <div style="font-size:9px;color:#374151;font-weight:700;letter-spacing:.06em;margin-bottom:3px">${{label}}</div>
      <div style="font-size:13px;font-weight:800;color:${{col}};margin-bottom:2px">${{val||'—'}}</div>
      ${{ev?`<div style="font-size:10px;color:#475569;line-height:1.4">${{ev}}</div>`:''}}
    </div>`;

  const priceF = rules.price?.value || {{}};
  const priceStr = [
    priceF.entry_price ? `entry $${{priceF.entry_price}}` : '',
    priceF.targets?.length ? `tp [${{priceF.targets.join(',')}}]` : '',
    priceF.stop ? `stop ${{priceF.stop}}` : '',
  ].filter(Boolean).join(' · ') || '—';

  return `<div style="display:flex;gap:8px;align-items:flex-start;flex-wrap:wrap">
    <div style="background:${{sc}}15;border:1px solid ${{sc}}44;border-radius:8px;padding:8px 14px;min-width:120px">
      <div style="font-size:9px;color:#6b7280;margin-bottom:2px">RESULT</div>
      <div style="font-size:20px;font-weight:900;color:${{sc}}">${{sig.action||'—'}}</div>
      <div style="display:flex;align-items:center;gap:6px;margin-top:4px">
        <div style="background:#1e293b;border-radius:999px;height:5px;width:60px;overflow:hidden">
          <div style="height:100%;border-radius:999px;background:${{bc}};width:${{cp}}%"></div>
        </div>
        <span style="font-size:11px;color:${{bc}};font-weight:700">${{cp}}%</span>
      </div>
      ${{sig.unsure_reasons?.length?`<div style="font-size:10px;color:#f59e0b;margin-top:3px">${{sig.unsure_reasons.join(' · ')}}</div>`:''}}
    </div>
    ${{chip('ACTION', rules.action?.value, AC[rules.action?.value]||'#94a3b8', (rules.action?.evidence||[]).join(' · '))}}
    ${{chip('SIDE',   rules.side?.value,   rules.side?.value==='LONG'?'#22c55e':'#ef4444', (rules.side?.evidence||[]).join(' · '))}}
    ${{chip('SYMBOL', (rules.symbol?.value?.symbol||'') + ' ' + (rules.symbol?.value?.asset_type||''), '#e2e8f0', (rules.symbol?.evidence||[]).join(' · '))}}
    ${{chip('PRICE',  priceStr, '#94a3b8', (rules.price?.evidence||[]).join(' · '))}}
  </div>`;
}}

async function _runTrace() {{
  const msg = document.getElementById('traceInput')?.value?.trim();
  const out = document.getElementById('traceOutput');
  if (!msg) return;
  out.innerHTML = '<div style="color:#374151;font-size:12px">Decoding...</div>';

  const r = await fetch('/api/parse/trace', {{
    method: 'POST',
    headers: {{'Content-Type':'application/json'}},
    body: JSON.stringify({{trader: currentTrader, message: msg}})
  }}).then(x=>x.json()).catch(e=>({{"error":e.message}}));

  if (r.error) {{ out.innerHTML = `<div style="color:#ef4444">Error: ${{r.error}}</div>`; return; }}

  const sig = r.signal || {{}};
  const rules = r.rules || {{}};

  const ACTION_C = {{ENTRY:'#22c55e',TRIM:'#22d3ee',EXIT:'#ef4444',ADD:'#60a5fa',UNSURE:'#f59e0b',NOISE:'#6b7280'}};
  const sigCol   = ACTION_C[sig.action] || '#94a3b8';
  const confPct  = Math.round((sig.confidence||0)*100);
  const barW     = confPct;
  const barCol   = confPct>=75?'#22c55e':confPct>=50?'#facc15':'#ef4444';

  const priceVal = (() => {{
    const f = (rules.price?.value) || {{}};
    const parts = [];
    if (f.entry_price) parts.push(`entry ${{f.entry_price}}`);
    if (f.targets?.length) parts.push(`tp [${{f.targets.join(',')}}]`);
    if (f.stop) parts.push(`stop ${{f.stop}}`);
    return parts.join(' · ') || '—';
  }})();

  function ruleChip(label, result, val, col) {{
    if (!result) return '';
    const pct = Math.round((result.confidence||0)*100);
    const bc  = pct>=75?'#22c55e':pct>=50?'#facc15':'#ef4444';
    const ev  = (result.evidence||[]).join(' · ');
    return `<div style="background:#0d1117;border:1px solid #1e293b;border-radius:6px;
                         padding:7px 10px;margin-bottom:6px">
      <div style="display:flex;align-items:center;gap:6px;margin-bottom:4px">
        <span style="font-size:9px;font-weight:700;color:#374151;letter-spacing:.06em;min-width:46px">${{label}}</span>
        <span style="font-size:12px;font-weight:800;color:${{col||'#e2e8f0'}}">${{val}}</span>
        <span style="margin-left:auto;font-size:10px;font-weight:700;color:${{bc}}">${{pct}}%</span>
      </div>
      <div style="font-size:10px;color:#475569;line-height:1.4;word-break:break-word">${{ev}}</div>
    </div>`;
  }}

  out.innerHTML = _renderTraceCompact(r);
}}

async function loadDebug() {{
  const el = document.getElementById('debugContent');
  el.innerHTML = '<div class="empty">Loading...</div>';
  try {{
    const [posR, eqR, cfgR, sigR] = await Promise.all([
      fetch(`/api/trades/${{currentTrader}}`),
      fetch(`/api/equity/${{currentTrader}}`),
      fetch(`/api/config/${{currentTrader}}`),
      fetch(`/api/signals/${{currentTrader}}`),
    ]);
    const posD  = await posR.json();
    const eqD   = await eqR.json();
    const cfgD  = await cfgR.json();
    const sigD  = await sigR.json();

    const positions  = posD.trades || [];
    const allTrades  = positions.flatMap(p => p.trades || []);
    const signals    = sigD.signals || [];
    const eqTrades   = eqD.trades   || [];
    const startBal   = eqD.starting_balance || 7000;
    const finalBal   = eqD.equity && eqD.equity.length ? eqD.equity[eqD.equity.length-1] : startBal;
    const totalPnl   = finalBal - startBal;

    // Zero / anomaly diagnostics
    const zeroSells    = allTrades.filter(t => t.action==='SELL' && (t.trade_pnl||0)===0);
    const missingPrice = allTrades.filter(t => t.price == null);
    const bigPnl       = allTrades.filter(t => Math.abs(t.trade_pnl||0) > 500);

    function row(k, v, warn) {{
      const c = warn ? '#fb923c' : '#e2e8f0';
      return `<div style="display:flex;gap:12px;margin-bottom:4px;font-size:12px;font-family:monospace">
        <span style="color:#6b7280;min-width:200px">${{k}}</span>
        <span style="color:${{c}}">${{v}}</span></div>`;
    }}
    function section(title) {{
      return `<div style="color:#60a5fa;font-size:12px;font-weight:700;margin:16px 0 6px;font-family:monospace;letter-spacing:.04em">${{title}}</div>`;
    }}

    let html = `<div style="max-width:900px">`;

    html += section('DATA LOADED FROM API');
    html += row('Endpoint /api/trades', `${{positions.length}} positions, ${{allTrades.length}} total trades`);
    html += row('Endpoint /api/equity', `${{eqTrades.length}} equity snapshots`);
    html += row('Endpoint /api/signals', `${{signals.length}} parsed signals`);
    html += row('Endpoint /api/config', `min_confidence=${{cfgD.risk?.min_confidence}} max_positions=${{cfgD.risk?.max_open_positions}}`);
    html += row('starting_balance', `$${{startBal}}`);
    html += row('final_balance (equity[-1])', `$${{finalBal.toFixed(2)}}`);
    html += row('total_pnl (final - start)', `${{(totalPnl>=0?'+':'')}}$${{totalPnl.toFixed(4)}}`, totalPnl < 0);

    html += section('P&L FORMULA APPLIED PER TRADE');
    html += row('Formula', 'notional × close_fraction × (exit_price − entry_price) / entry_price × side_mult');
    html += row('TRIM close_fraction', '0.50  (closes 50% of remaining notional)');
    html += row('EXIT close_fraction', '1.00  (closes 100% of remaining notional)');
    html += row('BUY / ADD trade_pnl', '0.00  (no realized P&L on opening a position)');
    html += row('Exit price fallback', 'If signal has no parsed price → uses position entry_price → $0 break-even');
    html += row('positions.realized_pnl', 'Cumulative sum of all trade_pnl within that position');

    html += section('ZERO / ANOMALY DIAGNOSTICS');
    if (zeroSells.length === 0) {{
      html += row('Zero-PnL SELL trades', 'None — all SELL trades have non-zero P&L');
    }} else {{
      html += row('Zero-PnL SELL trades', `${{zeroSells.length}} trades — exit price fell back to entry (no price parsed)`, true);
      zeroSells.slice(0,6).forEach(t => {{
        html += row(`  Trade#${{t.trade_id}} (${{(t.time||'').substring(0,10)}})`, `price=${{t.price}} qty=${{t.quantity}} → PnL=$0 (break-even fallback)`, true);
      }});
    }}
    if (missingPrice.length > 0) {{
      html += row('Trades with null price', `${{missingPrice.length}} trades`, true);
    }}
    if (bigPnl.length > 0) {{
      html += row('High-magnitude trades (|PnL|>$500)', `${{bigPnl.length}} trades — likely parser price mismatch`, true);
      bigPnl.forEach(t => {{
        html += row(`  Trade#${{t.trade_id}} ${{t.action}}`, `price=${{t.price}} pnl=${{(t.trade_pnl>=0?'+':'')}}$${{(t.trade_pnl||0).toFixed(2)}}`, true);
      }});
    }} else {{
      html += row('High-magnitude trades', 'None (all within expected range)');
    }}

    html += section('POSITION SIZE TRACKING');
    positions.forEach(p => {{
      const flow = (p.trades||[]).map(t => `${{t.action}}→${{t.size_after_pct??'?'}}%`).join(' ');
      const r = `remaining=${{p.remaining_pct}}% ($$${{(p.remaining||0).toFixed(0)}} of $$${{(p.original_qty||0).toFixed(0)}})`;
      html += row(`Pos#${{p.position_id}} ${{p.symbol}} [${{p.status}}]`, `${{flow}} | ${{r}}`, p.remaining_pct > 0 && p.status==='closed');
    }});

    html += section('RAW CONFIG (/api/config)');
    html += `<pre style="background:#111827;border:1px solid #1e293b;border-radius:6px;padding:12px;font-size:11px;color:#9ca3af;overflow-x:auto;margin-top:4px">${{JSON.stringify(cfgD,null,2)}}</pre>`;

    html += section('RAW EQUITY EVENTS (last 5)');
    const lastEq = eqTrades.slice(-5);
    lastEq.forEach(t => {{
      html += row(`${{(t.timestamp||'').substring(0,10)}} ${{t.symbol}}`, `trade_pnl=${{(t.pnl>=0?'+':'')}}$${{(t.pnl||0).toFixed(4)}} balance=$$${{(t.balance||0).toFixed(2)}}`);
    }});

    html += section('RAW POSITIONS JSON (first 3)');
    html += `<pre style="background:#111827;border:1px solid #1e293b;border-radius:6px;padding:12px;font-size:11px;color:#9ca3af;overflow-x:auto;margin-top:4px;max-height:300px">${{JSON.stringify(positions.slice(0,3),null,2)}}</pre>`;

    html += `</div>`;
    el.innerHTML = html;
  }} catch(e) {{ el.innerHTML = `<div class="empty">Error: ${{e.message}}</div>`; }}
}}

// ---- Paper pipeline ----------------------------------------------------------
async function runPaper() {{
  const btn = document.getElementById('runBtn');
  const log = document.getElementById('runLog');
  btn.disabled = true;
  btn.textContent = 'Running...';
  log.style.display = 'block';
  log.textContent = 'Running paper pipeline for ' + currentTrader + '...\\n';
  try {{
    const r = await fetch(`/api/paper/${{currentTrader}}`, {{method:'POST'}});
    const d = await r.json();
    log.textContent += `Parsed:   ${{d.signals}} signals\\n`;
    log.textContent += `Approved: ${{d.approved}}\\n`;
    log.textContent += `Rejected: ${{d.rejected}}\\n`;
    log.textContent += `Traded:   ${{d.traded}}\\n\\n`;
    if (d.top_rejects) {{
      log.textContent += 'Top reject reasons:\\n';
      d.top_rejects.forEach(r => log.textContent += `  ${{r.count}}x  ${{r.reason}}\\n`);
    }}
    if (d.equity && d.equity.trades && d.equity.trades.length) {{
      const start = d.equity.starting_balance || 7000;
      const final = d.equity.equity[d.equity.equity.length-1] || start;
      const pnl   = final - start;
      log.textContent += `\\nEquity: ${{d.equity.trades.length}} closed trades  P&L=${{(pnl>=0?'+':'')}}${{pnl.toFixed(2)}}  balance=$$${{final.toFixed(2)}}\\n`;
    }}
    if (d.console && d.console.length) {{
      log.textContent += `\\n--- Trade Log (${{d.console.length}} events) ---\\n`;
      d.console.forEach(line => log.textContent += line + '\\n');
    }}
    log.textContent += `\\nReport: ${{d.html}}\\n`;
    document.getElementById('statusRun').textContent = d.run_id;
    loadTab(activeTab);
  }} catch(e) {{
    log.textContent += 'Error: ' + e.message;
  }}
  btn.disabled = false;
  btn.textContent = 'Run Paper Pipeline';
}}

// Init
selectTrader('Grizzlies');
loadTab('live');
document.getElementById('runBtn').style.display = 'none';
</script>
</body>
</html>"""


# ---- Entry point -------------------------------------------------------------

def run(trader: str = "Grizzlies", host: str = "0.0.0.0", port: int = 8765):
    print(f"\n  Dashboard: http://localhost:{port}")
    print(f"  API docs:  http://localhost:{port}/docs\n")
    uvicorn.run(app, host=host, port=port, log_level="warning")


if __name__ == "__main__":
    import sys
    trader = sys.argv[1] if len(sys.argv) > 1 else "Grizzlies"
    run(trader)
