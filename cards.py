"""
cards.py — Card definitions for BUG Tempo and all 9 Legacy opponent decks.
All decks are exactly 60 cards. Verified with assertions.
"""

from rules import Card, CardType, LandType
from typing import List


def creature(name, cmc, mana_cost, colors, power, toughness, tag='',
             flash=False, haste=False, flying=False, indestructible=False,
             trample=False, delve=False, free_cast_if_blue=False,
             deathtouch=False, lifelink=False, vigilance=False, reach=False,
             subtypes=None, win_condition=False, is_combo_piece=False, **kwargs):
    return Card(
        name=name, card_type=CardType.CREATURE, cmc=cmc,
        mana_cost=mana_cost, colors=set(colors),
        subtypes=set(subtypes or []),
        base_power=power, base_toughness=toughness,
        flash=flash, haste=haste, flying=flying,
        indestructible=indestructible, trample=trample, delve=delve,
        free_cast_if_blue=free_cast_if_blue,
        deathtouch=deathtouch, lifelink=lifelink,
        vigilance=vigilance, reach=reach,
        win_condition=win_condition, is_combo_piece=is_combo_piece,
        tag=tag, gy_type='creature', **kwargs
    )

def instant(name, cmc, mana_cost, colors, tag='', free_cast_if_blue=False,
            win_condition=False, is_combo_piece=False, life_cost=0, **kwargs):
    return Card(
        name=name, card_type=CardType.INSTANT, cmc=cmc,
        mana_cost=mana_cost, colors=set(colors),
        free_cast_if_blue=free_cast_if_blue,
        win_condition=win_condition, is_combo_piece=is_combo_piece,
        life_cost=life_cost,
        tag=tag, gy_type='instant', **kwargs
    )

def sorcery(name, cmc, mana_cost, colors, tag='', win_condition=False,
            is_combo_piece=False, life_cost=0, **kwargs):
    return Card(
        name=name, card_type=CardType.SORCERY, cmc=cmc,
        mana_cost=mana_cost, colors=set(colors),
        win_condition=win_condition, is_combo_piece=is_combo_piece,
        life_cost=life_cost,
        tag=tag, gy_type='sorcery', **kwargs
    )

def artifact(name, cmc, mana_cost, tag='', win_condition=False,
             is_combo_piece=False, **kwargs):
    return Card(
        name=name, card_type=CardType.ARTIFACT, cmc=cmc,
        mana_cost=mana_cost, colors=set(),
        win_condition=win_condition, is_combo_piece=is_combo_piece,
        tag=tag, gy_type='artifact', **kwargs
    )

def enchantment(name, cmc, mana_cost, colors, tag='', win_condition=False,
                is_combo_piece=False, **kwargs):
    return Card(
        name=name, card_type=CardType.ENCHANTMENT, cmc=cmc,
        mana_cost=mana_cost, colors=set(colors),
        win_condition=win_condition, is_combo_piece=is_combo_piece,
        tag=tag, gy_type='enchantment', **kwargs
    )

def planeswalker(name, cmc, mana_cost, colors, tag='', **kwargs):
    return Card(
        name=name, card_type=CardType.PLANESWALKER, cmc=cmc,
        mana_cost=mana_cost, colors=set(colors),
        tag=tag, gy_type='planeswalker', **kwargs
    )

def basic_land(name, color, subtype):
    return Card(
        name=name, card_type=CardType.LAND, cmc=0, mana_cost={},
        colors=set(), subtypes={subtype},
        land_type=LandType.BASIC, produces={color},
        is_basic=True, tag='basic', gy_type='land'
    )

def dual_land(name, colors, subtypes, tag='dual'):
    return Card(
        name=name, card_type=CardType.LAND, cmc=0, mana_cost={},
        colors=set(), subtypes=set(subtypes),
        land_type=LandType.DUAL, produces=set(colors),
        is_basic=False, tag=tag, gy_type='land'
    )

def fetch_land(name, fetch_targets):
    return Card(
        name=name, card_type=CardType.LAND, cmc=0, mana_cost={},
        colors=set(), subtypes=set(),
        land_type=LandType.FETCH,
        produces=set(),   # FETCH LANDS DO NOT TAP FOR MANA
        is_basic=False, is_fetch=True,
        fetch_targets=set(fetch_targets),
        tag='fetch', gy_type='land'
    )

def utility_land(name, produces, tag, is_basic=False, is_combo_piece=False, life_loss=0, sac_on_land=False, **kwargs):
    return Card(
        name=name, card_type=CardType.LAND, cmc=0, mana_cost={},
        colors=set(), subtypes=set(),
        land_type=LandType.UTILITY,
        produces=set(produces),
        is_basic=is_basic, is_combo_piece=is_combo_piece,
        tag=tag, gy_type='land', **kwargs
    )


# ── BUG Tempo (60) ─────────────────────────────────────────────

def make_bug_deck() -> List[Card]:
    """
    UB Tempo — Sim-optimized build based on Oceansoul92 shell.
    Original: MTGO Challenge 32, 29 Mar 2026.
    Optimized: +1 Nethergoyf, +1 Kaito, -1 Borrower, -1 Murktide (+3.5pp WR).

    Creatures (17): 4 Tamiyo, 4 Nethergoyf, 4 Bowmasters, 2 Murktide, 3 Kaito
    Interaction (12): 4 FoW, 3 TS, 4 Daze, 1 FoN, 3 Push, 1 Snuff Out
    Cantrips (8): 4 Brainstorm, 3 Ponder, 1 Mishra's Bauble
    Lands (19): 4 Polluted Delta + 3 fetches, 4 Underground Sea, Sewers, 4 Wasteland, 2 basics
    """
    d = []
    # Creatures (17)
    d += [creature('Tamiyo, Inquisitive Student', 1, {'U':1}, {'U'}, 0, 3, tag='tamiyo')] * 4
    d += [creature('Nethergoyf', 2, {'B':1,'generic':1}, {'B'}, 0, 1, tag='nether')] * 4
    d += [creature('Orcish Bowmasters', 2, {'B':1,'generic':1}, {'B'}, 1, 1, tag='bowm', draw_trigger=True, flash=True)] * 4
    d += [creature('Murktide Regent', 7, {'U':1,'generic':6}, {'U'}, 3, 3, tag='murk', delve=True, flying=True)] * 2
    d += [creature('Kaito, Bane of Nightmares', 3, {'U':1,'B':1,'generic':1}, {'U','B'}, 3, 4, tag='kaito',   engine=True)] * 3
    # Interaction (12)
    d += [instant('Force of Will', 5, {'U':1,'generic':4}, {'U'}, tag='fow', free_cast_if_blue=True)] * 4
    d += [instant('Force of Negation', 3, {'U':1,'generic':2}, {'U'}, tag='fon', free_cast_if_blue=True)] * 1
    d += [instant('Daze', 2, {'U':1,'generic':1}, {'U'}, tag='daze')] * 4
    d += [instant('Fatal Push', 1, {'B':1}, {'B'}, tag='push',    is_removal=True)] * 3
    d += [instant('Snuff Out', 4, {'B':1,'generic':3}, {'B'}, tag='snuffout', life_cost=4)] * 1
    d += [sorcery('Thoughtseize', 1, {'B':1}, {'B'}, tag='ts', life_cost=2)] * 3
    # Cantrips (8)
    d += [instant('Brainstorm', 1, {'U':1}, {'U'}, tag='bs', is_cantrip=True)] * 4
    d += [sorcery('Ponder', 1, {'U':1}, {'U'}, tag='ponder', is_cantrip=True)] * 3
    d += [artifact("Mishra's Bauble", 0, {}, tag='bauble', is_cantrip=True)] * 1
    # Lands (19)
    d += [fetch_land('Polluted Delta', ['Island','Swamp'])] * 4
    d += [fetch_land('Marsh Flats', ['Swamp','Plains'])] * 1
    d += [fetch_land('Misty Rainforest', ['Island','Forest'])] * 1
    d += [fetch_land('Scalding Tarn', ['Island','Mountain'])] * 1
    d += [fetch_land('Flooded Strand', ['Island','Plains'])] * 1
    d += [dual_land('Underground Sea', ['U','B'], ['Island','Swamp'])] * 4
    d += [dual_land_tapped('Undercity Sewers', ['U','B'], ['Island','Swamp'], tag='sewers')] * 1
    d += [utility_land('Wasteland', [], 'wl')] * 4
    d += [basic_land('Island', 'U', 'Island')] * 1
    d += [basic_land('Swamp', 'B', 'Swamp')] * 1
    assert len(d) == 60, f"BUG deck has {len(d)} cards"
    return d

def dual_land_tapped(name, colors, subtypes, tag='dual'):
    """Land that enters tapped unless controller has 2+ other lands (e.g. Undercity Sewers)."""
    c = Card(
        name=name, card_type=CardType.LAND, cmc=0, mana_cost={},
        colors=set(), subtypes=set(subtypes),
        produces=set(colors),
        is_basic=False, land_type=LandType.DUAL,
        tag=tag, gy_type='land'
    )
    c.enters_tapped_unless_two_others = True
    return c


# Barrowgoyf — {1}{B}, */1+*, deathtouch, lifelink
# P/T = card types in ALL graveyards (identical formula to Tarmogoyf)
# Additional: deals combat damage → mill that many, may put creature into hand
def make_barrowgoyf():
    return creature('Barrowgoyf', 3, {'B':1,'generic':2}, {'B'}, 0, 1,
                    tag='barrow', deathtouch=True, lifelink=True)

# Baleful Strix — {U}{B}, 1/1 flying deathtouch, ETB: draw a card
def make_baleful_strix():
    return creature('Baleful Strix', 2, {'U':1,'B':1}, {'U','B'}, 1, 1,
                    tag='strix',    engine=True, flying=True, deathtouch=True)

# Kaito, Bane of Nightmares — {1}{U}{B} planeswalker
# Ninjutsu {1}{U}{B} — enter from hand by returning unblocked attacker
# Simplified as a value engine: when it enters, draw a card / mill opp
def make_kaito():
    return planeswalker('Kaito, Bane of Nightmares', 3, {'U':1,'B':1,'generic':1},
                        {'U','B'}, tag='kaito',   engine=True)

# Snuff Out — {3}{B} or free (pay 4 life) if you control a Swamp
# Destroy target nonblack creature (instant)
def make_snuff_out():
    return instant('Snuff Out', 4, {'B':1,'generic':3}, {'B'}, tag='snuffout', life_cost=4)

# Nihil Spellbomb — {1} artifact
# Sacrifice: exile target player's graveyard
# {B}, Sacrifice: draw a card
def make_mishras_bauble():
    """CMC 0 artifact. Tap+sac: look at top of any library.
    At beginning of next upkeep: draw a card.
    Simplified in sim: immediate sac → artifact in GY (grows Nethergoyf T), 
    delayed draw fires at start of owner's next turn."""
    return artifact('Mishra\'s Bauble', 0, {}, tag='bauble', is_cantrip=True)


def make_nihil_spellbomb():
    return artifact('Nihil Spellbomb', 1, {}, tag='nihil')


# ── Dimir Tempo Variant A: ecobaronen (MTGO Challenge 32, 2nd place, 28/03/2026) ──
# Exact 75: https://mtgtop8.com/dec?d=827554
def make_dimir_deck() -> List[Card]:
    d = []
    # Creatures (15)
    d += [creature('Tamiyo, Inquisitive Student', 1, {'U':1}, {'U'}, 0, 3,
                   tag='tamiyo', flying=True)] * 4
    d += [creature('Orcish Bowmasters', 2, {'B':1,'generic':1}, {'B'}, 1, 1,
                   tag='bowm',    draw_trigger=True, flash=True)] * 4
    d += [creature('Nethergoyf', 2, {'B':1,'generic':1}, {'B'}, 0, 1, tag='nether')] * 3
    d += [creature('Murktide Regent', 7, {'U':1,'generic':6}, {'U'}, 3, 3,
                   tag='murk', delve=True, flying=True)] * 2
    d += [creature('Brazen Borrower', 3, {'U':1,'generic':2}, {'U'}, 3, 1,
                   tag='borrow', flash=True, flying=True)] * 2
    # Spells (22)
    d += [instant('Brainstorm',  1, {'U':1}, {'U'}, tag='bs', is_cantrip=True)]    * 4
    d += [sorcery('Ponder',      1, {'U':1}, {'U'}, tag='ponder', is_cantrip=True)] * 3
    d += [instant('Force of Will', 5, {'U':1,'generic':4}, {'U'},
                  tag='fow', free_cast_if_blue=True)]              * 4
    d += [instant('Daze',        2, {'U':1,'generic':1}, {'U'}, tag='daze')] * 3
    d += [instant('Fatal Push',  1, {'B':1}, {'B'}, tag='push',    is_removal=True)]  * 4
    d += [sorcery('Thoughtseize',1, {'B':1}, {'B'}, tag='ts')]    * 4
    # Other (4)
    d += [make_kaito()]          * 2
    d += [make_mishras_bauble()] * 2   # CMC 0, sac→artifact in GY, delayed draw next upkeep
    # Lands (19)
    d += [fetch_land('Polluted Delta',   ['Island','Swamp'])]    * 4
    d += [fetch_land('Bloodstained Mire',['Swamp','Mountain'])]  * 2
    d += [fetch_land('Scalding Tarn',    ['Island','Mountain'])] * 2
    d += [dual_land('Underground Sea', ['U','B'], ['Island','Swamp'])] * 4
    d += [utility_land('Wasteland', [], 'wl')]                   * 4
    d += [dual_land_tapped('Undercity Sewers', ['U','B'], ['Island','Swamp'])] * 1
    d += [basic_land('Island', 'U', 'Island')]                   * 1
    d += [basic_land('Swamp',  'B', 'Swamp')]                    * 1
    assert len(d) == 60, f"Dimir A deck: {len(d)}"
    return d

