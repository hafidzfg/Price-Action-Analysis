#!/usr/bin/env python3
"""
backtest.py — Al Brooks price action backtester.

Slides the Tier-1 engine (+ deterministic Tier-2 decision layer) across
historical daily OHLCV data. Pure Python — no LLM calls.

Usage:
    python backtest.py AAPL
    python backtest.py BBRI.JK --bars 500
    python backtest.py TSX:BB --exchange TSX --bars 400 --start 80

Output:
    Console trade journal + summary statistics + JSON file
"""

import sys, json, os, asyncio
from datetime import datetime, timezone
from collections import defaultdict

# ── Path setup ──────────────────────────────────────────────────────────────
SKILL_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SKILL_DIR)

# ── Imports from existing modules ──────────────────────────────────────────
from fetch_data import (
    resolve_symbol, fetch_ohlcv, classify_bar,
    compute_trend_context, compute_bar_analysis, detect_patterns,
    detect_reversal_signals, compute_indicators_from_bars,
)
from brooks_analysis import analyze as brooks_analyze


# ── Constants ──────────────────────────────────────────────────────────────
DEFAULT_BARS = 450   # enough for ~1.5yr + indicator warmup
MIN_BARS     = 60    # minimum bars before we start looking for signals
MAX_HOLD     = 25    # max bars to hold a position (time stop)


# ══════════════════════════════════════════════════════════════════════════════
# 1. DATA FETCHING
# ══════════════════════════════════════════════════════════════════════════════

async def fetch_historical_data(ticker: str, exchange: str | None = None,
                                bars_count: int = DEFAULT_BARS) -> dict:
    """Fetch historical daily OHLCV + indicators for backtesting."""
    exchange_symbol, fetch_ticker, market_type = resolve_symbol(ticker, exchange)
    print(f"[backtest] {ticker} -> {exchange_symbol}  fetching {bars_count}d ...",
          file=sys.stderr)

    daily_bars = await fetch_ohlcv(exchange_symbol, '1D', bars_count)
    if not daily_bars or (isinstance(daily_bars, list) and
                          daily_bars and 'error' in daily_bars[0]):
        err = daily_bars[0].get('error', 'No data') if daily_bars else 'No data'
        return {'error': err, 'ticker': ticker}

    indicators = compute_indicators_from_bars(daily_bars)
    if daily_bars:
        indicators['close'] = daily_bars[-1]['close']

    classified = []
    for i, bar in enumerate(daily_bars):
        prev = daily_bars[i-1] if i > 0 else None
        classified.append(classify_bar(bar, prev))

    print(f"[backtest] Got {len(daily_bars)} daily bars ({len(classified)} classified)",
          file=sys.stderr)
    return {
        'ticker': ticker,
        'exchange_symbol': exchange_symbol,
        'daily_bars': daily_bars,
        'classified': classified,
        'indicators': indicators,
    }


# ══════════════════════════════════════════════════════════════════════════════
# 2. WINDOW BUILDER
# ══════════════════════════════════════════════════════════════════════════════

def build_window_data(ticker: str, all_bars: list, all_classified: list,
                      end_idx: int) -> dict:
    """
    Build the analysis input dict that brooks_analysis.analyze() expects
    for a window ending at end_idx.
    """
    bars = all_bars[:end_idx + 1]
    cls = all_classified[:end_idx + 1]

    trend_context = compute_trend_context(bars)
    bar_analysis = compute_bar_analysis(bars)
    patterns = detect_patterns(bars)
    reversal_signals = detect_reversal_signals(bars, patterns, trend_context)
    indicators = compute_indicators_from_bars(bars)

    last_bar = bars[-1]
    indicators['close'] = last_bar['close']
    if trend_context.get('ema20'):
        indicators['ema20'] = trend_context['ema20']

    last_10 = cls[-10:] if len(cls) >= 10 else cls
    last_bar_cls = cls[-1] if cls else {}

    return {
        'ticker': ticker,
        'timeframes': {'daily': bars},
        'analysis': {
            'daily': {
                'bar_count': len(bars),
                'trend_context': trend_context,
                'bar_analysis': bar_analysis,
                'patterns': patterns,
                'reversal_signals': reversal_signals,
                'last_bar_classified': last_bar_cls,
                'last_10_bars_classified': last_10,
            },
        },
        'indicators': indicators,
    }


# ══════════════════════════════════════════════════════════════════════════════
# 3. TRADE TRACKING
# ══════════════════════════════════════════════════════════════════════════════

class Position:
    __slots__ = (
        'entry_bar', 'entry_date', 'entry_price', 'direction',
        'setup_type', 'conviction', 'stop_loss', 'target',
        'bars_held',
    )
    def __init__(self, entry_bar: int, entry_date: str, entry_price: float,
                 direction: str, setup_type: str, conviction: int,
                 stop_loss: float, target: float):
        self.entry_bar = entry_bar
        self.entry_date = entry_date
        self.entry_price = entry_price
        self.direction = direction
        self.setup_type = setup_type
        self.conviction = conviction
        self.stop_loss = stop_loss
        self.target = target
        self.bars_held = 0


class Trade:
    __slots__ = (
        'entry_bar', 'entry_date', 'entry_price', 'direction',
        'setup_type', 'conviction', 'stop_loss', 'target',
        'exit_bar', 'exit_date', 'exit_price', 'exit_reason',
        'pnl_pct', 'bars_held',
    )
    def __init__(self, pos: Position, exit_bar: int, exit_date: str,
                 exit_price: float, exit_reason: str):
        self.entry_bar = pos.entry_bar
        self.entry_date = pos.entry_date
        self.entry_price = pos.entry_price
        self.direction = pos.direction
        self.setup_type = pos.setup_type
        self.conviction = pos.conviction
        self.stop_loss = pos.stop_loss
        self.target = pos.target
        self.exit_bar = exit_bar
        self.exit_date = exit_date
        self.exit_price = exit_price
        self.exit_reason = exit_reason
        self.bars_held = pos.bars_held + 1

        if pos.direction == 'LONG':
            self.pnl_pct = round((exit_price - pos.entry_price) / pos.entry_price * 100, 2)
        else:
            self.pnl_pct = round((pos.entry_price - exit_price) / pos.entry_price * 100, 2)


# ══════════════════════════════════════════════════════════════════════════════
# 4. DECISION LAYER — Entry / Exit Rules
# ══════════════════════════════════════════════════════════════════════════════

