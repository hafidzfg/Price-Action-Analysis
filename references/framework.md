# 🎯 Price Action Framework — Al Brooks Trilogy

> **Master framework for ALL trading analysis output.**
> Every ticker deep dive MUST follow this framework.
> Brooks terminology only — no Elliott Wave, no Wyckoff, no SMC.

---

## 1. Core Philosophy

Market selalu di suatu titik spektrum: **extreme trend ↔ extreme trading range** (Ch 1). Identifikasi posisi di spektrum ini dulu sebelum analisis apapun.

- **Always-In direction**: di setiap momen, kalo lo dipaksa milih long atau short, itu always-in direction-nya. Hampir semua always-in flip butuh SPIKE searah dulu.
- **Trader's Equation**: prob × reward > (1 − prob) × risk. Bukan rasio R:R kaku — keputusan entry harus lewat filter ini.
- **Dua jenis bar**: trend bar (momentum, body ≥ ~60% range) dan doji (equilibrium, body < ~40% range). Semua bar masuk salah satu dari dua ini.
- **Trend dulu**: klasifikasi trend atau trading range sebelum analisis bar individual.
- **Weak signals ≠ weak trend**: sinyal jelek justru FEATURE dari strong trend. Kalo setup terlihat perfect dan easy, berarti trend tidak kuat.
- **Dua kaki**: market selalu coba melakukan sesuatu dua kali. Berlaku di semua konteks (Ch 20).

---

## 2. Trend Definitions

### Bull Trend
| Criterion | Higher TF (Daily) | Lower TF (4H/1H) |
|-----------|------------------|-----------------|
| Structure | Higher highs + higher lows | Price above 20-EMA |
| Bars | Majority bull trend bars (body ≥ 60%) | Small/bear bars are pullbacks |
| EMA | Price above 20-EMA, slope up | 20-EMA slope supports |
| SMA alignment | SMA8 > SMA20 > SMA50 | — |
| Pullbacks | Shallow, 1-2 legs, reversed quickly | H1/H2 at/near 20-EMA |
| Signs of Strength | ≥ 12 signs from checklist | — |

### Bear Trend
| Criterion | Higher TF (Daily) | Lower TF (4H/1H) |
|-----------|------------------|-----------------|
| Structure | Lower highs + lower lows | Price below 20-EMA |
| Bars | Majority bear trend bars | Small/bull bars are pullbacks |
| EMA | Price below 20-EMA, slope down | 20-EMA slope supports |
| SMA alignment | SMA8 < SMA20 < SMA50 | — |
| Pullbacks | Shallow, 1-2 legs | L1/L2 at/near 20-EMA |

### Trading Range
- Overlapping bars, alternating direction
- 20-EMA mostly flat
- No clear always-in
- Breakouts fail ~2/3 of the time
- Fade extremes (sell high, buy low), especially second signal
- Barbwire (3+ overlapping doji bars) = AVOID trading, tunggu breakout dengan follow-through

```
BULL:  ↗↗↗↗↗↗↗    BEAR:  ↘↘↘↘↘↘↘    TR:  ↗↘↗↘→↗↘↗↘→
       ╱─╲─╱─╲               ╱─╲─╱─╲         ╱─╲──╱─╲
      ╱   ╲   ╲             ╱   ╲   ╲
```

---

## 3. Signal Bars

### Strong Signal Bars
| Criteria | Detail |
|----------|--------|
| Body size | ≥ 60% of bar range (strong = 70%+) |
| Wick/shadow | Small tails — indicates urgency |
| Close position | Top 25% (bull) / bottom 25% (bear) of range |
| Context | In trend direction, at/near 20-EMA, after pullback |
| Signal bar type | Trend bar OR reversal bar (Ch 5 criteria) |

