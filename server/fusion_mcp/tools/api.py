"""Generic Fusion API tools (full-coverage escape hatch).

introspect/docs are read-only and always registered. call/clear_context are
powerful (call can do anything Fusion can) and are only registered when
allow_arbitrary_code is enabled.
"""

from typing import Optional

from ._helpers import anno


def register(mcp, client):
    """Safe, read-only API helpers (always available)."""

    @mcp.tool(annotations=anno(readonly=True))
    def fusion_api_introspect(target: str, query: str = "") -> dict:
        """Inspect the live Fusion API: list a class's (or an object path's) properties
        and method signatures. `target` is a class name (e.g. 'ExtrudeFeatures') or a
        path ('rootComponent.bRepBodies'); `query` filters member names. Use this to
        discover the exact API to drive via fusion_api_call."""
        return client.call("api.introspect", {"target": target, "query": query})

    @mcp.tool(annotations=anno(readonly=True))
    def fusion_api_docs(name: str) -> dict:
        """Get the Autodesk cloudhelp URL for an API class or member
        (e.g. 'ExtrudeFeatures.createInput')."""
        return client.call("api.docs", {"name": name})


def register_power(mcp, client):
    """The arbitrary-call tools (only when allow_arbitrary_code is on)."""

    @mcp.tool(annotations=anno())
    def fusion_api_call(
        path: str,
        args: Optional[list] = None,
        kwargs: Optional[dict] = None,
        store_as: Optional[str] = None,
        return_properties: Optional[list] = None,
    ) -> dict:
        """Call ANY adsk.* method or read any property by dotted path — the full-coverage
        power tool for anything the curated tools don't cover.

        `path` examples: 'rootComponent.bRepBodies' (read), 'app.activeDocument.save'
        (method), 'adsk.fusion.Design.cast'. In args/kwargs use:
          - {"$path": "rootComponent"}  -> resolve another API path
          - {"$ref": "myObj"}           -> a previously stored object
          - {"type": "Point3D", "x":1, "y":2, "z":0} -> construct an object
          - {"type": "ValueInput", "expression": "10 mm"}  (or "value": 1.0)
        `store_as` saves the result for later $ref; `return_properties` reads named
        properties off the result. Discover signatures with fusion_api_introspect."""
        return client.call(
            "api.call",
            {"path": path, "args": args or [], "kwargs": kwargs or {},
             "store_as": store_as, "return_properties": return_properties or []},
        )

    @mcp.tool(annotations=anno(idempotent=True))
    def fusion_api_clear_context() -> dict:
        """Clear objects stored by fusion_api_call (the $ref store)."""
        return client.call("api.clear_context")
