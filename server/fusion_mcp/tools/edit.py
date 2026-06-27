"""Timeline / editing tools: undo, redo, delete-all, suppress features."""

from ._helpers import anno


def register(mcp, client):
    @mcp.tool(annotations=anno())
    def fusion_undo() -> dict:
        """Undo the last operation (guards against a parametric->direct design flip)."""
        return client.call("edit.undo")

    @mcp.tool(annotations=anno())
    def fusion_redo() -> dict:
        """Redo the last undone operation."""
        return client.call("edit.redo")

    @mcp.tool(annotations=anno(destructive=True))
    def fusion_delete_all() -> dict:
        """Delete every timeline feature, clearing the design. Destructive."""
        return client.call("edit.delete_all")

    @mcp.tool(annotations=anno(idempotent=True))
    def fusion_suppress_feature(name: str) -> dict:
        """Suppress a timeline feature by name (from fusion_list_features)."""
        return client.call("edit.suppress_feature", {"name": name})

    @mcp.tool(annotations=anno(idempotent=True))
    def fusion_unsuppress_feature(name: str) -> dict:
        """Unsuppress a timeline feature by name."""
        return client.call("edit.unsuppress_feature", {"name": name})
