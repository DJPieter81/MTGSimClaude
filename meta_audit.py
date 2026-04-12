"""
meta_audit.py — Post-simulation audit for outlier detection and replay dashboards.

Usage:
    # After a matrix run:
    python3 meta_audit.py                          # audit latest saved matrix
    python3 meta_audit.py --matrix-file results/matrix_20260406.json
    python3 meta_audit.py --run -n 50 --decks 12   # run matrix + audit in one step

    # From Python:
    from meta_audit import audit_matrix, audit_strategy
    report = audit_matrix('results/matrix_20260406.json')
    audit_strategy('oops')  # deep-dive one deck
"""

import sys, os, json, random, html
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from collections import Counter
from sim import run_game
from cards import DECKS
from deck_registry import get_meta_share, get_all_keys, get_meta
from meta_results import load_matrix, RESULTS_DIR


# ── Expected matchup ranges (PLANNING_REFERENCE §10 P2 #12) ──────────────────
#
# Legacy-consensus win-rate ranges for known matchups. Populated from
# PLANNING_REFERENCE.md Section 4 "Known matchup spot-checks" plus a few
# obvious additions. Key is (deck1, deck2) where deck1 is P1. Value is
# (lo, hi) as fractions — e.g. 'burn vs storm' expected 55-75% for Burn.
#
# Used by check_expected_ranges() to flag when the sim drifts outside a
# known-good range. Add entries here as new reference points are
# established through playtesting / tournament data.
EXPECTED_RANGES = {
    # From PLANNING_REFERENCE §4 spot-checks:
    ('burn', 'storm'):        (0.55, 0.75),
    ('burn', 'dimir'):        (0.55, 0.80),
    ('infect', 'burn'):       (0.35, 0.55),
    ('reanimator', 'dimir'):  (0.35, 0.65),
    ('eldrazi', 'storm'):     (0.55, 0.80),
    ('storm', 'dnt'):         (0.55, 0.80),  # P0 #1 target
    ('oops', 'burn'):         (0.55, 0.80),  # P0 #2 target
    # Symmetric counterparts for quick lookup
    ('storm', 'burn'):        (0.25, 0.45),
    ('dimir', 'burn'):        (0.20, 0.45),
    ('burn', 'infect'):       (0.45, 0.65),
    ('dimir', 'reanimator'):  (0.35, 0.65),
    ('storm', 'eldrazi'):     (0.20, 0.45),
    ('dnt', 'storm'):         (0.20, 0.45),
    ('burn', 'oops'):         (0.20, 0.45),
}


def check_expected_ranges(matrix_data, ranges=None):
    """Verify known matchups are within their expected ranges.

    Args:
        matrix_data: loaded matrix dict (must have 'matchups' key)
        ranges: dict {(d1, d2): (lo, hi)} of expected ranges.
                Defaults to EXPECTED_RANGES.

    Returns:
        list of (d1, d2, actual_wr, (lo, hi)) for matchups outside the range.
    """
    if ranges is None:
        ranges = EXPECTED_RANGES
    mu = matrix_data['matchups']
    out = []
    for (d1, d2), (lo, hi) in ranges.items():
        key = f"{d1}_vs_{d2}"
        wr = mu.get(key)
        if wr is None:
            continue
        # Matrix values can be either 0-1 floats or 0-100 percents
        wr_frac = wr / 100 if wr > 1 else wr
        if not (lo <= wr_frac <= hi):
            out.append((d1, d2, wr_frac, (lo, hi)))
    return out


# ── 1. Outlier Detection ─────────────────────────────────────────────────────