# ── Dimir Tempo Variant B: Barrowgoyf/Nishiwaki (midrange, Kyoto Top 8 Mar 2026) ──
# Deeper curve, Barrowgoyf + Baleful Strix + Snuff Out, slightly more lands
def make_dimir_b_deck() -> List[Card]:
    d = []
    # Creatures (14)
    d += [creature('Tamiyo, Inquisitive Student', 1, {'U':1}, {'U'}, 0, 3,
                        tag='tamiyo', flying=True)] * 4
    d += [creature('Orcish Bowmasters', 2, {'B':1,'generic':1}, {'B'}, 1, 1,
                   tag='bowm',    draw_trigger=True, flash=True)] * 3
    d += [make_barrowgoyf()] * 2
    d += [make_baleful_strix()] * 2
    d += [creature('Murktide Regent', 7, {'U':1,'generic':6}, {'U'}, 3, 3,
                   tag='murk', delve=True, flying=True)] * 2
    d += [creature('Brazen Borrower', 3, {'U':1,'generic':2}, {'U'}, 3, 1,
                   tag='borrow', flash=True, flying=True)] * 1

    # Spells (24)
    d += [instant('Brainstorm',  1, {'U':1}, {'U'}, tag='bs', is_cantrip=True)] * 4
    d += [sorcery('Ponder',      1, {'U':1}, {'U'}, tag='ponder', is_cantrip=True)] * 4
    d += [instant('Force of Will', 5, {'U':1,'generic':4}, {'U'}, tag='fow',
                  free_cast_if_blue=True)] * 4
    d += [instant('Daze',        2, {'U':1,'generic':1}, {'U'}, tag='daze')] * 3
    d += [instant('Fatal Push',  1, {'B':1}, {'B'}, tag='push',    is_removal=True)] * 3
    d += [sorcery('Thoughtseize',1, {'B':1}, {'B'}, tag='ts')] * 4
    # Snuff Out: free (pay 4 life) if controlling a Swamp, destroy nonblack creature
    d += [make_snuff_out()] * 2
    d += [instant('Force of Negation', 3, {'U':1,'generic':2}, {'U'}, tag='fon',
                  free_cast_if_blue=True)] * 1

    # Other (2)
    d += [make_kaito()] * 2

    # Lands (19) — matches real UB Tempo list
    d += [fetch_land('Polluted Delta', ['Island','Swamp'])] * 4
    d += [fetch_land('Flooded Strand', ['Island','Plains'])] * 1
    d += [fetch_land('Misty Rainforest', ['Island','Forest'])] * 1
    d += [fetch_land('Verdant Catacombs', ['Swamp','Forest'])] * 1
    d += [fetch_land('Bloodstained Mire', ['Swamp','Mountain'])] * 1
    d += [dual_land('Underground Sea', ['U','B'], ['Island','Swamp'])] * 3
    d += [dual_land_tapped('Undercity Sewers', ['U','B'], ['Island','Swamp'])] * 2
    d += [utility_land('Wasteland', [], 'wl')] * 4
    d += [basic_land('Island', 'U', 'Island')] * 1
    d += [basic_land('Swamp', 'B', 'Swamp')] * 1

    assert len(d) == 60, f"Dimir B deck: {len(d)}"
    return d

# ── Show and Tell (60) ─────────────────────────────────────────

def make_show_deck() -> List[Card]:
    d = []
    d += [sorcery('Show and Tell', 3, {'U':1,'generic':2}, {'U'}, tag='sat', is_combo_piece=True, win_condition=True)] * 4
    d += [instant('Brainstorm', 1, {'U':1}, {'U'}, tag='bs', is_cantrip=True)] * 4
    d += [sorcery('Ponder', 1, {'U':1}, {'U'}, tag='ponder', is_cantrip=True)] * 4
    d += [instant('Force of Will', 5, {'U':1,'generic':4}, {'U'}, tag='fow', free_cast_if_blue=True)] * 4
    d += [instant('Force of Negation', 3, {'U':1,'generic':2}, {'U'}, tag='fon', free_cast_if_blue=True)] * 2
    d += [instant('Daze', 2, {'U':1,'generic':1}, {'U'}, tag='daze')] * 3
    d += [creature('Emrakul, the Aeons Torn', 15, {'generic':15}, set(), 15, 15,
                   tag='emrakul', flying=True, trample=True, haste=True,
                   win_condition=True)] * 2  # haste simulates extra turn attack
    d += [enchantment('Omniscience', 10, {'U':1,'generic':9}, {'U'}, tag='omni', win_condition=True)] * 2
    d += [enchantment('Sneak Attack', 4, {'R':1,'generic':3}, {'R'}, tag='sneak', is_combo_piece=True, win_condition=True)] * 2
    d += [instant('Veil of Summer', 1, {'G':1}, {'G'}, tag='vos', is_removal=True)] * 3
    d += [sorcery('Preordain', 1, {'U':1}, {'U'}, tag='pre', is_cantrip=True)] * 2
    d += [sorcery('Cunning Wish', 3, {'U':1,'generic':2}, {'U'}, tag='wish')] * 1
    # 27 lands
    d += [fetch_land('Flooded Strand', ['Island','Plains'])] * 4
    d += [fetch_land('Scalding Tarn', ['Island','Mountain'])] * 4
    d += [dual_land('Volcanic Island', ['U','R'], ['Island','Mountain'])] * 3
    d += [dual_land('Tundra', ['U','W'], ['Island','Plains'])] * 2
    d += [basic_land('Island', 'U', 'Island')] * 14
    assert len(d) == 60, f"Show deck: {len(d)}"
    return d


# ── Lands (60) ─────────────────────────────────────────────────

def make_lands_deck() -> List[Card]:
    d = []
    d += [sorcery('Life from the Loam', 3, {'G':1,'generic':2}, {'G'}, tag='loam',      engine=True)] * 4
    d += [instant('Crop Rotation', 1, {'G':1}, {'G'}, tag='crop',      is_combo_piece=True)] * 4
    d += [creature('Elvish Reclaimer', 1, {'G':1}, {'G'}, 1, 2, tag='reclaimer')] * 3
    d += [instant('Punishing Fire', 2, {'R':1,'generic':1}, {'R'}, tag='pfire')] * 2
    d += [creature('Endurance', 3, {'G':1,'generic':2}, {'G'}, 3, 4, tag='endurance', flash=True, reach=True)] * 2
    # 45 lands
    d += [utility_land('Dark Depths', [], 'depths', is_combo_piece=True)] * 3
    d += [utility_land("Thespian's Stage", ['C'], 'stage', is_combo_piece=True)] * 3
    d += [utility_land('Wasteland', [], 'wl')] * 4
    d += [utility_land('Rishadan Port', ['C'], 'port')] * 4
    d += [utility_land('Maze of Ith', [], 'maze')] * 3
    d += [utility_land('The Tabernacle at Pendrell Vale', [], 'tab')] * 2
    d += [utility_land('Grove of the Burnwillows', ['G','R'], 'grove')] * 4
    d += [fetch_land('Windswept Heath', ['Forest','Plains'])] * 4
    d += [fetch_land('Verdant Catacombs', ['Swamp','Forest'])] * 4
    d += [dual_land('Bayou', ['B','G'], ['Swamp','Forest'])] * 2
    d += [dual_land('Taiga', ['R','G'], ['Mountain','Forest'])] * 2
    d += [basic_land('Forest', 'G', 'Forest')] * 10
    assert len(d) == 60, f"Lands deck: {len(d)}"
    return d


# ── Oops All Spells (60) ────────────────────────────────────────

def make_oops_deck() -> List[Card]:
    d = []
    d += [sorcery('Oops, All Spells', 2, {'U':1,'G':1}, {'U','G'}, tag='oops',
                  is_combo_piece=True, win_condition=True)] * 4
    d += [instant('Brainstorm', 1, {'U':1}, {'U'}, tag='bs', is_cantrip=True)] * 4
    d += [sorcery('Ponder', 1, {'U':1}, {'U'}, tag='ponder', is_cantrip=True)] * 4
    d += [instant('Force of Will', 5, {'U':1,'generic':4}, {'U'}, tag='fow', free_cast_if_blue=True)] * 4
    d += [instant('Veil of Summer', 1, {'G':1}, {'G'}, tag='vos', is_removal=True)] * 4
    d += [instant('Pact of Negation', 0, {}, {'U'}, tag='pact', free_cast_if_blue=True)] * 4
    d += [instant('Cabal Ritual', 2, {'B':1,'generic':1}, {'B'}, tag='ritual', mana_ritual=True)] * 4
    d += [sorcery('Unmask', 4, {'B':1,'generic':3}, {'B'}, tag='unmask')] * 2
    d += [creature('Balustrade Spy', 4, {'B':1,'generic':3}, {'B'}, 2, 3, tag='spy')] * 2
    # 28 lands
    d += [fetch_land('Polluted Delta', ['Island','Swamp'])] * 4
    d += [fetch_land('Misty Rainforest', ['Island','Forest'])] * 4
    d += [fetch_land('Verdant Catacombs', ['Swamp','Forest'])] * 2
    d += [dual_land('Underground Sea', ['U','B'], ['Island','Swamp'])] * 3
    d += [dual_land('Tropical Island', ['U','G'], ['Island','Forest'])] * 3
    d += [dual_land('Bayou', ['B','G'], ['Swamp','Forest'])] * 2
    d += [basic_land('Island', 'U', 'Island')] * 5
    d += [basic_land('Swamp', 'B', 'Swamp')] * 4
    d += [basic_land('Forest', 'G', 'Forest')] * 1
    assert len(d) == 60, f"Oops deck: {len(d)}"
    return d


# ── Artifacts Prison (60) ──────────────────────────────────────

def make_prison_deck() -> List[Card]:
    d = []
    d += [artifact('Chalice of the Void', 0, {}, tag='chalice', lock_piece=True, is_combo_piece=True)] * 4
    d += [artifact('Trinisphere', 3, {'generic':3}, tag='trini',   lock_piece=True)] * 3
    d += [artifact('Ensnaring Bridge', 3, {'generic':3}, tag='bridge',  lock_piece=True)] * 3
    d += [planeswalker('Karn, the Great Creator', 4, {'generic':4}, set(), tag='karn', engine=True, lock_piece=True)] * 4
    d += [creature('Thought-Knot Seer', 4, {'C':1,'generic':3}, set(), 4, 4, tag='tks')] * 4
    d += [artifact("Painter's Servant", 2, {'generic':2}, tag='painter', is_combo_piece=True)] * 2
    d += [artifact('Grindstone', 1, {'generic':1}, tag='grind', win_condition=True)] * 2
    d += [artifact('Null Rod', 2, {'generic':2}, tag='nullrod')] * 2
    # 36 lands
    d += [utility_land('Ancient Tomb', ['C','C'], 'tomb', mana_ritual=True)] * 4
    d += [utility_land('City of Traitors', ['C','C'], 'cot', mana_ritual=True)] * 4
    d += [utility_land('Eldrazi Temple', ['C'], 'temple')] * 4
    d += [basic_land('Wastes', 'C', 'Wastes')] * 24
    assert len(d) == 60, f"Prison deck: {len(d)}"
    return d


# ── UWx Control (60) ───────────────────────────────────────────

def make_uwx_deck() -> List[Card]:
    d = []
    d += [instant('Brainstorm', 1, {'U':1}, {'U'}, tag='bs', is_cantrip=True)] * 4
    d += [sorcery('Ponder', 1, {'U':1}, {'U'}, tag='ponder', is_cantrip=True)] * 4
    d += [instant('Force of Will', 5, {'U':1,'generic':4}, {'U'}, tag='fow', free_cast_if_blue=True)] * 4
    d += [instant('Force of Negation', 3, {'U':1,'generic':2}, {'U'}, tag='fon', free_cast_if_blue=True)] * 2
    d += [instant('Counterspell', 2, {'U':2}, {'U'}, tag='counter')] * 3
    d += [instant('Swords to Plowshares', 1, {'W':1}, {'W'}, tag='stp',     is_removal=True)] * 4
    d += [sorcery('Terminus', 6, {'W':1,'generic':5}, {'W'}, tag='terminus',is_removal=True, is_mass_removal=True)] * 3
    d += [planeswalker('Narset, Parter of Veils', 3, {'U':1,'generic':2}, {'U','W'}, tag='narset',  engine=True, lock_piece=True, draw_trigger=True)] * 2
    d += [creature('Monastery Mentor', 3, {'W':1,'generic':2}, {'W'}, 2, 2, tag='mentor')] * 3
    d += [creature('Snapcaster Mage', 2, {'U':1,'generic':1}, {'U'}, 2, 1, tag='snap', flash=True)] * 2
    d += [enchantment('Back to Basics', 3, {'U':1,'generic':2}, {'U'}, tag='b2b',     lock_piece=True)] * 2
    d += [instant('Flusterstorm', 1, {'U':1}, {'U'}, tag='fluster')] * 2
    # 26 lands
    d += [fetch_land('Flooded Strand', ['Island','Plains'])] * 4
    d += [fetch_land('Scalding Tarn', ['Island','Mountain'])] * 3
    d += [dual_land('Tundra', ['U','W'], ['Island','Plains'])] * 4
    d += [basic_land('Island', 'U', 'Island')] * 9
    d += [basic_land('Plains', 'W', 'Plains')] * 5
    assert len(d) == 60, f"UWx deck: {len(d)}"
    return d


# ── Eldrazi Aggro (manohito, MTGO Challenge 32, 12th place, 28/03/2026) ──
# Exact 60: https://mtgtop8.com/dec?d=827566
# Key oracle fixes:
#   Ancient Tomb: {T}→{CC} generic (can pay Chalice), 2 damage to controller
#   Eldrazi Temple: {T}→{C} free; {CC} Eldrazi-only (CANNOT pay Chalice)
#   Lotus Petal: sac→any mana (can pay Chalice)  
#   No SSG — real list uses Lotus Petal instead
def make_eldrazi_deck() -> List[Card]:
    d = []

    # ── Threats (16) ──
    # Thought-Knot Seer: 4/4, ETB exile nonland from opp hand
    d += [creature('Thought-Knot Seer', 4, {'generic':4}, set(), 4, 4,
                   tag='tks')] * 4
    # Glaring Fleshraker: 3/3 colorless, when you cast colorless spell → deals 1 damage
    # Simplified: 3/3 colorless threat, occasional ping on opp cast
    d += [creature('Glaring Fleshraker', 3, {'generic':3}, set(), 3, 3,
                   tag='fleshraker', trample=True)] * 4
    # Eldrazi Linebreaker: 4/3 trample menace haste (when cast with 3+ colorless mana)
    # Simplified: 4/3 with haste and trample
    d += [creature('Eldrazi Linebreaker', 3, {'generic':3}, set(), 4, 3,
                   tag='linebreaker', trample=True)] * 4
    # Wastescape Battlemage: 3/3, landfall → tap target opp land
    d += [creature('Wastescape Battlemage', 3, {'generic':3}, set(), 3, 3,
                   tag='battlemage')] * 4

    # ── Lock / Value (8) ──
    d += [artifact('Chalice of the Void', 0, {}, tag='chalice', lock_piece=True, is_combo_piece=True)] * 4
    # The One Ring: CMC 4, protection from everything ETB, then draw cards
    d += [artifact('The One Ring', 4, {'generic':4}, tag='ring')] * 4

    # ── Mana accel / spells (12) ──
    # Lotus Petal: CMC 0, sac for any mana
    d += [artifact('Lotus Petal', 0, {}, tag='petal',     mana_ritual=True)] * 4
    # Kozilek's Command: modal colorless instant, ~CMC 2-4
    d += [instant("Kozilek's Command", 3, {'generic':3}, set(), tag='kcommand')] * 4
    # Simian Spirit Guide: exile→{R}, CANNOT pay Chalice (generic), but kept as body
    d += [creature('Simian Spirit Guide', 2, {'R':1,'generic':2}, {'R'}, 2, 2,
                   tag='ssg')] * 4

    # ── Lands (24) ──
    # Ancient Tomb: {T}→{CC} generic, pay 2 life — PRIMARY Chalice enabler
    d += [utility_land('Ancient Tomb',    ['C','C'], 'tomb',  life_loss=2)] * 4
    # Eldrazi Temple: {T}→{C} free; restricted {CC} for Eldrazi only
    d += [utility_land('Eldrazi Temple',  ['C'],     'temple')] * 4
    # Cavern of Souls: adds {C} or colored mana; creature spells uncounterable
    d += [utility_land('Cavern of Souls', ['C'],     'cavern')] * 4
    # City of Traitors: {T}→{CC}, sacrifices itself when next land played
    d += [utility_land('City of Traitors',['C','C'], 'city',  sac_on_land=True)] * 3
    # Eye of Ugin: {T}→nothing, but reduces Eldrazi costs by 2
    d += [utility_land('Eye of Ugin',     ['C'],     'eye')] * 1
    # Abundant Countryside: enters tapped, fetches any basic type
    d += [fetch_land('Abundant Countryside', ['Forest','Plains','Island','Swamp','Mountain'])] * 4
    # Wasteland: destroy target nonbasic
    d += [utility_land('Wasteland', [], 'wl')] * 4

    assert len(d) == 60, f"Eldrazi deck: {len(d)}"
    return d

