# Prediction Toolkit

Route prediction problems to the right method. Covers 7 method families, with 4 implemented in-skill and 3 exposed as decision guides pointing at the right external library.

## Quick start

```bash
# From skills/prediction-toolkit/
# Get a recommendation for your problem
python3 -m engine router recommend "should we migrate to MongoDB?"

# Run a specific method
python3 -m engine bootstrap --data 1.2,1.5,0.9,1.1,1.3 --stat mean --ci 0.95
python3 -m engine bayes beta --alpha 2 --beta 8 --successes 3 --trials 50
python3 -m engine forecast --series 100,110,105,120,130 --periods 3

# Or JSON stdin/stdout
echo '{"method":"bootstrap","data":[1,2,3,4,5]}' | python3 -m engine run -

# Or MCP server
python3 -m engine.mcp_server

# Tests
python3 -m engine.tests.test_toolkit
```

## The 7 families

| # | Family | Implemented? |
|---|---|---|
| 1 | Statistical forecasting | ✅ `exponential_smoothing.py` |
| 2 | Machine learning | guide in `methods/machine-learning.md` |
| 3 | Bayesian inference | ✅ `bayesian_update.py` |
| 4 | Simulation (Monte Carlo + bootstrap) | ✅ `bootstrap.py` + sibling `monte-carlo-predictor` skill |
| 5 | Crowd aggregation | guide in `methods/crowd-aggregation.md` |
| 6 | Causal inference | guide in `methods/causal-inference.md` |
| 7 | First-principles / physics | guide in `methods/first-principles.md` |

## What lives where

```
skills/prediction-toolkit/
├── SKILL.md                    # The auto-loaded routing brain
├── README.md                   # This file
├── engine/
│   ├── router.py               # Heuristic: problem → recommended family
│   ├── bootstrap.py            # Bootstrap resampling
│   ├── bayesian_update.py      # Bayes' rule + Beta-Binomial conjugate
│   ├── exponential_smoothing.py# Simple / Holt / Holt-Winters forecasting
│   ├── cli.py                  # Unified CLI
│   ├── mcp_server.py           # MCP tool wrapper
│   ├── agent_contract.md       # Stable v1 API for other agents
│   └── tests/test_toolkit.py   # 18 passing integration tests
└── methods/
    ├── statistical-forecasting.md
    ├── machine-learning.md
    ├── bayesian.md
    ├── simulation.md
    ├── crowd-aggregation.md
    ├── causal-inference.md
    └── first-principles.md
```

## Interfaces (all four)

- **Python API:** `from engine import recommend_method, bootstrap_ci, beta_binomial_update, forecast`
- **CLI:** `python -m engine <subcommand>`
- **JSON stdin/stdout:** `echo '{...}' | python -m engine run -`
- **MCP server:** `python -m engine.mcp_server`

See `engine/agent_contract.md` for the full contract.

## Relationship to monte-carlo-predictor

The Monte Carlo family (#4) has its own dedicated skill at `skills/monte-carlo-predictor/`. This toolkit **routes to it** for simulation problems rather than duplicating. Bootstrap is implemented here because it's a complementary (not overlapping) simulation method.

## Design rules

1. No `eval()` anywhere. Safe for LLM-generated specs.
2. Pure data in, pure data out. All methods accept/return JSON-serializable dicts.
3. Pure-Python fallback — numpy is optional, speeds things up 10-100x when present.
4. Every result includes uncertainty bounds + caveats. No false precision.
