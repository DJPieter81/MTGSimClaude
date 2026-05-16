# MTGSimClaude LLM Audit — 2026-05-16

**N=41 traces graded** | Model(s): heuristic-v1

## Domain averages

| Domain | Avg Grade | Worst Trace | Best Trace |
|--------|-----------|-------------|------------|
| mulligan | B | depths_vs_burn_s99 (D) | bug_vs_storm_s2026 (B+) |
| mana | B | elves_vs_dnt_s2026 (C) | elves_vs_dnt_s99 (A) |
| combat | B | bug_vs_storm_s42 (C) | bug_vs_storm_s2026 (B) |
| combo | C+ | depths_vs_burn_s99 (D) | elves_vs_dnt_s99 (A+) |
| interaction | C+ | depths_vs_burn_s7 (C) | bug_vs_storm_s2026 (A) |
| meta | B | depths_vs_burn_s7 (C) | elves_vs_dnt_s42 (A) |

## Per-trace summary

### bug_vs_storm_s2026 — p1 won on turn 10
- **mulligan**: B+ — Kept 7; won — opening hand was adequate
- **mana**: B — Resource deployment supported a T10 win
- **combat**: B — Won through non-combat means
- **combo**: B — Non-combo deck — domain not primary axis
- **interaction**: A — Heavy disruption (9 decisions) enabled win
- **meta**: B — Eventually closed the matchup
- **overall**: B+ — Average across 6 domains — won in 10 turns

### bug_vs_storm_s42 — p2 won on turn 6
- **mulligan**: C+ — Mulled to 6; card disadvantage contributed to loss
- **mana**: C+ — Suboptimal mana utilization over 6 turns
- **combat**: C — Limited combat engagement
- **combo**: B — Non-combo deck — domain not primary axis
- **interaction**: C+ — Disruption was not enough to prevent opponent plan
- **meta**: C+ — Lost — played actively but could not overcome matchup
- **overall**: C+ — Average across 6 domains — lost in 6 turns

### bug_vs_storm_s7 — p1 won on turn 9
- **mulligan**: B+ — Kept 7; won — opening hand was adequate
- **mana**: B — Resource deployment supported a T9 win
- **combat**: B — Won through non-combat means
- **combo**: B — Non-combo deck — domain not primary axis
- **interaction**: A — Heavy disruption (10 decisions) enabled win
- **meta**: B — Eventually closed the matchup
- **overall**: B+ — Average across 6 domains — won in 9 turns

### bug_vs_storm_s99 — p1 won on turn 6
- **mulligan**: B+ — Kept 7; won — opening hand was adequate
- **mana**: B+ — Resource deployment supported a T6 win
- **combat**: B — Won through non-combat means
- **combo**: B — Non-combo deck — domain not primary axis
- **interaction**: A — Heavy disruption (5 decisions) enabled win
- **meta**: B+ — Efficiently closed the matchup
- **overall**: B+ — Average across 6 domains — won in 6 turns

### depths_vs_burn_s42 — p1 won on turn 5
- **mulligan**: B+ — Kept 7; won — opening hand was adequate
- **mana**: B+ — Won but took 5 turns — mana was adequate
- **combat**: B — Combo deck — combat decisions minimal
- **combo**: B+ — Combo executed on T5 — efficient
- **interaction**: B — Combo resolved without needing protection
- **meta**: B+ — Efficiently closed a favored matchup
- **overall**: B+ — Average across 6 domains — won in 5 turns

### depths_vs_burn_s7 — p2 won on turn None
- **mulligan**: B — Kept 7; lost — opening hand was possibly too greedy
- **mana**: C+ — Lost in 6 turns — possible mana sequencing issues
- **combat**: B — Combo deck — combat decisions minimal
- **combo**: C — Failed to assemble combo — could not find pieces
- **interaction**: C — No protection deployed against disruption
- **meta**: C — Lost a matchup that should be favored (depths vs burn) — possible role confusion
- **overall**: C+ — Average across 6 domains — lost in 6 turns

