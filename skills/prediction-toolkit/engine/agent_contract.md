# Prediction Toolkit — Agent Contract v1.0

A stable interface that any agent (Claude Code subagents, Hermes, AEGIS, OpenClaw agents, future MCP clients) can target. This contract will not change within v1.x without a deprecation warning.

## Four integration paths

Any of these work from any agent runtime:

### 1. Python API (in-process)

```python
from engine import (
    bootstrap_ci,
    beta_binomial_update,
    probability_update,
    forecast,
    recommend_method,
)

# Recommendation
rec = recommend_method("forecast next quarter's revenue")
# → {"top_recommendation": {...}, "candidates": [...], "reasoning": "..."}

# Bootstrap
ci = bootstrap_ci([1.2, 1.5, 0.9, 1.1, 1.3], stat="mean", ci=0.95)
# → {"observed": ..., "ci_lower": ..., "ci_upper": ..., ...}

# Bayesian
post = beta_binomial_update(alpha=2, beta=8, successes=3, trials=50)
# → {"prior": {...}, "posterior": {...}, "interpretation": "..."}

# Forecast
fc = forecast([100, 110, 105, 120, 130], periods=3)
# → {"method": ..., "forecasts": [...], "forecast_interval_95": [...]}
```

### 2. CLI (sub-agent via shell)

```bash
python -m engine router recommend "should we migrate databases"
python -m engine bootstrap --data 1,2,3,4,5 --stat mean --ci 0.95
python -m engine bayes probability --prior 0.01 --p-e-given-h 0.99 --p-e-given-not-h 0.05
python -m engine bayes beta --alpha 2 --beta 8 --successes 3 --trials 50
python -m engine forecast --series 100,110,105,120,130 --periods 3
```

Add `--format json` to any command for machine-readable output.

### 3. JSON stdin/stdout (agent-to-agent piping)

Single command, methods dispatched by `"method"` key:

```bash
echo '{"method":"bootstrap","data":[1,2,3,4,5],"stat":"mean","ci":0.95}' | python -m engine run -
echo '{"method":"beta_binomial_update","alpha":2,"beta":8,"successes":3,"trials":50}' | python -m engine run -
echo '{"method":"forecast","series":[100,110,105,120],"periods":3}' | python -m engine run -
echo '{"method":"recommend","problem":"forecast Q4 revenue"}' | python -m engine run -
```

Supported method values:
- `bootstrap`
- `probability_update`
- `beta_binomial_update`
- `forecast`
- `recommend`

### 4. MCP server (cross-runtime)

```bash
python -m engine.mcp_server
```

Tools exposed:
- `recommend_method(problem: str)` → routing recommendation
- `bootstrap_ci(data, stat?, n_resamples?, ci?, seed?)` → CI on a statistic
- `bayesian_probability_update(prior, likelihood_given_h, likelihood_given_not_h)` → P(H|E)
- `beta_binomial_update(alpha, beta, successes, trials)` → conjugate update
- `forecast_timeseries(series, periods?, method?, alpha?, beta?, gamma?, seasonal_periods?)` → forecast

Register with Claude Code via `.mcp.json` or your MCP client's config.

## Output contract

All methods return **JSON-serializable dicts**. Every result includes:

- `method`: name of the method used
- `interpretation`: human-readable one-line summary
- `caveats` (where applicable): list of limitation strings

Where relevant, results include:
- Point estimates with **confidence/credible intervals**
- Parameter values used (for reproducibility)
- Goodness-of-fit metrics (RMSE for forecasts)
- Honest flags when the sample is too small, the assumption questionable, etc.

## Input contract

All methods accept plain data types (lists, numbers, strings, booleans, dicts). No custom classes. This makes them safe to call from any language via JSON.

## Safety

- No `eval()`. All expression parsing (for Monte Carlo, via the sibling `monte-carlo-predictor` skill) uses AST whitelisting.
- All numeric inputs are validated (ranges, types, non-negative where required).
- Distribution parameters are checked before sampling.
- Random seeds are supported everywhere for reproducibility.

## Versioning

This contract follows semver. The `__version__` in `engine/__init__.py` is the authoritative version number. Breaking changes will bump the major version and be announced here.

## Errors

All methods raise `ValueError` with a clear message for bad inputs. The CLI returns non-zero exit code. The MCP server returns `{"error": "..."}` in the response.

## Composing methods

Common combinations:

```python
# Bayesian prior + Monte Carlo forward simulation
from engine import beta_binomial_update
from engine.bootstrap import bootstrap_ci

# Update your belief about a rate
post = beta_binomial_update(alpha=2, beta=8, successes=3, trials=50)
posterior_mean = post["posterior"]["mean"]

# Now use that rate inside a Monte Carlo spec (see monte-carlo-predictor skill)
# with distribution "beta" alpha=post["posterior"]["alpha"] beta=post["posterior"]["beta"]
```

```python
# Forecast + uncertainty via bootstrap
from engine import forecast, bootstrap_ci

# Historical data
series = [100, 110, 105, 120, 130, 125, 135, 140, 138, 145]

# Get point forecast
fc = forecast(series, periods=3)

# Bootstrap on residuals for prediction interval
residuals = [obs - fit for obs, fit in zip(series, fc["fitted_values"])]
residual_ci = bootstrap_ci(residuals, stat="stdev")
```

## Dependencies

- **Required:** Python 3.9+
- **Recommended:** `numpy` (10-100x faster for bootstrap)
- **Optional:** `mcp` (only for MCP server), `scipy`, `scikit-learn`, `statsmodels` (for external methods referenced in guides)

Pure-Python fallback is supported — the toolkit still works without numpy, just slower.

## Cross-project use

Three ways to expose this toolkit to other projects and agents:

1. **Global skill install** (for Claude Code across all projects):
   ```bash
   ln -s $(pwd)/skills/prediction-toolkit ~/.claude/skills/prediction-toolkit
   ```

2. **MCP registration** (for any MCP client):
   Add to `.mcp.json`:
   ```json
   {
     "mcpServers": {
       "prediction-toolkit": {
         "command": "python",
         "args": ["-m", "engine.mcp_server"],
         "cwd": "/path/to/skills/prediction-toolkit"
       }
     }
   }
   ```

3. **Package import** (from other Python projects):
   ```bash
   export PYTHONPATH=/path/to/skills/prediction-toolkit:$PYTHONPATH
   ```
   Then `from engine import recommend_method, bootstrap_ci, ...`

## Related skills

- **`monte-carlo-predictor`** — the simulation family (#4) is there. This toolkit routes to it for simulation problems. Do not reimplement Monte Carlo here.
