# Structural vs heuristic grader comparison

**N=41 paired traces** (heuristic-v1 vs structural-v1)

## Per-domain agreement

| Domain | Agreement | Heuristic example | Structural example |
|--------|-----------|-------------------|--------------------|
| mulligan | 41/41 = 100% | (all match) | (all match) |
| mana | 40/41 = 98% | ur_delver_vs_dimir_s2026: C+ | ur_delver_vs_dimir_s2026: B |
| combat | 40/41 = 98% | goblins_vs_uwx_s99: C | goblins_vs_uwx_s99: B- |
| combo | 28/41 = 68% | depths_vs_burn_s42: B+ | depths_vs_burn_s42: A+ |
| interaction | 36/41 = 88% | bug_vs_storm_s42: C+ | bug_vs_storm_s42: C |
| meta | 33/41 = 80% | bug_vs_storm_s42: C+ | bug_vs_storm_s42: C |

## Per-trace grades (heuristic | structural)

| trace | mulligan (H/S) | mana (H/S) | combat (H/S) | combo (H/S) | interaction (H/S) | meta (H/S) |
|---|---|---|---|---|---|---|
| bug_vs_storm_s2026 | B+/B+ | B/B | B/B | B/B | A/A | B/B |
| bug_vs_storm_s42 | C+/C+ | C+/C+ | C/C | B/B | C+/C * | C+/C * |
| bug_vs_storm_s7 | B+/B+ | B/B | B/B | B/B | A/A | B/B |
| bug_vs_storm_s99 | B+/B+ | B+/B+ | B/B | B/B | A/A | B+/B+ |
| depths_vs_burn_s42 | B+/B+ | B+/B+ | B/B | B+/A+ * | B/B | B+/B+ |
| depths_vs_burn_s7 | B/B | C+/C+ | B/B | C/C | C/C | C/C |
| depths_vs_burn_s99 | D/D | C+/C+ | B/B | D/C * | C/C | C/C |
| doomsday_vs_ur_delver_s2026 | B/B | C+/C+ | B/B | D/D | C/C | C+/C * |
| doomsday_vs_ur_delver_s42 | B/B | C+/C+ | B/B | C/C+ * | C/C | C+/C+ |
| doomsday_vs_ur_delver_s7 | B/B | C+/C+ | B/B | D/D | C/C | C+/C+ |
| doomsday_vs_ur_delver_s99 | B/B | C+/C+ | B/B | D/D | C/C | C+/C+ |
| elves_vs_dnt_s2026 | B/B | C/C | B/B | C/C | C/C | C+/C+ |
| elves_vs_dnt_s42 | B+/B+ | B+/B+ | B/B | B+/A+ * | B/B | A/A |
| elves_vs_dnt_s7 | B/B | C/C | B/B | C/C | C/C | C+/C+ |
| elves_vs_dnt_s99 | B+/B+ | A/A | B/B | A+/A+ | B/B | A/A |
| goblins_vs_uwx_s42 | B/B | B/B | C/C | B/B | C+/C+ | C/C+ * |
| goblins_vs_uwx_s7 | B/B | B/B | C/C | B/B | C+/C+ | C/C+ * |
| goblins_vs_uwx_s99 | B/B | B/B | C/B- * | B/B | C+/C+ | C/C+ * |
| oops_vs_dimir_s42 | C+/C+ | C/C | B/B | C/C | C+/C * | C+/C+ |
| oops_vs_dimir_s7 | C+/C+ | C/C | B/B | C/C | C+/C * | C+/C+ |
| oops_vs_dimir_s99 | B+/B+ | B+/B+ | B/B | B+/A+ * | B+/B * | A/A |
| painter_vs_eldrazi_s42 | B/B | C+/C+ | C/C | B/B | C+/C+ | C/C |
| painter_vs_eldrazi_s7 | B+/B+ | B+/B+ | B/B | B/B | B/B | B/B |
| painter_vs_eldrazi_s99 | D/D | C+/C+ | C/C | B/B | C+/C+ | C/C |
| reanimator_vs_burn_s2026 | B/B | C+/C+ | B/B | D/C+ * | C/C | C/C |
| reanimator_vs_burn_s42 | B+/B+ | A/A | B/B | A+/A+ | B/B | B+/B+ |
| reanimator_vs_burn_s7 | B+/B+ | B+/B+ | B/B | B+/A+ * | B/B | B+/B+ |
| reanimator_vs_burn_s99 | B/B | C+/C+ | B/B | D/C * | C/C | C/C |
| sneak_a_vs_bug_s2026 | B/B | C+/C+ | B/B | D/C * | C+/C+ | C+/C * |
| sneak_a_vs_bug_s42 | B+/B+ | B+/B+ | B/B | B/B+ * | B+/B+ | A/A |
| sneak_a_vs_bug_s7 | B/B | C/C | B/B | C/C | C+/C+ | C+/C * |
| sneak_a_vs_bug_s99 | B+/B+ | B+/B+ | B/B | B+/A+ * | B/B | A/A |
| storm_vs_dnt_s101 | B/B | A/A | B/B | A+/A+ | B/B | A/A |
| storm_vs_dnt_s2026 | B+/B+ | B+/B+ | B/B | B+/A+ * | B/B | A/A |
| storm_vs_dnt_s42 | B/B | C/C | B/B | C/C | C/C | C+/C+ |
| storm_vs_dnt_s7 | B/B | A/A | B/B | A+/A+ | B/B | A/A |
| storm_vs_dnt_s99 | B/B | C/C | B/B | C/C+ * | C/C | C+/C+ |
| ur_delver_vs_dimir_s2026 | D/D | C+/B * | C/C | B/B | C/C | C+/C * |
| ur_delver_vs_dimir_s42 | B+/B+ | B/B | B/B | B/B | A/A | B/B |
| ur_delver_vs_dimir_s7 | B/B | B+/B+ | B/B | B/B | B+/B+ | B/B |
| ur_delver_vs_dimir_s99 | B+/B+ | B/B | B/B | B/B | B+/A * | B/B |

## First disagreement per domain

### mana: ur_delver_vs_dimir_s2026
- heuristic = **C+**, structural = **B**
- structural rationale: Adequate mana utilization over 7 turns

### combat: goblins_vs_uwx_s99
- heuristic = **C**, structural = **B-**
- structural rationale: Aggro plan logged 2 combat decision(s) but lost — opponent stabilized

### combo: depths_vs_burn_s42
- heuristic = **B+**, structural = **A+**
- structural rationale: 1 Execute decision(s); combo resolved on T5

### interaction: bug_vs_storm_s42
- heuristic = **C+**, structural = **C**
- structural rationale: 0 counter + 0 discard + 0 remove + 0 hold + 0 defer decisions; not enough disruption surfaced

### meta: bug_vs_storm_s42
- heuristic = **C+**, structural = **C**
- structural rationale: Lost — limited decision points suggest structural disadvantage

