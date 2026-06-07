# Backtesting Decision Layer — Al Brooks Price Action

## Purpose

This document codifies the entry/exit rules that the LLM Tier-2 agent applies
during daily analysis, so the backtester can apply them deterministically over
historical data without LLM calls.

**Key principle:** The Tier-1 engine (`brooks_analysis.py`) computes what it
can from OHLCV data. This decision layer applies the judgment rules the LLM
would apply, using the engine's outputs as inputs.

---

## Tier-1 Engine Outputs Used

| Output | Source | Description |
|--------|--------|-------------|
| `day_type.hypothesis` | `classify_day_type()` | strong_bull, strong_bear, tfo_bull, tfo_bear, trading_range, ambiguous |
| `context.trend` | `compute_trend_context()` | bull_trend, bear_trend, no_trend |
| `pullbacks.structure_based.current_leg.pullback_count` | `compute_pullbacks()` | L1, L2, L3, H1, H2, H3, etc. |
| `pullbacks.structure_based.current_leg.ema_proximity` | `compute_pullbacks()` | at_ema, near_ema, far |
| `conviction_objective.subtotal` | `compute_conviction()` | Integer score (agent adds adjustments) |
| `trend_health.stage` | `compute_trend_health()` | trend_intact, early_weakening, late_stage, transition_complete |
| `patterns` | `detect_patterns()` | wedge_top, wedge_bottom, spike_bull, spike_bear, two_bar_reversal |
| `reversal_signals` | `detect_reversal_signals()` | List of active reversal conditions |
| `signs_of_strength.interpretation` | `compute_sos()` | strong_trend_likely, moderate_bullish, etc. |
| `context.price` | Current close price | Used for range position calculation |
| `context.atr` | Average True Range | For stop/target sizing |
| `context.swing_highs/lows` | Swing detection | For trading range bounds |

---

## Decision Matrix — Entry Rules

### Priority Order (highest to lowest)

Entries are evaluated in priority order. The first matching rule wins.

1. **M2B/M2S** — Mid-trend pullback (H2/L2 at EMA)
2. **Breakout Pullback** — Early trend (L1/H1 at breakout level)
3. **Breakout Entry** — Aggressive early trend (on spike bar)
4. **Range Edge Reversal** — Trading range (price at extreme + reversal signal)
5. **Failed Breakout (FBO)** — Trading range (BO fails in 1-3 bars)
6. **Wedge Reversal** — Late trend (wedge at trend channel line)
7. **Climax Reversal** — Exhaustion (consecutive strong bars + reversal bar)
8. **20 Gap Bar Touch** — Any trend (first MA touch after extended gap)

---

### 1. M2B / M2S — Standard Pullback Entry (Mid-Trend)

**When:** Strong trend or TFO, with H2/L2 completing at EMA.

**Conditions (ALL must be true):**
- `day_type.hypothesis` ∈ {strong_bull, strong_bear, tfo_bull, tfo_bear}
- `context.trend` matches day_type direction (bull for strong_bull, etc.)
- `pullback_count` = L2 (for LONG) or H2 (for SHORT)
- `ema_proximity` ∈ {at_ema, near_ema}
- `trend_health.stage` ∈ {trend_intact, early_weakening}
- `conviction_objective.subtotal` ≥ 1

**Entry:**
- LONG: Buy 1 tick above signal bar high (the L2 completion bar)
- SHORT: Short 1 tick below signal bar low (the H2 completion bar)

**Stop:**
- LONG: Below the pullback's lowest bar (or 0.3× ATR below entry if pullback low is too close)
- SHORT: Above the pullback's highest bar

**Target:**
- Measured move: leg 1 height projected from entry
- Minimum: 2× ATR from entry
- Maximum: test of prior trend extreme

**Exit rules:**
- Stop loss hit
- Target hit
- Time stop: 20 bars max
- Trend flip: always-in direction reverses (health stage → late_stage/transition_complete)