def detect_outliers(matrix_data, threshold=0.15):
    """
    Flag decks whose meta-weighted WR diverges from expected tier position.
    Returns list of {deck, wr, tier, expected_range, issue, severity}.
    """
    decks = matrix_data['decks']
    matchups = matrix_data['matchups']
    evs = matrix_data.get('meta_ev', {})

    # Expected WR ranges by tier
    tier_ranges = {
        'T1': (0.45, 0.75),  # T1 decks should be competitive
        'T2': (0.40, 0.70),
        'T3': (0.30, 0.60),
    }

    outliers = []
    for d in decks:
        share = get_meta_share(d)
        tier = 'T1' if share >= 0.05 else 'T2' if share >= 0.03 else 'T3'
        wr = evs.get(d, 0)
        lo, hi = tier_ranges[tier]

        issues = []
        if wr < lo:
            issues.append(f'WR {wr:.0%} below {tier} floor {lo:.0%}')
        if wr > hi:
            issues.append(f'WR {wr:.0%} above {tier} ceiling {hi:.0%}')

        # Check for extreme matchups (>90% or <10%)
        extreme_wins = []
        extreme_losses = []
        for d2 in decks:
            if d == d2:
                continue
            key = f"{d}_vs_{d2}"
            mwr = matchups.get(key, 0.5)
            if mwr >= 0.90:
                extreme_wins.append((d2, mwr))
            elif mwr <= 0.10:
                extreme_losses.append((d2, mwr))

        if extreme_losses:
            names = ', '.join(f'{d2} ({mwr:.0%})' for d2, mwr in extreme_losses)
            issues.append(f'Near-zero WR vs: {names}')
        if extreme_wins:
            names = ', '.join(f'{d2} ({mwr:.0%})' for d2, mwr in extreme_wins)
            issues.append(f'Near-100% WR vs: {names}')

        if issues:
            severity = 'HIGH' if wr < lo - threshold or wr > hi + threshold else 'MEDIUM'
            outliers.append({
                'deck': d, 'wr': wr, 'tier': tier, 'share': share,
                'expected': f'{lo:.0%}-{hi:.0%}', 'issues': issues,
                'severity': severity,
                'extreme_wins': extreme_wins, 'extreme_losses': extreme_losses,
            })

    outliers.sort(key=lambda x: (0 if x['severity'] == 'HIGH' else 1, x['wr']))
    return outliers


def check_symmetry(matrix_data, tolerance=0.20):
    """Flag all matchup pairs where A_vs_B + B_vs_A deviates from 100% by > tolerance."""
    decks = matrix_data['decks']
    matchups = matrix_data['matchups']
    violations = []
    for i, d1 in enumerate(decks):
        for d2 in decks[i+1:]:
            k1, k2 = f"{d1}_vs_{d2}", f"{d2}_vs_{d1}"
            if k1 in matchups and k2 in matchups:
                total = matchups[k1] + matchups[k2]
                if abs(total - 1.0) > tolerance:
                    violations.append((d1, d2, matchups[k1], matchups[k2], total))
    violations.sort(key=lambda x: abs(x[4] - 1.0), reverse=True)
    return violations


def check_extremes(matrix_data, threshold_hi=0.90, threshold_lo=0.10):
    """Flag any matchup with WR > threshold_hi or < threshold_lo."""
    extremes = []
    for key, wr in matrix_data['matchups'].items():
        if wr > threshold_hi or wr < threshold_lo:
            extremes.append((key, wr))
    extremes.sort(key=lambda x: x[1])
    return extremes


def post_matrix_audit(matrix_data):
    """Run all post-matrix holistic controls. Print warnings if any fail."""
    print("\n" + "=" * 60)
    print("POST-MATRIX HOLISTIC AUDIT")
    print("=" * 60)

    # Control 6: Symmetry
    sym = check_symmetry(matrix_data)
    if sym:
        print(f"\n⚠ SYMMETRY VIOLATIONS ({len(sym)} pairs >20% off):")
        for d1, d2, w1, w2, total in sym[:10]:
            print(f"  {d1} vs {d2}: {w1:.0%} + {w2:.0%} = {total:.0%} (off by {abs(total-1):.0%})")
    else:
        print("\n✓ All matchup pairs within symmetry tolerance")

    # Control 7: Extreme matchups
    ext = check_extremes(matrix_data)
    if ext:
        print(f"\n⚠ EXTREME MATCHUPS ({len(ext)} matchups >90% or <10%):")
        for key, wr in ext[:10]:
            print(f"  {key}: {wr:.0%}")
    else:
        print("\n✓ No extreme matchups (all within 10-90%)")

    # Control 8: Burn ceiling
    evs = matrix_data.get('meta_ev', {})
    burn_wr = evs.get('burn', None)
    if burn_wr is not None:
        if burn_wr > 0.55:
            print(f"\n⚠ BURN CEILING EXCEEDED: {burn_wr:.0%} (limit: 55%)")
        else:
            print(f"\n✓ Burn meta WR: {burn_wr:.0%} (within 55% ceiling)")

    # Control 9: Known matchup ranges
    out_of_range = check_expected_ranges(matrix_data)
    if out_of_range:
        print(f"\n⚠ MATCHUPS OUTSIDE EXPECTED RANGES ({len(out_of_range)} / "
              f"{len(EXPECTED_RANGES)} tracked):")
        for d1, d2, wr, (lo, hi) in out_of_range:
            print(f"  {d1} vs {d2}: {wr:.0%} (expected {lo:.0%}-{hi:.0%})")
    else:
        print(f"\n✓ All {len(EXPECTED_RANGES)} known matchups within expected ranges")

    print("=" * 60 + "\n")
    return len(sym), len(ext)