# ── Painter Combo (60) ─────────────────────────────────────────

def make_painter_deck() -> List[Card]:
    d = []
    d += [artifact("Painter's Servant", 2, {'generic':2}, tag='painter', is_combo_piece=True)] * 4
    d += [artifact('Grindstone', 1, {'generic':1}, tag='grind', is_combo_piece=True, win_condition=True)] * 4
    d += [instant('Pyroblast', 1, {'R':1}, {'R'}, tag='pyro')] * 4
    d += [instant('Red Elemental Blast', 1, {'R':1}, {'R'}, tag='reb')] * 4
    d += [creature('Imperial Recruiter', 3, {'R':1,'generic':2}, {'R'}, 1, 1, tag='recruiter',tutor_power_max=2)] * 4
    d += [enchantment('Blood Moon', 3, {'R':1,'generic':2}, {'R'}, tag='moon',    lock_piece=True)] * 3
    d += [planeswalker('Karn, the Great Creator', 4, {'generic':4}, set(), tag='karn', engine=True, lock_piece=True)] * 2
    d += [artifact('Ensnaring Bridge', 3, {'generic':3}, tag='bridge',  lock_piece=True)] * 2
    d += [creature('Walking Ballista', 0, {}, set(), 0, 0, tag='ballista')] * 2
    # 31 lands
    d += [utility_land('Ancient Tomb', ['C','C'], 'tomb', mana_ritual=True)] * 4
    d += [utility_land('City of Traitors', ['C','C'], 'cot', mana_ritual=True)] * 4
    d += [fetch_land('Arid Mesa', ['Mountain','Plains'])] * 4
    d += [dual_land('Volcanic Island', ['U','R'], ['Island','Mountain'])] * 2
    d += [basic_land('Mountain', 'R', 'Mountain')] * 17
    assert len(d) == 60, f"Painter deck: {len(d)}"
    return d


# ── Doomsday (60) ──────────────────────────────────────────────

def make_doomsday_deck() -> List[Card]:
    d = []
    d += [sorcery('Doomsday', 5, {'B':2,'generic':3}, {'B'}, tag='dd',
                  is_combo_piece=True, win_condition=True)] * 4
    d += [instant('Brainstorm', 1, {'U':1}, {'U'}, tag='bs', is_cantrip=True)] * 4
    d += [sorcery('Ponder', 1, {'U':1}, {'U'}, tag='ponder', is_cantrip=True)] * 4
    d += [instant('Force of Will', 5, {'U':1,'generic':4}, {'U'}, tag='fow', free_cast_if_blue=True)] * 4
    d += [creature("Thassa's Oracle", 2, {'U':2}, {'U'}, 1, 3, tag='oracle', win_condition=True)] * 4
    d += [instant('Dark Ritual', 1, {'B':1}, {'B'}, tag='darkrit',  mana_ritual=True)] * 3
    d += [instant('Veil of Summer', 1, {'G':1}, {'G'}, tag='vos', is_removal=True)] * 3
    d += [instant('Flusterstorm', 1, {'U':1}, {'U'}, tag='fluster')] * 3
    d += [creature('Street Wraith', 5, {'B':2,'generic':3}, {'B'}, 3, 4, tag='wraith', is_cantrip=True)] * 3
    d += [instant('Edge of Autumn', 2, {'G':1,'generic':1}, {'G'}, tag='edge', is_cantrip=True)] * 2
    # 26 lands
    d += [utility_land('Cavern of Souls', ['C'], 'cavern')] * 4
    d += [fetch_land('Polluted Delta', ['Island','Swamp'])] * 4
    d += [fetch_land('Misty Rainforest', ['Island','Forest'])] * 2
    d += [dual_land('Underground Sea', ['U','B'], ['Island','Swamp'])] * 3
    d += [dual_land('Tropical Island', ['U','G'], ['Island','Forest'])] * 1
    d += [basic_land('Island', 'U', 'Island')] * 6
    d += [basic_land('Swamp', 'B', 'Swamp')] * 4
    d += [basic_land('Forest', 'G', 'Forest')] * 2
    assert len(d) == 60, f"Doomsday deck: {len(d)}"
    return d


# ──────────────────────────────────────────────
# Death and Taxes (60-card, March 2026 standard list)
# Core: Aether Vial + Thalia + Stoneforge + Rishadan Port + Wasteland
# No FoW, no blue — BUG advantage: cantrips work freely, counters hit everything
# ──────────────────────────────────────────────
def make_dnt_deck() -> List[Card]:
    d = []
    # Creatures (22) — tuned to real March 2026 list (cardsrealm/mtgtop8)
    d += [creature('Thalia, Guardian of Thraben', 2, {'W':1,'generic':1}, {'W'}, 2, 1, tag='thalia')] * 3
    d += [creature('Stoneforge Mystic', 2, {'W':1,'generic':1}, {'W'}, 1, 2, tag='sfm',     engine=True)] * 4
    d += [creature('Recruiter of the Guard', 3, {'W':1,'generic':2}, {'W'}, 1, 1, tag='recruiter',tutor_power_max=2)] * 4
    d += [creature('Skyclave Apparition', 3, {'W':2,'generic':1}, {'W'}, 2, 2, tag='skyclave', is_removal=True)] * 3
    d += [creature('Solitude', 5, {'W':2,'generic':3}, {'W'}, 3, 2, tag='solitude', is_removal=True, flash=True, flying=True, lifelink=True)] * 2
    d += [creature('Phelia, Exuberant Shepherd', 2, {'W':1,'generic':1}, {'W'}, 2, 2, tag='phelia')] * 3
    d += [creature('Flickerwisp', 3, {'W':1,'generic':2}, {'W'}, 3, 1, tag='flickerwisp', flying=True)] * 2
    d += [creature('White Orchid Phantom', 3, {'W':2,'generic':1}, {'W'}, 2, 2, tag='orchid')] * 1
    # Spells (8)
    d += [instant('Swords to Plowshares', 1, {'W':1}, {'W'}, tag='stp',     is_removal=True)] * 4
    d += [artifact('Aether Vial', 1, {'generic':1}, tag='vial',    engine=True)] * 4
    # Equipment (3)
    d += [artifact('Kaldra Compleat', 7, {'generic':7}, tag='kaldra')] * 1
    d += [artifact('Pre-War Formalwear', 4, {'generic':4}, tag='equipment')] * 1
    d += [artifact('Batterskull', 5, {'generic':5}, tag='equipment')] * 1
    # Lands (27 — DnT runs lots of utility lands)
    d += [utility_land('Rishadan Port', [], 'port')] * 4
    d += [utility_land('Wasteland',     [], 'wl')]   * 4
    d += [utility_land('Karakas',       ['W'], 'karakas')] * 3
    d += [fetch_land('Flooded Strand', ['Plains'])]  * 2
    d += [fetch_land('Arid Mesa',      ['Plains'])]  * 2
    d += [basic_land('Plains', 'W', 'Plains')]        * 12
    assert len(d) == 60, f"DnT: {len(d)}"
    return d

# ──────────────────────────────────────────────
# Mono Black Aggro (Legacy 2025-2026 Dauthi variant)
# Core: fast black creatures, disruption, Grief evoke + Orcish Bowmasters
# ──────────────────────────────────────────────
def make_mono_black_deck() -> List[Card]:
    d = []
    # Creatures (20)
    d += [creature('Grief', 5, {'B':2,'generic':3}, {'B'}, 3, 2, tag='grief', flash=True)] * 4  # evoke exile black
    d += [creature('Orcish Bowmasters', 2, {'B':1,'generic':1}, {'B'}, 1, 1, tag='bowm',    draw_trigger=True)] * 4
    d += [creature('Dauthi Voidwalker', 2, {'B':2}, {'B'}, 3, 2, tag='dauthi')] * 4
    d += [creature('Carnage Interpreter', 2, {'B':1,'generic':1}, {'B'}, 2, 2, tag='carnage')] * 4
    d += [creature('Braids, Arisen Nightmare', 4, {'B':2,'generic':2}, {'B'}, 3, 3, tag='braids')] * 4
    # Spells (16)
    d += [sorcery('Thoughtseize', 1, {'B':1}, {'B'}, tag='ts', life_cost=2)] * 4
    d += [instant('Fatal Push', 1, {'B':1}, {'B'}, tag='push',    is_removal=True)] * 4
    d += [instant('Snuff Out', 4, {'B':1,'generic':3}, {'B'}, tag='snuffout', life_cost=4)] * 4  # free if Swamp
    d += [sorcery('Hymn to Tourach', 2, {'B':2}, {'B'}, tag='hymn')] * 4
    # Lands (24)
    d += [utility_land('Wasteland', [], 'wl')] * 4
    d += [fetch_land('Polluted Delta',   ['Swamp'])] * 4
    d += [fetch_land('Marsh Flats',      ['Swamp'])] * 4
    d += [basic_land('Swamp', 'B', 'Swamp')]          * 12
    assert len(d) == 60, f"Mono Black: {len(d)}"
    return d

# ──────────────────────────────────────────────
# Boros Initiative / Boros Aggro (legacy 2025-2026)
# Core: Initiative creatures + white weenie aggro + Orcish Bowmasters
# BUG weakness: Thalia taxes, multiple bodies racing Goyf/Bowmasters
# ──────────────────────────────────────────────
def make_boros_deck() -> List[Card]:
    d = []
    # Creatures (22): core aggro + Eidolon×3 Bowmasters×4 Recruiter×4 full density
    d += [creature('Thalia, Guardian of Thraben', 2, {'W':1,'generic':1}, {'W'}, 2, 1, tag='thalia')] * 2
    d += [creature('Orcish Bowmasters', 2, {'B':1,'generic':1}, {'B'}, 1, 1, tag='bowm', draw_trigger=True, flash=True)] * 4
    d += [creature('Seasoned Dungeoneer', 3, {'W':1,'generic':2}, {'W'}, 3, 3, tag='dungeoneer')] * 3
    d += [creature('Minsc and Boo, Timeless Heroes', 4, {'R':1,'W':1,'generic':2}, {'R','W'}, 4, 4, tag='minsc')] * 2
    d += [creature('White Orchid Phantom', 3, {'W':2,'generic':1}, {'W'}, 2, 2, tag='orchid')] * 3
    d += [creature('Recruiter of the Guard', 3, {'W':1,'generic':2}, {'W'}, 1, 1, tag='recruiter',tutor_power_max=2)] * 4
    d += [creature('Eidolon of the Great Revel', 2, {'R':2}, {'R'}, 2, 2,
                   tag='eidolon',  etb_damage=2)] * 4
    # Spells (14): Vial×4 STP×4 Bolt×4 Pyro×2
    d += [instant('Swords to Plowshares', 1, {'W':1}, {'W'}, tag='stp',     is_removal=True)] * 4
    d += [artifact('Aether Vial', 1, {'generic':1}, tag='vial',    engine=True)] * 4
    d += [instant('Lightning Bolt', 1, {'R':1}, {'R'}, tag='bolt',    is_removal=True)] * 4
    d += [instant('Pyroblast', 1, {'R':1}, {'R'}, tag='pyro')] * 2
    # Lands (24)
    d += [fetch_land('Arid Mesa',      ['Plains','Mountain'])] * 4
    d += [fetch_land('Flooded Strand', ['Plains'])]             * 2
    d += [dual_land('Plateau', ['W','R'], ['Plains','Mountain'])] * 2
    d += [utility_land('Wasteland', [], 'wl')]  * 4
    d += [utility_land('Rishadan Port', [], 'port')] * 2
    d += [basic_land('Plains',   'W', 'Plains')]  * 6
    d += [basic_land('Mountain', 'R', 'Mountain')] * 4
    assert len(d) == 60, f"Boros: {len(d)}"
    return d


def _bug_base(daze=3, ponder=3, kaito=2, bowm=4, bauble=2, snuff=1, extra_snuff=0, extra_ponder=0):
    """Shared builder for BUG variant decks. All counts relative to baseline."""
    d = []
    d += [creature('Tamiyo, Inquisitive Student', 1, {'U':1}, {'U'}, 0, 3,
                   tag='tamiyo', flying=True)] * 4
    d += [creature('Orcish Bowmasters', 2, {'B':1,'generic':1}, {'B'}, 1, 1,
                   tag='bowm', flash=True, draw_trigger=True)] * bowm
    d += [creature('Nethergoyf', 2, {'B':1,'generic':1}, {'B'}, 0, 1, tag='nether')] * 3
    d += [creature('Murktide Regent', 7, {'U':1,'generic':6}, {'U'}, 3, 3,
                   tag='murk', delve=True, flying=True)] * 3
    d += [creature('Brazen Borrower', 3, {'U':1,'generic':2}, {'U'}, 3, 1,
                   tag='borrow', flash=True, flying=True)] * 1
    d += [make_kaito()] * kaito
    d += [instant('Force of Will', 5, {'U':1,'generic':4}, {'U'}, tag='fow',
                  free_cast_if_blue=True)] * 4
    d += [instant('Daze', 2, {'U':1,'generic':1}, {'U'}, tag='daze')] * daze
    d += [instant('Fatal Push', 1, {'B':1}, {'B'}, tag='push', is_removal=True)] * 3
    d += [sorcery('Thoughtseize', 1, {'B':1}, {'B'}, tag='ts', life_cost=2)] * 4
    d += [instant('Brainstorm', 1, {'U':1}, {'U'}, tag='bs', is_cantrip=True)] * 4
    d += [sorcery('Ponder', 1, {'U':1}, {'U'}, tag='ponder', is_cantrip=True)] * (ponder + extra_ponder)
    d += [artifact("Mishra's Bauble", 0, {}, tag='bauble', is_cantrip=True)] * bauble
    d += [make_snuff_out()] * (snuff + extra_snuff)
    d += [fetch_land('Polluted Delta', ['Island','Swamp'])] * 4
    d += [fetch_land('Misty Rainforest', ['Island','Forest'])] * 1
    d += [fetch_land('Marsh Flats', ['Plains','Swamp'])] * 1
    d += [fetch_land('Scalding Tarn', ['Island','Mountain'])] * 1
    d += [fetch_land('Verdant Catacombs', ['Swamp','Forest'])] * 1
    d += [dual_land('Underground Sea', ['U','B'], ['Island','Swamp'])] * 4
    d += [dual_land_tapped('Undercity Sewers', ['U','B'], ['Island','Swamp'])] * 1
    d += [utility_land('Wasteland', [], 'wl')] * 4
    d += [basic_land('Island', 'U', 'Island')] * 1
    d += [basic_land('Swamp', 'B', 'Swamp')] * 1
    return d


def make_bug_daze4_deck() -> List[Card]:
    """H1: 4 Daze, 2 Ponder (disruption-heavy)."""
    d = _bug_base(daze=4, ponder=2)
    assert len(d) == 60, f"Daze4: {len(d)}"
    return d


