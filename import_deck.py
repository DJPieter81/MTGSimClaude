#!/usr/bin/env python3
"""
Deck importer — parse a raw decklist and generate a deck module.

Usage:
    # From CLI:
    python3 import_deck.py "Ruby Storm" aggro,combo < decklist.txt
    python3 import_deck.py "Bant Control" mirror --share 0.05 < decklist.txt

    # From Python:
    from import_deck import import_decklist
    import_decklist('''
        4 Goblin Guide
        4 Monastery Swiftspear
        4 Lightning Bolt
        4 Rift Bolt
        4 Lava Spike
        20 Mountain
        20 Mountain
    ''', name='Red Deck Wins', categories={'aggro'})

    # From a file in decks/imports/:
    # Just drop a .txt file and run:
    python3 import_deck.py --scan

Supports formats:
    4 Lightning Bolt
    4x Lightning Bolt
    4 Lightning Bolt (CMC 1)
    // comments and blank lines ignored
    Sideboard section ignored (after "Sideboard" line)
"""

import os
import re
import sys
import textwrap


# ── Card database: known cards with full attributes ──
# Cards already defined in the sim get their attributes from here.
# Unknown cards get reasonable defaults based on name heuristics.

def _load_known_cards():
    """Build a name → attributes dict from all existing decks."""
    known = {}
    try:
        from cards import DECKS
        for deck_key, deck_fn in DECKS.items():
            try:
                for card in deck_fn():
                    if card.name not in known:
                        known[card.name] = {
                            'cmc': card.cmc,
                            'tag': card.tag,
                            'colors': getattr(card, 'colors', set()),
                            'mana_cost': getattr(card, 'mana_cost', {}),
                            'is_creature': card.is_creature(),
                            'is_land': card.is_land(),
                            'is_cantrip': getattr(card, 'is_cantrip', False),
                            'base_power': getattr(card, 'base_power', 0),
                            'base_toughness': getattr(card, 'base_toughness', 0),
                            'card_type': card.card_type,
                            'haste': getattr(card, 'haste', False),
                            'flying': getattr(card, 'flying', False),
                            'flash': getattr(card, 'flash', False),
                            'win_condition': getattr(card, 'win_condition', False),
                            'is_combo_piece': getattr(card, 'is_combo_piece', False),
                        }
            except Exception:
                pass
    except ImportError:
        pass
    return known


def parse_decklist(text):
    """Parse a raw decklist string into [(count, name), ...].
    Stops at 'Sideboard' line. Ignores comments and blank lines."""
    lines = text.strip().split('\n')
    cards = []
    for line in lines:
        line = line.strip()
        if not line or line.startswith('//') or line.startswith('#'):
            continue
        if line.lower().startswith('sideboard'):
            break
        # Match: "4 Lightning Bolt" or "4x Lightning Bolt"
        m = re.match(r'^(\d+)\s*x?\s+(.+?)(?:\s*\(.*\))?\s*$', line, re.IGNORECASE)
        if m:
            count = int(m.group(1))
            name = m.group(2).strip()
            cards.append((count, name))
    return cards


def _make_tag(name):
    """Generate a card tag from name."""
    # Use existing tag if card is known
    known = _load_known_cards()
    if name in known and known[name]['tag']:
        return known[name]['tag']
    # Generate from name: lowercase, underscores, first meaningful word
    clean = re.sub(r'[^a-zA-Z0-9\s]', '', name).lower().split()
    if len(clean) >= 2:
        return clean[0][:4] + '_' + clean[1][:4]
    return clean[0][:8] if clean else 'card'


def _make_key(name):
    """Generate a deck key from name."""
    clean = re.sub(r'[^a-zA-Z0-9\s]', '', name).lower()
    return re.sub(r'\s+', '_', clean.strip())


def _guess_constructor(name, known_cards):
    """Guess the card constructor call for a card name."""
    n = repr(name)  # handles apostrophes in card names
    if name in known_cards:
        info = known_cards[name]
        tag = info['tag']
        if info['is_land']:
            if 'fetch' in tag or name in ('Polluted Delta', 'Flooded Strand', 'Scalding Tarn',
                    'Misty Rainforest', 'Bloodstained Mire', 'Windswept Heath', 'Wooded Foothills',
                    'Arid Mesa', 'Verdant Catacombs', 'Marsh Flats'):
                subtypes = _guess_fetch_subtypes(name)
                return f"fetch_land({n}, {subtypes})"
            elif tag == 'dual':
                return _dual_land_call(name)
            elif tag == 'basic' or getattr(info.get('card_type'), 'name', '') == 'LAND':
                return _basic_land_call(name)
            else:
                return _basic_land_call(name)  # fallback for unknown land types
        elif info['is_creature']:
            p = info['base_power']
            t = info['base_toughness']
            mc = info['mana_cost']
            colors = info['colors']
            extras = []
            if info['haste']: extras.append('haste=True')
            if info['flying']: extras.append('flying=True')
            if info['flash']: extras.append('flash=True')
            if info['win_condition']: extras.append('win_condition=True')
            ext = ', '.join(extras)
            if ext: ext = ', ' + ext
            return f"creature({n}, {info['cmc']}, {mc}, {colors}, {p}, {t}, tag='{tag}'{ext})"
        else:
            mc = info['mana_cost']
            colors = info['colors']
            return f"instant({n}, {info['cmc']}, {mc}, {colors}, tag='{tag}')"

    # Unknown card — generate placeholder
    return f"# TODO: define {n} — unknown card"


