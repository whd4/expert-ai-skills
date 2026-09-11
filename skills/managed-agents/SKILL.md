---
name: managed-agents
description: "Stand up, budget, and operate Claude Managed Agents - Anthropic-hosted agents with a per-session sandbox, versioned agent configs, vault-held credentials, cron deployments, and hard dollar budgets. Use when a task should run WITHOUT a human at the keyboard (scheduled briefings, recurring research, unattended ops), when you need Anthropic to run the agent loop and host the container, or when a user says 'managed agent', 'run this every night', 'spin up an agent that...', or 'enable Managed Agents'. Ships a preflight readiness check, an offline manifest validator that catches API 400s before they cost a round-trip, an idempotent apply loop, a budget-mandatory session runner with the correct idle gate, and a bridge that exposes this repository's whole skill library to a mounted session."
version: "1.0.0"
tags: ["managed-agents", "anthropic-api", "agents", "automation", "scheduling", "sandbox", "budgets", "zero-human"]
---

# Managed Agents

**Purpose:** Turn "I want an agent that does X on its own" into a running, budgeted, auditable Managed Agents session - and make it impossible to do the three things that quietly cost money or leak secrets.

Managed Agents is the Anthropic API surface where **Anthropic runs the agent loop and hosts the container** the agent's tools execute in. You define a persistent, versioned **Agent**; every run is a **Session** that points at it. Sessions can be started by you, by a **scheduled deployment** (cron), and each carries a **hard dollar budget** the platform enforces.

This skill is the operator's console for that surface. It is runnable: `python -m engine <command>` from `skills/managed-agents/`.

---

## When to use this skill

Load this skill when any of these apply:

- The task should run **without a human present** - nightly, weekly, "every morning at 7", "watch this and report"
- The user wants **Anthropic to host the execution sandbox** (bash, files, code) rather than run tools on their own machine
- The user says **"managed agent"**, **"enable Managed Agents"**, **"spin up an agent that..."**, **"agent team"**, **"zero-human"**
- Work needs a **persistent, versioned agent definition** that many runs share, with rollback
- Work needs **credentials the agent can use but never see** (vaults - substituted at egress, never inside the sandbox)
- Work needs a **spend ceiling** that the platform enforces, not one the model is politely asked to respect
- Work fans out across sources or files and one loop would drown in reading (multiagent roster)

Do NOT load this skill for:
- A single classification / summarisation / extraction call - use the plain Messages API
- A coding agent on the user's own machine with the user watching - that is Claude Code / the Agent SDK, a different product
- Tools that must execute on the user's hardware with the user's own runtime - use the Messages API tool runner and host it yourself
- Anything where the user has said they will not spend API credit - Managed Agents bills the API workspace, not a Claude Pro/Max seat

---

## The four rules

| # | Rule | Why it exists |
|---|------|---------------|
| 1 | **Agent first, session second. Agent ONCE.** `model` / `system` / `tools` / `mcp_servers` / `skills` live on `POST /v1/agents`, never on the session. Create it once, store the ID, reference it forever. | Sessions pin to an agent *version*. Re-creating agents orphans running sessions, defeats rollback, and pays create latency every run. |
| 2 | **Every session carries a budget.** `budget: {type: limit, max_list_cost: {amount: "<cents>", currency: USD}}`. The engine refuses to create an uncapped session. | The platform enforces this before every model request. A session that hits it *pauses* (`stop_reason: budget_reached`) - history and sandbox preserved. It is the only ceiling that does not rely on the model's good behaviour. |
| 3 | **Secrets go in a vault, never in a manifest, prompt, or message.** MCP auth: `mcp_oauth` / `static_bearer` keyed by server URL. Anything else: `environment_variable`, substituted at egress. | Prompts and messages are persisted in the session's event history and returned by `events.list()` for the life of the session. A vault credential never enters the sandbox at all - code the agent writes cannot read it. |
| 4 | **`session.status_idle` is not "done".** Break only on `session.status_terminated`, or on idle with `stop_reason.type != requires_action`. | Sessions idle transiently while waiting on *you* - a tool confirmation or a custom tool result. Break early and the session deadlocks. |

---

## Commands

Run from `skills/managed-agents/`:

