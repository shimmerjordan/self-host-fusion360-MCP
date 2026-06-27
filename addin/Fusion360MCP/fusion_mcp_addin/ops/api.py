"""Generic Fusion API access — the "full coverage" escape hatch.

A single op (``api.call``) can invoke ANY ``adsk.*`` method or read any property
by dotted path, construct argument objects, and store/reference results across
calls. Plus ``api.introspect`` (live ``inspect`` of the API) and ``api.docs`` (a
cloudhelp URL). Adapted from AuraFriday's design, with safer argument handling
and a proper constructor factory table.

``api.call`` is gated behind ``allow_arbitrary_code`` (it can do anything Fusion
can). ``api.introspect`` / ``api.docs`` are read-only and always available.

Reference forms in args/kwargs:
  - ``{"$ref": "name"}``    -> a previously stored object (api.call store_as)
  - ``{"$path": "design.rootComponent"}`` -> resolve a dotted API path
  - ``{"type": "Point3D", "x": 1, "y": 2, "z": 0}`` -> construct an object
  - plain numbers/bools/strings pass through literally
"""

import inspect
import re

import adsk.core
import adsk.fusion

from ._common import op, optional, require
from ..bridge.protocol import ERR_INVALID_PARAMS, ERR_NOT_ALLOWED, OpError

# Cross-call object store for $ref.
CONTEXT = {}


def _navigate(obj, path):
    for part in path.split("."):
        if not part:
            continue
        obj = getattr(obj, part)
    return obj


def _resolve_path(path):
    if not isinstance(path, str) or not path:
        raise OpError(ERR_INVALID_PARAMS, "api_path must be a non-empty string.")
    if path.startswith("$"):
        name, _, tail = path[1:].partition(".")
        if name not in CONTEXT:
            raise OpError(ERR_INVALID_PARAMS, "No stored object '{}'. Stored: {}".format(name, list(CONTEXT)))
        return _navigate(CONTEXT[name], tail) if tail else CONTEXT[name]
    if path.startswith("adsk.core."):
        return _navigate(adsk.core, path[len("adsk.core."):])
    if path.startswith("adsk.fusion."):
        return _navigate(adsk.fusion, path[len("adsk.fusion."):])
    app = adsk.core.Application.get()
    roots = {
        "app": app,
        "ui": app.userInterface,
        "design": adsk.fusion.Design.cast(app.activeProduct) or app.activeProduct,
        "rootComponent": adsk.fusion.Design.cast(app.activeProduct).rootComponent
        if adsk.fusion.Design.cast(app.activeProduct) else None,
    }
    head, _, tail = path.partition(".")
    if head in roots:
        base = roots[head]
        return _navigate(base, tail) if tail else base
    # fall back to app.<path>
    return _navigate(app, path)


_FACTORIES = {
    "Point3D": lambda p: adsk.core.Point3D.create(p.get("x", 0), p.get("y", 0), p.get("z", 0)),
    "Point2D": lambda p: adsk.core.Point2D.create(p.get("x", 0), p.get("y", 0)),
    "Vector3D": lambda p: adsk.core.Vector3D.create(p.get("x", 0), p.get("y", 0), p.get("z", 0)),
    "ObjectCollection": lambda p: adsk.core.ObjectCollection.create(),
}


def _construct(spec):
    obj_type = spec.get("type")
    if not obj_type:
        raise OpError(ERR_INVALID_PARAMS, "constructor spec needs a 'type'.")
    params = {k: _resolve_arg(v) for k, v in spec.items() if k != "type"}
    if obj_type in _FACTORIES:
        return _FACTORIES[obj_type](params)
    if obj_type == "ValueInput":
        if "expression" in params:
            return adsk.core.ValueInput.createByString(str(params["expression"]))
        return adsk.core.ValueInput.createByReal(float(params.get("value", 0)))
    cls = getattr(adsk.core, obj_type, None) or getattr(adsk.fusion, obj_type, None) or getattr(adsk.cam, obj_type, None)
    if cls is None:
        raise OpError(ERR_INVALID_PARAMS, "Unknown type '{}'.".format(obj_type))
    if hasattr(cls, "create"):
        try:
            return cls.create(**params)
        except TypeError:
            return cls.create(*params.values())
    return cls(**params)


