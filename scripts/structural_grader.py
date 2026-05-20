#!/usr/bin/env python3
"""
structural_grader.py — Prototype structural grader for MTGSimClaude traces.

PROTOTYPE — does NOT replace `scripts/grade_traces.py`. The point is to show
that we can derive meaningful per-domain grades from the *typed* `chosen`
field that strategies now emit (post-Phase-6 + PR #138):

    'defer', 'hold_<tag>', 'kill_<X>', 'cast_<combo>', 'entomb_<tag>',
    'combo:<path_tag>', 'attack with N <creatures>'

…instead of pattern-matching English keywords in the `reason` field (which
is gameable: a strategy could emit "protect" anywhere in `reason` and lift
its interaction grade).

Output shape matches `grade_one_local()` in `scripts/grade_traces.py`. The
graded file is written next to the trace as `<trace>_structural_graded.json`
so the two graders' outputs can coexist for comparison.

Usage:
    # Grade traces
    python3 scripts/structural_grader.py results/traces/*.json

    # Compare structural vs heuristic agreement (reads both _graded.json
    # and _structural_graded.json next to each trace)
    python3 scripts/structural_grader.py --report
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

# Allow importing llm_judge from repo root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from llm_judge import RUBRIC_DOMAINS, GRADE_SCALE  # noqa: E402
from config import _load_calibrated  # noqa: E402
from decision import (  # noqa: E402
    Decision, ComboDecision, DisruptionDecision, CombatDecision,
    ManaDecision, MulliganDecision, MetaDecision,
)

TRACE_DIR = Path(__file__).resolve().parent.parent / 'results' / 'traces'

# Promotion thresholds — calibrated via tools/calibrate_structural_thresholds.py.
# Each gates the grade promotion in one binding-constraint domain. The literal
# fallback values are the legacy hand-picked numbers; the calibrated values
# live in config/calibration.json under the `values` dict. See
# `_load_calibrated` in config.py for the resolution order.
#
# K_INTER_A          — promotes interaction grade B+ → A on wins for
#                      interaction decks when n_inter ≥ K_INTER_A.
# K_INTER_C_PLUS     — promotes interaction grade C → C+ on losses for
#                      interaction decks when n_inter ≥ K_INTER_C_PLUS.
# K_COMBO_GAME_LEN_A — game_length cap below which a winning combo deck
#                      grades A (vs B+) — i.e. "fast enough kill is A".
# K_MANA_GAME_LEN_B  — game_length cap below which a winning non-combo deck
#                      grades B+ (vs B) on mana.
# K_RAMP_A           — combo-deck mana grade promotes to A when a winning
#                      trace logs ≥ K_RAMP_A ramp tokens. Models a full
#                      ritual chain (Dark Ritual + Cabal Ritual + LED +
#                      petals → 4+ net mana events) backing the kill turn.
# K_RAMP_B_PLUS      — combo-deck mana grade promotes to B+ when a winning
#                      trace logs ≥ K_RAMP_B_PLUS ramp tokens. One ritual
#                      sub-chain is enough evidence the deck routed mana
#                      structurally rather than top-decking the win-con.
K_INTER_A          = _load_calibrated('STRUCT_K_INTER_A', 3)
K_INTER_C_PLUS     = _load_calibrated('STRUCT_K_INTER_C_PLUS', 2)
K_COMBO_GAME_LEN_A = _load_calibrated('STRUCT_K_COMBO_GAME_LEN_A', 4)
K_MANA_GAME_LEN_B  = _load_calibrated('STRUCT_K_MANA_GAME_LEN_B', 8)
K_RAMP_A           = _load_calibrated('STRUCT_K_RAMP_A', 4)
K_RAMP_B_PLUS      = _load_calibrated('STRUCT_K_RAMP_B_PLUS', 2)
# K_INTER_COMBAT_A — interaction-deck win promotes combat → A when the trace
# emits ≥ this many combat tokens (attacks + blocks + holds). Bug / dimir /
# ur_delver typically log a handful of these per game once block + hold
# wiring lands: a blocker assigned to a Murktide, a Tamiyo held back, a
# DRC cycled rather than attacking. 3 is the floor for "actively engaged
# the combat axis to win" vs lower counts that look incidental.
K_INTER_COMBAT_A   = _load_calibrated('STRUCT_K_INTER_COMBAT_A', 3)

GRADE_TO_NUM = {g: i for i, g in enumerate(GRADE_SCALE)}
NUM_TO_GRADE = {i: g for g, i in GRADE_TO_NUM.items()}

# ── Deck-class buckets ────────────────────────────────────────────────────
# Derived from `deck_registry.get_decks_in_category()` rather than literal
# sets — the prior hardcoded sets duplicated knowledge already declared in
# each plugin's `DECK_META['categories']` (see decks/*.py). Same pattern as
# `config.py:MatchupCategory` which merges _BUILTIN_* floors with
# `_registry_decks(category)`. The floors preserve membership for decks that
# don't (yet) declare the matching category — keeps the grader's existing
# canonical buckets stable when a deck file omits a category.

def _registry_decks(category):
    """Pull deck keys for `category` from the registry. Quiet fallback when
    deck_registry can't be imported (e.g. running grader from outside the
    repo root via sys.path tweaks)."""
    try:
        from deck_registry import get_decks_in_category
        return frozenset(get_decks_in_category(category))
    except ImportError:
        return frozenset()

# Built-in floors: decks the grader must classify as combo/interaction/aggro
# regardless of whether the plugin file declares the matching category.
# Justification (rule, not card-name): combo decks emit Execute tokens;
# interaction decks emit counter/discard/remove tokens; aggro decks close
# via combat tokens + spot removal. Built-in floors are the canonical
# members the grader's per-domain rules were originally calibrated against
# (see Phase 6 audit traces).
_BUILTIN_COMBO       = frozenset({
    'storm', 'doomsday', 'oops', 'belcher', 'cephalid', 'reanimator',
    'sneak_a', 'sneak_b', 'show', 'tes', 'depths',
})
_BUILTIN_INTERACTION = frozenset({
    'bug', 'dimir', 'dimir_b', 'dimir_c', 'dimir_d', 'dimir_flash',
    'ur_delver', 'ur_tempo', 'uwx', 'dnt', 'mardu',
})
_BUILTIN_AGGRO       = frozenset({
    'burn', 'goblins', 'eldrazi', 'affinity', 'ur_aggro', 'boros',
})

# Merged sets: floor ∪ category lookup. The category-lookup union with the
# floor means: any new deck plugin that declares `'combo'` / `'aggro'` /
# (`'tempo' | 'tempo_mirror' | 'control' | 'mirror'`) auto-registers into
# the right bucket without editing this file.
COMBO_DECKS       = _BUILTIN_COMBO       | _registry_decks('combo')
AGGRO_DECKS       = _BUILTIN_AGGRO       | _registry_decks('aggro')
# Interaction = any deck whose primary axis is reactive disruption.
# Today the registry expresses this through `tempo` (bug),
# `tempo_mirror` (ur_delver, ur_tempo, dimir_c/d), `control` (uwx,
# wan_shi_tong), and `mirror` (dimir family). Add new categories here as
# they appear in DECK_META rather than re-listing decks.
INTERACTION_DECKS = (
    _BUILTIN_INTERACTION
    | _registry_decks('tempo')
    | _registry_decks('tempo_mirror')
    | _registry_decks('control')
    | _registry_decks('mirror')
)

# Structured-token prefixes / values the strategies emit. Each token is a
# *de-facto API contract* between the strategy layer and any grader: it has
# a fixed meaning that does not depend on prose elsewhere in the entry.
EXECUTE_PREFIXES = ('combo:', 'kill_', 'cast_doomsday', 'cast_spy',
                    'entomb_', 'oracle_win', 't1_kill', 't2_kill')
# HOLD_PREFIXES — combo-axis "hold a piece" tokens (e.g. `hold_fow` to
# protect storm's plan). The same `hold_<tag>` prefix is ALSO emitted by
# CombatDecision(kind='hold').to_token() on the combat axis (defender
# crouching a creature back to block). The two are disambiguated by
# `phase`: combat-axis hold tokens carry `phase='combat'`; combo-axis hold
# tokens carry the combo-phase from the gameplan (`'combo'`/`'protect'`).
# `_is_hold` returns True for both prefixes; `_count_structural` uses the
# phase guard to route the dict-path entry to the correct bucket so we
# don't double-credit combat holds on the combo axis.
HOLD_PREFIXES = ('hold_',)
DEFER_TOKENS = {'defer'}
COUNTER_PREFIXES = ('counter_',)   # interaction decks log counter_<spell>_with_<ctr>
# Discard / extract share an axis: both empty out opponent's hand or graveyard
# of a specific card, denying access to that resource. The grader bucket is
# 'discard' for both; the dict-path predicate accepts either prefix so
# pre-algebra trace JSON with `extract_*` strings still rolls in.
DISCARD_PREFIXES = ('discard_', 'extract_')
# Removal includes land destruction: a Wasteland that removes a key dual is
# resource-denial on the same axis as a Push that removes a Goyf. Strategic
# tokens for both kinds share the 'removal' bucket via this prefix set.
REMOVAL_PREFIXES = ('remove_', 'land_destroy_')
TRIED_COMBO_PREFIXES = ('tried_combo:',)  # combo decks log when a piece was
                                          # played but the full kill did not fire
# Ramp tokens: combo decks emit `mana_ramp_<N>` whenever a ritual / petal /
# LED / Spirit-Guide produces net mana. The prefix-matched legacy path
# buckets identically with the typed `ManaDecision(kind='ramp')` fast-path
# so trace JSON written before this wiring still credits the deck's mana
# subscore. Driven by `ManaDecision.to_token()` in decision.py.
RAMP_PREFIXES = ('mana_ramp_',)
# Meta tokens: deck made a *play-around* decision — explicitly held / deferred
# its own plan because of a specific named opponent threat (fow, daze,
# surgical, bowmasters, …). The token is `meta_<kind>_<threat_tag>` —
# `MetaDecision(kind='play_around', threat_tag=…).to_token()`. Single prefix
# (vs prefix tuple) keeps the contract narrow: the only meta-axis structural
# signal today is play-around / sideboard.
META_PREFIX = 'meta_'
ATTACK_PREFIX = 'attack'  # 'attack with N goblins'
# BLOCK_PREFIXES — combat-axis "defender assigns blocker" tokens emitted by
# CombatDecision(kind='block').to_token() == 'block_<attacker_tag>'.
# Distinct from `HOLD_PREFIXES` (combo-axis) by phase: block tokens always
# carry `phase='combat'`. The typed isinstance path is unambiguous; the
# legacy dict path relies on the prefix alone (no combo decision uses
# `block_*`), so the two never collide.
BLOCK_PREFIXES = ('block_',)
COMBAT_PHASE = 'combat'


# ─── token-level structural counts ────────────────────────────────────────

def _is_execute(chosen: str) -> bool:
    """Decision indicates the strategy *fired* its combo plan."""
    if not chosen:
        return False
    return any(chosen.startswith(p) for p in EXECUTE_PREFIXES)


def _is_hold(chosen: str) -> bool:
    """Decision indicates the strategy *withheld* a card (protection / disruption)."""
    if not chosen:
        return False
    return any(chosen.startswith(p) for p in HOLD_PREFIXES)


def _is_defer(chosen: str) -> bool:
    """Decision indicates the strategy *passed* on firing this turn."""
    return chosen in DEFER_TOKENS


def _is_counter(chosen: str) -> bool:
    """Decision indicates the strategy *countered* an opposing spell."""
    if not chosen:
        return False
    return any(chosen.startswith(p) for p in COUNTER_PREFIXES)


def _is_discard(chosen: str) -> bool:
    """Decision indicates the strategy *denied a specific card to opp* —
    either forced discard from hand (Thoughtseize, Inquisition, Hymn) or
    extract from graveyard (Surgical Extraction, Endurance, Leyline). Both
    bucket the same axis: opponent loses access to a known card."""
    if not chosen:
        return False
    return any(chosen.startswith(p) for p in DISCARD_PREFIXES)


def _is_removal(chosen: str) -> bool:
    """Decision indicates the strategy *removed* an opposing permanent.
    Includes spot-removal spells on creature / planeswalker / artifact /
    enchantment (Push, STP, Snuff, Dismember, AD, Bolt-as-removal, Solitude,
    Skyclave Apparition, Fury, Deluge, Pyro/Hydroblast, Force of Vigor) and
    land destruction (Wasteland, Strip Mine, Ghost Quarter). Both kinds
    share the 'removal' bucket because they're the same axis: deny a
    permanent on the opposing battlefield."""
    if not chosen:
        return False
    return any(chosen.startswith(p) for p in REMOVAL_PREFIXES)


def _is_tried_combo(chosen: str) -> bool:
    """Decision indicates a combo piece was played but the kill did not fire.
    Partial-credit signal for combo decks whose plan was disrupted."""
    if not chosen:
        return False
    return any(chosen.startswith(p) for p in TRIED_COMBO_PREFIXES)


def _is_ramp(chosen: str) -> bool:
    """Decision indicates the strategy *generated net mana* from a ritual /
    petal / LED / Spirit Guide / Mox / Tinder. Mechanic: any non-land mana
    source that yields positive net mana after paying its cost. Combo decks
    chain these (Dark Ritual → Cabal Ritual → LED, etc.) to reach the kill
    cost on the turn the win-condition resolves. Prefix `mana_ramp_<N>` is
    `ManaDecision(kind='ramp', mana_value=N).to_token()`.
    """
    if not chosen:
        return False
    return any(chosen.startswith(p) for p in RAMP_PREFIXES)


def _is_combat_decision(decision: dict) -> bool:
    """Combat-axis decision: either tagged with combat phase, attack action,
    or block-assignment token.

    Block tokens (`block_<tag>`) always carry `phase='combat'`, so the phase
    check above already catches them. The prefix check exists for legacy
    trace JSON that may omit phase (e.g. early hand-rolled fixtures) so the
    grader still buckets the decision correctly.
    """
    if decision.get('phase') == COMBAT_PHASE:
        return True
    chosen = decision.get('chosen', '') or ''
    return (chosen.startswith(ATTACK_PREFIX)
            or any(chosen.startswith(p) for p in BLOCK_PREFIXES))


def _is_meta(chosen: str) -> bool:
    """Decision indicates the strategy *played around* a named opponent threat
    (FoW / Daze / Surgical / Bowmasters / …) or made a sideboard decision.
    The token format is `meta_<kind>_<threat>` — `MetaDecision.to_token()`.

    The predicate is a *strict prefix* match: prose `reason='play around fow'`
    with `chosen='pass'` does NOT increment the meta count. The grader's
    gameability defense lives in this prefix being the only path to the
    bucket, parallel to `_is_ramp` (`mana_`) and `_is_counter` (`counter_`).
    """
    if not chosen:
        return False
    return chosen.startswith(META_PREFIX)


# ─── typed Decision → bucket-name maps ────────────────────────────────────
#
# The grader's bucket names (`counter`, `discard`, `removal`, `execute`,
# `hold`, `defer`, `tried_combo`, `combat`) predate the typed algebra; the
# maps below pin Decision.kind to the existing bucket so `_count_structural`
# stays a single dict the per-domain `_grade_*` rules can consume.
_DISRUPTION_KIND_TO_BUCKET = {
    'counter':      'counter',
    'discard':      'discard',
    'remove':       'removal',
    # extract = exile-from-hand variant of discard; bucketed identically so
    # interaction-deck n_inter aggregates both.
    'extract':      'discard',
    # land_destroy = removal of a *land* permanent; bucketed with removal so
    # midrange/aggro decks credit it on the removal axis.
    'land_destroy': 'removal',
}
_COMBO_KIND_TO_BUCKET = {
    'execute': 'execute',
    'hold':    'hold',
    'defer':   'defer',
    'tried':   'tried_combo',
}


def _count_structural(decisions, deck1: str | None = None) -> dict:
    """Bucket decisions by structural token. Returns counts only — no keyword
    pattern matching on `reason`.

    Accepts a mixed list of typed `Decision` instances and legacy dict
    entries. Typed instances go through the `isinstance(d, Decision)` fast
    path (no string-prefix matching); dict entries fall through to the
    legacy `_is_*` prefix predicates so JSON traces written before the
    Decision algebra still grade identically.

    When `deck1` is provided, only decisions emitted by that deck count toward
    the structural buckets. Without this filter, an opponent's typed decision
    (e.g. storm casting TS that hits bug's FoW) would be credited to deck1's
    score — the wrong attribution. The grader's per-domain rules judge
    deck1's play, so its counts must only see deck1's decisions.
    """
    if deck1 is not None:
        decisions = [d for d in decisions
                     if (d.deck if isinstance(d, Decision) else d.get('deck')) == deck1]
    counts = {
        'execute': 0, 'hold': 0, 'defer': 0, 'counter': 0, 'discard': 0,
        'removal': 0, 'tried_combo': 0, 'ramp': 0, 'meta': 0,
        'combat': 0, 'combo_phase': 0, 'protect_phase': 0,
        'total': len(decisions),
    }
    for d in decisions:
        # ─── typed Decision fast-path ─────────────────────────────────────
        if isinstance(d, Decision):
            phase = d.phase
            if isinstance(d, DisruptionDecision):
                bucket = _DISRUPTION_KIND_TO_BUCKET.get(d.kind)
                if bucket is not None:
                    counts[bucket] += 1
            elif isinstance(d, ComboDecision):
                bucket = _COMBO_KIND_TO_BUCKET.get(d.kind)
                if bucket is not None:
                    counts[bucket] += 1
            elif isinstance(d, CombatDecision):
                counts['combat'] += 1
            elif isinstance(d, ManaDecision):
                # Only `ramp` rolls into a grader bucket today. `fix`, `burn`,
                # and `keep_open` are scaffold kinds — see decision.py — that
                # the grader doesn't credit until a per-domain rule asks for
                # them. Strict isinstance + kind check keeps the bucket sole
                # source-of-truth: prose `reason='ramp'` cannot fake it.
                if d.kind == 'ramp':
                    counts['ramp'] += 1
            elif isinstance(d, MetaDecision):
                # MetaDecision is the meta-axis structural signal — the deck
                # explicitly held / deferred its plan because of a named
                # opponent threat. Both `play_around` and `sideboard` kinds
                # roll into the meta bucket today; finer per-kind splits can
                # come if the grader later wants to weight them differently.
                counts['meta'] += 1
            # MulliganDecision: no axis bucket yet — only the
            # `total` and phase counters track it.
            if phase == 'combo':
                counts['combo_phase'] += 1
            if phase == 'protect' or phase == 'disruption':
                counts['protect_phase'] += 1
            continue

        # ─── legacy dict path (pre-algebra trace JSON) ────────────────────
        chosen = d.get('chosen', '') or ''
        phase = d.get('phase')
        if _is_execute(chosen):
            counts['execute'] += 1
        # Combo-axis `hold_<tag>` and combat-axis `hold_<tag>` share a prefix;
        # the phase guard routes combat holds to the `combat` bucket only.
        # Without this guard, a typed `CombatDecision(kind='hold')` that lost
        # its isinstance type during JSON serialization would double-count
        # (combo hold AND combat axis).
        if _is_hold(chosen) and phase != COMBAT_PHASE:
            counts['hold'] += 1
        if _is_defer(chosen):
            counts['defer'] += 1
        if _is_counter(chosen):
            counts['counter'] += 1
        if _is_discard(chosen):
            counts['discard'] += 1
        if _is_removal(chosen):
            counts['removal'] += 1
        if _is_tried_combo(chosen):
            counts['tried_combo'] += 1
        if _is_ramp(chosen):
            counts['ramp'] += 1
        if _is_meta(chosen):
            counts['meta'] += 1
        if _is_combat_decision(d):
            counts['combat'] += 1
        if phase == 'combo':
            counts['combo_phase'] += 1
        if phase == 'protect' or phase == 'disruption':
            counts['protect_phase'] += 1
    return counts


# ─── per-domain grading from structural counts ────────────────────────────

def _grade_mulligan(trace: dict) -> tuple[str, str]:
    p1_won = trace.get('winner') == 'p1'
    p1_mulls = trace.get('p1_mulls', 0)
    if p1_mulls == 0:
        g = 'B+' if p1_won else 'B'
        j = f"Kept 7; {'won' if p1_won else 'lost'} — opening hand was {'adequate' if p1_won else 'possibly too greedy'}"
    elif p1_mulls == 1:
        g = 'B' if p1_won else 'C+'
        j = f"Mulled to 6; {'still won' if p1_won else 'card disadvantage contributed to loss'}"
    else:
        g = 'C' if p1_won else 'D'
        j = f"Mulled to {7 - p1_mulls}; aggressive mulligan strategy {'paid off' if p1_won else 'backfired'}"
    return g, j


def _grade_mana(trace: dict, counts: dict | None = None) -> tuple[str, str]:
    """Grade the mana axis. Combo decks now consume the ramp-token count
    (`counts['ramp']`); a winning combo trace with ≥ K_RAMP_A ramp tokens
    grades A (full ritual chain). Non-combo branches are unchanged from the
    pre-wiring contract.

    `counts` is optional for backward compatibility — callers (tests / older
    graders) that pass only the trace dict fall back to the prior game-length
    branch on combo wins.
    """
    deck1 = trace.get('deck1', '')
    p1_won = trace.get('winner') == 'p1'
    game_length = trace.get('game_length', 10)
    n_ramp = (counts or {}).get('ramp', 0)
    if deck1 in COMBO_DECKS:
        if p1_won:
            # Combo wins: ramp-token count is the load-bearing signal. A full
            # ritual chain (≥ K_RAMP_A) → A; a sub-chain (≥ K_RAMP_B_PLUS) or
            # a fast kill (game_length ≤ 4 — the prior threshold from
            # K_COMBO_GAME_LEN_A) → A only via game_length, else B+. Composed
            # as max(ramp-based, length-based) so a wired callsite never
            # regresses a trace below its pre-wire grade.
            if n_ramp >= K_RAMP_A or game_length <= 4:
                return ('A',
                        f"{n_ramp} ramp tokens, T{game_length} kill — "
                        f"{'full ritual chain' if n_ramp >= K_RAMP_A else 'fast kill'}"
                        f" backed the win")
            if n_ramp >= K_RAMP_B_PLUS:
                return ('B+',
                        f"{n_ramp} ramp tokens — partial ritual chain on a "
                        f"T{game_length} win")
            return ('B+',
                    f"Won but took {game_length} turns — mana was adequate "
                    f"({n_ramp} ramp tokens)")
        return ('C+' if game_length <= 6 else 'C',
                f"Lost in {game_length} turns — possible mana sequencing "
                f"issues ({n_ramp} ramp tokens)")
    if p1_won:
        return ('B+' if game_length <= K_MANA_GAME_LEN_B else 'B',
                f"Resource deployment supported a T{game_length} win")
    return ('B' if game_length >= K_MANA_GAME_LEN_B else 'C+',
            f"{'Adequate' if game_length >= K_MANA_GAME_LEN_B else 'Suboptimal'} mana utilization over {game_length} turns")


def _grade_combat(trace: dict, counts: dict) -> tuple[str, str]:
    """Combat grading from structural combat-phase / attack / block / hold
    tokens, no English keywords.

    For aggro decks that won, spot-removal tokens (`remove_*`) count toward
    the combat tally too: a bolt or push that killed an opposing blocker
    *enabled* the swing that closed the game. Without crediting removal
    here, an aggro deck that cleared a Bowmasters/Goyf with a Bolt before
    attacking would look like it skipped combat decisioning.

    For interaction decks (tempo / control), combat decisions include block
    assignments (defender chooses a blocker) and hold-back (defender keeps a
    creature in the back row to block on the swing-back). A winning
    interaction deck with K_INTER_COMBAT_A+ combat tokens grades A —
    typically a bug / dimir / ur_delver game where the deck blocked the
    threat AND held its own Murktide / Tamiyo back.
    """
    deck1 = trace.get('deck1', '')
    p1_won = trace.get('winner') == 'p1'
    n_combat = counts['combat']
    n_removal = counts.get('removal', 0)

    if deck1 in COMBO_DECKS:
        # Combo decks: combat is secondary; absence is neutral.
        return ('B',
                f"Combo deck — {n_combat} combat decision(s); combat is not the primary axis")
    if deck1 in AGGRO_DECKS:
        # Aggro decks: roll spot-removal into the combat tally on wins —
        # a bolt that cleared a blocker is a combat-enabling decision.
        n_combat_aggro = n_combat + (n_removal if p1_won else 0)
        if p1_won and n_combat_aggro >= 1:
            return 'A', (f"Aggro plan with {n_combat} combat + {n_removal} remove "
                         f"decision(s) — pressure converted to win")
        if p1_won:
            return 'B+', "Aggro plan won without surfaced combat decisions (lethal via burn / direct damage)"
        if n_combat >= 1:
            return 'B-', f"Aggro plan logged {n_combat} combat decision(s) but lost — opponent stabilized"
        return 'C', "Aggro deck without combat decisions — combat axis was inactive"
    if deck1 in INTERACTION_DECKS:
        # Interaction decks: combat is a real axis — block-assignment and
        # hold-back decisions matter as much as the attack tally. A winning
        # tempo deck with ≥ K_INTER_COMBAT_A combat tokens (attacks + blocks
        # + holds) grades A; a leaner game grades B+ on the same win.
        if p1_won:
            if n_combat >= K_INTER_COMBAT_A:
                return ('A',
                        f"{n_combat} combat decision(s) (attacks/blocks/holds) — "
                        f"defensive crouch + counter-clock converted to win")
            return ('B+' if n_combat >= 1 else 'B',
                    f"{n_combat} combat decision(s); "
                    f"{'combat contributed to win' if n_combat else 'won via non-combat means'}")
        return ('C+' if n_combat >= 1 else 'C',
                f"{n_combat} combat decision(s); combat axis "
                f"{'engaged but insufficient' if n_combat else 'inactive'}")
    # Mid-range / other
    if p1_won:
        return ('B+' if n_combat >= 1 else 'B',
                f"{n_combat} combat decision(s); {'combat contributed to win' if n_combat else 'won via non-combat means'}")
    return ('C+' if n_combat >= 1 else 'C',
            f"{n_combat} combat decision(s); combat axis {'engaged but insufficient' if n_combat else 'inactive'}")


def _grade_combo(trace: dict, counts: dict) -> tuple[str, str]:
    """Combo grading from Execute-token counts, no English keywords.

    Combo-deck losses are promoted one grade (D→C+, C→C+ kept at C+, C+→
    well the rule below preserves the existing C+ for length>5 and only
    lifts the length≤5 D→C+ case) when at least one `tried_combo:<tag>`
    partial-credit token was logged. Encodes "played pieces but kill was
    disrupted" as distinct from "did nothing".
    """
    deck1 = trace.get('deck1', '')
    p1_won = trace.get('winner') == 'p1'
    game_length = trace.get('game_length', 10)
    n_exec = counts['execute']
    n_tried = counts.get('tried_combo', 0)

    if deck1 not in COMBO_DECKS:
        return 'B', "Non-combo deck — domain not primary axis"

    if n_exec == 0:
        # The deck's typed combo plan never fired. If at least one combo
        # piece was played (tried_combo token), promote from baseline C to C+.
        if n_tried >= 1:
            return ('C+',
                    f"No Execute token, but {n_tried} tried_combo token(s) — "
                    f"pieces deployed, kill disrupted")
        return 'C', "No combo Execute decision logged — deck did not fire its plan"
    if p1_won and game_length <= 6:
        return ('A+' if game_length <= K_COMBO_GAME_LEN_A else 'A',
                f"{n_exec} Execute decision(s); combo resolved on T{game_length}")
    if p1_won:
        return 'B+', f"{n_exec} Execute decision(s); combo resolved late on T{game_length}"
    if game_length <= 5:
        # One-grade promotion: D → C+ when at least one tried_combo was emitted.
        if n_tried >= 1:
            return ('C+',
                    f"{n_exec} Execute + {n_tried} tried_combo; "
                    f"lost on T{game_length} — disrupted early but pieces deployed")
        return 'D', f"{n_exec} Execute decision(s) but lost on T{game_length} — disrupted early"
    # game_length > 5
    if n_tried >= 1:
        return ('C',
                f"{n_exec} Execute + {n_tried} tried_combo; "
                f"lost on T{game_length} — combo could not close but pieces deployed")
    return 'C+', f"{n_exec} Execute decision(s) but lost on T{game_length} — combo could not close"


def _grade_interaction(trace: dict, counts: dict) -> tuple[str, str]:
    """Interaction grading from Hold/Defer/Counter-token counts, no English keywords.

    For interaction decks (bug, dimir, ur_delver, …), the relevant
    structural signal is `counter_<spell>_with_<ctr>` tokens emitted by
    `engine._try_counter_any` whenever the deck actually fires a
    counter spell. Hold/Defer tokens (a combo-deck signal) also count.

    For combo decks, Hold/Defer remains the primary signal.
    """
    deck1 = trace.get('deck1', '')
    p1_won = trace.get('winner') == 'p1'
    n_hold = counts['hold']
    n_defer = counts['defer']
    n_counter = counts.get('counter', 0)
    n_discard = counts.get('discard', 0)
    n_removal = counts.get('removal', 0)
    # Interaction decks earn primary credit from counter_*, discard_*, and
    # remove_* tokens. A spot-removal spell that kills a threat is just as
    # much "interaction" as a counter or a discard — it's how tempo/midrange
    # decks (bug, dimir, ur_delver, …) interact with creature plans.
    n_inter = n_hold + n_defer + n_counter + n_discard + n_removal

    if deck1 in INTERACTION_DECKS:
        if p1_won:
            return ('A' if n_inter >= K_INTER_A else 'B+',
                    f"{n_counter} counter + {n_discard} discard + {n_removal} remove + "
                    f"{n_hold} hold + {n_defer} defer decisions; "
                    f"{'heavy structured disruption' if n_inter >= K_INTER_A else 'measured disruption'} backed the win")
        return ('C+' if n_inter >= K_INTER_C_PLUS else 'C',
                f"{n_counter} counter + {n_discard} discard + {n_removal} remove + "
                f"{n_hold} hold + {n_defer} defer decisions; "
                f"{'logged but insufficient' if n_inter >= K_INTER_C_PLUS else 'not enough disruption surfaced'}")

    if deck1 in COMBO_DECKS:
        # For combo decks, Hold/Defer surfaces *protection*-grade play.
        if p1_won:
            return ('B+' if n_hold >= 1 else 'B',
                    f"{n_hold} hold + {n_defer} defer; {'protected combo via typed hold' if n_hold else 'combo resolved without holding protection'}")
        return ('C+' if n_hold >= 1 else 'C',
                f"{n_hold} hold + {n_defer} defer; {'protection deployed but insufficient' if n_hold else 'no protection token surfaced'}")

    return ('B' if p1_won else 'C+',
            f"{n_hold} hold + {n_defer} defer; interaction tokens {'sufficed' if p1_won else 'fell short'}")


def _grade_meta(trace: dict, counts: dict) -> tuple[str, str]:
    """Meta-axis grade: rewards explicit play-around decisions.

    Before PR #160 the grader keyed on `counts['total']` as a proxy for
    "strategic depth" — a deck with many decision points was assumed to be
    playing the matchup actively. That heuristic was a placeholder; the
    `meta_play_around_<threat>` tokens emitted by PR #160 give the grader a
    direct signal: the strategy *chose* to not execute its plan because of
    a named opponent threat (FoW, Daze, Surgical, Bowmasters).

    Promotion rules:
      - Win with n_meta >= 2: A — demonstrably played around opp threats
      - Win with n_meta >= 1: B+ — at least one play-around contributed
      - Loss with n_meta >= 1: C+ — tried to play around but lost anyway
      - All other branches: unchanged from the prior matchup-class heuristic.

    The matchup-class branches (favored / unfavored) remain because they
    capture a separate dimension — *role awareness* (combo wins vs
    interaction → A) — that the per-decision count cannot replace.
    """
    deck1 = trace.get('deck1', '')
    deck2 = trace.get('deck2', '')
    p1_won = trace.get('winner') == 'p1'
    game_length = trace.get('game_length', 10)
    n_meta = counts.get('meta', 0)

    is_favored = deck1 in COMBO_DECKS and deck2 in AGGRO_DECKS
    is_unfavored = deck1 in COMBO_DECKS and deck2 in INTERACTION_DECKS

    # ─── Win branch ──────────────────────────────────────────────────────
    if p1_won and is_unfavored:
        return 'A', f"Won an unfavored matchup ({deck1} vs {deck2}) — strong matchup awareness"
    if p1_won and n_meta >= 2:
        return ('A',
                f"{n_meta} play_around tokens — demonstrably navigated opp threats "
                f"({'favored' if is_favored else 'parity'} matchup, T{game_length} win)")
    if p1_won and n_meta >= 1:
        return ('B+',
                f"{n_meta} play_around token — at least one explicit play-around "
                f"contributed to a T{game_length} win")
    if p1_won:
        return ('B+' if game_length <= 6 else 'B',
                f"{'Efficiently closed' if game_length <= 6 else 'Eventually closed'} {'a favored' if is_favored else 'the'} matchup")
    # ─── Loss branch ─────────────────────────────────────────────────────
    if not p1_won and is_favored:
        return 'C', f"Lost a matchup that should be favored ({deck1} vs {deck2}) — possible role confusion"
    if not p1_won and n_meta >= 1:
        return ('C+',
                f"{n_meta} play_around token but lost in {game_length} turns — "
                f"tried to navigate opp threats, outcome insufficient")
    return ('C+' if counts['total'] >= 5 else 'C',
            f"Lost — {'played actively but could not overcome matchup' if counts['total'] >= 5 else 'limited decision points suggest structural disadvantage'}")


def grade_one_structural(trace_path: Path) -> Path | None:
    """Structural-grade a single trace. Returns path to _structural_graded.json."""
    with open(trace_path) as f:
        trace = json.load(f)

    decisions = trace.get('strategic_decisions', []) or []
    counts = _count_structural(decisions, deck1=trace.get('deck1'))

    grades = {}
    justs = {}
    grades['mulligan'], justs['mulligan'] = _grade_mulligan(trace)
    grades['mana'], justs['mana'] = _grade_mana(trace, counts)
    grades['combat'], justs['combat'] = _grade_combat(trace, counts)
    grades['combo'], justs['combo'] = _grade_combo(trace, counts)
    grades['interaction'], justs['interaction'] = _grade_interaction(trace, counts)
    grades['meta'], justs['meta'] = _grade_meta(trace, counts)

    # Coerce off-scale "B-" → "B" for the averaging step (GRADE_SCALE has no B-).
    overall_nums = []
    for g in grades.values():
        if g in GRADE_TO_NUM:
            overall_nums.append(GRADE_TO_NUM[g])
        elif g == 'B-':
            overall_nums.append(GRADE_TO_NUM['C+'])
    if overall_nums:
        avg = sum(overall_nums) / len(overall_nums)
        nearest = min(NUM_TO_GRADE.keys(), key=lambda k: abs(k - avg))
        grades['overall'] = NUM_TO_GRADE[nearest]
    else:
        grades['overall'] = 'UNGRADED'
    p1_won = trace.get('winner') == 'p1'
    justs['overall'] = (f"Average across 6 domains — {'won' if p1_won else 'lost'} "
                        f"in {trace.get('game_length','?')} turns; "
                        f"structural counts: exec={counts['execute']} "
                        f"hold={counts['hold']} defer={counts['defer']} "
                        f"remove={counts.get('removal', 0)} "
                        f"combat={counts['combat']}")

    raw_lines = []
    for d in list(RUBRIC_DOMAINS) + ['overall']:
        raw_lines.append(f"{d}: {grades[d]} — {justs[d]}")
    raw = '\n'.join(raw_lines)

    graded = {
        'trace_file': trace_path.name,
        'matchup': trace.get('matchup', ''),
        'seed': trace.get('seed', ''),
        'winner': trace.get('winner', ''),
        'win_reason': trace.get('win_reason', ''),
        'kill_turn': trace.get('kill_turn', ''),
        'game_length': trace.get('game_length', ''),
        'deck1': trace.get('deck1', ''),
        'deck2': trace.get('deck2', ''),
        'grades': grades,
        'justifications': justs,
        'structural_counts': counts,
        'raw_response': raw,
        'model': 'structural-v1',
        'graded_at': datetime.utcnow().isoformat() + 'Z',
    }

    out_path = trace_path.with_name(trace_path.stem + '_structural_graded.json')
    with open(out_path, 'w') as f:
        json.dump(graded, f, indent=2)

    grade_str = ' '.join(f"{d}={grades[d]}" for d in RUBRIC_DOMAINS)
    print(f"  + {trace_path.name} -> {grade_str}")
    return out_path


# ─── comparison report ────────────────────────────────────────────────────

def build_report() -> str:
    """Compare structural grades vs heuristic grades per domain.

    Reads `<trace>_graded.json` (heuristic) and `<trace>_structural_graded.json`
    (this script). For each trace where both exist, count per-domain
    agreement. Does not fail on disagreement — the comparison is the point.
    """
    structural_files = sorted(TRACE_DIR.glob('*_structural_graded.json'))
    if not structural_files:
        return ("# No structural-graded traces found\n\n"
                "Run `python3 scripts/structural_grader.py results/traces/*.json` first.\n")

    # Pair each with its heuristic counterpart, if any.
    pairs = []
    for sp in structural_files:
        base = sp.name.replace('_structural_graded.json', '')
        hp = sp.with_name(base + '_graded.json')
        if hp.exists():
            with open(sp) as f:
                s = json.load(f)
            with open(hp) as f:
                h = json.load(f)
            pairs.append((base, h, s))

    if not pairs:
        return "# No paired heuristic + structural graded traces found.\n"

    # Per-domain agreement count
    agree = defaultdict(int)
    disagree_examples = defaultdict(list)
    for base, h, s in pairs:
        for d in RUBRIC_DOMAINS:
            hg = h['grades'].get(d, 'UNGRADED')
            sg = s['grades'].get(d, 'UNGRADED')
            if hg == sg:
                agree[d] += 1
            else:
                disagree_examples[d].append((base, hg, sg,
                                             s.get('justifications', {}).get(d, '')))

    n = len(pairs)
    lines = [
        f"# Structural vs heuristic grader comparison",
        "",
        f"**N={n} paired traces** (heuristic-v1 vs structural-v1)",
        "",
        "## Per-domain agreement",
        "",
        "| Domain | Agreement | Heuristic example | Structural example |",
        "|--------|-----------|-------------------|--------------------|",
    ]
    for d in RUBRIC_DOMAINS:
        pct = 100.0 * agree[d] / max(n, 1)
        if disagree_examples[d]:
            base, hg, sg, _just = disagree_examples[d][0]
            lines.append(f"| {d} | {agree[d]}/{n} = {pct:.0f}% | "
                         f"{base}: {hg} | {base}: {sg} |")
        else:
            lines.append(f"| {d} | {agree[d]}/{n} = {pct:.0f}% | "
                         f"(all match) | (all match) |")

    # Per-trace side-by-side
    lines += ["", "## Per-trace grades (heuristic | structural)", ""]
    header = "| trace | " + " | ".join(
        f"{d} (H/S)" for d in RUBRIC_DOMAINS
    ) + " |"
    sep = "|" + "|".join(["---"] * (len(RUBRIC_DOMAINS) + 1)) + "|"
    lines.append(header)
    lines.append(sep)
    for base, h, s in pairs:
        cells = [base]
        for d in RUBRIC_DOMAINS:
            hg = h['grades'].get(d, '?')
            sg = s['grades'].get(d, '?')
            marker = '' if hg == sg else ' *'
            cells.append(f"{hg}/{sg}{marker}")
        lines.append("| " + " | ".join(cells) + " |")

    # Show a representative disagreement
    lines += ["", "## First disagreement per domain", ""]
    for d in RUBRIC_DOMAINS:
        if disagree_examples[d]:
            base, hg, sg, just = disagree_examples[d][0]
            lines.append(f"### {d}: {base}")
            lines.append(f"- heuristic = **{hg}**, structural = **{sg}**")
            lines.append(f"- structural rationale: {just}")
            lines.append("")

    return '\n'.join(lines) + '\n'


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('paths', nargs='*', help='Trace JSON files to grade')
    p.add_argument('--report', action='store_true',
                   help='Compare structural vs heuristic grades (reads existing graded files)')
    p.add_argument('--force', action='store_true',
                   help='Re-grade even if _structural_graded.json exists')

    args = p.parse_args()

    if args.report:
        report = build_report()
        report_path = TRACE_DIR.parent / 'structural_vs_heuristic_report.md'
        report_path.write_text(report)
        print(f"Report written to {report_path}")
        print(report)
        return

    if not args.paths:
        p.error("Provide trace JSON paths, or use --report")

    trace_paths = []
    for tp in args.paths:
        pp = Path(tp)
        if '_graded.json' in pp.name or '_prompt.txt' in pp.name:
            continue
        if not pp.exists():
            print(f"  ! skipping {tp} (not found)")
            continue
        trace_paths.append(pp)

    if not trace_paths:
        print("No trace files to grade.")
        return

    print(f"Grading {len(trace_paths)} traces with structural-v1...")
    graded = 0
    for tp in trace_paths:
        out_path = tp.with_name(tp.stem + '_structural_graded.json')
        if out_path.exists() and not args.force:
            print(f"  - {tp.name} already graded, skipping (use --force to re-grade)")
            continue
        if grade_one_structural(tp):
            graded += 1
    print(f"\nGraded {graded}/{len(trace_paths)} traces with structural-v1.")
    print(f"Next: python3 scripts/structural_grader.py --report")


if __name__ == '__main__':
    main()
