# Structural vs heuristic grader comparison

**N=41 paired traces** (heuristic-v1 vs structural-v1)

## Per-domain agreement

| Domain | Agreement | Heuristic example | Structural example |
|--------|-----------|-------------------|--------------------|
| mulligan | 41/41 = 100% | (all match) | (all match) |
| mana | 41/41 = 100% | (all match) | (all match) |
| combat | 41/41 = 100% | (all match) | (all match) |
| combo | 27/41 = 66% | depths_vs_burn_s42: B+ | depths_vs_burn_s42: C |
| interaction | 38/41 = 93% | bug_vs_storm_s2026: A | bug_vs_storm_s2026: B+ |
| meta | 41/41 = 100% | (all match) | (all match) |

## Per-trace grades (heuristic | structural)

| trace | mulligan (H/S) | mana (H/S) | combat (H/S) | combo (H/S) | interaction (H/S) | meta (H/S) |
|---|---|---|---|---|---|---|
| bug_vs_storm_s2026 | B+/B+ | B/B | B/B | B/B | A/B+ * | B/B |
| bug_vs_storm_s42 | C+/C+ | C+/C+ | C/C | B/B | C+/C+ | C+/C+ |
| bug_vs_storm_s7 | B+/B+ | B/B | B/B | B/B | A/B+ * | B/B |
| bug_vs_storm_s99 | B+/B+ | B+/B+ | B/B | B/B | A/B+ * | B+/B+ |
| depths_vs_burn_s42 | B+/B+ | B+/B+ | B/B | B+/C * | B/B | B+/B+ |
| depths_vs_burn_s7 | B/B | C+/C+ | B/B | C/C | C/C | C/C |
| depths_vs_burn_s99 | D/D | C+/C+ | B/B | D/C * | C/C | C/C |
| doomsday_vs_ur_delver_s2026 | B/B | C+/C+ | B/B | D/D | C/C | C/C |
| doomsday_vs_ur_delver_s42 | B/B | C+/C+ | B/B | C/C+ * | C/C | C+/C+ |
| doomsday_vs_ur_delver_s7 | B/B | C+/C+ | B/B | D/D | C/C | C+/C+ |
| doomsday_vs_ur_delver_s99 | B/B | C+/C+ | B/B | D/D | C/C | C+/C+ |
| elves_vs_dnt_s2026 | B/B | C/C | B/B | C/C | C/C | C+/C+ |
| elves_vs_dnt_s42 | B+/B+ | B+/B+ | B/B | B+/C * | B/B | A/A |
| elves_vs_dnt_s7 | B/B | C/C | B/B | C/C | C/C | C+/C+ |
| elves_vs_dnt_s99 | B+/B+ | A/A | B/B | A+/C * | B/B | A/A |
| goblins_vs_uwx_s42 | B/B | B/B | C/C | B/B | C+/C+ | C/C |
| goblins_vs_uwx_s7 | B/B | B/B | C/C | B/B | C+/C+ | C/C |
| goblins_vs_uwx_s99 | B/B | B/B | C/C | B/B | C+/C+ | C/C |
| oops_vs_dimir_s42 | C+/C+ | C/C | B/B | C/C+ * | C/C | C+/C+ |
| oops_vs_dimir_s7 | C+/C+ | C/C | B/B | C/C+ * | C/C | C+/C+ |
| oops_vs_dimir_s99 | B+/B+ | B+/B+ | B/B | B+/A * | B/B | A/A |
| painter_vs_eldrazi_s42 | B/B | C+/C+ | C/C | B/B | C+/C+ | C/C |
| painter_vs_eldrazi_s7 | B+/B+ | B+/B+ | B/B | B/B | B/B | B/B |
| painter_vs_eldrazi_s99 | D/D | C+/C+ | C/C | B/B | C+/C+ | C/C |
| reanimator_vs_burn_s2026 | B/B | C+/C+ | B/B | D/D | C/C | C/C |
| reanimator_vs_burn_s42 | B+/B+ | A/A | B/B | A+/A+ | B/B | B+/B+ |
| reanimator_vs_burn_s7 | B+/B+ | B+/B+ | B/B | B+/A * | B/B | B+/B+ |
| reanimator_vs_burn_s99 | B/B | C+/C+ | B/B | D/C * | C/C | C/C |
| sneak_a_vs_bug_s2026 | B/B | C+/C+ | B/B | D/C * | C/C | C/C |
| sneak_a_vs_bug_s42 | B+/B+ | B+/B+ | B/B | B/C * | B/B | A/A |
| sneak_a_vs_bug_s7 | B/B | C/C | B/B | C/C | C/C | C+/C+ |
| sneak_a_vs_bug_s99 | B+/B+ | B+/B+ | B/B | B+/C * | B/B | A/A |
| storm_vs_dnt_s101 | B/B | A/A | B/B | A+/A+ | B/B | A/A |
| storm_vs_dnt_s2026 | B+/B+ | B+/B+ | B/B | B+/A * | B/B | A/A |
| storm_vs_dnt_s42 | B/B | C/C | B/B | C/C | C/C | C+/C+ |
| storm_vs_dnt_s7 | B/B | A/A | B/B | A+/A+ | B/B | A/A |
| storm_vs_dnt_s99 | B/B | C/C | B/B | C/C | C/C | C+/C+ |
| ur_delver_vs_dimir_s2026 | D/D | C+/C+ | C/C | B/B | C/C | C+/C+ |
| ur_delver_vs_dimir_s42 | B+/B+ | B/B | B/B | B/B | B+/B+ | B/B |
| ur_delver_vs_dimir_s7 | B/B | B+/B+ | B/B | B/B | B+/B+ | B/B |
| ur_delver_vs_dimir_s99 | B+/B+ | B/B | B/B | B/B | B+/B+ | B/B |

## First disagreement per domain

### combo: depths_vs_burn_s42
- heuristic = **B+**, structural = **C**
- structural rationale: No combo Execute decision logged — deck did not fire its plan

### interaction: bug_vs_storm_s2026
- heuristic = **A**, structural = **B+**
- structural rationale: 0 hold + 0 defer decisions; measured disruption backed the win

