# Book 2 Verification — Sage

I'm uploading "Trading Price Action Trading Ranges" by Al Brooks as an ePub.

You're running on Mimo V2.5 Pro for this session. Workflow — multiple turns, same session:

## Turn 1: Gap Analysis + Mapping

Read the existing distillation at `/home/hermes/skill_backup/price-action-al-brooks/book2-ranges.md` and the full book table of contents. Do two things:
1. Map each existing distillation section to its source chapters.
2. **Identify chapters NOT represented in the distillation.** List which chapters and major concepts are entirely missing.

## Turn 2: Fill Missing Chapters

For missing chapters — read the source, extract the key rules, and draft new sections matching the distillation's format. Insert them at the structurally correct position.

## Turns 3-N: Verify Existing Sections (one at a time)

For each existing distillation section, read the corresponding book chapters. Evaluate:
- Does every rule trace to an actual passage? Mark any that don't.
- Are there critical rules the distillation misses within covered chapters? Add them.
- Terminology errors? Non-Brooks language? Fix them.
- Edge cases accurate? Spot-check against source.
- Anything oversimplified to the point of being misleading?
- Check for overlap with core.md — if a concept is already in core.md, don't duplicate it in full. Reference it with "See core.md" instead.

## Final Turn: Compile & Write

Compile all changes — new sections for missing chapters + corrections to existing sections. Rewrite the full file. Overwrite both:

1. `/home/hermes/skill_backup/price-action-al-brooks/book2-ranges.md` (canonical — source of truth)
2. `$OBSIDIAN_VAULT_PATH/3 - Resources/Price Action - Al Brooks/book2-ranges.md` (vault — sync)

Then run:
```
cd /home/hermes/skill_backup/price-action-al-brooks && git add -A && git commit -m "book2-ranges: corrections + missing chapters from source verification"
```

## Architecture Context

Book 2 is the **ranges module** in a three-tier knowledge system:
- **core.md** (~13KB) — universal price action (ALWAYS loaded). Already contains: bar anatomy, bar counting basics, breakout framework, 20-EMA, close importance, two legs, risk management, glossary.
- **trends.md** (~14KB) — trend-specific (loaded when trending). Already contains: trend classification, signs of strength, entry types, spike & channel, trend lines, trend channel lines, channels, micro channels, day types.
- **book2-ranges.md** (~16KB) — THIS FILE (loaded when ranging/barbwire).

**The distillation should focus on range-specific knowledge.** If a concept is already covered in core.md (e.g., basic breakout signals, bar anatomy, H1/H2 definitions), reference it rather than duplicating. The ranges module should add the RANGE-SPECIFIC layer: how breakouts behave in ranges, how bar counting changes meaning in ranges, TR-specific entries, tight TR/barbwire rules, triangles, magnets, etc.

## Quality Standards

- Brooks language only. No generic trading advice. No invented rules.
- Zero hallucination. If the book doesn't say it, don't write it.
- Every concept traces to a chapter/section.
- Minimize overlap with core.md and trends.md — reference, don't repeat.
- Add wikilinks to [[core]] and [[trends]] where cross-references exist.

## Summary

Report:
- How many new sections were added (which chapters were missing)
- How many existing sections were corrected
- Any major structural changes
- Size comparison: before vs after
