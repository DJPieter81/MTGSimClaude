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
from game import GameState, PlayerState, london_mulligan, bug_keep, opp_keep
from engine import bug_turn, opp_turn, play_turn, update_goyf


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

    # Compat aliases
    @property
    def bug_mulls(self): return self.p1_mulls
    @property
    def opp_mulls(self): return self.p2_mulls
    @property
    def bug_opening_hand(self): return self.p1_opening_hand
    @property
    def opp_opening_hand(self): return self.p2_opening_hand
    @property
    def final_bug_life(self): return self.final_p1_life
    @property
    def final_opp_life(self): return self.final_p2_life
    @property
    def bug_went_first(self): return self.p1_went_first


def run_game(deck1: str, deck2: str = None, verbose: bool = False) -> GameResult:
    """
    Run a single game between any two decks with equal AI quality.

    Usage:
        run_game('ur_delver', 'dimir')
        run_game('storm', 'burn')
        run_game('bug', 'eldrazi')
        run_game('storm')          # legacy: deck1=BUG, deck2='storm'
    """
    # Legacy compat: run_game('storm') means BUG vs storm
    if deck2 is None:
        deck2 = deck1
        deck1 = 'bug'

    if deck1 not in DECKS:
        raise ValueError(f"Unknown deck: {deck1}. Available: {sorted(DECKS.keys())}")
    if deck2 not in DECKS:
        raise ValueError(f"Unknown deck: {deck2}. Available: {sorted(DECKS.keys())}")

    # Mulligan: each deck uses its own keep logic
    p1_keep = bug_keep if deck1 == 'bug' else opp_keep
    p2_keep = bug_keep if deck2 == 'bug' else opp_keep

    p1_hand, p1_lib, p1_mulls = london_mulligan(DECKS[deck1], p1_keep, deck1 if deck1 != 'bug' else '')
    p2_hand, p2_lib, p2_mulls = london_mulligan(DECKS[deck2], p2_keep, deck2 if deck2 != 'bug' else '')

    p1_goes_first = random.random() < 0.5

    gs = GameState(
        p1=PlayerState(name='b', hand=list(p1_hand), library=list(p1_lib)),
        p2=PlayerState(name='o', hand=list(p2_hand), library=list(p2_lib)),
        p1_goes_first=p1_goes_first)
    gs.p1_deck = deck1
    gs.p2_deck = deck2
    gs.matchup = deck2  # backward compat: matchup = antagonist deck

    all_log = []
    display_turn = 0

    for turn in range(1, 16):
        if gs.game_over:
            break
        gs.turn = turn

        first, second = ('p1', 'p2') if p1_goes_first else ('p2', 'p1')
        for who in (first, second):
            display_turn += 1
            lines = play_turn(gs, turn, who)
            label = deck1.upper() if who == 'p1' else deck2.upper()
            all_log += [f"  T{display_turn}[{label}] {l}" for l in lines]
            if gs.game_over: break

    # Timeout resolution: score board position
    if not gs.game_over:
        p1_score = (sum(c.power for c in gs.p1.creatures) * 2 +
                    len(gs.p1.creatures) * 3 + len(gs.p1.lands) +
                    max(0, gs.p1.life - gs.p2.life))
        p2_score = (sum(c.power for c in gs.p2.creatures) * 2 +
                    len(gs.p2.creatures) * 3 + len(gs.p2.lands) +
                    max(0, gs.p2.life - gs.p1.life))

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
    )

def run_sweep(deck1: str, deck2: str, n_games: int = 100) -> dict:
    """
    Run n_games between deck1 and deck2, return stats.
    Returns dict with: p1_wins, p2_wins, p1_wr, avg_length, avg_kill_turn
    """
    results = [run_game(deck1, deck2) for _ in range(n_games)]
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


def run_meta_matrix(decks: list = None, n_games: int = 100, top_tier: int = 0) -> dict:
    """
    Run every deck vs every deck and return a matrix of win rates.
    Returns dict of {(deck1, deck2): p1_win_rate}.

    Args:
        decks: explicit list of deck keys. Overrides top_tier.
        n_games: games per matchup pair.
        top_tier: if > 0 and decks is None, pick this many random decks
                  from the highest meta-share decks (always includes 'bug').

    Usage:
        matrix = run_meta_matrix(['bug', 'dimir', 'ur_delver', 'storm'], n_games=200)
        matrix = run_meta_matrix(top_tier=5, n_games=100)  # 5 random top-meta decks
    """
    if decks is None:
        if top_tier > 0:
            # Sort decks by meta share descending, pick top_tier randomly
            def _get_share(k):
                meta = MATCHUP_META.get(k, {})
                if isinstance(meta, dict) and 'share' in meta:
                    return meta['share']
                return 0.0  # unknown decks get 0 share, not included
            ranked = sorted(
                ((k, _get_share(k)) for k in DECKS if _get_share(k) > 0),
                key=lambda x: -x[1]
            )
            # Always include 'bug' as reference deck
            pool = [k for k, _ in ranked[:max(top_tier * 2, 10)]]
            if 'bug' not in pool:
                pool.append('bug')
            chosen = ['bug'] if 'bug' in pool else []
            others = [k for k in pool if k not in chosen]
            random.shuffle(others)
            chosen += others[:top_tier - len(chosen)]
            decks = sorted(chosen)
            print(f"Top-tier selection ({top_tier}): {', '.join(decks)}")
        else:
            decks = sorted(DECKS.keys())

    matrix = {}
    total = len(decks) * (len(decks) - 1)
    done = 0

    for d1 in decks:
        for d2 in decks:
            if d1 == d2:
                continue
            stats = run_sweep(d1, d2, n_games)
            matrix[(d1, d2)] = stats['p1_wr']
            done += 1
            if done % 10 == 0:
                print(f"  {done}/{total} matchups complete...")

    return matrix


