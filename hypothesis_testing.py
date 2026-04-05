"""
hypothesis_testing.py — Statistical hypothesis testing for MTG simulation data.

Provides z-tests, confidence intervals, and sample size calculations for
matchup win rates. Uses only stdlib (no scipy/numpy dependency).

Usage:
  python hypothesis_testing.py --from-json results/overnight_sweep.json
  python hypothesis_testing.py --live bug storm 500
  python hypothesis_testing.py --compare bug storm dimir 500
  python hypothesis_testing.py --sample-size 0.03
  python hypothesis_testing.py --integrity storm dimir 200
  python hypothesis_testing.py --play-draw bug dimir 500
  python hypothesis_testing.py --mulligan bug dimir 500
  python hypothesis_testing.py --archetype 300
  python hypothesis_testing.py --kill-turn 300

All tests use the normal approximation to the binomial (valid for n >= 30).
"""

import argparse
import json
import math
import sys
from dataclasses import dataclass
from typing import Optional


# ── Standard normal CDF (no scipy needed) ────────────────────────────────────

def _phi(x: float) -> float:
    """Standard normal CDF via Abramowitz & Stegun approximation (|error| < 7.5e-8)."""
    if x < -8:
        return 0.0
    if x > 8:
        return 1.0
    a1, a2, a3, a4, a5 = 0.254829592, -0.284496736, 1.421413741, -1.453152027, 1.061405429
    p = 0.3275911
    sign = 1 if x >= 0 else -1
    x = abs(x) / math.sqrt(2)
    t = 1.0 / (1.0 + p * x)
    y = 1.0 - (((((a5 * t + a4) * t) + a3) * t + a2) * t + a1) * t * math.exp(-x * x)
    return 0.5 * (1.0 + sign * y)


def _z_critical(confidence: float) -> float:
    """Return z* for a given two-sided confidence level (e.g. 0.95 -> 1.96)."""
    # Newton's method to invert _phi
    target = 0.5 + confidence / 2
    z = 1.96  # initial guess
    for _ in range(50):
        err = _phi(z) - target
        pdf = math.exp(-z * z / 2) / math.sqrt(2 * math.pi)
        if pdf < 1e-15:
            break
        z -= err / pdf
    return z


# ── Data classes ──────────────────────────────────────────────────────────────

@dataclass
class ProportionTestResult:
    """Result of a one-sample or two-sample proportion z-test."""
    test_name: str
    p_hat: float              # observed proportion (or difference)
    p0: float                 # null hypothesis value
    z_stat: float
    p_value: float            # two-sided p-value
    ci_low: float             # confidence interval lower bound
    ci_high: float            # confidence interval upper bound
    confidence: float         # confidence level (e.g. 0.95)
    n: int                    # sample size
    significant: bool         # reject H0 at given confidence?
    detail: str               # human-readable summary

    def __str__(self):
        sig = "YES — REJECT H0" if self.significant else "no — fail to reject H0"
        return (
            f"\n{'─' * 60}\n"
            f"  {self.test_name}\n"
            f"{'─' * 60}\n"
            f"  Observed:    {self.p_hat * 100:.2f}%\n"
            f"  Null (H0):   {self.p0 * 100:.2f}%\n"
            f"  z-statistic: {self.z_stat:+.4f}\n"
            f"  p-value:     {self.p_value:.6f}\n"
            f"  {self.confidence * 100:.0f}% CI:     [{self.ci_low * 100:.2f}%, {self.ci_high * 100:.2f}%]\n"
            f"  Significant: {sig}\n"
            f"  {self.detail}\n"
            f"{'─' * 60}"
        )


@dataclass
class SampleSizeResult:
    """Result of a sample size power calculation."""
    effect_size: float    # minimum detectable difference from 50%
    confidence: float
    power: float
    required_n: int

    def __str__(self):
        return (
            f"\n{'─' * 60}\n"
            f"  Sample Size Calculator\n"
            f"{'─' * 60}\n"
            f"  Detect:     {self.effect_size * 100:.1f}% difference from 50%\n"
            f"  Confidence: {self.confidence * 100:.0f}%\n"
            f"  Power:      {self.power * 100:.0f}%\n"
            f"  Required N: {self.required_n:,} matches\n"
            f"{'─' * 60}"
        )


# ── Core statistical tests ───────────────────────────────────────────────────

def test_vs_fair(wins: int, n: int, confidence: float = 0.95) -> ProportionTestResult:
    """
    One-sample proportion z-test: is the win rate significantly different from 50%?

    H0: p = 0.50  (matchup is fair)
    H1: p ≠ 0.50  (matchup is favored/unfavored)
    """
    p0 = 0.50
    p_hat = wins / n
    se_null = math.sqrt(p0 * (1 - p0) / n)  # SE under H0
    z = (p_hat - p0) / se_null
    p_value = 2 * (1 - _phi(abs(z)))

    # Wilson score interval (better coverage than Wald for proportions)
    z_star = _z_critical(confidence)
    ci_low, ci_high = _wilson_ci(wins, n, z_star)

    return ProportionTestResult(
        test_name=f"Win rate vs 50% (n={n:,})",
        p_hat=p_hat, p0=p0, z_stat=z, p_value=p_value,
        ci_low=ci_low, ci_high=ci_high,
        confidence=confidence, n=n,
        significant=p_value < (1 - confidence),
        detail=_interpret_matchup(p_hat, ci_low, ci_high, p_value < (1 - confidence)),
    )


