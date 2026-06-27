"""Assembly operations: components, occurrences, joints, rigid groups.

Joints are created between two components using their origin points
(``JointGeometry.createByPoint``) — the most reliable programmatic path. Use
assembly.move_component to position a component before/after jointing.
"""

import adsk.core
import adsk.fusion

from ._common import op, optional, require
from ..bridge.protocol import ERR_INVALID_PARAMS, ERR_NOT_FOUND, OpError

_JOINT_TYPES = {
    "rigid": adsk.fusion.JointTypes.RigidJointType,
    "revolute": adsk.fusion.JointTypes.RevoluteJointType,
    "slider": adsk.fusion.JointTypes.SliderJointType,
    "cylindrical": adsk.fusion.JointTypes.CylindricalJointType,
    "pin_slot": adsk.fusion.JointTypes.PinSlotJointType,
    "planar": adsk.fusion.JointTypes.PlanarJointType,
    "ball": adsk.fusion.JointTypes.BallJointType,
}


def _axis_dir(name):
    return {
        "x": adsk.fusion.JointDirections.XAxisJointDirection,
        "y": adsk.fusion.JointDirections.YAxisJointDirection,
        "z": adsk.fusion.JointDirections.ZAxisJointDirection,
    }.get(str(name).lower(), adsk.fusion.JointDirections.ZAxisJointDirection)


def _joint_geometry(occ, face_index):
    """Joint geometry for an occurrence: a planar face (by index on its first body)
    if given, else the component origin point."""
    if face_index is None:
        pt = occ.component.originConstructionPoint.createForAssemblyContext(occ)
        return adsk.fusion.JointGeometry.createByPoint(pt)
    body = occ.component.bRepBodies.item(0)
    face = body.faces.item(int(face_index)).createForAssemblyContext(occ)
    return adsk.fusion.JointGeometry.createByPlanarFace(
        face, None, adsk.fusion.JointKeyPointTypes.CenterKeyPoint
    )


def _find_occurrence(root, name):
    occs = root.allOccurrences
    for i in range(occs.count):
        o = occs.item(i)
        if o.name == name or o.component.name == name:
            return o
    raise OpError(ERR_NOT_FOUND, "No component/occurrence named '{}'.".format(name))


@op("assembly.create_component", summary="Create a new (empty) component as an occurrence in the design.")
def create_component(ctx, params):
    name = require(params, "name", str)
    root = ctx.ensure_root()
    occ = root.occurrences.addNewComponent(adsk.core.Matrix3D.create())
    occ.component.name = name
    return {"created": name, "occurrence": occ.name}


@op("assembly.list_occurrences", summary="List component occurrences (name, grounded, visible).", readonly=True)
def list_occurrences(ctx, params):
    occs = ctx.root().allOccurrences
    out = []
    for i in range(occs.count):
        o = occs.item(i)
        out.append({
            "name": o.name,
            "component": o.component.name,
            "is_grounded": o.isGrounded,
            "is_visible": o.isLightBulbOn,
            "bodies": o.component.bRepBodies.count,
        })
    return {"count": occs.count, "occurrences": out}


@op("assembly.list_joints", summary="List joints (name, type) and rigid groups.", readonly=True)
def list_joints(ctx, params):
    root = ctx.root()
    joints = []
    for i in range(root.joints.count):
        j = root.joints.item(i)
        jt = None
        try:
            jt = j.jointMotion.jointType
        except Exception:
            pass
        joints.append({"name": j.name, "type": jt, "is_suppressed": j.isSuppressed})
    return {
        "count": root.joints.count,
        "joints": joints,
        "as_built_joints": root.asBuiltJoints.count,
        "rigid_groups": root.rigidGroups.count,
    }


