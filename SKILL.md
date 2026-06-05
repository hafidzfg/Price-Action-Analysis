---
name: price-action-al-brooks
description: "Two-stage price action analysis per Al Brooks' Trading Price Action series. Stage 1 scan to Stage 2 deep dive. Brooks terminology only — no Elliott Wave / Wyckoff / SMC. Modular design: Book 1 (Trends) always loaded, Book 2 (Ranges) loaded on-demand."
---

# Price Action — Al Brooks Framework

## Modular File Structure

```
skills/price-action/
├── SKILL.md              ← This file (router + workflow)
├── book1-trends.md       ← Trend trading rules (Book 1 — always loaded)
├── book2-ranges.md       ← Trading range rules (Book 2 — load on-demand)
├── tier2-routing.md      ← Tier-2 agent decision guide (~50 lines, replaces full book reading)
└── scripts/
    ├── fetch_data.py     ← Multi-timeframe OHLCV + indicators + pattern detection
    └── brooks_analysis.py ← Tier-1 deterministic engine (SoS, day type, pullbacks, etc.)
```

### Loading Rules
- **Always loaded:** `book1-trends.md` — trend trading is the default framework
- **On-demand:** `book2-ranges.md` — load ONLY when market is in or near a trading range
- **Never load both** unless context explicitly requires it (e.g., trend to TR transition)

### When to Load Book 2
Load `book2-ranges.md` when ANY of these are true:
- Day type classified as Trading Range or Barbwire
- Always-in direction is unclear/neutral
- Price is between 20-EMA and 50-SMA with no clear trend
- Multiple failed breakouts in recent bars
- User asks about range-bound ticker

---

| Core Tenets

1. **Market is always on a spectrum**: extreme trend vs extreme trading range
2. **Always-In direction**: at any moment, if forced to pick long or short, that is the always-in
3. **Trader's Equation**: prob x reward exceeds (1 minus prob) x risk — not rigid R:R
4. **Two-legged principle**: market regularly tries to do something twice
5. **Trend first**: always classify trend or trading range before analyzing any bar
6. **Weak signals do not mean weak trend**: weak signal bars are often a FEATURE of strong trends
7. **Trend phase determines entry type**: read `references/entry_type_matrix.md` before recommending any entry. Early trend → breakout. Mid → pullback. Late/climax → reversal/FBO. TR → range edge. Do NOT default to pullback.

---

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
| R:R ratio | At least 1:3 | +1 |
| R:R ratio | Under 1:1 | -1 |
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

---

## Execution Mode — Choose ONE

The skill supports two execution modes. **Use the inline pipeline for frictionless single-ticker analysis. Use sub-agents for batch scans.**

### MODE 1: Inline Pipeline (Primary — 0 approval prompts)

For single-ticker analysis. Run the ENTIRE pipeline in ONE `terminal()` call. No sub-agents, no `execute_code`, no intermediate files:

```bash
python3 -c "
import sys, asyncio, json
sys.path.insert(0, '/home/hermes/.hermes/profiles/analyst/skills/trading/price-action-al-brooks/scripts')
from fetch_data import analyze_ticker
from brooks_analysis import analyze as brooks_analyze

data = asyncio.run(asyncio.wait_for(analyze_ticker('TICKER'), timeout=45))

# For tickers not on NASDAQ, pass exchange= hint:
#   data = asyncio.run(asyncio.wait_for(analyze_ticker('BB', exchange='TSX'), timeout=45))
#   data = asyncio.run(asyncio.wait_for(analyze_ticker('BP', exchange='LSE'), timeout=45))

# Save indicators before stripping
price = data['indicators']['close']
ema20 = data['indicators'].get('ema20', None)
atr = data['indicators'].get('atr', None)
perf = data.get('performance', {})

# Strip non-Brooks fields
del data['indicators']
del data['performance']

# Run brooks analysis
analysis = brooks_analyze(data)

# Build compact output
bars = {}
cls = {}
for tf in ['daily', 'weekly', 'h4']:
    if tf in data['timeframes']:
        bars[tf] = data['timeframes'][tf][-20:]
    if tf in data.get('analysis', {}):
        cls[tf] = data['analysis'][tf].get('last_10_bars_classified', [])
        if 'patterns' in data['analysis'][tf]:
            cls[tf + '_patterns'] = data['analysis'][tf]['patterns']
        if 'bar_analysis' in data['analysis'][tf]:
            cls[tf + '_bar_analysis'] = data['analysis'][tf]['bar_analysis']
        if 'trend_context' in data['analysis'][tf]:
            cls[tf + '_trend_context'] = data['analysis'][tf]['trend_context']

print(json.dumps({
    'price': price, 'ema20': ema20, 'atr': atr,
    'performance': perf, 'analysis': analysis,
    'bars': bars, 'classifications': cls
}, default=str))
"
```

