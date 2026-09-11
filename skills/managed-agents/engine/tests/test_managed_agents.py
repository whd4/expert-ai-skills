"""Offline tests for the Managed Agents engine.

No network, no SDK, no credentials, no spend. Run from skills/managed-agents/:

    python3 -m engine.tests.test_managed_agents

Every validator test that asserts a rejection is a negative control: it feeds
the checker something known-bad and confirms it FAILS. A validator that has
never rejected anything has never been tested. The run-loop tests drive
`run_session` with a fake client so the money-spending path is exercised
without a session ever existing.
"""

from __future__ import annotations

import contextlib
import io
import os
import shutil
import sys
import tempfile
from types import SimpleNamespace

from .. import bridge, cli, config, control, deploy, session

PASSED = 0
FAILED: list[str] = []


def check(label: str, condition: bool, detail: str = "") -> None:
    global PASSED
    if condition:
        PASSED += 1
    else:
        FAILED.append(f"{label}{': ' + detail if detail else ''}")


def _agent(**overrides) -> dict:
    base = {
        "kind": "agent",
        "name": "Tester",
        "model": {"id": "claude-opus-5", "effort": "high"},
        "system": "You are a test agent.",
        "tools": [{"type": config.TOOLSET_TYPE, "default_config": {"enabled": True}}],
    }
    base.update(overrides)
    return base


def _deployment(**overrides) -> dict:
    base = {
        "kind": "deployment",
        "name": "nightly",
        "agent_name": "Tester",
        "environment_name": "env",
        "schedule": {"type": "cron", "expression": "10 7 * * 1-5", "timezone": "America/Chicago"},
        "initial_events": [{"type": "user.message", "content": [{"type": "text", "text": "go"}]}],
        "budget": {"type": "limit", "max_list_cost": {"amount": "500", "currency": "USD"}},
    }
    base.update(overrides)
    return base


# ==========================================================================
# agent validation
# ==========================================================================


def test_agent_happy_path() -> None:
    result = config.validate(_agent())
    check("valid agent passes", result.ok, str(result.errors))


def test_model_required() -> None:
    manifest = _agent()
    del manifest["model"]
    result = config.validate(manifest)
    check("missing model rejected", not result.ok and any("model" in e for e in result.errors))


def test_session_fields_rejected_on_agent() -> None:
    for field_name, value in [
        ("environment_id", "env_123"),
        ("resources", []),
        ("vault_ids", ["vlt_1"]),
        ("budget", {"type": "limit"}),
    ]:
        result = config.validate(_agent(**{field_name: value}))
        check(f"session field {field_name!r} rejected on agent",
              not result.ok and any(field_name in e for e in result.errors), str(result.errors))


def test_bad_effort_rejected() -> None:
    check("invalid effort rejected",
          not config.validate(_agent(model={"id": "claude-opus-5", "effort": "turbo"})).ok)


def test_unknown_model_warns_but_passes() -> None:
    result = config.validate(_agent(model="claude-not-released-yet"))
    check("unknown model still valid", result.ok, str(result.errors))
    check("unknown model warns", bool(result.warnings))


def test_mcp_toolset_must_reference_declared_server() -> None:
    manifest = _agent(tools=[{"type": config.TOOLSET_TYPE},
                             {"type": "mcp_toolset", "mcp_server_name": "ghost"}])
    check("dangling mcp_toolset rejected", not config.validate(manifest).ok)
    manifest["mcp_servers"] = [{"type": "url", "name": "ghost", "url": "https://mcp.example.com/mcp"}]
    result = config.validate(manifest)
    check("declared mcp server accepted", result.ok, str(result.errors))


def test_mcp_auth_in_manifest_rejected() -> None:
    manifest = _agent(
        mcp_servers=[{"type": "url", "name": "linear", "url": "https://mcp.linear.app/mcp",
                      "auth": {"token": "nope"}}],
        tools=[{"type": config.TOOLSET_TYPE}, {"type": "mcp_toolset", "mcp_server_name": "linear"}],
    )
    result = config.validate(manifest)
    check("inline mcp auth rejected", not result.ok)
    check("rejection mentions vault", any("vault" in e for e in result.errors))


def test_secret_shaped_strings_rejected_anywhere() -> None:
    """A credential-SHAPED token in ANY string field fails - the file is committed.
    Prose that merely names a format is not a credential (second-pass N-E)."""
    result = config.validate(_agent(system="Use ghp_abcdefghijklmnopqrstuvwxyz0123456789 to push."))
    check("ghp_ token in system rejected", not result.ok, str(result.errors))
    result = config.validate(_agent(metadata={"note": "sk-ant-api03-ABCDEFGHIJKLMNOPQRSTUVWX"}))
    check("sk-ant- token in metadata rejected", not result.ok)
    result = config.validate(_agent(system="Never paste an AWS key AKIAABCDEFGHIJKLMNOP here."))
    check("real AKIA-shaped key rejected", not result.ok)
    for prose in ("Never paste an AWS key (they start with AKIA) into a prompt.",
                  "Keys look like sk-ant-... - refuse them.",
                  "access_token is stored in the vault, ghp_ tokens are never typed here."):
        result = config.validate(_agent(system=prose))
        check(f"prose mention is fine: {prose[:30]}...", result.ok, str(result.errors))
    result = config.validate(_agent(metadata={"api_key": "literal-value"}))
    check("literal value under a secret key rejected", not result.ok)


def test_agent_unknown_top_level_keys_rejected() -> None:
    """Second-pass N-F: keys the API would TypeError on must fail validation."""
    result = config.validate(_agent(initial_events=[{"type": "user.message"}], schedule={}))
    check("deployment keys on an agent rejected", not result.ok and any("unknown" in e for e in result.errors),
          str(result.errors))
    check("x-notes is allowed", config.validate(_agent(**{"x-notes": "fine"})).ok)


def test_skills_require_read_tool() -> None:
    manifest = _agent(
        skills=[{"type": "anthropic", "skill_id": "xlsx"}],
        tools=[{"type": config.TOOLSET_TYPE, "default_config": {"enabled": False},
                "configs": [{"name": "bash", "enabled": True}]}],
    )
    check("skills without read rejected", not config.validate(manifest).ok)
    manifest["tools"][0]["configs"].append({"name": "read", "enabled": True})
    result = config.validate(manifest)
    check("skills with read accepted", result.ok, str(result.errors))


def test_permission_policy_values() -> None:
    manifest = _agent(tools=[{"type": config.TOOLSET_TYPE,
                              "configs": [{"name": "bash", "permission_policy": {"type": "sometimes"}}]}])
    check("bad permission policy rejected", not config.validate(manifest).ok)


def test_unknown_builtin_tool_name_rejected() -> None:
    manifest = _agent(tools=[{"type": config.TOOLSET_TYPE, "configs": [{"name": "curl", "enabled": True}]}])
    check("unknown builtin tool rejected", not config.validate(manifest).ok)


def test_metadata_values_must_be_strings() -> None:
    result = config.validate(_agent(metadata={"enabled": True}))
    check("bool metadata value rejected", not result.ok, str(result.errors))
    check("string metadata value ok", config.validate(_agent(metadata={"enabled": "true"})).ok)


# ==========================================================================
# domain lists - every rule here maps to a documented 400
# ==========================================================================


def _web_agent(tool: str, key: str, domains) -> dict:
    return _agent(tools=[{"type": config.TOOLSET_TYPE, "configs": [{"name": tool, key: domains}]}])


