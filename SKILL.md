---
name: price-action-al-brooks
description: "Two-stage price action analysis per Al Brooks' Trading Price Action series. Stage 1 scan to Stage 2 deep dive. Brooks terminology only — no Elliott Wave / Wyckoff / SMC. Four-tier loading: Core (always, ~22KB) + Trends or Ranges (engine-driven, ~14-20KB) + Reversals (when signals detected, ~24KB)."
---

# Price Action — Al Brooks Framework

## Backtester

The skill includes a deterministic backtester (`scripts/backtest.py`) that slides
the Tier-1 engine across historical daily bars and applies rule-based entry/exit
decisions. See `references/backtest_architecture.md` for architecture details.

## Modular File Structure

```
skills/price-action-al-brooks/
├── SKILL.md              ← This file (router + workflow)
├── core.md               ← Universal price action (~22KB — ALWAYS loaded)
├── trends.md             ← Trend-specific rules (~14KB — load when trending)
├── ranges.md             ← Trading range rules (~20KB — load when ranging)
├── reversals.md          ← Reversal patterns (~24KB — load when reversal signals detected)
├── DECISION_LAYER.md     ← Backtester decision layer (8 entry rules)
├── tier2-routing.md      ← Tier-2 agent decision guide (~50 lines, replaces full book reading)
└── scripts/
    ├── fetch_data.py     ← Multi-timeframe OHLCV + indicators + pattern detection
    ├── brooks_analysis.py ← Tier-1 deterministic engine (SoS, day type, pullbacks, etc.)
    └── backtest.py       ← Deterministic backtester (8 entry rules, no LLM calls)
```

## Two-Tier Architecture

This skill uses a four-tier knowledge loading system driven by the Tier-1 engine output.

| Tier | What | Who | What it produces |
|------|------|-----|-----------------|
| **Tier 1** | Deterministic analysis engine | `brooks_analysis.py` | SoS count, day type hypothesis, pullback count (H1/L1-H4/L4), measured move targets, conviction objective subtotal, pattern watch items |
| **Tier 2** | Human/agent judgment | The agent reading this skill | Always-In direction call, pattern evolution assessment, signal bar quality in context, Trader's Equation probability, final conviction score (subtotal + adjustments), entry management (scalp vs swing) |

**The engine computes what it can from OHLCV data. The agent applies Brooks' context-dependent judgment where the data can't.** See `tier2-routing.md` for Stage 2 decision rules.

## Known Limitations

- **No intraday / opening range data** — Brooks heavily emphasizes the first 30-min/hour high/low as key magnets. The framework uses daily/weekly/H4 only. The agent should note this gap in analyses.
- **H4 timeframe fetched but not analyzed by engine** — H4 data exists in the output for agent reference but brooks_analysis.py only processes daily. The agent should cross-check H4 structure manually.
- **Swing detection is primitive** — the built-in swing finder misses double tops/bottoms and equal extremes. Measured moves and leg structure are approximate.
- **Volume signs (SoS 20-22) are weakly computed** — volume data quality varies by instrument (crypto volume differs from stocks). Take these signs with caution.
- **Climax is identified retroactively** — the engine flags potential climax bars (body ≥75%, range >1.8× avg) but true climax can only be confirmed after the fact. The agent must verify.

## Four-Tier Loading (Engine-Driven)

| Tier | File | Size | When to Load |
|------|------|------|-------------|
| **Core** | `core.md` | ~22KB | **ALWAYS** — bar anatomy, bar counting, breakouts, close, EMA, risk management, trade management, time frames, glossary |
| **Trends** | `trends.md` | ~14KB | When `day_type.hypothesis` ∈ {`strong_bull`, `strong_bear`, `tfo_bull`, `tfo_bear`} |
| **Ranges** | `ranges.md` | ~20KB | When `day_type.hypothesis` ∈ {`trading_range`, `barbwire`} |
| **Reversals** | `reversals.md` | ~24KB | When reversal signals detected: trend line break + test of extreme, consecutive climaxes, wedge overshoot, final flag breakout, expanding triangle. **Overlay** — loads alongside state module. |

**When `ambiguous` or `insufficient_data`:** Load core.md ONLY. Agent should WAIT until structure clarifies before committing to a direction.

## Routing Table

| Engine Output | Knowledge Modules | Agent Action |
|---|---|---|
| `strong_bull` / `strong_bear` | core + trends | With-trend entries only. High conviction setups. |
| `strong_bull` + reversal signals | core + trends + reversals | With-trend primary, but watch for reversal setup at test of extreme. |
| `tfo_bull` / `tfo_bear` | core + trends | Trend from Open — aggressive with-trend, swing portion. |
| `tfo_bull` / `tfo_bear` + reversal signals | core + trends + reversals | With-trend primary, watch for opening reversal at support/resistance. |
| `trading_range` | core + ranges | Fade extremes. WAIT for edge of range. No with-trend bias. |
| `trading_range` + reversal signals | core + ranges + reversals | Fade extremes. Watch for final flag reversals at range edges. |
| `barbwire` | core + ranges | FORGET most setups. Only fade strong extremes at range edges. |
| `ambiguous` | core only | WAIT. No clear direction. Let the market tip its hand. |
| `insufficient_data` | core only | WAIT. Not enough bars for classification. |

