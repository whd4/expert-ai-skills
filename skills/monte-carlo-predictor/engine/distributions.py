"""Probability distributions for Monte Carlo simulations.

Each sampler returns a numpy array (if numpy available) or a Python list.
All distributions accept a `size` parameter and return `size` samples.
"""
from __future__ import annotations

import math
import random
from typing import Any

try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False


def _as_array(samples):
    if HAS_NUMPY:
        return np.asarray(samples, dtype=float)
    return list(samples)


def uniform(low: float, high: float, size: int):
    if HAS_NUMPY:
        return np.random.uniform(low, high, size)
    return [random.uniform(low, high) for _ in range(size)]


def normal(mean: float, stddev: float, size: int):
    if HAS_NUMPY:
        return np.random.normal(mean, stddev, size)
    return [random.gauss(mean, stddev) for _ in range(size)]


def triangular(low: float, likely: float, high: float, size: int):
    if not (low <= likely <= high):
        raise ValueError(f"triangular requires low <= likely <= high, got {low}, {likely}, {high}")
    if HAS_NUMPY:
        return np.random.triangular(low, likely, high, size)
    return [random.triangular(low, high, likely) for _ in range(size)]


def beta(alpha: float, beta_param: float, size: int, low: float = 0.0, high: float = 1.0):
    if HAS_NUMPY:
        samples = np.random.beta(alpha, beta_param, size)
        return low + samples * (high - low)
    return [low + random.betavariate(alpha, beta_param) * (high - low) for _ in range(size)]


def lognormal(mean: float, stddev: float, size: int):
    if HAS_NUMPY:
        return np.random.lognormal(mean, stddev, size)
    return [random.lognormvariate(mean, stddev) for _ in range(size)]


def poisson(lam: float, size: int):
    if HAS_NUMPY:
        return np.random.poisson(lam, size).astype(float)
    out = []
    for _ in range(size):
        L = math.exp(-lam)
        k = 0
        p = 1.0
        while p > L:
            k += 1
            p *= random.random()
        out.append(float(k - 1))
    return out


def choice(options: list, weights: list | None, size: int):
    if HAS_NUMPY:
        if weights is None:
            idx = np.random.randint(0, len(options), size)
        else:
            weights_arr = np.asarray(weights, dtype=float)
            probs = weights_arr / weights_arr.sum()
            idx = np.random.choice(len(options), size=size, p=probs)
        opts = np.asarray(options)
        return opts[idx]
    if weights is None:
        return [random.choice(options) for _ in range(size)]
    return random.choices(options, weights=weights, k=size)


def constant(value: float, size: int):
    if HAS_NUMPY:
        return np.full(size, float(value))
    return [float(value)] * size


_REGISTRY = {
    "uniform": lambda p, n: uniform(p["low"], p["high"], n),
    "normal": lambda p, n: normal(p["mean"], p["stddev"], n),
    "triangular": lambda p, n: triangular(p["low"], p["likely"], p["high"], n),
    "beta": lambda p, n: beta(p["alpha"], p["beta"], n, p.get("low", 0.0), p.get("high", 1.0)),
    "lognormal": lambda p, n: lognormal(p["mean"], p["stddev"], n),
    "poisson": lambda p, n: poisson(p["lam"], n),
    "choice": lambda p, n: choice(p["options"], p.get("weights"), n),
    "constant": lambda p, n: constant(p["value"], n),
}


def sample(params: dict[str, Any], size: int):
    """Sample from a distribution given its spec dict.

    Spec format: `{"distribution": "triangular", "low": 1, "likely": 5, "high": 20}`
    """
    dist_name = params.get("distribution")
    if dist_name is None:
        raise ValueError(f"distribution spec missing 'distribution' key: {params}")
    sampler = _REGISTRY.get(dist_name)
    if sampler is None:
        raise ValueError(f"unknown distribution: {dist_name!r}. Available: {sorted(_REGISTRY)}")
    return _as_array(sampler(params, size))


def three_point(low: float, likely: float, high: float, size: int):
    """Helper: classic three-point estimation → triangular distribution."""
    return triangular(low, likely, high, size)
