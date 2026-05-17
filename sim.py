"""
sim.py — Symmetric Monte Carlo game engine.

Public API: run_game, run_sweep, run_meta_matrix, run_any_match, run_any_bo3.
CLI interface: see run_meta.py.
"""

import random
import sys
from dataclasses import dataclass
from typing import List, Optional

from rules import MTGRules, StackType, Card
from cards import (DECKS, MATCHUP_META, make_postboard_opp_deck,
                   instant, sorcery, artifact, creature)
from game import GameState, PlayerState, london_mulligan, opp_keep, score_timeout
from engine import opp_turn, play_turn, update_goyf
from config import (GameRules as GR, CombatThresholds as CT, CounterLogic as CL,
                    RaceThresholds as RT, WastelandPriority as WP,
                    BurnLethal as BL, Elves as EL, MulliganTSPriority as MTSP)


@dataclass
class GameResult:
    winner: str
    win_reason: str
    kill_turn: Optional[int]
    game_length: int
    p1_mulls: int
    p2_mulls: int
    p1_opening_hand: List[str]
    p2_opening_hand: List[str]
    log_lines: List[str]
    final_p1_life: int
    final_p2_life: int
    p1_went_first: bool
    p1_deck: str = ''
    p2_deck: str = ''
    # Bo1 companion (CR 702.139) — name of the card placed outside the
    # 60-card deck at game start. None if the deck declared no companion.
    p1_companion_zone: Optional[str] = None
    p2_companion_zone: Optional[str] = None

    # Legacy aliases — deprecated, use p1_*/p2_* instead
    @property
    def bug_mulls(self): return self.p1_mulls
    @property
    def bug_went_first(self): return self.p1_went_first


def _trace_dual_board(log, gs, deck1, deck2):
    """Append both-player board state in side-by-side table format."""
    def _col(label, player, w=32):
        lines = []
        lines.append(f"{label:<{w}}")
        lines.append(f"  Life: {player.life:<{w-8}}")
        lines.append(f"  Hand: {len(player.hand)}  Lib: {len(player.library)}  GY: {len(player.graveyard)}")
        land_names = ', '.join(l.card.name for l in player.lands) or '(none)'
        if len(land_names) > w - 4:
            land_names = land_names[:w-7] + '...'
        lines.append(f"  Lands: {land_names}")
        cre = ', '.join(f"{c.card.name} ({c.power}/{c.toughness})" for c in player.creatures) or '(none)'
        if len(cre) > w - 4:
            cre = cre[:w-7] + '...'
        lines.append(f"  Creatures: {cre}")
        arts = ', '.join(a.card.name for a in player.artifacts)
        if arts:
            if len(arts) > w - 4:
                arts = arts[:w-7] + '...'
            lines.append(f"  Artifacts: {arts}")
        hand_str = ', '.join(c.name for c in player.hand) or '(empty)'
        # Wrap hand across multiple lines if needed
        hand_lines = []
        prefix = "  Hand: "
        while len(prefix + hand_str) > w:
            cut = hand_str.rfind(', ', 0, w - len(prefix))
            if cut <= 0:
                cut = w - len(prefix)
            hand_lines.append(prefix + hand_str[:cut])
            hand_str = hand_str[cut:].lstrip(', ')
            prefix = "        "
        hand_lines.append(prefix + hand_str)
        lines += hand_lines
        return lines

    left = _col(deck1.upper(), gs.p1)
    right = _col(deck2.upper(), gs.p2)
    # Pad to same height
    max_h = max(len(left), len(right))
    left += [''] * (max_h - len(left))
    right += [''] * (max_h - len(right))
    for l, r in zip(left, right):
        log.append(f"  │ {l:<32} │ {r:<32} │")


# ─── Companion zone helper ──────────────────────────────────────────────────
# Companion cards (CR 702.139) live OUTSIDE the 60-card deck. When a deck's
# DECK_META declares `'companion': '<tag>'`, this builder constructs that card
# at game start and `run_game` places it in `player.companion_zone`. Tag→card
# mapping is closed (only Lurrus of the Dream-Den is modelled today); add a
# new entry here when another companion enters the Legacy pool.
_COMPANION_BUILDERS = {}

def _build_companion_card(tag: str):
    """Build a single Card to place in `player.companion_zone`. Returns None
    when the tag is unknown — caller treats None as 'no companion'."""
    builder = _COMPANION_BUILDERS.get(tag)
    return builder() if builder else None


def _register_companion_builder(tag: str):
    """Decorator: registers a tag→builder mapping for companion construction."""
    def wrap(fn):
        _COMPANION_BUILDERS[tag] = fn
        return fn
    return wrap


@_register_companion_builder('lurrus')
def _build_lurrus():
    """Lurrus of the Dream-Den — Bo1 Doomsday companion. CR 702.139:
    once per game, may be cast from companion zone (real Magic taxes
    +3 mana; sim defers that nuance to Phase D/E wiring)."""
    from cards import creature
    return creature("Lurrus of the Dream-Den", 2, {'B': 1, 'generic': 1},
                    {'B'}, 3, 2, tag='lurrus', lifelink=True)


def run_game(deck1: str, deck2: str = None, verbose: bool = False,
             trace: bool = False,
             use_neural_gates: bool = False,
             use_neural_scorer: bool = False,
             use_ensemble: bool = False,
             use_rollout: bool = False,
             use_q_scorer: bool = False,
             use_q_mulligan: bool = False,
             collect_q_data: bool = False) -> GameResult:
    """
    Run a single game between any two decks with equal AI quality.

    Args:
        trace: If True, emit detailed phase markers, hand state, board state,
               mulligan decisions, and mana tracking for full play-by-play output.

    Usage:
        run_game('ur_delver', 'dimir')
        run_game('storm', 'burn')
        run_game('burn', 'dimir', trace=True)  # full play-by-play
    """
    # Legacy compat: run_game('storm') means BUG vs storm
    if deck2 is None:
        deck2 = deck1
        deck1 = 'bug'

    if deck1 not in DECKS:
        raise ValueError(f"Unknown deck: {deck1}. Available: {sorted(DECKS.keys())}")
    if deck2 not in DECKS:
        raise ValueError(f"Unknown deck: {deck2}. Available: {sorted(DECKS.keys())}")

    # Coin flip happens BEFORE mulligans (matches real Magic CR 103.1, and
    # lets matchup-aware mulligan policies condition on going first/second).
    p1_goes_first = random.random() < 0.5

    # Mulligan: each deck uses its own keep logic (via registry or fallback)
    from deck_registry import get_keep_fn
    p1_keep = get_keep_fn(deck1) or opp_keep
    p2_keep = get_keep_fn(deck2) or opp_keep
    # ── LEVER 6: Q-net mulligan policy (default off) ───────────────────
    if use_q_mulligan:
        try:
            from mulligan_q import should_keep as _q_should_keep
            _heuristic_keep = p1_keep
            def _q_wrapped_keep(hand, matchup='', _gf=p1_goes_first):
                v = _q_should_keep(hand, matchup, goes_first=_gf)
                return _heuristic_keep(hand, matchup) if v is None else v
            p1_keep = _q_wrapped_keep
        except Exception:
            # Checkpoint missing or torch not importable — fall back silently.
            pass

    p1_mull_trace = p2_mull_trace = None
    if trace:
        p1_hand, p1_lib, p1_mulls, p1_mull_trace = london_mulligan(
            DECKS[deck1], p1_keep, deck1, trace=True)
        p2_hand, p2_lib, p2_mulls, p2_mull_trace = london_mulligan(
            DECKS[deck2], p2_keep, deck2, trace=True)
    else:
        p1_hand, p1_lib, p1_mulls = london_mulligan(DECKS[deck1], p1_keep, deck1)
        p2_hand, p2_lib, p2_mulls = london_mulligan(DECKS[deck2], p2_keep, deck2)

    gs = GameState(
        p1=PlayerState(name='b', hand=list(p1_hand), library=list(p1_lib)),
        p2=PlayerState(name='o', hand=list(p2_hand), library=list(p2_lib)),
        p1_goes_first=p1_goes_first)
    gs.p1_deck = deck1
    gs.p2_deck = deck2
    # Bo1 companion (CR 702.139): if either deck's DECK_META declares a
    # 'companion' tag, build that card from a registry and place it in
    # `player.companion_zone`. The card is NOT in the 60-card deck.
    # Phase A wiring per docs/design/2026-05-16_doomsday_cabal_therapy_piles.md.
    from deck_registry import get_meta as _get_meta_companion
    for _slot_name, _slot, _deck_key in (('p1', gs.p1, deck1), ('p2', gs.p2, deck2)):
        _meta = _get_meta_companion(_deck_key) or {}
        _comp_tag = _meta.get('companion')
        if _comp_tag:
            _slot.companion_zone = _build_companion_card(_comp_tag)
    gs.matchup = deck2  # backward compat: matchup = antagonist deck
    gs.trace = trace
    # Phase 3b — opt-in neural-pivot toggles for `_strategy_tes`. Default
    # off so the heuristic matrix path is byte-identical to before.
    gs.use_neural_gates = use_neural_gates
    gs.use_neural_scorer = use_neural_scorer
    gs.use_ensemble = use_ensemble
    gs.use_rollout = use_rollout
    gs.use_q_scorer = use_q_scorer
    gs.use_q_mulligan = use_q_mulligan
    gs.collect_q_data = collect_q_data
    # Strategic logger follows the same trace flag
    gs.strat_log.enabled = trace

    all_log = []
    display_turn = 0

    # ── Trace: pregame section ──
    if trace:
        all_log.append(f"{'═' * 70}")
        all_log.append(f"  {deck1.upper()} vs {deck2.upper()}")
        all_log.append(f"{'═' * 70}")
        all_log.append("")
        all_log.append(f"── PREGAME {'─' * 58}")
        all_log.append("")
        first_name = deck1.upper() if p1_goes_first else deck2.upper()
        all_log.append(f"  Coin flip: {first_name} wins the die roll, goes FIRST")
        all_log.append("")
        all_log.append(f"  {deck1.upper()} (P1):")
        if p1_mull_trace:
            all_log += p1_mull_trace
        all_log.append("")
        all_log.append(f"  {deck2.upper()} (P2):")
        if p2_mull_trace:
            all_log += p2_mull_trace
        all_log.append("")

    for turn in range(1, GR.MAX_TURNS + 1):
        if gs.game_over:
            break
        gs.turn = turn

        first, second = ('p1', 'p2') if p1_goes_first else ('p2', 'p1')
        for who in (first, second):
            display_turn += 1
            label = deck1.upper() if who == 'p1' else deck2.upper()
            player = gs.p1 if who == 'p1' else gs.p2
            opponent = gs.p2 if who == 'p1' else gs.p1

            if trace:
                # Turn header with life totals
                life_str = f"{deck1} {gs.p1.life} | {deck2} {gs.p2.life}"
                header = f"━━ TURN {display_turn} — {label} "
                all_log.append(f"{header}{'━' * max(1, 50 - len(header))} Life: {life_str}")
                all_log.append("")

            lines = play_turn(gs, turn, who)

            if trace:
                for l in lines:
                    all_log.append(f"  {l}")
                # Both-player board state
                all_log.append("")
                all_log.append(f"  ┌{'─' * 34}┬{'─' * 34}┐")
                _trace_dual_board(all_log, gs, deck1, deck2)
                all_log.append(f"  └{'─' * 34}┴{'─' * 34}┘")
                all_log.append("")
            else:
                all_log += [f"  T{display_turn}[{label}] {l}" for l in lines]
            if gs.game_over: break

    # Timeout resolution: score board position
    if not gs.game_over:
        p1_score = score_timeout(gs.p1, gs.p2)
        p2_score = score_timeout(gs.p2, gs.p1)

        if p1_score > p2_score:
            gs.winner = 'p1'
            gs.win_reason = f"Board/life advantage after T{gs.turn}"
        elif p2_score > p1_score:
            gs.winner = 'p2'
            gs.win_reason = f"Board/life advantage after T{gs.turn}"
        else:
            gs.winner = 'p1' if gs.p1.life >= gs.p2.life else 'p2'
            gs.win_reason = f"Tied board after T{gs.turn}, life tiebreak"
        gs.kill_turn = gs.turn
        gs.game_over = True

    if trace:
        all_log.append(f"{'═' * 70}")
        winner_label = deck1.upper() if gs.winner == 'p1' else deck2.upper()
        all_log.append(f"  WINNER: {winner_label} — {gs.win_reason}")
        all_log.append(f"  Final life: {deck1} {gs.p1.life} | {deck2} {gs.p2.life}")
        all_log.append(f"{'═' * 70}")
        # Append strategic decision log (empty unless strategies called log_decision)
        strat_entries = gs.strat_log.dump()
        if strat_entries:
            all_log.append("")
            all_log.append(f"── STRATEGIC DECISIONS {'─' * 47}")
            all_log.extend(strat_entries)

    return GameResult(
        winner=gs.winner,
        win_reason=gs.win_reason or '',
        kill_turn=gs.kill_turn,
        game_length=gs.turn,
        p1_mulls=p1_mulls,
        p2_mulls=p2_mulls,
        p1_opening_hand=[c.name for c in p1_hand],
        p2_opening_hand=[c.name for c in p2_hand],
        log_lines=all_log,
        final_p1_life=gs.p1.life,
        final_p2_life=gs.p2.life,
        p1_went_first=p1_goes_first,
        p1_deck=deck1,
        p2_deck=deck2,
        p1_companion_zone=(gs.p1.companion_zone.name if gs.p1.companion_zone else None),
        p2_companion_zone=(gs.p2.companion_zone.name if gs.p2.companion_zone else None),
    )

