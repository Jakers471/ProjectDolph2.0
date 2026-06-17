# ProjectDolph2.0 — Project Map & Walkthrough

**Goal:** Fully automated trade copier — read trader signals from Discord, parse them into structured trade data, apply risk management, and place trades via Alpaca. Each trader gets their own parsing engine because every trader uses different vocabulary.

---

## 1. Quick start (clone-and-run)

```bash
pip install -r requirements.txt              # one-time setup
python main.py                               # full pipeline: ingest -> refs -> profile every trader

python dev.py                                # run parser fixture tests (15 cases, must stay 15/15)
python dev.py --corpus Grizzlies             # parse full corpus, show action/symbol stats
python dev.py --trace f01 f03               # rule-by-rule trace for specific fixtures
python dev.py --msg "stopped out" --trace   # trace any raw message through the parser
python dev.py --paper Grizzlies --save       # full mock pipeline: parse -> risk -> broker -> DB, save HTML
python dev.py --poll Grizzlies               # replay corpus in time order (mock live Discord)
python dev.py --equity Grizzlies             # equity curve from DB, writes PNG
python dev.py --serve Grizzlies             # launch live FastAPI dashboard at http://localhost:8765

# Add a new trader (creates config + data dirs)
python setup_trader.py NewTrader

# Import Discord message exports
python ingestion/from_discord_export.py export.json Grizzlies
```

---

## 2. The full pipeline

```
Discord (mock: corpus replay | live: discord_listener.py)
  -> parsing/parser.py              parse_message() -> Signal
  -> risk/rules.py                  evaluate(signal, db) -> (approved, reason)
  -> execution/broker.py            submit_order() -> logs to DB, links to position
       position_id FK               every trade references its parent position
       close_fraction               0.0=entry/add  0.5=trim  1.0=full exit
       trade_pnl                    realized $ for this specific event
  -> data/paper_db.py               SQLite: signals, trades, positions, equity_snapshots
  -> analytics/equity.py            order_book_data() -> position-grouped with nested trades
  -> parsing/report.py              HTML: Signals + Equity Curve + Order Book tabs
  -> daemon/server.py               FastAPI live dashboard (8 tabs + debug console)
  -> execution/alpaca_adapter.py    Alpaca order submission (offline until keys added)
```

Every message produces exactly one **Signal**: `action=ENTRY|TRIM|EXIT|ADD|UNSURE|NOISE`.

---

## 3. Per-trader parser architecture — KEY DESIGN PRINCIPLE

**Each trader speaks a different language.** You can't use one parser for all traders.

| Trader | Example vocab | Status |
|--------|--------------|--------|
| Grizzlies | "entry", "trim", "tp", "long IBIT", "High risk Short" | Parser built + tuned, full Discord corpus imported |
| ECS | TBD — needs profiling | Config + data dirs created |
| Eva | TBD | Config + data dirs created |
| Waxui | TBD | Config + data dirs created |
| Zabes | TBD | Config + data dirs created |
| Nando | TBD | Config + data dirs created |
| Ace | TBD | Config + data dirs created |

**How to build a per-trader parser:**
1. `python ingestion/from_discord_export.py export.json <Trader>` — import their Discord history
2. `python main.py <Trader>` — profile their language → charts in `data/<Trader>/profile/`
3. `python dev.py --corpus <Trader>` — see UNSURE/NOISE breakdown
4. Tune `config/<Trader>.json` and `parsing/rules/action.py` patterns for their vocab
5. Eventually: per-trader `parsing/rules/<Trader>/` ruleset

---

## 4. API connections & keys

### Alpaca (paper + live trading)
```
Status: SCAFFOLDED — not connected
File:   execution/alpaca_adapter.py
Keys:   .env (copy .env.example, fill in)
        ALPACA_API_KEY=PKXXXXXXXXXXXXXXXXXXXXXXXX
        ALPACA_SECRET_KEY=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
        ALPACA_PAPER=true     # keep true until weeks of paper testing
```
- Uses `alpaca-py` SDK — install: `pip install alpaca-py` (commented out in requirements.txt)
- **DO NOT set `ALPACA_PAPER=false` until paper trading is verified for weeks**

