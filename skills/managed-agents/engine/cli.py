"""Command line for the Claude Managed Agents engine.

    python -m engine preflight [--live]      readiness sweep     ($0)
    python -m engine validate                manifest lint       ($0, offline)
    python -m engine bridge [--check]        .claude/skills sync ($0, offline)
    python -m engine apply [--dry-run]       agents/environments ($0)
    python -m engine status                  what is applied     ($0)
    python -m engine run <agent> "<prompt>"  live session        (SPENDS MONEY)
    python -m engine deploy <manifest>       cron deployment     (SPENDS on fire)
    python -m engine runs <deployment>       deployment audit    ($0)

Only `run` and a fired `deploy` consume tokens or container time. Both are
capped by a dollar budget; there is no uncapped path.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any

from . import bridge, config, control, deploy, preflight, session

# realpath: under a symlink install (~/.claude/skills/managed-agents -> repo)
# __file__ is the symlink path, and the repo root must still resolve correctly.
HERE = os.path.dirname(os.path.realpath(__file__))
SKILL_ROOT = os.path.dirname(HERE)
REPO_ROOT = os.path.abspath(os.path.join(SKILL_ROOT, "..", ".."))
DEFAULT_MANIFEST_DIR = os.path.join(SKILL_ROOT, "agents")
DEFAULT_STATE = os.path.join(SKILL_ROOT, "agents", "state.json")
DEFAULT_ALLOWLIST = os.path.join(SKILL_ROOT, "bridge.allowlist")
DEFAULT_SESSION_BUDGET_USD = 5.00


def _emit(payload: Any, as_json: bool, text: str = "") -> None:
    if as_json:
        print(json.dumps(payload, indent=2, default=str))
    elif text:
        print(text)


def _message(exc: BaseException) -> str:
    """KeyError's str() wraps the message in repr quotes; unwrap it."""
    return str(exc.args[0]) if exc.args else str(exc)


def _confirm(question: str) -> bool:
    try:
        return input(question).strip().lower() in {"y", "yes"}
    except (EOFError, KeyboardInterrupt):
        return False


# --------------------------------------------------------------------------
# commands
# --------------------------------------------------------------------------


def cmd_preflight(args: argparse.Namespace) -> int:
    report = preflight.run(args.manifests, dict(os.environ), live=args.live)
    if args.json:
        _emit(report.to_dict(), True)
    else:
        print(preflight.render(report))
        if not args.live and report.ready:
            print("  Next: `python -m engine preflight --live` to confirm the")
            print("  workspace is actually enrolled in the beta (still $0).\n")
    return 0 if report.ready else 1


def cmd_validate(args: argparse.Namespace) -> int:
    paths = config.discover_manifests(args.manifests)
    if not paths:
        print(f"No manifests found in {args.manifests}", file=sys.stderr)
        return 1
    results = config.validate_all(paths)

    if args.json:
        _emit([r.to_dict() for r in results], True)
    else:
        for result in results:
            label = "OK  " if result.ok else "FAIL"
            print(f"[{label}] {os.path.basename(result.path)}  ({result.kind}: {result.name})")
            for error in result.errors:
                print(f"         error: {error}")
            for warning in result.warnings:
                print(f"         warn:  {warning}")
        bad = sum(1 for r in results if not r.ok)
        print(f"\n{len(results) - bad}/{len(results)} manifests valid.")
    return 0 if all(r.ok for r in results) else 1