def _resolve_arg(arg):
    if arg is None or isinstance(arg, (bool, int, float)):
        return arg
    if isinstance(arg, str):
        return arg  # strings are literal; use {"$path":...}/{"$ref":...} for references
    if isinstance(arg, list):
        return [_resolve_arg(x) for x in arg]
    if isinstance(arg, dict):
        if "$ref" in arg:
            return _resolve_path("$" + arg["$ref"])
        if "$path" in arg:
            return _resolve_path(arg["$path"])
        if "type" in arg:
            return _construct(arg)
    return arg


def _describe(result):
    if result is None or isinstance(result, (str, int, float, bool)):
        return result
    t = type(result).__name__
    for attr in ("name", "count", "value"):
        try:
            if hasattr(result, attr):
                return "{}({}={})".format(t, attr, getattr(result, attr))
        except Exception:
            pass
    try:
        return result.objectType
    except Exception:
        return t


@op("api.call", summary="Call ANY adsk.* method / read any property by dotted path (full-coverage power tool).")
def call(ctx, params):
    from .. import config

    if not config.get_settings().get("allow_arbitrary_code", False):
        raise OpError(
            ERR_NOT_ALLOWED,
            "api.call is disabled. Enable allow_arbitrary_code in ~/.fusion-mcp/addin.json. "
            "/ api.call 已禁用，请在 ~/.fusion-mcp/addin.json 开启 allow_arbitrary_code。",
        )
    path = require(params, "path", str)
    args = [_resolve_arg(a) for a in (params.get("args") or [])]
    kwargs = {k: _resolve_arg(v) for k, v in (params.get("kwargs") or {}).items()}
    store_as = optional(params, "store_as", None, types=str)
    return_properties = params.get("return_properties") or []

    target = _resolve_path(path)
    result = target(*args, **kwargs) if callable(target) else target
    if store_as:
        CONTEXT[store_as] = result

    out = {"path": path, "result": _describe(result), "result_type": type(result).__name__}
    if store_as:
        out["stored_as"] = store_as
    if return_properties:
        props = {}
        for p in return_properties:
            try:
                props[p] = _describe(getattr(result, p))
            except Exception as exc:
                props[p] = "ERR: {}".format(exc)
        out["properties"] = props
    return out


@op("api.clear_context", summary="Clear stored api.call objects ($ref store).", idempotent=True)
def clear_context(ctx, params):
    n = len(CONTEXT)
    CONTEXT.clear()
    return {"cleared": n}


def _clean_sig(func):
    try:
        s = str(inspect.signature(func))
    except (TypeError, ValueError):
        return "(...)"
    s = s.replace("(self, ", "(").replace("(self)", "()").replace("'", "")
    s = re.sub(r"adsk\.\w+\.Ptr<([^>]+)>", r"\1", s)
    return s


@op("api.introspect", summary="List a class/object's properties & methods with signatures (live inspect).", readonly=True)
def introspect(ctx, params):
    target = require(params, "target", str)
    query = (optional(params, "query", "", types=str) or "").lower()
    cls = None
    # try as a live path first, then as a class name in adsk modules
    try:
        obj = _resolve_path(target)
        cls = type(obj)
    except Exception:
        for mod in (adsk.core, adsk.fusion, adsk.cam):
            cls = getattr(mod, target, None)
            if isinstance(cls, type):
                break
    if not isinstance(cls, type):
        raise OpError(ERR_INVALID_PARAMS, "Could not resolve '{}' to a class or object.".format(target))

    props, methods = [], []
    for name, member in vars(cls).items():
        if name.startswith("_") or name in ("thisown", "cast"):
            continue
        if query and query not in name.lower():
            continue
        if isinstance(member, property):
            props.append({"name": name, "read_only": member.fset is None})
        elif callable(member):
            methods.append({"name": name, "signature": _clean_sig(member)})
    return {"class": cls.__name__, "properties": props, "methods": methods}


@op("api.docs", summary="Get the Autodesk cloudhelp URL for a class or member (e.g. 'ExtrudeFeatures.createInput').", readonly=True)
def docs(ctx, params):
    name = require(params, "name", str)
    base = "https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files"
    if "." in name:
        cls, _, member = name.partition(".")
        filename = "{}_{}.htm".format(cls, member)
    else:
        filename = "{}.htm".format(name)
    return {"name": name, "url": "{}/{}".format(base, filename)}
