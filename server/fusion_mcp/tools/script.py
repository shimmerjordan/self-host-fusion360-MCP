"""Gated arbitrary-code tool. Only registered when --allow-arbitrary-code is set."""

from ._helpers import anno


def register(mcp, client):
    @mcp.tool(annotations=anno(destructive=True))
    def fusion_run_script(code: str) -> dict:
        """Execute arbitrary Fusion 360 Python in-process (POWER TOOL, enabled by
        the operator). Available globals: adsk, app, ui, design, root. Assign a
        `result` variable to return a value; stdout is captured. Use only when a
        dedicated tool does not exist."""
        return client.call("script.run", {"code": code})
