# Price Action Analysis — Al Brooks Framework

A two-tier price action analysis framework based on Al Brooks' *Trading Price Action* series. Brooks terminology only — no Elliott Wave, Wyckoff, or SMC.

## Structure
```
├── SKILL.md               ← Workflow router & two-tier orchestration
├── core.md                ← Universal price action (~22KB — ALWAYS loaded)
├── trends.md              ← Trend-specific rules (~14KB — load when trending)
├── ranges.md              ← Trading range rules (~20KB — load when ranging)
├── reversals.md           ← Reversal patterns (~24KB — load when reversal signals detected)
├── tier2-routing.md       ← Tier-2 agent decision guide
├── references/
│   ├── entry_type_matrix.md   ← Trend phase → entry type mapping
│   └── global_exchanges.md    ← Exchange code registry
└── scripts/
    ├── fetch_data.py          ← Multi-timeframe OHLCV + indicators (tvkit/TradingView)
    └── brooks_analysis.py     ← Tier-1 deterministic analysis engine
```

## Four-Tier Architecture

| Tier | What | Output |
|------|------|--------|
| **Tier 1** | Deterministic engine (from OHLCV data) | SoS count, day type, pullback count, measured move targets, conviction objective subtotal |
| **Tier 2** | Human/agent judgment | Always-In direction, signal bar quality, Trader's Equation, final conviction score |

### Knowledge Loading

| Module | Size | When to Load |
|--------|------|-------------|
| **core.md** | ~22KB | ALWAYS — bar anatomy, counting, breakouts, EMA, risk, time frames |
| **trends.md** | ~14KB | When trending (strong_bull/bear, tfo_bull/bear) |
| **ranges.md** | ~20KB | When ranging (trading_range, barbwire) |
| **reversals.md** | ~24KB | When reversal signals detected — **overlay** (loads alongside state module) |

## Requirements

- Python 3.10+
- `tvkit` — TradingView WebSocket API

```
pip install tvkit
```

## Usage

```bash
# Full pipeline: fetch + analyze
python scripts/fetch_data.py --analyze NASDAQ:AAPL

# Fetch only
python scripts/fetch_data.py NASDAQ:AAPL

# Fetch with Brooks analysis output
python scripts/fetch_data.py --brooks NASDAQ:AAPL
```

Supports US stocks (`NASDAQ:`, `NYSE:`), Indonesian stocks (`.JK`), crypto (`BINANCE:`, `COINBASE:`), and commodities (`XAUUSD`).

## License

MIT
