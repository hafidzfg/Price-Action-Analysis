# Book 1: Trading Price Action Trends — DEPRECATED

> **This file is retained for backward compatibility only.** The canonical content has been split into:
>
> - **`core.md`** — Universal price action (bar anatomy, bar counting, breakouts, close, EMA, risk management, glossary). **Always loaded.**
> - **`trends.md`** — Trend-specific knowledge (signs of strength, entry types, spike & channel, trend lines, channels, micro channels, day types, pattern evolution). **Loaded when market is trending.**
>
> The three-tier routing is driven by the Tier-1 engine (`brooks_analysis.py`) output:
> - `strong_bull`/`strong_bear`/`tfo_bull`/`tfo_bear` → core + trends
> - `trading_range`/`barbwire` → core + book2-ranges
> - `ambiguous`/`insufficient_data` → core only (WAIT)
>
> See `SKILL.md` for the full routing table.
