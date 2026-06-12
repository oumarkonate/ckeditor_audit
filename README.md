# ckeditor-audit MCP server

A read-only MCP server that audits CKEditor custom plugins, reports migration status, and provides full-featured code search powered by ripgrep and ast-grep.

## Why this server exists — token savings

When Claude migrates a CKEditor plugin without this server, it typically reads 3–10 files to collect the information it needs:

- the plugin source (`plugin.js`, `index.js`) to detect legacy patterns
- the plugin manifest (`package.json`) for the version
- config files (`ckeditor.js`, `ckeditor5.yaml`, …) to know where the plugin is used

On a project with ~20 plugins that costs **6 000–15 000 tokens** just for discovery, before any migration work starts. In a long session, repeated re-reads multiply that cost further.

This server pre-indexes all of that. One `audit_plugin` call returns a ~200-token report covering status, detected patterns, and config references. One `audit_all` call covers the entire project in a single round-trip.

**Typical saving: 80–95 % of discovery tokens per migration session.**

The server also improves accuracy: it catches usages in commented-out code and searches across all relevant file types (JS entry files, YAML configs, PHP constants, plugin registries) — coverage that ad-hoc `grep` calls during a session often miss.

## Tools (32 total)

### CKEditor audit tools (domain-specific)

| Tool | Description |
|---|---|
| `list_patterns` | Returns the known legacy → latest pattern mapping table |
| `audit_plugin` | Detailed migration report for a single plugin (issues, config refs, file list) |
| `audit_all` | Summary migration status for all detected plugins |
| `find_plugin_usages` | Lists config files that reference a given plugin (active vs commented) |

### Migration assistance tools

| Tool | Description |
|---|---|
| `suggest_migration` | For each legacy pattern detected, returns file, line, legacy signature, and modern replacement — ready to apply |
| `validate_migration` | Confirms no legacy signatures remain in a plugin; returns `clean: true` when fully migrated |
| `export_audit_report` | Generates a full Markdown or JSON report for all plugins; writes to file if `output_path` is provided |

### Navigation & file I/O

| Tool | Description |
|---|---|
| `find_files` | Find project files by name pattern (case-insensitive, optional extension filter) |
| `directory_tree` | Show directory structure as a tree (configurable depth, extension filter) |
| `read_file` | Read any project file by relative path, in 200-line chunks |
| `get_file_outline` | List classes, methods, and functions with line numbers (AST-backed for JS/TS) |

### Search (ripgrep-backed, 10-100× faster when `rg` is installed)

| Tool | Description |
|---|---|
| `grep_code` | Regex/text search — smart-case, ranking, pagination, compact output |
| `grep_with_context` | Same as `grep_code` with N surrounding lines (default ±3, max ±10) |
| `count_matches` | Count occurrences without fetching snippets — use before `grep_code` to gauge scope |
| `multi_search` | Run up to 10 `grep_code` queries in parallel |

### AST structural search

| Tool | Description |
|---|---|
| `ast_search` | Find code by structure, not text — supports JS, TS, TSX, PHP. Pattern syntax: `class $NAME extends $BASE` |

### Code intelligence

| Tool | Description |
|---|---|
| `find_class` | Find class/interface declarations by name (AST-backed for JS/TS/PHP) |
| `find_method` | Find method/function declarations, optionally scoped to a class |
| `find_implementations` | Find classes implementing a given interface |
| `find_extends` | Find classes extending a given base class |
| `find_definition` | Universal lookup: class → method → route → grep fallback |
| `find_usages` | Find all usages of a code symbol, ranked by relevance |
| `who_calls` | Find all call sites of a method, with the enclosing caller name |
| `what_calls` | Find all outgoing calls from a method body |

### Framework-specific

| Tool | Description |
|---|---|
| `find_route` | Find Symfony routes (PHP 8 attributes, annotations, YAML) |
| `find_tests` | Find test files for a source file (PHPUnit, Jest, Playwright) |
| `find_source` | Inverse: find the source file for a test file |

### Git-aware search

| Tool | Description |
|---|---|
| `git_changed_files` | List files changed in the git working tree (unstaged / staged / all / SHA) |
| `grep_changed` | Run a pattern search restricted to git-changed files |
| `find_in_file_diff` | Get git hunk line ranges for a file |

## MCP Resources & Prompts

### Resources
- `ckeditor://patterns` — The full legacy → latest pattern table as JSON. Read without a tool call.

### Prompts
- `migrate_plugin(plugin)` — Guided step-by-step migration prompt: assembles current status, detected legacy patterns, and concrete instructions.

## Claude Code Skills (slash commands)

Three skills are bundled in `skills/` and made globally available via symlinks in `~/.claude/skills/`:

| Skill | Command | Description |
|---|---|---|
| `ckeditor-audit` | `/ckeditor-audit` | Migration dashboard — overview of all plugins (status, issue counts, config refs) |
| `ckeditor-migrate` | `/ckeditor-migrate <plugin>` | Full migration workflow for one plugin: audit → suggest fixes → apply → validate |
| `ckeditor-report` | `/ckeditor-report` | Generate and display the full Markdown/JSON audit report |

Skills are **user-invocable** (type the slash command) and also **auto-triggered** when you mention CKEditor migration in conversation. See [SETUP.md — Skills](SETUP.md#7-install-claude-code-skills) for the symlink setup.

## Quick test

Once installed, open a new conversation in Claude Desktop and try:

```
Use audit_all to give me the migration status of all CKEditor plugins
Use suggest_migration on "ckeditor5-image" to get actionable fixes
Use validate_migration on "ckeditor5-box" to confirm it's clean
Use export_audit_report with format="markdown" to get a full report

Use grep_code to search for "from '@ckeditor" in js files
Use find_class to find the Box class
Use who_calls on method "init"
Use ast_search with pattern "class $NAME extends Plugin" and lang "javascript"
```

## Dependencies

### Python packages (auto-installed via `pip install -r requirements.txt`)
- `mcp` — Official MCP Python SDK
- `pydantic>=2.0` — Structured tool outputs
- `python-dotenv>=1.0` — `.env` loading
- `rapidfuzz>=3.0` — Fuzzy matching for symbol searches (gracefully absent)
- `ast-grep-py>=0.38` — AST structural search for JS/TS/PHP (gracefully absent)
- `pathspec>=0.12` — `.gitignore` integration

### System binary (optional, strongly recommended)
- **ripgrep** (`rg`) — 10-100× faster grep. Install via:
  - Linux: `sudo apt install ripgrep` or `cargo install ripgrep`
  - macOS: `brew install ripgrep`
  - Windows: `winget install BurntSushi.ripgrep.MSVC`

When `rg` is not found, the server falls back to Python `re` — all tools still work.

## Setup

See [SETUP.md](SETUP.md) for step-by-step installation and Claude Desktop configuration.
