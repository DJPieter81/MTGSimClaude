---
title: Doomsday — Cabal Therapy + per-matchup pile architecture
date: 2026-05-16
status: proposal
supersedes: 2026-05-09_doomsday_cabal_therapy.md
---

# Doomsday — Cabal Therapy + per-matchup pile architecture

> This document supersedes and significantly extends the earlier
> [`2026-05-09_doomsday_cabal_therapy.md`](2026-05-09_doomsday_cabal_therapy.md)
> sketch. That note proposed a `PileBuilder` abstraction; the present doc
> upgrades it to a typed `Pile` algebra mirroring `combo_engine.combo_plan`'s
> `Execute / Hold / Defer / NoPlan` shape, fully specifies a 6-phase
> migration sequence, and folds in two months of structural-grader,
> typed-decision, and shared-preamble lessons that postdate the earlier
> sketch.
>
> **Status:** proposal. NO implementation is gated by this document
> landing on `main`. Implementation begins only after Phase A's failing
> test is written, per the project's CLAUDE.md "no fix without a failing
> test in the same diff" rule.

---

## 1. Context

The 2026-04-12 matrix has Doomsday at ~33% average meta-weighted WR —
PLANNING.md lines 600–602 (audit table) and lines 613–626 (matchup
breakdown). The deck's failure mode is matchup-specific and severe on
the aggressive-blue/red axis:

| Opponent | Doomsday WR |
|---|---:|
| burn | 5.7% |
| ur_tempo | 11.2% |
| uwx | 11.7% |
| ur_aggro | 11.9% |
| ur_delver | 14.0% |
| dimir variants | 15–19% |
| cloudpost / lands / oops / painter / belcher | 60–67% |

Real-Legacy Doomsday WR across the same field is ~45–50%. The deck wins
disrupted matchups (burn, tempo, control) because real lists exploit
two mechanics the simulator does not model:

1. **Per-matchup pile shape.** A real DD pilot selects a different
   five-card pile against burn (lifegain), control (counter-protection),
   aggro (race speed), and combo (tendrils race). The simulator stacks
   one generic pile that loses to all three of the disrupted matchup
   archetypes.
2. **Cabal Therapy.** Real 4-of in tier-1 lists; the simulator's
   `make_doomsday_deck` does not include it. Combined with Flashback
   from graveyard, CT lets the DD pilot strip a free counter before
   resolving Doomsday on the kill turn.

**PLANNING.md lines 124–137** (loop-break protocol) and the iteration-8
finding at **PLANNING.md lines 636–649** confirm the architectural
diagnosis: tightening `_keep_doomsday` (a one-line mulligan fix) moved
WR by 0.0pp because the simulator is missing the cards the strategy
would need to reference. Three single-line "DD vs Burn" patches over
the prior session (iter 8 keep-fn, plus PR #111 Round 3, plus iter 7
audit) moved WR by 0.0pp / +2pp / +0.0pp. The loop-break is in force:
**no further single-line DD fixes — write the architecture first.**