| Command | What it does | Spends money? |
|---------|--------------|---------------|
| `python -m engine preflight [--live]` | Readiness: Python, SDK version + namespaces, credential *source* (never the value), billing note, manifests. `--live` adds one `GET /v1/agents` - the definitive "is the beta enabled for this workspace" answer. | **No.** `--live` is a control-plane read. |
| `python -m engine validate` | Lint every manifest against the documented API constraints offline - session fields on an agent, dangling `mcp_toolset`, domain-list rules, budget string format, skills without `read`, DST-window cron. | **No.** No network at all. |
| `python -m engine bridge [--check]` | Build root `.claude/skills/` so a session that mounts this repo discovers all its skills. | **No.** |
| `python -m engine apply [--dry-run]` | Create-or-update every agent and environment manifest, idempotent by name. Writes IDs to `agents/state.json`. | **No.** Agents and environments are free objects. |
| `python -m engine status` | Show applied IDs and versions. | **No.** |
| `python -m engine run <Agent> "<task>" --budget 5` | Create a budgeted session, stream it, answer tool asks, print the Console trace link. Confirms before spending unless `--yes`. | **YES.** Capped at `--budget` (default $5.00). |
| `python -m engine deploy <manifest> --budget 5` | Create-or-update a cron deployment. The budget is copied onto every fired session. | **On every firing.** |
| `python -m engine runs <deployment> [--failures]` | Audit trail of deployment firings. | **No.** |

Every command accepts `--json`.

---

## Enabling it - the sequence

```
1. python -m engine preflight          # what is missing on this machine?
2. pip install --upgrade anthropic     # if preflight said so
3. ant auth login   OR   export ANTHROPIC_API_KEY=...   (never paste a key into chat)
4. python -m engine preflight --live   # is the workspace enrolled?  ($0)
5. python -m engine validate           # manifests clean?
6. python -m engine apply              # create the agents + environment ($0)
7. python -m engine run Atlas "..." --budget 2   # first real session, tiny cap
8. python -m engine deploy agents/morning-briefing.deployment.yaml --dry-run
```

Step 4 is the one that answers "is Managed Agents enabled?" - a 403/404 on `GET /v1/agents` means the workspace is not enrolled in the beta; fix that in the Console before anything else.

**Billing reality check:** Managed Agents bills the Anthropic **API workspace** (console credit / invoicing). A Claude Pro or Max subscription does not cover it. Confirm the workspace has credit before step 7.

---

## What ships in `agents/`

| File | Kind | Notes |
|------|------|-------|
| `environment.yaml` | environment `henry-cloud` | `limited` egress, package managers on. `web_search` / `web_fetch` are unaffected by this - they run on Anthropic's side. |
| `atlas.yaml` | agent | Strategy. Full toolset, `bash` asks. Houston-localised search. |
| `ledger.yaml` | agent | Finance. `xlsx` + `pdf` skills. Never states an unsourced figure. |
| `shield.yaml` | agent | Legal research. **No bash.** Web tools allow-listed to primary-source domains. Contains no case facts - by design, it is a committed file. |
| `closer.yaml` | agent | Sales. No bash. Drafts only, never sends. |
| `axis.yaml` | agent | Operations. Bash asks. Meant to mount this repository. |
| `morning-briefing.deployment.yaml` | deployment | Atlas, 07:10 weekdays `America/Chicago`. |

Forge (engineering) is deliberately absent: it runs on a different model stack and is not a Claude Managed Agent.

The manifest **is** the API body plus a `kind:` discriminator and an optional `x-notes:` block. Anything the API accepts, the manifest accepts.

---

## Manifest shape (agent)

```yaml
kind: agent
name: Atlas                      # 1-256 chars; apply is idempotent on this
model: {id: claude-opus-5, effort: high}   # effort lives HERE - a per-session override is silently ignored
system: |                        # <= 100K chars. NO secrets. NO case facts if the file is committed.
  ...
tools:
  - type: agent_toolset_20260401
    default_config: {enabled: true, permission_policy: {type: always_allow}}
    configs:
      - name: bash
        permission_policy: {type: always_ask}     # session idles; you send user.tool_confirmation
      - name: web_search
        allowed_domains: [texas.gov, courtlistener.com]   # plain hostnames, covers subdomains, max 64
        user_location: {type: approximate, city: Houston, country: US, timezone: America/Chicago}
      - name: web_fetch
        max_content_tokens: 50000
  # - {type: mcp_toolset, mcp_server_name: github}   # must match an mcp_servers entry
  # - {type: custom, name: run_tests, description: ..., input_schema: {...}}
mcp_servers: []                  # {type: url, name, url} ONLY - auth is a vault credential
skills:
  - {type: anthropic, skill_id: xlsx}   # requires the `read` tool to be enabled
metadata: {owner: henry-ai}      # <= 16 keys
```

