"""Scheduled deployments - the agent runs on cron, with no human at the keyboard.

Each firing creates a session autonomously and writes a `deployment_run` record
(`drun_`) whether it succeeded or not, so failures are auditable independently
of the session lifecycle.

Two facts worth carrying into any schedule you write here:
  * Fire times are jittered up to 15% of the interval (floor 5s, cap 9 min), so
    an hourly deployment can land up to 9 minutes late. Never hang a downstream
    deadline off `upcoming_runs_at`.
  * Cron matches literal wall-clock in the given IANA timezone. On a DST
    spring-forward day a 1-3am local time is SKIPPED; on fall-back it fires
    TWICE. Schedule outside that window, or use UTC.

A deployment fires with no client attached, so its agent must be able to finish
a turn unattended: an `always_ask` tool would park every firing in
`requires_action` forever. Manifests can carry `agent_overrides:` (the API's
`agent_with_overrides` form) to disable such tools for the scheduled run only.
"""

from __future__ import annotations

import copy
import os
import re
from typing import Any

from . import config, control

# Re-exported for callers that imported them from here before they moved.
validate_schedule = config.validate_schedule
schedule_warnings = config.schedule_warnings

_ENV_REF = re.compile(r"^\$\{([A-Z_][A-Z0-9_]*)\}$")
REDACTED = "<redacted>"


def expand_secret_refs(resources: Any) -> Any:
    """Resolve `${ENV_VAR}` references in resource tokens from the environment.

    Manifests are committed, so they carry references, never values. The value
    is read here - on the operator's machine, at apply time - and sent only to
    the API, which never echoes it back.
    """
    if not isinstance(resources, list):
        return resources
    expanded = []
    for resource in resources:
        if not isinstance(resource, dict):
            expanded.append(resource)
            continue
        item = dict(resource)
        token = item.get("authorization_token")
        if isinstance(token, str):
            match = _ENV_REF.match(token)
            if match:
                value = os.environ.get(match.group(1))
                if not value:
                    raise ValueError(
                        f"resource {item.get('url', '?')}: environment variable "
                        f"{match.group(1)} is not set (referenced by authorization_token)"
                    )
                item["authorization_token"] = value
        expanded.append(item)
    return expanded


def redact(body: dict[str, Any]) -> dict[str, Any]:
    """Copy of an API body safe to print: resource tokens masked."""
    safe = copy.deepcopy(body)
    for resource in safe.get("resources") or []:
        if isinstance(resource, dict) and "authorization_token" in resource:
            resource["authorization_token"] = REDACTED
    return safe


def build_body(
    manifest: dict[str, Any],
    agent_id: str,
    environment_id: str,
    budget_dollars: float | None = None,
    agent_version: int | None = None,
    expand_secrets: bool = True,
) -> dict[str, Any]:
    """Turn a deployment manifest plus resolved IDs into the API body.

    Budget precedence: an explicit `budget_dollars` (the CLI flag, when given)
    replaces a manifest `budget:`; otherwise the manifest's value stands. A body
    with NO budget is refused - a cron deployment fires unattended, so an
    uncapped one is the single most expensive mistake this engine can make.

    `expand_secrets=False` leaves `${ENV}` references in place, so a dry run
    can be inspected on a machine that does not hold the secret.
    """
    body = config.to_api_body(manifest)
    body.pop("agent_name", None)
    body.pop("environment_name", None)
    overrides = body.pop("agent_overrides", None)

    if overrides:
        agent_ref: dict[str, Any] = {"type": "agent_with_overrides", "id": agent_id}
        if agent_version:
            agent_ref["version"] = int(agent_version)
        agent_ref.update(overrides)
        body["agent"] = agent_ref
    elif agent_version:
        body["agent"] = {"type": "agent", "id": agent_id, "version": int(agent_version)}
    else:
        body["agent"] = agent_id
    body["environment_id"] = environment_id

    if budget_dollars is not None:
        body["budget"] = config.budget_from_dollars(budget_dollars)  # raises if <= 0
    if not body.get("budget"):
        raise ValueError(
            "deployment has no budget - set `budget:` in the manifest or pass --budget N. "
            "An uncapped cron deployment is never created by this engine."
        )

    if "resources" in body and expand_secrets:
        body["resources"] = expand_secret_refs(body["resources"])
    return body


def _not_found(exc: Exception) -> bool:
    return type(exc).__name__ == "NotFoundError" or getattr(exc, "status_code", None) == 404


def apply_deployment(
    client: Any,
    manifest: dict[str, Any],
    agent_id: str,
    environment_id: str,
    state: dict[str, Any],
    budget_dollars: float | None = None,
    agent_version: int | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Create or update one scheduled deployment, idempotent by name.

    Only a 404 on the recorded ID falls through to a name lookup and then to
    create. Any other failure is raised: falling through on a 429/500 would
    create a SECOND deployment on the same schedule, both firing billable
    sessions, with the first orphaned from `state.json`.
    """
    name = manifest["name"]
    body = build_body(manifest, agent_id, environment_id, budget_dollars, agent_version)
    recorded = state["deployments"].get(name)

    if dry_run:
        return {"name": name, "action": "would-apply", "id": (recorded or {}).get("id")}

    existing = None
    existing_id = (recorded or {}).get("id")
    if existing_id:
        try:
            existing = client.beta.deployments.retrieve(existing_id)
        except Exception as exc:
            if not _not_found(exc):
                raise
    if existing is None:
        # Required: this lookup is what stops a lost state.json from
        # producing a second, equally billable cron deployment.
        existing = control.find_by_name(client, "deployments", name, required=True)

    if existing is None:
        resource = client.beta.deployments.create(**body)
        action = "created"
    else:
        update_body = {k: v for k, v in body.items() if k != "name"}
        resource = client.beta.deployments.update(existing.id, **update_body)
        action = "updated"

    state["deployments"][name] = {"id": resource.id}
    upcoming: list[Any] = []
    schedule = getattr(resource, "schedule", None)
    if schedule is not None:
        upcoming = list(getattr(schedule, "upcoming_runs_at", None) or [])
    return {
        "name": name,
        "action": action,
        "id": resource.id,
        "status": getattr(resource, "status", None),
        "budget": body.get("budget"),
        "upcoming_runs_at": upcoming[:3],
    }


def list_runs(client: Any, deployment_id: str, failures_only: bool = False) -> list[dict[str, Any]]:
    """Every run record for a deployment - the audit trail for cron firings."""
    kwargs: dict[str, Any] = {"deployment_id": deployment_id}
    if failures_only:
        kwargs["has_error"] = True
    runs = control.iter_all(client.beta.deployment_runs.list(**kwargs))

    out = []
    for run in runs:
        error = getattr(run, "error", None)
        out.append(
            {
                "id": getattr(run, "id", None),
                "created_at": getattr(run, "created_at", None),
                "session_id": getattr(run, "session_id", None),
                "error_type": getattr(error, "type", None) if error else None,
                "error_message": getattr(error, "message", None) if error else None,
            }
        )
    return out
