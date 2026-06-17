# Alpaca API Reference — ProjectDolph2.0

Sourced from alpaca-py SDK enums + official docs. Last updated 2026-06-17.

---

## Authentication

**Headers (Legacy — used by alpaca-py SDK):**
```
APCA-API-KEY-ID:     your_api_key
APCA-API-SECRET-KEY: your_secret_key
```

**Base URLs:**
```
Paper trading:  https://paper-api.alpaca.markets
Live trading:   https://api.alpaca.markets
Market data:    https://data.alpaca.markets
```

Paper and live credentials are NOT interchangeable.

---

## Key Enums (from alpaca-py)

### OrderSide
```python
BUY   = "buy"
SELL  = "sell"
```

### OrderType
```python
MARKET       = "market"
LIMIT        = "limit"
STOP         = "stop"
STOP_LIMIT   = "stop_limit"
TRAILING_STOP = "trailing_stop"
```

### TimeInForce
```python
DAY = "day"   # Equity default — expires end of trading day
GTC = "gtc"   # Good Till Cancelled — required for crypto
OPG = "opg"   # Market on Open
CLS = "cls"   # Market on Close
IOC = "ioc"   # Immediate or Cancel
FOK = "fok"   # Fill or Kill
```

**Rules:**
- Equities: DAY, GTC, OPG, CLS, IOC, FOK
- Options: DAY only
- Crypto: GTC or IOC only

### OrderStatus
```python
NEW, PARTIALLY_FILLED, FILLED, DONE_FOR_DAY, CANCELED,
EXPIRED, REPLACED, PENDING_CANCEL, PENDING_REPLACE,
PENDING_REVIEW, ACCEPTED, PENDING_NEW, ACCEPTED_FOR_BIDDING,
STOPPED, REJECTED, SUSPENDED, CALCULATED, HELD
```

### OrderClass
```python
SIMPLE  = "simple"   # Single-leg (default)
BRACKET = "bracket"  # Entry + take_profit + stop_loss
OCO     = "oco"      # One-cancels-other
OTO     = "oto"      # One-triggers-other
MLEG    = "mleg"     # Multi-leg options
```

### PositionIntent (optional on orders)
```python
BUY_TO_OPEN   = "buy_to_open"    # Open a long
BUY_TO_CLOSE  = "buy_to_close"   # Cover a short
SELL_TO_OPEN  = "sell_to_open"   # Open a short
SELL_TO_CLOSE = "sell_to_close"  # Close a long
```

### PositionSide
```python
LONG  = "long"
SHORT = "short"
```

### AssetClass
```python
US_EQUITY  = "us_equity"
US_OPTION  = "us_option"
CRYPTO     = "crypto"
CRYPTO_PERP = "crypto_perp"
```

### QueryOrderStatus (for GET /orders filter)
```python
OPEN   = "open"
CLOSED = "closed"
ALL    = "all"
```

### AccountStatus
```python
ACTIVE, PAPER_ONLY, APPROVED, ONBOARDING, SUBMITTED,
APPROVAL_PENDING, REJECTED, DISABLED, ...
```

---

## POST /v2/orders — Request Body

```json
{
  "symbol":          "IBIT",
  "side":            "buy",
  "type":            "market",
  "time_in_force":   "day",
  "qty":             "1",
  "client_order_id": "dolph_20260617_IBIT_B"
}
```

**Crypto (notional-based):**
```json
{
  "symbol":          "BTC/USD",
  "side":            "buy",
  "type":            "market",
  "time_in_force":   "gtc",
  "notional":        "100.00",
  "client_order_id": "dolph_20260617_BTC_B"
}
```

**With bracket (take-profit + stop-loss):**
```json
{
  "symbol":        "AAPL",
  "side":          "buy",
  "type":          "market",
  "time_in_force": "day",
  "qty":           "1",
  "order_class":   "bracket",
  "take_profit":   { "limit_price": "200.00" },
  "stop_loss":     { "stop_price": "180.00" }
}
```

**Rules:**
- `qty` and `notional` are mutually exclusive
- `notional` only works with `type=market` + `time_in_force=day`
- Crypto symbols must use `/USD` pair format: `BTC/USD`, `ETH/USD`
- `client_order_id` max 128 chars — use it for idempotency

---

## GET /v2/account — Response Fields

