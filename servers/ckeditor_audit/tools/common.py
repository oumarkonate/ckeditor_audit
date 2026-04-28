from pydantic import BaseModel


class TokenSavings(BaseModel):
    """Estimated token savings from using this MCP tool instead of direct file reads."""

    files_scanned: int
    estimated_tokens_saved: int
    note: str