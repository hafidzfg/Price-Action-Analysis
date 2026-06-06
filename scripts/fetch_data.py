#!/usr/bin/env python3
"""
fetch_data.py v2 — Multi-timeframe OHLCV + indicators for Al Brooks analysis.

Uses:
- tvkit (TradingView WebSocket) for actual candle data across timeframes
- TradingView Scanner API for indicator snapshots (RSI, MACD, etc.)

Supports: IDX (.JK), US (NASDAQ/NYSE), Crypto, XAUUSD/Commodities

Output: JSON to stdout + saved raw file.
"""
import sys, json, os, asyncio
from datetime import datetime, timezone
from typing import Optional

# ---------------------------------------------------------------------------
# Symbol Resolution
# ---------------------------------------------------------------------------

# Known crypto symbols → BINANCE exchange
CRYPTO_MAP = {
    'BTCUSD': 'BINANCE:BTCUSDT',
    'BTCUSDT': 'BINANCE:BTCUSDT',
    'ETHUSD': 'BINANCE:ETHUSDT',
    'ETHUSDT': 'BINANCE:ETHUSDT',
    'SOLUSD': 'BINANCE:SOLUSDT',
    'SOLUSDT': 'BINANCE:SOLUSDT',
    'BNBUSD': 'BINANCE:BNBUSDT',
    'XRPUSD': 'BINANCE:XRPUSDT',
    'DOGEUSD': 'BINANCE:DOGEUSDT',
    'ADAUSD': 'BINANCE:ADAUSDT',
}

# Coinbase-only tokens (not on Binance)
COINBASE_MAP = {
    'AEROUSD': 'COINBASE:AEROUSD',
    'AEROUSDT': 'COINBASE:AEROUSD',
}

# Known commodities/forex → TVC exchange
COMMODITY_MAP = {
    'XAUUSD': 'TVC:GOLD',
    'GOLD': 'TVC:GOLD',
    'XAGUSD': 'TVC:SILVER',
    'SILVER': 'TVC:SILVER',
    'USOIL': 'TVC:USOIL',
    'CRUDE': 'TVC:USOIL',
    'DXY': 'TVC:DXY',
}

# Global exchange registry — source of truth for exchange resolution.
# The references/global_exchanges.md doc is generated from this dict.
# Exchange code → (region for TradingView Scanner API)
# Used when ticker has no prefix and --exchange is not specified.
# tvkit resolves any EXCHANGE:SYMBOL via TradingView WebSocket regardless of region;
# the 'region' field only affects which TradingView Scanner endpoint to hit.
# To add a new exchange: add it here. That's the only change needed.
GLOBAL_EXCHANGES: dict[str, str] = {
    # Americas
    'NASDAQ': 'america',
    'NYSE':   'america',
    'TSX':    'america',   # Toronto Stock Exchange
    'TSXV':   'america',   # TSX Venture Exchange
    'B3':     'america',   # Brazil
    # Europe
    'LSE':    'europe',    # London Stock Exchange
    'EURONEXT': 'europe',
    'XETRA':  'europe',    # Deutsche Börse
    'SIX':    'europe',    # Swiss Exchange
    # Asia-Pacific
    'TSE':    'asia',      # Tokyo Stock Exchange
    'HKEX':   'asia',      # Hong Kong Exchange
    'SGX':    'asia',      # Singapore Exchange
    'ASX':    'australia', # Australian Securities Exchange
    'KRX':    'asia',      # Korea Exchange
    'BSE':    'asia',      # Bombay Stock Exchange
    'NSE':    'asia',      # National Stock Exchange of India
    'IDX':    'indonesia', # Indonesia Stock Exchange
}

# Priority order for auto-resolution when no exchange hint given
# Starts with most common US exchanges, then major global exchanges
EXCHANGE_PRIORITY = ['NASDAQ', 'NYSE', 'TSX', 'LSE', 'TSE', 'HKEX', 'ASX', 'SGX', 'EURONEXT', 'XETRA']


def resolve_symbol(ticker: str, exchange: str | None = None) -> tuple[str, str, str]:
    """
    Resolve ticker to (exchange_symbol, fetch_ticker, market_type).

    Parameters:
        ticker: Raw ticker input (e.g., 'BB', 'TSX:BB', 'AAPL', 'BBRI.JK')
        exchange: Optional exchange hint ('NASDAQ', 'TSX', 'LSE', etc.).
                  When None, auto-resolves using priority list.

    Returns:
        (exchange_symbol: for tvkit, fetch_ticker: for scanner API, market_type)
    """
    t = ticker.strip().upper()

    # --- Explicit exchange prefix (highest priority) ---
    if ':' in t:
        ex, sym = t.split(':', 1)
        if ex in GLOBAL_EXCHANGES or ex in ('BINANCE', 'OKX', 'BYBIT', 'COINBASE'):
            market = 'crypto' if ex in ('BINANCE', 'OKX', 'BYBIT', 'COINBASE') else 'us'
            return t, t, market
        # Unknown exchange prefix — pass through, tvkit will either resolve or error
        return t, t, 'us'

    # --- IDX stocks (.JK suffix) ---
    if t.endswith('.JK'):
        base = t.replace('.JK', '')
        return f'IDX:{base}', f'IDX:{base}', 'idx'

    # --- Commodities (check BEFORE crypto — symbols like XAUUSD end with USD) ---
    if t in COMMODITY_MAP:
        return COMMODITY_MAP[t], t, 'commodity'

    # --- Crypto ---
    if t in CRYPTO_MAP:
        return CRYPTO_MAP[t], t, 'crypto'
    if t in COINBASE_MAP:
        return COINBASE_MAP[t], t, 'crypto'
    if t.endswith('USD') or t.endswith('USDT'):
        return f'BINANCE:{t.replace("USD","USDT") if not t.endswith("USDT") else t}', t, 'crypto'

    # --- Exchange hint provided (CLI --exchange flag) ---
    if exchange:
        ex = exchange.strip().upper()
        if ex in GLOBAL_EXCHANGES:
            return f'{ex}:{t}', t, 'us'
        # Unknown exchange code — warn via stderr but try anyway
        print(f"[warning: unknown exchange '{ex}', trying {ex}:{t} raw]", file=sys.stderr)
        return f'{ex}:{t}', t, 'us'

    # --- Auto-resolution: try the priority list ---
    # For each exchange in priority order, return the first match.
    # Since we don't have a way to pre-check existence, try in order and
    # let tvkit fail if wrong. The caller can retry with a different exchange.
    # Uses NASDAQ as default (most common US tech stocks).
    return f'NASDAQ:{t}', t, 'us'