def test_vs_value(wins: int, n: int, p0: float, confidence: float = 0.95) -> ProportionTestResult:
    """
    One-sample proportion z-test against an arbitrary null value.

    H0: p = p0
    H1: p ≠ p0
    """
    p_hat = wins / n
    se_null = math.sqrt(p0 * (1 - p0) / n)
    z = (p_hat - p0) / se_null
    p_value = 2 * (1 - _phi(abs(z)))

    z_star = _z_critical(confidence)
    ci_low, ci_high = _wilson_ci(wins, n, z_star)

    return ProportionTestResult(
        test_name=f"Win rate vs {p0 * 100:.1f}% (n={n:,})",
        p_hat=p_hat, p0=p0, z_stat=z, p_value=p_value,
        ci_low=ci_low, ci_high=ci_high,
        confidence=confidence, n=n,
        significant=p_value < (1 - confidence),
        detail=f"Observed {p_hat * 100:.1f}% vs null {p0 * 100:.1f}%",
    )


def compare_matchups(wins_a: int, n_a: int, wins_b: int, n_b: int,
                     label_a: str = "A", label_b: str = "B",
                     confidence: float = 0.95) -> ProportionTestResult:
    """
    Two-sample proportion z-test: do two matchups have significantly different win rates?

    H0: p_A = p_B
    H1: p_A ≠ p_B
    """
    p_a = wins_a / n_a
    p_b = wins_b / n_b
    diff = p_a - p_b

    # Pooled proportion under H0
    p_pool = (wins_a + wins_b) / (n_a + n_b)
    se_pool = math.sqrt(p_pool * (1 - p_pool) * (1 / n_a + 1 / n_b))

    z = diff / se_pool if se_pool > 0 else 0
    p_value = 2 * (1 - _phi(abs(z)))

    # CI for difference (unpooled SE)
    se_diff = math.sqrt(p_a * (1 - p_a) / n_a + p_b * (1 - p_b) / n_b)
    z_star = _z_critical(confidence)
    ci_low = diff - z_star * se_diff
    ci_high = diff + z_star * se_diff

    return ProportionTestResult(
        test_name=f"{label_a} vs {label_b} win rate comparison",
        p_hat=diff, p0=0.0, z_stat=z, p_value=p_value,
        ci_low=ci_low, ci_high=ci_high,
        confidence=confidence, n=n_a + n_b,
        significant=p_value < (1 - confidence),
        detail=(
            f"{label_a}: {p_a * 100:.1f}% (n={n_a:,})  vs  "
            f"{label_b}: {p_b * 100:.1f}% (n={n_b:,})\n"
            f"  Difference: {diff * 100:+.1f}pp  "
            f"CI: [{ci_low * 100:+.1f}pp, {ci_high * 100:+.1f}pp]"
        ),
    )


def confidence_interval(wins: int, n: int, confidence: float = 0.95) -> tuple:
    """Return (lower, upper) Wilson score confidence interval for a proportion."""
    z_star = _z_critical(confidence)
    return _wilson_ci(wins, n, z_star)


def required_sample_size(effect: float = 0.03, confidence: float = 0.95,
                         power: float = 0.80) -> SampleSizeResult:
    """
    How many games are needed to detect a given effect size (deviation from 50%)?

    effect: minimum detectable difference (e.g. 0.03 = 3 percentage points)
    confidence: significance level (e.g. 0.95 for alpha=0.05)
    power: statistical power (e.g. 0.80)
    """
    z_alpha = _z_critical(confidence)
    z_beta = _z_critical(power + (1 - power) / 2)  # one-sided z for power
    # For proportion test vs p0=0.5:
    # n = (z_alpha * sqrt(p0*q0) + z_beta * sqrt(p1*q1))^2 / (p1-p0)^2
    p0 = 0.50
    p1 = 0.50 + effect
    n = ((z_alpha * math.sqrt(p0 * (1 - p0)) +
          z_beta * math.sqrt(p1 * (1 - p1))) / effect) ** 2
    return SampleSizeResult(
        effect_size=effect, confidence=confidence, power=power,
        required_n=math.ceil(n),
    )


# ── Helpers ───────────────────────────────────────────────────────────────────

def _wilson_ci(wins: int, n: int, z: float) -> tuple:
    """Wilson score confidence interval — better than Wald for proportions near 0 or 1."""
    p_hat = wins / n
    denom = 1 + z * z / n
    centre = (p_hat + z * z / (2 * n)) / denom
    spread = z * math.sqrt((p_hat * (1 - p_hat) + z * z / (4 * n)) / n) / denom
    return (max(0, centre - spread), min(1, centre + spread))


