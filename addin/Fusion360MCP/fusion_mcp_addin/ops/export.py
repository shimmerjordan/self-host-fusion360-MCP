"""Export the design/bodies to STL, STEP, IGES, F3D.

Files are written on the **host** machine (where Fusion runs). If no path is
given, files land in ``~/fusion-mcp-exports``.
"""

import time
from pathlib import Path

import adsk.fusion

from ._common import op, optional, require


def _resolve_path(params, ext):
    raw = params.get("path")
    if raw:
        path = Path(raw)
        if path.suffix.lower() != ext:
            path = path.with_suffix(ext)
    else:
        base = Path.home() / "fusion-mcp-exports"
        stamp = time.strftime("%Y%m%d-%H%M%S")
        path = base / ("export-" + stamp + ext)
    path.parent.mkdir(parents=True, exist_ok=True)
    return str(path)


def _geometry(ctx, params):
    """A body if 'body' is given, else the root component."""
    if params.get("body") is not None:
        return ctx.get_body(params["body"])
    return ctx.root()


@op("export.stl", summary="Export to STL. Optional body; refinement low/medium/high.")
def export_stl(ctx, params):
    design = ctx.design()
    filename = _resolve_path(params, ".stl")
    options = design.exportManager.createSTLExportOptions(_geometry(ctx, params), filename)
    refinement = (optional(params, "refinement", "medium", types=str) or "medium").lower()
    enum_name = {
        "low": "MeshRefinementLow",
        "medium": "MeshRefinementMedium",
        "high": "MeshRefinementHigh",
    }.get(refinement, "MeshRefinementMedium")
    try:
        options.meshRefinement = getattr(adsk.fusion.MeshRefinementSettings, enum_name)
    except Exception:
        pass
    design.exportManager.execute(options)
    return {"format": "stl", "path": filename}


@op("export.step", summary="Export the whole design to STEP (.step).")
def export_step(ctx, params):
    design = ctx.design()
    filename = _resolve_path(params, ".step")
    options = design.exportManager.createSTEPExportOptions(filename, ctx.root())
    design.exportManager.execute(options)
    return {"format": "step", "path": filename}


@op("export.iges", summary="Export the whole design to IGES (.igs).")
def export_iges(ctx, params):
    design = ctx.design()
    filename = _resolve_path(params, ".igs")
    options = design.exportManager.createIGESExportOptions(filename, ctx.root())
    design.exportManager.execute(options)
    return {"format": "iges", "path": filename}


@op("export.f3d", summary="Export native Fusion archive (.f3d), preserving the design tree.")
def export_f3d(ctx, params):
    design = ctx.design()
    filename = _resolve_path(params, ".f3d")
    options = design.exportManager.createFusionArchiveExportOptions(filename, ctx.root())
    design.exportManager.execute(options)
    return {"format": "f3d", "path": filename}


@op("export.dxf", summary="Export a sketch to a DXF file (2D).")
def export_dxf(ctx, params):
    sk = ctx.get_sketch(require(params, "sketch", (int, str)))
    filename = _resolve_path(params, ".dxf")
    sk.saveAsDXF(filename)
    return {"format": "dxf", "path": filename, "sketch": sk.name}
