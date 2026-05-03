"""
Server configuration loaded from environment variables.

All CKEDITOR_AUDIT_* variables are read once at import time so every tool
module can simply do `from ckeditor_audit.config import settings`.
"""

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    # Absolute path to the project being audited (required)
    project_root: Path

    # Glob pattern (relative to project_root) that matches plugin directories
    plugins_glob: str

    # Glob pattern (relative to project_root) that matches config JS files
    configs_glob: str

    # Additional glob patterns to include in usage search (e.g. entry files, YAML configs)
    # Comma-separated. Covers files that live outside the configs_glob scope.
    extra_globs: tuple[str, ...]

    # Human-readable labels used in reports (e.g. "v26" / "v47")
    legacy_label: str
    target_label: str

    # Directory names to skip during generic file searches
    exclude_dirs: tuple[str, ...]

    # Maximum number of results returned by grep/find tools
    max_results: int


def _load() -> Settings:
    raw_root = os.environ.get("CKEDITOR_AUDIT_PROJECT_ROOT", "").strip()
    if not raw_root:
        raise RuntimeError(
            "CKEDITOR_AUDIT_PROJECT_ROOT is not set. "
            "Add it to the 'env' block in your claude_desktop_config.json."
        )

    project_root = Path(raw_root)
    if not project_root.is_dir():
        raise RuntimeError(
            f"CKEDITOR_AUDIT_PROJECT_ROOT does not point to a directory: {project_root}"
        )

    # CKEDITOR_AUDIT_EXTRA_GLOBS: comma-separated list of additional globs to scan
    # for plugin usages (active or commented). Leave empty to disable.
    raw_extra = os.environ.get("CKEDITOR_AUDIT_EXTRA_GLOBS", "").strip()
    extra_globs = tuple(g.strip() for g in raw_extra.split(",") if g.strip())

    raw_exclude = os.environ.get(
        "CKEDITOR_AUDIT_EXCLUDE_DIRS", "node_modules,.git,dist,build,vendor"
    ).strip()
    exclude_dirs = tuple(d.strip() for d in raw_exclude.split(",") if d.strip())

    return Settings(
        project_root=project_root,
        plugins_glob=os.environ.get(
            "CKEDITOR_AUDIT_PLUGINS_GLOB", "assets/ckeditor/ckeditor5-*"
        ),
        configs_glob=os.environ.get(
            "CKEDITOR_AUDIT_CONFIGS_GLOB", "assets/config/ckeditor/*_config.js"
        ),
        extra_globs=extra_globs,
        legacy_label=os.environ.get("CKEDITOR_AUDIT_LEGACY_LABEL", "legacy"),
        target_label=os.environ.get("CKEDITOR_AUDIT_TARGET_LABEL", "latest"),
        exclude_dirs=exclude_dirs,
        max_results=int(os.environ.get("CKEDITOR_AUDIT_MAX_RESULTS", "50")),
    )


# Module-level singleton — loaded once when the server starts
settings = _load()