def _interpret_matchup(p_hat: float, ci_low: float, ci_high: float,
                       significant: bool) -> str:
    """Human-readable matchup interpretation."""
    if not significant:
        return "Matchup is statistically indistinguishable from 50/50."
    if p_hat > 0.60:
        return f"Strong favorable matchup ({p_hat * 100:.1f}%)."
    if p_hat > 0.55:
        return f"Moderate edge ({p_hat * 100:.1f}%)."
    if p_hat > 0.50:
        return f"Slight edge ({p_hat * 100:.1f}%) — but small in practical terms."
    if p_hat > 0.45:
        return f"Slight disadvantage ({p_hat * 100:.1f}%)."
    if p_hat > 0.40:
        return f"Moderate disadvantage ({p_hat * 100:.1f}%)."
    return f"Strong unfavorable matchup ({p_hat * 100:.1f}%)."


# ── Analyze existing sweep data ──────────────────────────────────────────────

def analyze_sweep(json_path: str, protagonist: str = 'bug',
                  confidence: float = 0.95, n_assumed: int = 3000) -> list:
    """
    Analyze all matchups for a protagonist from sweep JSON.

    Since sweep JSON stores only win rates (not raw win counts), we reconstruct
    wins = round(wr/100 * n_assumed). For precise results, use --live mode.
    """
    with open(json_path) as f:
        data = json.load(f)

    if protagonist not in data.get('per_matchup', {}):
        print(f"Error: '{protagonist}' not found in sweep data.")
        print(f"Available: {list(data['per_matchup'].keys())}")
        return []

    matchups = data['per_matchup'][protagonist]
    results = []

    print(f"\n{'=' * 70}")
    print(f"  Hypothesis Tests for {protagonist.upper()} (n≈{n_assumed:,} per matchup)")
    print(f"{'=' * 70}")

    for opp, wr_pct in sorted(matchups.items(), key=lambda x: -x[1]):
        wins = round(wr_pct / 100 * n_assumed)
        result = test_vs_fair(wins, n_assumed, confidence)
        result.test_name = f"{protagonist} vs {opp}"
        results.append((opp, wr_pct, result))

    # Print summary table
    print(f"\n  {'Matchup':<18} {'WR%':>6} {'95% CI':>17} {'z':>7} {'p-value':>10} {'Sig?':>5}")
    print(f"  {'─' * 65}")
    for opp, wr_pct, r in results:
        sig_marker = " ***" if r.p_value < 0.001 else "  **" if r.p_value < 0.01 else "   *" if r.significant else ""
        print(f"  {opp:<18} {wr_pct:>5.1f}% [{r.ci_low * 100:>5.1f}, {r.ci_high * 100:>5.1f}%] {r.z_stat:>+7.2f} {r.p_value:>10.6f}{sig_marker}")

    # Meta EV confidence interval
    if protagonist in data.get('completed', {}):
        ev = data['completed'][protagonist]
        print(f"\n  Meta EV: {ev:.1f}%")

    # Count significant results
    sig_count = sum(1 for _, _, r in results if r.significant)
    total = len(results)
    print(f"\n  {sig_count}/{total} matchups significantly different from 50%")
    print(f"  Significance: *** p<0.001  ** p<0.01  * p<0.05")

    return results


# ── Live simulation with hypothesis test ─────────────────────────────────────

def run_live_test(protagonist: str, antagonist: str, n_matches: int,
                  confidence: float = 0.95):
    """Run a live simulation and perform hypothesis testing on the results."""
    from sim import run_any_bo3

    print(f"\nRunning {n_matches:,} Bo3 matches: {protagonist} vs {antagonist}...")
    result = run_any_bo3(protagonist, antagonist, n_matches)

    wins = result['wins']
    n = result['n']

    test_result = test_vs_fair(wins, n, confidence)
    test_result.test_name = f"{protagonist} vs {antagonist} (live, Bo3)"
    print(test_result)

    return test_result


def run_live_comparison(protagonist: str, matchup_a: str, matchup_b: str,
                        n_matches: int, confidence: float = 0.95):
    """Run two live simulations and compare the win rates."""
    from sim import run_any_bo3

    print(f"\nRunning {n_matches:,} Bo3 matches each...")
    print(f"  {protagonist} vs {matchup_a}...")
    result_a = run_any_bo3(protagonist, matchup_a, n_matches)
    print(f"  {protagonist} vs {matchup_b}...")
    result_b = run_any_bo3(protagonist, matchup_b, n_matches)

    # Individual tests
    test_a = test_vs_fair(result_a['wins'], result_a['n'], confidence)
    test_a.test_name = f"{protagonist} vs {matchup_a}"
    test_b = test_vs_fair(result_b['wins'], result_b['n'], confidence)
    test_b.test_name = f"{protagonist} vs {matchup_b}"

    print(test_a)
    print(test_b)

    # Comparison test
    comp = compare_matchups(
        result_a['wins'], result_a['n'],
        result_b['wins'], result_b['n'],
        label_a=f"vs {matchup_a}", label_b=f"vs {matchup_b}",
        confidence=confidence,
    )
    print(comp)

    return test_a, test_b, comp