def test_domain_list_rejections() -> None:
    cases = [
        ("scheme", ["https://example.com"]),
        ("wildcard", ["*.example.com"]),
        ("port", ["example.com:443"]),
        ("ipv4", ["192.168.1.1"]),
        ("ipv6", ["[::1]"]),
        ("single label", ["intranet"]),
        ("localhost", ["localhost"]),
        ("reserved suffix", ["box.internal"]),
        ("registry suffix co.uk", ["co.uk"]),
        ("registry suffix com.au", ["com.au"]),
        ("underscore", ["bad_host.example.com"]),
        ("empty list", []),
        ("duplicate", ["example.com", "example.com"]),
    ]
    for label, domains in cases:
        result = config.validate(_web_agent("web_search", "allowed_domains", domains))
        check(f"domain rejection: {label}", not result.ok, str(result.errors))


def test_domain_list_accepts_plain_hosts() -> None:
    result = config.validate(_web_agent("web_search", "allowed_domains",
                                        ["example.com", "docs.example.org", "bbc.co.uk"]))
    check("plain hostnames accepted (incl. name under co.uk)", result.ok, str(result.errors))


def test_allowed_and_blocked_mutually_exclusive() -> None:
    manifest = _agent(tools=[{"type": config.TOOLSET_TYPE, "configs": [
        {"name": "web_fetch", "allowed_domains": ["a.com"], "blocked_domains": ["b.com"]}]}])
    check("allow+block together rejected", not config.validate(manifest).ok)


def test_web_fetch_domain_cannot_carry_path() -> None:
    check("web_fetch path rejected",
          not config.validate(_web_agent("web_fetch", "allowed_domains", ["example.com/docs"])).ok)
    check("web_search path accepted",
          config.validate(_web_agent("web_search", "allowed_domains", ["example.com/blog"])).ok)


def test_web_settings_only_on_web_tools() -> None:
    check("domains on bash rejected",
          not config.validate(_web_agent("bash", "allowed_domains", ["example.com"])).ok)
    check("max_content_tokens on web_search rejected",
          not config.validate(_web_agent("web_search", "max_content_tokens", 1000)).ok)


def test_user_location_country_format() -> None:
    manifest = _agent(tools=[{"type": config.TOOLSET_TYPE, "configs": [
        {"name": "web_search", "user_location": {"type": "approximate", "country": "usa"}}]}])
    check("3-letter country rejected", not config.validate(manifest).ok)


# ==========================================================================
# environments
# ==========================================================================


def _env(**overrides) -> dict:
    base = {"kind": "environment", "name": "env",
            "config": {"type": "cloud", "networking": {"type": "limited", "allow_mcp_servers": True}}}
    base.update(overrides)
    return base


def test_environment_packages_rule_looks_under_config() -> None:
    manifest = _env()
    manifest["config"]["packages"] = {"pip": ["numpy"]}
    result = config.validate(manifest)
    check("config.packages under limited without allow_package_managers rejected",
          not result.ok and any("allow_package_managers" in e for e in result.errors), str(result.errors))
    manifest["config"]["networking"]["allow_package_managers"] = True
    check("config.packages with allow_package_managers accepted", config.validate(manifest).ok)


def test_environment_unknown_top_level_key_rejected() -> None:
    result = config.validate(_env(packages={"pip": ["x"]}))
    check("packages at manifest root rejected", not result.ok, str(result.errors))


def test_environment_unrestricted_warns() -> None:
    result = config.validate(_env(config={"type": "cloud", "networking": {"type": "unrestricted"}}))
    check("unrestricted valid", result.ok)
    check("unrestricted warns", bool(result.warnings))


# ==========================================================================
# budgets
# ==========================================================================


def test_budget_minor_units() -> None:
    budget = config.budget_from_dollars(25)
    check("budget amount is a string", isinstance(budget["max_list_cost"]["amount"], str))
    check("budget in cents", budget["max_list_cost"]["amount"] == "2500")
    check("fractional dollars round to cents", config.budget_from_dollars(0.5)["max_list_cost"]["amount"] == "50")
    for bad in (0, -3):
        try:
            config.budget_from_dollars(bad)
            check(f"budget {bad} rejected", False)
        except ValueError:
            check(f"budget {bad} rejected", True)


def test_budget_manifest_validation() -> None:
    manifest = _deployment(budget={"type": "limit", "max_list_cost": {"amount": "25.00", "currency": "USD"}})
    check("decimal budget amount rejected", not config.validate(manifest).ok)
    manifest["budget"]["max_list_cost"]["amount"] = "0500"
    check("leading-zero budget rejected", not config.validate(manifest).ok)
    manifest["budget"]["max_list_cost"]["amount"] = "2500"
    check("integer-string budget accepted", config.validate(manifest).ok)


def test_format_cost_handles_dicts_and_sdk_models() -> None:
    check("dict cost", config.format_cost({"amount": "2500", "currency": "USD"}) == "$25.00 USD")
    model = SimpleNamespace(amount="1234", currency="USD")  # shape of the SDK's money model
    check("object cost", config.format_cost(model) == "$12.34 USD", config.format_cost(model))
    check("None is unknown", config.format_cost(None) == "unknown")
    check("junk is unknown", config.format_cost({"amount": "abc"}) == "unknown")


# ==========================================================================
# deployments - validation
# ==========================================================================


def test_deployment_happy_path() -> None:
    result = config.validate(_deployment())
    check("valid deployment passes", result.ok, str(result.errors))


def test_deployment_needs_a_starting_event() -> None:
    check("empty initial_events rejected", not config.validate(_deployment(initial_events=[])).ok)
    check("system.message alone rejected", not config.validate(_deployment(
        initial_events=[{"type": "system.message", "content": [{"type": "text", "text": "ctx"}]}])).ok)
    check("tool result in initial_events rejected", not config.validate(_deployment(
        initial_events=[{"type": "user.tool_confirmation", "result": "allow"}])).ok)


def test_validate_checks_the_schedule_itself() -> None:
    """The gap the review found: `validate` claimed to check cron but did not."""
    result = config.validate(_deployment(schedule={"type": "cron", "expression": "0 7 * *", "timezone": "UTC"}))
    check("4-field cron rejected by validate()", not result.ok, str(result.errors))
    result = config.validate(_deployment(schedule={"type": "cron", "expression": "0 7 * * *"}))
    check("missing timezone rejected by validate()", not result.ok)
    result = config.validate(_deployment(schedule={"type": "cron", "expression": "0 2 * * *",
                                                   "timezone": "America/Chicago"}))
    check("2am local is valid but warns about DST", result.ok and any("DST" in w for w in result.warnings),
          str(result.warnings))
    result = config.validate(_deployment(schedule={"type": "cron", "expression": "* * * * *", "timezone": "UTC"}))
    check("every-minute cron warns", any("every minute" in w for w in result.warnings))


def test_deployment_without_budget_warns() -> None:
    manifest = _deployment()
    del manifest["budget"]
    result = config.validate(manifest)
    check("no-budget deployment valid but warned", result.ok and any("budget" in w for w in result.warnings))


def test_deployment_resource_token_must_be_a_reference() -> None:
    literal = _deployment(resources=[{"type": "github_repository", "url": "https://github.com/o/r",
                                      "authorization_token": "github_pat_11ABC_literal"}])
    result = config.validate(literal)
    check("literal PAT in deployment rejected", not result.ok, str(result.errors))
    ref = _deployment(resources=[{"type": "github_repository", "url": "https://github.com/o/r",
                                  "authorization_token": "${GITHUB_TOKEN}"}])
    result = config.validate(ref)
    check("${GITHUB_TOKEN} reference accepted", result.ok, str(result.errors))
    check("file resource needs absolute mount_path", not config.validate(_deployment(
        resources=[{"type": "file", "file_id": "file_1", "mount_path": "data.csv"}])).ok)


