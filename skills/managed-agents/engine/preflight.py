"""Readiness checks for Claude Managed Agents - the "is it actually enabled?" answer.

Every check is free. The optional `--live` probe is a control-plane GET
(`GET /v1/agents?limit=1`) which starts no session, provisions no container,
and consumes no tokens. Nothing here spends money.

Credential handling: this module reports whether a credential *source* is
present. It never reads, prints, logs, or transmits a secret value - not even
masked or truncated.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from typing import Any

from . import config

# The Files API `scope_id` filter (session output downloads) is untyped before
# this version of the Python SDK.
MIN_SDK_VERSION = (0, 92, 0)

CREDENTIAL_ENV_VARS = (
    "ANTHROPIC_API_KEY",
    "ANTHROPIC_AUTH_TOKEN",
    "ANTHROPIC_PROFILE",
)

REQUIRED_NAMESPACES = ("agents", "environments", "sessions")
OPTIONAL_NAMESPACES = ("vaults", "deployments", "deployment_runs", "memory_stores")

OK, WARN, FAIL = "ok", "warn", "fail"


@dataclass
class Check:
    name: str
    status: str
    detail: str
    fix: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "status": self.status, "detail": self.detail, "fix": self.fix}


@dataclass
class Report:
    checks: list[Check] = field(default_factory=list)

    def add(self, name: str, status: str, detail: str, fix: str = "") -> None:
        self.checks.append(Check(name=name, status=status, detail=detail, fix=fix))

    @property
    def failures(self) -> list[Check]:
        return [c for c in self.checks if c.status == FAIL]

    @property
    def warnings(self) -> list[Check]:
        return [c for c in self.checks if c.status == WARN]

    @property
    def ready(self) -> bool:
        return not self.failures

    def to_dict(self) -> dict[str, Any]:
        return {
            "ready": self.ready,
            "failed": len(self.failures),
            "warned": len(self.warnings),
            "checks": [c.to_dict() for c in self.checks],
        }


def _parse_version(raw: str) -> tuple[int, ...]:
    parts: list[int] = []
    for chunk in raw.split(".")[:3]:
        digits = "".join(ch for ch in chunk if ch.isdigit())
        parts.append(int(digits) if digits else 0)
    return tuple(parts)


def check_python(report: Report) -> None:
    version = sys.version_info
    label = f"{version.major}.{version.minor}.{version.micro}"
    if version >= (3, 10):
        report.add("python", OK, f"Python {label}")
    else:
        report.add(
            "python", FAIL, f"Python {label}", "The Anthropic SDK 1.x requires Python 3.10+"
        )


def check_sdk(report: Report) -> Any:
    """Import the SDK and confirm the Managed Agents namespaces exist."""
    try:
        import anthropic
    except ImportError:
        report.add(
            "anthropic-sdk",
            FAIL,
            "the `anthropic` package is not installed",
            "pip install --upgrade anthropic",
        )
        return None

    raw_version = getattr(anthropic, "__version__", "0")
    parsed = _parse_version(raw_version)
    if parsed >= MIN_SDK_VERSION:
        report.add("anthropic-sdk", OK, f"anthropic {raw_version}")
    else:
        wanted = ".".join(str(n) for n in MIN_SDK_VERSION)
        report.add(
            "anthropic-sdk",
            WARN,
            f"anthropic {raw_version} is older than {wanted}",
            f"pip install --upgrade 'anthropic>={wanted}' "
            "(older versions do not type the Files `scope_id` filter)",
        )
    return anthropic


def check_namespaces(report: Report, anthropic_module: Any) -> None:
    """Confirm client.beta.<namespace> exists without making a request."""
    if anthropic_module is None:
        report.add("sdk-namespaces", FAIL, "skipped - SDK not importable")
        return
    try:
        client = anthropic_module.Anthropic(api_key="placeholder-not-used")
    except Exception as exc:  # pragma: no cover - construction is offline
        report.add("sdk-namespaces", FAIL, f"could not construct a client: {exc}")
        return

    beta = getattr(client, "beta", None)
    if beta is None:
        report.add(
            "sdk-namespaces",
            FAIL,
            "client.beta is missing",
            "pip install --upgrade anthropic",
        )
        return

    missing = [ns for ns in REQUIRED_NAMESPACES if not hasattr(beta, ns)]
    if missing:
        report.add(
            "sdk-namespaces",
            FAIL,
            f"client.beta is missing {missing}",
            "pip install --upgrade anthropic - this SDK predates Managed Agents",
        )
        return

    absent_optional = [ns for ns in OPTIONAL_NAMESPACES if not hasattr(beta, ns)]
    if absent_optional:
        report.add(
            "sdk-namespaces",
            WARN,
            f"present: {list(REQUIRED_NAMESPACES)}; missing: {absent_optional}",
            "pip install --upgrade anthropic for vaults / scheduled deployments",
        )
    else:
        report.add("sdk-namespaces", OK, "agents, environments, sessions, vaults, deployments")


def check_credentials(report: Report, env: dict[str, str]) -> None:
    """Report which credential SOURCE resolves. Never touches a secret value."""
    direct = [name for name in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN") if env.get(name)]
    if direct:
        report.add(
            "credentials",
            OK,
            f"{', '.join(direct)} set in the environment (value not read)",
        )
        return

    # ANTHROPIC_PROFILE only *selects* a profile; it is a credential only if
    # that profile actually exists on disk, which `ant auth status` can tell us.
    profile = env.get("ANTHROPIC_PROFILE")
    if profile and not shutil.which("ant"):
        report.add(
            "credentials",
            WARN,
            f"ANTHROPIC_PROFILE={profile!r} is set but `ant` is not installed to confirm "
            "that profile exists",
            "install the ant CLI and run `ant auth status`, or export ANTHROPIC_API_KEY",
        )
        return

    if shutil.which("ant"):
        try:
            proc = subprocess.run(
                ["ant", "auth", "status"],
                capture_output=True,
                text=True,
                timeout=20,
                check=False,
            )
        except (subprocess.SubprocessError, OSError) as exc:
            report.add("credentials", WARN, f"`ant auth status` did not run: {exc}")
            return
        if proc.returncode == 0:
            report.add(
                "credentials",
                OK,
                "an `ant auth login` profile is active (SDK picks it up automatically)",
            )
        else:
            report.add(
                "credentials",
                FAIL,
                "`ant auth status` reports no active credential source",
                "run `ant auth login`, or export ANTHROPIC_API_KEY",
            )
        return

    report.add(
        "credentials",
        FAIL,
        "no ANTHROPIC_API_KEY / ANTHROPIC_AUTH_TOKEN / ant profile found",
        "run `ant auth login`, or export ANTHROPIC_API_KEY in this shell",
    )


def check_billing_note(report: Report) -> None:
    """Managed Agents bills API credits. A Claude Max seat does not cover it."""
    report.add(
        "billing",
        WARN,
        "Managed Agents bills your Anthropic API workspace (console credits), "
        "not a Claude Pro/Max subscription",
        "confirm the workspace has credit before running a session; "
        "always pass --budget so a session cannot run away",
    )


def check_manifests(report: Report, manifest_dir: str) -> None:
    paths = config.discover_manifests(manifest_dir)
    if not paths:
        report.add("manifests", WARN, f"no manifests found in {manifest_dir}")
        return
    results = config.validate_all(paths)
    bad = [r for r in results if not r.ok]
    if bad:
        detail = "; ".join(f"{r.path}: {r.errors[0]}" for r in bad[:3])
        report.add(
            "manifests",
            FAIL,
            f"{len(bad)}/{len(results)} manifests invalid - {detail}",
            "python -m engine validate",
        )
        return
    warned = sum(len(r.warnings) for r in results)
    suffix = f" ({warned} warning{'s' if warned != 1 else ''})" if warned else ""
    report.add("manifests", OK, f"{len(results)} manifests valid{suffix}")


def check_live(report: Report, anthropic_module: Any) -> None:
    """Control-plane read. Costs $0: no session, no container, no tokens."""
    if anthropic_module is None:
        report.add("live-probe", FAIL, "skipped - SDK not importable")
        return
    try:
        client = anthropic_module.Anthropic()
    except Exception as exc:
        report.add(
            "live-probe",
            FAIL,
            f"client construction failed: {type(exc).__name__}",
            "check that a credential source is configured",
        )
        return

    try:
        page = client.beta.agents.list(limit=1)
    except Exception as exc:
        name = type(exc).__name__
        status = getattr(exc, "status_code", None)
        hint = "GET /v1/agents was rejected"
        if status == 401:
            hint = "401 - the credential is not valid for this workspace"
        elif status == 403:
            hint = "403 - the key is valid but Managed Agents is not enabled for this workspace"
        elif status == 404:
            hint = "404 - endpoint not found; the beta may not be enabled for this org"
        report.add(
            "live-probe",
            FAIL,
            f"{hint} ({name})",
            "confirm the workspace is enrolled in the Managed Agents beta "
            "at platform.claude.com",
        )
        return

    count = len(getattr(page, "data", []) or [])
    report.add(
        "live-probe",
        OK,
        f"GET /v1/agents succeeded - Managed Agents is enabled "
        f"({'at least one' if count else 'no'} agent in this workspace)",
    )


def run(manifest_dir: str, env: dict[str, str], live: bool = False) -> Report:
    """Run the full readiness sweep."""
    report = Report()
    check_python(report)
    anthropic_module = check_sdk(report)
    check_namespaces(report, anthropic_module)
    check_credentials(report, env)
    check_billing_note(report)
    check_manifests(report, manifest_dir)
    if live:
        check_live(report, anthropic_module)
    return report


_GLYPH = {OK: "PASS", WARN: "WARN", FAIL: "FAIL"}


def render(report: Report) -> str:
    lines = ["", "Claude Managed Agents - readiness", "=" * 52]
    width = max((len(c.name) for c in report.checks), default=10)
    for check in report.checks:
        lines.append(f"  [{_GLYPH[check.status]}] {check.name.ljust(width)}  {check.detail}")
        if check.fix:
            lines.append(f"         {' ' * width}  -> {check.fix}")
    lines.append("=" * 52)
    if report.ready:
        lines.append(
            f"READY - {len(report.warnings)} warning(s). "
            "Nothing above spent money."
        )
    else:
        lines.append(f"NOT READY - {len(report.failures)} blocking failure(s).")
    lines.append("")
    return "\n".join(lines)
