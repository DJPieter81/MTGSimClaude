"""
clock.py — Clock-based evaluation helper (zero deps).

Every creature, removal, and burn spell can be scored by clock-delta:
the change in "turns until opponent is dead" if we resolve it.

This is a composable replacement for the categorical classify_threat()
in interaction.py (MUST/HIGH/MED/LOW → +3.5/+1.2/+0.3/-0.1).

Pure computation against Card / Permanent shapes from rules.py —
does NOT import engine, game, or sim. Safe to adopt incrementally.

    combat_clock(opp_life, power) -> int          # ceil(life / max(1,power))
    board_clock(our_c, opp_c, opp_life) -> int    # net clock from board
    spell_clock_delta(spell, state) -> float      # clock shaved off / added
    classify_threat_by_clock(creature, opp_state) -> float  # MUST/HIGH/MED/LOW
"""
from __future__ import annotations
import math
from typing import Iterable, Optional, Any

# ─────────────────────────────────────────────
# Constants — categorical → clock-delta mapping
# ─────────────────────────────────────────────

DELTA_MUST = 3.5    # combo / win-con — resolve = likely lose
DELTA_HIGH = 1.2    # engine / lock / haste / big threat
DELTA_MED  = 0.3    # fair creature / removal
DELTA_LOW  = -0.1   # cantrip / ritual (slight negative: wastes their mana)

INF_CLOCK = 99      # sentinel: "no clock" (no attackers / dead opp)


# ─────────────────────────────────────────────
# Helpers for duck-typed Permanent-ish objects
# ─────────────────────────────────────────────

def _is_attacker(perm) -> bool:
    """Can this permanent attack this combat? Mirrors Permanent.can_attack()."""
    if getattr(perm, 'tapped', False):
        return False
    card = getattr(perm, 'card', None)
    haste = getattr(card, 'haste', False) if card else False
    if getattr(perm, 'summoning_sick', False) and not haste:
        return False
    # Must actually be a creature with power > 0
    if card is not None and not card.is_creature():
        return False
    return getattr(perm, 'power', 0) > 0


def _effective_power(perms: Iterable) -> int:
    """Sum of power of creatures that can attack right now."""
    return sum(getattr(p, 'power', 0) for p in perms if _is_attacker(p))


# ─────────────────────────────────────────────
# Core API
# ─────────────────────────────────────────────

def combat_clock(opp_life: int, effective_power: int) -> int:
    """
    Turns-to-lethal assuming each combat deals `effective_power` damage.
    ceil(opp_life / max(1, effective_power)).

    opp_life <= 0 -> 0 (already dead).
    effective_power <= 0 -> INF_CLOCK (no clock).
    """
    if opp_life <= 0:
        return 0
    if effective_power <= 0:
        return INF_CLOCK
    return math.ceil(opp_life / effective_power)


def board_clock(player_creatures: Iterable,
                opp_creatures: Iterable,
                opp_life: int) -> int:
    """
    Net clock from a board state:  turns until our side kills opponent,
    accounting crudely for blockers (the opponent's biggest blocker
    absorbs one attacker of roughly equal toughness per turn).

    Not combat-simulation accurate — a fast heuristic for strategy scoring.
    """
    our_attackers = sorted(
        (p for p in player_creatures if _is_attacker(p)),
        key=lambda p: getattr(p, 'power', 0),
        reverse=True,
    )
    their_blockers = sorted(
        list(opp_creatures),
        key=lambda p: getattr(p, 'toughness', 0),
        reverse=True,
    )

    # Remove one attacker per blocker whose toughness >= attacker.power.
    # (Crude: assumes they block the biggest threats first.)
    surviving = []
    blockers = list(their_blockers)
    for atk in our_attackers:
        matched = None
        for i, blk in enumerate(blockers):
            if getattr(blk, 'toughness', 0) >= getattr(atk, 'power', 0):
                matched = i
                break
        if matched is not None:
            blockers.pop(matched)
        else:
            surviving.append(atk)

    eff_power = sum(getattr(p, 'power', 0) for p in surviving)
    return combat_clock(opp_life, eff_power)


