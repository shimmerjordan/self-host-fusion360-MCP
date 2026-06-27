"""CAM / manufacturing tools.

Prerequisite: open the Manufacturing workspace in Fusion once so the CAM product
exists. Tools return a clear hint otherwise. Lengths are millimetres.
"""

from typing import Optional, Union

from ._helpers import anno


def register(mcp, client):
    @mcp.tool(annotations=anno(readonly=True))
    def fusion_cam_list_setups() -> dict:
        """List CAM setups and their operations. Requires the Manufacturing
        workspace to have been opened once in Fusion."""
        return client.call("cam.list_setups")

    @mcp.tool(annotations=anno(readonly=True))
    def fusion_cam_list_operations(setup: str) -> dict:
        """List operations in a CAM setup (name, has_toolpath, is_valid)."""
        return client.call("cam.list_operations", {"setup": setup})

    @mcp.tool(annotations=anno(readonly=True))
    def fusion_cam_list_tools(limit: int = 20) -> dict:
        """List cutting tools from the local tool library (for assigning to operations)."""
        return client.call("cam.list_tools", {"limit": limit})

    @mcp.tool(annotations=anno())
    def fusion_cam_create_setup(
        body: Union[int, str], name: Optional[str] = None, operation_type: str = "milling"
    ) -> dict:
        """Create a CAM setup around a body. operation_type: milling/turning/cutting."""
        return client.call(
            "cam.create_setup",
            {"body": body, "name": name, "operation_type": operation_type},
        )

    @mcp.tool(annotations=anno())
    def fusion_cam_create_operation(
        setup: str,
        strategy: str,
        name: Optional[str] = None,
        tool_diameter: Optional[float] = None,
        stepdown: Optional[float] = None,
        stepover: Optional[float] = None,
    ) -> dict:
        """Add an operation to a setup by `strategy` (e.g. face, pocket2d, adaptive2d,
        contour2d, drill, bore). Optional tool_diameter/stepdown/stepover in mm.
        Note: most strategies need a tool assigned before a toolpath will generate."""
        return client.call(
            "cam.create_operation",
            {"setup": setup, "strategy": strategy, "name": name,
             "tool_diameter": tool_diameter, "stepdown": stepdown, "stepover": stepover},
        )

    @mcp.tool(annotations=anno())
    def fusion_cam_generate(
        setup: Optional[str] = None, operation: Optional[str] = None, all: bool = False
    ) -> dict:
        """Generate toolpaths: one `operation` in a `setup`, a whole `setup`, or all=true."""
        return client.call("cam.generate", {"setup": setup, "operation": operation, "all": all})

    @mcp.tool(annotations=anno())
    def fusion_cam_post_process(
        setup: str,
        operation: Optional[str] = None,
        post_processor: str = "fanuc",
        units: str = "mm",
        output_folder: Optional[str] = None,
    ) -> dict:
        """Post-process a setup (or one operation) to a G-code file on the host
        (default ~/fusion-mcp-exports/nc). post_processor is a generic post name."""
        return client.call(
            "cam.post_process",
            {"setup": setup, "operation": operation, "post_processor": post_processor,
             "units": units, "output_folder": output_folder},
        )
