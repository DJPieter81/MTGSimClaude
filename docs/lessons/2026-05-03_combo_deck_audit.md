---
title: Combo deck audit — what went wrong, what fixed it
date: 2026-05-03
session: claude/fix-critical-bugs-traces-hRUDU (PR #111)
audience: future-claude, sister project (MTGSimManu / Modern)
status: applied
---

# Combo deck audit — what went wrong, what fixed it

A trace audit of the lowest-WR combo matchups (Doomsday vs UR Delver 12.5%,
Reanimator vs Burn 20%, Depths vs Burn 35%) surfaced **seven independent
bugs** ranging from one-character typos to whole-deck design gaps. WRs
moved 12-27pp on key matchups. This document captures the bug taxonomy,
the diagnostic workflow that found them, and the lessons that generalise
to the sister project.

## Bug taxonomy

| # | Bug | Class | Found via | Impact |
|---|-----|-------|-----------|--------|
| 1 | Doomsday CMC = 5 (1BB+3 generic) instead of BBB = 3 | **Card data** | Trace: DD never castable T2 even with ritual | T1-T2 combo gated off entirely |
| 2 | Doomsday ran 1 Street Wraith (chain needs hand-presence) | **Deck construction** | Trace: pile built but no wraith to cycle | Same-turn wins blocked |
| 3 | Reanimator's T2 ritual mana eaten by shared `_execute_turn` Thoughtseize | **Strategy/preamble interaction** | Trace: TS cast pre-strategy, no mana left for combo | T2 Reanimate aborted |
| 4 | Combo-land priority hook gated on `active_deck == 'lands'` only | **Off-by-one in deck check** | Trace: Depths played filler basic on kill turn | depths vs burn 35% → 62% |
| 5 | Post-strategy Eidolon counted cycled cards as missed casts | **Heuristic over-counting** | Trace: 6 Eidolon damage from 3 wraith cycles | DD self-killed on combo turn |
| 6 | Lion's Eye Diamond missing from Doomsday | **Tier-1 card omission** | User intuition + trace showed no LED-Brainstorm line | Same-turn DD wins impossible |
| 7 | Lotus Petal missing from Storm (ANT) | **Tier-1 card omission** | Audit of canonical lists | storm vs dnt 34% → 50% |
| 8 | Oracle ETB winning at devotion = library (real rule is strict) | **Rule violation** | Surfaced by LED-BS fix exposing the gate | Over-counted wins |

## Bug class definitions

These five classes capture every audit finding. Future audits can use the
list as a checklist.

### A. Card data (fix in `cards.py`)
A single card's CMC, mana cost, types, or flags don't match the printed
card. **Diagnosis:** the strategy's mana gates lie — the strategy thinks
it can cast at N mana but `cast_spell` reads cmc and produces unexpected
behavior. **Search pattern:** for every key combo card, assert
`card.cmc` and `card.mana_cost` match the real card. Add a regression
test that names the card.

### B. Deck construction (fix in `cards.py`)
A real card is missing or undercounted. Tier-1 lists run specific
4-of staples (LED, Petal, Wraith, Brainstorm); anything that ships a
combo deck without the canonical fast-mana base is structurally
incapable of the matchup the deck is meant to win. **Diagnosis:** the
strategy works in isolation but the deck never assembles the kill.
**Search pattern:** compare deck contents to a recent top-8 list from
mtgtop8 / mtggoldfish. Assert key card counts in a regression test.

### C. Strategy / preamble interaction (fix in `sim.py:_execute_turn`
or the strategy)
A shared turn-step (Thoughtseize, removal, Bowmasters flash) consumes a
resource that the strategy needs for its combo line. The combo aborts
silently. **Diagnosis:** trace shows the shared action firing first,
then the strategy passing without doing anything. **Fix shape:** add a
defer-to-combo skip in the shared step, gated on the active deck
having a same-turn combo line ready.

