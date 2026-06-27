"""Assembly tools: components, occurrences, joints, rigid groups."""

from typing import Optional, Union

from ._helpers import anno


def register(mcp, client):
    @mcp.tool(annotations=anno())
    def fusion_create_component(name: str) -> dict:
        """Create a new (empty) component as an occurrence in the design. Build
        geometry, then joint components together to form an assembly."""
        return client.call("assembly.create_component", {"name": name})

    @mcp.tool(annotations=anno(readonly=True))
    def fusion_list_occurrences() -> dict:
        """List component occurrences: name, grounded, visible, body count."""
        return client.call("assembly.list_occurrences")

    @mcp.tool(annotations=anno(readonly=True))
    def fusion_list_joints() -> dict:
        """List joints (name, type), plus as-built-joint and rigid-group counts."""
        return client.call("assembly.list_joints")

    @mcp.tool(annotations=anno())
    def fusion_move_component(name: str, dx: float = 0.0, dy: float = 0.0, dz: float = 0.0) -> dict:
        """Translate a component occurrence by (dx, dy, dz) millimetres."""
        return client.call("assembly.move_component", {"name": name, "dx": dx, "dy": dy, "dz": dz})

    @mcp.tool(annotations=anno())
    def fusion_ground_component(name: str, grounded: bool = True) -> dict:
        """Ground (lock in place) or unground a component occurrence."""
        return client.call("assembly.ground_component", {"name": name, "grounded": grounded})

    @mcp.tool(annotations=anno())
    def fusion_joint(
        component_one: str,
        component_two: str,
        type: str = "rigid",
        axis: str = "z",
        face_one: Optional[int] = None,
        face_two: Optional[int] = None,
    ) -> dict:
        """Create a joint between two components.
        type: rigid / revolute / slider / cylindrical / planar; axis (x/y/z) is the
        motion axis. By default it joins at the component origins; pass face_one/face_two
        (planar face indices on each component's first body) to mate specific faces."""
        return client.call(
            "assembly.joint",
            {"component_one": component_one, "component_two": component_two, "type": type,
             "axis": axis, "face_one": face_one, "face_two": face_two},
        )

    @mcp.tool(annotations=anno())
    def fusion_create_flat_pattern(body: Union[int, str]) -> dict:
        """Create a flat pattern from an EXISTING sheet-metal body. Note: Fusion's API
        cannot create sheet-metal flanges/bends (model those interactively)."""
        return client.call("sheetmetal.create_flat_pattern", {"body": body})

    @mcp.tool(annotations=anno())
    def fusion_as_built_joint(component_one: str, component_two: str) -> dict:
        """Create an as-built joint (keeps both components in their current place)."""
        return client.call(
            "assembly.as_built_joint",
            {"component_one": component_one, "component_two": component_two},
        )

    @mcp.tool(annotations=anno())
    def fusion_rigid_group(components: list, include_children: bool = True) -> dict:
        """Lock 2+ components together as a rigid group (pass a list of names)."""
        return client.call(
            "assembly.rigid_group",
            {"components": components, "include_children": include_children},
        )
