# Monte Carlo Engine

A real Monte Carlo simulation engine. Runs N trials over a declarative spec of uncertain variables and outcome expressions, returns statistics + tornado charts + ASCII visualizations.

**Agent-callable four ways** — Python API, CLI, JSON stdin/stdout, MCP server — so any teammate agent (Hermes, AEGIS, or future MCP clients) can use it. See [`agent_contract.md`](./agent_contract.md).

## Files

| File | Purpose |
|------|---------|
| `monte_carlo.py` | Core simulation engine — `simulate(spec) -> report` |
| `distributions.py` | 8 probability distributions (uniform, normal, triangular, beta, lognormal, poisson, choice, constant) |
| `expressions.py` | **Safe** expression evaluator (AST whitelist, no `eval`) for outcome formulas |
| `visualize.py` | ASCII histograms + tornado plots, optional matplotlib PNGs |
| `cli.py` | Command-line + JSON-stdio entry point |
| `mcp_server.py` | MCP server wrapper (tools: `run_simulation`, `list_distributions`, `describe_distribution`) |
| `decision_optimizer.py` | Compare multiple options, rank by objective, compute Pareto frontier |
| `divergence_scanner.py` | Static scanner for intent-vs-reality gaps in a project |
| `agent_contract.md` | Stable contract for other agents to target |
| `__init__.py` | Public API exports |
| `__main__.py` | Enables `python -m engine run ...` |

## Quickstart

```bash
# From skills/monte-carlo-predictor/:
python3 -m engine run templates/spec-template.yaml

# Run the headline example:
python3 -m engine run examples/postgres-vs-mongo/spec.yaml

# Compare multiple options:
python3 -m engine.decision_optimizer examples/compare-databases/options.yaml --pareto

# Scan a project for divergences:
python3 -m engine.divergence_scanner /path/to/project
```

## Dependencies

- **Required:** Python 3.9+
- **Recommended:** `numpy` (10–100× faster sampling), `pyyaml` (for YAML specs)
- **Optional:** `matplotlib` (PNG charts), `mcp` (MCP server)

Pure Python fallback is supported — the engine still works without numpy, just slower.
