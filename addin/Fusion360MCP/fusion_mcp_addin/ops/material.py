"""Appearance / material operations (best effort across material libraries)."""

from ._common import op, optional, require
from ..bridge.protocol import ERR_NOT_FOUND, OpError


def _iter_library_appearances(ctx):
    libs = ctx.app.materialLibraries
    for i in range(libs.count):
        lib = libs.item(i)
        try:
            apps = lib.appearances
        except Exception:
            continue
        for j in range(apps.count):
            yield lib.name, apps.item(j)


@op("material.list_appearances", summary="List available appearance names (optionally filtered).", readonly=True)
def list_appearances(ctx, params):
    needle = (optional(params, "filter", "", types=str) or "").lower()
    limit = int(optional(params, "limit", 100, types=int))
    out = []
    for lib_name, appr in _iter_library_appearances(ctx):
        if needle and needle not in appr.name.lower():
            continue
        out.append({"name": appr.name, "library": lib_name})
        if len(out) >= limit:
            break
    return {"count": len(out), "appearances": out}


@op("material.set_appearance", summary="Apply an appearance (by name) to a body.", idempotent=True)
def set_appearance(ctx, params):
    body = ctx.get_body(require(params, "body", (int, str)))
    name = require(params, "name", str)
    target = None
    for _lib_name, appr in _iter_library_appearances(ctx):
        if appr.name.lower() == name.lower():
            target = appr
            break
    if target is None:
        raise OpError(
            ERR_NOT_FOUND,
            "No appearance named '{}'. Use material.list_appearances to discover names.".format(name),
        )
    body.appearance = target
    return {"name": body.name, "appearance": target.name}
