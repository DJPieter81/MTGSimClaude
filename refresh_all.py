#!/usr/bin/env python3
"""
refresh_all.py — Full pipeline: matrix inputs → matrix HTML → deck guides → verify.

Usage:
    python3 refresh_all.py              # rebuild from latest matrix JSON
    python3 refresh_all.py --resim 200  # re-run matrix at n=200 first (~6 min)
"""
import subprocess, sys, time, argparse

STEPS = [
    ("build_meta_inputs.py", "Derive meta_fresh.json + deck_agg.json from matrix"),
    ("build_matrix_html.py", "Rebuild matrix HTML (template swap, C/I data)"),
    ("gen_guides.py",        "Regenerate all deck guides (500 games/deck)"),
    ("verify.py all",        "Post-action quality checks"),
]

def run(cmd, label):
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
    return result.returncode == 0

def main():
    parser = argparse.ArgumentParser(description="Full refresh pipeline")
    parser.add_argument("--resim", type=int, metavar="N",
                        help="Re-run matrix first at N games/pair")
    parser.add_argument("--seed", type=int, default=2026,
                        help="Random seed for matrix run (default: 2026)")
    args = parser.parse_args()

    t_start = time.time()
    all_ok = True

    # Optional: re-run the matrix
    if args.resim:
        ok = run(f"run_meta.py --matrix -n {args.resim} -s {args.seed}", 
                 f"Re-run matrix (n={args.resim}, seed={args.seed})")
        if not ok:
            print("\n✗ Matrix run failed — aborting pipeline")
            sys.exit(1)

    # Run each downstream step
    for script, label in STEPS:
        ok = run(script, label)
        if not ok:
            print(f"\n✗ {script} failed — continuing anyway")
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