def test_agent_overrides_validation() -> None:
    check("unknown override key rejected",
          not config.validate(_deployment(agent_overrides={"budget": {}})).ok)
    check("model: null override rejected",
          not config.validate(_deployment(agent_overrides={"model": None})).ok)
    result = config.validate(_deployment(agent_overrides={"model": {"id": "claude-opus-5", "effort": "low"}}))
    check("effort in override warns (ignored by API)", result.ok and any("IGNORED" in w for w in result.warnings),
          str(result.warnings))
    result = config.validate(_deployment(agent_overrides={"tools": [
        {"type": config.TOOLSET_TYPE, "configs": [{"name": "bash", "enabled": False}]}]}))
    check("tools override validated and accepted", result.ok, str(result.errors))


def test_cross_validate_unattended_agent() -> None:
    """A cron deployment must not fire an agent that will wait on a human."""
    gated_agent = _agent(name="Gated", tools=[{"type": config.TOOLSET_TYPE, "configs": [
        {"name": "bash", "permission_policy": {"type": "always_ask"}}]}])
    dep = _deployment(name="d", agent_name="Gated")
    manifests = [("gated.yaml", gated_agent), ("d.yaml", dep)]
    results = {p: config.validate(m, p) for p, m in manifests}
    config.cross_validate(manifests, results)
    check("deployment on always_ask agent rejected",
          not results["d.yaml"].ok and any("requires_action" in e for e in results["d.yaml"].errors),
          str(results["d.yaml"].errors))

    dep_fixed = _deployment(name="d", agent_name="Gated", agent_overrides={"tools": [
        {"type": config.TOOLSET_TYPE, "configs": [{"name": "bash", "enabled": False}]}]})
    manifests = [("gated.yaml", gated_agent), ("d.yaml", dep_fixed)]
    results = {p: config.validate(m, p) for p, m in manifests}
    config.cross_validate(manifests, results)
    check("override disabling bash makes it valid", results["d.yaml"].ok, str(results["d.yaml"].errors))

    dep_unknown = _deployment(name="d", agent_name="Nobody")
    manifests = [("d.yaml", dep_unknown)]
    results = {p: config.validate(m, p) for p, m in manifests}
    config.cross_validate(manifests, results)
    check("unknown agent only warns", results["d.yaml"].ok and bool(results["d.yaml"].warnings))


def test_custom_tools_count_as_unattended_blockers() -> None:
    """Second-pass N-C: a custom tool idles the session for a client that a
    deployment does not have."""
    custom_agent = _agent(name="Custom", tools=[
        {"type": config.TOOLSET_TYPE},
        {"type": "custom", "name": "run_tests", "description": "d", "input_schema": {"type": "object"}}])
    dep = _deployment(name="d", agent_name="Custom")
    manifests = [("c.yaml", custom_agent), ("d.yaml", dep)]
    results = {p: config.validate(m, p) for p, m in manifests}
    config.cross_validate(manifests, results)
    check("deployment on custom-tool agent rejected",
          not results["d.yaml"].ok and any("custom:run_tests" in e for e in results["d.yaml"].errors),
          str(results["d.yaml"].errors))


def test_always_ask_detection_layers() -> None:
    tools = [{"type": config.TOOLSET_TYPE,
              "default_config": {"enabled": True, "permission_policy": {"type": "always_ask"}},
              "configs": [{"name": "read", "permission_policy": {"type": "always_allow"}}]}]
    gated = config._always_ask_tools(tools)
    check("default always_ask gates unlisted tools", "bash" in gated and "web_search" in gated, str(gated))
    check("per-tool always_allow lifts the gate", "read" not in gated, str(gated))
    disabled = [{"type": config.TOOLSET_TYPE, "configs": [
        {"name": "bash", "enabled": False, "permission_policy": {"type": "always_ask"}}]}]
    check("a disabled tool is not gated", not config._always_ask_tools(disabled))


# ==========================================================================
# deployments - body building + apply
# ==========================================================================


def test_build_body_budget_precedence() -> None:
    body = deploy.build_body(_deployment(), "agent_1", "env_1")
    check("manifest budget kept when no flag", body["budget"]["max_list_cost"]["amount"] == "500")
    body = deploy.build_body(_deployment(), "agent_1", "env_1", budget_dollars=12)
    check("flag overrides manifest budget", body["budget"]["max_list_cost"]["amount"] == "1200")
    manifest = _deployment()
    del manifest["budget"]
    try:
        deploy.build_body(manifest, "agent_1", "env_1")
        check("no budget anywhere -> refused", False)
    except ValueError as exc:
        check("no budget anywhere -> refused", "budget" in str(exc))
    for bad in (0, -1):
        try:
            deploy.build_body(manifest, "agent_1", "env_1", budget_dollars=bad)
            check(f"--budget {bad} refused", False)
        except ValueError:
            check(f"--budget {bad} refused", True)


def test_build_body_agent_reference_forms() -> None:
    body = deploy.build_body(_deployment(), "agent_1", "env_1")
    check("bare id when no version", body["agent"] == "agent_1")
    body = deploy.build_body(_deployment(), "agent_1", "env_1", agent_version=3)
    check("pinned when version known", body["agent"] == {"type": "agent", "id": "agent_1", "version": 3})
    tools = [{"type": config.TOOLSET_TYPE, "configs": [{"name": "bash", "enabled": False}]}]
    body = deploy.build_body(_deployment(agent_overrides={"tools": tools}), "agent_1", "env_1", agent_version=3)
    check("overrides -> agent_with_overrides",
          body["agent"]["type"] == "agent_with_overrides" and body["agent"]["id"] == "agent_1"
          and body["agent"]["version"] == 3 and body["agent"]["tools"] == tools, str(body["agent"]))
    check("local keys stripped", not {"agent_name", "environment_name", "agent_overrides", "kind"} & set(body))


def test_secret_refs_expand_from_environment() -> None:
    os.environ["MA_TEST_TOKEN"] = "value-from-env"
    try:
        out = deploy.expand_secret_refs([{"type": "github_repository", "url": "u",
                                          "authorization_token": "${MA_TEST_TOKEN}"}])
        check("${VAR} expanded", out[0]["authorization_token"] == "value-from-env")
        try:
            deploy.expand_secret_refs([{"type": "github_repository", "authorization_token": "${MA_UNSET_VAR_X}"}])
            check("unset ${VAR} refused", False)
        except ValueError as exc:
            check("unset ${VAR} refused", "MA_UNSET_VAR_X" in str(exc))
    finally:
        del os.environ["MA_TEST_TOKEN"]
    redacted = deploy.redact({"resources": [{"authorization_token": "value-from-env"}], "agent": "a"})
    check("redact masks token", redacted["resources"][0]["authorization_token"] == deploy.REDACTED)

    # Second-pass N-J: a dry run must not need the secret present.
    manifest = _deployment(resources=[{"type": "github_repository", "url": "u",
                                       "authorization_token": "${MA_UNSET_VAR_Y}"}])
    body = deploy.build_body(manifest, "a", "e", expand_secrets=False)
    check("dry-run body keeps the reference", body["resources"][0]["authorization_token"] == "${MA_UNSET_VAR_Y}")


