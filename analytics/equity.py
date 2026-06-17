"""Equity curve analytics.

build_equity_curve(analyst, db) -> list of dicts with balance, trade_pnl, symbol, etc.
generate_chart(analyst, db)     -> Path to PNG (requires matplotlib)
chart_data(analyst, db)         -> dict ready to embed in HTML report
order_book_data(analyst, db)    -> position-grouped list for Order Book tab
"""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from data.paper_db import DB

PROJECT = Path(__file__).resolve().parent.parent


def _starting_balance(analyst: str) -> float:
    from config.loader import get_config
    return get_config(analyst).get("broker", {}).get("starting_balance", 7000.0)


def build_equity_curve(analyst: str, db: "DB") -> list[dict]:
    """Build equity curve from equity_snapshots (authoritative cumulative P&L source)."""
    events = db.get_equity_events(analyst)
    start  = _starting_balance(analyst)
    curve  = []

    for ev in events:
        cum_pnl = ev.get("cumulative_pnl") or 0.0
        curve.append({
            "timestamp":      ev.get("timestamp") or "",
            "balance":        round(start + cum_pnl, 4),
            "cumulative_pnl": round(cum_pnl, 4),
            "trade_pnl":      round(ev.get("trade_pnl") or 0.0, 4),
            "symbol":         ev.get("symbol") or "?",
            "side":           ev.get("side") or "",
            "entry_price":    ev.get("entry_price"),
            "exit_price":     ev.get("trade_price"),
        })
    return curve


def chart_data(analyst: str, db: "DB") -> dict:
    """Return JSON-serializable dict for embedding in the HTML report."""
    curve = build_equity_curve(analyst, db)
    start = _starting_balance(analyst)

    if not curve:
        return {
            "labels":           [],
            "equity":           [],
            "trades":           [],
            "starting_balance": start,
        }

    return {
        "labels":           [p["timestamp"][:10] for p in curve],
        "equity":           [p["balance"] for p in curve],
        "starting_balance": start,
        "trades": [
            {
                "symbol":    p["symbol"],
                "pnl":       p["trade_pnl"],
                "side":      p["side"],
                "entry":     p["entry_price"],
                "exit":      p["exit_price"],
                "timestamp": p["timestamp"],
                "balance":   p["balance"],
            }
            for p in curve
        ],
    }


def order_book_data(analyst: str, db: "DB") -> list:
    """Return position-grouped list for the Order Book tab.

    Each item = one position with a nested 'trades' list.
    Includes remaining size %, cumulative P&L, and concurrent positions.
    """
    positions = db.get_positions_with_trades(analyst)

    # Detect concurrent open positions (potential hedges / simultaneous exposure)
    # For each position: which other positions were open at the same time?
    for pos in positions:
        opened = pos["opened_at"]
        closed = pos["closed_at"] or "9999"
        concurrent = [
            p["symbol"] for p in positions
            if p["position_id"] != pos["position_id"]
            and p["symbol"] != pos["symbol"]
            and p["opened_at"] <= closed
            and (p["closed_at"] or "9999") >= opened
        ]
        pos["concurrent_symbols"] = list(dict.fromkeys(concurrent))  # deduplicate, preserve order

    return positions


def generate_chart(analyst: str, db: "DB") -> Path | None:
    """Write equity curve PNG to data/<analyst>/profile/equity_curve.png."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return None

    curve = build_equity_curve(analyst, db)
    if not curve:
        return None

    start      = _starting_balance(analyst)
    timestamps = [p["timestamp"][:10] for p in curve]
    balances   = [p["balance"] for p in curve]
    pnls       = [p["trade_pnl"] for p in curve]

    timestamps = ["start"] + timestamps
    balances   = [start]   + balances

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 7),
                                    gridspec_kw={"height_ratios": [3, 1]})
    fig.patch.set_facecolor("#111827")
    for ax in (ax1, ax2):
        ax.set_facecolor("#1f2937")
        ax.tick_params(colors="#9ca3af")
        for sp in ax.spines.values():
            sp.set_color("#374151")

    color = "#22c55e" if balances[-1] >= start else "#ef4444"
    ax1.plot(range(len(balances)), balances, color=color, linewidth=2)
    ax1.fill_between(range(len(balances)), balances, start,
                     alpha=0.15, color=color)
    ax1.axhline(start, color="#374151", linewidth=0.8, linestyle="--")
    ax1.set_title(f"{analyst} — Equity Curve  (start=${start:,.0f})",
                  color="#f9fafb", fontsize=13, pad=10)
    ax1.set_ylabel("Balance ($)", color="#9ca3af")
    ax1.set_xticks([])

    bar_colors = ["#22c55e" if p >= 0 else "#ef4444" for p in pnls]
    ax2.bar(range(len(pnls)), pnls, color=bar_colors, width=0.8)
    ax2.axhline(0, color="#374151", linewidth=0.8)
    ax2.set_ylabel("Trade PnL ($)", color="#9ca3af")
    step = max(1, len(timestamps) // 10)
    ax2.set_xticks(range(0, len(pnls), step))
    ax2.set_xticklabels(timestamps[1::step], rotation=30, ha="right",
                         color="#9ca3af", fontsize=8)

    plt.tight_layout()
    out_dir = PROJECT / "data" / analyst / "profile"
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / "equity_curve.png"
    plt.savefig(out, dpi=120, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    return out
