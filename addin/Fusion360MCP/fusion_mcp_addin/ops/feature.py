"""Solid feature operations: extrude, revolve, fillet, chamfer, shell, patterns, mirror."""

import adsk.fusion

from ._common import op, optional, require
from ..bridge.protocol import ERR_INVALID_PARAMS, ERR_NOT_FOUND, OpError


def _profiles_from_sketch(ctx, sk, profile_ref):
    """Return a profile or an ObjectCollection of profiles to feed a feature."""
    count = sk.profiles.count
    if count == 0:
        raise OpError(
            ERR_NOT_FOUND,
            "Sketch '{}' has no closed profiles to use. / 草图没有可用的闭合轮廓。".format(sk.name),
        )
    if profile_ref in (None, "all"):
        if count == 1:
            return sk.profiles.item(0)
        return ctx.collection([sk.profiles.item(i) for i in range(count)])
    if isinstance(profile_ref, int):
        if profile_ref < 0 or profile_ref >= count:
            raise OpError(ERR_NOT_FOUND, "Profile index {} out of range (0..{}).".format(profile_ref, count - 1))
        return sk.profiles.item(profile_ref)
    raise OpError(ERR_INVALID_PARAMS, "profile must be an index or 'all'.")


def _edges_collection(ctx, body, edges_ref):
    if edges_ref in (None, "all"):
        items = [body.edges.item(i) for i in range(body.edges.count)]
    elif isinstance(edges_ref, list):
        items = []
        for idx in edges_ref:
            if not isinstance(idx, int) or idx < 0 or idx >= body.edges.count:
                raise OpError(ERR_NOT_FOUND, "Edge index {} out of range.".format(idx))
            items.append(body.edges.item(idx))
    else:
        raise OpError(ERR_INVALID_PARAMS, "edges must be 'all' or a list of indices.")
    if not items:
        raise OpError(ERR_NOT_FOUND, "No edges to operate on.")
    return ctx.collection(items)


def _feature_result(ctx, feature, kind):
    bodies = ctx.root().bRepBodies
    out = {"feature": kind, "body_count": bodies.count}
    try:
        out["feature_name"] = feature.name
    except Exception:
        pass
    return out


@op("feature.extrude", summary="Extrude a sketch profile. distance in mm; operation new/join/cut/intersect.")
def extrude(ctx, params):
    sk = ctx.get_sketch(require(params, "sketch", (int, str)))
    distance = float(require(params, "distance", (int, float)))
    operation = ctx.feature_operation(optional(params, "operation", "new", types=str))
    direction = optional(params, "direction", "positive", types=str).lower()
    profiles = _profiles_from_sketch(ctx, sk, params.get("profile", "all"))

    ext_feats = ctx.root().features.extrudeFeatures
    ext_input = ext_feats.createInput(profiles, operation)
    if direction == "symmetric":
        ext_input.setDistanceExtent(True, ctx.len_mm(distance))
    elif direction == "negative":
        ext_input.setDistanceExtent(False, ctx.len_mm(-abs(distance)))
    else:
        ext_input.setDistanceExtent(False, ctx.len_mm(abs(distance)))
    feature = ext_feats.add(ext_input)
    return _feature_result(ctx, feature, "extrude")


@op("feature.revolve", summary="Revolve a sketch profile around an axis (x/y/z). angle in degrees.")
def revolve(ctx, params):
    sk = ctx.get_sketch(require(params, "sketch", (int, str)))
    axis = ctx.get_axis(optional(params, "axis", "z", types=str))
    angle = float(optional(params, "angle", 360.0, types=(int, float)))
    operation = ctx.feature_operation(optional(params, "operation", "new", types=str))
    profiles = _profiles_from_sketch(ctx, sk, params.get("profile", "all"))

    rev_feats = ctx.root().features.revolveFeatures
    rev_input = rev_feats.createInput(profiles, axis, operation)
    rev_input.setAngleExtent(False, ctx.angle_deg(angle))
    feature = rev_feats.add(rev_input)
    return _feature_result(ctx, feature, "revolve")


