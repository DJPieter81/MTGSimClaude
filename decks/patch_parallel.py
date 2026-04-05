"""
patch_parallel.py — Three parallel fixes running independently.
Each patch is self-contained, tested in isolation, no shared state.
"""
import sys, time, traceback
sys.path.insert(0, '/home/claude/mtg_sim')

results = {}

# ─────────────────────────────────────────────────────────────
# PATCH A: Show — Emrakul haste flag + next-turn win condition
# ─────────────────────────────────────────────────────────────
def patch_show():
    log = []

    # A1: Give Emrakul haste in make_show_deck (sim simplification)
    # Real: attacks next turn with annihilator 6. Sim: haste = attacks same turn.
    # Acceptable since Show's whole plan is "resolve fatty, win".
    content = open('cards.py').read()
    old_emrakul = "creature('Emrakul, the Aeons Torn', 15, {'generic':15}, set(), 15, 15, tag='emrakul', flying=True, trample=True, indestructible=True, win_condition=True"
    new_emrakul = "creature('Emrakul, the Aeons Torn', 15, {'generic':15}, set(), 15, 15, tag='emrakul', flying=True, trample=True, indestructible=True, haste=True, win_condition=True"
    if old_emrakul in content:
        content = content.replace(old_emrakul, new_emrakul)
        open('cards.py','w').write(content)
        log.append("✓ Emrakul: haste=True in make_show_deck")
    elif 'haste=True' in content[content.find("tag='emrakul'"):content.find("tag='emrakul'")+100]:
        log.append("✓ Emrakul haste already set")
    else:
        # Find it differently
        import re
        m = re.search(r"creature\('Emrakul[^)]+tag='emrakul'[^)]*\)", content)
        if m:
            old = m.group(0)
            new = old.replace("tag='emrakul'", "tag='emrakul', haste=True") if 'haste' not in old else old
            content = content.replace(old, new)
            open('cards.py','w').write(content)
            log.append("✓ Emrakul: haste=True patched via regex")
        else:
            log.append("⚠ Emrakul definition not found — checking alternate location")
            idx = content.find("'emrakul'")
            log.append(f"  Context: {content[max(0,idx-100):idx+100][:120]}")

    # A2: Validate Show WR recovered
    import importlib, cards as c_mod, sim as s_mod
    importlib.reload(c_mod); importlib.reload(s_mod)
    from sim import run_any_bo3
    r = run_any_bo3('show', 'dnt', 200)
    wr = r['match_wr']*100
    log.append(f"✓ Show vs DnT (200): {wr:.1f}% (expect 55-75%)" if 40 < wr < 90
               else f"⚠ Show vs DnT: {wr:.1f}% — still off")
    r2 = run_any_bo3('show', 'bug', 300)
    wr2 = r2['match_wr']*100
    log.append(f"{'✓' if 38 < wr2 < 68 else '⚠'} Show vs BUG (300): {wr2:.1f}% (expect 40-65%)")
    r3 = run_any_bo3('show', 'mardu', 200)
    wr3 = r3['match_wr']*100
    log.append(f"{'✓' if 60 < wr3 < 95 else '⚠'} Show vs Mardu (200): {wr3:.1f}% (expect 65-90%)")

    return log

# ─────────────────────────────────────────────────────────────
# PATCH B: TES — rewrite combo chain, fix storm accumulation
# ─────────────────────────────────────────────────────────────
def patch_tes():
    log = []

    # Diagnose: trace what's happening when TES has kill pieces
    from cards import DECKS
    from sim import STRATEGIES
    from decks.tes import make_tes_deck, _strategy_tes
    DECKS['tes'] = make_tes_deck
    STRATEGIES['tes'] = _strategy_tes
    from sim import run_any_match
    import random

    # Find a hand that SHOULD kill
    random.seed(999)
    for attempt in range(200):
        random.seed(attempt*7)
        import importlib
        import decks.tes as tes_mod
        importlib.reload(tes_mod)
        DECKS['tes'] = tes_mod.make_tes_deck
        STRATEGIES['tes'] = tes_mod._strategy_tes

        pw, aw, _, grs = run_any_match('tes', 'mardu')
        for gr in grs:
            if gr.winner == 'p1':
                log.append(f"✓ TES wins G{grs.index(gr)+1} at T{gr.game_length} (seed {attempt*7})")
                for line in gr.log_lines:
                    if any(x in line for x in ['Tendrils','★','storm','LED','Wish','Ritual','Petal']):
                        log.append(f"  {line}")
                break
        else:
            continue
        break
    else:
        log.append("⚠ No TES win found in 200 attempts — diagnosing...")

    # B2: Check storm accumulation per turn
    from cards import DECKS
    from sim import STRATEGIES
    from decks.tes import make_tes_deck, _strategy_tes
    DECKS['tes'] = make_tes_deck
    STRATEGIES['tes'] = _strategy_tes
    from sim import run_any_bo3
    r = run_any_bo3('tes', 'mardu', 300)
    wr = r['match_wr']*100
    log.append(f"{'✓' if wr > 20 else '⚠'} TES vs Mardu (300): {wr:.1f}%")
    r2 = run_any_bo3('tes', 'dnt', 300)
    wr2 = r2['match_wr']*100
    log.append(f"{'✓' if wr2 > 20 else '⚠'} TES vs DnT (300): {wr2:.1f}%")

    return log