The current strategy lives at **`engine.py:4599–5115`**
(`_strategy_doomsday`) — 516 lines of monolithic combo logic that bakes
in a single kill line (LED + Brainstorm same-turn dig, per PR #111).
The pile shape is implicit (no `Pile` type exists; the pile is whatever
the strategy chooses to draw from the library after Doomsday resolves).
The current decklist lives at **`cards.py:581–634`**
(`make_doomsday_deck`). Lurrus of the Dream-Den is already in the
decklist (line 622–623) and gets deployed at engine.py:4768–4779. What
is **missing**:

- **Cabal Therapy** in the decklist (zero copies).
- **Flashback resolver** for Cabal Therapy (engine.py:2970–2986 already
  has a non-flashback CT wiring used by Mardu — needs Flashback
  extension for DD).
- **Lifegain pile shape** (`Lotus Petal → Brainstorm → Wraith × 3`
  gains ~6 life via Lurrus death-rebuy; cf. PLANNING.md line 646).
- **Per-matchup pile selection.** The strategy has no notion of
  "matchup class → pile shape"; it always builds toward the
  LED-Brainstorm-Oracle kill regardless of opponent.

---

## 2. The architectural problem

A single monolithic strategy cannot represent per-matchup pile choice
without devolving into deck-name patches inside `engine.py` — which the
CLAUDE.md abstraction contract explicitly prohibits (no
`opp.deck == 'burn'` inside engine code).

The pile shape is a *function of (matchup-class, own life, own
resources)*:

| Matchup class | Own life | Resources | Pile |
|---|---|---|---|
| AGGRO_DECKS | ≤ 10 | Lurrus available | LurrusPile (lifegain) |
| COMBO_DECKS | any | LED + Cabal Therapy | TendrilsPile (race) |
| INTERACTION_DECKS | any | LED + Brainstorm | WraithPile (resilience) |
| INTERACTION_DECKS | any | LED missing | OraclePile (slow, multi-turn) |

Today the code picks one pile implicitly: the LED-Brainstorm same-turn
dig. The design must declare a **pile-selection subsystem** with
typed pile dataclasses, mirroring the typed `Execute / Hold / Defer /
NoPlan` algebra `combo_engine.combo_plan` returns (see
`combo_engine.py:279–340`). The pattern is proven: structural-grader
landed on `combo_plan` because the typed algebra eliminated boolean-flag
strategy patches at the call sites. The same lesson applies inside DD.

---

## 3. Proposed architecture

### 3.1 Module location

**New module: `decks/doomsday_piles.py`**.

Rationale for `decks/` rather than a root module:

1. The pile-selection logic is **deck-specific**, not engine-shared.
   Per CLAUDE.md: "card-specific knowledge lives in oracle text, card
   flags, or `decks/*.py` plugin modules. NEVER in the engine/AI core
   files."
2. `decks/` modules legitimately reference card names (CLAUDE.md
   abstraction contract exception). Pile contents *must* reference
   specific tags (`'led'`, `'bs'`, `'wraith'`, `'oracle'`, `'petal'`,
   `'lurrus'`).
3. No circular import: `decks/doomsday_piles.py` can import
   `bhi.HandBelief` and the structural-grader's deck-class sets from
   `scripts/structural_grader.py:115–144` (or, preferably, from a
   shared `deck_classes.py` extracted in Phase B — see Risks §7).

### 3.2 Typed `Pile` dataclasses (frozen)

```python
# decks/doomsday_piles.py — sketch, not for implementation.

from dataclasses import dataclass

@dataclass(frozen=True)
class Pile:
    """Abstract base. Each concrete Pile declares its OWN resource cost
    and assembly invariant — no shared mutation."""
    name: str             # 'tendrils' | 'lurrus' | 'wraith' | 'oracle'
    cards: tuple          # tag sequence top→bottom (5 entries)
    draws_to_win: int     # how many draws after DD before Oracle/Tendrils win
    mana_to_execute: int  # mana required AFTER DD resolves
    life_floor: int       # minimum own life pre-DD to survive execution

@dataclass(frozen=True)
class TendrilsPile(Pile):
    """Tendrils race line. 5-card pile drains opponent via Lion's Eye
    Diamond + Dark Ritual + Cabal Ritual chain. Wins through counters
    by burning the stack pre-DD."""

@dataclass(frozen=True)
class LurrusPile(Pile):
    """Lifegain pile. Lotus Petal → Brainstorm → Wraith × 3.
    Combined with Lurrus-rebuy of dying CMC-≤2 permanents, gains 6+
    life. Used vs aggro at low life."""

@dataclass(frozen=True)
class WraithPile(Pile):
    """Resilience pile. Multi-Wraith chain with Brainstorm as the pile
    finisher. Used vs interaction where DD might get countered T2 and
    we need a recovery turn."""

@dataclass(frozen=True)
class OraclePile(Pile):
    """Slow Oracle pile. No LED required — wins T+1 of the DD turn by
    drawing Brainstorm naturally. Used vs INTERACTION_DECKS when LED
    is in the graveyard or exiled."""
```

Each pile is a **value** with no `__init__`-time side effects and no
mutable state. The strategy consumes a `Pile` and dispatches the
resolve sequence based on its type.

### 3.3 `select_pile(player, opponent, gs) → Pile`

```python
def select_pile(player, opponent, gs) -> Pile:
    """Pure function. No side effects on player / opponent / gs.

    Inputs read:
      - opponent's deck class (COMBO_DECKS / AGGRO_DECKS /
        INTERACTION_DECKS) per scripts/structural_grader.py:115–144
      - HandBelief(opp_deck_key).p_free_counter (BHI) per bhi.py
      - player.life
      - tag counts: led, petal, bs, wraith, oracle, lurrus, therapy
        in player.hand / .graveyard
      - whether Lurrus is on the battlefield
    """
```

Decision tree (executable specification, not implementation):

1. If `opp_deck in AGGRO_DECKS` and `player.life ≤ 10` and a Lurrus is
   available (in hand OR on battlefield OR companion zone): **LurrusPile**.
2. Else if `opp_deck in COMBO_DECKS`: **TendrilsPile** (race the
   opposing combo before they go off; CT pre-empts their key piece).
3. Else if `opp_deck in INTERACTION_DECKS` and the player has BS + LED
   in hand: **WraithPile** (recovery-via-Brainstorm if first DD
   resolves but Oracle gets countered).
4. Else: **OraclePile** (the existing kill line; default).

The function is **pure**. Wiring it into `_strategy_doomsday` is a
single call returning a typed value; the dispatch is a `match` on the
pile type, exactly the pattern `combo_engine.combo_plan` consumers
use today (cf. `decks/depths.py:319–328`).

### 3.4 Cabal Therapy as a discard subsystem

Cabal Therapy already has a non-flashback wiring at
**engine.py:2970–2986** (used by Mardu and tagged `'therapy'` in
`cards.py:400` for Oops, `decks/ocelot.py:25`, `decks/cephalid.py:88`).
The DD-specific work is:

1. **Add 4 Cabal Therapy** to `make_doomsday_deck`.
2. **Flashback model.** CT printed text: "Flashback — sacrifice a
   creature." Second cast comes from the graveyard, costs zero mana but
   sacrifices a creature. The DD pile naturally sacrifices Street Wraith
   (cycle = discard to graveyard), so the second CT cast is gated on
   `player.graveyard.count(tag='wraith') >= 1` and `creatures` having
   at least one expendable body.
3. **Disruption logging.** Reuse the existing typed-disruption API:

   ```python
   gs.strat_log.log_disruption(
       turn=gs.turn, gs=gs, player=player,
       kind='discard', target_tag=<named_tag>,
       instrument_tag='therapy',
       reason='strip free counter before DD-resolve turn')
   ```

   This is the canonical entry point per
   `strategic_logger.py:91–137`. The token format
   (`discard_<tag>_with_therapy`) feeds the structural grader's
   interaction axis (see `scripts/structural_grader.py:149`,
   `EXECUTE_PREFIXES`).

### 3.5 Lurrus as a companion

The current decklist embeds Lurrus as a 1-of in the maindeck
(`cards.py:622–623`). Real Bo1 lists run Lurrus as a **companion** —
a 61st card outside the deck that can be cast once per game from a
"companion zone." The design adds:

1. **`DECK_META['companion'] = 'lurrus'`** flag in `decks/doomsday.py`.
2. **Companion zone wiring.** At game start, if `DECK_META[deck].get
   ('companion')`, place that card in `player.companion_zone` (new
   slot). Casting from companion zone uses the same mana check as
   hand casts; once cast, the slot is empty for the rest of the game.
   (The existing `Lurrus → 4-of in maindeck` becomes `Lurrus → 1
   companion + 0 maindeck`.)
3. **Death-rebuy hook.** Lurrus printed text: "During each of your
   turns, you may cast one permanent spell with mana value 2 or less
   from your graveyard." This already partially exists at
   **engine.py:4781–4799** (Lotus Petal rebuy). Generalize to ANY
   CMC-≤2 permanent in graveyard (Petal + Oracle backup + Veil + LED).
   Gate on `gs._lurrus_used_turn == gs.turn` to enforce "once per
   turn." No change to the rebuy resource accounting — Lurrus only
   *grants permission*; the cast still pays its CMC.

### 3.6 What does NOT change

- **`combo_engine.combo_plan`** is untouched. DD's pile selection is
  internal to its strategy; the public `combo_plan` algebra remains
  `Execute | Hold | Defer | NoPlan`. The pile choice is a *refinement*
  of the `Execute(path)` branch, not a new top-level case.
- **`engine.py`** gains no new card-name string literals. The
  generalized Lurrus rebuy and the per-pile dispatch are the only
  edits, and they read tags / pile-type, never card names.
- **No matrix re-sim** is part of this design. Implementation gates
  on Phase F passing; sweep validation comes after Phase F lands.

---

## 4. Migration plan

Sequencing only — **do not implement in this PR**. Each phase has a
named failing test that turns green when the phase code lands. Per
CLAUDE.md: "No fix without a failing test in the same diff."

### Phase A — Cabal Therapy + Lurrus companion in decklist

- Edit `cards.py:make_doomsday_deck`: drop maindeck Lurrus,
  add 4 Cabal Therapy, fill to 60.
- Edit `decks/doomsday.py:DECK_META`: add `'companion': 'lurrus'`.
- Add `player.companion_zone` slot at game start.
- **Failing test:** `test_doomsday_companion_in_zone_at_game_start` —
  starting a game with `deck1='doomsday'` places Lurrus in
  `p1.companion_zone`, not in `p1.hand` / `p1.library`.

### Phase B — `decks/doomsday_piles.py` skeleton

- Create the module with the 4 frozen `Pile` dataclasses
  (TendrilsPile / LurrusPile / WraithPile / OraclePile).
- No wiring into engine yet.
- **Failing test:** `test_pile_dataclasses_are_frozen` — assert each
  Pile subclass is `@dataclass(frozen=True)` and that mutation
  raises `FrozenInstanceError`.

### Phase C — `select_pile(...)` pure function

- Add the function with the decision tree from §3.3.
- Unit-test against synthetic `GameView` inputs (matchup-class + life
  + resources → expected pile type).
- **Failing test:** `test_select_pile_picks_lurrus_vs_burn_at_low_life`
  — given `opp_deck='burn'`, `player.life=8`, lurrus
  available → returns `LurrusPile`. Plus three companion tests
  for the COMBO / INTERACTION / OraclePile branches.

### Phase D — Wire `select_pile` into `_strategy_doomsday`

- At the DD-resolve point (the existing
  `_doomsday_pile_built = True` site inside the resolve callback),
  call `select_pile(player, opponent, gs)` and dispatch the resolve
  sequence based on the returned pile type.
- The default (`OraclePile`) preserves byte-identical behavior with
  the current strategy — old replays still match.
- **Failing test:** `test_doomsday_vs_burn_selects_lurrus_pile_s1` —
  `run_game('doomsday', 'burn')` with `random.seed(1)`: assert
  `strat_log` contains a `combo:lurrus_pile` token (new Execute
  token to emit at pile-resolve time).

### Phase E — Generalize Lurrus death-rebuy

- Replace the Lotus-Petal-only rebuy block at
  `engine.py:4781–4799` with a generic loop over `player.graveyard`
  filtered to `cmc ≤ 2 AND is_permanent`.
- Gate on `gs._lurrus_used_turn`.
- **Failing test:** `test_lurrus_rebuys_oracle_from_graveyard` — set up
  GS with Lurrus on battlefield, Oracle in graveyard, devotion ≥
  library; cast budget = 2. After strategy tick, Oracle is in play
  and the game ends.

### Phase F — Cabal Therapy branch in `_strategy_doomsday`

- T1/T2 cast of Cabal Therapy targeting opponent's predicted free
  counter (BHI-driven choice, same pattern as the existing
  `_strategy_doomsday` BHI usage at engine.py:4608–4630).
- Flashback gate: on a subsequent turn, if a Wraith is in graveyard
  and a creature can be sacrificed, recast CT.
- Both casts go through `gs.strat_log.log_disruption(kind='discard',
  instrument_tag='therapy', ...)`.
- **Failing test:** `test_doomsday_casts_therapy_vs_storm_t1_s42` —
  `run_game('doomsday', 'storm')` with `random.seed(42)`: assert
  trace contains `discard_<tag>_with_therapy` for at least one
  Storm key piece, and that the second CT cast (flashback) appears
  if a Wraith hit the graveyard.

---

## 5. Verification recipe (post-implementation)

Not part of this design doc; run only after Phase F lands.

- **DD vs aggro:** WR rises from 12–15% toward 30–40% (the lifegain
  pile + Lurrus rebuy lets DD survive long enough to combo).
- **DD vs combo:** WR stable or +5pp (CT strips a key combo piece
  pre-emptively).
- **DD overall meta-weighted WR:** 33% → 40–45%.
- **Structural grader:** DD's `combo` axis should land at A or A+.
  Typed `combo:tendrils_pile` / `combo:lurrus_pile` / `combo:wraith_pile`
  Execute tokens land per Phase D; the existing `combo:doomsday_oracle`
  token (PR #147) continues to fire for the OraclePile branch.
- **Regression sweep:** `python3 tools/regression_sweep.py` must
  remain green (no baseline matchup drops > 5pp). If any non-DD
  matchup regresses, the phase that introduced the regression is
  reverted before proceeding.

---

## 6. Required cross-references

- **`docs/lessons/2026-05-03_combo_deck_audit.md` Round 3** (lines 166,
  229): identifies the close-out gap — "Doomsday vs Burn still 8–10%.
  The fundamental gap is that real Doomsday races aggro decks via
  Lurrus + lifegain piles, which the sim does not yet model." This
  design is the architectural close-out of that gap.
- **PLANNING.md lines 124–137** (loop-break protocol) and
  **lines 613–649** (iteration 7/8 audit + iteration 8 null result).
- **`docs/design/2026-05-09_doomsday_cabal_therapy.md`** — earlier
  sketch; this doc supersedes (see frontmatter).
- **`cards.py:581–634`** — current `make_doomsday_deck`.
- **`engine.py:4599–5115`** — current `_strategy_doomsday`.
- **`combo_engine.py:279–340`** — typed `Execute / Hold / Defer /
  NoPlan` algebra to mirror.
- **`scripts/structural_grader.py:115–144`** — deck-class sets
  (`COMBO_DECKS`, `AGGRO_DECKS`, `INTERACTION_DECKS`) the pile-selector
  consumes.
- **`strategic_logger.py:91–137`** — canonical `log_disruption` API.
- **PR #147** — typed Execute tokens for combo decks (the wiring this
  design extends).
- **PR #165** (TS preamble structural removal) and **PR #166** (Petal
  preamble double-count fix) — see Risks §7.