# ── 2. Strategy Audit ─────────────────────────────────────────────────────────

def audit_strategy(deck_key, n_games=50, opponent='dimir'):
    """
    Deep audit of a single deck's strategy. Runs games and analyzes:
    - Win conditions deployed
    - Cards never played
    - Average kill turn
    - Win reasons distribution
    - Mana efficiency
    Returns audit dict.
    """
    results = []
    all_log_lines = []
    for seed in range(n_games):
        random.seed(seed)
        r = run_game(deck_key, opponent)
        results.append(r)
        all_log_lines.extend(r.log_lines)

    wins = sum(1 for r in results if r.winner == 'p1')
    wr = wins / n_games

    # Win reasons
    win_reasons = Counter()
    loss_reasons = Counter()
    for r in results:
        reason = r.win_reason[:50] if r.win_reason else 'timeout'
        if r.winner == 'p1':
            win_reasons[reason] += 1
        else:
            loss_reasons[reason] += 1

    # Kill turns
    kill_turns = [r.kill_turn for r in results if r.kill_turn and r.winner == 'p1']
    avg_kill = sum(kill_turns) / len(kill_turns) if kill_turns else None

    # T15 timeouts
    timeouts = sum(1 for r in results if r.game_length >= 15)

    # Deck composition check
    deck_fn = DECKS.get(deck_key)
    if not deck_fn:
        meta = get_meta(deck_key)
        deck_fn = meta['make_deck'] if meta else None
    if deck_fn:
        cards = deck_fn()
        lands = sum(1 for c in cards if c.is_land())
        nonlands = 60 - lands
        win_cons = sum(1 for c in cards if c.win_condition)
        combo_pcs = sum(1 for c in cards if c.is_combo_piece)
        creatures = sum(1 for c in cards if c.is_creature())
    else:
        lands = nonlands = win_cons = combo_pcs = creatures = 0

    # Flag issues
    issues = []
    if wr < 0.25:
        issues.append(f'Very low WR: {wr:.0%} vs {opponent}')
    if timeouts > n_games * 0.3:
        issues.append(f'High timeout rate: {timeouts}/{n_games} ({timeouts/n_games:.0%})')
    if win_cons == 0 and combo_pcs == 0 and creatures == 0:
        issues.append('NO WIN CONDITION in decklist')
    if lands > 28:
        issues.append(f'Excessive lands: {lands}/60')
    if lands < 14 and deck_key != 'belcher':
        issues.append(f'Very few lands: {lands}/60')
    if avg_kill and avg_kill > 12:
        issues.append(f'Slow kill: avg T{avg_kill:.1f}')

    return {
        'deck': deck_key, 'opponent': opponent, 'n_games': n_games,
        'wr': wr, 'wins': wins, 'losses': n_games - wins,
        'avg_kill': avg_kill, 'timeouts': timeouts,
        'lands': lands, 'nonlands': nonlands,
        'win_cons': win_cons, 'combo_pieces': combo_pcs, 'creatures': creatures,
        'win_reasons': dict(win_reasons.most_common(5)),
        'loss_reasons': dict(loss_reasons.most_common(5)),
        'issues': issues,
    }


