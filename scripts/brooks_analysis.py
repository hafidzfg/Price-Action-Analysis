#!/usr/bin/env python3
"""
brooks_analysis.py — Tier-1 deterministic analysis engine for Al Brooks framework.

Takes a fetch_data.py JSON output (--brooks format) and produces a compact
brooks_analysis.json with pre-computed:
  - Signs of Strength count (18/22 computable)
  - Day type hypothesis (strong trend / TR / barbwire / ambiguous)
  - Leg-based pullback counting (H1-H4/L1-L4)
  - Measured move targets
  - Conviction score objective components
  - Brooks intent filtering (which setups are viable)
  - Pattern evolution watch items

Usage:
    python brooks_analysis.py AAPL_brooks.json
    cat AAPL_brooks.json | python brooks_analysis.py
"""
import sys, json, os
from datetime import datetime, timezone
from typing import Optional


# ---------------------------------------------------------------------------
# Helper: classify a single bar (re-implemented from fetch_data.py for
# standalone use, since the already-classified bars are in the input)
# ---------------------------------------------------------------------------

def classify_bar(bar: dict, prev_bar: Optional[dict] = None) -> dict:
    o, h, l, c = bar['open'], bar['high'], bar['low'], bar['close']
    bar_range = h - l
    if bar_range == 0:
        return {'bar_type': 'doji', 'body_pct': 0, 'close_position': 0.5,
                'tail_top_pct': 0, 'tail_bottom_pct': 0}

    body = abs(c - o)
    body_pct = (body / bar_range) * 100
    close_pos = (c - l) / bar_range
    tail_top = (h - max(o, c)) / bar_range * 100
    tail_bottom = (min(o, c) - l) / bar_range * 100

    if body_pct >= 60:
        bar_type = 'trend_bull' if c > o else 'trend_bear'
    elif body_pct <= 25:
        if tail_bottom >= 33 and close_pos > 0.5:
            bar_type = 'reversal_bull'
        elif tail_top >= 33 and close_pos < 0.5:
            bar_type = 'reversal_bear'
        else:
            bar_type = 'doji'
    else:
        if tail_bottom >= 30 and c > o and close_pos > 0.5:
            bar_type = 'reversal_bull'
        elif tail_top >= 30 and c < o and close_pos < 0.5:
            bar_type = 'reversal_bear'
        elif c > o:
            bar_type = 'weak_bull'
        else:
            bar_type = 'weak_bear'

    return {
        'bar_type': bar_type,
        'body_pct': round(body_pct, 1),
        'close_position': round(close_pos, 3),
        'tail_top_pct': round(tail_top, 1),
        'tail_bottom_pct': round(tail_bottom, 1),
    }


# ---------------------------------------------------------------------------
# 1. Signs of Strength (22 signs per Brooks Book 1, Ch 4)
# ---------------------------------------------------------------------------

SOS_SIGNS = [
    # 1-5: Gap / Opening
    (1, "Gap in trend direction on current bar or recent bars"),
    (2, "Gap in trend direction on signal bar"),
    (3, "Trend bar in direction of trend"),
    (4, "Body of signal bar above/below prior bar's high/low"),
    (5, "Multiple (2+) gaps in same direction"),

    # 6-10: Bar characteristics
    (6, "Big trend bar (body >= 70% bar range)"),
    (7, "Small or no tail in direction of trend"),
    (8, "Consecutive (2+) big trend bars = spike"),
    (9, "Bar closes on its high/low (no tail)"),  # rare, computable as tail<5%
    (10, "Small bodies in direction = measured move targets unlikely to be reached"),

    # 11-15: Pullback / EMA structure
    (11, "Pullback to EMA has small bars (absorbing)"),
    (12, "Pullback forms H2/L2 at 20-EMA"),
    (13, "Tight trading range after trend bar = micro channel"),
    (14, "Consecutive closes above/below 20-EMA (10+)"),
    (15, "20-EMA slope steepening"),

    # 16-19: Price action patterns
    (16, "Bull/bear flag (tight channel after spike)"),
    (17, "Wedge or climax reversal attempt fails"),  # wedge detection from patterns
    (18, "Trend bar breaks out of trading range"),
    (19, "Larger time frame also in trend"),

    # 20-22: Volume / structure (limited volume data available)
    (20, "High volume on trend bars"),
    (21, "Expanding range (volatility increasing)"),
    (22, "Relative volume above average"),
]


