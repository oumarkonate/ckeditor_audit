# Setup & Configuration

## Prerequisites

- Python ≥ 3.10
- Claude Desktop installed (Linux, macOS, or Windows)
- A CKEditor project cloned locally

## 1. Install

**macOS / Linux**

```bash
cd /path/to/mcp/ckeditor_audit
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

**Windows (PowerShell)**

```powershell
cd C:\path\to\mcp\ckeditor_audit
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
```

> No need to activate the venv — calling `.venv\Scripts\pip` directly installs into the correct environment.

What each command does:
- **`python -m venv .venv`** — creates an isolated Python environment in the `.venv/` folder, with its own `python` and `pip` independent from the system.
- **`pip install -r requirements.txt`** — installs each package inside the venv (not system-wide).

## 2. Smoke test (without Claude Desktop)

Run the server directly. It will wait on stdin — that is expected (stdio transport).

**macOS / Linux**

```bash
CKEDITOR_AUDIT_PROJECT_ROOT=/path/to/your/project \
  .venv/bin/python3 -m ckeditor_audit
```

**Windows (PowerShell)**

```powershell
$env:PYTHONPATH = "C:\path\to\mcp"
$env:CKEDITOR_AUDIT_PROJECT_ROOT = "C:\path\to\your\project"
& "C:\path\to\mcp\ckeditor_audit\.venv\Scripts\python.exe" -m ckeditor_audit
```

Press `Ctrl+C` to stop.

## 3. Inspect tools with MCP Inspector

The MCP Inspector is an interactive UI to call tools manually and verify their schemas.

**macOS / Linux**

```bash
npx @modelcontextprotocol/inspector \
  .venv/bin/python3 -m ckeditor_audit
```

**Windows (PowerShell)**

```powershell
npx @modelcontextprotocol/inspector `
  .venv\Scripts\python.exe -m ckeditor_audit
```

Set the `CKEDITOR_AUDIT_PROJECT_ROOT` env var in the Inspector UI before calling tools.

## 4. Configure environment variables

Project-specific settings are stored in a `.env` file at the server root — **never committed to git**.

**macOS / Linux**

```bash
cp .env.example .env
```

**Windows (PowerShell)**

```powershell
copy .env.example .env
```

Edit `.env` and set at least `CKEDITOR_AUDIT_PROJECT_ROOT`:

```dotenv
CKEDITOR_AUDIT_PROJECT_ROOT=/path/to/your/project      # macOS / Linux
CKEDITOR_AUDIT_PROJECT_ROOT=C:\path\to\your\project    # Windows
```

The server loads this file automatically at startup via `python-dotenv`. Any variable already set in the OS environment (or in `claude_desktop_config.json`) takes precedence.

## 5. Register in Claude Desktop

Open the configuration file:

- **macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows:** `%APPDATA%\Claude\claude_desktop_config.json`
- **Linux:** `~/.config/Claude/claude_desktop_config.json`

Add the following block (merge with existing `mcpServers` if present):

**macOS / Linux**

```json
{
  "mcpServers": {
    "ckeditor_audit": {
      "command": "/path/to/mcp/ckeditor_audit/.venv/bin/python3",
      "args": ["-m", "ckeditor_audit"],
      "env": {
        "PYTHONPATH": "/path/to/mcp"
      }
    }
  }
}
```

**Windows**

```json
{
  "mcpServers": {
    "ckeditor_audit": {
      "command": "C:\\path\\to\\mcp\\ckeditor_audit\\.venv\\Scripts\\python.exe",
      "args": ["-m", "ckeditor_audit"],
      "env": {
        "PYTHONPATH": "C:\\path\\to\\mcp"
      }
    }
  }
}
```

> `PYTHONPATH` must point to the **parent directory** of `ckeditor_audit/` so that `python -m ckeditor_audit` can resolve the package. Project-specific variables (`CKEDITOR_AUDIT_PROJECT_ROOT`, etc.) go in `.env`.