### Weak / "Ugly" Signal Bars
| Context | Validity |
|---------|----------|
| **In strong trend** | **VALID — THIS IS A FEATURE.** Weak signals create constant tension, force traders to chase. If setup looks perfect, trend is not strong. |
| **In weak trend** | Less reliable. Need stronger confirmation (trend bar as signal bar) |
| **In trading range** | Valid only at extremes (fade setup). Avoid middle-of-range signals. |

### Non-Signal Bars (Ignore)
- Bars in tight TR / barbwire (3+ overlapping doji)
- Reversal bars in strong trend without opposite breakout confirmation
- Inside bars as standalone (need breakout confirmation)

### Key Rules
- **Signal bar** = bar terakhir setup, hanya teridentifikasi setelah close
- **Entry bar** = bar saat order terisi (1 tick beyond signal bar)
- **Follow-through bar** = bar setelah entry — makin kuat makin baik
- **The CLOSE matters most** (Ch 8) — lebih penting dari open/HL
- **All bars in a channel** = potential with-trend entry setups (Ch 6)

---

## 4. Entry Rules

### Trend Entries

| Type | Entry | Stop | Target | When to skip |
|------|-------|------|--------|-------------|
| 1st pullback (H1/L1) | 1 tick beyond signal bar | 1 tick beyond signal bar extreme | Measured move prior leg | Early, less reliable — skip if trend uncertain |
| 2nd pullback (H2/L2) | 1 tick beyond signal bar at/near 20-EMA | 1 tick beyond signal bar extreme | Measured move prior leg | Only if H2 failed → look for H3 wedge |
| Late entry (Ch 11) | AT MARKET (swing portion only) | Same stop as original entry | Same target as original | Not for full position; swing only |
| Second entry (Ch 10) | Same as first entry | Same stop | Same target | **MORE RELIABLE** than first — prefer over first |
| Spike & channel | 1 tick beyond channel line break | Opposite side of channel | Scalp + trail | — |
| 1st breakout pullback | 1 tick beyond signal bar | 1 tick beyond signal bar extreme | Measured move breakout | — |

### Countertrend Entries (Lower Probability)

| Setup | Entry | Stop | Target | Probability |
|-------|-------|------|--------|------------|
| Climactic reversal | 1 tick beyond reversal bar after climax | Beyond climax extreme | Measured move | Moderate — needs 2-stage (climax + opposite breakout) |
| Double top/bottom | 1 tick beyond reversal bar at 2nd test | Beyond test extreme | Prior swing break | Moderate (second signal) |
| Failed breakout | 1 tick beyond reversal bar after failed breakout | Opposite side of breakout | Back into range | Moderate (second attempt) |
| Wedge fade (3rd push) | 1 tick beyond signal bar at push 3 | Beyond push 3 extreme | Measured move | Low-moderate — only if prior pushes losing momentum |

**⚠️ Countertrend default = lower probability.** "Most successful countertrend trades fail" (Ch 4). Beginners should avoid all but strongest countertrend signals.

---

## 5. Stop Placement Rules

- **In trend:** 1 tick beyond the signal bar extreme. 1 tick beyond the entry bar extreme (for tight stops).
- **In trading range:** 1 tick beyond the extreme of the reversal bar (fade setup). Or beyond the swing high/low.
- **After strong breakout:** Below breakout point (bull) / above breakout point (bear). Breakout test = possible re-entry area.
- **Trailing:** Below prior swing low (bull) / above prior swing high (bear). Or below/above 20-EMA in strong trend.
- **Late entry (Ch 11):** Use same stop as original entry, not current bar.
- **Max loss per trade:** Defined by Trader's Equation — not a fixed number. Each trade must pass prob × reward > (1 − prob) × risk.

---

## 6. Target Rules

- **Scalp target:** At breakeven or 1× risk. Quick profit before next pullback.
- **Swing target:** Measured move of prior leg (Leg 1 = Leg 2 projection). Height of spike projected from breakout point.
- **Measured move projection:** Leg 1 = Leg 2. Height of TR/channel projected from breakout. Micro measuring gap midpoint.
- **Trailing stop rules:** Move to breakeven after 1× risk secured. Trail below/above swing points. In strong trend, hold through pullbacks with trailing below EMA.

