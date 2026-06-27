"""Sketch operations.

All coordinates are millimetres in the sketch plane. Geometry ops accept either
an existing ``sketch`` (index/name) or a ``plane`` (xy/xz/yz) on which a new
sketch is created — so a single call like ``sketch.rectangle`` can both create a
sketch and draw on it.
"""

import math

import adsk.core
import adsk.fusion

from ._common import op, optional, require
from ..bridge.protocol import ERR_INVALID_PARAMS, ERR_NOT_FOUND, OpError


def _sketch_index(ctx, sk):
    sketches = ctx.root().sketches
    for i in range(sketches.count):
        if sketches.item(i) == sk:
            return i
    return -1


def _resolve_sketch(ctx, params):
    ref = params.get("sketch")
    if ref is not None:
        return ctx.get_sketch(ref)
    ctx.ensure_design()  # auto-create a document if none is open
    plane = ctx.get_plane(params.get("plane", "xy"))
    return ctx.root().sketches.add(plane)


def _result(ctx, sk):
    return {
        "sketch_index": _sketch_index(ctx, sk),
        "sketch_name": sk.name,
        "profiles": sk.profiles.count,
    }


@op("sketch.create", summary="Create an empty sketch on a plane (xy/xz/yz or index).")
def create(ctx, params):
    ctx.ensure_design()  # auto-create a document if none is open
    plane = ctx.get_plane(params.get("plane", "xy"))
    sk = ctx.root().sketches.add(plane)
    name = optional(params, "name", None, types=str)
    if name:
        sk.name = name
    return _result(ctx, sk)


@op("sketch.rectangle", summary="Draw a rectangle. mode='corner' (default) or 'center'.")
def rectangle(ctx, params):
    width = require(params, "width", (int, float))
    height = require(params, "height", (int, float))
    x = float(optional(params, "x", 0.0, types=(int, float)))
    y = float(optional(params, "y", 0.0, types=(int, float)))
    mode = optional(params, "mode", "corner", types=str)
    sk = _resolve_sketch(ctx, params)
    if str(mode).lower() == "center":
        p1 = ctx.point_mm(x - width / 2.0, y - height / 2.0)
        p2 = ctx.point_mm(x + width / 2.0, y + height / 2.0)
    else:
        p1 = ctx.point_mm(x, y)
        p2 = ctx.point_mm(x + width, y + height)
    sk.sketchCurves.sketchLines.addTwoPointRectangle(p1, p2)
    return _result(ctx, sk)


@op("sketch.circle", summary="Draw a circle by center (x,y) and radius (or diameter).")
def circle(ctx, params):
    x = float(optional(params, "x", 0.0, types=(int, float)))
    y = float(optional(params, "y", 0.0, types=(int, float)))
    if "diameter" in params and params["diameter"] is not None:
        radius = float(params["diameter"]) / 2.0
    else:
        radius = float(require(params, "radius", (int, float)))
    sk = _resolve_sketch(ctx, params)
    sk.sketchCurves.sketchCircles.addByCenterRadius(ctx.point_mm(x, y), ctx.mm2cm(radius))
    return _result(ctx, sk)


@op("sketch.line", summary="Draw a single line segment from (x1,y1) to (x2,y2).")
def line(ctx, params):
    x1 = float(require(params, "x1", (int, float)))
    y1 = float(require(params, "y1", (int, float)))
    x2 = float(require(params, "x2", (int, float)))
    y2 = float(require(params, "y2", (int, float)))
    sk = _resolve_sketch(ctx, params)
    sk.sketchCurves.sketchLines.addByTwoPoints(ctx.point_mm(x1, y1), ctx.point_mm(x2, y2))
    return _result(ctx, sk)


@op("sketch.polygon", summary="Draw a regular polygon (center, circumradius, sides>=3).")
def polygon(ctx, params):
    x = float(optional(params, "x", 0.0, types=(int, float)))
    y = float(optional(params, "y", 0.0, types=(int, float)))
    radius = float(require(params, "radius", (int, float)))
    sides = int(require(params, "sides", int))
    if sides < 3:
        from ..bridge.protocol import ERR_INVALID_PARAMS, OpError

        raise OpError(ERR_INVALID_PARAMS, "polygon 'sides' must be >= 3.")
    rotation = float(optional(params, "rotation_deg", 0.0, types=(int, float)))
    sk = _resolve_sketch(ctx, params)
    lines = sk.sketchCurves.sketchLines
    pts = []
    for k in range(sides):
        ang = math.radians(rotation) + 2.0 * math.pi * k / sides
        pts.append(ctx.point_mm(x + radius * math.cos(ang), y + radius * math.sin(ang)))
    for k in range(sides):
        lines.addByTwoPoints(pts[k], pts[(k + 1) % sides])
    return _result(ctx, sk)


@op("sketch.arc", summary="Draw a 3-point arc: start (x1,y1) -> through (x2,y2) -> end (x3,y3), in mm.")
def arc(ctx, params):
    x1 = float(require(params, "x1", (int, float)))
    y1 = float(require(params, "y1", (int, float)))
    x2 = float(require(params, "x2", (int, float)))
    y2 = float(require(params, "y2", (int, float)))
    x3 = float(require(params, "x3", (int, float)))
    y3 = float(require(params, "y3", (int, float)))
    sk = _resolve_sketch(ctx, params)
    sk.sketchCurves.sketchArcs.addByThreePoints(
        ctx.point_mm(x1, y1), ctx.point_mm(x2, y2), ctx.point_mm(x3, y3)
    )
    return _result(ctx, sk)


