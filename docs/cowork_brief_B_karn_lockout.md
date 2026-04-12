# Cowork Brief B: Karn the Great Creator lockout

## One-sentence task
Add `gs.karn_active` state + enforcement so Karn's static ability ("your opponents can't activate abilities of artifacts") actually prevents opponent artifact activations, mirroring the `gs.chalice_x` enforcement pattern.

## Why this matters
PLANNING.md §"Known Sim Limitations" lists this as a real gap. Tron/Prison/Painter decks use Karn as a lock piece, but currently Karn is modeled only as a 4-mana planeswalker body — the actual lockout effect is missing. This likely inflates opponent WRs vs Prison by ~5-10pp because fast-mana decks (Storm, Oops, Affinity, Belcher, Painter-itself) still get their Petals/Moxen off while Karn is on the board.

## Scope

### Part 1 — State field

Add to `GameState` in `game.py`:
```python
karn_active_by: Optional[str] = None
# 'b' or 'o' — which player controls Karn (None = no Karn)
# Mirror of gs.chalice_x pattern: opp-independent state that all code paths check
```

Set when Karn's +1 resolves (controller puts a creature into play — still modeled), or as a computed property:
```python
@property
def karn_active_by(self):
    if any(c.card.tag == 'karn' for c in self.p1.planeswalkers):
        return 'b'
    if any(c.card.tag == 'karn' for c in self.p2.planeswalkers):
        return 'o'
    return None
```

(Use whichever approach fits existing `bowmasters_on_board` / `orc_army` patterns in game.py.)

### Part 2 — Enforcement points

Karn's static says "your opponents can't activate abilities of artifacts that aren't mana abilities" — so mana abilities still work (you can still tap City of Traitors), but non-mana activated abilities don't.

Points to enforce (grep for each):

| Activation | Where it happens | Check to add |
|------------|------------------|--------------|
| Lotus Petal sac | `_strategy_*` functions + protagonist_turn | Skip if Karn controlled by opp |
| Mox Opal tap-for-mana | (mana ability — EXEMPT) | none |
| Chrome Mox imprint-at-cast | cast-time ability, not activated — exempt | none |
| Mishra's Bauble sacrifice | protagonist_turn | Skip if Karn controlled by opp |
| Grindstone activate | `_strategy_prison` | Skip if Karn opp |
| Painter's Servant — passive | passive, not activated — exempt | none |
| Pithing Needle | not in Legacy sim | — |
| Sensei's Divining Top | if in decks | Skip |

### Part 3 — Helper function

Add to `engine.py`:
```python
def opp_artifact_activation_blocked(gs, player) -> bool:
    """True iff Karn opponent controls Karn the Great Creator.
    CR 113.6b: static abilities work from the battlefield.
    """
    if gs.karn_active_by is None:
        return False
    player_side = 'b' if player is gs.p1 else 'o'
    return gs.karn_active_by != player_side
```

Use at every activation point.

### Part 4 — Tests

Add to `run_rules_tests()` Control 4 (new):
```
[PASS] Karn: no Karn → opp Petal sac works
[PASS] Karn: opp Karn → Petal sac blocked (card stays in hand)
[PASS] Karn: my Karn → my Petal still works
[PASS] Karn: opp Karn → Mox mana ability still works (mana ability exempt)
[PASS] Karn: opp Karn → Grindstone blocked
[PASS] Karn: opp Karn → Bauble sac blocked
[PASS] Karn removed → opp activations work again
```

## Constraints

- No hardcoded magic. Karn detection should be tag-based (`card.tag == 'karn'`) or property-based (`card.lock_piece_artifact_activation_static`).
- Don't break existing Karn wish (sideboard tutor) logic — that's controller-only.
- Run full matrix before/after at n=100 (quick spot check) to verify Prison/Painter/Tron WRs move up without breaking fair decks.

## Expected impact
- Prison: flat WR 47% → 52%-55% (more of its plan actually works)
- Painter: flat WR 40% → 45%+
- Decks running artifact mana against Prison: WR drops 3-8pp

## Branch / PR
- Branch: `claude/mtgsim-karn-lockout-<suffix>` off main.
- Title: "Karn the Great Creator — artifact activation lockout (CR 113.6b)"
- 3-4 commits: state field, helper fn + enforcement, tests, matrix re-run spot-check.

## Validation
- 7 new tests pass in run_rules_tests (147 + 7 = 154 target)
- `EXPECTED_RANGES` spot-checks still pass
- Matrix spot check: burn-vs-prison drops; storm-vs-prison drops; prison-vs-dimir climbs
