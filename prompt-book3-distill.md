# Book 3 Distillation — Sage

I'm uploading "Trading Price Action Reversals" by Al Brooks as an EPUB.

## Turn 1: Extract TOC + Assess Scope

Extract the full table of contents from the EPUB. Then do two things:
1. **Assess content scope.** Read each chapter title and front/back matter. What does this book actually cover? How much is reversal-specific vs universal vs already in core.md/trends.md/ranges.md?
2. **Flag potential overlap with existing modules.** Core.md already has: bar anatomy, bar counting, breakout framework, 20-EMA, close importance, two legs, trade management (stops, limits, scaling, profit), Trader's Equation, glossary. Trends.md has: trend classification, signs of strength, entry types, spike & channel, trend lines, channels, micro channels, day types. Ranges.md has: breakout signs, TR entries, barbwire, triangles, dueling lines, magnets, DT/DB/H&S context.

**Do NOT design the architecture yet.** Just report what's in the book and where it might overlap.

## Turn 2: Draft Full Distillation

Read every chapter. Extract the key rules, patterns, and decision logic. Draft the full distillation matching the format of the existing modules:

- Brooks terminology only. No generic trading advice. No invented rules.
- Zero hallucination. If the book doesn't say it, don't write it.
- Every concept traces to a chapter/section.
- Tables for structured data (patterns, rules, decision matrices).
- Compact prose — rules and bullets, not paragraphs.
- Add wikilinks to [[core]] and [[trends]] and [[ranges]] where cross-references exist.
- If a concept is already fully covered in core.md, reference it with "See [[core]]" rather than duplicating.

Save to: `/home/hermes/skill_backup/price-action-al-brooks/reversals-draft.md`

## Turn 3: Architectural Validation

Now that the content is written, decide WHERE it lives. For each section in the draft, classify:

| Category | Where it goes | Rationale |
|----------|--------------|-----------|
| **Reversal-specific** | `reversals.md` (new module) | Only loads when reversal signals detected |
| **Already in core.md** | Delete from draft, add "See [[core]]" | Don't duplicate universal content |
| **Better fit for trends.md** | Move to trends.md | Trend-specific reversal behavior |
| **Better fit for ranges.md** | Move to ranges.md | Range-specific breakout failure behavior |
| **Universal but missing from core.md** | Move to core.md | Content that should load on every analysis |

**Key question for each section:** "If the agent is analyzing a strong bull trend day with no reversal signals, does it need this content?" If yes → core.md. If no → specialist module.

**Output:** Final routing plan — which sections go where. Then execute the moves.

## Turn 4: Compile & Write

Rewrite all affected files:
1. New `reversals.md` with ONLY reversal-specific content
2. Updated `core.md` if any universal content was found
3. Updated `trends.md` if any trend-reversal content was added
4. Updated `ranges.md` if any range-reversal content was added
5. Update `SKILL.md` routing table if reversals.md is a new module (add loading conditions)
6. Overwrite vault copies at `$OBSIDIAN_VAULT_PATH/3 - Resources/Price Action - Al Brooks/`

Then commit and push:
```
cd /home/hermes/skill_backup/price-action-al-brooks && git add -A && git commit -m "book3-reversals: initial distillation + architectural placement"
```

## Architecture Context

Three-tier knowledge system (current state after Option A migration):

| Module | Size | Loads When | Content |
|--------|------|-----------|---------|
| **core.md** | ~20KB | ALWAYS | Bar anatomy, counting, breakouts, close, 2-EMA, two legs, trade management (stops, limits, scaling, profit), Trader's Equation, glossary |
| **trends.md** | ~14KB | Trending | Trend classification, signs of strength, entry types, spike & channel, trend lines, channels, micro channels, day types |
| **ranges.md** | ~20KB | Ranging | Breakout signs, TR entries, barbwire, triangles, dueling lines, magnets, DT/DB/H&S, bar counting in ranges |

**Book 3's place is TBD.** It might become a fourth module (`reversals.md`), or its content might distribute across existing modules. The distillation and architectural validation will determine this.

**Known hypothesis (to test, not assume):** Reversals are events, not states. They might work as an overlay that loads alongside the state module (core + trends + reversals, or core + ranges + reversals) rather than replacing it. But this needs validation against actual content.

## Quality Standards

- Brooks language only. No generic trading advice. No invented rules.
- Zero hallucination. If the book doesn't say it, don't write it.
- Every concept traces to a chapter/section.
- Minimize overlap with core.md, trends.md, ranges.md — reference, don't repeat.
- Add wikilinks to [[core]], [[trends]], [[ranges]] where cross-references exist.

## Summary Report

After completion, report:
- How many sections in the distillation
- How many sections routed to each module (reversals.md, core.md, trends.md, ranges.md)
- Any major structural decisions and why
- Size of reversals.md (if created)
- Updated sizes of core.md, trends.md, ranges.md (if modified)
- Total system size (all modules combined)
