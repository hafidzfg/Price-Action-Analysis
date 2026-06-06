# Global Exchange Registry

> **Source of truth:** `scripts/fetch_data.py` → `GLOBAL_EXCHANGES` dict.
> This file is a human reference only. For the authoritative list, read the code.

## Exchange Codes

| Code | Exchange Name | Region (API) | tvkit Prefix | Example Ticker |
|------|--------------|-------------|-------------|----------------|
| `NASDAQ` | NASDAQ (US) | `america` | `NASDAQ:` | AAPL |
| `NYSE` | New York Stock Exchange | `america` | `NYSE:` | BRK.B |
| `TSX` | Toronto Stock Exchange | `america` | `TSX:` | BB (BlackBerry) |
| `TSXV` | TSX Venture Exchange | `america` | `TSXV:` | ACB |
| `B3` | B3 (Brazil) | `america` | `B3:` | PETR4 |
| `LSE` | London Stock Exchange | `europe` | `LSE:` | BP |
| `EURONEXT` | Euronext | `europe` | `EURONEXT:` | AIR |
| `XETRA` | Xetra (Deutsche Börse) | `europe` | `XETRA:` | SAP |
| `SIX` | SIX Swiss Exchange | `europe` | `SIX:` | NESN |
| `TSE` | Tokyo Stock Exchange | `asia` | `TSE:` | 7203 (Toyota) |
| `HKEX` | Hong Kong Exchange | `asia` | `HKEX:` | 0700 (Tencent) |
| `SGX` | Singapore Exchange | `asia` | `SGX:` | D05 (DBS) |
| `ASX` | Australian Securities Exchange | `australia` | `ASX:` | CBA |
| `KRX` | Korea Exchange | `asia` | `KRX:` | 005930 (Samsung) |
| `BSE` | Bombay Stock Exchange | `asia` | `BSE:` | RELIANCE |
| `NSE` | National Stock Exchange (India) | `asia` | `NSE:` | TCS |
| `IDX` | Indonesia Stock Exchange | `indonesia` | `IDX:` | BBRI (BBRI.JK) |
| `BINANCE` | Binance crypto | `crypto` | `BINANCE:` | BTCUSDT |
| `COINBASE` | Coinbase crypto | `crypto` | `COINBASE:` | BTC-USD |
| `TVC` | TradingView Community (commodities) | `commodity` | `TVC:` | GOLD, SILVER |

## CLI Usage Patterns

```bash
# Auto-resolve (defaults to NASDAQ):
python fetch_data.py AAPL

# Explicit exchange via --exchange flag:
python fetch_data.py --exchange TSX BB
python fetch_data.py --exchange LSE BP
python fetch_data.py --exchange TSE 7203

# Explicit prefix (equivalent):
python fetch_data.py TSX:BB
python fetch_data.py LSE:BP
python fetch_data.py TSE:7203

# Python API:
data = await analyze_ticker('BB', exchange='TSX')
```

## Resolution Order

`fetch_data.py` resolves tickers in this order:

1. **Explicit prefix** `EXCHANGE:TICKER` — parse the colon, use as-is
2. **`--exchange EXCHANGE` flag** — prefix the ticker with that exchange
3. **Auto-resolution** — bare tickers check for `.JK` → IDX, known IDX stocks, then NASDAQ
4. **Error** — if still unresolved, tvkit returns `series_error`

## Prevention: When a Ticker Fails

1. User says "try TSX" → `--exchange TSX TICKER`
2. User says "it's on London" → `--exchange LSE TICKER`
3. User gives explicit prefix → `EXCHANGE:TICKER` format
4. If unsure, check with user — do NOT guess and do NOT default to stale cache