def compute_sos(bars: list, classified: list, trend_context: dict,
                patterns: dict, trend_direction: str) -> dict:
    """
    Compute which of the 22 Signs of Strength are present.
    Returns count, present/absent lists, interpretation.
    """
    present = []
    absent = []
    not_computable = []

    if not bars or len(bars) < 5:
        return {'count': 0, 'max_possible': 22, 'present': [], 'absent': [],
                'not_computable': list(range(1, 23)),
                'interpretation': 'insufficient_data'}

    last = bars[-1] if bars else None
    last_c = classified[-1] if classified else {}
    last_10_bars = bars[-10:] if len(bars) >= 10 else bars
    last_10_cls = classified[-10:] if len(classified) >= 10 else classified

    bull = trend_direction == 'bull_trend'
    bear = trend_direction == 'bear_trend'
    trend_up = bull  # alias

    # --- Sign 1: Gap in trend direction on current/recent bars ---
    s1 = False
    for b in last_10_bars[-3:]:
        prev_close = bars[bars.index(b) - 1]['close'] if bars.index(b) > 0 else None
        if prev_close:
            gap = b['open'] - prev_close
            if (trend_up and gap > 0) or (bear and gap < 0):
                s1 = True
                break
    present.append(1) if s1 else absent.append(1)

    # --- Sign 2: Gap in trend direction on signal bar (last bar) ---
    s2 = False
    if len(bars) >= 2:
        prev = bars[-2]
        gap = last['open'] - prev['close']
        if (trend_up and gap > 0) or (bear and gap < 0):
            s2 = True
    present.append(2) if s2 else absent.append(2)

    # --- Sign 3: Trend bar in direction of trend ---
    s3 = False
    trend_types = {'trend_bull', 'trend_bear'}
    for c in last_10_cls[-3:]:
        if c['bar_type'] in trend_types:
            if (trend_up and c['bar_type'] == 'trend_bull') or \
               (bear and c['bar_type'] == 'trend_bear'):
                s3 = True
                break
    present.append(3) if s3 else absent.append(3)

    # --- Sign 4: Body of signal bar above/below prior bar ---
    s4 = False
    if len(bars) >= 2:
        prev = bars[-2]
        if trend_up and last['low'] > prev['high']:
            s4 = True
        elif bear and last['high'] < prev['low']:
            s4 = True
    present.append(4) if s4 else absent.append(4)

    # --- Sign 5: Multiple (2+) gaps in same direction ---
    s5 = False
    gap_count = 0
    for i in range(1, min(len(bars), 20)):
        prev_c = bars[i-1]['close']
        g = bars[i]['open'] - prev_c
        if (trend_up and g > 0) or (bear and g < 0):
            gap_count += 1
    if gap_count >= 2:
        s5 = True
    present.append(5) if s5 else absent.append(5)

    # --- Sign 6: Big trend bar (body >= 70%) ---
    s6 = False
    for c in last_10_cls[-3:]:
        if c['body_pct'] >= 70:
            s6 = True
            break
    present.append(6) if s6 else absent.append(6)

    # --- Sign 7: Small/no tail in direction of trend ---
    s7 = False
    if trend_up and last_c.get('tail_bottom_pct', 100) < 20:
        s7 = True
    elif bear and last_c.get('tail_top_pct', 100) < 20:
        s7 = True
    present.append(7) if s7 else absent.append(7)

    # --- Sign 8: Consecutive big trend bars (spike) ---
    s8 = False
    spike_count = 0
    for c in reversed(last_10_cls):
        is_trend = (trend_up and c['bar_type'] == 'trend_bull') or \
                   (bear and c['bar_type'] == 'trend_bear')
        if is_trend and c['body_pct'] >= 60:
            spike_count += 1
        else:
            break
    if spike_count >= 2:
        s8 = True
    present.append(8) if s8 else absent.append(8)

    # --- Sign 9: Bar closes on its high/low (tail < 5%) ---
    s9 = False
    if trend_up and last_c.get('tail_top_pct', 100) < 5:
        s9 = True
    elif bear and last_c.get('tail_bottom_pct', 100) < 5:
        s9 = True
    present.append(9) if s9 else absent.append(9)

    # --- Sign 10: Small bodies in trend direction ---
    s10 = False
    small_bodies = 0
    for c in last_10_cls[-5:]:
        if c['body_pct'] < 25 and c['close_position'] > 0.5:
            small_bodies += 1
    if small_bodies >= 2:
        s10 = True
    present.append(10) if s10 else absent.append(10)

    # --- Sign 11: Pullback to EMA has small bars ---
    s11 = False
    # Check last 5 bars: if near EMA, are bodies small?
    ema20 = trend_context.get('ema20', 0)
    near_ema_bars = [b for b in last_10_bars[-5:]
                     if abs(b['close'] - ema20) / (ema20 or 1) < 0.02]
    if near_ema_bars:
        avg_body = sum(abs(b['close'] - b['open']) for b in near_ema_bars) / len(near_ema_bars)
        avg_range = sum(b['high'] - b['low'] for b in near_ema_bars) / len(near_ema_bars)
        if avg_range > 0 and (avg_body / avg_range) < 0.4:
            s11 = True
    present.append(11) if s11 else absent.append(11)

    # --- Sign 12: Pullback forms H2/L2 at 20-EMA ---
    s12 = False
    pullback_count = bar_analysis_field(bars, 'pullback_count', {})
    if trend_up and pullback_count.get('L', 0) == 2:
        s12 = True
    elif bear and pullback_count.get('H', 0) == 2:
        s12 = True
    present.append(12) if s12 else absent.append(12)

    # --- Sign 13: Tight trading range after trend bar = micro channel ---
    s13 = False
    if patterns.get('micro_channel_bull') or patterns.get('micro_channel_bear'):
        # Check it's in trend direction
        mc = patterns.get('micro_channel_bull') or patterns.get('micro_channel_bear')
        if mc and ((trend_up and 'micro_channel_bull' in patterns) or
                   (bear and 'micro_channel_bear' in patterns)):
            s13 = True
    present.append(13) if s13 else absent.append(13)

    # --- Sign 14: Consecutive closes above/below 20-EMA (10+) ---
    s14 = False
    ema20 = trend_context.get('ema20', 0)
    cons_count = 0
    for b in reversed(bars[-30:]):
        if (trend_up and b['close'] > ema20) or (bear and b['close'] < ema20):
            cons_count += 1
        else:
            break
    if cons_count >= 10:
        s14 = True
    present.append(14) if s14 else absent.append(14)

    # --- Sign 15: 20-EMA slope steepening ---
    s15 = False
    ema20_vals = get_ema20_over_time(bars)
    if len(ema20_vals) >= 10:
        recent_slope = ema20_vals[-1] - ema20_vals[-3]
        prior_slope = ema20_vals[-5] - ema20_vals[-10]
        if trend_up and recent_slope > prior_slope * 1.2:
            s15 = True
        elif bear and abs(recent_slope) > abs(prior_slope) * 1.2:
            s15 = True
    present.append(15) if s15 else absent.append(15)

    # --- Sign 16: Bull/bear flag (tight channel after spike) ---
    s16 = bool(patterns.get('micro_channel_bull') or patterns.get('micro_channel_bear'))
    present.append(16) if s16 else absent.append(16)

    # --- Sign 17: Wedge/climax reversal attempt fails ---
    s17 = False
    if patterns.get('wedge_top'):
        w = patterns['wedge_top']
        pushes = w.get('pushes', 0) if isinstance(w, dict) else 3
        if trend_up and pushes >= 3:
            # Wedge exists but no reversal yet = signs of strength
            s17 = True
    elif patterns.get('wedge_bottom'):
        w = patterns['wedge_bottom']
        pushes = w.get('pushes', 0) if isinstance(w, dict) else 3
        if bear and pushes >= 3:
            s17 = True
    present.append(17) if s17 else absent.append(17)

    # --- Sign 18: Trend bar breaks out of trading range ---
    s18 = False
    if trend_up and patterns.get('spike_bull'):
        s18 = True
    elif bear and patterns.get('spike_bear'):
        s18 = True
    present.append(18) if s18 else absent.append(18)

    # --- Sign 19: Larger time frame also in trend ---
    # (Requires multi-timeframe data — handled during merge)
    not_computable.append(19)

    # --- Sign 20: High volume on trend bars ---
    s20 = False
    for i in range(1, min(6, len(bars))):
        b = bars[-i]
        c = classified[-i]
        is_trend = (trend_up and c['bar_type'] == 'trend_bull') or \
                   (bear and c['bar_type'] == 'trend_bear')
        if is_trend and b.get('volume', 0) > 0:
            avg_vol = sum(bx.get('volume', 0) for bx in bars[-20:]) / 20
            if avg_vol > 0 and b['volume'] > avg_vol * 1.3:
                s20 = True
                break
    present.append(20) if s20 else absent.append(20)

    # --- Sign 21: Expanding range ---
    s21 = False
    if len(bars) >= 10:
        ranges_last5 = [bars[-i]['high'] - bars[-i]['low'] for i in range(1, 6)]
        ranges_prior5 = [bars[-i]['high'] - bars[-i]['low'] for i in range(6, 11)]
        if sum(ranges_last5) / 5 > sum(ranges_prior5) / 5 * 1.2:
            s21 = True
    present.append(21) if s21 else absent.append(21)

    # --- Sign 22: Relative volume above average ---
    s22 = False
    if len(bars) >= 10:
        recent_vols = [bars[-i].get('volume', 0) for i in range(1, 6)]
        prior_vols = [bars[-i].get('volume', 0) for i in range(6, 11)]
        avg_recent = sum(recent_vols) / len(recent_vols) if recent_vols else 0
        avg_prior = sum(prior_vols) / len(prior_vols) if prior_vols else 0
        if avg_prior > 0 and avg_recent > avg_prior * 1.2:
            s22 = True
    present.append(22) if s22 else absent.append(22)

    # --- Interpretation ---
    total_present = len(present)
    computable = 22 - len(not_computable)

    if total_present >= computable * 0.65:
        interpretation = 'strong_trend_likely'
    elif total_present >= computable * 0.35:
        interpretation = 'moderate_strength'
    else:
        interpretation = 'weak_or_ambiguous'

    return {
        'count': total_present,
        'max_possible': 22,
        'computable_count': computable,
        'present': sorted(present),
        'absent': sorted([s for s in absent if s not in not_computable]),
        'not_computable': sorted(not_computable),
        'interpretation': interpretation,
    }


