# Monte Carlo Methodology Reference

## Why Monte Carlo?

Monte Carlo simulation is the appropriate methodology for software project prediction because:

1. **Multiple interacting uncertainties.** Projects have many variables (team, tech, market, competition) that interact in complex ways. Monte Carlo models this naturally.

2. **Probability distributions, not point estimates.** Instead of saying "we'll have 500 users," Monte Carlo says "we have a 60% chance of 300-700 users, with 10% chance above 1000 and 10% chance below 100."

3. **Tail risk visibility.** The worst 5-10% of outcomes (tail risk) often matter more than the average. Monte Carlo makes these visible.

4. **Decision support under uncertainty.** By comparing scenario distributions, you can make decisions that are robust across multiple futures rather than optimizing for a single predicted future.

## The Five-Scenario Framework

We use exactly 5 scenarios to span the outcome distribution:

```
Probability Distribution of Outcomes

    S5     S4        S3          S2      S1
    │      │         │           │       │
    ▼      ▼         ▼           ▼       ▼
    ┌──────┬─────────┬───────────┬───────┐
    │      │         │           │       │
────┴──────┴─────────┴───────────┴───────┴────→ Outcome Quality
  Worst  Pessimistic  Base     Optimistic Best
  (10%)   (20%)      (35%)      (25%)    (10%)
```

### Scenario Probability Assignment

| Scenario | Probability Range | Characteristics |
|---|---|---|
| S1: Best Case | 5-15% | Everything goes right. Requires multiple favorable outcomes aligning. |
| S2: Optimistic | 20-30% | Most things go well. Achievable with good execution. |
| S3: Base Case | 30-40% | Realistic middle path. Historical base rates apply. |
| S4: Pessimistic | 15-25% | Multiple problems compound. Key risks materialize. |
| S5: Worst Case | 5-15% | Cascading failures. Requires multiple simultaneous failures. |

**Total must equal 100%.** Default: 10% + 25% + 35% + 20% + 10% = 100%

### Calibration Rules

1. **Base rates dominate.** Most software projects plateau (S3). Hypergrowth (S1) and collapse (S5) are exceptions.

2. **Asymmetric tails.** Downside moves faster than upside. A project can go from healthy to dead in weeks; going from healthy to dominant takes years.

3. **Correlated risks.** Bad events cluster. Security breach → reputation damage → user churn → revenue loss → team departures. Model correlations, not independence.

4. **Confidence decay.** Predictions get less reliable over time:
   - 30 days: High confidence (±20% on most metrics)
   - 90 days: Medium confidence (±40%)
   - 12 months: Low confidence (±100% or more)

## Time Horizons

### 30 Days (Sprint-Level)
- **Appropriate predictions:** Feature completion, bug counts, velocity, immediate blockers
- **Inappropriate predictions:** Market adoption, revenue, team growth
- **Accuracy target:** ±20%

### 90 Days (Quarter-Level)
- **Appropriate predictions:** MVP milestones, initial user traction, key hire completion
- **Inappropriate predictions:** Market position, long-term revenue trajectory
- **Accuracy target:** ±40%

### 12 Months (Annual)
- **Appropriate predictions:** Order-of-magnitude user/revenue ranges, team size, product maturity level
- **Inappropriate predictions:** Exact numbers, specific feature completion
- **Accuracy target:** Within 2x (i.e., 500-2000 users when predicting 1000)

## Updating Predictions

Monte Carlo predictions should be **continuously updated** as new information arrives:

### Weekly Update (Lightweight)
- New facts that change scenario probabilities
- Did any early warning triggers fire?
- Shift probabilities but don't rerun full analysis

### Monthly Update (Full Refresh)
- Re-gather all project health indicators
- Re-assess decision variables
- Recalculate all scenario forecasts
- Check: Did actual trajectory match predictions? Calibrate if not.

### Triggered Update (Event-Driven)
Immediately rerun when:
- Major team change (hire/departure)
- Significant customer win/loss
- Security incident
- Major competitive move
- Architecture decision locked in
- Funding event

## Probability Math Reference

### Expected Value
```
E[X] = Σ (probability_i × outcome_i)

Example: Expected MRR at 12 months
E[MRR] = (0.10 × $35K) + (0.25 × $12K) + (0.35 × $3K) + (0.20 × $400) + (0.10 × $0)
       = $3,500 + $3,000 + $1,050 + $80 + $0
       = $7,630/month
```

### Confidence Intervals
- **80% CI (P10-P90):** Wide interval; excludes only extreme 10% on each end
- **95% CI (P5-P95):** Very wide interval; almost all outcomes fall within
- **50% CI (P25-P75):** Narrow interval; represents "typical" outcomes

### Bayes' Update (Simplified)
When new evidence arrives, update scenario probabilities:

```
P(Scenario | Evidence) ∝ P(Evidence | Scenario) × P(Scenario)

Example: A key developer just quit.
- P(S4|quit) increases: This is consistent with pessimistic scenarios
- P(S5|quit) increases slightly: Could cascade
- P(S1|quit) decreases: Hard to achieve best case with key loss
- P(S2|quit) decreases: Optimistic now harder
- P(S3|quit) roughly stable: Base case can absorb one departure
```

## Decision Theory Integration

### Expected Value Maximization
Choose the path that maximizes expected outcome:
```
Choose A if E[Outcome_A] > E[Outcome_B]
```

### Risk-Adjusted Decision Making
When downside is severe, maximize expected value while constraining worst-case:
```
Choose the option where:
1. E[Outcome] is acceptable
2. P(Worst Case) is below threshold (e.g., <15%)
3. Worst Case outcome is survivable
```

### Real Options Thinking
Prefer decisions that preserve optionality:
```
When uncertain:
- Don't lock in irreversible choices
- Choose paths that allow course correction
- Value flexibility even if expected value is slightly lower
```

## Common Cognitive Biases to Avoid

| Bias | Description | Antidote |
|---|---|---|
| Anchoring | First number dominates thinking | Generate scenarios before estimating probabilities |
| Overconfidence | Underestimate uncertainty | Use historical base rates, widen CIs |
| Planning fallacy | Underestimate completion time | Add 50-100% buffer to time estimates |
| Confirmation bias | Seek evidence for preferred scenario | Explicitly argue for S4/S5 before concluding S2 |
| Availability | Recent/vivid events feel more likely | Use actual data, not memorable anecdotes |
| Sunk cost | Continue bad path due to past investment | Evaluate from today forward, ignore sunk costs |

## Quality Checklist for Predictions

Before delivering a Monte Carlo prediction, verify:

- [ ] Scenario probabilities sum to 100%
- [ ] Best case probability ≤ 15%
- [ ] Worst case probability ≤ 15%
- [ ] Base case is most likely (30-40%)
- [ ] 12-month confidence intervals are at least ±50%
- [ ] Tail risks (S4, S5) are explicitly described
- [ ] All forecasts are ranges, not point estimates
- [ ] Divergences detected are tied to real code/data findings
- [ ] Recommendations are actionable within 30 days
- [ ] Early warning triggers are specific and measurable
