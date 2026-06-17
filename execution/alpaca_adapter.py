"""Alpaca paper-trading adapter.

Uses the official alpaca-py SDK. Stays fully offline (dry-run) until
ALPACA_API_KEY and ALPACA_SECRET_KEY are set in .env.

Order strategy (per Alpaca docs):
  ENTRY / ADD  -> MarketOrderRequest with notional (equities: TIF=day, crypto: TIF=gtc)
  TRIM         -> close_position(symbol, ClosePositionRequest(percentage=50))
  EXIT         -> close_position(symbol)  (full close)

Crypto symbols must use /USD pair: BTC -> BTC/USD.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent


def _load_env():
    try:
        from dotenv import load_dotenv
        load_dotenv(PROJECT / ".env")
    except ImportError:
        pass


def _fmt_client_id(run_id: str, symbol: str, action: str) -> str:
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    raw = f"dolph_{run_id}_{ts}_{symbol}_{action[:1]}"
    return raw[:128]  # Alpaca max 128 chars


# Known crypto base tickers traded on Alpaca
_KNOWN_CRYPTO = {
    "BTC","ETH","SOL","DOGE","SHIB","AVAX","LINK","UNI","AAVE","BCH",
    "LTC","XLM","ALGO","DOT","MATIC","CRV","GRT","MKR","SUSHI","YFI",
    "BAT","ZRX","COMP","SNX","REN","BAL","KNC","UMA","NMR","OXT",
    "XTZ","ETC","ATOM","NEAR","FIL","HBAR","VET","THETA","EOS","TRX",
}

def _crypto_symbol(sym: str) -> str:
    """BTC -> BTC/USD — only for confirmed crypto tickers."""
    if "/" in sym:
        return sym
    return f"{sym}/USD" if sym.upper() in _KNOWN_CRYPTO else sym


def _is_crypto(symbol: str, asset_type: str) -> bool:
    """True only if symbol is a known crypto — don't trust parser asset_type alone."""
    return symbol.upper() in _KNOWN_CRYPTO or "/" in symbol


