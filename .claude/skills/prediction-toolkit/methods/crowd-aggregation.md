# Method 5: Crowd Aggregation

## Core idea

Many independent estimates average out to something better than any individual. When information is distributed across people (or models), aggregation beats picking one expert.

## When to reach for it

- You have **multiple independent forecasters** (experts, analysts, models)
- There's a **liquid prediction market** for your question (elections, macro events)
- You can run a **Delphi process** (expert rounds with anonymous revision)
- You want to **ensemble multiple ML models** for robustness

## When NOT to use it

- Only one source of information (just use it)
- Forecasters are correlated (they read the same news, consulted each other) — averaging doesn't help
- The question is technical and most voters don't have the expertise (wisdom-of-crowds ≠ anti-expertise)

## Five approaches

### 1. Simple averaging
Mean or median of N forecasts. Cheap, effective, hard to beat.

### 2. Weighted averaging (Brier-weighted)
Weight forecasters by their past accuracy (Brier score). Better than flat averaging when some forecasters are known to be more reliable.

### 3. Prediction markets
- **Polymarket** (crypto) — real-money betting on political/sports/macro events
- **Kalshi** (regulated US) — CFTC-regulated event markets
- **Manifold** (play-money) — lower barriers, still predictive
- **Metaculus** — non-monetary, calibration-focused, good for long-horizon
Prices = implicit probabilities. Watch for **liquidity** and **resolution source**.

### 4. Delphi method
Expert round 1: anonymous estimates.
Round 2: experts see distribution + reasoning, revise.
Round 3: converge. Used in tech forecasting, medicine, policy.

### 5. Superforecaster protocols (Tetlock)
- Break questions into sub-questions
- Consider base rates
- Update incrementally on new evidence
- Track calibration
- Rotate teams to avoid groupthink

Good Judgment Project found trained amateurs using these protocols beat CIA analysts by 30%.

## Combining crowd with this toolkit

| Your situation | Combination |
|---|---|
| Have N forecasts, want probability distribution | Bootstrap the forecasts → get CI on the mean |
| Running A/B test, have prior from similar tests | Bayesian update (prior from crowd, evidence from experiment) |
| Market price says 30%, your model says 60% | Weighted combine (using your model's track record) |
| Want quantified uncertainty beyond a point estimate | Monte Carlo with crowd estimates as input distributions |

## Implementation pattern

```python
# Simple ensemble
forecasts = [0.3, 0.35, 0.4, 0.25, 0.45]
from engine import bootstrap_ci
ci = bootstrap_ci(forecasts, stat="mean", n_resamples=5000)
# Now you have a 95% CI on the consensus estimate
```

## Watch out for

- **Groupthink** — social pressure destroys independence
- **Correlated errors** — everyone reads the same NYT article
- **Cherry-picking experts** — pick a diverse set, not just agreeing ones
- **Resolution criteria gaming** — if the market can be manipulated near close, prices lie
- **Thin markets** — low liquidity = noisy prices

## External reading

- Tetlock, "Superforecasting" (2015)
- Galton, "Vox Populi" (1907) — the ox-weight origin story
- Good Judgment Project: https://goodjudgment.com/
- Metaculus track record: https://www.metaculus.com/
