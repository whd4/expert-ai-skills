"""Monte Carlo simulation engine.

Takes a spec (dict / YAML / JSON) and runs N trials, returning statistics
for every declared outcome and a tornado-plot-ready variance breakdown.

Spec format:
    trials: 10000
    seed: 42                    # optional, for reproducibility
    variables:
        my_var:
            distribution: triangular
            low: 1
            likely: 5
            high: 20
    outcomes:
        my_outcome: "my_var * 2 + 3"
        success: "my_outcome > 10"
"""
from __future__ import annotations

import random
from typing import Any

from . import distributions
from .expressions import safe_eval

try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False


DEFAULT_TRIALS = 10_000


def _to_list(samples):
    if HAS_NUMPY and isinstance(samples, np.ndarray):
        return samples.tolist()
    return list(samples)


def _percentile(samples, pct):
    if HAS_NUMPY:
        return float(np.percentile(samples, pct))
    sorted_s = sorted(samples)
    k = (len(sorted_s) - 1) * pct / 100.0
    f = int(k)
    c = min(f + 1, len(sorted_s) - 1)
    if f == c:
        return float(sorted_s[f])
    return float(sorted_s[f] + (sorted_s[c] - sorted_s[f]) * (k - f))


def _stats(samples) -> dict[str, float]:
    if HAS_NUMPY:
        arr = np.asarray(samples, dtype=float)
        return {
            "mean": float(arr.mean()),
            "median": float(np.median(arr)),
            "stddev": float(arr.std()),
            "min": float(arr.min()),
            "max": float(arr.max()),
            "p5": float(np.percentile(arr, 5)),
            "p25": float(np.percentile(arr, 25)),
            "p50": float(np.percentile(arr, 50)),
            "p75": float(np.percentile(arr, 75)),
            "p95": float(np.percentile(arr, 95)),
        }
    n = len(samples)
    mean = sum(samples) / n
    variance = sum((x - mean) ** 2 for x in samples) / n
    return {
        "mean": mean,
        "median": _percentile(samples, 50),
        "stddev": variance ** 0.5,
        "min": min(samples),
        "max": max(samples),
        "p5": _percentile(samples, 5),
        "p25": _percentile(samples, 25),
        "p50": _percentile(samples, 50),
        "p75": _percentile(samples, 75),
        "p95": _percentile(samples, 95),
    }


def _probability_true(samples) -> float:
    """For boolean-like outcomes (0/1), return P(true)."""
    if HAS_NUMPY and isinstance(samples, np.ndarray):
        return float(np.mean(samples > 0.5))
    return sum(1 for s in samples if s > 0.5) / len(samples)


def _is_boolean_like(samples) -> bool:
    """Heuristic: only 0 and 1 values → boolean outcome."""
    if HAS_NUMPY and isinstance(samples, np.ndarray):
        unique = np.unique(samples)
        return len(unique) <= 2 and set(unique.tolist()).issubset({0.0, 1.0})
    unique = set(samples)
    return len(unique) <= 2 and unique.issubset({0.0, 1.0})


def _correlation(x, y) -> float:
    """Pearson correlation, numpy or pure Python."""
    if HAS_NUMPY:
        xa = np.asarray(x, dtype=float)
        ya = np.asarray(y, dtype=float)
        if xa.std() == 0 or ya.std() == 0:
            return 0.0
        return float(np.corrcoef(xa, ya)[0, 1])
    n = len(x)
    mx = sum(x) / n
    my = sum(y) / n
    num = sum((xi - mx) * (yi - my) for xi, yi in zip(x, y))
    dx = (sum((xi - mx) ** 2 for xi in x)) ** 0.5
    dy = (sum((yi - my) ** 2 for yi in y)) ** 0.5
    if dx == 0 or dy == 0:
        return 0.0
    return num / (dx * dy)


def _tornado(variables_samples: dict, outcome_samples, outcome_stats: dict):
    """Rank variables by their correlation with the outcome.

    Returns list of dicts sorted by |correlation| descending:
        [{"variable": "x", "correlation": 0.82, "impact": "high"}, ...]
    """
    if outcome_stats["stddev"] == 0:
        return []
    items = []
    for name, samples in variables_samples.items():
        try:
            corr = _correlation(samples, outcome_samples)
        except Exception:
            corr = 0.0
        items.append({"variable": name, "correlation": round(corr, 4)})
    items.sort(key=lambda x: abs(x["correlation"]), reverse=True)
    for it in items:
        abs_c = abs(it["correlation"])
        if abs_c >= 0.5:
            it["impact"] = "high"
        elif abs_c >= 0.25:
            it["impact"] = "medium"
        elif abs_c >= 0.10:
            it["impact"] = "low"
        else:
            it["impact"] = "negligible"
    return items