def _compute_range_metrics(analysis: dict, price: float):
    """Extract trading range bounds and price position from analysis."""
    context = analysis.get('context', {})
    swing_highs = context.get('swing_highs', [])
    swing_lows = context.get('swing_lows', [])
    range_high = max((sh['price'] for sh in swing_highs), default=None)
    range_low = min((sl['price'] for sl in swing_lows), default=None)

    price_pos = None
    if range_high and range_low and range_high > range_low:
        price_pos = (price - range_low) / (range_high - range_low)

    return range_high, range_low, price_pos


def _bar_is_reversal(bar_cls: dict, direction: str) -> bool:
    """Check if the last bar is a reversal bar in the given direction."""
    if direction == 'LONG':
        return bar_cls.get('bar_type') in ('reversal_bull',) and \
               bar_cls.get('body_pct', 0) >= 40
    else:
        return bar_cls.get('bar_type') in ('reversal_bear',) and \
               bar_cls.get('body_pct', 0) >= 40


def _bar_is_trend_bar(bar_cls: dict, direction: str) -> bool:
    """Check if the last bar is a strong trend bar in the given direction."""
    if direction == 'LONG':
        return bar_cls.get('bar_type') in ('trend_bull',) and \
               bar_cls.get('body_pct', 0) >= 60
    else:
        return bar_cls.get('bar_type') in ('trend_bear',) and \
               bar_cls.get('body_pct', 0) >= 60


def _has_reversal_signal(analysis: dict) -> list:
    """Check for active reversal signals."""
    daily_rev = analysis.get('analysis', {}).get('daily', {}).get('reversal_signals', [])
    if not daily_rev:
        daily_rev = []
    patterns = analysis.get('analysis', {}).get('daily', {}).get('patterns', {})
    if patterns is None:
        patterns = {}
    sigs = list(daily_rev)
    if patterns.get('wedge_top'):
        sigs.append('wedge_top')
    if patterns.get('wedge_bottom'):
        sigs.append('wedge_bottom')
    if patterns.get('two_bar_reversal_bull'):
        sigs.append('two_bar_reversal_bull')
    if patterns.get('two_bar_reversal_bear'):
        sigs.append('two_bar_reversal_bear')
    return sigs


def _get_stop_target(last_bar: dict, direction: str, atr: float,
                     pb_details: list = None) -> tuple:
    """
    Calculate stop loss and target for an entry.
    Uses pullback-based stops when available, else ATR-based.
    """
    last_low = last_bar.get('low', 0)
    last_high = last_bar.get('high', 0)
    last_close = last_bar.get('close', 0)
    atr = atr or (last_close * 0.02)

    if direction == 'LONG':
        # Stop below the pullback's lowest bar, or below last bar low
        # Use 1× ATR for wider stop (gives room for volatility)
        stop = last_low - (atr * 1.0)
        target = last_close + (atr * 2.0)
    else:
        stop = last_high + (atr * 1.0)
        target = last_close - (atr * 2.0)

    return round(stop, 4), round(target, 4)


def _min_rr_check(stop: float, target: float, entry: float, direction: str) -> bool:
    """Minimum 1:1 risk/reward check."""
    if direction == 'LONG':
        risk = entry - stop
        reward = target - entry
    else:
        risk = stop - entry
        reward = entry - target
    if risk <= 0 or reward <= 0:
        return False
    return (reward / risk) >= 1.0


# ── Entry rule implementations ────────────────────────────────────────────