### Discord (live signal ingestion)
```
Status: SCAFFOLDED — not connected
File:   ingestion/discord_listener.py
Keys:   .env
        DISCORD_BOT_TOKEN=your_bot_token_here
        DISCORD_CHANNEL_IDS=1234567890,9876543210
        CHANNEL_ANALYST_MAP=1234567890:Grizzlies
```
- Uses `discord.py` with gateway websocket (event-driven)
- Install: `pip install discord.py` (commented out in requirements.txt)
- See `ingestion/HOW_TO_EXPORT_DISCORD.md` for bulk export instructions

### Live dashboard (FastAPI)
```
Status: LIVE — works locally
File:   daemon/server.py
Start:  python dev.py --serve Grizzlies     (port 8765)
URL:    http://localhost:8765
```

---

## 5. Signal classification rules

All rules live in `parsing/rules/`. Priority order (first match wins):

| Priority | Action | Example phrases | Confidence |
|----------|--------|----------------|-----------|
| 1 | NOISE  | URLs, "giveaway", no numbers + no trade words | 0.85–0.95 |
| 2 | EXIT   | "stopped out", "closed here", "cut BTC here", "all TPs hit" | 0.90 |
| 3 | ADD    | "adding more", "DCA", "averaging down" | 0.88 |
| 4 | TRIM   | "tp1 hit", "trimmed/trimming", "up 20%", "taking profits" | 0.85 |
| 5 | ENTRY  | "Coin:", "Long/Short" header, "High risk Short", "Entry Targets:", "BTC long @90k" | 0.85 |
| 6 | UNSURE | Has trade vocabulary but nothing above matched | 0.35 |

**Price sanity guards (broker.py):**
- OPTION: exit/entry > 5x → break-even (option premium vs stock price bleed)
- All assets: exit/entry > 200x → break-even (parser misfire)
- CRYPTO entry price implausible for symbol (BTC < $5k) → skip position entirely
- OPTION entry price > $500 → skip (BTC spot price leaked into option entry)

**Symbol blocklist** (`profiling/profile.py`): stablecoins (USDT, USDC, BUSD, DAI), common English words that collide with crypto/stock tickers, confirmed false positives.

---

## 6. Order Book — position tracking system

- **Positions grouped** — each position card shows all trades linked to it via `position_id` FK
- **close_fraction** — 0.0=entry/add, 0.5=trim (50% of remaining), 1.0=full exit
- **remaining** — tracks remaining notional ($) as TRIMs reduce it
- **realized_pnl** — cumulates across all TRIMs + EXIT for the position
- **Concurrent positions** — flagged when trader was in multiple symbols simultaneously
- **Zero P&L trades** — exit price fell back to entry price (no price parsed from message = honest break-even, not fake)

**P&L formula:**
```
dollar_pnl = notional × close_fraction × (exit_price − entry_price) / entry_price × side_mult
side_mult = +1 for LONG, -1 for SHORT
```

---

## 7. Project structure

