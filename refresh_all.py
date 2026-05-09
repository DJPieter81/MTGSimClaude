#!/usr/bin/env python3
"""
refresh_all.py — Full pipeline: matrix inputs → matrix HTML / deck guides → verify.

Pipeline DAG:
    Stage 1: build_meta_inputs.py
                 │
        ┌────────┴────────┐
    Stage 2:  (concurrent — both read meta_fresh.json/deck_agg.json)
       build_matrix_html.py    gen_guides.py
        └────────┬────────┘
    Stage 3: verify.py all

Stage 2's two scripts are independent (both consume the JSON written
by Stage 1) so we run them in parallel via
`concurrent.futures.ProcessPoolExecutor(max_workers=2)`. Their stdout
is captured and printed serially after both finish so the logs do not
interleave.

Usage:
    python3 refresh_all.py              # rebuild from latest matrix JSON
    python3 refresh_all.py --resim 200  # re-run matrix at n=200 first (~6 min)

Worker count for nested parallel runs (gen_guides.py, run_meta.py)
honours the MTGSIM_WORKERS env var; see parallel.py.
"""
import subprocess, sys, time, argparse
from concurrent.futures import ProcessPoolExecutor


def run(cmd, label):
    """Run a step inheriting our stdout (live output). Returns (ok, elapsed)."""
    print(f"\n{'='*60}")
    print(f"  {label}")
    print(f"  $ python3 {cmd}")
    print(f"{'='*60}")
    t0 = time.time()
    result = subprocess.run(
        [sys.executable] + cmd.split(),
        capture_output=False,
    )
    elapsed = time.time() - t0
    status = "✓" if result.returncode == 0 else "✗"
    print(f"\n  {status} {label} ({elapsed:.1f}s)")
    return result.returncode == 0, elapsed


def _run_captured(cmd_and_label):
    """Worker for stage-2 concurrent runs.

    Captures stdout/stderr to a string buffer so concurrent steps don't
    interleave on the parent's terminal. Returns
    (cmd, label, ok, elapsed, output).
    """
    cmd, label = cmd_and_label
    t0 = time.time()
    proc = subprocess.run(
        [sys.executable] + cmd.split(),
        capture_output=True,
        text=True,
    )
    elapsed = time.time() - t0
    output = proc.stdout + (proc.stderr if proc.stderr else "")
    return (cmd, label, proc.returncode == 0, elapsed, output)


def run_stage2_concurrent(steps):
    """Run stage-2 steps concurrently via ProcessPoolExecutor.

    `steps` is a list of (cmd, label) tuples. Both run in parallel; after
    BOTH finish we print their captured output back-to-back in the order
    they were passed in (so logs don't interleave). Returns list of
    (ok, elapsed) tuples in the same order as `steps`.
    """
    print(f"\n{'='*60}")
    print(f"  Stage 2 (concurrent): {' + '.join(label for _, label in steps)}")
    for cmd, label in steps:
        print(f"  $ python3 {cmd}    # {label}")
    print(f"{'='*60}")
    t0 = time.time()

    results_by_cmd = {}
    with ProcessPoolExecutor(max_workers=len(steps)) as ex:
        for result in ex.map(_run_captured, steps):
            cmd, label, ok, elapsed, output = result
            results_by_cmd[cmd] = (label, ok, elapsed, output)

    stage_elapsed = time.time() - t0

    # Print captured output in the original step order, one block per step.
    out = []
    for cmd, label in steps:
        rec_label, ok, elapsed, output = results_by_cmd[cmd]
        status = "✓" if ok else "✗"
        print(f"\n--- output: {label} ({status} {elapsed:.1f}s) ---")
        if output:
            print(output, end='' if output.endswith('\n') else '\n')
        print(f"--- end: {label} ---")
        out.append((ok, elapsed))

    print(f"\n  Stage 2 total walltime: {stage_elapsed:.1f}s "
          f"(max of {', '.join(f'{e:.1f}s' for _, e in out)})")
    return out


def main():
    parser = argparse.ArgumentParser(description="Full refresh pipeline")
    parser.add_argument("--resim", type=int, metavar="N",
                        help="Re-run matrix first at N games/pair")
    parser.add_argument("--seed", type=int, default=2026,
                        help="Random seed for matrix run (default: 2026)")
    parser.add_argument("--decks", type=int, default=36,
                        help="Deck count for matrix re-run (default: 36 — full)")
    args = parser.parse_args()

    t_start = time.time()
    all_ok = True

    # Optional: re-run the matrix
    if args.resim:
        ok, _ = run(
            f"run_meta.py --matrix --decks {args.decks} -n {args.resim} -s {args.seed}",
            f"Re-run matrix ({args.decks} decks, n={args.resim}, seed={args.seed})",
        )
        if not ok:
            print("\n✗ Matrix run failed — aborting pipeline")
            sys.exit(1)

    # Stage 1: build inputs (sequential, downstream depends on its outputs)
    ok, _ = run("build_meta_inputs.py",
                "Derive meta_fresh.json + deck_agg.json from matrix")
    if not ok:
        print("\n✗ build_meta_inputs.py failed — continuing anyway")
        all_ok = False

    # Stage 2: matrix HTML + gen guides concurrently. Both read the JSON
    # written by Stage 1 and produce independent outputs.
    stage2 = [
        ("build_matrix_html.py", "Rebuild matrix HTML (template swap, C/I data)"),
        ("gen_guides.py",        "Regenerate all deck guides (500 games/deck)"),
    ]
    stage2_results = run_stage2_concurrent(stage2)
    for (cmd, label), (ok, _) in zip(stage2, stage2_results):
        if not ok:
            print(f"\n✗ {cmd} failed — continuing anyway")
            all_ok = False

    # Stage 3: verify (depends on stage 2 outputs)
    ok, _ = run("verify.py all", "Post-action quality checks")
    if not ok:
        print("\n✗ verify.py all failed — continuing anyway")
        all_ok = False

    elapsed = time.time() - t_start
    print(f"\n{'='*60}")
    if all_ok:
        print(f"  ✓ Full pipeline complete ({elapsed:.0f}s)")
    else:
        print(f"  ⚠ Pipeline complete with errors ({elapsed:.0f}s)")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