def rule_m2b_m2s(analysis: dict, bar_cls: dict, last_bar: dict,
                 atr: float, prev_pb_count: str | None,
                 prev_ema_prox: str | None = None,
                 bars: list = None) -> Position | None:
    """
    M2B/M2S: Standard H2/L2 at EMA in a clear trend.
    Works in strong_bull/bear and tfo_bull/bear day types.
    Also works in trading_range when H2/L2 aligns with range edge.
    Also works in ambiguous when trend is clear (price above/below EMA).
    """
    day_type = analysis.get('day_type', {}).get('hypothesis', '')
    trend_health = analysis.get('trend_health', {})
    health_stage = trend_health.get('stage', '')
    trend_dir = analysis.get('context', {}).get('trend', '')
    bull = 'bull' in trend_dir
    bear = 'bear' in trend_dir
    price = analysis.get('context', {}).get('price', 0)
    ema20 = analysis.get('context', {}).get('ema20', 0)

    pb = analysis.get('pullbacks', {})
    sb = pb.get('structure_based', {})
    cl = sb.get('current_leg', {})
    pb_count = cl.get('pullback_count', 'unknown')
    ema_prox = cl.get('ema_proximity', 'unknown')
    pb_details = cl.get('pullback_details', [])

    conv = analysis.get('conviction_objective', {})
    subtotal = conv.get('subtotal', 0)

    # Skip if trend health is transition_complete (too late)
    if health_stage == 'transition_complete':
        return None

    # Late stage: allow but with lower conviction requirement
    if health_stage == 'late_stage':
        conv_threshold = 1  # Same threshold, but mark as scalp
    else:
        conv_threshold = 1

    # ── M2B (Long) ────────────────────────────────────────────────────
    # Check if we have a bullish pullback (L2/L3) and price is above EMA
    if bull and pb_count in ('L2', 'L3'):
        # Allow entry if price is above EMA (trend is clear)
        price_above_ema = price > ema20 if ema20 else False
        
        # Check EMA proximity — allow "far" if price is above EMA
        ema_ok = ema_prox in ('at_ema', 'near_ema') or price_above_ema
        
        if not ema_ok:
            return None

        # Only trigger when pullback JUST formed (not already held)
        if prev_pb_count in ('L2', 'L3') and prev_pb_count is not None:
            # Block re-entry only if previous was also at EMA
            if prev_ema_prox in ('at_ema', 'near_ema'):
                return None  # Already at EMA, skip

        # Strong trend or TR at range bottom
        if day_type in ('strong_bull', 'tfo_bull'):
            # Valid - standard M2B setup
            if subtotal < 1:
                return None
        elif day_type == 'trading_range':
            _, _, price_pos = _compute_range_metrics(analysis, price)
            if price_pos is None or price_pos > 0.40:
                return None  # only fade LONG at range bottom
            if subtotal < 1:
                return None
        elif day_type == 'ambiguous':
            # Allow in ambiguous if trend is clear
            if subtotal < 1:
                return None
        else:
            return None

        # Confirm pullback is complete: current bar should be bullish
        # (trend_bull or reversal_bull with decent body)
        bar_type = bar_cls.get('bar_type', '')
        body_pct = bar_cls.get('body_pct', 0)
        is_bullish_bar = ('trend_bull' in bar_type or 'reversal_bull' in bar_type) and body_pct >= 40
        
        if not is_bullish_bar:
            return None  # Not a bullish confirmation bar
        
        # Additional confirmation: price should be above the previous bar's close
        # (confirms the pullback is complete and price is resuming)
        if bars and len(bars) > 1:
            prev_bar = bars[-2]
            prev_close = prev_bar.get('close', 0)
            if price <= prev_close:
                return None  # Price not above previous close, pullback not complete
        
        # Additional confirmation: price should be above the previous bar's close
        # (confirms the pullback is complete and price is resuming)
        if bars and len(bars) > 1:
            prev_bar = bars[-2]
            prev_close = prev_bar.get('close', 0)
            if price <= prev_close:
                return None  # Price not above previous close, pullback not complete

        stop, target = _get_stop_target(last_bar, 'LONG', atr, pb_details)
        if not _min_rr_check(stop, target, price, 'LONG'):
            return None

        # Entry should be 1 tick above signal bar high
        signal_bar_high = last_bar.get('high', 0)
        entry_price = signal_bar_high + (last_bar.get('close', 0) * 0.001)  # 0.1% above high
        
        # Note: We're entering at the signal bar high + 0.1%
        # This is a buy stop order that will be filled if price breaks above
        # We don't need to check if price already broke above, because
        # the order will only be filled if it does
        
        return Position(
            entry_bar=len(last_bar['date']) if 0 else 0,  # placeholder
            entry_date=last_bar.get('date', ''),
            entry_price=entry_price,
            direction='LONG',
            setup_type='M2B',
            conviction=subtotal,
            stop_loss=stop,
            target=target,
        )

    # ── M2S (Short) ───────────────────────────────────────────────────
    # Check if we have a bearish pullback (H2/H3) and price is below EMA
    if bear and pb_count in ('H2', 'H3'):
        # Allow entry if price is below EMA (trend is clear)
        price_below_ema = price < ema20 if ema20 else False
        
        # Check EMA proximity — allow "far" if price is below EMA
        ema_ok = ema_prox in ('at_ema', 'near_ema') or price_below_ema
        
        if not ema_ok:
            return None

        # Only trigger when pullback JUST formed (not already held)
        if prev_pb_count in ('H2', 'H3') and prev_pb_count is not None:
            # Block re-entry only if previous was also at EMA
            if prev_ema_prox in ('at_ema', 'near_ema'):
                return None  # Already at EMA, skip

        if day_type in ('strong_bear', 'tfo_bear'):
            # Valid - standard M2S setup
            if subtotal < 1:
                return None
        elif day_type == 'trading_range':
            _, _, price_pos = _compute_range_metrics(analysis, price)
            if price_pos is None or price_pos < 0.60:
                return None  # only fade SHORT at range top
            if subtotal < 1:
                return None
        elif day_type == 'ambiguous':
            # Allow in ambiguous if trend is clear
            if subtotal < 1:
                return None
        else:
            return None

        # Confirm pullback is complete: current bar should be bearish
        # (trend_bear or reversal_bear with decent body)
        bar_type = bar_cls.get('bar_type', '')
        body_pct = bar_cls.get('body_pct', 0)
        is_bearish_bar = ('trend_bear' in bar_type or 'reversal_bear' in bar_type) and body_pct >= 40
        
        if not is_bearish_bar:
            return None  # Not a bearish confirmation bar
        
        # Additional confirmation: price should be below the previous bar's close
        # (confirms the pullback is complete and price is resuming)
        if bars and len(bars) > 1:
            prev_bar = bars[-2]
            prev_close = prev_bar.get('close', 0)
            if price >= prev_close:
                return None  # Price not below previous close, pullback not complete
        
        # Additional confirmation: price should be below the previous bar's close
        # (confirms the pullback is complete and price is resuming)
        if bars and len(bars) > 1:
            prev_bar = bars[-2]
            prev_close = prev_bar.get('close', 0)
            if price >= prev_close:
                return None  # Price not below previous close, pullback not complete

        stop, target = _get_stop_target(last_bar, 'SHORT', atr, pb_details)
        if not _min_rr_check(stop, target, price, 'SHORT'):
            return None

        # Entry should be 1 tick below signal bar low
        signal_bar_low = last_bar.get('low', 0)
        entry_price = signal_bar_low - (last_bar.get('close', 0) * 0.001)  # 0.1% below low
        
        # Note: We're entering at the signal bar low - 0.1%
        # This is a sell stop order that will be filled if price breaks below
        # We don't need to check if price already broke below, because
        # the order will only be filled if it does
        
        return Position(
            entry_bar=0,
            entry_date=last_bar.get('date', ''),
            entry_price=entry_price,
            direction='SHORT',
            setup_type='M2S',
            conviction=subtotal,
            stop_loss=stop,
            target=target,
        )

    return None


def rule_trend_breakout(analysis: dict, bar_cls: dict, last_bar: dict,
                        atr: float) -> Position | None:
    """
    Trend breakout: Spike + first pullback in a strong trend.
    First pullback (L1/H1) that stalls at EMA in a strong trend day.
    """
    day_type = analysis.get('day_type', {}).get('hypothesis', '')
    trend_health = analysis.get('trend_health', {})
    health_stage = trend_health.get('stage', '')
    trend_dir = analysis.get('context', {}).get('trend', '')
    bull = 'bull' in trend_dir
    price = analysis.get('context', {}).get('price', 0)

    # Allow in strong/tfo trends, or ambiguous with clear trend
    if day_type in ('strong_bull', 'strong_bear', 'tfo_bull', 'tfo_bear'):
        conv_threshold = 1
    elif day_type == 'ambiguous' and trend_dir in ('bull_trend', 'bear_trend'):
        conv_threshold = 1  # Same threshold for ambiguous
    else:
        return None

    if health_stage in ('late_stage', 'transition_complete', 'insufficient_data'):
        return None

    pb = analysis.get('pullbacks', {})
    sb = pb.get('structure_based', {})
    cl = sb.get('current_leg', {})
    pb_count = cl.get('pullback_count', 'unknown')
    ema_prox = cl.get('ema_proximity', 'unknown')
    conv = analysis.get('conviction_objective', {}).get('subtotal', 0)

    patterns = analysis.get('analysis', {}).get('daily', {}).get('patterns', {})

    # First pullback (L1/H1) after a spike
    if bull and pb_count == 'L1' and ema_prox in ('at_ema', 'near_ema'):
        if not (patterns.get('spike_bull') or _bar_is_trend_bar(bar_cls, 'LONG')):
            return None
        if conv < conv_threshold:
            return None
        stop, target = _get_stop_target(last_bar, 'LONG', atr)
        if not _min_rr_check(stop, target, price, 'LONG'):
            return None
        return Position(0, last_bar.get('date', ''), price, 'LONG',
                        'TBO', conv, stop, target)

    if not bull and pb_count == 'H1' and ema_prox in ('at_ema', 'near_ema'):
        if not (patterns.get('spike_bear') or _bar_is_trend_bar(bar_cls, 'SHORT')):
            return None
        if conv < conv_threshold:
            return None
        stop, target = _get_stop_target(last_bar, 'SHORT', atr)
        if not _min_rr_check(stop, target, price, 'SHORT'):
            return None
        return Position(0, last_bar.get('date', ''), price, 'SHORT',
                        'TBS', conv, stop, target)

    return None


