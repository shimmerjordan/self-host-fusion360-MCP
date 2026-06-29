"""Read-only queries over the active design."""

import adsk.core
import adsk.fusion

from ._common import bbox_mm, body_summary, op, require
from ..bridge.protocol import ERR_INVALID_PARAMS, OpError


@op("query.list_bodies", summary="List solid/surface bodies with volume and bounds.", readonly=True)
def list_bodies(ctx, params):
    bodies = ctx.target().bRepBodies
    return {
        "count": bodies.count,
        "bodies": [body_summary(bodies.item(i), i) for i in range(bodies.count)],
    }


@op("query.list_components", summary="List all components in the design.", readonly=True)
def list_components(ctx, params):
    design = ctx.design()
    comps = design.allComponents
    return {
        "count": comps.count,
        "components": [
            {"name": comps.item(i).name, "bodies": comps.item(i).bRepBodies.count}
            for i in range(comps.count)
        ],
    }


@op("query.list_sketches", summary="List sketches with their profile counts.", readonly=True)
def list_sketches(ctx, params):
    sketches = ctx.target().sketches
    return {
        "count": sketches.count,
        "sketches": [
            {
                "index": i,
                "name": sketches.item(i).name,
                "profiles": sketches.item(i).profiles.count,
                "is_visible": sketches.item(i).isVisible,
            }
            for i in range(sketches.count)
        ],
    }


@op("query.bounding_box", summary="Overall bounding box of the whole design (mm).", readonly=True)
def bounding_box(ctx, params):
    bodies = ctx.target().bRepBodies
    if bodies.count == 0:
        return {"empty": True}
    import adsk.core

    overall = None
    for i in range(bodies.count):
        bb = bodies.item(i).boundingBox
        if bb is None:
            continue
        if overall is None:
            overall = adsk.core.BoundingBox3D.create(bb.minPoint, bb.maxPoint)
        else:
            overall.combine(bb)
    return {"empty": overall is None, "bbox_mm": bbox_mm(overall)}


@op("query.summary", summary="High-level snapshot: units, counts, and body list.", readonly=True)
def summary(ctx, params):
    design = ctx.design()
    root = design.rootComponent
    bodies = root.bRepBodies
    return {
        "document": ctx.app.activeDocument.name if ctx.app.activeDocument else None,
        "units": design.fusionUnitsManager.defaultLengthUnits,
        "counts": {
            "bodies": bodies.count,
            "components": design.allComponents.count,
            "sketches": root.sketches.count,
            "parameters": design.allParameters.count,
        },
        "bodies": [body_summary(bodies.item(i), i) for i in range(min(bodies.count, 50))],
    }


@op("query.get_body", summary="Detailed info for one body by index or name.", readonly=True)
def get_body(ctx, params):
    ref = require(params, "body", (int, str))
    body = ctx.get_body(ref)
    idx = -1
    bodies = ctx.target().bRepBodies
    for i in range(bodies.count):
        if bodies.item(i) == body:
            idx = i
            break
    data = body_summary(body, idx)
    try:
        data["area_mm2"] = body.area * 100.0
        data["faces"] = body.faces.count
        data["edges"] = body.edges.count
        data["vertices"] = body.vertices.count
    except Exception:
        pass
    return data


@op("query.list_faces", summary="List a body's faces (index, area, planar?, centroid) for face selection.", readonly=True)
def list_faces(ctx, params):
    body = ctx.get_body(require(params, "body", (int, str)))
    faces = body.faces
    out = []
    for i in range(faces.count):
        f = faces.item(i)
        entry = {"index": i}
        try:
            entry["area_mm2"] = f.area * 100.0
        except Exception:
            pass
        try:
            entry["is_planar"] = f.geometry.surfaceType == adsk.core.SurfaceTypes.PlaneSurfaceType
        except Exception:
            entry["is_planar"] = False
        try:
            c = f.centroid
            entry["centroid_mm"] = [c.x * 10.0, c.y * 10.0, c.z * 10.0]
        except Exception:
            pass
        if entry.get("is_planar"):
            try:
                n = f.geometry.normal
                entry["normal"] = [round(n.x, 4), round(n.y, 4), round(n.z, 4)]
            except Exception:
                pass
        out.append(entry)
    return {"count": faces.count, "faces": out}


@op("query.physical_properties", summary="Mass/volume/area/center-of-mass of a body (or whole design).", readonly=True)
def physical_properties(ctx, params):
    ref = params.get("body")
    if ref is not None:
        props = ctx.get_body(ref).physicalProperties
        scope = "body"
    else:
        props = ctx.root().getPhysicalProperties(
            adsk.fusion.CalculationAccuracy.MediumCalculationAccuracy
        )
        scope = "design"
    com = props.centerOfMass
    return {
        "scope": scope,
        "mass_g": props.mass * 1000.0,
        "volume_mm3": props.volume * 1000.0,
        "area_mm2": props.area * 100.0,
        "density_g_per_cm3": props.density * 1000.0,
        "center_of_mass_mm": [com.x * 10.0, com.y * 10.0, com.z * 10.0],
    }


@op("query.measure_distance", summary="Minimum distance (mm) between two bodies.", readonly=True)
def measure_distance(ctx, params):
    a = ctx.get_body(require(params, "body_a", (int, str)))
    b = ctx.get_body(require(params, "body_b", (int, str)))
    result = ctx.app.measureManager.measureMinimumDistance(a, b)
    return {"min_distance_mm": result.value * 10.0}


@op("query.measure_angle", summary="Angle (degrees) between the first faces of two bodies.", readonly=True)
def measure_angle(ctx, params):
    import math

    a = ctx.get_body(require(params, "body_a", (int, str)))
    b = ctx.get_body(require(params, "body_b", (int, str)))
    result = ctx.app.measureManager.measureAngle(a.faces.item(0), b.faces.item(0))
    return {"angle_degrees": math.degrees(result.value)}


@op("query.interference", summary="Check interference between 2+ bodies; returns overlapping volumes (mm³).", readonly=True)
def interference(ctx, params):
    refs = require(params, "bodies", list)
    if len(refs) < 2:
        from ..bridge.protocol import ERR_INVALID_PARAMS

        raise OpError(ERR_INVALID_PARAMS, "Provide at least 2 bodies.")
    coll = ctx.collection([ctx.get_body(r) for r in refs])
    design = ctx.design()
    inter_input = design.createInterferenceInput(coll)
    try:
        inter_input.areCoincidentFacesIgnored = not bool(params.get("include_coincident_faces", False))
    except Exception:
        pass
    results = design.analyzeInterference(inter_input)
    hits = []
    for i in range(results.count):
        r = results.item(i)
        try:
            hits.append({
                "body_one": r.entityOne.name,
                "body_two": r.entityTwo.name,
                "volume_mm3": r.interferenceBody.volume * 1000.0,
            })
        except Exception:
            pass
    return {"interference_count": results.count, "interferences": hits}
