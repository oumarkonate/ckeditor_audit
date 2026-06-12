"""Lightweight heuristic comment/string detection per language."""

from __future__ import annotations

import re

# Patterns for single-line comment starts per extension
_SINGLE_COMMENT: dict[str, list[str]] = {
    "php": ["//", "#", "*"],   # * for doc block interior lines
    "js": ["//", "*"],
    "ts": ["//", "*"],
    "tsx": ["//", "*"],
    "jsx": ["//", "*"],
    "yaml": ["#"],
    "yml": ["#"],
    "twig": ["{#"],
    "scss": ["//", "*"],
    "css": ["*"],
}

_BLOCK_COMMENT_RE = re.compile(r"/\*.*?\*/", re.DOTALL)
_TWIG_COMMENT_RE = re.compile(r"\{#.*?#\}", re.DOTALL)
_PHP_DOC_LINE_RE = re.compile(r"^\s*\*")  # inside /** */ blocks


def _build_block_comment_ranges(lines: list[str], ext: str) -> list[tuple[int, int]]:
    """Return sorted list of (start_line_idx, end_line_idx) for block comment spans.

    Computed once per file to avoid O(n²) rebuilds in classify_line.
    """
    source = "\n".join(lines)
    pattern = _TWIG_COMMENT_RE if ext == "twig" else _BLOCK_COMMENT_RE
    # Build cumulative char offsets to map char position → line index
    offsets: list[int] = []
    pos = 0
    for l in lines:
        offsets.append(pos)
        pos += len(l) + 1  # +1 for the '\n' we joined with

    def _char_to_line(char_pos: int) -> int:
        lo, hi = 0, len(offsets) - 1
        while lo < hi:
            mid = (lo + hi + 1) // 2
            if offsets[mid] <= char_pos:
                lo = mid
            else:
                hi = mid - 1
        return lo

    ranges: list[tuple[int, int]] = []
    for m in pattern.finditer(source):
        ranges.append((_char_to_line(m.start()), _char_to_line(m.end() - 1)))
    return ranges


def _is_inside_block_comment(line_idx: int, ranges: list[tuple[int, int]]) -> bool:
    """Check if line_idx falls inside any pre-computed block comment range."""
    for start, end in ranges:
        if start <= line_idx <= end:
            return True
        if start > line_idx:
            break
    return False


def _is_inside_string(line: str, match_col: int = 0) -> bool:
    """Heuristic: count unescaped quote chars before match_col."""
    single = 0
    double = 0
    i = 0
    col = match_col if match_col > 0 else len(line)
    while i < col:
        c = line[i]
        if c == "\\" and i + 1 < col:
            i += 2
            continue
        if c == "'":
            single += 1
        elif c == '"':
            double += 1
        i += 1
    # Inside a string if odd number of unescaped quotes
    return (single % 2 == 1) or (double % 2 == 1)


def classify_line(
    line: str,
    line_idx: int,
    block_ranges: list[tuple[int, int]],
    ext: str,
) -> tuple[bool, bool]:
    """Return (in_comment, in_string) for the given line.

    This is a fast heuristic — not a full parser. Good enough for ranking purposes.
    block_ranges must be pre-computed via _build_block_comment_ranges().
    """
    stripped = line.strip()
    prefixes = _SINGLE_COMMENT.get(ext, ["//", "#"])

    # Single-line comment check
    for prefix in prefixes:
        if stripped.startswith(prefix):
            return True, False

    # Block comment check using pre-computed ranges (O(1) per line)
    if block_ranges and _is_inside_block_comment(line_idx, block_ranges):
        return True, False

    # String check
    in_str = _is_inside_string(line)
    return False, in_str


def annotate_matches(results: list[dict], root_dir: str) -> list[dict]:
    """Add in_comment and in_string fields to each match by reading the source file."""
    from pathlib import Path

    file_cache: dict[str, list[str]] = {}
    block_ranges_cache: dict[str, list[tuple[int, int]]] = {}
    annotated = []

    for match in results:
        path = match.get("path", "")
        lineno = match.get("line", 1)
        ext = Path(path).suffix.lstrip(".")

        full_path = str(Path(root_dir) / path)
        if full_path not in file_cache:
            try:
                with open(full_path, encoding="utf-8", errors="ignore") as f:
                    lines_read = f.readlines()
                block_ranges_val = _build_block_comment_ranges(lines_read, ext)
                file_cache[full_path] = lines_read
                block_ranges_cache[full_path] = block_ranges_val
            except OSError:
                annotated.append({**match, "in_comment": False, "in_string": False})
                continue

        lines = file_cache[full_path]
        block_ranges = block_ranges_cache[full_path]
        idx = max(0, lineno - 1)
        if idx >= len(lines):
            annotated.append({**match, "in_comment": False, "in_string": False})
            continue

        in_comment, in_string = classify_line(lines[idx], idx, block_ranges, ext)
        annotated.append({**match, "in_comment": in_comment, "in_string": in_string})

    return annotated
