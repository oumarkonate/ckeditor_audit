# Setup & Configuration

## Prerequisites

- Python ≥ 3.10
- Claude Desktop installed (Linux, macOS, or Windows)
- A CKEditor project cloned locally

## 1. Install

```bash
cd /home/konate/IA/mcp/servers/ckeditor_audit
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

What each command does:
- **`python -m venv .venv`** — creates an isolated Python environment in the `.venv/` folder, with its own `python` and `pip` independent from the system.
- **`source .venv/bin/activate`** — activates the environment in the current terminal, redirecting `python` and `pip` to the ones inside `.venv/`. Temporary — only applies to the current terminal session.
- **`pip install -r requirements.txt`** — reads `requirements.txt` and installs each package **inside the active venv** (not system-wide).

## 2. Smoke test (without Claude Desktop)

Run the server directly. It will wait on stdin — that is expected (stdio transport).

```bash
CKEDITOR_AUDIT_PROJECT_ROOT=/path/to/your/project \
  .venv/bin/python -m ckeditor_audit
```

Press `Ctrl+C` to stop.

## 3. Inspect tools with MCP Inspector

The MCP Inspector is an interactive UI to call tools manually and verify their schemas.

```bash
npx @modelcontextprotocol/inspector \
  .venv/bin/python -m ckeditor_audit
```

Set the `CKEDITOR_AUDIT_PROJECT_ROOT` env var in the Inspector UI before calling tools.

## 4. Configure environment variables

Project-specific settings are stored in a `.env` file at the server root — **never committed to git**.

```bash
cp .env.example .env
# Edit .env and set at least CKEDITOR_AUDIT_PROJECT_ROOT
```

Minimum `.env`:
```dotenv
CKEDITOR_AUDIT_PROJECT_ROOT=/path/to/your/project
```

The server loads this file automatically at startup via `python-dotenv`. Any variable already set in the OS environment (or in `claude_desktop_config.json`) takes precedence.

## 5. Register in Claude Desktop

On Linux, the config file is at: `~/.config/Claude/claude_desktop_config.json`

Add the following block (merge with existing `mcpServers` if present):

```json
{
  "mcpServers": {
    "ckeditor-audit": {
      "command": "/path/to/mcp/servers/ckeditor_audit/.venv/bin/python3",
      "args": ["-m", "ckeditor_audit"],
      "env": {
        "PYTHONPATH": "/path/to/mcp/servers"
      }
    }
  }
}
```

> **Note:** `PYTHONPATH` must point to the **parent directory** of `ckeditor_audit/` so that `python -m ckeditor_audit` can resolve the package. Project-specific variables go in `.env`.

Fully quit and restart Claude Desktop after any change to this file (no hot-reload).

## 6. Environment variables reference

### CKEditor audit variables

| Variable | Where to set | Default | Description |
|---|---|---|---|
| `CKEDITOR_AUDIT_PROJECT_ROOT` | `.env` | *(required)* | Absolute path to the project root |
| `CKEDITOR_AUDIT_EXTRA_GLOBS` | `.env` | *(empty)* | Comma-separated additional globs to include in usage search |
| `CKEDITOR_AUDIT_PLUGINS_GLOB` | `.env` | `assets/ckeditor/ckeditor5-*` | Glob to discover plugin directories |
| `CKEDITOR_AUDIT_CONFIGS_GLOB` | `.env` | `assets/config/ckeditor/*_config.js` | Glob to discover config files |
| `CKEDITOR_AUDIT_LEGACY_LABEL` | `.env` | `legacy` | Display label for the source version (e.g. `v26`) |
| `CKEDITOR_AUDIT_TARGET_LABEL` | `.env` | `latest` | Display label for the target version (e.g. `v47`) |

These two labels are cosmetic — they appear in audit reports so Claude can name the versions clearly. Set them to match your actual migration:

```dotenv
# Migrating from CKEditor 5 v26 to v47
CKEDITOR_AUDIT_LEGACY_LABEL=v26
CKEDITOR_AUDIT_TARGET_LABEL=v47
```

The patterns that are actually detected come from `servers/ckeditor_audit/lib/patterns.py`. The labels tell Claude *how to name* the versions; the patterns table tells it *what to look for*.

### Generic file search variables

| Variable | Where to set | Default | Description |
|---|---|---|---|
| `CKEDITOR_AUDIT_EXCLUDE_DIRS` | `.env` | `node_modules,.git,dist,build,vendor` | Comma-separated directory names to skip in `find_files`, `grep_code`, `grep_with_context`, `count_matches` |
| `CKEDITOR_AUDIT_MAX_RESULTS` | `.env` | `50` | Maximum number of matches returned by `find_files`, `grep_code`, `grep_with_context` |

### Claude Desktop variable

| Variable | Where to set | Default | Description |
|---|---|---|---|
| `PYTHONPATH` | `claude_desktop_config.json` | *(required)* | Python module resolution — must point to the parent directory of `ckeditor_audit/` |

The default globs match a standard project layout. Override them in `.env` if your project uses a different structure.

### CKEDITOR_AUDIT_EXTRA_GLOBS — extending the usage search

By default, `find_usages` and `audit_plugin` only scan the files matched by `CKEDITOR_AUDIT_CONFIGS_GLOB`. Use `CKEDITOR_AUDIT_EXTRA_GLOBS` to also search entry files, YAML configs, PHP constants, or JS plugin registries.

Each file reference is reported with two flags:
- `active: true` — the plugin is referenced in an uncommented line (currently in use)
- `commented: true` — the plugin is referenced only in commented code (disabled or pending migration)

Example `.env` entry for a project with multiple registry files:

```dotenv
CKEDITOR_AUDIT_EXTRA_GLOBS=assets/ckeditor/ckeditor.js,config/editor/ckeditor5.yaml,src/Form/CKEditorType.php,assets/config/ckeditor/plugins.js
```

The comment detection is a line-level heuristic: a line is considered commented if its first non-whitespace characters are `//`, `#`, `*`, or `/*`. This covers JS, PHP, and YAML.

## 6. Verify in Claude Desktop

After restarting, open a new conversation. The MCP tools icon should list `ckeditor-audit` with its 11 tools.

**Audit tools:**

> Use `audit_all` to give me the migration status of all CKEditor plugins

> Use `audit_plugin` on "ckeditor5-box"

> Use `find_usages` on "ckeditor5-box"

> Use `list_patterns` to show me all known legacy patterns

**Generic search tools:**

> Use `find_files` to find all files whose name contains "plugin" with extension "js"

> Use `count_matches` to count how many times "ClassicEditor" appears in js files

> Use `grep_code` to search for `from '@ckeditor` in js and ts files

> Use `grep_with_context` on `import.*ckeditor5` with 5 context lines in the assets directory

> Use `read_file` to read "assets/ckeditor/ckeditor5-box/src/box.js"

**Git-aware tools:**

> Use `git_changed_files` to list all unstaged changes

> Use `grep_changed` to search for "@ckeditor" only in modified files

## 7. Troubleshooting

- **Tool not listed** → check the absolute path to the venv Python binary
- **`RuntimeError: CKEDITOR_AUDIT_PROJECT_ROOT is not set`** → the `env` block in the config is missing or misplaced
- **Logs** → `~/.config/Claude/logs/mcp-server-ckeditor-audit.log`
- Always restart Claude Desktop fully after config changes

## 8. Adding new patterns

When a migration reveals a new legacy → latest pattern, add it to `lib/patterns.py` and restart Claude Desktop.