def spell_clock_delta(spell, board_state: Optional[Any] = None) -> float:
    """
    Clock-delta of casting `spell` now. Positive = we win sooner.

    board_state is an optional duck-typed object with:
        .our_creatures, .opp_creatures, .opp_life, .our_life
    If absent, falls back to rough heuristics based on the card.

    Covered cases:
      - Burn to the face: damage / current_eff_power ~= turns shaved
      - Removal: delta = clock_before - clock_after (blocker removed)
      - New creature: adds its power (reduces clock) — positive for us
      - Cantrip/ritual: 0 (they don't change the clock directly)
    """
    card = getattr(spell, 'card', spell)  # accept Card or Permanent

    # ── Burn to face ──────────────────────────────────
    burn = _burn_damage(card)
    if burn > 0 and board_state is not None:
        opp_life = getattr(board_state, 'opp_life', 20)
        our_power = _effective_power(getattr(board_state, 'our_creatures', []))
        before = combat_clock(opp_life, our_power) if our_power else INF_CLOCK
        after = combat_clock(opp_life - burn, our_power) if our_power else INF_CLOCK
        if before == INF_CLOCK:
            # No board: burn still progresses; approximate as life fraction
            return burn / 3.0
        return float(before - after)
    if burn > 0:
        return burn / 3.0  # rough: Bolt ~= 1 turn shaved

    # ── Removal ──────────────────────────────────────
    if getattr(card, 'is_removal', False) and board_state is not None:
        opp_creatures = list(getattr(board_state, 'opp_creatures', []))
        our_creatures = list(getattr(board_state, 'our_creatures', []))
        opp_life = getattr(board_state, 'our_life', 20)   # our life from their POV
        before = board_clock(opp_creatures, our_creatures, opp_life)
        # Remove the biggest attacker
        if opp_creatures:
            biggest = max(opp_creatures, key=lambda p: getattr(p, 'power', 0))
            after_list = [p for p in opp_creatures if p is not biggest]
            after = board_clock(after_list, our_creatures, opp_life)
            # Their clock getting longer = positive for us
            return float(after - before)
        return 0.0
    if getattr(card, 'is_removal', False):
        return DELTA_MED  # heuristic fallback

    # ── New creature ─────────────────────────────────
    if card.is_creature():
        power = getattr(card, 'base_power', 0)
        haste = getattr(card, 'haste', False)
        if board_state is not None:
            opp_life = getattr(board_state, 'opp_life', 20)
            our_power = _effective_power(getattr(board_state, 'our_creatures', []))
            before = combat_clock(opp_life, our_power) if our_power else INF_CLOCK
            # Haste adds now; non-haste starts attacking next turn (approx: same)
            after_power = our_power + power
            after = combat_clock(opp_life, after_power) if after_power else INF_CLOCK
            if before == INF_CLOCK and after == INF_CLOCK:
                return float(power) * 0.3
            if before == INF_CLOCK:
                return float(20 - after)  # establishing clock from nothing
            delta = before - after
            if not haste:
                delta *= 0.7  # discount for sickness
            return float(delta)
        return float(power) * 0.3

    # ── Everything else: no direct clock change ─────
    return 0.0


