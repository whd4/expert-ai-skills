# Example: Postgres → MongoDB Migration Decision

This is a full worked example demonstrating the Monte Carlo engine on a real kind of decision. 20,000 trials, 10 uncertain variables, 6 outcome metrics.

## Scenario

A 2M-user SaaS built on Postgres is considering migrating to MongoDB for read scalability. Team of 5 engineers. Decision horizon: 3 years.

## Run It

```bash
./run.sh                       # text report with histograms + tornado
./run.sh --format json         # machine-readable JSON (for agent integration)
./run.sh --charts ./out        # + matplotlib PNGs in ./out
```

## The Spec — What We Modeled

10 uncertain variables with realistic distributions:

| Variable | Distribution | Why |
|----------|--------------|-----|
| `migration_weeks` | Triangular (6/10/24) | Classic three-point estimate |
| `team_disruption_pct` | Normal (μ=0.40, σ=0.12) | Symmetric uncertainty around 40% |
| `engineer_week_cost_usd` | Normal (μ=$5500, σ=$800) | Burdened rates vary a bit |
| `data_loss_probability` | Beta(2, 50) | Low probability, asymmetric |
| `data_loss_cost_usd` | Lognormal | Long right tail — disaster cost |
| `perf_gain_factor` | Triangular (0.85/1.25/1.8) | Real-world perf claims miss |
| `perf_value_per_unit_per_year_usd` | Triangular ($20k/$50k/$120k) | Business value is itself uncertain |
| `annual_ops_cost_delta_usd` | Normal (μ=$15k, σ=$20k) | Could go either way |
| `operational_sustainability` | Beta(5, 2) | Mean ~70% confidence team can sustain |

## The Verdict (seed=7, 20,000 trials)

```
=== Key decision outcomes ===
  should_migrate         P(true)=5.5%    ← the answer: no
  migration_pays_off     P(true)=7.2%
  big_win                P(true)=0.7%
  disaster               P(true)=64.7%   ← very likely to lose >$100k
  team_can_sustain       P(true)=76.2%

=== Net value over 3 years ===
  mean = -$138,618
  P5   = -$308,145   (1-in-20 worst case)
  P50  = -$134,635   (median — most typical outcome)
  P95  =   $18,600   (1-in-20 best case)

=== Top drivers of net value (tornado) ===
  - annual_ops_cost_delta_usd      r=-0.604  [high]    ← hosting costs kill it
  - team_disruption_pct            r=-0.433  [medium]  ← lost productivity
  - migration_weeks                r=-0.415  [medium]
  + perf_gain_factor               r=+0.374  [medium]
  - engineer_week_cost_usd         r=-0.213  [low]
```

## How to Read This

- **5.5% probability the migration is a good idea.** Not a coin flip — a clear no.
- **Median outcome loses $134k** over 3 years. Even in the optimistic P95 case, you barely break even.
- **The #1 driver is ongoing ops cost**, not migration time. That's the insight most people miss.
- **Performance gain helps**, but `perf_value_per_unit_per_year_usd * (perf_gain_factor - 1)` is a small number compared to 5 engineers × 13 weeks × 40% disruption × $5,500/week.

## What This Changes In Your Decision

Before the simulation: "MongoDB sounds faster, let's do it."
After the simulation: "We'd need ops costs to come in flat or negative AND a real 1.5x+ performance gain to have even a coin-flip chance. Not worth it without those commitments first."

**Next step:** If you still want to migrate, model **"MongoDB on current team's managed Atlas tier"** with different `annual_ops_cost_delta_usd` distributions. Get a real quote. Re-run. Decision changes as evidence sharpens.

## Integration with Other Agents

This example is agent-callable:

```python
# In a Python agent:
from engine import simulate
import yaml

spec = yaml.safe_load(open("examples/postgres-vs-mongo/spec.yaml"))
report = simulate(spec)
if report["outcomes"]["should_migrate"]["probability_true"] < 0.3:
    print("recommend against migration")
```

```bash
# Piping between CLI agents:
./run.sh --format json | other-agent --ingest monte-carlo-report
```

```python
# Via MCP (from any MCP-compatible agent):
# tool: run_simulation
# args: {"spec": <parsed yaml>}
# returns: full report dict
```