### depths_vs_burn_s99 — p2 won on turn None
- **mulligan**: D — Mulled to 4; aggressive mulligan strategy backfired
- **mana**: C+ — Lost in 3 turns — possible mana sequencing issues
- **combat**: B — Combo deck — combat decisions minimal
- **combo**: D — Failed to assemble combo — disrupted early
- **interaction**: C — No protection deployed against disruption
- **meta**: C — Lost a matchup that should be favored (depths vs burn) — possible role confusion
- **overall**: C — Average across 6 domains — lost in 3 turns

### doomsday_vs_ur_delver_s2026 — p2 won on turn None
- **mulligan**: B — Kept 7; lost — opening hand was possibly too greedy
- **mana**: C+ — Lost in 4 turns — possible mana sequencing issues
- **combat**: B — Combo deck — combat decisions minimal
- **combo**: D — Failed to assemble combo — disrupted early
- **interaction**: C — No protection deployed against disruption
- **meta**: C — Lost — limited decision points suggest structural disadvantage
- **overall**: C+ — Average across 6 domains — lost in 4 turns

### doomsday_vs_ur_delver_s42 — p2 won on turn None
- **mulligan**: B — Kept 7; lost — opening hand was possibly too greedy
- **mana**: C+ — Lost in 6 turns — possible mana sequencing issues
- **combat**: B — Combo deck — combat decisions minimal
- **combo**: C — Failed to assemble combo — could not find pieces
- **interaction**: C — No protection deployed against disruption
- **meta**: C+ — Lost — played actively but could not overcome matchup
- **overall**: C+ — Average across 6 domains — lost in 6 turns

### doomsday_vs_ur_delver_s7 — p2 won on turn None
- **mulligan**: B — Kept 7; lost — opening hand was possibly too greedy
- **mana**: C+ — Lost in 5 turns — possible mana sequencing issues
- **combat**: B — Combo deck — combat decisions minimal
- **combo**: D — Failed to assemble combo — disrupted early
- **interaction**: C — No protection deployed against disruption
- **meta**: C+ — Lost — played actively but could not overcome matchup
- **overall**: C+ — Average across 6 domains — lost in 5 turns

### doomsday_vs_ur_delver_s99 — p2 won on turn None
- **mulligan**: B — Kept 7; lost — opening hand was possibly too greedy
- **mana**: C+ — Lost in 5 turns — possible mana sequencing issues
- **combat**: B — Combo deck — combat decisions minimal
- **combo**: D — Failed to assemble combo — disrupted early
- **interaction**: C — No protection deployed against disruption
- **meta**: C+ — Lost — played actively but could not overcome matchup
- **overall**: C+ — Average across 6 domains — lost in 5 turns

### elves_vs_dnt_s2026 — p2 won on turn None
- **mulligan**: B — Kept 7; lost — opening hand was possibly too greedy
- **mana**: C — Lost in 7 turns — possible mana sequencing issues
- **combat**: B — Combo deck — combat decisions minimal
- **combo**: C — Failed to assemble combo — could not find pieces
- **interaction**: C — No protection deployed against disruption
- **meta**: C+ — Lost — played actively but could not overcome matchup
- **overall**: C+ — Average across 6 domains — lost in 7 turns

### elves_vs_dnt_s42 — p1 won on turn 6
- **mulligan**: B+ — Kept 7; won — opening hand was adequate
- **mana**: B+ — Won but took 6 turns — mana was adequate
- **combat**: B — Combo deck — combat decisions minimal
- **combo**: B+ — Combo executed on T6 — efficient
- **interaction**: B — Combo resolved without needing protection
- **meta**: A — Won an unfavored matchup (elves vs dnt) — strong matchup awareness
- **overall**: B+ — Average across 6 domains — won in 6 turns

### elves_vs_dnt_s7 — p2 won on turn None
- **mulligan**: B — Kept 7; lost — opening hand was possibly too greedy
- **mana**: C — Lost in 9 turns — possible mana sequencing issues
- **combat**: B — Combo deck — combat decisions minimal
- **combo**: C — Failed to assemble combo — could not find pieces
- **interaction**: C — No protection deployed against disruption
- **meta**: C+ — Lost — played actively but could not overcome matchup
- **overall**: C+ — Average across 6 domains — lost in 9 turns

