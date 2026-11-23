#!/usr/bin/env python3
"""Agentic OS vs AI OS — 24-month Monte Carlo for a 25-person knowledge-work team.

Decision
    (A) "AI OS path": bundled ambient assistants (Copilot+/Apple Intelligence/
        Gemini/ChatGPT Plus per seat). Humans still execute multi-step tasks.
    (B) "Agentic OS path": an agentic runtime (Claude Code / ChatGPT Agent /
        Devin-class per seat) executes multi-step tasks; humans review.

Everything runs through this repo's engine (`engine.simulate_with_samples`).
Both paths live in ONE spec so every trial draws shared inputs (wage, value
capture) once — a paired comparison, so P(B beats A) is meaningful.

Usage (from skills/monte-carlo-predictor/):
    python3 examples/agentic_vs_ai_os.py                 # full run + charts
    python3 examples/agentic_vs_ai_os.py --selfcheck     # negative controls only
    python3 examples/agentic_vs_ai_os.py --trials 50000 --seed 7

Outputs (repo-relative):
    docs/research/agentic-vs-ai-os-mc/*.png
    docs/research/agentic-vs-ai-os-mc/spec.json
    docs/research/agentic-vs-ai-os-mc/results.json

All inputs are ASSUMPTIONS (documented inline and in the write-up). Vendor
prices are list-price ranges as understood, not verified against vendor pages
in the run that produced the committed results.
"""
from __future__ import annotations

import argparse
import copy
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL_ROOT = os.path.dirname(HERE)
REPO_ROOT = os.path.dirname(os.path.dirname(SKILL_ROOT))
sys.path.insert(0, SKILL_ROOT)

from engine import simulate_with_samples  # noqa: E402

OUT_DIR = os.path.join(REPO_ROOT, "docs", "research", "agentic-vs-ai-os-mc")

TEAM = 25
MONTHS = 24
WORK_WEEKS_PER_YEAR = 46  # 52 minus holidays, PTO, sick days

# ---------------------------------------------------------------------------
# Inputs. Units: USD, hours, months. Per-seat costs are per month.
# ---------------------------------------------------------------------------
VARIABLES = {
    # ---- shared (same draw used by both paths in a trial) -----------------
    # Fully loaded cost of one knowledge-worker hour.
    "wage": {"distribution": "triangular", "low": 45, "likely": 65, "high": 110},
    # Share of saved hours that turn into real economic value (redeployed to
    # billable / higher-value work) rather than evaporating. Mean ~0.6.
    "value_capture": {"distribution": "beta", "alpha": 6, "beta": 4},

    # ---- Path A: AI OS (ambient assistant) --------------------------------
    "a_seat": {"distribution": "triangular", "low": 18, "likely": 25, "high": 35},
    "a_overage": {"distribution": "uniform", "low": 0, "high": 5},
    "a_setup": {"distribution": "triangular", "low": 1000, "likely": 3000, "high": 8000},
    # Gross hours saved / person / week once adopted (drafting, summarising, search).
    "a_hours": {"distribution": "triangular", "low": 0.5, "likely": 2.0, "high": 4.5},
    # Hours/person/week lost fixing assistant mistakes (human executes, so small).
    "a_rework": {"distribution": "triangular", "low": 0.05, "likely": 0.25, "high": 0.7},
    "a_ramp": {"distribution": "triangular", "low": 1, "likely": 2, "high": 4},
    "a_util": {"distribution": "beta", "alpha": 6, "beta": 4},  # mean 0.60

    # ---- Path B: Agentic OS (autonomous runtime + human review) -----------
    "b_seat": {"distribution": "triangular", "low": 40, "likely": 100, "high": 250},
    # Token/usage overage per ACTIVE seat per month; long right tail.
    # lognormal params are of the underlying normal: median = e^3.69 ≈ $40.
    "b_overage": {"distribution": "lognormal", "mean": 3.69, "stddev": 0.8},
    "b_setup": {"distribution": "triangular", "low": 5000, "likely": 20000, "high": 60000},
    # Gross hours of work delegated to the agent / person / week once adopted.
    "b_hours": {"distribution": "triangular", "low": 1.0, "likely": 5.0, "high": 12.0},
    # Gross human-hours of work in one delegated task. Tasks/week = hours / this.
    "b_task_hours": {"distribution": "triangular", "low": 0.15, "likely": 0.35, "high": 1.0},
    # Human review time as a share of the delegated gross hours.
    "b_review": {"distribution": "beta", "alpha": 3, "beta": 7},  # mean 0.30
    # Starting per-task bad-action rate (wrong edit, wrong send, broken output).
    # A bad task delivers NO saving and must be fixed (caught) or paid for (escaped).
    "b_error": {"distribution": "beta", "alpha": 2, "beta": 38},  # mean 0.05
    # Fractional reduction of the error rate by month 24 (model/tool progress).
    "b_reliab": {"distribution": "uniform", "low": 0.1, "high": 0.6},
    # Share of bad actions that slip past review and cause real damage.
    "b_escape": {"distribution": "beta", "alpha": 2, "beta": 8},  # mean 0.20
    # Hours to fix a bad action that review DID catch.
    "b_fix_hours": {"distribution": "triangular", "low": 0.25, "likely": 0.5, "high": 2.0},
    # Team-average $ cost of an ESCAPED bad action (median ≈ $150).
    "b_bad_cost": {"distribution": "lognormal", "mean": 5.0, "stddev": 0.8},
    # Baseline major-incident count over the horizon (leak, destructive action)
    # for a 25-person team at reference usage (0.5) and error rate (5%);
    # scaled in OUTCOMES by horizon, usage, team size and starting error rate.
    "b_incidents": {"distribution": "poisson", "lam": 0.3},
    "b_incident_cost": {"distribution": "lognormal", "mean": 9.6, "stddev": 1.0},  # median ≈ $15k
    "b_ramp": {"distribution": "triangular", "low": 2, "likely": 4, "high": 9},
    "b_util": {"distribution": "beta", "alpha": 5, "beta": 4},  # mean 0.56
}