**Conviction adjustment:**
- H2 at EMA in strong trend: +1 (standard setup)
- L2 at EMA in strong trend: +1
- Second entry (retry after first L2/H2 fails): +1
- Weak signal bar in strong trend: +0 (expected, don't deduct)

---

### 2. Breakout Pullback — Early Trend Entry

**When:** Fresh breakout from trading range, first pullback to breakout level.

**Conditions (ALL must be true):**
- `day_type.hypothesis` ∈ {strong_bull, strong_bear, tfo_bull, tfo_bear}
- `context.trend` matches direction
- `pullback_count` = L1 (for LONG) or H1 (for SHORT)
- `ema_proximity` ∈ {at_ema, near_ema}
- `patterns.spike_bull` or `patterns.spike_bear` is True (breakout spike exists)
- `trend_health.stage` = trend_intact
- `conviction_objective.subtotal` ≥ 1

**Entry:**
- LONG: Buy 1 tick above L1 signal bar high
- SHORT: Short 1 tick below H1 signal bar low

**Stop:** Below/above the breakout level (prior swing high/low)

**Target:** Measured move from spike height

**Exit rules:**
- Stop loss hit
- Target hit
- Time stop: 15 bars max
- Trend flip

**Conviction adjustment:**
- First pullback after strong spike: +1
- L1/H1 (less reliable than L2/H2): +0
- Breakout bar was strong (body ≥70%): +1

---

### 3. Range Edge Reversal — Trading Range Entry

**When:** Market in trading range, price at extreme edge with reversal signal.

**Conditions (ALL must be true):**
- `day_type.hypothesis` = trading_range
- Price position in range: bottom 25% (for LONG) or top 25% (for SHORT)
- **Signal confirmation** (at least ONE):
  - Reversal bar (bull/bear bar with body ≥40%, tail ≥33%)
  - H2/L2 completing at range edge
  - Two-bar reversal pattern
  - Wedge pattern at edge
- `conviction_objective.subtotal` ≥ 0 (lower threshold for range fades)

**Range position calculation:**
```
range_high = max(recent swing highs)
range_low = min(recent swing lows)
price_position = (price - range_low) / (range_high - range_low)
```

**Entry:**
- LONG (at bottom): Buy 1 tick above reversal bar high
- SHORT (at top): Short 1 tick below reversal bar low

**Stop:** Beyond the range extreme (beyond swing low/high)

**Target:** Opposite side of range (scalp)

**Exit rules:**
- Stop loss hit
- Target hit (opposite range extreme)
- Time stop: 15 bars max (range trades are quick)
- Price moves to middle of range (take partial profit)

**Conviction adjustment:**
- H2/L2 at range edge: +1
- Reversal bar at edge: +1
- Price in extreme 10% of range: +1
- No clear signal (just price position): -1
- Barbwire (3+ overlapping doji): -2

---

### 4. Failed Breakout (FBO) — Range Entry

**When:** Breakout from trading range fails within 1-3 bars.

**Conditions (ALL must be true):**
- `day_type.hypothesis` = trading_range
- Strong breakout bar (body ≥60%) in one direction
- Next 1-3 bars: reversal bar or opposite trend bar closing back inside range
- Breakout did NOT produce 2+ consecutive trend bars (if 2+ trend bars, BO likely real)

**Entry:**
- LONG (bear BO fails): Buy 1 tick above the reversal bar that signals failure
- SHORT (bull BO fails): Short 1 tick below the reversal bar

**Stop:** Beyond the breakout bar extreme

**Target:** Opposite side of range

**Exit rules:**
- Stop loss hit
- Target hit
- Time stop: 10 bars max (FBO moves are sharp)

**Conviction adjustment:**
- Breakout bar had large body + small tails: +1 (trapped traders = fuel)
- Breakout only 1 bar before reversal: +1
- Breakout pulled back >⅔ of bar height: +1

---

### 5. Wedge Reversal — Countertrend Entry (Late Stage)

**When:** Trend in late stage, wedge pattern at trend channel line.

**Conditions (ALL must be true):**
- `trend_health.stage` ∈ {late_stage, transition_complete}
- `patterns.wedge_top` (for SHORT) or `patterns.wedge_bottom` (for LONG)
- `reversal_signals` is non-empty
- `conviction_objective.subtotal` ≥ 1

**Entry:**
- LONG (wedge bottom in bear trend): Buy 1 tick above reversal bar high
- SHORT (wedge top in bull trend): Short 1 tick below reversal bar low

**Stop:** Beyond the wedge extreme (3rd push high/low)

**Target:** Measured move from wedge height

**Exit rules:**
- Stop loss hit
- Target hit
- Time stop: 20 bars max
- **Second entry preferred**: Most wedge reversals need a second entry (higher low after initial reversal)

**Conviction adjustment:**
- Wedge overshoot of trend channel line: +1
- 3+ pushes in wedge: +1
- Strong reversal bar (body ≥60%): +1
- Countertrend in strong trend: -2 (default penalty, offset by reversal signals)

---

### 6. 20 Gap Bar Touch — Exhaustion Entry

**When:** Price has been away from MA for 20+ bars, finally touches MA.

**Conditions:**
- `pullbacks.structure_based.current_leg.gap_bar_count` ≥ 20 (or equivalent metric)
- First bar touching MA after extended gap
- `day_type.hypothesis` ∈ {strong_bull, strong_bear, tfo_bull, tfo_bear}

**Entry:**
- LONG (bull trend, price touches MA from above): Buy 1 tick above signal bar
- SHORT (bear trend, price touches MA from below): Short 1 tick below signal bar

**Stop:** 1 tick beyond the gap bar extreme

**Target:** Test of trend extreme (swing trade)

**Exit rules:**
- Stop loss hit
- Target hit
- Time stop: 25 bars max

**Conviction adjustment:**
- After climax (3+ consecutive strong bars): +1
- First MA touch: +1
- Second MA gap bar: +1 (more reliable)

---

### 7. Breakout Entry — Aggressive Early Trend (On Spike Bar)

**When:** Fresh breakout from trading range, entering ON the spike bar (not waiting for pullback).

**Conditions (ALL must be true):**
- `day_type.hypothesis` ∈ {strong_bull, strong_bear, tfo_bull, tfo_bear}
- `context.trend` matches direction
- `patterns.spike_bull` or `patterns.spike_bear` is True (breakout spike detected)
- Spike bar body ≥ 60% (strong breakout bar)
- Spike bar range > 1.5× ATR (large move)
- `trend_health.stage` = trend_intact
- `conviction_objective.subtotal` ≥ 1

**Entry:**
- LONG: Buy at market or 1-2 ticks above spike bar close
- SHORT: Short at market or 1-2 ticks below spike bar close

**Stop:** Below/above the spike bar low/high (tight stop)

**Target:** Measured move from spike height (aggressive target)

**Exit rules:**
- Stop loss hit
- Target hit
- Time stop: 10 bars max (breakout trades are fast)
- If next bar is opposite trend bar → exit immediately (breakout failing)

**Conviction adjustment:**
- Strong spike (body ≥70%, small tails): +1
- Multiple breakout levels broken (EMA, swing H/L): +1
- Spike only 1 bar before pullback: +0 (less reliable)

**Risk:** This is aggressive — entering on the spike bar itself. Use smaller position size. If breakout fails, loss is quick but small (tight stop).

---

### 8. Climax Reversal — Exhaustion Fade

**When:** Trend exhaustion after 2+ consecutive strong trend bars, fade with reversal bar.

**Conditions (ALL must be true):**
- `trend_health.stage` ∈ {early_weakening, late_stage, transition_complete}
- Recent bars show exhaustion signs:
  - 2+ consecutive strong trend bars (body ≥60%)
  - OR bars with body ≥80% (climax bars)
  - OR range >1.8× trailing average (expansion)
- Reversal bar appears (opposite direction, body ≥40%)
- `conviction_objective.subtotal` ≥ 1

**Entry:**
- LONG (after bear climax): Buy 1 tick above reversal bar high
- SHORT (after bull climax): Short 1 tick below reversal bar low

**Stop:** Beyond the climax extreme (highest/lowest bar of the exhaustion sequence)

**Target:** 1.5× ATR from entry (quick scalp) or test of prior swing level

**Exit rules:**
- Stop loss hit
- Target hit
- Time stop: 10 bars max (climax fades are quick)
- If trend resumes with strong bar → exit immediately

**Conviction adjustment:**
- 3+ consecutive strong bars: +1
- Bars with body ≥80% (climax): +1
- Range >1.8× average (expansion): +1
- Countertrend in strong trend: -2 (default penalty, offset by exhaustion signs)

**Note:** This is different from wedge reversal. Wedge reversal is about pattern (3 pushes at trend channel line). Climax reversal is about exhaustion (consecutive strong bars, expansion). Both can occur in late-stage trends.

---

## Decision Matrix — Exit Rules

### Priority Order (checked each bar while in position)

1. **Stop loss** — Price hits stop → exit immediately
2. **Target hit** — Price reaches target → exit
3. **Time stop** — Bars held exceeds limit → exit at market
4. **Trend flip** — Always-in direction reverses AND health stage = late_stage/transition_complete → exit at market
5. **End of data** — Close position at market price

---

## Conviction Scoring — Deterministic Version

The Tier-1 engine provides `conviction_objective.subtotal`. The backtester
applies these deterministic adjustments:

| Factor | Condition | Adjustment |
|--------|-----------|------------|
| Trend alignment | With-trend (direction matches trend) | +1 |
| Trend alignment | Counter-trend | -2 |
| Signal bar quality | Strong trend bar (body ≥70%, small tails) | +1 |
| Signal bar quality | Weak bar in strong trend | +0 (don't deduct) |
| Signs of Strength | ≥12 signs | +1 |
| Signs of Strength | ≤5 signs | -1 |
| Second entry | Retry after first fails | +1 |
| Pullback count | H2/L2 at EMA (standard) | +1 |
| Pullback count | H1/L1 (first pullback) | +0 |
| Breakout entry | Early trend | +1 |
| Range edge | TR fade | +1 |
| Day type | Strong trend | +1 |
| Day type | Trading range | +0 |
| Day type | Barbwire | -2 |
| R:R ratio | ≥1:3 | +1 |
| R:R ratio | <1:1 | -1 |

**Final conviction → action:**
- ≥ +4 → HIGH conviction (full position, swing target)
- +2 to +3 → MEDIUM conviction (standard size, scalp + swing)
- 0 to +1 → WAIT (setup forming, note trigger)
- -1 to -2 → FORGET (skip)
- ≤ -3 → FORGET, strong reject

**Backtester threshold:** Only enter trades with final conviction ≥ +2.

---

## Position Sizing (Backtester)

- Fixed position size per trade (e.g., 1% of account risk)
- Risk = |entry - stop|
- Position size = risk_amount / risk_per_share

---

## IDX Override

- IDX stocks (`.JK`): no retail short-selling → only LONG setups allowed
- If bearish structure on IDX ticker → skip trade

---

## Known Limitations

1. **Day type classifier is conservative** — rarely classifies as "strong_bull/bear". Most markets classified as "ambiguous" or "trading_range". The backtester will generate fewer trend-following trades than a human trader would take.

2. **No intraday data** — Brooks emphasizes first 30-min high/low as key magnets. Daily-only analysis misses this.

3. **Pullback counting can lag** — The engine may not detect H2/L2 in real-time. The backtester uses the engine's count at each window.

4. **Swing detection is primitive** — Misses double tops/bottoms and equal extremes. Range position calculation is approximate.

5. **No volume analysis** — Volume signs of strength are weakly computed. Take volume-based signals with caution.

6. **Reversal signals are event-based** — The engine flags reversal conditions, but true reversal can only be confirmed after the fact. The backtester may enter countertrend too early.

7. **Signal bar quality is not fully assessed** — The engine classifies bars (trend_bull, reversal_bull, etc.) but doesn't assess tail/body ratios in context. The backtester uses simplified checks.

---

## Example Trade Flow

**Scenario: AAPL in trading range, price at bottom**

```
Engine output:
  day_type.hypothesis = trading_range
  context.trend = bull_trend
  pullback_count = L2
  ema_proximity = far
  conviction_objective.subtotal = 1
  price_position = 0.15 (bottom 15% of range)

Decision:
  1. Check M2B/M2S → day_type not strong → SKIP
  2. Check breakout pullback → no spike → SKIP
  3. Check range edge → YES (price at bottom 25%)
     - Signal confirmation? Check last bar: reversal_bull with body=45% → YES
     - Conviction: subtotal=1 + range_edge=1 = 2 → MEDIUM
     - Enter LONG at reversal bar high
     - Stop: below range low
     - Target: opposite side of range

Trade:
  Entry: $185.50 (reversal bar high)
  Stop: $182.00 (range low - 0.3×ATR)
  Target: $195.00 (opposite range extreme)
  Risk: $3.50/share
  Reward: $9.50/share
  R:R: 2.7:1
  Conviction: 2 (MEDIUM)
  Action: Enter LONG, scalp portion at $190, swing portion to $195
```

---

## Testing Checklist

Before accepting a backtest result, verify:

- [ ] Entry conditions match the rule (day_type, pullback_count, ema_proximity all correct)
- [ ] Stop loss is beyond the signal bar extreme
- [ ] Target is at least 1.5× ATR from entry
- [ ] R:R ratio is ≥ 1:1
- [ ] Conviction score is ≥ +2
- [ ] Position was not entered during barbwire
- [ ] IDX stocks are LONG-only
- [ ] Time stop was applied if held too long