### elves_vs_dnt_s99 — p1 won on turn 4
- **mulligan**: B+ — Kept 7; won — opening hand was adequate
- **mana**: A — Fast kill (T4) implies efficient mana sequencing
- **combat**: B — Combo deck — combat decisions minimal
- **combo**: A+ — Clean combo kill on T4 — optimal assembly
- **interaction**: B — Combo resolved without needing protection
- **meta**: A — Won an unfavored matchup (elves vs dnt) — strong matchup awareness
- **overall**: B+ — Average across 6 domains — won in 4 turns

### goblins_vs_uwx_s42 — p2 won on turn 15
- **mulligan**: B — Kept 7; lost — opening hand was possibly too greedy
- **mana**: B — Adequate mana utilization over 15 turns
- **combat**: C — Aggro plan stalled — opponent stabilized
- **combo**: B — Non-combo deck — domain not primary axis
- **interaction**: C+ — Interaction fell short of needs
- **meta**: C — Lost — limited decision points suggest structural disadvantage
- **overall**: C+ — Average across 6 domains — lost in 15 turns

### goblins_vs_uwx_s7 — p2 won on turn 15
- **mulligan**: B — Kept 7; lost — opening hand was possibly too greedy
- **mana**: B — Adequate mana utilization over 15 turns
- **combat**: C — Aggro plan stalled — opponent stabilized
- **combo**: B — Non-combo deck — domain not primary axis
- **interaction**: C+ — Interaction fell short of needs
- **meta**: C — Lost — limited decision points suggest structural disadvantage
- **overall**: C+ — Average across 6 domains — lost in 15 turns

### goblins_vs_uwx_s99 — p2 won on turn 15
- **mulligan**: B — Kept 7; lost — opening hand was possibly too greedy
- **mana**: B — Adequate mana utilization over 15 turns
- **combat**: C — Aggro plan stalled — opponent stabilized
- **combo**: B — Non-combo deck — domain not primary axis
- **interaction**: C+ — Interaction fell short of needs
- **meta**: C — Lost — limited decision points suggest structural disadvantage
- **overall**: C+ — Average across 6 domains — lost in 15 turns

### oops_vs_dimir_s42 — p2 won on turn None
- **mulligan**: C+ — Mulled to 6; card disadvantage contributed to loss
- **mana**: C — Lost in 10 turns — possible mana sequencing issues
- **combat**: B — Combo deck — combat decisions minimal
- **combo**: C — Failed to assemble combo — could not find pieces
- **interaction**: C+ — Protection was insufficient
- **meta**: C+ — Lost — played actively but could not overcome matchup
- **overall**: C+ — Average across 6 domains — lost in 10 turns

### oops_vs_dimir_s7 — p2 won on turn None
- **mulligan**: C+ — Mulled to 6; card disadvantage contributed to loss
- **mana**: C — Lost in 14 turns — possible mana sequencing issues
- **combat**: B — Combo deck — combat decisions minimal
- **combo**: C — Failed to assemble combo — could not find pieces
- **interaction**: C+ — Protection was insufficient
- **meta**: C+ — Lost — played actively but could not overcome matchup
- **overall**: C+ — Average across 6 domains — lost in 14 turns

### oops_vs_dimir_s99 — p1 won on turn 6
- **mulligan**: B+ — Kept 7; won — opening hand was adequate
- **mana**: B+ — Won but took 6 turns — mana was adequate
- **combat**: B — Combo deck — combat decisions minimal
- **combo**: B+ — Combo executed on T6 — efficient
- **interaction**: B+ — Protected combo with countermagic
- **meta**: A — Won an unfavored matchup (oops vs dimir) — strong matchup awareness
- **overall**: B+ — Average across 6 domains — won in 6 turns