Key fields from the account object:
```
id                string   Account UUID
account_number    string   Human-readable account number
status            enum     AccountStatus (see above)
equity            string   Total account equity ($)
buying_power      string   Available buying power ($)
cash              string   Cash balance ($)
portfolio_value   string   Same as equity for trading accounts
pattern_day_trader bool    PDT flag (triggered at 4+ day trades in 5 days)
paper             bool     True if paper trading account
```

---

## GET /v2/positions — Response (per position)

```
asset_id          uuid     Asset identifier
symbol            string   Ticker symbol
exchange          string   Exchange name
asset_class       enum     AssetClass
avg_entry_price   string   Average cost basis
qty               string   Total quantity held
side              enum     PositionSide (long/short)
market_value      string   Current market value ($)
cost_basis        string   Total cost basis ($)
unrealized_pl     string   Unrealized P&L ($)
unrealized_plpc   string   Unrealized P&L (%)
current_price     string   Current price
lastday_price     string   Previous close price
change_today      string   Today's price change (%)
```

---

## GET /v2/orders — Query Parameters

```
status    QueryOrderStatus   open | closed | all (default: open)
limit     int                Max orders to return (default 50, max 500)
after     timestamp          Filter orders after this time
until     timestamp          Filter orders before this time
direction string             asc | desc (default: desc)
symbols   string[]           Filter by symbols (comma-separated)
side      OrderSide          Filter by side: buy | sell
```

---

## alpaca-py SDK — Key Classes

```python
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import (
    MarketOrderRequest,
    LimitOrderRequest,
    GetOrdersRequest,
)
from alpaca.trading.enums import (
    OrderSide,      # BUY, SELL
    TimeInForce,    # DAY, GTC, IOC, FOK, OPG, CLS
    OrderStatus,    # NEW, FILLED, CANCELED, REJECTED, ...
    OrderClass,     # SIMPLE, BRACKET, OCO, OTO, MLEG
    AssetClass,     # US_EQUITY, US_OPTION, CRYPTO
    PositionSide,   # LONG, SHORT
    QueryOrderStatus, # OPEN, CLOSED, ALL
    PositionIntent, # BUY_TO_OPEN, BUY_TO_CLOSE, SELL_TO_OPEN, SELL_TO_CLOSE
)

# Connect
client = TradingClient(api_key, secret_key, paper=True)

# Account
account = client.get_account()
# account.equity, account.buying_power, account.cash, account.status

# Positions
positions = client.get_all_positions()
# pos.symbol, pos.qty, pos.side, pos.avg_entry_price, pos.unrealized_pl

# Submit market order (stock)
req = MarketOrderRequest(
    symbol="IBIT",
    qty=1,
    side=OrderSide.BUY,
    time_in_force=TimeInForce.DAY,
    client_order_id="dolph_...",
)
order = client.submit_order(order_data=req)

# Submit market order (crypto - notional)
req = MarketOrderRequest(
    symbol="BTC/USD",
    notional=100.0,
    side=OrderSide.BUY,
    time_in_force=TimeInForce.GTC,
)
order = client.submit_order(order_data=req)

# Get orders
from alpaca.trading.requests import GetOrdersRequest
req = GetOrdersRequest(status=QueryOrderStatus.ALL, limit=50)
orders = client.get_orders(filter=req)
# order.id, order.symbol, order.side.value, order.status.value, order.filled_avg_price
```

---

## What we need in .env to connect

```bash
ALPACA_API_KEY=PKXXXXXXXXXXXXXXXXXXXXXXXX    # starts with PK for paper keys
ALPACA_SECRET_KEY=xxxxxxxxxxxxxxxxxxxxxxxx   # 40-char hex string
ALPACA_PAPER=true                           # ALWAYS true until weeks of paper testing
```

Get keys at: alpaca.markets → Dashboard → Paper Trading → API Keys → Generate

---

## Notes for ProjectDolph2.0

- Our `execution/alpaca_adapter.py` wraps TradingClient — already uses correct enums
- `AlpacaOrder.to_dict()` produces the exact JSON body Alpaca expects
- The adapter stays **offline** (dry_run mode) until keys are present in .env
- `get_adapter()` is a singleton — one connection per process
- Paper account resets equity to $100,000 each time you regenerate keys
- Never use `ALPACA_PAPER=false` until at least several weeks of paper testing