---

## 7. Risks

Pile-selection logic is a class-of-bugs surface analogous to the
shared-preamble pattern. **PR #165** (commit `d88e2b8`) and **PR #166**
(commit `d28bdb3`) both landed because shared-preamble logic in
`sim.py:_execute_turn` was mutating resources (Thoughtseize cast eating
ritual mana; Lotus Petal counted twice once via preamble and once via
strategy) — exactly the bug class that arises when an outer layer
touches the same resource an inner layer also touches. The lessons
apply directly:

1. **Pile-selection logic stays inside `decks/doomsday_piles.py`,
   NOT inside `engine.py` shared layer.** No `if opp_deck in ...`
   branches in engine.py.
2. **Each typed Pile dataclass owns its OWN resource declaration**
   (mana required, life floor, draw count). No shared mutation of
   `total_mana` / `budget[0]` / `player.life` outside the
   per-pile resolve callback. Each pile's resolve runs inside the
   existing `cast_spell` resolve callbacks (see engine.py:4697,
   4736, 4775) — these already have the right boundary discipline.
3. **`select_pile` is pure.** No side effects; output depends only on
   inputs read from `gs` / `player` / `opponent`. Wiring it into
   `_strategy_doomsday` does not add state that future code paths can
   corrupt — a future contributor adding (say) a `prison` matchup
   branch cannot introduce a Petal-preamble-style double-count by
   modifying `select_pile`, because `select_pile` doesn't *modify*
   anything.