### painter_vs_eldrazi_s42 — p2 won on turn None
- **mulligan**: B — Kept 7; lost — opening hand was possibly too greedy
- **mana**: C+ — Suboptimal mana utilization over 4 turns
- **combat**: C — Limited combat engagement
- **combo**: B — Non-combo deck — domain not primary axis
- **interaction**: C+ — Interaction fell short of needs
- **meta**: C — Lost — limited decision points suggest structural disadvantage
- **overall**: C+ — Average across 6 domains — lost in 4 turns

### painter_vs_eldrazi_s7 — p1 won on turn 7
- **mulligan**: B+ — Kept 7; won — opening hand was adequate
- **mana**: B+ — Resource deployment supported a T7 win
- **combat**: B — Won through non-combat means
- **combo**: B — Non-combo deck — domain not primary axis
- **interaction**: B — Adequate interaction for game plan
- **meta**: B — Eventually closed the matchup
- **overall**: B — Average across 6 domains — won in 7 turns

### painter_vs_eldrazi_s99 — p2 won on turn None
- **mulligan**: D — Mulled to 4; aggressive mulligan strategy backfired
- **mana**: C+ — Suboptimal mana utilization over 4 turns
- **combat**: C — Limited combat engagement
- **combo**: B — Non-combo deck — domain not primary axis
- **interaction**: C+ — Interaction fell short of needs
- **meta**: C — Lost — limited decision points suggest structural disadvantage
- **overall**: C+ — Average across 6 domains — lost in 4 turns

### reanimator_vs_burn_s2026 — p2 won on turn None
- **mulligan**: B — Kept 7; lost — opening hand was possibly too greedy
- **mana**: C+ — Lost in 4 turns — possible mana sequencing issues
- **combat**: B — Combo deck — combat decisions minimal
- **combo**: D — Failed to assemble combo — disrupted early
- **interaction**: C — No protection deployed against disruption
- **meta**: C — Lost a matchup that should be favored (reanimator vs burn) — possible role confusion
- **overall**: C+ — Average across 6 domains — lost in 4 turns

### reanimator_vs_burn_s42 — p1 won on turn 4
- **mulligan**: B+ — Kept 7; won — opening hand was adequate
- **mana**: A — Fast kill (T4) implies efficient mana sequencing
- **combat**: B — Combo deck — combat decisions minimal
- **combo**: A+ — Clean combo kill on T4 — optimal assembly
- **interaction**: B — Combo resolved without needing protection
- **meta**: B+ — Efficiently closed a favored matchup
- **overall**: B+ — Average across 6 domains — won in 4 turns

### reanimator_vs_burn_s7 — p1 won on turn 6
- **mulligan**: B+ — Kept 7; won — opening hand was adequate
- **mana**: B+ — Won but took 6 turns — mana was adequate
- **combat**: B — Combo deck — combat decisions minimal
- **combo**: B+ — Combo executed on T6 — efficient
- **interaction**: B — Combo resolved without needing protection
- **meta**: B+ — Efficiently closed a favored matchup
- **overall**: B+ — Average across 6 domains — won in 6 turns

### reanimator_vs_burn_s99 — p2 won on turn None
- **mulligan**: B — Kept 7; lost — opening hand was possibly too greedy
- **mana**: C+ — Lost in 4 turns — possible mana sequencing issues
- **combat**: B — Combo deck — combat decisions minimal
- **combo**: D — Failed to assemble combo — disrupted early
- **interaction**: C — No protection deployed against disruption
- **meta**: C — Lost a matchup that should be favored (reanimator vs burn) — possible role confusion
- **overall**: C+ — Average across 6 domains — lost in 4 turns

### sneak_a_vs_bug_s2026 — p2 won on turn None
- **mulligan**: B — Kept 7; lost — opening hand was possibly too greedy
- **mana**: C+ — Lost in 5 turns — possible mana sequencing issues
- **combat**: B — Combo deck — combat decisions minimal
- **combo**: D — Failed to assemble combo — disrupted early
- **interaction**: C+ — Protection was insufficient
- **meta**: C+ — Lost — played actively but could not overcome matchup
- **overall**: C+ — Average across 6 domains — lost in 5 turns