def test_find_by_name_required_raises_on_missing_capability() -> None:
    """Second-pass N-I: a duplicate-preventing lookup must not degrade to 'not found'."""
    client = SimpleNamespace(beta=SimpleNamespace())
    try:
        control.find_by_name(client, "deployments", "x", required=True)
        check("required lookup raises without list()", False)
    except RuntimeError:
        check("required lookup raises without list()", True)
    check("optional lookup still returns None", control.find_by_name(client, "deployments", "x") is None)


class _NotFoundError(Exception):
    status_code = 404


def _deploy_client(update_exc=None, retrieve_exc=None, listed=()):
    calls = {"create": 0, "update": 0}

    class Deployments:
        @staticmethod
        def retrieve(deployment_id):
            if retrieve_exc:
                raise retrieve_exc
            return SimpleNamespace(id=deployment_id, name="nightly")

        @staticmethod
        def list(limit=100):
            return list(listed)

        @staticmethod
        def update(deployment_id, **body):
            calls["update"] += 1
            if update_exc:
                raise update_exc
            return SimpleNamespace(id=deployment_id, status="active", schedule=None)

        @staticmethod
        def create(**body):
            calls["create"] += 1
            return SimpleNamespace(id="depl_new", status="active", schedule=None)

    client = SimpleNamespace(beta=SimpleNamespace(deployments=Deployments))
    return client, calls


def test_apply_deployment_never_creates_on_update_failure() -> None:
    """The review's blocker 3: a 500 on update must NOT fall through to create."""
    client, calls = _deploy_client(update_exc=RuntimeError("500 from api"))
    state = {"deployments": {"nightly": {"id": "depl_old"}}}
    try:
        deploy.apply_deployment(client, _deployment(), "agent_1", "env_1", state)
        check("update failure re-raised", False)
    except RuntimeError:
        check("update failure re-raised", True)
    check("no create on update failure", calls["create"] == 0 and calls["update"] == 1, str(calls))
    check("state not clobbered", state["deployments"]["nightly"]["id"] == "depl_old")


def test_apply_deployment_404_falls_back_to_name_lookup() -> None:
    _NotFoundError.__name__ = "NotFoundError"
    existing = SimpleNamespace(id="depl_by_name", name="nightly")
    client, calls = _deploy_client(retrieve_exc=_NotFoundError(), listed=[existing])
    state = {"deployments": {"nightly": {"id": "depl_stale"}}}
    out = deploy.apply_deployment(client, _deployment(), "agent_1", "env_1", state)
    check("404 -> found by name -> updated", out["action"] == "updated" and out["id"] == "depl_by_name", str(out))
    check("no duplicate created", calls["create"] == 0)

    client, calls = _deploy_client(retrieve_exc=_NotFoundError(), listed=[])
    out = deploy.apply_deployment(client, _deployment(), "agent_1", "env_1", {"deployments": {}})
    check("nothing anywhere -> created once", out["action"] == "created" and calls["create"] == 1)


# ==========================================================================
# control plane
# ==========================================================================


class _Pager:
    """Mimics an SDK page: iterating yields ALL pages; .data is only the first."""

    def __init__(self, pages):
        self.pages = pages
        self.data = pages[0]

    def __iter__(self):
        for page in self.pages:
            yield from page


def test_iter_all_walks_every_page() -> None:
    pager = _Pager([[SimpleNamespace(name="a")], [SimpleNamespace(name="b")]])
    names = [x.name for x in control.iter_all(pager)]
    check("iter_all crosses pages", names == ["a", "b"], str(names))
    check("iter_all passes lists through", control.iter_all([1, 2]) == [1, 2])
    data_only = SimpleNamespace(data=[SimpleNamespace(name="z")])
    check("iter_all falls back to .data", [x.name for x in control.iter_all(data_only)] == ["z"])


def test_find_by_name_sees_second_page() -> None:
    pager = _Pager([[SimpleNamespace(id="1", name="a")], [SimpleNamespace(id="2", name="b")]])
    client = SimpleNamespace(beta=SimpleNamespace(agents=SimpleNamespace(list=lambda limit=100: pager)))
    found = control.find_by_name(client, "agents", "b")
    check("found on page 2", found is not None and found.id == "2")
    check("missing namespace -> None", control.find_by_name(client, "deployments", "x") is None)


def test_apply_agent_is_declarative() -> None:
    captured = {}

    class Agents:
        @staticmethod
        def retrieve(agent_id):
            return SimpleNamespace(id=agent_id, name="Tester", version=1,
                                   metadata={"stale": "gone", "keep": "old"})

        @staticmethod
        def update(agent_id, **body):
            captured.update(body)
            return SimpleNamespace(id=agent_id, version=2)

        @staticmethod
        def list(limit=100):
            return []

    client = SimpleNamespace(beta=SimpleNamespace(agents=Agents))
    manifest = _agent(metadata={"keep": "yes", "changed": "new"})
    del manifest["system"]
    state = {"agents": {"Tester": {"id": "agent_1", "version": 1}}, "environments": {}, "deployments": {}}
    out = control.apply_agent(client, manifest, state)
    check("update path taken", out["action"] == "updated" and out["version"] == 2)
    check("absent system sent as explicit clear", "system" in captured and captured["system"] is None)
    check("absent multiagent sent as explicit clear", "multiagent" in captured and captured["multiagent"] is None)
    check("absent skills sent as []", captured.get("skills") == [])
    check("absent mcp_servers sent as []", captured.get("mcp_servers") == [])
    check("present tools sent through", captured["tools"] == manifest["tools"])
    check("name never sent on update", "name" not in captured)
    # metadata merges on update: dropped live keys are nulled, kept/changed sent.
    check("dropped metadata key nulled, others sent",
          captured["metadata"] == {"stale": None, "keep": "yes", "changed": "new"}, str(captured["metadata"]))


def test_apply_environment_is_declarative() -> None:
    captured = {}

    class Environments:
        @staticmethod
        def retrieve(environment_id):
            return SimpleNamespace(id=environment_id, name="env", metadata={"old": "x"}, description="d")

        @staticmethod
        def update(environment_id, **body):
            captured.update(body)
            return SimpleNamespace(id=environment_id)

        @staticmethod
        def list(limit=100):
            return []

    client = SimpleNamespace(beta=SimpleNamespace(environments=Environments))
    state = {"agents": {}, "environments": {"env": {"id": "env_1"}}, "deployments": {}}
    control.apply_environment(client, _env(), state)
    check("env description cleared when absent", captured.get("description", "missing") is None)
    check("env dropped metadata key nulled", captured.get("metadata") == {"old": None}, str(captured.get("metadata")))
    check("env config sent", captured["config"]["type"] == "cloud")


# ==========================================================================
# session runner - the money path, driven by a fake client
# ==========================================================================


class _FakeStream:
    def __init__(self, events, raise_after=None):
        self.events, self.raise_after = events, raise_after

    def __enter__(self):
        return self._iter()

    def __exit__(self, *exc):
        return False

    def _iter(self):
        for index, event in enumerate(self.events):
            if self.raise_after is not None and index == self.raise_after:
                raise ConnectionError("simulated drop")
            yield event