def make_bug_kaito1_deck() -> List[Card]:
    """H3a: 1 Kaito, +1 Ponder."""
    d = _bug_base(kaito=1, extra_ponder=1)
    assert len(d) == 60, f"Kaito1: {len(d)}"
    return d


def make_bug_kaito0_deck() -> List[Card]:
    """H3b: 0 Kaito, +1 Ponder +1 Snuff Out."""
    d = _bug_base(kaito=0, extra_ponder=1, extra_snuff=1)
    assert len(d) == 60, f"Kaito0: {len(d)}"
    return d


def make_bug_bowm3_deck() -> List[Card]:
    """H4: 3 Bowmasters, +1 Ponder."""
    d = _bug_base(bowm=3, extra_ponder=1)
    assert len(d) == 60, f"Bowm3: {len(d)}"
    return d



# ─────────────────────────────────────────────
# BUG Sideboard (15)
# ─────────────────────────────────────────────

def make_bug_sideboard() -> List[Card]:
    """
    Oceansoul92 sideboard — MTGO Challenge 32, 29 Mar 2026.
    3 Barrowgoyf, 3 FoN, 2 Hydroblast, 2 Massacre, 2 Nihil Spellbomb, 1 Null Rod,
    1 Snuff Out, 1 Toxic Deluge.
    Hydroblast instead of Pyroblast (hits blue threats in mirror + UR Aggro).
    Massacre instead of Deluge (free sweeper — doesn't cost life vs aggressive decks).
    Barrowgoyf post-board in grindy matchups (deathtouch + lifelink blocker).
    """
    sb = []
    sb += [creature('Barrowgoyf', 3, {'B':1,'generic':2}, {'B'}, 0, 1,
                    tag='barrow', deathtouch=True, lifelink=True)] * 3
    sb += [instant('Force of Negation', 3, {'U':1,'generic':2}, {'U'}, tag='fon',
                   free_cast_if_blue=True)] * 3
    sb += [instant('Hydroblast', 1, {'U':1}, {'U'}, tag='pyro')] * 2  # modelled same as Pyroblast
    sb += [sorcery('Massacre', 3, {'B':1,'generic':2}, {'B'}, tag='deluge',  is_removal=True, is_mass_removal=True)] * 2  # modelled same as Deluge
    sb += [artifact('Nihil Spellbomb', 1, {}, tag='nihil')] * 1
    # Null Rod removed (low meta relevance vs current SB plan)
    sb += [instant('Snuff Out', 4, {'B':1,'generic':3}, {'B'}, tag='snuffout', life_cost=4)] * 1
    sb += [sorcery('Toxic Deluge', 3, {'B':1,'generic':2}, {'B'}, tag='deluge',  is_removal=True, is_mass_removal=True)] * 1
    sb += [instant('Flusterstorm', 1, {'U':1}, {'U'}, tag='fluster')] * 1
    sb += [instant('Mindbreak Trap', 4, {'U':1,'generic':3}, {'U'}, tag='mindbreak',
                   is_combo_piece=False, win_condition=False)] * 1
    assert len(sb) == 15, f"SB has {len(sb)} cards"
    return sb


def make_bug_realsb_sideboard() -> List[Card]:
    """Oceansoul92 exact sideboard from the real MTGO Challenge list.
    vs sim SB: +1 Null Rod, +1 Toxic Deluge, +1 Nihil; -1 Flusterstorm, -1 Mindbreak Trap, -1 Massacre.
    """
    sb = []
    sb += [creature('Barrowgoyf', 3, {'B':1,'generic':2}, {'B'}, 0, 1,
                    tag='barrow', deathtouch=True, lifelink=True)] * 3
    sb += [instant('Force of Negation', 3, {'U':1,'generic':2}, {'U'}, tag='fon',
                   free_cast_if_blue=True)] * 3
    sb += [instant('Hydroblast', 1, {'U':1}, {'U'}, tag='pyro')] * 2
    sb += [sorcery('Massacre', 3, {'B':1,'generic':2}, {'B'}, tag='deluge',
                   is_removal=True, is_mass_removal=True)] * 2
    sb += [artifact('Nihil Spellbomb', 1, {}, tag='nihil')] * 2
    sb += [artifact('Null Rod', 2, {'generic':2}, tag='nullrod')] * 1
    sb += [instant('Snuff Out', 4, {'B':1,'generic':3}, {'B'}, tag='snuffout', life_cost=4)] * 1
    sb += [sorcery('Toxic Deluge', 3, {'B':1,'generic':2}, {'B'}, tag='deluge',
                   is_removal=True, is_mass_removal=True)] * 1
    assert len(sb) == 15, f"Real SB has {len(sb)} cards"
    return sb

def make_postboard_bug_deck(matchup: str) -> List[Card]:
    """
    Returns BUG's 60-card post-sideboard deck for the given matchup.
    Applies the correct swap plan: remove cards from main, add from sideboard.
    """
    main = make_bug_deck()
    sb   = make_bug_sideboard()

    # Swap plans: (tags_to_remove as list of (tag, count)), (tags_to_add as list of (tag, count))
    # ── Sideboard swap plans — Oceansoul92 list, March 2026 ──
    # Main has: push x3, daze x3, ts x4, fow x4, snuff x1  (no fon, no fluster)
    # SB has: barrow x3, fon x3, hydroblast x2, massacre x2, nihil x2, nullrod x1, snuff x1, deluge x1
    swaps = {
        # Show: Push/Daze blank; bring in FoN (noncreature counters free on opp turn) + Snuff (Emrakul/Griselbrand)
        'show':       (
            [('push',3),('daze',2)],
            [('fon',2),('snuffout',1),('deluge',1),('nihil',1)]
        ),
        # Storm: Push/Daze blank; FoN x2 + Fluster x1 + Mindbreak Trap x1
        # Flusterstorm and Mindbreak Trap beat Veil of Summer (neither blue nor black)
        'storm':      (
            [('bs',3),('bs',1)],
            [('fon',2),('fluster',1),('mindbreak',1)]
        ),
        # Oops: Push dead; FoN + Nihil; keep TS for hand disruption
        'oops':       (
            [('bs',3),('bs',1)],
            [('fon',3),('nihil',1)]
        ),
        # Doomsday: Push dead; FoN counters Oracle; Nihil disrupts pile
        'doomsday':   (
            [('push',3),('daze',1)],
            [('fon',3),('nihil',1)]
        ),
        # Reanimator: FoN + Nihil GY hate; keep TS; Daze risky (they have 4+ mana)
        'reanimator': (
            [('bs',2),('daze',1),('snuffout',1)],
            [('fon',2),('barrow',1),('nihil',1)]
        ),
        # Dimir B: Barrowgoyf blocks deathtouch well; Massacre sweeps; Hydroblast hits their Murktide
        'dimir_b':    (
            [('daze',1),('ts',1)],
            [('barrow',1),('deluge',1)]
        ),
        # Dimir A: Hydroblast hits Murktide/Tamiyo; Barrowgoyf for grindy games
        'dimir':      (
            [('bs',2),('daze',1)],
            [('pyro',2),('barrow',1)]
        ),
        # UR Aggro: Hydroblast hits Murktide/DRC; Massacre sweeps tokens; FoN for their combo draws
        'ur_aggro':   (
            [('daze',1),('ts',2)],
            [('pyro',2),('deluge',1)]
        ),
        # Eldrazi: TS mostly blank; Massacre for token swarms; Snuff for big Eldrazi
        'eldrazi':    (
            [('ts',3)],
            [('fon',1),('deluge',1),('snuffout',1)]
        ),
        # Mardu: Massacre sweeps creature floods; Barrowgoyf blocks everything; TS less useful
        'mardu':      (
            [('daze',1),('snuffout',1),('ts',1)],
            [('deluge',1),('barrow',1),('nihil',1)]
        ),
        # Prison: FoN counters lock pieces; Null Rod shuts artifact mana; keep Snuff for Welder
        'prison':     (
            [('bs',2),('daze',1)],
            [('fon',2),('barrow',1)]
        ),
        # UWx: FoN free on their turn for Terminus/STP; Hydroblast hits their threats
        'uwx':        (
            [('ts',2),('daze',1)],
            [('fon',2),('pyro',1)]
        ),
        # Painter: FoN counters Blood Moon / Grindstone; Null Rod shuts Painter engine
        'painter':    (
            [('bs',2),('daze',1)],
            [('fon',2),('pyro',1)]
        ),
        # Lands: FoN counters Crop Rotation/Loam; Nihil disrupts their GY loop
        'lands':      (
            [('daze',1),('ts',1)],
            [('fon',1),('nihil',1)]
        ),
    }
    if matchup not in swaps:
        return main  # no changes for unknown matchups

    remove_plan, add_plan = swaps[matchup]

    # Remove cards from main deck
    deck = list(main)
    for tag, count in remove_plan:
        removed = 0
        remaining = []
        for card in deck:
            if card.tag == tag and removed < count:
                removed += 1
            else:
                remaining.append(card)
        deck = remaining

    # Add cards from sideboard
    sb_pool = list(sb)
    for tag, count in add_plan:
        added = 0
        remaining_sb = []
        for card in sb_pool:
            if card.tag == tag and added < count:
                deck.append(card)
                added += 1
            else:
                remaining_sb.append(card)
        sb_pool = remaining_sb

    assert len(deck) == 60, f"Post-board BUG vs {matchup}: {len(deck)} cards"
    return deck


# ─────────────────────────────────────────────
# Opponent sideboard swap plans
# Simplified: opp brings in best hate vs BUG tempo
# ─────────────────────────────────────────────

def make_postboard_opp_deck(matchup: str) -> List[Card]:
    """
    Opponent's post-sideboard adjustments vs BUG Tempo.
    Each archetype brings in their most relevant hate.
    """
    opp_fn = DECKS[matchup]
    main = opp_fn()

    opp_swaps = {
        # Dimir brings in Pyroblasts vs BUG's blue threats, Veil vs TS
        'dimir':     ([('bs',2),('bs',1),('fluster',1)],
                      [('pyro',2),('vos',2)]),
        # Show brings in more Veil to protect combo
        'show':      ([('daze',2)],
                      [('vos',2)]),
        # Storm brings in Veil x4 (usually already has 4, so no-op here)
        'storm':     ([], []),
        # Reanimator brings in Unmask to strip interaction
        'reanimator':([('reanimate',1)],
                      [('unmask',1)]),
        # Lands brings in more Wasteland effects
        'lands':     ([], []),
        # Others — minimal change post-board for simplicity
        'oops':      ([], []),
        'doomsday':  ([], []),
        'eldrazi':   ([('ww',2)],
                      [('chalice',2)] if sum(1 for c in main if c.tag == 'chalice') < 4 else []),
        'mardu':     ([], []),
        'prison':    ([], []),
        'uwx':       ([('counter',1)],
                      [('fluster',1)]),
        'painter':   ([], []),
        'ur_aggro':  ([], []),
    }

    if matchup not in opp_swaps:
        return main

    remove_plan, add_plan = opp_swaps[matchup]

    deck = list(main)
    for tag, count in remove_plan:
        removed = 0
        remaining = []
        for card in deck:
            if card.tag == tag and removed < count:
                removed += 1
            else:
                remaining.append(card)
        deck = remaining

    # For opponent, generate new cards of the needed types
    new_cards = {
        'pyro':    lambda: instant('Pyroblast', 1, {'R':1}, {'R'}, tag='pyro'),
        'vos':     lambda: instant('Veil of Summer', 1, {'G':1}, {'G'}, tag='vos', is_removal=True),
        'unmask':  lambda: sorcery('Unmask', 4, {'B':1,'generic':3}, {'B'}, tag='unmask'),
        'fluster':   lambda: instant('Flusterstorm', 1, {'U':1}, {'U'}, tag='fluster'),
        'mindbreak': lambda: instant('Mindbreak Trap', 4, {'U':1,'generic':3}, {'U'}, tag='mindbreak',
                                     free_cast_if_blue=False, is_combo_piece=False),
        'chalice': lambda: artifact('Chalice of the Void', 0, {}, tag='chalice', lock_piece=True, is_combo_piece=True),
    }

    for tag, count in add_plan:
        if tag in new_cards and len(deck) + count <= 60:
            for _ in range(count):
                deck.append(new_cards[tag]())

    # Trim or pad to 60 if needed
    while len(deck) > 60:
        deck.pop()

    return deck

# ── Legacy Elves (60) ────────────────────────────────────────────────────────
# Allosaurus Shepherd build: Glimpse of Nature engine, Natural Order → Craterhoof
# Key interaction: Shepherd makes all green spells uncounterable while in play.
# Heritage Druid: tap 3 untapped elves → GGG. Nettle Sentinel untaps on green spell cast.

def make_elves_deck() -> List[Card]:
    d = []
    # ── Mana elves ──
    d += [creature('Llanowar Elves',    1, {'G':1}, {'G'}, 1, 1, tag='llanowar')] * 4
    d += [creature('Elvish Mystic',     1, {'G':1}, {'G'}, 1, 1, tag='mystic')]   * 4
    d += [creature('Heritage Druid',    1, {'G':1}, {'G'}, 1, 1, tag='heritage',  engine=True)] * 3
    d += [creature('Elvish Spirit Guide',1,{'G':1}, {'G'}, 3, 2, tag='espirit',   flash=False)] * 1
    # ── Engine ──
    d += [creature('Nettle Sentinel',   1, {'G':1}, {'G'}, 2, 2, tag='nettle')] * 4
    d += [creature('Allosaurus Shepherd',1,{'G':1}, {'G'}, 1, 1, tag='shepherd', engine=True)] * 4
    d += [creature('Elvish Visionary',  1, {'G':1}, {'G'}, 1, 1, tag='visionary')] * 4
    d += [creature('Wirewood Symbiote', 1, {'G':1}, {'G'}, 1, 1, tag='symbiote',  engine=True)] * 2
    d += [creature('Quirion Ranger',    1, {'G':1}, {'G'}, 1, 1, tag='qranger')] * 2
    d += [creature('Reclamation Sage',  2, {'G':1,'generic':1}, {'G'}, 2, 1, tag='recsage', is_removal=True)] * 1
    # ── Finisher ──
    d += [creature('Craterhoof Behemoth', 8, {'G':1,'generic':7}, {'G'}, 5, 5,
                   tag='hoof', win_condition=True, engine=True)] * 1
    # ── Spells ──
    d += [sorcery('Glimpse of Nature',  1, {'G':1}, {'G'}, tag='glimpse',    is_combo_piece=True)] * 4
    d += [sorcery("Green Sun's Zenith", 1, {'G':1}, {'G'}, tag='gsz',       is_combo_piece=True)] * 4
    d += [sorcery('Natural Order',       2, {'G':2}, {'G'}, tag='natorder',   is_combo_piece=True)] * 3
    # ── Lands ──
    d += [utility_land("Gaea's Cradle", ['G'], 'cradle')] * 4
    d += [fetch_land('Verdant Catacombs', ['Forest','Swamp'])] * 4
    d += [fetch_land('Windswept Heath',   ['Forest','Plains'])] * 2
    d += [dual_land('Bayou',   ['G','B'], ['Forest','Swamp'])] * 2
    d += [dual_land('Savannah',['G','W'], ['Forest','Plains'])] * 1
    d += [basic_land('Forest', 'G', 'Forest')] * 3
    # Dryad Arbor: creature + land (model as creature with land tag)
    d += [creature('Dryad Arbor',       0, {}, {'G'}, 1, 1, tag='dryad_arbor')] * 1

    d += [fetch_land('Misty Rainforest', ['Forest','Island'])] * 1
    d += [basic_land('Forest', 'G', 'Forest')] * 1
    assert len(d) == 60, f"Elves: {len(d)}"
    return d





