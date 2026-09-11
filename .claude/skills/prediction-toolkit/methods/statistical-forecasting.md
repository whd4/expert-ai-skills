# Method 1: Statistical Forecasting

## Core idea

You have a time series — values observed at regular intervals. Extract the pattern (level, trend, seasonality) and project it forward.

## When to reach for it

- Historical data with a **time axis** (daily, weekly, monthly, ...)
- You want to **forecast the next N periods**
- The pattern is **reasonably stable** (no major regime changes)
- You need **prediction intervals** alongside the point forecast

## When NOT to use

- No historical data → use Monte Carlo or expert elicitation
- Many features besides time → use machine learning
- You need to answer "what if we changed X?" → use causal inference

## Methods, smallest to largest

### Simple exponential smoothing (SES) — implemented
No trend, no seasonality. Weighted average of past values, weights decay exponentially.

```python
from engine import forecast
result = forecast([10.0, 10.2, 9.8, 10.1, 10.0], periods=3, method="simple")
```

### Holt's linear trend — implemented
Level + trend. Projects the trend forward.

```python
result = forecast([10, 12, 14, 16, 18, 20], periods=3, method="holt")
# forecasts: [22, 24, 26]
```

### Holt-Winters — implemented
Level + trend + seasonality (additive). Needs ≥2 full seasons of data.

```python
# Quarterly data, repeating Q1 high Q3 low
series = [100, 120, 110, 90] * 4
result = forecast(series, periods=4, method="holt_winters", seasonal_periods=4)
```

### ARIMA — external (statsmodels)
Auto-regressive integrated moving average. Handles stationarity, seasonality, trend more formally. Better confidence intervals than exponential smoothing.

```python
# external
import statsmodels.api as sm
model = sm.tsa.ARIMA(series, order=(1, 1, 1)).fit()
forecast = model.forecast(steps=3)
```

Use ARIMA when:
- You have 50+ observations
- You need formal statistical guarantees
- You're willing to do model selection (p, d, q)

### Prophet — external (Meta)
Automated trend + multi-seasonality + holidays. Handles missing data, outliers.

```bash
pip install prophet
```

Use Prophet when:
- You have daily data with strong weekly/yearly patterns
- You want defaults to mostly work
- You have business calendars (holidays, promotions)

### State-space / Kalman — external (statsmodels, filterpy)
Recursive estimation from noisy data. Good when:
- Data arrives incrementally
- You want to fuse multiple noisy sources
- Applications: navigation, trading, sensor fusion

## Decision tree

```
How much data do you have?
├── <10 points → not enough; use Monte Carlo or expert judgment
├── 10-30 → simple ES or Holt (this toolkit)
├── 30-100 + seasonality → Holt-Winters (this toolkit) or Prophet
├── 100+ + need rigorous CI → ARIMA
└── 1000+ + many features → machine learning (XGBoost, transformers)
```

## Combining with other methods

1. **Forecast + Monte Carlo** — point forecast as input distribution mean, residual stddev as the spread. Simulate downstream impact.
2. **Forecast + Bayesian** — forecast gives you expected value; Bayesian gives you the uncertainty via prior on parameters.
3. **Forecast + bootstrap** — resample residuals, get empirical prediction intervals without assuming normality.

## Known failure modes

- **Structural breaks** — COVID, regime changes. Models trained on pre-break data fail on post-break.
- **Trend extrapolation** — exponential-looking trends rarely continue forever; Holt will happily extrapolate them off the chart.
- **Insufficient history for seasonality** — need at least 2 full seasons.
- **Multiple overlapping seasons** — monthly + yearly? Use Prophet or hand-craft.

## External reading

- Hyndman & Athanasopoulos, "Forecasting: Principles and Practice" (free: https://otexts.com/fpp3/)
- Prophet paper: Taylor & Letham 2018
- statsmodels docs: https://www.statsmodels.org/stable/tsa.html
