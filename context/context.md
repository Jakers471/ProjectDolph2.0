# Project Brief: Automated Trade Copier via Signal Parsing

## What we're building (eventually)

The long-term goal is an **automated trade copier**: read a Discord trader's signals, turn them into structured trade data, and act on it with our own risk management layered on top.

But that's downstream. **Right now the entire focus is one thing: figuring out how to parse his messages.** Everything else depends on getting that right, and we are at the very beginning of it.

## Where we actually are

Be clear-eyed about this: **we have only looked at about 5 messages so far.** We do not understand his language yet. We have a *hypothesis* that he follows repeatable personal patterns, and a few ideas about how parsing might work — but nothing is confirmed. The job of this phase is to **learn how he talks**, then design parsing methods around what we actually find — not to assume we already know.

Do not treat the examples or rules below as a finished spec. They're a starting hypothesis to test and revise.

## The core problem

From each message we ultimately want to extract:

1. **Action** — buy / sell (and likely sub-types: entry, trim/partial, full exit, add to position)
2. **Symbol** — ticker
3. **Price** — entry, target(s), or fill
4. **Quantity / contracts** — *probably not required*; we'll run our own risk management

Action, symbol, price are the three that matter most. But **we don't yet know all the ways he expresses these** — discovering that range is the work.

## What we've seen so far (small sample — not the full picture)

These are early examples only. There are almost certainly formats and phrasings we haven't encountered yet.

**Possible entry (crypto):**
```
Btc long
Entry:
1)66250
targets:
1)66800
2)67300
...
```

**Possible entry (options):**
```
CLSK 10c 2/20/26
@0.50
```
→ looks like ticker + strike + expiry + price, positional.

**Possible trim / take-profit** (appeared as replies to an entry):
```
TP1 hit
Tp3 on btc
Trimming and setting stops
```

**Possible exit:**
```
Stopped out on entry, not bad for an hour
```

**Possible add:**
```
Bought more CLSK here ... Avg price for con is $42
```

**Commentary (the genuinely hard case):**
```
If no strength, then btc should tumble down to 60-62k
```
Has numbers that look like prices but is a hypothetical, not a signal. We need to learn how to tell these apart — and we don't know yet how often or in what forms this shows up.

## A structural clue worth investigating

In the sample, TP/trim messages appeared to **reply to the original entry message** (messages carry a parent ID). If that holds across the full dataset, reply-linking is how we connect "TP1 hit" back to its trade. **To be verified** against more data — don't assume it's universal.

## Direction we're leaning (a hypothesis, not a verdict)

We're inclined toward **rule-based parsing rather than an AI/LLM model**, for reasons worth stating but also worth re-testing:

- A prior collaborator spent ~a year trying to parse these with AI and struggled to get reliable results.
- For a single trader with a consistent personal dialect, rules *may* be simpler, cheaper, more reproducible, and easier to debug.

But this is a working assumption. If, once we actually study the language, the failures turn out to be scattered and irregular rather than clustered, ML or a hybrid approach goes back on the table. **Let the data decide.**

### Bar we're aiming for
- Roughly **85%+** correct, not 100%.
- Ambiguous messages get **flagged and skipped**, never guessed. Fallbacks over hallucinations.

## The actual first step: learn his language

Before writing any parser, we need to **understand how he talks** across the full corpus — not extrapolate from 5 messages. Build a script that profiles his dialect:

1. Tokenize all messages into words and phrases
2. Count frequencies — most common words, repeated phrases, recurring number formats
3. Look at context — what words cluster near apparent buys vs sells vs prices
4. Surface the formats we *haven't* hand-noticed yet
5. Output a readable report

The point is to **see his patterns quantitatively** so we don't miss things a 5-message glance can't reveal. Only after that do we design parsing methods grounded in what's actually there.

## Iteration workflow

1. Profile the language (above) → form real, evidence-based pattern rules
2. Parse → dump results to a file
3. Spot-check a sample, log failures
4. Failures **cluster** around phrasings → add/adjust rules
5. Failures **scatter** → rethink approach (this is the signal that rules alone may not be enough)
6. Repeat. Compute is instant over thousands of messages; the bottleneck is our review time and understanding.

## Data & infrastructure

- **~1,000+ messages** from this one trader over a couple of years — enough to actually learn his patterns (and far more than we've looked at).
- Stored in **Google Drive / Google Docs**.
- **Ingestion:** simplest path is export to CSV/plain text, drop it in the project, read locally, commit for reproducibility. Drive API exists but is overkill now — wire up later only if we need live data.
- **No live Discord/API hookup yet.** This phase is entirely offline iteration on understanding and parsing.

## Scope for whoever picks this up

- **In scope now:** *learning his language*, then building parsing methods for action + symbol + price, aiming ≥85%, flagging the rest. This is exploratory — expect to discover patterns we haven't documented.
- **Out of scope now:** live ingestion, trade execution, our risk management, contract-quantity precision.
- **Mindset:** we don't know his language yet. Stay curious, study the data, treat every rule as provisional until the corpus backs it up. Don't act like the problem is solved — it isn't, that's the whole point.