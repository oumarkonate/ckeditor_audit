"""
Tool: list_patterns

Returns the full legacy → latest pattern mapping table.
This is the simplest tool — no arguments, no file I/O.
It lets Claude know what patterns the scanner can detect before diving into a plugin.
"""

from ckeditor_audit.lib.patterns import PATTERNS, Pattern


def list_patterns() -> list[Pattern]:
    """
    Return all known legacy → latest migration patterns.

    Use this tool to understand which code signatures the audit scanner can detect.
    Each pattern has a legacy signature, its modern replacement, a description,
    and a category (import | api | schema | utils).
    """
    return PATTERNS
