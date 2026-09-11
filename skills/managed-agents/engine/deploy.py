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
"""

from __future__ import annotations

from typing import Any

from . import config

# Local hours where DST transitions make wall-clock matching lossy or doubled.
DST_RISK_HOURS = {1, 2, 3}


def validate_schedule(schedule: dict[str, Any]) -> list[str]:
    """Offline checks on a cron schedule block."""
    problems: list[str] = []
    if not isinstance(schedule, dict):
        return ["`schedule` must be a mapping"]
    if schedule.get("type") != "cron":
        problems.append('`schedule.type` must be "cron"')

    expression = schedule.get("expression")
    if not isinstance(expression, str) or not expression.strip():
        problems.append("`schedule.expression` is required")
    else:
        fields = expression.split()
        if len(fields) != 5:
            problems.append(
                f"`schedule.expression` has {len(fields)} fields, POSIX cron takes 5 "
                "(minute hour day-of-month month day-of-week)"
            )

    if not schedule.get("timezone"):
        problems.append("`schedule.timezone` is required (IANA identifier)")

    return problems


def schedule_warnings(schedule: dict[str, Any]) -> list[str]:
    """Non-fatal risks worth surfacing before a schedule goes live."""
    warnings: list[str] = []
    expression = schedule.get("expression")
    timezone = schedule.get("timezone", "")
    if not isinstance(expression, str):
        return warnings
    fields = expression.split()
    if len(fields) != 5:
        return warnings

    hour_field = fields[1]
    if hour_field.isdigit() and int(hour_field) in DST_RISK_HOURS and timezone != "UTC":
        warnings.append(
            f"hour {hour_field} in {timezone} sits in the DST transition window - "
            "that wall-clock time is skipped on spring-forward and fires twice on "
            "fall-back. Move it outside 01:00-03:59 local, or use UTC."
        )
    if fields[0] == "*":
        warnings.append(
            "this fires every minute - a scheduled deployment creates a full "
            "session per firing. Confirm that is intended."
        )
    return warnings


def build_body(
    manifest: dict[str, Any],
    agent_id: str,
    environment_id: str,
    budget_dollars: float | None = None,
) -> dict[str, Any]:
    """Turn a deployment manifest plus resolved IDs into the API body."""
    body = config.to_api_body(manifest)
    body.pop("agent_name", None)
    body.pop("environment_name", None)
    body["agent"] = agent_id
    body["environment_id"] = environment_id
    if budget_dollars:
        body["budget"] = config.budget_from_dollars(budget_dollars)
    return body


def apply_deployment(
    client: Any,
    manifest: dict[str, Any],
    agent_id: str,
    environment_id: str,
    state: dict[str, Any],
    budget_dollars: float | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Create or update one scheduled deployment, idempotent by name."""
    name = manifest["name"]
    body = build_body(manifest, agent_id, environment_id, budget_dollars)
    recorded = state["deployments"].get(name)

    if dry_run:
        return {"name": name, "action": "would-apply", "id": (recorded or {}).get("id")}

    existing_id = (recorded or {}).get("id")
    if existing_id:
        try:
            update_body = {k: v for k, v in body.items() if k != "name"}
            resource = client.beta.deployments.update(existing_id, **update_body)
            action = "updated"
        except Exception:
            resource = client.beta.deployments.create(**body)
            action = "created"
    else:
        resource = client.beta.deployments.create(**body)
        action = "created"

    state["deployments"][name] = {"id": resource.id}
    upcoming = []
    schedule = getattr(resource, "schedule", None)
    if schedule is not None:
        upcoming = list(getattr(schedule, "upcoming_runs_at", None) or [])
    return {
        "name": name,
        "action": action,
        "id": resource.id,
        "status": getattr(resource, "status", None),
        "upcoming_runs_at": upcoming[:3],
    }


def list_runs(client: Any, deployment_id: str, failures_only: bool = False) -> list[dict[str, Any]]:
    """Recent run records for a deployment - the audit trail for cron firings."""
    kwargs: dict[str, Any] = {"deployment_id": deployment_id}
    if failures_only:
        kwargs["has_error"] = True
    page = client.beta.deployment_runs.list(**kwargs)
    runs = getattr(page, "data", None)
    runs = list(runs) if runs is not None else list(page)

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