class _FakeEvents:
    def __init__(self, history=(), live=(), list_exc=None):
        self.history = list(history)
        self.live = [list(x) for x in live] if live and isinstance(live[0], list) else [list(live)]
        self.list_exc = list_exc
        self.sent: list[dict] = []
        self.stream_calls = 0

    def stream(self, session_id):
        self.stream_calls += 1
        spec = self.live[min(self.stream_calls - 1, len(self.live) - 1)]
        if spec and isinstance(spec[0], tuple):  # ("raise_after", n, events)
            _, n, events = spec[0]
            return _FakeStream(events, raise_after=n)
        return _FakeStream(spec)

    def send(self, session_id, events):
        if getattr(self, "send_failures", 0) > 0:
            self.send_failures -= 1
            raise ConnectionError("simulated send failure")
        self.sent.extend(events)

    def list(self, session_id, **kwargs):
        self.list_kwargs = kwargs
        if self.list_exc:
            raise self.list_exc
        return list(self.history)


def _client(events):
    return SimpleNamespace(beta=SimpleNamespace(sessions=SimpleNamespace(events=events)))


def _ev(type_, id_=None, **fields):
    data = {"type": type_, "id": id_}
    data.update(fields)
    return data


def _idle(reason, ids=None, id_="sevt_idle"):
    stop = {"type": reason}
    if ids is not None:
        stop["event_ids"] = ids
    return _ev("session.status_idle", id_, stop_reason=stop)


def _run(events, **kw):
    out = io.StringIO()
    outcome = session.run_session(_client(events), "sesn_1", prompt=kw.pop("prompt", None),
                                  stream_out=out, **kw)
    return outcome, out.getvalue()


def test_run_history_pending_custom_tool_is_answered() -> None:
    """Review blocker 1: a pending ask found only in history must be answered."""
    events = _FakeEvents(
        history=[_ev("agent.custom_tool_use", "sevt_1", name="run_tests", input={"p": "x"}),
                 _idle("requires_action", ["sevt_1"], "sevt_2")],
        live=[_idle("end_turn", id_="sevt_3")],
    )
    outcome, _ = _run(events, custom_tool_handler=lambda n, i: f"ran {n}")
    results = [e for e in events.sent if e["type"] == "user.custom_tool_result"]
    check("custom tool result sent from history", len(results) == 1, str(events.sent))
    check("result targets the right event id", results and results[0]["custom_tool_use_id"] == "sevt_1")
    check("handler output used", results and results[0]["content"][0]["text"] == "ran run_tests")
    check("stops on end_turn", outcome.stop_reason == "end_turn" and not outcome.errors, str(outcome.errors))
    check("answered counted", outcome.answered == 1)


def test_run_history_terminated_stops_immediately() -> None:
    events = _FakeEvents(history=[_ev("session.status_terminated", "sevt_t")], live=[])
    outcome, _ = _run(events)
    check("terminated from history", outcome.terminated and not outcome.errors, str(outcome.errors))
    check("no wasted reconnects", outcome.reconnects == 0 and events.stream_calls == 1)


def test_run_mcp_tool_ask_is_confirmed() -> None:
    """Review bug 4: agent.mcp_tool_use with always_ask was never confirmed."""
    events = _FakeEvents(live=[
        _ev("agent.mcp_tool_use", "sevt_9", name="linear.create_issue", evaluated_permission="ask"),
        _idle("requires_action", ["sevt_9"], "sevt_10"),
        _idle("end_turn", id_="sevt_11"),
    ])
    outcome, _ = _run(events, approve=session.APPROVE_DENY)
    confirmations = [e for e in events.sent if e["type"] == "user.tool_confirmation"]
    check("mcp ask confirmed", len(confirmations) == 1, str(events.sent))
    check("tool_use_id is the event id", confirmations and confirmations[0]["tool_use_id"] == "sevt_9")
    check("deny carries a message", confirmations and confirmations[0]["result"] == "deny"
          and confirmations[0].get("deny_message"))
    check("denied counted", outcome.denied == 1 and outcome.stop_reason == "end_turn")


def test_run_allow_all_echoes_thread_id() -> None:
    events = _FakeEvents(live=[
        _ev("agent.tool_use", "sevt_5", name="bash", evaluated_permission="ask", session_thread_id="thr_1"),
        _idle("requires_action", ["sevt_5"], "sevt_6"),
        _idle("end_turn", id_="sevt_7"),
    ])
    outcome, printed = _run(events, approve=session.APPROVE_ALLOW)
    conf = [e for e in events.sent if e["type"] == "user.tool_confirmation"]
    check("allowed", conf and conf[0]["result"] == "allow" and "deny_message" not in conf[0])
    check("session_thread_id echoed", conf and conf[0].get("session_thread_id") == "thr_1", str(conf))
    check("auto-allow is visible in the log", "AUTO-ALLOWED" in printed)
    check("non-ask tool_use is not confirmed", outcome.answered == 1)


def test_run_answers_each_pending_event_once() -> None:
    """Same event in history AND live stream -> exactly one answer."""
    ask = _ev("agent.custom_tool_use", "sevt_1", name="t", input={})
    events = _FakeEvents(history=[ask, _idle("requires_action", ["sevt_1"], "sevt_2")],
                         live=[ask, _idle("requires_action", ["sevt_1"], "sevt_2"), _idle("end_turn", id_="sevt_3")])
    outcome, _ = _run(events)
    check("one answer despite duplicate delivery", sum(1 for e in events.sent if e["type"] == "user.custom_tool_result") == 1)
    check("tool counted once", outcome.tool_calls == 1)


def test_run_unknown_pending_id_is_reported_not_fatal() -> None:
    events = _FakeEvents(live=[_idle("requires_action", ["sevt_ghost"], "sevt_1"), _idle("end_turn", id_="sevt_2")])
    outcome, _ = _run(events)
    check("unknown pending id recorded", any("sevt_ghost" in e for e in outcome.errors), str(outcome.errors))
    check("loop still reaches end_turn", outcome.stop_reason == "end_turn")


def test_run_reconnects_after_stream_drop() -> None:
    first = [("raise_after", 1, [_ev("agent.message", "sevt_m", content=[{"type": "text", "text": "hi"}]),
                                _idle("end_turn", id_="sevt_e")])]
    second = [_idle("end_turn", id_="sevt_e")]
    events = _FakeEvents(history=[_ev("agent.message", "sevt_m", content=[{"type": "text", "text": "hi"}])],
                         live=[first, second])
    outcome, printed = _run(events)
    check("reconnected once", outcome.reconnects == 1 and events.stream_calls == 2, f"{outcome.reconnects} {events.stream_calls}")
    check("finished on second connection", outcome.stop_reason == "end_turn" and not outcome.errors, str(outcome.errors))
    check("text not duplicated across reconnect", "".join(outcome.text) == "hi", repr("".join(outcome.text)))
    check("reconnect logged", "reconnecting" in printed)


def test_run_history_failure_is_surfaced() -> None:
    events = _FakeEvents(live=[_idle("end_turn", id_="sevt_1")], list_exc=RuntimeError("boom"))
    outcome, printed = _run(events)
    check("history failure recorded", any("history read failed" in e for e in outcome.errors))
    check("live stream still processed", outcome.stop_reason == "end_turn")


def test_run_prompt_sent_once_after_stream_open() -> None:
    events = _FakeEvents(live=[_idle("end_turn", id_="sevt_1")])
    _run(events, prompt="do the thing")
    messages = [e for e in events.sent if e["type"] == "user.message"]
    check("prompt sent exactly once", len(messages) == 1 and messages[0]["content"][0]["text"] == "do the thing")