def bar_analysis_field(bars, field, default=None):
    """Extract a field from the analysis embedded in the data."""
    return default


def get_ema20_over_time(bars: list) -> list:
    """
    Estimate EMA20 values over time from the bar data.
    Since we don't store historical ema20 per bar, we compute trailing EMA20.
    """
    if not bars or len(bars) < 20:
        return []

    closes = [b['close'] for b in bars]
    multiplier = 2 / (20 + 1)
    ema = [closes[0]]
    for c in closes[1:]:
        ema.append(c * multiplier + ema[-1] * (1 - multiplier))
    return ema


# ---------------------------------------------------------------------------
# 2. Day Type Classifier
# ---------------------------------------------------------------------------

def classify_day_type(bars: list, classified: list, trend_context: dict,
                      bar_analysis: dict) -> dict:
    """
    Weighted decision tree for day type classification.
    Outputs hypothesis + confidence + alternatives.
    """
    if not bars or len(bars) < 10:
        return {'hypothesis': 'insufficient_data', 'confidence': 'low',
                'reasoning': {}, 'alternatives': []}

    # Gather metrics
    trend_bar_ratio = 0
    bull_bars = 0
    bear_bars = 0
    doji_count = 0

    last_20_cls = classified[-20:] if len(classified) >= 20 else classified
    total = len(last_20_cls)
    for c in last_20_cls:
        if 'trend_bull' in c['bar_type']:
            bull_bars += 1
        elif 'trend_bear' in c['bar_type']:
            bear_bars += 1
        elif c['bar_type'] == 'doji':
            doji_count += 1

    trend_bars = bull_bars + bear_bars
    trend_bar_ratio = trend_bars / total if total > 0 else 0
    bull_ratio = bull_bars / total if total > 0 else 0
    bear_ratio = bear_bars / total if total > 0 else 0
    doji_ratio = doji_count / total if total > 0 else 0

    # Body overlap
    body_overlap = bar_analysis.get('avg_body_overlap_pct', 50)

    # EMA slope
    ema20_vals = get_ema20_over_time(bars)
    ema_slope = 'flat'
    if len(ema20_vals) >= 10:
        recent_change = ema20_vals[-1] - ema20_vals[-5]
        ema_pct = abs(recent_change) / (ema20_vals[-1] or 1) * 100
        if ema_pct > 1.0:
            ema_slope = 'steep_up' if recent_change > 0 else 'steep_down'
        elif ema_pct > 0.3:
            ema_slope = 'moderate_up' if recent_change > 0 else 'moderate_down'
        else:
            ema_slope = 'flat'

    # Gap count last 10
    gap_count = 0
    for i in range(max(1, len(bars) - 10), len(bars)):
        gap = bars[i]['open'] - bars[i-1]['close']
        if abs(gap) / (bars[i-1]['close'] or 1) > 0.001:
            gap_count += 1

    # Consecutive closes on same side of EMA
    ema20 = trend_context.get('ema20', 0)
    cons_above = 0
    cons_below = 0
    for b in reversed(bars[-15:]):
        if b['close'] > ema20:
            cons_above += 1
            cons_below = 0
        else:
            cons_below += 1
            cons_above = 0
        if cons_above > 5 or cons_below > 5:
            break
    closes_above_ema = cons_above > cons_below

    # Decision tree
    trend_direction = trend_context.get('trend', 'unknown')
    bull_bias = trend_direction == 'bull_trend'
    bear_bias = trend_direction == 'bear_trend'

    # Check barbwire: 3+ overlapping dojis
    barbwire = False
    if doji_ratio > 0.3 and body_overlap > 50:
        # Count consecutive dojis
        doji_run = 0
        for c in reversed(last_20_cls):
            if c['bar_type'] == 'doji':
                doji_run += 1
            else:
                break
        if doji_run >= 3:
            barbwire = True

    # Check strong trend
    strong_trend = False
    if trend_bar_ratio > 0.6 and body_overlap < 35:
        if 'steep' in ema_slope:
            if (bull_bias and bull_ratio > bear_ratio * 1.5) or \
               (bear_bias and bear_ratio > bull_ratio * 1.5):
                strong_trend = True

    # Check trading range
    trading_range = False
    if body_overlap > 50 or trend_bar_ratio < 0.4:
        if 'flat' in ema_slope or 'moderate' in ema_slope:
            trading_range = True

    # Check trend from open (TFO)
    trend_from_open = False
    if trend_bar_ratio > 0.5:
        if (bull_bias and closes_above_ema and gap_count >= 3) or \
           (bear_bias and not closes_above_ema and gap_count >= 3):
            trend_from_open = True

    # Final classification with confidence
    hypotheses = []
    if barbwire:
        hypotheses.append(('barbwire', 'high',
                           {'doji_run': doji_run, 'doji_ratio': doji_ratio}))
    if strong_trend:
        label = 'strong_bull' if bull_bias else 'strong_bear'
        hypotheses.append((label, 'high' if trend_bar_ratio > 0.7 else 'medium',
                          {'trend_bar_ratio': trend_bar_ratio,
                           'body_overlap_pct': body_overlap,
                           'ema_slope': ema_slope}))
    if trend_from_open:
        label2 = 'tfo_bull' if bull_bias else 'tfo_bear'
        hypotheses.append((label2, 'medium',
                          {'gap_count': gap_count,
                           'closes_above_ema': closes_above_ema}))
    if trading_range:
        hypotheses.append(('trading_range', 'medium' if body_overlap > 60 else 'low',
                          {'body_overlap_pct': body_overlap,
                           'trend_bar_ratio': trend_bar_ratio,
                           'doji_ratio': doji_ratio}))
    if not hypotheses:
        hypotheses.append(('ambiguous', 'low',
                          {'trend_bar_ratio': trend_bar_ratio,
                           'body_overlap_pct': body_overlap,
                           'ema_slope': ema_slope}))

    # Sort by confidence: high > medium > low
    conf_order = {'high': 0, 'medium': 1, 'low': 2}
    hypotheses.sort(key=lambda h: (conf_order.get(h[1], 3),))

    primary = hypotheses[0]
    alternatives = [h[0] for h in hypotheses[1:]]

    return {
        'hypothesis': primary[0],
        'confidence': primary[1],
        'reasoning': primary[2],
        'alternatives': alternatives,
    }


