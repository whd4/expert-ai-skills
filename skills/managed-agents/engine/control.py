"""Control plane: apply agent and environment manifests to the API.

This is the "create once, reference forever" half of Managed Agents. Applying
is idempotent by `name`: an existing resource is UPDATED in place (bumping its
version) rather than duplicated, because sessions pin to an agent version and
re-creating agents orphans them.

Control-plane calls cost nothing - no session is created, no container is
provisioned, no tokens are consumed.
"""

from __future__ import annotations

from typing import Any

from . import config


def make_client(anthropic_module: Any = None) -> Any:
    """Construct an SDK client, resolving credentials from the environment.

    The SDK checks ANTHROPIC_API_KEY, then ANTHROPIC_AUTH_TOKEN, then an
    `ant auth login` profile. We never read the secret ourselves.
    """
    if anthropic_module is None:
        import anthropic as anthropic_module  # noqa: PLC0415
    return anthropic_module.Anthropic()


def iter_all(pager: Any) -> list[Any]:
    """Collect a paginated response into a plain list - EVERY page.

    Iterating an SDK page object auto-paginates (`BaseSyncPage.__iter__` walks
    `iter_pages()`); reading `.data` would stop at the first page and make
    `find_by_name` miss resources past it, which is how duplicates get created.
    """
    if isinstance(pager, list):
        return pager
    try:
        return list(pager)
    except TypeError:
        data = getattr(pager, "data", None)
        return list(data) if data is not None else []


def find_by_name(client: Any, resource: str, name: str, required: bool = False) -> Any | None:
    """Locate an existing agent/environment/deployment by exact name, or None.

    `required=True` makes a missing `list` capability an error instead of a
    quiet "not found" - when this lookup is what stands between a lost
    state.json and a duplicate resource, degrading silently is the wrong
    failure mode.
    """
    namespace = getattr(client.beta, resource, None)
    if namespace is None or not hasattr(namespace, "list"):
        if required:
            raise RuntimeError(
                f"this SDK cannot list {resource}; refusing to create one blind - "
                "upgrade the anthropic package (pip install --upgrade anthropic)"
            )
        return None
    try:
        page = namespace.list(limit=100)
    except TypeError:  # pragma: no cover - SDKs that take no limit kwarg
        page = namespace.list()
    for item in iter_all(page):
        if getattr(item, "name", None) == name:
            return item
    return None


def _metadata_delta(live: Any, desired: Any) -> dict[str, Any]:
    """Metadata body that makes the live resource match the manifest exactly.

    The API merges metadata on update and deletes a key when its value is
    null, so every live key absent from the manifest is sent as null.
    """
    live_keys = set(live or {}) if isinstance(live, dict) else set()
    wanted = dict(desired or {})
    return {**{key: None for key in live_keys if key not in wanted}, **wanted}


def apply_environment(
    client: Any, manifest: dict[str, Any], state: dict[str, Any], dry_run: bool = False
) -> dict[str, Any]:
    """Create or update one environment. Names are unique - duplicates 409."""
    name = manifest["name"]
    body = config.to_api_body(manifest)
    recorded = state["environments"].get(name)

    if dry_run:
        return {"name": name, "action": "would-apply", "id": (recorded or {}).get("id")}

    existing = None
    if recorded and recorded.get("id"):
        try:
            existing = client.beta.environments.retrieve(recorded["id"])
        except Exception:
            existing = None
    if existing is None:
        existing = find_by_name(client, "environments", name)

    if existing is None:
        created = client.beta.environments.create(**body)
        action = "created"
        resource = created
    else:
        update_body = {k: v for k, v in body.items() if k != "name"}
        update_body.setdefault("description", None)
        update_body["metadata"] = _metadata_delta(
            getattr(existing, "metadata", None), body.get("metadata")
        )
        resource = client.beta.environments.update(existing.id, **update_body)
        action = "updated"

    state["environments"][name] = {"id": resource.id}
    return {"name": name, "action": action, "id": resource.id}


def apply_agent(
    client: Any, manifest: dict[str, Any], state: dict[str, Any], dry_run: bool = False
) -> dict[str, Any]:
    """Create or update one agent.

    Update is preferred over create whenever the name already exists: each
    update makes a new immutable version, running sessions keep the version
    they pinned, and rollback stays possible. `version` is deliberately NOT
    sent - this is a declarative apply loop that owns the agent, so the
    unconditional form is correct (supplying it would 409 on any drift).
    """
    name = manifest["name"]
    body = config.to_api_body(manifest)
    recorded = state["agents"].get(name)

    if dry_run:
        return {"name": name, "action": "would-apply", "id": (recorded or {}).get("id")}

    existing = None
    if recorded and recorded.get("id"):
        try:
            existing = client.beta.agents.retrieve(recorded["id"])
        except Exception:
            existing = None
    if existing is None:
        existing = find_by_name(client, "agents", name)

    if existing is None:
        resource = client.beta.agents.create(**body)
        action = "created"
    else:
        # Declarative: the file is the source of truth. The API preserves
        # omitted fields on update, so a block deleted from the manifest must
        # be sent as an explicit clear or the old value silently stays live.
        update_body = {k: v for k, v in body.items() if k != "name"}
        for cleared in ("system", "description", "multiagent"):
            update_body.setdefault(cleared, None)
        for cleared in ("tools", "skills", "mcp_servers"):
            update_body.setdefault(cleared, [])
        # metadata merges key-by-key on update (a null value deletes a key),
        # so a key dropped from the manifest must be sent as null explicitly.
        update_body["metadata"] = _metadata_delta(
            getattr(existing, "metadata", None), body.get("metadata")
        )
        resource = client.beta.agents.update(existing.id, **update_body)
        action = "updated"

    state["agents"][name] = {
        "id": resource.id,
        "version": getattr(resource, "version", None),
    }
    return {
        "name": name,
        "action": action,
        "id": resource.id,
        "version": getattr(resource, "version", None),
    }


def apply_manifests(
    client: Any,
    manifests: list[tuple[str, dict[str, Any]]],
    state: dict[str, Any],
    dry_run: bool = False,
) -> list[dict[str, Any]]:
    """Apply environments first, then agents - agents may reference nothing else,
    but a session needs both, and this ordering keeps `state` useful if the run
    is interrupted partway."""
    ordered = sorted(
        manifests, key=lambda item: 0 if item[1].get("kind") == "environment" else 1
    )
    results = []
    for path, manifest in ordered:
        kind = manifest.get("kind")
        if kind == "environment":
            outcome = apply_environment(client, manifest, state, dry_run=dry_run)
        elif kind == "agent":
            outcome = apply_agent(client, manifest, state, dry_run=dry_run)
        else:
            continue
        outcome["kind"] = kind
        outcome["path"] = path
        results.append(outcome)
    return results


def resolve(state: dict[str, Any], kind: str, name: str) -> str:
    """Look up an applied resource ID by name, with an actionable error."""
    bucket = state.get(f"{kind}s", {})
    entry = bucket.get(name)
    if not entry or not entry.get("id"):
        known = ", ".join(sorted(bucket)) or "(none applied yet)"
        raise KeyError(
            f"no applied {kind} named {name!r}. Applied {kind}s: {known}. "
            f"Run `python -m engine apply` first."
        )
    return entry["id"]
