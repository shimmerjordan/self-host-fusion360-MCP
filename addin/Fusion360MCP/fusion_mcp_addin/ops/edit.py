"""Timeline / editing operations: undo, redo, delete-all, suppress features."""

import adsk.core
import adsk.fusion

from ._common import op, optional, require
from ..bridge.protocol import ERR_NOT_FOUND, OpError


def _run_command(ctx, command_id):
    cmd = ctx.ui.commandDefinitions.itemById(command_id)
    if not cmd:
        raise OpError(ERR_NOT_FOUND, "Command '{}' not available.".format(command_id))
    cmd.execute()
    adsk.doEvents()


@op("edit.undo", summary="Undo the last operation (guards against a parametric->direct design-type flip).")
def undo(ctx, params):
    design = ctx.design()
    before = design.designType
    _run_command(ctx, "UndoCommand")
    if design.designType != before:
        # Undo silently converted the design; reverse it.
        _run_command(ctx, "RedoCommand")
        raise OpError(
            ERR_NOT_FOUND,
            "Undo would change the design type (parametric<->direct); reverted. Avoid undoing past the base feature.",
        )
    return {"undone": True}


@op("edit.redo", summary="Redo the last undone operation.")
def redo(ctx, params):
    _run_command(ctx, "RedoCommand")
    return {"redone": True}


@op("edit.delete_all", summary="Delete every timeline feature (clears the design). Destructive.", destructive=True)
def delete_all(ctx, params):
    timeline = ctx.design().timeline
    deleted = 0
    for i in range(timeline.count - 1, -1, -1):
        try:
            timeline.item(i).deleteMe()
            deleted += 1
        except Exception:
            pass
    return {"deleted": deleted, "remaining": ctx.design().timeline.count}


def _find_timeline_entity(design, name):
    tl = design.timeline
    for i in range(tl.count):
        item = tl.item(i)
        try:
            if item.entity and item.entity.name == name:
                return item
        except Exception:
            continue
    raise OpError(ERR_NOT_FOUND, "No timeline feature named '{}'.".format(name))


@op("edit.suppress_feature", summary="Suppress a timeline feature by name.", idempotent=True)
def suppress_feature(ctx, params):
    item = _find_timeline_entity(ctx.design(), require(params, "name", str))
    item.isSuppressed = True
    return {"name": params["name"], "is_suppressed": True}


@op("edit.unsuppress_feature", summary="Unsuppress a timeline feature by name.", idempotent=True)
def unsuppress_feature(ctx, params):
    item = _find_timeline_entity(ctx.design(), require(params, "name", str))
    item.isSuppressed = False
    return {"name": params["name"], "is_suppressed": False}
