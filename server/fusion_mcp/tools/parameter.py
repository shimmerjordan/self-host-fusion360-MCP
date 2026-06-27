"""Parameter tools — drive models with named values for robust edits."""

from typing import Union

from ._helpers import anno


def register(mcp, client):
    @mcp.tool(annotations=anno(readonly=True))
    def fusion_list_parameters() -> dict:
        """List all parameters (user + model) with expression, value, and unit."""
        return client.call("parameter.list")

    @mcp.tool(annotations=anno(readonly=True))
    def fusion_get_parameter(name: str) -> dict:
        """Get one parameter by name."""
        return client.call("parameter.get", {"name": name})

    @mcp.tool(annotations=anno(idempotent=True))
    def fusion_set_parameter(name: str, expression: str) -> dict:
        """Set a parameter's expression, e.g. '25 mm' or 'width * 2'. This is the
        preferred way to resize an existing parametric model."""
        return client.call("parameter.set", {"name": name, "expression": expression})

    @mcp.tool(annotations=anno())
    def fusion_create_parameter(
        name: str, expression: str, unit: str = "mm", comment: str = ""
    ) -> dict:
        """Create a new user parameter (e.g. name='width', expression='40 mm')."""
        return client.call(
            "parameter.create",
            {"name": name, "expression": expression, "unit": unit, "comment": comment},
        )

    @mcp.tool(annotations=anno(destructive=True))
    def fusion_delete_parameter(name: str) -> dict:
        """Delete a user parameter by name (model parameters cannot be deleted)."""
        return client.call("parameter.delete", {"name": name})