### D. Off-by-one in deck check (fix where the check happens)
A deck-specific gate names one deck where it should name a class.
Lands and Depths run the same combo (Dark Depths + Thespian's Stage),
but `_pick_land`'s combo-piece priority only fired for `'lands'`.
**Diagnosis:** the second deck silently performs worse than its
sibling. **Search pattern:** `grep` for `active_deck == '...'` and
`deck in ('...',)` — any single-deck gate that controls a *mechanic*
(not a deck-specific quirk) is suspect.

### E. Heuristic over-counting / under-counting
A heuristic fires on the wrong cardinality of events. The post-strategy
Eidolon check used `(graveyard_growth − cast_spell_casts)` as a proxy
for "missed casts" — but every cycled wraith adds to graveyard_growth
without going through `cast_spell`. **Diagnosis:** logs show triggers
firing in counts that don't match real-MTG cardinality. **Fix shape:**
track the bypass channel explicitly and subtract it.

### F. Rule violation
The sim's win condition is looser than the real card's. Oracle's text
is "library has FEWER cards than your devotion" — strict less-than.
The sim checked `≤`. **Diagnosis:** logs show wins at numerically
boundary states (devotion = library = 2). **Fix shape:** read the
oracle text, replicate the strict comparison.

## Diagnostic workflow

The workflow that surfaced these bugs in ~3 hours:

1. **List the worst matchups by WR delta from expected.** Pull the latest
   matrix JSON, sort by `|sim_wr - expected_wr|`. Top of the list gets
   audited first.
2. **Generate 5-10 deep traces** with `run_game(d1, d2)` at fixed seeds.
   Read every line of the loss traces. Don't skim.
3. **Per trace, ask three questions:**
   - Did the strategy ever try to fire its win condition?
   - When it did, did the win condition's mana / lifeloss / draws
     match what real-deck math would produce?
   - When it didn't, what specifically was missing (card, mana,
     life, time)?
4. **Statistical breakdown of one matchup.** For 500 games, count
   (a) how often the win-condition card was in opening hand,
   (b) how often it was cast at all,
   (c) win rate conditional on it being cast,
   broken down by turn. The discontinuity (e.g. T1=47% win, T4=4% win)
   points at "what changed by T4" — usually opp damage + Eidolon.
5. **Read the strategy code with the trace open in another window.**
   Most bugs become visible the moment trace text and code line up:
   "trace says wraith cycled at T7 with life=2; code condition is
   `life > 2`; at life=2 the cycle silently doesn't happen."
6. **Write the regression test before the fix.** The test names the
   *mechanic* (e.g. "shared preamble disruption defers to combo"),
   not the card. The test goes red, then the fix turns it green, in
   the same commit.

## Lessons for the sister project (MTGSimManu / Modern)

These are findings that should port directly to Modern's combo decks.

1. **Audit every combo deck against a recent tier-1 list.** Modern's
   decks were imported from MTGGoldfish at some point; the imports
   may have drifted. For each combo deck, write a card-count
   regression test that asserts the canonical 4-ofs are present.
2. **Trace audit > heuristic tuning.** The biggest WR jumps in this
   session (depths vs burn +27pp, storm vs dnt +16pp) came from
   single-line bug fixes, not from tuning numeric thresholds. If a
   matchup is far from expected, a real bug is *very* likely; don't
   assume the strategy "needs more work."
3. **Eidolon-style heuristics need explicit channel tracking.** Any
   "post-strategy estimate based on graveyard growth" needs the same
   `_gy_via_non_cast` counter Legacy now has. Modern almost certainly
   has the same false-positive on cycled cards (Wraith/Edge of
   Autumn).
4. **Single-deck gates in shared pickers are bug nests.** Modern's
   `_pick_land` (or whatever its equivalent is) almost certainly has
   `active_deck == '...'` checks. Audit them — if the gate controls
   a mechanic (combo land priority, fast-mana priority), the
   right-hand side should be a *class* of decks, not a single name.
5. **Oracle / win-condition strict comparisons.** Re-read every win
   condition's oracle text. Real Magic has lots of strict-vs-loose
   wins (Oracle, Test of Endurance, Helix Pinnacle). Each one is a
   potential `≤ vs <` bug.
6. **Real-deck math as a sanity check.** When DD pays half life and
   needs to cycle 4 wraiths, the math is "20 → 10 → 8 → 6 → 4 → 2".
   When the trace shows "20 → 10 → 7 ... died T3", the *math* is the
   bug — opp damage is being absorbed silently or the cycle is
   firing wrong. Don't accept "RNG was bad" until the math reconciles.

## What this session did NOT fix

- **Doomsday vs Burn still 8-10%.** The fundamental gap is that real
  Legacy DD has Cabal Therapy (sees opp hand, removes Bolt) which the
  sim doesn't model, and a faster discard suite. Real WR ~40-45%.
  This is a deeper architectural gap, not a one-line fix. Round-3
  re-audit confirmed: the deck IS already the canonical tier-1 list
  (4 LED + 4 Petal + 4 Dark Ritual + 4 Wraith + 1 Lurrus). The
  remaining gap is sim-architecture-level — sim doesn't model:
  (a) Cabal Therapy's hand-look + name-a-card interaction
  (b) Per-matchup pile construction (vs Burn: heavy lifegain pile;
      vs Control: protection-heavy pile; sim uses one fixed structure)
  Flagged as a separate multi-day workstream.
- **No-DD-cast rate 34%.** When DD never gets drawn the strategy can't
  do anything useful. Not a strategy bug — RNG-bound. Could be
  improved with mulligan-for-DD logic, but that's a separate workstream.

