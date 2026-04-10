# Data Model Reference

## generate_html() Return

Returns a complete HTML string. Called via:
```python
html = generate_html(matchup, seeds, protagonist='deck')
```
- `matchup`: opponent deck key (e.g., 'sneak_a', 'dimir_flash')
- `seeds`: list of ints for Bo3 (e.g., [42, 99, 7]) or single int for Bo1
- `protagonist`: P1 deck key (e.g., 'burn', 'oops')

## run_one_game() Return Dict

```python
{
    'matchup': str,           # opponent deck key
    'meta_name': str,         # human-readable opponent name
    'seed': int,              # random seed used
    'protagonist': str,       # P1 deck key
    'pro_label': str,         # P1 display name (e.g., 'BURN')
    'bug_goes_first': bool,   # True if P1 is on the play
    'bug_mulls': int,         # P1 mulligan count
    'opp_mulls': int,         # P2 mulligan count
    'bug_mull_history': List[MullStep],  # P1 mulligan decisions
    'opp_mull_history': List[MullStep],  # P2 mulligan decisions
    'bug_open': List[str],    # P1 kept hand (abbreviated card names)
    'opp_open': List[str],    # P2 kept hand
    'turns_data': List[TurnData],  # per-turn structured data
    'life_bug': List[int],    # P1 life at each display turn
    'life_opp': List[int],    # P2 life at each display turn
    'display_turn': int,      # total display turns played
    'winner': str,            # 'PRO_LABEL' or 'OPP'
    'win_reason': str,        # human-readable win condition
    'bug_life': int,          # P1 final life
    'opp_life': int,          # P2 final life
    'bug_board': List[CreatureData],  # P1 final creatures
    'opp_board': List[CreatureData],  # P2 final creatures
}
```

## MullStep

```python
{
    'hand': List[str],    # abbreviated card names for this hand
    'size': int,          # hand size (7, 6, 5, 4)
    'kept': bool,         # True if this hand was kept
    'reason': str,        # _explain_hand() output: composition + issues/strengths
}
```

Example: `{'hand': ['USea', 'Ponder', 'FoW', ...], 'size': 7, 'kept': False, 'reason': '3L/0T/2can · 1 protection — ISSUES: no action'}`

## TurnData

```python
{
    'num': int,              # display turn number (sequential across both players)
    'label': str,            # player label ('BURN', 'OPP')
    'label_cls': str,        # CSS class ('bug' or 'opp')
    'life': int,             # this player's life after the turn
    'life_before': int,      # this player's life before the turn
    'opp_life': int,         # opponent's life after the turn
    'hand_before': List[str],  # cards in hand at start of turn
    'hand_after': List[str],   # cards in hand at end of turn
    'creatures': List[CreatureData],      # player's creatures
    'opp_creatures': List[CreatureData],  # opponent's creatures
    'lands': List[str],                   # player's lands
    'opp_lands': List[str],               # opponent's lands
    'artifacts': List[str],               # player's artifacts
    'opp_artifacts': List[str],
    'enchantments': List[str],            # player's enchantments
    'opp_enchantments': List[str],
    'planeswalkers': List[str],           # player's planeswalkers
    'opp_planeswalkers': List[str],
    'graveyard': List[str],               # player's graveyard
    'opp_graveyard': List[str],
    'plays': List[PlayData],   # actions taken this turn
    'narrative': str,          # strategic commentary (may be empty)
}
```

## CreatureData

```python
{
    'name': str,         # abbreviated name (max 14 chars)
    'power': int,
    'toughness': int,
    'sick': bool,        # True if has summoning sickness
}
```

## PlayData

```python
{
    'text': str,         # HTML-escaped action text
    'reason': str,       # human-readable reasoning (may be empty)
    'key': bool,         # True for ★ game-deciding plays
    'counter': bool,     # True if this play was countered
    'cat': str,          # category: draw/land/combat/interact/discard/removal/combo/spell/trigger/cantrip/mana/other
}
```

## Card Name Abbreviations

The replayer uses the `ABBREV` dict to shorten card names for display:
- `Force of Will` → `FoW`
- `Dragon's Rage Channeler` → `DRC`
- `Underground Sea` → `USea`
- `Mishra's Bauble` → `Bauble`
- `Lightning Bolt` → `Bolt`
- etc.

Full list in game_replay.py `ABBREV` dict (~80 entries).