# ---------------------------------------------------------------------------
# 3. Pullback Counting — Swing-based leg detection
# ---------------------------------------------------------------------------

def compute_pullbacks(bars: list, classified: list,
                      trend_context: dict) -> dict:
    """
    Leg-based pullback counting using swing points.
    Within each leg, count distinct countertrend bar runs as H1-H4/L1-L4.
    """
    if not bars or len(bars) < 10:
        return {
            'structure_based': None,
            'bar_scan_fallback': {'H': 0, 'L': 0, 'note': 'insufficient_data'},
            'ambiguous': True,
        }

    swing_highs = trend_context.get('swing_highs', [])
    swing_lows = trend_context.get('swing_lows', [])
    trend_dir = trend_context.get('trend', 'unknown')
    bull = trend_dir == 'bull_trend'
    bear = trend_dir == 'bear_trend'

    if not swing_highs or not swing_lows:
        return {
            'structure_based': None,
            'bar_scan_fallback': _bar_scan_pullbacks(bars, classified, trend_dir),
            'ambiguous': True,
        }

    # Build leg structure from swing points
    # A leg = swing low → swing high (bull) or swing high → swing low (bear)
    legs = []
    swing_points = []

    for sh in swing_highs:
        swing_points.append(('high', sh['bar_idx'], sh['price']))
    for sl in swing_lows:
        swing_points.append(('low', sl['bar_idx'], sl['price']))

    swing_points.sort(key=lambda x: x[1])

    # Detect legs: alternate between swing low → high (bull) and high → low (bear)
    i = 0
    while i < len(swing_points) - 1:
        curr = swing_points[i]
        next_sp = swing_points[i + 1]
        if curr[0] == 'low' and next_sp[0] == 'high':
            legs.append({
                'type': 'bull',
                'start_bar': curr[1],
                'end_bar': next_sp[1],
                'start_price': curr[2],
                'end_price': next_sp[2],
                'extent_pct': round((next_sp[2] - curr[2]) / (curr[2] or 1) * 100, 2),
            })
            i += 2
        elif curr[0] == 'high' and next_sp[0] == 'low':
            legs.append({
                'type': 'bear',
                'start_bar': curr[1],
                'end_bar': next_sp[1],
                'start_price': curr[2],
                'end_price': next_sp[2],
                'extent_pct': round((curr[2] - next_sp[2]) / (curr[2] or 1) * 100, 2),
            })
            i += 2
        else:
            i += 1

    if not legs:
        return {
            'structure_based': None,
            'bar_scan_fallback': _bar_scan_pullbacks(bars, classified, trend_dir),
            'ambiguous': True,
        }

    legs_with_pullbacks = []
    for leg in legs:
        start = leg['start_bar']
        end = leg['end_bar']
        leg_bars = bars[start:end + 1]
        leg_cls = classified[start:end + 1]

        if len(leg_bars) < 2:
            continue

        # Within this leg, count countertrend bar runs
        pullback_runs = []
        in_pb = False
        pb_start = None

        for j, c in enumerate(leg_cls):
            is_countertrend = False
            if leg['type'] == 'bull':
                # Countertrend in a bull leg = bear bars and dojis
                is_countertrend = c['bar_type'] in ('trend_bear', 'weak_bear', 'doji', 'reversal_bear')
            else:
                is_countertrend = c['bar_type'] in ('trend_bull', 'weak_bull', 'doji', 'reversal_bull')

            if is_countertrend and not in_pb:
                in_pb = True
                pb_start = j
            elif not is_countertrend and in_pb:
                in_pb = False
                pullback_runs.append({
                    'type': 'L' if leg['type'] == 'bull' else 'H',
                    'start_bar_idx': start + pb_start,
                    'end_bar_idx': start + j - 1,
                    'bar_count': j - pb_start,
                    'bar_types': list(set(c2['bar_type']
                                        for c2 in leg_cls[pb_start:j])),
                })

        # Handle pullback still in progress at leg end
        if in_pb:
            pullback_runs.append({
                'type': 'L' if leg['type'] == 'bull' else 'H',
                'start_bar_idx': start + pb_start,
                'end_bar_idx': end,
                'bar_count': len(leg_cls) - pb_start,
                'bar_types': list(set(c2['bar_type']
                                    for c2 in leg_cls[pb_start:])),
                'in_progress': True,
            })

        leg_with_pb = {**leg}
        leg_with_pb['pullbacks'] = []
        for idx, pr in enumerate(pullback_runs):
            pb_label = f"{pr['type']}{idx + 1}"
            leg_with_pb['pullbacks'].append({
                'label': pb_label,
                'start_bar': pr['start_bar_idx'],
                'end_bar': pr['end_bar_idx'],
                'bar_count': pr['bar_count'],
                'in_progress': pr.get('in_progress', False),
            })

        # Count H/L totals from this leg
        h_count = sum(1 for pb in leg_with_pb['pullbacks'] if pb['label'].startswith('H'))
        l_count = sum(1 for pb in leg_with_pb['pullbacks'] if pb['label'].startswith('L'))

        leg_with_pb['counts'] = {'H': h_count, 'L': l_count}
        legs_with_pullbacks.append(leg_with_pb)

    # Current leg = last leg
    current_leg = legs_with_pullbacks[-1] if legs_with_pullbacks else None
    ambiguous_flag = False

    # Determine current pullback count
    if current_leg:
        h = current_leg['counts']['H']
        l = current_leg['counts']['L']
        pb_count_str = f"L{l}" if current_leg['type'] == 'bull' else f"H{h}"
    else:
        pb_count_str = 'unknown'
        ambiguous_flag = True

    return {
        'structure_based': {
            'legs': legs_with_pullbacks,
            'current_leg': {
                'type': current_leg['type'] if current_leg else 'unknown',
                'start_bar': current_leg['start_bar'] if current_leg else None,
                'pullback_count': pb_count_str,
                'pullback_details': current_leg['pullbacks'] if current_leg else [],
                'ema_proximity': 'unknown',
            },
            'ambiguous': ambiguous_flag,
        },
        'bar_scan_fallback': _bar_scan_pullbacks(bars, classified, trend_dir),
        'ambiguous': ambiguous_flag,
    }


