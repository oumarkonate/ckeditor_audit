"""
Pytest fixtures: minimal CKEditor project fixture for testing.

Creates a temporary project with:
- One fully migrated plugin (ckeditor5-box)
- One partially migrated plugin (ckeditor5-toolbar)
- One not-migrated plugin (ckeditor5-image)
- One config file referencing two plugins
"""

import os
import pytest


@pytest.fixture(scope="session")
def project_root(tmp_path_factory):
    root = tmp_path_factory.mktemp("ckeditor_project")

    # --- ckeditor5-box (migrated) ---
    box = root / "assets/ckeditor/ckeditor5-box/src"
    box.mkdir(parents=True)
    (box / "box.js").write_text(
        "import { Plugin } from 'ckeditor5';\n"
        "import { Widget } from 'ckeditor5';\n"
        "export default class Box extends Plugin {}\n",
        encoding="utf-8",
    )

    # --- ckeditor5-toolbar (partial) ---
    toolbar = root / "assets/ckeditor/ckeditor5-toolbar/src"
    toolbar.mkdir(parents=True)
    (toolbar / "toolbar.js").write_text(
        "import { Plugin } from 'ckeditor5';\n"
        "import ToolbarPlugin from '@ckeditor/ckeditor5-ui/src/toolbar/toolbar';\n",
        encoding="utf-8",
    )

    # --- ckeditor5-image (not migrated) ---
    image = root / "assets/ckeditor/ckeditor5-image/src"
    image.mkdir(parents=True)
    (image / "image.js").write_text(
        "import Plugin from '@ckeditor/ckeditor5-core/src/plugin';\n"
        "import Command from '@ckeditor/ckeditor5-core/src/command';\n"
        "const schema = { allowIn: 'root' };\n",
        encoding="utf-8",
    )

    # --- Config file referencing plugins ---
    config_dir = root / "assets/config/ckeditor"
    config_dir.mkdir(parents=True)
    (config_dir / "article_config.js").write_text(
        "import ckeditor5Box from 'ckeditor5-box';\n"
        "// import ckeditor5Image from 'ckeditor5-image'; // disabled\n",
        encoding="utf-8",
    )

    return root


@pytest.fixture(scope="session", autouse=True)
def configure_env(project_root):
    """Set all required env vars before any test imports ckeditor_audit."""
    os.environ["CKEDITOR_AUDIT_PROJECT_ROOT"] = str(project_root)
    os.environ["CKEDITOR_AUDIT_PLUGINS_GLOB"] = "assets/ckeditor/ckeditor5-*"
    os.environ["CKEDITOR_AUDIT_CONFIGS_GLOB"] = "assets/config/ckeditor/*_config.js"
    os.environ["CKEDITOR_AUDIT_EXTRA_GLOBS"] = ""
    os.environ["CKEDITOR_AUDIT_BACKEND"] = "python"  # deterministic, no ripgrep required
    os.environ["CKEDITOR_AUDIT_EXTENSIONS"] = "js,ts,jsx,tsx,yaml,php"
    os.environ["CKEDITOR_AUDIT_MAX_RESULTS"] = "50"
    yield
