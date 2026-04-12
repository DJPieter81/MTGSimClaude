# Hand Analysis Methodology

## Overview

Extract real opening hands from the sim and generalize what wins. This produces two outputs:
1. **Statistical profiles** — WR by composition (land count, creature count, key cards)
2. **Real example hands** — Actual 7-card hands from games with turn-by-turn logs

## Step 1: Sample Collection

Run 2,000 games with the target deck as player 1 against a random spread of opponents:

```python
random.seed(42)  # Reproducible
for _ in range(2000):
    opp = random.choice(all_opponents)
    r = run_symmetric_game(target_deck, opp)
    if r.bug_mulls > 0: continue  # Only 7-card keeps
    
    record = {
        'hand': [str(c) for c in r.bug_opening_hand],
        'won': r.winner == 'p1',
        'vs': opp,
        'kill_turn': r.kill_turn,
        'game_len': r.game_length,
        'mulls': r.bug_mulls,
    }
```

Expect ~75-80% of games to be 7-card keeps (1,500-1,600 usable samples).

## Step 2: Card Classification

Classify each card in the hand into functional categories. These are deck-specific:

### Burn categories
| Category | Cards |
|----------|-------|
| Lands | Mountain, Barbarian Ring, Inspiring Vantage, Fiery Islet |
| Creatures | Goblin Guide, Monastery Swiftspear, Eidolon of the Great Revel |
| Burn spells | Lightning Bolt, Chain Lightning, Lava Spike, Rift Bolt, Price of Progress, Fireblast, Searing Blaze, Skullcrack |

### UR Delver categories
| Category | Cards |
|----------|-------|
| Lands | Volcanic Island, Scalding Tarn, Polluted Delta, etc. |
| Threats | Delver, DRC, Murktide Regent, Brazen Borrower |
| Cantrips | Brainstorm, Ponder, Preordain, Expressive Iteration |
| Free counters | Force of Will, Daze, Spell Pierce |
| Removal | Lightning Bolt, Unholy Heat |

## Step 3: Composition Analysis

### By count (land, creature, spell split)
```python
formulas = defaultdict(lambda: [0, 0])  # [wins, games]
for h in hands:
    key = f"{n_lands}L-{n_creatures}C-{n_spells}S"
    formulas[key][0] += h['won']
    formulas[key][1] += 1
```

Report WR for each formula with ≥30 games.

### By named archetype
Define 8-12 archetypes per deck based on MTG strategy:

```python
archetypes = {
    'T1 threat + Force + cantrip': [h for h in hands 
        if has_t1_threat and has_force and n_cantrips >= 1],
    'Double threat + cantrip': [h for h in hands 
        if n_creatures >= 2 and n_cantrips >= 1],
    # etc.
}
```

Report WR with delta from baseline (e.g., "+6.4pp above average").

### By individual card presence
```python
for key_card in deck_key_cards:
    with_card = [h for h in hands if key_card in hand]
    without = [h for h in hands if key_card not in hand]
    # Compare WRs
```

## Step 4: Generalization

Distill findings into 2-3 memorable rules. Pattern:

> "**[Deck]'s best hands have [N] lands** ([WR]% — each additional land costs ~[X]pp), 
> **[M] creatures** ([WR]%), and **[K] [spell type]** ([WR]%)."

Always include:
1. The single best formula with WR and sample size
2. The most surprising finding (e.g., "Force barely matters")
3. The worst keepable composition

## Step 5: Example Hand Selection

### Winning hands (3 examples)
1. **Fastest kill**: Sort by kill_turn, pick the most instructive T3-T4 kill
2. **Typical win**: A T5-T6 win that shows the standard game plan
3. **Unusual win**: A hand that looks bad but won (demonstrates the archetype insight)

For each, replay the game and extract turn-by-turn from logs. Verify mana math.

### Losing hands (2-3 examples)
Key insight: **show hands that SHOULD have won but lost to matchup/variance**. This teaches what the deck can't beat, not what a "bad hand" looks like.

1. **Good hand, T1 combo**: Perfect 7 that lost to opponent's T1 kill
2. **Had the answer, got stripped**: E.g., Force of Will taken by Unmask
3. **Uninteractable threat**: E.g., Marit Lage that can't be blocked or removed

## Mana Math Checklist

Before publishing any hand example, verify:

- [ ] Each turn's plays don't exceed available mana
- [ ] Suspend costs are accounted for (Rift Bolt suspend = R)
- [ ] Fireblast needs 2 Mountains ON THE BATTLEFIELD
- [ ] Free spells have correct alternate costs (Force = exile blue card + 1 life)
- [ ] Daze = return Island to hand (costs your land drop tempo)
- [ ] Goblin Guide trigger reveals OPPONENT's card, not yours
- [ ] Prowess triggers from NONCREATURE spells only
- [ ] Delve uses cards from graveyard (need prior cantrips/fetches)
- [ ] Fetchlands cost 1 life

## Sample Output Format

```
The Winning Formula
───────────────────
2 lands · 1 creature · 4 spells
79.8% win rate (238 games) — +6.4pp above baseline

HAND ARCHETYPE WIN RATES
────────────────────────
2 lands + creature + 4 burn    79.8%  ████████████████ +6.4pp
Double creature + burn         73.9%  ██████████████   +0.5pp
── baseline (all keeps) ──     73.4%  ──────────────── 
No creature, all burn          69.8%  █████████████    -3.7pp
```