See `claude_desktop_config.json.linux.example` (Linux/macOS) and `claude_desktop_config.json.windows.example` (Windows) for ready-to-copy templates.

Fully quit and restart Claude Desktop after any change to this file (no hot-reload).

## 6. Register in Claude Code (VS Code / CLI)

Add a `.mcp.json` at the root of your project — same format as above.

## 7. Install Claude Code Skills

The repository ships three slash commands in `skills/`. They live in the project for versioning and
are linked into the global Claude Code skills directory so they are available in every session.

### What gets installed

| Skill | Slash command | Description |
|---|---|---|
| `skills/ckeditor-audit/` | `/ckeditor-audit` | Migration dashboard for all plugins |
| `skills/ckeditor-migrate/` | `/ckeditor-migrate <plugin>` | Full migration workflow for one plugin |
| `skills/ckeditor-report/` | `/ckeditor-report` | Generate the full Markdown/JSON audit report |

### macOS / Linux

```bash
# Create the global skills directory if it doesn't exist yet
mkdir -p ~/.claude/skills

# Create one symlink per skill
ln -s /path/to/mcp/ckeditor_audit/skills/ckeditor-audit   ~/.claude/skills/ckeditor-audit
ln -s /path/to/mcp/ckeditor_audit/skills/ckeditor-migrate ~/.claude/skills/ckeditor-migrate
ln -s /path/to/mcp/ckeditor_audit/skills/ckeditor-report  ~/.claude/skills/ckeditor-report
```

### Windows (PowerShell — run as Administrator)

```powershell
# Create the global skills directory if it doesn't exist yet
New-Item -ItemType Directory -Force "$env:USERPROFILE\.claude\skills"

# Create one symlink per skill
New-Item -ItemType SymbolicLink `
  -Path "$env:USERPROFILE\.claude\skills\ckeditor-audit" `
  -Target "C:\path\to\mcp\ckeditor_audit\skills\ckeditor-audit"

New-Item -ItemType SymbolicLink `
  -Path "$env:USERPROFILE\.claude\skills\ckeditor-migrate" `
  -Target "C:\path\to\mcp\ckeditor_audit\skills\ckeditor-migrate"

New-Item -ItemType SymbolicLink `
  -Path "$env:USERPROFILE\.claude\skills\ckeditor-report" `
  -Target "C:\path\to\mcp\ckeditor_audit\skills\ckeditor-report"
```

> **Why symlinks?** The skill files live in the project so they are versioned alongside the server
> code and updated with `git pull`. The symlinks make them visible to Claude Code globally without
> duplicating the files.

### Verify

In any Claude Code session (Claude Desktop or CLI), type `/` — the three skills should appear in
the autocomplete list. Or try directly:

```
/ckeditor-audit
```

Claude will call `audit_all` and display the migration dashboard.

### Update after `git pull`

No action needed — the symlinks point to the project files, so pulling updates to `skills/` is
immediately reflected in the global skills directory.

### Remove the skills

```bash
# macOS / Linux
rm ~/.claude/skills/ckeditor-audit
rm ~/.claude/skills/ckeditor-migrate
rm ~/.claude/skills/ckeditor-report
```

```powershell
# Windows
Remove-Item "$env:USERPROFILE\.claude\skills\ckeditor-audit"
Remove-Item "$env:USERPROFILE\.claude\skills\ckeditor-migrate"
Remove-Item "$env:USERPROFILE\.claude\skills\ckeditor-report"
```

## 8. Environment variables reference

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

The patterns that are actually detected come from `lib/patterns.py`. The labels tell Claude *how to name* the versions; the patterns table tells it *what to look for*.

### Search engine variables