> **⚠️ Path note:** The inline pipeline path above is correct for the **analyst** profile on this system. On other profiles, resolve dynamically with `skill_view('price-action-al-brooks')` or `dirname $(find ~/.hermes -path '*/price-action-al-brooks/scripts/fetch_data.py' -print -quit)`.

**⚠️ Timeout handling:** `fetch_data.py` can hang when tvkit/TradingView WebSocket is slow (common on IDX tickers). The one-shot pipeline above uses `asyncio.wait_for` with a 45s timeout.

**⚠️ If the pipeline fails: DO NOT fall back to cached data without asking the user.** Stale cache produces analyses that waste time and erode trust. Instead:
1. Check the error — if it's a `resolve error`, the exchange prefix is likely wrong (see Exchange Prefix Resolution below)
2. Try `--exchange EXCHANGE` on the CLI or `exchange=` in the Python API
3. If all data sources fail, tell the user exactly which ticker + exchange failed and why. Let them decide next steps.

**CRITICAL:** Do NOT use `execute_code` or pipe `curl | python3` — both trigger approval prompts. Use the one-shot `terminal()` call above. Zero prompts.

### MODE 2: Sub-agent Workflow (for batch scanning)

For scanning multiple tickers in parallel, use sub-agents as Stage 1 and Stage 2 runners:

**Stage 1 (sub-agent):** Run `python ~/.hermes/profiles/analyst/skills/trading/price-action-al-brooks/scripts/fetch_data.py --brooks TICKER1 TICKER2 ...`

**Stage 2 (sub-agent):** For each actionable ticker, spawn a sub-agent that reads book references + entry_type_matrix + tier2-routing, then writes the analysis.

## Workflow

### Stage 1: Multi-Timeframe Scan

Pull data (via Mode 1 or Mode 2). For each TF determine:

| TF | Purpose | Look for |
|----|---------|----------|
| **Weekly** | Dominant TF — is there a macro trend? | Alternating bull/bear bars? TR? |
| **Daily** | Intermediate structure | Swing highs/lows, higher lows, lower highs |
| **H4** | Entry TF | Range extremes, tightness, signal bars, wedge top/bottom |

Classify Trend Phase: early/mid/late/climax/TR (read `references/entry_type_matrix.md`). Entry recommendation MUST match the trend phase — do NOT default to pullback.

### Stage 2: Deep Dive

Analyze entry timeframe. Read:
- Always: `book1-trends.md` via `skill_view('price-action-al-brooks', 'book1-trends.md')`
- If Trading Range or Barbwire: also `book2-ranges.md`
- `tier2-routing.md` for agent decision rules
- `references/entry_type_matrix.md` for trend phase → entry type mapping

Write analysis to: `OBSIDIAN_VAULT_PATH/2 - Areas/Trading/Deep Dives/{WEEK_FOLDER}/{TICKER} - Deep Dive {YYYY-MM-DD}.md`

### Vault File — Folder Naming (CRITICAL)

