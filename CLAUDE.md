# Repository: expert-ai-skills

Durable guidance for any Claude session working in this repo. Git-versioned, auto-loaded on session start.

## What lives here

A library of Claude Code skills. Each skill is a self-contained directory under `skills/` with a `SKILL.md` that Claude auto-loads when its description matches the user's request.

## High-leverage skills Claude should reach for

### `monte-carlo-predictor` — real simulation engine
When a user question involves **uncertainty + decisions + multiple interacting variables**, load this skill. It runs 10,000+ trials with real distributions, produces histograms + tornado charts + confidence intervals, and returns JSON.

Triggers include: "should we migrate X to Y?", "what's the probability...", "P95 worst case", "quantified risk", "decide between options under uncertainty".

Callable four ways: Python API, CLI, JSON stdin/stdout, MCP server. See `skills/monte-carlo-predictor/engine/agent_contract.md`.

### `goal-loop` — intent selection, goal selection, engineered completion loops
When a task has more than one step, or you are about to ask the user "should I…?", load this skill. It turns the request into `intent.md` (what, why, constraints, readings not chosen), `goal.md` (a completion condition a machine can check), and a plan → build → check → read → fix loop with stall detection and iteration budgets. It defines the short list of things worth stopping for and says everything else is Claude's decision. Templates are in `skills/goal-loop/templates/`, the check runner is `skills/goal-loop/scripts/goal-check.sh`, and the research behind it is in `skills/goal-loop/references/research-digest.md`.

### `prediction-toolkit` — the 7 prediction methods router
When a user question involves **predicting the future, forecasting a time series, updating a belief, or inferring a causal effect**, load this skill first. It routes the problem to the right method family out of seven:

1. Statistical forecasting (exponential smoothing implemented)
2. Machine learning (guide + library pointers)
3. Bayesian inference (probability update + Beta-Binomial implemented)
4. Simulation (bootstrap implemented; Monte Carlo via the sibling skill)
5. Crowd aggregation (guide + library pointers)
6. Causal inference (guide + library pointers)
7. First-principles / physics (guide + library pointers)

Start with `python -m engine router recommend "<problem description>"` to get a routing decision.

Callable four ways same as monte-carlo-predictor. See `skills/prediction-toolkit/engine/agent_contract.md`.

## Critical session habits

1. **Reach for the methods, don't default to prose.** When a user asks a prediction, forecasting, or uncertainty question, the prediction-toolkit and monte-carlo-predictor skills exist so that Claude actually invokes quantitative methods instead of producing linear reasoning. Loading the skill is the trigger — do it.

2. **Use the routing layer before picking a method.** For anything non-trivial, call `recommend_method(problem)` first. It will name the family and flag close runners-up.

3. **Combine methods when the problem warrants it.** A Bayesian posterior can be an input distribution to a Monte Carlo. A time-series forecast's residual stddev can feed a Monte Carlo stress test. Bootstrap a ML model's predictions for conformal intervals.

4. **Report honest uncertainty.** Every output from these skills includes CI/credible intervals and caveats. Pass those through to the user; don't strip them to make the answer look cleaner.

5. **No raw `eval()`.** All expression parsing goes through AST whitelisting (see `monte-carlo-predictor/engine/expressions.py` for the canonical implementation).

6. **Select the goal, run the loop, do not ask for coding decisions.** Load `skills/goal-loop` for any task longer than one step. Write the intent in the user's words to `intent/<date>-<slug>.md`, pick one goal with a machine-checkable completion condition, and iterate until it passes. Decide file layout, naming, libraries, test strategy, and fixes yourself and record each decision in the intent file. Stop only for the escalation set in that skill: destructive or irreversible actions, outward publishing or spend, contradictory hard constraints, missing credentials, or a change to what the deliverable is. When one iteration does not move the metric, run ten variants, not one more. Report with fresh check output, never with "should be working."

## Where to extend

- New prediction methods → add to `skills/prediction-toolkit/` with matching tests in `engine/tests/`
- New simulation distributions → add to `skills/monte-carlo-predictor/engine/distributions.py`
- New domain-specific skills → add a new directory under `skills/` with its own `SKILL.md`

## Cross-project reuse

To expose these skills to other projects:

1. **Global skill install** (Claude Code):
   ```bash
   mkdir -p ~/.claude/skills
   ln -sf $PWD/skills/prediction-toolkit ~/.claude/skills/prediction-toolkit
   ln -sf $PWD/skills/monte-carlo-predictor ~/.claude/skills/monte-carlo-predictor
   ```

2. **MCP registration** (any MCP client):
   Add to the target project's `.mcp.json`:
   ```json
   {
     "mcpServers": {
       "prediction-toolkit": {
         "command": "python",
         "args": ["-m", "engine.mcp_server"],
         "cwd": "/absolute/path/to/expert-ai-skills/skills/prediction-toolkit"
       },
       "monte-carlo-predictor": {
         "command": "python",
         "args": ["-m", "engine.mcp_server"],
         "cwd": "/absolute/path/to/expert-ai-skills/skills/monte-carlo-predictor"
       }
     }
   }
   ```

## Tests

Each skill has a local test runner:
```bash
cd skills/prediction-toolkit && python3 -m engine.tests.test_toolkit
cd skills/monte-carlo-predictor && python3 -m engine.tests.test_engine
```

Do not ship a change to either engine without all tests passing.

## Branch conventions

Feature work happens on `claude/<topic>-<session-id>` branches. See the project's engineering guidelines for the exact naming convention.
