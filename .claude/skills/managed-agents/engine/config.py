"""Manifest loading + offline validation for Claude Managed Agents.

Every rule here mirrors a documented API constraint. The point is to fail on
your laptop for free instead of failing on `POST /v1/agents` after you have
already burned a round-trip. No network, no SDK, no credentials required.

Manifest kinds:
    kind: agent        -> POST /v1/agents        body
    kind: environment  -> POST /v1/environments  body
    kind: deployment   -> POST /v1/deployments   body

The manifest IS the API body (plus a `kind` discriminator). No invented
abstraction layer, so anything the API grows keeps working without a
release here.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from typing import Any

try:
    import yaml
except ImportError:  # pragma: no cover - yaml is in the repo's baseline
    yaml = None

# --------------------------------------------------------------------------
# Documented constants (source: Anthropic Managed Agents beta, 2026-04-01)
# --------------------------------------------------------------------------

TOOLSET_TYPE = "agent_toolset_20260401"
BETA_HEADER = "managed-agents-2026-04-01"

BUILTIN_TOOLS = frozenset(
    {"bash", "read", "write", "edit", "glob", "grep", "web_fetch", "web_search"}
)
WEB_TOOLS = frozenset({"web_search", "web_fetch"})
PERMISSION_POLICIES = frozenset({"always_allow", "always_ask"})

# Agents accept "all Claude 4.5+ models". Unknown IDs warn rather than fail so
# a model released after this file was written is not blocked by it.
KNOWN_MODELS = frozenset(
    {
        "claude-fable-5-1",
        "claude-fable-5",
        "claude-mythos-5-1",
        "claude-opus-5",
        "claude-opus-4-8",
        "claude-opus-4-7",
        "claude-opus-4-6",
        "claude-sonnet-5",
        "claude-sonnet-4-6",
        "claude-haiku-4-5",
    }
)
EFFORT_LEVELS = frozenset({"low", "medium", "high", "xhigh", "max"})
INFERENCE_GEOS = frozenset({"us", "global"})

MAX_TOOLS = 128
MAX_MCP_SERVERS = 20
MAX_SKILLS = 20
MAX_METADATA_KEYS = 16
MAX_METADATA_KEY_CHARS = 64
MAX_METADATA_VALUE_CHARS = 512
MAX_SYSTEM_CHARS = 100_000
MAX_DESCRIPTION_CHARS = 2048
MAX_NAME_CHARS = 256
MAX_DOMAINS = 64
MAX_DOMAIN_CHARS = 255

# Domain-list rejections, documented verbatim in the API's 400 messages.
_RESERVED_SUFFIXES = (".localhost", ".local", ".internal", ".localdomain", ".invalid")
_IPV4_RE = re.compile(r"^\d{1,3}(\.\d{1,3}){3}$")
# Hostnames: letters, digits, dots, hyphens. Underscores are not valid in a
# hostname; `/` is allowed only so a web_search path suffix can be split off.
_ASCII_HOST_RE = re.compile(r"^[A-Za-z0-9.\-/]+$")
# Registry suffixes the API rejects as "bare TLDs/registry suffixes". A listed
# domain must be a registrable name, not the registry it lives under.
_REGISTRY_SUFFIXES = frozenset(
    {
        "co.uk", "org.uk", "gov.uk", "ac.uk", "me.uk", "net.uk", "ltd.uk", "plc.uk",
        "com.au", "net.au", "org.au", "edu.au", "gov.au",
        "co.nz", "org.nz", "net.nz", "govt.nz",
        "co.jp", "ne.jp", "or.jp", "ac.jp", "go.jp",
        "co.in", "net.in", "org.in", "gov.in", "ac.in",
        "co.za", "org.za", "gov.za",
        "com.br", "net.br", "org.br", "gov.br",
        "com.mx", "org.mx", "gob.mx",
        "com.sg", "com.hk", "com.tw", "com.cn", "net.cn", "org.cn",
        "com.ar", "com.tr", "com.my", "co.kr", "co.id", "co.il",
    }
)

# Anything shaped like a credential has no business in a committed manifest.
_SECRET_MARKERS = ("sk-ant-", "ghp_", "github_pat_", "gho_", "ghs_", "xoxb-", "xoxp-", "AKIA")
_SECRET_KEYS = frozenset(
    {"access_token", "refresh_token", "client_secret", "secret_value", "api_key", "password"}
)
_ENV_REF_RE = re.compile(r"^\$\{[A-Z_][A-Z0-9_]*\}$")


class ManifestError(Exception):
    """Raised when a manifest cannot be loaded at all (bad YAML, missing kind)."""


@dataclass
class ValidationResult:
    """Outcome of validating one manifest."""

    path: str
    kind: str
    name: str
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "kind": self.kind,
            "name": self.name,
            "ok": self.ok,
            "errors": self.errors,
            "warnings": self.warnings,
        }


# --------------------------------------------------------------------------
# Loading
# --------------------------------------------------------------------------


def load_manifest(path: str) -> dict[str, Any]:
    """Read one YAML (or JSON) manifest off disk."""
    if yaml is None:
        raise ManifestError("PyYAML is required to read manifests: pip install pyyaml")
    with open(path, encoding="utf-8") as handle:
        try:
            data = yaml.safe_load(handle)
        except yaml.YAMLError as exc:
            raise ManifestError(f"{path}: invalid YAML: {exc}") from exc
    if not isinstance(data, dict):
        raise ManifestError(f"{path}: manifest must be a mapping, got {type(data).__name__}")
    if "kind" not in data:
        raise ManifestError(f"{path}: manifest is missing the required `kind` field")
    if data["kind"] not in {"agent", "environment", "deployment"}:
        raise ManifestError(
            f"{path}: unknown kind {data['kind']!r} "
            "(expected agent, environment, or deployment)"
        )
    return data


def discover_manifests(directory: str) -> list[str]:
    """Every *.yaml / *.yml manifest in a directory, sorted, dotfiles skipped."""
    if not os.path.isdir(directory):
        return []
    found = [
        os.path.join(directory, entry)
        for entry in sorted(os.listdir(directory))
        if entry.endswith((".yaml", ".yml")) and not entry.startswith(".")
    ]
    return found


def to_api_body(manifest: dict[str, Any]) -> dict[str, Any]:
    """Strip local-only keys, leaving exactly what the endpoint accepts."""
    return {k: v for k, v in manifest.items() if k not in {"kind", "x-notes"}}


# --------------------------------------------------------------------------
# Validation
# --------------------------------------------------------------------------


def validate(manifest: dict[str, Any], path: str = "<memory>") -> ValidationResult:
    """Validate one manifest against the documented API constraints."""
    kind = manifest.get("kind", "?")
    name = manifest.get("name", "")
    result = ValidationResult(path=path, kind=kind, name=name if isinstance(name, str) else "")

    _check_name(name, result)
    _check_metadata(manifest.get("metadata"), result)
    _scan_for_secrets(manifest, result)

    if kind == "agent":
        _validate_agent(manifest, result)
    elif kind == "environment":
        _validate_environment(manifest, result)
    elif kind == "deployment":
        _validate_deployment(manifest, result)

    return result


def validate_all(paths: list[str]) -> list[ValidationResult]:
    """Validate each manifest, then the rules that span them."""
    results: list[ValidationResult] = []
    loaded: list[tuple[str, dict[str, Any]]] = []
    by_path: dict[str, ValidationResult] = {}
    for path in paths:
        try:
            manifest = load_manifest(path)
        except ManifestError as exc:
            results.append(
                ValidationResult(path=path, kind="?", name="", errors=[str(exc)])
            )
            continue
        result = validate(manifest, path)
        results.append(result)
        loaded.append((path, manifest))
        by_path[path] = result
    cross_validate(loaded, by_path)
    return results


def _check_name(name: Any, result: ValidationResult) -> None:
    if not isinstance(name, str) or not name.strip():
        result.errors.append("`name` is required and must be a non-empty string")
    elif len(name) > MAX_NAME_CHARS:
        result.errors.append(f"`name` is {len(name)} chars, max {MAX_NAME_CHARS}")


def _check_metadata(metadata: Any, result: ValidationResult) -> None:
    if metadata is None:
        return
    if not isinstance(metadata, dict):
        result.errors.append("`metadata` must be a mapping")
        return
    if len(metadata) > MAX_METADATA_KEYS:
        result.errors.append(
            f"`metadata` has {len(metadata)} keys, max {MAX_METADATA_KEYS}"
        )
    for key, value in metadata.items():
        if len(str(key)) > MAX_METADATA_KEY_CHARS:
            result.errors.append(f"metadata key {key!r} exceeds {MAX_METADATA_KEY_CHARS} chars")
        if not isinstance(value, str):
            result.errors.append(
                f"metadata value for {key!r} must be a string (YAML parsed it as "
                f"{type(value).__name__} - quote it)"
            )
        elif len(value) > MAX_METADATA_VALUE_CHARS:
            result.errors.append(
                f"metadata value for {key!r} exceeds {MAX_METADATA_VALUE_CHARS} chars"
            )


# ---- agent ---------------------------------------------------------------


def _validate_agent(manifest: dict[str, Any], result: ValidationResult) -> None:
    for forbidden in ("environment_id", "resources", "vault_ids", "budget"):
        if forbidden in manifest:
            result.errors.append(
                f"`{forbidden}` is a SESSION field - it does not belong on an agent manifest"
            )

    _validate_model(manifest.get("model"), result)

    system = manifest.get("system")
    if system is not None:
        if not isinstance(system, str):
            result.errors.append("`system` must be a string")
        elif len(system) > MAX_SYSTEM_CHARS:
            result.errors.append(
                f"`system` is {len(system)} chars, max {MAX_SYSTEM_CHARS}"
            )
        elif not system.strip():
            result.warnings.append("`system` is blank - the agent has no persona")

    description = manifest.get("description")
    if description is not None and isinstance(description, str):
        if len(description) > MAX_DESCRIPTION_CHARS:
            result.errors.append(
                f"`description` is {len(description)} chars, max {MAX_DESCRIPTION_CHARS}"
            )

    servers = _validate_mcp_servers(manifest.get("mcp_servers"), result)
    _validate_tools(manifest.get("tools"), servers, result)
    _validate_skills(manifest.get("skills"), manifest.get("tools"), result)


def _validate_model(model: Any, result: ValidationResult) -> None:
    if model is None:
        result.errors.append("`model` is required on an agent")
        return

    if isinstance(model, str):
        model_id, effort, geo = model, None, None
    elif isinstance(model, dict):
        model_id = model.get("id")
        effort = model.get("effort")
        geo = model.get("inference_geo")
        if not model_id:
            result.errors.append("`model.id` is required when `model` is an object")
    else:
        result.errors.append("`model` must be a string or an object")
        return

    if isinstance(model_id, str) and model_id and model_id not in KNOWN_MODELS:
        result.warnings.append(
            f"model {model_id!r} is not in this file's known list - "
            "verify it exists and is 4.5+ before applying"
        )

    if effort is not None:
        level = effort.get("type") if isinstance(effort, dict) else effort
        if level not in EFFORT_LEVELS:
            result.errors.append(
                f"`model.effort` is {level!r}, expected one of {sorted(EFFORT_LEVELS)}"
            )

    if geo is not None and geo not in INFERENCE_GEOS:
        result.errors.append(
            f"`model.inference_geo` is {geo!r}, expected 'us' or 'global'"
        )


def _validate_mcp_servers(servers: Any, result: ValidationResult) -> set[str]:
    names: set[str] = set()
    if servers is None:
        return names
    if not isinstance(servers, list):
        result.errors.append("`mcp_servers` must be a list")
        return names
    if len(servers) > MAX_MCP_SERVERS:
        result.errors.append(
            f"`mcp_servers` has {len(servers)} entries, max {MAX_MCP_SERVERS}"
        )
    for index, server in enumerate(servers):
        if not isinstance(server, dict):
            result.errors.append(f"mcp_servers.{index}: must be a mapping")
            continue
        if server.get("type") != "url":
            result.errors.append(f"mcp_servers.{index}: `type` must be \"url\"")
        server_name = server.get("name")
        if not server_name:
            result.errors.append(f"mcp_servers.{index}: `name` is required")
        elif server_name in names:
            result.errors.append(f"mcp_servers.{index}: duplicate name {server_name!r}")
        else:
            names.add(server_name)
        if not server.get("url"):
            result.errors.append(f"mcp_servers.{index}: `url` is required")
        for secret_key in ("auth", "authorization", "token", "headers", "api_key"):
            if secret_key in server:
                result.errors.append(
                    f"mcp_servers.{index}: `{secret_key}` is not an MCP server field - "
                    "MCP auth belongs in a vault credential, never in the agent manifest"
                )
    return names


def _validate_tools(tools: Any, servers: set[str], result: ValidationResult) -> None:
    if tools is None:
        result.warnings.append("no `tools` - the agent can only talk, not act")
        return
    if not isinstance(tools, list):
        result.errors.append("`tools` must be a list")
        return
    if len(tools) > MAX_TOOLS:
        result.errors.append(f"`tools` has {len(tools)} entries, max {MAX_TOOLS}")

    for index, tool in enumerate(tools):
        if not isinstance(tool, dict):
            result.errors.append(f"tools.{index}: must be a mapping")
            continue
        tool_type = tool.get("type")
        if tool_type == TOOLSET_TYPE:
            _validate_toolset(tool, index, result)
        elif tool_type == "mcp_toolset":
            server_name = tool.get("mcp_server_name")
            if not server_name:
                result.errors.append(f"tools.{index}: `mcp_server_name` is required")
            elif server_name not in servers:
                result.errors.append(
                    f"tools.{index}: mcp_toolset references {server_name!r}, "
                    "which is not declared in `mcp_servers`"
                )
        elif tool_type == "custom":
            if not tool.get("name"):
                result.errors.append(f"tools.{index}: custom tool needs a `name`")
            if not isinstance(tool.get("input_schema"), dict):
                result.errors.append(
                    f"tools.{index}: custom tool needs an `input_schema` object"
                )
        elif tool_type and tool_type.startswith("agent_toolset_"):
            result.errors.append(
                f"tools.{index}: toolset version {tool_type!r} is not the one this "
                f"engine targets ({TOOLSET_TYPE})"
            )
        else:
            result.errors.append(f"tools.{index}: unknown tool type {tool_type!r}")


def _validate_toolset(tool: dict[str, Any], index: int, result: ValidationResult) -> None:
    default_config = tool.get("default_config")
    if default_config is not None:
        if not isinstance(default_config, dict):
            result.errors.append(f"tools.{index}: `default_config` must be a mapping")
        else:
            _validate_permission_policy(
                default_config.get("permission_policy"),
                f"tools.{index}.default_config",
                result,
            )

    configs = tool.get("configs")
    if configs is None:
        return
    if not isinstance(configs, list):
        result.errors.append(f"tools.{index}: `configs` must be a list")
        return

    seen: set[str] = set()
    for config_index, config in enumerate(configs):
        label = f"tools.{index}.configs.{config_index}"
        if not isinstance(config, dict):
            result.errors.append(f"{label}: must be a mapping")
            continue
        tool_name = config.get("name")
        if tool_name not in BUILTIN_TOOLS:
            result.errors.append(
                f"{label}: `name` is {tool_name!r}, expected one of {sorted(BUILTIN_TOOLS)}"
            )
            continue
        if tool_name in seen:
            result.errors.append(f"{label}: duplicate config for {tool_name!r}")
        seen.add(tool_name)

        declared_type = config.get("type")
        if declared_type is not None and declared_type != tool_name:
            result.errors.append(
                f"{label}: `type` {declared_type!r} must match `name` {tool_name!r}"
            )

        _validate_permission_policy(config.get("permission_policy"), label, result)
        _validate_web_settings(config, tool_name, label, result)


def _validate_permission_policy(policy: Any, label: str, result: ValidationResult) -> None:
    if policy is None:
        return
    if not isinstance(policy, dict):
        result.errors.append(f"{label}: `permission_policy` must be a mapping")
        return
    if policy.get("type") not in PERMISSION_POLICIES:
        result.errors.append(
            f"{label}: permission_policy.type is {policy.get('type')!r}, "
            f"expected one of {sorted(PERMISSION_POLICIES)}"
        )


def _validate_web_settings(
    config: dict[str, Any], tool_name: str, label: str, result: ValidationResult
) -> None:
    web_keys = {"allowed_domains", "blocked_domains", "max_content_tokens", "user_location"}
    present = web_keys & set(config)
    if present and tool_name not in WEB_TOOLS:
        result.errors.append(
            f"{label}: {sorted(present)} only apply to web_search / web_fetch"
        )
        return

    if "allowed_domains" in config and "blocked_domains" in config:
        result.errors.append(
            f"{label}: allowed_domains and blocked_domains are mutually exclusive"
        )

    for key in ("allowed_domains", "blocked_domains"):
        if key in config:
            _validate_domain_list(config[key], tool_name, f"{label}.{key}", result)

    if "max_content_tokens" in config:
        if tool_name != "web_fetch":
            result.errors.append(f"{label}: max_content_tokens applies to web_fetch only")
        elif not isinstance(config["max_content_tokens"], int) or config["max_content_tokens"] <= 0:
            result.errors.append(f"{label}: max_content_tokens must be a positive integer")

    if "user_location" in config:
        if tool_name != "web_search":
            result.errors.append(f"{label}: user_location applies to web_search only")
        else:
            _validate_user_location(config["user_location"], f"{label}.user_location", result)


def _validate_user_location(location: Any, label: str, result: ValidationResult) -> None:
    if not isinstance(location, dict):
        result.errors.append(f"{label}: must be a mapping")
        return
    if location.get("type") != "approximate":
        result.errors.append(f"{label}: `type` must be \"approximate\"")
    optional = {"city", "region", "country", "timezone"}
    if not (optional & set(location)):
        result.errors.append(f"{label}: needs at least one of {sorted(optional)}")
    country = location.get("country")
    if country is not None and not (
        isinstance(country, str) and len(country) == 2 and country.isupper()
    ):
        result.errors.append(
            f"{label}.country must be a 2-letter uppercase ISO 3166-1 code"
        )


def _validate_domain_list(
    domains: Any, tool_name: str, label: str, result: ValidationResult
) -> None:
    if not isinstance(domains, list):
        result.errors.append(f"{label}: must be a list")
        return
    if not domains:
        result.errors.append(
            f"{label}: empty list is rejected - omit the field for \"no restriction\""
        )
        return
    if len(domains) > MAX_DOMAINS:
        result.errors.append(f"{label}: {len(domains)} domains, max {MAX_DOMAINS}")

    seen: set[str] = set()
    for index, domain in enumerate(domains):
        entry_label = f"{label}.{index}"
        if not isinstance(domain, str) or not domain:
            result.errors.append(f"{entry_label}: must be a non-empty string")
            continue
        normalized = domain.rstrip("/").lower()
        if normalized in seen:
            result.errors.append(f"{entry_label}: duplicate domain {domain!r}")
        seen.add(normalized)

        if len(domain) > MAX_DOMAIN_CHARS:
            result.errors.append(f"{entry_label}: exceeds {MAX_DOMAIN_CHARS} chars")
        if "://" in domain:
            result.errors.append(f"{entry_label}: drop the scheme - plain hostname only")
            continue
        if domain.startswith("*."):
            result.errors.append(
                f"{entry_label}: wildcards are not supported - a listed domain "
                "already covers its subdomains"
            )
            continue
        if normalized.startswith("[") or normalized.count(":") > 1:
            result.errors.append(f"{entry_label}: IP addresses are not supported")
            continue
        if ":" in normalized:
            result.errors.append(f"{entry_label}: ports are not supported")
            continue
        if "_" in normalized:
            result.errors.append(f"{entry_label}: underscores are not valid in a hostname")
            continue
        if not _ASCII_HOST_RE.match(normalized):
            result.errors.append(
                f"{entry_label}: non-ASCII domains must be Punycode (xn--)"
            )
            continue

        host = normalized.split("/", 1)[0]
        path = normalized[len(host):]
        if path and tool_name == "web_fetch":
            result.errors.append(f"{entry_label}: web_fetch domains cannot carry a path")
        if _IPV4_RE.match(host):
            result.errors.append(f"{entry_label}: IP addresses are not supported")
            continue
        if "." not in host:
            result.errors.append(
                f"{entry_label}: single-label names are not supported"
            )
            continue
        if host == "localhost" or host.endswith(_RESERVED_SUFFIXES):
            result.errors.append(f"{entry_label}: reserved/internal names are not supported")
            continue
        if host in _REGISTRY_SUFFIXES:
            result.errors.append(
                f"{entry_label}: {host!r} is a registry suffix, not a registrable domain"
            )
            continue
        if host.startswith(".") or host.endswith(".") or ".." in host or "-." in host or ".-" in host:
            result.errors.append(f"{entry_label}: malformed domain")


# ---- environment ---------------------------------------------------------

ENVIRONMENT_TYPES = frozenset({"cloud", "self_hosted"})
NETWORKING_TYPES = frozenset({"unrestricted", "limited"})


ENVIRONMENT_KEYS = frozenset(
    {"kind", "name", "description", "metadata", "config", "scope", "x-notes"}
)


def _validate_environment(manifest: dict[str, Any], result: ValidationResult) -> None:
    unknown = sorted(set(manifest) - ENVIRONMENT_KEYS)
    if unknown:
        result.errors.append(
            f"unknown top-level keys on an environment: {unknown} "
            "(`packages` and `networking` live under `config`)"
        )
    env_config = manifest.get("config")
    if not isinstance(env_config, dict):
        result.errors.append("`config` is required and must be a mapping")
        return

    env_type = env_config.get("type")
    if env_type not in ENVIRONMENT_TYPES:
        result.errors.append(
            f"`config.type` is {env_type!r}, expected 'cloud' or 'self_hosted'"
        )

    networking = env_config.get("networking")
    if networking is None:
        if env_type == "cloud":
            result.warnings.append(
                "no `config.networking` - the container's egress policy is unstated"
            )
    elif not isinstance(networking, dict):
        result.errors.append("`config.networking` must be a mapping")
    else:
        if env_type == "self_hosted":
            result.warnings.append(
                "`networking` does not apply to a self_hosted environment - "
                "you control egress on your own infrastructure"
            )
        net_type = networking.get("type")
        if net_type not in NETWORKING_TYPES:
            result.errors.append(
                f"`config.networking.type` is {net_type!r}, "
                "expected 'unrestricted' or 'limited'"
            )
        elif net_type == "unrestricted":
            result.warnings.append(
                "networking is `unrestricted` - the sandbox can reach any host. "
                "Prefer `limited` with allowed_hosts unless a task needs open egress"
            )
        else:
            hosts = networking.get("allowed_hosts")
            if hosts is not None and not isinstance(hosts, list):
                result.errors.append("`networking.allowed_hosts` must be a list")
            if env_config.get("packages") and not networking.get("allow_package_managers"):
                result.errors.append(
                    "`packages` under `limited` networking requires "
                    "`allow_package_managers: true` - listing the registry in "
                    "allowed_hosts is not enough"
                )
            declares_mcp_hosts = bool(hosts)
            if not networking.get("allow_mcp_servers") and not declares_mcp_hosts:
                result.warnings.append(
                    "`limited` networking with neither allow_mcp_servers nor "
                    "allowed_hosts: any MCP server the agent declares will be "
                    "unreachable and its tools will fail silently"
                )


# ---- deployment ----------------------------------------------------------

# A session's initial_events accepts only user.message / user.define_outcome.
# A deployment's also accepts system.message.
DEPLOYMENT_INITIAL_EVENTS = frozenset(
    {"user.message", "user.define_outcome", "system.message"}
)
MAX_INITIAL_EVENTS = 50


def _validate_deployment(manifest: dict[str, Any], result: ValidationResult) -> None:
    """Validate a scheduled-deployment manifest.

    Manifests name the agent and environment (`agent_name` / `environment_name`)
    rather than carrying raw IDs, so the file stays readable and portable across
    workspaces. `deploy` resolves them against the applied-state file.
    """
    for key in ("agent_name", "environment_name"):
        if not manifest.get(key):
            result.errors.append(f"`{key}` is required on a deployment manifest")
    for raw in ("agent", "environment_id"):
        if raw in manifest:
            result.warnings.append(
                f"`{raw}` is set directly - it will be overwritten by the ID "
                f"resolved from `{'agent_name' if raw == 'agent' else 'environment_name'}`"
            )

    events = manifest.get("initial_events")
    if not isinstance(events, list) or not events:
        result.errors.append(
            "`initial_events` must contain at least one starting event - "
            "a deployment with nothing to do never does anything"
        )
    else:
        if len(events) > MAX_INITIAL_EVENTS:
            result.errors.append(
                f"`initial_events` has {len(events)} entries, max {MAX_INITIAL_EVENTS}"
            )
        outcomes = 0
        starters = 0
        for index, event in enumerate(events):
            if not isinstance(event, dict):
                result.errors.append(f"initial_events.{index}: must be a mapping")
                continue
            event_type = event.get("type")
            if event_type not in DEPLOYMENT_INITIAL_EVENTS:
                result.errors.append(
                    f"initial_events.{index}: type {event_type!r} is not accepted "
                    f"here - expected one of {sorted(DEPLOYMENT_INITIAL_EVENTS)}"
                )
                continue
            if event_type == "user.define_outcome":
                outcomes += 1
                starters += 1
                if not event.get("rubric"):
                    result.errors.append(
                        f"initial_events.{index}: user.define_outcome requires a `rubric`"
                    )
            elif event_type == "user.message":
                starters += 1
                if not event.get("content"):
                    result.errors.append(
                        f"initial_events.{index}: user.message requires `content`"
                    )
        if outcomes > 1:
            result.errors.append("at most one `user.define_outcome` is allowed")
        if starters == 0:
            result.errors.append(
                "`initial_events` needs a user.message or a user.define_outcome - "
                "a system.message alone starts no work"
            )

    schedule = manifest.get("schedule")
    if schedule is None:
        result.errors.append("`schedule` is required")
    else:
        result.errors.extend(validate_schedule(schedule))
        result.warnings.extend(schedule_warnings(schedule))

    budget = manifest.get("budget")
    if budget is not None:
        _validate_budget(budget, result)
    else:
        result.warnings.append(
            "no `budget:` in the manifest - `deploy` will refuse unless --budget is passed"
        )

    overrides = manifest.get("agent_overrides")
    if overrides is not None:
        _validate_agent_overrides(overrides, result)

    _validate_session_resources(manifest.get("resources"), result)


# A deployment fires with no client attached; the session has to finish a turn
# on its own. These are the only override keys the API accepts.
OVERRIDE_KEYS = frozenset({"model", "system", "tools", "skills", "mcp_servers"})
RESOURCE_TYPES = frozenset({"file", "github_repository", "memory_store"})


def _validate_agent_overrides(overrides: Any, result: ValidationResult) -> None:
    if not isinstance(overrides, dict):
        result.errors.append("`agent_overrides` must be a mapping")
        return
    unknown = sorted(set(overrides) - OVERRIDE_KEYS)
    if unknown:
        result.errors.append(
            f"`agent_overrides` has unknown keys {unknown}; allowed: {sorted(OVERRIDE_KEYS)}"
        )
    if "model" in overrides:
        _validate_model(overrides["model"], result)
        model = overrides["model"]
        if isinstance(model, dict) and "effort" in model:
            result.warnings.append(
                "`agent_overrides.model.effort` is silently IGNORED by the API - "
                "effort is agent configuration; set it on the agent"
            )
    if overrides.get("model") is None and "model" in overrides:
        result.errors.append("`agent_overrides.model` cannot be null - model is never clearable")
    if "tools" in overrides and overrides["tools"] is not None:
        servers = _validate_mcp_servers(overrides.get("mcp_servers"), result) \
            if "mcp_servers" in overrides else set()
        _validate_tools(overrides["tools"], servers, result)
        if overrides.get("skills"):
            _validate_skills(overrides["skills"], overrides["tools"], result)


def _validate_session_resources(resources: Any, result: ValidationResult) -> None:
    """Resources ride on deployments (and sessions). Tokens must be references."""
    if resources is None:
        return
    if not isinstance(resources, list):
        result.errors.append("`resources` must be a list")
        return
    for index, resource in enumerate(resources):
        label = f"resources.{index}"
        if not isinstance(resource, dict):
            result.errors.append(f"{label}: must be a mapping")
            continue
        rtype = resource.get("type")
        if rtype not in RESOURCE_TYPES:
            result.errors.append(f"{label}: type {rtype!r} not in {sorted(RESOURCE_TYPES)}")
        if rtype == "github_repository":
            token = resource.get("authorization_token")
            if not token:
                result.errors.append(f"{label}: github_repository requires `authorization_token`")
            elif not (isinstance(token, str) and _ENV_REF_RE.match(token)):
                result.errors.append(
                    f"{label}: `authorization_token` must be an environment reference like "
                    "${GITHUB_TOKEN} - a literal token in a committed manifest is a leak"
                )
            if not resource.get("url"):
                result.errors.append(f"{label}: github_repository requires `url`")
        if rtype == "file":
            if not resource.get("file_id"):
                result.errors.append(f"{label}: file resource requires `file_id`")
            mount = resource.get("mount_path")
            if not (isinstance(mount, str) and mount.startswith("/")):
                result.errors.append(f"{label}: `mount_path` is required and must be absolute")


def _scan_for_secrets(node: Any, result: ValidationResult, path: str = "") -> None:
    """Walk every string in a manifest looking for credential shapes."""
    if isinstance(node, dict):
        for key, value in node.items():
            child = f"{path}.{key}" if path else str(key)
            if key in _SECRET_KEYS and isinstance(value, str) and not _ENV_REF_RE.match(value):
                result.errors.append(
                    f"{child}: looks like a credential field with a literal value - "
                    "credentials belong in a vault, never in a manifest"
                )
            _scan_for_secrets(value, result, child)
    elif isinstance(node, list):
        for index, value in enumerate(node):
            _scan_for_secrets(value, result, f"{path}.{index}")
    elif isinstance(node, str):
        for marker in _SECRET_MARKERS:
            if marker in node:
                result.errors.append(
                    f"{path or '<root>'}: contains a credential-shaped token ({marker}...) - "
                    "remove it; this file is committed"
                )
                break


# ---- schedules (deployments) --------------------------------------------

# Local hours where DST transitions make wall-clock matching lossy or doubled.
DST_RISK_HOURS = {1, 2, 3}


def validate_schedule(schedule: Any) -> list[str]:
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


def schedule_warnings(schedule: Any) -> list[str]:
    """Non-fatal risks worth surfacing before a schedule goes live."""
    warnings: list[str] = []
    if not isinstance(schedule, dict):
        return warnings
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


def _always_ask_tools(tools: Any) -> list[str]:
    """Names of built-in/MCP tools gated by always_ask after config layering."""
    gated: list[str] = []
    if not isinstance(tools, list):
        return gated
    for tool in tools:
        if not isinstance(tool, dict):
            continue
        default = (tool.get("default_config") or {}).get("permission_policy") or {}
        default_ask = default.get("type") == "always_ask"
        configs = tool.get("configs") or []
        names_seen: set[str] = set()
        for cfg in configs:
            if not isinstance(cfg, dict) or not cfg.get("name"):
                continue
            names_seen.add(cfg["name"])
            enabled = cfg.get("enabled", (tool.get("default_config") or {}).get("enabled", True))
            policy = cfg.get("permission_policy")
            ask = default_ask if policy is None else policy.get("type") == "always_ask"
            if enabled and ask:
                gated.append(cfg["name"])
        if default_ask and tool.get("type") == TOOLSET_TYPE:
            for name in sorted(BUILTIN_TOOLS - names_seen):
                if (tool.get("default_config") or {}).get("enabled", True):
                    gated.append(name)
        if default_ask and tool.get("type") == "mcp_toolset":
            gated.append(f"{tool.get('mcp_server_name')}:*")
    return gated


def cross_validate(
    manifests: list[tuple[str, dict[str, Any]]], results: dict[str, ValidationResult]
) -> None:
    """Rules that span manifests: a deployment must fire an agent that can
    finish a turn with nobody watching."""
    agents = {m.get("name"): m for _, m in manifests if m.get("kind") == "agent"}
    for path, manifest in manifests:
        if manifest.get("kind") != "deployment":
            continue
        result = results[path]
        agent = agents.get(manifest.get("agent_name"))
        if agent is None:
            result.warnings.append(
                f"agent {manifest.get('agent_name')!r} is not defined alongside this "
                "deployment - the unattended-tool check could not run"
            )
            continue
        overrides = manifest.get("agent_overrides") or {}
        effective_tools = overrides["tools"] if "tools" in overrides else agent.get("tools")
        gated = _always_ask_tools(effective_tools)
        if gated:
            result.errors.append(
                f"deployment fires with no client attached, but its effective tools gate "
                f"{gated} with always_ask - every firing would park in requires_action. "
                "Disable or always_allow them via `agent_overrides.tools` for this deployment."
            )


def _validate_budget(budget: Any, result: ValidationResult) -> None:
    if not isinstance(budget, dict):
        result.errors.append("`budget` must be a mapping")
        return
    if budget.get("type") != "limit":
        result.errors.append('`budget.type` must be "limit"')
    cost = budget.get("max_list_cost")
    if not isinstance(cost, dict):
        result.errors.append("`budget.max_list_cost` must be a mapping")
        return
    amount = cost.get("amount")
    if not isinstance(amount, str):
        result.errors.append(
            "`budget.max_list_cost.amount` must be a STRING of minor units "
            '(cents): "2500" is $25.00'
        )
    elif not amount.isdigit() or amount.startswith("0") or int(amount) <= 0:
        result.errors.append(
            f"`budget.max_list_cost.amount` is {amount!r} - it must be a positive "
            'integer string in cents with no leading zeros; decimals like "25.00" '
            "are rejected by the API"
        )
    if cost.get("currency") != "USD":
        result.errors.append("`budget.max_list_cost.currency` must be \"USD\"")


def _validate_skills(skills: Any, tools: Any, result: ValidationResult) -> None:
    if skills is None:
        return
    if not isinstance(skills, list):
        result.errors.append("`skills` must be a list")
        return
    if len(skills) > MAX_SKILLS:
        result.errors.append(f"`skills` has {len(skills)} entries, max {MAX_SKILLS}")

    for index, skill in enumerate(skills):
        if not isinstance(skill, dict):
            result.errors.append(f"skills.{index}: must be a mapping")
            continue
        if skill.get("type") not in {"anthropic", "custom"}:
            result.errors.append(
                f"skills.{index}: `type` must be \"anthropic\" or \"custom\""
            )
        if not skill.get("skill_id"):
            result.errors.append(f"skills.{index}: `skill_id` is required")

    if skills and not _read_tool_enabled(tools):
        result.errors.append(
            "`skills` are attached but the `read` tool is disabled - "
            "skills require `read` and the API rejects this combination"
        )


def _read_tool_enabled(tools: Any) -> bool:
    """Whether `read` survives the toolset's default_config / configs layering."""
    if not isinstance(tools, list):
        return False
    for tool in tools:
        if not isinstance(tool, dict) or tool.get("type") != TOOLSET_TYPE:
            continue
        default_config = tool.get("default_config") or {}
        enabled = default_config.get("enabled", True)
        for config in tool.get("configs") or []:
            if isinstance(config, dict) and config.get("name") == "read":
                enabled = config.get("enabled", enabled)
        if enabled:
            return True
    return False


