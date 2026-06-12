"""Ripgrep backend for grep_code, grep_with_context, count_matches."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import threading
import time
from pathlib import Path

_RG_CMD = os.environ.get("CKEDITOR_AUDIT_RG_PATH", "rg")

# ---------------------------------------------------------------------------
# Native rg type map — use --type instead of --glob when extension is known
# ---------------------------------------------------------------------------
_RG_TYPE_MAP: dict[str, str] = {
    "php": "php",
    "js": "js",
    "jsx": "js",
    "mjs": "js",
    "cjs": "js",
    "ts": "ts",
    "tsx": "ts",
    "mts": "ts",
    "cts": "ts",
    "py": "py",
    "rb": "ruby",
    "go": "go",
    "rs": "rust",
    "java": "java",
    "c": "c",
    "h": "c",
    "cpp": "cpp",
    "cc": "cpp",
    "cs": "csharp",
    "json": "json",
    "html": "html",
    "xml": "xml",
    "css": "css",
    "sh": "sh",
    "bash": "sh",
    "md": "md",
    "sql": "sql",
    "yaml": "yaml",
    "yml": "yaml",
    # twig, scss, twig have no native rg type → fall back to --glob
}

# ---------------------------------------------------------------------------
# TTL result cache (5 s) — avoids re-spawning rg for repeated identical calls
# ---------------------------------------------------------------------------
_CACHE_TTL = 5.0
_cache: dict[str, tuple[float, object]] = {}
_cache_lock = threading.Lock()


def _cache_key(args: list[str]) -> str:
    return hashlib.md5(" ".join(args).encode()).hexdigest()


def _cache_get(key: str):
    with _cache_lock:
        entry = _cache.get(key)
        if entry and time.monotonic() - entry[0] < _CACHE_TTL:
            return entry[1]
        if entry:
            del _cache[key]
    return None


def _cache_set(key: str, value: object) -> None:
    now = time.monotonic()
    with _cache_lock:
        _cache[key] = (now, value)
        # Evict expired entries to prevent unbounded growth
        stale = [k for k, (ts, _) in _cache.items() if now - ts >= _CACHE_TTL]
        for k in stale:
            del _cache[k]


def _center_snippet(line: str, match_start: int, match_end: int, width: int = 120) -> str:
    """Return snippet of `width` chars centered around the match."""
    line = line.rstrip("\n\r")
    if len(line) <= width:
        return line.strip()
    half = width // 2
    center = (match_start + match_end) // 2
    start = max(0, center - half)
    end = min(len(line), start + width)
    # nudge start if we hit the end boundary
    start = max(0, end - width)
    return line[start:end].strip()


def _build_base_args(
    root: Path,
    directory: str | None,
    extensions: list[str] | None,
    settings_extensions: tuple[str, ...],
    settings_exclude_dirs: frozenset[str],
    max_results: int,
    case_sensitive: bool | str = "smart",
    whole_word: bool = False,
    fixed_string: bool = False,
    path_glob: str | None = None,
    respect_gitignore: bool = True,
    context_lines: int = 0,
    multiline: bool = False,
) -> tuple[list[str], Path]:
    """Build rg argument list. Returns (args, search_root)."""
    args: list[str] = [_RG_CMD, "--json", "--no-heading"]

    if not respect_gitignore:
        args += ["--no-ignore-vcs"]

    if multiline:
        args += ["--multiline"]

    if case_sensitive == "smart":
        args += ["--smart-case"]
    elif case_sensitive is True:
        args += ["--case-sensitive"]
    else:
        args += ["--ignore-case"]

    if whole_word:
        args += ["--word-regexp"]

    if fixed_string:
        args += ["--fixed-strings"]

    if context_lines > 0:
        args += [f"--before-context={context_lines}", f"--after-context={context_lines}"]

    if path_glob:
        args += ["--glob", path_glob]
    else:
        exts = extensions or list(settings_extensions)
        added_types: set[str] = set()
        for ext in exts:
            clean = ext.lstrip(".")
            rg_type = _RG_TYPE_MAP.get(clean)
            if rg_type and rg_type not in added_types:
                args += ["--type", rg_type]
                added_types.add(rg_type)
            elif not rg_type:
                args += ["--glob", f"*.{clean}"]

    for excl in settings_exclude_dirs:
        args += ["--glob", f"!{excl}/"]

    search_root = root / directory if directory else root
    return args, search_root


def grep_code(
    query: str,
    root: Path,
    directory: str | None,
    extensions: list[str] | None,
    settings_extensions: tuple[str, ...],
    settings_exclude_dirs: frozenset[str],
    max_results: int,
    case_sensitive: bool | str = "smart",
    whole_word: bool = False,
    fixed_string: bool = False,
    path_glob: str | None = None,
    respect_gitignore: bool = True,
    multiline: bool = False,
) -> tuple[list[dict], int]:
    args, search_root = _build_base_args(
        root=root,
        directory=directory,
        extensions=extensions,
        settings_extensions=settings_extensions,
        settings_exclude_dirs=settings_exclude_dirs,
        max_results=max_results,
        case_sensitive=case_sensitive,
        whole_word=whole_word,
        fixed_string=fixed_string,
        path_glob=path_glob,
        respect_gitignore=respect_gitignore,
        multiline=multiline,
    )
    args += [query, str(search_root)]

    key = _cache_key(args)
    cached = _cache_get(key)
    if cached is not None:
        return cached  # type: ignore[return-value]

    try:
        proc = subprocess.run(args, capture_output=True, text=True, timeout=30)
    except subprocess.TimeoutExpired:
        return [], 0

    results: list[dict] = []
    files_searched = 0

    for raw in proc.stdout.splitlines():
        if not raw.strip():
            continue
        try:
            obj = json.loads(raw)
        except json.JSONDecodeError:
            continue

        t = obj.get("type")
        if t == "match":
            data = obj["data"]
            try:
                rel = str(Path(data["path"]["text"]).relative_to(root))
            except ValueError:
                rel = data["path"]["text"]

            line_text = data["lines"]["text"]
            submatches = data.get("submatches", [])
            if submatches:
                snippet = _center_snippet(line_text, submatches[0]["start"], submatches[0]["end"])
            else:
                snippet = line_text.strip()[:120]

            results.append({"path": rel, "line": data["line_number"], "snippet": snippet})

        elif t == "summary":
            stats = obj["data"].get("stats", {})
            files_searched = stats.get("searches", files_searched)

    # Deduplicate same-line matches
    unique: list[dict] = []
    dedup_index: dict[tuple, int] = {}  # key → index in unique for O(1) lookup
    for r in results:
        dedup_key = (r["path"], r["line"])
        if dedup_key not in dedup_index:
            dedup_index[dedup_key] = len(unique)
            unique.append(r)
        else:
            idx = dedup_index[dedup_key]
            unique[idx]["occurrences"] = unique[idx].get("occurrences", 1) + 1

    result = unique[:max_results], files_searched
    _cache_set(key, result)
    return result


def grep_with_context(
    query: str,
    context_lines: int,
    root: Path,
    directory: str | None,
    extensions: list[str] | None,
    settings_extensions: tuple[str, ...],
    settings_exclude_dirs: frozenset[str],
    max_results: int,
    case_sensitive: bool | str = "smart",
    whole_word: bool = False,
    fixed_string: bool = False,
    path_glob: str | None = None,
    respect_gitignore: bool = True,
    multiline: bool = False,
) -> tuple[list[dict], int]:
    ctx = min(max(context_lines, 0), 10)
    args, search_root = _build_base_args(
        root=root,
        directory=directory,
        extensions=extensions,
        settings_extensions=settings_extensions,
        settings_exclude_dirs=settings_exclude_dirs,
        max_results=max_results,
        case_sensitive=case_sensitive,
        whole_word=whole_word,
        fixed_string=fixed_string,
        path_glob=path_glob,
        respect_gitignore=respect_gitignore,
        context_lines=ctx,
        multiline=multiline,
    )
    args += [query, str(search_root)]

    try:
        proc = subprocess.run(args, capture_output=True, text=True, timeout=30)
    except subprocess.TimeoutExpired:
        return [], 0

    # Build results: accumulate context per match
    results: list[dict] = []
    # We collect (before_lines, match_line, after_lines) per match block
    pending_before: list[str] = []
    pending_match: dict | None = None
    files_searched = 0

    for raw in proc.stdout.splitlines():
        if not raw.strip():
            continue
        try:
            obj = json.loads(raw)
        except json.JSONDecodeError:
            continue

        t = obj.get("type")
        if t == "context":
            line_text = obj["data"]["lines"]["text"].rstrip("\n")
            if pending_match is None:
                pending_before.append(line_text)
                if len(pending_before) > ctx:
                    pending_before.pop(0)
            else:
                pending_match["after"].append(line_text)
                if len(pending_match["after"]) >= ctx:
                    results.append(pending_match)
                    pending_match = None
                    pending_before = []

        elif t == "match":
            if pending_match is not None:
                results.append(pending_match)

            data = obj["data"]
            try:
                rel = str(Path(data["path"]["text"]).relative_to(root))
            except ValueError:
                rel = data["path"]["text"]

            line_text = data["lines"]["text"]
            submatches = data.get("submatches", [])
            if submatches:
                snippet = _center_snippet(line_text, submatches[0]["start"], submatches[0]["end"])
            else:
                snippet = line_text.strip()[:120]

            pending_match = {
                "path": rel,
                "line": data["line_number"],
                "snippet": snippet,
                "before": list(pending_before),
                "after": [],
            }
            pending_before = []

        elif t == "summary":
            stats = obj["data"].get("stats", {})
            files_searched = stats.get("searches", files_searched)

    if pending_match is not None:
        results.append(pending_match)

    return results[:max_results], files_searched


def count_matches(
    query: str,
    root: Path,
    directory: str | None,
    extensions: list[str] | None,
    settings_extensions: tuple[str, ...],
    settings_exclude_dirs: frozenset[str],
    case_sensitive: bool | str = "smart",
    whole_word: bool = False,
    fixed_string: bool = False,
    path_glob: str | None = None,
    respect_gitignore: bool = True,
) -> dict:
    # Use rg --count-matches for efficient counting
    args: list[str] = [_RG_CMD, "--count-matches", "--no-heading"]

    if not respect_gitignore:
        args += ["--no-ignore-vcs"]

    if case_sensitive == "smart":
        args += ["--smart-case"]
    elif case_sensitive is True:
        args += ["--case-sensitive"]
    else:
        args += ["--ignore-case"]

    if whole_word:
        args += ["--word-regexp"]
    if fixed_string:
        args += ["--fixed-strings"]

    if path_glob:
        args += ["--glob", path_glob]
    else:
        exts = extensions or list(settings_extensions)
        for ext in exts:
            args += ["--glob", f"*.{ext.lstrip('.')}"]

    for excl in settings_exclude_dirs:
        args += ["--glob", f"!{excl}/"]

    search_root = root / directory if directory else root
    args += [query, str(search_root)]

    try:
        proc = subprocess.run(args, capture_output=True, text=True, timeout=30)
    except subprocess.TimeoutExpired:
        return 0, 0

    total_matches = 0
    files_matched = 0

    for line in proc.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        # Format: path:count
        if ":" in line:
            _, _, count_str = line.rpartition(":")
            try:
                count = int(count_str.strip())
                total_matches += count
                files_matched += 1
            except ValueError:
                continue

    # files_searched not available from --count-matches; use files_matched as lower bound
    return {
        "total_matches": total_matches,
        "files_matched": files_matched,
        "files_searched": files_matched,
    }
