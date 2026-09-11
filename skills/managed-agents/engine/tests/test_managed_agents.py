"""Offline tests for the Managed Agents engine.

No network, no SDK, no credentials, no spend. Run from skills/managed-agents/:

    python3 -m engine.tests.test_managed_agents

Every validator test that asserts a rejection is a negative control: it feeds
the checker something known-bad and confirms it FAILS. A validator that has
never rejected anything has never been tested.
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile

from .. import bridge, config, deploy, session

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


# --------------------------------------------------------------------------
# agent validation
# --------------------------------------------------------------------------


def test_agent_happy_path() -> None:
    result = config.validate(_agent())
    check("valid agent passes", result.ok, str(result.errors))


def test_model_required() -> None:
    manifest = _agent()
    del manifest["model"]
    result = config.validate(manifest)
    check("missing model rejected", not result.ok)
    check(
        "missing model names the field",
        any("model" in e for e in result.errors),
        str(result.errors),
    )


def test_session_fields_rejected_on_agent() -> None:
    """The single most common Managed Agents mistake: session fields on an agent."""
    for field_name, value in [
        ("environment_id", "env_123"),
        ("resources", []),
        ("vault_ids", ["vlt_1"]),
        ("budget", {"type": "limit"}),
    ]:
        result = config.validate(_agent(**{field_name: value}))
        check(
            f"session field {field_name!r} rejected on agent",
            not result.ok and any(field_name in e for e in result.errors),
            str(result.errors),
        )


def test_bad_effort_rejected() -> None:
    result = config.validate(_agent(model={"id": "claude-opus-5", "effort": "turbo"}))
    check("invalid effort rejected", not result.ok, str(result.errors))


def test_unknown_model_warns_but_passes() -> None:
    result = config.validate(_agent(model="claude-not-released-yet"))
    check("unknown model still valid", result.ok, str(result.errors))
    check("unknown model warns", bool(result.warnings))


def test_mcp_toolset_must_reference_declared_server() -> None:
    manifest = _agent(
        tools=[
            {"type": config.TOOLSET_TYPE},
            {"type": "mcp_toolset", "mcp_server_name": "ghost"},
        ]
    )
    result = config.validate(manifest)
    check("dangling mcp_toolset rejected", not result.ok, str(result.errors))

    manifest["mcp_servers"] = [
        {"type": "url", "name": "ghost", "url": "https://mcp.example.com/mcp"}
    ]
    result = config.validate(manifest)
    check("declared mcp server accepted", result.ok, str(result.errors))


def test_mcp_auth_in_manifest_rejected() -> None:
    """MCP auth belongs in a vault. A token in a committed manifest is a leak."""
    manifest = _agent(
        mcp_servers=[
            {
                "type": "url",
                "name": "linear",
                "url": "https://mcp.linear.app/mcp",
                "auth": {"token": "nope"},
            }
        ],
        tools=[{"type": config.TOOLSET_TYPE}, {"type": "mcp_toolset", "mcp_server_name": "linear"}],
    )
    result = config.validate(manifest)
    check("inline mcp auth rejected", not result.ok, str(result.errors))
    check("rejection mentions vault", any("vault" in e for e in result.errors))


def test_skills_require_read_tool() -> None:
    manifest = _agent(
        skills=[{"type": "anthropic", "skill_id": "xlsx"}],
        tools=[
            {
                "type": config.TOOLSET_TYPE,
                "default_config": {"enabled": False},
                "configs": [{"name": "bash", "enabled": True}],
            }
        ],
    )
    result = config.validate(manifest)
    check("skills without read rejected", not result.ok, str(result.errors))

    manifest["tools"][0]["configs"].append({"name": "read", "enabled": True})
    result = config.validate(manifest)
    check("skills with read accepted", result.ok, str(result.errors))


def test_permission_policy_values() -> None:
    manifest = _agent(
        tools=[
            {
                "type": config.TOOLSET_TYPE,
                "configs": [{"name": "bash", "permission_policy": {"type": "sometimes"}}],
            }
        ]
    )
    check("bad permission policy rejected", not config.validate(manifest).ok)


def test_unknown_builtin_tool_name_rejected() -> None:
    manifest = _agent(
        tools=[{"type": config.TOOLSET_TYPE, "configs": [{"name": "curl", "enabled": True}]}]
    )
    check("unknown builtin tool rejected", not config.validate(manifest).ok)


# --------------------------------------------------------------------------
# domain lists - every rule here maps to a documented 400
# --------------------------------------------------------------------------


def _web_agent(tool: str, key: str, domains) -> dict:
    return _agent(
        tools=[{"type": config.TOOLSET_TYPE, "configs": [{"name": tool, key: domains}]}]
    )


def test_domain_list_rejections() -> None:
    cases = [
        ("scheme", ["https://example.com"]),
        ("wildcard", ["*.example.com"]),
        ("port", ["example.com:443"]),
        ("ip address", ["192.168.1.1"]),
        ("single label", ["intranet"]),
        ("localhost", ["localhost"]),
        ("reserved suffix", ["box.internal"]),
        ("empty list", []),
        ("duplicate", ["example.com", "example.com"]),
    ]
    for label, domains in cases:
        result = config.validate(_web_agent("web_search", "allowed_domains", domains))
        check(f"domain rejection: {label}", not result.ok, str(result.errors))


def test_domain_list_accepts_plain_hosts() -> None:
    result = config.validate(
        _web_agent("web_search", "allowed_domains", ["example.com", "docs.example.org"])
    )
    check("plain hostnames accepted", result.ok, str(result.errors))


def test_allowed_and_blocked_mutually_exclusive() -> None:
    manifest = _agent(
        tools=[
            {
                "type": config.TOOLSET_TYPE,
                "configs": [
                    {
                        "name": "web_fetch",
                        "allowed_domains": ["a.com"],
                        "blocked_domains": ["b.com"],
                    }
                ],
            }
        ]
    )
    check("allow+block together rejected", not config.validate(manifest).ok)


def test_web_fetch_domain_cannot_carry_path() -> None:
    check(
        "web_fetch path rejected",
        not config.validate(_web_agent("web_fetch", "allowed_domains", ["example.com/docs"])).ok,
    )
    check(
        "web_search path accepted",
        config.validate(_web_agent("web_search", "allowed_domains", ["example.com/blog"])).ok,
    )


def test_web_settings_only_on_web_tools() -> None:
    check(
        "domains on bash rejected",
        not config.validate(_web_agent("bash", "allowed_domains", ["example.com"])).ok,
    )


def test_max_content_tokens_is_web_fetch_only() -> None:
    check(
        "max_content_tokens on web_search rejected",
        not config.validate(_web_agent("web_search", "max_content_tokens", 1000)).ok,
    )


def test_user_location_country_format() -> None:
    manifest = _agent(
        tools=[
            {
                "type": config.TOOLSET_TYPE,
                "configs": [
                    {
                        "name": "web_search",
                        "user_location": {"type": "approximate", "country": "usa"},
                    }
                ],
            }
        ]
    )
    check("3-letter country rejected", not config.validate(manifest).ok)


# --------------------------------------------------------------------------
# budgets
# --------------------------------------------------------------------------


def test_budget_minor_units() -> None:
    budget = config.budget_from_dollars(25)
    check("budget amount is a string", isinstance(budget["max_list_cost"]["amount"], str))
    check("budget in cents", budget["max_list_cost"]["amount"] == "2500",
          budget["max_list_cost"]["amount"])
    check("budget currency USD", budget["max_list_cost"]["currency"] == "USD")
    check("budget type limit", budget["type"] == "limit")

    cents = config.budget_from_dollars(0.5)["max_list_cost"]["amount"]
    check("fractional dollars round to cents", cents == "50", cents)

    try:
        config.budget_from_dollars(0)
        check("zero budget rejected", False)
    except ValueError:
        check("zero budget rejected", True)


def test_budget_manifest_validation() -> None:
    """Decimal amounts are the trap - the API rejects "25.00"."""
    manifest = {
        "kind": "deployment",
        "name": "d",
        "agent_name": "Atlas",
        "environment_name": "henry-cloud",
        "schedule": {"type": "cron", "expression": "0 7 * * 1-5", "timezone": "America/Chicago"},
        "initial_events": [{"type": "user.message", "content": [{"type": "text", "text": "go"}]}],
        "budget": {"type": "limit", "max_list_cost": {"amount": "25.00", "currency": "USD"}},
    }
    check("decimal budget amount rejected", not config.validate(manifest).ok)

    manifest["budget"]["max_list_cost"]["amount"] = "2500"
    check("integer-string budget accepted", config.validate(manifest).ok,
          str(config.validate(manifest).errors))


def test_format_cost() -> None:
    check("format_cost renders dollars",
          config.format_cost({"amount": "2500", "currency": "USD"}) == "$25.00 USD")
    check("format_cost survives junk", config.format_cost(None) == "unknown")


# --------------------------------------------------------------------------
# deployments
# --------------------------------------------------------------------------


def _deployment(**overrides) -> dict:
    base = {
        "kind": "deployment",
        "name": "nightly",
        "agent_name": "Atlas",
        "environment_name": "henry-cloud",
        "schedule": {"type": "cron", "expression": "10 7 * * 1-5", "timezone": "America/Chicago"},
        "initial_events": [{"type": "user.message", "content": [{"type": "text", "text": "go"}]}],
    }
    base.update(overrides)
    return base


def test_deployment_happy_path() -> None:
    result = config.validate(_deployment())
    check("valid deployment passes", result.ok, str(result.errors))


def test_deployment_needs_a_starting_event() -> None:
    check("empty initial_events rejected", not config.validate(_deployment(initial_events=[])).ok)
    check(
        "system.message alone rejected",
        not config.validate(
            _deployment(
                initial_events=[
                    {"type": "system.message", "content": [{"type": "text", "text": "ctx"}]}
                ]
            )
        ).ok,
    )


def test_deployment_rejects_tool_result_events() -> None:
    check(
        "tool result in initial_events rejected",
        not config.validate(
            _deployment(initial_events=[{"type": "user.tool_confirmation", "result": "allow"}])
        ).ok,
    )


def test_cron_field_count() -> None:
    problems = deploy.validate_schedule(
        {"type": "cron", "expression": "0 7 * *", "timezone": "UTC"}
    )
    check("4-field cron rejected", bool(problems), str(problems))
    check("5-field cron accepted",
          not deploy.validate_schedule(
              {"type": "cron", "expression": "0 7 * * 1-5", "timezone": "UTC"}
          ))


def test_cron_timezone_required() -> None:
    problems = deploy.validate_schedule({"type": "cron", "expression": "0 7 * * *"})
    check("missing timezone rejected", bool(problems))


def test_dst_window_warning() -> None:
    warnings = deploy.schedule_warnings(
        {"type": "cron", "expression": "0 2 * * *", "timezone": "America/Chicago"}
    )
    check("2am local warns about DST", any("DST" in w for w in warnings), str(warnings))
    check(
        "7am local does not warn",
        not deploy.schedule_warnings(
            {"type": "cron", "expression": "0 7 * * *", "timezone": "America/Chicago"}
        ),
    )
    check(
        "every-minute cron warns",
        any("every minute" in w for w in deploy.schedule_warnings(
            {"type": "cron", "expression": "* * * * *", "timezone": "UTC"}
        )),
    )


def test_build_body_swaps_names_for_ids() -> None:
    body = deploy.build_body(_deployment(), "agent_1", "env_1", budget_dollars=5)
    check("agent id set", body["agent"] == "agent_1")
    check("environment id set", body["environment_id"] == "env_1")
    check("name keys stripped", "agent_name" not in body and "environment_name" not in body)
    check("kind stripped", "kind" not in body)
    check("budget attached", body["budget"]["max_list_cost"]["amount"] == "500")


# --------------------------------------------------------------------------
# session helpers
# --------------------------------------------------------------------------


def test_console_url() -> None:
    url = session.console_url("sesn_abc", "default")
    check("console url shape", url.endswith("/workspaces/default/sessions/sesn_abc"), url)


def test_session_refuses_zero_budget() -> None:
    class FakeClient:
        class beta:  # noqa: N801
            class sessions:  # noqa: N801
                @staticmethod
                def create(**kwargs):
                    raise AssertionError("must not be called")

    try:
        session.create_session(FakeClient(), "a", "e", "prompt", budget_dollars=0)
        check("uncapped session refused", False)
    except ValueError:
        check("uncapped session refused", True)


def test_session_create_body() -> None:
    captured = {}

    class FakeSessions:
        @staticmethod
        def create(**kwargs):
            captured.update(kwargs)
            return type("S", (), {"id": "sesn_1", "status": "idle"})()

    class FakeClient:
        beta = type("B", (), {"sessions": FakeSessions})()

    session.create_session(FakeClient(), "agent_1", "env_1", "hi", budget_dollars=5, title="T")
    check("agent passed as pointer", captured["agent"] == "agent_1")
    check("environment passed", captured["environment_id"] == "env_1")
    check("budget attached", captured["budget"]["max_list_cost"]["amount"] == "500")
    check("no model on session", "model" not in captured)
    check("no system on session", "system" not in captured)
    check("no tools on session", "tools" not in captured)
    check("initial_events not used", "initial_events" not in captured)


def test_idle_gate_constants() -> None:
    check("requires_action is not terminal",
          "requires_action" not in session.TERMINAL_STOP_REASONS)
    for reason in ("end_turn", "retries_exhausted", "budget_reached"):
        check(f"{reason} is terminal", reason in session.TERMINAL_STOP_REASONS)


# --------------------------------------------------------------------------
# skills bridge
# --------------------------------------------------------------------------


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
        check("keeps top-level skill", "alpha" in names, str(names))
        check("collision disambiguated", "group-alpha" in names, str(names))
        check("collision recorded", bool(plan.collisions))
        check("no skill without SKILL.md", not any("y" == n for n in names), str(names))
    finally:
        shutil.rmtree(tmp)


def test_bridge_build_and_check_roundtrip() -> None:
    tmp = tempfile.mkdtemp()
    try:
        _fixture_repo(tmp)
        built = bridge.build(tmp, mode="symlink")
        check("bridge created entries", built["planned"] == 3, str(built))

        state = bridge.check(tmp)
        check("bridge reports in sync", state["in_sync"], str(state))

        # Every link must actually resolve to a real SKILL.md.
        for name, _ in bridge.plan(tmp).entries:
            target = os.path.join(tmp, bridge.BRIDGE_DIR, name, "SKILL.md")
            check(f"link {name} resolves", os.path.isfile(target), target)

        # Negative control: break it and confirm check() FAILS.
        os.unlink(os.path.join(tmp, bridge.BRIDGE_DIR, "alpha"))
        broken = bridge.check(tmp)
        check("check detects a missing link", not broken["in_sync"], str(broken))
        check("missing link named", "alpha" in broken["missing"], str(broken))

        # Negative control: a stray entry must be reported, then pruned.
        bridge.build(tmp, mode="symlink")
        os.makedirs(os.path.join(tmp, bridge.BRIDGE_DIR, "stray"), exist_ok=True)
        stray = bridge.check(tmp)
        check("stray entry detected", "stray" in stray["extra"], str(stray))
        bridge.build(tmp, mode="symlink", prune=True)
        check("stray entry pruned", bridge.check(tmp)["in_sync"])
    finally:
        shutil.rmtree(tmp)


def test_bridge_relative_links_survive_relocation() -> None:
    """Links must be relative, or they break the moment the repo is cloned."""
    tmp = tempfile.mkdtemp()
    try:
        repo = os.path.join(tmp, "repo")
        os.makedirs(repo)
        _fixture_repo(repo)
        bridge.build(repo, mode="symlink")

        link = os.path.join(repo, bridge.BRIDGE_DIR, "alpha")
        check("link is a symlink", os.path.islink(link))
        check("link target is relative", not os.path.isabs(os.readlink(link)), os.readlink(link))

        moved = os.path.join(tmp, "moved")
        shutil.move(repo, moved)
        check(
            "link still resolves after move",
            os.path.isfile(os.path.join(moved, bridge.BRIDGE_DIR, "alpha", "SKILL.md")),
        )
    finally:
        shutil.rmtree(tmp)


def test_bridge_copy_mode() -> None:
    tmp = tempfile.mkdtemp()
    try:
        _fixture_repo(tmp)
        bridge.build(tmp, mode="copy")
        target = os.path.join(tmp, bridge.BRIDGE_DIR, "alpha", "SKILL.md")
        check("copy mode writes a real file", os.path.isfile(target))
        check("copy mode leaves no symlink",
              not os.path.islink(os.path.join(tmp, bridge.BRIDGE_DIR, "alpha")))
        check("copy mode in sync", bridge.check(tmp)["in_sync"])
    finally:
        shutil.rmtree(tmp)


def test_bridge_never_touches_source() -> None:
    tmp = tempfile.mkdtemp()
    try:
        _fixture_repo(tmp)
        before = sorted(os.listdir(os.path.join(tmp, "skills")))
        bridge.build(tmp, mode="symlink", prune=True)
        after = sorted(os.listdir(os.path.join(tmp, "skills")))
        check("source directory untouched", before == after, f"{before} != {after}")
    finally:
        shutil.rmtree(tmp)


# --------------------------------------------------------------------------
# shipped manifests
# --------------------------------------------------------------------------


def test_shipped_manifests_validate() -> None:
    here = os.path.dirname(os.path.abspath(__file__))
    manifest_dir = os.path.join(here, "..", "..", "agents")
    paths = config.discover_manifests(os.path.abspath(manifest_dir))
    check("manifests found", bool(paths), manifest_dir)
    for result in config.validate_all(paths):
        check(f"shipped manifest valid: {os.path.basename(result.path)}",
              result.ok, str(result.errors))


def test_no_secrets_in_shipped_manifests() -> None:
    """A credential in a committed manifest is a leak, not a convenience."""
    here = os.path.dirname(os.path.abspath(__file__))
    manifest_dir = os.path.abspath(os.path.join(here, "..", "..", "agents"))
    markers = ("sk-ant-", "ghp_", "github_pat_", "access_token:", "secret_value:")
    for path in config.discover_manifests(manifest_dir):
        with open(path, encoding="utf-8") as handle:
            body = handle.read()
        for marker in markers:
            check(
                f"no {marker!r} in {os.path.basename(path)}",
                marker not in body,
                path,
            )


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
