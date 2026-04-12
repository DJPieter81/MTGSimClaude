# MTGSimClaude LLM Audit — 2026-04-12

**N=41 traces graded** | Model(s): heuristic-v1

## Domain averages

| Domain | Avg Grade | Worst Trace | Best Trace |
|--------|-----------|-------------|------------|
| mulligan | B | oops_vs_dimir_s42 (C+) | bug_vs_storm_s2026 (B+) |
| mana | B | elves_vs_dnt_s2026 (C) | elves_vs_dnt_s7 (A) |
| combat | B | goblins_vs_uwx_s42 (C) | goblins_vs_uwx_s99 (B+) |
| combo | C+ | depths_vs_burn_s42 (D) | elves_vs_dnt_s7 (A+) |
| interaction | C+ | depths_vs_burn_s42 (C) | bug_vs_storm_s2026 (B+) |
| meta | B | depths_vs_burn_s42 (C) | elves_vs_dnt_s42 (A) |

## Per-trace summary

### bug_vs_storm_s2026 — p1 won on turn 6
- **mulligan**: B+ — Kept 7; won — opening hand was adequate
- **mana**: B+ — Resource deployment supported a T6 win
- **combat**: B — Won through non-combat means
- **combo**: B — Non-combo deck — domain not primary axis
- **interaction**: B+ — Interaction-backed win with measured disruption
- **meta**: B+ — Efficiently closed the matchup
- **overall**: B+ — Average across 6 domains — won in 6 turns

### bug_vs_storm_s42 — p1 won on turn 7
- **mulligan**: B — Mulled to 6; still won
- **mana**: B+ — Resource deployment supported a T7 win
- **combat**: B — Won through non-combat means
- **combo**: B — Non-combo deck — domain not primary axis
- **interaction**: B+ — Interaction-backed win with measured disruption
- **meta**: B — Eventually closed the matchup
- **overall**: B — Average across 6 domains — won in 7 turns

### bug_vs_storm_s7 — p1 won on turn 9
- **mulligan**: B+ — Kept 7; won — opening hand was adequate
- **mana**: B — Resource deployment supported a T9 win
- **combat**: B — Won through non-combat means
- **combo**: B — Non-combo deck — domain not primary axis
- **interaction**: B+ — Interaction-backed win with measured disruption
- **meta**: B — Eventually closed the matchup
- **overall**: B — Average across 6 domains — won in 9 turns

### bug_vs_storm_s99 — p1 won on turn 6
- **mulligan**: B+ — Kept 7; won — opening hand was adequate
- **mana**: B+ — Resource deployment supported a T6 win
- **combat**: B — Won through non-combat means
- **combo**: B — Non-combo deck — domain not primary axis
- **interaction**: B+ — Interaction-backed win with measured disruption
- **meta**: B+ — Efficiently closed the matchup
- **overall**: B+ — Average across 6 domains — won in 6 turns

### depths_vs_burn_s42 — p2 won on turn None
- **mulligan**: B — Kept 7; lost — opening hand was possibly too greedy
- **mana**: C+ — Lost in 4 turns — possible mana sequencing issues
- **combat**: B — Combo deck — combat decisions minimal
- **combo**: D — Failed to assemble combo — disrupted early
- **interaction**: C — No protection deployed against disruption
- **meta**: C — Lost a matchup that should be favored (depths vs burn) — possible role confusion
- **overall**: C+ — Average across 6 domains — lost in 4 turns

### depths_vs_burn_s7 — p2 won on turn None
- **mulligan**: B — Kept 7; lost — opening hand was possibly too greedy
- **mana**: C+ — Lost in 4 turns — possible mana sequencing issues
- **combat**: B — Combo deck — combat decisions minimal
- **combo**: D — Failed to assemble combo — disrupted early
- **interaction**: C — No protection deployed against disruption
- **meta**: C — Lost a matchup that should be favored (depths vs burn) — possible role confusion
- **overall**: C+ — Average across 6 domains — lost in 4 turns