def cmd_bridge(args: argparse.Namespace) -> int:
    allowlist = None if args.all else bridge.read_allowlist(args.allowlist)
    if not args.all and allowlist is None:
        print(f"No allowlist at {args.allowlist} - pass --all to bridge every skill, "
              "or create the file.", file=sys.stderr)
        return 1

    if args.check:
        state = bridge.check(REPO_ROOT, allowlist=allowlist)
        if args.json:
            _emit(state, True)
        elif state["in_sync"]:
            print(f"Bridge in sync: {state['expected']} skills in .claude/skills/")
        else:
            print(f"Bridge OUT OF SYNC ({state['expected']} expected)")
            for key in ("missing", "extra", "broken", "stale", "allowlist_unmatched"):
                if state[key]:
                    print(f"  {key}: {len(state[key])} -> {', '.join(state[key][:8])}")
            print("\nRun `python -m engine bridge` to rebuild.")
        return 0 if state["in_sync"] else 1

    result = bridge.build(
        REPO_ROOT, mode=args.mode, prune=not args.no_prune, dry_run=args.dry_run, allowlist=allowlist
    )
    if args.json:
        _emit(result, True)
        return 0

    verb = "Would bridge" if args.dry_run else "Bridged"
    print(f"{verb} {result['planned']} skills into .claude/skills/ (mode={result['mode']})")
    for key in ("would_create", "would_refresh", "would_leave", "would_unlink", "would_quarantine",
                "created", "refreshed", "left", "unlinked", "quarantined"):
        if result.get(key):
            print(f"  {key:<17} {len(result[key])}: {', '.join(result[key][:8])}"
                  f"{' ...' if len(result[key]) > 8 else ''}")
    if result.get("collisions_resolved"):
        print(f"  renamed for collisions: {', '.join(result['collisions_resolved'][:10])}")
    if result.get("aliases_skipped"):
        print(f"  aliases skipped: {len(result['aliases_skipped'])}")
    if result.get("allowlist_unmatched"):
        print(f"  WARNING allowlist names matching no skill: "
              f"{', '.join(result['allowlist_unmatched'])}")
    return 0


def cmd_apply(args: argparse.Namespace) -> int:
    paths = config.discover_manifests(args.manifests)
    if not paths:
        print(f"No manifests found in {args.manifests} - nothing to apply.", file=sys.stderr)
        return 1
    results = config.validate_all(paths)
    invalid = [r for r in results if not r.ok]
    if invalid:
        print("Refusing to apply - fix these first:", file=sys.stderr)
        for result in invalid:
            for error in result.errors:
                print(f"  {os.path.basename(result.path)}: {error}", file=sys.stderr)
        return 1

    manifests = [(p, config.load_manifest(p)) for p in paths]
    manifests = [(p, m) for p, m in manifests if m.get("kind") in {"agent", "environment"}]
    state = config.load_state(args.state)

    client = None if args.dry_run else control.make_client()
    applied = control.apply_manifests(client, manifests, state, dry_run=args.dry_run)

    if not args.dry_run:
        config.save_state(args.state, state)

    if args.json:
        _emit(applied, True)
    else:
        for item in applied:
            version = f" v{item['version']}" if item.get("version") else ""
            print(f"  {item['action']:<12} {item['kind']:<12} {item['name']}"
                  f"  {item.get('id') or ''}{version}")
        print("\nDry run - nothing was sent." if args.dry_run else f"\nState written to {args.state}")
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    state = config.load_state(args.state)
    if args.json:
        _emit(state, True)
        return 0
    for kind in ("environments", "agents", "deployments"):
        entries = state.get(kind, {})
        print(f"\n{kind} ({len(entries)}):")
        if not entries:
            print("  (none applied)")
        for name, meta in sorted(entries.items()):
            version = f"  v{meta['version']}" if meta.get("version") else ""
            print(f"  {name:<24} {meta.get('id', '?')}{version}")
    print()
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    state = config.load_state(args.state)
    try:
        agent_id = control.resolve(state, "agent", args.agent)
        environment_id = control.resolve(state, "environment", args.environment)
    except KeyError as exc:
        print(_message(exc), file=sys.stderr)
        return 1
    agent_version = state["agents"][args.agent].get("version")

    approve = args.approve
    if approve == session.APPROVE_ASK and not sys.stdin.isatty():
        approve = session.APPROVE_DENY
    if approve == session.APPROVE_ALLOW and not args.yes:
        print("--approve allow-all auto-approves every `always_ask` tool call - including a\n"
              "shell command the agent composed from a web page it just fetched. That defeats\n"
              "the gate the manifest set. Pass --yes as well if you really mean it.",
              file=sys.stderr)
        return 1

    budget = args.budget
    print(f"\n  agent:       {args.agent} ({agent_id}{f' v{agent_version}' if agent_version else ''})")
    print(f"  environment: {args.environment} ({environment_id})")
    print(f"  budget:      ${budget:,.2f} USD hard cap (session pauses at the cap)")
    print(f"  approvals:   {approve}")
    print("  NOTE: this bills your Anthropic API workspace, not a Claude subscription.")

    if not args.yes and not _confirm("\n  Create this session and spend against it? [y/N] "):
        print("  Aborted - nothing was created.")
        return 130

    client = control.make_client()
    created = session.create_session(
        client,
        agent_id=agent_id,
        environment_id=environment_id,
        budget_dollars=budget,
        title=args.title,
        agent_version=agent_version,
    )
    print(f"\n  session:  {created.id}")
    print(f"  console:  {session.console_url(created.id, args.workspace)}\n")

    outcome = session.run_session(client, created.id, prompt=args.prompt, approve=approve)
    status = session.settle(client, created.id)

    print("\n" + "-" * 52)
    print(f"  stop_reason: {outcome.stop_reason or ('terminated' if outcome.terminated else '?')}")
    print(f"  tool calls:  {outcome.tool_calls} ({outcome.answered} answered, {outcome.denied} denied)")
    print(f"  status:      {status}")
    if outcome.stop_reason == "budget_reached":
        print("  The session hit its budget and PAUSED (not terminated). Raise or")
        print("  remove the budget to resume, or leave it - history is preserved.")
    for error in outcome.errors:
        print(f"  error: {error}")
    print(f"  console:     {session.console_url(created.id, args.workspace)}")
    print("-" * 52 + "\n")

    if args.json:
        _emit(outcome.to_dict(), True)
    return 0 if not outcome.errors else 1