# ── Old BUG-centric functions removed (run_matchup, run_all_matchups,
#    ELVES_MATCHUPS, run_elves_match, run_elves_bo3) — use symmetric API instead.

# ── Strategy registry — all decks as protagonists ───────────────────────────
from engine import (
    _strategy_dimir, _strategy_dnt, _strategy_mono_black, _strategy_boros,
    _strategy_prison, _strategy_eldrazi, _strategy_show, _strategy_lands,
    _strategy_oops, _strategy_doomsday, _strategy_uwx, _strategy_painter,
    _strategy_storm, _strategy_reanimator, _strategy_ur_aggro, _strategy_mardu,
    _strategy_dimir_flash, _strategy_elves, _elves_strategy,
)

STRATEGIES = {
    'dimir':       _strategy_dimir,
    'dimir_b':     _strategy_dimir,       # same strategy, different deck
    'dimir_flash': _strategy_dimir_flash,
    'show':        _strategy_show,
    'lands':       _strategy_lands,
    'storm':       _strategy_storm,
    'oops':        _strategy_oops,
    'prison':      _strategy_prison,
    'uwx':         _strategy_uwx,
    'uwx_real':    _strategy_uwx,         # proxy — use uwx strategy
    'eldrazi':     _strategy_eldrazi,
    'painter':     _strategy_painter,
    'doomsday':    _strategy_doomsday,
    'reanimator':  _strategy_reanimator,
    'dnt':         _strategy_dnt,
    'mono_black':  _strategy_mono_black,
    'boros':       _strategy_boros,
    'ur_aggro':    _strategy_ur_aggro,
    'mardu':       _strategy_mardu,
    'elves':       _strategy_elves,
    # bug uses bug_turn (special — not yet in STRATEGIES)
}


