# managed-agents

Operator console for **Claude Managed Agents** - Anthropic-hosted agents with a per-session sandbox, versioned configs, vault-held credentials, cron deployments, and platform-enforced dollar budgets.

Everything here is runnable. Nothing here spends money unless you type `run` or a deployment fires, and both are capped - the engine refuses to create either without a budget.

## Quick start

```bash
cd skills/managed-agents

python3 -m engine preflight            # what's missing?            $0
pip install --upgrade anthropic        # if it said so
ant auth login                         # or: export ANTHROPIC_API_KEY=...
python3 -m engine preflight --live     # is the workspace enrolled?  $0
python3 -m engine validate             # manifests clean?           $0, offline
python3 -m engine apply                # create agents + env         $0
python3 -m engine run Atlas "Give me the honest read on this week's pipeline." --budget 2
```

`run` prints a Console link (`platform.claude.com/workspaces/<ws>/sessions/<id>`) the moment the session exists - watch tool calls stream in there rather than parsing the terminal.

## What each command costs

| Command | Money |
|---|---|
| `preflight`, `preflight --live`, `validate`, `bridge`, `apply`, `status`, `runs` | **$0** - offline, or control-plane reads/writes with no session |
| `run <Agent> "<task>" --budget N` | up to **$N** list price, platform-enforced; session pauses at the cap |
| `deploy <manifest> [--budget N]` | up to **$N per firing** (flag), else the manifest's `budget:`; refused if neither |

Managed Agents bills your **Anthropic API workspace**. A Claude Pro/Max subscription does not cover it.

## Layout

```
managed-agents/
├── SKILL.md                    the operating guide (rules, shapes, traps)
├── README.md                   this file
├── bridge.allowlist            which skills a mounted session may see
├── agents/                     manifests = API bodies + `kind:`
│   ├── environment.yaml        henry-cloud, limited egress
│   ├── atlas.yaml              strategy (interactive: bash asks)
│   ├── ledger.yaml             finance (interactive: bash asks; xlsx, pdf)
│   ├── shield.yaml             legal research (no bash, allow-listed web)
│   ├── closer.yaml             sales (no bash, Markdown drafts only)
│   ├── axis.yaml               operations (bash asks; mounts this repo)
│   ├── morning-briefing.deployment.yaml   Atlas, bash disabled via agent_overrides, $5 cap
│   └── state.json              created by `apply`: name -> {id, version}
└── engine/
    ├── cli.py                  python -m engine ...
    ├── config.py               manifest load + OFFLINE validation (incl. cross-manifest)
    ├── preflight.py            readiness (never reads a secret value)
    ├── control.py              apply agents/environments: idempotent, declarative, all pages
    ├── session.py              budgeted session runner: history dispatch, reconnect, idle gate
    ├── deploy.py               cron deployments: budget-mandatory, no duplicate-on-error
    ├── bridge.py               builds root .claude/skills/ from the allowlist (copies)
    ├── agent_contract.md       how another agent calls this
    └── tests/test_managed_agents.py
```

## The skills bridge

A session that mounts this repository as a `github_repository` resource discovers skills from the repo's **root `.claude/skills/`** only - one level deep. This repo keeps them in `skills/`. So:

```bash
python3 -m engine bridge --dry-run   # what would change (create / unlink / quarantine)
python3 -m engine bridge             # build from bridge.allowlist, as copies
python3 -m engine bridge --check     # CI: exit 1 if missing / extra / broken / stale
```

Why an allowlist: everything under `.claude/skills/` becomes agent instructions with no review step, and this library includes ~25 offensive-security skills. Why copies: the platform docs do not say the scanner follows symlinks. Why it never deletes: strays that are not the bridge's own symlinks go to `.claude/skills-quarantine/<date>/`.

Commit `.claude/skills/`. Edit `bridge.allowlist` to change what is exposed; `--all` bridges everything if you truly want that.

## Undo

- `apply` created something you didn't want: agents and environments have no cost sitting idle. Leave them, or archive from the Console (archive is **permanent** - the engine never archives on its own).
- `apply` changed a live agent: every update is a new immutable version; pin a session to the previous one with `{type: agent, id, version: N}` from the Console or SDK.
- A session is running away: it can't - it stops at its budget. To stop earlier, send `user.interrupt` from the Console.
- A deployment is firing when it shouldn't: pause it in the Console (reversible). Don't archive unless you mean forever.
- `bridge` moved something: look in `.claude/skills-quarantine/<date>/` and move it back.
- `state.json` is wrong: delete the entry; the next `apply` finds the resource by name (every page) and re-links it.

## Tests

```bash
python3 -m engine.tests.test_managed_agents
```