### depths_vs_burn_s99 — p2 won on turn None
- **mulligan**: B — Kept 7; lost — opening hand was possibly too greedy
- **mana**: C+ — Lost in 4 turns — possible mana sequencing issues
- **combat**: B — Combo deck — combat decisions minimal
- **combo**: D — Failed to assemble combo — disrupted early
- **interaction**: C — No protection deployed against disruption
- **meta**: C — Lost a matchup that should be favored (depths vs burn) — possible role confusion
- **overall**: C+ — Average across 6 domains — lost in 4 turns

### doomsday_vs_ur_delver_s2026 — p2 won on turn None
- **mulligan**: B — Kept 7; lost — opening hand was possibly too greedy
- **mana**: C+ — Lost in 5 turns — possible mana sequencing issues
- **combat**: B — Combo deck — combat decisions minimal
- **combo**: D — Failed to assemble combo — disrupted early
- **interaction**: C — No protection deployed against disruption
- **meta**: C — Lost — limited decision points suggest structural disadvantage
- **overall**: C+ — Average across 6 domains — lost in 5 turns

### doomsday_vs_ur_delver_s42 — p2 won on turn None
- **mulligan**: B — Kept 7; lost — opening hand was possibly too greedy
- **mana**: C+ — Lost in 5 turns — possible mana sequencing issues
- **combat**: B — Combo deck — combat decisions minimal
- **combo**: D — Failed to assemble combo — disrupted early
- **interaction**: C — No protection deployed against disruption
- **meta**: C+ — Lost — played actively but could not overcome matchup
- **overall**: C+ — Average across 6 domains — lost in 5 turns

### doomsday_vs_ur_delver_s7 — p2 won on turn None
- **mulligan**: B — Kept 7; lost — opening hand was possibly too greedy
- **mana**: C+ — Lost in 4 turns — possible mana sequencing issues
- **combat**: B — Combo deck — combat decisions minimal
- **combo**: D — Failed to assemble combo — disrupted early
- **interaction**: C — No protection deployed against disruption
- **meta**: C — Lost — limited decision points suggest structural disadvantage
- **overall**: C+ — Average across 6 domains — lost in 4 turns

### doomsday_vs_ur_delver_s99 — p2 won on turn None
- **mulligan**: B — Kept 7; lost — opening hand was possibly too greedy
- **mana**: C+ — Lost in 5 turns — possible mana sequencing issues
- **combat**: B — Combo deck — combat decisions minimal
- **combo**: D — Failed to assemble combo — disrupted early
- **interaction**: C — No protection deployed against disruption
- **meta**: C — Lost — limited decision points suggest structural disadvantage
- **overall**: C+ — Average across 6 domains — lost in 5 turns

### elves_vs_dnt_s2026 — p2 won on turn None
- **mulligan**: B — Kept 7; lost — opening hand was possibly too greedy
- **mana**: C — Lost in 9 turns — possible mana sequencing issues
- **combat**: B — Combo deck — combat decisions minimal
- **combo**: C — Failed to assemble combo — could not find pieces
- **interaction**: C — No protection deployed against disruption
- **meta**: C+ — Lost — played actively but could not overcome matchup
- **overall**: C+ — Average across 6 domains — lost in 9 turns

### elves_vs_dnt_s42 — p1 won on turn 5
- **mulligan**: B+ — Kept 7; won — opening hand was adequate
- **mana**: B+ — Won but took 5 turns — mana was adequate
- **combat**: B — Combo deck — combat decisions minimal
- **combo**: B+ — Combo executed on T5 — efficient
- **interaction**: B — Combo resolved without needing protection
- **meta**: A — Won an unfavored matchup (elves vs dnt) — strong matchup awareness
- **overall**: B+ — Average across 6 domains — won in 5 turns

### elves_vs_dnt_s7 — p1 won on turn 3
- **mulligan**: B+ — Kept 7; won — opening hand was adequate
- **mana**: A — Fast kill (T3) implies efficient mana sequencing
- **combat**: B — Combo deck — combat decisions minimal
- **combo**: A+ — Clean combo kill on T3 — optimal assembly
- **interaction**: B — Combo resolved without needing protection
- **meta**: A — Won an unfavored matchup (elves vs dnt) — strong matchup awareness
- **overall**: B+ — Average across 6 domains — won in 3 turns

