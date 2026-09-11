# Agent contract - `managed-agents` engine

How another agent (Claude session, subagent, MCP client, shell script) calls this engine. Same pattern as `prediction-toolkit` and `monte-carlo-predictor`: a CLI with `--json`, and importable Python.

Working directory for every call: `skills/managed-agents/`.

## Cost classes - check before you call

| Class | Commands | Money |
|---|---|---|
| **offline** | `validate`, `bridge`, `status`, `preflight` (without `--live`) | none, no network |
| **control-plane** | `preflight --live`, `apply`, `runs` | none - reads/writes agent & environment objects, no session |
| **data-plane** | `run`, `deploy` (on every firing) | YES - capped by `--budget` (USD, required semantics, default 5.00) |

An agent MUST NOT invoke a data-plane command without the human's explicit go-ahead in the same conversation. `run` and `deploy` prompt for confirmation on a TTY; `--yes` skips it and is for scripts the human has already approved.

## CLI

```
python -m engine <command> [options] --json
```

| Command | Args | JSON result |
|---|---|---|
| `preflight [--live]` | | `{ready, failed, warned, checks:[{name,status(ok|warn|fail),detail,fix}]}` |
| `validate` | | `[{path, kind, name, ok, errors[], warnings[]}]` |
| `bridge [--check] [--dry-run] [--mode symlink|copy]` | | check: `{expected, present, missing[], extra[], broken[], in_sync}`; build: `{mode, planned, created[], refreshed[], pruned[], collisions_resolved[], aliases_skipped[]}` |
| `apply [--dry-run]` | | `[{kind, name, action(created|updated|would-apply), id, version, path}]` |
| `status` | | `{agents:{name:{id,version}}, environments:{name:{id}}, deployments:{name:{id}}}` |
| `run <Agent> "<prompt>" [--budget N] [--environment henry-cloud] [--approve ask|allow-all|deny-all] [--yes]` | | `{session_id, stop_reason, terminated, tool_calls, denied, errors[], text}` |
| `deploy <manifest.yaml> [--budget N] [--dry-run] [--yes]` | | `{name, action, id, status, upcoming_runs_at[]}`; `--dry-run` prints the API body |
| `runs <deployment> [--failures]` | | `[{id, created_at, session_id, error_type, error_message}]` |

Exit codes: `0` ok · `1` a check/validation failed or an error occurred · `130` the human declined the spend prompt.

Global options (place after the subcommand): `--manifests <dir>` (default `agents/`), `--state <file>` (default `agents/state.json`).

## Python

```python
import sys; sys.path.insert(0, "skills/managed-agents")
from engine import config, preflight, bridge

# Offline - no SDK required
result = config.validate(manifest_dict)          # -> ValidationResult(ok, errors, warnings)
results = config.validate_all(config.discover_manifests("skills/managed-agents/agents"))
budget = config.budget_from_dollars(5)           # -> {"type":"limit","max_list_cost":{"amount":"500","currency":"USD"}}
report = preflight.run(manifest_dir, dict(os.environ), live=False)   # -> Report(ready, checks)
plan = bridge.plan(repo_root)                    # -> BridgePlan(entries, collisions, skipped_aliases)

# Control / data plane - SDK + credentials required
from engine import control, session, deploy
client = control.make_client()
control.apply_manifests(client, [(path, manifest), ...], state)
s = session.create_session(client, agent_id, environment_id, prompt, budget_dollars=5)
outcome = session.run_session(client, s.id, prompt=prompt, approve="deny-all",
                              custom_tool_handler=lambda name, args: "...")
```

`session.run_session` answers every `agent.custom_tool_use` (via `custom_tool_handler`, or a default "no handler" result so the session never deadlocks) and every `always_ask` tool call (per `approve`), reconnects losslessly on stream drops, and returns only on a real stop.

## Guarantees this engine makes

1. It will not create a session without a budget (`ValueError`).
2. It never reads, prints, logs, or transmits a credential value - `preflight` reports only which *source* is present.
3. `apply` never archives or deletes; it creates or updates by name.
4. `bridge` writes only inside `.claude/skills/`; nothing under `skills/` is modified.
5. Every manifest rule in `config.py` corresponds to a documented API rejection; unknown model IDs *warn* rather than fail so newer models are not blocked.

## Things it does not do (yet)

- Vault / credential creation - do that in the Console or with `client.beta.vaults.credentials.create(...)`; the manifests only *reference* `vault_ids` at session create.
- File upload / output download - `client.beta.files.upload(...)` and `client.beta.files.list(scope_id=session_id, betas=["managed-agents-2026-04-01"])`.
- Multiagent rosters and outcomes - the manifest passes `multiagent:` through untouched; the validator does not yet inspect it.
- Webhooks - Console-registered; see the Managed Agents webhook docs.