Things the validator will stop you from sending (each is a documented 400):
`environment_id` / `resources` / `vault_ids` / `budget` on an agent - a wildcard, scheme, port, IP, or `localhost` in a domain list - `allowed_domains` and `blocked_domains` on the same tool - a path on a `web_fetch` domain - a decimal budget amount (`"25.00"`; it must be `"2500"`) - an `mcp_toolset` naming an undeclared server - skills with `read` disabled - a 4-field cron - a deployment with no starting event.

---

## Exposing this repository to a session

The platform scans a mounted repository's **root `.claude/skills/<name>/SKILL.md`** at session start - one level deep, nothing nested, nothing outside `.claude`. This repository keeps skills in `skills/`, some nested two levels. `python -m engine bridge` builds the flat index of relative symlinks the scanner expects; `--check` verifies it (run it in CI). Then mount:

```yaml
resources:
  - type: github_repository
    url: https://github.com/whd4/expert-ai-skills
    authorization_token: <fine-grained PAT, Contents: Read>   # injected by Anthropic's git proxy; never enters the sandbox
    checkout: {type: branch, name: main}
```

Skills are scanned once, from the checkout at session start - push a change, start a new session.

> Repository skills are agent instructions loaded with no review step. Anyone who can commit to the mounted repo can put instructions in front of an agent that has `bash` and `web_fetch`. Mount only what you trust.

---

## Driving a session correctly (what `engine/session.py` does)

```
open stream  ->  drain events.list() history, dedupe by id  ->  send user.message
             ->  for each event:
                   agent.custom_tool_use          -> run it host-side, send user.custom_tool_result   (or it deadlocks)
                   agent.tool_use + permission=ask -> send user.tool_confirmation {allow|deny, deny_message}
                   session.status_terminated      -> stop
                   session.status_idle            -> requires_action ? keep reading : stop
             ->  settle(): poll retrieve() until status != running before archive/delete
```

`tool_use_id` on a confirmation is the **event id** (`sevt_…`), not a `toolu_…` id. `session.usage` events carry the running `list_cost`. `budget_reached` is a pause, not a failure - raise or remove the budget to resume.

---

## Credentials - how they actually flow

| Need | Mechanism | The agent sees |
|------|-----------|----------------|
| MCP server auth | vault credential `mcp_oauth` / `static_bearer`, keyed by server URL; attach `vault_ids` at session create (create-only) | nothing - injected by Anthropic's MCP proxy |
| API key for a CLI / SDK / `curl` in `bash` | vault credential `environment_variable` with `networking.allowed_hosts` | an opaque placeholder; real value substituted at egress, headers/body only, never URL path |
| Git push to a mounted repo | `authorization_token` on the `github_repository` resource | nothing - git proxy injects it |
| Secret that must never leave your infra | declare a `custom` tool; your orchestrator executes the call with its own key and returns `user.custom_tool_result` | only the result |

Never put a key in `system`, in a `user.message`, or in a committed manifest. The validator rejects `auth`/`token`/`headers` keys on `mcp_servers` entries for this reason.

---

## Scheduled deployments - the two traps

1. **Jitter.** Firing is delayed up to 15% of the interval (floor 5 s, cap 9 min). Never hang a downstream deadline off `upcoming_runs_at`.
2. **DST.** Cron matches literal wall-clock in the IANA timezone. 01:00-03:59 local is *skipped* on spring-forward and *fires twice* on fall-back. The validator warns; the shipped deployment fires at 07:10.

Pause is reversible; archive is terminal. Test with a manual run (`POST /v1/deployments/{id}/run` - works while paused) before trusting the schedule. Every firing writes a `drun_` record whether it succeeded or not - `python -m engine runs <name> --failures` is the audit.

---

## Other agents calling this skill

See `engine/agent_contract.md` - every command has a `--json` form, and `engine.config.validate(manifest)` / `engine.preflight.run(...)` are importable without the SDK installed.

## Tests

```bash
cd skills/managed-agents && python3 -m engine.tests.test_managed_agents
```

Offline. No SDK, no credentials, no spend. Every rejection test is a negative control - it feeds the validator something known-bad and asserts it fails.