def rule_range_fade(analysis: dict, bar_cls: dict, last_bar: dict,
                    atr: float, prev_signal_bars: dict,
                    bar_idx: int) -> Position | None:
    """
    Range fade: H2/L2 at trading range edge with reversal bar confirmation.
    Only triggers when ALL conditions met.
    """
    day_type = analysis.get('day_type', {}).get('hypothesis', '')
    if day_type != 'trading_range':
        return None

    price = analysis.get('context', {}).get('price', 0)
    trend_dir = analysis.get('context', {}).get('trend', '')
    bull = 'bull' in trend_dir
    bear = 'bear' in trend_dir
    conv = analysis.get('conviction_objective', {}).get('subtotal', 0)

    range_high, range_low, price_pos = _compute_range_metrics(analysis, price)
    if range_high is None or range_low is None or price_pos is None:
        return None

    pb = analysis.get('pullbacks', {})
    sb = pb.get('structure_based', {})
    cl = sb.get('current_leg', {})
    pb_count = cl.get('pullback_count', 'unknown')

    # Minimum conviction for range trades
    if conv < 0:
        return None

    # ── LONG: Near bottom of range + bullish reversal bar ─────────────
    if price_pos < 0.30:
        # Check for bullish signal: reversal bar, or L2 at bottom, or trend bar
        has_bull_signal = (
            _bar_is_reversal(bar_cls, 'LONG') or
            (bull and pb_count in ('L2', 'L3')) or
            (bear and pb_count in ('H2', 'H3')) or  # H2/H3 at bottom = buy
            _bar_is_trend_bar(bar_cls, 'LONG')
        )
        if has_bull_signal:
            # Don't re-enter too quickly
            last_long = prev_signal_bars.get('RF_LONG', -999)
            if bar_idx - last_long < 5:
                return None

            stop, target = _get_stop_target(last_bar, 'LONG', atr)
            if _min_rr_check(stop, target, price, 'LONG'):
                return Position(0, last_bar.get('date', ''), price, 'LONG',
                                'RF_LONG', conv, stop, target)

    # ── SHORT: Near top of range + bearish reversal bar ──────────────
    if price_pos > 0.70:
        has_bear_signal = (
            _bar_is_reversal(bar_cls, 'SHORT') or
            (bear and pb_count in ('H2', 'H3')) or
            (bull and pb_count in ('L2', 'L3')) or  # L2/L3 at top = sell
            _bar_is_trend_bar(bar_cls, 'SHORT')
        )
        if has_bear_signal:
            last_short = prev_signal_bars.get('RF_SHORT', -999)
            if bar_idx - last_short < 5:
                return None

            stop, target = _get_stop_target(last_bar, 'SHORT', atr)
            if _min_rr_check(stop, target, price, 'SHORT'):
                return Position(0, last_bar.get('date', ''), price, 'SHORT',
                                'RF_SHORT', conv, stop, target)

    return None


def rule_wedge_reversal(analysis: dict, bar_cls: dict, last_bar: dict,
                        atr: float, bar_idx: int,
                        prev_signal_bars: dict) -> Position | None:
    """
    Wedge/Climax reversal: wedge pattern + reversal signal + overshoot.
    Countertrend — only when trend health is late/complete.
    """
    trend_health = analysis.get('trend_health', {})
    health_stage = trend_health.get('stage', '')
    if health_stage not in ('late_stage', 'transition_complete'):
        return None

    sigs = _has_reversal_signal(analysis)
    if not sigs:
        return None

    patterns = analysis.get('analysis', {}).get('daily', {}).get('patterns', {})
    trend_dir = analysis.get('context', {}).get('trend', '')
    bull = 'bull' in trend_dir
    price = analysis.get('context', {}).get('price', 0)
    conv = analysis.get('conviction_objective', {}).get('subtotal', 0)

    day_type = analysis.get('day_type', {}).get('hypothesis', '')

    # LONG reversal (bear trend climax with wedge bottom)
    if not bull and patterns.get('wedge_bottom'):
        if conv >= 1 and _min_rr_check(last_bar.get('low', 0) * 0.98, price + (atr * 2), price, 'LONG'):
            last_sig = prev_signal_bars.get('WEDGE_L', -999)
            if bar_idx - last_sig >= 10:
                stop, target = _get_stop_target(last_bar, 'LONG', atr)
                return Position(0, last_bar.get('date', ''), price, 'LONG',
                                'WEDGE_L', conv, stop, target)

    # SHORT reversal (bull trend climax with wedge top)
    if bull and patterns.get('wedge_top'):
        if conv >= 1 and _min_rr_check(price, price - (atr * 2), price, 'SHORT'):
            last_sig = prev_signal_bars.get('WEDGE_S', -999)
            if bar_idx - last_sig >= 10:
                stop, target = _get_stop_target(last_bar, 'SHORT', atr)
                return Position(0, last_bar.get('date', ''), price, 'SHORT',
                                'WEDGE_S', conv, stop, target)

    return None


# ══════════════════════════════════════════════════════════════════════════════
# 5. MAIN BACKTEST LOOP
# ══════════════════════════════════════════════════════════════════════════════

