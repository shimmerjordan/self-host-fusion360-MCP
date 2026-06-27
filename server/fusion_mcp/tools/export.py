"""Export tools. Files are written on the HOST machine where Fusion runs."""

from typing import Optional, Union

from ._helpers import anno


def register(mcp, client):
    @mcp.tool(annotations=anno())
    def fusion_export_stl(
        path: Optional[str] = None,
        body: Optional[Union[int, str]] = None,
        refinement: str = "medium",
    ) -> dict:
        """Export to STL (for 3D printing). Optional `body` (else whole design);
        refinement low/medium/high. Saved on the host (default ~/fusion-mcp-exports)."""
        return client.call("export.stl", {"path": path, "body": body, "refinement": refinement})

    @mcp.tool(annotations=anno())
    def fusion_export_step(path: Optional[str] = None) -> dict:
        """Export the whole design to STEP (.step), the best format for CAD interchange."""
        return client.call("export.step", {"path": path})

    @mcp.tool(annotations=anno())
    def fusion_export_iges(path: Optional[str] = None) -> dict:
        """Export the whole design to IGES (.igs). Note: IGES export is restricted on
        personal-use Fusion licenses — prefer STEP for CAD interchange."""
        return client.call("export.iges", {"path": path})

    @mcp.tool(annotations=anno())
    def fusion_export_f3d(path: Optional[str] = None) -> dict:
        """Export a native Fusion archive (.f3d), preserving the full design tree."""
        return client.call("export.f3d", {"path": path})

    @mcp.tool(annotations=anno())
    def fusion_export_dxf(sketch: Union[int, str], path: Optional[str] = None) -> dict:
        """Export a sketch to a 2D DXF file (e.g. for laser cutting / drawings)."""
        return client.call("export.dxf", {"sketch": sketch, "path": path})