def _bar_scan_pullbacks(bars, classified, trend_dir):
    """Fallback: scan last 20 bars backward for pullback count."""
    h_count = 0
    l_count = 0
    leg_dir = None
    bull = trend_dir == 'bull_trend'

    start = max(0, len(classified) - 20)
    cls_slice = classified[start:]

    for i in range(len(cls_slice) - 1, 0, -1):
        ct = cls_slice[i]
        if leg_dir is None:
            ct_simple = 'bull' if ct['close_position'] > 0.5 else 'bear' if ct['close_position'] < 0.5 else 'neutral'
            leg_dir = 'up' if (bull and ct_simple != 'bear') or (not bull and ct_simple == 'bear') else 'down'

        bar_is_trend = ct['bar_type'] in ('trend_bull', 'trend_bear')
        bar_is_weak = ct['bar_type'] in ('weak_bull', 'weak_bear')
        bar_is_doji = ct['bar_type'] == 'doji'

        if leg_dir == 'up':
            if bar_is_weak or bar_is_doji:
                l_count += 1
                break
        else:
            if bar_is_weak or bar_is_doji:
                h_count += 1
                break

    return {'H': h_count, 'L': l_count, 'leg_direction': 'up' if leg_dir == 'up' else 'down',
            'note': 'fallback_bar_scan'}


