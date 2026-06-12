"""
MCP Prompts for ckeditor-audit.

Expose guided prompts that assemble context-rich messages for common
migration workflows, using the MCP Prompts primitive.
"""

from mcp.types import PromptMessage, TextContent

from ckeditor_audit.lib.scanner import detect_status, find_pattern_hits, list_plugins


def register_prompts(mcp) -> None:
    """Register all MCP prompts on the given MCPServer instance."""

    @mcp.prompt()
    def migrate_plugin(plugin: str) -> list[PromptMessage]:
        """
        Guided step-by-step prompt for migrating a CKEditor plugin.

        Assembles the plugin's current migration status, detected legacy patterns,
        and concrete instructions — ready to paste into a Claude conversation.

        `plugin` must be the plugin directory name, e.g. "ckeditor5-box".
        """
        status = detect_status(plugin)
        hits = find_pattern_hits(plugin)
        all_plugins = list_plugins()

        status_line = {
            "migrated": "✅ Fully migrated — no legacy imports detected.",
            "partial": "⚠️ Partially migrated — legacy and modern imports coexist.",
            "not_migrated": "❌ Not migrated — only legacy imports found.",
            "no_imports": "➖ No CKEditor imports — nothing to migrate.",
        }.get(status, f"Unknown status: {status}")

        lines = [
            f"# Migrate CKEditor plugin: `{plugin}`",
            "",
            f"**Migration status:** {status_line}",
            "",
        ]

        if hits:
            lines += [
                "## Detected legacy patterns",
                "",
                "| File | Line | Legacy | Replacement |",
                "|------|------|--------|-------------|",
            ]
            for h in hits:
                legacy_short = h.matched[:50].replace("|", "\\|")
                repl_short = h.pattern.replacement[:50].replace("|", "\\|")
                lines.append(f"| `{h.file}` | {h.line} | `{legacy_short}` | `{repl_short}` |")
            lines.append("")
            lines += [
                "## Step-by-step migration guide",
                "",
                "For each entry in the table above:",
                "1. Open the file at the given line.",
                "2. Replace the **legacy** import/API with the **replacement** shown.",
                "3. After all changes, run `validate_migration` to confirm clean status.",
                "",
                "### Pattern details",
                "",
            ]
            seen = set()
            for h in hits:
                key = h.matched
                if key not in seen:
                    seen.add(key)
                    lines += [
                        f"**{h.pattern.category.upper()}** — `{h.matched}`",
                        f"→ `{h.pattern.replacement}`",
                        f"_{h.pattern.description}_",
                        "",
                    ]
        else:
            lines += [
                "No legacy patterns detected. Run `validate_migration` to confirm.",
                "",
            ]

        lines += [
            "---",
            f"_Available plugins: {', '.join(f'`{p}`' for p in all_plugins)}_",
        ]

        return [
            PromptMessage(
                role="user",
                content=TextContent(type="text", text="\n".join(lines)),
            )
        ]
