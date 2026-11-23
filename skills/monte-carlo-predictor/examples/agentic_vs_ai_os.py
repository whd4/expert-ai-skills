#!/usr/bin/env python3
"""Agentic OS vs AI OS — 24-month Monte Carlo for a 25-person knowledge-work team.

Options compared (all paired inside ONE engine spec, so every trial shares draws):
    (A)   "AI OS":      ambient assistant seat for everyone; humans execute tasks.
    (B)   "Agentic OS": agentic-runtime seat for everyone; agent executes, humans review.
    (C_k) "Mix":        A for everyone + k agentic seats (C_K_GRID). Seats go to the
                        team's genuine power users first (p_count of them), then to
                        ordinary users — so returns diminish as k grows.

Also computes:
    * sensitivity sweep (agent error rate × hours delegated) for B;
    * scale-up gates for the Mix, in pilot-observable units;
    * a 3-month power-user pilot: its cost, and the value of what it can learn:
        EVPI  — perfect information on every input (ceiling),
        EVPPI — perfect information on the pilot-measurable inputs (ceiling),
        EVSI  — the pilot's actual, NOISY measurements (decision-relevant number).

Inputs are anchored to published evidence where it exists (EVIDENCE below and
docs/research/agentic-vs-ai-os-monte-carlo.md). Everything else is an assumption.

Usage (from skills/monte-carlo-predictor/):
    python3 examples/agentic_vs_ai_os.py                 # full run + charts
    python3 examples/agentic_vs_ai_os.py --selfcheck     # negative controls only
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
WORK_WEEKS_PER_YEAR = 46          # 52 minus holidays, PTO, sick days
C_K_GRID = [1, 2, 3, 5, 8, 12, 18, 25]   # agent seats tested in the Mix option (25 = everyone)
SETUP_FIXED_SHARE = 0.4           # share of rollout setup that does not shrink with seats
PILOT_SEATS = 3
PILOT_MONTHS = 3
PILOT_SETUP_SHARE = 0.15          # lean pilot: accounts + guardrails, no integrations
ERROR_REF = 0.20                  # incident rate λ is defined at this (prior-mean) error rate

EVIDENCE = {
    "a_hours": [
        "HMRC Copilot Phase III (randomised over 3,000 licences): ~60 min/week per licence "
        "holder, already discounted ~20% for non-use — gov.uk, 2026-07-09",
        "DWP M365 Copilot trial (3,549 staff, regression): 19 min/day ≈ 1.6 h/wk — gov.uk, 2026-01-29",
        "GDS cross-government trial (20,000 staff): 26 min/day ≈ 2.2 h/wk, self-reported — gov.uk, 2025-06-02",
    ],
    "b_error": [
        "TheAgentCompany (NeurIPS 2025): best agent completes 30% of workplace tasks autonomously",
        "OfficeEval (Microsoft Research, 2026-06): best coding agent 68.8% rubric score (not a task-success rate)",
        "Workspace-Bench (2026): agent mean 45.1% rubric pass vs 80.7% human+tool (rubric, not task-success)",
    ],
    "b_hours": [
        "METR RCT (2025-07): experienced devs 19% SLOWER with AI while believing 20% faster",
        "METR follow-up (2026-02-24): -18% / -4% speedup, CIs include zero; self-reports unreliable",
        "=> no reliable measurement exists; this prior is an assumption",
    ],
    "prices": [
        "Microsoft 365 Copilot Business add-on $21/user/mo ($18 promo) — microsoft.com",
        "Claude Team premium seat $100 (annual) / $125 (monthly) — support.claude.com",
        "Devin Teams $80/mo minimum + usage; Claude Max $100-200 — devin.ai, claude.com",
    ],
}

# ---------------------------------------------------------------------------
# Inputs. Units: USD, hours, months. Per-seat costs are per month.
# ---------------------------------------------------------------------------
VARIABLES = {
    # ---- shared ------------------------------------------------------------
    "wage": {"distribution": "triangular", "low": 45, "likely": 65, "high": 110},
    "value_capture": {"distribution": "beta", "alpha": 6, "beta": 4},          # mean 0.60

    # ---- A: ambient assistant ----------------------------------------------
    "a_seat": {"distribution": "triangular", "low": 18, "likely": 21, "high": 32},
    "a_overage": {"distribution": "uniform", "low": 0, "high": 5},
    "a_setup": {"distribution": "triangular", "low": 1000, "likely": 3000, "high": 8000},
    # Net hours saved per LICENCE HOLDER per week at steady state. The trials already
    # average over light and non-users, so no separate seat-use discount is applied.
    "a_hours": {"distribution": "triangular", "low": 0.5, "likely": 1.1, "high": 2.2},
    # Hours/week lost fixing assistant mistakes (absolute hours, small: human executes).
    "a_rework": {"distribution": "triangular", "low": 0.0, "likely": 0.05, "high": 0.2},
    "a_ramp": {"distribution": "triangular", "low": 1, "likely": 2, "high": 4},

    # ---- agentic runtime (B and the agent part of C) --------------------------
    "b_seat": {"distribution": "triangular", "low": 80, "likely": 100, "high": 200},
    "b_overage": {"distribution": "lognormal", "mean": 3.69, "stddev": 0.8},     # median ≈ $40
    "b_setup": {"distribution": "triangular", "low": 5000, "likely": 20000, "high": 60000},
    # UNMEASURED. Gross hours an ORDINARY user delegates / week while active.
    "b_hours": {"distribution": "triangular", "low": 1.0, "likely": 4.0, "high": 10.0},
    "b_task_hours": {"distribution": "triangular", "low": 0.15, "likely": 0.35, "high": 1.0},
    "b_review": {"distribution": "beta", "alpha": 3, "beta": 7},                 # mean 0.30
    # Benchmarks: best agents complete ~30-70% of realistic office tasks unsupervised.
    # Delegated tasks are chosen and scoped by people, so the bad-action rate is set
    # between the 15% floor and the ~25% midpoint of "half the benchmark failure".
    "b_error": {"distribution": "beta", "alpha": 4, "beta": 16},                 # mean 0.20
    "b_reliab": {"distribution": "uniform", "low": 0.1, "high": 0.6},
    "b_escape": {"distribution": "beta", "alpha": 2, "beta": 8},                 # mean 0.20
    "b_fix_hours": {"distribution": "triangular", "low": 0.25, "likely": 0.5, "high": 2.0},
    "b_bad_cost": {"distribution": "lognormal", "mean": 5.0, "stddev": 0.8},     # median ≈ $150
    # Major incidents per 24 months for 25 seats at reference usage 0.5 and error 20%.
    "b_incidents": {"distribution": "poisson", "lam": 0.3},
    "b_incident_cost": {"distribution": "lognormal", "mean": 9.6, "stddev": 1.0},
    "b_ramp": {"distribution": "triangular", "low": 2, "likely": 4, "high": 9},
    "b_util": {"distribution": "beta", "alpha": 5, "beta": 4},                   # mean 0.56

    # ---- power users -------------------------------------------------------
    # Genuine power users in a 25-person team (continuous = expected count).
    "p_count": {"distribution": "triangular", "low": 1, "likely": 3, "high": 6},
    "p_util": {"distribution": "beta", "alpha": 8, "beta": 2},                   # mean 0.80
    # Power users delegate this multiple of an ordinary user's hours (mean ≈ 1.67).
    "p_hours_mult": {"distribution": "triangular", "low": 1.0, "likely": 1.5, "high": 2.5},
    # Share of ANY agent seat-holder's assistant saving that the agent displaces (same work).
    "p_overlap": {"distribution": "uniform", "low": 0.3, "high": 0.8},
}


def _adopt(r: str, T: int) -> str:
    """Average adoption under a linear ramp of R months over a T-month horizon."""
    return f"((1 - min({r}, {T}) / {2 * T}) * ({r} <= {T}) + ({T} / (2 * {r})) * ({r} > {T}))"


def _agent_block(p: str, seats, months: int, setup_share) -> dict:
    """Outcome expressions for `seats` agent seats over `months` (prefix p).
    Seats go to genuine power users first, ordinary users after."""
    weeks = months / 12 * WORK_WEEKS_PER_YEAR
    h = min(months / 24, 1.0)
    return {
        f"{p}adopt": _adopt("b_ramp", months),
        f"{p}pu": f"min({seats}, p_count)",                          # power-user seats
        f"{p}ou": f"max({seats} - p_count, 0)",                       # ordinary-user seats
        f"{p}usage": f"{p}adopt * ({p}pu * p_util + {p}ou * b_util) / {seats}",
        f"{p}gross": (f"{weeks} * {p}adopt * b_hours"
                      f" * ({p}pu * p_util * p_hours_mult + {p}ou * b_util)"),
        f"{p}err": f"min(b_error * (1 - b_reliab * {h} / 2), 1)",
        f"{p}tasks": f"{p}gross / b_task_hours",
        f"{p}bad": f"{p}tasks * {p}err",
        f"{p}escaped": f"{p}bad * b_escape",
        f"{p}hours_net": (f"{p}gross * (1 - {p}err) - {p}gross * b_review"
                          f" - ({p}bad - {p}escaped) * b_fix_hours"),
        f"{p}incidents": (f"b_incidents * {h} * ({seats} / 25) * ({p}usage / 0.5)"
                          f" * (b_error / {ERROR_REF})"),
        f"{p}cost": (f"{seats} * {months} * b_seat + {seats} * {months} * {p}usage * b_overage"
                     f" + b_setup * {setup_share} + {p}escaped * b_bad_cost"
                     f" + {p}incidents * b_incident_cost"),
        f"{p}value": f"{p}hours_net * wage * value_capture",
        # Assistant value displaced for the seat-holders (they keep their A seat).
        f"{p}overlap": f"{seats} * a_hours_pp * p_overlap * {p}usage * wage * value_capture",
    }


def _rollout_setup(seats) -> float:
    return SETUP_FIXED_SHARE + (1 - SETUP_FIXED_SHARE) * seats / TEAM


def build_outcomes(team: int = TEAM, months: int = MONTHS, k_grid=None, pilot: bool = True) -> dict:
    weeks = months / 12 * WORK_WEEKS_PER_YEAR
    k_grid = C_K_GRID if k_grid is None else k_grid
    out = {
        "a_adopt": _adopt("a_ramp", months),
        "a_hours_pp": f"{weeks} * a_adopt * max(a_hours - a_rework, 0)",     # per person
        "a_cost": f"{team} * {months} * (a_seat + a_overage) + a_setup",
        "a_value": f"{team} * a_hours_pp * wage * value_capture",
        "net_a": "a_value - a_cost",
    }
    # B: every seat is an agent seat; A is NOT kept, so no overlap term.
    out.update(_agent_block("b_", team, months, _rollout_setup(team)))
    out["net_b"] = "b_value - b_cost"
    # C_k: keep A for everyone, add k agent seats, remove displaced A value.
    for k in k_grid:
        if k > team:
            continue
        p = f"c{k}_"
        out.update(_agent_block(p, k, months, _rollout_setup(k)))
        out[f"net_c{k}"] = f"net_a + {p}value - {p}cost - {p}overlap"
        out[f"c{k}_beats_a"] = f"net_c{k} > net_a"
    if pilot:
        # Lean pilot: PILOT_SEATS power-user seats for PILOT_MONTHS, on top of A.
        out.update(_agent_block("pil_", PILOT_SEATS, PILOT_MONTHS, PILOT_SETUP_SHARE))
        out["pilot_net"] = "pil_value - pil_cost - pil_overlap"
    out["diff_b_minus_a"] = "net_b - net_a"
    out["b_beats_a"] = "diff_b_minus_a > 0"
    out["a_positive"] = "net_a > 0"
    out["b_positive"] = "net_b > 0"
    return out


HEADLINE = ["a_cost", "a_value", "net_a", "b_cost", "b_value", "net_b", "diff_b_minus_a"]


def build_spec(trials, seed, overrides=None, team=TEAM, months=MONTHS, k_grid=None, pilot=True) -> dict:
    spec = {"trials": trials, "seed": seed, "variables": copy.deepcopy(VARIABLES),
            "outcomes": build_outcomes(team, months, k_grid, pilot)}
    for k, v in (overrides or {}).items():
        spec["variables"][k] = {"distribution": "constant", "value": v}
    return spec


TRIAL_COUNT = {"n": 0}


def run(trials, seed, overrides=None, team=TEAM, months=MONTHS, k_grid=None, pilot=True):
    TRIAL_COUNT["n"] += trials
    return simulate_with_samples(build_spec(trials, seed, overrides, team, months, k_grid, pilot))


def p_win(trials, seed, overrides=None, **kw) -> float:
    rep, _, _ = run(trials, seed, overrides, k_grid=[], pilot=False, **kw)
    return rep["outcomes"]["b_beats_a"]["probability_true"]


# ---------------------------------------------------------------------------
# Value of information. Decision = option with the highest mean net.
#   EVPI  = E[max_d net_d] − max_d E[net_d]
#   EV(P/S)I = E[max_d E[net_d | signal]] − max_d E[net_d]
# E[net_d | signal] by quadratic regression on the signal (regression-based
# EVPPI/EVSI; Strong, Oakley & Brennan 2014; Strong et al. 2015).
# ---------------------------------------------------------------------------
def _quad_features(cols):
    import numpy as np
    X = np.column_stack(cols).astype(float)
    X = (X - X.mean(axis=0)) / np.where(X.std(axis=0) > 0, X.std(axis=0), 1)
    feats = [np.ones(len(X))] + [X[:, i] for i in range(X.shape[1])]
    for i in range(X.shape[1]):
        for j in range(i, X.shape[1]):
            feats.append(X[:, i] * X[:, j])
    return np.column_stack(feats)


def _ev_given(nets, F):
    import numpy as np
    fitted = np.column_stack([F @ np.linalg.lstsq(F, nets[:, d], rcond=None)[0]
                              for d in range(nets.shape[1])])
    return float(np.mean(fitted.max(axis=1)) - nets.mean(axis=0).max()), fitted.argmax(axis=1)


def pilot_signals(var_s, out_s, rng):
    """What a 3-seat, 3-month power-user pilot actually observes, with noise.
    - bad-action rate: Binomial(tasks observed, true pilot error rate) / tasks
    - power-user hours delegated / week while active: true value × lognormal(σ=0.25)
    - review share: true + N(0, 0.05);  power-user seat use: true + N(0, 0.08)"""
    import numpy as np
    n = np.maximum(np.round(np.asarray(out_s["pil_tasks"], dtype=float)), 0).astype(int)
    err = np.clip(np.asarray(out_s["pil_err"], dtype=float), 0, 1)
    obs_err = rng.binomial(n, err) / np.maximum(n, 1)
    pu_hours = np.asarray(var_s["b_hours"]) * np.asarray(var_s["p_hours_mult"])
    obs_hours = pu_hours * np.exp(rng.normal(0, 0.25, len(n)))
    obs_review = np.asarray(var_s["b_review"]) + rng.normal(0, 0.05, len(n))
    obs_use = np.asarray(var_s["p_util"]) + rng.normal(0, 0.08, len(n))
    return {"obs_err": obs_err, "obs_hours": obs_hours, "obs_review": obs_review,
            "obs_use": obs_use, "tasks": n}


def value_of_information(var_s, out_s, options, seed=0):
    import numpy as np
    nets = np.column_stack([np.asarray(out_s[o], dtype=float) for o in options])
    means = nets.mean(axis=0)
    evpi = float(np.mean(nets.max(axis=1)) - means.max())
    pu_hours = np.asarray(var_s["b_hours"]) * np.asarray(var_s["p_hours_mult"])
    true_cols = [np.asarray(var_s["b_error"]), pu_hours,
                 np.asarray(var_s["b_review"]), np.asarray(var_s["p_util"])]
    evppi, _ = _ev_given(nets, _quad_features(true_cols))
    sig = pilot_signals(var_s, out_s, np.random.default_rng(seed))
    evsi, pick = _ev_given(nets, _quad_features([sig["obs_err"], sig["obs_hours"],
                                                 sig["obs_review"], sig["obs_use"]]))
    counts = {options[i]: float(np.mean(pick == i)) for i in range(len(options))}
    return {"options": options, "mean_net": dict(zip(options, map(float, means))),
            "best_option": options[int(means.argmax())], "evpi": evpi,
            "evppi_pilot_params": evppi, "evsi_pilot": evsi,
            "post_pilot_choice_share": counts,
            "pilot_tasks_median": float(np.median(sig["tasks"]))}


# ---------------------------------------------------------------------------
# Negative controls (exit non-zero on failure). Labels say what is pinned and
# whether a pin lies outside the prior.
# ---------------------------------------------------------------------------
GOOD = {"b_hours": 10.0, "b_util": 0.8, "b_review": 0.2}


def selfcheck(trials: int = 5000, seed: int = 1) -> bool:
    import numpy as np
    ok = True

    def report(label, passed, detail):
        nonlocal ok
        ok &= passed
        print(f"  [{'PASS' if passed else 'FAIL'}] {label}: {detail}")

    p = p_win(trials, seed, {**GOOD, "b_error": 0.0})
    report("10 h/wk, 80% use, 20% review, 0% errors → B must win (P > 0.95)", p > 0.95, f"P = {p:.3f}")
    p = p_win(trials, seed, {**GOOD, "b_error": 0.40})
    report("same, 40% bad-action rate (prior tail) → B must lose (P < 0.05)", p < 0.05, f"P = {p:.3f}")
    ps = [p_win(trials, seed, {**GOOD, "b_hours": 6.0, "b_error": e}) for e in (0.0, 0.05, 0.12, 0.25)]
    mono = all(a > b for a, b in zip(ps, ps[1:])) and ps[0] - ps[-1] > 0.3
    report("P(B wins) falls strictly with error rate, by > 30 pts", mono, " → ".join(f"{x:.2f}" for x in ps))

    # Overlap term: identical draws, overlap 0 vs 1 → C gain must fall by exactly the
    # analytic displaced value. Fails if the sign or units of the overlap term are wrong.
    base = {"b_error": 0.05, "b_hours": 6.0}
    r0, _, o0 = run(trials, seed, {**base, "p_overlap": 0.0}, k_grid=[3], pilot=False)
    r1v, v1, o1 = run(trials, seed, {**base, "p_overlap": 1.0}, k_grid=[3], pilot=False)
    drop = np.asarray(o0["net_c3"]) - np.asarray(o1["net_c3"])
    # Independent recomputation from first principles (units: h/person × seats × use × $/h × capture).
    weeks = MONTHS / 12 * WORK_WEEKS_PER_YEAR
    a_hrs = weeks * np.asarray(o1["a_adopt"]) * np.maximum(np.asarray(v1["a_hours"]) - np.asarray(v1["a_rework"]), 0)
    expect = 3 * a_hrs * np.asarray(o1["c3_usage"]) * np.asarray(v1["wage"]) * np.asarray(v1["value_capture"])
    good = np.all(drop >= 0) and np.allclose(drop, expect, rtol=1e-9, atol=1e-6) and \
        r0["outcomes"]["c3_beats_a"]["probability_true"] > r1v["outcomes"]["c3_beats_a"]["probability_true"]
    report("Overlap 0 → 1 lowers C by the independently recomputed displaced A value", good,
           f"mean drop ${drop.mean():,.0f}; P {r0['outcomes']['c3_beats_a']['probability_true']:.3f}"
           f" → {r1v['outcomes']['c3_beats_a']['probability_true']:.3f}")

    # Diminishing returns: with 2 power users, the MARGINAL gain of a power-user seat
    # (k 1→2) must be far above that of an ordinary-user seat (k 2→5, 5→12). Average
    # gain per seat is not the right test: it also reflects fixed setup being amortised.
    rep, _, o = run(trials, seed, {**base, "p_count": 2.0}, k_grid=[1, 2, 5, 12], pilot=False)
    na = np.asarray(o["net_a"])
    G = {k: float((np.asarray(o[f"net_c{k}"]) - na).mean()) for k in (1, 2, 5, 12)}
    m_pu, m_ou1, m_ou2 = G[2] - G[1], (G[5] - G[2]) / 3, (G[12] - G[5]) / 7
    dim = m_pu > 3 * max(m_ou1, m_ou2)
    report("Marginal gain: power-user seat > 3× ordinary-user seat", dim,
           f"${m_pu:,.0f} vs ${m_ou1:,.0f} / ${m_ou2:,.0f} per seat")

    # Mix with an excellent agent must beat A.
    rep, _, _ = run(trials, seed, {"b_hours": 8.0, "b_error": 0.0, "b_review": 0.2}, k_grid=[3], pilot=False)
    p = rep["outcomes"]["c3_beats_a"]["probability_true"]
    report("Mix with excellent agent (0% err, 20% review) → C must beat A (P > 0.9)", p > 0.9, f"P = {p:.3f}")

    # Value-of-information ordering on raw (unclipped) estimates.
    rep, vs, os_ = run(trials, seed, k_grid=[2, 3])
    v = value_of_information(vs, os_, ["net_a", "net_c2", "net_c3"], seed=seed)
    tol = 0.02 * max(v["evpi"], 1)
    good = v["evpi"] + tol >= v["evppi_pilot_params"] and v["evppi_pilot_params"] + tol >= v["evsi_pilot"] \
        and v["evsi_pilot"] > -tol
    report("EVPI ≥ EVPPI ≥ EVSI ≥ 0 (raw estimates)", good,
           f"${v['evpi']:,.0f} ≥ ${v['evppi_pilot_params']:,.0f} ≥ ${v['evsi_pilot']:,.0f}")
    return ok


# ---------------------------------------------------------------------------
# Sweep (B), Mix gates (observable units), pilot.
# ---------------------------------------------------------------------------
ERR_GRID = [0.0, 0.02, 0.05, 0.08, 0.12, 0.18, 0.25]
HRS_GRID = [1, 2, 3, 5, 7, 10, 14]
GATE_PU_HOURS = [3, 4, 5, 6, 7, 8, 10, 12, 14, 16]
GATE_ERRORS = [0.02, 0.05, 0.10, 0.20]
MULT_MEAN = (1.0 + 1.5 + 2.5) / 3


def sweep(trials, seed):
    p_tab, med = [], []
    for e in ERR_GRID:
        row_p, row_m = [], []
        for h in HRS_GRID:
            rep, _, _ = run(trials, seed, {"b_error": e, "b_hours": h}, k_grid=[], pilot=False)
            row_p.append(rep["outcomes"]["b_beats_a"]["probability_true"])
            row_m.append(rep["outcomes"]["diff_b_minus_a"]["stats"]["p50"])
        p_tab.append(row_p)
        med.append(row_m)
    return p_tab, med


def mix_gates(trials, seed):
    """Gates in what a pilot observes: hours delegated per power user per week (while
    active) and bad-action rate. Pins p_hours_mult at its mean and b_hours so that power
    users delegate exactly h; review pinned at 30%. Seat count chosen by expected value
    (same rule as the main decision); reports P(that C beats A)."""
    import numpy as np
    out = {}
    for e in GATE_ERRORS:
        row = []
        for h in GATE_PU_HOURS:
            ov = {"b_review": 0.3, "b_error": e, "p_hours_mult": MULT_MEAN, "b_hours": h / MULT_MEAN}
            rep, _, o = run(trials, seed, ov, pilot=False)
            na = np.asarray(o["net_a"])
            gains = {k: float((np.asarray(o[f"net_c{k}"]) - na).mean()) for k in C_K_GRID}
            k_star = max(gains, key=gains.get)
            if gains[k_star] <= 0:
                best_p = max(rep["outcomes"][f"c{k}_beats_a"]["probability_true"] for k in C_K_GRID)
                row.append({"h": h, "k": 0, "p": best_p, "mean_gain": gains[k_star]})
            else:
                row.append({"h": h, "k": k_star, "mean_gain": gains[k_star],
                            "p": rep["outcomes"][f"c{k_star}_beats_a"]["probability_true"]})
        gate = next((r for r in row if r["k"] > 0 and r["p"] >= 0.70), None)
        out[e] = {"curve": row, "gate": gate}
    return out


PRIOR_MEANS = [0.05, 0.08, 0.10, 0.12, 0.15, 0.20]


def error_prior_sensitivity(trials, seed):
    """Re-run the decision and the pilot value under different BELIEFS about the agent
    bad-action rate (beta(4, 4/m − 4), mean m). The error prior is the #1 driver and a
    judgement call, so the verdicts are reported as a function of it."""
    import numpy as np
    rows = []
    options = ["net_a", "net_b"] + [f"net_c{k}" for k in C_K_GRID]
    for m in PRIOR_MEANS:
        spec = build_spec(trials, seed)
        spec["variables"]["b_error"] = {"distribution": "beta", "alpha": 4, "beta": 4 / m - 4}
        TRIAL_COUNT["n"] += trials
        rep, vs, os_ = simulate_with_samples(spec)
        voi = value_of_information(vs, os_, options, seed=seed)
        cost = -float(np.mean(os_["pilot_net"]))
        rows.append({"error_prior_mean": m, "best_option": voi["best_option"],
                     "mean_net": voi["mean_net"], "evsi": voi["evsi_pilot"], "evpi": voi["evpi"],
                     "pilot_net_cost": cost, "pilot_worth_it": voi["evsi_pilot"] > cost})
    return rows


# ---------------------------------------------------------------------------
# Charts
# ---------------------------------------------------------------------------
def charts(report, out_s, p_tab, med, k_best, mix_table, voi, pil):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np
    from engine.visualize import save_matplotlib_charts

    os.makedirs(OUT_DIR, exist_ok=True)
    saved = save_matplotlib_charts(report, {k: out_s[k] for k in ["net_a", "net_b", "diff_b_minus_a"]}, OUT_DIR)
    K = 1000.0

    series = [("A: AI OS for all", "net_a", "#4a90d9"), ("B: Agentic for all", "net_b", "#d9822b"),
              (f"C: AI OS + {k_best} agent seat{'s' if k_best > 1 else ''}", f"net_c{k_best}", "#5a8f3c")]
    allv = np.concatenate([np.asarray(out_s[k]) / K for _, k, _ in series])
    lo, hi = np.percentile(allv, [0.5, 99.5])
    bins = np.linspace(lo, hi, 90)
    fig, ax = plt.subplots(figsize=(9, 4.6))
    for label, key, col in series:
        arr = np.asarray(out_s[key]) / K
        ax.hist(arr, bins=bins, alpha=0.45, color=col, label=f"{label} (median {np.median(arr):+.0f}k)")
        ax.axvline(np.median(arr), color=col, linestyle="--", linewidth=1.2)
    ax.axvline(0, color="black", linewidth=0.8)
    ax.set_xlabel("24-month net benefit ($k) — dashed = median")
    ax.set_ylabel("Trials")
    ax.set_title(f"Three strategies, 25 people × 24 months ({report['trials']:,} trials)")
    ax.legend(fontsize=8)
    p = os.path.join(OUT_DIR, "overlay_net_a_vs_b.png")
    fig.savefig(p, dpi=130, bbox_inches="tight"); plt.close(fig); saved.append(p)

    ks = [r["k"] for r in mix_table]
    fig, ax1 = plt.subplots(figsize=(8, 4.2))
    ax1.bar([str(k) for k in ks], [r["mean_gain"] / K for r in mix_table], color="#5a8f3c", alpha=0.8)
    ax1.axhline(0, color="black", linewidth=0.8)
    ax1.set_xlabel("Agent seats added (everyone keeps the AI OS seat)")
    ax1.set_ylabel("Mean gain over A ($k)")
    ax2 = ax1.twinx()
    ax2.plot([str(k) for k in ks], [r["p_beats_a"] for r in mix_table], color="#141413", marker="o")
    ax2.set_ylim(0, 1)
    ax2.set_ylabel("P(C beats A)")
    ax1.set_title("Option C: how many agent seats to add on top of AI OS")
    p = os.path.join(OUT_DIR, "mix_seats.png")
    fig.savefig(p, dpi=130, bbox_inches="tight"); plt.close(fig); saved.append(p)

    fig, ax = plt.subplots(figsize=(7.5, 3.8))
    labels = ["EVPI (ceiling:\nperfect info, all inputs)", "EVPPI (ceiling:\nperfect pilot measures)",
              "EVSI (what this pilot\nactually learns)", "Pilot net cost\n(mean)"]
    vals = [voi["evpi"] / K, voi["evppi_pilot_params"] / K, voi["evsi_pilot"] / K, -pil["mean"] / K]
    ax.barh(labels, vals, color=["#b0aea5", "#cfd8e3", "#6a9bcc", "#d97757"])
    for i, v in enumerate(vals):
        ax.text(v, i, f"  ${v:,.1f}k", va="center", fontsize=9)
    ax.set_xlabel("$k")
    ax.set_title("Is a pilot worth paying for? (EVSI vs cost)")
    p = os.path.join(OUT_DIR, "value_of_information.png")
    fig.savefig(p, dpi=130, bbox_inches="tight"); plt.close(fig); saved.append(p)

    for name, data, fmt, title in (
        ("sweep_p_b_wins.png", np.asarray(p_tab), "{:.0%}", "P(B beats A) vs agent error rate × hours delegated"),
        ("sweep_median_diff.png", np.asarray(med) / K, "{:+.0f}", "Median (B − A) net benefit, $k"),
    ):
        fig, ax = plt.subplots(figsize=(8, 5.2))
        if name.startswith("sweep_p"):
            im = ax.imshow(data, cmap="RdYlGn", vmin=0, vmax=1, aspect="auto")
        else:
            v = np.max(np.abs(data))
            im = ax.imshow(data, cmap="RdYlGn", vmin=-v, vmax=v, aspect="auto")
        ax.set_xticks(range(len(HRS_GRID)), [str(h) for h in HRS_GRID])
        ax.set_yticks(range(len(ERR_GRID)), [f"{e:.0%}" for e in ERR_GRID])
        ax.set_xlabel("Ordinary-user hours delegated / week")
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
    import numpy as np
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

    report, var_s, out_s = run(args.trials, args.seed)
    o = report["outcomes"]
    print(f"\nBase case: {args.trials:,} trials, seed {args.seed}, {TEAM} people, {MONTHS} months")
    print(f"{'outcome':<16}{'P5':>12}{'P50':>12}{'mean':>12}{'P95':>12}")
    for k in HEADLINE:
        s = o[k]["stats"]
        print(f"{k:<16}{fmt_money(s['p5']):>12}{fmt_money(s['p50']):>12}"
              f"{fmt_money(s['mean']):>12}{fmt_money(s['p95']):>12}")
    for k in ("b_beats_a", "a_positive", "b_positive"):
        print(f"P({k}) = {o[k]['probability_true']:.3f}")

    net_a = np.asarray(out_s["net_a"])
    mix = []
    for k in C_K_GRID:
        c = np.asarray(out_s[f"net_c{k}"])
        mix.append({"k": k, "mean_net": float(c.mean()), "p5": float(np.percentile(c, 5)),
                    "p50": float(np.median(c)), "p95": float(np.percentile(c, 95)),
                    "p_beats_a": o[f"c{k}_beats_a"]["probability_true"],
                    "median_gain": float(np.median(c - net_a)), "mean_gain": float((c - net_a).mean())})
    k_best = max(mix, key=lambda r: r["mean_net"])["k"]
    print("\nOption C (AI OS for all + k agent seats):")
    for r in mix:
        print(f"  k={r['k']:>2}: P(C>A)={r['p_beats_a']:.3f}  mean gain {fmt_money(r['mean_gain'])}"
              f"  median gain {fmt_money(r['median_gain'])}  net P5/P50/P95 {fmt_money(r['p5'])}/"
              f"{fmt_money(r['p50'])}/{fmt_money(r['p95'])}")
    print(f"  best k by expected value: {k_best}")

    options = ["net_a", "net_b"] + [f"net_c{k}" for k in C_K_GRID]
    voi = value_of_information(var_s, out_s, options, seed=args.seed)
    pn = np.asarray(out_s["pilot_net"])
    pil = {"seats": PILOT_SEATS, "months": PILOT_MONTHS, "setup_share": PILOT_SETUP_SHARE,
           "mean": float(pn.mean()), "p5": float(np.percentile(pn, 5)), "p50": float(np.median(pn)),
           "p95": float(np.percentile(pn, 95)), "cost_mean": float(np.mean(out_s["pil_cost"])),
           "tasks_median": voi["pilot_tasks_median"]}
    worth = voi["evsi_pilot"] > -pil["mean"]
    print(f"\nDecision by expected value: {voi['best_option']}  (means: "
          + ", ".join(f"{k}={fmt_money(v)}" for k, v in voi["mean_net"].items()) + ")")
    print(f"EVPI {fmt_money(voi['evpi'])}  EVPPI {fmt_money(voi['evppi_pilot_params'])}  "
          f"EVSI {fmt_money(voi['evsi_pilot'])}")
    print("  after-pilot choice share: " + ", ".join(f"{k}={v:.0%}" for k, v in voi["post_pilot_choice_share"].items() if v > 0))
    print(f"Pilot ({PILOT_SEATS} seats × {PILOT_MONTHS} mo, lean): cost mean {fmt_money(pil['cost_mean'])}; "
          f"net mean {fmt_money(pil['mean'])} P5/P50/P95 {fmt_money(pil['p5'])}/{fmt_money(pil['p50'])}/"
          f"{fmt_money(pil['p95'])}; median tasks observed {pil['tasks_median']:.0f}")
    print(f"Pilot worth it (EVSI > mean pilot net cost)? {'YES' if worth else 'NO'}")

    print("\nTornado on B − A (top 10):")
    for t in o["diff_b_minus_a"]["tornado"][:10]:
        print(f"  {t['variable']:<16}{t['correlation']:+.3f}  {t['impact']}")

    print(f"\nSweep (B): {len(ERR_GRID)}×{len(HRS_GRID)}, {args.sweep_trials:,} trials per cell")
    p_tab, med = sweep(args.sweep_trials, args.seed)
    for e, row in zip(ERR_GRID, p_tab):
        print(f"  {e:>5.0%} " + " ".join(f"{x:5.0%}" for x in row))

    print("\nMix gates (power-user hours/wk observed, review 30%; k chosen by expected value):")
    gates = mix_gates(args.sweep_trials, args.seed)
    for e, g in gates.items():
        gate = g["gate"]
        print(f"  error {e:.0%}: gate = " + (f"{gate['h']} h/wk (k={gate['k']}, P={gate['p']:.0%})" if gate else "none ≤16 h")
              + "   [" + " ".join(f"{r['h']}h:k{r['k']}/{r['p']:.0%}" for r in g["curve"]) + "]")

    print("\nVerdict vs belief about agent bad-action rate (prior mean):")
    sens = error_prior_sensitivity(args.trials, args.seed)
    for r in sens:
        print(f"  mean {r['error_prior_mean']:.0%}: best {r['best_option']:<8} "
              f"EVSI {fmt_money(r['evsi'])} vs pilot cost {fmt_money(r['pilot_net_cost'])} → "
              f"{'PILOT' if r['pilot_worth_it'] else 'no pilot'}   means: "
              + ", ".join(f"{k}={fmt_money(v)}" for k, v in r["mean_net"].items() if k in ("net_a", "net_c5", "net_c12", "net_c25")))

    print(f"\nTotal trials simulated this run: {TRIAL_COUNT['n']:,}")
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(os.path.join(OUT_DIR, "spec.json"), "w") as f:
        json.dump(build_spec(args.trials, args.seed), f, indent=2)
    with open(os.path.join(OUT_DIR, "results.json"), "w") as f:
        json.dump({"report": report, "evidence": EVIDENCE, "mix": mix, "k_best": k_best,
                   "value_of_information": voi, "pilot": pil, "pilot_worth_it": worth,
                   "sweep": {"error_grid": ERR_GRID, "hours_grid": HRS_GRID, "p_b_beats_a": p_tab,
                             "median_diff": med, "trials_per_cell": args.sweep_trials},
                   "mix_gates": {"fixed": {"b_review": 0.3, "p_hours_mult": MULT_MEAN},
                                 "by_error": {str(e): g for e, g in gates.items()}},
                   "error_prior_sensitivity": sens,
                   "total_trials": TRIAL_COUNT["n"]}, f, indent=2)
    if not args.no_charts:
        for p in charts(report, out_s, p_tab, med, k_best, mix, voi, pil):
            print("chart:", os.path.relpath(p, REPO_ROOT))
    return 0


if __name__ == "__main__":
    sys.exit(main())
