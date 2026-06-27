"""Viewport tools. Screenshot returns an image Claude can actually see."""

import base64

from mcp.server.fastmcp import Image

from ._helpers import anno


def register(mcp, client):
    @mcp.tool(annotations=anno(readonly=True))
    def fusion_screenshot(width: int = 1280, height: int = 720, fit: bool = True):
        """Capture the active Fusion viewport and return it as a PNG image so you
        can visually inspect the model. Set fit=False to keep the current camera."""
        result = client.call("view.screenshot", {"width": width, "height": height, "fit": fit})
        return Image(data=base64.b64decode(result["base64"]), format="png")

    @mcp.tool(annotations=anno(idempotent=True))
    def fusion_fit_view() -> dict:
        """Zoom/fit the view to show the whole model."""
        return client.call("view.fit")

    @mcp.tool(annotations=anno(idempotent=True))
    def fusion_set_view(name: str = "iso") -> dict:
        """Set a named camera orientation: home/iso/top/bottom/front/back/left/right."""
        return client.call("view.orientation", {"name": name})
