"""Shared helpers for tool modules."""

from mcp.types import ToolAnnotations


def anno(readonly=False, destructive=False, idempotent=False, open_world=True):
    """Build MCP tool annotations.

    Hints let clients (e.g. Claude) auto-approve safe (read-only) operations and
    warn before destructive ones.
    """
    return ToolAnnotations(
        readOnlyHint=readonly,
        destructiveHint=destructive,
        idempotentHint=idempotent,
        openWorldHint=open_world,
    )
