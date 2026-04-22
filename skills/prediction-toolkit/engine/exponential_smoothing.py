"""Exponential smoothing for time-series forecasting.

Three levels of sophistication, each suited to a different pattern:

1. **Simple (SES)** — series with no trend, no seasonality.
   Formula: level_t = alpha * y_t + (1 - alpha) * level_{t-1}

2. **Holt** — series with a trend but no seasonality.
   Maintains level + trend separately.

3. **Holt-Winters** — series with trend AND seasonality.
   Maintains level + trend + per-season components (additive variant).

Best for:
  - Short time series (12-500 points)
  - You need a point forecast + prediction interval
  - The pattern is stable (no regime changes)
  - You don't have many features — just the series itself

Not for:
  - Very long series with complex patterns (use Prophet / ARIMA)
  - Multi-feature prediction (use ML — XGBoost, neural nets)
  - Causal questions ("would X have changed Y?")
"""
from __future__ import annotations

import math
from typing import Any, Sequence


def forecast(
    series: Sequence[float],
    periods: int = 1,
    method: str = "auto",
    alpha: float | None = None,
    beta: float | None = None,
    gamma: float | None = None,
    seasonal_periods: int | None = None,
) -> dict[str, Any]:
    """Forecast the next N periods of a time series.

    Args:
        series: Historical observations, oldest first.
        periods: How many future periods to forecast.
        method: "simple" | "holt" | "holt_winters" | "auto".
                "auto" picks based on series length and seasonal_periods.
        alpha: Level smoothing in (0, 1]. If None, auto-tuned.
        beta: Trend smoothing in (0, 1]. Required for holt/holt_winters.
        gamma: Seasonal smoothing in (0, 1]. Required for holt_winters.
        seasonal_periods: Length of one season (e.g., 12 for monthly/yearly).

    Returns:
        dict with forecasts, fitted values, components, method used, RMSE.
    """
    if len(series) < 2:
        raise ValueError(f"need at least 2 observations, got {len(series)}")
    if periods < 1:
        raise ValueError(f"periods must be >= 1, got {periods}")

    data = [float(v) for v in series]

    if method == "auto":
        if seasonal_periods and len(data) >= 2 * seasonal_periods:
            method = "holt_winters"
        elif len(data) >= 4 and _has_trend(data):
            method = "holt"
        else:
            method = "simple"

    if method == "simple":
        return _ses(data, periods, alpha)
    if method == "holt":
        return _holt(data, periods, alpha, beta)
    if method == "holt_winters":
        if not seasonal_periods:
            raise ValueError("holt_winters requires seasonal_periods")
        return _holt_winters(data, periods, seasonal_periods, alpha, beta, gamma)
    raise ValueError(f"unknown method {method!r}")


def _has_trend(data: Sequence[float]) -> bool:
    """Cheap trend detector: compare first-half mean to second-half mean."""
    mid = len(data) // 2
    if mid == 0:
        return False
    first = sum(data[:mid]) / mid
    second = sum(data[mid:]) / (len(data) - mid)
    # Relative change >= 5% = "has trend"
    denom = max(abs(first), abs(second), 1e-9)
    return abs(second - first) / denom >= 0.05


def _ses(data: list[float], periods: int, alpha: float | None) -> dict:
    """Simple exponential smoothing."""
    best_alpha = alpha if alpha is not None else _tune_alpha(data, _ses_fit)
    fitted, residuals = _ses_fit(data, best_alpha)
    level = fitted[-1]
    forecasts = [level] * periods
    rmse = _rmse(residuals)
    return {
        "method": "simple_exponential_smoothing",
        "parameters": {"alpha": round(best_alpha, 4)},
        "fitted_values": [round(v, 4) for v in fitted],
        "forecasts": [round(v, 4) for v in forecasts],
        "rmse": round(rmse, 4),
        "forecast_interval_95": _naive_interval(forecasts, rmse, 1.96),
        "interpretation": _interpret(data, forecasts, "simple"),
    }


