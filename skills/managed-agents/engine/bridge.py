"""Expose this repository's skill library to Managed Agents sessions.

When a session mounts a `github_repository` resource, the platform scans the
repository's **root `.claude/skills`** directory at session start and offers
every skill it finds to the agent. The scan is one directory level deep:
`.claude/skills/<skill-name>/SKILL.md` is discovered; anything nested deeper,
or any `skills/` directory outside `.claude`, is not.

This repository keeps its skills in `skills/`, some of them nested two levels
(`skills/game-development/2d-games`). This module builds the flat
`.claude/skills/` index the scanner expects, so mounting the repo makes the
whole library available without moving a single source file.

Default mode is `symlink` (relative, so it survives a clone anywhere and costs
a few bytes per skill). `copy` exists as a fallback if a consumer does not
follow symlinks.

SECURITY: skills discovered from a mounted repository are agent instructions
loaded with no review step, in a sandbox where `bash` and `web_fetch` give them
real capability. Only mount repositories you trust, and audit what lands in
`.claude/skills/` before mounting a repo that takes external contributions.
"""

from __future__ import annotations

import os
import shutil
from dataclasses import dataclass, field
from typing import Any

BRIDGE_DIR = os.path.join(".claude", "skills")
SOURCE_DIR = "skills"
SKILL_FILE = "SKILL.md"
MAX_SCAN_DEPTH = 3


@dataclass
class BridgePlan:
    """What the bridge would contain, before anything touches the filesystem."""

    entries: list[tuple[str, str]] = field(default_factory=list)  # (link_name, repo_rel_target)
    collisions: list[str] = field(default_factory=list)
    skipped_aliases: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "count": len(self.entries),
            "collisions_resolved": self.collisions,
            "aliases_skipped": self.skipped_aliases,
        }


def discover_skills(repo_root: str, source_dir: str = SOURCE_DIR) -> list[str]:
    """Every directory under `skills/` holding a SKILL.md, repo-relative."""
    root = os.path.join(repo_root, source_dir)
    found: list[str] = []
    if not os.path.isdir(root):
        return found

    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        rel = os.path.relpath(dirpath, repo_root)
        depth = len(rel.split(os.sep))
        if depth > MAX_SCAN_DEPTH:
            dirnames[:] = []
            continue
        dirnames[:] = [d for d in dirnames if not d.startswith(".")]
        if SKILL_FILE in filenames:
            found.append(rel.replace(os.sep, "/"))
            # Keep walking: this repository treats nested skills
            # (skills/game-development/2d-games) as first-class entries in
            # skills_index.json, so the bridge must too - same walk as
            # scripts/generate_index.py.
    return sorted(found)


def plan(repo_root: str, source_dir: str = SOURCE_DIR) -> BridgePlan:
    """Compute the flat name -> source mapping, resolving collisions.

    Two skills can share a leaf name across different parents
    (`skills/a/review` and `skills/b/review`). The first in sorted order keeps
    the bare name; later ones are disambiguated with their parent directory.
    """
    result = BridgePlan()
    taken: dict[str, str] = {}
    seen_targets: dict[str, str] = {}

    for rel_path in discover_skills(repo_root, source_dir):
        absolute = os.path.join(repo_root, rel_path)

        # `skills/docx -> docx-official` style aliases point at a directory we
        # already indexed; keep the first (friendlier) name, skip the alias.
        real = os.path.realpath(absolute)
        if real in seen_targets:
            result.skipped_aliases.append(f"{rel_path} (alias of {seen_targets[real]})")
            continue
        seen_targets[real] = rel_path

        parts = rel_path.split("/")
        leaf = parts[-1]
        name = leaf
        if name in taken:
            parent = parts[-2] if len(parts) > 1 else "skill"
            name = f"{parent}-{leaf}"
            result.collisions.append(f"{rel_path} -> {name}")
            suffix = 2
            while name in taken:
                name = f"{parent}-{leaf}-{suffix}"
                suffix += 1
        taken[name] = rel_path
        result.entries.append((name, rel_path))

    result.entries.sort()
    return result


def _relative_target(link_name: str, repo_rel_target: str) -> str:
    """Symlink target relative to `.claude/skills/<link_name>`."""
    link_dir = os.path.join(BRIDGE_DIR, link_name)
    return os.path.relpath(repo_rel_target, os.path.dirname(link_dir))


def check(repo_root: str, source_dir: str = SOURCE_DIR) -> dict[str, Any]:
    """Compare the on-disk bridge with what it should be. No writes."""
    expected = plan(repo_root, source_dir)
    bridge_root = os.path.join(repo_root, BRIDGE_DIR)

    present: set[str] = set()
    if os.path.isdir(bridge_root):
        present = {e for e in os.listdir(bridge_root) if not e.startswith(".")}

    wanted = {name for name, _ in expected.entries}
    missing = sorted(wanted - present)
    extra = sorted(present - wanted)

    broken: list[str] = []
    for name, _ in expected.entries:
        link = os.path.join(bridge_root, name)
        if not os.path.exists(link):  # follows symlinks; False for a dangling one
            if os.path.islink(link):
                broken.append(name)
            continue
        if not os.path.isfile(os.path.join(link, SKILL_FILE)):
            broken.append(name)

    return {
        "expected": len(wanted),
        "present": len(present),
        "missing": missing,
        "extra": extra,
        "broken": broken,
        "in_sync": not (missing or extra or broken),
    }


def build(
    repo_root: str,
    source_dir: str = SOURCE_DIR,
    mode: str = "symlink",
    prune: bool = True,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Materialise `.claude/skills/`.

    Only entries inside `.claude/skills/` are ever removed, and only when they
    are not in the plan. Nothing under `skills/` is touched.
    """
    if mode not in {"symlink", "copy"}:
        raise ValueError(f"mode must be 'symlink' or 'copy', got {mode!r}")

    computed = plan(repo_root, source_dir)
    bridge_root = os.path.join(repo_root, BRIDGE_DIR)
    wanted = {name for name, _ in computed.entries}

    created, refreshed, pruned = [], [], []

    if dry_run:
        state = check(repo_root, source_dir)
        return {
            "mode": mode,
            "dry_run": True,
            "planned": len(computed.entries),
            "would_create": state["missing"],
            "would_prune": state["extra"] if prune else [],
            **computed.to_dict(),
        }

    os.makedirs(bridge_root, exist_ok=True)

    if prune and os.path.isdir(bridge_root):
        for entry in sorted(os.listdir(bridge_root)):
            if entry.startswith(".") or entry in wanted:
                continue
            target = os.path.join(bridge_root, entry)
            if os.path.islink(target) or os.path.isfile(target):
                os.unlink(target)
            else:
                shutil.rmtree(target)
            pruned.append(entry)

    for name, rel_target in computed.entries:
        link = os.path.join(bridge_root, name)
        existed = os.path.islink(link) or os.path.exists(link)
        if existed:
            if os.path.islink(link) or os.path.isfile(link):
                os.unlink(link)
            else:
                shutil.rmtree(link)

        if mode == "symlink":
            os.symlink(_relative_target(name, rel_target), link)
        else:
            shutil.copytree(
                os.path.join(repo_root, rel_target),
                link,
                symlinks=False,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
            )

        (refreshed if existed else created).append(name)

    return {
        "mode": mode,
        "dry_run": False,
        "planned": len(computed.entries),
        "created": created,
        "refreshed": refreshed,
        "pruned": pruned if prune else [],
        **computed.to_dict(),
    }