def build_outcomes(team: int = TEAM, months: int = MONTHS) -> dict:
    """Outcome expressions.

    Linear adoption ramp over R months, horizon T: average adoption is
    1 - R/(2T) when R <= T, and T/(2R) when the ramp outlasts the horizon.
    Reliability gain is defined at month 24; a horizon of T months reaches
    gain*min(T/24, 1), and a linear path averages half of that.
    Incident rate is per 24 months for 25 people; scaled by T/24 and team/25."""
    weeks = months / 12 * WORK_WEEKS_PER_YEAR
    T = months
    h = min(months / 24, 1.0)

    def adopt(r):
        return f"(1 - min({r}, {T}) / {2 * T}) * ({r} <= {T}) + ({T} / (2 * {r})) * ({r} > {T})"

    return {
        "a_adopt": adopt("a_ramp"),
        "a_hours_net": f"{team} * {weeks} * a_adopt * a_util * max(a_hours - a_rework, 0)",
        "a_cost": f"{team} * {months} * (a_seat + a_overage) + a_setup",
        "a_value": "a_hours_net * wage * value_capture",
        "net_a": "a_value - a_cost",

        "b_adopt": adopt("b_ramp"),
        "b_active": f"{team} * {weeks} * b_adopt * b_util",           # active person-weeks
        "b_usage": "b_adopt * b_util",
        "b_err_avg": f"min(b_error * (1 - b_reliab * {h} / 2), 1)",
        "b_gross_hours": "b_active * b_hours",
        "b_tasks_total": "b_gross_hours / b_task_hours",
        "b_bad_actions": "b_tasks_total * b_err_avg",
        "b_escaped": "b_bad_actions * b_escape",
        # Delivered = gross hours of tasks that succeeded; review applies to all.
        "b_hours_net": ("b_gross_hours * (1 - b_err_avg) - b_gross_hours * b_review"
                        " - (b_bad_actions - b_escaped) * b_fix_hours"),
        "b_incident_n": f"b_incidents * {h} * ({team} / 25) * (b_usage / 0.5) * (b_error / 0.05)",
        "b_cost": (f"{team} * {months} * b_seat + {team} * {months} * b_usage * b_overage"
                   " + b_setup + b_escaped * b_bad_cost + b_incident_n * b_incident_cost"),
        "b_value": "b_hours_net * wage * value_capture",
        "net_b": "b_value - b_cost",

        "diff_b_minus_a": "net_b - net_a",
        "b_beats_a": "diff_b_minus_a > 0",
        "a_positive": "net_a > 0",
        "b_positive": "net_b > 0",
    }