def _ses_fit(data: list[float], alpha: float) -> tuple[list[float], list[float]]:
    fitted = [data[0]]
    for t in range(1, len(data)):
        level = alpha * data[t - 1] + (1 - alpha) * fitted[-1]
        fitted.append(level)
    residuals = [data[t] - fitted[t] for t in range(len(data))]
    return fitted, residuals


def _holt(data: list[float], periods: int, alpha: float | None, beta: float | None) -> dict:
    """Holt's linear trend."""
    best_alpha, best_beta = _tune_holt(data, alpha, beta)
    level, trend, fitted, residuals = _holt_fit(data, best_alpha, best_beta)
    forecasts = [level + (h + 1) * trend for h in range(periods)]
    rmse = _rmse(residuals)
    return {
        "method": "holt_linear_trend",
        "parameters": {"alpha": round(best_alpha, 4), "beta": round(best_beta, 4)},
        "fitted_values": [round(v, 4) for v in fitted],
        "forecasts": [round(v, 4) for v in forecasts],
        "rmse": round(rmse, 4),
        "forecast_interval_95": _naive_interval(forecasts, rmse, 1.96),
        "final_level": round(level, 4),
        "final_trend": round(trend, 4),
        "interpretation": _interpret(data, forecasts, "holt"),
    }


def _holt_fit(data: list[float], alpha: float, beta: float) -> tuple[float, float, list[float], list[float]]:
    level = data[0]
    trend = data[1] - data[0]
    fitted = [level]
    for t in range(1, len(data)):
        new_level = alpha * data[t] + (1 - alpha) * (level + trend)
        new_trend = beta * (new_level - level) + (1 - beta) * trend
        level, trend = new_level, new_trend
        fitted.append(level)
    residuals = [data[t] - fitted[t] for t in range(len(data))]
    return level, trend, fitted, residuals


def _holt_winters(
    data: list[float],
    periods: int,
    s: int,
    alpha: float | None,
    beta: float | None,
    gamma: float | None,
) -> dict:
    """Holt-Winters additive seasonality."""
    best_alpha, best_beta, best_gamma = _tune_hw(data, s, alpha, beta, gamma)
    level, trend, seasons, fitted, residuals = _hw_fit(data, s, best_alpha, best_beta, best_gamma)
    forecasts = []
    for h in range(periods):
        forecasts.append(level + (h + 1) * trend + seasons[(len(data) + h) % s])
    rmse = _rmse(residuals)
    return {
        "method": "holt_winters_additive",
        "parameters": {
            "alpha": round(best_alpha, 4),
            "beta": round(best_beta, 4),
            "gamma": round(best_gamma, 4),
            "seasonal_periods": s,
        },
        "fitted_values": [round(v, 4) for v in fitted],
        "forecasts": [round(v, 4) for v in forecasts],
        "rmse": round(rmse, 4),
        "forecast_interval_95": _naive_interval(forecasts, rmse, 1.96),
        "final_level": round(level, 4),
        "final_trend": round(trend, 4),
        "seasonal_components": [round(v, 4) for v in seasons],
        "interpretation": _interpret(data, forecasts, "holt_winters"),
    }


def _hw_fit(
    data: list[float],
    s: int,
    alpha: float,
    beta: float,
    gamma: float,
) -> tuple[float, float, list[float], list[float], list[float]]:
    # Initialization: first season = mean of first s points; seasonal = data - level
    level = sum(data[:s]) / s
    # Initial trend via average of first two seasons
    if len(data) >= 2 * s:
        trend = (sum(data[s : 2 * s]) / s - sum(data[:s]) / s) / s
    else:
        trend = (data[s - 1] - data[0]) / max(s - 1, 1)
    seasons = [data[i] - level for i in range(s)]
    fitted = [level + seasons[0]]
    for t in range(1, len(data)):
        season_idx = t % s
        new_level = alpha * (data[t] - seasons[season_idx]) + (1 - alpha) * (level + trend)
        new_trend = beta * (new_level - level) + (1 - beta) * trend
        new_season = gamma * (data[t] - new_level) + (1 - gamma) * seasons[season_idx]
        seasons[season_idx] = new_season
        level, trend = new_level, new_trend
        fitted.append(level + trend + seasons[(t + 1) % s])
    residuals = [data[t] - fitted[t] for t in range(len(data))]
    return level, trend, seasons, fitted, residuals