class AlpacaAdapter:
    """Wraps alpaca-py TradingClient. Offline when keys are missing."""

    def __init__(self):
        self._client = None
        self._connected = False
        self._paper = True
        self._load()

    def _load(self):
        _load_env()
        api_key    = os.getenv("ALPACA_API_KEY")
        secret_key = os.getenv("ALPACA_SECRET_KEY")
        paper      = os.getenv("ALPACA_PAPER", "true").lower() != "false"
        self._paper = paper

        if not api_key or not secret_key:
            return

        try:
            from alpaca.trading.client import TradingClient
            self._client    = TradingClient(api_key, secret_key, paper=paper)
            self._connected = True
        except ImportError:
            pass

    @property
    def connected(self) -> bool:
        return self._connected

    @property
    def mode(self) -> str:
        return "paper" if self._paper else "LIVE"

    def get_account(self) -> dict:
        if not self._client:
            return {"error": "not connected — add keys to .env"}
        a = self._client.get_account()
        return {
            "ok":               True,
            "equity":           float(a.equity          or 0),
            "cash":             float(a.cash            or 0),
            "buying_power":     float(a.buying_power    or 0),
            "portfolio_value":  float(a.portfolio_value or 0),
            "pattern_day_trader": bool(a.pattern_day_trader),
            "trading_blocked":  bool(a.trading_blocked),
            "shorting_enabled": bool(a.shorting_enabled),
            "status": str(a.status.value) if hasattr(a.status, "value") else str(a.status),
            "account_number": str(a.account_number or ""),
        }

    def get_positions(self) -> list:
        if not self._client:
            return []
        return [
            {
                "symbol":         p.symbol,
                "side":           str(p.side.value) if hasattr(p.side, "value") else str(p.side),
                "qty":            float(p.qty          or 0),
                "avg_entry_price":float(p.avg_entry_price  or 0),
                "current_price":  float(p.current_price    or 0),
                "market_value":   float(p.market_value     or 0),
                "unrealized_pl":  float(p.unrealized_pl    or 0),
                "unrealized_plpc":float(p.unrealized_plpc  or 0),
            }
            for p in self._client.get_all_positions()
        ]

    def get_orders(self, limit: int = 50) -> list:
        if not self._client:
            return []
        from alpaca.trading.requests import GetOrdersRequest
        from alpaca.trading.enums import QueryOrderStatus
        req = GetOrdersRequest(status=QueryOrderStatus.ALL, limit=limit)
        return [
            {
                "id":               str(o.id),
                "symbol":           o.symbol,
                "side":             str(o.side.value) if hasattr(o.side, "value") else str(o.side),
                "type":             str(o.type.value) if hasattr(o.type, "value") else str(o.type),
                "status":           str(o.status.value) if hasattr(o.status, "value") else str(o.status),
                "qty":              float(o.qty or 0) if o.qty else None,
                "notional":         float(o.notional or 0) if o.notional else None,
                "filled_qty":       float(o.filled_qty or 0) if o.filled_qty else None,
                "filled_avg_price": float(o.filled_avg_price or 0) if o.filled_avg_price else None,
                "submitted_at": str(o.submitted_at)[:16].replace("T", " ") if o.submitted_at else "",
                "filled_at":    str(o.filled_at)[:16].replace("T", " ")    if o.filled_at    else "",
                "client_order_id": o.client_order_id,
            }
            for o in self._client.get_orders(filter=req)
        ]

    def submit_order(self, signal, run_id: str, notional: float) -> dict:
        """Submit or dry-run an order for a parsed Signal.

        ENTRY/ADD -> MarketOrderRequest with notional dollar amount
        TRIM      -> close_position 50% of held position
        EXIT      -> close_position 100%
        """
        from alpaca.trading.requests import MarketOrderRequest
        from alpaca.trading.enums import OrderSide, TimeInForce

        action    = signal.action
        symbol    = signal.symbol or "UNKNOWN"
        is_crypto = _is_crypto(symbol, signal.asset_type or "")
        alp_sym   = _crypto_symbol(symbol) if is_crypto else symbol
        tif       = TimeInForce.GTC if is_crypto else TimeInForce.DAY
        cid       = _fmt_client_id(run_id, symbol, action)

        # ---- ENTRY / ADD --------------------------------------------------------
        if action in ("ENTRY", "ADD"):
            side = OrderSide.BUY if (signal.side or "LONG") == "LONG" else OrderSide.SELL
            req = MarketOrderRequest(
                symbol          = alp_sym,
                side            = side,
                time_in_force   = tif,
                notional        = round(notional, 2),
                client_order_id = cid,
            )
            tag = f"[alpaca] {action} {alp_sym} ${notional:.2f} notional side={side.value} tif={tif.value}"
            if not self._client:
                return {"dry_run": True, "tag": tag, "submitted": False, "reason": "no keys"}
            result = self._client.submit_order(order_data=req)
            return {"dry_run": False, "tag": tag, "submitted": True,
                    "id": str(result.id), "status": str(result.status.value)}

        # ---- TRIM ---------------------------------------------------------------
        if action == "TRIM":
            from alpaca.trading.requests import ClosePositionRequest
            tag = f"[alpaca] TRIM {alp_sym} — close 50%"
            if not self._client:
                return {"dry_run": True, "tag": tag, "submitted": False, "reason": "no keys"}
            try:
                result = self._client.close_position(
                    alp_sym,
                    close_options=ClosePositionRequest(percentage=50),
                )
                return {"dry_run": False, "tag": tag, "submitted": True,
                        "id": str(result.id), "status": str(result.status.value)}
            except Exception as e:
                return {"dry_run": False, "tag": tag, "submitted": False, "error": str(e)}

        # ---- EXIT ---------------------------------------------------------------
        if action == "EXIT":
            tag = f"[alpaca] EXIT {alp_sym} — full close"
            if not self._client:
                return {"dry_run": True, "tag": tag, "submitted": False, "reason": "no keys"}
            try:
                result = self._client.close_position(alp_sym)
                return {"dry_run": False, "tag": tag, "submitted": True,
                        "id": str(result.id), "status": str(result.status.value)}
            except Exception as e:
                return {"dry_run": False, "tag": tag, "submitted": False, "error": str(e)}

        return {"dry_run": True, "submitted": False, "reason": f"unsupported action: {action}"}


# Singleton — one adapter per process
_adapter: AlpacaAdapter | None = None

def get_adapter() -> AlpacaAdapter:
    global _adapter
    if _adapter is None:
        _adapter = AlpacaAdapter()
    return _adapter
