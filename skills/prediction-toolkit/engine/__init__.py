"""Prediction Toolkit — a router + four implemented methods + four guides.

Public API:
    bootstrap_ci(data, stat, n_resamples, ci) -> dict
    beta_binomial_update(alpha, beta, successes, trials) -> dict
    probability_update(prior, likelihood_given_h, likelihood_given_not_h) -> float
    forecast(series, periods, method, alpha, beta, gamma, seasonal_periods) -> dict
    recommend_method(problem: dict | str) -> dict

Usage:
    from engine import bootstrap_ci, forecast, recommend_method
    ci = bootstrap_ci([1.2, 1.5, 0.9, 1.1, 1.3], stat="mean", ci=0.95)
    fc = forecast([100, 110, 105, 120, 130], periods=3)
    rec = recommend_method("should we migrate databases?")
"""
from .bootstrap import bootstrap_ci
from .bayesian_update import beta_binomial_update, probability_update
from .exponential_smoothing import forecast
from .router import recommend_method

__all__ = [
    "bootstrap_ci",
    "beta_binomial_update",
    "probability_update",
    "forecast",
    "recommend_method",
]
__version__ = "1.0.0"