def _curve(sk, idx):
    curves = list(sk.sketchCurves)
    if not isinstance(idx, int) or idx < 0 or idx >= len(curves):
        raise OpError(ERR_NOT_FOUND, "Sketch curve index {} out of range (0..{}).".format(idx, len(curves) - 1))
    return curves[idx]


@op("sketch.spline", summary="Draw a spline through points [[x,y],...] (mm). type fit_points (default) or control_points.")
def spline(ctx, params):
    points = require(params, "points", list)
    stype = str(optional(params, "type", "fit_points", types=str)).lower()
    sk = _resolve_sketch(ctx, params)
    coll = adsk.core.ObjectCollection.create()
    for p in points:
        coll.add(ctx.point_mm(p[0], p[1], p[2] if len(p) > 2 else 0))
    if stype == "control_points":
        sk.sketchCurves.sketchControlPointSplines.add(coll, int(optional(params, "degree", 3, types=int)))
    else:
        sk.sketchCurves.sketchFittedSplines.add(coll)
    return _result(ctx, sk)


_CONSTRAINT_METHOD = {
    "coincident": "addCoincident", "parallel": "addParallel", "perpendicular": "addPerpendicular",
    "tangent": "addTangent", "equal": "addEqual", "concentric": "addConcentric",
    "collinear": "addCollinear", "smooth": "addSmooth", "horizontal": "addHorizontal",
    "vertical": "addVertical", "midpoint": "addMidPoint", "symmetry": "addSymmetry",
}
_TWO_CURVE = {"parallel", "perpendicular", "tangent", "equal", "concentric", "collinear", "smooth"}
_ONE_CURVE = {"horizontal", "vertical"}


@op("sketch.constrain", summary="Add a geometric constraint between sketch curves/points by index (coincident/parallel/perpendicular/tangent/equal/horizontal/vertical/concentric/collinear/midpoint/symmetry).")
def constrain(ctx, params):
    sk = ctx.get_sketch(require(params, "sketch", (int, str)))
    ctype = str(require(params, "type", str)).lower()
    method_name = _CONSTRAINT_METHOD.get(ctype)
    gc = sk.geometricConstraints
    if not method_name or not hasattr(gc, method_name):
        raise OpError(ERR_INVALID_PARAMS, "Unsupported constraint type '{}'.".format(ctype))
    fn = getattr(gc, method_name)
    e1 = params.get("entity_one")
    e2 = params.get("entity_two")
    if ctype in _TWO_CURVE:
        fn(_curve(sk, e1), _curve(sk, e2))
    elif ctype in _ONE_CURVE:
        fn(_curve(sk, e1))
    elif ctype in ("coincident", "midpoint"):
        fn(sk.sketchPoints.item(e1), _curve(sk, e2))  # first arg is a sketch point
    elif ctype == "symmetry":
        fn(_curve(sk, e1), _curve(sk, e2), _curve(sk, require(params, "symmetry_line", int)))
    return {"constraint": ctype}


@op("sketch.dimension", summary="Add a driving dimension (distance/horizontal/vertical/angular/radial/diameter). value mm (deg for angular).")
def dimension(ctx, params):
    sk = ctx.get_sketch(require(params, "sketch", (int, str)))
    dtype = str(require(params, "type", str)).lower()
    dims = sk.sketchDimensions
    text_pt = adsk.core.Point3D.create(0, 0, 0)
    e1 = _curve(sk, require(params, "entity_one", int))
    value = optional(params, "value", None, types=(int, float))
    orient = {
        "distance": adsk.fusion.DimensionOrientations.AlignedDimensionOrientation,
        "horizontal": adsk.fusion.DimensionOrientations.HorizontalDimensionOrientation,
        "vertical": adsk.fusion.DimensionOrientations.VerticalDimensionOrientation,
    }
    if dtype in orient:
        e2 = _curve(sk, require(params, "entity_two", int))
        dim = dims.addDistanceDimension(e1.startSketchPoint, e2.startSketchPoint, orient[dtype], text_pt)
    elif dtype == "angular":
        dim = dims.addAngularDimension(e1, _curve(sk, require(params, "entity_two", int)), text_pt)
    elif dtype == "radial":
        dim = dims.addRadialDimension(e1, text_pt)
    elif dtype == "diameter":
        dim = dims.addDiameterDimension(e1, text_pt)
    else:
        raise OpError(ERR_INVALID_PARAMS, "Unknown dimension type '{}'.".format(dtype))
    if value is not None:
        dim.parameter.value = math.radians(value) if dtype == "angular" else ctx.mm2cm(value)
    return {"dimension": dtype, "value": value}


@op("sketch.offset", summary="Offset a sketch curve (by index) by distance mm toward (dir_x, dir_y).")
def offset(ctx, params):
    sk = ctx.get_sketch(require(params, "sketch", (int, str)))
    curve = _curve(sk, require(params, "curve", int))
    distance = float(require(params, "distance", (int, float)))
    dir_pt = ctx.point_mm(optional(params, "dir_x", 1.0, types=(int, float)), optional(params, "dir_y", 0.0, types=(int, float)))
    coll = adsk.core.ObjectCollection.create()
    coll.add(curve)
    sk.offset(coll, dir_pt, ctx.mm2cm(distance))
    return _result(ctx, sk)


@op("sketch.project", summary="Project a body's edges onto a sketch.")
def project(ctx, params):
    sk = ctx.get_sketch(require(params, "sketch", (int, str)))
    body = ctx.get_body(require(params, "body", (int, str)))
    n = 0
    for edge in body.edges:
        try:
            n += sk.project(edge).count
        except Exception:
            pass
    return {"projected_curves": n}
