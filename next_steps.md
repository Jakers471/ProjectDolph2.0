# Next Steps — From Profiles to a Parsing Engine

This document captures the **plan for Phase 2 (parsing)** and beyond. None of it is built yet. It's a living design doc — update as ideas firm up.

---

## The goal

The profiler tells us *what the trader's language looks like*. The next phase uses that knowledge to build a **parsing engine** that turns each message into a structured trade signal we can act on.

Per-message extraction target:

```jsonc
{
  "source_message_id": "1463756861772664982",  // original Discord ID, for traceability
  "analyst": "Grizzlies",                      // which trader
  "timestamp": "2026-02-06T15:30:12+00:00",    // when (from the source row)
  "action": "ENTRY",                           // ENTRY | TRIM | EXIT | ADD | UNSURE
  "side": "LONG",                              // LONG | SHORT
  "asset_type": "CRYPTO",                      // CRYPTO | STOCK | OPTION
  "symbol": "BTC",                             // ticker (validated against crypto / stock DB)
  "entry_price": 90250,                        // or null
  "targets": [90800, 91300, 92000],            // list, may be empty
  "stop": 88500,                               // or null
  "size_hint": "20x",                          // leverage / contracts / "$50" — captured verbatim
  "confidence": 0.88,                          // parser self-rating
  "raw_content": "...",                        // the message body, verbatim
  "unsure_reasons": []                         // populated when confidence < threshold
}
```

Everything we extract gets two homes:

- **Machine-readable**: `data/<trader>/signals/<run_id>.jsonl` — one signal per line. AIs, scripts, and the downstream executor read from here.
- **Human-readable**: `data/<trader>/signals/<run_id>_report.md` — grouped by signal type, with the original message inline and the extracted fields beside it. You skim this to gut-check parser quality.

`run_id` is the timestamp of the parse run (so re-parses don't overwrite history).

---

## How the parser will be built (rules first)

Per `context/context.md`, we lean rule-based for one consistent dialect. The profiler outputs are the rulebook:

| Profiler output | What we use it for |
|---|---|
| Top **line prefixes** (`entry:`, `targets:`, `coin: btc`, `ibit calls up`) | Detect message type and pull the structural anchors |
| Top **n-grams** + **action keyword %s** | Confirm and refine action classification |
| **Validated tickers** (crypto + stock DBs) | Match the symbol — high-confidence when in either DB |
| **Number-format classes** | Pick which numbers are prices vs sizes vs ranges |
| `unknown_samples.txt` | Where the rules fail — iteration target |

Engine layout (sketch):

```
parsing/
├── parser.py            Main entry: parser.parse_corpus(trader) -> signals
├── rules/
│   ├── action.py        Action classifier (ENTRY/TRIM/EXIT/ADD)
│   ├── symbol.py        Symbol extraction + DB validation
│   ├── price.py         Price/target/stop extraction
│   └── side.py          LONG vs SHORT detection
├── confidence.py        Combines rule-vote into a confidence score
└── signals_schema.py    The dataclass/Pydantic schema above
```

The orchestrator runs each rule, votes, and produces the final signal. Anything below the confidence threshold gets `action="UNSURE"` and lands in the report's "review needed" section instead of being silently dropped.

---

## The analysis / inspection script

A separate script that reads the latest parse run and lets you inspect it.

```
python parsing/inspect.py <trader>
```

What it does:

- Reads `data/<trader>/signals/<latest>.jsonl`
- Prints a **summary**: total parsed, by action type, by symbol, % flagged UNSURE
- Renders a **report**: `data/<trader>/signals/<run_id>_report.md`
  - One section per action type (ENTRY, TRIM, EXIT, ADD)
  - For each signal: original message (verbatim, indented quote), extracted fields beside it
  - Trailing section "Flagged for review" — every UNSURE signal with the reasons
- Optionally diffs against a prior run: which messages changed classification, which new ones appeared

Same dual-format rule as the profiler: humans skim the `.md`, machines/AIs read the `.jsonl`.

---

## Folding into `main.py`

When parsing exists, `main.py` gets a **Step 4: Parse** that runs after profiling. Sketch:

```
STEP 1: Ingest source workbook
STEP 2: Reference databases (crypto + stocks)
STEP 3: Profile every trader
STEP 4: Parse every trader  <-- new
STEP 5: Render reports + summary
```

The order matters: profilers feed rule design; parsers consume the rules; reports give us feedback to tune the rules.

---

## Beyond parsing (Phase 3+)

Captured here so we don't lose the thread. Each is a separate effort, not a quick add.

### Phase 3 — Live Discord ingestion
Replace the spreadsheet export with a live feed.
- **Preferred: event-driven** — Discord bot using gateway events (websocket push), `discord.py` or raw API. Lowest latency, no polling waste.
- **Fallback: polling** — REST poll the channel every N seconds.
Auth via bot token in `.env` (never committed).

### Phase 4 — Trade execution
A broker adapter that turns parsed signals into live orders. **Risk management layer mandatory** between parser and broker (position sizing, max drawdown, kill switch). Critical safety practice: **dry-run mode with full logging** for weeks before any live trade.

### Phase 5 — Orchestration daemon
The long-running process tying it together: Discord listener -> parser -> risk filter -> broker. Health checks, retries, alerting.

### Cross-cutting
- **Observability** — structured logs of every parsed signal, every order attempt, every rejection
- **Per-trader configuration** — different traders need different sizing and active hours
- **Backtesting** — replay the corpus through the parser+executor in simulation mode

---

## Keeping this current

Update `next_steps.md` whenever:
- A phase gets meaningfully refined (new constraints, new rejected approaches)
- Implementation of a sketched phase begins (link to the real code, leave the design rationale)
- A phase is completed (move it to `project.md`'s built sections, condense the entry here)

Routine code work within an already-implemented phase doesn't need updates here.
