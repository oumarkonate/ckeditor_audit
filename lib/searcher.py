"""
Generic file search engine.

Pure functions shared by find_files, grep_code, grep_with_context,
count_matches, and the git-aware tools. No side effects — operates
on paths derived from config.settings.
"""

import re
import subprocess
from pathlib import Path
from typing import Generator

from ckeditor_audit.config import settings

# ---------------------------------------------------------------------------
# Token cost estimates (tokens Claude would spend reading files directly)
# ---------------------------------------------------------------------------

TOKENS_PER_FILE_SEARCH = 1200   # grep-style tools: full file scan
TOKENS_PER_FILE_FIND   = 80     # name-only tools: just stat + name check


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _compile_pattern(query: str) -> re.Pattern:
    """Compile query as regex; fall back to escaped literal on invalid syntax."""
    try:
        return re.compile(query)
    except re.error:
        return re.compile(re.escape(query))


def _iter_files(
    directory: str | None,
    extensions: list[str] | None,
) -> Generator[Path, None, None]:
    """
    Yield project files, skipping excluded directories and filtering by extension.

    `directory` is relative to project_root (None = whole project).
    `extensions` is a list of extensions without dot, e.g. ["js", "ts"].
    """
    root = settings.project_root
    base = root / directory if directory else root
    ext_set = {e.lstrip(".").lower() for e in extensions} if extensions else None

    for path in base.rglob("*"):
        if not path.is_file():
            continue
        # Check relative parts so we exclude e.g. node_modules anywhere in the tree
        try:
            rel_parts = path.relative_to(root).parts
        except ValueError:
            continue
        # Exclude based on directory components only (not the filename itself)
        if any(part in settings.exclude_dirs for part in rel_parts[:-1]):
            continue
        if ext_set and path.suffix.lstrip(".").lower() not in ext_set:
            continue
        yield path


# ---------------------------------------------------------------------------
# Data classes (plain objects, no Pydantic — kept out of Pydantic models
# so tools can map them to their own response models)
# ---------------------------------------------------------------------------

class GrepMatch:
    __slots__ = ("path", "line", "snippet")

    def __init__(self, path: str, line: int, snippet: str):
        self.path = path
        self.line = line
        self.snippet = snippet


class ContextMatch:
    __slots__ = ("path", "line", "snippet", "before", "after")

    def __init__(
        self,
        path: str,
        line: int,
        snippet: str,
        before: list[str],
        after: list[str],
    ):
        self.path = path
        self.line = line
        self.snippet = snippet
        self.before = before
        self.after = after


# ---------------------------------------------------------------------------
# Search functions
# ---------------------------------------------------------------------------

def grep_files(
    query: str,
    directory: str | None = None,
    extensions: list[str] | None = None,
    max_results: int | None = None,
) -> tuple[list[GrepMatch], int]:
    """
    Search files for query. Returns (matches, files_searched).

    Stops as soon as max_results is reached.
    """
    limit = max_results if max_results is not None else settings.max_results
    pattern = _compile_pattern(query)
    root = settings.project_root
    matches: list[GrepMatch] = []
    files_searched = 0

    for path in _iter_files(directory, extensions):
        files_searched += 1
        try:
            lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
        except OSError:
            continue

        rel = str(path.relative_to(root))
        for lineno, line in enumerate(lines, start=1):
            if pattern.search(line):
                matches.append(GrepMatch(path=rel, line=lineno, snippet=line[:120]))
                if len(matches) >= limit:
                    return matches, files_searched

    return matches, files_searched


def grep_files_with_context(
    query: str,
    context_lines: int = 3,
    directory: str | None = None,
    extensions: list[str] | None = None,
    max_results: int | None = None,
) -> tuple[list[ContextMatch], int]:
    """
    Search files for query, including surrounding lines.

    Returns (matches, files_searched). context_lines is clamped to [0, 10].
    """
    limit = max_results if max_results is not None else settings.max_results
    ctx = max(0, min(context_lines, 10))
    pattern = _compile_pattern(query)
    root = settings.project_root
    matches: list[ContextMatch] = []
    files_searched = 0

    for path in _iter_files(directory, extensions):
        files_searched += 1
        try:
            lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
        except OSError:
            continue

        rel = str(path.relative_to(root))
        for lineno, line in enumerate(lines, start=1):
            if pattern.search(line):
                before = lines[max(0, lineno - 1 - ctx) : lineno - 1]
                after = lines[lineno : min(len(lines), lineno + ctx)]
                matches.append(
                    ContextMatch(
                        path=rel,
                        line=lineno,
                        snippet=line[:120],
                        before=before,
                        after=after,
                    )
                )
                if len(matches) >= limit:
                    return matches, files_searched

    return matches, files_searched


