# Price Action — Al Brooks Skill Review

**Reviewed:** 2026-06-06
**Reviewer:** Sage
**Scope:** Full stack — SKILL.md, book1-trends.md, book2-ranges.md, tier2-routing.md, references/entry_type_matrix.md, references/global_exchanges.md, scripts/fetch_data.py, scripts/brooks_analysis.py

---

## Table of Contents
1. [Critical Bugs (Must Fix)](#1-critical-bugs-must-fix)
2. [Framework Inaccuracies](#2-framework-inaccuracies)
3. [Missing Brooks Principles](#3-missing-brooks-principles)
4. [Script Improvements](#4-script-improvements)
5. [Bloat & Cleanup](#5-bloat--cleanup)
6. [Prioritized Action Plan](#6-prioritized-action-plan)

---

## 1. Critical Bugs (Must Fix)

### B1: Sign 12 (SoS) never fires — `bar_analysis_field()` is a dead stub
**File:** `scripts/brooks_analysis.py`
**Lines:** 248-253, 378-380
**Problem:** `compute_sos()` calls `bar_analysis_field(bars, 'pullback_count', {})` which always returns `{}`. The function body is literally:
```python
def bar_analysis_field(bars, field, default=None):
    return default
```
This means Sign 12 ("Pullback forms H2/L2 at 20-EMA") will **never** register as present. The conviction scoring depends on accurate SoS counts, so every analysis undercounts strength by at least 1.
**Fix:** Either remove Sign 12 from the SoS list OR wire `bar_analysis_field` to actually read from `compute_bar_analysis().pullback_count` which IS computed.

### B2: `_bar_scan_pullbacks` can never count >1 pullback
**File:** `scripts/brooks_analysis.py`, lines 729-759
**Problem:** The fallback pullback scanner has a `break` statement after the first countertrend bar found (line 752/755). It always returns at most `H:1` or `L:1`. This means when swing-based detection fails (no swing points), the fallback can't count L2/H2. Every analysis with ambiguous swing structure defaults to L1/H1.
**Fix:** Remove the `break` — continue scanning backward through the bar window, counting each countertrend run as a distinct pullback.

### B3: Sign 10 checks the wrong thing
**File:** `scripts/brooks_analysis.py`, lines 224-232
**Problem:** Brooks' Sign 10 is about the **absence** of big climaxes — i.e., no large countertrend bars. The code checks for **small bodies with close > 0.5**, which is a different concept entirely. This produces false positives for Sign 10, inflating the SoS count.
**Fix:** Reimplement: scan last 10 bars for any bar in the countertrend direction with body ≥ 70% of range. If none found, Sign 10 is present.

### B4: SoS rubric threshold mismatch (12 vs 14)
**File:** `SKILL.md` (conviction rubric) vs `scripts/brooks_analysis.py` (line 360)
**Problem:** 
- SKILL.md says: SoS count ≥ 12 → +1 conviction
- Code says: `total_present >= computable * 0.65` → 'strong_trend_likely' (with computable=21, that's 14/21 = 66%)
- Conviction code (line 876) checks `sos['count'] >= 12` which is consistent with the rubric
- But `brooks_intent` (line 976) checks `sos_int == 'strong_trend_likely'` to set countertrend = 'none_recommended'
- Result: At 12 signs, conviction gives +1 but intent filter is more lenient. At 14 signs, both kick in. The inconsistency means confidence and risk warnings are out of sync.
**Fix:** Align the three thresholds. Either change rubric to 14, or change code to match 12. Prefer keeping ≥12 (simpler, more conservative) and adjust `compute_sos` interpretation thresholds to match.

### B5: R:R scoring in rubric is computational dead code
**File:** `SKILL.md`, conviction rubric (lines 64-65)
**Problem:** The rubric awards +1 for "R:R at least 1:3" and -1 for "R:R under 1:1". But the Tier-1 engine (`brooks_analysis.py`) can't compute R:R — it requires signal bar location and entry price. The `compute_conviction_objective()` function doesn't even attempt it. The rubric promises analysis that doesn't exist.
**Fix:** Either remove R:R from the rubric (it's a Tier-2 subjective adjustment), or note clearly "**Tier-2 only** — computed by Stage 2 agent, not by engine."

---

## 2. Framework Inaccuracies

### F1: "Climax" listed as a Trend Phase — Brooks says it's a bar event
**File:** `references/entry_type_matrix.md` (line 14)
**Problem:** The matrix classifies "Climax" as a distinct trend phase alongside Early/Mid/Late/TR. Brooks explicitly says climax is **retrospective** — you can only identify it after it's happened. It's a bar-level or multi-bar event, not a phase. A climax can occur in early, mid, OR late trend.
**Severity:** Medium — misleads the agent into treating climax as a trading regime when it's really a signal.
**Fix:** Rename to "Climax Zone / Exhaustion" and clarify that it's identified BY the signs (gaps, big trend bars, MA gap), not as a structural phase. Or merge into Late Trend.

### F2: "20%+ from 20-EMA" threshold for climax is arbitrary
**File:** `references/entry_type_matrix.md` (line 14)
**Problem:** Brooks doesn't define a percentage. The threshold is imported from other frameworks. Different instruments have different typical deviations from EMA.
**Fix:** Use ATR-based detection instead: "price > 3× ATR from 20-EMA" or "consecutive 3+ trend bars that each fail to make a new high/low on the following bar."

### F3: Bull trend definition uses SMA8 > SMA20 > SMA50
**File:** `book1-trends.md` (line 19)
**Problem:** Brooks only uses the 20-EMA as his default moving average. He occasionally references the 50-SMA for larger context, but never the SMA8. The SMA8 is introduced here from another trader's framework.
**Fix:** Remove SMA8 from the standard definition. Keep trend classification to: price > 20-EMA, 20-EMA slope up, HH/HL structure. That's Brooks.

### F4: Sign definition #4 incorrectly described in book1-trends.md
**File:** `book1-trends.md` (line 83)
**Problem:** Sign #4 says "Little/no overlap of consecutive bar bodies" but in Brooks' original list, this is about "breakout gap" — the signal bar body is entirely above/below the prior bar's body range.
**Fix:** Align the 22-sign list with Brooks' original. The current list is a re-interpretation that lost fidelity. Cross-reference against Brooks Book 1, Chapter 4.

### F5: "DT/DB/H&S are continuation patterns, not reversals" — stated too absolutely
**File:** `book2-ranges.md` (line 9)
**Problem:** Brooks says these patterns are usually continuation in the context of a trend, but can be reversal patterns at trend extremes (e.g., double top after climax can be a reversal). The parenthetical "(Brooks context)" helps but the agent may over-apply the rule.
**Fix:** Add qualifier: "In a strong trend, DT/DB/H&S are usually continuation. At trend extremes (climax, wedge, 20-bar gap), they CAN be reversal. Context matters."

### F6: M2B/M2S labeled as H2/L2 synonym but they're not identical
**File:** `book1-trends.md` (line 169) and multiple locations
**Problem:** M2B = "Measured Move Buy" = H2 at the 20-EMA. The framework uses H2/L2 and M2B/M2S interchangeably. But:
- H2 is the SECOND pullback in a bull leg (bar counting)
- M2B is specifically the SECOND PULLBACK IN THE TREND that reaches the EMA
A pullback could be H2 in bar counting but not reach the EMA — it's not an M2B setup. The framework doesn't check EMA proximity.
**Fix:** Separate the concepts. H2/L2 = bar counting label. M2B/M2S = setup label requiring EMA touch. The compute_pullbacks function should add `ema_touch` field.

### F7: Consecutive closes on same side of EMA as a classifier input is not Brooks
**File:** `scripts/brooks_analysis.py` (classify_day_type, lines 460-471)
**Problem:** The day classifier uses `cons_above > 5` as a trend strength signal. Brooks mentions this as ONE of 22 signs of strength (Sign #21: No two consecutive closes on opposite side of MA). Using it as a primary day classifier input overweights it.
**Fix:** De-prioritize in day classifier. Let the SoS system handle it.

### F8: Losing Sequence concept missing from conviction system
**File:** `book2-ranges.md` line 118: "After multiple winners of same type → WAIT."
**Problem:** Brooks emphasizes the concept of "losing sequence" — after several profitable trades of the same type, the next one is less reliable. This is a key risk management principle absent from the conviction system.
**Fix:** Add a "consecutive signals" counter to the conviction system. After the engine/N-1 signal was profitable, reduce conviction by 1 for signal N.

---

## 3. Missing Brooks Principles

### M1: "Need Two Reasons" — Unimplemented as a gate
**File:** Mentioned in `book2-ranges.md` (line 250) but never operationalized
**Principle:** Brooks says always have 2+ reasons before entering. The conviction system gives a score but doesn't enforce "minimum 2 reasons." A setup could score +4 from a single reason (strong trend + good bar) which IS valid per Brooks' exceptions (line 254 says strong trend alone is valid as a reason), but the system doesn't articulate this.
**Fix:** Add a `reasons_summary` field to the analysis output listing the actual reasons present (signal bar, EMA pullback, trend alignment, SoS, second entry, etc.).

### M2: "First Pullback Sequence" — the 21-step trend weakening framework
**File:** Mentioned in `book2-ranges.md` (lines 103-118) but not computed
**Principle:** Brooks defines a 21-step sequence (in a bull→bear transition) from "bodies smaller" (step 1) through "major TL break" (step 16-17) to "larger TR" (step 18-21). This is the most comprehensive framework for detecting trend transitions and is completely absent from the analysis engine.
**Fix:** Implement a `trend_health_index` that maps recent bar characteristics to steps in the sequence. This lets the agent know if the trend is at step 3 (early weakening) vs step 11 (major violation approaching).

### M3: "Opening Range" concept completely absent
**Principle:** Brooks pays enormous attention to the first 30-min/hour range. The high/low of this range are key magnets for the day. The framework only has daily/weekly/h4 timeframes so this is structurally absent.
**Fix:** For daily timeframe analysis, add "first 2-3 bars" as a proxy for intraday opening range. Or note the limitation explicitly so the agent knows it's missing.

### M4: "Spike & Channel" as a complete lifecycle — incompletely modeled
**File:** `book1-trends.md` (lines 107-117) covers basics, but no computational detection
**Principle:** Brooks says almost every trend follows spike → channel → TR. The framework detects spikes (multiple trend bars) but doesn't detect:
- When the channel phase starts (bars developing tails, two-sided trading)
- When the channel breaks down into TR
**Fix:** Add channel detection: after a spike, track if subsequent bars have alternating direction, longer tails, body overlap >50%. When enough bars satisfy these, label phase as "channel" instead of "trending."

### M5: "Final Flag" concept missing
**Principle:** The last pullback before a major trend reversal. Identified as a shallow pullback after many bars of trend where the next leg tries but fails to make a new extreme. This is an important setup type for countertrend entries.
**Fix:** Add final flag detection in the pattern watch module. Conditions: trend ≥20 bars, last leg is shallow (<25% of prior leg), next bar(s) fail to extend trend.

### M6: "Dueling Lines" / competing trend lines absent
**Principle:** Brooks talks about competing trend channels — when there are two valid trend lines pointing in opposite directions, it's a micro TR and the resolution direction is the trade.
**Fix:** Compute trend channel lines from swing points and check for convergence/divergence. Add to pattern watch.

### M7: "H2 in trend = continuation, H2 in range = reversal" — only partially implemented
**File:** `book2-ranges.md` (line 148) — documented but code doesn't distinguish
**Problem:** The compute_conviction_objective gives +1 for L2/H2 regardless of context (line 904-909). In a trading range, H2 near the bottom is a buy setup, but the code doesn't verify range position.
**Fix:** Add a range_position check: if day_type is 'trading_range', verify the pullback is near the RANGE EXTREME before awarding +1.

### M8: "Bar counting resets on new leg" — not implemented
**File:** `book1-trends.md` (line 40) — documented but not in code
**Problem:** Brooks says pullback counting resets when a new leg begins. The code attempts this with leg-based counting but the leg detection is too unreliable to reset properly.
**Fix:** Improve leg detection and explicitly reset H/L counters at leg boundaries.

### M9: "Micro measuring gap" — highly specific Brooks pattern not detected
**File:** `book2-ranges.md` (lines 77-78) — documented only
**Principle:** 3 trending bars where bar 3 doesn't overlap bar 1. The pullback after this is a high-probability entry.
**Fix:** Add pattern detection: scan for 3 consecutive trend-direction bars where `min(bars[-1].close, bars[-1].open) > max(bars[-3].close, bars[-3].open)` (bull case).

### M10: "Failed breakout trap" detection oversimplified
**File:** `book2-ranges.md` (line 212) — documented as "fade logic" but not in code
**Principle:** A strong breakout bar that reverses 1-3 bars later is a fade setup. But 2+ consecutive trend bars means the breakout is real.
**Fix:** Add to pattern watch: detect breakout bar (>1× ATR push beyond prior swing/S/R level) followed by 1-3 bars of reversal.

---

## 4. Script Improvements

### S1: Multi-timeframe analysis for SoS Sign 19
**File:** `scripts/brooks_analysis.py`, `compute_sos()` lines 319-320
**Problem:** Sign 19 ("Larger timeframe also in trend") is hardcoded as `not_computable` even though weekly data is available in the input.
**Fix:** Compute weekly trend direction and compare with daily. Report present if both agree. This is ~10 lines of code and fixes an SoS hole.

### S2: Scanner API is synchronous, blocking event loop
**File:** `scripts/fetch_data.py`, `fetch_scanner()` lines 251-324
**Problem:** `fetch_scanner()` uses `urllib.request` (blocking I/O) inside an async context. This blocks the entire event loop during indicator fetching.
**Severity:** Low (scanner fetch is 1-2 seconds), but poor design.
**Fix:** Use `aiohttp.ClientSession` for async HTTP. Or make the scanner fetch non-optional and run in an executor thread.

### S3: TV Scanner columns are hardcoded by index — extremely fragile
**File:** `scripts/fetch_data.py`, SCANNER_COLUMNS list (lines 232-248) and fetch_scanner() (lines 283-321)
**Problem:** Column values are accessed by position (`raw[8]` for RSI, `raw[16]` for SMA20, etc.). If TradingView changes column order, every index breaks silently.
**Fix:** Build a mapping from column name to index dynamically: `col_map = {col: idx for idx, col in enumerate(SCANNER_COLUMNS)}`, then use `raw[col_map['RSI']]`. This way column order changes only require reordering the list, not updating every hardcoded index.

### S4: Swing detection is too primitive
**File:** `scripts/brooks_analysis.py`, `compute_trend_context()` in fetch_data.py (lines 783-791)
**Problem:** The swing detection requires: `high[i] > high[i-1] AND high[i] > high[i-2] AND high[i] > high[i+1]`. This misses:
- Double tops (equal highs)
- Last bar as swing high (no i+1 to compare)
- Swings in volatile markets (requires 3-bar separation)
**Fix:** Implement a proper swing detection using percent-based thresholds and allowing equal highs/lows as swing levels. Use `scipy.signal.argrelextrema` or a simple lookback/forward window.

### S5: Measured move projects from wrong reference point
**File:** `scripts/brooks_analysis.py`, lines 792-798
**Problem:** Bull measured move: `last_high['price'] + leg_extent`. This projects from the swing high with the leg's full height. But Brooks' measured move projects the leg 1 extent from the PULLBACK LOW, not from the swing high. The formula should be: `pullback_low + (leg1_high - leg1_low)`.
**Fix:** Use the pullback low (end of the correction after leg 1) as the projection base. This requires identifying the pullback low, not just the prior swing low.

### S6: H4 timezone issue — daily basis matters for time
**File:** `scripts/fetch_data.py`, TIMEFRAMES (lines 145-149)
**Problem:** The H4 timeframe uses `'240'` which is 240 minutes = 4 hours. But for crypto (24/7 market), 4-hour candles are clean. For stocks, H4 candles depend on exchange hours and may produce incomplete data.
**Fix:** Document that H4 data reliability depends on market type. Consider using H2 for greater granularity. Add a note that H4 on daily-indexed stocks may have uneven bar spacing.

### S7: `filter_brooks()` deletes indicators that brooks_analysis.py needs
**File:** `scripts/fetch_data.py`, lines 876-901
**Problem:** `filter_brooks()` strips `sma20`, `sma50`, `ema50` from trend_context. But `brooks_analysis.py`'s analyze() function receives the CLEANED data and uses `trend_context.get('ema20')` which survives because `filter_brooks()` only removes sma20/sma50/ema50. However, the data flow is confusing: the inline pipeline in SKILL.md DELETES `data['indicators']` entirely, then passes to brooks_analyze. The brooks_analyze function gets `indicators = {}` and falls back to trend_context.
**Fix:** Either:
(a) Don't delete indicators in the pipeline — just pass clean data
(b) Make brooks_analysis.py extract EMA from bars directly (it already does, line 764)
(c) Document this diamond dependency clearly

### S8: Scanner fields `Aroon.Up`, `Aroon.Down`, `ADX`, `CCI20` are fetched but never used
**File:** `scripts/fetch_data.py`, SCANNER_COLUMNS (lines 244-246)
**Problem:** Aroon, ADX, and CCI20 are non-Brooks indicators fetched in every scan. They consume bandwidth and processing time but are stripped by `filter_brooks()` and never used even in non-Brooks mode.
**Fix:** Remove from SCANNER_COLUMNS. Brooks analysis doesn't need them. If the user wants them in a different context, add them then.

### S9: `compute_indicators_from_bars()` computes RSI/MACD/Stoch which are anti-Brooks
**File:** `scripts/fetch_data.py`, lines 636-736
**Problem:** The fallback indicator computation recreates oscillators (RSI, MACD, Stochastic) from the OHLCV data. These are explicitly forbidden by the "Brooks Language Only" guardrail. The fallback should only compute EMA20 and ATR.
**Fix:** Remove or guard the oscillator functions. `compute_indicators_from_bars` should only compute EMA, ATR, and maybe Simple Moving Averages for trend context.

---

## 5. Bloat & Cleanup

### C1: 30+ sample JSON files in scripts/ — hundreds of KB of noise
**Files:** `scripts/*_raw.json`, `scripts/*_brooks.json`, `scripts/*_brooks_analysis.json`
**Total:** ~30 files, ~1MB+
**Problem:** These are cached analysis outputs from prior runs. They inflate the skill's size, serve no purpose for new users (the analysis would be stale), and create confusion ("should I use this file?").
**Fix:** Delete all `scripts/*.json` files. The skill should produce fresh data on every run. Move a single representative example to `examples/` if teaching purposes needed.

### C2: `UNKNOWN_raw.json` and `--help_raw.json` — literal garbage
**Problem:** These are artifacts from incorrect invocations (`python fetch_data.py --help` captured the help text as JSON). They should never have been committed.
**Fix:** Delete immediately.

### C3: `__pycache__/` directories — gitignored but present on disk
**Problem:** Compiled Python bytecode. Adding nothing to the code review. Not version controlled, but taking space.
**Fix:** Run `find . -type d -name __pycache__ -exec rm -rf {} +`

### C4: `references/global_exchanges.md` duplicates the Python dict
**Problem:** The exchange registry lives in both the `.md` doc and `fetch_data.py`'s `GLOBAL_EXCHANGES` dict.
**Fix:** Move to a single source of truth. Approach: Use the Python dict as truth. Auto-generate the .md doc from the Python dict with a docstring or `__doc__`. Or just add a comment in the .md: "Source: scripts/fetch_data.py — GLOBAL_EXCHANGES dict. This file is a human reference. For truth, read the code."

### C5: The inline pipeline code in SKILL.md is ~50 lines of double-maintained Python
**File:** `SKILL.md`, lines 101-146
**Problem:** This Python code is a fragile copy of the analysis flow. When `fetch_data.py` or `brooks_analysis.py` change (new parameters, new output keys), the inline pipeline will silently break. It's maintained in TWO places with no synchronization.
**Fix:** Add a single CLI entry point that does the pipeline in ONE command:
```bash
python scripts/pipeline.py TICKER
```
Or use the existing `--analyze` flag (`fetch_data.py --analyze TICKER`) which already does both steps. Document that instead of the inline Python snippet.

### C6: `bar_analysis_field()` is completely dead code
**File:** `scripts/brooks_analysis.py`, lines 378-381
**Problem:** Function exists only to be called by compute_sos, but always returns `None`. Either remove it or implement it properly.
**Fix:** Either implement as a proper data bridge OR remove the function and inline the relevant data access.

### C7: `last_5_bars` in trend_context is display data, not analysis data
**File:** `scripts/fetch_data.py`, lines 802-806
**Problem:** The last 5 OHLCV bars are included in the output for display. They consume JSON space (~100 bytes/bar = 500 bytes per TF) and are never used by brooks_analysis.py.
**Fix:** Either remove, or make it conditional (`--verbose` flag). For the standard pipeline, it's decorative.

### C8: H4 data is fetched but never analyzed
**File:** `scripts/fetch_data.py` fetches H4; `scripts/brooks_analysis.py` only uses daily
**Problem:** The whole skill fetches 3 timeframes but only analyzes 1 (daily). The weekly and H4 data exist only as display context. This is a ~60% efficiency loss in data fetching.
**Fix:** Either:
(a) Add weekly/H4 analysis to brooks_analysis.py (recommended — Sign 19 needs it)
(b) Remove H4 from default fetch and add `--h4` flag for on-demand
(c) Keep as is but document: "H4 fetched for agent display only; analysis engine uses daily"

---

## 6. Prioritized Action Plan

### Phase 1: Critical Fixes (Before First Live Use)
| # | Item | Effort | Impact |
|---|------|--------|--------|
| B1 | Fix `bar_analysis_field()` or remove SoS Sign 12 | 20 min | **High** — currently always undercounts SoS |
| B2 | Fix `_bar_scan_pullbacks` break → continue | 5 min | **High** — fallback can't count >1 pullback |
| B3 | Reimplement SoS Sign 10 correctly | 15 min | **Medium** — false positives inflate SoS |
| B4 | Align SoS thresholds (12 vs 14) | 10 min | **High** — conviction/intent inconsistency |
| B5 | Fix R:R rubric to match capabilities | 10 min | **Medium** — misleading documentation |
| C2 | Delete garbage files (`UNKNOWN_raw.json`, `--help_raw.json`) | 1 min | Low — cleanup |

### Phase 2: Framework Corrections
| # | Item | Effort | Impact |
|---|------|--------|--------|
| F1 | Rename/restructure "Climax" as event not phase | 30 min | **High** — misleads entry selection |
| F3 | Remove SMA8 from Bull Trend definition | 5 min | Medium — Brooks purity |
| F6 | Separate H2/L2 counting from M2B/M2S EMA proximity | 2-3h | **High** — affects entry quality filtering |
| F8 | Add losing-sequence concept to conviction | 1h | Medium — risk management |

### Phase 3: Missing Principles
| # | Item | Effort | Impact |
|---|------|--------|--------|
| M2 | Implement First Pullback Sequence (21-step weakening) | 4h | **High** — most valuable missing analysis |
| M4 | Add channel detection after spike | 2h | Medium — better trend phase detection |
| M5 | Add final flag detection | 1h | Medium — catches late-trend reversals |
| M7 | Add range position context to H2/L2 scoring | 1h | Medium — fixes TR conviction errors |
| M9 | Detect micro measuring gap | 30 min | Low — niche pattern |
| M10 | Add failed breakout trap detection | 1h | Medium — common setup |

### Phase 4: Script Quality
| # | Item | Effort | Impact |
|---|------|--------|--------|
| S1 | Multi-TF analysis for SoS Sign 19 | 30 min | Medium — fills SoS gap |
| S3 | Dynamic scanner column mapping | 1h | Medium — prevents future breakage |
| S4 | Proper swing detection | 2-3h | **High** — affects leg/pullback/MM accuracy |
| S5 | Fix measured move projection base | 30 min | Medium — target accuracy |
| S8 | Remove unused scanner columns (Aroon, ADX, CCI20) | 5 min | Low — bandwidth savings |

### Phase 5: Cleanup & Efficiency
| # | Item | Effort | Impact |
|---|------|--------|--------|
| C1 | Delete all sample JSON files | 5 min | Medium — reduces skill size 80% |
| C4 | Single-source exchange registry | 30 min | Low — maintainability |
| C5 | Consolidate pipeline into single CLI entry point | 1-2h | **High** — eliminates doc/code divergence |
| C6 | Remove or implement `bar_analysis_field()` | 10 min | Medium — dead code |
| C7 | Remove decorative `last_5_bars` or make conditional | 15 min | Low — JSON size savings |
| C8 | Either analyze H4/weekly or don't fetch them | 2h | Medium — efficiency |

### Phase 6: Documentation
| # | Item | Effort | Impact |
|---|------|--------|--------|
| — | Clarify Tier-1 vs Tier-2 boundaries in SKILL.md | 30 min | Medium — prevents agent confusion |
| — | Add Brooks terminology glossary with original source refs | 1h | Medium — quality-of-life |
| — | Document all known limitations (no intraday, no opening range, H4 unused) | 20 min | Low — transparency |

---

## Summary Statistics

| Category | Count | Critical | High | Medium | Low |
|----------|-------|----------|------|--------|-----|
| Bugs | 5 | 3 (B1,B2,B4) | 1 (B3) | 1 (B5) | — |
| Framework Inaccuracies | 8 | — | 2 (F1,F6) | 4 | 2 |
| Missing Principles | 10 | — | 1 (M2) | 6 | 3 |
| Script Improvements | 9 | — | 2 (S4,S5) | 4 | 3 |
| Bloat/Cleanup | 8 | — | 1 (C5) | 2 | 5 |
| **Total** | **40** | **3** | **7** | **17** | **13** |

**Estimated effort for full overhaul:** ~20-25 hours
**Estimated effort for Phase 1 (Critical):** ~1 hour
**Estimated effort for Phase 1+2 (Critical + Framework):** ~4 hours