# ---------------------------------------------------------------------------
# OHLCV Fetching via tvkit
# ---------------------------------------------------------------------------

TIMEFRAMES = {
    'daily':   ('1D',  120),   # ~6 months of daily bars
    'weekly':  ('1W',  52),    # ~1 year of weekly bars
    'h4':      ('240', 120),   # ~20 days of 4H bars (for intraday context)
}


def _exchange_suggestion(exchange_symbol: str) -> str:
    """Return a helpful suggestion string based on the exchange symbol."""
    if ':' not in exchange_symbol:
        return ""
    exchange = exchange_symbol.split(':')[0]
    symbol = exchange_symbol.split(':', 1)[1]

    suggestions = {
        'BINANCE': f"Symbol '{symbol}' doesn't exist on BINANCE. "
                   f"Try COINBASE:{symbol.replace('USDT','USD')} for tokens on Coinbase.",
        'NASDAQ': f"Symbol '{symbol}' doesn't exist on NASDAQ. "
                  f"Try NYSE:{symbol} — many stocks trade on NYSE instead of NASDAQ.",
        'NYSE': f"Symbol '{symbol}' doesn't exist on NYSE. "
                f"Try NASDAQ:{symbol} — this stock may trade on NASDAQ.",
        'TSX': f"Symbol '{symbol}' doesn't exist on TSX. "
               f"Try TSXV:{symbol} or NYSE:{symbol} or NASDAQ:{symbol}.",
        'IDX': f"Symbol '{symbol}' doesn't exist on IDX. "
               f"Check spelling — IDX tickers use the full company code (e.g., BBRI, ASII).",
    }
    base = suggestions.get(exchange, f"Symbol '{exchange_symbol}' not found. "
                           f"Available exchanges: {', '.join(sorted(GLOBAL_EXCHANGES.keys()))}.")
    return f"\n  💡 {base}"


async def fetch_ohlcv(exchange_symbol: str, interval: str, bars_count: int) -> list[dict]:
    """Fetch OHLCV bars via tvkit. Returns list of bar dicts."""
    from tvkit.api.chart.ohlcv import OHLCV

    try:
        async with OHLCV() as client:
            bars = await client.get_historical_ohlcv(
                exchange_symbol=exchange_symbol,
                interval=interval,
                bars_count=bars_count,
            )
            result = []
            for bar in bars:
                # Convert unix timestamp to ISO date
                dt = datetime.fromtimestamp(bar.timestamp, tz=timezone.utc)
                result.append({
                    'date': dt.strftime('%Y-%m-%d'),
                    'datetime': dt.isoformat(),
                    'timestamp': bar.timestamp,
                    'open': round(bar.open, 4),
                    'high': round(bar.high, 4),
                    'low': round(bar.low, 4),
                    'close': round(bar.close, 4),
                    'volume': int(bar.volume) if bar.volume else 0,
                })
            return result
    except Exception as e:
        err_msg = str(e)
        hint = _exchange_suggestion(exchange_symbol)
        return [{'error': err_msg + hint}]


async def fetch_all_timeframes(exchange_symbol: str) -> dict:
    """Fetch daily, weekly, and H4 bars concurrently."""
    tasks = {}
    for tf_name, (interval, count) in TIMEFRAMES.items():
        tasks[tf_name] = fetch_ohlcv(exchange_symbol, interval, count)

    results = {}
    for tf_name, coro in tasks.items():
        # Run sequentially to avoid WebSocket conflicts
        # (tvkit may not handle multiple concurrent sessions well)
        results[tf_name] = await coro

    return results


# ---------------------------------------------------------------------------
# Indicator Snapshot (from Scanner API — kept for RSI/MACD/BB/etc.)
# ---------------------------------------------------------------------------

import urllib.request, urllib.error

TV_URL_BASE = "https://scanner.tradingview.com"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