@op("assembly.move_component", summary="Translate a component occurrence by (dx,dy,dz) mm.")
def move_component(ctx, params):
    name = require(params, "name", str)
    dx = float(optional(params, "dx", 0.0, types=(int, float)))
    dy = float(optional(params, "dy", 0.0, types=(int, float)))
    dz = float(optional(params, "dz", 0.0, types=(int, float)))
    occ = _find_occurrence(ctx.root(), name)
    transform = occ.transform
    delta = adsk.core.Matrix3D.create()
    delta.translation = adsk.core.Vector3D.create(ctx.mm2cm(dx), ctx.mm2cm(dy), ctx.mm2cm(dz))
    transform.transformBy(delta)
    occ.transform = transform
    try:
        ctx.design().snapshots.add()  # capture the position change in parametric mode
    except Exception:
        pass
    return {"name": occ.name, "moved_mm": [dx, dy, dz]}


@op("assembly.ground_component", summary="Ground/unground a component occurrence (locks it in place).", idempotent=True)
def ground_component(ctx, params):
    name = require(params, "name", str)
    grounded = bool(optional(params, "grounded", True, types=bool))
    occ = _find_occurrence(ctx.root(), name)
    occ.isGrounded = grounded
    return {"name": occ.name, "is_grounded": occ.isGrounded}


@op("assembly.joint", summary="Create a joint between two components at their origins. type rigid/revolute/slider/cylindrical/planar.")
def joint(ctx, params):
    c1 = require(params, "component_one", str)
    c2 = require(params, "component_two", str)
    jtype = str(optional(params, "type", "rigid", types=str)).lower()
    axis = _axis_dir(optional(params, "axis", "z", types=str))
    if jtype not in _JOINT_TYPES:
        raise OpError(ERR_INVALID_PARAMS, "type must be one of " + "/".join(_JOINT_TYPES))

    root = ctx.root()
    occ1 = _find_occurrence(root, c1)
    occ2 = _find_occurrence(root, c2)
    geo1 = _joint_geometry(occ1, params.get("face_one"))
    geo2 = _joint_geometry(occ2, params.get("face_two"))
    joint_input = root.joints.createInput(geo1, geo2)

    if jtype == "rigid":
        joint_input.setAsRigidJointMotion()
    elif jtype == "revolute":
        joint_input.setAsRevoluteJointMotion(axis)
    elif jtype == "slider":
        joint_input.setAsSliderJointMotion(axis)
    elif jtype == "cylindrical":
        joint_input.setAsCylindricalJointMotion(axis)
    elif jtype == "planar":
        joint_input.setAsPlanarJointMotion(axis)
    else:
        raise OpError(
            ERR_INVALID_PARAMS,
            "Joint type '{}' needs extra geometry; use rigid/revolute/slider/cylindrical/planar.".format(jtype),
        )

    j = root.joints.add(joint_input)
    return {"created": j.name, "type": jtype}


@op("assembly.as_built_joint", summary="Create an as-built joint (keeps components where they are).")
def as_built_joint(ctx, params):
    c1 = require(params, "component_one", str)
    c2 = require(params, "component_two", str)
    root = ctx.root()
    occ1 = _find_occurrence(root, c1)
    occ2 = _find_occurrence(root, c2)
    joint_input = root.asBuiltJoints.createInput(occ1, occ2, None)
    j = root.asBuiltJoints.add(joint_input)
    return {"created": j.name}


@op("assembly.rigid_group", summary="Lock 2+ components together as a rigid group.")
def rigid_group(ctx, params):
    names = require(params, "components", list)
    include_children = bool(optional(params, "include_children", True, types=bool))
    if len(names) < 2:
        raise OpError(ERR_INVALID_PARAMS, "rigid_group needs at least 2 components.")
    root = ctx.root()
    occs = adsk.core.ObjectCollection.create()
    for name in names:
        occs.add(_find_occurrence(root, name))
    group = root.rigidGroups.add(occs, include_children)
    return {"created": group.name if hasattr(group, "name") else True, "components": len(names)}