def grep_specific_files(
    query: str,
    paths: list[Path],
) -> list[GrepMatch]:
    """
    Search a specific list of files (used by grep_changed).

    No result cap — caller is responsible for limiting input paths.
    """
    pattern = _compile_pattern(query)
    root = settings.project_root
    matches: list[GrepMatch] = []

    for path in paths:
        try:
            lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
        except OSError:
            continue
        try:
            rel = str(path.relative_to(root))
        except ValueError:
            rel = str(path)
        for lineno, line in enumerate(lines, start=1):
            if pattern.search(line):
                matches.append(GrepMatch(path=rel, line=lineno, snippet=line[:120]))

    return matches


def count_pattern(
    query: str,
    directory: str | None = None,
    extensions: list[str] | None = None,
) -> tuple[int, int, int]:
    """
    Count occurrences of query across project files.

    Returns (total_matches, files_matched, files_searched).
    """
    pattern = _compile_pattern(query)
    total = 0
    files_matched = 0
    files_searched = 0

    for path in _iter_files(directory, extensions):
        files_searched += 1
        try:
            lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
        except OSError:
            continue
        hits = sum(1 for line in lines if pattern.search(line))
        if hits:
            total += hits
            files_matched += 1

    return total, files_matched, files_searched


def find_files_by_name(
    pattern: str,
    directory: str | None = None,
    extension: str | None = None,
) -> tuple[list[Path], int]:
    """
    Find files whose name contains pattern (case-insensitive).

    Returns (matching_paths, files_checked). Stops at max_results.
    """
    root = settings.project_root
    base = root / directory if directory else root
    pattern_lower = pattern.lower()
    ext = extension.lstrip(".").lower() if extension else None
    results: list[Path] = []
    files_checked = 0

    for path in base.rglob("*"):
        if not path.is_file():
            continue
        try:
            rel_parts = path.relative_to(root).parts
        except ValueError:
            continue
        if any(part in settings.exclude_dirs for part in rel_parts[:-1]):
            continue
        files_checked += 1
        if ext and path.suffix.lstrip(".").lower() != ext:
            continue
        if pattern_lower in path.name.lower():
            results.append(path)
            if len(results) >= settings.max_results:
                break

    return results, files_checked


# ---------------------------------------------------------------------------
# Git helpers
# ---------------------------------------------------------------------------

def git_list_changed(scope: str = "unstaged") -> list[tuple[str, str]]:
    """
    Return [(status, relative_path)] for git-changed files.

    `scope` values: "unstaged", "staged", "all", or a commit SHA.
    Returns an empty list if the project root is not a git repo or git is unavailable.
    """
    root = settings.project_root

    if scope == "unstaged":
        cmd = ["git", "diff", "--name-status"]
    elif scope == "staged":
        cmd = ["git", "diff", "--cached", "--name-status"]
    elif scope == "all":
        cmd = ["git", "status", "--porcelain"]
    else:
        # Treat as a commit SHA
        cmd = ["git", "diff-tree", "--no-commit-id", "-r", "--name-status", scope]

    try:
        result = subprocess.run(
            cmd,
            cwd=str(root),
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return []

    files: list[tuple[str, str]] = []
    for line in result.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        if scope == "all":
            # porcelain: "XY path" or "XY old -> new"
            status = line[:2].strip() or "M"
            path = line[3:].strip()
            if " -> " in path:
                path = path.split(" -> ")[-1]
        else:
            parts = line.split("\t", 1)
            if len(parts) == 2:
                status, path = parts[0].strip(), parts[1].strip()
            else:
                continue
        files.append((status, path))

    return files