# ── Meta EV confidence interval via bootstrap-style approximation ────────────

def meta_ev_ci(json_path: str, protagonist: str = 'bug',
               n_assumed: int = 3000, confidence: float = 0.95) -> tuple:
    """
    Compute confidence interval on the meta EV by propagating per-matchup CIs.

    Uses delta method: Var(EV) = sum(w_i^2 * Var(p_i)) where w_i = meta share.
    """
    with open(json_path) as f:
        data = json.load(f)

    # Load meta shares from the codebase
    try:
        from cards import MATCHUP_META
        shares = {k: v['share'] for k, v in MATCHUP_META.items()}
    except (ImportError, KeyError):
        # Fallback: equal weights
        matchups = data['per_matchup'].get(protagonist, {})
        n_mu = len(matchups)
        shares = {k: 1.0 / n_mu for k in matchups}

    matchups = data['per_matchup'].get(protagonist, {})
    if not matchups:
        return None

    total_share = sum(shares.get(k, 0) for k in matchups)
    if total_share == 0:
        return None

    ev = 0.0
    var_ev = 0.0
    for opp, wr_pct in matchups.items():
        w = shares.get(opp, 0) / total_share
        p = wr_pct / 100
        ev += w * p
        var_ev += (w ** 2) * p * (1 - p) / n_assumed

    se_ev = math.sqrt(var_ev)
    z_star = _z_critical(confidence)

    ci_low = ev - z_star * se_ev
    ci_high = ev + z_star * se_ev

    print(f"\n{'─' * 60}")
    print(f"  Meta EV Confidence Interval for {protagonist.upper()}")
    print(f"{'─' * 60}")
    print(f"  Meta EV:   {ev * 100:.2f}%")
    print(f"  SE:        {se_ev * 100:.2f}%")
    print(f"  {confidence * 100:.0f}% CI:   [{ci_low * 100:.2f}%, {ci_high * 100:.2f}%]")
    print(f"{'─' * 60}")

    return (ev, ci_low, ci_high)


# ── H1: Reciprocity / Simulator Integrity Test ───────────────────────────────

def test_reciprocity(deck_a: str, deck_b: str, n_matches: int = 200,
                     confidence: float = 0.95):
    """
    H1: If A beats B at X%, does B beat A at ~(100-X)%?

    A well-calibrated simulator should produce symmetric results. Significant
    deviations indicate a protagonist/antagonist implementation bug.

    H0: WR(A vs B) + WR(B vs A) = 100%  (symmetric)
    H1: WR(A vs B) + WR(B vs A) ≠ 100%  (asymmetric — possible bug)
    """
    from sim import run_any_bo3

    print(f"\n{'=' * 60}")
    print(f"  H1: Reciprocity Test — {deck_a} vs {deck_b}")
    print(f"  n={n_matches:,} Bo3 each direction")
    print(f"{'=' * 60}")

    print(f"  Running {deck_a} vs {deck_b}...", flush=True)
    r_ab = run_any_bo3(deck_a, deck_b, n_matches)
    print(f"  Running {deck_b} vs {deck_a}...", flush=True)
    r_ba = run_any_bo3(deck_b, deck_a, n_matches)

    wr_ab = r_ab['match_wr']
    wr_ba = r_ba['match_wr']
    symmetry_sum = wr_ab + wr_ba  # should be ~1.0

    # Test: is wr_ab + wr_ba significantly different from 1.0?
    # Reframe: is (wr_ab - (1 - wr_ba)) significantly different from 0?
    diff = wr_ab - (1 - wr_ba)  # should be ~0 if symmetric
    se = math.sqrt(wr_ab * (1 - wr_ab) / n_matches +
                   wr_ba * (1 - wr_ba) / n_matches)
    z = diff / se if se > 0 else 0
    p_value = 2 * (1 - _phi(abs(z)))
    z_star = _z_critical(confidence)
    ci_low = diff - z_star * se
    ci_high = diff + z_star * se
    significant = p_value < (1 - confidence)

    status = "FAIL — asymmetry detected" if significant else "PASS — symmetric"
    print(f"\n  {deck_a} vs {deck_b}: {wr_ab * 100:.1f}%")
    print(f"  {deck_b} vs {deck_a}: {wr_ba * 100:.1f}%")
    print(f"  Sum:                  {symmetry_sum * 100:.1f}%  (expect ~100%)")
    print(f"  Asymmetry:            {diff * 100:+.1f}pp  CI: [{ci_low * 100:+.1f}, {ci_high * 100:+.1f}]pp")
    print(f"  z={z:+.3f}  p={p_value:.6f}")
    print(f"  Result: {status}")
    print(f"{'─' * 60}")

    return {
        'deck_a': deck_a, 'deck_b': deck_b,
        'wr_ab': wr_ab, 'wr_ba': wr_ba,
        'asymmetry': diff, 'z': z, 'p_value': p_value,
        'significant': significant, 'status': status,
    }


