"""Monte Carlo Predictor — simulation engine.

Public API:
    simulate(spec: dict) -> dict
    simulate_with_samples(spec: dict) -> (report, vars_samples, outcomes_samples)

Usage:
    from engine import simulate
    report = simulate({
        "trials": 10000,
        "variables": {"x": {"distribution": "normal", "mean": 0, "stddev": 1}},
        "outcomes": {"y": "x * 2"},
    })
"""
from .monte_carlo import simulate, simulate_with_samples

__all__ = ["simulate", "simulate_with_samples"]
__version__ = "1.0.0"