# --------------------------------------------------------------------------
# Budgets
# --------------------------------------------------------------------------


def budget_from_dollars(dollars: float) -> dict[str, Any]:
    """Build the API's budget object from a dollar figure.

    `max_list_cost.amount` is minor units (cents) as an integer STRING - the API
    rejects decimal forms like "25.00" so no float rounding is ever applied.
    """
    cents = int(round(dollars * 100))
    if cents <= 0:
        raise ValueError("budget must be greater than zero")
    return {"type": "limit", "max_list_cost": {"amount": str(cents), "currency": "USD"}}


def _field(obj: Any, name: str, default: Any = None) -> Any:
    """Read a field off a dict or an SDK (pydantic) model alike."""
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def format_cost(cost: Any) -> str:
    """Render an API money object (`{amount, currency}` or SDK model) as $X.XX."""
    if cost is None:
        return "unknown"
    amount = _field(cost, "amount")
    if amount is None:
        return "unknown"
    try:
        cents = int(amount)
    except (TypeError, ValueError):
        return "unknown"
    return f"${cents / 100:,.2f} {_field(cost, 'currency', 'USD') or 'USD'}"


# --------------------------------------------------------------------------
# Applied-state file (agent/environment IDs - not secrets, safe to commit)
# --------------------------------------------------------------------------


def load_state(path: str) -> dict[str, Any]:
    if not os.path.exists(path):
        return {"agents": {}, "environments": {}, "deployments": {}}
    with open(path, encoding="utf-8") as handle:
        state = json.load(handle)
    for key in ("agents", "environments", "deployments"):
        state.setdefault(key, {})
    return state


def save_state(path: str, state: dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(state, handle, indent=2, sort_keys=True)
        handle.write("\n")