HEADLINE = ["a_cost", "a_value", "net_a", "b_cost", "b_value", "net_b", "diff_b_minus_a"]


def build_spec(trials: int, seed: int, overrides: dict | None = None,
               team: int = TEAM, months: int = MONTHS) -> dict:
    spec = {"trials": trials, "seed": seed,
            "variables": copy.deepcopy(VARIABLES), "outcomes": build_outcomes(team, months)}
    for k, v in (overrides or {}).items():
        spec["variables"][k] = {"distribution": "constant", "value": v}
    return spec


def run(trials: int, seed: int, overrides: dict | None = None, team: int = TEAM, months: int = MONTHS):
    return simulate_with_samples(build_spec(trials, seed, overrides, team, months))


def p_win(trials, seed, overrides=None, **kw) -> float:
    rep, _, _ = run(trials, seed, overrides, **kw)
    return rep["outcomes"]["b_beats_a"]["probability_true"]


# ---------------------------------------------------------------------------
# Negative controls: the model MUST flip when fed known-bad / known-good inputs.
# Every control pins values INSIDE the priors, and the error-rate controls hold
# hours, usage and review at favourable values so only the error rate can act.
# ---------------------------------------------------------------------------
GOOD = {"b_hours": 12.0, "b_util": 0.8, "b_review": 0.2}


def selfcheck(trials: int = 5000, seed: int = 1) -> bool:
    ok = True

    def report(label, passed, detail):
        nonlocal ok
        ok &= passed
        print(f"  [{'PASS' if passed else 'FAIL'}] {label}: {detail}")

    p = p_win(trials, seed, {**GOOD, "b_error": 0.0})
    report("12 hr/wk, 80% use, 20% review, 0% errors → B must win (P > 0.95)", p > 0.95, f"P = {p:.3f}")
    p = p_win(trials, seed, {**GOOD, "b_error": 0.40})
    report("same, but 40% bad-action rate → B must lose (P < 0.05)", p < 0.05, f"P = {p:.3f}")
    p = p_win(trials, seed, {"b_hours": 0.0})
    report("agent saves 0 hours → B must lose (P < 0.01)", p < 0.01, f"P = {p:.3f}")
    ps = [p_win(trials, seed, {**GOOD, "b_hours": 7.0, "b_error": e}) for e in (0.0, 0.05, 0.12, 0.25)]
    mono = all(a > b for a, b in zip(ps, ps[1:])) and ps[0] - ps[-1] > 0.3
    report("P(B wins) falls strictly with error rate, by > 30 pts over 0→25%", mono,
           " → ".join(f"{x:.2f}" for x in ps))
    return ok


# ---------------------------------------------------------------------------
# Sensitivity sweep on the two decision drivers.
# ---------------------------------------------------------------------------
ERR_GRID = [0.0, 0.02, 0.05, 0.08, 0.12, 0.18, 0.25]
HRS_GRID = [1, 2, 3, 5, 7, 10, 14]


def sweep(trials: int, seed: int, fixed: dict | None = None):
    p_tab, med = [], []
    for e in ERR_GRID:
        row_p, row_m = [], []
        for h in HRS_GRID:
            rep, _, _ = run(trials, seed, {**(fixed or {}), "b_error": e, "b_hours": h})
            row_p.append(rep["outcomes"]["b_beats_a"]["probability_true"])
            row_m.append(rep["outcomes"]["diff_b_minus_a"]["stats"]["p50"])
        p_tab.append(row_p)
        med.append(row_m)
    return p_tab, med


# Pilot-gate thresholds: with usage and review AT the gate values (not the
# default priors), how many agent hours/week are needed for P(B beats A) ≥ 70%?
GATE_FIXED = {"b_util": 0.7, "b_review": 0.3}
GATE_HOURS = [3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 14, 16]
GATE_ERRORS = [0.02, 0.05, 0.10]


def gate_table(trials: int, seed: int):
    out = {}
    for e in GATE_ERRORS:
        row = [(h, p_win(trials, seed, {**GATE_FIXED, "b_error": e, "b_hours": h})) for h in GATE_HOURS]
        need = next((h for h, p in row if p >= 0.70), None)
        out[e] = {"curve": row, "hours_for_p70": need}
    return out


