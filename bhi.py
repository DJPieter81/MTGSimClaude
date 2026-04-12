"""
bhi.py — Bayesian Hand Inference module.

Maintains a probability distribution over what cards the opponent is holding,
given public information (deck composition, cards drawn, priority passes, casts
observed). Seeded from hypergeometric priors (interaction_model._prob_at_least_one).

This is pure infrastructure — no strategy currently consumes it. It is meant to
be adopted incrementally by engine.py / sim.py decision points (e.g. "should I
go for combo this turn given P(free_counter) ≈ 0.27?").

Design:
  - Track four aggregate probabilities: counter, removal, burn, free_counter.
  - Each tracked as P(at least one copy in opponent's hand).
  - Priors come from hypergeometric draws against a per-deck profile.
  - Bayesian updates fold in observed evidence:
      * priority_pass(open_mana):  they had mana and didn't counter →
        P(counter | didn't counter & had mana) is lower than prior.
      * cast(card_tag): a specific card was cast from hand → remove it from
        the belief (one fewer copy possible in hand).
      * discard(card_tag): Thoughtseize / Cabal Therapy reveal → same update.

Per-deck profiles live in _DECK_PROFILES. Decks not listed get an empty profile,
in which case all probabilities start at 0 — the belief is still usable, just
uninformative.

Keep under ~280 lines. No imports from engine.py / sim.py / game.py.
"""

from interaction_model import _prob_at_least_one

try:
    from deck_registry import get_meta, get_categories
except ImportError:  # pragma: no cover - registry is always importable in practice
    def get_meta(_):
        return None
    def get_categories(_):
        return set()


# ── Per-deck card-count profiles ────────────────────────────────────────────
# Keys are deck registry keys. Values map semantic card tags to copy counts.
# Tags:
#   fow, fon, daze, force_negation, spell_pierce, flusterstorm, pyroblast  (counters)
#   ts, inquisition, push, bolt, pyroblast, swords, stp, snuff, drown       (removal/discard)
#   bolt, spike, skewer, chain, helix, price                                (burn)
#
# Only the top ~10 meta decks carry detailed profiles. Others fall back to empty.
_DECK_PROFILES = {
    'dimir': {
        'fow': 4, 'daze': 4, 'force_negation': 0, 'flusterstorm': 0,
        'ts': 4, 'push': 4, 'drown': 2,
    },
    'dimir_b': {
        'fow': 4, 'daze': 4,
        'ts': 4, 'push': 4, 'drown': 2,
    },
    'ur_delver': {
        'fow': 4, 'daze': 4, 'spell_pierce': 2, 'pyroblast': 2,
        'push': 0, 'bolt': 4, 'spike': 4,
    },
    'bug': {
        'fow': 4, 'daze': 2, 'flusterstorm': 1,
        'ts': 4, 'push': 4,
    },
    'burn': {
        'bolt': 4, 'spike': 4, 'skewer': 4, 'chain': 4, 'helix': 4, 'price': 4,
    },
    'storm': {
        'fow': 4, 'flusterstorm': 2,
        'ts': 4,
    },
    'doomsday': {
        'fow': 4, 'daze': 2,
        'ts': 4,
    },
    'lands': {
        'fow': 0, 'daze': 0,
    },
    'oops': {
        'fow': 4, 'daze': 0,
    },
    'sneak_a': {
        'fow': 4, 'spell_pierce': 2, 'flusterstorm': 1,
    },
    'show': {
        'fow': 4, 'spell_pierce': 2,
    },
    'painter': {
        'fow': 2, 'pyroblast': 4,
    },
    'prison': {
        'fow': 0, 'daze': 0,
    },
    'uwx': {
        'fow': 4, 'daze': 0, 'force_negation': 2, 'flusterstorm': 1,
        'swords': 4, 'stp': 4,
    },
}


# Which tags count toward each aggregate probability.
_COUNTER_TAGS     = ('fow', 'fon', 'daze', 'force_negation', 'spell_pierce',
                     'flusterstorm', 'pyroblast')
_FREE_COUNTER_TAGS = ('fow', 'fon', 'daze')   # 0-mana / alt-cost counters
_REMOVAL_TAGS     = ('ts', 'inquisition', 'push', 'swords', 'stp', 'snuff',
                     'drown', 'bolt', 'pyroblast')
