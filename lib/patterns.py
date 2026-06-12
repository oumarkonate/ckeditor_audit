"""
Known legacy → latest migration patterns.

The catalog lives as data in ``lib/data/patterns.json`` so it can grow without
code changes. Each entry maps an old import/API signature to its modern
equivalent when migrating a CKEditor custom plugin to a newer version.

- ``legacy``       : the old signature to look for — a literal substring, or a
                     regular expression when ``is_regex`` is True
- ``replacement``  : the equivalent in the target version
- ``description``  : plain-English explanation for the developer
- ``category``     : groups patterns by theme (import | api | schema | utils)
- ``is_regex``     : when True, ``legacy`` is matched with ``re.search``
- ``confidence``   : how certain the mapping is (high | medium | low)
- ``since_version``: optional CKEditor version the change landed in

Add new entries by editing ``lib/data/patterns.json`` — no code change needed.
"""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel


class Pattern(BaseModel):
    legacy: str
    replacement: str
    description: str
    category: str
    is_regex: bool = False
    confidence: str = "high"
    since_version: str | None = None


_DATA_FILE = Path(__file__).parent / "data" / "patterns.json"


def _load_patterns() -> list[Pattern]:
    """Load and validate the pattern catalog from the JSON data file."""
    raw = json.loads(_DATA_FILE.read_text(encoding="utf-8"))
    return [Pattern(**entry) for entry in raw]


# Pattern table — loaded once at import time from the JSON data file.
PATTERNS: list[Pattern] = _load_patterns()