# ─────────────────────────────────────────────────────────────────────────────
# Protagonist-aware opponent sideboard
# Opponents adjust their SB based on WHO they're facing, not just their own deck
# ─────────────────────────────────────────────────────────────────────────────




def make_postboard_opp_vs_protagonist(protagonist: str, antagonist: str) -> List[Card]:
    """
    Build the antagonist's post-board deck, calibrated to fight the PROTAGONIST.
    Uses OPP_SB_VS_PROTAGONIST for protagonist-specific swap plans.
    Falls back to BUG-calibrated SB if no plan defined.
    """
    from cards import DECKS, make_postboard_opp_deck

    proto_swaps = OPP_SB_VS_PROTAGONIST.get(protagonist, {})
    ant_swaps   = proto_swaps.get(antagonist, None)
    if ant_swaps is None:
        return make_postboard_opp_deck(antagonist)

    main = DECKS[antagonist]()
    remove_plan, add_plan = ant_swaps

    # Card factory for SB additions
    def _sb(tag):
        _factory = {
            'fluster':   lambda: instant('Flusterstorm', 1, {'U':1}, {'U'}, tag='fluster'),
            'mindbreak': lambda: instant('Mindbreak Trap', 4, {'U':2,'generic':2}, {'U'}, tag='mindbreak'),
            'leyline':   lambda: enchantment('Leyline of Sanctity', 4, {'W':2,'generic':2}, {'W'}, tag='leyline'),
            'fon':       lambda: instant('Force of Negation', 3, {'U':1,'generic':2}, {'U'}, tag='fon', free_cast_if_blue=True),
            'nihil':     lambda: artifact('Nihil Spellbomb', 1, {}, tag='nihil'),
            'surgical':  lambda: instant('Surgical Extraction', 0, {'B':1}, {'B'}, tag='surgical'),
            'push':      lambda: instant('Fatal Push', 1, {'B':1}, {'B'}, tag='push', is_removal=True),
            'pyro':      lambda: instant('Pyroblast', 1, {'R':1}, {'R'}, tag='pyro'),
            'vos':       lambda: instant('Veil of Summer', 1, {'G':1}, {'G'}, tag='vos'),
            'dnt_hate':  lambda: instant('Swords to Plowshares', 1, {'W':1}, {'W'}, tag='stp', is_removal=True),
        }
        return _factory.get(tag, lambda: None)()

    # Remove cards (correct stateful loop — no walrus tricks)
    deck = list(main)
    for tag, count in remove_plan:
        removed, new_deck = 0, []
        for c in deck:
            if c.tag == tag and removed < count:
                removed += 1
            else:
                new_deck.append(c)
        deck = new_deck

    # Add SB cards — collect them first, then trim original to make room
    sb_adds = []
    for tag, count in add_plan:
        for _ in range(count):
            card = _sb(tag)
            if card: sb_adds.append(card)
    # Trim original deck to make room for SB adds
    NEVER_TRIM = {'nihil','surgical','mindbreak','fluster','fon',
                  'leyline','vos','pyro','stp','fow'}
    target = 60 - len(sb_adds)
    while len(deck) > target:
        # Prefer to remove cantrips, then least important spells
        removed = False
        for priority_tags in [('bs','ponder','bauble','daze','counter','narset'),
                              ('snap','reanimate','exhume','animatedead')]:
            for i, c in enumerate(deck):
                if c.tag in priority_tags and c.tag not in NEVER_TRIM:
                    deck.pop(i); removed = True; break
            if removed: break
        if not removed:
            for i, c in enumerate(deck):
                if c.tag not in NEVER_TRIM and not c.is_land():
                    deck.pop(i); break
            else:
                deck.pop()
    deck.extend(sb_adds)

    return deck



# ─────────────────────────────────────────────────────────────────────────────
# Protagonist-aware opponent sideboard
# Opponents adjust their SB based on WHO they're facing, not just their own deck
# ─────────────────────────────────────────────────────────────────────────────

OPP_SB_VS_PROTAGONIST = {
    # Opponents' post-sideboard decks calibrated to the PROTAGONIST, not always BUG.
    # Format: protagonist_key -> { antagonist_key: (remove_plan, add_plan) }
    'storm': {
        'bug':        ([('push',3),('daze',1)],                 [('fluster',2),('mindbreak',2)]),
        'dimir':      ([('push',3),('daze',1)],                 [('fluster',2),('mindbreak',2)]),
        'dimir_b':    ([('push',3),('daze',1)],                 [('fluster',2),('mindbreak',2)]),
        'uwx':        ([('bs',1),('stp',1),('ponder',1)], [('fluster',2),('mindbreak',1)]),
        'mardu':      ([('stp',1),('ts',1)],                    [('mindbreak',2),('fluster',1)]),
        'dnt':        ([('bs',2)],                             [('fluster',2)]),
        'boros':      ([('bs',1)],                             [('mindbreak',1),('fluster',1)]),
        'eldrazi':    ([],                                       [('mindbreak',1)]),
        'mono_black': ([('push',1)],                            [('mindbreak',1),('fluster',1)]),
        'ur_aggro':   ([('bolt',1)],                            [('fluster',1)]),
        'eight_cast': ([],                                      [('mindbreak',1)]),
        'reanimator': ([],                                      [('fluster',1)]),
        'elves':      ([('gsz',1),('glimpse',1)],              [('mindbreak',1)]),
        'painter':    ([],                                      [('fluster',1)]),
        'lands':      ([],                                      [('mindbreak',1)]),
    },

    'show': {
        'bug':        ([('bs',2),('daze',1)],                 [('fon',2),('surgical',1)]),
        'dimir':      ([('push',3),('daze',1)],                 [('fon',2),('surgical',1),('nihil',1)]),
        'dimir_b':    ([('push',3),('daze',1)],                 [('fon',2),('surgical',1),('nihil',1)]),
        'uwx':        ([('stp',1),('snap',1)],               [('fon',2),('surgical',1)]),
        'mardu':      ([('stp',1),('ts',1)],                   [('fon',1),('surgical',1)]),
        'dnt':        ([('bs',1),('ts',0)],                    [('fluster',2)]),
        'boros':      ([('bs',1),('stp',1)],           [('fon',1),('surgical',1)]),
        'storm':      ([],                                      [('fluster',1)]),
    },

    'oops': {
        'bug':        ([('bs',2),('ts',1)],                   [('nihil',2),('fon',1)]),
        'dimir':      ([('push',3),('daze',1)],                 [('nihil',2),('surgical',2)]),
        'dimir_b':    ([('push',3),('daze',1)],                 [('nihil',2),('surgical',2)]),
        'uwx':        ([('stp',1),('snap',1)],                  [('nihil',2),('fon',1)]),
        'mardu':      ([('stp',1),('ts',1)],                    [('nihil',2)]),
        'dnt':        ([('bs',2)],                             [('nihil',2)]),
        'boros':      ([('stp',1)],                             [('nihil',1)]),
        'mono_black': ([('bs',1)],                            [('nihil',2)]),
        'storm':      ([],                                      [('nihil',1)]),
        'reanimator': ([],                                      [('nihil',1)]),
        'eight_cast': ([('bauble',1)],                         [('nihil',1)]),
        'painter':    ([],                                      [('nihil',1)]),
        'eldrazi':    ([],                                      [('nihil',1)]),
        'elves':      ([('gsz',1),('glimpse',1)],              [('nihil',2)]),
        'lands':      ([],                                      [('nihil',1)]),
    },

    'doomsday': {
        'bug':        ([('bs',2),('ts',1)],                   [('fon',2),('nihil',1)]),
        'dimir':      ([('push',3)],                            [('fon',2),('nihil',1)]),
        'dimir_b':    ([('push',3)],                            [('fon',2),('nihil',1)]),
        'uwx':        ([('stp',1),('snap',1),('ponder',1)],    [('fon',2),('nihil',1)]),
        'mardu':      ([('stp',1),('ts',1)],                    [('mindbreak',1),('fluster',1)]),
        'dnt':        ([('stp',2)],                             [('fluster',2)]),
        'boros':      ([('stp',1)],                             [('mindbreak',1)]),
        'mono_black': ([('bs',1)],                            [('nihil',1)]),
        'storm':      ([],                                      [('fluster',1)]),
        'eight_cast': ([],                                      [('fluster',1)]),
        'reanimator': ([],                                      [('nihil',1)]),
        'painter':    ([],                                      [('fluster',1)]),
        'eldrazi':    ([],                                      [('nihil',1)]),
    },

    'reanimator': {
        'bug':        ([('bs',2),('ts',1)],                   [('nihil',2),('surgical',1)]),
        'dimir':      ([('bs',2),('daze',1)],                 [('nihil',2),('surgical',1)]),
        'dimir_b':    ([('bs',2),('daze',1)],                 [('nihil',2),('surgical',1)]),
        'uwx':        ([('stp',1),('stp',1)],                [('nihil',2),('fon',1)]),
        'storm':      ([],                                      [('nihil',1)]),
        'mardu':      ([('stp',1),('ts',1)],                    [('nihil',2)]),
        'dnt':        ([('stp',2)],                             [('nihil',2)]),
        'boros':      ([('stp',1)],                             [('nihil',1)]),
        'mono_black': ([('push',1)],                            [('nihil',2)]),
        'painter':    ([],                                      [('nihil',1)]),
        'eldrazi':    ([],                                      [('nihil',1)]),
    },

    'elves': {
        # vs Elves: Push + mass removal; combo boards GY hate
        'bug':        ([('ts',1),('daze',1)],                   [('bs',2)]),
        'dimir':      ([('ts',1),('daze',1)],                   [('stp',2)]),
        'uwx':        ([('narset',1),('snap',1)],               [('stp',2)]),
        'storm':      ([('bs',2),('ponder',1)],                            [('mindbreak',1),('fluster',1)]),
        'oops':       ([('stp',2)],                            [('nihil',2)]),
        'doomsday':   ([('stp',2)],                            [('nihil',1),('fon',1)]),
        'reanimator': ([('stp',2)],                            [('nihil',2)]),
        'show':       ([('stp',2)],                            [('fon',2)]),
        'mono_black': ([('push',1)],                            [('push',1)]),
        'mardu':      ([('ts',1)],                              [('stp',2)]),
        'boros':      ([('ts',1)],                              [('push',2)]),
        'dnt':        ([('ts',1)],                              [('push',2)]),
        'eldrazi':    ([('ts',1)],                              [('push',2)]),
        'prison':     ([('ts',1)],                              [('push',1),('fon',1)]),
        'lands':      ([('ts',1)],                              [('push',1)]),
    },

    'ur_aggro': {
        'dimir':      ([('ts',2)],                              [('pyro',2)]),
        'dimir_b':    ([('ts',2)],                              [('pyro',2)]),
        'uwx':        ([('narset',1),('snap',1)],               [('pyro',2)]),
        'mardu':      ([('ts',1)],                              [('pyro',1)]),
    },

    # ── vs BUG Tempo ─────────────────────────────────────────────────────────
    # How each ANTAGONIST adapts when facing BUG as protagonist.
    'bug': {
        # Fair decks: board Pyroblast (hits Brainstorm, Daze, Bowmasters triggers)
        'uwx':        ([('bs',2),('ponder',1)],                [('pyro',2),('fluster',1)]),
        'mardu':      ([('push',2)],                           [('pyro',2)]),
        'dnt':        ([('push',1)],                           [('pyro',1)]),
        'boros':      ([('stp',1)],                            [('pyro',1)]),
        # Combo decks: board Veil of Summer to protect their combo from BUG's TS/Daze/FoW
        'storm':      ([('ponder',2),('bs',1)],                [('vos',3)]),
        'show':       ([('ponder',2),('daze',1)],              [('vos',3)]),
        'oops':       ([('petal',2),('bs',1)],                 [('vos',3)]),
        'doomsday':   ([('ponder',2),('bs',1)],                [('vos',3)]),
        'reanimator': ([('reanimate',1),('animatedead',1)],    [('vos',1),('unmask',1)]),
        # Aggro decks: add removal for BUG threats
        'eldrazi':    ([('ww',1)],                             [('stp',1)]),
        'mono_black': ([('ts',1)],                             [('push',1)]),
    },
    # ── vs Dimir Tempo ───────────────────────────────────────────────────────
    'dimir': {
        'uwx':        ([('bs',2),('bs',1)],              [('vos',2)]),
        'mardu':      ([('push',2)],                           [('pyro',1),('vos',1)]),
        'storm':      ([('bs',1),('ponder',1),('bs',1)],                [('fluster',2),('mindbreak',1)]),
        'show':       ([('push',2),('daze',1)],                [('fon',2),('surgical',1)]),
        'oops':       ([('push',3),('daze',1)],                [('nihil',2),('fon',1)]),
        'doomsday':   ([('push',3)],                           [('fon',2),('nihil',1)]),
        'reanimator': ([('push',2),('daze',1)],                [('nihil',2),('surgical',1)]),
        'eldrazi':    ([('ts',1)],                             [('push',2)]),
        'boros':      ([('ts',1)],                             [('push',2)]),
        'elves':      ([('ts',1),('daze',1)],                  [('push',2)]),
    },
    # ── vs UWx Control ───────────────────────────────────────────────────────
    'uwx': {
        'dimir':      ([('narset',1),('push',1)],              [('pyro',1)]),
        'mardu':      ([('narset',1)],                         [('stp',2)]),
        'storm':      ([('bs',2),('ponder',1)],              [('fluster',2),('mindbreak',1)]),
        'show':       ([('bs',2),('bs',1)],              [('fon',2),('surgical',1)]),
        'oops':       ([('push',2),('narset',1)],              [('nihil',2),('fon',1)]),
        'doomsday':   ([('push',2),('snap',1)],                [('fon',2),('nihil',1)]),
        'reanimator': ([('push',2),('narset',1)],              [('nihil',2),('surgical',1)]),
        'elves':      ([('narset',1)],                         [('push',2)]),
        'eldrazi':    ([('narset',1)],                         [('stp',2)]),
        'boros':      ([('narset',1)],                         [('stp',2)]),
    },
    # ── vs Mono Black ────────────────────────────────────────────────────────
    'mono_black': {
        'storm':      ([('bs',2),('ponder',1)],                           [('nihil',1),('fluster',1)]),
        'oops':       ([('push',2)],                           [('nihil',2)]),
        'doomsday':   ([('push',2)],                           [('nihil',1),('fluster',1)]),
        'reanimator': ([('push',1)],                           [('nihil',2)]),
        'show':       ([('push',2)],                           [('nihil',1)]),
        'eldrazi':    ([],                                     [('nihil',1)]),
        'boros':      ([('push',1)],                           [('push',1)]),
    },
    # ── vs 8-Cast ────────────────────────────────────────────────────────────
    'eight_cast': {
        'storm':      ([],                                     [('mindbreak',1)]),
        'oops':       ([],                                     [('nihil',1)]),
        'doomsday':   ([],                                     [('fon',2)]),
        'reanimator': ([],                                     [('nihil',1)]),
        'dimir':      ([('push',2)],                           [('fon',2)]),
        'uwx':        ([('push',2),('narset',1)],              [('fon',2)]),
        'bug':        ([('push',2),('ts',1)],                  [('fon',2)]),
        'mardu':      ([('push',2)],                           [('mindbreak',1)]),
        'show':       ([('push',2)],                           [('fon',2)]),
        'eldrazi':    ([],                                     [('fon',1)]),
    },
    # ── vs Mardu ─────────────────────────────────────────────────────────────
    'mardu': {
        'storm':      ([('stp',1),('ts',1)],                   [('mindbreak',2)]),
        'oops':       ([('stp',1)],                            [('nihil',2)]),
        'doomsday':   ([('stp',1)],                            [('nihil',1),('mindbreak',1)]),
        'reanimator': ([('stp',1)],                            [('nihil',2)]),
        'show':       ([('stp',1)],                            [('fon',1)]),
        'elves':      ([('stp',1)],                            [('bolt',1)]),
        'lands':      ([('stp',1)],                            [('bolt',1)]),
    },
    # ── vs Death & Taxes ─────────────────────────────────────────────────────
    'dnt': {
        'storm':      ([('stp',1)],                            [('fluster',2)]),
        'oops':       ([('stp',1)],                            [('nihil',2)]),
        'doomsday':   ([('stp',1)],                            [('nihil',1),('fluster',1)]),
        'reanimator': ([('stp',1)],                            [('nihil',2)]),
        'show':       ([('stp',1)],                            [('fon',1)]),
        'elves':      ([('stp',1)],                            [('stp',1)]),
        'mardu':      ([],                                     [('stp',1)]),
        'boros':      ([],                                     [('stp',1)]),
    },
    # ── vs Boros Initiative ──────────────────────────────────────────────────
    'boros': {
        'storm':      ([('stp',1)],                            [('mindbreak',1)]),
        'oops':       ([('stp',1)],                            [('nihil',1)]),
        'reanimator': ([('stp',1)],                            [('nihil',1)]),
        'doomsday':   ([('stp',1)],                            [('nihil',1)]),
        'eldrazi':    ([],                                     [('stp',1)]),
        'elves':      ([('stp',1)],                            [('stp',1)]),
        'dimir':      ([('stp',1)],                            [('stp',1)]),
    },
    # ── vs Eldrazi Aggro ─────────────────────────────────────────────────────
    'eldrazi': {
        'storm':      ([],                                     [('mindbreak',1)]),
        'oops':       ([],                                     [('nihil',1)]),
        'reanimator': ([],                                     [('nihil',1)]),
        'doomsday':   ([],                                     [('nihil',1)]),
        'elves':      ([('ww',1)],                             [('chalice',1)]),
        'mardu':      ([],                                     [('stp',1)]),
        'boros':      ([('ww',1)],                             [('chalice',1)]),
        'dnt':        ([],                                     [('stp',1)]),
    },
    # ── vs Painter ───────────────────────────────────────────────────────────
    'painter': {
        'storm':      ([],                                     [('mindbreak',1)]),
        'oops':       ([],                                     [('nihil',1)]),
        'reanimator': ([],                                     [('nihil',1)]),
        'doomsday':   ([],                                     [('nihil',1)]),
        'dimir':      ([],                                     [('fon',1)]),
        'uwx':        ([],                                     [('fon',1)]),
        'bug':        ([],                                     [('fon',1)]),
        'lands':      ([],                                     [('stp',1)]),
    },
    # ── vs Artifacts Prison ──────────────────────────────────────────────────
    'prison': {
        'storm':      ([],                                     [('mindbreak',1)]),
        'oops':       ([],                                     [('nihil',1)]),
        'reanimator': ([],                                     [('nihil',1)]),
        'doomsday':   ([],                                     [('nihil',1)]),
        'dimir':      ([],                                     [('fon',1)]),
        'bug':        ([],                                     [('fon',1)]),
        'elves':      ([],                                     [('stp',1)]),
    },
    # ── vs Lands ─────────────────────────────────────────────────────────────
    'lands': {
        'storm':      ([],                                     [('mindbreak',1)]),
        'oops':       ([],                                     [('nihil',1)]),
        'reanimator': ([],                                     [('nihil',1)]),
        'doomsday':   ([],                                     [('nihil',1)]),
        'dimir':      ([('stp',1)],                             [('fon',1)]),
        'bug':        ([('stp',1)],                             [('fon',1)]),
        'mardu':      ([('wl',1)],                             [('stp',1)]),
        'eldrazi':    ([('wl',1)],                             [('stp',1)]),
    },
}


