"""Expose a curated slice of this repository's skill library to Managed Agents.

When a session mounts a `github_repository` resource, the platform scans the
repository's **root `.claude/skills`** directory at session start and offers
every skill it finds to the agent. The scan is one directory level deep:
`.claude/skills/<skill-name>/SKILL.md` is discovered; anything nested deeper,
or any `skills/` directory outside `.claude`, is not.

This repository keeps its skills in `skills/`, some of them nested two levels
(`skills/game-development/2d-games`). This module builds the flat
`.claude/skills/` index the scanner expects.

Two deliberate defaults:

  * **Allowlist, not everything.** Repository skills are agent instructions
    loaded with no review step, in a sandbox where `bash` and `web_fetch` give
    them real capability. This library also carries ~25 offensive-security
    skills. Bridging all 240 would put those in front of an unattended,
    Anthropic-hosted agent and charge their announcements against every turn's
    budget. `bridge.allowlist` names what is bridged; `--all` overrides.
  * **Copy, not symlink.** Nothing in the platform docs says the scanner follows
    symlinks, and that cannot be verified without spending money. Copies are
    guaranteed to work; `--check` detects when a copy has drifted from its
    source. `--mode symlink` is available once symlink-following is confirmed.

Nothing under `skills/` is ever modified, and nothing inside `.claude/skills/`
is ever deleted: a stray symlink is unlinked (it is the bridge's own artefact
and points at content that still exists), while any real directory that is
either not wanted or has been edited locally is MOVED to a dated quarantine
directory before being replaced.
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import os
import shutil
from dataclasses import dataclass, field
from typing import Any

BRIDGE_DIR = os.path.join(".claude", "skills")
QUARANTINE_DIR = os.path.join(".claude", "skills-quarantine")
SOURCE_DIR = "skills"
SKILL_FILE = "SKILL.md"
MAX_SCAN_DEPTH = 3
DEFAULT_MODE = "copy"
# Build noise and per-workspace state never belong in a bridged copy.
_SKIP_DIRS = frozenset({".git", "__pycache__", ".pytest_cache"})
_SKIP_FILES = frozenset({"state.json"})
_SKIP_SUFFIXES = (".pyc", ".pyo")


def _ignore(directory: str, names: list[str]) -> set[str]:
    return {n for n in names if n in _SKIP_DIRS or n in _SKIP_FILES or n.endswith(_SKIP_SUFFIXES)}


@dataclass
class BridgePlan:
    """What the bridge would contain, before anything touches the filesystem."""

    entries: list[tuple[str, str]] = field(default_factory=list)  # (link_name, repo_rel_target)
    collisions: list[str] = field(default_factory=list)
    skipped_aliases: list[str] = field(default_factory=list)
    unmatched: list[str] = field(default_factory=list)  # allowlist names that matched nothing

    def to_dict(self) -> dict[str, Any]:
        return {
            "count": len(self.entries),
            "collisions_resolved": self.collisions,
            "aliases_skipped": self.skipped_aliases,
            "allowlist_unmatched": self.unmatched,
        }


# --------------------------------------------------------------------------
# discovery + planning
# --------------------------------------------------------------------------


def discover_skills(repo_root: str, source_dir: str = SOURCE_DIR) -> list[str]:
    """Every directory under `skills/` holding a SKILL.md, repo-relative.

    Same walk as scripts/generate_index.py: nested skills
    (skills/game-development/2d-games) are first-class entries.
    """
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
    return sorted(found)


def read_allowlist(path: str) -> list[str] | None:
    """Skill names (or repo-relative paths) to bridge. None if the file is absent."""
    if not path or not os.path.isfile(path):
        return None
    names: list[str] = []
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            line = line.split("#", 1)[0].strip()
            if line:
                names.append(line.rstrip("/"))
    return names


def plan(
    repo_root: str,
    source_dir: str = SOURCE_DIR,
    allowlist: list[str] | None = None,
) -> BridgePlan:
    """Compute the flat name -> source mapping, resolving collisions.

    `allowlist` entries match a skill by leaf name (`docx-official` - matches
    EVERY skill with that leaf) or by repo-relative path
    (`skills/game-development/2d-games` - exact). None means all.
    """
    result = BridgePlan()
    taken: dict[str, str] = {}
    seen_targets: dict[str, str] = {}
    wanted = None if allowlist is None else set(allowlist)
    matched: set[str] = set()

    for rel_path in discover_skills(repo_root, source_dir):
        leaf = rel_path.split("/")[-1]
        if wanted is not None:
            hit = {n for n in (leaf, rel_path) if n in wanted}
            if not hit:
                continue
            matched |= hit

        absolute = os.path.join(repo_root, rel_path)
        real = os.path.realpath(absolute)
        if real in seen_targets:
            result.skipped_aliases.append(f"{rel_path} (alias of {seen_targets[real]})")
            continue
        seen_targets[real] = rel_path

        parts = rel_path.split("/")
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

    if wanted is not None:
        result.unmatched = sorted(wanted - matched)
    result.entries.sort()
    return result


# --------------------------------------------------------------------------
# filesystem helpers
# --------------------------------------------------------------------------


def _roots(repo_root: str) -> tuple[str, str]:
    """(real repo root, real bridge root) - and refuse to operate outside the repo."""
    real_repo = os.path.realpath(repo_root)
    bridge_root = os.path.realpath(os.path.join(real_repo, BRIDGE_DIR))
    if not (bridge_root == real_repo or bridge_root.startswith(real_repo + os.sep)):
        raise RuntimeError(f"refusing to operate: {bridge_root} is outside {real_repo}")
    return real_repo, bridge_root


def _relative_target(link_name: str, repo_rel_target: str) -> str:
    """Symlink target relative to `.claude/skills/<link_name>`."""
    link_dir = os.path.join(BRIDGE_DIR, link_name)
    return os.path.relpath(repo_rel_target, os.path.dirname(link_dir))


def _walk(root: str):
    """os.walk without following symlinks, skipping build noise."""
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        dirnames[:] = sorted(d for d in dirnames if d not in _SKIP_DIRS)
        yield dirpath, dirnames, sorted(
            f for f in filenames if f not in _SKIP_FILES and not f.endswith(_SKIP_SUFFIXES)
        )


def _tree_digest(root: str) -> str:
    """Content hash of a directory tree (paths + bytes).

    Symlinks are hashed by their target string, never followed - following
    would let a self-referential link loop forever.
    """
    digest = hashlib.sha256()
    for dirpath, _dirnames, filenames in _walk(root):
        for filename in filenames:
            path = os.path.join(dirpath, filename)
            digest.update(os.path.relpath(path, root).encode("utf-8"))
            if os.path.islink(path):
                digest.update(b"link:" + os.readlink(path).encode("utf-8"))
                continue
            try:
                with open(path, "rb") as handle:
                    digest.update(handle.read())
            except OSError:
                digest.update(b"<unreadable>")
    return digest.hexdigest()


def _escaping_symlinks(source: str, real_repo: str) -> list[str]:
    """Symlinks inside a source tree whose target resolves outside the repo.

    Copying one would drag external content into a committed directory.
    """
    escapes: list[str] = []
    for dirpath, dirnames, filenames in _walk(source):
        for name in list(dirnames) + list(filenames):
            path = os.path.join(dirpath, name)
            if not os.path.islink(path):
                continue
            target = os.path.realpath(path)
            if not (target == real_repo or target.startswith(real_repo + os.sep)):
                escapes.append(os.path.relpath(path, real_repo))
    return escapes


# --------------------------------------------------------------------------
# check / build
# --------------------------------------------------------------------------


def check(
    repo_root: str,
    source_dir: str = SOURCE_DIR,
    allowlist: list[str] | None = None,
) -> dict[str, Any]:
    """Compare the on-disk bridge with what it should be. No writes.

    A copied entry whose content no longer matches its source is `stale`; a
    symlink that does not resolve to a SKILL.md is `broken`.
    """
    expected = plan(repo_root, source_dir, allowlist)
    real_repo, bridge_root = _roots(repo_root)

    present: set[str] = set()
    if os.path.isdir(bridge_root):
        present = {e for e in os.listdir(bridge_root) if not e.startswith(".")}

    wanted = {name for name, _ in expected.entries}
    missing = sorted(wanted - present)
    extra = sorted(present - wanted)

    broken: list[str] = []
    stale: list[str] = []
    for name, rel_target in expected.entries:
        link = os.path.join(bridge_root, name)
        if name in missing:
            continue
        if not os.path.isfile(os.path.join(link, SKILL_FILE)):
            broken.append(name)
            continue
        if not os.path.islink(link):
            source = os.path.join(real_repo, rel_target)
            if _tree_digest(source) != _tree_digest(link):
                stale.append(name)

    return {
        "expected": len(wanted),
        "present": len(present),
        "missing": missing,
        "extra": extra,
        "broken": broken,
        "stale": stale,
        "allowlist_unmatched": expected.unmatched,
        "in_sync": not (missing or extra or broken or stale),
    }


def _quarantine(real_repo: str, path: str, stamp: str) -> str:
    """Move an entry out of the bridge, never delete it. Returns the new relpath."""
    quarantine_root = os.path.join(real_repo, QUARANTINE_DIR, stamp)
    os.makedirs(quarantine_root, exist_ok=True)
    destination = os.path.join(quarantine_root, os.path.basename(path))
    if os.path.lexists(destination):
        destination = f"{destination}-{_dt.datetime.now().strftime('%H%M%S%f')}"
    shutil.move(path, destination)
    return os.path.relpath(destination, real_repo)


def build(
    repo_root: str,
    source_dir: str = SOURCE_DIR,
    mode: str = DEFAULT_MODE,
    prune: bool = True,
    dry_run: bool = False,
    allowlist: list[str] | None = None,
) -> dict[str, Any]:
    """Materialise `.claude/skills/`.

    Only entries inside `.claude/skills/` are ever touched. Symlinks are
    unlinked (the bridge's own artefacts). A real directory is never deleted:
    an unwanted one, or a wanted copy whose content differs from its source
    (local edits, or drift), is MOVED to `.claude/skills-quarantine/<date>/`
    before the fresh copy is written. An up-to-date copy is left untouched.
    """
    if mode not in {"symlink", "copy"}:
        raise ValueError(f"mode must be 'symlink' or 'copy', got {mode!r}")

    computed = plan(repo_root, source_dir, allowlist)
    real_repo, bridge_root = _roots(repo_root)
    wanted = {name for name, _ in computed.entries}

    # Refuse before touching anything if a source would drag in external content.
    if mode == "copy":
        for name, rel_target in computed.entries:
            escapes = _escaping_symlinks(os.path.join(real_repo, rel_target), real_repo)
            if escapes:
                raise RuntimeError(
                    f"skill {name!r} contains symlinks that resolve outside the repository "
                    f"({', '.join(escapes[:3])}); refusing to copy them into .claude/skills/"
                )

    present: set[str] = set()
    if os.path.isdir(bridge_root):
        present = {e for e in os.listdir(bridge_root) if not e.startswith(".")}
    strays = sorted(present - wanted) if prune else []
    stray_links = [s for s in strays if os.path.islink(os.path.join(bridge_root, s))]
    stray_dirs = [s for s in strays if s not in stray_links]

    # Classify wanted entries that already exist.
    unchanged: list[str] = []
    edited: list[str] = []  # real dirs whose content differs from source
    replace_links: list[str] = []
    for name, rel_target in computed.entries:
        link = os.path.join(bridge_root, name)
        if not os.path.lexists(link):
            continue
        if os.path.islink(link) or os.path.isfile(link):
            replace_links.append(name)
        elif mode == "copy" and _tree_digest(os.path.join(real_repo, rel_target)) == _tree_digest(link):
            unchanged.append(name)
        else:
            edited.append(name)

    if dry_run:
        return {
            "mode": mode,
            "dry_run": True,
            "planned": len(computed.entries),
            "would_create": sorted(wanted - present),
            "would_refresh": sorted(replace_links),
            "would_leave": sorted(unchanged),
            "would_quarantine": sorted(stray_dirs + edited),
            "would_unlink": stray_links,
            **computed.to_dict(),
        }

    os.makedirs(bridge_root, exist_ok=True)
    stamp = _dt.date.today().isoformat()
    created, refreshed, left, unlinked, quarantined = [], [], [], [], []

    if prune:
        for entry in stray_links:
            os.unlink(os.path.join(bridge_root, entry))
            unlinked.append(entry)
        for entry in stray_dirs:
            quarantined.append(_quarantine(real_repo, os.path.join(bridge_root, entry), stamp))

    for name, rel_target in computed.entries:
        link = os.path.join(bridge_root, name)
        if name in unchanged:
            left.append(name)
            continue
        existed = os.path.lexists(link)
        if existed:
            if os.path.islink(link) or os.path.isfile(link):
                os.unlink(link)
            else:
                quarantined.append(_quarantine(real_repo, link, stamp))

        if mode == "symlink":
            os.symlink(_relative_target(name, rel_target), link)
        else:
            shutil.copytree(os.path.join(real_repo, rel_target), link, symlinks=True, ignore=_ignore)

        (refreshed if existed else created).append(name)

    return {
        "mode": mode,
        "dry_run": False,
        "planned": len(computed.entries),
        "created": created,
        "refreshed": refreshed,
        "left": left,
        "unlinked": unlinked,
        "quarantined": quarantined,
        **computed.to_dict(),
    }
