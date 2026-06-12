"""
File system scanner and static analyser.

All functions are pure (no side effects) and operate on the paths provided
by config.Settings. They are called by the tool functions, not directly.
"""

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Literal

from ckeditor_audit.config import settings
from ckeditor_audit.lib.patterns import PATTERNS, Pattern


# ---------------------------------------------------------------------------
# Type aliases
# ---------------------------------------------------------------------------

# "no_imports" = a plugin directory with no CKEditor imports at all (nothing to
# migrate); kept distinct from "not_migrated" (legacy imports present).
MigrationStatus = Literal["migrated", "not_migrated", "partial", "no_imports"]


class PatternHit(object):
    """A single pattern match found inside a plugin file."""

    def __init__(self, file: str, pattern: Pattern, line: int, matched: str | None = None):
        self.file = file       # relative path inside the plugin directory
        self.pattern = pattern
        self.line = line
        # The concrete text matched on the line. For regex and generic hits this
        # is the actual import found, not the pattern expression — more actionable.
        self.matched = matched if matched is not None else pattern.legacy


# ---------------------------------------------------------------------------
# Plugin discovery
# ---------------------------------------------------------------------------

def list_plugins() -> list[str]:
    """Return the names of all plugin directories matching CKEDITOR_AUDIT_PLUGINS_GLOB."""
    root = settings.project_root
    # glob() returns Path objects — we only want the directory name, not the full path
    return sorted(
        p.name
        for p in root.glob(settings.plugins_glob)
        if p.is_dir()
    )


def plugin_root(name: str) -> Path:
    """Return the absolute path of a plugin directory."""
    # The glob may include subdirs like assets/ckeditor/ckeditor5-box.
    # Reconstruct the full path by joining the glob's parent prefix with the name.
    # When the glob has no "/" (plugins live directly under project_root), there
    # is no parent prefix to prepend.
    base = settings.project_root
    if "/" in settings.plugins_glob:
        base = base / settings.plugins_glob.rsplit("/", 1)[0]  # e.g. "assets/ckeditor"
    return base / name


def plugin_files(name: str) -> list[Path]:
    """Return all .js files inside a plugin directory (recursive)."""
    root = plugin_root(name)
    if not root.is_dir():
        return []
    return sorted(root.rglob("*.js"))


# ---------------------------------------------------------------------------
# Migration status detection
# ---------------------------------------------------------------------------

# Signatures that identify each version
_LEGACY_SIGNATURE = "@ckeditor/ckeditor5-"   # present in old-style deep imports
_MODERN_SIGNATURE = "from 'ckeditor5'"        # present in migrated flat imports


def detect_status(name: str) -> MigrationStatus:
    """
    Classify a plugin as migrated / not_migrated / partial / no_imports.

    - migrated     : only modern imports found
    - not_migrated : only legacy imports found
    - partial      : both kinds coexist (migration in progress)
    - no_imports   : no CKEditor imports at all (nothing to migrate)
    """
    has_legacy = False
    has_modern = False

    for path in plugin_files(name):
        try:
            content = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue

        if _LEGACY_SIGNATURE in content:
            has_legacy = True
        if _MODERN_SIGNATURE in content:
            has_modern = True

        # Early exit once both are found
        if has_legacy and has_modern:
            break

    if has_legacy and has_modern:
        return "partial"
    if has_modern:
        return "migrated"
    if has_legacy:
        return "not_migrated"
    return "no_imports"


# ---------------------------------------------------------------------------
# Pattern matching
# ---------------------------------------------------------------------------

# Generic legacy deep-import detector. Any "@ckeditor/ckeditor5-<pkg>/..."
# reference that no specific pattern recognises still needs migrating to a flat
# 'ckeditor5' import — this guarantees suggest_migration is never empty for a
# plugin that detect_status flags as not_migrated/partial.
_GENERIC_IMPORT_RE = re.compile(r"@ckeditor/ckeditor5-[\w./-]+")


@lru_cache(maxsize=1)
def _compiled_patterns() -> list[tuple[Pattern, "re.Pattern[str] | None"]]:
    """Pair each catalog pattern with a compiled regex (or None for substring).

    Compiled once and cached so regexes are not recompiled on every scanned line.
    """
    compiled: list[tuple[Pattern, "re.Pattern[str] | None"]] = []
    for pattern in PATTERNS:
        rx = re.compile(pattern.legacy) if pattern.is_regex else None
        compiled.append((pattern, rx))
    return compiled


def _generic_import_pattern(matched_text: str) -> Pattern:
    """Build a synthetic Pattern for a legacy deep import with no specific rule."""
    return Pattern(
        legacy=matched_text,
        replacement="import { /* named export(s) */ } from 'ckeditor5'",
        description=(
            "Deep '@ckeditor/ckeditor5-*' import with no specific rule — replace "
            "with the matching named export(s) from the flat 'ckeditor5' package"
        ),
        category="import",
        confidence="medium",
    )


