# Cowork Briefs — Index

Session handoffs for MTGSimClaude after the PR #82/#83/#84/#87 merge cluster (April 2026).
Each brief is self-contained with starting commands, file-level scope, and validation checklist.

## Active briefs

| # | Brief | Sessions | Impact |
|---|-------|----------|--------|
| A | `cowork_brief_A_clock_bhi_decisional.md` | Burn/UR Delver go-face + Storm/Oops combo gates | ±3-5pp WR shifts in aggro matchups, better sim-vs-meta correspondence |
| B | `cowork_brief_B_karn_lockout.md` | Add Karn static ability enforcement | Prison/Painter +5-10pp; fast-mana decks vs them drop 3-8pp |
| C | `cowork_brief_C_response_function_unification.md` | Extract `_respond_on_active_turn` | Avg tempo-mirror asymmetry 7.8pp → ~5pp (follow-up to PR #84) |
| D | `cowork_brief_D_llm_judge_actual_pass.md` | Run `grade_traces.py` on 30-50 traces | Audit report flagging systematic strategy weaknesses |
| E | `cowork_brief_E_matrix_n500.md` | Re-run matrix at n=500 | σ ±3.9pp → ±2.5pp; canonical reference dataset |

## Archived briefs (already merged)

- `cowork_brief_bo3_matrix.md` — merged as PR #87
- `cowork_brief_llm_judge.md` — merged as PR #83
- `cowork_brief_turn_unification.md` — merged as PR #84

## Suggested execution order

1. **A + B + D in parallel** (3 cowork sessions)
   - A touches `_strategy_*` functions + config
   - B touches `opp_can_cast` + new state field
   - D is read-only on sim, needs `ANTHROPIC_API_KEY`
   - Minor engine.py conflict risk between A and B; both are small enough to resolve on merge

2. **Merge A + B + D** to main

3. **C** (solo cowork session)
   - Response function unification; depends on merged main having A's strategy changes
   - Self-contained — doesn't overlap with anything else

4. **Merge C** to main

5. **E** (solo cowork session, last)
   - Matrix re-run at n=500, captures all of A/B/C's WR impact in one dataset
   - Also regenerates guides + HTML
   - ~35 min compute

## Paste-able session starters

**Session A:**
```
Read docs/cowork_brief_A_clock_bhi_decisional.md on main. Create branch
claude/mtgsim-clock-bhi-decisional-<suffix> off main. Goal: wire
clock.board_clock() and bhi.HandBelief into actual decisions (not just
traces), eliminating the hardcoded opp.life<=12 / p_free_counter>0.4
magic numbers. Must obey CLAUDE.md §"Key Design Principles" #4.
```

**Session B:**
```
Read docs/cowork_brief_B_karn_lockout.md on main. Create branch
claude/mtgsim-karn-lockout-<suffix> off main. Goal: add gs.karn_active_by
state + opp_artifact_activation_blocked() enforcement at all activation
sites. Mirror the gs.chalice_x pattern. 7 new rules tests.
```

**Session C:**
```
Read docs/cowork_brief_C_response_function_unification.md on main.
Create branch claude/mtgsim-response-unification-<suffix> off main
(AFTER A/B have merged). Goal: extract _respond_on_active_turn() to
close the residual tempo-mirror asymmetry. Follow-up to PR #84.
```

**Session D:**
```
Read docs/cowork_brief_D_llm_judge_actual_pass.md on main. Create branch
claude/mtgsim-llm-audit-<suffix> off main. Goal: run grade_traces.py on
30-50 representative traces, produce results/llm_audit_report.md +
findings analysis. Needs ANTHROPIC_API_KEY env var.
```

**Session E:**
```
Read docs/cowork_brief_E_matrix_n500.md on main. Create branch
claude/mtgsim-matrix-n500-<suffix> off main (AFTER A/B/C have merged).
Goal: re-run full matrix at n=500 to tighten σ from ±3.9pp to ±2.5pp.
Commits become canonical reference dataset.
```