@op("feature.fillet", summary="Round edges of a body. radius in mm; edges='all' or list of indices.")
def fillet(ctx, params):
    body = ctx.get_body(require(params, "body", (int, str)))
    radius = float(require(params, "radius", (int, float)))
    edges = _edges_collection(ctx, body, params.get("edges", "all"))
    fillet_feats = ctx.root().features.filletFeatures
    fillet_input = fillet_feats.createInput()
    fillet_input.edgeSetInputs.addConstantRadiusEdgeSet(edges, ctx.len_mm(radius), True)
    feature = fillet_feats.add(fillet_input)
    return _feature_result(ctx, feature, "fillet")


@op("feature.chamfer", summary="Chamfer edges of a body. distance in mm; edges='all' or list of indices.")
def chamfer(ctx, params):
    body = ctx.get_body(require(params, "body", (int, str)))
    distance = float(require(params, "distance", (int, float)))
    edges = _edges_collection(ctx, body, params.get("edges", "all"))
    chamfer_feats = ctx.root().features.chamferFeatures
    chamfer_input = chamfer_feats.createInput2()
    chamfer_input.chamferEdgeSets.addEqualDistanceChamferEdgeSet(
        edges, ctx.len_mm(distance), True
    )
    feature = chamfer_feats.add(chamfer_input)
    return _feature_result(ctx, feature, "chamfer")


@op("feature.shell", summary="Hollow out a body to a wall thickness (mm).")
def shell(ctx, params):
    body = ctx.get_body(require(params, "body", (int, str)))
    thickness = float(require(params, "thickness", (int, float)))
    entities = ctx.collection([body])
    shell_feats = ctx.root().features.shellFeatures
    shell_input = shell_feats.createInput(entities, False)
    shell_input.insideThickness = ctx.len_mm(thickness)
    feature = shell_feats.add(shell_input)
    return _feature_result(ctx, feature, "shell")


@op("feature.rectangular_pattern", summary="Pattern a body along axis (x/y/z); count + spacing in mm.")
def rectangular_pattern(ctx, params):
    body = ctx.get_body(require(params, "body", (int, str)))
    count = int(require(params, "count", int))
    spacing = float(require(params, "spacing", (int, float)))
    axis = ctx.get_axis(optional(params, "axis", "x", types=str))
    entities = ctx.collection([body])
    import adsk.core

    pat_feats = ctx.root().features.rectangularPatternFeatures
    pat_input = pat_feats.createInput(
        entities,
        axis,
        adsk.core.ValueInput.createByReal(count),
        ctx.len_mm(spacing),
        adsk.fusion.PatternDistanceType.SpacingPatternDistanceType,
    )
    feature = pat_feats.add(pat_input)
    return _feature_result(ctx, feature, "rectangular_pattern")


@op("feature.circular_pattern", summary="Pattern a body around axis (x/y/z); count + total angle (deg).")
def circular_pattern(ctx, params):
    body = ctx.get_body(require(params, "body", (int, str)))
    count = int(require(params, "count", int))
    angle = float(optional(params, "angle", 360.0, types=(int, float)))
    axis = ctx.get_axis(optional(params, "axis", "z", types=str))
    entities = ctx.collection([body])
    import adsk.core

    pat_feats = ctx.root().features.circularPatternFeatures
    pat_input = pat_feats.createInput(entities, axis)
    pat_input.quantity = adsk.core.ValueInput.createByReal(count)
    pat_input.totalAngle = ctx.angle_deg(angle)
    pat_input.isSymmetric = bool(optional(params, "symmetric", False, types=bool))
    feature = pat_feats.add(pat_input)
    return _feature_result(ctx, feature, "circular_pattern")


@op("feature.mirror", summary="Mirror a body across a plane (xy/xz/yz).")
def mirror(ctx, params):
    body = ctx.get_body(require(params, "body", (int, str)))
    plane = ctx.get_plane(optional(params, "plane", "xy", types=str))
    entities = ctx.collection([body])
    mirror_feats = ctx.root().features.mirrorFeatures
    mirror_input = mirror_feats.createInput(entities, plane)
    feature = mirror_feats.add(mirror_input)
    return _feature_result(ctx, feature, "mirror")


