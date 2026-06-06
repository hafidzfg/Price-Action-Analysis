# Book 1 Verification — Sage

I'm uploading "Trading Price Action Trends" by Al Brooks as an ePub.

You're running on Mimo V2.5 Pro for this session. Workflow — multiple turns, same session:

## Turn 1: Gap Analysis + Mapping

Read the existing distillation at `/home/hermes/skill_backup/price-action-al-brooks/book1-trends.md` and the full book table of contents. Do two things:
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
- Signs of Strength checklist (Ch 19) — count against actual text. Is "22+" correct?
- Anything oversimplified to the point of being misleading?

## Final Turn: Compile & Write

Compile all changes — new sections for missing chapters + corrections to existing sections. Rewrite the full file. Overwrite both:

1. `/home/hermes/skill_backup/price-action-al-brooks/book1-trends.md` (canonical — source of truth)
2. `/home/hermes/hfg_obsidian_vault/3 - Resources/Price Action - Al Brooks/book1-trends.md` (vault — sync)

Then run:
```
cd /home/hermes/skill_backup/price-action-al-brooks && git add -A && git commit -m "book1-trends: corrections + missing chapters from source verification"
```

## Quality Standards

- Brooks language only. No generic trading advice. No invented rules.
- Zero hallucination. If the book doesn't say it, don't write it.
- Every concept traces to a chapter/section.
- Add wikilinks to [[book2-ranges]] where forward references exist.

## Summary

Report:
- How many new sections were added (which chapters were missing)
- How many existing sections were corrected
- Any major structural changes