def _tune_alpha(data: list[float], fit_fn) -> float:
    """Grid-search alpha to minimize RMSE."""
    best = (float("inf"), 0.3)
    for a in [0.05, 0.1, 0.15, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]:
        _, residuals = fit_fn(data, a)
        rmse = _rmse(residuals)
        if rmse < best[0]:
            best = (rmse, a)
    return best[1]


def _tune_holt(data: list[float], alpha: float | None, beta: float | None) -> tuple[float, float]:
    grid = [0.1, 0.2, 0.3, 0.5, 0.7, 0.9]
    a_grid = [alpha] if alpha is not None else grid
    b_grid = [beta] if beta is not None else grid
    best = (float("inf"), 0.3, 0.1)
    for a in a_grid:
        for b in b_grid:
            _, _, _, residuals = _holt_fit(data, a, b)
            rmse = _rmse(residuals)
            if rmse < best[0]:
                best = (rmse, a, b)
    return best[1], best[2]


def _tune_hw(
    data: list[float], s: int, alpha: float | None, beta: float | None, gamma: float | None
) -> tuple[float, float, float]:
    grid = [0.1, 0.3, 0.5, 0.7]
    a_grid = [alpha] if alpha is not None else grid
    b_grid = [beta] if beta is not None else grid
    g_grid = [gamma] if gamma is not None else grid
    best = (float("inf"), 0.3, 0.1, 0.3)
    for a in a_grid:
        for b in b_grid:
            for g in g_grid:
                _, _, _, _, residuals = _hw_fit(data, s, a, b, g)
                rmse = _rmse(residuals)
                if rmse < best[0]:
                    best = (rmse, a, b, g)
    return best[1], best[2], best[3]


def _rmse(residuals: Sequence[float]) -> float:
    if not residuals:
        return 0.0
    return (sum(r * r for r in residuals) / len(residuals)) ** 0.5


def _naive_interval(forecasts: list[float], rmse: float, z: float) -> list[dict]:
    """Naive prediction interval: forecast ± z * rmse * sqrt(h).

    This widens the interval for longer horizons. Not as good as a proper
    model-based interval but honest about growing uncertainty.
    """
    out = []
    for h, f in enumerate(forecasts, start=1):
        half = z * rmse * math.sqrt(h)
        out.append({
            "horizon": h,
            "forecast": round(f, 4),
            "lower": round(f - half, 4),
            "upper": round(f + half, 4),
        })
    return out


def _interpret(data: Sequence[float], forecasts: Sequence[float], method: str) -> str:
    last = data[-1]
    next_forecast = forecasts[0]
    change = (next_forecast - last) / max(abs(last), 1e-9) * 100
    direction = "up" if change > 0.5 else "down" if change < -0.5 else "flat"
    method_hint = {
        "simple": "no trend/seasonality assumed — forecast is a flat line",
        "holt": "trend projected forward, no seasonality",
        "holt_winters": "trend + seasonal pattern projected forward",
    }.get(method, "")
    return f"{method_hint}. Next period {direction} from {last:.2f} to {next_forecast:.2f} ({change:+.1f}%)"


def render(result: dict) -> str:
    """ASCII report."""
    lines = []
    lines.append("=" * 60)
    lines.append(f"  TIME-SERIES FORECAST — method: {result['method']}")
    lines.append("=" * 60)
    params = ", ".join(f"{k}={v}" for k, v in result["parameters"].items())
    lines.append(f"  Parameters:  {params}")
    lines.append(f"  Fit RMSE:    {result['rmse']:.4f}")
    lines.append("  " + "-" * 50)
    lines.append("  Forecasts (with 95% interval):")
    for row in result["forecast_interval_95"]:
        lines.append(
            f"    t+{row['horizon']}: {row['forecast']:>10.4f}  "
            f"[{row['lower']:>10.4f}, {row['upper']:>10.4f}]"
        )
    lines.append("")
    lines.append(f"  {result['interpretation']}")
    lines.append("=" * 60)
    return "\n".join(lines) + "\n"