# ---------------------------------------------------------------------------
# 4. Measured Move Targets
# ---------------------------------------------------------------------------

def compute_measured_moves(bars: list, trend_context: dict) -> dict:
    """
    Compute measured move targets from the most recent completed swing leg.
    Both bull and bear projections.
    """
    swing_highs = trend_context.get('swing_highs', [])
    swing_lows = trend_context.get('swing_lows', [])
    trend_dir = trend_context.get('trend', 'unknown')

    result = {
        'bull': None,
        'bear': None,
        'current_leg_pct': None,
    }

    # Most recent completed bull leg: swing low → swing high
    if len(swing_lows) >= 1 and len(swing_highs) >= 1:
        # Find the most recent matching pair
        last_high = swing_highs[-1]
        best_low = None
        for sl in reversed(swing_lows):
            if sl['bar_idx'] < last_high['bar_idx']:
                best_low = sl
                break

        if best_low:
            leg_extent = last_high['price'] - best_low['price']
            result['bull'] = {
                'leg1_high': last_high['price'],
                'leg1_low': best_low['price'],
                'extent': round(leg_extent, 4),
                'measured_target': round(last_high['price'] + leg_extent, 4),
                'note': f"Leg 1 extent = ${round(leg_extent, 2)}. Project from leg low ${best_low['price']} → ${round(last_high['price'] + leg_extent, 2)}",
            }
            # Current leg progress
            last_close = bars[-1]['close'] if bars else 0
            if leg_extent > 0:
                progress = (last_close - best_low['price']) / leg_extent * 100
                result['current_leg_pct'] = round(progress, 1)

    # Most recent completed bear leg: swing high → swing low
    if len(swing_highs) >= 1 and len(swing_lows) >= 1:
        last_low = swing_lows[-1]
        best_high = None
        for sh in reversed(swing_highs):
            if sh['bar_idx'] < last_low['bar_idx']:
                best_high = sh
                break

        if best_high:
            leg_extent = best_high['price'] - last_low['price']
            result['bear'] = {
                'leg1_high': best_high['price'],
                'leg1_low': last_low['price'],
                'extent': round(leg_extent, 4),
                'measured_target': round(last_low['price'] - leg_extent, 4),
                'note': f"Leg 1 extent = ${round(leg_extent, 2)}. Project from leg high ${best_high['price']} → ${round(last_low['price'] - leg_extent, 2)}",
            }

    return result

# ---------------------------------------------------------------------------
# 5. Conviction Objective Components
# ---------------------------------------------------------------------------