### sneak_a_vs_bug_s42 — p1 won on turn 9
- **mulligan**: B+ — Kept 7; won — opening hand was adequate
- **mana**: B+ — Won but took 9 turns — mana was adequate
- **combat**: B — Combo deck — combat decisions minimal
- **combo**: B — Combo executed on T9 — delayed but successful
- **interaction**: B+ — Protected combo with countermagic
- **meta**: A — Won an unfavored matchup (sneak_a vs bug) — strong matchup awareness
- **overall**: B+ — Average across 6 domains — won in 9 turns

### sneak_a_vs_bug_s7 — p2 won on turn None
- **mulligan**: B — Kept 7; lost — opening hand was possibly too greedy
- **mana**: C — Lost in 7 turns — possible mana sequencing issues
- **combat**: B — Combo deck — combat decisions minimal
- **combo**: C — Failed to assemble combo — could not find pieces
- **interaction**: C+ — Protection was insufficient
- **meta**: C+ — Lost — played actively but could not overcome matchup
- **overall**: C+ — Average across 6 domains — lost in 7 turns

### sneak_a_vs_bug_s99 — p1 won on turn 5
- **mulligan**: B+ — Kept 7; won — opening hand was adequate
- **mana**: B+ — Won but took 5 turns — mana was adequate
- **combat**: B — Combo deck — combat decisions minimal
- **combo**: B+ — Combo executed on T5 — efficient
- **interaction**: B+ — Protected combo with countermagic
- **meta**: A — Won an unfavored matchup (sneak_a vs bug) — strong matchup awareness
- **overall**: B+ — Average across 6 domains — won in 5 turns

### storm_vs_dnt_s101 — p1 won on turn 2
- **mulligan**: B — Mulled to 6; still won
- **mana**: A — Fast kill (T2) implies efficient mana sequencing
- **combat**: B — Combo deck — combat decisions minimal
- **combo**: A+ — Clean combo kill on T2 — optimal assembly
- **interaction**: B — Combo resolved without needing protection
- **meta**: A — Won an unfavored matchup (storm vs dnt) — strong matchup awareness
- **overall**: B+ — Average across 6 domains — won in 2 turns

### storm_vs_dnt_s2026 — p1 won on turn 6
- **mulligan**: B+ — Kept 7; won — opening hand was adequate
- **mana**: B+ — Won but took 6 turns — mana was adequate
- **combat**: B — Combo deck — combat decisions minimal
- **combo**: B+ — Combo executed on T6 — efficient
- **interaction**: B — Combo resolved without needing protection
- **meta**: A — Won an unfavored matchup (storm vs dnt) — strong matchup awareness
- **overall**: B+ — Average across 6 domains — won in 6 turns

### storm_vs_dnt_s42 — p2 won on turn None
- **mulligan**: B — Kept 7; lost — opening hand was possibly too greedy
- **mana**: C — Lost in 7 turns — possible mana sequencing issues
- **combat**: B — Combo deck — combat decisions minimal
- **combo**: C — Failed to assemble combo — could not find pieces
- **interaction**: C — No protection deployed against disruption
- **meta**: C+ — Lost — played actively but could not overcome matchup
- **overall**: C+ — Average across 6 domains — lost in 7 turns

### storm_vs_dnt_s7 — p1 won on turn 4
- **mulligan**: B — Mulled to 6; still won
- **mana**: A — Fast kill (T4) implies efficient mana sequencing
- **combat**: B — Combo deck — combat decisions minimal
- **combo**: A+ — Clean combo kill on T4 — optimal assembly
- **interaction**: B — Combo resolved without needing protection
- **meta**: A — Won an unfavored matchup (storm vs dnt) — strong matchup awareness
- **overall**: B+ — Average across 6 domains — won in 4 turns

