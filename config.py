"""
Server configuration loaded from environment variables.

All CKEDITOR_AUDIT_* variables are read once at import time so every tool
module can simply do `from ckeditor_audit.config import settings`.
"""

import logging
import os
import shutil
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger("ckeditor_audit.config")


@dataclass(frozen=True)
class Settings:
    # --- CKEditor-specific ---
    # Absolute path to the project being audited (required)
    project_root: Path

    # Glob pattern (relative to project_root) that matches plugin directories
    plugins_glob: str

    # Glob pattern (relative to project_root) that matches config JS files
    configs_glob: str

    # Additional glob patterns to include in usage search (e.g. entry files, YAML configs)
    extra_globs: tuple[str, ...]

    # Human-readable labels used in reports (e.g. "v26" / "v47")
    legacy_label: str
    target_label: str

    # --- Search engine ---
    # Directory names to skip during generic file searches
    exclude_dirs: frozenset[str]

    # Maximum number of results returned by grep/find tools
    max_results: int

    # File extensions to search (without dot)
    extensions: tuple[str, ...]

    # Search backend: "rg" | "python"
    backend: str

    # Whether ripgrep binary is available
    rg_available: bool

    # Whether ast-grep-py is installed
    ast_grep_available: bool

    # Whether to respect .gitignore when searching
    respect_gitignore: bool


def _probe_rg() -> str | None:
    """Return path to rg binary, or None if not found."""
    found = shutil.which("rg")
    if found:
        return found
    home = os.path.expanduser("~")
    for path in [f"{home}/.local/bin/rg", "/usr/local/bin/rg", "/usr/bin/rg", "/snap/bin/rg"]:
        if shutil.which(path):
            return path
    return None


def _probe_ast_grep() -> bool:
    try:
        from ast_grep_py import SgRoot  # noqa: F401
        return True
    except ImportError:
        return False


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

    raw_extra = os.environ.get("CKEDITOR_AUDIT_EXTRA_GLOBS", "").strip()
    extra_globs = tuple(g.strip() for g in raw_extra.split(",") if g.strip())

    raw_exclude = os.environ.get(
        "CKEDITOR_AUDIT_EXCLUDE_DIRS",
        "node_modules,.git,dist,build,vendor,coverage,.nyc_output,__pycache__,.next,.cache",
    ).strip()
    exclude_dirs = frozenset(d.strip() for d in raw_exclude.split(",") if d.strip())

    max_results = max(1, min(500, int(os.environ.get("CKEDITOR_AUDIT_MAX_RESULTS", "50"))))

    raw_ext = os.environ.get("CKEDITOR_AUDIT_EXTENSIONS", "js,ts,jsx,tsx,yaml,yml,php,scss,css")
    extensions = tuple(e.strip().lstrip(".") for e in raw_ext.split(",") if e.strip())

    rg_path = _probe_rg()
    rg_available = rg_path is not None
    ast_grep_available = _probe_ast_grep()

    requested_backend = os.environ.get("CKEDITOR_AUDIT_BACKEND", "auto").lower()
    if requested_backend == "auto":
        backend = "rg" if rg_available else "python"
    elif requested_backend == "rg":
        backend = "rg" if rg_available else "python"
    else:
        backend = "python"

    # Export rg path so backends can use it directly
    if rg_path and rg_path != "rg":
        os.environ.setdefault("CKEDITOR_AUDIT_RG_PATH", rg_path)

    respect_gitignore = os.environ.get(
        "CKEDITOR_AUDIT_RESPECT_GITIGNORE", "true"
    ).lower() in ("1", "true", "yes")

    logger.info(
        "backend=%s rg=%s ast_grep=%s respect_gitignore=%s",
        backend, rg_available, ast_grep_available, respect_gitignore,
    )

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
        max_results=max_results,
        extensions=extensions,
        backend=backend,
        rg_available=rg_available,
        ast_grep_available=ast_grep_available,
        respect_gitignore=respect_gitignore,
    )


# Module-level singleton — loaded once when the server starts
settings = _load()
