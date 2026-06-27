"""Parameter operations: list / get / set / create.

Parameters are the heart of parametric CAD — driving features by named values
lets Claude edit a model robustly (vs. brittle absolute coordinates).
"""

from ._common import op, optional, require
from ..bridge.protocol import ERR_NOT_FOUND, OpError


def _param_dict(ctx, p):
    return {
        "name": p.name,
        "expression": p.expression,
        "value_internal_cm": p.value,
        "unit": p.unit,
        "comment": p.comment,
    }


@op("parameter.list", summary="List all parameters (user + model).", readonly=True)
def list_params(ctx, params):
    design = ctx.design()
    allp = design.allParameters
    return {
        "count": allp.count,
        "parameters": [_param_dict(ctx, allp.item(i)) for i in range(allp.count)],
    }


@op("parameter.get", summary="Get one parameter by name.", readonly=True)
def get_param(ctx, params):
    name = require(params, "name", str)
    p = ctx.design().allParameters.itemByName(name)
    if p is None:
        raise OpError(ERR_NOT_FOUND, "No parameter named '{}'.".format(name))
    return _param_dict(ctx, p)


@op("parameter.set", summary="Set a parameter's expression (e.g. '25 mm' or 'width*2').", idempotent=True)
def set_param(ctx, params):
    name = require(params, "name", str)
    expression = require(params, "expression", (str, int, float))
    p = ctx.design().allParameters.itemByName(name)
    if p is None:
        raise OpError(ERR_NOT_FOUND, "No parameter named '{}'.".format(name))
    p.expression = str(expression)
    return _param_dict(ctx, p)


@op("parameter.create", summary="Create a user parameter.", params=[])
def create_param(ctx, params):
    import adsk.core

    name = require(params, "name", str)
    expression = require(params, "expression", (str, int, float))
    unit = optional(params, "unit", "mm", types=str)
    comment = optional(params, "comment", "", types=str)
    user_params = ctx.design().userParameters
    if user_params.itemByName(name) is not None:
        raise OpError(ERR_NOT_FOUND, "Parameter '{}' already exists; use parameter.set.".format(name))
    value_input = adsk.core.ValueInput.createByString(str(expression))
    p = user_params.add(name, value_input, unit, comment)
    return _param_dict(ctx, p)


@op("parameter.delete", summary="Delete a user parameter by name (model parameters cannot be deleted).", destructive=True)
def delete_param(ctx, params):
    name = require(params, "name", str)
    p = ctx.design().userParameters.itemByName(name)
    if p is None:
        raise OpError(
            ERR_NOT_FOUND,
            "No user parameter named '{}'. Only user parameters can be deleted.".format(name),
        )
    p.deleteMe()
    return {"deleted": name}
