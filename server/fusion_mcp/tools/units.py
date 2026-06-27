"""Unit tools."""

from ._helpers import anno


def register(mcp, client):
    @mcp.tool(annotations=anno(readonly=True))
    def fusion_get_units() -> dict:
        """Get the document's default length unit."""
        return client.call("units.get")

    @mcp.tool(annotations=anno(idempotent=True))
    def fusion_set_units(units: str) -> dict:
        """Set the document's display length unit: mm/cm/m/in/ft. (Note: tool inputs
        are always in millimetres regardless of this display setting.)"""
        return client.call("units.set", {"units": units})
