"""Token-saving output utilities."""

from __future__ import annotations


def to_compact(matches: list[dict]) -> str:
    """Convert list of match dicts to compact path:line:snippet format (~30% fewer tokens)."""
    lines = []
    for m in matches:
        occ = m.get("occurrences", 1)
        occ_str = f" ({occ}x)" if occ > 1 else ""
        lines.append(f"{m.get('path', '?')}:{m.get('line', 0)}: {m.get('snippet', '')}{occ_str}")
    return "\n".join(lines)


def center_snippet(line: str, match_start: int, match_end: int, width: int = 120) -> str:
    """Return up to `width` chars of `line` centered on [match_start, match_end]."""
    line = line.rstrip("\n\r")
    if len(line) <= width:
        return line.strip()
    half = width // 2
    center = (match_start + match_end) // 2
    start = max(0, center - half)
    end = min(len(line), start + width)
    start = max(0, end - width)
    return line[start:end].strip()


def truncate_snippet(line: str, max_len: int = 120) -> str:
    """Truncate from start of line, strip whitespace."""
    return line.strip()[:max_len]
