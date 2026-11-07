"""Mesh import: bring an STL / OBJ / 3MF file in as a mesh body.

Imports into the sticky *target* component (so it lands in the CURRENT document
alongside existing parts without disturbing them). An optional (dx,dy,dz) offset
in millimetres translates the imported body into free space to avoid overlaps.
"""

import os

import adsk.core
import adsk.fusion

from ._common import op, optional, require
from ..bridge.protocol import ERR_INVALID_PARAMS, ERR_NOT_FOUND, OpError


@op(
    "mesh.import",
    summary="Import a mesh file (STL/OBJ/3MF) as a mesh body into the target component. "
    "params: path; optional dx/dy/dz mm offset, component.",
    params=[
        {"name": "path", "type": "str", "required": True},
        {"name": "dx", "type": "number", "required": False},
        {"name": "dy", "type": "number", "required": False},
        {"name": "dz", "type": "number", "required": False},
    ],
)
def import_mesh(ctx, params):
    path = require(params, "path", str)
    if not os.path.exists(path):
        raise OpError(ERR_NOT_FOUND, "Mesh file not found: {}".format(path))

    comp = ctx.build_target(params)
    design = ctx.ensure_design()

    units_map = {
        "mm": adsk.fusion.MeshUnits.MillimeterMeshUnit,
        "cm": adsk.fusion.MeshUnits.CentimeterMeshUnit,
        "m": adsk.fusion.MeshUnits.MeterMeshUnit,
        "in": adsk.fusion.MeshUnits.InchMeshUnit,
        "ft": adsk.fusion.MeshUnits.FootMeshUnit,
    }
    unit = units_map.get(str(optional(params, "units", "mm", types=str)).lower(),
                         adsk.fusion.MeshUnits.MillimeterMeshUnit)

    before = comp.meshBodies.count
    # Parametric designs (designType == 1) require mesh bodies to be added inside
    # a base feature; direct-edit designs can add straight to meshBodies.
    is_parametric = design.designType == adsk.fusion.DesignTypes.ParametricDesignType
    base = None
    try:
        if is_parametric:
            base = comp.features.baseFeatures.add()
            base.startEdit()
        comp.meshBodies.add(path, unit)
        if base is not None:
            base.finishEdit()
    except Exception as exc:  # noqa: BLE001
        try:
            if base is not None:
                base.finishEdit()
        except Exception:
            pass
        raise OpError(ERR_INVALID_PARAMS, "Mesh import failed.", str(exc))
    after = comp.meshBodies.count

    new_bodies = [comp.meshBodies.item(i) for i in range(before, after)]

    dx = optional(params, "dx", 0.0, types=(int, float)) or 0.0
    dy = optional(params, "dy", 0.0, types=(int, float)) or 0.0
    dz = optional(params, "dz", 0.0, types=(int, float)) or 0.0
    moved = False
    if new_bodies and (dx or dy or dz):
        transform = adsk.core.Matrix3D.create()
        transform.translation = adsk.core.Vector3D.create(dx / 10.0, dy / 10.0, dz / 10.0)
        coll = adsk.core.ObjectCollection.create()
        for mb in new_bodies:
            coll.add(mb)
        try:
            mf = comp.features.moveFeatures
            mi = mf.createInput2(coll)
            mi.defineAsFreeMove(transform)
            mf.add(mi)
            moved = True
        except Exception as exc:  # noqa: BLE001
            # import still succeeded; report that the offset could not be applied
            return {
                "imported": after - before,
                "mesh_bodies": [{"index": before + i, "name": b.name} for i, b in enumerate(new_bodies)],
                "component": comp.name,
                "moved": False,
                "move_error": str(exc),
            }

    def _bbox(b):
        bb = getattr(b, "boundingBox", None)
        if bb is None:
            return None
        return {
            "min": [bb.minPoint.x * 10.0, bb.minPoint.y * 10.0, bb.minPoint.z * 10.0],
            "max": [bb.maxPoint.x * 10.0, bb.maxPoint.y * 10.0, bb.maxPoint.z * 10.0],
        }

    return {
        "imported": after - before,
        "mesh_bodies": [
            {"index": before + i, "name": b.name, "bbox_mm": _bbox(b)}
            for i, b in enumerate(new_bodies)
        ],
        "component": comp.name,
        "moved": moved,
        "offset_mm": [dx, dy, dz],
    }


def _enum_member(enum_cls_name, needle):
    cls = getattr(adsk.fusion, enum_cls_name, None)
    if cls is None:
        return None, []
    names = [n for n in dir(cls) if not n.startswith("_") and n not in ("classType", "cast")]
    for n in names:
        if needle.lower() in n.lower():
            return getattr(cls, n), names
    return None, names


@op(
    "mesh.convert",
    summary="Convert a mesh body to a solid BRep body (Fusion 'Convert Mesh'). "
    "params: mesh (index/name, default = last mesh body); method faceted|prismatic|organic "
    "(default faceted — keeps every triangle as a planar face, no extension needed).",
    params=[
        {"name": "mesh", "type": "int|str", "required": False},
        {"name": "method", "type": "str", "required": False},
    ],
)
def convert_mesh(ctx, params):
    comp = ctx.build_target(params)
    meshes = comp.meshBodies
    if meshes.count == 0:
        raise OpError(ERR_NOT_FOUND, "No mesh bodies in component '{}'.".format(comp.name))
    ref = params.get("mesh", meshes.count - 1)
    if isinstance(ref, bool) or not isinstance(ref, (int, str)):
        raise OpError(ERR_INVALID_PARAMS, "mesh must be an index (int) or name (str).")
    if isinstance(ref, int):
        if ref < 0 or ref >= meshes.count:
            raise OpError(ERR_NOT_FOUND, "Mesh index {} out of range (0..{}).".format(ref, meshes.count - 1))
        mb = meshes.item(ref)
    else:
        mb = meshes.itemByName(ref)
        if mb is None:
            raise OpError(ERR_NOT_FOUND, "No mesh body named '{}'.".format(ref))

    method = str(optional(params, "method", "faceted", types=str)).lower()
    member, names = _enum_member("MeshConvertMethodTypes", method)
    if member is None:
        raise OpError(ERR_INVALID_PARAMS, "Unknown convert method '{}'. Available: {}".format(method, names))

    feats = comp.features.meshConvertFeatures
    before = comp.bRepBodies.count
    try:
        inp = feats.createInput([mb])
    except Exception:  # noqa: BLE001 — older builds want an ObjectCollection
        coll = adsk.core.ObjectCollection.create()
        coll.add(mb)
        inp = feats.createInput(coll)
    inp.meshConvertMethodType = member
    try:
        feature = feats.add(inp)
    except Exception as exc:  # noqa: BLE001
        raise OpError(ERR_INVALID_PARAMS, "Mesh convert failed.", str(exc))

    new_bodies = []
    for i in range(before, comp.bRepBodies.count):
        b = comp.bRepBodies.item(i)
        new_bodies.append({
            "index": i,
            "name": b.name,
            "is_solid": b.isSolid,
            "faces": b.faces.count,
            "volume_mm3": b.volume * 1000.0,
        })
    return {
        "converted": mb.name,
        "method": method,
        "feature": getattr(feature, "name", None),
        "new_bodies": new_bodies,
    }
