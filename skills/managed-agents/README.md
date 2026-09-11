# managed-agents

Operator console for **Claude Managed Agents** - Anthropic-hosted agents with a per-session sandbox, versioned configs, vault-held credentials, cron deployments, and platform-enforced dollar budgets.

Everything here is runnable. Nothing here spends money unless you type `run` or a deployment fires, and both are capped.

## Quick start

```bash
cd skills/managed-agents

python3 -m engine preflight            # what's missing?            $0
pip install --upgrade anthropic        # if it said so
ant auth login                         # or: export ANTHROPIC_API_KEY=...
python3 -m engine preflight --live     # is the workspace enrolled?  $0
python3 -m engine validate             # manifests clean?           $0, offline
python3 -m engine apply                # create agents + env         $0
python3 -m engine run Atlas "Give me the honest read on TXS5450." --budget 2
```

`run` prints a Console link (`platform.claude.com/workspaces/<ws>/sessions/<id>`) the moment the session exists - watch tool calls stream in there rather than parsing the terminal.

## What each command costs

| Command | Money |
|---|---|
| `preflight`, `preflight --live`, `validate`, `bridge`, `apply`, `status`, `runs` | **$0** - offline, or control-plane reads/writes with no session |
| `run <Agent> "<task>" --budget N` | up to **$N** list price, platform-enforced; session pauses at the cap |
| `deploy <manifest> --budget N` | up to **$N per firing**, on the cron schedule |

Managed Agents bills your **Anthropic API workspace**. A Claude Pro/Max subscription does not cover it.

## Layout

```
managed-agents/
├── SKILL.md                    the operating guide (rules, shapes, traps)
├── README.md                   this file
├── agents/                     manifests = API bodies + `kind:`
│   ├── environment.yaml        henry-cloud, limited egress
│   ├── atlas.yaml              strategy
│   ├── ledger.yaml             finance (xlsx, pdf)
│   ├── shield.yaml             legal research (no bash, allow-listed web)
│   ├── closer.yaml             sales (drafts only)
│   ├── axis.yaml               operations (mounts this repo)
│   ├── morning-briefing.deployment.yaml
│   └── state.json              created by `apply`: name -> {id, version}
└── engine/
    ├── cli.py                  python -m engine ...
    ├── config.py               manifest load + OFFLINE validation
    ├── preflight.py            readiness (never reads a secret value)
    ├── control.py              apply agents/environments, idempotent by name
    ├── session.py              budgeted session runner, correct idle gate
    ├── deploy.py               cron deployments + run audit
    ├── bridge.py               builds root .claude/skills/ for mounted-repo discovery
    ├── agent_contract.md       how another agent calls this
    └── tests/test_managed_agents.py
```

## The skills bridge

A session that mounts this repository as a `github_repository` resource discovers skills from the repo's **root `.claude/skills/`** only - one level deep. This repo keeps them in `skills/`. So:

```bash
python3 -m engine bridge          # (re)build the relative-symlink index
python3 -m engine bridge --check  # CI: exit 1 if out of sync
```

Commit `.claude/skills/`. Symlinks are relative, so they survive a clone anywhere.

## Undo

- `apply` created something you didn't want: agents and environments have no cost sitting idle. Leave them, or archive from the Console (archive is **permanent** - the engine never archives on its own).
- A session is running away: it can't - it stops at its budget. To stop earlier, send `user.interrupt` from the Console.
- `bridge` made a mess: `rm -rf .claude/skills && python3 -m engine bridge`. Nothing under `skills/` is ever touched.
- `state.json` is wrong: delete the entry; the next `apply` finds the resource by name and re-links it.

## Tests

```bash
python3 -m engine.tests.test_managed_agents
```
