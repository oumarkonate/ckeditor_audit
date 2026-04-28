"""
Package entry point — enables `python -m ckeditor_audit`.

Calling mcp.run() with no arguments uses the stdio transport by default.
stdio is what Claude Desktop expects: it spawns this process and communicates
through stdin/stdout. No port, no HTTP server.
"""

from pathlib import Path

from dotenv import load_dotenv

# Load project-specific env vars from .env at the server root (not versioned).
# Path resolution: __file__ is servers/ckeditor_audit/__main__.py
#   → .parent       = servers/ckeditor_audit/
#   → .parent.parent = servers/
#   → .parent.parent.parent = ckeditor_audit/  (server root, where .env lives)
# Falls back silently if the file doesn't exist.
# Does NOT override vars already set in the environment (e.g. from claude_desktop_config.json).
_env_file = Path(__file__).parent.parent.parent / ".env"
load_dotenv(_env_file)

from ckeditor_audit.server import mcp  # noqa: E402 — must come after load_dotenv


def main() -> None:
    mcp.run()  # stdio transport — process stays alive, reads from stdin


if __name__ == "__main__":
    main()