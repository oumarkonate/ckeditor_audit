"""Fuzzy matching for symbol and file name lookups."""

from __future__ import annotations

try:
    from rapidfuzz import fuzz, process as _rf_process
    _HAS_RAPIDFUZZ = True
except ImportError:
    _HAS_RAPIDFUZZ = False


def fuzzy_filter(
    query: str,
    candidates: list[str],
    threshold: int = 55,
    limit: int = 20,
) -> list[tuple[str, int]]:
    """Return (candidate, score) pairs above threshold, sorted by score desc.

    Uses WRatio scorer which combines multiple fuzzy strategies.
    Returns empty list if rapidfuzz is not installed.
    """
    if not candidates or not _HAS_RAPIDFUZZ:
        return []
    results = _rf_process.extract(query, candidates, scorer=fuzz.WRatio, limit=limit)
    return [(r[0], int(r[1])) for r in results if r[1] >= threshold]


def fuzzy_match_items(
    query: str,
    items: list[dict],
    key: str,
    threshold: int = 55,
) -> list[dict]:
    """Filter and rank a list of dicts using fuzzy match on a string field.

    Preserves all original dict fields. Adds a 'fuzzy_score' field.
    """
    if not items:
        return []
    names = [str(item.get(key, "")) for item in items]
    scored = fuzzy_filter(query, names, threshold=threshold)
    name_scores = {name: score for name, score in scored}
    result = []
    for item in items:
        name = str(item.get(key, ""))
        if name in name_scores:
            result.append({**item, "fuzzy_score": name_scores[name]})
    result.sort(key=lambda x: x["fuzzy_score"], reverse=True)
    return result