- Weekly folder format: `{ISO-WEEK}-{MonShort-DD}-{SunShort-DD}` (e.g., `2026-W22-May-25-31`)
- **BEFORE creating a folder, check if the correct week folder already exists.** If it does, USE IT. Do NOT create new folders per day or with different naming.
- Example: W23 week (June 1-7, 2026) = `2026-W23-Jun-01-07`. If that folder exists from a prior session, put new deep dives IN IT. Do NOT create `2026-W23-Jun-02` or `2026-W23-Jun-01-Jun-07`.

### Git — Commit & Push Automatically

Every deep dive session MUST end with a push:

```bash
cd $OBSIDIAN_VAULT_PATH
git add -A
git commit -m "Deep dive: TICKER YYYY-MM-DD"
git push
```

For batch commits:
```bash
cd $OBSIDIAN_VAULT_PATH
git add -A
git commit -m "vault: deep dives & updates YYYY-MM-DD"
git push
```

This is not optional. The remote is the single source of truth.

---

## Scripts

### fetch_data.py v2
Fetches multi-timeframe OHLCV candle data + indicator snapshots via tvkit (TradingView WebSocket) + Scanner API.

**Markets supported:**
- IDX — IDX:{ticker} (e.g., BBRI.JK → IDX:BBRI)
- US — NASDAQ:{ticker} or NYSE:{ticker}
- Canada — TSX:{ticker} or TSXV:{ticker}
- Europe — LSE:{ticker}, EURONEXT:{ticker}, XETRA:{ticker}, SIX:{ticker}
- Asia-Pacific — TSE:{ticker}, HKEX:{ticker}, SGX:{ticker}, ASX:{ticker}, KRX:{ticker}, BSE:{ticker}, NSE:{ticker}
- Crypto — BINANCE:{ticker}USDT
- Commodities — TVC:GOLD, TVC:SILVER

**Exchange resolution:**
- Bare tickers (e.g., `AAPL`, `BB`, `7203`) auto-resolve to `NASDAQ:` by default
- Use `--exchange EXCHANGE` to force a specific exchange:  
  `python fetch_data.py --exchange TSX BB` → resolves to `TSX:BB`
- Use `EXCHANGE:TICKER` prefix for explicit resolution:  
  `python fetch_data.py TSX:BB` → resolves to `TSX:BB`

Usage:
```bash
# Default auto-resolution (NASDAQ)
python ~/.hermes/profiles/analyst/skills/trading/price-action-al-brooks/scripts/fetch_data.py AAPL BBRI.JK BTCUSD XAUUSD

# With exchange hint
python ~/.hermes/profiles/analyst/skills/trading/price-action-al-brooks/scripts/fetch_data.py --exchange TSX BB
python ~/.hermes/profiles/analyst/skills/trading/price-action-al-brooks/scripts/fetch_data.py --exchange LSE BP

# With explicit prefix
python ~/.hermes/profiles/analyst/skills/trading/price-action-al-brooks/scripts/fetch_data.py TSX:BB LSE:BP TSE:7203

# Combined with brooks mode
python ~/.hermes/profiles/analyst/skills/trading/price-action-al-brooks/scripts/fetch_data.py --brooks --exchange TSX BB
```

### brooks_analysis.py (Tier-1 Engine)
```bash
python ~/.hermes/profiles/analyst/skills/trading/price-action-al-brooks/scripts/brooks_analysis.py AAPL_brooks.json
cat AAPL_brooks.json | python ~/.hermes/profiles/analyst/skills/trading/price-action-al-brooks/scripts/brooks_analysis.py
```

---

## Obsidian Output

Deep dives to `OBSIDIAN_VAULT_PATH/2 - Areas/Trading/Deep Dives/{WEEK_FOLDER}/{TICKER} - Deep Dive {YYYY-MM-DD}.md`
Week folder format: `{ISO-WEEK}-{MonShort-DD}-{SunShort-DD}` (e.g., `2026-W22-May-25-31`)