# ── H2: Play/Draw Advantage ─────────────────────────────────────────────────

def test_play_draw(protagonist: str, antagonist: str, n_games: int = 500,
                   confidence: float = 0.95):
    """
    H2: Does going first significantly improve win rate?

    Legacy average is ~53-55% for the player on the play. Large deviations
    suggest the simulator has a turn-order bias.

    H0: WR(on play) = WR(on draw)
    H1: WR(on play) ≠ WR(on draw)
    """
    from sim import run_any_match

    print(f"\n{'=' * 60}")
    print(f"  H2: Play/Draw Advantage — {protagonist} vs {antagonist}")
    print(f"  n={n_games:,} individual games")
    print(f"{'=' * 60}")

    # Collect individual game results
    play_wins = play_total = draw_wins = draw_total = 0
    for _ in range(n_games):
        pw, aw, gp, results = run_any_match(protagonist, antagonist)
        for r in results:
            if r.bug_went_first:
                play_total += 1
                if r.winner == 'bug':
                    play_wins += 1
            else:
                draw_total += 1
                if r.winner == 'bug':
                    draw_wins += 1

    play_wr = play_wins / play_total if play_total else 0
    draw_wr = draw_wins / draw_total if draw_total else 0

    # Two-sample proportion test
    comp = compare_matchups(
        play_wins, play_total, draw_wins, draw_total,
        label_a="On play", label_b="On draw", confidence=confidence,
    )

    # Also test: is play WR significantly > 50%?
    play_test = test_vs_fair(play_wins, play_total, confidence)

    z_star = _z_critical(confidence)
    play_ci = _wilson_ci(play_wins, play_total, z_star)
    draw_ci = _wilson_ci(draw_wins, draw_total, z_star)

    advantage = play_wr - draw_wr

    print(f"\n  On play:  {play_wr * 100:.1f}%  ({play_wins}/{play_total})  CI: [{play_ci[0] * 100:.1f}, {play_ci[1] * 100:.1f}%]")
    print(f"  On draw:  {draw_wr * 100:.1f}%  ({draw_wins}/{draw_total})  CI: [{draw_ci[0] * 100:.1f}, {draw_ci[1] * 100:.1f}%]")
    print(f"  Advantage: {advantage * 100:+.1f}pp  (z={comp.z_stat:+.3f}, p={comp.p_value:.4f})")
    if comp.significant:
        print(f"  Result: Significant play/draw advantage detected")
    else:
        print(f"  Result: No significant play/draw advantage at {confidence * 100:.0f}% level")

    # Sanity check against expected Legacy range
    if play_total > 100:
        if play_wr > 0.62:
            print(f"  WARNING: Play WR ({play_wr * 100:.1f}%) unusually high — possible turn-order bias")
        elif play_wr < 0.45:
            print(f"  WARNING: Play WR ({play_wr * 100:.1f}%) unusually low — possible turn-order bias")

    print(f"{'─' * 60}")

    return {
        'play_wr': play_wr, 'draw_wr': draw_wr,
        'play_n': play_total, 'draw_n': draw_total,
        'advantage': advantage, 'comparison': comp,
    }


# ── H3: Mulligan Penalty ────────────────────────────────────────────────────

