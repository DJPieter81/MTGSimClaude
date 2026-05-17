"""
test_all.py — Parallel test runner for all three new deck modules.
Runs each deck's test suite independently. Reports results without
modifying any shared state until all tests pass.

Usage: python decks/test_all.py
"""
import sys, time, traceback
sys.path.insert(0, '/home/claude/mtg_sim')

RESULTS = {}

def run_module_tests(name, test_fn):
    print(f"\n{'='*50}")
    print(f"  {name}")
    print(f"{'='*50}")
    t0 = time.time()
    try:
        results = test_fn()
        for r in results:
            print(f"  {r}")
        RESULTS[name] = {'status': 'PASS', 'results': results, 
                         'time': round(time.time()-t0, 1)}
    except Exception as e:
        print(f"  ✗ EXCEPTION: {e}")
        traceback.print_exc()
        RESULTS[name] = {'status': 'FAIL', 'error': str(e),
                         'time': round(time.time()-t0, 1)}

def main():
    print("Parallel deck module test runner")
    print(f"Time: {time.strftime('%H:%M:%S')}")
    
    # Module 1: 8-Cast
    from decks.eight_cast import test_eight_cast
    run_module_tests("8-Cast", test_eight_cast)
    
    # Module 2: TES
    from decks.tes import test_tes
    run_module_tests("TES (The Epic Storm)", test_tes)
    
    # Module 3: Show fix
    from decks.show_fix import test_show_fix
    run_module_tests("Show and Tell SB Fix", test_show_fix)
    
    # Module 4: Existing engine still healthy
    print(f"\n{'='*50}")
    print("  Existing engine (pytest -m fast)")
    print(f"{'='*50}")
    t0 = time.time()
    import subprocess
    r = subprocess.run(['python3', '-m', 'pytest', '-m', 'fast', '-q'],
        capture_output=True, text=True, cwd='/home/claude/mtg_sim', timeout=120)
    ok = r.returncode == 0 and 'passed' in r.stdout
    print(f"  {'✓' if ok else '✗'} pytest fast suite: {'PASS' if ok else 'FAIL'}")
    RESULTS['existing_engine'] = {'status': 'PASS' if ok else 'FAIL', 
                                   'time': round(time.time()-t0,1)}

    # Summary
    print(f"\n{'='*50}")
    print("  SUMMARY")
    print(f"{'='*50}")
    all_pass = all(v['status'] == 'PASS' for v in RESULTS.values())
    for name, res in RESULTS.items():
        icon = '✓' if res['status'] == 'PASS' else '✗'
        print(f"  {icon} {name:<35} {res['time']}s")
    print()
    print(f"  {'ALL PASS' if all_pass else 'FAILURES PRESENT'}")
    return all_pass

if __name__ == '__main__':
    ok = main()
    sys.exit(0 if ok else 1)