_BURN_TAGS        = ('bolt', 'spike', 'skewer', 'chain', 'helix', 'price')

# Mana thresholds for "could have countered" updates.
# A counter that needs >open_mana is not penalized on a priority pass.
_COUNTER_MANA_COST = {
    'fow': 0, 'fon': 0, 'daze': 0,    # alt-cost / free (Daze needs untapped Island but ok)
    'spell_pierce': 1, 'pyroblast': 1,
    'flusterstorm': 1,
    'force_negation': 3,
}


def _category_fallback_profile(deck_key):
    """For decks without an explicit profile, infer a rough one from categories."""
    cats = get_categories(deck_key) or set()
    profile = {}
    if 'aggro' in cats:
        profile.update({'bolt': 2, 'push': 2})
    if 'control' in cats:
        profile.update({'fow': 4, 'daze': 2, 'swords': 2})
    if 'tempo_mirror' in cats or 'dimir_only' in cats:
        profile.update({'fow': 4, 'daze': 4, 'push': 4, 'ts': 2})
    if 'combo' in cats or 'fast_combo' in cats:
        profile.update({'fow': 3})
    return profile


class HandBelief:
    """
    Bayesian belief over what's in an opponent's hand.

    Attributes:
        deck_key       : registered deck key (or None for unknown)
        cards_drawn    : total cards opponent has drawn (opening 7 + turns)
        cards_in_hand  : current hand size (cards still held)
        deck_size      : 60 by default
        profile        : tag → copies-in-60 dict
        p_counter      : P(≥1 counter in hand)
        p_free_counter : P(≥1 free counter in hand) — FoW / FoN / Daze
        p_removal      : P(≥1 removal in hand)
        p_burn         : P(≥1 burn spell in hand)
        remaining      : tag → estimated copies still in deck+hand (float)
    """

    def __init__(self, deck_key, cards_drawn=7, cards_in_hand=7, deck_size=60):
        self.deck_key = deck_key
        self.cards_drawn = max(0, int(cards_drawn))
        self.cards_in_hand = max(0, int(cards_in_hand))
        self.deck_size = deck_size
        self.profile = dict(_DECK_PROFILES.get(deck_key) or _category_fallback_profile(deck_key))
        # Track remaining copies (float: expected value). Decremented on cast/discard.
        self.remaining = {tag: float(n) for tag, n in self.profile.items()}
        self._recompute()

    # ── Core math ──────────────────────────────────────────────────────────

    def _p_in_hand(self, tags):
        """
        P(≥1 of any card with a tag in `tags` currently in hand).
        Combines the independent per-tag draws via inclusion-exclusion
        (approximated as 1 - ∏(1 - p_i)).
        """
        if self.cards_in_hand <= 0:
            return 0.0
        p_none = 1.0
        for tag in tags:
            copies = self.remaining.get(tag, 0.0)
            if copies <= 0:
                continue
            # P(≥1 in hand) ~ hypergeometric with cards_drawn draws,
            # then scale by (cards_in_hand / cards_drawn) to account for
            # cards that may have been played already.
            p_drawn = _prob_at_least_one(
                max(1, int(round(copies))), self.cards_drawn, self.deck_size
            )
            # If they've played down some cards, fewer remain in hand.
            retention = self.cards_in_hand / max(1, self.cards_drawn)
            p_in_hand = min(1.0, p_drawn * retention)
            p_none *= (1.0 - p_in_hand)
        return 1.0 - p_none

    def _recompute(self):
        self.p_counter      = self._p_in_hand(_COUNTER_TAGS)
        self.p_free_counter = self._p_in_hand(_FREE_COUNTER_TAGS)
        self.p_removal      = self._p_in_hand(_REMOVAL_TAGS)
        self.p_burn         = self._p_in_hand(_BURN_TAGS)

    # ── Public updates ─────────────────────────────────────────────────────

    def update_on_priority_pass(self, open_mana):
        """
        Opponent held priority with `open_mana` available and did NOT counter.

        Bayesian update:  P(C | no_counter, mana) =
            P(no_counter | C, mana) * P(C) / P(no_counter | mana)

        For counters that cost ≤ open_mana, "holding one and not using it" is
        unlikely when a real threat was cast — so we shrink those tags hard.
        For counters that cost > open_mana, no update (couldn't have anyway).
        """
        if open_mana < 0:
            return
        # Tag-level update: for each counter tag castable within open_mana,
        # multiply remaining expected copies by a suppression factor.
        # Factor derived from P(would have countered | has it) = 0.85 base.
        suppression = 0.35  # posterior retention factor when castable & held
        for tag in _COUNTER_TAGS:
            cost = _COUNTER_MANA_COST.get(tag, 2)
            if cost <= open_mana and self.remaining.get(tag, 0.0) > 0:
                self.remaining[tag] *= suppression
        self._recompute()

    def update_on_cast(self, card_tag):
        """
        A specific card (identified by tag) was cast from opponent's hand.
        Decrement one expected copy, and reduce cards_in_hand by 1.
        """
        if card_tag in self.remaining and self.remaining[card_tag] > 0:
            self.remaining[card_tag] = max(0.0, self.remaining[card_tag] - 1.0)
        self.cards_in_hand = max(0, self.cards_in_hand - 1)
        self._recompute()

    def update_on_discard(self, card_tag):
        """
        A specific card was revealed + discarded (Thoughtseize, Cabal Therapy).
        Same math as cast: one fewer copy possible in hand.
        """
        if card_tag in self.remaining and self.remaining[card_tag] > 0:
            self.remaining[card_tag] = max(0.0, self.remaining[card_tag] - 1.0)
        self.cards_in_hand = max(0, self.cards_in_hand - 1)
        self._recompute()

    def update_on_draw(self, n=1):
        """Opponent drew n more cards (normal turn draw, cantrip resolution)."""
        self.cards_drawn += n
        self.cards_in_hand += n
        self._recompute()

    # ── Introspection ──────────────────────────────────────────────────────

    def snapshot(self):
        return {
            'deck': self.deck_key,
            'hand_size': self.cards_in_hand,
            'p_counter': round(self.p_counter, 3),
            'p_free_counter': round(self.p_free_counter, 3),
            'p_removal': round(self.p_removal, 3),
            'p_burn': round(self.p_burn, 3),
        }

    def __repr__(self):
        s = self.snapshot()
        return (f"HandBelief({s['deck']}, hand={s['hand_size']}, "
                f"C={s['p_counter']}, FC={s['p_free_counter']}, "
                f"R={s['p_removal']}, B={s['p_burn']})")