def test_mulligan_penalty(protagonist: str, antagonist: str, n_games: int = 500,
                          confidence: float = 0.95):
    """
    H3: Does mulliganing significantly reduce win rate?

    Expected: 5-15% penalty per mulligan. No penalty or extreme penalty
    suggests broken mulligan/keep logic.

    H0: WR(kept 7) = WR(mulliganed)
    H1: WR(kept 7) ≠ WR(mulliganed)
    """
    from sim import run_any_match

    print(f"\n{'=' * 60}")
    print(f"  H3: Mulligan Penalty — {protagonist} vs {antagonist}")
    print(f"  n={n_games:,} individual games")
    print(f"{'=' * 60}")

    keep7_wins = keep7_total = mull_wins = mull_total = 0
    mull_counts = {}

    for _ in range(n_games):
        pw, aw, gp, results = run_any_match(protagonist, antagonist)
        for r in results:
            mulls = r.bug_mulls
            mull_counts[mulls] = mull_counts.get(mulls, 0) + 1
            if mulls == 0:
                keep7_total += 1
                if r.winner == 'bug':
                    keep7_wins += 1
            else:
                mull_total += 1
                if r.winner == 'bug':
                    mull_wins += 1

    keep7_wr = keep7_wins / keep7_total if keep7_total else 0
    mull_wr = mull_wins / mull_total if mull_total else 0
    penalty = keep7_wr - mull_wr

    # Two-sample test
    comp = compare_matchups(
        keep7_wins, keep7_total, mull_wins, mull_total,
        label_a="Kept 7", label_b="Mulliganed", confidence=confidence,
    ) if mull_total >= 10 else None

    z_star = _z_critical(confidence)

    print(f"\n  Mulligan distribution:")
    total_games = sum(mull_counts.values())
    for m in sorted(mull_counts.keys()):
        pct = mull_counts[m] / total_games * 100
        print(f"    Mull {m}: {mull_counts[m]:>4} games ({pct:.1f}%)")

    print(f"\n  Kept 7 WR:     {keep7_wr * 100:.1f}%  ({keep7_wins}/{keep7_total})")
    if mull_total >= 10:
        print(f"  Mulliganed WR: {mull_wr * 100:.1f}%  ({mull_wins}/{mull_total})")
        print(f"  Penalty:       {penalty * 100:+.1f}pp")
        if comp:
            print(f"  z={comp.z_stat:+.3f}  p={comp.p_value:.4f}")
            if comp.significant:
                print(f"  Result: Significant mulligan penalty detected")
            else:
                print(f"  Result: No significant mulligan penalty at {confidence * 100:.0f}% level")
            if mull_total >= 30 and abs(penalty) < 0.02:
                print(f"  WARNING: Near-zero penalty — mulligan logic may not be working")
    else:
        print(f"  Mulliganed: too few samples ({mull_total}) to test")

    print(f"{'─' * 60}")

    return {
        'keep7_wr': keep7_wr, 'mull_wr': mull_wr,
        'penalty': penalty, 'mull_counts': mull_counts,
        'comparison': comp,
    }


# ── H4: Archetype Dominance (Combo vs Fair) ─────────────────────────────────

def test_archetype_dominance(n_matches: int = 200, confidence: float = 0.95):
    """
    H4: Do combo decks significantly beat fair decks?

    Tests the rock-paper-scissors metagame structure:
    Combo should beat Fair, Fair should beat Prison, Prison should beat Combo.

    H0: Combo WR vs Fair = 50%
    H1: Combo WR vs Fair ≠ 50%
    """
    from sim import run_any_bo3
    from cards import DECKS
    from deck_registry import get_categories

    print(f"\n{'=' * 60}")
    print(f"  H4: Archetype Dominance Test")
    print(f"  n={n_matches:,} Bo3 per pairing")
    print(f"{'=' * 60}")

    # Classify decks by archetype
    combo_decks = [k for k in DECKS if 'combo' in get_categories(k) and k in DECKS]
    fair_decks = [k for k in DECKS if 'aggro' in get_categories(k)
                  and 'combo' not in get_categories(k) and k in DECKS]
    prison_decks = [k for k in DECKS if 'prison' in get_categories(k)
                    and 'combo' not in get_categories(k)
                    and 'aggro' not in get_categories(k) and k in DECKS]

    # Pick representative decks (avoid running 30+ pairings)
    combo_reps = [d for d in ['storm', 'reanimator', 'oops'] if d in DECKS][:3]
    fair_reps = [d for d in ['dimir', 'mardu', 'eldrazi'] if d in DECKS][:3]
    prison_reps = [d for d in ['prison', 'dnt'] if d in DECKS][:2]

    print(f"\n  Combo reps:  {combo_reps}")
    print(f"  Fair reps:   {fair_reps}")
    print(f"  Prison reps: {prison_reps}")

    def _run_archetype_vs(archetype_a, label_a, archetype_b, label_b):
        wins = total = 0
        results_detail = []
        for a in archetype_a:
            for b in archetype_b:
                if a == b:
                    continue
                r = run_any_bo3(a, b, n_matches)
                w = r['wins']
                n = r['n']
                wins += w
                total += n
                wr = w / n * 100
                results_detail.append((a, b, wr, n))
                print(f"    {a:<14} vs {b:<14} {wr:>5.1f}%", flush=True)
        return wins, total, results_detail

    # Combo vs Fair
    print(f"\n  Combo vs Fair:")
    cf_wins, cf_total, cf_detail = _run_archetype_vs(combo_reps, "Combo", fair_reps, "Fair")
    cf_test = test_vs_fair(cf_wins, cf_total, confidence)

    # Fair vs Prison
    print(f"\n  Fair vs Prison:")
    fp_wins, fp_total, fp_detail = _run_archetype_vs(fair_reps, "Fair", prison_reps, "Prison")
    fp_test = test_vs_fair(fp_wins, fp_total, confidence)

    # Prison vs Combo
    print(f"\n  Prison vs Combo:")
    pc_wins, pc_total, pc_detail = _run_archetype_vs(prison_reps, "Prison", combo_reps, "Combo")
    pc_test = test_vs_fair(pc_wins, pc_total, confidence)

    print(f"\n  {'─' * 55}")
    print(f"  {'Archetype Pairing':<25} {'WR':>6} {'z':>7} {'p':>10} {'Sig':>5}")
    print(f"  {'─' * 55}")
    for label, test, wins, total in [
        ("Combo vs Fair", cf_test, cf_wins, cf_total),
        ("Fair vs Prison", fp_test, fp_wins, fp_total),
        ("Prison vs Combo", pc_test, pc_wins, pc_total),
    ]:
        wr = wins / total * 100 if total else 0
        sig = "***" if test.p_value < 0.001 else "**" if test.p_value < 0.01 else "*" if test.significant else ""
        print(f"  {label:<25} {wr:>5.1f}% {test.z_stat:>+7.2f} {test.p_value:>10.4f} {sig:>5}")

    # Check RPS structure
    rps = (cf_test.p_hat > 0.5 and fp_test.p_hat > 0.5 and pc_test.p_hat > 0.5)
    print(f"\n  Rock-Paper-Scissors structure: {'YES' if rps else 'NO'}")
    if rps:
        print(f"  Combo > Fair > Prison > Combo — metagame is non-transitive")
    else:
        all_results = [(cf_test, "Combo>Fair"), (fp_test, "Fair>Prison"), (pc_test, "Prison>Combo")]
        broken = [label for t, label in all_results if t.p_hat <= 0.5]
        print(f"  Violated: {broken}")

    print(f"{'─' * 60}")

    return {
        'combo_vs_fair': {'wr': cf_wins / cf_total if cf_total else 0, 'test': cf_test},
        'fair_vs_prison': {'wr': fp_wins / fp_total if fp_total else 0, 'test': fp_test},
        'prison_vs_combo': {'wr': pc_wins / pc_total if pc_total else 0, 'test': pc_test},
        'rps_holds': rps,
    }


