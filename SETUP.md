# ProjectDolph2.0 — Setup Guide

Fully automated Discord → parse → risk → Alpaca paper trade copier.
This guide takes you from a fresh clone to a running live dashboard.

---

## Prerequisites

- **Python 3.11+** — [python.org](https://python.org)
- **Git**
- **Windows 10/11** — the toast watcher (`uiautomation`) is Windows-only
- **Discord desktop app** installed and logged in (not the browser version)
- **Alpaca account** (paper trading) — [alpaca.markets](https://alpaca.markets) (free)

---

## 1. Clone and install

```bash
git clone https://github.com/Jakers471/ProjectDolph2.0.git
cd ProjectDolph2.0
pip install -r requirements.txt
```

> **Linux/Mac note:** remove the `uiautomation` line from `requirements.txt` before installing — it is Windows-only. The toast watcher won't work, but everything else will.

---

## 2. Set up your .env

Copy the example file and fill in your credentials:

```bash
cp .env.example .env
```

Open `.env` and fill in:

```
ALPACA_API_KEY=PKXXXXXXXXXXXXXXXXXXXXXXXX
ALPACA_SECRET_KEY=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
ALPACA_PAPER=true

CHANNEL_ANALYST_MAP=grizzlies-signals:Grizzlies
```

**Where to get these:**

| Key | Where |
|-----|-------|
| `ALPACA_API_KEY` / `ALPACA_SECRET_KEY` | alpaca.markets → Paper Trading → API Keys |
| `CHANNEL_ANALYST_MAP` | The channel name that appears in Discord toast notifications, mapped to the trader name. Check your toast notifications to see the exact channel name Discord uses. |
| `DISCORD_BOT_TOKEN` | Optional — only needed for the full bot ingestion path. See `ingestion/discord_listener.py`. The Windows watcher works without it. |

> **Never commit `.env`** — it is already in `.gitignore`.

---

## 3. Start the dashboard

```bash
python -m uvicorn daemon.server:app --host 0.0.0.0 --port 8765 --reload
```

Then open: **http://localhost:8765**

The dashboard starts on the **Live** tab. All other tabs (Signals, Equity, Order Book, Trace, Pipeline, Health) work immediately.

---

## 4. Run a sanity check (verify Alpaca is wired)

With the dashboard open:

1. Go to **Live tab → Step 1**
2. Paste your Alpaca API key + secret into the fields (they save to `.env` — not the browser)
3. Click **Save All Settings**
4. Click **▶ Sanity Check**

The sanity check fires a real BTC signal end-to-end: parse → risk → Alpaca paper order → close. You should see 5 green log steps and an orange `[SANITY]` row appear in Recent Orders. It places and immediately closes the order — no lasting positions.

---

## 5. Run the paper pipeline (backtest / replay)

This replays the existing Grizzlies corpus through the full pipeline and generates an HTML report:

```bash
python dev.py --paper Grizzlies --save
```

Then open the dashboard → **Signals / Equity / Order Book / Trace** tabs to see results.

Other useful commands:

```bash
python dev.py                          # run 15 parser unit tests (must all pass)
python dev.py --corpus Grizzlies       # profile corpus language patterns
python dev.py --equity Grizzlies       # print equity table + write chart PNG
python dev.py --serve Grizzlies        # same as uvicorn command above
```

---

## 6. Configure Discord → Live trading

**Watcher-only mode (no bot token required):**

1. Open Discord desktop app — keep it **minimized** (not fullscreen, not in focus)
2. Enable Discord notifications for the channel you want to watch
3. In `.env`, set `CHANNEL_ANALYST_MAP` to match the channel name in toasts:
   ```
   CHANNEL_ANALYST_MAP=grizzlies-signals:Grizzlies
   ```
4. In the dashboard → Live tab, click **START**
5. When a message posts in the channel, Windows fires a toast → the watcher captures it → the pipeline processes it

> **Key rule:** Discord must be open but minimized. Toasts only fire when Discord is not the active focused window. If Discord is fullscreen or focused, Windows suppresses the notification and the watcher misses it.

---

## 7. Add a new trader

```bash
python setup_trader.py <TraderName>
```

This creates `config/<TraderName>.json` and `data/<TraderName>/` directories. Then:

1. Get their message corpus into `data/<TraderName>/corpus/`
2. `python main.py <TraderName>` — profile their language patterns
3. `python dev.py --corpus <TraderName>` — check UNSURE/NOISE breakdown
4. Tune `config/<TraderName>.json` thresholds to match their vocabulary

Each trader needs their own parser rules in `parsing/rules/<TraderName>/` if their vocabulary differs significantly from Grizzlies. See `CLAUDE.md` for the per-trader architecture details.

---

## 8. Per-trader risk config

Each trader has a config at `config/<TraderName>.json`:

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

**`dry_run` must stay `true`** until you have run weeks of paper testing and verified the sanity check passes consistently.

---

## Project structure (quick reference)

```
daemon/server.py          FastAPI dashboard + Live tab UI
parsing/parser.py         parse_message() → Signal
parsing/rules/            per-rule extractors (action, symbol, price, etc.)
risk/rules.py             evaluate(signal, db) → (approved, reason)
execution/broker.py       submit_order() → logs to SQLite DB
execution/alpaca_adapter.py   Alpaca paper order submission
ingestion/windows_watcher.py  Windows toast notification capture
ingestion/live_pipeline.py    polls discord_messages.db, runs pipeline
data/paper_db.py          SQLite: signals, trades, positions, equity_snapshots
config/                   per-trader JSON configs
dev.py                    debug hub — tests, corpus profiling, paper runs
main.py                   corpus profiler entry point
setup_trader.py           scaffold a new trader
```

Full module map: see `project.md`.

---

## Common issues

| Problem | Fix |
|---------|-----|
| `ALPACA_API_KEY not set` | Copy `.env.example` to `.env` and fill in keys |
| Sanity check "cleanup: close failed — Not Found" | Order filled before cancel — normal, the adapter now tries BTCUSD / BTC/USD / BTC automatically |
| Toast watcher misses messages | Discord must be minimized, not fullscreen. Check Windows notification settings for Discord. |
| `uiautomation` install fails | Windows only — remove from `requirements.txt` on Linux/Mac |
| Parser fixtures failing | Run `python dev.py` — all 15 must pass before any pipeline change |
| Port 8765 already in use | Kill the old process: `netstat -ano | findstr :8765` then `taskkill /PID <pid> /F` |