def simulate(spec: dict[str, Any]) -> dict[str, Any]:
    """Run a Monte Carlo simulation from a spec dict.

    Returns a dict:
        {
          "trials": N,
          "variables": {name: stats_dict},
          "outcomes": {
            name: {
              stats_dict,
              "probability_true": 0.78,     # only if boolean-like
              "tornado": [{variable, correlation, impact}, ...],
            }
          }
        }
    """
    trials = int(spec.get("trials", DEFAULT_TRIALS))
    if trials <= 0:
        raise ValueError(f"trials must be positive, got {trials}")

    seed = spec.get("seed")
    if seed is not None:
        random.seed(seed)
        if HAS_NUMPY:
            np.random.seed(seed)

    var_specs = spec.get("variables") or {}
    outcome_specs = spec.get("outcomes") or {}

    if not var_specs:
        raise ValueError("spec must declare at least one variable")

    # 1) Sample all variables
    variables_samples: dict[str, Any] = {}
    for name, dist_spec in var_specs.items():
        if not isinstance(dist_spec, dict):
            raise ValueError(f"variable {name!r} must be a dict, got {type(dist_spec).__name__}")
        variables_samples[name] = distributions.sample(dist_spec, trials)

    # 2) Evaluate outcomes
    outcomes_samples: dict[str, Any] = {}
    for name, expr in outcome_specs.items():
        if not isinstance(expr, str):
            raise ValueError(f"outcome {name!r} must be a string expression, got {type(expr).__name__}")
        # Outcomes can reference variables and previously-computed outcomes
        ctx = {**variables_samples, **outcomes_samples}
        result = safe_eval(expr, ctx)
        if HAS_NUMPY and not isinstance(result, np.ndarray):
            result = np.full(trials, float(result))
        elif not HAS_NUMPY and not isinstance(result, list):
            result = [float(result)] * trials
        outcomes_samples[name] = result

    # 3) Compute statistics
    var_stats = {name: _stats(s) for name, s in variables_samples.items()}

    outcome_reports: dict[str, Any] = {}
    for name, samples in outcomes_samples.items():
        s = _stats(samples)
        entry = {
            "stats": s,
            "tornado": _tornado(variables_samples, samples, s),
        }
        if _is_boolean_like(samples):
            entry["probability_true"] = _probability_true(samples)
        outcome_reports[name] = entry

    return {
        "trials": trials,
        "seed": seed,
        "variables": var_stats,
        "outcomes": outcome_reports,
    }


def simulate_with_samples(spec: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    """Same as simulate() but also returns raw samples.

    Returns (report, variables_samples, outcomes_samples).
    Useful for visualization that needs full sample arrays.
    """
    # Duplicate of simulate() logic with samples returned.
    # Kept as separate function so simulate() stays small and serializable.
    trials = int(spec.get("trials", DEFAULT_TRIALS))
    seed = spec.get("seed")
    if seed is not None:
        random.seed(seed)
        if HAS_NUMPY:
            np.random.seed(seed)

    var_specs = spec.get("variables") or {}
    outcome_specs = spec.get("outcomes") or {}

    variables_samples: dict[str, Any] = {}
    for name, dist_spec in var_specs.items():
        variables_samples[name] = distributions.sample(dist_spec, trials)

    outcomes_samples: dict[str, Any] = {}
    for name, expr in outcome_specs.items():
        ctx = {**variables_samples, **outcomes_samples}
        result = safe_eval(expr, ctx)
        if HAS_NUMPY and not isinstance(result, np.ndarray):
            result = np.full(trials, float(result))
        elif not HAS_NUMPY and not isinstance(result, list):
            result = [float(result)] * trials
        outcomes_samples[name] = result

    var_stats = {name: _stats(s) for name, s in variables_samples.items()}
    outcome_reports: dict[str, Any] = {}
    for name, samples in outcomes_samples.items():
        s = _stats(samples)
        entry = {"stats": s, "tornado": _tornado(variables_samples, samples, s)}
        if _is_boolean_like(samples):
            entry["probability_true"] = _probability_true(samples)
        outcome_reports[name] = entry

    report = {
        "trials": trials,
        "seed": seed,
        "variables": var_stats,
        "outcomes": outcome_reports,
    }
    return report, variables_samples, outcomes_samples
