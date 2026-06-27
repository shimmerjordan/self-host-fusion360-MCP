"""One-call primitive solids. These auto-create a document if none is open."""

from typing import Optional

from ._helpers import anno


def register(mcp, client):
    @mcp.tool(annotations=anno())
    def fusion_box(
        width: float,
        depth: float,
        height: float,
        x: float = 0.0,
        y: float = 0.0,
        name: Optional[str] = None,
        component: Optional[str] = None,
    ) -> dict:
        """Create a box (cuboid): width(X) x depth(Y) x height(Z) in mm, centered on
        the XY origin and rising in +Z. Auto-creates a document if none is open.
        For a cube, pass equal width/depth/height. Pass `component` (a component name
        from fusion_create_component) to build the box INSIDE that component — useful
        for building assembly parts to then joint together."""
        return client.call(
            "primitive.box",
            {"width": width, "depth": depth, "height": height, "x": x, "y": y,
             "name": name, "component": component},
        )

    @mcp.tool(annotations=anno())
    def fusion_cylinder(
        height: float,
        radius: Optional[float] = None,
        diameter: Optional[float] = None,
        x: float = 0.0,
        y: float = 0.0,
        name: Optional[str] = None,
    ) -> dict:
        """Create a cylinder of `height` mm and `radius` OR `diameter` mm, centered
        on the XY origin. Auto-creates a document if none is open."""
        return client.call(
            "primitive.cylinder",
            {"height": height, "radius": radius, "diameter": diameter, "x": x, "y": y, "name": name},
        )

    @mcp.tool(annotations=anno())
    def fusion_sphere(
        radius: Optional[float] = None,
        diameter: Optional[float] = None,
        name: Optional[str] = None,
    ) -> dict:
        """Create a sphere of `radius` OR `diameter` mm, centered on the origin.
        Auto-creates a document if none is open."""
        return client.call(
            "primitive.sphere", {"radius": radius, "diameter": diameter, "name": name}
        )