# Threshold below which the multiprocessing pool overhead outweighs the speedup.
# Calls smaller than this run serially even when parallel=True is requested.
_PARALLEL_SWEEP_MIN_GAMES = 50


def run_sweep(deck1: str, deck2: str, n_games: int = 100,
              use_neural_gates: bool = False,
              use_neural_scorer: bool = False,
              use_ensemble: bool = False,
              use_rollout: bool = False,
              use_q_scorer: bool = False,
              use_q_mulligan: bool = False,
              parallel: bool = True) -> dict:
    """
    Run n_games between deck1 and deck2, return stats.
    Returns dict with: p1_wins, p2_wins, p1_wr, avg_length, avg_kill_turn

    parallel: when True (default) and n_games >= _PARALLEL_SWEEP_MIN_GAMES,
              delegate to parallel.parallel_sweep for multiprocessing speedup.
              Set parallel=False for single-process debugging / deterministic
              traces.
    """
    neural_flags = {
        'use_neural_gates': use_neural_gates,
        'use_neural_scorer': use_neural_scorer,
        'use_ensemble': use_ensemble,
        'use_rollout': use_rollout,
        'use_q_scorer': use_q_scorer,
        'use_q_mulligan': use_q_mulligan,
    }

    if parallel and n_games >= _PARALLEL_SWEEP_MIN_GAMES:
        from parallel import parallel_sweep
        # parallel_sweep returns the same dict shape this function builds.
        return parallel_sweep(deck1, deck2, n_games=n_games,
                              neural_flags=neural_flags)

    results = [run_game(deck1, deck2, **neural_flags)
               for _ in range(n_games)]
    p1_wins = sum(1 for r in results if r.winner == 'p1')
    p2_wins = n_games - p1_wins
    kill_turns = [r.kill_turn for r in results if r.kill_turn]
    return {
        'deck1': deck1, 'deck2': deck2,
        'p1_wins': p1_wins, 'p2_wins': p2_wins,
        'p1_wr': p1_wins / n_games,
        'n_games': n_games,
        'avg_length': sum(r.game_length for r in results) / n_games,
        'avg_kill': sum(kill_turns) / len(kill_turns) if kill_turns else 0,
    }


def run_meta_matrix(decks: list = None, n_games: int = 100, top_tier: int = 0,
                    parallel: bool = True) -> dict:
    """
    Run every deck vs every deck and return a matrix of win rates.
    Returns dict of {(deck1, deck2): p1_win_rate}.

    Args:
        decks: explicit list of deck keys. Overrides top_tier.
        n_games: games per matchup pair.
        top_tier: if > 0 and decks is None, pick this many random decks
                  from the highest meta-share decks (always includes 'bug').
        parallel: when True (default), delegate to parallel.parallel_meta_matrix
                  for multiprocessing speedup. Set parallel=False for
                  single-process debugging / deterministic traces.

    Usage:
        matrix = run_meta_matrix(['bug', 'dimir', 'ur_delver', 'storm'], n_games=200)
        matrix = run_meta_matrix(top_tier=5, n_games=100)  # 5 random top-meta decks
    """
    if decks is None:
        if top_tier > 0:
            # Sort decks by meta share descending, take top N deterministically
            def _get_share(k):
                meta = MATCHUP_META.get(k, {})
                if isinstance(meta, dict) and 'share' in meta:
                    return meta['share']
                return 0.0  # unknown decks get 0 share, not included
            ranked = sorted(
                ((k, _get_share(k)) for k in DECKS if _get_share(k) > 0),
                key=lambda x: (-x[1], x[0])
            )
            decks = sorted(k for k, _ in ranked[:top_tier])
            print(f"Top-{top_tier} by meta share: {', '.join(decks)}")
        else:
            decks = sorted(DECKS.keys())

    if parallel:
        from parallel import parallel_meta_matrix
        return parallel_meta_matrix(decks, n_games=n_games)

    matrix = {}
    total = len(decks) * (len(decks) - 1)
    done = 0

    for d1 in decks:
        for d2 in decks:
            if d1 == d2:
                continue
            stats = run_sweep(d1, d2, n_games, parallel=False)
            matrix[(d1, d2)] = stats['p1_wr']
            done += 1
            if done % 10 == 0:
                print(f"  {done}/{total} matchups complete...")

    return matrix


# ── Old BUG-centric functions removed (run_matchup, run_all_matchups,
#    ELVES_MATCHUPS, run_elves_match, run_elves_bo3) — use symmetric API instead.

# All strategies are registered via deck_registry (decks/*.py modules).
# No manual STRATEGIES dict needed — get_strategy(matchup) handles dispatch.


def run_meta_matrix_bo3(decks: list = None, n_matches: int = 100, top_tier: int = 0) -> dict:
    """
    Run every deck vs every deck as Bo3 matches (sideboard-aware) and return
    a matrix of match WRs + game WRs.

    Returns dict of {(deck1, deck2): {'match_wr': float, 'game_wr': float}}.

    Args:
        decks: explicit list of deck keys. Overrides top_tier.
        n_matches: Bo3 matches per matchup pair.
        top_tier: if > 0 and decks is None, pick this many top-meta decks.
    """
    if decks is None:
        if top_tier > 0:
            def _get_share(k):
                meta = MATCHUP_META.get(k, {})
                if isinstance(meta, dict) and 'share' in meta:
                    return meta['share']
                return 0.0
            ranked = sorted(
                ((k, _get_share(k)) for k in DECKS if _get_share(k) > 0),
                key=lambda x: (-x[1], x[0])
            )
            decks = sorted(k for k, _ in ranked[:top_tier])
            print(f"Top-{top_tier} by meta share: {', '.join(decks)}")
        else:
            decks = sorted(DECKS.keys())

    from parallel import parallel_meta_matrix_bo3
    return parallel_meta_matrix_bo3(decks, n_matches)


