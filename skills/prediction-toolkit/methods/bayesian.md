# Method 3: Bayesian Inference

## Core idea

Start with a prior belief. Update it with evidence. Get a posterior belief. Probability *is* belief, updated rationally by Bayes' rule:

`P(H | E) = P(E | H) × P(H) / P(E)`

## When to reach for it

- You have a **prior** (from past experiments, expert judgment, domain knowledge)
- You have new **evidence** and want to update
- You need **calibrated uncertainty** (credible intervals, not just point estimates)
- **Small-sample** rate estimation (A/B tests, CTR, hit rate)
- **Sequential decision-making** — evidence arrives over time

## When NOT to use it

- No prior available → use frequentist methods or bootstrap
- Large sample where the prior barely matters → any method works, pick simplest
- The question is causal, not inferential → use causal methods

## What's implemented here

### 1. Simple probability update

```python
from engine import probability_update
# Medical test: 1% prevalence, 99% sensitivity, 5% false positive
result = probability_update(prior=0.01, likelihood_given_h=0.99, likelihood_given_not_h=0.05)
# → posterior: 16.7% (not 99% — base rate dominates)
```

Use for:
- Diagnostic tests
- Fraud detection ("how likely fraud given this signal")
- Any P(H | E) where you can specify the likelihoods

### 2. Beta-Binomial conjugate update

```python
from engine import beta_binomial_update
# Prior: rate ≈ 5% (Beta(5, 95)). Evidence: 3 out of 50 trials.
result = beta_binomial_update(alpha=5, beta=95, successes=3, trials=50)
# → posterior: Beta(8, 142), mean 5.3%, 95% CI [2.6%, 9.3%]
```

Use for:
- A/B test analysis (conversion rates)
- CTR estimation on new ads
- Any rate/probability with a prior

## What's NOT implemented (external)

### MCMC (Markov Chain Monte Carlo)
For complex posteriors where no conjugate form exists. Sample from the posterior by constructing a Markov chain.

Python: `PyMC`, `NumPyro`, `Stan` (via `pystan`).

Use when:
- Multiple parameters with complex interactions
- Hierarchical models
- The conjugate shortcut doesn't apply

### Bayesian networks
DAG of variables, each with conditional probability tables. Propagate evidence through the graph.

Python: `pgmpy`, `pomegranate`.

Use for:
- Medical diagnosis with many symptoms
- Risk assessment with dependency structure
- Any problem where variables condition on each other

### Hidden Markov Models
State is hidden, observations are noisy. Forward/backward/Viterbi algorithms.

Python: `hmmlearn`, `pomegranate`.

Use for:
- Speech recognition
- Bioinformatics (gene prediction)
- Activity recognition from sensor data

### Gaussian processes
Nonparametric Bayesian regression. Great for small data + smooth functions + need for uncertainty.

Python: `scikit-learn`, `GPyTorch`.

## Decision tree

```
Do you have a prior belief about the outcome?
├── NO → frequentist methods / bootstrap
└── YES → what's the evidence shape?
    ├── Binary test (positive/negative) → probability_update
    ├── Successes / trials (rate) → beta_binomial_update
    ├── Multiple parameters, complex → MCMC (PyMC)
    ├── Variable network with dependencies → Bayesian network (pgmpy)
    ├── Hidden states + observations → HMM (hmmlearn)
    └── Continuous function, small data → Gaussian process (sklearn)
```

## Integration patterns

1. **Bayesian + Monte Carlo** — posterior as input distribution to a downstream simulation.
2. **Bayesian + forecast** — posterior on a forecasting model's parameters → uncertainty bands on forecasts.
3. **Bayesian update chain** — observe evidence in batches, update sequentially (the posterior of one batch becomes the prior for the next).

## Prior choices

Common priors for rates:
- `Beta(1, 1)` — uniform ("I know nothing")
- `Beta(2, 2)` — weakly centered on 50%
- `Beta(2, 8)` — weak prior on ~20%
- `Beta(5, 95)` — strong prior on ~5%
- `Beta(10, 40)` — moderate prior on ~20%

Strength of prior ≈ (alpha + beta). The bigger, the harder it is for evidence to move the posterior.

## Critical habits

- **State your prior explicitly** — write it down, justify it, stress-test with alternatives
- **Check prior sensitivity** — does the answer change much with a different prior? If yes, you need more data
- **Report credible intervals, not just point estimates**
- **Update sequentially, not retrospectively** — don't look at the data to pick the prior

## External reading

- McElreath, "Statistical Rethinking" (2020) — the best intro
- Gelman et al., "Bayesian Data Analysis" — the standard reference
- PyMC docs: https://www.pymc.io/
- Downey, "Think Bayes" (free) — Python-first intro