def _dual_land_call(name):
    """Generate dual_land() call with correct colors and subtypes."""
    duals = {
        'Underground Sea':  ({'U', 'B'}, {'Island', 'Swamp'}),
        'Volcanic Island':  ({'U', 'R'}, {'Island', 'Mountain'}),
        'Tropical Island':  ({'U', 'G'}, {'Island', 'Forest'}),
        'Tundra':           ({'U', 'W'}, {'Island', 'Plains'}),
        'Bayou':            ({'B', 'G'}, {'Swamp', 'Forest'}),
        'Badlands':         ({'B', 'R'}, {'Swamp', 'Mountain'}),
        'Scrubland':        ({'B', 'W'}, {'Swamp', 'Plains'}),
        'Taiga':            ({'R', 'G'}, {'Mountain', 'Forest'}),
        'Plateau':          ({'R', 'W'}, {'Mountain', 'Plains'}),
        'Savannah':         ({'G', 'W'}, {'Forest', 'Plains'}),
        # Shocklands
        'Steam Vents':      ({'U', 'R'}, {'Island', 'Mountain'}),
        'Watery Grave':     ({'U', 'B'}, {'Island', 'Swamp'}),
        'Breeding Pool':    ({'U', 'G'}, {'Island', 'Forest'}),
        'Hallowed Fountain':({'U', 'W'}, {'Island', 'Plains'}),
        'Overgrown Tomb':   ({'B', 'G'}, {'Swamp', 'Forest'}),
        'Blood Crypt':      ({'B', 'R'}, {'Swamp', 'Mountain'}),
        'Godless Shrine':   ({'B', 'W'}, {'Swamp', 'Plains'}),
        'Stomping Ground':  ({'R', 'G'}, {'Mountain', 'Forest'}),
        'Sacred Foundry':   ({'R', 'W'}, {'Mountain', 'Plains'}),
        'Temple Garden':    ({'G', 'W'}, {'Forest', 'Plains'}),
        # Undercity Sewers etc
        'Undercity Sewers': ({'U', 'B'}, {'Island', 'Swamp'}),
    }
    if name in duals:
        colors, subtypes = duals[name]
        return f"dual_land({repr(name)}, {colors}, {subtypes})"
    return f"dual_land({repr(name)}, {{'U', 'B'}}, {{'Island', 'Swamp'}})"


def _basic_land_call(name):
    """Generate basic_land() call with correct color and subtype."""
    basics = {
        'Island':   ('U', 'Island'),
        'Swamp':    ('B', 'Swamp'),
        'Mountain': ('R', 'Mountain'),
        'Forest':   ('G', 'Forest'),
        'Plains':   ('W', 'Plains'),
        'Wastes':   ('C', 'Wastes'),
    }
    if name in basics:
        color, subtype = basics[name]
        return f"basic_land({repr(name)}, '{color}', '{subtype}')"
    return f"basic_land({repr(name)}, 'C', {repr(name)})"


def _guess_fetch_subtypes(name):
    """Guess fetch land subtypes from name."""
    fetch_map = {
        'Polluted Delta': "['Island', 'Swamp']",
        'Flooded Strand': "['Plains', 'Island']",
        'Scalding Tarn': "['Island', 'Mountain']",
        'Misty Rainforest': "['Forest', 'Island']",
        'Bloodstained Mire': "['Swamp', 'Mountain']",
        'Windswept Heath': "['Forest', 'Plains']",
        'Wooded Foothills': "['Mountain', 'Forest']",
        'Arid Mesa': "['Mountain', 'Plains']",
        'Verdant Catacombs': "['Swamp', 'Forest']",
        'Marsh Flats': "['Plains', 'Swamp']",
    }
    return fetch_map.get(name, "['Island', 'Swamp']")


