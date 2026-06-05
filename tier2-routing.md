# Tier-2 Routing Guide — Agent Decision Rules

This guide replaces the full book-reading workflow when `brooks_analysis.py` has already computed Tier-1 outputs. The agent receives `brooks_analysis.json` (~2–3 KB) plus these rules (~50 lines) instead of raw OHLCV + 400+ lines of book text.

---

## Workflow

```
brooks_analysis.json + tier2-routing.md
    │
    ▼
Stage 2 Agent produces:
  - Always-In direction (subjective)
  - Pattern evolution assessment
  - Signal bar quality in context
  - Trader's Equation probability
  - Final conviction score (Tier-1 + agent adjustment)
  - Entry management (scalp vs swing sizing)
```

---

## 1. Always-In Direction

**Not fully computable.** Use Tier-1 outputs as inputs, but own the call:

| Input | What to check |
|-------|---------------|
| `context.trend` | Primary bias, but can be stale |
| `signs_of_strength.interpretation` | "strong_trend_likely" → with-trend only |
| `day_type.hypothesis` | Strong trend → low bar for entries; TR → neutral AI |
| `pullbacks.current_leg` | Which pullback are we in? H2 at EMA is higher prob |
| `pattern_evolution_watch` | Wedge pending → AI direction may be reversing |

**Override rules:**
- SoS ≥ 12 → with-trend AI, do not consider countertrend
- Barbwire day → no clear AI; fade extremes
- Wedge top in bull trend → AI may be shifting (watch bar by bar)
- Trend says bull but day type says ambiguous → trust structure, look at H4

---

## 2. Signal Bar Quality — Context > Shape

Do not evaluate signal bars mechanically. The meaning depends on trend stage:

| Context | What a weak bar means |
|---------|----------------------|
| Strong trend (SoS ≥ 12) | Weak bar = feature, not warning. Trend resumes. |
| Strong trend, H2/L2 pullback | Low-energy pullback to EMA = standard setup |
| Trading range | Mixed bars = normal. Fade extremes. |
| Barbwire | Weak bars = uncertainty. Walk away or scalp. |
| After wedge | Weak bar = potential reversal first leg |

**Rule:** If `brooks_intent.warnings` mentions *"Weak signal bars... expected"*, do not deduct from conviction. If day type is `trading_range`, mixed bars are baseline.

---

## 3. Trader's Equation — Probability Estimate

`conviction_objective.subtotal` gives the raw score. **You adjust for probability.**

**Formula:**
```
P(win) × avg_reward > P(loss) × avg_risk

Where P is your subjective probability estimate based on:
  - Signal bar reliability at this stage of trend/TR
  - Current pullback number: L2 at EMA > L1 at EMA
  - Measured move target attainability (how far to target?)
  - Fail rate of current pattern type
```

**Adjustment rules:**
- Strong trend + L2/H2 at EMA: P(win) ≈ 70–80% → edge is clear
- Trading range + 2nd entry: P(win) ≈ 60–70% → marginal edge
- Barbwire + any entry: P(win) < 50% → no edge
- First pullback (L1/H1): P(win) ≈ 50–60% → reduce conviction by 1
- Countertrend in strong trend: P(win) < 30% → do not take

Finally: set conviction = `conviction_objective.subtotal` + your probability/context adjustment.

---

## 4. Pattern Evolution — What to Watch

Tier-1 provides `pattern_evolution_watch.watch_items`. Your job:

- **Is the pattern evolving or stable?** An inside bar on bar 2 of the pattern is different from bar 5.
- **Is the wedge still holding?** If price broke wedge line, it's no longer a wedge.
- **Is the spike/channel still intact?** Spike → channel is the strongest trend pattern.
- **Are we in a failed breakout?** Breakout bar closes weak, next bar fails to follow = failure → fade.

**Key Brooks rule:** Patterns morph. A wedge top that fails becomes a flag. A spike that stalls becomes a trading range. The Tier-1 snapshot can't capture this — you must.

---

## 5. Conviction Score — Final

Start with `conviction_objective.subtotal`, then adjust:

| Adjustment factor | Value range |
|-----------------|-------------|
| Trader's Equation edge | +1 if clear, −1 if unclear |
| Pattern evolution supports entry | +1 |
| Pattern evolution warns against | −1 |
| Second entry (same setup tried before) | +1 |
| Signal bar context | ±0–1 |
| Countertrend (if taking it despite warnings) | −2 |
| H4 timeframe aligns with daily | +1 |
| H4 timeframe contradicts | −1 |

**Final score → verdict:**
- ≥ +4 → HIGH conviction (full position, swing target)
- +2 to +3 → MEDIUM conviction (standard size, scalp + swing)
- 0 to +1 → WAIT (setup forming, note trigger)
- −1 to −2 → FORGET (skip)
- ≤ −3 → FORGET, strong reject

---

## 6. Countertrend Exceptions

The only exceptions to "countertrend in strong trend = no":

1. **Climax reversal** — after extreme wedge, first strong countertrend bar with big tail
2. **Double top/bottom failure** — trend tests but fails to break, the failed attempt is the entry
3. **L2 at range extreme** — in a trading range, buying H2 at bottom or selling L2 at top

**If none of these apply, do not fade the trend.** `brooks_intent.countertrend` will say "none_recommended" when SoS is high.

---

## 7. Entry Management

- **HIGH conviction:** Enter at market or tight limit at pullback EMA. Swing target = measured move.
- **MEDIUM conviction:** Scalp the entry, trail stop after 1 ATR profit. Second half swings.
- **WAIT:** Set alert at trigger level. Do not pre-enter.
- **FORGET:** Do not watch. Move on.

---

## 8. IDX Override (`.JK` tickers)

- No retail short-selling on IDX.
- Only LONG setups allowed.
- If bearish structure → verdict is FORGET or WAIT, never SHORT.
- Filter out anything with `direction: SHORT` in your output.

---

## What You DON'T Need

You do NOT need to:
- Read raw OHLCV bars (Tier-1 already processed them)
- Re-derive pullback counts from bar scans (already computed)
- Tally SoS from bar-by-bar walkthrough (already counted)
- Compute measured moves from swing structure (already projected)
- Remember day type rules from books (classifier provided hypothesis)

**You only need to apply judgement where the data can't.**
