"""Surface modelling tools."""

from typing import Union

from ._helpers import anno


def register(mcp, client):
    @mcp.tool(annotations=anno())
    def fusion_surface_thicken(body: Union[int, str], thickness: float, direction: str = "positive") -> dict:
        """Thicken a (surface) body's faces into a solid by thickness mm. direction
        'positive' or 'symmetric'."""
        return client.call("surface.thicken", {"body": body, "thickness": thickness, "direction": direction})

    @mcp.tool(annotations=anno())
    def fusion_surface_patch(sketch: Union[int, str]) -> dict:
        """Patch a closed sketch profile into a surface body."""
        return client.call("surface.patch", {"sketch": sketch})

    @mcp.tool(annotations=anno())
    def fusion_surface_ruled(body: Union[int, str], edge: int, distance: float) -> dict:
        """Create a ruled surface from a body edge (by index), extended by distance mm."""
        return client.call("surface.ruled", {"body": body, "edge": edge, "distance": distance})

    @mcp.tool(annotations=anno())
    def fusion_surface_stitch(bodies: list, tolerance: float = 0.1) -> dict:
        """Stitch surface bodies (list of indices/names) into one, with tolerance mm."""
        return client.call("surface.stitch", {"bodies": bodies, "tolerance": tolerance})
