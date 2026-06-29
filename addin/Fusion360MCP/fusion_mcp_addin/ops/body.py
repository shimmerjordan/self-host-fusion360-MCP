"""Body-level operations: rename, visibility, delete, move."""

import adsk.core

from ._common import op, optional, require


@op("body.rename", summary="Rename a body.", idempotent=True)
def rename(ctx, params):
    body = ctx.get_body(require(params, "body", (int, str)))
    new_name = require(params, "name", str)
    body.name = new_name
    return {"name": body.name}


@op("body.set_visible", summary="Show or hide a body.", idempotent=True)
def set_visible(ctx, params):
    body = ctx.get_body(require(params, "body", (int, str)))
    visible = bool(require(params, "visible", bool))
    body.isVisible = visible
    return {"name": body.name, "is_visible": body.isVisible}


@op("body.delete", summary="Delete a body.", destructive=True)
def delete(ctx, params):
    body = ctx.get_body(require(params, "body", (int, str)))
    name = body.name
    body.deleteMe()
    return {"deleted": name, "remaining_bodies": ctx.target().bRepBodies.count}


@op("body.move", summary="Translate a body by (dx,dy,dz) millimetres.")
def move(ctx, params):
    body = ctx.get_body(require(params, "body", (int, str)))
    dx = float(optional(params, "dx", 0.0, types=(int, float)))
    dy = float(optional(params, "dy", 0.0, types=(int, float)))
    dz = float(optional(params, "dz", 0.0, types=(int, float)))
    entities = ctx.collection([body])
    transform = adsk.core.Matrix3D.create()
    transform.translation = adsk.core.Vector3D.create(
        ctx.mm2cm(dx), ctx.mm2cm(dy), ctx.mm2cm(dz)
    )
    move_feats = ctx.target().features.moveFeatures
    move_input = move_feats.createInput(entities, transform)
    move_feats.add(move_input)
    return {"name": body.name, "moved_mm": [dx, dy, dz]}


@op("body.combine", summary="Boolean combine a target body with tool body/bodies (join/cut/intersect).", destructive=True)
def combine(ctx, params):
    target = ctx.get_body(require(params, "target", (int, str)))
    tools_ref = require(params, "tools", (int, str, list))
    refs = tools_ref if isinstance(tools_ref, list) else [tools_ref]
    tool_bodies = [ctx.get_body(r) for r in refs]
    op_name = optional(params, "operation", "join", types=str)
    operation = ctx.feature_operation(op_name)
    keep_tools = bool(optional(params, "keep_tools", False, types=bool))

    combines = ctx.target().features.combineFeatures
    combine_input = combines.createInput(target, ctx.collection(tool_bodies))
    combine_input.operation = operation
    combine_input.isKeepToolBodies = keep_tools
    combines.add(combine_input)
    return {
        "feature": "combine",
        "operation": op_name,
        "target": target.name,
        "remaining_bodies": ctx.target().bRepBodies.count,
    }