# ── 3. HTML Dashboard ────────────────────────────────────────────────────────

def _generate_replay_html(deck1, deck2, seed):
    """Run one game and return turn-by-turn HTML block."""
    random.seed(seed)
    r = run_game(deck1, deck2)
    lines_html = '\n'.join(
        f'<div class="log-line {"key" if "★" in l else ""}">{html.escape(l)}</div>'
        for l in r.log_lines
    )
    winner_class = 'win' if r.winner == 'p1' else 'loss'
    return f"""
    <div class="game-card {winner_class}">
        <div class="game-header">
            Seed {seed} — <b>{r.p1_deck}</b> vs <b>{r.p2_deck}</b>
            — <span class="{winner_class}">{'P1 WINS' if r.winner == 'p1' else 'P2 WINS'}</span>
            T{r.game_length} | {r.win_reason or 'timeout'}
        </div>
        <div class="game-meta">
            Life: {r.final_p1_life}-{r.final_p2_life} |
            P1 mulls: {r.p1_mulls} | P2 mulls: {r.p2_mulls} |
            P1 first: {r.p1_went_first}
        </div>
        <div class="game-log" style="display:none">{lines_html}</div>
        <button onclick="this.previousElementSibling.style.display=
            this.previousElementSibling.style.display==='none'?'block':'none';
            this.textContent=this.textContent==='Show Log'?'Hide Log':'Show Log'">Show Log</button>
    </div>"""


