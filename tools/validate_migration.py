"""
Tool: validate_migration

Confirms that a CKEditor plugin has no remaining legacy signatures.
Use this at the end of a migration session to verify the work is complete.
"""

from pydantic import BaseModel

from ckeditor_audit.lib.scanner import detect_status, find_pattern_hits
from ckeditor_audit.tools.common import TokenSavings

_TOKENS_PER_FILE = 400


class RemainingHit(BaseModel):
    """A legacy pattern that still needs to be fixed."""

    file: str
    line: int
    legacy: str
    category: str


class ValidateMigrationReport(BaseModel):
    plugin: str
    status: str
    clean: bool
    remaining_hits: list[RemainingHit]
    token_savings: TokenSavings


def validate_migration(plugin: str) -> ValidateMigrationReport:
    """
    Verify that a CKEditor plugin has been fully migrated.

    Returns `clean: true` if no legacy import or API patterns remain.
    Returns `clean: false` with the list of remaining hits otherwise.

    Useful at the end of a migration session, or in an automated check.

    `plugin` must be the plugin directory name, e.g. "ckeditor5-box".
    """
    status = detect_status(plugin)
    hits = find_pattern_hits(plugin)
    files_count = len(set(h.file for h in hits)) if hits else 0

    remaining = [
        RemainingHit(
            file=h.file,
            line=h.line,
            legacy=h.pattern.legacy,
            category=h.pattern.category,
        )
        for h in hits
    ]
    clean = len(remaining) == 0 and status == "migrated"

    return ValidateMigrationReport(
        plugin=plugin,
        status=status,
        clean=clean,
        remaining_hits=remaining,
        token_savings=TokenSavings(
            files_scanned=files_count,
            estimated_tokens_saved=files_count * _TOKENS_PER_FILE,
            note=(
                f"plugin '{plugin}' is {'clean' if clean else 'not clean'} — "
                f"{len(remaining)} legacy hit(s) remaining"
            ),
        ),
    )