def rule_trend_pullback(analysis: dict, bar_cls: dict, last_bar: dict,
                       atr: float, bars: list = None) -> Position | None:
    """
    Simple trend pullback: Buy bullish bar when price is above EMA in uptrend.
    Doesn't rely on Tier-1 pullback detection. Simpler, more aggressive.
    """
    trend_dir = analysis.get('context', {}).get('trend', '')
    price = analysis.get('context', {}).get('price', 0)
    ema20 = analysis.get('context', {}).get('ema20', 0)
    conv = analysis.get('conviction_objective', {}).get('subtotal', 0)
    
    # Only in clear uptrend
    if trend_dir != 'bull_trend':
        return None
    
    # Price must be above EMA
    if not ema20 or price <= ema20:
        return None
    
    # Current bar must be bullish (trend_bull or reversal_bull with decent body)
    bar_type = bar_cls.get('bar_type', '')
    body_pct = bar_cls.get('body_pct', 0)
    is_bullish_bar = ('trend_bull' in bar_type or 'reversal_bull' in bar_type) and body_pct >= 50
    
    if not is_bullish_bar:
        return None
    
    # Price should be above previous close (confirming uptrend resumption)
    if bars and len(bars) > 1:
        prev_bar = bars[-2]
        prev_close = prev_bar.get('close', 0)
        if price <= prev_close:
            return None
    
    # Don't enter if price is too far above EMA (> 8% above)
    if ema20 and (price - ema20) / ema20 > 0.08:
        return None
    
    # Minimum conviction
    if conv < 1:
        return None
    
    stop, target = _get_stop_target(last_bar, 'LONG', atr)
    if not _min_rr_check(stop, target, price, 'LONG'):
        return None
    
    return Position(
        entry_bar=0,
        entry_date=last_bar.get('date', ''),
        entry_price=price,
        direction='LONG',
        setup_type='TREND_L',
        conviction=conv,
        stop_loss=stop,
        target=target,
    )


def rule_breakout_entry(analysis: dict, bar_cls: dict, last_bar: dict,
                        atr: float) -> Position | None:
    """
    Breakout Entry: Aggressive entry ON the spike bar (not waiting for pullback).
    Best R:R but higher risk. Use smaller position size.
    """
    day_type = analysis.get('day_type', {}).get('hypothesis', '')
    trend_health = analysis.get('trend_health', {})
    health_stage = trend_health.get('stage', '')
    trend_dir = analysis.get('context', {}).get('trend', '')
    bull = 'bull' in trend_dir
    bear = 'bear' in trend_dir
    price = analysis.get('context', {}).get('price', 0)
    conv = analysis.get('conviction_objective', {}).get('subtotal', 0)

    # Allow in strong/tfo trends, or ambiguous with clear trend
    if day_type in ('strong_bull', 'strong_bear', 'tfo_bull', 'tfo_bear'):
        conv_threshold = 1
    elif day_type == 'ambiguous' and trend_dir in ('bull_trend', 'bear_trend'):
        conv_threshold = 1  # Same threshold for ambiguous
    else:
        return None

    if health_stage in ('late_stage', 'transition_complete', 'insufficient_data'):
        return None

    patterns = analysis.get('analysis', {}).get('daily', {}).get('patterns', {})
    if patterns is None:
        patterns = {}

    # Check for spike pattern
    spike_detected = (patterns.get('spike_bull') or patterns.get('spike_bear'))
    if not spike_detected:
        return None

    # Check spike bar characteristics
    bar_body = bar_cls.get('body_pct', 0)
    bar_range_pct = bar_cls.get('range_pct', 0)

    if bar_body < 60:  # Strong trend bar
        return None

    # Check if range is > 1.5× ATR (large move)
    bar_range = last_bar.get('high', 0) - last_bar.get('low', 0)
    if atr and bar_range < (atr * 1.5):
        return None

    if conv < conv_threshold:
        return None

    # LONG: Buy on spike bull bar
    if bull and patterns.get('spike_bull'):
        stop = last_bar.get('low', 0) - (atr * 0.3)  # Tight stop
        target = price + (atr * 2.0)  # Aggressive target
        if not _min_rr_check(stop, target, price, 'LONG'):
            return None
        return Position(0, last_bar.get('date', ''), price, 'LONG',
                        'BO_LONG', conv, stop, target)

    # SHORT: Sell on spike bear bar
    if bear and patterns.get('spike_bear'):
        stop = last_bar.get('high', 0) + (atr * 0.3)  # Tight stop
        target = price - (atr * 2.0)  # Aggressive target
        if not _min_rr_check(stop, target, price, 'SHORT'):
            return None
        return Position(0, last_bar.get('date', ''), price, 'SHORT',
                        'BO_SHORT', conv, stop, target)

    return None


def rule_climax_reversal(analysis: dict, bar_cls: dict, last_bar: dict,
                         atr: float, bar_idx: int,
                         prev_signal_bars: dict) -> Position | None:
    """
    Climax Reversal: Fade exhaustion after 2+ consecutive strong trend bars.
    Different from wedge reversal — this is about exhaustion, not pattern.
    """
    trend_health = analysis.get('trend_health', {})
    health_stage = trend_health.get('stage', '')
    if health_stage not in ('early_weakening', 'late_stage', 'transition_complete'):
        return None

    trend_dir = analysis.get('context', {}).get('trend', '')
    bull = 'bull' in trend_dir
    bear = 'bear' in trend_dir
    price = analysis.get('context', {}).get('price', 0)
    conv = analysis.get('conviction_objective', {}).get('subtotal', 0)

    # Check for exhaustion signs in recent bars
    daily_analysis = analysis.get('analysis', {}).get('daily', {})
    last_10 = daily_analysis.get('last_10_bars_classified', [])
    if not last_10:
        return None

    # Count consecutive strong trend bars
    consecutive_bull = 0
    consecutive_bear = 0
    for bar in reversed(last_10):
        bar_type = bar.get('bar_type', '')
        body_pct = bar.get('body_pct', 0)
        if 'trend_bull' in bar_type and body_pct >= 60:
            consecutive_bull += 1
        elif 'trend_bear' in bar_type and body_pct >= 60:
            consecutive_bear += 1
        else:
            break

    # Check for climax bars (body ≥80%)
    has_climax = any(
        'trend' in bar.get('bar_type', '') and bar.get('body_pct', 0) >= 80
        for bar in last_10[-3:]
    )

    # Check for expansion (range >1.8× average)
    has_expansion = False
    if last_10:
        ranges = [b.get('high', 0) - b.get('low', 0) for b in last_10[-5:]]
        avg_range = sum(ranges) / len(ranges) if ranges else 0
        last_range = last_10[-1].get('high', 0) - last_10[-1].get('low', 0)
        if avg_range and last_range > (avg_range * 1.8):
            has_expansion = True

    # Need at least 2 consecutive strong bars OR climax OR expansion
    if consecutive_bull < 2 and consecutive_bear < 2 and not has_climax and not has_expansion:
        return None

    # Check for reversal bar
    if not (_bar_is_reversal(bar_cls, 'LONG') or _bar_is_reversal(bar_cls, 'SHORT')):
        return None

    if conv < 1:
        return None

    # LONG: After bear climax
    if consecutive_bear >= 2 and _bar_is_reversal(bar_cls, 'LONG'):
        stop = last_bar.get('low', 0) - (atr * 0.3)
        target = price + (atr * 1.5)  # Quick scalp
        if not _min_rr_check(stop, target, price, 'LONG'):
            return None
        last_sig = prev_signal_bars.get('CLIMAX_L', -999)
        if bar_idx - last_sig >= 5:
            return Position(0, last_bar.get('date', ''), price, 'LONG',
                            'CLIMAX_L', conv, stop, target)

    # SHORT: After bull climax
    if consecutive_bull >= 2 and _bar_is_reversal(bar_cls, 'SHORT'):
        stop = last_bar.get('high', 0) + (atr * 0.3)
        target = price - (atr * 1.5)  # Quick scalp
        if not _min_rr_check(stop, target, price, 'SHORT'):
            return None
        last_sig = prev_signal_bars.get('CLIMAX_S', -999)
        if bar_idx - last_sig >= 5:
            return Position(0, last_bar.get('date', ''), price, 'SHORT',
                            'CLIMAX_S', conv, stop, target)

    return None


