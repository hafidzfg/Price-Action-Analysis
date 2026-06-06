# Price Action Analysis — Al Brooks Framework

A two-tier price action analysis framework based on Al Brooks' *Trading Price Action* series. Brooks terminology only — no Elliott Wave, Wyckoff, or SMC.

## Structure

```
├── SKILL.md               ← Workflow router & two-tier orchestration
├── book1-trends.md        ← Trend trading rules
├── ranges.md              ← Trading range rules
├── tier2-routing.md       ← Tier-2 agent decision guide
├── references/
│   ├── entry_type_matrix.md   ← Trend phase → entry type mapping
│   └── global_exchanges.md    ← Exchange code registry
└── scripts/
    ├── fetch_data.py          ← Multi-timeframe OHLCV + indicators (tvkit/TradingView)
    └── brooks_analysis.py     ← Tier-1 deterministic analysis engine
```

## Two-Tier Architecture

| Tier | What | Output |
|------|------|--------|
| **Tier 1** | Deterministic engine (from OHLCV data) | SoS count, day type, pullback count, measured move targets, conviction objective subtotal |
| **Tier 2** | Human/agent judgment | Always-In direction, signal bar quality, Trader's Equation, final conviction score |

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