def classify_threat_by_clock(creature, opp_state: Optional[Any] = None) -> float:
    """
    Clock-delta replacement for interaction.classify_threat() categorical output.
    Returns a float in the spirit of MUST/HIGH/MED/LOW → +3.5/+1.2/+0.3/-0.1.

    `creature` is a Card (incoming spell) or Permanent (already on battlefield).
    `opp_state` is the OPPONENT's PlayerState (whose life / board we measure).
    """
    card = getattr(creature, 'card', creature)

    # Combo pieces and win conditions — resolving them ends the game.
    if getattr(card, 'is_combo_piece', False) or getattr(card, 'win_condition', False):
        return DELTA_MUST

    # Lock pieces / engines / mass removal — snowball advantage.
    if getattr(card, 'lock_piece', False):       return DELTA_HIGH
    if getattr(card, 'engine', False):           return DELTA_HIGH
    if getattr(card, 'is_mass_removal', False):  return DELTA_HIGH
    if getattr(card, 'draw_trigger', False):     return DELTA_HIGH

    # Haste creatures attack now — immediate clock pressure.
    if card.is_creature() and getattr(card, 'haste', False):
        return DELTA_HIGH

    # Big (CMC5+) finishers.
    if getattr(card, 'cmc', 0) >= 5:
        return DELTA_HIGH

    # Decent creatures (CMC2+).
    if card.is_creature() and getattr(card, 'cmc', 0) >= 2:
        # Use their actual power to refine: 3+ power = HIGH, else MED
        if getattr(card, 'base_power', 0) >= 3:
            return DELTA_HIGH
        return DELTA_MED

    # Removal / cheap creatures.
    if getattr(card, 'is_removal', False):  return DELTA_MED
    if card.is_creature():                  return DELTA_MED

    # Cantrips, rituals, nothing-burgers.
    return DELTA_LOW


# ─────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────

def _burn_damage(card) -> int:
    """Rough damage-to-face for known burn spells, by tag/name."""
    tag = getattr(card, 'tag', '') or ''
    name = getattr(card, 'name', '') or ''
    key = (tag + '|' + name).lower()
    # Common Legacy burn
    if 'bolt' in key:              return 3
    if 'chain_lightning' in key or 'chain lightning' in key: return 3
    if 'lava_spike' in key or 'lava spike' in key: return 3
    if 'fireblast' in key:         return 4
    if 'price_of_progress' in key or 'price of progress' in key: return 4
    if 'skewer' in key:            return 3
    if 'shock' in key:             return 2
    if 'searing_blaze' in key or 'searing blaze' in key: return 3
    if 'rift_bolt' in key or 'rift bolt' in key: return 3
    return 0


# ─────────────────────────────────────────────
# Test harness
# ─────────────────────────────────────────────