| Variable | Where to set | Default | Description |
|---|---|---|---|
| `CKEDITOR_AUDIT_EXCLUDE_DIRS` | `.env` | `node_modules,.git,dist,build,vendor,coverage,...` | Comma-separated directory names to skip during file search |
| `CKEDITOR_AUDIT_MAX_RESULTS` | `.env` | `50` | Maximum number of matches returned by `grep`/`find` tools (1–500) |
| `CKEDITOR_AUDIT_EXTENSIONS` | `.env` | `js,ts,jsx,tsx,yaml,yml,php,scss,css` | File extensions searched by `grep_code`, `find_class`, `ast_search`, etc. |
| `CKEDITOR_AUDIT_BACKEND` | `.env` | `auto` | Search backend: `auto` (use ripgrep if found), `rg`, or `python` |
| `CKEDITOR_AUDIT_RESPECT_GITIGNORE` | `.env` | `true` | Whether to honour `.gitignore` when searching |

### Claude Desktop variable

| Variable | Where to set | Default | Description |
|---|---|---|---|
| `PYTHONPATH` | `claude_desktop_config.json` | *(required)* | Must point to the parent directory of `ckeditor_audit/` |

### CKEDITOR_AUDIT_EXTRA_GLOBS — extending the usage search

By default, `find_plugin_usages` and `audit_plugin` only scan the files matched by `CKEDITOR_AUDIT_CONFIGS_GLOB`. Use `CKEDITOR_AUDIT_EXTRA_GLOBS` to also search entry files, YAML configs, PHP constants, or JS plugin registries.

Each file reference is reported with two flags:
- `active: true` — the plugin is referenced in an uncommented line (currently in use)
- `commented: true` — the plugin is referenced only in commented code (disabled or pending migration)

Example `.env` entry for a project with multiple registry files:

```dotenv
CKEDITOR_AUDIT_EXTRA_GLOBS=assets/ckeditor/ckeditor.js,config/editor/ckeditor5.yaml,src/Form/CKEditorType.php,assets/config/ckeditor/plugins.js
```

## 9. Verify in Claude Desktop

After restarting, open a new conversation. The MCP tools icon should list `ckeditor-audit` with its 32 tools.

**Audit tools:**

> Use `audit_all` to give me the migration status of all CKEditor plugins

> Use `audit_plugin` on "ckeditor5-box"

> Use `find_plugin_usages` on "ckeditor5-box"

> Use `list_patterns` to show me all known legacy patterns

**Migration assistance:**

> Use `suggest_migration` on "ckeditor5-image" to get actionable fixes

> Use `validate_migration` on "ckeditor5-box" to confirm it is clean

> Use `export_audit_report` with format="markdown" to get the full report

**Search tools:**

> Use `find_files` to find all files whose name contains "plugin" with extension "js"

> Use `grep_code` to search for `from '@ckeditor` in js and ts files

> Use `find_class` to find the Plugin class

> Use `ast_search` with pattern "class $NAME extends Plugin" and lang "javascript"

**Skills (slash commands):**

> /ckeditor-audit

> /ckeditor-migrate ckeditor5-image

> /ckeditor-report

## 10. Troubleshooting

| Problem | Cause | Fix |
|---|---|---|
| Tool not listed in Claude | Wrong path to `python.exe` | Use the full absolute path to `.venv\Scripts\python.exe` (Windows) or `.venv/bin/python3` (Linux/macOS) |
| `RuntimeError: CKEDITOR_AUDIT_PROJECT_ROOT is not set` | Missing env var | Set it in `.env` or in the `env` block of the config |
| `RuntimeError: does not point to a directory` | Path doesn't exist | Check the path — on Windows use `\\` or `/` as separator |
| Server not appearing after config change | Claude not restarted | Fully quit and reopen Claude Desktop |
| Skill not appearing in `/` autocomplete | Symlink missing or wrong target | Verify with `ls -la ~/.claude/skills/ckeditor-*` (Linux/macOS) or `dir $env:USERPROFILE\.claude\skills` (Windows) |
| **Logs — Linux/macOS** | | `~/.config/Claude/logs/mcp-server-ckeditor-audit.log` |
| **Logs — Windows** | | `%APPDATA%\Claude\logs\mcp-server-ckeditor-audit.log` |

## 11. Adding new patterns

When a migration reveals a new legacy → latest pattern, add it to `lib/patterns.py` and restart Claude Desktop.