def find_pattern_hits(name: str) -> list[PatternHit]:
    """
    Scan all .js files of a plugin and return every line that matches a known
    legacy pattern from the PATTERNS table, plus a generic fallback hit for any
    legacy '@ckeditor/ckeditor5-*' deep import not covered by a specific pattern.
    """
    hits: list[PatternHit] = []
    compiled = _compiled_patterns()

    for path in plugin_files(name):
        try:
            lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
        except OSError:
            continue

        # Relative path for display (e.g. "src/box.js")
        rel = str(path.relative_to(plugin_root(name)))

        for lineno, line in enumerate(lines, start=1):
            matched_specific = False
            for pattern, rx in compiled:
                m = rx.search(line) if rx is not None else None
                if rx is not None:
                    if m is None:
                        continue
                    matched_text = m.group(0)
                elif pattern.legacy in line:
                    matched_text = pattern.legacy
                else:
                    continue
                hits.append(PatternHit(file=rel, pattern=pattern, line=lineno, matched=matched_text))
                matched_specific = True

            # Generic fallback only when no specific pattern matched this line,
            # so we never double-count a line already covered above.
            if not matched_specific:
                gm = _GENERIC_IMPORT_RE.search(line)
                if gm:
                    hits.append(
                        PatternHit(
                            file=rel,
                            pattern=_generic_import_pattern(gm.group(0)),
                            line=lineno,
                            matched=gm.group(0),
                        )
                    )

    return hits


# ---------------------------------------------------------------------------
# Config file cross-reference
# ---------------------------------------------------------------------------

# A line is "commented" if its first non-whitespace characters are a comment marker.
# This heuristic works for JS (//, /*), PHP (//, #), and YAML (#). The bare "*"
# marker is deliberately excluded: it caused false positives on multiplications
# and JSDoc continuation lines.
_COMMENT_MARKERS = ("//", "#", "/*")


def _is_commented(line: str) -> bool:
    """Return True if the line appears to be a comment (heuristic)."""
    stripped = line.lstrip()
    return any(stripped.startswith(m) for m in _COMMENT_MARKERS)


class UsageInfo:
    """Summary of how a plugin is referenced in one file."""

    def __init__(self, file: str, active: bool, commented: bool):
        # Path relative to project root (e.g. "assets/config/ckeditor/article_config.js")
        self.file = file
        # True if at least one uncommented line references the plugin
        self.active = active
        # True if at least one commented line references the plugin
        self.commented = commented


def _collect_paths(glob_pattern: str) -> list[Path]:
    """Expand a single glob relative to project root and return matching paths."""
    root = settings.project_root
    return sorted(p for p in root.glob(glob_pattern) if p.is_file())


def configs_using(name: str) -> tuple[list[UsageInfo], int]:
    """
    Return (usages, files_checked) where usages is one UsageInfo per file that
    references the given plugin name, and files_checked is the total number of
    candidate files that were scanned.

    Scans both CKEDITOR_AUDIT_CONFIGS_GLOB and CKEDITOR_AUDIT_EXTRA_GLOBS.
    For each file, reports whether the reference is active (uncommented),
    commented, or both.
    """
    root = settings.project_root
    results: list[UsageInfo] = []

    # Collect all candidate files from all configured globs
    all_globs = [settings.configs_glob] + list(settings.extra_globs)
    seen: set[Path] = set()
    candidates: list[Path] = []
    for glob_pattern in all_globs:
        for p in _collect_paths(glob_pattern):
            if p not in seen:
                seen.add(p)
                candidates.append(p)

    for file_path in candidates:
        try:
            lines = file_path.read_text(encoding="utf-8", errors="ignore").splitlines()
        except OSError:
            continue

        active = False
        commented = False

        for line in lines:
            if name not in line:
                continue
            if _is_commented(line):
                commented = True
            else:
                active = True

        if active or commented:
            rel = str(file_path.relative_to(root))
            results.append(UsageInfo(file=rel, active=active, commented=commented))

    return results, len(candidates)


# ---------------------------------------------------------------------------
# package.json inspection (CKEditor dependency versions)
# ---------------------------------------------------------------------------

_PKG_DEP_SECTIONS = ("dependencies", "devDependencies", "peerDependencies")


def _is_excluded_path(rel: Path) -> bool:
    """True if any path segment is in the configured exclude_dirs (node_modules, …)."""
    return any(part in settings.exclude_dirs for part in rel.parts)


def _ckeditor_deps(data: dict) -> dict[str, str]:
    """Extract '@ckeditor/*' and 'ckeditor5' dependency version specs from a parsed package.json."""
    deps: dict[str, str] = {}
    for section in _PKG_DEP_SECTIONS:
        for pkg, ver in (data.get(section) or {}).items():
            if pkg == "ckeditor5" or pkg.startswith("@ckeditor/"):
                deps[pkg] = ver
    return deps


def plugin_package_info(name: str) -> dict | None:
    """
    Read a plugin's package.json (if present) and return its declared name,
    version, and any CKEditor dependency version specs. Returns None when the
    plugin has no package.json or it cannot be parsed.
    """
    pkg = plugin_root(name) / "package.json"
    if not pkg.is_file():
        return None
    try:
        data = json.loads(pkg.read_text(encoding="utf-8", errors="ignore"))
    except (OSError, ValueError):
        return None
    return {
        "name": data.get("name"),
        "version": data.get("version"),
        "ckeditor_dependencies": _ckeditor_deps(data),
    }


def find_package_jsons() -> list[Path]:
    """Return all package.json files under project_root, skipping excluded dirs."""
    root = settings.project_root
    result: list[Path] = []
    for p in root.rglob("package.json"):
        if _is_excluded_path(p.relative_to(root)):
            continue
        result.append(p)
    return sorted(result)
