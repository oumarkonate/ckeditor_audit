"""
Pytest fixtures: minimal CKEditor project fixture for testing.

Creates a temporary project with:
- One fully migrated plugin (ckeditor5-box)
- One partially migrated plugin (ckeditor5-toolbar)
- One not-migrated plugin (ckeditor5-image)
- One config file referencing two plugins
"""

import json
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
    (image.parent / "package.json").write_text(
        json.dumps({
            "name": "@acme/ckeditor5-image",
            "version": "1.2.3",
            "dependencies": {
                "@ckeditor/ckeditor5-core": "^41.0.0",
                "@ckeditor/ckeditor5-widget": "^41.0.0",
            },
        }),
        encoding="utf-8",
    )

    # box declares the modern flat package
    (box.parent / "package.json").write_text(
        json.dumps({
            "name": "@acme/ckeditor5-box",
            "version": "2.0.0",
            "dependencies": {"ckeditor5": "^42.0.0"},
        }),
        encoding="utf-8",
    )

    # --- ckeditor5-empty (no CKEditor imports at all) ---
    empty = root / "assets/ckeditor/ckeditor5-empty/src"
    empty.mkdir(parents=True)
    (empty / "noop.js").write_text(
        "export const VERSION = '1.0.0';\n",
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

    # --- Application code (outside the plugins glob) for code-intelligence tools ---
    # A Symfony-style PHP controller: class with extends/implements, a #[Route]
    # attribute, and a method that calls another method.
    app_php = root / "app/Controller"
    app_php.mkdir(parents=True)
    (app_php / "ArticleController.php").write_text(
        "<?php\n"
        "namespace App\\Controller;\n"
        "\n"
        "class ArticleController extends AbstractController implements ControllerInterface\n"
        "{\n"
        "    #[Route('/articles', methods: ['GET'])]\n"
        "    public function list(): Response\n"
        "    {\n"
        "        return $this->render('list.html.twig');\n"
        "    }\n"
        "}\n",
        encoding="utf-8",
    )

    # A JS module with a class, methods, and an internal call (init -> doThing).
    app_js = root / "app/js"
    app_js.mkdir(parents=True)
    (app_js / "widget.js").write_text(
        "export default class CustomWidget extends Plugin {\n"
        "    init() {\n"
        "        this.doThing();\n"
        "    }\n"
        "    doThing() {}\n"
        "}\n",
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
