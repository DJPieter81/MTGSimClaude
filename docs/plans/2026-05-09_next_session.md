---
title: Next session plan (post-2026-05-09 audit close-out)
date: 2026-05-09
audience: future-claude (Legacy session) + Manu (Modern port)
status: pending
prereq_reading:
  - docs/lessons/2026-05-03_combo_deck_audit.md  (bug taxonomy + diagnostic workflow)
  - CROSS_PROJECT_SYNC.md  lessons #29-#33
  - PLANNING.md  Session Log (May 03-04 rows)
---

# Next session plan

## Where we left off (commits e0067ef ← #119)

Eight PRs landed across two sessions:
- #111-#118: combo deck audit work
- #119: full matrix + guide refresh

End-state on `main`:
- **Tests**: 170 (up from 149)
- **Domain grades**: all 6 ≥ B- (was 4, combo+interaction failed)
- **Matrix**: `results/matrix_20260509_092522.json` (1,260 matchups, n=200)
- **Worktree**: clean

## What's still open

### A. Engine-level outliers (matrix-wide)

The May 09 refresh surfaced one big remaining outlier:

| Deck | WR vs field | Real Legacy | Δ |
|---|---|---|---|
| burn | **70.5%** | ~50-55% | +15-20pp |
| depths | 66.7% | ~55-60% | +6-12pp |
| eldrazi | 64.4% | ~55% | +9pp |
| ur_tempo | 63.4% | ~55-60% | +3-8pp |
| dimir_d | 58.2% | ~52% | +6pp |

**Burn at 70.5% is the canonical Bo1-modeling gap.** Real Legacy Burn is held in check by mainboard + sideboard hate (Sanctifier en-Vec, Mindbreak Trap, Solitude, gain-life creatures). The sim is Bo1-only and most decks don't run main-deck anti-burn. Two ways to attack this:

1. **Bo3-style main-deck reweighting** — bump anti-burn cards to higher main-deck counts in the sim (similar to the WST Sanctifier 2→3 fix in PR #113). Specifically:
   - WST: already at 3 Sanctifier; could go to 4
   - UWX: add 2-3 Sanctifier en-Vec or Solitude
   - Lands: already runs Maze of Ith
   - DnT: already at 2 Solitude (could go 3)
2. **Model the missing damage-prevention infrastructure** — Sanctifier en-Vec works but only via the per-strategy `pro_red` flag in burn.py's `deal_face_damage`. Generalise to all damage routers, then add Mindbreak Trap (free counter for storm/burn).

Suggested first move: Bo3-style maindeck reweighting (smaller diff, lower risk). The damage-prevention generalisation is a multi-day project.

### B. Bottom-5 decks still flagged

| Deck | Avg WR | Status |
|---|---|---|
| doomsday | 30.5% | Architectural — needs Cabal Therapy + per-matchup pile |
| mardu | 33.9% | Audited; structural Grief/Fury timing gap |
| belcher | 37.7% | Audited; tier-1 list now correct (PR #115) |
| goblins | 39.5% | Audited; mostly RNG-bound |
| wan_shi_tong | 39.5% | Audited; needs damage prevention work |

The architectural fixes here all involve engine-level work (CR-correctly model an ability or a damage type). Each is 1-3 days.

### C. Modern (Manu) port

Cross-project sync lessons #29-#33 are ready for the Manu session to consume.  Suggested order:

1. **Run the grep one-liner first** (lesson #29 question 9):
   ```bash
   grep -rn "draw(1)" decks/*.py
   ```
   Every hit should be a non-Brainstorm cantrip or activated ability. Found 3 bugs in Legacy this way.

2. **Build the `KNOWN[card] → (cmc, cost)` reference table** (lesson #31). Grep-walk all Modern deck builders. Found 18 mismatches in Legacy.

3. **Audit `_pick_land`-equivalent for single-deck gates** (lesson #29 question 4).

4. **Run the trace audit** on Modern's lowest-WR matchups using the diagnostic workflow from `docs/lessons/2026-05-03_combo_deck_audit.md`.

## Suggested next-session priorities (one-pager)

### P0 (start here)

**Burn rebalancing — Bo3-style maindeck reweighting.**
- Add 2-3 Sanctifier en-Vec to UWX maindeck
- Bump WST Sanctifier 3 → 4
- Bump DnT Solitude 2 → 3
- Verify burn vs field drops to ~55-60% on n=200 sweep

Estimate: 1-2 hours including verification + regression tests.

### P1 (if time)

**Mardu Grief/Fury structural gap.**  Mardu at 33.9% is below where it should be (~50%).  Trace audit of mardu vs dimir_b / mardu vs ur_delver to find the specific Grief/Fury issue.  Likely a Class C (strategy/preamble) bug — the evoke pitch logic interacting with shared TS.

Estimate: 2-3 hours.

**Doomsday vs Burn architectural fix.**  Adding Cabal Therapy modeling (sees opp hand, name a card, opp discards all copies).  This is the canonical real-DD discard tool.  Multi-day project; can be scoped down by adding it as a simplified "name highest-CMC nonland in opp hand".

Estimate: 1 day for simplified Cabal Therapy; 3-5 days for full per-matchup pile construction.

### P2 (parking lot — eventually)

- LED-Brainstorm pile per-matchup variants (race vs lifegain pile vs control pile)
- Mindbreak Trap modeling (free counter triggered by 3+ spells in opp turn)
- Generalise damage-prevention from `pro_red` → `protection_from_color(color)`
- Bo3 sideboard sim refresh (last run April 12)

## Files / commands cheat-sheet

```bash
# Latest matrix
results/matrix_20260509_092522.json

# Audit checklist (lessons doc)
docs/lessons/2026-05-03_combo_deck_audit.md

# Trace generator (uses run_game from sim.py)
# See PR #118 commit dcd5a22 for the regenerate-traces snippet

# Re-grade after sim changes
python3 scripts/grade_traces.py results/traces/*.json --local --force
python3 scripts/grade_traces.py --report

# Full refresh (~6min)
python3 refresh_all.py --resim 200 --seed 2026

# Tier-1 audit pattern
python3 << 'EOF'
from cards import DECKS
KNOWN = {"Doomsday": (3, {'B': 3}), ...}  # see PR #115 sim.py for full table
for deck_name, builder in DECKS.items():
    d = builder()
    for c in d:
        if c.name in KNOWN:
            exp_cmc, exp_cost = KNOWN[c.name]
            if c.cmc != exp_cmc or dict(c.mana_cost) != exp_cost:
                print(f'{deck_name} {c.name}: mismatch')
EOF
```

## Loop-break signal

Per CLAUDE.md ABSTRACTION CONTRACT: if 3 consecutive commits target the same outlier deck without moving the win rate toward its expected band, **halt**.  Run a replay against the worst matchup, identify the exact turn where EV diverges from correct play, name the responsible subsystem in writing in `docs/`.  No further code until that document exists.

This kicks in for **doomsday vs burn** specifically.  Three rounds of audit on Doomsday (PRs #111, #115, #117) moved doomsday vs burn from 8% to ~10% — well below the 8pp/3-rounds threshold.  Loop-break document already exists implicitly in `docs/lessons/2026-05-03_combo_deck_audit.md` ("Round 3 follow-up" + "What this session did NOT fix").  Next session must NOT attempt another single-line Doomsday fix without first writing the architectural design doc for Cabal Therapy + per-matchup pile.
