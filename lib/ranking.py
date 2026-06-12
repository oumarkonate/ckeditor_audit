"""Result ranking for token-savings: push declarations before comments/strings."""

from __future__ import annotations

import re

_DECLARATION_RE = re.compile(
    r"\b(function|class|interface|trait|enum|const|abstract class|final class)\b"
)
_SRC_DIRS = frozenset(["src", "lib", "app", "core", "domain", "module", "modules"])
_LOW_DIRS = frozenset(["test", "tests", "spec", "specs", "fixtures", "examples", "docs", "doc"])


def score_match(match: dict) -> int:
    """Compute a relevance score for a single match dict.

    Higher score = more relevant = show earlier.
    """
    score = 0
    path: str = match.get("path", "")
    snippet: str = match.get("snippet", "")
    in_comment: bool = match.get("in_comment", False)
    in_string: bool = match.get("in_string", False)

    # Declaration bonus
    if _DECLARATION_RE.search(snippet) and not in_comment and not in_string:
        score += 10

    # Source location
    parts = path.replace("\\", "/").split("/")
    if any(p in _SRC_DIRS for p in parts):
        score += 5
    if any(p in _LOW_DIRS for p in parts):
        score -= 5

    # Comment/string penalty
    if in_comment:
        score -= 10
    if in_string:
        score -= 5

    return score


def rank_results(results: list[dict]) -> list[dict]:
    """Sort results by descending relevance score. Stable sort preserves original order for ties."""
    return sorted(results, key=score_match, reverse=True)