def generate_audit_dashboard(matrix_data, outliers, n_replays=5):
    """Generate a full HTML audit dashboard with outlier analysis and replays."""

    decks = matrix_data['decks']
    matchups = matrix_data['matchups']
    evs = matrix_data.get('meta_ev', {})
    rankings = matrix_data.get('rankings', sorted(evs.keys(), key=lambda k: -evs.get(k, 0)))

    # ── Rankings table ──
    rankings_rows = ''
    for i, d in enumerate(rankings):
        share = get_meta_share(d)
        tier = 'T1' if share >= 0.05 else 'T2' if share >= 0.03 else ''
        wr = evs.get(d, 0)
        bar_w = int(wr * 300)
        is_outlier = any(o['deck'] == d for o in outliers)
        row_class = 'outlier-row' if is_outlier else ''
        rankings_rows += f"""
        <tr class="{row_class}">
            <td>{i+1}</td><td>{d}</td><td>{tier}</td><td>{share:.0%}</td>
            <td>{wr:.1%}</td>
            <td><div class="bar" style="width:{bar_w}px"></div></td>
        </tr>"""

    # ── Outlier cards ──
    outlier_cards = ''
    for o in outliers:
        sev_class = 'high' if o['severity'] == 'HIGH' else 'medium'
        issues_html = '<br>'.join(html.escape(i) for i in o['issues'])
        outlier_cards += f"""
        <div class="outlier-card {sev_class}">
            <div class="outlier-header">{o['severity']}: {o['deck']} ({o['tier']}, {o['share']:.0%} meta)</div>
            <div class="outlier-wr">Meta-Weighted WR: {o['wr']:.1%} (expected {o['expected']})</div>
            <div class="outlier-issues">{issues_html}</div>
        </div>"""

    # ── Replay section for outliers ──
    replay_html = ''
    replay_decks = set()
    for o in outliers[:6]:  # Top 6 outliers
        dk = o['deck']
        if dk in replay_decks:
            continue
        replay_decks.add(dk)

        # Pick opponents: worst matchup and best matchup
        opponents = []
        if o['extreme_losses']:
            opponents.append(o['extreme_losses'][0][0])
        if o['extreme_wins']:
            opponents.append(o['extreme_wins'][0][0])
        if not opponents:
            opponents = ['dimir']

        for opp in opponents[:2]:
            replay_html += f'<h3>{dk} vs {opp}</h3>'
            for seed in range(n_replays):
                replay_html += _generate_replay_html(dk, opp, seed)

    # ── Strategy audits for worst outliers ──
    audit_cards = ''
    for o in [x for x in outliers if x['severity'] == 'HIGH'][:4]:
        audit = audit_strategy(o['deck'], n_games=30)
        wins_html = '<br>'.join(f'{v}x {html.escape(k)}' for k, v in audit['win_reasons'].items())
        losses_html = '<br>'.join(f'{v}x {html.escape(k)}' for k, v in audit['loss_reasons'].items())
        issues_html = '<br>'.join(html.escape(i) for i in audit['issues']) or 'None'
        audit_cards += f"""
        <div class="audit-card">
            <h3>{audit['deck']} Strategy Audit ({audit['n_games']}g vs {audit['opponent']})</h3>
            <table class="audit-table">
                <tr><td>Win Rate</td><td>{audit['wr']:.0%} ({audit['wins']}W-{audit['losses']}L)</td></tr>
                <tr><td>Avg Kill Turn</td><td>{f"T{audit['avg_kill']:.1f}" if audit['avg_kill'] else 'N/A'}</td></tr>
                <tr><td>Timeouts (T15+)</td><td>{audit['timeouts']}/{audit['n_games']}</td></tr>
                <tr><td>Deck</td><td>{audit['lands']}L / {audit['nonlands']}NL, {audit['win_cons']} win cons, {audit['combo_pieces']} combo, {audit['creatures']} creatures</td></tr>
                <tr><td>Issues</td><td class="issue-text">{issues_html}</td></tr>
                <tr><td>Win Reasons</td><td>{wins_html or 'None'}</td></tr>
                <tr><td>Loss Reasons</td><td>{losses_html or 'None'}</td></tr>
            </table>
        </div>"""

    # ── Assemble HTML ──
    dashboard = f"""<!DOCTYPE html>
<html><head>
<meta charset="utf-8">
<title>Meta Audit Dashboard</title>
<style>
    body {{ font-family: 'Segoe UI', Tahoma, sans-serif; background: #1a1a2e; color: #e0e0e0; margin: 20px; }}
    h1 {{ color: #00d4ff; border-bottom: 2px solid #00d4ff; padding-bottom: 10px; }}
    h2 {{ color: #ff6b6b; margin-top: 30px; }}
    h3 {{ color: #ffd93d; }}
    table {{ border-collapse: collapse; width: 100%; margin: 10px 0; }}
    th, td {{ padding: 6px 12px; text-align: left; border-bottom: 1px solid #333; }}
    th {{ background: #16213e; color: #00d4ff; }}
    .bar {{ height: 16px; background: linear-gradient(90deg, #00d4ff, #0066ff); border-radius: 3px; }}
    .outlier-row {{ background: #2a1a1a !important; }}
    .outlier-row td {{ color: #ff6b6b; }}
    .outlier-card {{ border: 2px solid #666; border-radius: 8px; padding: 15px; margin: 10px 0; }}
    .outlier-card.high {{ border-color: #ff4444; background: #2a1515; }}
    .outlier-card.medium {{ border-color: #ffaa00; background: #2a2215; }}
    .outlier-header {{ font-size: 1.2em; font-weight: bold; }}
    .outlier-wr {{ font-size: 1.1em; margin: 5px 0; }}
    .outlier-issues {{ color: #ffaa00; margin-top: 8px; }}
    .game-card {{ border: 1px solid #333; border-radius: 6px; padding: 10px; margin: 8px 0; }}
    .game-card.win {{ border-left: 4px solid #44ff44; }}
    .game-card.loss {{ border-left: 4px solid #ff4444; }}
    .game-header {{ font-weight: bold; }}
    .game-meta {{ color: #888; font-size: 0.9em; }}
    .game-log {{ background: #0a0a15; padding: 10px; margin: 8px 0; font-family: monospace; font-size: 0.85em; max-height: 400px; overflow-y: auto; }}
    .log-line.key {{ color: #ffd93d; font-weight: bold; }}
    .win {{ color: #44ff44; }}
    .loss {{ color: #ff4444; }}
    button {{ background: #16213e; color: #00d4ff; border: 1px solid #00d4ff; padding: 4px 12px; cursor: pointer; border-radius: 4px; }}
    button:hover {{ background: #1a3a5c; }}
    .audit-card {{ background: #16213e; border-radius: 8px; padding: 15px; margin: 15px 0; }}
    .audit-table td {{ padding: 4px 10px; }}
    .audit-table td:first-child {{ color: #00d4ff; font-weight: bold; width: 150px; }}
    .issue-text {{ color: #ff6b6b; }}
    .summary {{ background: #16213e; padding: 15px; border-radius: 8px; margin: 15px 0; }}
</style>
</head><body>

<h1>Meta Audit Dashboard</h1>

<div class="summary">
    <b>{len(decks)}</b> decks | <b>{len(outliers)}</b> outliers flagged
    ({sum(1 for o in outliers if o['severity']=='HIGH')} HIGH,
     {sum(1 for o in outliers if o['severity']=='MEDIUM')} MEDIUM)
</div>

<h2>Rankings (Meta-Weighted WR, T1+T2)</h2>
<table>
<tr><th>#</th><th>Deck</th><th>Tier</th><th>Meta</th><th>WR</th><th></th></tr>
{rankings_rows}
</table>

<h2>Outliers</h2>
{outlier_cards if outlier_cards else '<p>No outliers detected.</p>'}

<h2>Strategy Audits</h2>
{audit_cards if audit_cards else '<p>No HIGH severity outliers to audit.</p>'}

<h2>Game Replays (Outlier Matchups)</h2>
{replay_html if replay_html else '<p>No replays generated.</p>'}

</body></html>"""

    return dashboard


