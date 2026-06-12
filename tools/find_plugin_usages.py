"""
Tool: find_plugin_usages

Returns which files reference a given CKEditor plugin, and whether those references
are active (uncommented) or commented out.

Scans CKEDITOR_AUDIT_CONFIGS_GLOB and CKEDITOR_AUDIT_EXTRA_GLOBS so that
entry files, YAML configs, PHP constants, and JS plugin registries are all
covered when the project owner configures the extra globs.
"""

from pydantic import BaseModel

from ckeditor_audit.lib.scanner import configs_using
from ckeditor_audit.tools.common import TokenSavings

_TOKENS_PER_CONFIG_FILE = 300


class FileUsage(BaseModel):
    """How a plugin is referenced in one file."""

    # Path relative to the project root (e.g. "assets/config/ckeditor/article_config.js")
    file: str

    # True if at least one uncommented line references the plugin
    active: bool

    # True if at least one commented line references the plugin
    # (plugin was used but may have been disabled / not yet migrated)
    commented: bool


class FindPluginUsagesReport(BaseModel):
    """Result of find_plugin_usages: matched files and token savings metadata."""

    usages: list[FileUsage]
    token_savings: TokenSavings


def find_plugin_usages(plugin: str) -> FindPluginUsagesReport:
    """
    Return the list of config files that reference the given CKEditor plugin.

    `plugin` must be the plugin directory name, e.g. "ckeditor5-box".

    Each entry reports whether the reference is active (plugin currently in use),
    commented (plugin disabled or pending), or both.

    Configure CKEDITOR_AUDIT_EXTRA_GLOBS to extend the search beyond the
    default config files — for example to include the main entry file,
    YAML configs, or PHP plugin constants.

    An empty list means the plugin is not referenced anywhere in the scanned files.

    Note: use `find_usages` (the generic symbol search tool) to search for
    any code symbol across the whole codebase.
    """
    raw, n_candidates = configs_using(plugin)
    usages = [
        FileUsage(file=u.file, active=u.active, commented=u.commented)
        for u in raw
    ]
    estimated_saved = n_candidates * _TOKENS_PER_CONFIG_FILE
    return FindPluginUsagesReport(
        usages=usages,
        token_savings=TokenSavings(
            files_scanned=n_candidates,
            estimated_tokens_saved=estimated_saved,
            note=(
                f"scanned {n_candidates} config file(s), "
                f"found {len(usages)} reference(s) to '{plugin}'"
            ),
        ),
    )
