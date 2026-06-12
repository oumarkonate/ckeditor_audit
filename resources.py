"""
MCP Resources for ckeditor-audit.

Expose static data as MCP Resources so clients can read them without
a tool call.
"""

import json

from ckeditor_audit.lib.patterns import PATTERNS


def register_resources(mcp) -> None:
    """Register all MCP resources on the given MCPServer instance."""

    @mcp.resource("ckeditor://patterns")
    def patterns_resource() -> str:
        """
        Legacy → latest CKEditor migration patterns.

        Returns the full JSON table of known patterns: legacy signature,
        modern replacement, description, and category (import | api | schema | utils).
        """
        data = [p.model_dump() for p in PATTERNS]
        return json.dumps(data, indent=2, ensure_ascii=False)
