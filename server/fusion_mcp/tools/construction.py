"""Construction-geometry tools."""

from ._helpers import anno


def register(mcp, client):
    @mcp.tool(annotations=anno())
    def fusion_offset_plane(offset: float, base: str = "xy") -> dict:
        """Create a construction plane offset from a base plane (xy/xz/yz) by
        `offset` mm. Returns its index for use as a sketch plane."""
        return client.call("construction.offset_plane", {"offset": offset, "base": base})