### elves_vs_dnt_s99 — p1 won on turn 11
- **mulligan**: B+ — Kept 7; won — opening hand was adequate
- **mana**: B+ — Won but took 11 turns — mana was adequate
- **combat**: B — Combo deck — combat decisions minimal
- **combo**: B — Combo executed on T11 — delayed but successful
- **interaction**: B — Combo resolved without needing protection
- **meta**: A — Won an unfavored matchup (elves vs dnt) — strong matchup awareness
- **overall**: B+ — Average across 6 domains — won in 11 turns

### goblins_vs_uwx_s42 — p2 won on turn None
- **mulligan**: B — Kept 7; lost — opening hand was possibly too greedy
- **mana**: B — Adequate mana utilization over 11 turns
- **combat**: C — Aggro plan stalled — opponent stabilized
- **combo**: B — Non-combo deck — domain not primary axis
- **interaction**: C+ — Interaction fell short of needs
- **meta**: C — Lost — limited decision points suggest structural disadvantage
- **overall**: C+ — Average across 6 domains — lost in 11 turns

### goblins_vs_uwx_s7 — p2 won on turn 15
- **mulligan**: B — Kept 7; lost — opening hand was possibly too greedy
- **mana**: B — Adequate mana utilization over 15 turns
- **combat**: C — Aggro plan stalled — opponent stabilized
- **combo**: B — Non-combo deck — domain not primary axis
- **interaction**: C+ — Interaction fell short of needs
- **meta**: C — Lost — limited decision points suggest structural disadvantage
- **overall**: C+ — Average across 6 domains — lost in 15 turns

### goblins_vs_uwx_s99 — p1 won on turn 12
- **mulligan**: B+ — Kept 7; won — opening hand was adequate
- **mana**: B — Resource deployment supported a T12 win
- **combat**: B+ — Aggro plan executed in 12 turns — solid pressure
- **combo**: B — Non-combo deck — domain not primary axis
- **interaction**: B — Adequate interaction for game plan
- **meta**: B — Eventually closed the matchup
- **overall**: B — Average across 6 domains — won in 12 turns

### oops_vs_dimir_s42 — p2 won on turn None
- **mulligan**: C+ — Mulled to 6; card disadvantage contributed to loss
- **mana**: C — Lost in 9 turns — possible mana sequencing issues
- **combat**: B — Combo deck — combat decisions minimal
- **combo**: C — Failed to assemble combo — could not find pieces
- **interaction**: C — No protection deployed against disruption
- **meta**: C+ — Lost — played actively but could not overcome matchup
- **overall**: C+ — Average across 6 domains — lost in 9 turns

### oops_vs_dimir_s7 — p2 won on turn None
- **mulligan**: B — Kept 7; lost — opening hand was possibly too greedy
- **mana**: C — Lost in 12 turns — possible mana sequencing issues
- **combat**: B — Combo deck — combat decisions minimal
- **combo**: C — Failed to assemble combo — could not find pieces
- **interaction**: C — No protection deployed against disruption
- **meta**: C+ — Lost — played actively but could not overcome matchup
- **overall**: C+ — Average across 6 domains — lost in 12 turns

### oops_vs_dimir_s99 — p2 won on turn None
- **mulligan**: B — Kept 7; lost — opening hand was possibly too greedy
- **mana**: C — Lost in 9 turns — possible mana sequencing issues
- **combat**: B — Combo deck — combat decisions minimal
- **combo**: C — Failed to assemble combo — could not find pieces
- **interaction**: C — No protection deployed against disruption
- **meta**: C+ — Lost — played actively but could not overcome matchup
- **overall**: C+ — Average across 6 domains — lost in 9 turns

