"""
File system scanner and static analyser.

All functions are pure (no side effects) and operate on the paths provided
by config.Settings. They are called by the tool functions, not directly.
"""

from pathlib import Path
from typing import Literal

from ckeditor_audit.config import settings
from ckeditor_audit.lib.patterns import PATTERNS, Pattern


# ---------------------------------------------------------------------------
# Type aliases
# ---------------------------------------------------------------------------

MigrationStatus = Literal["migrated", "not_migrated", "partial"]


class PatternHit(object):
    """A single pattern match found inside a plugin file."""

    def __init__(self, file: str, pattern: Pattern, line: int):
        self.file = file       # relative path inside the plugin directory
        self.pattern = pattern
        self.line = line


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
    # The glob may include subdirs like assets/ckeditor/ckeditor5-box
    # We reconstruct the full path by joining the glob's parent prefix with the name
    glob_parent = settings.plugins_glob.rsplit("/", 1)[0]  # e.g. "assets/ckeditor"
    return settings.project_root / glob_parent / name


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
    Classify a plugin as migrated / not_migrated / partial.

    - migrated     : only modern imports found
    - not_migrated : only legacy imports found (or no imports at all)
    - partial      : both kinds coexist (migration in progress)
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

    if has_modern and not has_legacy:
        return "migrated"
    if has_legacy and has_modern:
        return "partial"
    return "not_migrated"


# ---------------------------------------------------------------------------
# Pattern matching
# ---------------------------------------------------------------------------

def find_pattern_hits(name: str) -> list[PatternHit]:
    """
    Scan all .js files of a plugin and return every line that matches a
    known legacy pattern from the PATTERNS table.
    """
    hits: list[PatternHit] = []

    for path in plugin_files(name):
        try:
            lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
        except OSError:
            continue

        # Relative path for display (e.g. "src/box.js")
        rel = str(path.relative_to(plugin_root(name)))

        for lineno, line in enumerate(lines, start=1):
            for pattern in PATTERNS:
                if pattern.legacy in line:
                    hits.append(PatternHit(file=rel, pattern=pattern, line=lineno))

    return hits


# ---------------------------------------------------------------------------
# Config file cross-reference
# ---------------------------------------------------------------------------

# A line is "commented" if its first non-whitespace characters are a comment marker.
# This heuristic works for JS (//, /*), PHP (//, #), and YAML (#).
_COMMENT_MARKERS = ("//", "#", "*", "/*")


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
