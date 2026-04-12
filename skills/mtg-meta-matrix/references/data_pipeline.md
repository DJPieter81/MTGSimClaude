# Data Pipeline Reference

## Overview

The meta matrix requires 5 JSON data files extracted from a game simulator. Each file captures a different dimension of the matchup data.

## Required Simulator Interface

The sim engine must provide a function with this signature:

```python
def run_symmetric_game(deck1: str, deck2: str) -> GameResult
```

Where `GameResult` has:
- `winner`: str ('p1' or 'p2')
- `kill_turn`: Optional[int]
- `game_length`: int
- `bug_mulls` / `opp_mulls`: int (mulligan count)
- `bug_opening_hand` / `opp_opening_hand`: List[Card]
- `final_bug_life` / `final_opp_life`: int
- `bug_went_first`: bool
- `log_lines`: List[str] — game log for parsing
- `win_reason`: str

## Step 1: Meta Matrix (N games per matchup)

```python
# Run N games for each ordered pair (d1, d2)
for d1 in decks:
    for d2 in decks:
        if d1 == d2: continue
        results = [run_symmetric_game(d1, d2) for _ in range(N)]
        # Compute: win_rate, avg_kill_turn, avg_game_length,
        # play_wr, draw_wr, final_lives, mull_rates, win_reasons
```

**Output format** (`meta_N.json`):
```json
{
  "d": ["deck1", "deck2", ...],           // deck names
  "a": {"deck1": 73.9, ...},              // flat average WR
  "w": {"deck1": 71.9, ...},              // meta-weighted WR
  "m": {
    "deck1|deck2": [wr, kill_turn, game_len, otp_wr, otd_wr, 
                     otp_n, otd_n, p1_life, p2_life, p1_mulls, 
                     p2_mulls, {"damage": N, "combo": N, ...}],
    ...
  }
}
```

**Recommended**: N=200 gives stable WR estimates (±3-5% at 95% CI). N=100 is faster but noisier.

## Step 2: Interaction Extraction (20 games per matchup)

Parse game logs for strategic events. Categories:

| Category | Key | Examples |
|----------|-----|----------|
| Locks/Hate | `l` | "Chalice on 1", "Blood Moon", "Thalia taxes" |
| Removal | `r` | "Bolt kills Guide", "Swords exiles Murktide" |
| Counters | `x` | "Force counters Show and Tell", "Daze on Brainstorm" |
| Pivots | `p` | "Sneak Attack → Emrakul", "Natural Order → Craterhoof" |

**Filtering**: Use a BORING_PIVOTS regex to exclude routine events (e.g., "deals 3 damage at 17 life" is not pivotal, "deals 3 damage at 1 life" is).

**Output format** (`interact_v3.json`):
```json
{
  "deck1|deck2": {
    "l": [["Chalice on 1 locks out deck", 8], ...],
    "r": [["Bolt kills Goblin Guide", 12], ...],
    "x": [["Force counters Ad Nauseam", 6], ...],
    "p": [["Sneak Attack → Emrakul, game over", 4], ...]
  }
}
```

## Step 3: Card-Level Extraction (20 games per matchup)

Parse game logs to identify:

1. **Top casts**: Most-played cards per deck per matchup
2. **Top attackers**: Which creatures connect in combat
3. **Damage engines**: Direct damage sources with total damage
4. **Finishers**: Which card dealt the killing blow

**Log line patterns to parse**:
```
★ CardName → X damage (opp at Y)     # direct damage
Attack: Card1, Card2 — N unblocked    # combat
CardName enters the battlefield       # creature deployment
CardName (draw N, mana=N)             # cantrip cast
```

**Finisher detection**: Scan from end of log backwards for the lethal action. Check for `opp at 0` or `opp at -N` patterns.

**Output format** (`card_trimmed.json`):
```json
{
  "deck1|deck2": {
    "c1": [["Card", count], ...],   // d1 top casts (top 3)
    "c2": [["Card", count], ...],   // d2 top casts
    "a1": [["Card", count], ...],   // d1 top attackers
    "a2": [["Card", count], ...],   // d2 top attackers
    "dm1": [["Card", total_dmg]],   // d1 damage engines
    "dm2": [["Card", total_dmg]],   // d2 damage engines
    "f": [["Card", kill_count]]     // d1 finisher cards
  }
}
```

## Step 4: Deck Aggregation

Roll up per-matchup card data into deck-level profiles:

```python
for deck in decks:
    aggregate = {
        'type': 'aggro|tempo|combo|control|midrange|prison|ramp',
        'speed': 'fast|medium|slow',
        'plan': 'One-sentence strategic description',
        'wr': flat_average_wr,
        'wwr': weighted_average_wr,
        'mvp': [[card, total_casts], ...],    # top 5 most-cast
        'atk': [[card, total_attacks], ...],   # top 4 attackers
        'dmg': [[card, total_damage], ...],    # damage engines
        'fin': [[card, total_kills], ...],     # top 4 finishers
        'mu': [[opponent, wr], ...]            # all matchups
    }
```

## Step 5: Weighted Win Rate

```python
for deck in decks:
    weighted = sum(wr_vs_opp * opp_avg_wr for opp) / sum(opp_avg_wr for opp)
```

This weights matchups by opponent meta strength as a proxy for tournament representation. Stronger decks are assumed to be more popular.

## Performance

Typical run times (36 decks, single-threaded Python):
- 200 games/matchup: ~5-6 minutes (two batched halves)
- 20 games/matchup card extraction: ~50 seconds
- 20 games/matchup interaction extraction: ~50 seconds
- Aggregation + weighted WR: <1 second