### painter_vs_eldrazi_s42 — p2 won on turn None
- **mulligan**: B — Kept 7; lost — opening hand was possibly too greedy
- **mana**: C+ — Suboptimal mana utilization over 6 turns
- **combat**: C — Limited combat engagement
- **combo**: B — Non-combo deck — domain not primary axis
- **interaction**: C+ — Interaction fell short of needs
- **meta**: C+ — Lost — played actively but could not overcome matchup
- **overall**: C+ — Average across 6 domains — lost in 6 turns

### painter_vs_eldrazi_s7 — p2 won on turn None
- **mulligan**: B — Kept 7; lost — opening hand was possibly too greedy
- **mana**: C+ — Suboptimal mana utilization over 6 turns
- **combat**: C — Limited combat engagement
- **combo**: B — Non-combo deck — domain not primary axis
- **interaction**: C+ — Interaction fell short of needs
- **meta**: C+ — Lost — played actively but could not overcome matchup
- **overall**: C+ — Average across 6 domains — lost in 6 turns

### painter_vs_eldrazi_s99 — p1 won on turn 4
- **mulligan**: B+ — Kept 7; won — opening hand was adequate
- **mana**: B+ — Resource deployment supported a T4 win
- **combat**: B — Won through non-combat means
- **combo**: B — Non-combo deck — domain not primary axis
- **interaction**: B — Adequate interaction for game plan
- **meta**: B+ — Efficiently closed the matchup
- **overall**: B+ — Average across 6 domains — won in 4 turns

### reanimator_vs_burn_s2026 — p2 won on turn None
- **mulligan**: B — Kept 7; lost — opening hand was possibly too greedy
- **mana**: C+ — Lost in 3 turns — possible mana sequencing issues
- **combat**: B — Combo deck — combat decisions minimal
- **combo**: D — Failed to assemble combo — disrupted early
- **interaction**: C — No protection deployed against disruption
- **meta**: C — Lost a matchup that should be favored (reanimator vs burn) — possible role confusion
- **overall**: C+ — Average across 6 domains — lost in 3 turns

### reanimator_vs_burn_s42 — p1 won on turn 4
- **mulligan**: B+ — Kept 7; won — opening hand was adequate
- **mana**: A — Fast kill (T4) implies efficient mana sequencing
- **combat**: B — Combo deck — combat decisions minimal
- **combo**: A+ — Clean combo kill on T4 — optimal assembly
- **interaction**: B — Combo resolved without needing protection
- **meta**: B+ — Efficiently closed a favored matchup
- **overall**: B+ — Average across 6 domains — won in 4 turns

### reanimator_vs_burn_s7 — p2 won on turn None
- **mulligan**: B — Kept 7; lost — opening hand was possibly too greedy
- **mana**: C+ — Lost in 3 turns — possible mana sequencing issues
- **combat**: B — Combo deck — combat decisions minimal
- **combo**: D — Failed to assemble combo — disrupted early
- **interaction**: C — No protection deployed against disruption
- **meta**: C — Lost a matchup that should be favored (reanimator vs burn) — possible role confusion
- **overall**: C+ — Average across 6 domains — lost in 3 turns

### reanimator_vs_burn_s99 — p2 won on turn None
- **mulligan**: B — Kept 7; lost — opening hand was possibly too greedy
- **mana**: C+ — Lost in 3 turns — possible mana sequencing issues
- **combat**: B — Combo deck — combat decisions minimal
- **combo**: D — Failed to assemble combo — disrupted early
- **interaction**: C — No protection deployed against disruption
- **meta**: C — Lost a matchup that should be favored (reanimator vs burn) — possible role confusion
- **overall**: C+ — Average across 6 domains — lost in 3 turns

### sneak_a_vs_bug_s2026 — p2 won on turn None
- **mulligan**: B — Kept 7; lost — opening hand was possibly too greedy
- **mana**: C+ — Lost in 4 turns — possible mana sequencing issues
- **combat**: B — Combo deck — combat decisions minimal
- **combo**: D — Failed to assemble combo — disrupted early
- **interaction**: C — No protection deployed against disruption
- **meta**: C — Lost — limited decision points suggest structural disadvantage
- **overall**: C+ — Average across 6 domains — lost in 4 turns