## Round 3 follow-up (PR #113, 2026-05-03 evening)

Two of the deferred gaps from round 1 turned out to be Class B
(deck-construction) bugs after all — not architectural. Both single-line
fixes after digging into the deck-list data:

### Eldrazi: Abundant Countryside fetches basics that didn't exist

The deck ran 4 Abundant Countryside (a fetch land searching for *any*
basic land type) but had **zero basics**. Every crack paid 1 life and
produced no land — silently nerfing Eldrazi by ~4 effective mana
sources. Replaced 4 Countryside with 4 basic Wastes (Wasteland-immune
colorless mana — the canonical mono-brown Eldrazi fix).

Sweep delta: `eldrazi vs burn` 39% → 48.5% (+9.5pp).

The audit checklist gets a new question:
> **Does every fetch in this deck have a valid target in the library?**
> Specifically: for `fetch_targets={'Forest', 'Plains', ...}`, count
> basics with matching subtypes in the deck. If zero, the fetch is
> pure life-loss — replace it.

### Wan Shi Tong: Sanctifier en-Vec underrepresented for Bo1

WST is the canonical anti-Burn Legacy deck *specifically because*
Sanctifier en-Vec has protection from red. At 2 copies the deck
only saw Sanctifier in opener ~22% of games vs Burn — too rare for
the matchup to feel like the lock it should be. Real Bo1 lists run
2-3 main; bumped to 3.

Sweep delta: `wan_shi_tong vs burn` 30.5% → 40.5% (+10pp).

The audit checklist gets a new question:
> **For each combo / control deck, is the matchup-specific hate card
> at the count needed for a Bo1 sample of 200 games?** A 2-of card has
> ~22% chance to be in opener; if the matchup hinges on that card
> being seen, 3-of is the minimum for the sim to evaluate the
> matchup faithfully. Real Bo3 lists run 1-2 main + sideboard, but
> the sim is Bo1 and needs higher main counts.

## Numbers — round-by-round

Tracking the WR deltas over four commits.

### Round 1 — initial audit fixes (commit 55aea3b)

| Matchup | Before | After |
|---|---|---|
| doomsday vs ur_delver | 12.5% | 15% |
| doomsday vs storm | ~20% | 32% |
| doomsday vs dnt | ~30% | 44% |
| reanimator vs burn | 20% | 25% |
| reanimator vs ur_delver | ~30% | 38% |

### Round 2 — combo-land priority for Depths (commit 9fce985)

| Matchup | Before | After |
|---|---|---|
| depths vs burn | 35% | **62%** (+27pp) |
| depths vs dimir | 71% | 78% |
| depths vs storm | — | 74% |
| depths vs ur_delver | — | 85% |

### Round 3 — Eidolon false-positive on cycling (commit 02cf80a)

| Matchup | Before | After |
|---|---|---|
| doomsday vs storm | 32% | 37% |
| doomsday vs burn | 8% | 10% |

### Round 4 — Tier-1 LED + Lotus Petal (commits d6430b5 + 229ead8)

| Matchup | Before | After |
|---|---|---|
| storm vs dnt | 34% | **50%** (+16pp) |
| storm vs burn | 30% | **43%** (+13pp) |
| storm vs dimir | 40% | **60%** (+20pp) |
| storm vs lands | — | 52% |
| doomsday vs storm | 32% | 37% |
| doomsday vs lands | — | 41% |

### Round 5 — Cephalid Brainstorm + wizardcycling (PR #112)

| Matchup | Before | After |
|---|---|---|
| cephalid vs dimir | 31.7% | 36.5% |
| cephalid vs lands | — | 60% |

### Round 6 — Eldrazi basics + Wan Shi Tong Sanctifier (PR #113)

| Matchup | Before | After |
|---|---|---|
| eldrazi vs burn | 39% | **48.5%** (+9.5pp) |
| eldrazi vs storm | — | 59% |
| wan_shi_tong vs burn | 30.5% | **40.5%** (+10pp) |

## Tests added

```
Doomsday: printed CMC is 3 (BBB)
Doomsday: mana cost is exactly BBB
Doomsday: Street Wraith count ≥ 3 (chain reliability)
Doomsday: Lion's Eye Diamond count == 4 (tier-1 mandatory)
Reanimator vs Burn @ 10 fixed seeds: ≥ 4 wins
Depths vs Burn @ 10 fixed seeds: ≥ 5 wins (combo-land priority)
Storm (ANT): Lotus Petal count == 4
Storm (ANT): Lion's Eye Diamond count == 4
Cephalid vs Storm @ 10 fixed seeds: ≥ 3 wins
Eldrazi: deck has ≥ 4 basic lands (Countryside / Wasteland-immune)
Wan Shi Tong: Sanctifier en-Vec count == 3
```

149 → 160 total tests, all green.