# ── H5: Kill Turn Distribution (Combo vs Fair Speed) ────────────────────────

def test_kill_turn(n_games: int = 300, confidence: float = 0.95):
    """
    H5: Do combo decks kill significantly faster than fair decks?

    Compares average kill turn for combo vs fair archetypes using a
    two-sample t-test (Welch's, no equal variance assumption).

    H0: mean_kill_combo = mean_kill_fair
    H1: mean_kill_combo < mean_kill_fair  (combo is faster)
    """
    from sim import run_any_match
    from cards import DECKS

    print(f"\n{'=' * 60}")
    print(f"  H5: Kill Turn Comparison — Combo vs Fair")
    print(f"  n={n_games:,} games per deck")
    print(f"{'=' * 60}")

    combo_decks = [d for d in ['storm', 'oops', 'reanimator'] if d in DECKS]
    fair_decks = [d for d in ['dimir', 'mardu', 'eldrazi'] if d in DECKS]
    # Use 'bug' as a common opponent
    opponent = 'bug'

    combo_turns = []
    fair_turns = []

    for deck in combo_decks:
        deck_turns = []
        for _ in range(n_games):
            pw, aw, gp, results = run_any_match(deck, opponent)
            for r in results:
                if r.winner == 'bug' and r.kill_turn:
                    deck_turns.append(r.kill_turn)
        avg = sum(deck_turns) / len(deck_turns) if deck_turns else 0
        combo_turns.extend(deck_turns)
        print(f"  {deck:<14} avg kill: T{avg:.1f}  ({len(deck_turns)} wins)", flush=True)

    for deck in fair_decks:
        deck_turns = []
        for _ in range(n_games):
            pw, aw, gp, results = run_any_match(deck, opponent)
            for r in results:
                if r.winner == 'bug' and r.kill_turn:
                    deck_turns.append(r.kill_turn)
        avg = sum(deck_turns) / len(deck_turns) if deck_turns else 0
        fair_turns.extend(deck_turns)
        print(f"  {deck:<14} avg kill: T{avg:.1f}  ({len(deck_turns)} wins)", flush=True)

    if not combo_turns or not fair_turns:
        print("  Not enough data to compare.")
        return None

    # Welch's t-test
    n1, n2 = len(combo_turns), len(fair_turns)
    mean1 = sum(combo_turns) / n1
    mean2 = sum(fair_turns) / n2
    var1 = sum((x - mean1) ** 2 for x in combo_turns) / (n1 - 1)
    var2 = sum((x - mean2) ** 2 for x in fair_turns) / (n2 - 1)
    se = math.sqrt(var1 / n1 + var2 / n2) if (var1 / n1 + var2 / n2) > 0 else 1

    t_stat = (mean1 - mean2) / se
    # Approximate p-value using normal (valid for large n)
    p_value = 2 * (1 - _phi(abs(t_stat)))

    z_star = _z_critical(confidence)
    ci_low = (mean1 - mean2) - z_star * se
    ci_high = (mean1 - mean2) + z_star * se

    print(f"\n  Combo avg kill: T{mean1:.2f}  (sd={math.sqrt(var1):.2f}, n={n1})")
    print(f"  Fair avg kill:  T{mean2:.2f}  (sd={math.sqrt(var2):.2f}, n={n2})")
    print(f"  Difference:     {mean1 - mean2:+.2f} turns  CI: [{ci_low:+.2f}, {ci_high:+.2f}]")
    print(f"  t={t_stat:+.3f}  p={p_value:.6f}")

    if p_value < (1 - confidence) and mean1 < mean2:
        print(f"  Result: Combo kills SIGNIFICANTLY faster than Fair")
    elif p_value < (1 - confidence) and mean1 > mean2:
        print(f"  WARNING: Fair kills faster than Combo — unexpected!")
    else:
        print(f"  Result: No significant speed difference at {confidence * 100:.0f}% level")

    print(f"{'─' * 60}")

    return {
        'combo_mean': mean1, 'fair_mean': mean2,
        'difference': mean1 - mean2, 't_stat': t_stat,
        'p_value': p_value, 'significant': p_value < (1 - confidence),
    }


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description='Hypothesis testing for MTG simulation data',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Analyze all matchups from existing sweep data
  python hypothesis_testing.py --from-json results/overnight_sweep.json

  # Analyze a specific protagonist
  python hypothesis_testing.py --from-json results/overnight_sweep.json --protagonist storm

  # Live test: run 500 Bo3 matches and test significance
  python hypothesis_testing.py --live bug storm 500

  # Compare two matchups head-to-head
  python hypothesis_testing.py --compare bug storm dimir 500

  # How many games to detect a 3% edge?
  python hypothesis_testing.py --sample-size 0.03

  # Meta EV confidence interval
  python hypothesis_testing.py --meta-ev results/overnight_sweep.json
        """,
    )
    parser.add_argument('--from-json', metavar='PATH',
                        help='Analyze matchups from sweep JSON file')
    parser.add_argument('--protagonist', default='bug',
                        help='Protagonist deck to analyze (default: bug)')
    parser.add_argument('--live', nargs=3, metavar=('PROTO', 'ANT', 'N'),
                        help='Run live sim and test: protagonist antagonist n_matches')
    parser.add_argument('--compare', nargs=4, metavar=('PROTO', 'A', 'B', 'N'),
                        help='Compare two matchups: protagonist matchup_a matchup_b n_matches')
    parser.add_argument('--sample-size', type=float, metavar='EFFECT',
                        help='Calculate required sample size for given effect size (e.g. 0.03)')
    parser.add_argument('--meta-ev', metavar='PATH',
                        help='Compute meta EV confidence interval from sweep JSON')
    parser.add_argument('--confidence', type=float, default=0.95,
                        help='Confidence level (default: 0.95)')
    parser.add_argument('--n-assumed', type=int, default=3000,
                        help='Assumed games per matchup in sweep data (default: 3000)')

    # H1-H5 hypothesis tests
    parser.add_argument('--integrity', nargs=3, metavar=('A', 'B', 'N'),
                        help='H1: Reciprocity test — deck_a deck_b n_matches')
    parser.add_argument('--play-draw', nargs=3, metavar=('PROTO', 'ANT', 'N'),
                        help='H2: Play/draw advantage — protagonist antagonist n_games')
    parser.add_argument('--mulligan', nargs=3, metavar=('PROTO', 'ANT', 'N'),
                        help='H3: Mulligan penalty — protagonist antagonist n_games')
    parser.add_argument('--archetype', type=int, metavar='N',
                        help='H4: Archetype dominance (combo vs fair vs prison) — n_matches per pairing')
    parser.add_argument('--kill-turn', type=int, metavar='N',
                        help='H5: Kill turn comparison (combo vs fair speed) — n_games per deck')

    args = parser.parse_args()

    has_action = any([args.from_json, args.live, args.compare, args.sample_size,
                      args.meta_ev, args.integrity, args.play_draw, args.mulligan,
                      args.archetype, args.kill_turn])
    if not has_action:
        parser.print_help()
        return

    if args.sample_size:
        print(required_sample_size(args.sample_size, args.confidence))

    if args.from_json:
        analyze_sweep(args.from_json, args.protagonist, args.confidence, args.n_assumed)

    if args.meta_ev:
        meta_ev_ci(args.meta_ev, args.protagonist, args.n_assumed, args.confidence)

    if args.live:
        proto, ant, n = args.live
        run_live_test(proto, ant, int(n), args.confidence)

    if args.compare:
        proto, a, b, n = args.compare
        run_live_comparison(proto, a, b, int(n), args.confidence)

    if args.integrity:
        a, b, n = args.integrity
        test_reciprocity(a, b, int(n), args.confidence)

    if args.play_draw:
        proto, ant, n = args.play_draw
        test_play_draw(proto, ant, int(n), args.confidence)

    if args.mulligan:
        proto, ant, n = args.mulligan
        test_mulligan_penalty(proto, ant, int(n), args.confidence)

    if args.archetype:
        test_archetype_dominance(args.archetype, args.confidence)

    if args.kill_turn:
        test_kill_turn(args.kill_turn, args.confidence)


if __name__ == '__main__':
    main()
