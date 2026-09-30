"""Bootstrap resampling.

Answers: "I have N data points. What is the confidence interval on a
statistic (mean, median, ratio, etc.) without assuming a distribution?"

Method: Resample the data with replacement B times. Compute the statistic
on each resample. The percentiles of that distribution give you the CI.

Best for:
  - Small samples (N < 50)
  - Non-normal distributions
  - Any statistic (mean, median, correlation, ratio) you can compute
  - When you don't trust parametric assumptions

Not for:
  - Point forecasts (use forecasting methods)
  - Highly structured data (time series — use block bootstrap)
  - Updating priors (use Bayesian)
"""
from __future__ import annotations

import random
import statistics
from typing import Any, Callable, Sequence

try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False


_STAT_FUNCTIONS: dict[str, Callable] = {
    "mean": statistics.mean,
    "median": statistics.median,
    "stdev": lambda xs: statistics.stdev(xs) if len(xs) >= 2 else 0.0,
    "variance": lambda xs: statistics.variance(xs) if len(xs) >= 2 else 0.0,
    "min": min,
    "max": max,
    "sum": sum,
}


def _percentile(sorted_values: Sequence[float], pct: float) -> float:
    if HAS_NUMPY:
        return float(np.percentile(sorted_values, pct))
    k = (len(sorted_values) - 1) * pct / 100.0
    f = int(k)
    c = min(f + 1, len(sorted_values) - 1)
    if f == c:
        return float(sorted_values[f])
    return float(sorted_values[f] + (sorted_values[c] - sorted_values[f]) * (k - f))


def bootstrap_ci(
    data: Sequence[float],
    stat: str | Callable = "mean",
    n_resamples: int = 10_000,
    ci: float = 0.95,
    seed: int | None = None,
) -> dict[str, Any]:
    """Bootstrap confidence interval for a statistic.

    Args:
        data: Observed values.
        stat: Either a name ("mean", "median", "stdev", "variance", "min",
              "max", "sum") or a callable taking a sequence.
        n_resamples: Number of bootstrap resamples (default 10,000).
        ci: Confidence level in (0, 1). 0.95 = 95% CI.
        seed: Optional RNG seed for reproducibility.

    Returns:
        dict with:
            observed: stat value on original data
            mean: mean of bootstrap distribution
            stddev: stddev of bootstrap distribution (== standard error)
            ci_lower, ci_upper: endpoints of the CI
            ci_level: the CI level used
            n_resamples: number of resamples performed
    """
    if len(data) == 0:
        raise ValueError("data cannot be empty")
    if not 0.0 < ci < 1.0:
        raise ValueError(f"ci must be in (0, 1), got {ci}")
    if n_resamples < 100:
        raise ValueError(f"n_resamples must be at least 100, got {n_resamples}")

    if isinstance(stat, str):
        if stat not in _STAT_FUNCTIONS:
            raise ValueError(f"unknown stat {stat!r}. Available: {sorted(_STAT_FUNCTIONS)}")
        stat_fn = _STAT_FUNCTIONS[stat]
        stat_name = stat
    else:
        stat_fn = stat
        stat_name = getattr(stat, "__name__", "custom")

    if seed is not None:
        random.seed(seed)
        if HAS_NUMPY:
            np.random.seed(seed)

    observed = float(stat_fn(data))

    n = len(data)
    if HAS_NUMPY:
        arr = np.asarray(data, dtype=float)
        # Vectorized resampling: shape (n_resamples, n)
        idx = np.random.randint(0, n, size=(n_resamples, n))
        resamples = arr[idx]
        # Apply stat over each row
        if stat_name in ("mean",):
            resample_stats = resamples.mean(axis=1)
        elif stat_name == "median":
            resample_stats = np.median(resamples, axis=1)
        elif stat_name == "min":
            resample_stats = resamples.min(axis=1)
        elif stat_name == "max":
            resample_stats = resamples.max(axis=1)
        elif stat_name == "sum":
            resample_stats = resamples.sum(axis=1)
        elif stat_name == "stdev":
            resample_stats = resamples.std(axis=1, ddof=1) if n >= 2 else np.zeros(n_resamples)
        elif stat_name == "variance":
            resample_stats = resamples.var(axis=1, ddof=1) if n >= 2 else np.zeros(n_resamples)
        else:
            # Fallback for custom stats
            resample_stats = np.array([float(stat_fn(row.tolist())) for row in resamples])
        resample_stats = resample_stats.tolist()
    else:
        resample_stats = []
        data_list = list(data)
        for _ in range(n_resamples):
            sample = [random.choice(data_list) for _ in range(n)]
            resample_stats.append(float(stat_fn(sample)))

    resample_stats_sorted = sorted(resample_stats)
    alpha = (1.0 - ci) / 2.0
    lower_pct = alpha * 100.0
    upper_pct = (1.0 - alpha) * 100.0

    mean = sum(resample_stats) / len(resample_stats)
    if len(resample_stats) >= 2:
        variance = sum((x - mean) ** 2 for x in resample_stats) / (len(resample_stats) - 1)
        stddev = variance ** 0.5
    else:
        stddev = 0.0

    return {
        "method": "bootstrap",
        "stat": stat_name,
        "n_data": n,
        "n_resamples": n_resamples,
        "observed": observed,
        "mean": round(mean, 6),
        "stddev": round(stddev, 6),
        "ci_level": ci,
        "ci_lower": round(_percentile(resample_stats_sorted, lower_pct), 6),
        "ci_upper": round(_percentile(resample_stats_sorted, upper_pct), 6),
        "caveats": _caveats(n, n_resamples),
    }


def _caveats(n: int, n_resamples: int) -> list[str]:
    out = []
    if n < 10:
        out.append(f"very small sample (n={n}) — CI is unreliable; add more data if possible")
    elif n < 30:
        out.append(f"small sample (n={n}) — treat CI as indicative, not definitive")
    if n_resamples < 1000:
        out.append(f"only {n_resamples} resamples — for stable CI use at least 1000, ideally 10000")
    return out


def render(result: dict) -> str:
    """ASCII report."""
    lines = []
    lines.append("=" * 60)
    lines.append(f"  BOOTSTRAP CI — stat: {result['stat']}")
    lines.append("=" * 60)
    lines.append(f"  Sample size:   {result['n_data']}")
    lines.append(f"  Resamples:     {result['n_resamples']}")
    lines.append(f"  Observed:      {result['observed']:.4f}")
    lines.append(f"  Bootstrap mean:{result['mean']:.4f}   stddev: {result['stddev']:.4f}")
    lines.append(
        f"  {int(result['ci_level']*100)}% CI:       [{result['ci_lower']:.4f}, {result['ci_upper']:.4f}]"
    )
    if result.get("caveats"):
        lines.append("")
        lines.append("  Caveats:")
        for c in result["caveats"]:
            lines.append(f"    - {c}")
    lines.append("=" * 60)
    return "\n".join(lines) + "\n"
