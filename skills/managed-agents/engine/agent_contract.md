# Agent contract - `managed-agents` engine

How another agent (Claude session, subagent, MCP client, shell script) calls this engine. Same pattern as `prediction-toolkit` and `monte-carlo-predictor`: a CLI with `--json`, and importable Python.

Working directory for every call: `skills/managed-agents/`.

## Cost classes - check before you call

| Class | Commands | Money |
|---|---|---|
| **offline** | `validate`, `bridge`, `status`, `preflight` (without `--live`) | none, no network |
| **control-plane** | `preflight --live`, `apply`, `runs` | none - reads/writes agent & environment objects, no session |
| **data-plane** | `run`, `deploy` (on every firing) | YES - capped by a budget the engine will not proceed without |

An agent MUST NOT invoke a data-plane command without the human's explicit go-ahead in the same conversation. `run` and `deploy` prompt for confirmation on a TTY; `--yes` skips it and is for scripts the human has already approved. `run --approve allow-all` additionally requires `--yes` and is for sessions the human has decided to run ungated.

## CLI

```
python -m engine <command> [options] --json
```

| Command | Args | JSON result |
|---|---|---|
| `preflight [--live]` | | `{ready, failed, warned, checks:[{name,status(ok|warn|fail),detail,fix}]}` |
| `validate` | | `[{path, kind, name, ok, errors[], warnings[]}]` - includes cross-manifest rules |
| `bridge [--check] [--dry-run] [--all] [--no-prune] [--mode copy|symlink] [--allowlist F]` | | check: `{expected, present, missing[], extra[], broken[], stale[], allowlist_unmatched[], in_sync}`; dry-run: `{planned, would_create[], would_refresh[], would_unlink[], would_quarantine[], ...}`; build: `{mode, planned, created[], refreshed[], unlinked[], quarantined[], collisions_resolved[], aliases_skipped[], allowlist_unmatched[]}` |
| `apply [--dry-run]` | | `[{kind, name, action(created|updated|would-apply), id, version, path}]` |
| `status` | | `{agents:{name:{id,version}}, environments:{name:{id}}, deployments:{name:{id}}}` |
| `run <Agent> "<prompt>" [--budget N>0] [--environment henry-cloud] [--approve ask|allow-all|deny-all] [--yes]` | | `{session_id, stop_reason, terminated, tool_calls, answered, denied, reconnects, errors[], text}` |
| `deploy <manifest.yaml> [--budget N>0] [--dry-run] [--yes]` | | `{name, action, id, status, budget, upcoming_runs_at[]}`; `--dry-run` prints the API body with resource tokens redacted |
| `runs <deployment> [--failures]` | | `[{id, created_at, session_id, error_type, error_message}]` |

Exit codes: `0` ok · `1` a check/validation failed or an error occurred (incl. "no budget") · `130` the human declined the spend prompt · `2` bad arguments (e.g. `--budget 0`).

Shared options (place after the subcommand): `--manifests <dir>` (default `agents/`), `--state <file>` (default `agents/state.json`).

## Python

```python
import sys; sys.path.insert(0, "skills/managed-agents")
from engine import config, preflight, bridge

# Offline - no SDK required
result = config.validate(manifest_dict)          # -> ValidationResult(ok, errors, warnings)
results = config.validate_all(config.discover_manifests("skills/managed-agents/agents"))  # + cross checks
budget = config.budget_from_dollars(5)           # -> {"type":"limit","max_list_cost":{"amount":"500","currency":"USD"}}
report = preflight.run(manifest_dir, dict(os.environ), live=False)   # -> Report(ready, checks)
plan = bridge.plan(repo_root, allowlist=bridge.read_allowlist("skills/managed-agents/bridge.allowlist"))

# Control / data plane - SDK + credentials required
from engine import control, session, deploy
client = control.make_client()
control.apply_manifests(client, [(path, manifest), ...], state)
s = session.create_session(client, agent_id, environment_id, budget_dollars=5, agent_version=3)
outcome = session.run_session(client, s.id, prompt=prompt, approve="deny-all",
                              custom_tool_handler=lambda name, args: "...")
body = deploy.build_body(manifest, agent_id, environment_id, budget_dollars=None, agent_version=3)  # raises without a budget
```