SCANNER_COLUMNS = [
    "name","close","change","high","low","open","volume",
    "Recommend.All",
    "RSI","RSI[1]",
    "MACD.macd","MACD.signal",
    "Stoch.K","Stoch.D",
    "BB.upper","BB.lower",
    "SMA20","SMA50","SMA200",
    "EMA5","EMA20","EMA50",
    "ATR",
    "High.All","High.1M","High.3M","High.6M",
    "Low.All","Low.1M","Low.3M","Low.6M",
    "market_cap_basic",
    "gap",
    "relative_volume_10d_calc",
]

def fetch_scanner(ticker: str, market_type: str) -> dict:
    """Fetch indicator snapshot from TradingView Scanner API."""
    exchange_symbol, fetch_ticker, mtype = resolve_symbol(ticker)

    # Scanner API uses exchange:symbol format for all markets
    tv_sym = exchange_symbol

    # Resolve scanner region from exchange prefix
    region = 'america'  # default
    if ':' in tv_sym:
        ex = tv_sym.split(':', 1)[0]
        region = GLOBAL_EXCHANGES.get(ex, 'america')

    url = f"{TV_URL_BASE}/{region}/scan"

    payload = {
        "symbols": {"tickers": [tv_sym], "query": {"types": []}},
        "columns": SCANNER_COLUMNS
    }

    try:
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode(),
            headers={"User-Agent": UA, "Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=15) as r:
            data = json.loads(r.read().decode())

        if not data.get("data") or not data["data"][0].get("d"):
            return {'error': f'Scanner: no data for {ticker}'}

        raw = data["data"][0]["d"]
        result = {
            'name': raw[0],
            'close': raw[1],
            'change_pct': raw[2],
            'high': raw[3],
            'low': raw[4],
            'open_price': raw[5],
            'volume': raw[6],
            'recommend': raw[7],
            'rsi': raw[8],
            'rsi_prev': raw[9],
            'macd': raw[10],
            'macd_signal': raw[11],
            'stoch_k': raw[12],
            'stoch_d': raw[13],
            'bb_upper': raw[14],
            'bb_lower': raw[15],
            'sma20': raw[16],
            'sma50': raw[17],
            'sma200': raw[18],
            'ema5': raw[19],
            'ema20': raw[20],
            'ema50': raw[21],
            'atr': raw[22],
            'high_alltime': raw[23],
            'high_1m': raw[24],
            'high_3m': raw[25],
            'high_6m': raw[26],
            'low_alltime': raw[27],
            'low_1m': raw[28],
            'low_3m': raw[29],
            'low_6m': raw[30],
            'market_cap': raw[31],
        }
        # Round floats
        for k, v in result.items():
            if isinstance(v, float):
                result[k] = round(v, 4)
        return result
    except Exception as e:
        return {'error': f'Scanner error: {e}'}


def fetch_perf(ticker: str, market_type: str) -> dict:
    """Fetch performance data."""
    exchange_symbol, fetch_ticker, mtype = resolve_symbol(ticker)
    tv_sym = exchange_symbol

    # Resolve scanner region from exchange prefix
    region = 'america'
    if ':' in tv_sym:
        ex = tv_sym.split(':', 1)[0]
        region = GLOBAL_EXCHANGES.get(ex, 'america')

    url = f"{TV_URL_BASE}/{region}/scan"

    payload = {
        "symbols": {"tickers": [tv_sym], "query": {"types": []}},
        "columns": ["Perf.W","Perf.1M","Perf.3M","Perf.6M","Perf.YTD","Perf.Y"]
    }
    try:
        req = urllib.request.Request(
            url, data=json.dumps(payload).encode(),
            headers={"User-Agent": UA, "Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.loads(r.read().decode())
        if data.get("data") and data["data"][0].get("d"):
            d = data["data"][0]["d"]
            return {
                'perf_1w': round(d[0], 2) if d[0] else None,
                'perf_1m': round(d[1], 2) if d[1] else None,
                'perf_3m': round(d[2], 2) if d[2] else None,
                'perf_6m': round(d[3], 2) if d[3] else None,
                'perf_ytd': round(d[4], 2) if d[4] else None,
                'perf_1y': round(d[5], 2) if d[5] else None,
            }
    except:
        pass
    return {}


# ---------------------------------------------------------------------------
# Candlestick Pattern Detection
# ---------------------------------------------------------------------------

def classify_bar(bar: dict, prev_bar: Optional[dict] = None) -> dict:
    """
    Classify a single OHLCV bar per Al Brooks terminology.

    Returns dict with:
    - bar_type: 'trend_bull', 'trend_bear', 'doji', 'reversal_bull', 'reversal_bear'
    - body_pct: body as % of range (0-100)
    - close_position: where close is in range (0=low, 1=high)
    - tail_top_pct: top tail as % of range
    - tail_bottom_pct: bottom tail as % of range
    - is_outside_bar: high > prev high AND low < prev low
    - is_inside_bar: high <= prev high AND low >= prev low
    """
    o, h, l, c = bar['open'], bar['high'], bar['low'], bar['close']
    bar_range = h - l
    if bar_range == 0:
        return {'bar_type': 'doji', 'body_pct': 0, 'close_position': 0.5,
                'tail_top_pct': 0, 'tail_bottom_pct': 0, 'is_outside_bar': False,
                'is_inside_bar': False}

    body = abs(c - o)
    body_pct = (body / bar_range) * 100
    close_pos = (c - l) / bar_range
    tail_top = (h - max(o, c)) / bar_range * 100
    tail_bottom = (min(o, c) - l) / bar_range * 100

    # Bar type classification
    if body_pct >= 60:
        bar_type = 'trend_bull' if c > o else 'trend_bear'
    elif body_pct <= 25:
        # Doji — check for reversal bar (tail in opposite direction)
        if tail_bottom >= 33 and close_pos > 0.5:
            bar_type = 'reversal_bull'
        elif tail_top >= 33 and close_pos < 0.5:
            bar_type = 'reversal_bear'
        else:
            bar_type = 'doji'
    else:
        # 25-60% body — in-between, check for reversal characteristics
        if tail_bottom >= 30 and c > o and close_pos > 0.5:
            bar_type = 'reversal_bull'
        elif tail_top >= 30 and c < o and close_pos < 0.5:
            bar_type = 'reversal_bear'
        elif c > o:
            bar_type = 'weak_bull'
        else:
            bar_type = 'weak_bear'

    # Outside/Inside bar detection
    is_outside = False
    is_inside = False
    if prev_bar:
        is_outside = h > prev_bar['high'] and l < prev_bar['low']
        is_inside = h <= prev_bar['high'] and l >= prev_bar['low']

    return {
        'bar_type': bar_type,
        'body_pct': round(body_pct, 1),
        'close_position': round(close_pos, 3),
        'tail_top_pct': round(tail_top, 1),
        'tail_bottom_pct': round(tail_bottom, 1),
        'is_outside_bar': is_outside,
        'is_inside_bar': is_inside,
    }


def detect_patterns(bars: list[dict]) -> dict:
    """
    Detect multi-bar candlestick patterns on the last N bars.
    Returns dict of detected patterns with bar indices.
    """
    if len(bars) < 3:
        return {}

    patterns = {}
    classified = [classify_bar(bars[i], bars[i-1] if i > 0 else None) for i in range(len(bars))]

    # --- Inside bar sequences (ii, iii, ioi) ---
    ii_count = 0
    ii_start = None
    for i in range(len(bars) - 1, 0, -1):
        if classified[i]['is_inside_bar']:
            if ii_count == 0:
                ii_start = i
            ii_count += 1
        else:
            break
    if ii_count >= 2:
        patterns['ii'] = {'count': ii_count, 'bars_ago': len(bars) - ii_start}
    elif ii_count == 1:
        patterns['inside_bar'] = {'bars_ago': len(bars) - ii_start}

    # ioi pattern (inside-outside-inside)
    for i in range(2, len(bars)):
        if (classified[i]['is_inside_bar'] and
            classified[i-1]['is_outside_bar'] and
            classified[i-2]['is_inside_bar']):
            patterns['ioi'] = {'bars_ago': len(bars) - i}

    # --- Two-bar reversal ---
    if len(bars) >= 2:
        last = classified[-1]
        prev = classified[-2]
        # Bull two-bar reversal: bear trend bar followed by bull trend bar that engulfs
        if (prev['bar_type'] in ('trend_bear', 'weak_bear') and
            last['bar_type'] in ('trend_bull', 'weak_bull') and
            bars[-1]['close'] > bars[-2]['open']):
            patterns['two_bar_reversal_bull'] = {'bars_ago': 0}
        # Bear two-bar reversal
        if (prev['bar_type'] in ('trend_bull', 'weak_bull') and
            last['bar_type'] in ('trend_bear', 'weak_bear') and
            bars[-1]['close'] < bars[-2]['open']):
            patterns['two_bar_reversal_bear'] = {'bars_ago': 0}

    # --- Micro channel (2-10 bars, all highs/lows trending) ---
    for length in range(10, 2, -1):
        if len(bars) < length:
            continue
        segment = bars[-length:]
        bull_channel = all(segment[i]['high'] >= segment[i-1]['high'] and
                          segment[i]['low'] >= segment[i-1]['low']
                          for i in range(1, len(segment)))
        bear_channel = all(segment[i]['high'] <= segment[i-1]['high'] and
                          segment[i]['low'] <= segment[i-1]['low']
                          for i in range(1, len(segment)))
        if bull_channel:
            patterns['micro_channel_bull'] = {'length': length}
            break
        if bear_channel:
            patterns['micro_channel_bear'] = {'length': length}
            break

    # --- Spike detection (1-5 strong trend bars in a row) ---
    spike_dir = None
    spike_len = 0
    for i in range(len(bars) - 1, max(len(bars) - 6, -1), -1):
        ct = classified[i]
        if spike_dir is None:
            if ct['bar_type'] == 'trend_bull':
                spike_dir = 'bull'
                spike_len = 1
            elif ct['bar_type'] == 'trend_bear':
                spike_dir = 'bear'
                spike_len = 1
            else:
                break
        elif spike_dir == 'bull' and ct['bar_type'] in ('trend_bull', 'weak_bull'):
            spike_len += 1
        elif spike_dir == 'bear' and ct['bar_type'] in ('trend_bear', 'weak_bear'):
            spike_len += 1
        else:
            break
    if spike_len >= 2:
        patterns[f'spike_{spike_dir}'] = {'bars': spike_len}

    # --- Channel phase after spike (spike → channel → TR lifecycle) ---
    if spike_len >= 2 and len(bars) >= spike_len + 4:
        # Bars after the spike
        after_bars = bars[-(len(bars) - spike_len):]
        after_cls = classified[-(len(bars) - spike_len):]

        if len(after_bars) >= 3:
            channel_count = 0
            check_count = min(len(after_bars), 10)

            for k in range(check_count):
                c = after_cls[-(k + 1)]
                # Channel characteristics:
                # 1. Two-sided trading (not pure trend bars)
                two_sided = c['bar_type'] in ('doji', 'weak_bull', 'weak_bear',
                                               'reversal_bull', 'reversal_bear')
                # 2. Significant tails (hesitation)
                has_tails = c.get('tail_top_pct', 0) > 25 or c.get('tail_bottom_pct', 0) > 25
                # 3. Body overlap with prior bar
                body_overlap = False
                if k < len(after_bars) - 1:
                    prev_body_top = max(after_bars[-(k + 2)]['open'], after_bars[-(k + 2)]['close'])
                    prev_body_bot = min(after_bars[-(k + 2)]['open'], after_bars[-(k + 2)]['close'])
                    curr_body_top = max(after_bars[-(k + 1)]['open'], after_bars[-(k + 1)]['close'])
                    curr_body_bot = min(after_bars[-(k + 1)]['open'], after_bars[-(k + 1)]['close'])
                    overlap = min(prev_body_top, curr_body_top) - max(prev_body_bot, curr_body_bot)
                    if overlap > 0:
                        body_overlap = True

                if two_sided or has_tails or body_overlap:
                    channel_count += 1

            channel_ratio = channel_count / check_count
            if channel_ratio >= 0.4:
                patterns['channel_phase'] = {
                    'direction': spike_dir,
                    'channel_bars': channel_count,
                    'total_checked': check_count,
                    'channel_ratio': round(channel_ratio, 2),
                    'note': f'Spike {spike_dir} transitioning to channel phase: '
                            f'{channel_count}/{check_count} bars show two-sided trading/tails.',
                }

    # --- Three-push pattern (wedge) ---
    if len(bars) >= 10:
        highs = [bars[i]['high'] for i in range(-10, 0)]
        lows = [bars[i]['low'] for i in range(-10, 0)]
        # Find 3 pushes up (each push makes new high but momentum waning)
        push_highs = []
        for i in range(2, len(highs)):
            if highs[i] > highs[i-1] and highs[i] > highs[i-2]:
                push_highs.append(i)
        if len(push_highs) >= 3:
            patterns['wedge_top'] = {'pushes': len(push_highs)}

        push_lows = []
        for i in range(2, len(lows)):
            if lows[i] < lows[i-1] and lows[i] < lows[i-2]:
                push_lows.append(i)
        if len(push_lows) >= 3:
            patterns['wedge_bottom'] = {'pushes': len(push_lows)}

    return patterns


# ---------------------------------------------------------------------------
# Bar-Level Analysis
# ---------------------------------------------------------------------------

def compute_bar_analysis(bars: list[dict]) -> dict:
    """
    Compute bar-level analysis metrics for Al Brooks framework.
    """
    if len(bars) < 20:
        return {'error': 'Insufficient bars for analysis'}

    classified = [classify_bar(bars[i], bars[i-1] if i > 0 else None) for i in range(len(bars))]

    # --- Trend bar ratio (last 20 bars) ---
    recent = classified[-20:]
    bull_trend_bars = sum(1 for c in recent if c['bar_type'] in ('trend_bull', 'weak_bull'))
    bear_trend_bars = sum(1 for c in recent if c['bar_type'] in ('trend_bear', 'weak_bear'))
    trend_bar_ratio = bull_trend_bars / 20 if bull_trend_bars > bear_trend_bars else -bear_trend_bars / 20

    # --- Overlap analysis (consecutive bar body overlap) ---
    overlaps = []
    for i in range(max(len(bars)-10, 1), len(bars)):
        prev_body_top = max(bars[i-1]['open'], bars[i-1]['close'])
        prev_body_bottom = min(bars[i-1]['open'], bars[i-1]['close'])
        curr_body_top = max(bars[i]['open'], bars[i]['close'])
        curr_body_bottom = min(bars[i]['open'], bars[i]['close'])
        overlap = max(0, min(prev_body_top, curr_body_top) - max(prev_body_bottom, curr_body_bottom))
        bar_range = bars[i]['high'] - bars[i]['low']
        overlaps.append(overlap / bar_range * 100 if bar_range > 0 else 0)
    avg_overlap = sum(overlaps) / len(overlaps) if overlaps else 0

    # --- Gap analysis (body gaps between consecutive bars) ---
    gaps_up = 0
    gaps_down = 0
    for i in range(max(len(bars)-10, 1), len(bars)):
        if bars[i]['open'] > bars[i-1]['close']:
            gaps_up += 1
        elif bars[i]['close'] < bars[i-1]['open']:
            gaps_down += 1

    # --- Consecutive closes on same side of 20 EMA ---
    # (we compute a simple 20-bar EMA from closes)
    closes = [b['close'] for b in bars]
    ema_period = 20
    if len(closes) >= ema_period:
        ema = sum(closes[:ema_period]) / ema_period
        for price in closes[ema_period:]:
            ema = (price * (2 / (ema_period + 1))) + (ema * (1 - 2 / (ema_period + 1)))
        above_ema = sum(1 for b in bars[-20:] if b['close'] > ema)
        below_ema = 20 - above_ema
    else:
        above_ema = below_ema = 0

    # --- Latest H1/H2/L1/L2 counting ---
    # Find the most recent leg direction and count pullbacks
    h_count = 0
    l_count = 0
    leg_dir = None
    for i in range(len(bars) - 1, max(len(bars) - 20, 0), -1):
        ct = classified[i]
        if leg_dir is None:
            leg_dir = 'up' if bars[i]['close'] > bars[i]['open'] else 'down'
        if leg_dir == 'up':
            if ct['bar_type'] in ('trend_bear', 'weak_bear', 'doji'):
                l_count += 1
            else:
                if l_count > 0:
                    break  # end of pullback
        else:
            if ct['bar_type'] in ('trend_bull', 'weak_bull', 'doji'):
                h_count += 1
            else:
                if h_count > 0:
                    break

    return {
        'last_20_bars': {
            'bull_trend_bars': bull_trend_bars,
            'bear_trend_bars': bear_trend_bars,
            'doji_bars': 20 - bull_trend_bars - bear_trend_bars,
            'trend_bar_ratio': round(trend_bar_ratio, 2),
        },
        'avg_body_overlap_pct': round(avg_overlap, 1),
        'gaps_last_10': {'up': gaps_up, 'down': gaps_down},
        'closes_vs_ema20_last_20': {'above': above_ema, 'below': below_ema},
        'pullback_count': {'H': h_count, 'L': l_count, 'leg_direction': leg_dir},
    }


def compute_rsi(closes: list[float], period: int = 14) -> Optional[float]:
    """Compute RSI from close prices."""
    if len(closes) < period + 1:
        return None
    deltas = [closes[i] - closes[i-1] for i in range(1, len(closes))]
    gains = [d if d > 0 else 0 for d in deltas]
    losses = [-d if d < 0 else 0 for d in deltas]
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    for i in range(period, len(deltas)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return round(100 - (100 / (1 + rs)), 2)


def compute_macd(closes: list[float], fast: int = 12, slow: int = 26, signal: int = 9) -> Optional[dict]:
    """Compute MACD from close prices."""
    if len(closes) < slow + signal:
        return None
    def ema_val(data, period):
        e = sum(data[:period]) / period
        mult = 2 / (period + 1)
        vals = [e]
        for val in data[period:]:
            e = (val * mult) + (e * (1 - mult))
            vals.append(e)
        return vals
    ema_fast = ema_val(closes, fast)
    ema_slow = ema_val(closes, slow)
    # Align: ema_slow starts at index (slow-1), ema_fast at (fast-1)
    offset = slow - fast
    macd_line = [ema_fast[i + offset] - ema_slow[i] for i in range(len(ema_slow))]
    if len(macd_line) < signal:
        return None
    signal_line = ema_val(macd_line, signal)
    return {
        'macd': round(macd_line[-1], 4),
        'signal': round(signal_line[-1], 4),
        'histogram': round(macd_line[-1] - signal_line[-1], 4),
    }


def compute_stochastic(bars: list[dict], period: int = 14, smooth: int = 3) -> Optional[dict]:
    """Compute Stochastic %K and %D from OHLCV bars."""
    if len(bars) < period + smooth:
        return None
    k_values = []
    for i in range(period - 1, len(bars)):
        segment = bars[i - period + 1:i + 1]
        highest = max(b['high'] for b in segment)
        lowest = min(b['low'] for b in segment)
        if highest == lowest:
            k_values.append(50.0)
        else:
            k_values.append((bars[i]['close'] - lowest) / (highest - lowest) * 100)
    k = round(sum(k_values[-smooth:]) / smooth, 2)
    d = round(sum(k_values[-smooth * 2:-smooth]) / smooth, 2) if len(k_values) >= smooth * 2 else k
    return {'k': k, 'd': d}


def compute_atr(bars: list[dict], period: int = 14) -> Optional[float]:
    """Compute Average True Range."""
    if len(bars) < period + 1:
        return None
    trs = []
    for i in range(1, len(bars)):
        tr = max(
            bars[i]['high'] - bars[i]['low'],
            abs(bars[i]['high'] - bars[i-1]['close']),
            abs(bars[i]['low'] - bars[i-1]['close'])
        )
        trs.append(tr)
    atr = sum(trs[-period:]) / period
    return round(atr, 4)


def compute_indicators_from_bars(bars: list[dict]) -> dict:
    """Compute RSI, MACD, Stoch, ATR from OHLCV bars (fallback when scanner unavailable)."""
    if len(bars) < 30:
        return {}
    closes = [b['close'] for b in bars]
    result = {}
    rsi = compute_rsi(closes)
    if rsi is not None:
        result['rsi'] = rsi
    macd = compute_macd(closes)
    if macd:
        result['macd'] = macd['macd']
        result['macd_signal'] = macd['signal']
        result['macd_histogram'] = macd['histogram']
    stoch = compute_stochastic(bars)
    if stoch:
        result['stoch_k'] = stoch['k']
        result['stoch_d'] = stoch['d']
    atr = compute_atr(bars)
    if atr:
        result['atr'] = atr
    return result


def _find_swings(bars: list[dict], lookback: int = 2, forward: int = 2,
                  pct_threshold: float = 0.3) -> tuple[list, list]:
    """
    Proper swing detection with percent-based thresholding.

    Improvements over naive neighbour comparison:
    - Uses a lookback/forward window (allows equal highs/lows as swing levels)
    - Percent-based noise filter (ignores micro-swings below threshold)
    - Merges nearby swings (within 3 bars)
    - Handles last bars with tentative detection (no forward bars available)

    Returns (swing_highs, swing_lows) where each is a list of
    {'price': float, 'bar_idx': int, 'tentative': bool (optional)}.
    """
    n = len(bars)
    swing_highs: list[dict] = []
    swing_lows: list[dict] = []

    # --- Main pass: bars with full lookback+forward window ---
    for i in range(lookback, n - forward):
        high_i = bars[i]['high']
        low_i = bars[i]['low']

        # Swing high: bar i's high is >= ALL highs in window
        is_pivot_high = True
        for j in range(i - lookback, i + forward + 1):
            if j == i:
                continue
            if high_i < bars[j]['high']:
                is_pivot_high = False
                break

        if is_pivot_high:
            # Merge nearby swings (within 3 bars) — keep the higher one
            if swing_highs and i - swing_highs[-1]['bar_idx'] < 3:
                if high_i > swing_highs[-1]['price']:
                    swing_highs[-1] = {'price': high_i, 'bar_idx': i}
                continue
            # Percent threshold: significant move from prior swing?
            if swing_highs:
                pct_move = (high_i - swing_highs[-1]['price']) / swing_highs[-1]['price'] * 100
                if pct_move < pct_threshold:
                    continue
            swing_highs.append({'price': high_i, 'bar_idx': i})

        # Swing low: bar i's low is <= ALL lows in window
        is_pivot_low = True
        for j in range(i - lookback, i + forward + 1):
            if j == i:
                continue
            if low_i > bars[j]['low']:
                is_pivot_low = False
                break

        if is_pivot_low:
            if swing_lows and i - swing_lows[-1]['bar_idx'] < 3:
                if low_i < swing_lows[-1]['price']:
                    swing_lows[-1] = {'price': low_i, 'bar_idx': i}
                continue
            if swing_lows:
                prev_price = swing_lows[-1]['price']
                pct_move = abs(low_i - prev_price) / prev_price * 100 if prev_price else 0
                if pct_move < pct_threshold:
                    continue
            swing_lows.append({'price': low_i, 'bar_idx': i})

    # --- Tentative pass: last `forward` bars (only lookback available) ---
    for i in range(max(lookback, n - forward), n):
        high_i = bars[i]['high']
        is_pivot_high = all(high_i >= bars[j]['high'] for j in range(i - lookback, i))
        if is_pivot_high:
            if (not swing_highs or i > swing_highs[-1]['bar_idx']) and \
               (not swing_highs or
                (high_i - swing_highs[-1]['price']) / swing_highs[-1]['price'] * 100 >= pct_threshold):
                swing_highs.append({'price': high_i, 'bar_idx': i, 'tentative': True})

        low_i = bars[i]['low']
        is_pivot_low = all(low_i <= bars[j]['low'] for j in range(i - lookback, i))
        if is_pivot_low:
            if (not swing_lows or i > swing_lows[-1]['bar_idx']) and \
               (not swing_lows or
                abs(low_i - swing_lows[-1]['price']) / swing_lows[-1]['price'] * 100 >= pct_threshold):
                swing_lows.append({'price': low_i, 'bar_idx': i, 'tentative': True})

    return swing_highs, swing_lows


def compute_trend_context(bars: list[dict]) -> dict:
    """
    Compute trend context from OHLCV data.
    Returns SMA/EMA values, trend classification, key levels.
    """
    closes = [b['close'] for b in bars]
    if len(closes) < 50:
        return {'error': 'Need at least 50 bars for trend context'}

    def sma(data, period):
        if len(data) < period:
            return None
        return round(sum(data[-period:]) / period, 4)

    def ema(data, period):
        if len(data) < period:
            return None
        e = sum(data[:period]) / period
        mult = 2 / (period + 1)
        for val in data[period:]:
            e = (val * mult) + (e * (1 - mult))
        return round(e, 4)

    sma20 = sma(closes, 20)
    sma50 = sma(closes, 50)
    ema20 = ema(closes, 20)
    ema50 = ema(closes, 50)

    last_close = closes[-1]

    # Trend classification
    if ema20 and ema50:
        if last_close > ema20 > ema50:
            trend = 'bull_trend'
        elif last_close < ema20 < ema50:
            trend = 'bear_trend'
        elif ema20 and abs(ema20 - ema50) / ema50 < 0.01:
            trend = 'trading_range'
        else:
            trend = 'mixed'
    else:
        trend = 'insufficient_data'

    # Proper swing detection with percent-based thresholding
    swing_highs, swing_lows = _find_swings(bars, lookback=2, forward=2, pct_threshold=0.3)

    return {
        'sma20': sma20,
        'sma50': sma50,
        'ema20': ema20,
        'ema50': ema50,
        'last_close': last_close,
        'trend': trend,
        'swing_highs': swing_highs[-5:] if swing_highs else [],
        'swing_lows': swing_lows[-5:] if swing_lows else [],
    }


# ---------------------------------------------------------------------------
# Main Entry Point
# ---------------------------------------------------------------------------

async def analyze_ticker(ticker: str, exchange: str | None = None) -> dict:
    """Full analysis: OHLCV multi-timeframe + indicators + patterns."""
    exchange_symbol, fetch_ticker, market_type = resolve_symbol(ticker, exchange)

    print(f"[fetching {ticker} → {exchange_symbol} ({market_type})]", file=sys.stderr)

    # Fetch OHLCV for all timeframes
    ohlcv_data = {}
    for tf_name, (interval, count) in TIMEFRAMES.items():
        bars = await fetch_ohlcv(exchange_symbol, interval, count)
        if bars and 'error' not in bars[0]:
            ohlcv_data[tf_name] = bars
        else:
            ohlcv_data[tf_name] = bars  # include error for debugging

    # Fetch scanner indicators
    scanner = fetch_scanner(ticker, market_type)
    perf = fetch_perf(ticker, market_type)

    # If scanner failed, compute indicators from daily OHLCV bars
    if 'error' in scanner and ohlcv_data.get('daily') and isinstance(ohlcv_data['daily'], list) and ohlcv_data['daily'] and 'error' not in ohlcv_data['daily'][0]:
        computed = compute_indicators_from_bars(ohlcv_data['daily'])
        scanner = {'_computed': True, **computed}
        # Also set close from last bar
        if ohlcv_data['daily']:
            scanner['close'] = ohlcv_data['daily'][-1]['close']

    # Compute analysis per timeframe
    analysis = {}
    for tf_name, bars in ohlcv_data.items():
        if not bars or (isinstance(bars, list) and bars and 'error' in bars[0]):
            analysis[tf_name] = {'error': bars[0].get('error', 'No data') if bars else 'No data'}
            continue

        analysis[tf_name] = {
            'bar_count': len(bars),
            'trend_context': compute_trend_context(bars),
            'bar_analysis': compute_bar_analysis(bars),
            'patterns': detect_patterns(bars),
            'last_bar_classified': classify_bar(
                bars[-1], bars[-2] if len(bars) > 1 else None
            ) if bars else None,
            'last_10_bars_classified': [
                classify_bar(bars[i], bars[i-1] if i > 0 else None)
                for i in range(max(0, len(bars)-10), len(bars))
            ] if bars else [],
        }

    result = {
        'ticker': ticker,
        'exchange_symbol': exchange_symbol,
        'market_type': market_type,
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'indicators': scanner,
        'performance': perf,
        'timeframes': ohlcv_data,
        'analysis': analysis,
    }

    return result


def filter_brooks(data: dict) -> dict:
    """
    Strip non-Brooks indicators from output.
    Keeps: OHLCV, ema20, atr, bar_analysis, patterns, trend_context, swing points.
    Removes: rsi, macd, stoch, bb, aroon, adx, cci, sma50, sma200, ema5, ema50, performance.
    """
    if 'indicators' in data:
        ind = data['indicators']
        brooks_indicators = {}
        # Keep only Brooks-relevant fields
        for key in ('ema20', 'atr', 'close'):
            if key in ind:
                brooks_indicators[key] = ind[key]
        data['indicators'] = brooks_indicators

    # Remove performance (not Brooks)
    data.pop('performance', None)

    # Clean trend_context: keep ema20, remove sma50/ema50
    for tf_name, tf_analysis in data.get('analysis', {}).items():
        tc = tf_analysis.get('trend_context', {})
        tc.pop('sma50', None)
        tc.pop('ema50', None)
        tc.pop('sma20', None)  # sma20 not Brooks — only ema20

    return data


def main():
    args = sys.argv[1:]
    brooks_mode = '--brooks' in args
    analyze_mode = '--analyze' in args
    exchange_hint = None
    remaining = []
    i = 0
    while i < len(args):
        a = args[i]
        if a == '--exchange':
            i += 1
            if i < len(args):
                exchange_hint = args[i]
            else:
                print("[error: --exchange requires a value]", file=sys.stderr)
                sys.exit(1)
        elif a in ('--brooks', '--analyze'):
            pass  # handled above
        else:
            remaining.append(a)
        i += 1
    tickers = remaining or ['CNMA.JK']

    async def run_all():
        for ticker in tickers:
            try:
                data = await analyze_ticker(ticker, exchange=exchange_hint)

                if brooks_mode:
                    data = filter_brooks(data)

                if analyze_mode:
                    # Run brooks_analysis inline — no intermediate files, no pipes
                    from brooks_analysis import analyze as brooks_analyze
                    analysis = brooks_analyze(data)
                    print(json.dumps(analysis, indent=2, default=str))

                    # Save analysis file
                    outdir = os.path.dirname(os.path.abspath(__file__))
                    fname = ticker.replace(":", "_").replace(".", "_") + "_brooks_analysis.json"
                    outpath = os.path.join(outdir, fname)
                    with open(outpath, 'w') as f:
                        json.dump(analysis, f, default=str, indent=2)
                    print(f"\n[saved: {outpath}]", file=sys.stderr)
                else:
                    # Print raw/brooks JSON
                    print(json.dumps(data, indent=2, default=str))

                    # Save raw file
                    outdir = os.path.dirname(os.path.abspath(__file__))
                    suffix = "_brooks.json" if brooks_mode else "_raw.json"
                    fname = ticker.replace(":", "_").replace(".", "_") + suffix
                    outpath = os.path.join(outdir, fname)
                    with open(outpath, 'w') as f:
                        json.dump(data, f, default=str, indent=2)
                    print(f"\n[saved: {outpath}]", file=sys.stderr)
            except Exception as e:
                err = {'error': str(e), 'ticker': ticker}
                print(json.dumps(err, indent=2))
                print(f"\n[error: {e}]", file=sys.stderr)

    asyncio.run(run_all())


if __name__ == '__main__':
    main()
