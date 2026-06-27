"""One-call primitive solids (box / cylinder / sphere).

These compose a sketch + feature internally so the result is a normal parametric
body — no TemporaryBRepManager/BaseFeature complexity. They auto-create a design
if none is open, so "make a 20 mm cube" works from a blank Fusion.
"""

import adsk.fusion

from ._common import op, optional, require


def _name_body(body, params):
    name = optional(params, "name", None, types=str)
    if name:
        body.name = name
    return body


def _build_target(ctx, params):
    """Return the Component to build into: a named component occurrence if the
    'component' param is given, else the (ensured) root component."""
    comp_name = params.get("component")
    if comp_name:
        from .assembly import _find_occurrence

        return _find_occurrence(ctx.ensure_root() and ctx.root(), comp_name).component
    return ctx.ensure_root()


@op("primitive.box", summary="Create a box width(x) x depth(y) x height(z) mm, centered on the XY origin, rising in +Z.")
def box(ctx, params):
    w = float(require(params, "width", (int, float)))
    d = float(require(params, "depth", (int, float)))
    h = float(require(params, "height", (int, float)))
    cx = float(optional(params, "x", 0.0, types=(int, float)))
    cy = float(optional(params, "y", 0.0, types=(int, float)))
    root = _build_target(ctx, params)
    sketch = root.sketches.add(root.xYConstructionPlane)
    sketch.sketchCurves.sketchLines.addTwoPointRectangle(
        ctx.point_mm(cx - w / 2.0, cy - d / 2.0), ctx.point_mm(cx + w / 2.0, cy + d / 2.0)
    )
    ext = root.features.extrudeFeatures
    ext_input = ext.createInput(
        sketch.profiles.item(0), adsk.fusion.FeatureOperations.NewBodyFeatureOperation
    )
    ext_input.setDistanceExtent(False, ctx.len_mm(h))
    feature = ext.add(ext_input)
    body = _name_body(feature.bodies.item(0), params)
    return {"primitive": "box", "body": body.name, "size_mm": [w, d, h]}


@op("primitive.cylinder", summary="Create a cylinder of given radius (or diameter) and height mm, centered on XY origin.")
def cylinder(ctx, params):
    if params.get("diameter") is not None:
        radius = float(params["diameter"]) / 2.0
    else:
        radius = float(require(params, "radius", (int, float)))
    h = float(require(params, "height", (int, float)))
    cx = float(optional(params, "x", 0.0, types=(int, float)))
    cy = float(optional(params, "y", 0.0, types=(int, float)))
    root = ctx.ensure_root()
    sketch = root.sketches.add(root.xYConstructionPlane)
    sketch.sketchCurves.sketchCircles.addByCenterRadius(
        ctx.point_mm(cx, cy), ctx.mm2cm(radius)
    )
    ext = root.features.extrudeFeatures
    ext_input = ext.createInput(
        sketch.profiles.item(0), adsk.fusion.FeatureOperations.NewBodyFeatureOperation
    )
    ext_input.setDistanceExtent(False, ctx.len_mm(h))
    feature = ext.add(ext_input)
    body = _name_body(feature.bodies.item(0), params)
    return {"primitive": "cylinder", "body": body.name, "radius_mm": radius, "height_mm": h}


@op("primitive.sphere", summary="Create a sphere of given radius (or diameter) mm, centered on the origin.")
def sphere(ctx, params):
    if params.get("diameter") is not None:
        radius = float(params["diameter"]) / 2.0
    else:
        radius = float(require(params, "radius", (int, float)))
    root = ctx.ensure_root()
    # A HALF-disk whose flat (diameter) edge lies ON the X axis, revolved 360 deg
    # around X -> a sphere. A full circle would straddle the axis and Fusion
    # rejects it ("profile intersects the revolution axis").
    sketch = root.sketches.add(root.xYConstructionPlane)
    sketch.sketchCurves.sketchArcs.addByThreePoints(
        ctx.point_mm(-radius, 0), ctx.point_mm(0, radius), ctx.point_mm(radius, 0)
    )
    sketch.sketchCurves.sketchLines.addByTwoPoints(
        ctx.point_mm(radius, 0), ctx.point_mm(-radius, 0)
    )
    rev = root.features.revolveFeatures
    rev_input = rev.createInput(
        sketch.profiles.item(0),
        root.xConstructionAxis,
        adsk.fusion.FeatureOperations.NewBodyFeatureOperation,
    )
    rev_input.setAngleExtent(False, ctx.angle_deg(360))
    feature = rev.add(rev_input)
    body = _name_body(feature.bodies.item(0), params)
    return {"primitive": "sphere", "body": body.name, "radius_mm": radius}
