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

import adsk.core

from ._common import RUNTIME, op

_PKG = "fusion_mcp_addin.ops"
_COMMON = _PKG + "._common"
_ROOT_PKG = "fusion_mcp_addin"
# Must match config.RESTART_EVENT_ID. Kept as a local literal because system.reload
# does NOT reload the package-level config module, so a freshly-added config
# attribute isn't visible here until a full restart.
_RESTART_EVENT_ID = "fusion360_mcp_restart_event"


class _OpRestartHandler(adsk.core.CustomEventHandler):
    """Self-contained restart handler registered from a (hot-reloadable) op, so
    the restart capability can be bootstrapped via system.reload — WITHOUT a
    Fusion Stop→Run — even when the currently-running __init__ predates it. Does a
    full stop → purge package modules → re-import → start on the main thread."""

    def notify(self, args):
        from .. import config as _config

        mod = sys.modules.get(_ROOT_PKG)
        try:
            if mod is not None:
                mod.stop()
        except Exception as exc:  # noqa: BLE001
            _config.log("restart: stop error: {}".format(exc))
        for name in [n for n in list(sys.modules) if n == _ROOT_PKG or n.startswith(_ROOT_PKG + ".")]:
            sys.modules.pop(name, None)
        try:
            fresh = importlib.import_module(_ROOT_PKG)
            fresh.start()
            _config.log("restart: complete — re-imported {} fresh from disk.".format(_ROOT_PKG))
        except Exception as exc:  # noqa: BLE001
            _config.log("restart: start error: {}".format(exc))


def _ensure_restart_channel(ctx):
    """Register (idempotently, unregister-first) the restart custom event + handler
    so system.restart can fire it. Runs on the main thread (called from an op).
    The handler ref is kept in RUNTIME so it survives system.reload."""
    app = ctx.app
    old_event = RUNTIME.get("restart_event")
    old_handler = RUNTIME.get("restart_handler")
    try:
        if old_event is not None and old_handler is not None:
            old_event.remove(old_handler)
    except Exception:
        pass
    try:
        app.unregisterCustomEvent(_RESTART_EVENT_ID)
    except Exception:
        pass
    event = app.registerCustomEvent(_RESTART_EVENT_ID)
    handler = _OpRestartHandler()
    event.add(handler)
    RUNTIME["restart_event"] = event
    RUNTIME["restart_handler"] = handler


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

    # Bootstrap the restart channel so system.restart works even if the running
    # __init__ predates it (lets us avoid a manual Stop→Run entirely).
    restart_ready = False
    try:
        _ensure_restart_channel(ctx)
        restart_ready = True
    except Exception:
        pass

    return {
        "reloaded": True,
        "ops_before": before,
        "ops_after": len(registry),
        "restart_channel_ready": restart_ready,
    }


@op("system.test_dialog", summary="Dev: pop a modal messageBox to verify the auto-dismiss watchdog closes it.", readonly=True)
def test_dialog(ctx, params):
    import time as _t

    t0 = _t.monotonic()
    # This blocks the main thread until the dialog is dismissed. If the watchdog
    # works, it closes it within a couple seconds and this returns on its own.
    ctx.ui.messageBox("MCP dialog-watchdog self-test.\nThis should auto-close.",
                      "Fusion360MCP self-test")
    return {"messagebox_returned": True, "blocked_seconds": round(_t.monotonic() - t0, 2)}


@op(
    "system.restart",
    summary="Full in-process reload (stop→reimport→start) of the WHOLE add-in incl. bridge/__init__ — no Fusion Stop→Run needed. Use after changing bridge code; reconnect after ~1-2s.",
    readonly=True,
)
def restart(ctx, params):
    import threading

    app = ctx.app
    delay = float(params.get("delay", 0.6))

    # Make sure the restart channel exists (self-bootstrap on the main thread),
    # so this works without any prior Stop→Run.
    _ensure_restart_channel(ctx)

    def fire():
        try:
            app.fireCustomEvent(_RESTART_EVENT_ID, "")
        except Exception:
            pass

    # Defer off the request thread: doing the teardown inline would deadlock
    # (server.shutdown waits on the very request handler we're running in). The
    # timer lets this response flush first; the restart then runs on the main
    # thread via the dedicated custom event.
    threading.Timer(delay, fire).start()
    return {
        "restarting": True,
        "delay_seconds": delay,
        "note": "Bridge will stop, re-import all modules from disk, and start. Reconnect in ~1-2s.",
    }


@op("system.pyinfo", summary="Dev: report the embedded Python interpreter paths (to locate python.exe for the guard).", readonly=True)
def pyinfo(ctx, params):
    import os as _os

    cands = {
        "sys.executable": sys.executable,
        "base_exec_prefix/python.exe": _os.path.join(sys.base_exec_prefix, "python.exe"),
        "base_prefix/python.exe": _os.path.join(sys.base_prefix, "python.exe"),
        "prefix/python.exe": _os.path.join(sys.prefix, "python.exe"),
    }
    return {
        "executable": sys.executable,
        "base_prefix": sys.base_prefix,
        "base_exec_prefix": sys.base_exec_prefix,
        "prefix": sys.prefix,
        "candidates": {k: {"path": v, "exists": _os.path.exists(v)} for k, v in cands.items()},
    }


@op("system.info", summary="Bridge runtime info (op count, version, flags).", readonly=True)
def info(ctx, params):
    from .. import config

    return {
        "version": config.VERSION,
        "ops": len(sys.modules[_COMMON].REGISTRY),
        "allow_arbitrary_code": config.get_settings().get("allow_arbitrary_code", False),
        "auto_create_document": config.get_settings().get("auto_create_document", True),
    }