def _execute_turn(gs, turn, b, o, who, matchup):
    """
    Unified turn function — single code path for BOTH P1 and P2.

    Args:
        gs: GameState
        turn: turn number
        b: active player (PlayerState)
        o: opposing player (PlayerState)
        who: 'p1' or 'p2' — which slot is the active player
        matchup: deck key for strategy dispatch

    Full turn structure: cleanup → untap → upkeep → draw → bauble draws →
    land (with priority) → mana → Rishadan Port → Wasteland → Thoughtseize →
    removal → gameplan → lock enforcement → strategy dispatch → Tamiyo →
    combat → opponent instant-speed responses → EOT.
    """
    from engine import (bowmasters_triggers, update_goyf, opp_can_cast,
                        _try_counter_any, _select_attackers, combat_declare,
                        apply_lock_effects, restore_lock_effects, _check_tamiyo_flip)
    from rules import LandPermanent, MTGRules
    from config import MatchupCategory as _MC

    log_entries = []

    def log(msg, key=False):
        gs.log_event(who, 'main', msg, key)
        log_entries.append(msg)

    # Determine if active player is on the play and skips T1 draw
    active_on_play = (gs.p1_goes_first and who == 'p1') or (not gs.p1_goes_first and who == 'p2')

    # Treasure key: slot-specific
    treasure_attr = 'p1_treasure' if who == 'p1' else 'p2_treasure'

    # Deck key for active player (for artifact deck land priority etc.)
    active_deck = gs.p1_deck if who == 'p1' else gs.p2_deck
    opp_deck = gs.p2_deck if who == 'p1' else gs.p1_deck

    # Bowmasters controller: when active player draws, opponent's Bowmasters fires
    bowm_ctrl = 'o' if who == 'p1' else 'b'

    # ── Cleanup — CR 510.2 ──
    for p in [b, o]:
        for c in p.creatures:
            c.damage_marked = 0
            if hasattr(c, 'hexproof'):
                del c.hexproof

    # ── Untap ──
    b.untap_all()
    b.revolt_this_turn = False
    b.clear_summoning_sickness()
    gs.combat_this_turn = False
    gs.p2_spells_cast_this_turn = 0
    gs.veil_active = False
    gs.teferi_active = False
    b.spells_cast_this_turn = 0
    b._gy_via_non_cast = 0
    # Resync eidolon_active — must check BOTH players each turn (fixes ghost trigger after death)
    gs.eidolon_active = (any(c.card.tag == 'eidolon' for c in gs.p1.creatures)
                         or any(c.card.tag == 'eidolon' for c in gs.p2.creatures))
    if gs.trace:
        log(f"── Untap ── ({len(b.lands)} lands)")

    # ── Upkeep: Goyf update ──
    update_goyf(gs)

    # ── Upkeep: Suspend resolution (CR 702.62) ──
    # Tick down all suspended cards. When counter reaches 0, cast for free.
    if b.suspended:
        still_suspended = []
        for card, turns_left in b.suspended:
            if turns_left <= 1:
                # Cast from exile — opponent gets counter window
                log(f"★ {card.name} comes off suspend — cast for free!")
                countered = _try_counter_any(b, o, gs, card, log_entries)
                if not countered:
                    b.add_to_grave(card)
                    if card.tag == 'rift':
                        o.life -= 3
                        log(f"  Rift Bolt → 3 damage (opp at {o.life})")
                        gs.check_life_totals()
                        if gs.game_over:
                            break
                else:
                    b.add_to_grave(card)
                    log(f"  {card.name} countered off suspend")
            else:
                still_suspended.append((card, turns_left - 1))
        b.suspended = still_suspended
    if gs.trace:
        log("── Upkeep ──")

    # ── Draw (first player on play skips T1 draw) ──
    if gs.trace:
        if turn == 1 and active_on_play:
            log("── Draw ── (skipped — on the play, T1)")
        else:
            log("── Draw ──")
    if not (turn == 1 and active_on_play):
        drawn = b.draw(1, is_draw_step=True)
        if drawn:
            log(f"Draw: {drawn[0].name}")

    # ── Pending Bauble draws from previous turn ──
    pending = gs.pending_bauble_draws
    if pending > 0:
        drawn = b.draw(pending)
        for d in drawn:
            log(f"Bauble (upkeep draw) → {d.name}")
        bowmasters_triggers(pending, gs, log_entries, controller=bowm_ctrl)
        gs.pending_bauble_draws = 0

    # ── Land drop (with priority picking) ──
    def _pick_land():
        lands_in_hand = [c for c in b.hand if c.is_land()]
        if not lands_in_hand:
            return None
        # Filter out fetches that can't find anything in the current library
        # (their basic-type targets are gone).  Cracking such a fetch costs 1
        # life for nothing and on a sub-3 life total can lose the game outright.
        # Triggers when Doomsday's pile replaces the library with non-basics or
        # any deck has fully depleted the fetched basic types.
        def _fetch_useful(c):
            if not getattr(c, 'is_fetch', False):
                return True
            targets = getattr(c, 'fetch_targets', set())
            if not targets:
                return True
            return any(targets.intersection(getattr(lib_card, 'subtypes', set()))
                       for lib_card in b.library)
        non_fetches = [c for c in lands_in_hand if not getattr(c, 'is_fetch', False)]
        usable_fetches = [c for c in lands_in_hand if _fetch_useful(c)
                          and getattr(c, 'is_fetch', False)]
        if non_fetches or usable_fetches:
            lands_in_hand = non_fetches + usable_fetches
        else:
            return None  # only useless fetches in hand — skip the land drop
        has_2drop = any(c.tag in ('chalice', 'trini', 'null_rod') or
                        (not c.is_land() and sum(c.mana_cost.values()) == 2)
                        for c in b.hand)
        if has_2drop:
            fast = next((c for c in lands_in_hand
                         if c.tag in ('ancient_tomb', 'tomb', 'city')), None)
            if fast:
                return fast
        is_artifact_deck = active_deck in _MC.ARTIFACT
        # Both Lands and Depths run the Dark Depths + Thespian's Stage combo —
        # both need to prioritize the missing combo piece for their land drop,
        # otherwise a "filler" basic gets played instead and the kill turn
        # slips by one (Depths vs Burn was 35% before this fix).
        is_combo_lands_deck = active_deck in _MC.DEPTHS_COMBO
        needs_combo = False
        if is_combo_lands_deck:
            has_d = any(l.card.tag == 'depths' for l in b.lands)
            has_s = any(l.card.tag == 'stage' for l in b.lands)
            needs_combo = (has_d and not has_s) or (has_s and not has_d) or (not has_d and not has_s)
        def land_priority(c):
            if getattr(c, 'is_fetch', False): return 2
            tag = getattr(c, 'tag', '')
            if tag == 'dual': return 1
            if tag in ('sewers',): return 1
            if tag in ('ancient_tomb', 'city'): return 0
            if is_artifact_deck and tag == 'saga': return 0
            if is_artifact_deck and tag == 'seat': return 0
            # Lands / Depths: prioritize the missing combo piece
            if is_combo_lands_deck and needs_combo and tag in ('depths', 'stage'): return 0
            if c.is_basic: return 1
            if tag == 'wl': return 5
            return 3
        return min(lands_in_hand, key=land_priority)

    # Land drops: first drop is always allowed; additional drops require an
    # Exploration permanent in play. Loop while we have lands in hand AND a
    # drop slot remaining. (Real Lands runs 4× Exploration → up to 5 land
    # drops per turn early game, more typically 2-3.)
    for _land_drop in range(1 + b._exploration_count()):
        if b.land_played_this_turn and not b.can_play_extra_land():
            break
        land = _pick_land()
        if not land:
            break
        b.hand.remove(land)
        lp = LandPermanent(card=land, controller='b')
        b.lands.append(lp)
        if b.land_played_this_turn:
            b.extra_land_drops_used += 1
        b.land_played_this_turn = True
        gs.apply_continuous_effects(lp)
        if lp.is_fetch:
            fetched = b.use_fetch(lp)
            if fetched:
                gs.apply_continuous_effects(fetched)
                log(f"Play+crack {land.name} (−1 life, {b.life}) → {fetched.name}")
            else:
                log(f"Play+crack {land.name} → ?")
            b.revolt_this_turn = True
        else:
            extra_marker = " [Exploration]" if _land_drop > 0 else ""
            log(f"Land: {land.name} ({len(b.lands)} lands){extra_marker}")

    # ── Mana calculation ──
    # Lands only — fast-mana sources (Lotus Petal, Mox Opal, Chrome Mox, LED,
    # Dark Ritual, Grim Monolith) are owned by each deck's strategy. Pre-fix,
    # this block added `+1 per Petal in hand` here, and every strategy that
    # cracked petals ALSO incremented total_mana — double-counting every
    # Petal in the opener and giving painter T1 deploys (Petal+Monolith+
    # Painter's Servant+Grindstone with 0 lands). The Karn-lockout log
    # remains: it informs the strategy that artifact mana abilities can't
    # be activated, which is consumed by the per-deck fast-mana branches.
    total_mana = b.available_mana_count()
    opp_has_karn = (gs.p1_karn_active if o is gs.p1 else gs.p2_karn_active)
    if opp_has_karn:
        log(f"Karn lockout — can't activate artifact mana sources")
    treasure = getattr(gs, treasure_attr, 0)
    if treasure > 0:
        total_mana += treasure
        if gs.trace:
            log(f"Treasure ({treasure}) → +{treasure} mana")
        setattr(gs, treasure_attr, 0)
    tomb_count = sum(1 for l in b.lands if l.card.tag == 'tomb' and not l.tapped)
    if tomb_count > 0:
        total_mana += tomb_count
        b.life -= tomb_count * 2
    for l in b.lands:
        if l.card.tag == 'cradle' and not l.tapped:
            total_mana += len(b.creatures)
            l.tapped = True

    if gs.trace:
        log(f"── Main ── Mana: {total_mana}")
        log(f"  Hand ({len(b.hand)}): {', '.join(c.name for c in b.hand)}")

    # ── Rishadan Port: tap opponent's best land (Vial decks only) ──
    if matchup in _MC.VIAL_DECKS:
        def land_value(lp):
            if lp.card.tag == 'dual': return 3
            if lp.card.is_fetch: return 2
            if lp.card.is_basic: return 1
            return 0
        for port in [l for l in b.lands if l.card.tag == 'port' and not l.tapped]:
            untapped_opp = [l for l in o.lands if not l.tapped]
            if not untapped_opp:
                break
            target = max(untapped_opp, key=land_value)
            target.tapped = True
            port.tapped = True
            log(f"Rishadan Port taps {target.name} (opp loses 1 mana)", True)

    # ── Wasteland: destroy opponent's best nonbasic land ──
    wl_land = next((l for l in b.lands if l.card.tag in ('wl', 'wasteland') and not l.tapped), None)
    if wl_land and o.lands:
        eligible = [l for l in o.lands if not l.card.is_basic and l.card.tag != 'wl']
        if eligible:
            def _wl_prio(land):
                if land.card.tag in ('depths', 'stage'): return 50
                if getattr(land.card, 'mana_ritual', False): return 5
                return 1
            target = max(eligible, key=_wl_prio)
            wl_land.tapped = True
            o.lands.remove(target)
            o.add_to_grave(target.card)
            b.revolt_this_turn = True
            log(f"Wasteland [ACTIVATED-uncounterable] → {target.card.name}")

    # ── Thoughtseize: now deck-owned ──
    # The shared "Thoughtseize preamble" block previously cast TS for ANY deck
    # with tag='ts' before the per-deck strategy ran. This violated separation
    # of concerns (sim.py made tactical card-cast decisions) and accumulated
    # deck-specific patches (mardu-vs-burn skip, preamble_skip combo defer,
    # mardu+Grief pitch fuel collision). Each deck strategy now owns its TS
    # branch — see _strategy_bug, _strategy_dimir, _strategy_dimir_flash,
    # _strategy_mono_black, _strategy_mardu, _strategy_ocelot, _strategy_storm,
    # _strategy_reanimator, decks/goblins.py and decks/depths.py.

    # ── Removal: kill opponent's biggest threat ──
    _mom_protected = getattr(gs, '_mom_protected_tag', None)

    if o.creatures and total_mana >= 1:
        push = b.find_tag('push') or b.find_tag('fatal_push')
        if push and not gs.spell_blocked_by_chalice(push.cmc):
            revolt = b.revolt_this_turn
            valid_targets = [c for c in o.creatures
                             if MTGRules.fatal_push_valid_target(c, revolt)
                             and c.card.tag != _mom_protected]
            if valid_targets:
                target = max(valid_targets, key=lambda c: c.power)
                b.remove_from_hand(push)
                countered = _try_counter_any(b, o, gs, push, log_entries)
                if not countered:
                    b.add_to_grave(push)
                    total_mana -= 1
                    o.creatures.remove(target)
                    o.add_to_grave(target.card)
                    log(f"Fatal Push → {target.card.name} ({'revolt' if revolt else 'no revolt'})")
                    # Typed removal log for structural-grader interaction signal.
                    gs.strat_log.log_disruption(
                        gs.turn, gs, b, 'remove',
                        target.card.tag or 'creature', 'push',
                        reason=f'push kills {target.card.tag or "creature"}')
                else:
                    b.add_to_grave(push)

        stp = b.find_tag('stp')
        if stp and o.creatures and total_mana >= 1 and not gs.spell_blocked_by_chalice(stp.cmc):
            valid_stp = [c for c in o.creatures if c.card.tag != _mom_protected]
            target = max(valid_stp, key=lambda c: c.power) if valid_stp else None
            # Burn is already in _MC.AGGRO (config.py:_BUILTIN_AGGRO);
            # the prior `or opp_deck == 'burn'` was redundant.
            opp_is_aggro = opp_deck in _MC.AGGRO
            stp_threshold = CT.STP_THRESHOLD_AGGRO if opp_is_aggro else CT.STP_THRESHOLD_FAIR
            if target and target.power >= stp_threshold:
                b.remove_from_hand(stp)
                countered = _try_counter_any(b, o, gs, stp, log_entries)
                if not countered:
                    b.add_to_grave(stp)
                    total_mana -= 1
                    o.creatures.remove(target)
                    o.life += target.power
                    log(f"Swords to Plowshares → exile {target.card.name} (opp +{target.power} life)")
                    # Typed removal log for structural-grader interaction signal.
                    gs.strat_log.log_disruption(
                        gs.turn, gs, b, 'remove',
                        target.card.tag or 'creature', 'stp',
                        reason=f'stp exiles {target.card.tag or "creature"}')
                else:
                    b.add_to_grave(stp)

    # ── Gameplan layer ──
    from gameplan import GAMEPLANS, assess, active_goal
    plan = GAMEPLANS.get(matchup)
    if plan:
        ba = assess(gs, turn)
        gs.p2_goal = active_goal(plan, ba)
    else:
        gs.p2_goal = None

    # ── Lock piece enforcement (shared helpers — single source of truth) ──
    _adjustments = apply_lock_effects(gs, b, log)

    # ── Snapshot for Eidolon post-strategy check ──
    _hand_before = len(b.hand)
    _gy_nonland_before = sum(1 for c in b.graveyard if not c.is_land())

    # ── Snapshot for tried_combo post-pass ──
    # Capture the multiset of combo-piece tags currently in hand, plus the
    # current strat_log entry-count, so we can attribute newly-cast pieces
    # and detect whether an Execute token was logged this turn.
    from deck_registry import get_combo_meta as _gcm
    _cm = _gcm(active_deck)
    if _cm is not None:
        _combo_piece_tags = frozenset(_cm.get('pieces', ()))
        _hand_tags_before = [c.tag for c in b.hand if c.tag in _combo_piece_tags]
    else:
        _combo_piece_tags = frozenset()
        _hand_tags_before = []
    _strat_log_len_before = len(gs.strat_log.entries)

    # ── Strategy dispatch ──
    from deck_registry import get_strategy
    strategy_fn = get_strategy(matchup)
    if strategy_fn:
        try:
            strategy_fn(b, o, gs, total_mana, log, log_entries)
        except Exception as e:
            log(f"⚠ Strategy error ({matchup}): {e} — forfeiting turn")
    else:
        log(f"No strategy for {matchup} — passing")

    # ── Post-strategy: restore lock adjustments ──
    restore_lock_effects(b, _adjustments)

    # ── tried_combo:<piece_tag> post-pass ──
    # Mechanic: combo decks that played at least one combo piece this turn
    # but did NOT log an Execute token (combo didn't fire) get partial
    # credit via a `tried_combo:<tag>` log_decision. Lets the structural
    # grader distinguish "disrupted combo" from "did nothing".
    # Detection: any combo-piece tag that was in hand at start-of-turn and
    # is no longer in hand at end-of-turn is treated as "played this turn".
    # If an Execute token (combo:* / kill_* / cast_doomsday / cast_spy /
    # entomb_* / oracle_win / t1_kill / t2_kill) was logged by THIS deck
    # since dispatch began, suppress the emit — combo fired.
    if _combo_piece_tags and gs.strat_log.enabled:
        _new_entries = gs.strat_log.entries[_strat_log_len_before:]
        _exec_prefixes = ('combo:', 'kill_', 'cast_doomsday', 'cast_spy',
                          'entomb_', 'oracle_win', 't1_kill', 't2_kill')
        _exec_logged = any(
            e.get('deck') == active_deck and any(
                (e.get('chosen') or '').startswith(p) for p in _exec_prefixes
            )
            for e in _new_entries
        )
        if not _exec_logged:
            _hand_tags_after = [c.tag for c in b.hand if c.tag in _combo_piece_tags]
            # Multiset difference: pieces that left hand this turn.
            from collections import Counter as _Counter
            _played = _Counter(_hand_tags_before) - _Counter(_hand_tags_after)
            for _tag in sorted(_played):  # deterministic order
                gs.strat_log.log_decision(
                    gs.turn, active_deck,
                    candidates=['execute', 'tried_combo', 'pass'],
                    chosen=f'tried_combo:{_tag}',
                    reason=f'played {_tag} but combo did not fire this turn')

    # ── Eidolon post-strategy: apply damage for spells cast this turn ──
    # Strategies that bypass cast_spell() don't fire _eidolon_trigger.
    # Estimate spells cast: count nonland cards that moved from hand to graveyard.
    # This fires Eidolon on the ACTIVE player (b) for their own spells.
    # Eidolon already triggers on cast_spell() users (don't double-count).
    if gs.eidolon_active and not gs.game_over:
        _gy_nonland_after = sum(1 for c in b.graveyard if not c.is_land())
        _spells_via_cast_spell = getattr(b, 'spells_cast_this_turn', 0)
        _gy_via_non_cast = getattr(b, '_gy_via_non_cast', 0)
        _gy_growth = max(0, _gy_nonland_after - _gy_nonland_before)
        # Spells that went through cast_spell already triggered Eidolon.
        # Cards that hit graveyard via non-cast actions (cycling, discards,
        # sacrifices) aren't spells and must not trigger Eidolon.
        # Missed casts = total grave growth − cast_spell casts − non-cast moves.
        _missed_spells = max(0, _gy_growth - _spells_via_cast_spell - _gy_via_non_cast)
        if _missed_spells > 0:
            _eid_dmg = _missed_spells * 2
            b.life -= _eid_dmg
            _p_label = 'P1' if b is gs.p1 else 'P2'
            log(f"Eidolon trigger (post-strategy) — {_missed_spells} spell(s), {_eid_dmg} damage to {_p_label} ({b.life})")
            gs.check_life_totals()

    # ── Tamiyo flip check — oracle: flip when you draw your 3rd card in a turn ──
    _check_tamiyo_flip(gs, b, log)

    # ── Fallback combat: attack with eligible creatures if strategy didn't ──
    if gs.trace:
        atk = [c for c in b.creatures if not c.summoning_sick]
        log(f"── Combat ── ({len(atk)} eligible attackers)")
    if not gs.combat_this_turn and not gs.game_over and b.creatures:
        attackers = _select_attackers(b, o)
        if attackers:
            combat_declare(b, o, gs, log_entries, attackers)

    # ── Opponent instant-speed responses (after combat) ──
    if not gs.game_over:
        from engine import _respond_on_opponent_turn
        responder = gs.p2 if who == 'p1' else gs.p1
        active_player = gs.p1 if who == 'p1' else gs.p2
        _respond_on_opponent_turn(responder, active_player, gs, log, log_entries)

    update_goyf(gs)
    b.land_played_this_turn = False
    b.extra_land_drops_used = 0
    gs.state_based_actions()

    if gs.trace:
        log("── End ──")

    return log_entries