def pilot(trials: int, seed: int, team: int = 5, months: int = 3):
    """Cost of a small time-boxed pilot. Its job is to buy information, so we
    report its cash outlay and net, not whether it 'beats' A at that scale."""
    rep, _, _ = run(trials, seed, None, team=team, months=months)
    o = rep["outcomes"]
    return {"team": team, "months": months,
            "b_cost": o["b_cost"]["stats"], "net_b": o["net_b"]["stats"],
            "p_b_positive": o["b_positive"]["probability_true"]}


# ---------------------------------------------------------------------------
# Charts
# ---------------------------------------------------------------------------
def charts(report, out_s, p_tab, med):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np
    from engine.visualize import save_matplotlib_charts

    os.makedirs(OUT_DIR, exist_ok=True)
    saved = []
    keys = ["net_a", "net_b", "diff_b_minus_a"]
    saved += save_matplotlib_charts(report, {k: out_s[k] for k in keys}, OUT_DIR)

    k = 1000.0
    a = np.asarray(out_s["net_a"]) / k
    b = np.asarray(out_s["net_b"]) / k
    lo, hi = np.percentile(np.concatenate([a, b]), [0.5, 99.5])
    bins = np.linspace(lo, hi, 80)
    fig, ax = plt.subplots(figsize=(9, 4.5))
    ax.hist(a, bins=bins, alpha=0.6, color="#4a90d9", label="A: AI OS (ambient)")
    ax.hist(b, bins=bins, alpha=0.6, color="#d9822b", label="B: Agentic OS")
    for arr, c in ((a, "#1f5fa8"), (b, "#a85410")):
        ax.axvline(np.median(arr), color=c, linestyle="--", linewidth=1.2)
    ax.axvline(0, color="black", linewidth=0.8)
    ax.set_xlabel("24-month net benefit ($k)  — dashed = median")
    ax.set_ylabel("Trials")
    ax.set_title(f"Net benefit, 25 people × 24 months ({report['trials']:,} trials)")
    ax.legend()
    p = os.path.join(OUT_DIR, "overlay_net_a_vs_b.png")
    fig.savefig(p, dpi=130, bbox_inches="tight"); plt.close(fig); saved.append(p)

    for name, data, fmt, title in (
        ("sweep_p_b_wins.png", np.asarray(p_tab), "{:.0%}",
         "P(B beats A) vs agent error rate × hours delegated"),
        ("sweep_median_diff.png", np.asarray(med) / k, "{:+.0f}",
         "Median (B − A) net benefit, $k"),
    ):
        fig, ax = plt.subplots(figsize=(8, 5.2))
        if name.startswith("sweep_p"):
            im = ax.imshow(data, cmap="RdYlGn", vmin=0, vmax=1, aspect="auto")
        else:
            v = np.max(np.abs(data))
            im = ax.imshow(data, cmap="RdYlGn", vmin=-v, vmax=v, aspect="auto")
        ax.set_xticks(range(len(HRS_GRID)), [str(h) for h in HRS_GRID])
        ax.set_yticks(range(len(ERR_GRID)), [f"{e:.0%}" for e in ERR_GRID])
        ax.set_xlabel("Agent gross hours delegated / person / week")
        ax.set_ylabel("Agent starting bad-action rate per task")
        ax.set_title(title)
        for i in range(len(ERR_GRID)):
            for j in range(len(HRS_GRID)):
                ax.text(j, i, fmt.format(data[i, j]), ha="center", va="center", fontsize=8)
        fig.colorbar(im, ax=ax)
        p = os.path.join(OUT_DIR, name)
        fig.savefig(p, dpi=130, bbox_inches="tight"); plt.close(fig); saved.append(p)
    return saved


