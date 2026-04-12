# Mana Math Pitfalls

Common errors to check before publishing any hand example with a turn-by-turn sequence.

## Land & Mana Rules

| Rule | Wrong | Right |
|------|-------|-------|
| 1 land = 1 mana/turn | "T1: Guide + suspend Rift Bolt" (2 mana on 1 land) | Cast one OR the other, not both |
| Fireblast alt cost | "Fireblast with 1 Mountain" | Needs 2 Mountains ON THE BATTLEFIELD to sacrifice |
| Fetchland life cost | "Crack fetch, still at 20" | Each fetch costs 1 life |
| Shock land ETB | "Steam Vents untapped, still at 20" | Costs 2 life to enter untapped |
| Daze bounce cost | "Daze their spell, play land" | Daze returns an Island — you lose your land drop's mana |

## Spell Timing Rules

| Rule | Wrong | Right |
|------|-------|-------|
| Suspend is a special action | "Suspend triggers prowess" | Suspending does NOT cast the spell, no prowess |
| Suspend resolution IS a cast | "Rift Bolt off suspend, no prowess" | When it comes off suspend, it IS cast → prowess triggers |
| Prowess = noncreature only | "Cast Guide, Swiftspear gets +1/+0" | Guide is a creature, no prowess trigger |
| Sorcery speed | "Lava Spike in response to..." | Lava Spike is sorcery-speed only |

## Creature Ability Rules

| Rule | Wrong | Right |
|------|-------|-------|
| Goblin Guide trigger | "Guide reveals my top card" | Guide reveals DEFENDING PLAYER's top card |
| Eidolon symmetric | "Eidolon only hits them" | Eidolon triggers for YOUR spells too (CMC ≤3) |
| DRC delirium | "T1 DRC is 3/3" | Need 4 card types in graveyard (fetch + cantrip + instant + sorcery) |
| Delve uses graveyard | "T2 Murktide for UU" | Need 5+ cards in graveyard to delve to UU cost |
| Force of Will | "Force for free" | Force exiles a BLUE card from hand + costs 1 life |

## Common Kill Sequences to Verify

### Burn T3 Kill (requires 2+ lands)
```
T1: Land → Guide → attack 2 (18)
T2: Land → Swiftspear → suspend Rift Bolt → attack 3 (15)
T3: Rift Bolt (3, prowess) → Bolt (3, prowess) → Chain (3, prowess) 
    → attack Guide(2) + Swiftspear(4) = 6 → total 15 damage
```
Verify: T2 needs 2 mana (Swiftspear R + suspend R). T3 Rift resolves free (off suspend), then 2 mana for Bolt + Chain Lightning.

### UR Delver T4 Kill (requires 2+ lands + delirium by T3)
```
T1: Volcanic → Delver
T2: Fetch → DRC → cantrip → attack Delver 3 (15)  
T3: Cantrip → attack Delver(3) + DRC(3) = 6 (9)
T4: Bolt → attack 6 → total 15 damage from T2
```
Verify: DRC needs delirium by T3 (fetch = land, cantrip = instant/sorcery, need 1 more type in GY).