@op("feature.sweep", summary="Sweep a profile (from profile_sketch) along a path (path_sketch's first curve).")
def sweep(ctx, params):
    prof_sk = ctx.get_sketch(require(params, "profile_sketch", (int, str)))
    path_sk = ctx.get_sketch(require(params, "path_sketch", (int, str)))
    operation = ctx.feature_operation(optional(params, "operation", "new", types=str))
    profile = _profiles_from_sketch(ctx, prof_sk, params.get("profile", 0))
    if path_sk.sketchCurves.count == 0:
        raise OpError(ERR_NOT_FOUND, "Path sketch '{}' has no curves.".format(path_sk.name))
    path = ctx.root().features.createPath(path_sk.sketchCurves.item(0), True)
    sweep_feats = ctx.root().features.sweepFeatures
    sweep_input = sweep_feats.createInput(profile, path, operation)
    feature = sweep_feats.add(sweep_input)
    return _feature_result(ctx, feature, "sweep")


@op("feature.loft", summary="Loft between profiles taken from a list of sketches (profile 0 of each).")
def loft(ctx, params):
    sketch_refs = require(params, "sketches", list)
    if len(sketch_refs) < 2:
        raise OpError(ERR_INVALID_PARAMS, "loft needs at least 2 sketches.")
    operation = ctx.feature_operation(optional(params, "operation", "new", types=str))
    loft_feats = ctx.root().features.loftFeatures
    loft_input = loft_feats.createInput(operation)
    for ref in sketch_refs:
        sk = ctx.get_sketch(ref)
        loft_input.loftSections.add(_profiles_from_sketch(ctx, sk, 0))
    feature = loft_feats.add(loft_input)
    return _feature_result(ctx, feature, "loft")


@op("feature.hole", summary="Drill a circular hole (cut) at (x,y) on a plane/face; diameter mm; through-all or depth mm.")
def hole(ctx, params):
    diameter = float(require(params, "diameter", (int, float)))
    x = float(optional(params, "x", 0.0, types=(int, float)))
    y = float(optional(params, "y", 0.0, types=(int, float)))
    depth = optional(params, "depth", None, types=(int, float))
    through = bool(optional(params, "through_all", depth is None, types=bool))
    plane = ctx.get_plane(params.get("plane", "xy"))
    root = ctx.root()
    sk = root.sketches.add(plane)
    sk.sketchCurves.sketchCircles.addByCenterRadius(ctx.point_mm(x, y), ctx.mm2cm(diameter / 2.0))
    ext = root.features.extrudeFeatures
    ext_input = ext.createInput(
        sk.profiles.item(0), adsk.fusion.FeatureOperations.CutFeatureOperation
    )
    if through:
        ext_input.setAllExtent(adsk.fusion.ExtentDirections.SymmetricExtentDirection)
    else:
        ext_input.setDistanceExtent(False, ctx.len_mm(-abs(float(depth))))
    feature = ext.add(ext_input)
    return _feature_result(ctx, feature, "hole")


@op("feature.scale", summary="Uniformly scale a body by a factor about the origin.")
def scale(ctx, params):
    import adsk.core

    body = ctx.get_body(require(params, "body", (int, str)))
    factor = float(require(params, "factor", (int, float)))
    root = ctx.root()
    scale_feats = root.features.scaleFeatures
    sf_input = scale_feats.createInput(
        ctx.collection([body]),
        root.originConstructionPoint,
        adsk.core.ValueInput.createByReal(factor),
    )
    feature = scale_feats.add(sf_input)
    return _feature_result(ctx, feature, "scale")


def _faces_collection(ctx, body, face_ref):
    import adsk.core

    faces = body.faces
    if face_ref in (None, "all"):
        items = [faces.item(i) for i in range(faces.count)]
    elif isinstance(face_ref, list):
        items = []
        for idx in face_ref:
            if not isinstance(idx, int) or idx < 0 or idx >= faces.count:
                raise OpError(ERR_NOT_FOUND, "Face index {} out of range.".format(idx))
            items.append(faces.item(idx))
    else:
        raise OpError(ERR_INVALID_PARAMS, "faces must be 'all' or a list of indices.")
    coll = adsk.core.ObjectCollection.create()
    for f in items:
        coll.add(f)
    return coll


@op("feature.draft", summary="Apply draft to faces of a body. angle deg; pull-direction plane xy/xz/yz.")
def draft(ctx, params):
    import adsk.core

    body = ctx.get_body(require(params, "body", (int, str)))
    angle = float(require(params, "angle", (int, float)))
    plane = ctx.get_plane(optional(params, "plane", "xy", types=str))
    face_ref = params.get("faces", "all")
    if face_ref in (None, "all"):
        faces = [body.faces.item(i) for i in range(body.faces.count)]
    else:
        faces = [body.faces.item(i) for i in face_ref]
    drafts = ctx.root().features.draftFeatures
    draft_input = drafts.createInput(faces, plane, True)
    draft_input.setSingleAngle(False, adsk.core.ValueInput.createByString("{} deg".format(angle)))
    feature = drafts.add(draft_input)
    return _feature_result(ctx, feature, "draft")