### storm_vs_dnt_s99 — p2 won on turn None
- **mulligan**: B — Kept 7; lost — opening hand was possibly too greedy
- **mana**: C — Lost in 8 turns — possible mana sequencing issues
- **combat**: B — Combo deck — combat decisions minimal
- **combo**: C — Failed to assemble combo — could not find pieces
- **interaction**: C — No protection deployed against disruption
- **meta**: C+ — Lost — played actively but could not overcome matchup
- **overall**: C+ — Average across 6 domains — lost in 8 turns

### ur_delver_vs_dimir_s2026 — p2 won on turn None
- **mulligan**: D — Mulled to 4; aggressive mulligan strategy backfired
- **mana**: C+ — Suboptimal mana utilization over 7 turns
- **combat**: C — Limited combat engagement
- **combo**: B — Non-combo deck — domain not primary axis
- **interaction**: C — Disruption was insufficient — key threats went unanswered
- **meta**: C+ — Lost — played actively but could not overcome matchup
- **overall**: C+ — Average across 6 domains — lost in 7 turns

### ur_delver_vs_dimir_s42 — p1 won on turn 9
- **mulligan**: B+ — Kept 7; won — opening hand was adequate
- **mana**: B — Resource deployment supported a T9 win
- **combat**: B — Won through non-combat means
- **combo**: B — Non-combo deck — domain not primary axis
- **interaction**: B+ — Interaction-backed win with measured disruption
- **meta**: B — Eventually closed the matchup
- **overall**: B — Average across 6 domains — won in 9 turns

### ur_delver_vs_dimir_s7 — p1 won on turn 7
- **mulligan**: B — Mulled to 6; still won
- **mana**: B+ — Resource deployment supported a T7 win
- **combat**: B — Won through non-combat means
- **combo**: B — Non-combo deck — domain not primary axis
- **interaction**: B+ — Interaction-backed win with measured disruption
- **meta**: B — Eventually closed the matchup
- **overall**: B — Average across 6 domains — won in 7 turns

### ur_delver_vs_dimir_s99 — p1 won on turn 10
- **mulligan**: B+ — Kept 7; won — opening hand was adequate
- **mana**: B — Resource deployment supported a T10 win
- **combat**: B — Won through non-combat means
- **combo**: B — Non-combo deck — domain not primary axis
- **interaction**: B+ — Interaction-backed win with measured disruption
- **meta**: B — Eventually closed the matchup
- **overall**: B — Average across 6 domains — won in 10 turns

## Flagged weaknesses (repeat C/D/F grades)

