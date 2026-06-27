"""Document tools."""

from ._helpers import anno


def register(mcp, client):
    @mcp.tool(annotations=anno())
    def fusion_new_document() -> dict:
        """Create a new, empty Fusion 360 design document and make it active.
        Call this first if no design is open."""
        return client.call("document.new")

    @mcp.tool(annotations=anno(readonly=True))
    def fusion_document_info() -> dict:
        """Summarize the active document: display units and counts of bodies,
        components, sketches, and parameters."""
        return client.call("document.info")

    @mcp.tool(annotations=anno(readonly=True))
    def fusion_list_documents() -> dict:
        """List the names of all currently open Fusion documents."""
        return client.call("document.list")

    @mcp.tool(annotations=anno(idempotent=True))
    def fusion_save_document(description: str = "") -> dict:
        """Save the active document. The document must have been saved once
        interactively in Fusion first (the first save picks a project folder)."""
        return client.call("document.save", {"description": description})
