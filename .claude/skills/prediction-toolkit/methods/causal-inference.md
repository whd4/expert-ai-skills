# Method 6: Causal Inference

## Core idea

Correlation is not causation. If you want to predict **what would happen if you intervene** (change X), you need a **causal model**, not just a predictive one.

A model that says "users who see the banner convert 20% more" does not mean showing the banner *causes* conversion. They may just be more engaged users already.

## When to reach for it

- The question has the word **"if"** or **"would"**: "What if we raised the price?", "Would we have lost the deal without Y?"
- You're evaluating a **decision** or **intervention**
- You need to strip out **confounders** — variables that influence both cause and outcome
- Predictions from ML are not actionable (correlational)

## When NOT to use it

- You only need forecasts, not explanations — use ML or forecasting
- You're estimating a rate or probability — use Bayesian
- You have a controlled experiment (A/B test) — simple comparison works, causal inference is for **observational** data

## The core techniques

### 1. Randomized controlled trials (RCT / A/B test)
The gold standard. Random assignment breaks all confounding. If you can run one, use it.
Combine with Bayesian update (this toolkit) for small-sample A/B analysis.

### 2. Difference-in-differences (DiD)
Compare the change in outcome for treated group vs. control group.
Requires **parallel trends** assumption (both groups would have moved similarly without treatment).
Used in economics, public policy.

### 3. Instrumental variables (IV)
Find a variable Z that:
- Affects the treatment X
- Has NO direct effect on outcome Y except through X
Example: "Does more schooling → higher wages?" → use compulsory schooling laws (varies by state/year) as the IV.
Implemented in Python: `linearmodels` package.

### 4. Propensity score matching
Match treated units to similar untreated units. Compare outcomes.
Python: `causalinference`, `DoWhy`.

### 5. Pearl's do-calculus
Formal framework separating `P(Y | X)` (observation) from `P(Y | do(X))` (intervention).
Draw a **causal DAG** showing which variables affect which. Let the graph tell you what you can identify from data.
Python: `DoWhy` (Microsoft), `causalnex`.

### 6. Synthetic control
Construct a weighted combination of untreated units that matches the treated unit pre-intervention. The divergence post-intervention estimates the effect.
Used in: minimum wage studies, policy evaluation.

## Decision tree

```
Can you run an experiment?
├── YES → RCT / A/B test (easiest path)
└── NO → you have observational data
    ├── Have pre/post data for both groups? → Difference-in-differences
    ├── Have a natural experiment? → Instrumental variables
    ├── Have many units, can match? → Propensity matching
    ├── Have one affected unit, many comparables? → Synthetic control
    └── Have a rich causal model? → Pearl's do-calculus + DoWhy
```

## Integration with this toolkit

Causal inference gives you a point estimate of a treatment effect. To quantify uncertainty:

1. **Bootstrap the estimate** — resample your data, recompute the causal effect, get a CI
2. **Bayesian update over effect size** — prior belief about effect + observed data → posterior
3. **Monte Carlo over assumption violations** — if you're unsure about parallel trends, simulate violations and see how the answer moves

## Key mental shifts

- Drawing a DAG before looking at data is the single highest-value habit
- "Control for variable X" — verify X is actually a confounder, not a collider (controlling for a collider *creates* spurious association)
- If a model is purely predictive, its coefficients are NOT causal effects — don't interpret them as such
- Treatment effects are **heterogeneous** — the average effect can hide important subgroup differences

## Essential reading

- Pearl, "The Book of Why" (2018) — accessible intro
- Angrist & Pischke, "Mostly Harmless Econometrics" — practical methods
- Hernán & Robins, "Causal Inference: What If" (free PDF) — rigorous treatment
- `DoWhy` docs: https://www.pywhy.org/dowhy/

## Fast sanity checks

Before believing any causal claim:
1. What's the treatment? Is assignment randomized or self-selected?
2. What's the confounder? Could X and Y both be caused by Z?
3. What's the counterfactual? What would have happened without treatment?
4. How big is the effect size? Is it practically meaningful, or just statistically significant?
5. Does it generalize? Or is it specific to this sample?