## Core Tenets

1. **Market is always on a spectrum**: extreme trend vs extreme trading range
2. **Always-In direction**: at any moment, if forced to pick long or short, that is the always-in
3. **Trader's Equation**: prob x reward exceeds (1 minus prob) x risk — not rigid R:R
4. **Two-legged principle**: market regularly tries to do something twice
5. **Trend first**: always classify trend or trading range before analyzing any bar
6. **Weak signals do not mean weak trend**: weak signal bars are often a FEATURE of strong trends
7. **Trend phase determines entry type**: read `references/entry_type_matrix.md` before recommending any entry. Early trend → breakout. Mid → pullback. Late/climax → reversal/FBO. TR → range edge. Do NOT default to pullback.

## Conviction Scoring System

Every LONG/SHORT verdict must include a conviction score. Use this rubric:

### Score Modifiers

| Factor | Condition | Modifier |
|--------|-----------|----------|
| Trend alignment | With-trend (always-in agrees) | +1 |
| Trend alignment | Counter-trend | -2 |
| Signal bar quality | Strong trend bar (body at least 70%, small tails, close in top/bottom 25%) | +1 |
| Signal bar quality | Weak/doji signal bar in strong trend (normal) | 0 |
| Signal bar quality | Weak signal bar in weak/no trend | -1 |
| Signs of Strength count | At least 12 signs | +1 |
| Signs of Strength count | At most 5 signs | -1 |
| Second entry | Second attempt at same setup | +1 |
| R:R ratio (agent-assessed) | At least 1:3 | +1 |
| R:R ratio (agent-assessed) | Under 1:1 | -1 |
| Bar counting | H2/L2 at 20-EMA (standard setup) | +1 |
| Bar counting | H1/L1 (first pullback, less reliable) | 0 |
| Bar counting | Breakout entry (early trend) | +1 |
| Bar counting | Wedge/FBO entry (late/climax) | +1 |
| Bar counting | Range edge reversal (TR) | +1 |
| Day type | Strong trend day | +1 |
| Day type | Trading range day (fade extremes only) | 0 |
| Day type | Barbwire | -2 |

### Conviction Verdicts

| Score | Verdict | Action |
|-------|---------|--------|
| At least +4 | LONG/SHORT — HIGH conviction | Full position, swing target |
| +2 to +3 | LONG/SHORT — MEDIUM conviction | Standard position, scalp + swing portion |
| 0 to +1 | WAIT | Setup forming but not ready; note exact trigger level |
| -1 to -2 | FORGET | Skip — low probability, poor R:R |
| At most -3 | FORGET — strong reject | Do not even watch |

### IDX Override
- IDX stocks (`.JK`): no retail short-selling — only LONG setups allowed
- If bearish structure on IDX ticker — FORGET or WAIT (never SHORT)
- Non-IDX tickers (US, crypto, commodities): both LONG and SHORT allowed

## Execution Mode — Choose ONE

The skill supports two execution modes. **Use the `--analyze` flag for frictionless single-ticker analysis. Use sub-agents for batch scans.**

### MODE 1: Single-Ticker Pipeline (Primary — 0 approval prompts)

For single-ticker analysis. Run the ENTIRE pipeline in ONE `terminal()` call:

```bash
python3 /home/hermes/skill_backup/price-action-al-brooks/scripts/fetch_data.py --analyze TICKER
```

### MODE 2: Sub-agent Workflow (for batch scanning)

For scanning multiple tickers in parallel, use sub-agents as Stage 1 and Stage 2 runners.

## Scripts

### fetch_data.py v2
Fetches multi-timeframe OHLCV candle data + indicator snapshots via tvkit (TradingView WebSocket) + Scanner API.

### brooks_analysis.py (Tier-1 Engine)
```bash
python ~/.hermes/profiles/analyst/skills/trading/price-action-al-brooks/scripts/brooks_analysis.py AAPL_brooks.json
```

### backtest.py (Deterministic Backtester)
```bash
python3 backtest.py AAPL --bars 200 --show-trades
python3 backtest.py --list-setups
```

## Data Sourcing — Hard Rules

### Rule 1: fetch_data.py (tvkit/TradingView) is the ONLY primary data source.
### Rule 2: If the primary source fails — STOP. Tell the user.
### Rule 3: Never use cached data without explicit user consent.
### Rule 4: When the user confirms an exchange or ticker, try again.

## Brooks Language Only
Acceptable: wedge top/bottom, micro channel, trend bar, doji, inside bar, outside bar, barbwire, measured move, pullback, trading range, HH/HL/LH/LL, signal bar, breakout, failed breakout, reversal bar, trend resumption.
Forbidden: parabolic, blow-off top, capitulation, FOMO, overbought, oversold, Elliott Wave, Wyckoff, SMC, RSI, MACD, Fibonacci.

## Knowledge Base
**Source:** Al Brooks, Trading Price Action series
- Core: Universal price action (bar anatomy, counting, breakouts, close, EMA, risk, time frames) — `core.md`
- Book 1: Trends (26 chapters) — `trends.md` (load when trending)
- Book 2: Trading Ranges (32 chapters) — `ranges.md` (load when ranging)
- Book 3: Reversals (25 chapters) — `reversals.md` (load when reversal signals detected — overlay)