```
ProjectDolph2.0/
├── CLAUDE.md                Project rules and setup for Claude sessions
├── project.md               This file — living map of the project
├── main.py                  ONE-COMMAND sweep: ingest -> refs -> profile all traders
├── dev.py                   CENTRAL DEBUG HUB: corpus, paper, poll, equity, serve
├── setup_trader.py          Add a new trader: creates config + data dirs
├── requirements.txt         Python deps (pip install -r requirements.txt)
├── .env.example             Copy to .env and add API keys (NEVER commit .env)
│
├── config/                  Per-trader risk + broker config (JSON)
│   ├── default.json           Base config inherited by all traders
│   │     risk: {min_confidence, max_open_positions, kill_switch, allowed_actions, allowed_asset_types}
│   │     broker: {dry_run, trade_notional, trim_fraction, starting_balance}
│   ├── Grizzlies.json         Grizzlies overrides (min_confidence:0.60, CRYPTO+OPTION)
│   ├── ECS.json / Eva.json / Waxui.json / Zabes.json / Nando.json / Ace.json
│   └── loader.py              get_config(trader) -> deep-merged dict
│
├── context/
│   ├── context.md             The originating brief (read first)
│   └── logs.md                API diagnostic snapshot (auto-generated, not committed)
│
├── data/
│   ├── paper.db               SQLite paper-trading database
│   │     Tables: signals, trades, positions, equity_snapshots
│   │     trades.position_id FK -> positions (every trade linked to its position)
│   │     trades.close_fraction  0.0=entry/add  0.5=trim  1.0=exit
│   │     trades.trade_pnl       realized P&L for this specific trade event
│   │     positions.remaining    remaining notional ($) after TRIMs
│   │     positions.realized_pnl cumulative P&L across all TRIMs + EXIT
│   ├── paper_db.py            DB wrapper: open_position, insert_trade, update_position_after_trade
│   ├── price_fetcher.py       get_exit_price() — Alpaca historical bar lookup (offline fallback)
│   ├── _full_workbook.xlsx    Raw source backup of the Google Sheet corpus
│   ├── _ref/
│   │   ├── crypto_symbols.json   Top 500 coins by mcap (CoinGecko)
│   │   ├── stock_symbols.json    ~10,400 US stocks + ETFs (SEC EDGAR)
│   │   └── *.md                  Browsable symbol tables
│   └── <Trader>/              One per trader: Grizzlies, ECS, Eva, Waxui, Zabes, Nando, Ace
│       ├── messages.csv        Slim schema: analyst, timestamp, content
│       ├── messages.jsonl      Same data, JSON per line, sorted by timestamp
│       ├── profile/            Profiler outputs (PNGs + profile.json)
│       └── signals/            Parser outputs — created by dev.py --save / --paper
│           ├── <run_id>.jsonl    One Signal per line
│           └── <run_id>.html     Interactive HTML report
│
├── ingestion/                Pull source data, normalize, ingest reference DBs
│   ├── to_jsonl.py             XLSX -> per-trader messages.{csv,jsonl} (merge, no overwrite)
│   ├── from_discord_export.py  DiscordChatExporter JSON/CSV -> messages.jsonl (merge + dedup)
│   ├── HOW_TO_EXPORT_DISCORD.md  Step-by-step guide for Discord bulk export
│   ├── fetch_crypto_symbols.py Refresh _ref/crypto_symbols.json (CoinGecko)
│   ├── fetch_stock_symbols.py  Refresh _ref/stock_symbols.json (SEC EDGAR)
│   ├── discord_poller.py       Mock: replay corpus in timestamp order (offline)
│   └── discord_listener.py    Live: event-driven Discord bot (requires DISCORD_BOT_TOKEN)
│
├── profiling/                Analyze corpus — learn the trader's dialect
│   ├── profile.py              Full profiler: writes PNGs + profile.json
│   │     CRYPTO_SYMBOL_BLOCKLIST  words that collide with crypto tickers (incl. stablecoins)
│   │     STOCK_SYMBOL_BLOCKLIST   superset of above + stock-specific false positives
│   └── show.py                 Print profile.json + DB samples as text
│
├── parsing/                  Parse messages into structured trade Signals
│   ├── signals_schema.py       Signal + RuleResult dataclasses (the output contract)
│   ├── parser.py               parse_message() -> Signal, parse_corpus() -> list[Signal]
│   ├── confidence.py           Combines rule votes into final action + confidence score
│   ├── report.py               HTML report writer
│   └── rules/
│       ├── action.py           ENTRY/TRIM/EXIT/ADD/NOISE/UNSURE detection
│       │     _HAS_TRADE_WORDS  gate: skips NOISE fast-path if trade vocab present
│       │     _EXIT patterns    "stopped out", "closed here", "cut X here", "all TPs hit"
│       │     _TRIM patterns    "tp1 hit", "trimmed/trimming", "up 20%", "taking profits"
│       │     _ENTRY patterns   "Coin:", leading long/short, "High risk Short/Long",
│       │                       "Entry Targets:", "BTC long @price", option notation
│       ├── side.py             LONG / SHORT detection
│       ├── symbol.py           Ticker + CRYPTO/STOCK/OPTION classification
│       │     Blocklist check   prevents stablecoins + English words matching as symbols
│       └── price.py            entry_price, targets, stop, size hint extraction
│
├── risk/
│   └── rules.py               evaluate(signal, db) -> (approved, reason)
│         Gates (in order): kill_switch, action whitelist, asset_type whitelist,
│         min_confidence, duplicate position, max_open_positions, requires open pos
│
├── execution/
│   ├── broker.py              submit_order() — dry-run broker
│   │     ENTRY:  opens position, price plausibility check (skips implausible entries)
│   │     TRIM:   50% close, stores trade_pnl, updates position.remaining
│   │     EXIT:   100% close, position -> closed
│   │     ADD:    links to existing open position, no P&L
│   │     Price sanity: OPTION >5x, all assets >200x -> break-even fallback
│   │     _price_plausible(): per-symbol price bounds (BTC $5k-$250k, etc.)
│   └── alpaca_adapter.py      Alpaca scaffold (offline until .env keys added)
│
├── analytics/
│   └── equity.py              chart_data() + order_book_data() + generate_chart()
│
├── daemon/
│   └── server.py              FastAPI dashboard at localhost:8765
│         Tabs: Signals | Equity | Order Book | Config | Health | Trace | Pipeline | Debug
│         GET  /api/health
│         GET  /api/traders
│         GET  /api/config/{trader}   (read)
│         PUT  /api/config/{trader}   (save from UI)
│         GET  /api/signals/{trader}
│         GET  /api/trades/{trader}
│         GET  /api/equity/{trader}
│         GET  /api/trace/{trader}
│         GET  /api/pipeline/{trader}  (pipeline docs + signal samples)
│         POST /api/paper/{trader}     (run full paper pipeline)
│
└── tests/
    ├── test_ingestion.py
    ├── test_refs.py
    ├── test_profiler.py
    ├── test_numbers.py
    └── fixtures/
        └── mock_messages.jsonl   15 hand-crafted messages covering every action type
```

