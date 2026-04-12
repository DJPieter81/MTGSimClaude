# Cowork Brief: LLM Judge Execution (PLANNING_REFERENCE §9 #7)

## One-sentence task
Add `scripts/grade_traces.py` that posts each `llm_judge.py` prompt bundle to the Anthropic API, captures the 6-domain grades, and writes a markdown audit report.

## Why this matters
`llm_judge.py` already collects traces and builds LLM-ready prompts (scaffold committed in `98b8436`). But the actual grading loop doesn't exist — right now a human has to copy each `_prompt.txt` into Claude and capture the response by hand. Automating this completes PLANNING_REFERENCE §9 #7: "6-expert panel grading decisions across mulligan/mana/combat/combo/interaction/meta domains."

## What's already in place
- `llm_judge.py collect <d1> <d2> --seeds ...` → writes `results/traces/<d1>_vs_<d2>_s<seed>.json`
- `llm_judge.py bundle <json>` → writes `results/traces/<name>_prompt.txt` ready for LLM
- Rubric: 6 domains (mulligan, mana, combat, combo, interaction, meta); grade scale A+..F
- Sample traces committed: `results/traces/storm_vs_dnt_s42.json` + `s99.json` (+ prompt)

## Scope

### Part 1 — `scripts/grade_traces.py`

```python
# Usage:
#   export ANTHROPIC_API_KEY=sk-ant-...
#   python3 scripts/grade_traces.py results/traces/*.json
#   python3 scripts/grade_traces.py --report  # summarise existing graded files
```

Core loop:
1. For each `*.json` trace file, build the prompt via `llm_judge.bundle()`
2. Call `anthropic.messages.create(model="claude-opus-4-6", messages=[...])`
3. Parse the response — expect lines like `mulligan: B+ — ...`, `mana: A — ...`, etc.
4. Write `results/traces/<name>_graded.json` with `{grades: {mulligan:"B+", ...}, raw_response: "..."}`

Parser should be tolerant: regex for `^(\w+):\s*([A-F][+-]?)\s*[—-]\s*(.+)$`.

### Part 2 — Report generator

`grade_traces.py --report` reads all `*_graded.json` and produces `results/llm_audit_report.md`:

```markdown
# MTGSimClaude LLM Audit — <date>

## Domain averages across N=<N> traces

| Domain | Avg Grade | Worst Trace | Best Trace |
|--------|-----------|-------------|------------|
| mulligan | B+ | oops_vs_burn_s42 (D) | storm_vs_dimir_s99 (A+) |
| ...

## Per-trace summary

### storm_vs_dnt_s42 — p2 won on turn 7
- mulligan: B+ — Kept a keepable 7 with rituals + kill spell
- mana: C — Failed to deploy LED when it would have enabled T3 kill
- ...

## Flagged weaknesses (repeat C/D grades)

- **storm.mana** (3/5 traces C or below): Storm consistently fails
  to sequence rituals optimally under Thalia tax.
- ...
```

### Part 3 — CI-style threshold check

Exit 1 if any domain average drops below a configurable threshold (default B-).
Lets us fail a pipeline when strategies regress on LLM-judged quality.

## Dependencies
- Adds `anthropic` to requirements (or just documents env var + direct import)
- Does NOT commit the API key — read from env only

## Branch / PR shape
- Branch: `claude/mtgsim-llm-judge-exec-<suffix>`
- Commits:
  1. `scripts/grade_traces.py` + `scripts/__init__.py` (make `scripts/` a module)
  2. Unit test: parser handles malformed responses gracefully
  3. Small sample run: grade the 2 existing storm_vs_dnt traces, commit the `_graded.json` artifacts (without the API response if it's too chatty)
  4. `results/llm_audit_report.md` sample
  5. Optional: GitHub Actions workflow calling `grade_traces.py --report --threshold B-`

## Files the cowork session will touch
- NEW: `scripts/grade_traces.py`, `scripts/__init__.py`
- NEW JSON artifacts: `results/traces/*_graded.json`
- NEW REPORT: `results/llm_audit_report.md`
- MAYBE MODIFY: `llm_judge.py` (expose `build_prompt(trace_dict) -> str` helper so the grader doesn't duplicate templating)
- MAYBE NEW: `.github/workflows/llm_audit.yml`

## Validation checklist
- `python3 scripts/grade_traces.py results/traces/storm_vs_dnt_s42.json` produces a valid `_graded.json`
- Report shows 6 domains with grade + justification for the storm-vs-dnt traces
- Parser survives empty/malformed LLM output (returns `UNGRADED`)
- No API key in the repo

## Starting point
```bash
git fetch origin && git checkout -b claude/mtgsim-llm-judge-exec-<suffix> origin/main
cat llm_judge.py  # read the existing scaffold + prompt template
cat results/traces/storm_vs_dnt_s42_prompt.txt  # see what the LLM will receive
# First: write the Anthropic call as a standalone script; grade the sample;
# only after that works, wrap it in scripts/grade_traces.py with CLI.
```

## Rubric reference (from llm_judge.py)

| Domain | What to grade |
|--------|---------------|
| mulligan | Keep/mull defensibility given matchup |
| mana | Resource efficiency, tap sequencing, spending |
| combat | Attack/block decisions, trading value |
| combo | Assembly-and-execution quality |
| interaction | Counter/removal timing and targeting |
| meta | Matchup-aware adjustments (did the AI play to the matchup?) |

Grade scale: **A+ / A / B+ / B / C+ / C / D / F**
