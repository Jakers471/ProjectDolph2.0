# ProjectDolph2.0

- **Repo:** https://github.com/Jakers471/ProjectDolph2.0.git
- **Local path:** `C:\Users\jakers\Desktop\ProjectDolph2.0`
- **Goal:** Fully automated trade copier — read Discord signals, parse them into structured Signals, apply per-trader risk rules, and place trades via Alpaca.

## Setup

```
pip install -r requirements.txt
```

Required (already in requirements.txt): `openpyxl`, `matplotlib`, `fastapi`, `uvicorn`, `python-dotenv`
Optional (install when ready): `alpaca-py`, `discord.py` (commented out in requirements.txt)

Add any new third-party imports to `requirements.txt` so cloners can run the project without guessing.

## Project structure

The full map of folders and modules lives in `project.md`. **Read it first** to find where things go and what each module is for.

**Rule:** whenever you add, remove, rename, or change the role of a top-level folder or module, update `project.md` in the same change. Routine edits inside an existing module don't require touching it.

## API keys (never commit .env)

Copy `.env.example` to `.env` and fill in your credentials:

```bash
# Alpaca paper trading (get from alpaca.markets)
ALPACA_API_KEY=PKxxxxxxxxxxxxxxxxxxxxxxxx
ALPACA_SECRET_KEY=xxxxxxxxxxxxxxxxxxxxxxxx
ALPACA_PAPER=true     # ALWAYS true until weeks of testing

# Discord bot (from discord.com/developers/applications)
DISCORD_BOT_TOKEN=your_bot_token_here
DISCORD_CHANNEL_IDS=1234567890,9876543210   # comma-separated channel IDs
CHANNEL_ANALYST_MAP=1234567890:Grizzlies    # channel_id:TraderName
```

Both Alpaca and Discord are scaffolded but not wired. The system runs fully offline until keys are added.

## Per-trader architecture — KEY DESIGN PRINCIPLE

Every trader uses different vocabulary. Grizzlies says "entry", "trim", "tp". Other traders may say completely different things. Each trader needs:
1. Their own corpus profiled → `python main.py <Trader>`
2. Their own config tuned → `config/<Trader>.json`
3. Eventually their own parser rules → `parsing/rules/<Trader>/`

**Current state:** Grizzlies parser is fully built. Other 6 traders (ECS, Eva, Waxui, Zabes, Nando, Ace) have config files and data dirs but need their corpuses profiled and parsers tuned.

## Adding a new trader

```
python setup_trader.py <TraderName>
```

Creates `config/<TraderName>.json` (copy of defaults) + `data/<TraderName>/` directories. Then:
1. `python main.py <TraderName>` — profile their language patterns
2. Read `data/<TraderName>/profile/` charts to understand their vocab
3. `python dev.py --corpus <TraderName>` — see UNSURE/NOISE breakdown
4. Tune `config/<TraderName>.json` thresholds

## Per-trader config (config/<Trader>.json)

```json
{
  "risk": {
    "min_confidence": 0.60,
    "max_open_positions": 3,
    "kill_switch": false,
    "allowed_asset_types": ["CRYPTO", "OPTION"],
    "allowed_actions": ["ENTRY", "TRIM", "EXIT", "ADD"]
  },
  "broker": {
    "dry_run": true,
    "trade_notional": 100.0,
    "trim_fraction": 0.5,
    "starting_balance": 7000
  }
}
```

`config/loader.py` → `get_config(trader)` deep-merges trader file over `default.json`.

## The full pipeline

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
  -> daemon/server.py               FastAPI live dashboard (5 tabs + debug console)
  -> execution/alpaca_adapter.py    Alpaca order submission (offline until keys added)
```

## Order Book — position tracking

- Each **position** groups all trades that belong to it (linked by `position_id` FK)
- `close_fraction` tracks how much was closed: 0.5 for TRIM, 1.0 for EXIT
- `positions.remaining` tracks remaining notional ($) as TRIMs happen
- `positions.realized_pnl` accumulates P&L across all TRIMs + EXIT
- Concurrent positions are flagged (trader was in multiple symbols simultaneously)
- **Why zeros:** exit price falls back to entry price when signal has no parsed price → break-even

## P&L formula

```
dollar_pnl = notional × close_fraction × (exit_price − entry_price) / entry_price × side_multiplier
```
- `TRIM`: close_fraction = 0.5, notional = position.remaining
- `EXIT`: close_fraction = 1.0, notional = position.remaining
- `ADD`: no P&L (just logged as a position add-on)
- If no exit price parsed: falls back to entry_price → break-even ($0 P&L), not a fake default

## dev.py — central debug hub

```
python dev.py                              # 15 fixture tests (parser unit tests)
python dev.py --trace f01 f03              # rule-by-rule trace for specific fixtures
python dev.py --msg "..." --trace          # trace a raw message
python dev.py --corpus Grizzlies           # parse full corpus, print stats
python dev.py --corpus Grizzlies --save    # also write JSONL + HTML report
python dev.py --paper Grizzlies --save     # full mock pipeline: parse->risk->broker->DB, save HTML
python dev.py --poll Grizzlies             # replay corpus in time order (mock live Discord)
python dev.py --poll Grizzlies --speed 10  # 10x faster replay
python dev.py --equity Grizzlies           # print equity table from DB + write PNG
python dev.py --serve Grizzlies            # live FastAPI dashboard at localhost:8765
```

## Database (data/paper.db)

SQLite file — persists across runs. Reset happens automatically at the start of each `--paper` / `--poll` run (clean simulation). Tables:

| Table | Purpose |
|-------|---------|
| `signals` | Every parsed signal with action, symbol, price, confidence |
| `trades` | Every order event — linked to position via `position_id` FK |
| `positions` | Open/partial/closed positions with `remaining` and `realized_pnl` |
| `equity_snapshots` | Running cumulative P&L snapshots for equity curve |

## Key rules

- **dry_run is always True** until Alpaca keys are added and paper trading is verified
- **Never commit .env** — Alpaca keys and Discord token only in .env
- **All Unicode chars** must be ASCII-safe for Windows terminal (cp1252 encoding)
- **Parser fixtures must stay green** after any rule change: `python dev.py` must show 15/15 passed
- **Always run `--paper Grizzlies --save`** after any pipeline change to verify the full loop