def test_run_budget_reached_stops_and_reports_usage() -> None:
    events = _FakeEvents(live=[
        _ev("session.usage", "sevt_u", usage={"list_cost": SimpleNamespace(amount="499", currency="USD")}),
        _idle("budget_reached", id_="sevt_b"),
    ])
    outcome, printed = _run(events)
    check("budget_reached stops", outcome.stop_reason == "budget_reached" and not outcome.errors)
    check("usage rendered from SDK-shaped object", "$4.99 USD" in printed, printed)


def test_run_unknown_stop_reason_is_terminal_with_note() -> None:
    events = _FakeEvents(live=[_idle("something_new", id_="sevt_1")])
    outcome, _ = _run(events)
    check("unknown reason stops", outcome.stop_reason == "something_new")
    check("unknown reason noted", any("unrecognised" in e for e in outcome.errors))


def test_run_session_error_event_extracts_message() -> None:
    events = _FakeEvents(live=[_ev("session.error", "sevt_e", error=SimpleNamespace(type="mcp_auth", message="bad token")),
                               _idle("end_turn", id_="sevt_1")])
    outcome, printed = _run(events)
    check("error message extracted", "bad token" in outcome.errors and "[error] bad token" in printed, str(outcome.errors))


def _echo(text, id_, processed):
    return _ev("user.message", id_, content=[{"type": "text", "text": text}],
               processed_at="2026-09-11T00:00:00Z" if processed else None)


def test_run_reuse_sends_prompt_and_returns_only_the_new_turn() -> None:
    """Second-pass N-B: an old end_turn in history must not end the NEW turn."""
    events = _FakeEvents(
        history=[_ev("agent.message", "sevt_old", content=[{"type": "text", "text": "OLD"}]),
                 _idle("end_turn", id_="sevt_old_idle")],
        live=[_echo("new task", "sevt_q", False), _echo("new task", "sevt_q", True),
              _ev("agent.message", "sevt_new", content=[{"type": "text", "text": "NEW"}]),
              _idle("end_turn", id_="sevt_new_idle")],
    )
    outcome, _ = _run(events, prompt="new task")
    check("prompt was sent", any(e["type"] == "user.message" for e in events.sent), str(events.sent))
    check("returned text is the new turn only", "".join(outcome.text) == "NEW", repr("".join(outcome.text)))
    check("stopped on the new turn's end", outcome.stop_reason == "end_turn" and not outcome.errors, str(outcome.errors))


def test_run_reuse_ignores_matching_old_prompt_echo() -> None:
    """The same prompt text sent last turn must not count as this turn's echo."""
    events = _FakeEvents(
        history=[_echo("again", "sevt_prev_q", True),
                 _ev("agent.message", "sevt_old", content=[{"type": "text", "text": "OLD"}]),
                 _idle("end_turn", id_="sevt_old_idle")],
        live=[_echo("again", "sevt_q2", True),
              _ev("agent.message", "sevt_new", content=[{"type": "text", "text": "NEW"}]),
              _idle("end_turn", id_="sevt_new_idle")],
    )
    outcome, _ = _run(events, prompt="again")
    check("old echo did not unlock the old idle", "".join(outcome.text) == "NEW", repr("".join(outcome.text)))


def test_run_observe_mode_returns_immediately_on_finished_session() -> None:
    events = _FakeEvents(history=[_idle("end_turn", id_="sevt_done")], live=[])
    outcome, _ = _run(events)
    check("no prompt -> old terminal honoured", outcome.stop_reason == "end_turn" and not outcome.errors)
    check("nothing sent", events.sent == [])


def test_run_history_order_pinned_and_late_ids_not_reported() -> None:
    """Second-pass N-D: a requires_action idle listing an id that appears LATER
    in the page must not raise a spurious 'not in history' error."""
    events = _FakeEvents(
        history=[_idle("requires_action", ["sevt_c1"], "sevt_i1"),
                 _ev("agent.custom_tool_use", "sevt_c1", name="t", input={})],
        live=[_idle("end_turn", id_="sevt_e")],
    )
    outcome, _ = _run(events)
    check("history requested oldest-first", events.list_kwargs.get("order") == "asc", str(events.list_kwargs))
    check("late-arriving pending answered once",
          sum(1 for e in events.sent if e["type"] == "user.custom_tool_result") == 1, str(events.sent))
    check("no spurious error", not outcome.errors, str(outcome.errors))


def test_run_send_failure_reconnects_without_double_counting() -> None:
    """Second-pass N-J: a deny whose send() raises is retried after reconnect
    and counted once."""
    ask = _ev("agent.tool_use", "sevt_a", name="bash", evaluated_permission="ask")
    events = _FakeEvents(history=[], live=[[ask, _idle("requires_action", ["sevt_a"], "sevt_i")],
                                           [_idle("end_turn", id_="sevt_e")]])
    events.send_failures = 1
    events.history = [ask, _idle("requires_action", ["sevt_a"], "sevt_i")]
    outcome, _ = _run(events, approve=session.APPROVE_DENY)
    confirmations = [e for e in events.sent if e["type"] == "user.tool_confirmation"]
    check("confirmation eventually sent once", len(confirmations) == 1, str(events.sent))
    check("denied counted once", outcome.denied == 1, str(outcome.denied))
    check("reconnected", outcome.reconnects == 1)


def test_create_session_refuses_uncapped_and_pins_version() -> None:
    captured = {}
    sessions = SimpleNamespace(create=lambda **kw: captured.update(kw) or SimpleNamespace(id="sesn_1", status="idle"))
    client = SimpleNamespace(beta=SimpleNamespace(sessions=sessions))
    for bad in (0, -1, None):
        try:
            session.create_session(client, "a", "e", budget_dollars=bad)
            check(f"uncapped session refused ({bad})", False)
        except (ValueError, TypeError):
            check(f"uncapped session refused ({bad})", True)
    session.create_session(client, "agent_1", "env_1", budget_dollars=5, title="T", agent_version=4)
    check("agent pinned to version", captured["agent"] == {"type": "agent", "id": "agent_1", "version": 4})
    check("budget attached", captured["budget"]["max_list_cost"]["amount"] == "500")
    check("no agent config on the session", not {"model", "system", "tools", "initial_events"} & set(captured))
    session.create_session(client, "agent_1", "env_1", budget_dollars=5)
    check("bare id when version unknown", captured["agent"] == "agent_1")


def test_console_url() -> None:
    check("console url shape", session.console_url("sesn_abc", "ws_1").endswith("/workspaces/ws_1/sessions/sesn_abc"))


# ==========================================================================
# CLI wiring
# ==========================================================================


def test_cli_rejects_non_positive_budgets() -> None:
    parser = cli.build_parser()
    for argv in (["deploy", "x.yaml", "--budget", "0"], ["run", "A", "p", "--budget", "-2"]):
        try:
            with contextlib.redirect_stderr(io.StringIO()):  # argparse prints usage; expected
                parser.parse_args(argv)
            check(f"{argv[0]} --budget {argv[-1]} rejected", False)
        except SystemExit:
            check(f"{argv[0]} --budget {argv[-1]} rejected", True)
    args = parser.parse_args(["deploy", "x.yaml"])
    check("deploy --budget defaults to None (manifest wins)", args.budget is None)
    args = parser.parse_args(["validate", "--json"])
    check("--json accepted after the subcommand", args.json)


def test_cli_message_unwraps_keyerror() -> None:
    check("KeyError message unwrapped", cli._message(KeyError("no such agent")) == "no such agent")


