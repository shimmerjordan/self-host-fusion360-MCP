"""Dev/maintenance ops.

``system.reload`` hot-reloads ALL op code from disk — including ``_common`` —
without a Fusion restart. _common holds the shared ``REGISTRY``/``OPS_META``/
``RUNTIME`` objects that the live Dispatcher and BridgeServer reference, so we
can't just rebind them. Instead we reload ``_common`` in place and then re-point
its module globals back to the SAME objects, preserving identity. Then we purge
and re-import every other op module (picking up new files and edits).

If this ever leaves the bridge in a bad state, a Fusion Stop->Run fully resets
it (the add-in entry purges all package modules on start).
"""

import importlib
import sys

from ._common import op

_PKG = "fusion_mcp_addin.ops"
_COMMON = _PKG + "._common"


@op(
    "system.reload",
    summary="Dev: hot-reload all op modules (incl. _common) from disk; no Fusion restart needed.",
    readonly=True,
    idempotent=True,
)
def reload(ctx, params):
    common = sys.modules[_COMMON]
    registry, ops_meta, runtime = common.REGISTRY, common.OPS_META, common.RUNTIME
    before = len(registry)

    # Clear shared collections IN PLACE (preserve object identity).
    registry.clear()
    ops_meta[:] = []

    # Reload _common, then re-point its globals back to the shared objects so the
    # Dispatcher/BridgeServer references stay valid and the @op decorator (now
    # redefined) registers into the same dict/list.
    importlib.reload(common)
    common.REGISTRY = registry
    common.OPS_META = ops_meta
    common.RUNTIME = runtime

    # Purge + re-import every other op module (handles new files and edits).
    for name in [n for n in list(sys.modules) if n.startswith(_PKG + ".") and n != _COMMON]:
        del sys.modules[name]
    sys.modules.pop(_PKG, None)
    importlib.import_module(_PKG)

    dispatcher = runtime.get("dispatcher")
    if dispatcher is not None:
        dispatcher.refresh_readonly({m["name"] for m in ops_meta if m.get("readonly")})

    return {"reloaded": True, "ops_before": before, "ops_after": len(registry)}


@op("system.info", summary="Bridge runtime info (op count, version, flags).", readonly=True)
def info(ctx, params):
    from .. import config

    return {
        "version": config.VERSION,
        "ops": len(sys.modules[_COMMON].REGISTRY),
        "allow_arbitrary_code": config.get_settings().get("allow_arbitrary_code", False),
        "auto_create_document": config.get_settings().get("auto_create_document", True),
    }
