# Method 4: Simulation (Monte Carlo + bootstrap)

## Core idea

Build a model of the world and run many synthetic histories. The distribution of outcomes across simulations tells you what's likely and what's possible.

Two styles are implemented/referenced from this toolkit:

## A. Monte Carlo simulation

**Where:** The sibling skill `skills/monte-carlo-predictor/`.

**When:** You have uncertain inputs + a known formula connecting them to an outcome. You want the full distribution of the outcome, not just a point estimate.

**Example:** "Should we migrate Postgres to MongoDB?" — inputs: migration weeks (triangular), ops cost delta (normal), perf gain (normal). Outcome: 3-year net value. Run 20,000 trials, report P5/P50/P95 + which variable drives variance most.

**Tools:** `from engine import simulate` in the monte-carlo-predictor skill, or `python -m engine run spec.yaml` from that skill's directory.

See `skills/monte-carlo-predictor/engine/agent_contract.md` for the full API.

## B. Bootstrap resampling

**Where:** `engine/bootstrap.py` in this skill.

**When:** You have a real dataset (not a formula) and want a confidence interval on a statistic (mean, median, ratio, correlation, etc.) without assuming a distribution.

**Example:** "I ran 20 trials of a new pricing algorithm. Mean revenue was $12.40. What's the 95% CI?"

```python
from engine import bootstrap_ci
ci = bootstrap_ci(
    data=[12.1, 11.8, 13.2, 12.5, 12.0, 13.1, 11.9, 12.8, 12.3, 12.6,
          11.5, 13.0, 12.2, 12.9, 11.7, 12.4, 12.1, 13.3, 12.7, 12.0],
    stat="mean",
    n_resamples=10000,
    ci=0.95,
)
# → observed: 12.41, 95% CI: [12.17, 12.66]
```

## When to use which

| Situation | Method |
|---|---|
| Uncertain inputs + formula → outcome | Monte Carlo |
| Real sample + need CI on a statistic | Bootstrap |
| Small sample (<30) + no distribution assumption | Bootstrap |
| Business decision ("should we do X?") | Monte Carlo |
| Quick sanity check on an estimate | Bootstrap |
| Tail risk ("what's the P99 worst case?") | Monte Carlo |

## Other simulation families (not implemented, but see first-principles.md)

- **Agent-based modeling** — many interacting agents, emergent behavior. Python: `mesa`.
- **Discrete event simulation** — queues and events. Python: `SimPy`.
- **System dynamics** — stock/flow with feedback. Python: `pysd`.

## Integration patterns

1. **Monte Carlo over a Bayesian posterior** — update your prior with `beta_binomial_update`, then use the posterior as an input distribution in Monte Carlo.
2. **Bootstrap inside ML** — resample training data, refit model, bootstrap the predictions for conformal-like intervals.
3. **Monte Carlo over a forecast** — take `forecast()` output, treat the point forecast + residual stddev as a normal distribution in a larger Monte Carlo simulation.

## External reading

- "Monte Carlo Statistical Methods" (Robert & Casella)
- "An Introduction to the Bootstrap" (Efron & Tibshirani)
- monte-carlo-predictor `SKILL.md` and `engine/README.md` for the full API