`session.run_session` dispatches history (oldest first, every page) and live events through one path, answers every `agent.custom_tool_use` (via `custom_tool_handler`, or a default "no handler" result so the session never deadlocks) and every `always_ask` `agent.tool_use` / `agent.mcp_tool_use` (per `approve`) exactly once, answers whatever a `requires_action` idle lists in `stop_reason.event_ids`, reconnects losslessly on stream drops, and returns only on a real stop. With `prompt`, it is safe on a session that already has history: earlier turns' end-of-turn idles are ignored until the new `user.message` is echoed back as processed, and `outcome.text` is THIS turn's output only. Without `prompt`, it observes: an already-finished session returns immediately with its last `stop_reason`. Ctrl-C at an approval prompt aborts the run (`KeyboardInterrupt`); it is not turned into a deny.

## Guarantees this engine makes

1. It will not create a session without a budget (`ValueError`), and will not create or update a deployment whose body has no budget (`ValueError`).
2. It never reads, prints, logs, or transmits a credential value - `preflight` reports only which *source* is present; `deploy --dry-run` redacts resource tokens; the validator rejects credential-shaped literals in manifests.
3. `apply` never archives or deletes; it creates or updates by name, across every page of the listing, and is declarative: `system` / `description` / `multiagent` / `tools` / `skills` / `mcp_servers` removed from the manifest are cleared on the live agent, and metadata keys dropped from the manifest are nulled (the API merges metadata key-by-key). Environments: `description` and metadata likewise.
4. A deployment update that fails for any reason other than 404 is raised, never turned into a second deployment; the by-name lookup that guards against a lost `state.json` raises if the SDK cannot list deployments rather than silently creating.
5. `bridge` writes only inside `.claude/skills/`; nothing under `skills/` is modified; nothing inside `.claude/skills/` is ever deleted - stray symlinks are unlinked, every real directory that is unwanted OR differs from its source (a local edit, or drift) is moved to `.claude/skills-quarantine/<date>/`, an up-to-date copy is left untouched; it refuses to run if `.claude/skills` resolves outside the repository, and refuses to copy a skill containing a symlink that resolves outside it.
6. `deploy` refuses when the agent named by the manifest is not defined in `--manifests` or beside the manifest, because unattended-safety (no `always_ask` tool, no `custom` tool in effect) cannot be certified without it. `deploy --dry-run` needs no secrets present: `${ENV}` references stay unexpanded and are printed redacted.
7. Every manifest rule in `config.py` corresponds to a documented API rejection or a documented deadlock; unknown model IDs *warn* rather than fail so newer models are not blocked. Secret detection matches token *shapes* (`AKIA[0-9A-Z]{16}`, `ghp_` + 36 chars, `sk-ant-` + 20, ...) - prose that names a format is not flagged; a literal value under `api_key` / `access_token` / `secret_value` / `password` / `client_secret` / `refresh_token` always is.

## Things it does not do (yet)

- Vault / credential creation - do that in the Console or with `client.beta.vaults.credentials.create(...)`; the manifests only *reference* `vault_ids` at session create.
- File upload / output download - `client.beta.files.upload(...)` and `client.beta.files.list(scope_id=session_id, betas=["managed-agents-2026-04-01"])`.
- Multiagent rosters and outcomes - the manifest passes `multiagent:` through untouched; the validator does not inspect it (it does inspect `agent_overrides`).
- Webhooks - Console-registered; see the Managed Agents webhook docs.
- Confirm that the platform's skill scanner follows symlinks - hence `copy` is the bridge default.
