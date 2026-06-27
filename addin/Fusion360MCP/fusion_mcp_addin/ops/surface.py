"""Surface modelling: patch, stitch, thicken, ruled. (Trim is available via api.call.)"""

import adsk.core
import adsk.fusion

from ._common import op, optional, require


@op("surface.thicken", summary="Thicken a body's faces into a solid by thickness mm.")
def thicken(ctx, params):
    body = ctx.get_body(require(params, "body", (int, str)))
    thickness = float(require(params, "thickness", (int, float)))
    symmetric = str(optional(params, "direction", "positive", types=str)).lower() == "symmetric"
    faces = adsk.core.ObjectCollection.create()
    for i in range(body.faces.count):
        faces.add(body.faces.item(i))
    thickens = ctx.root().features.thickenFeatures
    thicken_input = thickens.createInput(
        faces, ctx.len_mm(thickness), False,
        adsk.fusion.FeatureOperations.NewBodyFeatureOperation, symmetric,
    )
    feature = thickens.add(thicken_input)
    return {"feature": "thicken", "body_count": ctx.root().bRepBodies.count}


@op("surface.ruled", summary="Create a ruled surface from a body edge, extending by distance mm.")
def ruled(ctx, params):
    body = ctx.get_body(require(params, "body", (int, str)))
    edge_index = int(require(params, "edge", int))
    distance = float(require(params, "distance", (int, float)))
    if edge_index < 0 or edge_index >= body.edges.count:
        from ..bridge.protocol import ERR_NOT_FOUND, OpError

        raise OpError(ERR_NOT_FOUND, "Edge index {} out of range.".format(edge_index))
    ruled_feats = ctx.root().features.ruledSurfaceFeatures
    ruled_input = ruled_feats.createInput(body.edges.item(edge_index), ctx.len_mm(distance))
    ruled_feats.add(ruled_input)
    return {"feature": "ruled", "body_count": ctx.root().bRepBodies.count}


@op("surface.patch", summary="Patch a closed sketch profile into a surface.")
def patch(ctx, params):
    sk = ctx.get_sketch(require(params, "sketch", (int, str)))
    if sk.profiles.count == 0:
        from ..bridge.protocol import ERR_NOT_FOUND, OpError

        raise OpError(ERR_NOT_FOUND, "Sketch '{}' has no closed profile to patch.".format(sk.name))
    patches = ctx.root().features.patchFeatures
    patch_input = patches.createInput(
        sk.profiles.item(0), adsk.fusion.FeatureOperations.NewBodyFeatureOperation
    )
    patches.add(patch_input)
    return {"feature": "patch", "body_count": ctx.root().bRepBodies.count}


@op("surface.stitch", summary="Stitch surface bodies into one (tolerance mm).")
def stitch(ctx, params):
    refs = require(params, "bodies", list)
    tolerance = float(optional(params, "tolerance", 0.1, types=(int, float)))
    coll = ctx.collection([ctx.get_body(r) for r in refs])
    stitches = ctx.root().features.stitchFeatures
    stitch_input = stitches.createInput(
        coll, ctx.len_mm(tolerance), adsk.fusion.FeatureOperations.NewBodyFeatureOperation
    )
    stitches.add(stitch_input)
    return {"feature": "stitch", "body_count": ctx.root().bRepBodies.count}