### sneak_a_vs_bug_s42 — p2 won on turn None
- **mulligan**: B — Kept 7; lost — opening hand was possibly too greedy
- **mana**: C — Lost in 8 turns — possible mana sequencing issues
- **combat**: B — Combo deck — combat decisions minimal
- **combo**: C — Failed to assemble combo — could not find pieces
- **interaction**: C — No protection deployed against disruption
- **meta**: C+ — Lost — played actively but could not overcome matchup
- **overall**: C+ — Average across 6 domains — lost in 8 turns

### sneak_a_vs_bug_s7 — p2 won on turn None
- **mulligan**: B — Kept 7; lost — opening hand was possibly too greedy
- **mana**: C — Lost in 7 turns — possible mana sequencing issues
- **combat**: B — Combo deck — combat decisions minimal
- **combo**: C — Failed to assemble combo — could not find pieces
- **interaction**: C — No protection deployed against disruption
- **meta**: C+ — Lost — played actively but could not overcome matchup
- **overall**: C+ — Average across 6 domains — lost in 7 turns

### sneak_a_vs_bug_s99 — p2 won on turn None
- **mulligan**: B — Kept 7; lost — opening hand was possibly too greedy
- **mana**: C — Lost in 7 turns — possible mana sequencing issues
- **combat**: B — Combo deck — combat decisions minimal
- **combo**: C — Failed to assemble combo — could not find pieces
- **interaction**: C — No protection deployed against disruption
- **meta**: C+ — Lost — played actively but could not overcome matchup
- **overall**: C+ — Average across 6 domains — lost in 7 turns

### storm_vs_dnt_s101 — p1 won on turn 4
- **mulligan**: B — Mulled to 6; still won
- **mana**: A — Fast kill (T4) implies efficient mana sequencing
- **combat**: B — Combo deck — combat decisions minimal
- **combo**: A+ — Clean combo kill on T4 — optimal assembly
- **interaction**: B — Combo resolved without needing protection
- **meta**: A — Won an unfavored matchup (storm vs dnt) — strong matchup awareness
- **overall**: B+ — Average across 6 domains — won in 4 turns

### storm_vs_dnt_s2026 — p2 won on turn None
- **mulligan**: B — Kept 7; lost — opening hand was possibly too greedy
- **mana**: C+ — Lost in 6 turns — possible mana sequencing issues
- **combat**: B — Combo deck — combat decisions minimal
- **combo**: C — Failed to assemble combo — could not find pieces
- **interaction**: C — No protection deployed against disruption
- **meta**: C+ — Lost — played actively but could not overcome matchup
- **overall**: C+ — Average across 6 domains — lost in 6 turns

### storm_vs_dnt_s42 — p2 won on turn None
- **mulligan**: B — Kept 7; lost — opening hand was possibly too greedy
- **mana**: C — Lost in 7 turns — possible mana sequencing issues
- **combat**: B — Combo deck — combat decisions minimal
- **combo**: C — Failed to assemble combo — could not find pieces
- **interaction**: C — No protection deployed against disruption
- **meta**: C+ — Lost — played actively but could not overcome matchup
- **overall**: C+ — Average across 6 domains — lost in 7 turns

### storm_vs_dnt_s7 — p1 won on turn 5
- **mulligan**: B+ — Kept 7; won — opening hand was adequate
- **mana**: B+ — Won but took 5 turns — mana was adequate
- **combat**: B — Combo deck — combat decisions minimal
- **combo**: B+ — Combo executed on T5 — efficient
- **interaction**: B — Combo resolved without needing protection
- **meta**: A — Won an unfavored matchup (storm vs dnt) — strong matchup awareness
- **overall**: B+ — Average across 6 domains — won in 5 turns

### storm_vs_dnt_s99 — p1 won on turn 3
- **mulligan**: B+ — Kept 7; won — opening hand was adequate
- **mana**: A — Fast kill (T3) implies efficient mana sequencing
- **combat**: B — Combo deck — combat decisions minimal
- **combo**: A+ — Clean combo kill on T3 — optimal assembly
- **interaction**: B — Combo resolved without needing protection
- **meta**: A — Won an unfavored matchup (storm vs dnt) — strong matchup awareness
- **overall**: B+ — Average across 6 domains — won in 3 turns