def rule_20_gap_bar(analysis: dict, bar_cls: dict, last_bar: dict,
                    atr: float) -> Position | None:
    """
    20 Gap Bar Touch: First MA touch after 20+ bars away from MA.
    High-probability exhaustion entry.
    """
    day_type = analysis.get('day_type', {}).get('hypothesis', '')
    if day_type not in ('strong_bull', 'strong_bear', 'tfo_bull', 'tfo_bear'):
        return None

    trend_dir = analysis.get('context', {}).get('trend', '')
    bull = 'bull' in trend_dir
    bear = 'bear' in trend_dir
    price = analysis.get('context', {}).get('price', 0)
    conv = analysis.get('conviction_objective', {}).get('subtotal', 0)

    # Check if we have gap_bar_count in pullbacks
    pb = analysis.get('pullbacks', {})
    sb = pb.get('structure_based', {})
    cl = sb.get('current_leg', {})
    gap_bar_count = cl.get('gap_bar_count', 0)

    if gap_bar_count < 20:
        return None

    # Check if price just touched MA (proximity)
    ema_prox = cl.get('ema_proximity', 'unknown')
    if ema_prox not in ('at_ema', 'near_ema'):
        return None

    if conv < 1:
        return None

    # LONG: Bull trend, price touches MA from above
    if bull:
        stop = last_bar.get('low', 0) - (atr * 0.3)
        target = price + (atr * 2.0)
        if not _min_rr_check(stop, target, price, 'LONG'):
            return None
        return Position(0, last_bar.get('date', ''), price, 'LONG',
                        'GAP20_L', conv, stop, target)

    # SHORT: Bear trend, price touches MA from below
    if bear:
        stop = last_bar.get('high', 0) + (atr * 0.3)
        target = price - (atr * 2.0)
        if not _min_rr_check(stop, target, price, 'SHORT'):
            return None
        return Position(0, last_bar.get('date', ''), price, 'SHORT',
                        'GAP20_S', conv, stop, target)

    return None


