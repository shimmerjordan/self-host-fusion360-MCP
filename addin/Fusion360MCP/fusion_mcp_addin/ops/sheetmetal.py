"""Sheet metal.

IMPORTANT: Fusion's API does NOT expose creation of sheet-metal features
(FlangeFeatures/BendFeatures have no create methods) — that is an Autodesk
limitation, not ours. Model sheet metal interactively. What IS available is
creating a flat pattern from an *existing* sheet-metal body, below.
"""

import adsk.core

from ._common import op, require
from ..bridge.protocol import ERR_NOT_FOUND, OpError


@op("sheetmetal.create_flat_pattern", summary="Create a flat pattern from an existing sheet-metal body (uses a planar face as stationary).")
def create_flat_pattern(ctx, params):
    body = ctx.get_body(require(params, "body", (int, str)))
    stationary = None
    for i in range(body.faces.count):
        f = body.faces.item(i)
        try:
            if f.geometry.surfaceType == adsk.core.SurfaceTypes.PlaneSurfaceType:
                stationary = f
                break
        except Exception:
            continue
    if stationary is None:
        raise OpError(ERR_NOT_FOUND, "No planar face to use as the stationary face.")
    try:
        fp = body.parentComponent.createFlatPattern(stationary)
    except Exception as exc:
        raise OpError(
            ERR_NOT_FOUND,
            "Flat pattern requires a sheet-metal body. The Fusion API cannot create "
            "sheet-metal flanges/bends. / 该体不是钣金体；Fusion API 无法程序化创建钣金特征。",
            str(exc),
        )
    return {"created": True, "name": getattr(fp, "name", None)}