def protagonist_turn(gs, turn, matchup):
    """P1's turn — thin wrapper around _execute_turn."""
    return _execute_turn(gs, turn, gs.p1, gs.p2, 'p1', matchup)


def opp_turn_unified(gs, turn, matchup):
    """P2's turn — thin wrapper around _execute_turn."""
    return _execute_turn(gs, turn, gs.p2, gs.p1, 'p2', matchup)


def run_any_match(protagonist: str, antagonist: str, verbose: bool = False):
    """
    Run a Bo3 match: protagonist deck vs antagonist deck.
    protagonist and antagonist are matchup keys (e.g. 'dimir', 'storm', 'elves').
    Returns (protagonist_wins, antagonist_wins, games_played, results).
    """
    import random

    protagonist_wins = antagonist_wins = games_played = 0
    results = []

    for game_num in range(1, 4):
        if protagonist_wins == 2 or antagonist_wins == 2:
            break
        games_played += 1

        use_sideboard = (game_num > 1)

        if use_sideboard:
            pro_deck_fn = lambda: make_postboard_any_deck(protagonist, antagonist)
            try:
                from cards import make_postboard_opp_vs_protagonist
                ant_deck_fn = lambda: make_postboard_opp_vs_protagonist(protagonist, antagonist)
            except Exception:
                ant_deck_fn = lambda: make_postboard_opp_deck(antagonist)
        else:
            pro_deck_fn  = DECKS[protagonist]
            ant_deck_fn  = DECKS[antagonist]

        pro_hand, pro_lib, pro_mulls = london_mulligan(pro_deck_fn, opp_keep, protagonist)
        ant_hand, ant_lib, ant_mulls = london_mulligan(ant_deck_fn, opp_keep, antagonist)

        pro_goes_first = random.random() < 0.5
        pro_player = PlayerState(name='b', hand=list(pro_hand), library=list(pro_lib))
        ant_player = PlayerState(name='o', hand=list(ant_hand), library=list(ant_lib))
        gs = GameState(p1=pro_player, p2=ant_player, p1_goes_first=pro_goes_first)
        gs.matchup = antagonist
        gs.p1_deck = protagonist
        gs.p2_deck = antagonist

        all_log = []
        for turn in range(1, GR.MAX_TURNS + 1):
            if gs.game_over: break
            gs.turn = turn

            first, second = ('p1', 'p2') if pro_goes_first else ('p2', 'p1')
            for who in (first, second):
                lines = play_turn(gs, turn, who)
                label = 'PRO' if who == 'p1' else 'ANT'
                all_log += [f"G{game_num}T{turn}[{label}] {l}" for l in lines]
                if gs.game_over: break

        if not gs.game_over:
            pro_power = sum(c.power for c in gs.p1.creatures)
            ant_power = sum(c.power for c in gs.p2.creatures)
            if pro_power > ant_power or gs.p1.life > gs.p2.life + 3:
                gs.winner = 'p1'; gs.win_reason = f"Board advantage G{game_num}"
                gs.kill_turn = gs.turn
            else:
                gs.winner = 'p2'; gs.win_reason = f"Opp board advantage G{game_num}"

        result = GameResult(
            winner=gs.winner, win_reason=gs.win_reason or '',
            kill_turn=gs.kill_turn, game_length=gs.turn,
            p1_mulls=pro_mulls, p2_mulls=ant_mulls,
            p1_opening_hand=[c.name for c in pro_hand],
            p2_opening_hand=[c.name for c in ant_hand],
            log_lines=all_log,
            final_p1_life=gs.p1.life, final_p2_life=gs.p2.life,
            p1_went_first=pro_goes_first,
            p1_deck=protagonist, p2_deck=antagonist,
        )
        results.append(result)
        if gs.winner == 'p1': protagonist_wins += 1
        else: antagonist_wins += 1

    return protagonist_wins, antagonist_wins, games_played, results


def run_any_bo3(protagonist: str, antagonist: str, n_matches: int) -> dict:
    """Run n_matches Bo3 matches, protagonist vs antagonist. Returns WR stats."""
    wins = 0
    all_results = []
    for _ in range(n_matches):
        pw, aw, _, grs = run_any_match(protagonist, antagonist)
        if pw > aw: wins += 1
        all_results.extend(grs)
    game_wins = sum(1 for r in all_results if r.winner == 'p1')
    total_games = len(all_results)
    return {
        'match_wr': wins / n_matches,
        'game_wr': game_wins / total_games if total_games else 0,
        'wins': wins, 'n': n_matches
    }


def best_deck_for_field(field: dict, n_per_matchup: int = 1000,
                        decks: list = None) -> list:
    """
    Compute expected match WR for each deck against the given field.
    field: {matchup_key: share} e.g. {'uwx': 0.18, 'mardu': 0.12, ...}
    decks: list of protagonist keys to evaluate (default: all known decks)
    Returns sorted list of (deck, ev_wr) tuples, best first.
    """
    if decks is None:
        decks = list(STRATEGIES.keys()) + ['bug']

    field_total = sum(field.values())
    field_norm  = {k: v/field_total for k, v in field.items()}

    results = {}
    for protagonist in decks:
        ev = 0.0
        for antagonist, share in field_norm.items():
            if antagonist not in DECKS and antagonist != 'bug':
                continue
            r = run_any_bo3(protagonist, antagonist, n_per_matchup)
            ev += share * r['match_wr'] * 100
            print(f"  {protagonist} vs {antagonist}: {r['match_wr']*100:.1f}%  (weight {share:.2f})")
        results[protagonist] = ev
        print(f"  → {protagonist} EV: {ev:.1f}%")
        print()

    return sorted(results.items(), key=lambda x: -x[1])


# ─────────────────────────────────────────────────────────────────────────────
# Protagonist sideboard pools and swap plans
# ─────────────────────────────────────────────────────────────────────────────

def _make_sb_cards():
    """Common sideboard card factory — returns a pool of Card objects by tag."""
    pool = {}
    pool['fon']       = [instant('Force of Negation', 3, {'U':1,'generic':2}, {'U'}, tag='fon',
                                  free_cast_if_blue=True, is_combo_piece=False)] * 6
    pool['pyro']      = [instant('Pyroblast', 1, {'R':1}, {'R'}, tag='pyro')] * 4
    pool['hydro']     = [instant('Hydroblast', 1, {'U':1}, {'U'}, tag='hydro')] * 4
    pool['barrow']    = [creature('Barrowgoyf', 2, {'B':1,'generic':1}, {'B'}, 2, 3, tag='barrow')] * 3
    pool['massacre']  = [sorcery('Massacre', 4, {'B':1,'generic':3}, {'B'}, tag='massacre',
                                  is_mass_removal=True, is_removal=True)] * 3
    pool['nihil']     = [artifact('Nihil Spellbomb', 1, {}, tag='nihil')] * 3
    pool['fluster']   = [instant('Flusterstorm', 1, {'U':1}, {'U'}, tag='fluster')] * 2
    pool['mindbreak'] = [instant('Mindbreak Trap', 4, {'W':1,'generic':3}, {'W'}, tag='mindbreak')] * 2
    pool['snuffout']  = [instant('Snuff Out', 4, {'B':1,'generic':3}, {'B'}, tag='snuffout',
                                  is_removal=True)] * 2
    pool['endurance'] = [creature('Endurance', 3, {'G':1,'generic':2}, {'G'}, 3, 4, tag='endurance',
                                   flash=True)] * 3
    pool['fovig']     = [instant('Force of Vigor', 4, {'G':2,'generic':2}, {'G'}, tag='fovig',
                                  free_cast_if_blue=False)] * 2
    pool['collector'] = [creature('Collector Ouphe', 2, {'G':1,'generic':1}, {'G'}, 2, 2, tag='collector')] * 2
    pool['leyline']   = [enchantment('Leyline of Sanctity', 4, {'W':2,'generic':2}, {'W'},
                                      tag='leyline')] * 2 if 'enchantment' in dir() else []
    pool['surgical']  = [instant('Surgical Extraction', 0, {'B':1}, {'B'}, tag='surgical')] * 2
    # Sanctifier en-Vec — anti-burn / anti-red+black creature, 2/2 pro-red+black.
    # Used by mana_drain SB plan vs burn / mono_black matchups.
    pool['sanctifier'] = [creature('Sanctifier en-Vec', 2, {'W':1,'generic':1}, {'W'},
                                    2, 2, tag='sanctifier', pro_red=True)] * 2
    pool['sblood']    = [instant('Searing Blood', 2, {'R':2}, {'R'}, tag='sblood',
                                  is_removal=True)] * 4
    pool['eidolon']   = [creature('Eidolon of the Great Revel', 2, {'R':2}, {'R'}, 2, 2,
                                   tag='eidolon')] * 4
    pool['smash']     = [instant('Smash to Smithereens', 2, {'R':1,'generic':1}, {'R'},
                                  tag='smash')] * 4
    pool['heat']      = [instant('Searing Blaze', 2, {'R':2}, {'R'}, tag='heat',
                                  is_removal=True)] * 4
    pool['abrupt']    = [instant('Abrupt Decay', 2, {'B':1,'G':1}, {'B','G'}, tag='abrupt',
                                  is_removal=True)] * 2
    # UWx SB additions
    pool['flusterwx'] = [instant('Flusterstorm', 1, {'U':1}, {'U'}, tag='fluster')] * 2
    pool['pyruwx']    = [instant('Pyroblast', 1, {'R':1}, {'R'}, tag='pyro')] * 2
    pool['reb']       = [instant('Red Elemental Blast', 1, {'R':1}, {'R'}, tag='pyro')] * 2
    pool['needle']    = [artifact('Pithing Needle', 1, {'generic':1}, tag='needle')] * 3
    pool['rishadan']  = []  # Rishadan Port is a land — use nihil as proxy for Lands SB
    pool['vos']       = [instant('Veil of Summer', 1, {'G':1}, {'G'}, tag='vos')] * 4
    pool['unmask']    = [instant('Unmask', 0, {'B':1}, {'B'}, tag='unmask')] * 2
    pool['wst']       = []  # Wasteland (already in main, can't add more) — use nihil as proxy
    return pool