### ur_delver_vs_dimir_s2026 — p1 won on turn 8
- **mulligan**: B+ — Kept 7; won — opening hand was adequate
- **mana**: B+ — Resource deployment supported a T8 win
- **combat**: B — Won through non-combat means
- **combo**: B — Non-combo deck — domain not primary axis
- **interaction**: B+ — Interaction-backed win with measured disruption
- **meta**: B — Eventually closed the matchup
- **overall**: B+ — Average across 6 domains — won in 8 turns

### ur_delver_vs_dimir_s42 — p1 won on turn 6
- **mulligan**: B+ — Kept 7; won — opening hand was adequate
- **mana**: B+ — Resource deployment supported a T6 win
- **combat**: B — Won through non-combat means
- **combo**: B — Non-combo deck — domain not primary axis
- **interaction**: B+ — Interaction-backed win with measured disruption
- **meta**: B+ — Efficiently closed the matchup
- **overall**: B+ — Average across 6 domains — won in 6 turns

### ur_delver_vs_dimir_s7 — p2 won on turn None
- **mulligan**: C+ — Mulled to 6; card disadvantage contributed to loss
- **mana**: B — Adequate mana utilization over 10 turns
- **combat**: C — Limited combat engagement
- **combo**: B — Non-combo deck — domain not primary axis
- **interaction**: C — Disruption was insufficient — key threats went unanswered
- **meta**: C+ — Lost — played actively but could not overcome matchup
- **overall**: C+ — Average across 6 domains — lost in 10 turns

### ur_delver_vs_dimir_s99 — p1 won on turn 8
- **mulligan**: B+ — Kept 7; won — opening hand was adequate
- **mana**: B+ — Resource deployment supported a T8 win
- **combat**: B — Won through non-combat means
- **combo**: B — Non-combo deck — domain not primary axis
- **interaction**: B+ — Interaction-backed win with measured disruption
- **meta**: B — Eventually closed the matchup
- **overall**: B+ — Average across 6 domains — won in 8 turns

## Flagged weaknesses (repeat C/D/F grades)

