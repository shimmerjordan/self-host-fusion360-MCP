"""Solid feature tools."""

from typing import Optional, Union

from ._helpers import anno


def register(mcp, client):
    @mcp.tool(annotations=anno())
    def fusion_extrude(
        sketch: Union[int, str],
        distance: float,
        operation: str = "new",
        direction: str = "positive",
        profile: Union[int, str] = "all",
    ) -> dict:
        """Extrude a sketch profile by `distance` mm. operation: new/join/cut/
        intersect. direction: positive/negative/symmetric. profile: index or 'all'."""
        return client.call(
            "feature.extrude",
            {"sketch": sketch, "distance": distance, "operation": operation,
             "direction": direction, "profile": profile},
        )

    @mcp.tool(annotations=anno())
    def fusion_revolve(
        sketch: Union[int, str],
        axis: str = "z",
        angle: float = 360.0,
        operation: str = "new",
        profile: Union[int, str] = "all",
    ) -> dict:
        """Revolve a sketch profile around axis x/y/z by `angle` degrees."""
        return client.call(
            "feature.revolve",
            {"sketch": sketch, "axis": axis, "angle": angle,
             "operation": operation, "profile": profile},
        )

    @mcp.tool(annotations=anno())
    def fusion_fillet(
        body: Union[int, str],
        radius: float,
        edges: Union[str, list] = "all",
    ) -> dict:
        """Round edges of a body by `radius` mm. edges='all' (default) or a list of
        edge indices."""
        return client.call("feature.fillet", {"body": body, "radius": radius, "edges": edges})

    @mcp.tool(annotations=anno())
    def fusion_chamfer(
        body: Union[int, str],
        distance: float,
        edges: Union[str, list] = "all",
    ) -> dict:
        """Chamfer edges of a body by `distance` mm. edges='all' or a list of indices."""
        return client.call("feature.chamfer", {"body": body, "distance": distance, "edges": edges})

    @mcp.tool(annotations=anno())
    def fusion_shell(body: Union[int, str], thickness: float) -> dict:
        """Hollow out a body to a wall `thickness` mm."""
        return client.call("feature.shell", {"body": body, "thickness": thickness})

    @mcp.tool(annotations=anno())
    def fusion_rectangular_pattern(
        body: Union[int, str], count: int, spacing: float, axis: str = "x"
    ) -> dict:
        """Pattern a body in a line along axis x/y/z: `count` copies, `spacing` mm apart."""
        return client.call(
            "feature.rectangular_pattern",
            {"body": body, "count": count, "spacing": spacing, "axis": axis},
        )

    @mcp.tool(annotations=anno())
    def fusion_circular_pattern(
        body: Union[int, str], count: int, angle: float = 360.0, axis: str = "z"
    ) -> dict:
        """Pattern a body around axis x/y/z: `count` copies spread over `angle` degrees."""
        return client.call(
            "feature.circular_pattern",
            {"body": body, "count": count, "angle": angle, "axis": axis},
        )

    @mcp.tool(annotations=anno())
    def fusion_mirror(body: Union[int, str], plane: str = "xy") -> dict:
        """Mirror a body across plane xy/xz/yz."""
        return client.call("feature.mirror", {"body": body, "plane": plane})

    @mcp.tool(annotations=anno())
    def fusion_sweep(
        profile_sketch: Union[int, str],
        path_sketch: Union[int, str],
        operation: str = "new",
        profile: Union[int, str] = 0,
    ) -> dict:
        """Sweep a profile (from profile_sketch) along the first curve of path_sketch.
        Draw the path as an open sketch (line/arc/spline) and the profile as a closed
        sketch, then sweep."""
        return client.call(
            "feature.sweep",
            {"profile_sketch": profile_sketch, "path_sketch": path_sketch,
             "operation": operation, "profile": profile},
        )

    @mcp.tool(annotations=anno())
    def fusion_loft(sketches: list, operation: str = "new") -> dict:
        """Loft a smooth solid between profiles taken from a list of sketch indices/
        names (>=2), in order. Each sketch should contain one closed profile."""
        return client.call("feature.loft", {"sketches": sketches, "operation": operation})

    @mcp.tool(annotations=anno())
    def fusion_hole(
        diameter: float,
        x: float = 0.0,
        y: float = 0.0,
        plane: str = "xy",
        depth: Optional[float] = None,
        through_all: bool = True,
        on_body: Optional[Union[int, str]] = None,
        on_face: Optional[int] = None,
    ) -> dict:
        """Drill a circular hole (cut) of `diameter` mm at (x,y). By default it goes
        through everything on `plane` (xy/xz/yz). For a hole on an existing body face,
        pass on_body + on_face (from fusion_list_faces); (x,y) are then in that face's
        local coordinates. Set `depth` for a blind hole."""
        plane_ref = {"body": on_body, "face": on_face} if on_face is not None else plane
        return client.call(
            "feature.hole",
            {"diameter": diameter, "x": x, "y": y, "plane": plane_ref,
             "depth": depth, "through_all": through_all},
        )

    @mcp.tool(annotations=anno())
    def fusion_scale_body(body: Union[int, str], factor: float) -> dict:
        """Uniformly scale a body by `factor` about the origin (2.0 doubles its size)."""
        return client.call("feature.scale", {"body": body, "factor": factor})

    @mcp.tool(annotations=anno())
    def fusion_draft(
        body: Union[int, str], angle: float, faces: Optional[list] = None, plane: str = "xy"
    ) -> dict:
        """Apply draft to faces of a body. angle deg; pull-direction plane xy/xz/yz.
        faces is a list of face indices (from fusion_list_faces) or omitted for all."""
        return client.call(
            "feature.draft",
            {"body": body, "angle": angle, "faces": faces or "all", "plane": plane},
        )

    @mcp.tool(annotations=anno())
    def fusion_split_body(
        body: Union[int, str], plane: str = "xy", tool_body: Optional[Union[int, str]] = None
    ) -> dict:
        """Split a body by a plane (xy/xz/yz) or by another body (tool_body)."""
        return client.call("feature.split_body", {"body": body, "plane": plane, "tool_body": tool_body})

    @mcp.tool(annotations=anno())
    def fusion_split_face(body: Union[int, str], plane: str = "xy", faces: Optional[list] = None) -> dict:
        """Split faces of a body by a plane (xy/xz/yz)."""
        return client.call("feature.split_face", {"body": body, "plane": plane, "faces": faces or "all"})

    @mcp.tool(annotations=anno())
    def fusion_offset_faces(body: Union[int, str], distance: float, faces: Optional[list] = None) -> dict:
        """Offset faces of a body by distance mm (creates an offset surface body)."""
        return client.call("feature.offset_faces", {"body": body, "distance": distance, "faces": faces or "all"})

    @mcp.tool(annotations=anno())
    def fusion_thread(
        body: Union[int, str], face: int, internal: bool = False, modeled: bool = True,
        thread_type: str = "ISO Metric profile",
    ) -> dict:
        """Add a thread to a cylindrical face (face index from fusion_list_faces, the
        non-planar one). internal=True for a hole; modeled=True for real geometry."""
        return client.call(
            "feature.thread",
            {"body": body, "face": face, "internal": internal, "modeled": modeled, "thread_type": thread_type},
        )

    @mcp.tool(annotations=anno(readonly=True))
    def fusion_list_features() -> dict:
        """List timeline features in creation order."""
        return client.call("feature.list")
