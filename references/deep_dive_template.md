# Deep Dive Template — Stage 1 Scan + Stage 2 Analysis

Use this template for full research-grade ticker analyses.

**CRITICAL:** This template balances ALL entry types. Read [references/entry_type_matrix.md](references/entry_type_matrix.md) before writing the "Entry Zone" section.

---

## Stage 1: Initial Scan

### Mandatory Output Format — add `Trend Phase` field

```
## TICKER — VERDICT
**Price:** xxx | **Trend:** xxx | **Day Type:** xxx
**Trend Phase:** early/mid/late/climax/TR
**Always-In:** long/short/neutral
**Entry Approach:** breakout / pullback / reversal / FBO / range_edge (from entry_type_matrix)
**Conviction:** HIGH/MEDIUM/WAIT/FORGET (score: +X)
**Entry zone:** xxx – xxx
**SL / Invalidation:** below/above xxx
**TP1:** xxx  (R:R ~x:x)
**TP2:** xxx  (R:R ~x:x)
**TP3:** xxx  (R:R ~x:x)
**Key context:** (1-2 sentences)
```

---

## Stage 2: Deep Dive

### Header — add `Trend Phase` + `Entry Approach`

```
## $TICKER — Deep Dive YYYY-MM-DD
**Price:** xxx | **Trend:** xxx | **Day Type:** xxx
**Trend Phase:** early/mid/late/climax/TR
**Always-In:** weekly: ... | daily: ... | H4: ...
**Entry Approach:** {breakout/pullback/reversal/FBO/range_edge}
**Conviction:** HIGH/MEDIUM/WAIT/FORGET (score: +X)
**Entry zone:** xxx – xxx
**SL / Invalidation:** below/above xxx
**TP1:** xxx  (R:R ~x:x)
**TP2:** xxx  (R:R ~x:x)
**TP3:** xxx  (R:R ~x:x)
**Trader's Equation:** ... → edge yes/no
```

### Section 1: Trend Phase + Entry Type Mapping (MANDATORY)

```
**Trend Phase:** {early/mid/late/climax/TR}
**Primary Entry Type:** {from entry_type_matrix}
**Rationale:** {why THIS entry, not pullback}
**Alternatives Considered:**
- {entry A}: {rejected because}
- {entry B}: {chosen as alt}
```

### Section 2-7: Standard Analysis

Where on spectrum → Signs of Strength → Bar counting → Signal bar → Entries → Trader's Equation

### Multi-Scenario Entry (Section 6)

Present AT LEAST 2 trade scenarios with different entry types.