def _write_yaml(path: str, data: dict) -> None:
    import yaml
    with open(path, "w", encoding="utf-8") as fh:
        yaml.safe_dump(data, fh)


def test_cli_deploy_guard_cannot_be_bypassed_by_file_location() -> None:
    """Second-pass N-A: the unattended guard must run wherever the manifest lives."""
    gated_agent = _agent(name="Gated", tools=[{"type": config.TOOLSET_TYPE, "configs": [
        {"name": "bash", "permission_policy": {"type": "always_ask"}}]}])
    agents_dir = tempfile.mkdtemp()
    elsewhere = tempfile.mkdtemp()
    try:
        _write_yaml(os.path.join(agents_dir, "gated.yaml"), gated_agent)
        dep_path = os.path.join(elsewhere, "d.yaml")
        _write_yaml(dep_path, _deployment(name="d", agent_name="Gated"))
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            code = cli.main(["deploy", dep_path, "--dry-run", "--manifests", agents_dir,
                             "--state", os.path.join(elsewhere, "s.json")])
        check("guard fires for a manifest outside the agents dir", code == 1 and "requires_action" in err.getvalue(),
              f"code={code} err={err.getvalue()[:200]}")

        # And when the agent cannot be found at all, deploy refuses (validate only warns).
        empty = tempfile.mkdtemp()
        err = io.StringIO()
        with contextlib.redirect_stderr(err), contextlib.redirect_stdout(io.StringIO()):
            code = cli.main(["deploy", dep_path, "--dry-run", "--manifests", empty,
                             "--state", os.path.join(elsewhere, "s.json")])
        check("unknown agent is fatal for deploy", code == 1 and "cannot verify" in err.getvalue(),
              f"code={code} err={err.getvalue()[:200]}")
        shutil.rmtree(empty)
    finally:
        shutil.rmtree(agents_dir)
        shutil.rmtree(elsewhere)


def test_cli_apply_empty_dir_fails() -> None:
    tmp = tempfile.mkdtemp()
    try:
        with contextlib.redirect_stderr(io.StringIO()):  # "No manifests found" is the point
            code = cli.main(["apply", "--dry-run", "--manifests", tmp, "--state", os.path.join(tmp, "s.json")])
        check("apply on empty manifest dir exits 1", code == 1)
        check("state file not written", not os.path.exists(os.path.join(tmp, "s.json")))
    finally:
        shutil.rmtree(tmp)


# ==========================================================================
# skills bridge
# ==========================================================================


def _fixture_repo(tmp: str) -> str:
    for rel in ("skills/alpha", "skills/group/beta", "skills/group/alpha", "skills/deep/x/y"):
        os.makedirs(os.path.join(tmp, rel), exist_ok=True)
        if not rel.endswith("x/y"):
            with open(os.path.join(tmp, rel, "SKILL.md"), "w", encoding="utf-8") as fh:
                fh.write(f"---\nname: {os.path.basename(rel)}\n---\n")
    return tmp


def test_bridge_plan_flattens_and_resolves_collisions() -> None:
    tmp = tempfile.mkdtemp()
    try:
        _fixture_repo(tmp)
        plan = bridge.plan(tmp)
        names = {name for name, _ in plan.entries}
        check("flattens nested skill", "beta" in names, str(names))
        check("keeps top-level skill", "alpha" in names)
        check("collision disambiguated", "group-alpha" in names, str(names))
        check("no skill without SKILL.md", "y" not in names)
    finally:
        shutil.rmtree(tmp)


def test_bridge_allowlist_filters_and_reports_unmatched() -> None:
    tmp = tempfile.mkdtemp()
    try:
        _fixture_repo(tmp)
        # Leaf-name form matches EVERY skill with that leaf (alpha and group/alpha).
        plan = bridge.plan(tmp, allowlist=["alpha"])
        names = sorted(name for name, _ in plan.entries)
        check("leaf name matches all skills with that leaf", names == ["alpha", "group-alpha"], str(names))
        # Path form is exact, so it is how you pick one of them.
        plan = bridge.plan(tmp, allowlist=["skills/alpha", "skills/group/beta", "does-not-exist"])
        names = sorted(name for name, _ in plan.entries)
        check("allowlist by path is exact", names == ["alpha", "beta"], str(names))
        check("unmatched reported", plan.unmatched == ["does-not-exist"], str(plan.unmatched))
        listing = os.path.join(tmp, "list.txt")
        with open(listing, "w") as fh:
            fh.write("# comment\n\nalpha   # trailing\nskills/group/beta/\n")
        check("read_allowlist parses", bridge.read_allowlist(listing) == ["alpha", "skills/group/beta"])
        check("missing allowlist is None", bridge.read_allowlist(os.path.join(tmp, "nope")) is None)
    finally:
        shutil.rmtree(tmp)


def test_bridge_copy_mode_detects_stale_copies() -> None:
    tmp = tempfile.mkdtemp()
    try:
        _fixture_repo(tmp)
        built = bridge.build(tmp)  # default mode
        check("default mode is copy", built["mode"] == "copy" and not os.path.islink(os.path.join(tmp, bridge.BRIDGE_DIR, "alpha")))
        check("copy in sync", bridge.check(tmp)["in_sync"])
        again = bridge.build(tmp)
        check("unchanged copies are left alone", sorted(again["left"]) == ["alpha", "beta", "group-alpha"], str(again))
        with open(os.path.join(tmp, "skills", "alpha", "SKILL.md"), "a") as fh:
            fh.write("\nchanged\n")
        state = bridge.check(tmp)
        check("edited source -> stale reported", "alpha" in state["stale"] and not state["in_sync"], str(state))
        result = bridge.build(tmp)
        check("rebuild clears stale", bridge.check(tmp)["in_sync"])
        check("the outdated copy was quarantined, not deleted", len(result["quarantined"]) == 1
              and os.path.isfile(os.path.join(tmp, result["quarantined"][0], "SKILL.md")), str(result))
    finally:
        shutil.rmtree(tmp)


def test_bridge_local_edit_in_wanted_copy_is_quarantined() -> None:
    """Second-pass partial-6: a rebuild must never destroy a locally edited copy."""
    tmp = tempfile.mkdtemp()
    try:
        _fixture_repo(tmp)
        bridge.build(tmp)
        local = os.path.join(tmp, bridge.BRIDGE_DIR, "alpha", "LOCAL_EDIT.md")
        with open(local, "w") as fh:
            fh.write("precious\n")
        dry = bridge.build(tmp, dry_run=True)
        check("dry-run announces the quarantine", "alpha" in dry["would_quarantine"], str(dry))
        result = bridge.build(tmp)
        moved = [q for q in result["quarantined"] if os.path.isfile(os.path.join(tmp, q, "LOCAL_EDIT.md"))]
        check("local edit survives in quarantine", len(moved) == 1, str(result["quarantined"]))
        check("fresh copy is clean", not os.path.exists(local) and bridge.check(tmp)["in_sync"])
    finally:
        shutil.rmtree(tmp)