---

## Data Sourcing — Hard Rules

### Rule 1: fetch_data.py (tvkit/TradingView) is the ONLY primary data source.
Use the inline pipeline or `--brooks` CLI flag. Wrap with `asyncio.wait_for(..., timeout=45)` for IDX tickers that may hang.

### Rule 2: If the primary source fails — STOP. Tell the user.
Do NOT silently fall back to yfinance, cached JSON, or browser TradingView. Present the error to the user:
- *"Ticker X on exchange Y failed because: [reason]. Suggested: --exchange Z or manual check on TradingView."*
- Let them decide what to do. They may know the exchange is wrong, the ticker changed, or they want you to use a different approach.

### Rule 3: Never use cached data without explicit user consent.
A `_raw.json` file in `scripts/` may be days or weeks old. Analyzing stale data produces misleading analysis and erodes trust. If the user explicitly says "use cached data", flag the date in the output.

### Rule 4: When the user confirms an exchange or ticker, try again.
If the user says "try TSX:BB", re-run fetch_data.py with that exact exchange. Don't proceed with stale fallback.

### ⚠️ Exchange Prefix Resolution

When tvkit returns a `series_error` / `resolve error` for a ticker, the auto-resolved exchange prefix may be wrong. The script defaults to `NASDAQ:` for bare tickers, but the stock might trade on NYSE, TSX, LSE, etc.

**Do NOT fall back to stale cache. Try exchange resolution first:**

1. **Try `--exchange EXCHANGE`** on the CLI:
   ```bash
   python fetch_data.py --exchange TSX BB
   python fetch_data.py --exchange NYSE BB
   ```
   This is the fastest fix. It bypasses auto-resolution entirely and feeds the exact prefix to tvkit.

2. **Use explicit prefix** (equivalent):
   ```bash
   python fetch_data.py TSX:BB
   ```

3. **Check cached raw JSONs for prefix hints only** — search `scripts/*{TICKER}*raw.json` for files like `NYSE_{TICKER}_raw.json` or `TSX_{TICKER}_raw.json`. If one exists, it confirms the correct exchange prefix. Do NOT use the data inside for analysis without user consent.

4. **Or in Python API:** pass `exchange=` to `analyze_ticker`:
   ```python
   data = await analyze_ticker('BB', exchange='TSX')
   ```

**Known exchange codes:** See `references/global_exchanges.md` for the full registry (17 exchanges + crypto + commodities). Quick ref: `NASDAQ`, `NYSE`, `TSX`, `TSXV`, `LSE`, `TSE`, `HKEX`, `IDX`, `BINANCE`, `COINBASE`, `TVC`.

## Brooks Language Only
Acceptable: wedge top/bottom, micro channel, trend bar, doji, inside bar, outside bar, barbwire, measured move, pullback, trading range, HH/HL/LH/LL, signal bar, breakout, failed breakout, reversal bar, trend resumption.
Forbidden: parabolic, blow-off top, capitulation, FOMO, overbought, oversold, Elliott Wave, Wyckoff, SMC, RSI, MACD, Fibonacci.

## Guardrail: The Skill IS the Procedure
This skill is not a suggestion pile. Every step — execution mode, analysis format, folder naming, git push — is mandatory. Deviating from it (inventing new folder names, skipping git, bypassing fetch_data.py, **using stale cached data without user consent**, using non-Brooks indicators) is a procedural error that wastes tokens and erodes trust.

## Knowledge Base
**Source:** Al Brooks, Trading Price Action series
- Book 1: Trends (26 chapters) — `book1-trends.md`
- Book 2: Trading Ranges (32 chapters) — `book2-ranges.md`

**Known Watchlists:**
- 8898 - 19 APR (10 emiten): TTWO, HIVE, YOII.JK, PTMP.JK, WOLF, NOW, ALII.JK, ENPH, VAL, MX