if __name__ == '__main__':
    passed = 0
    failed = 0

    def check(label, got, expected, tol=0.0):
        global passed, failed
        ok = (abs(got - expected) <= tol) if tol else (got == expected)
        mark = 'PASS' if ok else 'FAIL'
        print(f'  [{mark}] {label}: got={got}, expected={expected}')
        if ok: passed += 1
        else:  failed += 1

    # Minimal duck-typed stand-ins (avoid importing rules.py)
    class _FakeCard:
        def __init__(self, name='X', cmc=1, power=0, toughness=0, creature=True,
                     haste=False, removal=False, mass_removal=False,
                     combo=False, winc=False, lock=False, engine=False,
                     draw=False, tag='', mdfc=False):
            self.name = name; self.cmc = cmc
            self.base_power = power; self.base_toughness = toughness
            self._creature = creature
            self.haste = haste
            self.is_removal = removal
            self.is_mass_removal = mass_removal
            self.is_combo_piece = combo
            self.win_condition = winc
            self.lock_piece = lock
            self.engine = engine
            self.draw_trigger = draw
            self.tag = tag
            self.is_mdfc_land = mdfc
        def is_creature(self): return self._creature
        def is_land(self): return False

    class _FakePerm:
        def __init__(self, card, tapped=False, sick=False):
            self.card = card; self.tapped = tapped; self.summoning_sick = sick
        @property
        def power(self): return self.card.base_power
        @property
        def toughness(self): return self.card.base_toughness

    class _State:
        def __init__(self, our=(), opp=(), our_life=20, opp_life=20):
            self.our_creatures = list(our); self.opp_creatures = list(opp)
            self.our_life = our_life; self.opp_life = opp_life

    print('-- combat_clock --')
    check('20 life, 0 power -> INF', combat_clock(20, 0), INF_CLOCK)
    check('20 life, 3 power -> 7',   combat_clock(20, 3), 7)
    check('20 life, 5 power -> 4',   combat_clock(20, 5), 4)
    check('10 life, 4 power -> 3',   combat_clock(10, 4), 3)
    check('0 life, 3 power -> 0',    combat_clock(0, 3), 0)

    print('-- board_clock --')
    goyf  = _FakePerm(_FakeCard('Goyf', power=4, toughness=5))
    delver= _FakePerm(_FakeCard('Delver', power=3, toughness=2))
    thals = _FakePerm(_FakeCard('Thalassic', power=1, toughness=1))
    check('3+4 power vs no blockers, 20 life -> 3',
          board_clock([goyf, delver], [], 20), 3)
    # Blocker with toughness 5 eats Goyf; delver (3) still swings
    blocker_big = _FakePerm(_FakeCard('Wall', power=0, toughness=5, creature=True))
    check('Goyf blocked, only Delver(3) through, 20 life -> 7',
          board_clock([goyf, delver], [blocker_big], 20), 7)

    print('-- spell_clock_delta --')
    # Lightning Bolt face: 3 dmg, opp at 20, we have 3 power on board
    bolt = _FakeCard('Lightning Bolt', cmc=1, creature=False, tag='bolt')
    st = _State(our=[delver], opp=[], opp_life=20)
    # before = ceil(20/3)=7, after = ceil(17/3)=6, delta = 1
    check('Bolt with 3 power board, opp 20 -> +1',
          spell_clock_delta(bolt, st), 1.0, tol=0.01)
    # New 3-power haste creature with empty board vs 20 life
    goblin = _FakeCard('Goblin Guide', cmc=1, power=2, toughness=2, haste=True)
    st2 = _State(our=[], opp=[], opp_life=20)
    d = spell_clock_delta(goblin, st2)
    check('Haste 2/2 on empty board (positive delta)', d > 0, True)
    # Cantrip -> 0
    brain = _FakeCard('Brainstorm', cmc=1, creature=False, tag='brainstorm')
    check('Brainstorm delta == 0', spell_clock_delta(brain, st), 0.0)

    print('-- classify_threat_by_clock --')
    storm_kill = _FakeCard('Tendrils', cmc=4, creature=False, winc=True)
    check('Win-condition -> +3.5', classify_threat_by_clock(storm_kill), DELTA_MUST)
    chalice = _FakeCard('Chalice', cmc=0, creature=False, lock=True)
    check('Lock piece -> +1.2', classify_threat_by_clock(chalice), DELTA_HIGH)
    vial = _FakeCard('AEther Vial', cmc=1, creature=False, engine=True)
    check('Engine -> +1.2', classify_threat_by_clock(vial), DELTA_HIGH)
    hasty = _FakeCard('Ragavan', cmc=1, power=2, toughness=1, haste=True)
    check('Haste creature -> +1.2', classify_threat_by_clock(hasty), DELTA_HIGH)
    goyfc = _FakeCard('Goyf', cmc=2, power=4, toughness=5)
    check('CMC2 3+ power -> +1.2', classify_threat_by_clock(goyfc), DELTA_HIGH)
    delvec = _FakeCard('Delver', cmc=1, power=1, toughness=1)
    check('CMC1 1/1 creature -> +0.3', classify_threat_by_clock(delvec), DELTA_MED)
    brainc = _FakeCard('Brainstorm', cmc=1, creature=False)
    check('Cantrip -> -0.1', classify_threat_by_clock(brainc), DELTA_LOW)

    print()
    print(f'{passed} passed, {failed} failed')
    if failed == 0:
        print('all pass')