def cmd_deploy(args: argparse.Namespace) -> int:
    manifest = config.load_manifest(args.manifest)
    if manifest.get("kind") != "deployment":
        print(f"{args.manifest}: kind must be `deployment`", file=sys.stderr)
        return 1

    # Validate alongside every manifest we know about - the configured
    # manifest directory AND the deployment's own directory - so the
    # unattended-agent cross-check can find the agent wherever it lives.
    manifest_path = os.path.abspath(args.manifest)
    candidate_paths = config.discover_manifests(args.manifests) + config.discover_manifests(
        os.path.dirname(manifest_path)
    )
    sibling_paths = sorted({os.path.abspath(p) for p in candidate_paths} | {manifest_path})
    results = {os.path.abspath(r.path): r for r in config.validate_all(sibling_paths)}
    result = results[manifest_path]
    if not result.ok:
        for error in result.errors:
            print(f"  error: {error}", file=sys.stderr)
        return 1
    for warning in result.warnings:
        print(f"  warn: {warning}")

    # For `validate` an unknown agent is a warning; for `deploy` it is fatal -
    # unattended-safety cannot be certified without the agent's tool config.
    known_agents = {
        m.get("name")
        for p in sibling_paths
        for m in [config.load_manifest(p)]
        if m.get("kind") == "agent"
    }
    if manifest["agent_name"] not in known_agents:
        print(
            f"  error: agent {manifest['agent_name']!r} is not defined in {args.manifests} "
            f"or next to {args.manifest}; cannot verify it can run unattended. "
            "Pass --manifests <dir containing its manifest>.",
            file=sys.stderr,
        )
        return 1

    state = config.load_state(args.state)
    try:
        agent_id = control.resolve(state, "agent", manifest["agent_name"])
        environment_id = control.resolve(state, "environment", manifest["environment_name"])
    except KeyError as exc:
        print(_message(exc), file=sys.stderr)
        return 1
    agent_version = state["agents"][manifest["agent_name"]].get("version")

    # A dry run must be inspectable without the secrets present: keep ${ENV}
    # references unexpanded and print the body with any tokens redacted.
    body = deploy.build_body(
        manifest, agent_id, environment_id, args.budget, agent_version,
        expand_secrets=not args.dry_run,
    )
    cap = config.format_cost(body["budget"]["max_list_cost"])
    schedule = manifest.get("schedule") or {}

    if args.dry_run:
        _emit(deploy.redact(body), True)
        return 0

    if not args.yes:
        print(f"\n  This schedules {manifest['name']!r} to fire a real session on")
        print(f"  {schedule.get('expression')} ({schedule.get('timezone')}), capped at {cap} per run.")
        if not _confirm("  Create this deployment? [y/N] "):
            print("  Aborted - nothing was created.")
            return 130

    client = control.make_client()
    applied = deploy.apply_deployment(
        client, manifest, agent_id, environment_id, state,
        budget_dollars=args.budget, agent_version=agent_version,
    )
    config.save_state(args.state, state)
    _emit(applied, args.json, text=json.dumps(applied, indent=2, default=str))
    return 0


