"""Read-only query tools."""

from typing import Union

from ._helpers import anno


def register(mcp, client):
    @mcp.tool(annotations=anno(readonly=True))
    def fusion_list_bodies() -> dict:
        """List all solid/surface bodies with index, name, volume (mm³), and
        bounding box (mm). Use the index or name to target a body in other tools."""
        return client.call("query.list_bodies")

    @mcp.tool(annotations=anno(readonly=True))
    def fusion_list_components() -> dict:
        """List all components in the design with their body counts."""
        return client.call("query.list_components")

    @mcp.tool(annotations=anno(readonly=True))
    def fusion_list_sketches() -> dict:
        """List sketches with index, name, and number of closed profiles."""
        return client.call("query.list_sketches")

    @mcp.tool(annotations=anno(readonly=True))
    def fusion_bounding_box() -> dict:
        """Get the overall bounding box of the whole design, in millimetres."""
        return client.call("query.bounding_box")

    @mcp.tool(annotations=anno(readonly=True))
    def fusion_summary() -> dict:
        """High-level snapshot of the design: units, counts, and a body list.
        A good first call to understand the current model."""
        return client.call("query.summary")

    @mcp.tool(annotations=anno(readonly=True))
    def fusion_get_body(body: Union[int, str]) -> dict:
        """Detailed info for one body (by index or name): volume, area, face/edge/
        vertex counts, and bounding box."""
        return client.call("query.get_body", {"body": body})

    @mcp.tool(annotations=anno(readonly=True))
    def fusion_list_faces(body: Union[int, str]) -> dict:
        """List a body's faces (index, area mm², is_planar, centroid, normal). Use a
        planar face's index to sketch/drill on it (fusion_create_sketch_on_face,
        fusion_hole with on_body/on_face)."""
        return client.call("query.list_faces", {"body": body})

    @mcp.tool(annotations=anno(readonly=True))
    def fusion_physical_properties(body: Union[int, str, None] = None) -> dict:
        """Mass (g), volume (mm³), area (mm²), density, and center of mass for a body
        (by index/name) or the whole design if omitted."""
        return client.call("query.physical_properties", {"body": body})

    @mcp.tool(annotations=anno(readonly=True))
    def fusion_measure_distance(body_a: Union[int, str], body_b: Union[int, str]) -> dict:
        """Minimum distance in millimetres between two bodies."""
        return client.call("query.measure_distance", {"body_a": body_a, "body_b": body_b})

    @mcp.tool(annotations=anno(readonly=True))
    def fusion_measure_angle(body_a: Union[int, str], body_b: Union[int, str]) -> dict:
        """Angle (degrees) between the first faces of two bodies."""
        return client.call("query.measure_angle", {"body_a": body_a, "body_b": body_b})

    @mcp.tool(annotations=anno(readonly=True))
    def fusion_interference(bodies: list, include_coincident_faces: bool = False) -> dict:
        """Check interference between 2+ bodies (list of indices/names); returns the
        overlapping volumes (mm³). Use to validate clearances/fits in an assembly."""
        return client.call(
            "query.interference",
            {"bodies": bodies, "include_coincident_faces": include_coincident_faces},
        )