# ── Test harness ────────────────────────────────────────────────────────────

if __name__ == '__main__':
    # Dimir: 4 FoW + 4 Daze → should have high P(counter) after 7 cards.
    d = HandBelief('dimir', cards_drawn=7, cards_in_hand=7)
    print('initial dimir:', d)
    assert d.p_counter > 0.6, f"expected dimir p_counter > 0.6, got {d.p_counter:.3f}"
    p_before = d.p_counter

    # They pass priority with 2 mana up — didn't Daze.
    d.update_on_priority_pass(open_mana=2)
    print('after pass(2): ', d)
    assert d.p_counter < p_before, \
        f"p_counter should drop after priority pass (was {p_before:.3f}, now {d.p_counter:.3f})"

    # Burn: lots of bolts, no counters.
    b = HandBelief('burn', cards_drawn=7, cards_in_hand=7)
    print('initial burn: ', b)
    assert b.p_burn > b.p_counter, \
        f"burn p_burn ({b.p_burn:.3f}) should exceed p_counter ({b.p_counter:.3f})"

    # Cast update: if dimir casts their known FoW, remaining['fow'] drops.
    fow_before = d.remaining.get('fow', 0)
    d.update_on_cast('fow')
    assert d.remaining['fow'] < fow_before, "fow copies should decrement on cast"

    # Discard update: Thoughtseize sees Daze, takes it.
    daze_before = d.remaining.get('daze', 0)
    d.update_on_discard('daze')
    assert d.remaining['daze'] < daze_before, "daze copies should decrement on discard"

    # Unknown deck should not crash; probabilities are 0.
    u = HandBelief('__unknown_deck__', cards_drawn=7, cards_in_hand=7)
    assert u.p_counter == 0.0 and u.p_burn == 0.0, "unknown deck should give zero priors"

    populated = sum(1 for v in _DECK_PROFILES.values() if v)
    print(f"_DECK_PROFILES populated: {populated} entries")
    print('all pass')