def cmd_runs(args: argparse.Namespace) -> int:
    state = config.load_state(args.state)
    try:
        deployment_id = control.resolve(state, "deployment", args.deployment)
    except KeyError as exc:
        print(_message(exc), file=sys.stderr)
        return 1
    client = control.make_client()
    runs = deploy.list_runs(client, deployment_id, failures_only=args.failures)
    if args.json:
        _emit(runs, True)
    else:
        for run in runs:
            marker = run["error_type"] or run["session_id"] or "?"
            print(f"  {run['created_at']}  {marker}")
        print(f"\n{len(runs)} run(s).")
    return 0


# --------------------------------------------------------------------------
# parser
# --------------------------------------------------------------------------


def _positive(text: str) -> float:
    value = float(text)
    if value <= 0:
        raise argparse.ArgumentTypeError("budget must be greater than zero")
    return value


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m engine",
        description="Stand up and operate Claude Managed Agents.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    # Shared options live on every subcommand so they can be given where a
    # user naturally types them: `python -m engine validate --json`.
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--json", action="store_true", help="machine-readable output")
    common.add_argument("--manifests", default=DEFAULT_MANIFEST_DIR, help="manifest directory")
    common.add_argument("--state", default=DEFAULT_STATE, help="applied-state file")
    sub = parser.add_subparsers(dest="command", required=True)

    def add(name: str, help_text: str) -> argparse.ArgumentParser:
        return sub.add_parser(name, help=help_text, parents=[common])

    p = add("preflight", "check readiness (free)")
    p.add_argument("--live", action="store_true",
                   help="also probe GET /v1/agents - a control-plane read, costs $0")
    p.set_defaults(func=cmd_preflight)

    p = add("validate", "lint manifests offline")
    p.set_defaults(func=cmd_validate)

    p = add("bridge", "build .claude/skills/ so a mounted repo exposes its skills")
    p.add_argument("--check", action="store_true", help="verify without writing")
    p.add_argument("--mode", choices=["symlink", "copy"], default=bridge.DEFAULT_MODE)
    p.add_argument("--allowlist", default=DEFAULT_ALLOWLIST, help="skills to bridge, one per line")
    p.add_argument("--all", action="store_true", help="bridge every skill, ignoring the allowlist")
    p.add_argument("--no-prune", action="store_true",
                   help="leave entries that are not in the plan untouched")
    p.add_argument("--dry-run", action="store_true")
    p.set_defaults(func=cmd_bridge)

    p = add("apply", "create/update agents + environments")
    p.add_argument("--dry-run", action="store_true")
    p.set_defaults(func=cmd_apply)

    p = add("status", "show applied resource IDs")
    p.set_defaults(func=cmd_status)

    p = add("run", "run a live session (SPENDS MONEY)")
    p.add_argument("agent", help="agent name from the manifests")
    p.add_argument("prompt", help="the task to send")
    p.add_argument("--environment", default="henry-cloud")
    p.add_argument("--budget", type=_positive, default=DEFAULT_SESSION_BUDGET_USD,
                   help=f"hard USD cap for this session (default {DEFAULT_SESSION_BUDGET_USD:.2f})")
    p.add_argument("--title")
    p.add_argument("--workspace", default="default", help="workspace ID for the Console link")
    p.add_argument("--approve", choices=[session.APPROVE_ASK, session.APPROVE_ALLOW,
                                         session.APPROVE_DENY], default=session.APPROVE_ASK)
    p.add_argument("--yes", action="store_true", help="skip the spend confirmation")
    p.set_defaults(func=cmd_run)

    p = add("deploy", "create/update a cron deployment")
    p.add_argument("manifest", help="path to a kind: deployment manifest")
    p.add_argument("--budget", type=_positive, default=None,
                   help="hard USD cap per fired session; overrides the manifest's `budget:`")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--yes", action="store_true")
    p.set_defaults(func=cmd_deploy)

    p = add("runs", "list deployment run records")
    p.add_argument("deployment", help="deployment name from the manifests")
    p.add_argument("--failures", action="store_true", help="failed runs only")
    p.set_defaults(func=cmd_runs)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except config.ManifestError as exc:
        print(f"manifest error: {exc}", file=sys.stderr)
        return 1
    except (ValueError, RuntimeError) as exc:
        print(f"error: {_message(exc)}", file=sys.stderr)
        return 1
    except TypeError as exc:
        # The SDK rejected a field the validator let through - report, don't trace.
        print(f"error: the API client rejected the request: {_message(exc)}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nInterrupted.", file=sys.stderr)
        return 130


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