def fmt_money(x):
    return f"${x/1000:,.0f}k" if abs(x) >= 1000 else f"${x:,.0f}"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--trials", type=int, default=20000)
    ap.add_argument("--sweep-trials", type=int, default=10000)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--selfcheck", action="store_true", help="run negative controls only")
    ap.add_argument("--no-charts", action="store_true")
    args = ap.parse_args(argv)

    print("Negative controls:")
    if not selfcheck():
        print("SELFCHECK FAILED — model does not respond correctly to known inputs.")
        return 1
    if args.selfcheck:
        return 0

    report, _, out_s = run(args.trials, args.seed)
    o = report["outcomes"]
    print(f"\nBase case: {args.trials:,} trials, seed {args.seed}, "
          f"{TEAM} people, {MONTHS} months, {WORK_WEEKS_PER_YEAR} work weeks/yr")
    print(f"{'outcome':<16}{'P5':>12}{'P50':>12}{'mean':>12}{'P95':>12}")
    for k in HEADLINE:
        s = o[k]["stats"]
        print(f"{k:<16}{fmt_money(s['p5']):>12}{fmt_money(s['p50']):>12}"
              f"{fmt_money(s['mean']):>12}{fmt_money(s['p95']):>12}")
    for k in ("b_beats_a", "a_positive", "b_positive"):
        print(f"P({k}) = {o[k]['probability_true']:.3f}")
    print("\nTornado on B − A (top 10):")
    for t in o["diff_b_minus_a"]["tornado"][:10]:
        print(f"  {t['variable']:<16}{t['correlation']:+.3f}  {t['impact']}")

    print(f"\nSweep: {len(ERR_GRID)}×{len(HRS_GRID)} grid, {args.sweep_trials:,} trials per cell")
    p_tab, med = sweep(args.sweep_trials, args.seed)
    print("P(B beats A); rows = error rate, cols = hours/wk " + str(HRS_GRID))
    for e, row in zip(ERR_GRID, p_tab):
        print(f"  {e:>5.0%} " + " ".join(f"{x:5.0%}" for x in row))

    print(f"\nGate table (usage {GATE_FIXED['b_util']:.0%}, review {GATE_FIXED['b_review']:.0%} pinned):")
    gates = gate_table(args.sweep_trials, args.seed)
    for e, g in gates.items():
        curve = " ".join(f"{h}h:{p:.0%}" for h, p in g["curve"])
        print(f"  error {e:.0%}: hours for P≥70% = {g['hours_for_p70']}   [{curve}]")

    pil = pilot(args.trials, args.seed)
    print(f"\nPilot ({pil['team']} people × {pil['months']} months, full setup cost):")
    print(f"  B cost P5/P50/P95 = {fmt_money(pil['b_cost']['p5'])} / {fmt_money(pil['b_cost']['p50'])}"
          f" / {fmt_money(pil['b_cost']['p95'])}")
    print(f"  B net  P5/P50/P95 = {fmt_money(pil['net_b']['p5'])} / {fmt_money(pil['net_b']['p50'])}"
          f" / {fmt_money(pil['net_b']['p95'])};  P(net > 0) = {pil['p_b_positive']:.3f}")
    small, _, _ = run(args.trials, args.seed, None, team=5, months=MONTHS)
    so = small["outcomes"]
    print(f"  5 people × 24 months: P(B beats A) = {so['b_beats_a']['probability_true']:.3f}, "
          f"P(B net > 0) = {so['b_positive']['probability_true']:.3f}, "
          f"median net B = {fmt_money(so['net_b']['stats']['p50'])}")

    os.makedirs(OUT_DIR, exist_ok=True)
    with open(os.path.join(OUT_DIR, "spec.json"), "w") as f:
        json.dump(build_spec(args.trials, args.seed), f, indent=2)
    with open(os.path.join(OUT_DIR, "results.json"), "w") as f:
        json.dump({"report": report,
                   "sweep": {"error_grid": ERR_GRID, "hours_grid": HRS_GRID,
                             "p_b_beats_a": p_tab, "median_diff": med,
                             "trials_per_cell": args.sweep_trials},
                   "gates": {"fixed": GATE_FIXED,
                             "by_error": {str(e): g for e, g in gates.items()}},
                   "pilot_5x3": pil,
                   "small_team_5x24": {"p_b_beats_a": so["b_beats_a"]["probability_true"],
                                       "p_b_positive": so["b_positive"]["probability_true"],
                                       "net_b": so["net_b"]["stats"]}}, f, indent=2)
    if not args.no_charts:
        for p in charts(report, out_s, p_tab, med):
            print("chart:", os.path.relpath(p, REPO_ROOT))
    return 0


if __name__ == "__main__":
    sys.exit(main())