def make_postboard_opp_vs_protagonist(protagonist: str, antagonist: str) -> List[Card]:
    """
    Build the antagonist's post-board deck, calibrated to fight the PROTAGONIST.
    Uses OPP_SB_VS_PROTAGONIST for protagonist-specific swap plans.
    Falls back to BUG-calibrated SB if no plan defined.
    """
    from cards import DECKS, make_postboard_opp_deck

    proto_swaps = OPP_SB_VS_PROTAGONIST.get(protagonist, {})
    ant_swaps   = proto_swaps.get(antagonist, None)
    if ant_swaps is None:
        return make_postboard_opp_deck(antagonist)

    main = DECKS[antagonist]()
    remove_plan, add_plan = ant_swaps

    # Card factory for SB additions
    def _sb(tag):
        _factory = {
            'fluster':   lambda: instant('Flusterstorm', 1, {'U':1}, {'U'}, tag='fluster'),
            'mindbreak': lambda: instant('Mindbreak Trap', 4, {'U':2,'generic':2}, {'U'}, tag='mindbreak'),
            'leyline':   lambda: enchantment('Leyline of Sanctity', 4, {'W':2,'generic':2}, {'W'}, tag='leyline'),
            'fon':       lambda: instant('Force of Negation', 3, {'U':1,'generic':2}, {'U'}, tag='fon', free_cast_if_blue=True),
            'nihil':     lambda: artifact('Nihil Spellbomb', 1, {}, tag='nihil'),
            'surgical':  lambda: instant('Surgical Extraction', 0, {'B':1}, {'B'}, tag='surgical'),
            'push':      lambda: instant('Fatal Push', 1, {'B':1}, {'B'}, tag='push', is_removal=True),
            'bolt':      lambda: instant('Lightning Bolt', 1, {'R':1}, {'R'}, tag='bolt', is_removal=True),
            'stp':       lambda: instant('Swords to Plowshares', 1, {'W':1}, {'W'}, tag='stp', is_removal=True),
            'pyro':      lambda: instant('Pyroblast', 1, {'R':1}, {'R'}, tag='pyro'),
            'vos':       lambda: instant('Veil of Summer', 1, {'G':1}, {'G'}, tag='vos'),
            'dnt_hate':  lambda: instant('Swords to Plowshares', 1, {'W':1}, {'W'}, tag='stp', is_removal=True),
        }
        return _factory.get(tag, lambda: None)()

    # Remove cards (correct stateful loop — no walrus tricks)
    deck = list(main)
    for tag, count in remove_plan:
        removed, new_deck = 0, []
        for c in deck:
            if c.tag == tag and removed < count:
                removed += 1
            else:
                new_deck.append(c)
        deck = new_deck

    # Add SB cards — collect them first, then trim original to make room
    sb_adds = []
    for tag, count in add_plan:
        for _ in range(count):
            card = _sb(tag)
            if card: sb_adds.append(card)
    # Trim original deck to make room for SB adds
    NEVER_TRIM = {'nihil','surgical','mindbreak','fluster','fon',
                  'leyline','vos','pyro','stp','fow'}
    target = 60 - len(sb_adds)
    while len(deck) > target:
        # Prefer to remove cantrips, then least important spells
        removed = False
        for priority_tags in [('bs','ponder','bauble','daze','counter','narset'),
                              ('snap','reanimate','exhume','animatedead')]:
            for i, c in enumerate(deck):
                if c.tag in priority_tags and c.tag not in NEVER_TRIM:
                    deck.pop(i); removed = True; break
            if removed: break
        if not removed:
            for i, c in enumerate(deck):
                if c.tag not in NEVER_TRIM and not c.is_land():
                    deck.pop(i); break
            else:
                deck.pop()
    deck.extend(sb_adds)

    return deck