---

## 8. Dashboard tabs

| Tab | What it shows |
|-----|--------------|
| **Signals** | Last 100 parsed signals — action badge, symbol, asset type, side, price, confidence, raw message |
| **Equity** | Full-width SVG chart (1200×400) with gradient fill, hover tooltips, 8 gridlines, 10 date labels. KPIs: Balance, Return, Win Rate, Trades, Max DD, Avg Win, Avg Loss, Max Win, Max Loss |
| **Order Book** | Position-grouped cards with nested trade rows, size bar (100%→50%→0%), P&L per trade + per position, concurrent exposure flag |
| **Config** | Editable risk + broker config with live Save |
| **Health** | Heartbeat, DB status, trader list |
| **Trace** | Every signal with rule-by-rule trace showing why it was approved/rejected, linked to trade outcome |
| **Pipeline** | 12-section notebook: pipeline flow, signal classification, asset classification, trade types, risk rules, real message examples, trace explanation, backtesting, fixtures, commands, Alpaca status |
| **Debug** | Raw API diagnostics, P&L formula, zero-PnL trades, position size replay |

---

## 9. Data model

```
positions
  id, analyst, symbol, asset_type, side
  entry_price, quantity (original notional $), remaining (after TRIMs)
  opened_at, closed_at, realized_pnl, status (open|partial|closed)

trades
  id, signal_id, position_id (FK)
  analyst, symbol, asset_type, side
  action (BUY|SELL|SELL_SHORT|BUY_COVER|ADD)
  quantity (notional $), price, close_fraction, trade_pnl
  dry_run, status (filled|corpus_end), created_at

signals
  id, analyst, timestamp, raw_content
  action, confidence, symbol, asset_type, side, entry_price

equity_snapshots
  id, analyst, timestamp, cumulative_pnl, trade_id (FK)
```

---

## 10. Roadmap

### Now: More Discord data + parser tuning
- Export remaining months of Grizzlies history (currently have Jan–Jun 2026 + some 2024)
- Profile and tune parsers for 6 remaining traders (ECS, Eva, Waxui, Zabes, Nando, Ace)
- Reduce UNSURE from ~17% toward <10% for Grizzlies

### Next: Parser quality
- Price context scoping — prevent BTC spot price leaking into MARA option entry
- More exit phrase coverage (reduce 30+ zero-PnL break-even fallbacks)

### After: Alpaca + Discord wiring
1. Add Alpaca keys to `.env` → paper trades go live
2. Add Discord bot token → replace corpus replay with real-time signals
3. Verify paper trading for weeks before enabling live

### Long-term
- Position sizing (not fixed notional — scale by confidence or equity %)
- Multi-trader simultaneous monitoring
- Alerting on large drawdowns or kill_switch triggers
