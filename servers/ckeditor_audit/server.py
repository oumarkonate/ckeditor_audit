"""
MCP server entry point.

MCPServer is the high-level class from the official MCP Python SDK.
It was previously named FastMCP and renamed in v1.12+.

Each tool is registered via the @mcp.tool() decorator defined in its own module.
MCPServer reads the function's type hints to auto-generate the JSON input/output
schemas that Claude uses to call the tool correctly.
"""

import logging
import sys

from mcp.server.mcpserver import MCPServer

from ckeditor_audit.tools.audit_all import audit_all
from ckeditor_audit.tools.audit_plugin import audit_plugin
from ckeditor_audit.tools.count_matches import count_matches
from ckeditor_audit.tools.find_files import find_files
from ckeditor_audit.tools.find_usages import find_usages
from ckeditor_audit.tools.git_tools import git_changed_files, grep_changed
from ckeditor_audit.tools.grep_code import grep_code
from ckeditor_audit.tools.grep_with_context import grep_with_context
from ckeditor_audit.tools.list_patterns import list_patterns
from ckeditor_audit.tools.read_file import read_file

# ---------------------------------------------------------------------------
# Logging — must go to stderr (stdout is reserved for JSON-RPC on stdio transport)
# Claude Desktop captures stderr and writes it to:
#   ~/.config/Claude/logs/mcp-server-ckeditor-audit.log
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger("ckeditor-audit")

# ---------------------------------------------------------------------------
# Server declaration
# ---------------------------------------------------------------------------

mcp = MCPServer(
    name="ckeditor-audit",
    title="CKEditor Migration Audit",
    description=(
        "Read-only audit server for CKEditor custom plugins. "
        "Reports migration status, detects legacy patterns, and maps plugin/config dependencies."
    ),
)

# ---------------------------------------------------------------------------
# Tool registration
# Each function is wrapped with @mcp.tool() so MCPServer exposes it to Claude.
# The docstring becomes the tool description visible in Claude Desktop.
# The type hints become the JSON schema for inputs and outputs.
# ---------------------------------------------------------------------------

# --- Audit tools (CKEditor-specific) ---
mcp.tool()(list_patterns)
mcp.tool()(audit_plugin)
mcp.tool()(audit_all)
mcp.tool()(find_usages)

# --- Generic file search tools ---
mcp.tool()(find_files)
mcp.tool()(grep_code)
mcp.tool()(grep_with_context)
mcp.tool()(read_file)
mcp.tool()(count_matches)

# --- Git-aware search tools ---
mcp.tool()(git_changed_files)
mcp.tool()(grep_changed)

logger.info("ckeditor-audit server ready — 11 tools registered")