MATCHUP_META = {
    'dimir':      {'name': 'Dimir Tempo A (Nethergoyf)', 'share': 0.09},
    'dimir_b':    {'name': 'Dimir Tempo B (Barrowgoyf)',  'share': 0.06},
    'dimir_flash':{'name': 'Dimir Flash (Wan Shi Tong)',  'share': 0.03},
    'show':       {'name': 'Show and Tell',               'share': 0.07},
    'lands':      {'name': 'Lands',                       'share': 0.05},
    'storm':      {'name': 'Storm',                       'share': 0.03},
    'oops':       {'name': 'Oops All Spells',             'share': 0.06},
    'prison':     {'name': 'Artifacts Prison',            'share': 0.05},
    'uwx':        {'name': 'UWx Control',                 'share': 0.04},
    'eldrazi':    {'name': 'Eldrazi Aggro',               'share': 0.03},
    'painter':    {'name': 'Painter',                     'share': 0.04},
    'doomsday':   {'name': 'Doomsday',                    'share': 0.03},
    'reanimator': {'name': 'Reanimator',                  'share': 0.02},
    'dnt':        {'name': 'Death and Taxes',             'share': 0.03},
    'mono_black': {
        # vs Mono Black: tempo boards disruption; aggro boards removal
        'bug':        ([('push',1)],                            [('surgical',1)]),
        'dimir':      ([('push',1)],                            [('surgical',1)]),
        'uwx':        ([('push',1)],                            [('nihil',1)]),
        'storm':      ([('bs',2),('ponder',1)],                            [('mindbreak',1),('fluster',1)]),
        'oops':       ([('push',2)],                            [('nihil',2)]),
        'doomsday':   ([('push',2)],                            [('nihil',1),('fon',1)]),
        'reanimator': ([('push',2)],                            [('nihil',2)]),
        'show':       ([('push',2)],                            [('nihil',1),('surgical',1)]),
        'elves':      ([('push',1)],                            [('push',1)]),
        'eldrazi':    ([('push',1)],                            [('push',1)]),
        'mardu':      ([],                                      [('push',1)]),
        'boros':      ([],                                      [('push',1)]),
        'dnt':        ([('push',1)],                            [('push',1)]),
        'prison':     ([('push',1)],                            [('nihil',1)]),
        'lands':      ([],                                      [('nihil',1)]),
    },

    'uwx': {
        # vs UWx: aggro boards aggression; combo boards Fluster/REB effects
        'bug':        ([('narset',1),('push',1)],               [('pyro',2)]),
        'dimir':      ([('narset',1),('push',1)],               [('pyro',2)]),
        'storm':      ([('bs',2),('ponder',1),('bs',1)],               [('fluster',2),('mindbreak',1)]),
        'oops':       ([('push',2),('narset',1)],               [('nihil',2),('fon',1)]),
        'doomsday':   ([('push',2),('narset',1)],               [('fon',2),('nihil',1)]),
        'reanimator': ([('push',2),('narset',1)],               [('nihil',2),('surgical',1)]),
        'show':       ([('push',2),('narset',1)],               [('fon',2),('surgical',1)]),
        'mardu':      ([('narset',1)],                          [('push',2)]),
        'boros':      ([('narset',1)],                          [('push',2)]),
        'dnt':        ([('narset',1)],                          [('push',2)]),
        'eldrazi':    ([('narset',1)],                          [('push',2)]),
        'elves':      ([('narset',1),('push',1)],               [('push',1)]),
        'lands':      ([('narset',1)],                          [('fon',1)]),
        'prison':     ([('narset',1),('push',1)],               [('fon',2)]),
    },

    'dnt': {
        # vs DnT: artifact hate is key (Aether Vial); removal for creatures
        'bug':        ([('push',1)],                            [('push',1)]),
        'dimir':      ([('push',1)],                            [('push',1)]),
        'uwx':        ([('push',1)],                            [('push',1)]),
        'storm':      ([('bs',2),('ponder',1)],                            [('fluster',2)]),
        'oops':       ([('push',2)],                            [('nihil',2)]),
        'doomsday':   ([('push',2)],                            [('nihil',1),('fon',1)]),
        'reanimator': ([('push',2)],                            [('nihil',2)]),
        'show':       ([('push',2)],                            [('fon',2)]),
        'mono_black': ([('push',1)],                            [('push',1)]),
        'elves':      ([('push',1)],                            [('push',1)]),
        'mardu':      ([],                                      [('push',1)]),
        'boros':      ([],                                      [('push',1)]),
        'eldrazi':    ([('push',1)],                            [('push',1)]),
        'prison':     ([('push',1)],                            [('fon',1)]),
        'lands':      ([],                                      [('push',1)]),
    },

    'painter': {
        # vs Painter: Pithing Needle naming Grindstone; blue decks board Pyro
        'bug':        ([('push',1)],                            [('pyro',1),('nihil',1)]),
        'dimir':      ([('push',1)],                            [('pyro',1),('nihil',1)]),
        'uwx':        ([('push',1),('narset',1)],               [('pyro',2)]),
        'storm':      ([],                                      [('fluster',1)]),
        'oops':       ([('push',1)],                            [('nihil',1)]),
        'doomsday':   ([('push',1)],                            [('nihil',1)]),
        'reanimator': ([('push',1)],                            [('nihil',1)]),
        'show':       ([('push',1)],                            [('surgical',1)]),
        'mono_black': ([('push',1)],                            [('nihil',1)]),
        'elves':      ([('push',1)],                            [('push',1)]),
        'eldrazi':    ([('push',1)],                            [('push',1)]),
        'mardu':      ([],                                      [('push',1)]),
        'boros':      ([],                                      [('push',1)]),
        'dnt':        ([('push',1)],                            [('push',1)]),
        'prison':     ([('push',1)],                            [('nihil',1)]),
        'lands':      ([],                                      [('nihil',1)]),
    },

    'eldrazi': {
        # vs Eldrazi: removal (Push, Swords); bounce; counters for Tron pieces
        'bug':        ([('push',1)],                            [('push',1)]),
        'dimir':      ([('push',1)],                            [('push',1)]),
        'uwx':        ([('narset',1)],                          [('push',2)]),
        'storm':      ([('bs',1)],                            [('mindbreak',1)]),
        'oops':       ([('push',2)],                            [('nihil',1)]),
        'doomsday':   ([('push',2)],                            [('nihil',1)]),
        'reanimator': ([('push',2)],                            [('nihil',1)]),
        'show':       ([('push',2)],                            [('fon',1)]),
        'mono_black': ([('push',1)],                            [('push',1)]),
        'mardu':      ([],                                      [('push',1)]),
        'boros':      ([],                                      [('push',1)]),
        'dnt':        ([('push',1)],                            [('push',1)]),
        'elves':      ([('push',1)],                            [('push',1)]),
        'prison':     ([('push',1)],                            [('fon',1)]),
        'lands':      ([('push',1)],                            [('push',1)]),
    },

    'mardu': {
        # vs Mardu: removal + disruption; combo boards stack interaction
        'bug':        ([('ts',1)],                              [('push',2)]),
        'dimir':      ([('ts',1)],                              [('push',2)]),
        'uwx':        ([('ts',1)],                              [('push',1),('stp',1)]),
        'storm':      ([('bs',2),('ponder',1)],                            [('mindbreak',2),('fluster',1)]),
        'oops':       ([('push',2)],                            [('nihil',2)]),
        'doomsday':   ([('push',2)],                            [('nihil',1),('mindbreak',1)]),
        'reanimator': ([('push',2)],                            [('nihil',2)]),
        'show':       ([('push',2)],                            [('nihil',1),('surgical',1)]),
        'mono_black': ([('ts',1)],                              [('push',1)]),
        'dnt':        ([('ts',1)],                              [('push',1)]),
        'boros':      ([],                                      [('push',1)]),
        'eldrazi':    ([('ts',1)],                              [('push',1)]),
        'elves':      ([('ts',1)],                              [('push',2)]),
        'prison':     ([('ts',1)],                              [('fon',1)]),
        'lands':      ([('ts',1)],                              [('push',1)]),
    },

    'boros': {
        # vs Boros: same structure as Mardu — removal + some combo interaction
        'bug':        ([('stp',1)],                             [('push',1)]),
        'dimir':      ([('stp',1)],                             [('push',1)]),
        'uwx':        ([('stp',1)],                             [('push',1)]),
        'storm':      ([('stp',2)],                             [('mindbreak',2)]),
        'oops':       ([('stp',2)],                             [('nihil',2)]),
        'doomsday':   ([('stp',2)],                             [('nihil',1),('mindbreak',1)]),
        'reanimator': ([('stp',2)],                             [('nihil',2)]),
        'show':       ([('stp',2)],                             [('nihil',1),('surgical',1)]),
        'mono_black': ([('stp',1)],                             [('push',1)]),
        'dnt':        ([('stp',1)],                             [('push',1)]),
        'mardu':      ([],                                      [('push',1)]),
        'eldrazi':    ([('stp',1)],                             [('push',1)]),
        'elves':      ([('stp',1)],                             [('push',2)]),
        'prison':     ([('stp',1)],                             [('fon',1)]),
        'lands':      ([('stp',1)],                             [('push',1)]),
    },

    'prison': {
        # vs Prison: artifact hate is the correct call, but we model as FoN (no Force of Vigor)
        # Blue decks board FoN; fair decks board minimal hate
        'bug':        ([('ts',1),('daze',1)],                   [('fon',2)]),
        'dimir':      ([('ts',1),('daze',1)],                   [('fon',2)]),
        'uwx':        ([('narset',1),('push',1)],               [('fon',2)]),
        'storm':      ([('bs',2),('ponder',1)],                            [('mindbreak',1),('fluster',1)]),
        'oops':       ([('push',2)],                            [('nihil',1),('fon',1)]),
        'doomsday':   ([('push',2)],                            [('fon',2)]),
        'reanimator': ([('push',2)],                            [('nihil',1),('fon',1)]),
        'show':       ([('push',2)],                            [('fon',2)]),
        'mono_black': ([('push',1)],                            [('nihil',1)]),
        'dnt':        ([('push',1)],                            [('fon',1)]),
        'mardu':      ([('ts',1)],                              [('fon',1)]),
        'boros':      ([('stp',1)],                             [('fon',1)]),
        'eldrazi':    ([('push',1)],                            [('fon',1)]),
        'elves':      ([('push',1)],                            [('fon',1)]),
        'lands':      ([],                                      [('fon',1)]),
    },

    'lands': {
        # vs Lands: Pithing Needle (naming Rishadan Port/Wasteland), GY hate vs Loam
        # Blue decks board Surgical; fair decks board minimal
        'bug':        ([('ts',1),('daze',1)],                   [('surgical',1),('push',1)]),
        'dimir':      ([('ts',1),('daze',1)],                   [('surgical',1),('push',1)]),
        'uwx':        ([('narset',1),('push',1)],               [('surgical',1),('fon',1)]),
        'storm':      ([('bs',1)],                            [('mindbreak',1)]),
        'oops':       ([('push',2)],                            [('nihil',1)]),
        'doomsday':   ([('push',2)],                            [('nihil',1)]),
        'reanimator': ([('push',2)],                            [('nihil',1)]),
        'show':       ([('push',2)],                            [('fon',1)]),
        'mono_black': ([('push',1)],                            [('nihil',1)]),
        'dnt':        ([('push',1)],                            [('surgical',1)]),
        'mardu':      ([('ts',1)],                              [('push',1)]),
        'boros':      ([('stp',1)],                             [('push',1)]),
        'eldrazi':    ([('push',1)],                            [('push',1)]),
        'elves':      ([('push',1)],                            [('push',1)]),
        'prison':     ([('push',1)],                            [('fon',1)]),
    },

    'eight_cast': {
        # vs 8-Cast: artifact hate is key (Null Rod/Force of Vigor) — we model as FoN
        'bug':        ([('ts',1),('daze',1)],                   [('fon',2),('nihil',1)]),
        'dimir':      ([('ts',1),('daze',1)],                   [('fon',2),('nihil',1)]),
        'uwx':        ([('narset',1),('push',1)],               [('fon',2)]),
        'storm':      ([('bs',2),('ponder',1)],                            [('mindbreak',1),('fluster',1)]),
        'oops':       ([('push',2)],                            [('nihil',2)]),
        'doomsday':   ([('push',2)],                            [('nihil',1),('fon',1)]),
        'reanimator': ([('push',2)],                            [('nihil',2)]),
        'show':       ([('push',2)],                            [('fon',2)]),
        'mono_black': ([('push',1)],                            [('nihil',1)]),
        'dnt':        ([('push',1)],                            [('fon',1)]),
        'mardu':      ([('ts',1)],                              [('push',1)]),
        'boros':      ([('stp',1)],                             [('push',1)]),
        'eldrazi':    ([('push',1)],                            [('push',1)]),
        'elves':      ([('push',1)],                            [('push',2)]),
        'prison':     ([('push',1)],                            [('fon',2)]),
        'lands':      ([('push',1)],                            [('fon',1)]),
    },

    # ── vs BUG Tempo ─────────────────────────────────────────────────────────
    # How each antagonist adapts when BUG is protagonist.
    'bug': {
        # Fair decks: board Pyroblast vs BUG's blue threats
        'uwx':        ([('push',2),('narset',1)],              [('pyro',2),('fluster',1)]),
        'mardu':      ([('push',2)],                           [('pyro',2)]),
        'dnt':        ([('push',1)],                           [('pyro',1)]),
        'boros':      ([('stp',1)],                            [('pyro',1)]),
        # Combo decks: minor adjustments (Veil already maindeck in storm/doomsday)
        # Storm already runs 4 Veil main — no extra needed
        'storm':      ([('ts',1)],                             [('nihil',1)]),
        # Show boards Empty the Warrens as alt win vs BUG (BUG has no answer to tokens)
        'show':       ([('ponder',1)],                         [('nihil',1)]),
        # Oops boards Chain of Vapor to bounce BUG threats
        'oops':       ([('petal',1)],                          [('nihil',1)]),
        # Doomsday already has Veil in some builds; minor swap
        'doomsday':   ([('ponder',1)],                         [('nihil',1)]),
        # Reanimator boards Unmask to strip BUG's FoW before going off
        'reanimator': ([('animatedead',1)],                    [('unmask',1)]),
        # Aggro decks adjust removal package
        'eldrazi':    ([('ww',1)],                             [('stp',1)]),
        'mono_black': ([('ts',1)],                             [('push',1)]),
    },
    # ── vs Dimir Tempo ───────────────────────────────────────────────────────
    'dimir': {
        'uwx':        ([('push',2),('narset',1)],              [('vos',2)]),
        'mardu':      ([('push',2)],                           [('pyro',1),('vos',1)]),
        'storm':      ([('bs',1),('ponder',1),('bs',1)],                [('fluster',2),('mindbreak',1)]),
        'show':       ([('push',2),('daze',1)],                [('fon',2),('surgical',1)]),
        'oops':       ([('push',3),('daze',1)],                [('nihil',2),('fon',1)]),
        'doomsday':   ([('push',3)],                           [('fon',2),('nihil',1)]),
        'reanimator': ([('push',2),('daze',1)],                [('nihil',2),('surgical',1)]),
        'dnt':        ([('push',2)],                           [('push',1),('stp',1)]),
        'eldrazi':    ([('ts',1)],                             [('push',2)]),
        'boros':      ([('ts',1)],                             [('push',2)]),
        'elves':      ([('ts',1),('daze',1)],                  [('push',2)]),
    },
    # ── vs UWx Control ───────────────────────────────────────────────────────
    'uwx': {
        'dimir':      ([('narset',1),('push',1)],              [('pyro',1)]),
        'mardu':      ([('narset',1)],                         [('stp',2)]),
        'storm':      ([('bs',2),('ponder',1),('bs',1)],              [('fluster',2),('mindbreak',1)]),
        'show':       ([('push',2),('narset',1)],              [('fon',2),('surgical',1)]),
        'oops':       ([('push',2),('narset',1)],              [('nihil',2),('fon',1)]),
        'doomsday':   ([('push',2),('snap',1)],                [('fon',2),('nihil',1)]),
        'reanimator': ([('push',2),('narset',1)],              [('nihil',2),('surgical',1)]),
        'elves':      ([('narset',1)],                         [('push',2)]),
        'eldrazi':    ([('narset',1)],                         [('stp',2)]),
        'boros':      ([('narset',1)],                         [('stp',2)]),
        'dnt':        ([('narset',1)],                         [('stp',1)]),
    },
    # ── vs Mono Black ────────────────────────────────────────────────────────
    'mono_black': {
        'storm':      ([('bs',2),('ponder',1)],                           [('nihil',1),('fluster',1)]),
        'oops':       ([('push',2)],                           [('nihil',2)]),
        'doomsday':   ([('push',2)],                           [('nihil',1),('fluster',1)]),
        'reanimator': ([('push',1)],                           [('nihil',2)]),
        'show':       ([('push',2)],                           [('nihil',1)]),
        'mardu':      ([('push',2)],                           [('push',2)]),
        'eldrazi':    ([],                                     [('nihil',1)]),
        'boros':      ([('push',1)],                           [('push',1)]),
        'dnt':        ([],                                     [('nihil',1)]),
    },
    # ── vs 8-Cast ────────────────────────────────────────────────────────────
    'eight_cast': {
        'storm':      ([],                                     [('mindbreak',1),('fluster',1)]),
        'oops':       ([],                                     [('nihil',1),('mindbreak',1)]),
        'doomsday':   ([],                                     [('fon',2)]),
        'reanimator': ([],                                     [('nihil',1)]),
        'dimir':      ([('push',2)],                           [('fon',2)]),
        'uwx':        ([('push',2),('narset',1)],              [('fon',2)]),
        'bug':        ([('push',2),('ts',1)],                  [('fon',2),('fluster',1)]),
        'mardu':      ([('push',2)],                           [('mindbreak',1)]),
        'show':       ([('push',2)],                           [('fon',2)]),
        'lands':      ([],                                     [('fon',1)]),
        'eldrazi':    ([],                                     [('fon',1)]),
    },
    # ── vs Mardu ─────────────────────────────────────────────────────────────
    'mardu': {
        'storm':      ([('bs',2),('ponder',1)],                           [('mindbreak',2)]),
        'oops':       ([('push',2)],                           [('nihil',2)]),
        'doomsday':   ([('push',2)],                           [('nihil',1),('mindbreak',1)]),
        'reanimator': ([('push',1)],                           [('nihil',2)]),
        'show':       ([('push',2)],                           [('fon',1)]),
        'dimir':      ([('push',2)],                           [('push',1),('pyro',1)]),
        'uwx':        ([('push',2)],                           [('stp',1),('pyro',1)]),
        'eldrazi':    ([],                                     [('stp',1)]),
        'elves':      ([('push',2)],                           [('push',2)]),
        'lands':      ([('push',1)],                           [('stp',1)]),
    },
    # ── vs Death & Taxes ─────────────────────────────────────────────────────
    'dnt': {
        'storm':      ([('bs',1)],                           [('fluster',2)]),
        'oops':       ([('push',1)],                           [('nihil',2)]),
        'doomsday':   ([('push',1)],                           [('nihil',1),('fluster',1)]),
        'reanimator': ([('push',1)],                           [('nihil',2)]),
        'show':       ([('push',1)],                           [('fon',1)]),
        'eldrazi':    ([],                                     [('stp',1)]),
        'elves':      ([('push',1)],                           [('stp',1)]),
        'mardu':      ([],                                     [('stp',1)]),
        'boros':      ([],                                     [('stp',1)]),
    },
    # ── vs Boros Initiative ──────────────────────────────────────────────────
    'boros': {
        'storm':      ([('bs',1)],                           [('mindbreak',1)]),
        'oops':       ([('push',1)],                           [('nihil',1)]),
        'reanimator': ([('push',1)],                           [('nihil',1)]),
        'doomsday':   ([('push',1)],                           [('nihil',1)]),
        'eldrazi':    ([],                                     [('stp',1)]),
        'elves':      ([('push',1)],                           [('stp',1)]),
        'dimir':      ([('push',1)],                           [('stp',1)]),
        'dnt':        ([],                                     [('stp',1)]),
    },
    # ── vs Eldrazi Aggro ─────────────────────────────────────────────────────
    'eldrazi': {
        'storm':      ([],                                     [('mindbreak',1)]),
        'oops':       ([],                                     [('nihil',1)]),
        'reanimator': ([],                                     [('nihil',1)]),
        'doomsday':   ([],                                     [('nihil',1),('mindbreak',1)]),
        'elves':      ([],                                     [('stp',1)]),
        'mardu':      ([],                                     [('stp',1)]),
        'boros':      ([('ww',1)],                             [('chalice',1)]),
        'dnt':        ([],                                     [('stp',1)]),
        'lands':      ([],                                     [('stp',1)]),
    },
    # ── vs Painter ───────────────────────────────────────────────────────────
    'painter': {
        'storm':      ([],                                     [('mindbreak',1)]),
        'oops':       ([],                                     [('nihil',1)]),
        'reanimator': ([],                                     [('nihil',1)]),
        'doomsday':   ([],                                     [('nihil',1)]),
        'dimir':      ([],                                     [('fon',1)]),
        'uwx':        ([],                                     [('fon',1)]),
        'bug':        ([],                                     [('fon',1)]),
        'lands':      ([],                                     [('stp',1)]),
        'eldrazi':    ([],                                     [('stp',1)]),
    },
    # ── vs Artifacts Prison ──────────────────────────────────────────────────
    'prison': {
        'storm':      ([],                                     [('mindbreak',1)]),
        'oops':       ([],                                     [('nihil',1)]),
        'reanimator': ([],                                     [('nihil',1)]),
        'doomsday':   ([],                                     [('nihil',1)]),
        'dimir':      ([],                                     [('fon',1)]),
        'bug':        ([],                                     [('fon',1)]),
        'elves':      ([],                                     [('stp',1)]),
        'lands':      ([],                                     [('stp',1)]),
    },
    # ── vs Lands ─────────────────────────────────────────────────────────────
    'lands': {
        'storm':      ([],                                     [('mindbreak',1)]),
        'oops':       ([],                                     [('nihil',1)]),
        'reanimator': ([],                                     [('nihil',1)]),
        'doomsday':   ([],                                     [('nihil',1)]),
        'dimir':      ([('wl',1)],                             [('fon',1)]),
        'bug':        ([('wl',1)],                             [('fon',1)]),
        'mardu':      ([('wl',1)],                             [('stp',1)]),
        'eldrazi':    ([('wl',1)],                             [('stp',1)]),
    },

}


