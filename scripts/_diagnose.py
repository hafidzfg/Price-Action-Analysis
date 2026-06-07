#!/usr/bin/env python3
"""Diagnostic: check what M2B/M2S signals the engine would generate."""
import asyncio, sys
sys.path.insert(0, '.')
from fetch_data import (
    fetch_ohlcv, classify_bar,
    compute_trend_context, compute_bar_analysis, detect_patterns,
)
from brooks_analysis import compute_pullbacks, classify_day_type

async def main():
    bars = await fetch_ohlcv('NASDAQ:AAPL', '1D', 300)
    print(f'Got {len(bars)} bars', file=sys.stderr)
    
    classified = []
    for i, bar in enumerate(bars):
        prev = bars[i-1] if i > 0 else None
        classified.append(classify_bar(bar, prev))
    
    prev_pb = 'unknown'
    m2b_signals = 0
    m2s_signals = 0
    
    for i in range(60, len(bars)):
        sub_bars = bars[:i+1]
        sub_cls = classified[:i+1]
        
        tc = compute_trend_context(sub_bars)
        ba = compute_bar_analysis(sub_bars)
        pats = detect_patterns(sub_bars)
        
        pb = compute_pullbacks(sub_bars, sub_cls, tc)
        sb = pb.get('structure_based', {})
        cl = sb.get('current_leg', {})
        pb_count = cl.get('pullback_count', 'unknown')
        ema_prox = cl.get('ema_proximity', 'unknown')
        
        dt = classify_day_type(sub_bars, sub_cls, tc, ba)
        dt_hyp = dt['hypothesis']
        trend_dir = tc.get('trend', 'unknown')
        
        date_str = bars[i]['date']
        
        # M2B check
        if dt_hyp in ('strong_bull', 'tfo_bull') and pb_count == 'L2' and ema_prox in ('at_ema', 'near_ema'):
            if prev_pb != 'L2':
                line = f"M2B SIGNAL bar {i} ({date_str}): pb={pb_count} ema={ema_prox} dt={dt_hyp} trend={trend_dir} close={bars[i]['close']}"
                print(line)
                m2b_signals += 1
        
        # M2S check
        if dt_hyp in ('strong_bear', 'tfo_bear') and pb_count == 'H2' and ema_prox in ('at_ema', 'near_ema'):
            if prev_pb != 'H2':
                line = f"M2S SIGNAL bar {i} ({date_str}): pb={pb_count} ema={ema_prox} dt={dt_hyp} trend={trend_dir} close={bars[i]['close']}"
                print(line)
                m2s_signals += 1
        
        if pb_count != 'unknown':
            prev_pb = pb_count
    
    print(f'\nTotal M2B signals: {m2b_signals}, M2S signals: {m2s_signals}')
    
    # Day type distribution
    from collections import Counter
    dt_counts = Counter()
    for i in range(60, len(bars)):
        sub_bars = bars[:i+1]
        sub_cls = classified[:i+1]
        tc = compute_trend_context(sub_bars)
        ba = compute_bar_analysis(sub_bars)
        dt = classify_day_type(sub_bars, sub_cls, tc, ba)
        dt_counts[dt['hypothesis']] += 1
    print(f'Day types: {dict(sorted(dt_counts.items()))}')

if __name__ == '__main__':
    asyncio.run(main())
