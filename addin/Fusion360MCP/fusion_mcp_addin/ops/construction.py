"""Construction geometry: offset planes."""

from ._common import op, optional, require


@op("construction.offset_plane", summary="Create a construction plane offset from xy/xz/yz by mm.")
def offset_plane(ctx, params):
    base = ctx.get_plane(optional(params, "base", "xy", types=str))
    offset = float(require(params, "offset", (int, float)))
    planes = ctx.root().constructionPlanes
    plane_input = planes.createInput()
    plane_input.setByOffset(base, ctx.len_mm(offset))
    plane = planes.add(plane_input)
    return {"index": planes.count - 1, "name": plane.name, "offset_mm": offset}
