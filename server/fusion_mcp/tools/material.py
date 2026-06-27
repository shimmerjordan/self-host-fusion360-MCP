"""Appearance / material tools."""

from typing import Union

from ._helpers import anno


def register(mcp, client):
    @mcp.tool(annotations=anno(readonly=True))
    def fusion_list_appearances(filter: str = "", limit: int = 100) -> dict:
        """List available appearance names (optionally filtered by substring)."""
        return client.call("material.list_appearances", {"filter": filter, "limit": limit})

    @mcp.tool(annotations=anno(idempotent=True))
    def fusion_set_appearance(body: Union[int, str], name: str) -> dict:
        """Apply an appearance (by name) to a body. Use fusion_list_appearances to
        discover valid names (e.g. 'Steel', 'Aluminum', 'ABS')."""
        return client.call("material.set_appearance", {"body": body, "name": name})