4. **No new card-name strings in engine.py.** All card identity flows
   through tags (`'lurrus'`, `'therapy'`, `'led'`). `tools/check_
   abstraction.py` will reject any commit that violates this; the
   pre-commit ratchet is the structural enforcement.
5. **Companion zone is a new state slot.** It must be cleared by
   `GameState.__init__` and serialized by `game_replay.py` (else
   replays will desync). Phase A's failing test must check both
   game start AND replay round-trip.

A separate risk: the `select_pile` decision tree at §3.3 can grow
unboundedly as new matchups are added. Mitigation: enforce that any
new branch lands with a unit test naming the rule (e.g.,
`test_select_pile_vs_dnt_picks_wraith_pile`), not the card. The
abstraction-baseline ratchet at `tools/abstraction_baseline.json`
should be inspected when this module lands — adding `select_pile`
should not unlock new card-name leaks elsewhere.

---

## 8. Implementation-gate checklist

For the future implementer (could be a different session, no shared
context):

- [ ] All four CLAUDE.md abstraction-contract questions answered for
      each phase before writing the diff.
- [ ] Phase A's failing test is in the same commit as Phase A's fix.
      Test goes red first; commit only after test goes green.
- [ ] Phase D's wiring point preserves byte-identical behavior on the
      `OraclePile` default — verify by replaying a fixed-seed
      `doomsday vs storm` game from before/after.
- [ ] No new `card.name == "X"` outside `decks/` and `import_deck.py`.
      Run `python tools/check_abstraction.py` before each commit.
- [ ] `python3 tools/regression_sweep.py` passes after Phase F.
- [ ] Open follow-up issue if `select_pile` accumulates a 5th branch —
      that's the signal to extract `decks/_pile_registry.py` analogous
      to `deck_registry.py`.