---

## 7. Trading Range Playbook

- **Buying at support:** Wait for bull reversal bar at or near prior swing low. Second touch is more reliable. Entry 1 tick above signal bar.
- **Selling at resistance:** Wait for bear reversal bar at or near prior swing high. Second touch is more reliable. Entry 1 tick below signal bar.
- **False breakout:** Kalo breakout candle closes back inside range = fade setup. Entry 1 tick beyond reversal bar.
- **Breakout with successful retest:** Breakout → pullback to breakout point → reversal bar = high probability with-trend entry.
- **Barbwire** (3+ overlapping doji): AVOID trading. Wait for breakout with follow-through.
- **Breakout mode**: Expected breakout either direction — tunggu sebelum fade.
- **"Middle of day acts like magnet"** — extreme breakouts likely to fade (Ch 17).

---

## 8. Decision Call Definitions

| Call | Meaning | When to use |
|------|---------|-------------|
| **LONG (↑)** | Enter long position | With-trend setup, signal bar present, trend aligned, Trader's Equation positive |
| **SHORT (↓)** | Enter short position | With-trend setup, signal bar present, trend aligned, Trader's Equation positive |
| **WAIT** | No entry yet, but watching specific level | Price not at entry zone yet. Specify exact level and trigger to watch. |
| **FORGET** | Not worth trading. Move on. | Low probability, unclear structure, bad risk-reward. |
| **WATCH** | Sideways, but interesting catalysts | Monitor periodically for breakout or trend shift. |

**⚠️ TERMINOLOGY RULES:**
- **LONG = bullish bet** (expect price to go UP) — jangan pakai "BUY"
- **SHORT = bearish bet** (expect price to go DOWN) — jangan pakai "SELL"
- **WAIT / FORGET / WATCH** tetap sama

---

## 9. Conviction Rating System

| Score | Meaning | Conditions |
|-------|---------|------------|
| 9-10 | Very high probability | Strong trend (≥12 signs) + clear H2/L2 signal at 20-EMA + second entry + 1:3+ R:R |
| 7-8 | High probability | Trend aligned + signal bar valid + 1:2+ R:R |
| 5-6 | Medium — standard setup | Pullback in trend with signal bar. Trend may be moderate. |
| 3-4 | Low — only for advanced | Countertrend setup (climax reversal, wedge fade). Needs strong context. |
| 1-2 | Very low — avoid unless... | Against clear always-in, no signal bar, TR middle. Avoid. |

**Conviction modifiers:**
| Factor | Modifier |
|--------|----------|
| Trend alignment (with-trend) | +1 |
| Against trend (countertrend) | -2 |
| Strong signal bar | +1 |
| Weak signal bar (but in strong trend) | 0 (this is normal for strong trends) |
| Signs of Strength ≥ 12 | +1 |
| Signs of Strength ≤ 5 | -1 |
| Second entry | +1 |
| R:R ≥ 1:3 | +1 |
| R:R < 1:2 | -1 |

---

## 10. Pattern Reference — Quick Lookup

| Pattern | Trend Bias | Entry Signal | Notes |
|---------|-----------|-------------|-------|
| H2/L2 pullback at 20-EMA | Same as trend | Bull/bear reversal bar at 20-EMA | Standard with-trend. Most reliable day-in, day-out setup. |
| Spike & channel | Same as spike direction | 1 tick beyond channel line break, or any bar in channel | Spike = agresif. Channel = all bars are potential setups. |
| Wedge (3 pushes) | Fade (countertrend) | 1 tick beyond reversal bar at push 3 | Only if each push losing momentum. Failed wedge = failed failure → continuation. |
| Double top/bottom pullback | Countertrend initially | Reversal bar at 2nd test | Second signal. Moderate probability. Swing + scalp. |
| Breakout of tight TR | Direction of breakout | 1 tick beyond breakout bar | Expect follow-through. Pullback to breakout level = add. |
| Climactic reversal | Reversal | 1 tick beyond pause bar after climax | 2-stage: climax + opposite breakout. Most climaxes → TR, not reversal. |
| Final flag | Continuation (then reversal) | Breakout in trend direction | Last flag that fails to make new extreme = trend end. |
| Failed reversal attempt | Same as prior trend | Entry at stop where reversal traders cut loss | Reversal attempt that fails = strong continuation signal. |

