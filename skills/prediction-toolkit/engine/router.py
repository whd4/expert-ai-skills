"""Router: given a problem description or structured shape, recommend
which of the 7 prediction method families to use.

Input shapes accepted:
  1. Free-text problem description (string)
  2. Structured shape dict with explicit features

The router uses keyword heuristics for text input and a decision tree for
structured input. It is intentionally conservative — returns a ranked list
of candidates with confidence, so the caller can pick.

This is a heuristic, not ML. The value is in *making Claude actually
consider the 7 methods* instead of defaulting to linear reasoning.
"""
from __future__ import annotations

import re
from typing import Any


# Each family has a description, when-to-use signals, and an implementation pointer.
FAMILIES = {
    "statistical_forecasting": {
        "name": "Statistical forecasting",
        "implemented": True,
        "entry": "engine.exponential_smoothing.forecast",
        "also": ["ARIMA (scipy/statsmodels)", "Prophet (Meta)", "Kalman filter"],
        "when": "You have historical time-series data and want to project it forward",
        "keywords": [
            "forecast", "time series", "next month", "next quarter", "next year",
            "projection", "trend", "seasonal", "seasonality", "historical data",
            "past sales", "past revenue", "growth rate", "over time",
        ],
    },
    "machine_learning": {
        "name": "Machine learning",
        "implemented": False,
        "entry": "methods/machine-learning.md",
        "also": ["XGBoost", "LightGBM", "CatBoost", "scikit-learn", "PyTorch"],
        "when": "You have many features, lots of labeled examples, and nonlinear relationships",
        "keywords": [
            "many features", "high dimensional", "lots of data", "millions of rows",
            "classification", "regression", "neural net", "deep learning",
            "feature engineering", "labeled data", "predict from features",
        ],
    },
    "bayesian_inference": {
        "name": "Bayesian inference",
        "implemented": True,
        "entry": "engine.bayesian_update.beta_binomial_update",
        "also": ["probability_update for medical/diagnostic tests", "MCMC for complex posteriors"],
        "when": "You have a prior belief and want to update it with new evidence",
        "keywords": [
            "prior", "posterior", "update belief", "bayes", "bayesian",
            "given this new", "evidence suggests", "revise estimate",
            "conversion rate", "click through", "ctr", "a/b test",
            "small sample probability", "hit rate",
        ],
    },
    "simulation": {
        "name": "Simulation (Monte Carlo + bootstrap)",
        "implemented": True,
        "entry": "monte-carlo-predictor skill OR engine.bootstrap.bootstrap_ci",
        "also": ["agent-based modeling", "system dynamics", "discrete event simulation"],
        "when": "You have uncertain inputs and a known formula, OR a small sample needing CI",
        "keywords": [
            "monte carlo", "simulation", "uncertainty", "random",
            "what's the chance", "probability of", "risk", "tail risk",
            "p95", "p99", "worst case", "confidence interval",
            "bootstrap", "resample", "no distribution assumption",
            "migration", "should we", "decision", "uncertainty range",
        ],
    },
    "crowd_aggregation": {
        "name": "Crowd aggregation",
        "implemented": False,
        "entry": "methods/crowd-aggregation.md",
        "also": ["prediction markets (Polymarket/Kalshi)", "Delphi method", "superforecasting protocols"],
        "when": "You have multiple independent expert opinions or market signals to combine",
        "keywords": [
            "expert opinion", "multiple forecasts", "aggregate", "ensemble",
            "prediction market", "wisdom of crowd", "consensus",
            "delphi", "superforecaster", "betting market",
        ],
    },
    "causal_inference": {
        "name": "Causal inference",
        "implemented": False,
        "entry": "methods/causal-inference.md",
        "also": ["Pearl do-calculus", "difference-in-differences", "instrumental variables", "propensity matching"],
        "when": "You need to know 'what if we changed X?' — counterfactual / intervention",
        "keywords": [
            "caused", "because of", "if we change", "counterfactual", "what if",
            "intervention", "causal", "effect of", "would have happened",
            "treatment effect", "natural experiment", "confound",
        ],
    },
    "first_principles": {
        "name": "First-principles / physics",
        "implemented": False,
        "entry": "methods/first-principles.md",
        "also": ["ODE/PDE solvers (scipy.integrate)", "domain simulators", "mechanistic models"],
        "when": "You know the underlying laws and can simulate them forward",
        "keywords": [
            "physics", "differential equation", "ode", "pde", "mechanistic",
            "underlying law", "conservation", "thermodynamic", "fluid",
            "kinetic", "newton", "chemistry", "pharmacokinetic",
        ],
    },
}


def recommend_method(problem: str | dict[str, Any]) -> dict[str, Any]:
    """Recommend prediction method(s) for a problem.

    Args:
        problem: Either a free-text description or a structured shape dict.

    Returns:
        dict with:
            top_recommendation: name of the top family
            candidates: ranked list of family recommendations with scores
            reasoning: why the top match was chosen
    """
    if isinstance(problem, str):
        scores = _score_text(problem)
    elif isinstance(problem, dict):
        scores = _score_structured(problem)
    else:
        raise ValueError(f"problem must be str or dict, got {type(problem).__name__}")

    # Sort candidates by score
    ranked = sorted(scores.items(), key=lambda x: -x[1]["score"])
    top = ranked[0] if ranked else None

    candidates = []
    for name, s in ranked:
        fam = FAMILIES[name]
        candidates.append({
            "family": fam["name"],
            "family_id": name,
            "score": round(s["score"], 3),
            "matched_signals": s["matches"],
            "implemented": fam["implemented"],
            "entry": fam["entry"],
            "when": fam["when"],
            "also_consider": fam["also"],
        })

    if top and top[1]["score"] > 0:
        reasoning = _build_reasoning(top[0], top[1], ranked)
    else:
        reasoning = (
            "No strong signal matched the 7 families. This may be a deterministic "
            "problem (just compute), or the problem statement may be too abstract. "
            "Consider reframing: what future outcome are you uncertain about?"
        )

    return {
        "problem": problem if isinstance(problem, str) else str(problem),
        "top_recommendation": candidates[0] if candidates else None,
        "candidates": candidates,
        "reasoning": reasoning,
    }