def run_backtest(ticker: str, daily_bars: list, classified: list,
                 start_bar: int = MIN_BARS) -> dict:
    """Run the sliding-window backtest over all bars."""
    n = len(daily_bars)
    position: Position | None = None
    trades: list[Trade] = []
    prev_pb_count: str | None = None
    prev_ema_prox: str | None = None
    prev_signal_bars: dict = {}
    bars = daily_bars  # Reference to daily_bars for passing to rules

    print(f"[backtest] Running {n - start_bar} windows from bar {start_bar} to {n-1}...",
          file=sys.stderr)

    for i in range(start_bar, n):
        window_data = build_window_data(ticker, daily_bars, classified, i)
        analysis = brooks_analyze(window_data)

        last_bar = daily_bars[i]
        bar_cls = classified[i]

        # Extract vars for decision layer
        atr = analysis.get('context', {}).get('atr', 0)
        price = analysis.get('context', {}).get('price', 0)

        # ── If in position, check exits ──────────────────────────────
        if position is not None:
            position.bars_held += 1
            direction = position.direction

            # 1. Stop loss
            if direction == 'LONG' and last_bar['low'] <= position.stop_loss:
                exit_price = max(position.stop_loss, last_bar['low'])
                position, completed = None, Trade(position, i, last_bar['date'],
                                                  exit_price, 'stop_loss')
                trades.append(completed)
                continue
            if direction == 'SHORT' and last_bar['high'] >= position.stop_loss:
                exit_price = min(position.stop_loss, last_bar['high'])
                position, completed = None, Trade(position, i, last_bar['date'],
                                                  exit_price, 'stop_loss')
                trades.append(completed)
                continue

            # 2. Target hit
            if direction == 'LONG' and last_bar['high'] >= position.target:
                exit_price = max(position.target, last_bar['close'])
                position, completed = None, Trade(position, i, last_bar['date'],
                                                  exit_price, 'target_hit')
                trades.append(completed)
                continue
            if direction == 'SHORT' and last_bar['low'] <= position.target:
                exit_price = min(position.target, last_bar['close'])
                position, completed = None, Trade(position, i, last_bar['date'],
                                                  exit_price, 'target_hit')
                trades.append(completed)
                continue

            # 3. Time stop
            if position.bars_held >= MAX_HOLD:
                position, completed = None, Trade(position, i, last_bar['date'],
                                                  last_bar['close'], 'time_stop')
                trades.append(completed)
                continue

            # 4. Trend flip
            trend_dir = analysis.get('context', {}).get('trend', '')
            health_stage = analysis.get('trend_health', {}).get('stage', '')
            if health_stage in ('late_stage', 'transition_complete'):
                if direction == 'LONG' and 'bear' in trend_dir:
                    position, completed = None, Trade(position, i, last_bar['date'],
                                                      last_bar['close'], 'trend_flip')
                    trades.append(completed)
                    continue
                if direction == 'SHORT' and 'bull' in trend_dir:
                    position, completed = None, Trade(position, i, last_bar['date'],
                                                      last_bar['close'], 'trend_flip')
                    trades.append(completed)
                    continue

            # Still in position
            pb = analysis.get('pullbacks', {})
            sb = pb.get('structure_based', {})
            cl = sb.get('current_leg', {})
            current_pb = cl.get('pullback_count', 'unknown')
            if current_pb != 'unknown':
                prev_pb_count = current_pb
            continue

        # ── Not in position — evaluate entries in priority order ────
        if i < MIN_BARS:
            pb = analysis.get('pullbacks', {})
            sb = pb.get('structure_based', {})
            cl = sb.get('current_leg', {})
            current_pb = cl.get('pullback_count', 'unknown')
            if current_pb != 'unknown':
                prev_pb_count = current_pb
            continue

        new_pos = None

        # Priority 1: M2B/M2S (highest probability)
        new_pos = rule_m2b_m2s(analysis, bar_cls, last_bar, atr, prev_pb_count, prev_ema_prox, bars)

        # Priority 2: Breakout pullback (first pullback after spike)
        if new_pos is None:
            new_pos = rule_trend_breakout(analysis, bar_cls, last_bar, atr)

        # Priority 3: Simple trend pullback (price above EMA + bullish bar)
        if new_pos is None:
            new_pos = rule_trend_pullback(analysis, bar_cls, last_bar, atr, bars)

        # Priority 4: Breakout entry (aggressive, on spike bar)
        if new_pos is None:
            new_pos = rule_breakout_entry(analysis, bar_cls, last_bar, atr)

        # Priority 4: Range edge reversal (trading range)
        if new_pos is None:
            new_pos = rule_range_fade(analysis, bar_cls, last_bar, atr,
                                      prev_signal_bars, i)

        # Priority 5: Failed breakout (trading range)
        # (rule_range_fade already handles FBO via reversal bar check)

        # Priority 6: Wedge reversal (countertrend, late stage)
        if new_pos is None:
            new_pos = rule_wedge_reversal(analysis, bar_cls, last_bar, atr,
                                          i, prev_signal_bars)

        # Priority 7: Climax reversal (exhaustion fade)
        if new_pos is None:
            new_pos = rule_climax_reversal(analysis, bar_cls, last_bar, atr,
                                           i, prev_signal_bars)

        # Priority 8: 20 gap bar touch (first MA touch after extended gap)
        if new_pos is None:
            new_pos = rule_20_gap_bar(analysis, bar_cls, last_bar, atr)

        if new_pos is not None:
            new_pos.entry_bar = i
            prev_signal_bars[new_pos.setup_type] = i

        position = new_pos

        # Track pullback count and EMA proximity
        pb = analysis.get('pullbacks', {})
        sb = pb.get('structure_based', {})
        cl = sb.get('current_leg', {})
        current_pb = cl.get('pullback_count', 'unknown')
        current_ema = cl.get('ema_proximity', 'unknown')
        if current_pb != 'unknown':
            prev_pb_count = current_pb
        if current_ema != 'unknown':
            prev_ema_prox = current_ema

    # Close open position at end of data
    if position is not None:
        last_bar = daily_bars[-1]
        trades.append(Trade(
            position, n - 1, last_bar['date'],
            last_bar['close'], 'end_of_data'
        ))

    # ── Compute statistics ─────────────────────────────────────────────
    total = len(trades)
    winners = [t for t in trades if t.pnl_pct > 0]
    losers  = [t for t in trades if t.pnl_pct <= 0]
    win_count = len(winners)
    loss_count = len(losers)
    win_rate = win_count / total * 100 if total > 0 else 0

    avg_win = sum(t.pnl_pct for t in winners) / win_count if win_count else 0
    avg_loss = sum(t.pnl_pct for t in losers) / loss_count if loss_count else 0

    # Proper account compounding for return + max drawdown
    account = 100.0
    peak_account = 100.0
    max_dd_pct = 0.0
    total_return = 0.0
    for t in trades:
        account *= (1.0 + t.pnl_pct / 100.0)
        if account > peak_account:
            peak_account = account
        dd_from_peak = (peak_account - account) / peak_account * 100.0
        if dd_from_peak > max_dd_pct:
            max_dd_pct = dd_from_peak
    total_return = account - 100.0

    # Profit factor
    gross_win = sum(t.pnl_pct for t in winners)
    gross_loss = abs(sum(t.pnl_pct for t in losers))
    profit_factor = gross_win / gross_loss if gross_loss > 0 else float('inf')

    # By setup
    by_setup = defaultdict(lambda: {'wins': 0, 'losses': 0, 'total_pnl': 0.0})
    for t in trades:
        s = t.setup_type
        by_setup[s]['total_pnl'] += t.pnl_pct
        if t.pnl_pct > 0:
            by_setup[s]['wins'] += 1
        else:
            by_setup[s]['losses'] += 1

    # By month
    by_month = defaultdict(lambda: {'trades': 0, 'wins': 0, 'pnl': 0.0})
    for t in trades:
        month = t.entry_date[:7] if t.entry_date else 'unknown'
        by_month[month]['trades'] += 1
        by_month[month]['pnl'] += t.pnl_pct
        if t.pnl_pct > 0:
            by_month[month]['wins'] += 1

    return {
        'ticker': ticker,
        'period': {
            'start': daily_bars[start_bar]['date'] if start_bar < len(daily_bars) else '',
            'end': daily_bars[-1]['date'] if daily_bars else '',
            'bars_analyzed': n - start_bar,
            'total_bars': n,
        },
        'summary': {
            'total_trades': total,
            'win_count': win_count,
            'loss_count': loss_count,
            'win_rate_pct': round(win_rate, 1),
            'avg_win_pct': round(avg_win, 2),
            'avg_loss_pct': round(avg_loss, 2),
            'total_return_pct': round(total_return, 2),
            'profit_factor': round(profit_factor, 2) if profit_factor != float('inf') else 'inf',
            'max_drawdown_pct': round(max_dd_pct, 2),
            'avg_bars_held': round(sum(t.bars_held for t in trades) / total, 1) if total else 0,
            'avg_conviction': round(sum(t.conviction for t in trades) / total, 1) if total else 0,
        },
        'by_setup': dict(by_setup),
        'by_month': dict(by_month),
        'trades': [
            {
                'entry_bar': t.entry_bar,
                'entry_date': t.entry_date,
                'entry_price': t.entry_price,
                'direction': t.direction,
                'setup_type': t.setup_type,
                'conviction': t.conviction,
                'exit_bar': t.exit_bar,
                'exit_date': t.exit_date,
                'exit_price': t.exit_price,
                'exit_reason': t.exit_reason,
                'pnl_pct': t.pnl_pct,
                'bars_held': t.bars_held,
            }
            for t in trades
        ],
    }


# ══════════════════════════════════════════════════════════════════════════════
# 6. OUTPUT
# ══════════════════════════════════════════════════════════════════════════════

