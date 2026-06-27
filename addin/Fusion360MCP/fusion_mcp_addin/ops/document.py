"""Document-level operations: create / inspect / save / list."""

import adsk.core

from ._common import op, optional


@op(
    "document.new",
    summary="Create a new, empty Fusion design document and make it active.",
    params=[],
)
def new_document(ctx, params):
    doc = ctx.app.documents.add(adsk.core.DocumentTypes.FusionDesignDocumentType)
    return {"document": doc.name}


@op(
    "document.info",
    summary="Summarize the active document: units and object counts.",
    readonly=True,
)
def info(ctx, params):
    design = ctx.design()
    root = design.rootComponent
    return {
        "document": ctx.app.activeDocument.name if ctx.app.activeDocument else None,
        "units": design.fusionUnitsManager.defaultLengthUnits,
        "bodies": root.bRepBodies.count,
        "components": design.allComponents.count,
        "sketches": root.sketches.count,
        "parameters": design.allParameters.count,
        "is_modified": bool(ctx.app.activeDocument.isModified)
        if ctx.app.activeDocument
        else None,
    }


@op(
    "document.list",
    summary="List the names of all currently open documents.",
    readonly=True,
)
def list_documents(ctx, params):
    return {"documents": [d.name for d in ctx.app.documents]}


@op(
    "document.save",
    summary="Save the active document (must already have been saved once).",
    idempotent=True,
)
def save(ctx, params):
    description = optional(params, "description", "", types=str)
    doc = ctx.app.activeDocument
    if doc is None:
        return {"saved": False, "reason": "no active document"}
    try:
        doc.save(description or "")
        return {"saved": True, "document": doc.name}
    except Exception as exc:
        # Never-saved docs require an interactive Save As into a data folder.
        return {
            "saved": False,
            "reason": "First save must be done in Fusion (choose a project folder). "
            "/ 首次保存需在 Fusion 中手动选择项目文件夹。",
            "detail": str(exc),
        }
