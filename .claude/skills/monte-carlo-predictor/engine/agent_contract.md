# Monte Carlo Engine — Agent Contract

**Purpose:** This document is the contract other agents (Hermes, AEGIS, OpenClaw-native skills, any MCP client) use to call the Monte Carlo engine. It is stable across versions — agents should target this contract, not the engine internals.

---

## The Four Integration Modes

### 1. Python API (in-process)

```python
from engine import simulate

report = simulate({
    "trials": 10000,
    "variables": {"x": {"distribution": "normal", "mean": 10, "stddev": 2}},
    "outcomes": {"y": "x * 3"},
})
print(report["outcomes"]["y"]["stats"]["mean"])  # ~30
```

### 2. CLI

```bash
python -m engine run spec.yaml                # text report
python -m engine run spec.yaml --format json  # machine-readable
python -m engine run spec.yaml --charts ./out # + matplotlib PNGs
```

### 3. JSON over stdin/stdout (pipe between agents)

```bash
echo '{"trials":5000,"variables":{"x":{"distribution":"uniform","low":0,"high":1}},"outcomes":{"y":"x*100"}}' \
  | python -m engine run - --format json
```

### 4. MCP Server

```bash
python -m engine.mcp_server   # speaks MCP over stdio
```

Exposes tools:
- `run_simulation(spec: object) -> object`
- `list_distributions() -> object`
- `describe_distribution(name: string) -> object`

Any MCP-compatible agent can register this server and invoke the tools.

---

## Spec Schema

```yaml
trials: 10000               # optional, default 10000, positive integer
seed: 42                    # optional, for reproducibility

variables:                  # required, at least one
  <name>:
    distribution: <kind>    # see Distributions below
    # ...distribution-specific params...

outcomes:                   # optional
  <name>: "<expression>"    # Expression over variables & prior outcomes
```

Outcomes may reference variables and earlier outcomes by name. Later outcomes see earlier ones.

## Distributions

| Name | Params | Notes |
|------|--------|-------|
| `uniform` | `low`, `high` | Continuous uniform |
| `normal` | `mean`, `stddev` | Gaussian |
| `triangular` | `low`, `likely`, `high` | Three-point estimation (best/likely/worst) |
| `beta` | `alpha`, `beta`, `low?` (0), `high?` (1) | Optionally rescaled |
| `lognormal` | `mean`, `stddev` | mean/stddev are of the underlying normal |
| `poisson` | `lam` | Count with rate λ |
| `choice` | `options`, `weights?` | Discrete pick (only numeric options if used in expressions) |
| `constant` | `value` | Deterministic |

## Expression Language (safe-evaluated)

Outcome expressions support arithmetic, comparison, boolean, `if/else`, and these functions:
`min, max, abs, round, sqrt, log, exp, floor, ceil, clip`

**Forbidden:** attribute access, subscript, comprehensions, lambdas, imports, any name not in variables + functions. Passing user input as an expression is safe — it cannot execute arbitrary code.

Comparisons (`>`, `<=`, etc.) return 0.0 or 1.0, so boolean outcomes become probabilities automatically.

## Report Format (what you get back)

```json
{
  "trials": 10000,
  "seed": 42,
  "variables": {
    "x": {"mean": ..., "median": ..., "stddev": ..., "p5": ..., "p50": ..., "p95": ..., "min": ..., "max": ...}
  },
  "outcomes": {
    "y": {
      "stats": {"mean": ..., "median": ..., "stddev": ..., "p5": ..., "p95": ..., ...},
      "tornado": [
        {"variable": "x", "correlation": 0.93, "impact": "high"},
        ...
      ],
      "probability_true": 0.72   // only present for 0/1-valued outcomes
    }
  }
}
```

## Agent Usage Patterns

### Pattern: "Should I do X?"
1. Agent gathers decision context from user
2. Agent generates a spec (variables = uncertain drivers, outcomes = cost/benefit/success)
3. Agent calls `run_simulation(spec)`
4. Agent interprets `probability_true` and `tornado` to write a recommendation
5. Agent stores spec + report for later calibration

### Pattern: "How bad could this get?"
1. Agent generates worst-case-heavy spec (fat-tailed distributions)
2. Reads P5 of cost/failure outcomes
3. Reports P5-to-P95 bands with early-warning triggers

### Pattern: "Which option is best?"
1. Agent generates one spec per option (same outcomes, different variable specs)
2. Calls `run_simulation` per option
3. Compares means, P5s, and variance to rank

### Pattern: "Compose with other tools"
- Upstream agent generates spec → pipes JSON → this engine → pipes JSON to downstream agent
- E.g. AEGIS security agent scans code → suggests risk variables → Monte Carlo simulates blast radius → reporting agent writes summary

## Versioning

The contract (this document) is v1.0.0. The engine internals may change freely so long as:
- Input spec schema remains backward-compatible
- Output report shape stays the same
- Named distributions behave the same for the same parameters
- Safe-eval expression whitelist only grows, never shrinks

Any breaking change bumps the contract version and is called out in this file.