# ── 4. Main: audit a matrix ──────────────────────────────────────────────────

def audit_matrix(matrix_path=None, tag='matrix'):
    """Load a matrix, detect outliers, generate dashboard. Returns outlier list."""
    if matrix_path:
        with open(matrix_path) as f:
            data = json.load(f)
        print(f"Loaded: {matrix_path}")
    else:
        data = load_matrix(tag)
        if not data:
            print("No matrix found. Run a matrix first.")
            return []

    outliers = detect_outliers(data)

    # Print summary
    print(f"\n{'='*60}")
    print(f"  META AUDIT — {len(data['decks'])} decks")
    print(f"{'='*60}")

    if not outliers:
        print("\n  No outliers detected. All decks within expected ranges.")
    else:
        print(f"\n  {len(outliers)} outliers flagged:\n")
        for o in outliers:
            sev = '!!' if o['severity'] == 'HIGH' else ' ?'
            print(f"  {sev} {o['deck']:15s}  {o['tier']}  WR={o['wr']:.1%}  (expected {o['expected']})")
            for issue in o['issues']:
                print(f"       {issue}")

    # Generate dashboard
    print("\n  Generating HTML dashboard...")
    dashboard_html = generate_audit_dashboard(data, outliers)
    os.makedirs(RESULTS_DIR, exist_ok=True)
    out_path = os.path.join(RESULTS_DIR, 'audit_dashboard.html')
    with open(out_path, 'w') as f:
        f.write(dashboard_html)
    print(f"  Saved: {out_path}")

    return outliers


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Meta Audit — outlier detection and replay dashboards')
    parser.add_argument('--file', '-f', help='Path to matrix JSON file')
    parser.add_argument('--run', action='store_true', help='Run a matrix first, then audit')
    parser.add_argument('-n', type=int, default=50, help='Games per matchup (for --run)')
    parser.add_argument('--decks', type=int, default=16, help='Top N decks (for --run)')
    parser.add_argument('--replays', type=int, default=5, help='Replays per outlier matchup')
    args = parser.parse_args()

    if args.run:
        from sim import run_meta_matrix
        from meta_results import save_matrix
        print(f"Running {args.decks}-deck matrix ({args.n} games each)...")
        matrix = run_meta_matrix(top_tier=args.decks, n_games=args.n)
        decks = sorted(set(d for pair in matrix for d in pair))
        path = save_matrix(matrix, decks=decks, n_games=args.n, tag='audit')
        audit_matrix(path)
    elif args.file:
        audit_matrix(args.file)
    else:
        audit_matrix()