# Swap plans: {protagonist: {antagonist: ([remove (tag,n)], [add (tag,n)])}}
PROTAGONIST_SB_SWAPS = {
    'dimir': {
        'uwx':        ([('push',2),('ts',1)],         [('fon',2),('pyro',1)]),
        'show':       ([('push',3),('daze',2)],        [('fon',3),('nihil',1),('snuffout',1)]),
        'storm':      ([('push',3),('daze',1)],        [('fon',2),('fluster',1),('mindbreak',1)]),
        'prison':     ([('push',2),('daze',1)],        [('fon',2),('pyro',1)]),
        'reanimator': ([('push',2),('daze',1)],        [('fon',2),('nihil',1)]),
        'mardu':      ([('ts',1),('daze',1)],          [('massacre',2)]),
        'eldrazi':    ([('ts',2)],                     [('fon',1),('snuffout',1)]),
        'dnt':        ([('ts',2)],                     [('massacre',2)]),
        'boros':      ([('ts',2)],                     [('massacre',2)]),
        'mono_black': ([('ts',2),('push',1)],          [('pyro',2),('hydro',1)]),
        'ur_aggro':   ([('ts',2),('push',1)],          [('pyro',2),('hydro',1)]),
        'doomsday':   ([('push',3)],                   [('fon',2),('nihil',1)]),
        'oops':       ([('push',3)],                   [('fon',3)]),
        'lands':      ([('push',1),('ts',1)],          [('fon',1),('nihil',1)]),
        'bug':        ([('push',1)],                     [('pyro',1)]),
        'burn':       ([('ts',1)],                       [('sblood',1)]),
        'elves':      ([('push',1)],                     [('massacre',1)]),
        'infect':     ([('push',1)],                     [('snuffout',1)]),
        'painter':    ([('push',1)],                     [('pyro',1)]),
        'ur_delver':  ([('push',1)],                     [('pyro',1)]),
        'ur_tempo':   ([('push',1)],                     [('pyro',1)]),
    },
    'uwx': {
        'dimir':      ([('b2b',1)],                    [('pyro',1)]),
        'mardu':      ([('b2b',1),('narset',1)],       [('massacre',2)]),
        'storm':      ([('b2b',1),('snap',1)],         [('fluster',1),('mindbreak',1)]),
        'show':       ([('b2b',1),('snap',1)],         [('fon',2)]),
        'reanimator': ([('b2b',1),('narset',1)],       [('nihil',1),('surgical',1)]),
        'prison':     ([('narset',1),('b2b',1)],       [('fon',2)]),
        'dnt':        ([('narset',1)],                 [('fluster',1)]),
        'oops':       ([('snap',2)],                   [('fon',2)]),
        'doomsday':   ([('snap',2)],                   [('fon',2)]),
        'lands':      ([('narset',1)],                 [('pyro',1)]),
        'boros':      ([('snap',1)],                   [('mindbreak',1)]),
        'bug':        ([('snap',1)],                   [('pyro',1)]),
        'burn':       ([('snap',1)],                   [('nihil',1)]),
        'eldrazi':    ([('snap',1)],                   [('mindbreak',1)]),
        'elves':      ([('snap',1)],                   [('massacre',1)]),
        'infect':     ([('snap',1)],                   [('snuffout',1)]),
        'mono_black': ([('snap',1)],                   [('snuffout',1)]),
        'painter':    ([('snap',1)],                   [('pyro',1)]),
        'ur_aggro':   ([('snap',1)],                   [('pyro',1)]),
        'ur_delver':  ([('snap',1)],                   [('pyro',1)]),
        'ur_tempo':   ([('snap',1)],                   [('pyro',1)]),
    },
    'show': {
        'dimir':      ([('daze',2)],                   [('vos',2)]),
        'uwx':        ([('daze',2)],                   [('vos',2)]),
        'storm':      ([('daze',1)],                   [('fon',1)]),
        'dnt':        ([('daze',2)],                   [('vos',2)]),
        'boros':      ([('daze',1)],                   [('vos',1)]),
        'bug':        ([('daze',2)],                   [('vos',2)]),
        'burn':       ([('daze',1)],                   [('vos',1)]),
        'doomsday':   ([('daze',1)],                   [('fon',1)]),
        'eldrazi':    ([('daze',1)],                   [('vos',1)]),
        'elves':      ([('daze',1)],                   [('vos',1)]),
        'infect':     ([('daze',1)],                   [('vos',1)]),
        'lands':      ([('daze',1)],                   [('fon',1)]),
        'mardu':      ([('daze',1)],                   [('vos',1)]),
        'mono_black': ([('daze',1)],                   [('vos',1)]),
        'oops':       ([('daze',1)],                   [('fon',1)]),
        'painter':    ([('daze',1)],                   [('vos',1)]),
        'prison':     ([('daze',1)],                   [('fon',1)]),
        'reanimator': ([('daze',1)],                   [('surgical',1)]),
        'ur_aggro':   ([('daze',1)],                   [('vos',1)]),
        'ur_delver':  ([('daze',1)],                   [('vos',1)]),
        'ur_tempo':   ([('daze',1)],                   [('vos',1)]),
    },
    'elves': {
        'dimir':      ([('qranger',1),('symbiote',1)],  [('endurance',2)]),
        'mardu':      ([('qranger',1),('symbiote',1)],  [('endurance',2)]),
        'prison':     ([('recsage',1),('espirit',1)],   [('fovig',2)]),
        'storm':      ([('qranger',1)],                  [('mindbreak',1)]),
        'reanimator': ([('qranger',1),('symbiote',1)],  [('endurance',2)]),
        'mono_black': ([('qranger',1),('symbiote',1)],  [('endurance',2)]),
        'ur_aggro':   ([('qranger',1)],                  [('endurance',1)]),
        'painter':    ([('recsage',1),('espirit',1)],   [('collector',2)]),
        'oops':       ([('qranger',1)],                  [('mindbreak',1)]),
        'doomsday':   ([('qranger',1)],                  [('mindbreak',1)]),
        'boros':      ([('qranger',1)],                  [('endurance',1)]),
        'bug':        ([('qranger',1),('symbiote',1)],  [('endurance',2)]),
        'burn':       ([('qranger',1)],                  [('endurance',1)]),
        'dnt':        ([('qranger',1)],                  [('endurance',1)]),
        'eldrazi':    ([('qranger',1)],                  [('mindbreak',1)]),
        'infect':     ([('qranger',1)],                  [('endurance',1)]),
        'lands':      ([('qranger',1)],                  [('fon',1)]),
        'show':       ([('qranger',1)],                  [('fon',1)]),
        'ur_delver':  ([('qranger',1)],                  [('endurance',1)]),
        'ur_tempo':   ([('qranger',1)],                  [('endurance',1)]),
        'uwx':        ([('qranger',1)],                  [('endurance',1)]),
    },

    # ── Storm (ANT) protagonist SB ───────────────────────────────────────────
    # Storm boards Veil of Summer vs interaction; more tutors vs GY hate
    'storm': {
        'dimir':      ([('bs',1)],                       [('vos',1)]),
        'uwx':        ([('bs',1)],                       [('vos',1)]),
        'bug':        ([('bs',1)],                       [('vos',1)]),
        'dnt':        ([('bs',1)],                       [('vos',1)]),
        'mardu':      ([('bs',1)],                       [('vos',1)]),
        'reanimator': ([('bs',1)],                       [('nihil',1)]),
        'eldrazi':    ([('bs',1)],                       [('vos',1)]),
        'boros':      ([('bs',1)],                       [('vos',1)]),
        'mono_black': ([('bs',1)],                       [('vos',1)]),
        'prison':     ([('bs',2)],                       [('vos',1),('fon',1)]),
        'burn':       ([('bs',1)],                       [('vos',1)]),
        'doomsday':   ([('bs',1)],                       [('fon',1)]),
        'elves':      ([('bs',1)],                       [('vos',1)]),
        'infect':     ([('bs',1)],                       [('vos',1)]),
        'lands':      ([('bs',1)],                       [('fon',1)]),
        'oops':       ([('bs',1)],                       [('fon',1)]),
        'painter':    ([('bs',1)],                       [('mindbreak',1)]),
        'show':       ([('bs',1)],                       [('fon',1)]),
        'ur_aggro':   ([('bs',1)],                       [('vos',1)]),
        'ur_delver':  ([('bs',1)],                       [('vos',1)]),
        'ur_tempo':   ([('bs',1)],                       [('vos',1)]),
    },

    # ── Oops All Spells protagonist SB ───────────────────────────────────────
    # Oops boards nothing useful — the deck is all-in combo. Nominal swaps.
    'oops': {
        'dimir':      ([('therapy',1)],                  [('nihil',1)]),
        'uwx':        ([('therapy',1)],                  [('nihil',1)]),
        'bug':        ([('therapy',1)],                  [('nihil',1)]),
        'reanimator': ([('therapy',1)],                  [('nihil',1)]),
        'storm':      ([('therapy',1)],                  [('nihil',1)]),
        'doomsday':   ([('therapy',1)],                  [('nihil',1)]),
        'boros':      ([('therapy',1)],                  [('mindbreak',1)]),
        'burn':       ([('therapy',1)],                  [('mindbreak',1)]),
        'dnt':        ([('therapy',1)],                  [('mindbreak',1)]),
        'eldrazi':    ([('therapy',1)],                  [('mindbreak',1)]),
        'elves':      ([('therapy',1)],                  [('mindbreak',1)]),
        'infect':     ([('therapy',1)],                  [('vos',1)]),
        'lands':      ([('therapy',1)],                  [('fon',1)]),
        'mardu':      ([('therapy',1)],                  [('mindbreak',1)]),
        'mono_black': ([('therapy',1)],                  [('mindbreak',1)]),
        'painter':    ([('therapy',1)],                  [('mindbreak',1)]),
        'prison':     ([('therapy',1)],                  [('fon',1)]),
        'show':       ([('therapy',1)],                  [('fon',1)]),
        'ur_aggro':   ([('therapy',1)],                  [('vos',1)]),
        'ur_delver':  ([('therapy',1)],                  [('vos',1)]),
        'ur_tempo':   ([('therapy',1)],                  [('vos',1)]),
    },

    # ── Doomsday protagonist SB ───────────────────────────────────────────────
    # Doomsday boards Flusterstorm vs Storm, extra protection vs interaction
    'doomsday': {
        'storm':      ([('bs',1)],                       [('fluster',1)]),
        'dimir':      ([('bs',1)],                       [('fon',1)]),
        'uwx':        ([('bs',1)],                       [('fon',1)]),
        'bug':        ([('bs',1)],                       [('fon',1)]),
        'oops':       ([('bs',1)],                       [('nihil',1)]),
        'reanimator': ([('bs',1)],                       [('nihil',1)]),
        'boros':      ([('bs',1)],                       [('mindbreak',1)]),
        'burn':       ([('bs',1)],                       [('vos',1)]),
        'dnt':        ([('bs',1)],                       [('mindbreak',1)]),
        'eldrazi':    ([('bs',1)],                       [('mindbreak',1)]),
        'elves':      ([('bs',1)],                       [('mindbreak',1)]),
        'infect':     ([('bs',1)],                       [('vos',1)]),
        'lands':      ([('bs',1)],                       [('fon',1)]),
        'mardu':      ([('bs',1)],                       [('mindbreak',1)]),
        'mono_black': ([('bs',1)],                       [('mindbreak',1)]),
        'painter':    ([('bs',1)],                       [('mindbreak',1)]),
        'prison':     ([('bs',1)],                       [('fon',1)]),
        'show':       ([('bs',1)],                       [('fon',1)]),
        'ur_aggro':   ([('bs',1)],                       [('vos',1)]),
        'ur_delver':  ([('bs',1)],                       [('vos',1)]),
        'ur_tempo':   ([('bs',1)],                       [('vos',1)]),
    },

    # ── Reanimator protagonist SB ─────────────────────────────────────────────
    # Reanimator boards Unmask + extra Reanimate vs disruption; Leyline vs GY hate
    'reanimator': {
        'dimir':      ([('animate',1)],                  [('unmask',1)]),
        'uwx':        ([('animate',1)],                  [('unmask',1)]),
        'bug':        ([('animate',1)],                  [('unmask',1)]),
        'storm':      ([('animate',1)],                  [('nihil',1)]),
        'oops':       ([('animate',1)],                  [('nihil',1)]),
        'mono_black': ([('animate',1)],                  [('unmask',1)]),
        'mardu':      ([('animate',1)],                  [('unmask',1)]),
        'boros':      ([('animate',1)],                  [('unmask',1)]),
        'burn':       ([('animate',1)],                  [('unmask',1)]),
        'dnt':        ([('animate',1)],                  [('unmask',1)]),
        'doomsday':   ([('animate',1)],                  [('nihil',1)]),
        'eldrazi':    ([('animate',1)],                  [('unmask',1)]),
        'elves':      ([('animate',1)],                  [('unmask',1)]),
        'infect':     ([('animate',1)],                  [('unmask',1)]),
        'lands':      ([('animate',1)],                  [('fon',1)]),
        'painter':    ([('animate',1)],                  [('unmask',1)]),
        'prison':     ([('animate',1)],                  [('fon',1)]),
        'show':       ([('animate',1)],                  [('fon',1)]),
        'ur_aggro':   ([('animate',1)],                  [('unmask',1)]),
        'ur_delver':  ([('animate',1)],                  [('unmask',1)]),
        'ur_tempo':   ([('animate',1)],                  [('unmask',1)]),
    },

    # ── Mardu Aggro protagonist SB ────────────────────────────────────────────
    # Mardu boards Mindbreak Trap vs combo; extra removal vs creature decks
    'mardu': {
        'storm':      ([('ts',1)],                       [('mindbreak',1)]),
        'oops':       ([('ts',1)],                       [('mindbreak',1)]),
        'doomsday':   ([('ts',1)],                       [('mindbreak',1)]),
        'show':       ([('ts',1)],                       [('mindbreak',1)]),
        'reanimator': ([('ts',1)],                       [('nihil',1)]),
        'elves':      ([('ts',1)],                       [('massacre',1)]),
        'dnt':        ([('ts',1)],                       [('massacre',1)]),
        'dimir':      ([('ts',1)],                       [('mindbreak',1)]),
        'uwx':        ([('ts',1)],                       [('mindbreak',1)]),
        'bug':        ([('ts',1)],                       [('mindbreak',1)]),
        'boros':      ([('ts',1)],                       [('massacre',1)]),
        'burn':       ([('ts',1)],                       [('sblood',1)]),
        'eldrazi':    ([('ts',1)],                       [('massacre',1)]),
        'infect':     ([('ts',1)],                       [('snuffout',1)]),
        'lands':      ([('ts',1)],                       [('fon',1)]),
        'mono_black': ([('ts',1)],                       [('snuffout',1)]),
        'painter':    ([('ts',1)],                       [('mindbreak',1)]),
        'prison':     ([('ts',1)],                       [('fon',1)]),
        'ur_aggro':   ([('ts',1)],                       [('heat',1)]),
        'ur_delver':  ([('ts',1)],                       [('heat',1)]),
        'ur_tempo':   ([('ts',1)],                       [('heat',1)]),
    },

    # ── Boros Initiative protagonist SB ──────────────────────────────────────
    # Boros boards Mindbreak vs combo; Surgical vs GY decks; more removal vs creature mirrors
    'boros': {
        'storm':      ([('stp',1)],                      [('mindbreak',1)]),
        'oops':       ([('stp',1)],                      [('mindbreak',1)]),
        'doomsday':   ([('stp',1)],                      [('mindbreak',1)]),
        'show':       ([('stp',1)],                      [('mindbreak',1)]),
        'reanimator': ([('stp',1)],                      [('surgical',1)]),
        'dimir':      ([('stp',1)],                      [('mindbreak',1)]),
        'uwx':        ([('stp',1)],                      [('mindbreak',1)]),
        'bug':        ([('stp',1)],                      [('mindbreak',1)]),
        'elves':      ([('wl',1)],                       [('massacre',1)]),
        'burn':       ([('stp',1)],                      [('sblood',1)]),
        'dnt':        ([('stp',1)],                      [('massacre',1)]),
        'eldrazi':    ([('stp',1)],                      [('massacre',1)]),
        'infect':     ([('stp',1)],                      [('snuffout',1)]),
        'lands':      ([('stp',1)],                      [('fon',1)]),
        'mardu':      ([('stp',1)],                      [('massacre',1)]),
        'mono_black': ([('stp',1)],                      [('snuffout',1)]),
        'painter':    ([('stp',1)],                      [('mindbreak',1)]),
        'prison':     ([('stp',1)],                      [('fon',1)]),
        'ur_aggro':   ([('stp',1)],                      [('heat',1)]),
        'ur_delver':  ([('stp',1)],                      [('heat',1)]),
        'ur_tempo':   ([('stp',1)],                      [('heat',1)]),
    },

    # ── Death and Taxes protagonist SB ────────────────────────────────────────
    # DnT boards Mindbreak vs combo; Surgical vs GY; Sanctum Prelate vs cantrip decks
    'dnt': {
        'storm':      ([('stp',1)],                      [('mindbreak',1)]),
        'oops':       ([('stp',1)],                      [('mindbreak',1)]),
        'doomsday':   ([('stp',1)],                      [('mindbreak',1)]),
        'show':       ([('stp',1)],                      [('mindbreak',1)]),
        'reanimator': ([('stp',1)],                      [('surgical',1)]),
        'elves':      ([('stp',1)],                      [('mindbreak',1)]),
        'dimir':      ([('stp',1)],                      [('mindbreak',1)]),
        'uwx':        ([('stp',1)],                      [('mindbreak',1)]),
        'bug':        ([('stp',1)],                      [('mindbreak',1)]),
        'mardu':      ([('stp',1)],                      [('massacre',1)]),
        'boros':      ([('stp',1)],                      [('massacre',1)]),
        'burn':       ([('stp',1)],                      [('sblood',1)]),
        'eldrazi':    ([('stp',1)],                      [('massacre',1)]),
        'infect':     ([('stp',1)],                      [('snuffout',1)]),
        'lands':      ([('stp',1)],                      [('fon',1)]),
        'mono_black': ([('stp',1)],                      [('snuffout',1)]),
        'painter':    ([('stp',1)],                      [('mindbreak',1)]),
        'prison':     ([('stp',1)],                      [('fon',1)]),
        'ur_aggro':   ([('stp',1)],                      [('heat',1)]),
        'ur_delver':  ([('stp',1)],                      [('heat',1)]),
        'ur_tempo':   ([('stp',1)],                      [('heat',1)]),
    },

    # ── Mono Black protagonist SB ─────────────────────────────────────────────
    # Mono Black boards Nihil vs GY decks; Mindbreak vs combo; Massacre vs creature decks
    'mono_black': {
        'storm':      ([('ts',1)],                       [('mindbreak',1)]),
        'oops':       ([('ts',1)],                       [('mindbreak',1)]),
        'doomsday':   ([('ts',1)],                       [('mindbreak',1)]),
        'reanimator': ([('ts',1)],                       [('nihil',1)]),
        'show':       ([('ts',1)],                       [('mindbreak',1)]),
        'elves':      ([('ts',1)],                       [('massacre',1)]),
        'dnt':        ([('ts',1)],                       [('massacre',1)]),
        'boros':      ([('ts',1)],                       [('massacre',1)]),
        'dimir':      ([('ts',1)],                       [('nihil',1)]),
        'uwx':        ([('ts',1)],                       [('nihil',1)]),
        'bug':        ([('ts',1)],                       [('nihil',1)]),
        'burn':       ([('ts',1)],                       [('sblood',1)]),
        'eldrazi':    ([('ts',1)],                       [('massacre',1)]),
        'infect':     ([('ts',1)],                       [('snuffout',1)]),
        'lands':      ([('ts',1)],                       [('fon',1)]),
        'mardu':      ([('ts',1)],                       [('massacre',1)]),
        'painter':    ([('ts',1)],                       [('mindbreak',1)]),
        'prison':     ([('ts',1)],                       [('fon',1)]),
        'ur_aggro':   ([('ts',1)],                       [('heat',1)]),
        'ur_delver':  ([('ts',1)],                       [('heat',1)]),
        'ur_tempo':   ([('ts',1)],                       [('heat',1)]),
    },

    # ── Eldrazi Aggro protagonist SB ──────────────────────────────────────────
    # Eldrazi boards Thorn of Amethyst (taxes spells) vs combo
    'eldrazi': {
        'storm':      ([('petal',1)],                    [('mindbreak',1)]),
        'oops':       ([('petal',1)],                    [('mindbreak',1)]),
        'doomsday':   ([('petal',1)],                    [('mindbreak',1)]),
        'show':       ([('petal',1)],                    [('mindbreak',1)]),
        'reanimator': ([('petal',1)],                    [('nihil',1)]),
        'dimir':      ([('petal',1)],                    [('mindbreak',1)]),
        'bug':        ([('petal',1)],                    [('mindbreak',1)]),
        'uwx':        ([('petal',1)],                    [('mindbreak',1)]),
        'elves':      ([('petal',1)],                    [('mindbreak',1)]),
        'boros':      ([('ssg',1)],                      [('massacre',1)]),
        'burn':       ([('ssg',1)],                      [('nihil',1)]),
        'dnt':        ([('ssg',1)],                      [('massacre',1)]),
        'infect':     ([('ssg',1)],                      [('nihil',1)]),
        'lands':      ([('petal',1)],                    [('fon',1)]),
        'mardu':      ([('ssg',1)],                      [('massacre',1)]),
        'mono_black': ([('ssg',1)],                      [('snuffout',1)]),
        'painter':    ([('petal',1)],                    [('mindbreak',1)]),
        'prison':     ([('petal',1)],                    [('fon',1)]),
        'ur_aggro':   ([('ssg',1)],                      [('heat',1)]),
        'ur_delver':  ([('ssg',1)],                      [('heat',1)]),
        'ur_tempo':   ([('ssg',1)],                      [('heat',1)]),
    },

    # ── Imperial Painter protagonist SB ───────────────────────────────────────
    # Painter boards Pyroblast (everything is blue with Painter's Servant) vs blue decks
    'painter': {
        'dimir':      ([('needle',1)],                   [('pyro',2)]),
        'uwx':        ([('needle',1)],                   [('pyro',2)]),
        'bug':        ([('needle',1)],                   [('pyro',2)]),
        'storm':      ([('needle',1)],                   [('mindbreak',1)]),
        'oops':       ([('needle',1)],                   [('nihil',1)]),
        'doomsday':   ([('needle',1)],                   [('nihil',1)]),
        'reanimator': ([('needle',1)],                   [('nihil',1)]),
        'show':       ([('needle',1)],                   [('fon',1)]),
        'elves':      ([('needle',1)],                   [('pyro',1)]),
        'boros':      ([('needle',1)],                   [('mindbreak',1)]),
        'burn':       ([('needle',1)],                   [('nihil',1)]),
        'dnt':        ([('needle',1)],                   [('massacre',1)]),
        'eldrazi':    ([('needle',1)],                   [('mindbreak',1)]),
        'infect':     ([('needle',1)],                   [('pyro',1)]),
        'lands':      ([('needle',1)],                   [('fon',1)]),
        'mardu':      ([('needle',1)],                   [('massacre',1)]),
        'mono_black': ([('needle',1)],                   [('snuffout',1)]),
        'prison':     ([('needle',1)],                   [('fon',1)]),
        'ur_aggro':   ([('needle',1)],                   [('pyro',1)]),
        'ur_delver':  ([('needle',1)],                   [('pyro',1)]),
        'ur_tempo':   ([('needle',1)],                   [('pyro',1)]),
    },

    # ── Artifacts Prison protagonist SB ───────────────────────────────────────
    # Prison boards FoN vs combo; Thorn vs fast mana decks
    'prison': {
        'storm':      ([('grind',1)],                    [('fon',1)]),
        'oops':       ([('grind',1)],                    [('fon',1)]),
        'doomsday':   ([('grind',1)],                    [('fon',1)]),
        'show':       ([('grind',1)],                    [('fon',1)]),
        'reanimator': ([('grind',1)],                    [('nihil',1)]),
        'dimir':      ([('grind',1)],                    [('fon',1)]),
        'bug':        ([('grind',1)],                    [('fon',1)]),
        'uwx':        ([('grind',1)],                    [('fon',1)]),
        'elves':      ([('grind',1)],                    [('fon',1)]),
        'boros':      ([('grind',1)],                    [('massacre',1)]),
        'burn':       ([('grind',1)],                    [('nihil',1)]),
        'dnt':        ([('grind',1)],                    [('massacre',1)]),
        'eldrazi':    ([('grind',1)],                    [('mindbreak',1)]),
        'infect':     ([('grind',1)],                    [('fon',1)]),
        'lands':      ([('grind',1)],                    [('fon',1)]),
        'mardu':      ([('grind',1)],                    [('massacre',1)]),
        'mono_black': ([('grind',1)],                    [('snuffout',1)]),
        'painter':    ([('grind',1)],                    [('mindbreak',1)]),
        'ur_aggro':   ([('grind',1)],                    [('fon',1)]),
        'ur_delver':  ([('grind',1)],                    [('fon',1)]),
        'ur_tempo':   ([('grind',1)],                    [('fon',1)]),
    },

    # ── Lands protagonist SB ──────────────────────────────────────────────────
    # Lands boards Sphere of Resistance (Rishadan Port) vs combo; Bojuka Bog vs GY
    'lands': {
        'storm':      ([('pfire',1)],                    [('nihil',1)]),
        'oops':       ([('pfire',1)],                    [('nihil',1)]),
        'doomsday':   ([('pfire',1)],                    [('nihil',1)]),
        'reanimator': ([('pfire',1)],                    [('nihil',1)]),
        'show':       ([('pfire',1)],                    [('nihil',1)]),
        'dimir':      ([('pfire',1)],                    [('nihil',1)]),
        'bug':        ([('pfire',1)],                    [('nihil',1)]),
        'uwx':        ([('pfire',1)],                    [('nihil',1)]),
        'mardu':      ([('pfire',1)],                    [('nihil',1)]),
        'boros':      ([('loam',1)],                     [('massacre',1)]),
        'burn':       ([('loam',1)],                     [('nihil',1)]),
        'dnt':        ([('loam',1)],                     [('massacre',1)]),
        'eldrazi':    ([('loam',1)],                     [('mindbreak',1)]),
        'elves':      ([('loam',1)],                     [('mindbreak',1)]),
        'infect':     ([('loam',1)],                     [('nihil',1)]),
        'mono_black': ([('loam',1)],                     [('snuffout',1)]),
        'painter':    ([('loam',1)],                     [('mindbreak',1)]),
        'prison':     ([('loam',1)],                     [('fon',1)]),
        'ur_aggro':   ([('pfire',1)],                    [('nihil',1)]),
        'ur_delver':  ([('pfire',1)],                    [('nihil',1)]),
        'ur_tempo':   ([('pfire',1)],                    [('nihil',1)]),
    },

    # ── 8-Cast protagonist SB ─────────────────────────────────────────────────
    # 8-Cast boards FoN vs combo; Thorn vs fair blue; Tormod's vs GY
    'eight_cast': {
        'storm':      ([('shadowspear',1)],              [('fon',1)]),
        'oops':       ([('shadowspear',1)],              [('nihil',1)]),
        'doomsday':   ([('shadowspear',1)],              [('nihil',1)]),
        'reanimator': ([('shadowspear',1)],              [('nihil',1)]),
        'dimir':      ([('shadowspear',1)],              [('fon',1)]),
        'bug':        ([('shadowspear',1)],              [('fon',1)]),
        'uwx':        ([('shadowspear',1)],              [('fon',1)]),
        'prison':     ([('shadowspear',1)],              [('fon',1)]),
        'elves':      ([('shadowspear',1)],              [('nihil',1)]),
    },

    # ── UR Delver protagonist SB ─────────────────────────────────────────────
    # Delver boards Pyroblast vs blue mirrors; Surgical vs GY combo;
    # extra removal vs creature decks; FoN vs fast combo
    'ur_delver': {
        'dimir':      ([('pierce',1)],                    [('pyro',1)]),
        'dimir_b':    ([('pierce',1)],                    [('pyro',1)]),
        'dimir_flash':([('pierce',1)],                    [('pyro',1)]),
        'uwx':        ([('pierce',1)],                    [('pyro',1)]),
        'bug':        ([('pierce',1)],                    [('pyro',1)]),
        'storm':      ([('bolt',1)],                      [('fon',1)]),
        'oops':       ([('bolt',1)],                      [('fon',1)]),
        'doomsday':   ([('bolt',1)],                      [('fon',1)]),
        'show':       ([('bolt',1)],                      [('fon',1)]),
        'reanimator': ([('bolt',1)],                      [('surgical',1)]),
        'dnt':        ([('pierce',1)],                    [('heat',1)]),
        'eldrazi':    ([('pierce',1)],                    [('heat',1)]),
        'elves':      ([('pierce',1)],                    [('heat',1)]),
        'lands':      ([('heat',1)],                      [('pyro',1)]),
        'sneak_a':    ([('bolt',1)],                      [('fon',1)]),
        'tes':        ([('bolt',1)],                      [('fon',1)]),
        'boros':      ([('pierce',1)],                    [('heat',1)]),
        'burn':       ([('bolt',1)],                      [('sblood',1)]),
        'infect':     ([('bolt',1)],                      [('snuffout',1)]),
        'mardu':      ([('pierce',1)],                    [('heat',1)]),
        'mono_black': ([('pierce',1)],                    [('snuffout',1)]),
        'painter':    ([('pierce',1)],                    [('pyro',1)]),
        'prison':     ([('ei',1)],                        [('fon',1)]),
        'ur_aggro':   ([('bolt',1)],                      [('pyro',1)]),
        'ur_tempo':   ([('bolt',1)],                      [('pyro',1)]),
    },

    # ── Burn protagonist SB ──────────────────────────────────────────────────
    # Burn boards Smash to Smithereens vs artifacts; Pyrostatic Pillar vs combo;
    # Searing Blood vs creature decks
    'burn': {
        'dimir':      ([('spike',1)],                     [('sblood',1)]),
        'bug':        ([('spike',1)],                     [('sblood',1)]),
        'uwx':        ([('spike',1)],                     [('sblood',1)]),
        'storm':      ([('spike',1)],                     [('eidolon',1)]),
        'oops':       ([('spike',1)],                     [('eidolon',1)]),
        'doomsday':   ([('spike',1)],                     [('eidolon',1)]),
        'show':       ([('spike',1)],                     [('eidolon',1)]),
        'reanimator': ([('spike',1)],                     [('eidolon',1)]),
        'dnt':        ([('spike',1)],                     [('sblood',1)]),
        'eldrazi':    ([('spike',1)],                     [('sblood',1)]),
        'prison':     ([('spike',1)],                     [('smash',1)]),
        'eight_cast': ([('spike',1)],                     [('smash',1)]),
        'affinity':   ([('spike',1)],                     [('smash',1)]),
        'boros':      ([('spike',1)],                     [('sblood',1)]),
        'elves':      ([('spike',1)],                     [('sblood',1)]),
        'infect':     ([('spike',1)],                     [('sblood',1)]),
        'lands':      ([('spike',1)],                     [('eidolon',1)]),
        'mardu':      ([('spike',1)],                     [('sblood',1)]),
        'mono_black': ([('spike',1)],                     [('sblood',1)]),
        'painter':    ([('spike',1)],                     [('smash',1)]),
        'ur_aggro':   ([('spike',1)],                     [('sblood',1)]),
        'ur_delver':  ([('spike',1)],                     [('sblood',1)]),
        'ur_tempo':   ([('spike',1)],                     [('sblood',1)]),
    },

    # ── Sneak & Show A protagonist SB ────────────────────────────────────────
    # Sneak boards Veil vs interaction; FoN vs other combo
    'sneak_a': {
        'dimir':      ([('daze',1)],                      [('vos',1)]),
        'bug':        ([('daze',1)],                      [('vos',1)]),
        'uwx':        ([('daze',1)],                      [('vos',1)]),
        'storm':      ([('daze',1)],                      [('fon',1)]),
        'oops':       ([('daze',1)],                      [('fon',1)]),
        'doomsday':   ([('daze',1)],                      [('fon',1)]),
        'reanimator': ([('daze',1)],                      [('surgical',1)]),
        'dnt':        ([('daze',1)],                      [('vos',1)]),
        'eldrazi':    ([('daze',1)],                      [('vos',1)]),
    },
    'sneak_b': {
        'dimir':      ([('daze',1)],                      [('vos',1)]),
        'bug':        ([('daze',1)],                      [('vos',1)]),
        'uwx':        ([('daze',1)],                      [('vos',1)]),
        'storm':      ([('daze',1)],                      [('fon',1)]),
        'reanimator': ([('daze',1)],                      [('surgical',1)]),
    },

    # ── The Epic Storm protagonist SB ────────────────────────────────────────
    # TES boards Veil vs interaction; Galvanic Relay vs grindy matchups
    'tes': {
        'dimir':      ([('petal',1)],                     [('vos',1)]),
        'bug':        ([('petal',1)],                     [('vos',1)]),
        'uwx':        ([('petal',1)],                     [('vos',1)]),
        'dnt':        ([('petal',1)],                     [('vos',1)]),
        'storm':      ([('petal',1)],                     [('fon',1)]),
        'reanimator': ([('petal',1)],                     [('nihil',1)]),
        'eldrazi':    ([('petal',1)],                     [('vos',1)]),
    },

    # ── Infect protagonist SB ────────────────────────────────────────────────
    # Infect boards Veil vs interaction; Force vs combo; extra pump vs removal
    'infect': {
        'dimir':      ([('become',1)],                    [('vos',1)]),
        'bug':        ([('become',1)],                    [('vos',1)]),
        'uwx':        ([('become',1)],                    [('vos',1)]),
        'storm':      ([('become',1)],                    [('fon',1)]),
        'oops':       ([('become',1)],                    [('fon',1)]),
        'doomsday':   ([('become',1)],                    [('fon',1)]),
        'reanimator': ([('become',1)],                    [('surgical',1)]),
        'dnt':        ([('become',1)],                    [('vos',1)]),
        'eldrazi':    ([('become',1)],                    [('vos',1)]),
        'boros':      ([('become',1)],                    [('vos',1)]),
        'burn':       ([('become',1)],                    [('vos',1)]),
        'elves':      ([('become',1)],                    [('vos',1)]),
        'lands':      ([('become',1)],                    [('fon',1)]),
        'mardu':      ([('become',1)],                    [('vos',1)]),
        'mono_black': ([('become',1)],                    [('vos',1)]),
        'painter':    ([('become',1)],                    [('fon',1)]),
        'prison':     ([('become',1)],                    [('fon',1)]),
        'show':       ([('become',1)],                    [('fon',1)]),
        'ur_aggro':   ([('become',1)],                    [('vos',1)]),
        'ur_delver':  ([('become',1)],                    [('vos',1)]),
        'ur_tempo':   ([('become',1)],                    [('vos',1)]),
    },

    # ── Dark Depths protagonist SB ───────────────────────────────────────────
    # Depths boards Surgical vs GY combo; extra discard vs combo; Abrupt Decay vs prison
    'depths': {
        'storm':      ([('push',1)],                      [('surgical',1)]),
        'oops':       ([('push',1)],                      [('surgical',1)]),
        'doomsday':   ([('push',1)],                      [('surgical',1)]),
        'reanimator': ([('push',1)],                      [('surgical',1)]),
        'show':       ([('push',1)],                      [('surgical',1)]),
        'dimir':      ([('push',1)],                      [('abrupt',1)]),
        'bug':        ([('push',1)],                      [('abrupt',1)]),
        'prison':     ([('push',1)],                      [('abrupt',1)]),
    },

    # ── BUG protagonist SB ───────────────────────────────────────────────────
    # BUG boards FoN vs combo; Surgical vs GY; Massacre vs white weenie
    'bug': {
        'storm':      ([('push',2)],                      [('fon',2)]),
        'oops':       ([('push',2)],                      [('fon',2)]),
        'doomsday':   ([('push',2)],                      [('fon',1),('nihil',1)]),
        'show':       ([('push',2)],                      [('fon',2)]),
        'reanimator': ([('push',2)],                      [('nihil',1),('surgical',1)]),
        'sneak_a':    ([('push',2)],                      [('fon',2)]),
        'dnt':        ([('ts',2)],                        [('massacre',2)]),
        'boros':      ([('ts',2)],                        [('massacre',2)]),
        'eldrazi':    ([('ts',1)],                        [('fon',1)]),
        'dimir':      ([('push',1)],                      [('pyro',1)]),
        'uwx':        ([('push',1)],                      [('pyro',1)]),
        'lands':      ([('push',1)],                      [('fon',1)]),
        'prison':     ([('push',1)],                      [('fon',1)]),
        'burn':       ([('push',1)],                      [('sblood',1)]),
        'elves':      ([('push',1)],                      [('massacre',1)]),
        'infect':     ([('push',1)],                      [('snuffout',1)]),
        'mardu':      ([('push',1)],                      [('massacre',1)]),
        'mono_black': ([('push',1)],                      [('snuffout',1)]),
        'painter':    ([('push',1)],                      [('pyro',1)]),
        'ur_aggro':   ([('push',1)],                      [('pyro',1)]),
        'ur_delver':  ([('push',1)],                      [('pyro',1)]),
        'ur_tempo':   ([('push',1)],                      [('pyro',1)]),
    },

    # ── UR Aggro protagonist SB ──────────────────────────────────────────────
    'ur_aggro': {
        'dimir':      ([('pierce',1)],                    [('pyro',1)]),
        'bug':        ([('pierce',1)],                    [('pyro',1)]),
        'uwx':        ([('pierce',1)],                    [('pyro',1)]),
        'storm':      ([('bolt',1)],                      [('fon',1)]),
        'oops':       ([('bolt',1)],                      [('fon',1)]),
        'doomsday':   ([('bolt',1)],                      [('fon',1)]),
        'reanimator': ([('bolt',1)],                      [('surgical',1)]),
        'dnt':        ([('pierce',1)],                    [('heat',1)]),
        'boros':      ([('pierce',1)],                    [('heat',1)]),
        'burn':       ([('bolt',1)],                      [('sblood',1)]),
        'eldrazi':    ([('pierce',1)],                    [('heat',1)]),
        'elves':      ([('pierce',1)],                    [('heat',1)]),
        'infect':     ([('bolt',1)],                      [('snuffout',1)]),
        'lands':      ([('pierce',1)],                    [('fon',1)]),
        'mardu':      ([('pierce',1)],                    [('heat',1)]),
        'mono_black': ([('pierce',1)],                    [('snuffout',1)]),
        'painter':    ([('pierce',1)],                    [('pyro',1)]),
        'prison':     ([('pierce',1)],                    [('fon',1)]),
        'show':       ([('daze',1)],                      [('fon',1)]),
        'ur_delver':  ([('bolt',1)],                      [('pyro',1)]),
        'ur_tempo':   ([('bolt',1)],                      [('pyro',1)]),
    },

    # ── UR Tempo protagonist SB ──────────────────────────────────────────────
    'ur_tempo': {
        'dimir':      ([('cutter',1)],                    [('pyro',1)]),
        'bug':        ([('cutter',1)],                    [('pyro',1)]),
        'uwx':        ([('cutter',1)],                    [('pyro',1)]),
        'storm':      ([('bolt',1)],                      [('fon',1)]),
        'oops':       ([('bolt',1)],                      [('fon',1)]),
        'reanimator': ([('bolt',1)],                      [('surgical',1)]),
        'boros':      ([('cutter',1)],                    [('heat',1)]),
        'burn':       ([('bolt',1)],                      [('sblood',1)]),
        'dnt':        ([('cutter',1)],                    [('heat',1)]),
        'doomsday':   ([('bolt',1)],                      [('fon',1)]),
        'eldrazi':    ([('cutter',1)],                    [('heat',1)]),
        'elves':      ([('cutter',1)],                    [('heat',1)]),
        'infect':     ([('bolt',1)],                      [('snuffout',1)]),
        'lands':      ([('cutter',1)],                    [('fon',1)]),
        'mardu':      ([('cutter',1)],                    [('heat',1)]),
        'mono_black': ([('cutter',1)],                    [('snuffout',1)]),
        'painter':    ([('cutter',1)],                    [('pyro',1)]),
        'prison':     ([('cutter',1)],                    [('fon',1)]),
        'show':       ([('daze',1)],                      [('fon',1)]),
        'ur_aggro':   ([('bolt',1)],                      [('pyro',1)]),
        'ur_delver':  ([('bolt',1)],                      [('pyro',1)]),
    },

    # ── Dimir variants — inherit from dimir with minor tweaks ────────────────
    'dimir_b': {
        'uwx':        ([('push',2),('ts',1)],             [('fon',2),('pyro',1)]),
        'storm':      ([('push',3),('daze',1)],            [('fon',2),('fluster',1),('mindbreak',1)]),
        'show':       ([('push',3),('daze',2)],            [('fon',2),('nihil',1),('snuffout',1)]),
        'reanimator': ([('push',2),('daze',1)],            [('fon',2),('nihil',1)]),
        'dnt':        ([('ts',2)],                         [('massacre',2)]),
        'oops':       ([('push',3)],                       [('fon',3)]),
    },
    'dimir_c': {
        'storm':      ([('push',2)],                       [('fon',2)]),
        'show':       ([('push',2)],                       [('fon',2)]),
        'reanimator': ([('push',2)],                       [('fon',1),('nihil',1)]),
        'dnt':        ([('ts',2)],                         [('massacre',2)]),
    },
    'dimir_d': {
        'storm':      ([('push',2)],                       [('fon',2)]),
        'show':       ([('push',2)],                       [('fon',2)]),
        'reanimator': ([('push',2)],                       [('fon',1),('nihil',1)]),
        'dnt':        ([('ts',2)],                         [('massacre',2)]),
    },
    'dimir_flash': {
        'storm':      ([('push',2)],                       [('fon',2)]),
        'show':       ([('push',2)],                       [('fon',2)]),
        'reanimator': ([('push',2)],                       [('fon',1),('nihil',1)]),
    },

    # ── Goblins protagonist SB ───────────────────────────────────────────────
    'goblins': {
        'storm':      ([('lackey',1)],                     [('mindbreak',1)]),
        'oops':       ([('lackey',1)],                     [('nihil',1)]),
        'doomsday':   ([('lackey',1)],                     [('nihil',1)]),
        'reanimator': ([('lackey',1)],                     [('nihil',1)]),
        'show':       ([('lackey',1)],                     [('mindbreak',1)]),
        'dimir':      ([('lackey',1)],                     [('pyro',1)]),
        'bug':        ([('lackey',1)],                     [('pyro',1)]),
        'uwx':        ([('lackey',1)],                     [('pyro',1)]),
    },

    # ── Belcher protagonist SB ───────────────────────────────────────────────
    'belcher': {
        'dimir':      ([('probe',1)],                      [('vos',1)]),
        'bug':        ([('probe',1)],                      [('vos',1)]),
        'uwx':        ([('probe',1)],                      [('vos',1)]),
        'storm':      ([('probe',1)],                      [('fon',1)]),
    },

    # ── Affinity protagonist SB ──────────────────────────────────────────────
    'affinity': {
        'storm':      ([('bauble',1)],                     [('fon',1)]),
        'oops':       ([('bauble',1)],                     [('nihil',1)]),
        'doomsday':   ([('bauble',1)],                     [('nihil',1)]),
        'reanimator': ([('bauble',1)],                     [('nihil',1)]),
        'dimir':      ([('bauble',1)],                     [('fon',1)]),
        'bug':        ([('bauble',1)],                     [('fon',1)]),
    },

    # ── Cephalid Breakfast protagonist SB ────────────────────────────────────
    'cephalid': {
        'dimir':      ([('daze',1)],                       [('vos',1)]),
        'bug':        ([('daze',1)],                       [('vos',1)]),
        'storm':      ([('daze',1)],                       [('fon',1)]),
        'reanimator': ([('daze',1)],                       [('surgical',1)]),
    },

    # ── Cloudpost protagonist SB ─────────────────────────────────────────────
    'cloudpost': {
        'storm':      ([('map',1)],                        [('fon',1)]),
        'oops':       ([('map',1)],                        [('fon',1)]),
        'dimir':      ([('map',1)],                        [('fon',1)]),
        'reanimator': ([('map',1)],                        [('nihil',1)]),
    },

    # ── Mana Drain protagonist SB ─────────────────────────────────────────────
    # Limited to tags that are wired into engine.try_reactive_counter and
    # actually fire: 'fon' (Force of Negation), 'fluster' (Flusterstorm).
    # Other SB-pool tags (hydro, mindbreak, nihil, needle, leyline) require
    # engine support that isn't present, so they sit dead in hand.
    #
    # General plan: vs combo decks (where the engine's major-threat gate
    # makes our counters fire), board up to more FoNs and Flusterstorms.
    # vs aggro/control we leave the main deck mostly intact.
    'mana_drain': {
        # 'storm' SB intentionally omitted — empirical sweeps showed any SFM/
        # Counterspell trim regressed the matchup (Storm is naturally bad for
        # us since the engine treats their rituals/cantrips as minor threats
        # so our counters rarely fire reactively; SB shaping doesn't help).
        # vs red-heavy aggro — Sanctifier blanket is the single strongest
        # card.  Swap SFM (vulnerable to Bolt at cmc 2) and a Counterspell
        # (mostly dead vs cmc-1 spells) for 2 extra Sanctifiers from the SB.
        'burn':       ([('sfm',2),('counter',1)],           [('sanctifier',2),('fon',1)]),
        'boros':      ([('sfm',1)],                         [('sanctifier',1)]),
        'mardu':      ([('sfm',1)],                         [('sanctifier',1)]),
        'goblins':    ([('sfm',1)],                         [('sanctifier',1)]),
        # vs mono_black — pro-black Sanctifier dodges Push+Snuff, but heavy
        # Sanctifier-stack tested worse (Hymn random discard hits extras).
        # Light 1-for-1 swap is the sweet spot.
        'mono_black': ([('sfm',1)],                         [('sanctifier',1)]),

        'doomsday':   ([('sfm',2),('equipment',1)],          [('fon',2),('fluster',1)]),
        'oops':       ([('sfm',2),('equipment',1)],          [('fon',2),('fluster',1)]),
        'reanimator': ([('sfm',2),('equipment',1)],          [('fon',2),('fluster',1)]),
        # vs combo: SFM/Batterskull are dead (no aggro to wall); trim them
        # for fast counter density.
        'show':       ([('sfm',2),('equipment',1)],          [('fon',2),('fluster',1)]),
        'sneak_a':    ([('sfm',2),('equipment',1)],          [('fon',2),('fluster',1)]),
        'sneak_b':    ([('sfm',2),('equipment',1)],          [('fon',2),('fluster',1)]),
        'painter':    ([('sfm',1),('equipment',1)],          [('fon',1),('fluster',1)]),
        'depths':     ([('counter',1)],                      [('fon',1)]),
        'lands':      ([('sfm',2),('terminus',1)],           [('fon',2),('fluster',1)]),
        'uwx':        ([('stp',1),('terminus',1)],           [('fon',1),('fluster',1)]),
        'dimir_flash':([('terminus',1)],                     [('fon',1)]),
        'eldrazi':    ([('drain',1)],                        [('fon',1)]),
        # Dimir tempo variants — Fluster swaps in for Counterspell.  Empirically
        # helps the cantrip-heavy variants (dimir, dimir_c); hurts barrowgoyf
        # variants where the goyf is a creature target Counterspell hits via
        # the major-threat gate.  Limited to the matchups where it tested
        # positively.
        'dimir':      ([('counter',1)],                      [('fluster',1)]),
        'dimir_c':    ([('counter',1)],                      [('fluster',1)]),
    },
}