---

## 11. Session Context & Timeframes

- **Primary chart (context):** Daily — trend classification, always-in, signs of strength
- **Entry chart:** H4 / 1H — pullback count (H1/H2/L1/L2), signal bar, entry precision
- **Weekly chart:** For HTF context (only if daily trend unclear)

### Intraday Timeframes (for day trading context)

- **5-minute:** Standard Brooks default for day trading (Ch 19: "best to trade only off the 5-minute chart in a runaway trend")
- **3-minute:** Only for additional with-trend setups in strong trends (can create confusion)
- **1-minute:** Avoid during runaway trends — countertrend setups create confusion

### Multi-timeframe alignment
- Weekly UP + Daily pullback to support = HIGH PROBABILITY LONG
- Weekly DOWN + Daily bounce to resistance = HIGH PROBABILITY SHORT
- All aligned = strong trend (beware of climax)
- Conflicting = ranging / uncertain — skip

---

## 12. Output Format — Deep Dive Template

Setiap ticker analysis HARUS menggunakan format ini:

```
## [TICKER]: $PRICE (+/-%)

### Trend Structure
**HTF:** [Bull/Bear/Trading Range]
**LTF:** [Bull/Bear/Trading Range]
**Spectrum position:** [extreme trend ↔ extreme TR]
**Always-In:** [Long/Short]
**Day type:** [Trend from Open / Trending TR / Reversal / Resumption / Stairs / Strong Trend]
**Verdict:** [Overall assessment]

### Signal Bars & Market State
[Describe current bars. Signal bar? Type? Context > shape.]
[Weak signal bars are FEATURE of strong trends — note if this applies.]
[Bar counting: H1/H2/L1/L2 in current leg.]

### Signs of Strength Count: [X/22]
[List which signs present. If ≥ 12 → strong trend, with-trend only.]

### Key Levels
- **Support:** [levels — swing lows, 20-EMA, TL support]
- **Resistance:** [levels — swing highs, 20-EMA, TL resistance]
- **Measured move target:** [projection]

### Decision Call: [LONG / SHORT / WAIT / FORGET]
**Entry zone:** [price range or specific level]
**Stop:** [price]
**Target 1 (scalp):** [price]
**Target 2 (swing):** [price]
**R:R:** [ratio]
**Conviction:** [X/10]

### Justification
[2-3 sentences: why this call based on Brooks framework. Reference specific signs and patterns.]

### Scenario If Wrong (Invalidation)
[What breaks this thesis? Price level that invalidates. Where to exit if wrong.]
[Pattern evolution: if this setup fails, what might it evolve into?]

### Day Type Implication
[If Reversal Day → note multi-day follow-through potential.
 If Trend Resumption → second leg ≈ first leg measured move.
 If Stairs → expect next day continuation.]
```

---

## Related Documents

- **SKILL.md** → `price-action/SKILL.md` (this framework as agent skill)
- **Ingestion Notes** → `Ingestion Notes - Trading Price Action Trends.md`
- **Full Chapter 4 notes** → `Al Brooks Ch.4 - Bar Basics Reversal Signals.md`
- **Prompt Generator** → `Prompt - Al Brooks Price Action Skill Generator.md`

---

*Framework version: v2 — 25 Mei 2026 — Integrated from full Al Brooks ingestion*
*Source: Trading Price Action Trends (2011, Wiley) — 26 chapters*
