# Screener Setup — Al Brooks PA Ticker Discovery

To prevent analyzing only spiking/climax tickers, screen for ALL trend phases daily.

## TradingView Screener Presets

### Scan 1 — Early Trend / Breakout
**Purpose:** Tickers that JUST broke out of a range — NOT yet spiking.

| Filter | Setting |
|--------|---------|
| Change % (1M) | > 5% and < 30% |
| Volume | > Volume MA(50) |
| Price | > SMA(20) and > SMA(50) |
| RSI (14) | 50 – 70 |
| ATR % | > 2% |

→ **Entry approach: breakout entry** (not pullback)

### Scan 2 — Mid Trend / Pullback  
**Purpose:** Trending tickers pulling back to EMA — M2B/M2S ready.

| Filter | Setting |
|--------|---------|
| Price > SMA(50) and SMA(20) > SMA(50) | Trend confirmed |
| Change % (1M) | > 10% |
| RSI (14) | 40 – 55 |
| Price / SMA(20) | < 1.05 |
| ADX (14) | > 25 |

→ **Entry approach: pullback to EMA** (correct for mid-trend)

### Scan 3 — Late Trend / Wedge
**Purpose:** Overextended tickers — look for FBO/reversal.

| Filter | Setting |
|--------|---------|
| Price > SMA(20) and > SMA(50) | Still bull |
| RSI (14) | > 75 |
| Price / SMA(20) | > 1.15 |
| Change % (1M) | > 25% |

→ **Entry approach: wedge FBO / reversal** (NOT continuation)

### Scan 4 — Squeeze / Breakout Mode
**Purpose:** Tickers compressing — about to move.

| Filter | Setting |
|--------|---------|
| ATR % (14) | < 2% |
| BB Width (20,2) | Near 3-month low |
| RSI (14) | 40 – 60 |
| Change % (1M) | < 10% |

→ **Entry approach: range edge or breakout**

## Automated Cron Option (Future)

yfinance tersedia di VPS. Bisa build Python cron yang:
- Fetch OHLCV per watchlist
- Compute trend phase
- Screen every market open
- Post results ke Discord

Butuh dari kamu: watchlist, confirm cron budget.