def make_storm_deck() -> List[Card]:
    d = []
    # Rituals
    d += [instant('Dark Ritual', 1, {'B':1}, {'B'}, tag='darkrit')] * 4
    d += [instant('Cabal Ritual', 2, {'B':1,'generic':1}, {'B'}, tag='cabalrit')] * 4
    d += [artifact('Lion\'s Eye Diamond', 0, {}, tag='led', is_combo_piece=True)] * 4
    # Tutors / draw
    d += [instant('Brainstorm', 1, {'U':1}, {'U'}, tag='bs')] * 4
    d += [sorcery('Ponder', 1, {'U':1}, {'U'}, tag='ponder')] * 4
    d += [sorcery('Infernal Tutor', 2, {'B':1,'generic':1}, {'B'}, tag='itutor', is_combo_piece=True)] * 4
    d += [instant('Ad Nauseam', 5, {'B':2,'generic':3}, {'B'}, tag='adnauseam', is_combo_piece=True)] * 3
    d += [sorcery('Past in Flames', 5, {'R':1,'generic':4}, {'R'}, tag='pif', is_combo_piece=True)] * 2
    # Win condition
    d += [sorcery('Tendrils of Agony', 4, {'B':1,'generic':3}, {'B'}, tag='tendrils',
                  win_condition=True, is_combo_piece=True)] * 4
    # Protection
    d += [instant('Force of Will', 5, {'U':1,'generic':4}, {'U'}, tag='fow', free_cast_if_blue=True)] * 4
    d += [instant('Veil of Summer', 1, {'G':1}, {'G'}, tag='vos')] * 4
    d += [instant('Flusterstorm', 1, {'U':1}, {'U'}, tag='fluster')] * 3
    # Discard
    d += [sorcery('Thoughtseize', 1, {'B':1}, {'B'}, tag='ts', life_cost=2)] * 2
    # 14 lands
    d += [fetch_land('Polluted Delta', ['Island','Swamp'])] * 4
    d += [fetch_land('Misty Rainforest', ['Island','Forest'])] * 2
    d += [dual_land('Underground Sea', ['U','B'], ['Island','Swamp'])] * 3
    d += [dual_land('Volcanic Island', ['U','R'], ['Island','Mountain'])] * 1
    d += [dual_land('Bayou', ['B','G'], ['Swamp','Forest'])] * 1
    d += [basic_land('Swamp', 'B', 'Swamp')] * 3
    assert len(d) == 60, f"Storm deck: {len(d)}"
    return d


# ── Reanimator (60) ────────────────────────────────────────────
# Fast reanimate: Entomb + Reanimate/Exhume T1


def make_reanimator_deck() -> List[Card]:
    d = []
    # Combo engine
    d += [instant('Entomb', 1, {'B':1}, {'B'}, tag='entomb', is_combo_piece=True)] * 4
    d += [sorcery('Reanimate', 1, {'B':1}, {'B'}, tag='reanimate', is_combo_piece=True)] * 4
    d += [sorcery('Exhume', 2, {'B':1,'generic':1}, {'B'}, tag='exhume', is_combo_piece=True)] * 4
    d += [enchantment('Animate Dead', 2, {'B':1,'generic':1}, {'B'}, tag='animatedead', is_combo_piece=True)] * 4
    # Win conditions
    d += [creature('Griselbrand', 8, {'B':4,'generic':4}, {'B'}, 7, 7,
                   tag='gris', flying=True, win_condition=True)] * 4
    d += [creature('Archon of Cruelty', 8, {'B':2,'generic':6}, {'B'}, 6, 6,
                   tag='archon', flying=True, win_condition=True)] * 2
    d += [creature('Atraxa, Grand Unifier', 7, {'W':1,'U':1,'B':1,'G':1,'generic':3},
                   {'W','U','B','G'}, 7, 7, tag='atraxa', flying=True, win_condition=True)] * 2
    # Protection / disruption
    d += [instant('Force of Will', 5, {'U':1,'generic':4}, {'U'}, tag='fow', free_cast_if_blue=True)] * 4
    d += [sorcery('Thoughtseize', 1, {'B':1}, {'B'}, tag='ts', life_cost=2)] * 4
    d += [sorcery('Unmask', 4, {'B':1,'generic':3}, {'B'}, tag='unmask')] * 4
    d += [instant('Brainstorm', 1, {'U':1}, {'U'}, tag='bs')] * 4
    # 20 lands
    d += [fetch_land('Polluted Delta', ['Island','Swamp'])] * 4
    d += [fetch_land('Marsh Flats', ['Plains','Swamp'])] * 4
    d += [dual_land('Underground Sea', ['U','B'], ['Island','Swamp'])] * 3
    d += [basic_land('Swamp', 'B', 'Swamp')] * 9
    assert len(d) == 60, f"Reanimator deck: {len(d)}"
    return d


# ── UR Aggro (60) ──────────────────────────────────────────────
# Murktide shell — Ragavan, DRC, bolts, Price of Progress


def make_mardu_deck() -> List[Card]:
    d = []
    # Free evoke engine
    d += [creature('Grief', 3, {'B':1,'generic':2}, {'B'}, 3, 2,
                   tag='grief', flash=True, is_combo_piece=True)] * 4
    d += [creature('Fury', 5, {'R':1,'generic':4}, {'R'}, 3, 3,
                   tag='fury', flash=True, trample=True, is_combo_piece=True)] * 4
    # Ephemerate returns the evoked creature before sacrifice resolves
    d += [instant('Ephemerate', 1, {'W':1}, {'W'}, tag='ephemerate', is_combo_piece=True)] * 4
    # Fast threats
    d += [creature('Ragavan, Nimble Pilferer', 1, {'R':1}, {'R'}, 2, 1,
                   tag='ragavan', haste=True)] * 4
    d += [creature('Orcish Bowmasters', 2, {'B':1,'generic':1}, {'B'}, 1, 1,
                   tag='bowm', flash=True)] * 4
    # Disruption
    d += [sorcery('Thoughtseize', 1, {'B':1}, {'B'}, tag='ts', life_cost=2)] * 4
    d += [instant('Lightning Bolt', 1, {'R':1}, {'R'}, tag='bolt')] * 4
    d += [instant('Swords to Plowshares', 1, {'W':1}, {'W'}, tag='stp')] * 2
    # Counterspells
    d += [instant('Force of Will', 5, {'U':1,'generic':4}, {'U'}, tag='fow', free_cast_if_blue=True)] * 2
    # 28 lands
    d += [fetch_land('Arid Mesa', ['Mountain','Plains'])] * 4
    d += [fetch_land('Marsh Flats', ['Plains','Swamp'])] * 4
    d += [fetch_land('Bloodstained Mire', ['Swamp','Mountain'])] * 2
    d += [dual_land('Badlands', ['B','R'], ['Swamp','Mountain'])] * 2
    d += [dual_land('Plateau', ['R','W'], ['Mountain','Plains'])] * 2
    d += [dual_land('Scrubland', ['W','B'], ['Plains','Swamp'])] * 2
    d += [basic_land('Plains', 'W', 'Plains')] * 4
    d += [basic_land('Swamp', 'B', 'Swamp')] * 4
    d += [basic_land('Mountain', 'R', 'Mountain')] * 4
    assert len(d) == 60, f"Mardu deck: {len(d)}"
    return d


# ──────────────────────────────────────────────
# Death and Taxes (60-card, March 2026 standard list)
# Core: Aether Vial + Thalia + Stoneforge + Rishadan Port + Wasteland
# No FoW, no blue — BUG advantage: cantrips work freely, counters hit everything
# ──────────────────────────────────────────────

def make_ur_aggro_deck() -> List[Card]:
    d = []
    # Threats
    d += [creature('Ragavan, Nimble Pilferer', 1, {'R':1}, {'R'}, 2, 1,
                   tag='ragavan', haste=True)] * 4
    d += [creature('Dragon\'s Rage Channeler', 1, {'R':1}, {'R'}, 3, 3,
                   tag='drc')] * 4
    d += [creature('Murktide Regent', 7, {'U':1,'generic':6}, {'U'}, 8, 8,
                   tag='murk', delve=True)] * 4
    d += [creature('Brazen Borrower', 3, {'U':1,'generic':2}, {'U'}, 3, 1,
                   tag='borrow', flash=True, flying=True)] * 2
    # Burn / removal
    d += [instant('Lightning Bolt', 1, {'R':1}, {'R'}, tag='bolt')] * 4
    d += [sorcery('Price of Progress', 2, {'R':1,'generic':1}, {'R'}, tag='pop')] * 2
    d += [instant('Unholy Heat', 1, {'R':1}, {'R'}, tag='heat')] * 2
    # Cantrips / filtering
    d += [instant('Brainstorm', 1, {'U':1}, {'U'}, tag='bs')] * 4
    d += [sorcery('Ponder', 1, {'U':1}, {'U'}, tag='ponder')] * 4
    d += [sorcery('Expressive Iteration', 2, {'U':1,'R':1}, {'U','R'}, tag='ei')] * 4
    # Counterspells
    d += [instant('Force of Will', 5, {'U':1,'generic':4}, {'U'}, tag='fow', free_cast_if_blue=True)] * 4
    d += [instant('Daze', 2, {'U':1,'generic':1}, {'U'}, tag='daze')] * 2
    # 20 lands
    d += [fetch_land('Scalding Tarn', ['Island','Mountain'])] * 4
    d += [fetch_land('Flooded Strand', ['Island','Plains'])] * 2
    d += [dual_land('Volcanic Island', ['U','R'], ['Island','Mountain'])] * 4
    d += [basic_land('Island', 'U', 'Island')] * 4
    d += [basic_land('Mountain', 'R', 'Mountain')] * 6
    assert len(d) == 60, f"UR Aggro deck: {len(d)}"
    return d


# ── Mardu Aggro (60) ───────────────────────────────────────────
# Grief + Ephemerate engine, Fury, Bowmasters, Ragavan


def make_dimir_flash_deck() -> List[Card]:
    """
    Dimir Flash with Wan Shi Tong, Librarian — Legacy 2025/2026
    WST held at flash speed; triggers on every BUG fetch crack.
    {X}{U}{U}: enters with X counters, draws X/2 cards.
    Passive: whenever opp searches library → +1/+1 counter + draw.
    """
    d = []
    d += [creature('Wan Shi Tong, Librarian', 2, {'U':2}, {'U'},
                   1, 1, tag='wst', flash=True, flying=True, vigilance=True)] * 4
    d += [creature('Orcish Bowmasters', 2, {'B':1,'generic':1}, {'B'},
                   1, 1, tag='bowm', flash=True)] * 4
    d += [creature('Murktide Regent', 7, {'U':1,'generic':6}, {'U'},
                   3, 3, tag='murk', flying=True, delve=True)] * 2
    d += [creature('Tamiyo, Inquisitive Student', 1, {'U':1}, {'U'},
                   0, 3, tag='tamiyo')] * 3
    d += [instant('Force of Will', 5, {'U':1,'generic':4}, {'U'},
                  tag='fow', free_cast_if_blue=True)] * 4
    d += [instant('Force of Negation', 3, {'U':1,'generic':2}, {'U'},
                  tag='fon', free_cast_if_blue=True)] * 2
    d += [instant('Daze', 1, {'U':1}, {'U'}, tag='daze')] * 3
    d += [instant('Flusterstorm', 1, {'U':1}, {'U'}, tag='fluster')] * 1
    d += [instant('Brainstorm', 1, {'U':1}, {'U'}, tag='bs')] * 4
    d += [sorcery('Ponder', 1, {'U':1}, {'U'}, tag='ponder')] * 4
    d += [instant('Fatal Push', 1, {'B':1}, {'B'}, tag='push')] * 4
    d += [sorcery('Thoughtseize', 1, {'B':1}, {'B'}, tag='ts', life_cost=2)] * 3
    d += [fetch_land('Polluted Delta', ['Underground Sea', 'Tropical Island'])] * 4
    d += [fetch_land('Misty Rainforest', ['Underground Sea', 'Tropical Island'])] * 2
    d += [fetch_land('Scalding Tarn', ['Underground Sea', 'Volcanic Island'])] * 2
    d += [dual_land('Underground Sea', ['U', 'B'], ['Island', 'Swamp'])] * 4
    d += [dual_land_tapped('Undercity Sewers', ['U', 'B'], ['Island', 'Swamp'])] * 2
    d += [utility_land('Wasteland', [], 'wl')] * 4
    d += [basic_land('Island', 'U', 'Island')] * 3
    d += [basic_land('Swamp', 'B', 'Swamp')] * 1
    assert len(d) == 60, f"Dimir Flash: {len(d)}"
    return d


DECKS = {
    'bug':       make_bug_deck,
    'dimir':     make_dimir_deck,
    'dimir_b':    make_dimir_b_deck,
    'show':      make_show_deck,
    'lands':     make_lands_deck,
    'oops':      make_oops_deck,
    'prison':    make_prison_deck,
    'uwx':       make_uwx_deck,
    'eldrazi':   make_eldrazi_deck,
    'painter':   make_painter_deck,
    'doomsday':  make_doomsday_deck,
    'storm':     make_storm_deck,
    'reanimator':make_reanimator_deck,
    'ur_aggro':  make_ur_aggro_deck,
    'mardu':     make_mardu_deck,
    'dnt':       make_dnt_deck,
    'mono_black':make_mono_black_deck,
    'boros':     make_boros_deck,
    'dimir_flash': make_dimir_flash_deck,
}

# MATCHUP_META: auto-built from deck_registry (each deck declares name + meta_share)
# Fallback for built-in decks that don't have DECK_META yet
_BUILTIN_META = {
    'bug': {'name': 'BUG Tempo', 'share': 0.02},
}
try:
    from deck_registry import build_matchup_meta
    MATCHUP_META = build_matchup_meta()
    MATCHUP_META.update(_BUILTIN_META)
except ImportError:
    MATCHUP_META = _BUILTIN_META


# ─────────────────────────────────────────────
# BUG Sideboard (15)
# ─────────────────────────────────────────────


DECKS = {
    'bug':          make_bug_deck,
    'dimir':        make_dimir_deck,
    'dimir_b':      make_dimir_b_deck,
    'show':         make_show_deck,
    'lands':        make_lands_deck,
    'oops':         make_oops_deck,
    'prison':       make_prison_deck,
    'uwx':          make_uwx_deck,
    'eldrazi':      make_eldrazi_deck,
    'painter':      make_painter_deck,
    'doomsday':     make_doomsday_deck,
    'storm':        make_storm_deck,
    'reanimator':   make_reanimator_deck,
    'ur_aggro':     make_ur_aggro_deck,
    'mardu':        make_mardu_deck,
    'dnt':          make_dnt_deck,
    'mono_black':   make_mono_black_deck,
    'boros':        make_boros_deck,
    'dimir_flash':  make_dimir_flash_deck,
    'elves':        make_elves_deck,
}

# Register all deck constructors from deck_registry (replaces _PLUGIN_DECKS)
try:
    from deck_registry import register_into_decks_dict
    register_into_decks_dict(DECKS)
except ImportError:
    pass