def _score_text(text: str) -> dict[str, dict]:
    """Score each family by keyword match in free text (word boundaries)."""
    lowered = text.lower()
    scores = {}
    for name, fam in FAMILIES.items():
        matches = []
        for kw in fam["keywords"]:
            pattern = r"\b" + re.escape(kw) + r"\b"
            if re.search(pattern, lowered):
                matches.append(kw)
        # Score = fraction of keywords matched, with a bonus for multi-word matches
        if not fam["keywords"]:
            score = 0.0
        else:
            total_weight = sum(len(kw.split()) for kw in matches)
            score = total_weight / max(len(fam["keywords"]), 1)
        scores[name] = {"score": score, "matches": matches}
    return scores


def _score_structured(shape: dict[str, Any]) -> dict[str, dict]:
    """Score each family from explicit problem-shape features.

    Expected shape keys (all optional):
        has_historical_data: bool
        data_points: int
        time_series: bool
        seasonal_periods: int | None
        variables_uncertain: bool
        has_known_formula: bool
        updating_belief: bool
        prior_available: bool
        counterfactual: bool
        physical_laws_known: bool
        multiple_experts: bool
        small_sample: bool              # n < 30
        need_confidence_interval: bool
        high_dimensional: bool          # many features
        nonlinear_relationship: bool
        labeled_training_data: bool
    """
    s = shape
    scores = {k: {"score": 0.0, "matches": []} for k in FAMILIES}

    def add(fam: str, pts: float, reason: str):
        scores[fam]["score"] += pts
        scores[fam]["matches"].append(reason)

    if s.get("time_series") or s.get("has_historical_data"):
        add("statistical_forecasting", 0.5, "time-series data")
        if s.get("seasonal_periods"):
            add("statistical_forecasting", 0.3, "seasonality present")
        if s.get("data_points", 0) > 200:
            add("machine_learning", 0.3, "long series → ML viable")

    if s.get("high_dimensional") or s.get("labeled_training_data"):
        add("machine_learning", 0.6, "high-dim / labeled data")
    if s.get("nonlinear_relationship"):
        add("machine_learning", 0.3, "nonlinear")

    if s.get("updating_belief") or s.get("prior_available"):
        add("bayesian_inference", 0.7, "prior + evidence → Bayesian")
    if s.get("small_sample") and s.get("need_confidence_interval"):
        add("bayesian_inference", 0.3, "small sample with prior")
        add("simulation", 0.5, "small sample CI → bootstrap")

    if s.get("variables_uncertain") and s.get("has_known_formula"):
        add("simulation", 0.8, "uncertain inputs + formula → Monte Carlo")
    if s.get("small_sample") and not s.get("prior_available"):
        add("simulation", 0.5, "bootstrap for no-prior CI")

    if s.get("multiple_experts"):
        add("crowd_aggregation", 0.7, "multiple experts to combine")

    if s.get("counterfactual"):
        add("causal_inference", 0.8, "counterfactual question")

    if s.get("physical_laws_known"):
        add("first_principles", 0.8, "known underlying laws")

    return scores


def _build_reasoning(top_name: str, top_score: dict, ranked: list) -> str:
    fam = FAMILIES[top_name]
    matches = top_score["matches"]
    matched_str = ", ".join(matches[:3]) + ("..." if len(matches) > 3 else "")
    lines = []
    lines.append(f"Top match: {fam['name']} — {fam['when']}.")
    if matches:
        lines.append(f"Signals matched: {matched_str}")
    if fam["implemented"]:
        lines.append(f"Implemented as: {fam['entry']}")
    else:
        lines.append(f"Not implemented here; see {fam['entry']} for guidance on which library to use.")
    # Runner-up callout if close
    if len(ranked) > 1:
        second = ranked[1]
        if second[1]["score"] > top_score["score"] * 0.6:
            lines.append(f"Also consider: {FAMILIES[second[0]]['name']} (close runner-up).")
    return " ".join(lines)


def render(result: dict) -> str:
    """ASCII report."""
    lines = []
    lines.append("=" * 70)
    lines.append("  METHOD RECOMMENDATION")
    lines.append("=" * 70)
    lines.append(f"  Problem: {result['problem'][:120]}")
    lines.append("")
    if result["top_recommendation"]:
        top = result["top_recommendation"]
        lines.append(f"  → {top['family']}   (score: {top['score']})")
        lines.append(f"    When: {top['when']}")
        lines.append(f"    Entry: {top['entry']}")
        if top["matched_signals"]:
            lines.append(f"    Matched signals: {', '.join(top['matched_signals'][:5])}")
    lines.append("")
    lines.append(f"  Reasoning: {result['reasoning']}")
    lines.append("")
    lines.append("  All candidates (ranked):")
    for c in result["candidates"]:
        marker = "★" if c == result["top_recommendation"] else " "
        impl = "✓" if c["implemented"] else " "
        lines.append(f"    {marker} [{impl}] {c['family']:<40} score={c['score']:.3f}")
    lines.append("=" * 70)
    return "\n".join(lines) + "\n"