def print_results(results: dict, show_trades: bool = True):
    s = results['summary']
    period = results['period']
    ticker = results['ticker']
    trades = results['trades']
    bar = chr(0x2550) * 60

    print(f"\n{bar}")
    print(f"  BACKTEST: {ticker}")
    print(f"  Period:   {period['start']} -> {period['end']}  ({period['bars_analyzed']} bars)")
    print(f"{bar}")

    if show_trades and trades:
        print(f"\n  TRADE JOURNAL ({len(trades)} trades):")
        print(f"  {'#':>3} {'Date':<12} {'Setup':<8} {'Dir':<6} {'Entry':>8} "
              f"{'Exit':>8} {'PnL%':>7} {'Bars':>4} {'Reason'}")
        print(f"  {'-'*60}")
        for idx, t in enumerate(trades, 1):
            pnl_str = f"{t['pnl_pct']:+.2f}%"
            print(f"  {idx:>3} {t['entry_date']:<12} {t['setup_type']:<8} "
                  f"{t['direction']:<6} {t['entry_price']:>8.2f} "
                  f"{t['exit_price']:>8.2f} {pnl_str:>7} "
                  f"{t['bars_held']:>4} {t['exit_reason']}")

    print(f"\n{bar}")
    print(f"  SUMMARY")
    print(f"{bar}")
    print(f"  Total trades:     {s['total_trades']}")
    print(f"  Win rate:         {s['win_rate_pct']}%  ({s['win_count']}W / {s['loss_count']}L)")
    print(f"  Avg win:          {s['avg_win_pct']:+.2f}%")
    print(f"  Avg loss:         {s['avg_loss_pct']:+.2f}%")
    print(f"  Total return:     {s['total_return_pct']:+.2f}%")
    print(f"  Profit factor:    {s['profit_factor']}")
    print(f"  Max drawdown:     {s['max_drawdown_pct']:.2f}%")
    print(f"  Avg bars held:    {s['avg_bars_held']}")
    print(f"  Avg conviction:   {s['avg_conviction']}")

    if results.get('by_setup'):
        print(f"\n{bar}")
        print(f"  BY SETUP TYPE")
        print(f"{bar}")
        for setup, data in sorted(results['by_setup'].items()):
            wt = data['wins']
            lt = data['losses']
            tt = wt + lt
            wr = wt / tt * 100 if tt else 0
            print(f"  {setup:<8}  {tt:>2} trades  {wr:5.1f}% WR  "
                  f"PnL: {data['total_pnl']:+.2f}%  ({wt}W / {lt}L)")

    if results.get('by_month'):
        print(f"\n{bar}")
        print(f"  MONTHLY BREAKDOWN")
        print(f"{bar}")
        for month, data in sorted(results['by_month'].items()):
            print(f"  {month}  {data['trades']:>2} trades  "
                  f"{data['wins']:>2}W / {data['trades']-data['wins']:>2}L  "
                  f"PnL: {data['pnl']:+.2f}%")

    print(f"\n{bar}\n")


# ══════════════════════════════════════════════════════════════════════════════
# 7. CLI
# ══════════════════════════════════════════════════════════════════════════════

def main():
    import argparse
    parser = argparse.ArgumentParser(
        description='Al Brooks price action backtester (deterministic, no LLM)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument('ticker', nargs='?', help='Ticker symbol')
    parser.add_argument('--exchange', help='Exchange hint')
    parser.add_argument('--bars', type=int, default=DEFAULT_BARS,
                        help=f'Daily bars to fetch (default: {DEFAULT_BARS})')
    parser.add_argument('--start', type=int, default=MIN_BARS,
                        help=f'Start testing from this bar index (default: {MIN_BARS})')
    parser.add_argument('--show-trades', action='store_true', default=True,
                        help='Show trade journal')
    parser.add_argument('--json', help='Save results to this JSON path')
    parser.add_argument('--list-setups', action='store_true',
                        help='List supported entry setup types')

    args = parser.parse_args()

    if args.list_setups:
        print("""
SETUP TYPES (in priority order):

  M2B      — Standard Buy: L2 at EMA in bull trend (strong/tfo/TR-bottom)
  M2S      — Standard Sell: H2 at EMA in bear trend (strong/tfo/TR-top)
  TBO      — Trend Breakout Long: spike + L1 in strong bull trend
  TBS      — Trend Breakout Short: spike + H1 in strong bear trend
  BO_LONG  — Breakout Entry Long: aggressive entry ON spike bar
  BO_SHORT — Breakout Entry Short: aggressive entry ON spike bar
  RF_LONG  — Range Fade Long: reversal bar at TR bottom
  RF_SHORT — Range Fade Short: reversal bar at TR top
  WEDGE_L  — Wedge Reversal Long: wedge bottom in late-stage bear trend
  WEDGE_S  — Wedge Reversal Short: wedge top in late-stage bull trend
  CLIMAX_L — Climax Reversal Long: fade bear exhaustion
  CLIMAX_S — Climax Reversal Short: fade bull exhaustion
  GAP20_L  — 20 Gap Bar Long: first MA touch after 20+ bar gap
  GAP20_S  — 20 Gap Bar Short: first MA touch after 20+ bar gap

EXIT RULES (checked each bar in order):
  1. Stop loss (0.3x ATR beyond the signal bar extreme)
  2. Target hit (1.5-2.0x ATR from entry depending on setup)
  3. Time stop (10-25 bars max depending on setup)
  4. Trend flip (always-in direction reversed + late/complete health)
  5. End of data
""")
        return

    if not args.ticker:
        parser.print_help()
        sys.exit(1)

    hist = asyncio.run(fetch_historical_data(args.ticker, args.exchange, args.bars))
    if 'error' in hist:
        print(f"[error] {hist['error']}", file=sys.stderr)
        sys.exit(1)

    daily_bars = hist['daily_bars']
    classified = hist['classified']

    start = max(args.start, MIN_BARS)
    if start >= len(daily_bars):
        print(f"[error] start {start} >= bars {len(daily_bars)}", file=sys.stderr)
        sys.exit(1)

    results = run_backtest(args.ticker, daily_bars, classified, start)
    print_results(results, show_trades=args.show_trades)

    outname = f"{args.ticker.replace(':', '_').replace('.', '_')}_backtest.json"
    outpath = os.path.join(SKILL_DIR, outname)
    with open(outpath, 'w') as f:
        json.dump(results, f, indent=2, default=str)
    print(f"[saved: {outpath}]", file=sys.stderr)

    if args.json and args.json != outpath:
        with open(args.json, 'w') as f:
            json.dump(results, f, indent=2, default=str)
        print(f"[saved: {args.json}]", file=sys.stderr)


if __name__ == '__main__':
    main()