def import_decklist(text, name='New Deck', categories=None, meta_share=0.03):
    """
    Parse a decklist and generate a deck module file.
    Returns the file path of the generated module.
    """
    if categories is None:
        categories = set()

    cards = parse_decklist(text)
    total = sum(c for c, _ in cards)

    if total != 60:
        print(f"WARNING: Decklist has {total} cards (expected 60)")

    key = _make_key(name)
    known = _load_known_cards()

    # Generate the module
    lines = []
    lines.append(f'"""Auto-generated deck module for {name}."""')
    lines.append('')
    lines.append('from cards import creature, instant, sorcery, artifact, fetch_land, dual_land, basic_land')
    lines.append('from engine import _try_counter_any, combat_declare, update_goyf')
    lines.append('')
    lines.append('')
    lines.append(f'def make_{key}_deck():')
    lines.append(f'    """Build {name} — {total} cards."""')
    lines.append('    return [')

    unknown = []
    for count, card_name in cards:
        constructor = _guess_constructor(card_name, known)
        if constructor.startswith('# TODO'):
            unknown.append(card_name)
            lines.append(f'        # {count}x {card_name} — UNKNOWN, needs manual definition')
        else:
            lines.append(f'        *[{constructor}] * {count},')

    lines.append('    ]')
    lines.append('')
    lines.append('')
    lines.append(f'def strategy_{key}(player, opponent, gs, total_mana, log_fn, log_entries):')
    lines.append(f'    """Strategy for {name}."""')
    lines.append('    # Cast creatures (cheapest first)')
    lines.append('    for card in sorted([c for c in player.hand if c.is_creature()], key=lambda c: c.cmc):')
    lines.append('        if total_mana >= card.cmc:')
    lines.append('            player.remove_from_hand(card)')
    lines.append('            if not _try_counter_any(player, opponent, gs, card, log_entries):')
    lines.append('                player.put_creature_in_play(card)')
    lines.append(f'                log_fn(f"{{card.name}} ({{card.cmc}})")')
    lines.append('                total_mana -= card.cmc')
    lines.append('            else:')
    lines.append('                player.add_to_grave(card)')
    lines.append('            break')
    lines.append('')
    lines.append('    # Cast cantrips')
    lines.append('    can = next((c for c in player.hand if c.is_cantrip and total_mana >= c.cmc), None)')
    lines.append('    if can:')
    lines.append('        player.remove_from_hand(can); player.add_to_grave(can)')
    lines.append('        player.draw(1)')
    lines.append(f'        log_fn(f"{{can.name}} (cantrip)")')
    lines.append('        total_mana -= can.cmc')
    lines.append('')
    lines.append('    # Combat')
    lines.append('    attackers = [c for c in player.creatures if not c.summoning_sick]')
    lines.append('    if attackers:')
    lines.append('        combat_declare(player, opponent, gs, log_entries, attackers)')
    lines.append('')
    lines.append('    update_goyf(gs)')
    lines.append('')
    lines.append('')

    cats_str = '{' + ', '.join(f"'{c}'" for c in sorted(categories)) + '}'
    lines.append('DECK_META = {')
    lines.append(f"    'key':        '{key}',")
    lines.append(f"    'name':       '{name}',")
    lines.append(f"    'make_deck':  make_{key}_deck,")
    lines.append(f"    'strategy':   strategy_{key},")
    lines.append(f"    'keep':       None,")
    lines.append(f"    'categories': {cats_str},")
    lines.append(f"    'meta_share': {meta_share},")
    lines.append('}')

    # Write to decks/ directory
    decks_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'decks')
    filepath = os.path.join(decks_dir, f'{key}.py')

    with open(filepath, 'w') as f:
        f.write('\n'.join(lines) + '\n')

    print(f"Generated: {filepath}")
    print(f"  Key: {key}")
    print(f"  Cards: {total} ({len(cards)} unique)")
    if unknown:
        print(f"  UNKNOWN cards ({len(unknown)}): {', '.join(unknown)}")
        print(f"  These need manual Card definitions in the generated file.")
    print(f"\nVerify:")
    print(f"  python3 run_meta.py --deck {key}")
    print(f"  python3 run_meta.py --matchup {key} bug -n 50")

    return filepath


def scan_imports():
    """Scan decks/imports/ for .txt decklists and import them."""
    imports_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'decks', 'imports')
    if not os.path.isdir(imports_dir):
        print(f"No imports directory: {imports_dir}")
        return

    for f in sorted(os.listdir(imports_dir)):
        if not f.endswith('.txt'):
            continue
        name = f[:-4].replace('_', ' ').title()
        filepath = os.path.join(imports_dir, f)
        text = open(filepath).read()
        print(f"\n{'='*60}")
        print(f"Importing: {f} → {name}")
        import_decklist(text, name=name)


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Import a raw decklist into MTGSimClaude')
    parser.add_argument('name', nargs='?', default='New Deck', help='Deck name')
    parser.add_argument('categories', nargs='?', default='', help='Comma-separated categories (aggro,combo,...)')
    parser.add_argument('--share', type=float, default=0.03, help='Meta share (default: 0.03)')
    parser.add_argument('--scan', action='store_true', help='Scan decks/imports/ for .txt files')
    args = parser.parse_args()

    if args.scan:
        scan_imports()
    else:
        cats = set(args.categories.split(',')) if args.categories else set()
        cats.discard('')
        text = sys.stdin.read()
        if not text.strip():
            print("Paste decklist on stdin (Ctrl+D when done):")
            text = sys.stdin.read()
        import_decklist(text, name=args.name, categories=cats, meta_share=args.share)
