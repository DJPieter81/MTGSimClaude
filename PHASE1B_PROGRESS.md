# Phase 1B Audit Fixes — Cumulative Progress

**Sessions 1, 2, 3. 400/400 tests passing throughout.**
**Latest matrix: `matrix_20260517_175024.json` (36 decks, 1260 matchups, n=100, seed=2026)**

## What landed across sessions

### Engine-wide keyword infrastructure
| Keyword | Pre-audit | Post-fixes | Status |
|---|---|---|---|
| flying | 26 refs | 31 refs | ✅ |
| evoke, lifelink, reach, deathtouch, haste, indestructible, hexproof | various | unchanged | ✅ pre-existing |
| **first_strike** | 0 refs | ~10 | ✅ session 2 — 2-step combat damage |
| **double_strike** | 0 refs | ~10 | ✅ session 2 |
| **menace** | 0 refs | ~3 | ✅ session 2 — block restriction |
| **delirium** | 0 refs | ~15 | ✅ session 2 — DRC + Unholy Heat |
| **trample** | 1 ref | ~5 | ✅ session 3 — excess to player |
| vigilance, surveil, cascade | 1 each | unchanged | ❌ low-priority |

### Structural fixes
- Tamiyo, Seasoned Scholar → planeswalker (session 1; was creature)
- Kaito, Bane of Nightmares → planeswalker (session 2; was creature)
- Delver of Secrets transform (session 2; reveals top of library)

### Card-specific implementations

**Lands deck (7 cards, session 3):**
- Mox Diamond — discard land for +1 mana/turn
- Expedition Map — cast for 1, {2}+T+sac to tutor combo lands
- Once Upon a Time — free if first spell, tutor creature/land
- Malevolent Rumble — reveal 4 + mill 3 + Eldrazi Spawn ritual
- Grafdigger's Cage — opp.cage_lock blocks reanimate
- Skateboard — ETB taps opp's biggest creature
- Cage-respect check added to Reanimator

**Oops (session 3):**
- Pact of Negation — 0-mana free counter + upkeep tax
- Gated to major threats (is_major_threat check)

**D&T (session 3):**
- Sanctum Prelate — deploy priority + ETB choice "1"
- opp_can_cast: blocks noncreature CMC=1 spells

**Painter (session 3):**
- Voltaic Key, Manifold Key, Mishra's Desk — deploy as artifacts
- Gated to combo-assembled or ≥3 spare mana

**Mono-Black (session 3):**
- Carnage Interpreter ETB — discard hand + 4 clue tokens + +2/+2
- Clue tokens: sac {2}+T to draw a card

**Show (session 3):**
- Stock Up — 3-mana cast, top 5 → take 2

### Bug fixes
- `gs.p1_deck`/`gs.p2_deck` never set in `game_replay.py`
- CardType shadowing in lands strategy crashed Marit Lage creation
- Stock Up went in wrong function (regex search jumped past undocstring'd show)
- Pact used as generic counter — added `is_major_threat` gate
- Painter support artifacts deploying too aggressively — added combo-gate

### P/T data corrections
- Carnage Interpreter: 2/2 → 3/3 (now 5/5 menace post-ETB)
- Seasoned Dungeoneer: 3/3 → 3/4
- Elvish Spirit Guide 'espirit': 3/2 cmc=1 → 2/2 cmc=3

## Post-audit matrix WR rankings

### T1 (top 6)
1. **burn** 70.0% — fastest deck
2. **depths** 66.5%
3. **ur_tempo** 66.3%
4. **eldrazi** 63.5% — boosted by trample (session 3)
5. **lands** 62.5% — **biggest winner**: Mox + Rumble + Cage + OUAT
6. **dnt** 57.8% — Thalia first strike + Sanctum Prelate

### T2 (7 decks): ur_delver, mono_black 57%, affinity, dimir_d, storm, boros, infect
### T3 (10 decks): oops, dimir_c, sneak_a/b, uwx, cloudpost, dimir_b, ocelot, elves, painter
### T4 (11 decks): prison, show, **bug 43.3%**, dimir, reanimator, dimir_flash, cephalid, eight_cast, goblins, wan_shi_tong, belcher, **mardu 35.2%**, **doomsday 30.7%**

### Key shifts from audit
- **lands** moved from middle to T1 (+major utility cards)
- **bug** dropped due to Tamiyo + Kaito → planeswalkers (no free attacks)
- **mardu** still struggles vs burn (own discard + Eidolon-style damage)

## Files modified (cumulative)

| File | Cumulative Δ lines | Highlights |
|---|---|---|
| rules.py | +3 | Card.first_strike, double_strike, menace fields |
| cards.py | +22 | creature() kwargs + P/T + keyword tagging |
| engine.py | ~+19,000 | Bulk: keyword logic + card implementations |
| sim.py | +9 | `_execute_turn` hooks for delirium / delver / pact |
| game_replay.py | +682 | `gs.p1_deck` fix + earlier v3 replayer |
| config.py | +8 | Pact added to COUNTER_TAGS |

## Backups (in /tmp/)
- `rules.before_p1.py`, `cards.before_p1.py`
- `engine.before_p2.py`, `before_fs.py`, `before_delver.py`
- `engine.before_p7.py`, `before_p8.py`, `before_p9.py`, `before_p10.py`, `before_p11.py`
- `config.before_p9.py`, `sim.before_p9.py`

## Still pending (lower priority)

**Card implementations:**
- Kaldra Compleat equip — needs equipment grant system
- Bridge from Below — near-zero impact (oops self-mill exiles them)
- Nihil Spellbomb — sideboard only
- Portable Hole — can't cast in painter (no W mana)
- Turntimber Symbiosis sorcery mode — rarely used

**Modeling refinements:**
- Tamiyo's +1 (each player draws on upkeep)
- Kaito's "creature during your turn" mode
- Grief aliasing bug (shared object across copies)
- Pact upkeep is 3UU specifically (sim uses 5 generic)

**Phase 2 / 3 (original asks):**
- Phase 2: NDJSON event-log port from `MTGSimManu/engine/replay_log.py` (~2-3 hours, 288-line module)
- Phase 3: Cross-pollinate replayers — decision cards + subsystem chips + feedback (~2-3 hours)

## Audit data preserved
- `/tmp/card_inventory.json` (194 cards)
- `/tmp/scryfall_data.json` (193 matched)
- `/tmp/audit_findings.json` (27 flagged)
- `/tmp/AUDIT_REPORT.txt`
- `/tmp/oracle_cards.json` (173MB; redownload from `https://api.scryfall.com/bulk-data` if needed)
