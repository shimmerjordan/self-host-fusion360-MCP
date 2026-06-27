"""Sketch tools. Coordinates are millimetres in the sketch plane.

Each draw tool accepts EITHER an existing ``sketch`` (index/name) OR a ``plane``
(xy/xz/yz) on which a new sketch is created. Returns the sketch index to feed
into feature tools."""

from typing import Optional, Union

from ._helpers import anno


def register(mcp, client):
    @mcp.tool(annotations=anno())
    def fusion_create_sketch(plane: str = "xy", name: Optional[str] = None) -> dict:
        """Create an empty sketch on a construction plane (xy/xz/yz)."""
        return client.call("sketch.create", {"plane": plane, "name": name})

    @mcp.tool(annotations=anno())
    def fusion_create_sketch_on_face(
        body: Union[int, str], face: int, name: Optional[str] = None
    ) -> dict:
        """Create a sketch ON a planar face of a body. Get the face index from
        fusion_list_faces (is_planar=true). Sketch coordinates are then local to
        that face."""
        return client.call("sketch.create", {"plane": {"body": body, "face": face}, "name": name})

    @mcp.tool(annotations=anno())
    def fusion_sketch_rectangle(
        width: float,
        height: float,
        x: float = 0.0,
        y: float = 0.0,
        mode: str = "corner",
        sketch: Optional[Union[int, str]] = None,
        plane: str = "xy",
    ) -> dict:
        """Draw a rectangle (mm). mode='corner' treats (x,y) as a corner;
        mode='center' treats (x,y) as the center. Creates a new sketch on `plane`
        unless an existing `sketch` is given."""
        return client.call(
            "sketch.rectangle",
            {"width": width, "height": height, "x": x, "y": y, "mode": mode,
             "sketch": sketch, "plane": plane},
        )

    @mcp.tool(annotations=anno())
    def fusion_sketch_circle(
        radius: Optional[float] = None,
        diameter: Optional[float] = None,
        x: float = 0.0,
        y: float = 0.0,
        sketch: Optional[Union[int, str]] = None,
        plane: str = "xy",
    ) -> dict:
        """Draw a circle (mm) by center (x,y) and radius OR diameter."""
        return client.call(
            "sketch.circle",
            {"radius": radius, "diameter": diameter, "x": x, "y": y,
             "sketch": sketch, "plane": plane},
        )

    @mcp.tool(annotations=anno())
    def fusion_sketch_line(
        x1: float,
        y1: float,
        x2: float,
        y2: float,
        sketch: Optional[Union[int, str]] = None,
        plane: str = "xy",
    ) -> dict:
        """Draw a single line segment from (x1,y1) to (x2,y2), in mm."""
        return client.call(
            "sketch.line",
            {"x1": x1, "y1": y1, "x2": x2, "y2": y2, "sketch": sketch, "plane": plane},
        )

    @mcp.tool(annotations=anno())
    def fusion_sketch_arc(
        x1: float,
        y1: float,
        x2: float,
        y2: float,
        x3: float,
        y3: float,
        sketch: Optional[Union[int, str]] = None,
        plane: str = "xy",
    ) -> dict:
        """Draw a 3-point arc (mm): from start (x1,y1), through (x2,y2), to end (x3,y3).
        Useful as a sweep/revolve path."""
        return client.call(
            "sketch.arc",
            {"x1": x1, "y1": y1, "x2": x2, "y2": y2, "x3": x3, "y3": y3,
             "sketch": sketch, "plane": plane},
        )

    @mcp.tool(annotations=anno())
    def fusion_sketch_polygon(
        radius: float,
        sides: int,
        x: float = 0.0,
        y: float = 0.0,
        rotation_deg: float = 0.0,
        sketch: Optional[Union[int, str]] = None,
        plane: str = "xy",
    ) -> dict:
        """Draw a regular polygon (mm) by center, circumradius, and side count (>=3)."""
        return client.call(
            "sketch.polygon",
            {"radius": radius, "sides": sides, "x": x, "y": y,
             "rotation_deg": rotation_deg, "sketch": sketch, "plane": plane},
        )

    @mcp.tool(annotations=anno())
    def fusion_sketch_spline(
        points: list,
        type: str = "fit_points",
        degree: int = 3,
        sketch: Optional[Union[int, str]] = None,
        plane: str = "xy",
    ) -> dict:
        """Draw a spline through points [[x,y],...] (mm). type 'fit_points' or
        'control_points' (uses degree)."""
        return client.call(
            "sketch.spline",
            {"points": points, "type": type, "degree": degree, "sketch": sketch, "plane": plane},
        )

    @mcp.tool(annotations=anno())
    def fusion_sketch_constrain(
        sketch: Union[int, str],
        type: str,
        entity_one: int,
        entity_two: Optional[int] = None,
        symmetry_line: Optional[int] = None,
    ) -> dict:
        """Add a geometric constraint between sketch entities (by curve index).
        type: coincident/parallel/perpendicular/tangent/equal/horizontal/vertical/
        concentric/collinear/midpoint/symmetry. For coincident/midpoint, entity_one is
        a sketch-point index. This is the key to robust, editable parametric sketches."""
        return client.call(
            "sketch.constrain",
            {"sketch": sketch, "type": type, "entity_one": entity_one,
             "entity_two": entity_two, "symmetry_line": symmetry_line},
        )

    @mcp.tool(annotations=anno())
    def fusion_sketch_dimension(
        sketch: Union[int, str],
        type: str,
        entity_one: int,
        entity_two: Optional[int] = None,
        value: Optional[float] = None,
    ) -> dict:
        """Add a driving dimension. type: distance/horizontal/vertical/angular/radial/
        diameter. value is mm (degrees for angular). Drives parametric sizing."""
        return client.call(
            "sketch.dimension",
            {"sketch": sketch, "type": type, "entity_one": entity_one,
             "entity_two": entity_two, "value": value},
        )

    @mcp.tool(annotations=anno())
    def fusion_sketch_offset(
        sketch: Union[int, str], curve: int, distance: float, dir_x: float = 1.0, dir_y: float = 0.0
    ) -> dict:
        """Offset a sketch curve (by index) by distance mm toward (dir_x, dir_y)."""
        return client.call(
            "sketch.offset",
            {"sketch": sketch, "curve": curve, "distance": distance, "dir_x": dir_x, "dir_y": dir_y},
        )

    @mcp.tool(annotations=anno())
    def fusion_sketch_project(sketch: Union[int, str], body: Union[int, str]) -> dict:
        """Project a body's edges onto a sketch (linked reference geometry)."""
        return client.call("sketch.project", {"sketch": sketch, "body": body})
