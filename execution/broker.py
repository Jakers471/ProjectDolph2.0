"""Dry-run broker adapter.

submit_order(signal, db, run_id, dry_run=True) -> trade_id | None

PnL model (percentage-based, fixed notional):
  - Every ENTRY risks NOTIONAL dollars (default $100, config: broker.trade_notional)
  - PnL = NOTIONAL * (exit_price - entry_price) / entry_price * side_multiplier
  - TRIM closes 50%: PnL = 0.5 * NOTIONAL * pct_change
  - EXIT closes 100%: PnL = NOTIONAL * pct_change
  - If no exit price is parsed from the signal, falls back to the position's
    entry price (break-even, PnL=0) rather than a fake default.

Position linkage:
  - Every trade stores position_id pointing to its parent position row.
  - close_fraction: 0.0 = ENTRY/ADD, 0.5 = TRIM, 1.0 = EXIT
  - trade_pnl: realized dollar P&L for this specific trade event
  - positions.realized_pnl accumulates across TRIMs + EXIT
  - positions.remaining tracks remaining notional after each partial close
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from parsing.signals_schema import Signal
    from data.paper_db import DB

NOTIONAL = 100.0   # fixed dollar amount risked per ENTRY trade

# Per-asset price plausibility: (min, max) in USD.
# Catches BTC entered at $1.10 (option premium bleed) or MARA at $59,750 (BTC price bleed).
_PRICE_BOUNDS: dict[str, tuple[float, float]] = {
    # CRYPTO spot prices
    "BTC":  (5_000,   250_000),
    "ETH":  (100,     20_000),
    "SOL":  (5,       2_000),
    "BNB":  (50,      2_000),
    "AVAX": (3,       500),
    "LINK": (1,       200),
    "TAO":  (10,      2_000),
    "SUI":  (0.3,     100),
    "INJ":  (1,       200),
    "HYPE": (2,       500),
    "XRP":  (0.1,     50),
    "DOGE": (0.01,    5),
    "ONDO": (0.1,     20),
    "ORDI": (5,       500),
}
# OPTION premiums are per-contract (100 shares), typically $0.01–$50
_OPTION_MAX = 500.0


def _price_plausible(symbol: str, asset_type: str, price: float) -> bool:
    if asset_type == "OPTION" and price > _OPTION_MAX:
        return False
    bounds = _PRICE_BOUNDS.get(symbol)
    if bounds and asset_type == "CRYPTO":
        lo, hi = bounds
        if price < lo or price > hi:
            return False
    return True


def submit_order(signal: "Signal", db: "DB", run_id: str = "",
                 dry_run: bool = True, sig_id: int | None = None) -> int | None:
    from config.loader import get_config
    cfg      = get_config(signal.analyst)
    notional = cfg.get("broker", {}).get("trade_notional", NOTIONAL)

    if sig_id is None:
        sig_id = db.insert_signal(signal, run_id)
    action = signal.action

    # ---- ENTRY -----------------------------------------------------------------
    if action == "ENTRY":
        entry_price = signal.entry_price
        if not entry_price:
            return None  # no price = can't size this trade

        asset_type = signal.asset_type or ""
        sym = signal.symbol or ""
        if not _price_plausible(sym, asset_type, entry_price):
            print(f"  [SKIP] implausible entry price: {sym} {asset_type} @{entry_price}")
            return None

        pos_side = signal.side or "LONG"
        # LONG = BUY to open, SHORT = SELL to open (short selling)
        open_action = "BUY" if pos_side == "LONG" else "SELL_SHORT"

        pos_id = db.open_position(
            analyst     = signal.analyst,
            symbol      = signal.symbol or "UNKNOWN",
            asset_type  = signal.asset_type or "",
            side        = pos_side,
            entry_price = entry_price,
            quantity    = notional,
            opened_at   = signal.timestamp,
        )
        trade_id = db.insert_trade(
            signal_id      = sig_id,
            position_id    = pos_id,
            analyst        = signal.analyst,
            symbol         = signal.symbol or "UNKNOWN",
            asset_type     = signal.asset_type or "",
            side           = pos_side,
            action         = open_action,
            quantity       = notional,
            price          = entry_price,
            close_fraction = 0.0,
            trade_pnl      = 0.0,
            dry_run        = dry_run,
            status         = "filled",
        )
        _print_order(open_action, signal, notional, entry_price, dry_run)
        return trade_id

    # ---- EXIT / TRIM -----------------------------------------------------------
    if action in ("EXIT", "TRIM"):
        pos = db.get_open_position(signal.analyst, signal.symbol or "")
        if not pos:
            return None

        pos_entry    = pos["entry_price"] or 0.0
        pos_notional = pos["remaining"] if pos["remaining"] is not None else (pos["quantity"] or notional)
        partial      = (action == "TRIM")
        close_frac   = 0.5 if partial else 1.0

        # Stop trimming dust positions — less than $1 remaining is noise
        if pos_notional < 1.0 and partial:
            return None

        # Exit price priority:
        #   1. Absolute price parsed from message ("closed @1.85")
        #   2. Alpaca historical bar at signal timestamp  (CRYPTO / STOCK only)
        #   3. Percentage reported in message ("up 25%") → synthetic price
        #   4. Break-even fallback (entry price, PnL = $0)
        exit_pct = getattr(signal, "exit_pct", None)
        if signal.entry_price:
            exit_price = signal.entry_price
        else:
            from data.price_fetcher import get_exit_price as _fetch
            # Use position's asset_type — the exit signal often mis-classifies it
            pos_asset = pos["asset_type"] or signal.asset_type
            market_price = _fetch(
                symbol      = signal.symbol or "",
                asset_type  = pos_asset,
                timestamp   = str(signal.timestamp),
                db          = db,
            )
            if market_price:
                exit_price = market_price
            elif exit_pct is not None and pos_entry:
                exit_price = round(pos_entry * (1 + exit_pct / 100.0), 6)
            else:
                exit_price = pos_entry  # break-even fallback
        if not exit_price or not pos_entry:
            return None

        # Sanity: implausible price ratios are parser misfires, not real moves.
        # OPTIONS: >5x is already suspicious (premium vs stock price bleed).
        # All others: >200x is never a real trade move.
        pos_asset = (pos["asset_type"] or signal.asset_type or "")
        ratio = exit_price / pos_entry if pos_entry else 1
        limit = 5 if pos_asset == "OPTION" else 200
        if ratio > limit or ratio < (1 / limit):
            print(f"  [WARN] price sanity: {signal.symbol} exit={exit_price} "
                  f"vs entry={pos_entry} ({ratio:.1f}x) -- break-even fallback")
            exit_price = pos_entry

        pos_side   = pos["side"] or "LONG"
        side_mult  = 1.0 if pos_side == "LONG" else -1.0
        pct_change = (exit_price - pos_entry) / pos_entry
        dollar_pnl = round(pos_notional * close_frac * pct_change * side_mult, 4)

        # LONG exit = SELL (sell what we own)
        # SHORT exit = BUY_COVER (buy back the short)
        close_action = "SELL" if pos_side == "LONG" else "BUY_COVER"

        # Update position: remaining_qty, cumulative realized_pnl, status
        db.update_position_after_trade(
            position_id    = pos["id"],
            close_fraction = close_frac,
            trade_pnl      = dollar_pnl,
            closed_at      = signal.timestamp,
        )

        sell_qty = pos_notional * close_frac
        trade_id = db.insert_trade(
            signal_id      = sig_id,
            position_id    = pos["id"],
            analyst        = signal.analyst,
            symbol         = signal.symbol or "UNKNOWN",
            asset_type     = signal.asset_type or "",
            side           = pos_side,
            action         = close_action,
            quantity       = sell_qty,
            price          = exit_price,
            close_fraction = close_frac,
            trade_pnl      = dollar_pnl,
            dry_run        = dry_run,
            status         = "filled",
        )

        pct_str = f"{pct_change*100:+.2f}%"
        _print_order(close_action, signal, sell_qty, exit_price, dry_run,
                     pnl=dollar_pnl, pct=pct_str)

        # Equity snapshot — cumulative P&L from all closed/trimmed trades
        curve = db.get_equity_curve(signal.analyst)
        prev  = curve[-1]["cumulative_pnl"] if curve else 0.0
        db.insert_equity_snapshot(signal.analyst, signal.timestamp,
                                  prev + dollar_pnl, trade_id)
        return trade_id

    # ---- ADD -------------------------------------------------------------------
    if action == "ADD":
        add_price = signal.entry_price
        if not add_price:
            return None

        pos = db.get_open_position(signal.analyst, signal.symbol or "")
        pos_id = pos["id"] if pos else None

        trade_id = db.insert_trade(
            signal_id      = sig_id,
            position_id    = pos_id,
            analyst        = signal.analyst,
            symbol         = signal.symbol or "UNKNOWN",
            asset_type     = signal.asset_type or "",
            side           = signal.side or "LONG",
            action         = "ADD",
            quantity       = notional * 0.5,
            price          = add_price,
            close_fraction = 0.0,
            trade_pnl      = 0.0,
            dry_run        = dry_run,
            status         = "filled",
        )
        _print_order("ADD", signal, notional * 0.5, add_price, dry_run)
        return trade_id

    return None


def force_close_all(analyst: str, db: "DB", timestamp: str,
                    run_id: str = "", dry_run: bool = True) -> int:
    """Close all remaining open/partial positions at break-even (corpus ended).

    Called at the end of a paper run to avoid leaving ghost open positions
    when the corpus has no exit message for a trade.
    """
    rows = db.con.execute(
        "SELECT id, symbol, side, entry_price, remaining "
        "FROM positions WHERE analyst=? AND status IN ('open','partial')",
        (analyst,),
    ).fetchall()

    closed = 0
    for pos_id, symbol, side, entry_price, remaining in rows:
        if not entry_price or not remaining or remaining < 1.0:
            continue
        # Insert a synthetic EXIT signal into signals table
        from parsing.signals_schema import Signal
        fake_sig = Signal(
            analyst=analyst,
            timestamp=timestamp,
            raw_content="[corpus-end auto-close]",
            action="EXIT",
            confidence=1.0,
            side=side,
            symbol=symbol,
            entry_price=entry_price,  # same as entry = break-even
        )
        sig_id = db.insert_signal(fake_sig, run_id)
        db.update_position_after_trade(
            position_id=pos_id,
            close_fraction=1.0,
            trade_pnl=0.0,
            closed_at=timestamp,
        )
        close_action = "SELL" if side == "LONG" else "BUY_COVER"
        db.insert_trade(
            signal_id=sig_id,
            position_id=pos_id,
            analyst=analyst,
            symbol=symbol,
            asset_type="",
            side=side,
            action=close_action,
            quantity=remaining,
            price=entry_price,
            close_fraction=1.0,
            trade_pnl=0.0,
            dry_run=dry_run,
            status="corpus_end",
        )
        tag = "[DRY-RUN] " if dry_run else "[LIVE]    "
        print(f"  {tag}[corpus-end] {close_action} {symbol:6} "
              f"notional=${remaining:.0f}  @{entry_price}  pnl=$0.00 (no exit in corpus)")
        closed += 1
    return closed


def _print_order(order_type: str, signal: "Signal", notional: float,
                 price: float, dry_run: bool,
                 pnl: float | None = None, pct: str = ""):
    tag     = "[DRY-RUN] " if dry_run else "[LIVE]    "
    pnl_str = f"  pnl={pnl:+.4f} ({pct})" if pnl is not None else ""
    print(f"  {tag}{order_type:4} {signal.symbol or '?':6} "
          f"notional=${notional:.0f}  @{price}  "
          f"analyst={signal.analyst}{pnl_str}")
