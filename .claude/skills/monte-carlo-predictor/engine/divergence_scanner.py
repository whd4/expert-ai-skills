"""Divergence Scanner — compare project's declared intent vs observable reality.

Scans a project directory and flags gaps between what the project *claims* to be
(from README/package.json/test declarations) and what it actually *is*
(file contents, commit velocity, actual dependencies, test-to-code ratios).

Runs without network access. No LLM calls. Pure static analysis.

CLI:
    python -m engine.divergence_scanner /path/to/project
    python -m engine.divergence_scanner /path/to/project --format json

Public API:
    scan(path: str) -> dict with severity-ranked divergences
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any


SEVERITY_LABELS = {
    (8, 10): "critical",
    (5, 8):  "high",
    (3, 5):  "medium",
    (1, 3):  "low",
    (0, 1):  "negligible",
}


def _severity_label(score: float) -> str:
    for (lo, hi), label in SEVERITY_LABELS.items():
        if lo <= score < hi:
            return label
    return "critical" if score >= 10 else "negligible"


# ── Check helpers ────────────────────────────────────────────────────

def _git_stats(path: Path) -> dict:
    try:
        out = subprocess.run(
            ["git", "-C", str(path), "log", "--oneline", "--since=90 days ago"],
            capture_output=True, text=True, timeout=15,
        )
        if out.returncode != 0:
            return {"is_git": False}
        commits_90d = len([l for l in out.stdout.splitlines() if l.strip()])
        out_all = subprocess.run(
            ["git", "-C", str(path), "log", "--oneline"],
            capture_output=True, text=True, timeout=15,
        )
        total = len([l for l in out_all.stdout.splitlines() if l.strip()])
        out_last = subprocess.run(
            ["git", "-C", str(path), "log", "-1", "--format=%cr"],
            capture_output=True, text=True, timeout=15,
        )
        last_ago = out_last.stdout.strip() if out_last.returncode == 0 else "unknown"
        return {
            "is_git": True,
            "commits_last_90d": commits_90d,
            "total_commits": total,
            "last_commit_ago": last_ago,
        }
    except Exception:
        return {"is_git": False}


def _glob_files(path: Path, pattern: str, exclude: list[str] | None = None) -> list[Path]:
    exclude = exclude or ["node_modules", ".git", "venv", ".venv", "__pycache__", "dist", "build", ".next", "target"]
    files = []
    for root, dirs, fnames in os.walk(path):
        dirs[:] = [d for d in dirs if d not in exclude and not d.startswith(".")]
        for fname in fnames:
            full = Path(root) / fname
            if full.match(pattern):
                files.append(full)
    return files


def _count_lines(files: list[Path]) -> int:
    total = 0
    for f in files:
        try:
            with open(f, "rb") as fp:
                total += sum(1 for _ in fp)
        except (OSError, IOError):
            continue
    return total


def _grep_count(files: list[Path], pattern: str) -> int:
    rx = re.compile(pattern)
    total = 0
    for f in files:
        try:
            with open(f, "r", encoding="utf-8", errors="ignore") as fp:
                for line in fp:
                    if rx.search(line):
                        total += 1
        except (OSError, IOError):
            continue
    return total


def _read_json(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _read_text_head(path: Path, limit: int = 50000) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="ignore")[:limit]
    except Exception:
        return ""


# ── Divergence checks ────────────────────────────────────────────────

def _check_readme_claims_vs_tests(root: Path) -> list[dict]:
    """If README claims features/tests but there are no tests, flag it."""
    findings = []
    readme = None
    for name in ["README.md", "Readme.md", "readme.md", "README.rst"]:
        if (root / name).exists():
            readme = root / name
            break
    if not readme:
        return []
    text = _read_text_head(readme).lower()

    # Claim: "tested", "well-tested", "100% test coverage", etc.
    claims_tested = bool(re.search(r"\b(tested|test coverage|unit tests?|tdd|ci/cd)\b", text))
    if claims_tested:
        test_files = (
            _glob_files(root, "*.test.*")
            + _glob_files(root, "*.spec.*")
            + _glob_files(root, "test_*.py")
            + _glob_files(root, "*_test.go")
        )
        code_files = (
            _glob_files(root, "*.py")
            + _glob_files(root, "*.ts")
            + _glob_files(root, "*.js")
            + _glob_files(root, "*.go")
            + _glob_files(root, "*.rs")
        )
        # Subtract test files from code files (they often match both)
        code_files = [f for f in code_files if f not in test_files]
        n_tests = len(test_files)
        n_code = max(1, len(code_files))
        ratio = n_tests / n_code
        if n_tests == 0:
            findings.append({
                "kind": "readme_vs_tests",
                "severity_score": 7.0,
                "claim": "README mentions tests/testing",
                "reality": f"0 test files found, {n_code} code files",
                "suggestion": "Either add tests or remove test claims from README",
            })
        elif ratio < 0.05:
            findings.append({
                "kind": "readme_vs_tests",
                "severity_score": 4.0,
                "claim": "README mentions tests/testing",
                "reality": f"{n_tests} test files vs {n_code} code files (ratio {ratio:.0%})",
                "suggestion": "Test coverage appears thin; consider expanding or softening claim",
            })
    return findings


def _check_declared_vs_imported_deps(root: Path) -> list[dict]:
    findings = []
    # Python: pyproject.toml / requirements.txt
    req = root / "requirements.txt"
    pyproject = root / "pyproject.toml"
    declared = set()
    if req.exists():
        for line in _read_text_head(req).splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                name = re.split(r"[<>=~!;\s]", line)[0].lower()
                if name:
                    declared.add(name)
    if pyproject.exists():
        text = _read_text_head(pyproject)
        for m in re.finditer(r'"([a-zA-Z0-9_-]+)[^"]*"', text):
            declared.add(m.group(1).lower())

    # Check actual imports
    py_files = _glob_files(root, "*.py")
    imported = set()
    import_rx = re.compile(r"^\s*(?:from|import)\s+([a-zA-Z0-9_]+)")
    for f in py_files:
        try:
            with open(f, "r", encoding="utf-8", errors="ignore") as fp:
                for line in fp:
                    m = import_rx.match(line)
                    if m:
                        imported.add(m.group(1).lower())
        except (OSError, IOError):
            continue

    if declared and imported:
        stdlib = {"os", "sys", "re", "json", "math", "random", "time", "datetime", "typing",
                  "pathlib", "collections", "itertools", "functools", "subprocess", "argparse",
                  "asyncio", "logging", "unittest", "dataclasses", "abc", "ast", "io",
                  "__future__", "enum", "decimal", "fractions", "hashlib", "secrets", "uuid",
                  "copy", "contextlib", "threading", "multiprocessing", "queue", "shutil", "tempfile",
                  "inspect", "importlib", "weakref", "csv", "xml", "urllib", "http", "email"}
        # Unused declared (in pyproject/requirements but never imported)
        unused = declared - imported - stdlib
        unused = {u for u in unused if len(u) > 2}  # filter noise
        if len(unused) > 3:
            findings.append({
                "kind": "declared_unused_deps",
                "severity_score": 3.0,
                "claim": f"{len(declared)} dependencies declared",
                "reality": f"{len(unused)} never imported: {sorted(list(unused))[:8]}",
                "suggestion": "Remove unused dependencies to reduce surface area and supply-chain risk",
            })
        # Imported but not declared (possibly vendored or missing)
        undeclared = imported - declared - stdlib
        # Filter out local/project modules
        local_mods = {f.stem for f in py_files}
        undeclared = undeclared - local_mods
        if len(undeclared) > 3:
            findings.append({
                "kind": "undeclared_imports",
                "severity_score": 4.0,
                "claim": "requirements/pyproject declares project dependencies",
                "reality": f"{len(undeclared)} imports not in requirements: {sorted(list(undeclared))[:8]}",
                "suggestion": "Add missing dependencies or remove imports; install will fail elsewhere",
            })
    return findings


def _check_todo_fixme_density(root: Path) -> list[dict]:
    code_files = (
        _glob_files(root, "*.py") + _glob_files(root, "*.ts")
        + _glob_files(root, "*.js") + _glob_files(root, "*.go")
        + _glob_files(root, "*.rs") + _glob_files(root, "*.md")
    )
    if not code_files:
        return []
    total_lines = _count_lines(code_files)
    if total_lines < 100:
        return []
    todos = _grep_count(code_files, r"\bTODO\b|\bFIXME\b|\bXXX\b|\bHACK\b")
    ratio = todos / max(1, total_lines / 1000)  # TODOs per 1000 lines
    if ratio > 15:
        return [{
            "kind": "high_todo_density",
            "severity_score": 5.0,
            "claim": "project appears production/complete",
            "reality": f"{todos} TODO/FIXME/HACK markers in {total_lines} lines (~{ratio:.1f} per kloc)",
            "suggestion": "High marker density suggests unfinished work — audit and resolve or triage",
        }]
    if ratio > 5:
        return [{
            "kind": "moderate_todo_density",
            "severity_score": 2.0,
            "claim": "project appears stable",
            "reality": f"{todos} TODO/FIXME markers (~{ratio:.1f} per kloc)",
            "suggestion": "Consider grooming marker list; some may be stale",
        }]
    return []


def _check_stale_git(root: Path) -> list[dict]:
    stats = _git_stats(root)
    if not stats.get("is_git"):
        return []
    findings = []
    commits_90d = stats.get("commits_last_90d", 0)
    last_ago = stats.get("last_commit_ago", "")
    if "year" in last_ago:
        findings.append({
            "kind": "stale_repo",
            "severity_score": 6.0,
            "claim": "repo exists / project active",
            "reality": f"last commit {last_ago}, {commits_90d} commits in last 90 days",
            "suggestion": "Confirm project is still maintained; archive or revive explicitly",
        })
    elif commits_90d == 0:
        findings.append({
            "kind": "stagnant_repo",
            "severity_score": 3.0,
            "claim": "active development",
            "reality": f"0 commits in last 90 days (last: {last_ago})",
            "suggestion": "Either commit progress or declare project on hold",
        })
    return findings


def _check_oversized_files(root: Path) -> list[dict]:
    code_files = _glob_files(root, "*.py") + _glob_files(root, "*.ts") + _glob_files(root, "*.js")
    huge = []
    for f in code_files:
        try:
            n_lines = sum(1 for _ in open(f, "rb"))
            if n_lines > 1500:
                huge.append((f.relative_to(root), n_lines))
        except (OSError, IOError):
            continue
    if len(huge) >= 1:
        sev = min(6.0, 2.0 + 0.5 * len(huge))
        return [{
            "kind": "oversized_files",
            "severity_score": sev,
            "claim": "modular, maintainable architecture",
            "reality": f"{len(huge)} files >1500 lines: " + ", ".join(
                f"{p}({n})" for p, n in sorted(huge, key=lambda x: -x[1])[:5]
            ),
            "suggestion": "Split large files by responsibility; keeps cognitive load manageable",
        }]
    return []


def _check_readme_vs_ci(root: Path) -> list[dict]:
    readme = None
    for name in ["README.md", "Readme.md", "readme.md"]:
        if (root / name).exists():
            readme = root / name
            break
    if not readme:
        return []
    text = _read_text_head(readme).lower()
    claims_ci = bool(re.search(r"\b(ci/cd|github actions|continuous integration|automated build)\b", text))
    has_ci = (root / ".github" / "workflows").exists() or (root / ".gitlab-ci.yml").exists() or (root / ".circleci").exists()
    if claims_ci and not has_ci:
        return [{
            "kind": "readme_vs_ci",
            "severity_score": 5.0,
            "claim": "README mentions CI/CD",
            "reality": "no .github/workflows, .gitlab-ci.yml, or .circleci/ found",
            "suggestion": "Add real CI config, or remove CI claims from README",
        }]
    return []


# ── Main ─────────────────────────────────────────────────────────────

CHECKS = [
    _check_readme_claims_vs_tests,
    _check_readme_vs_ci,
    _check_declared_vs_imported_deps,
    _check_todo_fixme_density,
    _check_stale_git,
    _check_oversized_files,
]


def scan(path: str) -> dict[str, Any]:
    """Scan a project directory and return ranked divergences.

    Returns:
        {
          "project": "<path>",
          "is_git": bool,
          "git": {...},
          "divergences": [
            {"kind", "severity_score", "severity_label", "claim", "reality", "suggestion"},
            ...
          ],
          "summary": {"total": int, "by_severity": {critical: 2, high: 1, ...}}
        }
    """
    root = Path(path).resolve()
    if not root.is_dir():
        raise ValueError(f"not a directory: {path}")

    all_findings = []
    for check in CHECKS:
        try:
            all_findings.extend(check(root))
        except Exception as e:
            all_findings.append({
                "kind": "scanner_error",
                "severity_score": 0.0,
                "claim": f"scanner {check.__name__}",
                "reality": f"crashed: {type(e).__name__}: {e}",
                "suggestion": "this is a bug in the scanner; ignore for now",
            })

    # Attach severity label + sort
    for f in all_findings:
        f["severity_label"] = _severity_label(f["severity_score"])
    all_findings.sort(key=lambda x: x["severity_score"], reverse=True)

    # Summary
    by_sev: dict[str, int] = {}
    for f in all_findings:
        by_sev[f["severity_label"]] = by_sev.get(f["severity_label"], 0) + 1

    return {
        "project": str(root),
        "git": _git_stats(root),
        "divergences": all_findings,
        "summary": {
            "total": len(all_findings),
            "by_severity": by_sev,
        },
    }


def render(result: dict) -> str:
    lines = []
    lines.append("=" * 72)
    lines.append(f"  DIVERGENCE SCAN — {result['project']}")
    lines.append("=" * 72)
    summary = result["summary"]
    lines.append(f"  Total divergences: {summary['total']}")
    if summary["by_severity"]:
        parts = [f"{k}: {v}" for k, v in summary["by_severity"].items()]
        lines.append("  By severity: " + ", ".join(parts))
    lines.append("")
    if not result["divergences"]:
        lines.append("  ✓ No divergences detected.")
        lines.append("=" * 72)
        return "\n".join(lines) + "\n"
    for f in result["divergences"]:
        mark = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🔵", "negligible": "⚪"}.get(
            f["severity_label"], "•"
        )
        lines.append(f"  {mark} [{f['severity_label']}] {f['kind']}  (score {f['severity_score']:.1f})")
        lines.append(f"      claim:   {f['claim']}")
        lines.append(f"      reality: {f['reality']}")
        lines.append(f"      fix:     {f['suggestion']}")
        lines.append("")
    lines.append("=" * 72)
    return "\n".join(lines) + "\n"


def main(argv=None):
    import argparse
    p = argparse.ArgumentParser(prog="divergence_scanner")
    p.add_argument("path", help="project directory to scan")
    p.add_argument("--format", choices=["text", "json"], default="text")
    args = p.parse_args(argv)
    result = scan(args.path)
    if args.format == "json":
        json.dump(result, sys.stdout, indent=2, default=str)
        sys.stdout.write("\n")
    else:
        sys.stdout.write(render(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