- **depths.combo** (3/41 traces C or below): depths_vs_burn_s42 (D), depths_vs_burn_s7 (D), depths_vs_burn_s99 (D)
- **depths.interaction** (3/41 traces C or below): depths_vs_burn_s42 (C), depths_vs_burn_s7 (C), depths_vs_burn_s99 (C)
- **depths.mana** (3/41 traces C or below): depths_vs_burn_s42 (C+), depths_vs_burn_s7 (C+), depths_vs_burn_s99 (C+)
- **depths.meta** (3/41 traces C or below): depths_vs_burn_s42 (C), depths_vs_burn_s7 (C), depths_vs_burn_s99 (C)
- **doomsday.combo** (4/41 traces C or below): doomsday_vs_ur_delver_s2026 (D), doomsday_vs_ur_delver_s42 (D), doomsday_vs_ur_delver_s7 (D), doomsday_vs_ur_delver_s99 (D)
- **doomsday.interaction** (4/41 traces C or below): doomsday_vs_ur_delver_s2026 (C), doomsday_vs_ur_delver_s42 (C), doomsday_vs_ur_delver_s7 (C), doomsday_vs_ur_delver_s99 (C)
- **doomsday.mana** (4/41 traces C or below): doomsday_vs_ur_delver_s2026 (C+), doomsday_vs_ur_delver_s42 (C+), doomsday_vs_ur_delver_s7 (C+), doomsday_vs_ur_delver_s99 (C+)
- **doomsday.meta** (4/41 traces C or below): doomsday_vs_ur_delver_s2026 (C), doomsday_vs_ur_delver_s42 (C+), doomsday_vs_ur_delver_s7 (C), doomsday_vs_ur_delver_s99 (C)
- **goblins.combat** (2/41 traces C or below): goblins_vs_uwx_s42 (C), goblins_vs_uwx_s7 (C)
- **goblins.interaction** (2/41 traces C or below): goblins_vs_uwx_s42 (C+), goblins_vs_uwx_s7 (C+)
- **goblins.meta** (2/41 traces C or below): goblins_vs_uwx_s42 (C), goblins_vs_uwx_s7 (C)
- **oops.combo** (3/41 traces C or below): oops_vs_dimir_s42 (C), oops_vs_dimir_s7 (C), oops_vs_dimir_s99 (C)
- **oops.interaction** (3/41 traces C or below): oops_vs_dimir_s42 (C), oops_vs_dimir_s7 (C), oops_vs_dimir_s99 (C)
- **oops.mana** (3/41 traces C or below): oops_vs_dimir_s42 (C), oops_vs_dimir_s7 (C), oops_vs_dimir_s99 (C)
- **oops.meta** (3/41 traces C or below): oops_vs_dimir_s42 (C+), oops_vs_dimir_s7 (C+), oops_vs_dimir_s99 (C+)
- **painter.combat** (2/41 traces C or below): painter_vs_eldrazi_s42 (C), painter_vs_eldrazi_s7 (C)
- **painter.interaction** (2/41 traces C or below): painter_vs_eldrazi_s42 (C+), painter_vs_eldrazi_s7 (C+)
- **painter.mana** (2/41 traces C or below): painter_vs_eldrazi_s42 (C+), painter_vs_eldrazi_s7 (C+)
- **painter.meta** (2/41 traces C or below): painter_vs_eldrazi_s42 (C+), painter_vs_eldrazi_s7 (C+)
- **reanimator.combo** (3/41 traces C or below): reanimator_vs_burn_s2026 (D), reanimator_vs_burn_s7 (D), reanimator_vs_burn_s99 (D)
- **reanimator.interaction** (3/41 traces C or below): reanimator_vs_burn_s2026 (C), reanimator_vs_burn_s7 (C), reanimator_vs_burn_s99 (C)
- **reanimator.mana** (3/41 traces C or below): reanimator_vs_burn_s2026 (C+), reanimator_vs_burn_s7 (C+), reanimator_vs_burn_s99 (C+)
- **reanimator.meta** (3/41 traces C or below): reanimator_vs_burn_s2026 (C), reanimator_vs_burn_s7 (C), reanimator_vs_burn_s99 (C)
- **sneak_a.combo** (4/41 traces C or below): sneak_a_vs_bug_s2026 (D), sneak_a_vs_bug_s42 (C), sneak_a_vs_bug_s7 (C), sneak_a_vs_bug_s99 (C)
- **sneak_a.interaction** (4/41 traces C or below): sneak_a_vs_bug_s2026 (C), sneak_a_vs_bug_s42 (C), sneak_a_vs_bug_s7 (C), sneak_a_vs_bug_s99 (C)
- **sneak_a.mana** (4/41 traces C or below): sneak_a_vs_bug_s2026 (C+), sneak_a_vs_bug_s42 (C), sneak_a_vs_bug_s7 (C), sneak_a_vs_bug_s99 (C)
- **sneak_a.meta** (4/41 traces C or below): sneak_a_vs_bug_s2026 (C), sneak_a_vs_bug_s42 (C+), sneak_a_vs_bug_s7 (C+), sneak_a_vs_bug_s99 (C+)
- **storm.combo** (2/41 traces C or below): storm_vs_dnt_s2026 (C), storm_vs_dnt_s42 (C)
- **storm.interaction** (2/41 traces C or below): storm_vs_dnt_s2026 (C), storm_vs_dnt_s42 (C)
- **storm.mana** (2/41 traces C or below): storm_vs_dnt_s2026 (C+), storm_vs_dnt_s42 (C)
- **storm.meta** (2/41 traces C or below): storm_vs_dnt_s2026 (C+), storm_vs_dnt_s42 (C+)

## Threshold check (minimum: B-)

**FAIL** — domains below B-: mana (B), combat (B), combo (C+), interaction (C+), meta (B)
