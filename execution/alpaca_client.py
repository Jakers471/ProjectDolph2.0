"""Alpaca paper trading client wrapper.

Thin layer over alpaca-py TradingClient for use in the dashboard and live pipeline.
Keys come from .env — never hardcoded.

Usage:
    from execution.alpaca_client import get_client, account_snapshot, positions_snapshot
    snap = account_snapshot()   # dict ready for JSON serialization
    pos  = positions_snapshot() # list of dicts
"""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent


def _load_env():
    try:
        from dotenv import load_dotenv
        load_dotenv(PROJECT / ".env")
    except ImportError:
        pass


def get_client():
    """Return a TradingClient. Call each time — do not cache (keys may change)."""
    _load_env()
    key    = os.getenv("ALPACA_API_KEY", "")
    secret = os.getenv("ALPACA_SECRET_KEY", "")
    paper  = os.getenv("ALPACA_PAPER", "true").lower() != "false"
    if not key or not secret:
        raise RuntimeError("ALPACA_API_KEY / ALPACA_SECRET_KEY not set in .env")
    from alpaca.trading.client import TradingClient
    return TradingClient(key, secret, paper=paper)


def account_snapshot() -> dict:
    """Return key account fields as a plain dict."""
    try:
        a = get_client().get_account()
        return {
            "ok":            True,
            "equity":        float(a.equity         or 0),
            "cash":          float(a.cash           or 0),
            "buying_power":  float(a.buying_power   or 0),
            "portfolio_value": float(a.portfolio_value or 0),
            "long_market_value":  float(a.long_market_value  or 0),
            "short_market_value": float(a.short_market_value or 0),
            "daytrade_count": int(a.daytrade_count or 0),
            "pattern_day_trader": bool(a.pattern_day_trader),
            "trading_blocked":    bool(a.trading_blocked),
            "shorting_enabled":   bool(a.shorting_enabled),
            "status":        str(a.status.value) if hasattr(a.status, "value") else str(a.status),
            "account_number": str(a.account_number or ""),
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}


def positions_snapshot() -> list[dict]:
    """Return open positions as a list of plain dicts."""
    try:
        positions = get_client().get_all_positions()
        result = []
        for p in positions:
            result.append({
                "symbol":           str(p.symbol),
                "side":             str(p.side.value) if hasattr(p.side, "value") else str(p.side),
                "qty":              float(p.qty          or 0),
                "avg_entry_price":  float(p.avg_entry_price  or 0),
                "current_price":    float(p.current_price    or 0),
                "market_value":     float(p.market_value     or 0),
                "cost_basis":       float(p.cost_basis       or 0),
                "unrealized_pl":    float(p.unrealized_pl    or 0),
                "unrealized_plpc":  float(p.unrealized_plpc  or 0),
                "change_today":     float(p.change_today     or 0),
                "asset_class":      str(p.asset_class.value) if hasattr(p.asset_class, "value") else str(p.asset_class),
            })
        return result
    except Exception as e:
        return [{"error": str(e)}]


def orders_snapshot(limit: int = 20) -> list[dict]:
    """Return recent orders as a list of plain dicts."""
    try:
        from alpaca.trading.requests import GetOrdersRequest
        from alpaca.trading.enums import QueryOrderStatus
        req = GetOrdersRequest(status=QueryOrderStatus.ALL, limit=limit)
        orders = get_client().get_orders(filter=req)
        result = []
        for o in orders:
            result.append({
                "id":          str(o.id),
                "symbol":      str(o.symbol),
                "side":        str(o.side.value)   if hasattr(o.side,   "value") else str(o.side),
                "type":        str(o.type.value)   if hasattr(o.type,   "value") else str(o.type),
                "status":      str(o.status.value) if hasattr(o.status, "value") else str(o.status),
                "qty":         float(o.qty         or 0) if o.qty         else None,
                "notional":    float(o.notional    or 0) if o.notional    else None,
                "filled_qty":  float(o.filled_qty  or 0) if o.filled_qty  else None,
                "filled_avg_price": float(o.filled_avg_price or 0) if o.filled_avg_price else None,
                "submitted_at": str(o.submitted_at)[:16].replace("T", " ") if o.submitted_at else "",
                "filled_at":    str(o.filled_at)[:16].replace("T", " ")    if o.filled_at    else "",
            })
        return result
    except Exception as e:
        return [{"error": str(e)}]
