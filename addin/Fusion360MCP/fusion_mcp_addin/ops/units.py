"""Document display-unit operations."""

import adsk.fusion

from ._common import op
from ..bridge.protocol import ERR_INVALID_PARAMS, OpError

_UNIT_ENUM = {
    "mm": "MillimeterDistanceUnits",
    "cm": "CentimeterDistanceUnits",
    "m": "MeterDistanceUnits",
    "in": "InchDistanceUnits",
    "ft": "FootDistanceUnits",
}


@op("units.get", summary="Get the document's default length unit.", readonly=True)
def get_units(ctx, params):
    return {"units": ctx.design().fusionUnitsManager.defaultLengthUnits}


@op("units.set", summary="Set the document's display length unit (mm/cm/m/in/ft).", idempotent=True)
def set_units(ctx, params):
    unit = str(params.get("unit") or params.get("units") or "").strip().lower()
    enum_name = _UNIT_ENUM.get(unit)
    if enum_name is None:
        raise OpError(ERR_INVALID_PARAMS, "Provide 'unit' as one of mm/cm/m/in/ft.")
    mgr = ctx.design().fusionUnitsManager
    mgr.distanceDisplayUnits = getattr(adsk.fusion.DistanceUnits, enum_name)
    return {"units": mgr.defaultLengthUnits}