def compute_conviction_objective(trend_context: dict, sos: dict,
                                  day_type: dict, pullbacks: dict,
                                  last_bar_classified: dict) -> dict:
    """
    Compute the objective components of the Brooks conviction scoring table.
    Agent adjusts subjectively (Trader's Equation, context, pattern evolution).
    """
    trend_dir = trend_context.get('trend', 'unknown')
    bull = 'bull' in trend_dir
    bear = 'bear' in trend_dir

    score = 0
    breakdown = {}

    # 1. Trend alignment
    if trend_dir in ('bull_trend', 'bear_trend'):
        score += 1
        breakdown['trend_alignment'] = 1
    else:
        score -= 2
        breakdown['trend_alignment'] = -2

    # 2. Signal bar quality
    last_bar = last_bar_classified or {}
    body_pct = last_bar.get('body_pct', 0)
    close_pos = last_bar.get('close_position', 0.5)

    if body_pct >= 70:
        score += 1
        breakdown['signal_quality'] = 1
    elif body_pct <= 25:
        if sos['interpretation'] == 'strong_trend_likely':
            breakdown['signal_quality'] = 0
        else:
            score -= 1
            breakdown['signal_quality'] = -1
    else:
        if body_pct >= 50 and ((bull and close_pos > 0.7) or (bear and close_pos < 0.3)):
            score += 1
            breakdown['signal_quality'] = 1
        else:
            breakdown['signal_quality'] = 0

    # 3. SoS band
    if sos['count'] >= 12:
        score += 1
        breakdown['sos_band'] = 1
    elif sos['count'] <= 5:
        score -= 1
        breakdown['sos_band'] = -1
    else:
        breakdown['sos_band'] = 0

    # 4. Day type factor
    dt = day_type['hypothesis']
    if dt in ('strong_bull', 'strong_bear'):
        score += 1
        breakdown['day_type_factor'] = 1
    elif dt == 'barbwire':
        score -= 2
        breakdown['day_type_factor'] = -2
    elif dt == 'trading_range':
        breakdown['day_type_factor'] = 0
    else:
        breakdown['day_type_factor'] = 0

    # 5. Pullback factor
    pb_info = {}
    if pullbacks.get('structure_based'):
        cl = pullbacks['structure_based']['current_leg']
        pb_info = cl
    pcount = pb_info.get('pullback_count', 'unknown')

    if bull and pcount in ('L2', 'L3'):
        score += 1
        breakdown['pullback_factor'] = 1
    elif bear and pcount in ('H2', 'H3'):
        score += 1
        breakdown['pullback_factor'] = 1
    elif bull and pcount == 'L1':
        breakdown['pullback_factor'] = 0
    elif bear and pcount == 'H1':
        breakdown['pullback_factor'] = 0
    else:
        breakdown['pullback_factor'] = 0

    return {
        'subtotal': score,
        'breakdown': breakdown,
        'note': "Agent adjusts for Trader's Equation, pattern evolution, countertrend exceptions",
    }


# ---------------------------------------------------------------------------
# 6. Brooks Intent Filtering
# ---------------------------------------------------------------------------

def compute_brooks_intent(sos: dict, day_type: dict,
                          trend_context: dict) -> dict:
    """
    Pre-filter which setups are worth considering based on SoS + day type.
    """
    trend_dir = trend_context.get('trend', 'unknown')
    bull = 'bull' in trend_dir
    dt = day_type['hypothesis']
    sos_int = sos['interpretation']

    primary = 'none'
    secondary = 'none'
    countertrend = 'none_recommended'
    warnings = []

    if dt in ('strong_bull', 'strong_bear'):
        if bull:
            primary = 'M2B_top_priority'
            secondary = 'breakout_pullback'
        else:
            primary = 'M2T_top_priority'
            secondary = 'breakout_pullback'
        warnings.append('Weak signal bars in strong trend are expected.')
        warnings.append('Do not penalize small pullback bars — normal for strong trend.')

    elif dt == 'barbwire':
        primary = 'fade_only'
        secondary = 'none'
        countertrend = 'fade_extremes'
        warnings.append('Barbwire: Most breakouts fail (~80%). Fade extremes only.')
        warnings.append('Never enter on stops in tight trading range.')

    elif dt in ('tfo_bull', 'tfo_bear'):
        primary = 'pullback_from_EMA'
        secondary = 'breakout_entry'

    elif dt == 'trading_range':
        primary = 'fade_extremes'
        secondary = 'breakout_pullback'
        countertrend = 'fade_2nd_entry'
        warnings.append('Trading range: buy H2 near bottom, sell L2 near top.')
        warnings.append('Most breakouts fail — wait for pullback confirmation.')

    else:
        primary = 'wait_for_clarification'
        secondary = 'none'
        warnings.append('Day type is ambiguous. Wait for clearer structure.')

    if sos_int == 'strong_trend_likely':
        countertrend = 'none_recommended'
        warnings.append('Strong SoS: Countertrend traps likely. Only with-trend entries.')

    return {
        'primary': primary,
        'secondary': secondary,
        'countertrend': countertrend,
        'warnings': warnings,
        'fade_setups': 'none' if 'fade' not in primary else 'fade_extremes',
    }


# ---------------------------------------------------------------------------
# 7. Pattern Evolution Watch
# ---------------------------------------------------------------------------

def compute_pattern_watch(patterns: dict, pullbacks: dict,
                          day_type: dict, trend_context: dict) -> dict:
    """
    Identify patterns that are evolving and what to watch for.
    """
    trend_dir = trend_context.get('trend', 'unknown')
    bull = 'bull' in trend_dir

    watch_items = []
    trigger_bars = 5
    note = 'No specific pattern evolution detected.'
    bear_watch = not bull

    if patterns.get('inside_bar'):
        watch_items.append('Inside bar: breakout or further compression pending.')
        trigger_bars = 2

    if patterns.get('wedge_top'):
        pushes = patterns['wedge_top'].get('pushes', 3) if isinstance(patterns['wedge_top'], dict) else 3
        if bull:
            watch_items.append(f'Wedge top ({pushes} pushes): trend exhaustion possible.')
        else:
            watch_items.append(f'Wedge top ({pushes} pushes) in bear trend: countertrend rally likely failing.')
        trigger_bars = 3

    if patterns.get('wedge_bottom'):
        pushes = patterns['wedge_bottom'].get('pushes', 3) if isinstance(patterns['wedge_bottom'], dict) else 3
        if not bull:
            watch_items.append(f'Wedge bottom ({pushes} pushes): selling exhaustion possible.')
        else:
            watch_items.append(f'Wedge bottom ({pushes} pushes) in bull trend: countertrend dip likely failing.')
        trigger_bars = 3

    if patterns.get('spike_bull'):
        watch_items.append('Spike up: follow-through or channel phase expected.')
        trigger_bars = 3
    if patterns.get('spike_bear'):
        watch_items.append('Spike down: follow-through or channel phase expected.')
        trigger_bars = 3

    if patterns.get('micro_channel_bull') or patterns.get('micro_channel_bear'):
        watch_items.append('Micro channel: steep trend, trend resumption likely after pullback.')
        trigger_bars = 2

    if patterns.get('ioi'):
        watch_items.append('IOI pattern: breakout imminent.')
        trigger_bars = 1

    pb_info = {}
    if pullbacks.get('structure_based'):
        pb_info = pullbacks['structure_based'].get('current_leg', {})
    pb_count = pb_info.get('pullback_count', 'unknown')
    if bull and pb_count == 'L1':
        watch_items.append('L1 formed. Watch for L2 at EMA for standard H2/L2 setup.')
    elif bear_watch and pb_count == 'H1':
        watch_items.append('H1 formed. Watch for H2 at EMA for standard M2T setup.')

    if watch_items:
        note = ' | '.join(watch_items)

    return {
        'note': note,
        'watch_items': watch_items,
        'trigger_bars': trigger_bars,
    }