def test_bridge_refuses_escaping_symlinks_and_never_loops() -> None:
    """Second-pass N-G: no external content copied in, no infinite walk."""
    tmp = tempfile.mkdtemp()
    outside = tempfile.mkdtemp()
    try:
        _fixture_repo(tmp)
        with open(os.path.join(outside, "secret.txt"), "w") as fh:
            fh.write("external\n")
        os.symlink(outside, os.path.join(tmp, "skills", "alpha", "external"))
        try:
            bridge.build(tmp)
            check("escaping symlink refused", False)
        except RuntimeError as exc:
            check("escaping symlink refused", "outside the repository" in str(exc))
        check("nothing copied", not os.path.exists(os.path.join(tmp, bridge.BRIDGE_DIR, "alpha")))
        os.unlink(os.path.join(tmp, "skills", "alpha", "external"))

        # A self-referential link must not hang check()/digest.
        os.symlink(".", os.path.join(tmp, "skills", "beta_loop"))
        os.symlink("..", os.path.join(tmp, "skills", "group", "beta", "up"))
        bridge.build(tmp)
        state = bridge.check(tmp)
        check("check() terminates with internal symlinks present", isinstance(state["in_sync"], bool))
    finally:
        shutil.rmtree(tmp)
        shutil.rmtree(outside)


def test_bridge_prune_quarantines_never_deletes() -> None:
    tmp = tempfile.mkdtemp()
    try:
        _fixture_repo(tmp)
        bridge.build(tmp, mode="symlink")
        root = os.path.join(tmp, bridge.BRIDGE_DIR)
        os.symlink("../../skills/alpha", os.path.join(root, "stray-link"))
        os.makedirs(os.path.join(root, "handwritten"))
        with open(os.path.join(root, "handwritten", "SKILL.md"), "w") as fh:
            fh.write("precious\n")

        dry = bridge.build(tmp, mode="symlink", dry_run=True)
        check("dry-run names what it would unlink", dry["would_unlink"] == ["stray-link"], str(dry))
        check("dry-run names what it would quarantine", dry["would_quarantine"] == ["handwritten"], str(dry))
        check("dry-run touched nothing", os.path.isdir(os.path.join(root, "handwritten")))

        result = bridge.build(tmp, mode="symlink")
        check("stray symlink unlinked", result["unlinked"] == ["stray-link"] and not os.path.lexists(os.path.join(root, "stray-link")))
        check("real dir quarantined, not deleted", len(result["quarantined"]) == 1
              and os.path.isfile(os.path.join(tmp, result["quarantined"][0], "SKILL.md")), str(result["quarantined"]))
        check("quarantine lives under .claude/skills-quarantine/<date>",
              result["quarantined"][0].startswith(bridge.QUARANTINE_DIR))

        os.makedirs(os.path.join(root, "keep-me"))
        bridge.build(tmp, mode="symlink", prune=False)
        check("--no-prune leaves strays alone", os.path.isdir(os.path.join(root, "keep-me")))
    finally:
        shutil.rmtree(tmp)


def test_bridge_relative_links_survive_relocation() -> None:
    tmp = tempfile.mkdtemp()
    try:
        repo = os.path.join(tmp, "repo")
        os.makedirs(repo)
        _fixture_repo(repo)
        bridge.build(repo, mode="symlink")
        link = os.path.join(repo, bridge.BRIDGE_DIR, "alpha")
        check("link target is relative", os.path.islink(link) and not os.path.isabs(os.readlink(link)))
        moved = os.path.join(tmp, "moved")
        shutil.move(repo, moved)
        check("link still resolves after move", os.path.isfile(os.path.join(moved, bridge.BRIDGE_DIR, "alpha", "SKILL.md")))
    finally:
        shutil.rmtree(tmp)


def test_bridge_refuses_to_operate_outside_repo() -> None:
    """Negative control: .claude/skills pointing outside the repo must be refused."""
    tmp = tempfile.mkdtemp()
    outside = tempfile.mkdtemp()
    try:
        _fixture_repo(tmp)
        os.makedirs(os.path.join(tmp, ".claude"))
        os.symlink(outside, os.path.join(tmp, ".claude", "skills"))
        try:
            bridge.build(tmp)
            check("outside-repo bridge root refused", False)
        except RuntimeError:
            check("outside-repo bridge root refused", True)
        check("outside dir untouched", os.listdir(outside) == [])
    finally:
        shutil.rmtree(tmp)
        shutil.rmtree(outside)


def test_bridge_never_touches_source() -> None:
    tmp = tempfile.mkdtemp()
    try:
        _fixture_repo(tmp)
        before = sorted(os.listdir(os.path.join(tmp, "skills")))
        bridge.build(tmp)
        bridge.build(tmp, mode="symlink")
        after = sorted(os.listdir(os.path.join(tmp, "skills")))
        check("source directory untouched", before == after)
    finally:
        shutil.rmtree(tmp)


# ==========================================================================
# shipped manifests + allowlist
# ==========================================================================


def _shipped_dir() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.abspath(os.path.join(here, "..", "..", "agents"))


def test_shipped_manifests_validate_including_cross_checks() -> None:
    paths = config.discover_manifests(_shipped_dir())
    check("manifests found", bool(paths))
    for result in config.validate_all(paths):
        check(f"shipped manifest valid: {os.path.basename(result.path)}", result.ok, str(result.errors))


def test_shipped_deployment_can_run_unattended() -> None:
    paths = config.discover_manifests(_shipped_dir())
    manifests = [(p, config.load_manifest(p)) for p in paths]
    deployments = [m for _, m in manifests if m.get("kind") == "deployment"]
    agents = {m["name"]: m for _, m in manifests if m.get("kind") == "agent"}
    for dep in deployments:
        overrides = dep.get("agent_overrides") or {}
        tools = overrides["tools"] if "tools" in overrides else agents[dep["agent_name"]].get("tools")
        check(f"{dep['name']}: no always_ask tool in effect", not config._always_ask_tools(tools))
        check(f"{dep['name']}: carries a budget", bool(dep.get("budget")))


def test_no_secrets_or_pipeline_ids_in_shipped_manifests() -> None:
    markers = ("sk-ant-", "ghp_", "github_pat_", "access_token:", "secret_value:", "TXS5")
    for path in config.discover_manifests(_shipped_dir()):
        with open(path, encoding="utf-8") as handle:
            body = handle.read()
        for marker in markers:
            check(f"no {marker!r} in {os.path.basename(path)}", marker not in body)


def test_shipped_allowlist_matches_real_skills() -> None:
    here = os.path.dirname(os.path.abspath(__file__))
    skill_root = os.path.abspath(os.path.join(here, "..", ".."))
    repo_root = os.path.abspath(os.path.join(skill_root, "..", ".."))
    names = bridge.read_allowlist(os.path.join(skill_root, "bridge.allowlist"))
    check("allowlist present", bool(names))
    plan = bridge.plan(repo_root, allowlist=names)
    check("every allowlisted name matches a skill", plan.unmatched == [], str(plan.unmatched))
    bridged = {n for n, _ in plan.entries}
    for banned in ("metasploit-framework", "sqlmap-database-pentesting", "linux-privilege-escalation",
                   "active-directory-attacks", "red-team-tools"):
        check(f"offensive skill not bridged by default: {banned}", banned not in bridged)
    check("managed-agents is not duplicated into the bridge", "managed-agents" not in bridged)
    for heavy in ("docx-official", "pptx-official", "xlsx-official", "pdf-official"):
        check(f"hosted document skill not copied: {heavy}", heavy not in bridged)


def main() -> int:
    tests = [value for name, value in sorted(globals().items()) if name.startswith("test_")]
    for test in tests:
        try:
            test()
        except Exception as exc:  # a crashing test is a failing test
            FAILED.append(f"{test.__name__} raised {type(exc).__name__}: {exc}")

    print(f"\n{PASSED} checks passed, {len(FAILED)} failed, across {len(tests)} tests.")
    for failure in FAILED:
        print(f"  FAIL  {failure}")
    print()
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
