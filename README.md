# ckeditor-audit MCP server

A read-only MCP server that audits CKEditor custom plugins and reports their migration status from a legacy version to the latest.

## Why this server exists — token savings

When Claude migrates a CKEditor plugin without this server, it typically reads 3–10 files to collect the information it needs:

- the plugin source (`plugin.js`, `index.js`) to detect legacy patterns
- the plugin manifest (`package.json`) for the version
- config files (`ckeditor.js`, `ckeditor5.yaml`, …) to know where the plugin is used

On a project with ~20 plugins that costs **6 000–15 000 tokens** just for discovery, before any migration work starts. In a long session, repeated re-reads multiply that cost further.

This server pre-indexes all of that. One `audit_plugin` call returns a ~200-token report covering status, detected patterns, and config references. One `audit_all` call covers the entire project in a single round-trip.

**Typical saving: 80–95 % of discovery tokens per migration session.**

The server also improves accuracy: it catches usages in commented-out code and searches across all relevant file types (JS entry files, YAML configs, PHP constants, plugin registries) — coverage that ad-hoc `grep` calls during a session often miss.

## Tools

| Tool | Description |
|---|---|
| `list_patterns` | Returns the known legacy → latest pattern mapping table |
| `audit_plugin` | Detailed migration report for a single plugin |
| `audit_all` | Summary migration status for all detected plugins |
| `find_usages` | Lists config files that reference a given plugin |

## Quick test

Once installed, open a new conversation in Claude Desktop and try:

```
Use audit_all to give me the migration status of all CKEditor plugins
Use audit_plugin on "ckeditor5-box"
Use find_usages on "ckeditor5-box"
Use list_patterns to show me all known legacy patterns
```

## Setup

See [SETUP.md](SETUP.md) for step-by-step installation and Claude Desktop configuration.
