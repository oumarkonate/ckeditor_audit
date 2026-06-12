"""
Git-aware search helpers.

Pure functions over ``settings.project_root``. They raise ``RuntimeError`` when
the project is not a git repository or when a git call fails or times out.

Extracted from ``searcher.py`` to keep git logic isolated and independently
testable; ``searcher`` re-exports these names for backward compatibility.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

from ckeditor_audit.config import settings
from ckeditor_audit.lib.constants import GIT_TIMEOUT, SUBPROCESS_TIMEOUT


def _assert_git_repo() -> None:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            cwd=str(settings.project_root),
            capture_output=True,
            text=True,
            timeout=GIT_TIMEOUT,
        )
    except subprocess.TimeoutExpired:
        raise RuntimeError("git rev-parse timed out")
    if result.returncode != 0:
        raise RuntimeError(f"Not a git repository: {settings.project_root}")


def git_changed_files(scope: str = "unstaged") -> list[dict]:
    _assert_git_repo()

    if scope == "staged":
        cmd = ["git", "diff", "--cached", "--name-status"]
    elif scope == "all":
        cmd = ["git", "status", "--porcelain"]
    elif scope == "unstaged":
        cmd = ["git", "diff", "--name-status"]
    else:
        cmd = ["git", "diff-tree", "--no-commit-id", "-r", "--name-status", scope]

    try:
        result = subprocess.run(
            cmd,
            cwd=str(settings.project_root),
            capture_output=True,
            text=True,
            timeout=SUBPROCESS_TIMEOUT,
        )
    except subprocess.TimeoutExpired:
        raise RuntimeError("git command timed out")
    if result.returncode != 0:
        raise RuntimeError(f"git command failed: {result.stderr.strip()}")

    files: list[dict] = []
    for line in result.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        if scope == "all":
            status = line[:2].strip() or "M"
            path = line[3:].strip()
        else:
            parts = line.split("\t", 1)
            if len(parts) < 2:
                continue
            status, path = parts[0][0], parts[1].strip()
        files.append({"path": path, "status": status})

    return files


def grep_changed(
    query: str,
    scope: str = "unstaged",
    extensions: list[str] | None = None,
) -> tuple[list[dict], int]:
    changed = git_changed_files(scope)
    if not changed:
        return [], 0

    exts = tuple(e.lstrip(".") for e in extensions) if extensions else settings.extensions
    relevant = [
        f["path"] for f in changed
        if f["status"] != "D" and Path(f["path"]).suffix.lstrip(".") in exts
    ]
    if not relevant:
        return [], 0

    try:
        pattern = re.compile(query)
    except re.error:
        pattern = re.compile(re.escape(query))

    results: list[dict] = []
    files_searched = 0

    for rel_path in relevant:
        full_path = settings.project_root / rel_path
        if not full_path.exists():
            continue
        files_searched += 1
        try:
            with open(full_path, encoding="utf-8", errors="ignore") as f:
                for lineno, line in enumerate(f, 1):
                    if pattern.search(line):
                        results.append({
                            "path": rel_path,
                            "line": lineno,
                            "snippet": line.strip()[:120],
                        })
        except OSError:
            continue

    return results, files_searched


def find_in_file_diff(path: str, scope: str = "unstaged") -> list[dict]:
    """Return modified line ranges (hunks) for a specific file."""
    _assert_git_repo()

    if scope == "staged":
        cmd = ["git", "diff", "--cached", "-U0", "--", path]
    elif scope == "unstaged":
        cmd = ["git", "diff", "-U0", "--", path]
    else:
        cmd = ["git", "diff-tree", "--no-commit-id", "-r", "-U0", scope, "--", path]

    try:
        result = subprocess.run(
            cmd, cwd=str(settings.project_root), capture_output=True, text=True,
            timeout=SUBPROCESS_TIMEOUT,
        )
    except subprocess.TimeoutExpired:
        raise RuntimeError("git diff timed out")
    if result.returncode not in (0, 1):
        raise RuntimeError(f"git diff failed: {result.stderr.strip()}")

    hunks: list[dict] = []
    hunk_re = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")
    for line in result.stdout.splitlines():
        m = hunk_re.match(line)
        if m:
            old_start, old_count = int(m.group(1)), int(m.group(2) or 1)
            new_start, new_count = int(m.group(3)), int(m.group(4) or 1)
            hunks.append({
                "path": path,
                "old_start": old_start,
                "old_lines": old_count,
                "new_start": new_start,
                "new_lines": new_count,
            })

    return hunks