def _apply_sb_swaps(main_deck: list, remove_plan: list, add_plan: list,
                    sb_pool: dict) -> list:
    """Apply remove/add swap plan to main deck using the sb_pool."""
    deck = list(main_deck)
    for tag, count in remove_plan:
        removed = 0
        remaining = []
        for card in deck:
            if card.tag == tag and removed < count:
                removed += 1
            else:
                remaining.append(card)
        deck = remaining

    for tag, count in add_plan:
        cards = sb_pool.get(tag, [])
        added = 0
        for card in cards:
            if added >= count: break
            deck.append(card)
            added += 1

    return deck


def make_postboard_any_deck(protagonist: str, antagonist: str) -> List[Card]:
    """
    Returns the post-sideboard deck for any protagonist deck vs a given antagonist.
    Falls back to main deck if no swap plan defined.
    """
    from cards import DECKS
    main = DECKS[protagonist]()
    swaps = PROTAGONIST_SB_SWAPS.get(protagonist, {})
    if antagonist not in swaps:
        return main
    remove_plan, add_plan = swaps[antagonist]
    try:
        sb_pool = _make_sb_cards()
    except Exception:
        return main
    deck = _apply_sb_swaps(main, remove_plan, add_plan, sb_pool)
    # Pad/trim to exactly 60 cards. A sideboard plan can produce an uneven
    # count when requested tags are not all present in the maindeck (e.g.
    # removing 3 'push' when only 2 exist) or when a swap pool runs short.
    # Trim overflow; pad shortfall by repeating a stable maindeck card.
    while len(deck) > 60:
        deck.pop()
    if len(deck) < 60:
        # Pad with the most common nonland tag from the original maindeck
        # (deterministic — no randomness, no magic score). Fall back to a
        # basic land if the deck is all lands (should never happen).
        from collections import Counter
        nonland_counts = Counter(c.tag for c in main if not c.is_land())
        pad_tag = nonland_counts.most_common(1)[0][0] if nonland_counts else None
        pad_card = next((c for c in main if c.tag == pad_tag), main[0])
        while len(deck) < 60:
            deck.append(pad_card)
    return deck


def make_postboard_opp_vs_protagonist(protagonist: str, antagonist: str) -> List[Card]:
    """
    Returns the antagonist deck adjusted to fight the protagonist (not BUG).
    Uses make_postboard_opp_deck where available, otherwise returns main.
    """
    from cards import DECKS, make_postboard_opp_deck
    # The existing make_postboard_opp_deck is calibrated vs BUG.
    # When protagonist is Dimir (which is similar to BUG), it works.
    # For non-BUG protagonists, we use the same adjustments as a proxy.
    try:
        return make_postboard_opp_deck(antagonist)
    except Exception:
        return DECKS[antagonist]()