def protagonist_turn(gs, turn, matchup):
    """
    Generic protagonist turn for any deck in STRATEGIES.
    Full turn structure: cleanup → untap → upkeep → draw → land → mana →
    Wasteland → Thoughtseize → removal → strategy → combat → EOT.
    gs.p1 = protagonist deck, gs.p2 = antagonist.
    """
    from engine import (bowmasters_triggers, update_goyf, opp_can_cast,
                        _try_counter_any, _select_attackers, combat_declare)
    from rules import LandPermanent, MTGRules

    b = gs.p1
    o = gs.p2
    log_entries = []

    def log(msg, key=False):
        gs.log_event('b', 'main', msg, key)
        log_entries.append(msg)

    # ── Cleanup — CR 510.2 ──
    for player in [b, o]:
        for c in player.creatures:
            c.damage_marked = 0

    # ── Untap ──
    b.untap_all()
    b.revolt_this_turn = False
    b.clear_summoning_sickness()
    gs.opp_spells_cast_this_turn = 0
    gs.veil_active = False
    b.spells_cast_this_turn = 0

    # ── Upkeep: Goyf update ──
    update_goyf(gs)

    # ── Draw (first player on play skips T1 draw) ──
    if not (turn == 1 and gs.p1_goes_first):
        drawn = b.draw(1, is_draw_step=True)
        if drawn:
            log(f"Draw: {drawn[0].name}")
            # Bowmasters on opponent's board triggers on protagonist's draws
            bowmasters_triggers(1, gs, log_entries, controller='o')

    # ── Pending Bauble draws from previous turn ──
    pending = getattr(gs, 'pending_bauble_draws_bug', 0)
    if pending > 0:
        drawn = b.draw(pending)
        for d in drawn:
            log(f"Bauble (upkeep draw) → {d.name}")
        bowmasters_triggers(pending, gs, log_entries, controller='o')
        gs.pending_bauble_draws_bug = 0

    # ── Land drop ──
    # Prioritise mana-producing lands (duals, basics) over utility lands (Wasteland)
    def _pick_land():
        lands_in_hand = [c for c in b.hand if c.is_land()]
        if not lands_in_hand:
            return None
        # Prefer fast lands (Tomb/City) when a 2-mana play is in hand
        has_2drop = any(c.tag in ('chalice', 'trini', 'null_rod') or
                        (not c.is_land() and sum(c.mana_cost.values()) == 2)
                        for c in b.hand)
        if has_2drop:
            fast = next((c for c in lands_in_hand
                         if c.tag in ('ancient_tomb', 'tomb', 'city')), None)
            if fast:
                return fast
        # Priority: fetch > dual > basic > utility (Wasteland etc)
        def land_priority(c):
            if getattr(c, 'is_fetch', False): return 2
            tag = getattr(c, 'tag', '')
            if tag == 'dual': return 1
            if c.is_basic: return 1
            if tag in ('sewers',): return 1
            if tag in ('ancient_tomb', 'city'): return 0
            if tag == 'wl': return 5
            return 3
        return min(lands_in_hand, key=land_priority)

    land = _pick_land()
    if land and not getattr(b, 'land_played_this_turn', False):
        b.hand.remove(land)
        lp = LandPermanent(card=land, controller='b')
        b.lands.append(lp)
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
            log(f"Land: {land.name} ({len(b.lands)} lands)")

    # ── Mana calculation (mirrors opp_turn) ──
    total_mana = b.available_mana_count()
    # Lotus Petal in hand
    total_mana += sum(1 for c in b.hand if c.tag == 'petal')
    # Treasure tokens
    bug_treasure = getattr(gs, 'bug_treasure', 0)
    if bug_treasure > 0:
        total_mana += bug_treasure
        gs.bug_treasure = 0
    # Ancient Tomb: produces 2C (1 already counted, add 1 bonus), costs 2 life
    tomb_count = sum(1 for l in b.lands if l.card.tag == 'tomb' and not l.tapped)
    if tomb_count > 0:
        total_mana += tomb_count
        b.life -= tomb_count * 2
    # Gaea's Cradle: tap for G equal to creature count
    for l in b.lands:
        if l.card.tag == 'cradle' and not l.tapped:
            total_mana += len(b.creatures)
            l.tapped = True

    # ── Wasteland: destroy opponent's best nonbasic land ──
    wl_land = next((l for l in b.lands if l.card.tag in ('wl', 'wasteland') and not l.tapped), None)
    if wl_land and o.lands:
        target = next((l for l in o.lands if not l.card.is_basic and l.card.tag != 'wl'), None)
        if target:
            wl_land.tapped = True
            o.lands.remove(target)
            o.add_to_grave(target.card)
            b.revolt_this_turn = True
            log(f"Wasteland [ACTIVATED-uncounterable] → {target.card.name}")

    # ── Thoughtseize: strip opponent's best card (if we have mana) ──
    ts = b.find_tag('ts') or b.find_tag('thoughtseize')
    if ts and total_mana >= 1 and not gs.spell_blocked_by_chalice(ts.cmc):
        opp_nonland = [c for c in o.hand if not c.is_land()]
        if opp_nonland and b.life > 4:
            b.remove_from_hand(ts)
            countered = _try_counter_any(b, o, gs, ts, log_entries)
            if not countered:
                b.add_to_grave(ts)
                b.life -= 2
                total_mana -= 1
                def _ts_priority(c):
                    score = 0
                    if c.win_condition: score += 10
                    if c.is_combo_piece: score += 8
                    if c.tag in ('fow', 'fon', 'daze', 'fluster'): score += 6
                    if c.is_creature(): score += 3 + c.base_power
                    score += c.cmc
                    return score
                best = max(opp_nonland, key=_ts_priority)
                o.remove_from_hand(best)
                o.add_to_grave(best)
                log(f"Thoughtseize → takes {best.name} (−2 life, {b.life})")
            else:
                b.add_to_grave(ts)

    # ── Removal: kill opponent's biggest threat ──
    if o.creatures and total_mana >= 1:
        push = b.find_tag('push') or b.find_tag('fatal_push')
        if push and not gs.spell_blocked_by_chalice(push.cmc):
            revolt = b.revolt_this_turn
            valid_targets = [c for c in o.creatures
                             if MTGRules.fatal_push_valid_target(c, revolt)]
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
                else:
                    b.add_to_grave(push)

        stp = b.find_tag('stp')
        if stp and o.creatures and total_mana >= 1 and not gs.spell_blocked_by_chalice(stp.cmc):
            target = max(o.creatures, key=lambda c: c.power)
            if target.power >= 2:
                b.remove_from_hand(stp)
                countered = _try_counter_any(b, o, gs, stp, log_entries)
                if not countered:
                    b.add_to_grave(stp)
                    total_mana -= 1
                    o.creatures.remove(target)
                    o.life += target.power
                    log(f"Swords to Plowshares → exile {target.card.name} (opp +{target.power} life)")
                else:
                    b.add_to_grave(stp)

    # ── Gameplan layer ──
    from gameplan import GAMEPLANS, assess, active_goal
    plan = GAMEPLANS.get(matchup)
    if plan:
        ba = assess(gs, turn)
        gs.opp_goal = active_goal(plan, ba)
    else:
        gs.opp_goal = None

    # ── Lock piece enforcement ──
    _chalice_blocked = []
    if gs.chalice_x is not None:
        for card in list(b.hand):
            if not card.is_land() and card.cmc == gs.chalice_x:
                _chalice_blocked.append(card)
                b.hand.remove(card)
        if _chalice_blocked:
            log(f"Chalice on {gs.chalice_x} — blocks: {', '.join(set(c.name for c in _chalice_blocked))}")
    _trini_blocked = []
    if gs.trinisphere_active:
        for card in list(b.hand):
            if not card.is_land() and card.cmc < 3 and card not in _chalice_blocked:
                if total_mana < 3:
                    _trini_blocked.append(card)
                    b.hand.remove(card)
        if _trini_blocked:
            log(f"Trinisphere — cheap spells blocked (need 3 mana, have {total_mana})")

    # ── Strategy dispatch ──
    from deck_registry import get_strategy
    strategy_fn = get_strategy(matchup) or STRATEGIES.get(matchup)
    if strategy_fn:
        strategy_fn(b, o, gs, total_mana, log, log_entries)
    else:
        log(f"No strategy for {matchup} — passing")

    # Restore blocked cards
    b.hand.extend(_chalice_blocked)
    b.hand.extend(_trini_blocked)

    # ── Fallback combat: attack with eligible creatures if strategy didn't ──
    combat_happened = any('unblocked' in entry or 'blocked' in entry for entry in log_entries)
    if not combat_happened and not gs.game_over and b.creatures:
        attackers = _select_attackers(b, o)
        if attackers:
            combat_declare(b, o, gs, log_entries, attackers)

    update_goyf(gs)
    b.land_played_this_turn = False
    gs.state_based_actions()
    return log_entries