- **depths.combo** (2/41 traces C or below): depths_vs_burn_s7 (C), depths_vs_burn_s99 (D)
- **depths.interaction** (2/41 traces C or below): depths_vs_burn_s7 (C), depths_vs_burn_s99 (C)
- **depths.mana** (2/41 traces C or below): depths_vs_burn_s7 (C+), depths_vs_burn_s99 (C+)
- **depths.meta** (2/41 traces C or below): depths_vs_burn_s7 (C), depths_vs_burn_s99 (C)
- **doomsday.combo** (4/41 traces C or below): doomsday_vs_ur_delver_s2026 (D), doomsday_vs_ur_delver_s42 (C), doomsday_vs_ur_delver_s7 (D), doomsday_vs_ur_delver_s99 (D)
- **doomsday.interaction** (4/41 traces C or below): doomsday_vs_ur_delver_s2026 (C), doomsday_vs_ur_delver_s42 (C), doomsday_vs_ur_delver_s7 (C), doomsday_vs_ur_delver_s99 (C)
- **doomsday.mana** (4/41 traces C or below): doomsday_vs_ur_delver_s2026 (C+), doomsday_vs_ur_delver_s42 (C+), doomsday_vs_ur_delver_s7 (C+), doomsday_vs_ur_delver_s99 (C+)
- **doomsday.meta** (4/41 traces C or below): doomsday_vs_ur_delver_s2026 (C), doomsday_vs_ur_delver_s42 (C+), doomsday_vs_ur_delver_s7 (C+), doomsday_vs_ur_delver_s99 (C+)
- **elves.combo** (2/41 traces C or below): elves_vs_dnt_s2026 (C), elves_vs_dnt_s7 (C)
- **elves.interaction** (2/41 traces C or below): elves_vs_dnt_s2026 (C), elves_vs_dnt_s7 (C)
- **elves.mana** (2/41 traces C or below): elves_vs_dnt_s2026 (C), elves_vs_dnt_s7 (C)
- **elves.meta** (2/41 traces C or below): elves_vs_dnt_s2026 (C+), elves_vs_dnt_s7 (C+)
- **goblins.combat** (3/41 traces C or below): goblins_vs_uwx_s42 (C), goblins_vs_uwx_s7 (C), goblins_vs_uwx_s99 (C)
- **goblins.interaction** (3/41 traces C or below): goblins_vs_uwx_s42 (C+), goblins_vs_uwx_s7 (C+), goblins_vs_uwx_s99 (C+)
- **goblins.meta** (3/41 traces C or below): goblins_vs_uwx_s42 (C), goblins_vs_uwx_s7 (C), goblins_vs_uwx_s99 (C)
- **oops.combo** (2/41 traces C or below): oops_vs_dimir_s42 (C), oops_vs_dimir_s7 (C)
- **oops.interaction** (2/41 traces C or below): oops_vs_dimir_s42 (C+), oops_vs_dimir_s7 (C+)
- **oops.mana** (2/41 traces C or below): oops_vs_dimir_s42 (C), oops_vs_dimir_s7 (C)
- **oops.meta** (2/41 traces C or below): oops_vs_dimir_s42 (C+), oops_vs_dimir_s7 (C+)
- **oops.mulligan** (2/41 traces C or below): oops_vs_dimir_s42 (C+), oops_vs_dimir_s7 (C+)
- **painter.combat** (2/41 traces C or below): painter_vs_eldrazi_s42 (C), painter_vs_eldrazi_s99 (C)
- **painter.interaction** (2/41 traces C or below): painter_vs_eldrazi_s42 (C+), painter_vs_eldrazi_s99 (C+)
- **painter.mana** (2/41 traces C or below): painter_vs_eldrazi_s42 (C+), painter_vs_eldrazi_s99 (C+)
- **painter.meta** (2/41 traces C or below): painter_vs_eldrazi_s42 (C), painter_vs_eldrazi_s99 (C)
- **reanimator.combo** (2/41 traces C or below): reanimator_vs_burn_s2026 (D), reanimator_vs_burn_s99 (D)
- **reanimator.interaction** (2/41 traces C or below): reanimator_vs_burn_s2026 (C), reanimator_vs_burn_s99 (C)
- **reanimator.mana** (2/41 traces C or below): reanimator_vs_burn_s2026 (C+), reanimator_vs_burn_s99 (C+)
- **reanimator.meta** (2/41 traces C or below): reanimator_vs_burn_s2026 (C), reanimator_vs_burn_s99 (C)
- **sneak_a.combo** (2/41 traces C or below): sneak_a_vs_bug_s2026 (D), sneak_a_vs_bug_s7 (C)
- **sneak_a.interaction** (2/41 traces C or below): sneak_a_vs_bug_s2026 (C+), sneak_a_vs_bug_s7 (C+)
- **sneak_a.mana** (2/41 traces C or below): sneak_a_vs_bug_s2026 (C+), sneak_a_vs_bug_s7 (C)
- **sneak_a.meta** (2/41 traces C or below): sneak_a_vs_bug_s2026 (C+), sneak_a_vs_bug_s7 (C+)
- **storm.combo** (2/41 traces C or below): storm_vs_dnt_s42 (C), storm_vs_dnt_s99 (C)
- **storm.interaction** (2/41 traces C or below): storm_vs_dnt_s42 (C), storm_vs_dnt_s99 (C)
- **storm.mana** (2/41 traces C or below): storm_vs_dnt_s42 (C), storm_vs_dnt_s99 (C)
- **storm.meta** (2/41 traces C or below): storm_vs_dnt_s42 (C+), storm_vs_dnt_s99 (C+)
