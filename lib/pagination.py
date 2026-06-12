"""Simple offset-based pagination for search results."""

from __future__ import annotations

import base64
import json


def encode_cursor(offset: int, query_hash: int) -> str:
    data = {"o": offset, "q": query_hash}
    return base64.urlsafe_b64encode(json.dumps(data).encode()).decode()


def decode_cursor(cursor: str) -> tuple[int, int]:
    """Returns (offset, query_hash). Raises ValueError on invalid cursor."""
    try:
        data = json.loads(base64.urlsafe_b64decode(cursor.encode()))
        return int(data["o"]), int(data["q"])
    except Exception as exc:
        raise ValueError(f"Invalid cursor: {exc}") from exc


def paginate(
    results: list[dict],
    max_results: int,
    cursor: str | None,
    query: str,
) -> tuple[list[dict], str | None, bool]:
    """Slice results according to cursor/limit.

    Returns (page_results, next_cursor_or_None, has_more).
    """
    query_hash = hash(query) & 0xFFFF_FFFF

    offset = 0
    if cursor:
        try:
            c_offset, c_hash = decode_cursor(cursor)
            if c_hash == query_hash:
                offset = c_offset
        except ValueError:
            pass

    page = results[offset : offset + max_results]
    has_more = (offset + max_results) < len(results)
    next_cursor = encode_cursor(offset + max_results, query_hash) if has_more else None
    return page, next_cursor, has_more