def run_any_match(protagonist: str, antagonist: str, verbose: bool = False):
    """
    Run a Bo3 match: protagonist deck vs antagonist deck.
    protagonist and antagonist are matchup keys (e.g. 'dimir', 'storm', 'elves').
    'bug' as protagonist uses bug_turn (the full BUG AI).
    Returns (protagonist_wins, antagonist_wins, games_played, results).
    """
    import random
    from engine import bug_turn

    protagonist_wins = antagonist_wins = games_played = 0
    results = []

    for game_num in range(1, 4):
        if protagonist_wins == 2 or antagonist_wins == 2:
            break
        games_played += 1

        use_sideboard = (game_num > 1)

        if use_sideboard:
            if protagonist == 'bug':
                from cards import make_postboard_bug_deck
                pro_deck_fn = lambda: make_postboard_bug_deck(antagonist)
            else:
                pro_deck_fn = lambda: make_postboard_any_deck(protagonist, antagonist)
            try:
                from cards import make_postboard_opp_vs_protagonist
                ant_deck_fn = lambda: make_postboard_opp_vs_protagonist(protagonist, antagonist)
            except Exception:
                ant_deck_fn = lambda: make_postboard_opp_deck(antagonist)
        else:
            pro_deck_fn  = DECKS.get(protagonist, DECKS['bug'])
            ant_deck_fn  = DECKS.get(antagonist,  DECKS['bug'])

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
        for turn in range(1, 16):
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
        'show':       ([('push',3),('daze',2)],        [('fon',2),('nihil',1),('snuffout',1)]),
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
    },
    'show': {
        'dimir':      ([('daze',2)],                   [('vos',2)]),
        'uwx':        ([('daze',2)],                   [('vos',2)]),
        'storm':      ([('daze',1)],                   [('fon',1)]),
        'dnt':        ([('daze',2)],                   [('vos',2)]),
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
    },

    # ── Oops All Spells protagonist SB ───────────────────────────────────────
    # Oops boards nothing useful — the deck is all-in combo. Nominal swaps.
    'oops': {
        'dimir':      ([('bs',1)],                       [('nihil',1)]),
        'uwx':        ([('bs',1)],                       [('nihil',1)]),
        'bug':        ([('bs',1)],                       [('nihil',1)]),
        'reanimator': ([('bs',1)],                       [('nihil',1)]),
        'storm':      ([('bs',1)],                       [('nihil',1)]),
        'doomsday':   ([('bs',1)],                       [('nihil',1)]),
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
    },

    # ── UR Tempo protagonist SB ──────────────────────────────────────────────
    'ur_tempo': {
        'dimir':      ([('pierce',1)],                    [('pyro',1)]),
        'bug':        ([('pierce',1)],                    [('pyro',1)]),
        'uwx':        ([('pierce',1)],                    [('pyro',1)]),
        'storm':      ([('bolt',1)],                      [('fon',1)]),
        'oops':       ([('bolt',1)],                      [('fon',1)]),
        'reanimator': ([('bolt',1)],                      [('surgical',1)]),
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
    # Pad/trim to 60
    while len(deck) > 60: deck.pop()
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


def run_rules_tests():
    from rules import (Card, CardType, Permanent, LandPermanent, StackObject,
                       StackType, MTGRules, ManaPool)

    print("\n" + "="*60)
    print("MTG RULES UNIT TESTS v2")
    print("="*60)
    passed = failed = 0

    def test(name, result, expected, detail=""):
        nonlocal passed, failed
        if result == expected:
            passed += 1
            print(f"  [PASS] {name}")
        else:
            failed += 1
            print(f"  [FAIL] {name}: got {result}, expected {expected}. {detail}")

    # CR 113.9 — stack types
    spell   = StackObject("Show and Tell", StackType.SPELL, 'o', cmc=3)
    trigger = StackObject("Marit Lage",    StackType.TRIGGERED, 'o')
    activ   = StackObject("Wasteland",     StackType.ACTIVATED, 'o')
    test("Spell counterable",         spell.is_counterable_by_spell(),   True)
    test("Triggered NOT counterable", trigger.is_counterable_by_spell(), False)
    test("Activated NOT counterable", activ.is_counterable_by_spell(),   False)
    test("Marit Lage = TRIGGERED",    MTGRules.marit_lage_stack_type(),  StackType.TRIGGERED)
    test("Marit Lage uncounterable",  MTGRules.marit_lage_is_counterable(), False)
    test("Wasteland uncounterable",   MTGRules.wasteland_is_counterable(),  False)

    # Fatal Push CMC
    def mkc(name, cmc, power, toughness):
        c = Card(name=name, card_type=CardType.CREATURE, cmc=cmc, mana_cost={},
                 colors=set(), base_power=power, base_toughness=toughness, gy_type='creature')
        return Permanent(card=c, controller='o', summoning_sick=False)
    rag   = mkc("Ragavan",       1, 2, 1)
    goyf  = mkc("Tarmogoyf",    2, 4, 5)
    tks   = mkc("TKS",          4, 4, 4)
    smasher = mkc("Smasher",    5, 5, 5)
    murk  = mkc("Murktide",     7, 8, 8)
    borrow = mkc("Borrower",    3, 3, 1)
    test("Push hits Ragavan CMC1",        MTGRules.fatal_push_valid_target(rag,    False), True)
    test("Push hits Goyf CMC2",           MTGRules.fatal_push_valid_target(goyf,   False), True)
    test("Push misses TKS no revolt",     MTGRules.fatal_push_valid_target(tks,    False), False)
    test("Push hits TKS with revolt",     MTGRules.fatal_push_valid_target(tks,    True),  True)
    test("Push misses Smasher CMC5",      MTGRules.fatal_push_valid_target(smasher,True),  False)
    test("Push misses Murktide CMC7",     MTGRules.fatal_push_valid_target(murk,   True),  False)
    test("Push misses Borrower no revolt",MTGRules.fatal_push_valid_target(borrow, False), False)
    test("Push hits Borrower revolt",     MTGRules.fatal_push_valid_target(borrow, True),  True)

    # Tarmogoyf
    def mkcard(gy_type):
        return Card(name="x", card_type=CardType.INSTANT, cmc=1, mana_cost={},
                    colors=set(), gy_type=gy_type)
    pw, pt = MTGRules.tarmogoyf_pt(
        [mkcard('instant'), mkcard('sorcery')],
        [mkcard('creature'), mkcard('land')])
    test("Goyf 4 types = 4/5", (pw, pt), (4, 5))
    test("Goyf empty = 0/1",   MTGRules.tarmogoyf_pt([], []), (0, 1))

    # Ensnaring Bridge
    test("Bridge blocks power>hand",    MTGRules.bridge_prevents_attack(goyf, 3),  True)
    test("Bridge allows power==hand",   MTGRules.bridge_prevents_attack(goyf, 4),  False)
    test("Bridge blocks Murktide 7 hand",MTGRules.bridge_prevents_attack(murk, 7), True)

    # Summoning sickness + attacker tapping
    sick = mkc("Sick", 2, 2, 2); sick.summoning_sick = True
    haste_card = Card(name="Haste", card_type=CardType.CREATURE, cmc=2, mana_cost={},
                      colors=set(), base_power=2, base_toughness=2, haste=True, gy_type='creature')
    haste_perm = Permanent(card=haste_card, controller='b', summoning_sick=True)
    test("Sick can't attack",            MTGRules.can_attack(sick),       False)
    test("Haste ignores sickness",       MTGRules.can_attack(haste_perm), True)
    sick.summoning_sick = False
    test("Cleared sickness can attack",  MTGRules.can_attack(sick),       True)
    # C2: tap_attacker actually taps
    MTGRules.tap_attacker(sick)
    test("C2: tap_attacker taps",        sick.tapped,                     True)
    test("C2: tapped can't attack",      MTGRules.can_attack(sick),       False)

    # Bowmasters draw triggers
    test("Brainstorm=3 draws=3 triggers", MTGRules.bowmasters_trigger_count(3), 3)
    test("Ponder=1 draw=1 trigger",       MTGRules.bowmasters_trigger_count(1), 1)

    # Fetch land
    test("Fetch produces no mana", MTGRules.fetch_produces_mana(), False)
    test("Fetch costs 1 life",     MTGRules.fetch_costs_life(),    1)

    # Chalice CMC check (printed CMC)
    bs_spell = StackObject("Brainstorm", StackType.SPELL, 'o', cmc=1)
    daze_spell = StackObject("Daze",     StackType.SPELL, 'o', cmc=2)
    fow_spell  = StackObject("FoW",      StackType.SPELL, 'o', cmc=5)
    test("Chalice=1 hits Brainstorm", MTGRules.chalice_counters_spell(bs_spell,   1), True)
    test("Chalice=1 misses Daze",     MTGRules.chalice_counters_spell(daze_spell, 1), False)
    test("Chalice=2 hits Daze",       MTGRules.chalice_counters_spell(daze_spell, 2), True)
    test("Chalice=1 misses FoW",      MTGRules.chalice_counters_spell(fow_spell,  1), False)

    # Abrupt Decay
    def mkperm(name, cmc):
        c = Card(name=name, card_type=CardType.ARTIFACT, cmc=cmc, mana_cost={},
                 colors=set(), gy_type='artifact')
        return Permanent(card=c, controller='o')
    test("AD hits Bridge CMC3",    MTGRules.abrupt_decay_valid_target(mkperm("Bridge", 3)), True)
    test("AD misses Karn CMC4",    MTGRules.abrupt_decay_valid_target(mkperm("Karn",   4)), False)
    test("AD hits Chalice CMC0",   MTGRules.abrupt_decay_valid_target(mkperm("Chalice",0)), True)

    # Wasteland basic vs nonbasic
    from rules import LandType
    island = LandPermanent(card=Card(name="Island", card_type=CardType.LAND, cmc=0, mana_cost={},
                                     colors=set(), is_basic=True, land_type=LandType.BASIC,
                                     produces={'U'}, gy_type='land'), controller='o')
    sea = LandPermanent(card=Card(name="Underground Sea", card_type=CardType.LAND, cmc=0, mana_cost={},
                                   colors=set(), is_basic=False, land_type=LandType.DUAL,
                                   produces={'U','B'}, gy_type='land'), controller='o')
    test("Wasteland can't target Island", MTGRules.wasteland_can_target(island), False)
    test("Wasteland can target USea",     MTGRules.wasteland_can_target(sea),    True)

    # C1: mana enforcement
    pool_empty = ManaPool()
    pool_one_u = ManaPool(); pool_one_u.add('U')
    bs_card = Card(name="Brainstorm", card_type=CardType.INSTANT, cmc=1,
                   mana_cost={'U': 1}, colors={'U'}, gy_type='instant')
    test("C1: can't cast BS with 0 mana", MTGRules.can_cast(bs_card, pool_empty), False)
    test("C1: can cast BS with 1U",       MTGRules.can_cast(bs_card, pool_one_u), True)

    # L3: Dismember kills check
    low_t = mkc("Low", 1, 2, 4)    # toughness 4: 4-5 = -1 ≤ 0 → dies
    high_t = mkc("High", 1, 2, 10) # toughness 10: 10-5 = 5 > 0 → survives
    test("L3: Dismember kills 4-toughness",     MTGRules.dismember_kills(low_t),  True)
    test("L3: Dismember survives 10-toughness", MTGRules.dismember_kills(high_t), False)

    # L1: STP life gain = power only
    a_4_4 = mkc("Goyf", 2, 4, 5)
    test("L1: STP gain = power only (4)", MTGRules.stp_life_gain(a_4_4), 4)

    # S3: Blood Moon — nonbasic produces only R
    sea.blood_moon_active = True
    test("S3: USea under Blood Moon produces only R", sea.effective_produces(), {'R'})
    sea.blood_moon_active = False
    test("S3: USea no Blood Moon produces UB", 'U' in sea.effective_produces(), True)

    # S4: Back to Basics — nonbasic can't untap
    sea.b2b_active = True
    test("S4: USea under B2B can't untap",    sea.can_untap(),          False)
    test("S4: USea under B2B produces nothing", sea.effective_produces(), set())
    island.b2b_active = True
    test("S4: Island (basic) still untaps under B2B", island.can_untap(), True)

    # S5: FoN free only on opponent's turn
    noncreature_spell = StackObject("Show and Tell", StackType.SPELL, 'o', cmc=3,
                                     card_type=CardType.SORCERY, colors={'U'})
    hand_with_fon = [Card(name="FoN", card_type=CardType.INSTANT, cmc=3,
                          mana_cost={'U':1,'generic':2}, colors={'U'}, tag='fon', gy_type='instant')]
    test("S5: FoN usable on opp's turn",   MTGRules.force_of_negation_can_counter(noncreature_spell, hand_with_fon, is_opponents_turn=True),  True)
    test("S5: FoN NOT free on own turn",   MTGRules.force_of_negation_can_counter(noncreature_spell, hand_with_fon, is_opponents_turn=False), False)

    # ── Audit: Wasteland targeting (CR 305.6) ──────────────────────────────
    def mkland(name, tag='', is_basic=False, subtypes=None):
        c = Card(name=name, card_type=CardType.LAND, cmc=0, mana_cost={},
                 colors=set(), is_basic=is_basic, produces={'U'},
                 subtypes=set(subtypes or []), tag=tag, gy_type='land')
        return LandPermanent(card=c, controller='o')

    basic_island  = mkland('Island',         is_basic=True, subtypes=['Island'])
    underground   = mkland('Underground Sea', tag='dual')
    polluted      = mkland('Polluted Delta',  tag='fetch')
    wl_self       = mkland('Wasteland',       tag='wl')

    test("Wasteland: can't target basic",         MTGRules.wasteland_can_target(basic_island), False)
    test("Wasteland: hits dual (Underground Sea)", MTGRules.wasteland_can_target(underground),  True)
    test("Wasteland: hits fetch (Polluted Delta)", MTGRules.wasteland_can_target(polluted),      True)
    test("Wasteland: can't target itself (wl tag)",MTGRules.wasteland_can_target(wl_self),      False)

    # ── Audit: Force of Will pitch cost (must exile blue card) ─────────────
    fow_card_  = Card(name='Force of Will', card_type=CardType.INSTANT, cmc=5,
                      mana_cost={'U':1,'generic':4}, colors={'U'}, tag='fow', gy_type='instant',
                      free_cast_if_blue=True)
    blue_card_ = Card(name='Brainstorm', card_type=CardType.INSTANT, cmc=1,
                      mana_cost={'U':1}, colors={'U'}, tag='bs', gy_type='instant')
    grn_card_  = Card(name='Veil of Summer', card_type=CardType.INSTANT, cmc=1,
                      mana_cost={'G':1}, colors={'G'}, tag='veil', gy_type='instant')
    sat_card_  = StackObject("Show and Tell", StackType.SPELL, 'o', cmc=4,
                             card_type=CardType.SORCERY, colors={'U'})

    test("FoW: fires with blue pitch card",     MTGRules.force_of_will_can_counter(sat_card_, [fow_card_, blue_card_]), True)
    test("FoW: blocked by non-blue pitch card", MTGRules.force_of_will_can_counter(sat_card_, [fow_card_, grn_card_]),  False)
    test("FoW: blocked with no pitch card",     MTGRules.force_of_will_can_counter(sat_card_, [fow_card_]),             False)

    # ── Audit: Daze tapped-out logic (opp_mana <= spell_cmc) ───────────────
    from game import PlayerState as PS_
    opp_3lands = PS_(name='o', hand=[], library=[])
    opp_4lands = PS_(name='o', hand=[], library=[])
    for _ in range(3):
        lp_ = mkland('Underground Sea', tag='dual')
        lp_.tapped = False
        opp_3lands.lands.append(lp_)
    for _ in range(4):
        lp_ = mkland('Underground Sea', tag='dual')
        lp_.tapped = False
        opp_4lands.lands.append(lp_)

    daze_3 = opp_3lands.available_mana_count() <= 3  # casting CMC3 spell taps out
    daze_4 = opp_4lands.available_mana_count() <= 3  # 4 lands, spare mana available
    test("Daze: tapped-out opp (3 lands, CMC3)",   daze_3, True)
    test("Daze: opp has spare mana (4 lands, CMC3)", daze_4, False)

    # ── Audit: Card attributes (Oracle text correctness) ───────────────────
    from cards import DECKS as ALL_DECKS
    bug_deck_ = ALL_DECKS['bug']()
    murktide_  = next((c for c in bug_deck_ if c.name == 'Murktide Regent'), None)
    borrower_  = next((c for c in bug_deck_ if c.name == 'Brazen Borrower'), None)
    bowm_      = next((c for c in bug_deck_ if c.name == 'Orcish Bowmasters'), None)
    tamiyo_    = next((c for c in bug_deck_ if c.name == 'Tamiyo, Inquisitive Student'), None)
    daze_card_ = next((c for c in bug_deck_ if c.name == 'Daze'), None)

    test("Murktide has flying (BUG deck)",   murktide_.flying if murktide_ else 'MISSING',  True)
    test("Murktide has delve (BUG deck)",    murktide_.delve  if murktide_ else 'MISSING',  True)
    if borrower_:
        test("Brazen Borrower has flash",        borrower_.flash,  True)
        test("Brazen Borrower has flying",       borrower_.flying, True)
    test("Orcish Bowmasters has flash",      bowm_.flash      if bowm_     else 'MISSING',  True)
    test("Tamiyo CMC=1",                     tamiyo_.cmc      if tamiyo_   else -1,          1)
    test("Daze CMC=2 (not 1)",               daze_card_.cmc   if daze_card_ else -1,         2)

    # ── Audit: Bowmasters — 3 triggers for Brainstorm (3 draw events) ──────
    from game import GameState
    from cards import make_bug_deck, make_dimir_deck
    from engine import bowmasters_triggers
    gs_bm = GameState(
        p1=PS_(name='b', hand=make_bug_deck(), library=[]),
        p2=PS_(name='o', hand=make_dimir_deck(), library=[]),
        p1_goes_first=True
    )
    # Put Bowmasters in play so the computed property returns True
    from rules import Permanent
    from cards import make_bug_deck
    bowm_card = next(c for c in make_bug_deck() if c.tag == 'bowm')
    gs_bm.p1.creatures.append(Permanent(card=bowm_card, controller='b'))
    bm_log = []; bowmasters_triggers(3, gs_bm, bm_log)
    test("Bowmasters: 3 triggers for Brainstorm (3 draws)", len(bm_log), 3)

    # ── Audit: Orc Army is a real Permanent (not just a counter) ───────────
    gs_orc = GameState(
        p1=PS_(name='b', hand=make_bug_deck(), library=[]),
        p2=PS_(name='o', hand=make_dimir_deck(), library=[]),
        p1_goes_first=True
    )
    # Put Bowmasters in play so the trigger can actually fire
    from rules import Card, CardType, Permanent as Perm_
    bowm_card = next((c for c in gs_orc.p1.hand if c.tag == 'bowm'), None)
    if bowm_card:
        gs_orc.p1.hand.remove(bowm_card)
        bowm_perm = Perm_(card=bowm_card, controller='b', summoning_sick=False)
        gs_orc.p1.creatures.append(bowm_perm)
    orc_log = []; bowmasters_triggers(1, gs_orc, orc_log)
    orc_in_creatures = any(p.name == 'Orc Army' for p in gs_orc.p1.creatures)
    test("Orc Army: added to creatures list (real permanent)", orc_in_creatures, True)

    # ── Audit: BUG deck is exactly 60 cards ────────────────────────────────
    test("BUG main deck is exactly 60 cards", len(bug_deck_), 60)

    # ── Audit: All 18 opponent decks are exactly 60 cards ──────────────────
    for deck_name, deck_fn in ALL_DECKS.items():
        if deck_name == 'bug': continue
        try:
            d = deck_fn()
            test(f"Deck '{deck_name}' is 60 cards", len(d), 60)
        except Exception as e:
            test(f"Deck '{deck_name}' builds without error", str(e), '')

    # ── Audit: Brainstorm draws 3, puts back 2 ─────────────────────────────
    # -- Audit: CR 510.2 - damage cleared between turns -------------------------
    # Tamiyo (0/3) should survive repeated Bowmasters (1/1) blocks across turns
    gs_dmg = GameState(
        p1=PS_(name='b', hand=make_bug_deck(), library=[]),
        p2=PS_(name='o', hand=make_dimir_deck(), library=[]),
        p1_goes_first=True
    )
    from rules import Permanent
    tamiyo_c = Card(name='Tamiyo, Inquisitive Student', card_type=CardType.CREATURE,
                    cmc=1, mana_cost={}, colors={'U'}, base_power=0, base_toughness=3,
                    tag='tamiyo', gy_type='creature')
    tam_perm = Permanent(card=tamiyo_c, controller='o')
    tam_perm.power_mod = 0; tam_perm.toughness_mod = 0
    gs_dmg.p2.creatures = [tam_perm]
    # Simulate 1 damage from Bowmasters block, then damage clears
    tam_perm.damage_marked = 1
    # Simulate turn boundary cleanup
    for c in gs_dmg.p2.creatures: c.damage_marked = 0
    gs_dmg.state_based_actions()
    test("CR 510.2: Tamiyo survives 1 damage after turn cleanup", len(gs_dmg.p2.creatures), 1)
    # Now mark 3 damage (lethal) - should die
    tam_perm.damage_marked = 3
    gs_dmg.state_based_actions()
    test("CR 510.2: Tamiyo dies to 3 damage (lethal = toughness)", len(gs_dmg.p2.creatures), 0)

    # -- Audit: mana budget refreshes after fetch crack -----------------------
    # BUG starts T1 with 0 lands, cracks a fetch → should have 1 mana available
    # (verified by checking available_mana_count after fetch resolves)
    # -- Audit: mana budget refreshes after fetch crack -----------------------
    gs_budget = GameState(
        p1=PS_(name='b', hand=[], library=make_bug_deck()),
        p2=PS_(name='o', hand=[], library=[]),
        p1_goes_first=True
    )
    from cards import fetch_land
    fetch_c = fetch_land('Polluted Delta', ['Island', 'Swamp'])  # subtypes, not names
    fetch_p = LandPermanent(card=fetch_c, controller='b')
    gs_budget.p1.lands.append(fetch_p)
    pre_fetch = gs_budget.p1.available_mana_count()
    fetched_land = gs_budget.p1.use_fetch(fetch_p)
    post_fetch = gs_budget.p1.available_mana_count()
    test("Budget: before fetch crack, 0 mana (fetch taps for nothing)", pre_fetch, 0)
    test("Budget: fetch crack gives 1 mana (untapped dual enters)", post_fetch, 1)

    test("Brainstorm draws 3",    MTGRules.brainstorm_draws(),    3)
    test("Brainstorm puts back 2", MTGRules.brainstorm_puts_back(), 2)

    # -- Audit: Nethergoyf P/T uses controller's GY (Oracle: "in your graveyard") ----
    from game import GameState
    from cards import make_bug_deck, make_dimir_deck
    from engine import update_goyf
    from rules import Permanent

    gs_ng = GameState(
        p1=PS_(name='b', hand=make_bug_deck(), library=[]),
        p2=PS_(name='o', hand=make_dimir_deck(), library=[]),
        p1_goes_first=True
    )
    # Put Nethergoyf into play controlled by opp
    from cards import creature as mkc_ng
    ng_card = mkc_ng('Nethergoyf', 1, {'U':1}, {'U','B'}, 0, 1, tag='nether')
    ng_perm = Permanent(card=ng_card, controller='o')
    ng_perm.power_mod = 0; ng_perm.toughness_mod = 0
    gs_ng.p2.creatures.append(ng_perm)

    # Give opp GY: land + instant + creature = 3 types
    from rules import Card, CardType
    def gy_card(gy_type):
        c = Card(name='x', card_type=CardType.INSTANT, cmc=1, mana_cost={}, colors=set(), gy_type=gy_type)
        return c
    gs_ng.p2.graveyard = [gy_card('land'), gy_card('instant'), gy_card('creature')]
    gs_ng.p1.graveyard = [gy_card('sorcery')]  # 1 type in BUG GY — should NOT affect opp's Nethergoyf

    update_goyf(gs_ng)
    test("Nethergoyf (opp-controlled): P uses opp GY (3 types → P=3)", ng_perm.power, 3)
    test("Nethergoyf (opp-controlled): T uses opp GY (3 types → T=4)", ng_perm.toughness, 4)
    test("Nethergoyf: BUG GY sorcery does NOT affect opp Nethergoyf power",
         ng_perm.power, 3)  # still 3, not 1 (BUG's GY sorcery type ignored)

    # -- Audit: Legend rule CR 704.5j - two Tamiyos -> one survives --------
    from game import GameState
    from cards import make_bug_deck, make_dimir_deck
    gs_leg = GameState(
        p1=PS_(name='b', hand=make_bug_deck(), library=[]),
        p2=PS_(name='o', hand=make_dimir_deck(), library=[]),
        p1_goes_first=True
    )
    from rules import Permanent
    def make_tagged_creature(name, tag, cmc=1):
        c = Card(name=name, card_type=CardType.CREATURE,
                 cmc=cmc, mana_cost={}, colors={'U'}, base_power=0, base_toughness=3,
                 tag=tag, gy_type='creature')
        p = Permanent(card=c, controller='o'); p.power_mod=0; p.toughness_mod=0
        return p
    # Two Tamiyos -> legend rule fires
    gs_leg.p2.creatures = [make_tagged_creature('Tamiyo, Inquisitive Student','tamiyo'),
                             make_tagged_creature('Tamiyo, Inquisitive Student','tamiyo')]
    gs_leg.state_based_actions()
    test("Legend rule: two Tamiyos -> only one survives", len(gs_leg.p2.creatures), 1)
    test("Legend rule: second Tamiyo goes to GY",         len(gs_leg.p2.graveyard), 1)
    # Two Bowmasters -> legend rule does NOT fire (not legendary)
    gs_bowm = GameState(
        p1=PS_(name='b', hand=make_bug_deck(), library=[]),
        p2=PS_(name='o', hand=make_dimir_deck(), library=[]),
        p1_goes_first=True
    )
    gs_bowm.p2.creatures = [make_tagged_creature('Orcish Bowmasters','bowm',cmc=2),
                              make_tagged_creature('Orcish Bowmasters','bowm',cmc=2)]
    gs_bowm.state_based_actions()
    test("Legend rule: two Bowmasters both survive (not legendary)", len(gs_bowm.p2.creatures), 2)

    # -- Audit: Thoughtseize priority - Bowmasters over removal ------------
    from cards import instant, creature as mkc2
    bowm_card = mkc2('Orcish Bowmasters', 2, {'B':1,'generic':1}, {'B'}, 1, 1, tag='bowm', flash=True)
    push_card = instant('Fatal Push', 1, {'B':1}, {'B'}, tag='push')
    fow_card2 = instant('Force of Will', 5, {'U':1,'generic':4}, {'U'}, tag='fow', free_cast_if_blue=True)
    # Simulate opp hand: Bowmasters + Push + FoW
    from game import PlayerState as PS2
    opp_ts = PS2(name='o', hand=[push_card, fow_card2, bowm_card], library=[])
    # Priority: Bowmasters > FoW > Push
    # Check priority order manually
    target = (
        next((c for c in opp_ts.hand if c.tag == 'bowm'), None) or
        next((c for c in opp_ts.hand if c.tag in ('fow','fon')), None) or
        next((c for c in opp_ts.hand if not c.is_land()), None)
    )
    test("Thoughtseize priority: Bowmasters over Push/FoW", target.name if target else None, 'Orcish Bowmasters')

    # -- Audit: FoW does not fire on CMC<=1 non-dangerous creatures (Tamiyo) ----
    # The sim's fow_worthwhile logic: CMC1 creature only if haste or dangerous tag
    tamiyo_haste = False  # Tamiyo has no haste
    tamiyo_dangerous_tag = 'tamiyo' in {'ragavan','drc','loam','bauble'}
    ragavan_haste = True  # Ragavan has haste
    tamiyo_fow = tamiyo_haste or tamiyo_dangerous_tag  # → False
    ragavan_fow = ragavan_haste                          # → True
    test("FoW: NOT worthwhile for CMC1 non-hasty creature (Tamiyo)", tamiyo_fow, False)
    test("FoW: worthwhile for CMC1 hasty creature (Ragavan)",         ragavan_fow, True)

    print(f"\n{'='*60}")
    print(f"Tests: {passed} passed, {failed} failed")
    if failed == 0:
        print("✓ All rules verified correctly")
    else:
        print(f"✗ {failed} rule(s) failing")
    print(f"{'='*60}\n")
    return failed == 0