# ---------------------------------------------------------------------------
# 8. Main Entry Point
# ---------------------------------------------------------------------------

def analyze(raw_data: dict) -> dict:
    """
    Main analysis function. Takes fetch_data.py output, returns brooks_analysis dict.
    """
    ticker = raw_data.get('ticker', 'UNKNOWN')
    timeframes = raw_data.get('timeframes', {})
    analysis_data = raw_data.get('analysis', {})
    indicators = raw_data.get('indicators', {})

    result = {
        'ticker': ticker,
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'timeframes_analyzed': list(timeframes.keys()),
    }

    daily_analysis = analysis_data.get('daily', {})
    daily_bars = timeframes.get('daily', [])

    if not daily_analysis or not daily_bars or 'error' in daily_analysis:
        result['error'] = 'No daily data available'
        return result

    trend_context = daily_analysis.get('trend_context', {})
    bar_analysis = daily_analysis.get('bar_analysis', {})
    patterns = daily_analysis.get('patterns', {})
    last_bar_classified = daily_analysis.get('last_bar_classified', {})
    last_10_classified = daily_analysis.get('last_10_bars_classified', [])

    classified = _build_full_classified(daily_bars, last_10_classified)

    trend_dir = trend_context.get('trend', 'unknown')

    sos = compute_sos(daily_bars, classified, trend_context, patterns, trend_dir)
    result['signs_of_strength'] = sos

    day_type = classify_day_type(daily_bars, classified, trend_context, bar_analysis)
    result['day_type'] = day_type

    pullbacks = compute_pullbacks(daily_bars, classified, trend_context)
    result['pullbacks'] = pullbacks

    mm = compute_measured_moves(daily_bars, trend_context)
    result['measured_moves'] = mm

    conv = compute_conviction_objective(trend_context, sos, day_type, pullbacks, last_bar_classified)
    result['conviction_objective'] = conv

    intent = compute_brooks_intent(sos, day_type, trend_context)
    result['brooks_intent'] = intent

    watch = compute_pattern_watch(patterns, pullbacks, day_type, trend_context)
    result['pattern_evolution_watch'] = watch

    ema20 = indicators.get('ema20', trend_context.get('ema20', 0))
    atr = indicators.get('atr', 0)
    last_close = indicators.get('close', daily_bars[-1]['close'] if daily_bars else 0)

    result['context'] = {
        'price': round(last_close, 2) if last_close else None,
        'ema20': round(ema20, 2) if ema20 else None,
        'atr': round(atr, 2) if atr else None,
        'bars_total': len(daily_bars),
        'swing_highs': trend_context.get('swing_highs', [])[-3:],
        'swing_lows': trend_context.get('swing_lows', [])[-3:],
        'trend': trend_dir,
    }

    return result


def _build_full_classified(bars: list, pre_classified_last_10: list) -> list:
    """Classify all bars for analysis, using pre-classified last 10 if available."""
    if not bars:
        return []

    classified = []
    for i, bar in enumerate(bars):
        if len(pre_classified_last_10) > 0:
            offset = len(bars) - len(pre_classified_last_10)
            if i >= offset:
                idx = i - offset
                if idx < len(pre_classified_last_10):
                    classified.append(pre_classified_last_10[idx])
                    continue

        prev_bar = bars[i - 1] if i > 0 else None
        classified.append(classify_bar(bar, prev_bar))

    return classified


def main():
    """CLI entry point."""
    if len(sys.argv) > 1:
        input_path = sys.argv[1]
        with open(input_path) as f:
            raw_data = json.load(f)
    else:
        raw_data = json.load(sys.stdin)

    result = analyze(raw_data)
    print(json.dumps(result, indent=2, default=str))

    outdir = os.path.dirname(os.path.abspath(input_path)) if len(sys.argv) > 1 else '.'
    outname = f"{raw_data.get('ticker', 'output')}_brooks_analysis.json"
    outpath = os.path.join(outdir, outname)
    with open(outpath, 'w') as f:
        json.dump(result, f, indent=2, default=str)
    print(f"\n[saved: {outpath}]", file=sys.stderr)


if __name__ == '__main__':
    main()