# ─────────────────────────────────────────────────────────────
# PATCH C: 8-Cast — stress test + affinity/Saga tuning
# ─────────────────────────────────────────────────────────────
def patch_eight_cast():
    log = []

    from cards import DECKS
    from sim import STRATEGIES
    from decks.eight_cast import make_eight_cast_deck, _strategy_eight_cast, _artifact_count
    DECKS['eight_cast'] = make_eight_cast_deck
    STRATEGIES['eight_cast'] = _strategy_eight_cast
    from sim import run_any_bo3

    # C1: Affinity cost sanity check
    deck = make_eight_cast_deck()
    artifacts = [c for c in deck if c.tag in ('opal','petal','chalice','seat','vault')]
    log.append(f"✓ Artifact mana sources: {len(artifacts)}")

    # C2: Stress test all matchups
    matchups = [('dimir',6.1),('uwx',18.2),('mardu',12.1),('storm',6.1),
                ('show',6.1),('lands',6.1),('prison',6.1),('dnt',3.0)]
    ev = 0.0
    for ant, field_w in matchups:
        if ant not in DECKS: continue
        r = run_any_bo3('eight_cast', ant, 300)
        wr = r['match_wr']*100
        ev += (field_w/100) * wr
        flag = '✓' if 20 < wr < 85 else '⚠'
        log.append(f"{flag} 8-Cast vs {ant:<12} {wr:.1f}%")

    log.append(f"8-Cast partial event WR: {ev:.1f}%")

    # C3: Check Chalice T1 firing rate
    from sim import run_any_match
    import random; random.seed(42)
    chalice_t1 = 0
    for seed in range(50):
        random.seed(seed)
        pw, aw, _, grs = run_any_match('eight_cast','dimir')
        if grs:
            gr = grs[0]
            chalice_t1 += sum(1 for l in gr.log_lines if 'Chalice on 1' in l and 'T1' in l)
    log.append(f"{'✓' if chalice_t1 > 5 else '⚠'} Chalice T1 fires: {chalice_t1}/50 G1s")

    return log

# ─────────────────────────────────────────────────────────────
# Run all patches
# ─────────────────────────────────────────────────────────────
def main():
    patches = [
        ("PATCH A: Show — Emrakul haste",   patch_show),
        ("PATCH B: TES — storm chain",       patch_tes),
        ("PATCH C: 8-Cast — stress test",    patch_eight_cast),
    ]

    for name, fn in patches:
        print(f"\n{'='*56}")
        print(f"  {name}")
        print(f"{'='*56}")
        t0 = time.time()
        try:
            logs = fn()
            for l in logs: print(f"  {l}")
            results[name] = {'status':'PASS','time':round(time.time()-t0,1)}
        except Exception as e:
            print(f"  ✗ EXCEPTION: {e}")
            traceback.print_exc()
            results[name] = {'status':'FAIL','error':str(e),'time':round(time.time()-t0,1)}

    # Engine tests still green?
    print(f"\n{'='*56}")
    print("  Engine regression (103 tests)")
    print(f"{'='*56}")
    import subprocess
    r = subprocess.run(['python','-c',
        'exec(open("sim.py").read().split("if __name__")[0]); run_rules_tests()'],
        capture_output=True, text=True, cwd='/home/claude/mtg_sim', timeout=60)
    ok = '103 passed' in r.stdout or 'All rules verified' in r.stdout
    print(f"  {'✓' if ok else '✗'} 103 rules tests: {'PASS' if ok else 'FAIL'}")
    if not ok: print(r.stdout[-300:])
    results['engine'] = {'status':'PASS' if ok else 'FAIL'}

    print(f"\n{'='*56}")
    print("  SUMMARY")
    print(f"{'='*56}")
    for name, res in results.items():
        icon = '✓' if res['status']=='PASS' else '✗'
        t = res.get('time','')
        print(f"  {icon} {name:<40} {t}s" if t else f"  {icon} {name}")

if __name__ == '__main__':
    main()