@op("feature.split_body", summary="Split a body by a plane (xy/xz/yz) or another body.")
def split_body(ctx, params):
    body = ctx.get_body(require(params, "body", (int, str)))
    extend = bool(optional(params, "extend_tool", True, types=bool))
    if params.get("tool_body") is not None:
        tool = ctx.get_body(params["tool_body"])
    else:
        tool = ctx.get_plane(optional(params, "plane", "xy", types=str))
    splits = ctx.root().features.splitBodyFeatures
    split_input = splits.createInput(body, tool, extend)
    feature = splits.add(split_input)
    return _feature_result(ctx, feature, "split_body")


@op("feature.split_face", summary="Split faces of a body by a plane (xy/xz/yz).")
def split_face(ctx, params):
    body = ctx.get_body(require(params, "body", (int, str)))
    plane = ctx.get_plane(optional(params, "plane", "xy", types=str))
    extend = bool(optional(params, "extend_tool", True, types=bool))
    faces = _faces_collection(ctx, body, params.get("faces", "all"))
    splits = ctx.root().features.splitFaceFeatures
    split_input = splits.createInput(faces, plane, extend)
    feature = splits.add(split_input)
    return _feature_result(ctx, feature, "split_face")


@op("feature.offset_faces", summary="Offset faces of a body by distance mm (creates an offset surface body).")
def offset_faces(ctx, params):
    import adsk.core

    body = ctx.get_body(require(params, "body", (int, str)))
    distance = float(require(params, "distance", (int, float)))
    faces = _faces_collection(ctx, body, params.get("faces", "all"))
    offsets = ctx.root().features.offsetFeatures
    offset_input = offsets.createInput(
        faces, ctx.len_mm(distance), adsk.fusion.FeatureOperations.NewBodyFeatureOperation
    )
    feature = offsets.add(offset_input)
    return _feature_result(ctx, feature, "offset_faces")


@op("feature.thread", summary="Add a thread to a cylindrical face. internal bool; modeled=True for real geometry.")
def thread(ctx, params):
    body = ctx.get_body(require(params, "body", (int, str)))
    face_index = int(require(params, "face", int))
    if face_index < 0 or face_index >= body.faces.count:
        raise OpError(ERR_NOT_FOUND, "Face index {} out of range.".format(face_index))
    face = body.faces.item(face_index)
    internal = bool(optional(params, "internal", False, types=bool))
    modeled = bool(optional(params, "modeled", True, types=bool))
    thread_type = optional(params, "thread_type", "ISO Metric profile", types=str)

    threads = ctx.root().features.threadFeatures
    query = threads.threadDataQuery
    try:
        diameter_cm = face.geometry.radius * 2.0
    except Exception:
        raise OpError(ERR_INVALID_PARAMS, "Face {} is not cylindrical; thread needs a cylindrical face.".format(face_index))
    recommend = query.recommendThreadData(diameter_cm, internal, thread_type)
    # SWIG out-params: returns (success, threadDesignation, threadClass).
    vals = list(recommend) if isinstance(recommend, (list, tuple)) else [recommend]
    if len(vals) < 3:
        raise OpError(ERR_INVALID_PARAMS, "Could not recommend thread data for diameter {:.1f}mm.".format(diameter_cm * 10))
    designation, thread_class = vals[1], vals[2]
    thread_info = threads.createThreadInfo(internal, thread_type, designation, thread_class)
    thread_input = threads.createInput(face, thread_info)
    thread_input.isModeled = modeled
    feature = threads.add(thread_input)
    return _feature_result(ctx, feature, "thread")


@op("feature.list", summary="List timeline features in creation order.", readonly=True)
def list_features(ctx, params):
    design = ctx.design()
    try:
        timeline = design.timeline
    except Exception:
        return {"supported": False, "features": []}
    items = []
    for i in range(timeline.count):
        item = timeline.item(i)
        entity = None
        try:
            entity = item.entity.objectType
        except Exception:
            entity = None
        items.append({"index": i, "name": item.name, "type": entity})
    return {"count": len(items), "features": items}
