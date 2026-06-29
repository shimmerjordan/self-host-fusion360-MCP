"""In-Fusion MCP bridge add-in.

Architecture
------------
An external MCP server process cannot call Fusion's ``adsk.*`` API directly:
that API is single-threaded and only valid on Fusion's main thread. So this
add-in runs *inside* Fusion and exposes a small local HTTP server (on a worker
thread). Each incoming request is marshalled onto Fusion's main thread via a
registered custom event, executed there, and the result handed back to the
worker thread that is blocking on a per-request ``threading.Event``.

    HTTP worker thread          main (UI) thread
    ------------------          ----------------
    submit(op, params)  --fireCustomEvent(id)-->  notify() -> ops[op](ctx, params)
            |                                                       |
            +------------------ Event.set() <-----------------------+

Only the Python standard library is used here — Fusion's bundled Python cannot
``pip install`` third-party packages.
"""

import os
import subprocess
import sys
import threading

import adsk.core

from . import config
from .bridge.dispatcher import Dispatcher
from .bridge.http_server import BridgeServer
from .ops import OPS_META, REGISTRY
from .ops._common import RUNTIME

__version__ = config.VERSION

_state = {}


def log(message):
    """Append a line to the add-in log file (best effort)."""
    config.log(message)


class _RestartHandler(adsk.core.CustomEventHandler):
    """Runs on the main thread (deferred via a Timer by system.restart) and does a
    full in-process reload: stop() → purge package modules → re-import → start().
    This applies bridge/__init__ code changes without a manual Fusion Stop→Run."""

    def notify(self, args):
        _do_restart()


def _do_restart():
    import importlib

    pkg = __package__ or __name__
    log("restart: stopping current bridge ...")
    try:
        stop()
    except Exception as exc:  # noqa: BLE001
        config.log("restart: stop error: {}".format(exc))
    # Purge every package module so the fresh import picks up on-disk edits.
    for name in [n for n in list(sys.modules) if n == pkg or n.startswith(pkg + ".")]:
        sys.modules.pop(name, None)
    try:
        mod = importlib.import_module(pkg)
        mod.start()
        config.log("restart: complete — re-imported {} fresh from disk.".format(pkg))
    except Exception as exc:  # noqa: BLE001
        config.log("restart: start error: {}".format(exc))


def start():
    """Start the bridge. Called from the add-in ``run(context)``."""
    if _state.get("server") is not None:
        log("start() called but server already running; ignoring.")
        return

    cfg = config.get_settings()
    token = config.ensure_token()
    app = adsk.core.Application.get()

    # Keep the add-in resident after run() returns.
    adsk.autoTerminate(False)

    readonly_ops = {m["name"] for m in OPS_META if m.get("readonly")}
    dispatcher = Dispatcher(
        app,
        REGISTRY,
        request_timeout=cfg["request_timeout"],
        readonly_ops=readonly_ops,
        busy_file=str(config.BUSY_FILE) if cfg.get("auto_dismiss_dialogs", True) else None,
    )
    dispatcher.register()
    RUNTIME["dispatcher"] = dispatcher

    # Restart channel: a dedicated custom event so `system.restart` can trigger a
    # full in-process reload on the main thread (see _RestartHandler).
    try:
        app.unregisterCustomEvent(config.RESTART_EVENT_ID)
    except Exception:
        pass
    restart_event = app.registerCustomEvent(config.RESTART_EVENT_ID)
    restart_handler = _RestartHandler()
    restart_event.add(restart_handler)

    guard = None
    if cfg.get("auto_dismiss_dialogs", True):
        guard = _start_dialog_guard(cfg)

    server = BridgeServer(
        (cfg["bind"], int(cfg["port"])),
        context={
            "token": token,
            "dispatcher": dispatcher,
            "meta": OPS_META,
            "config": cfg,
            "version": config.VERSION,
            "log": log,
        },
    )
    thread = threading.Thread(
        target=server.serve_forever, name="fusion-mcp-http", daemon=True
    )
    thread.start()

    _state.update(
        server=server, thread=thread, dispatcher=dispatcher, guard=guard,
        restart_event=restart_event, restart_handler=restart_handler,
    )
    log(
        "Fusion360MCP started on http://{}:{} (auth={}, arbitrary_code={}, ops={})".format(
            cfg["bind"],
            cfg["port"],
            "on" if token else "off",
            "on" if cfg["allow_arbitrary_code"] else "off",
            len(REGISTRY),
        )
    )


def _python_exe():
    """Path to the Python interpreter to run the guard with. Fusion's
    ``sys.executable`` points at Fusion360.exe (not python.exe), so derive the
    bundled interpreter from the prefix — confirmed at
    ``<base_exec_prefix>/python.exe``."""
    exe = sys.executable or ""
    if os.path.basename(exe).lower().startswith("python"):
        return exe
    for prefix in (sys.base_exec_prefix, sys.base_prefix, sys.prefix):
        cand = os.path.join(prefix, "python.exe")
        if os.path.exists(cand):
            return cand
    return exe  # last resort — let Popen surface the error to the log


def _start_dialog_guard(cfg):
    """Launch the external dialog-guard process (see bridge/dialog_guard.py for
    why it must be a separate process). Best effort: a failure here never blocks
    the bridge from starting. Windows only (the guard uses Win32)."""
    if os.name != "nt":
        return None
    try:
        guard_path = os.path.join(os.path.dirname(__file__), "bridge", "dialog_guard.py")
        titles = ",".join(cfg.get("dialog_titles", []) or [])
        args = [
            _python_exe(), guard_path,
            "--pid", str(os.getpid()),
            "--busy-file", str(config.BUSY_FILE),
            "--log", str(config.LOG_FILE),
            "--poll", str(cfg.get("dialog_poll", 1.0)),
            "--grace", str(cfg.get("dialog_grace", 1.5)),
            "--grace-allow", str(cfg.get("dialog_grace_allow", 4.0)),
            "--titles", titles,
        ]
        creationflags = 0
        if os.name == "nt":
            creationflags = 0x08000000  # CREATE_NO_WINDOW (no console flash)
        proc = subprocess.Popen(
            args,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=creationflags,
            close_fds=True,
        )
        log("dialog guard started (pid={}, target={}).".format(proc.pid, os.getpid()))
        return proc
    except Exception as exc:  # pragma: no cover - defensive
        log("dialog guard failed to start: {}".format(exc))
        return None


def stop():
    """Stop the bridge. Called from the add-in ``stop(context)``."""
    server = _state.get("server")
    if server is not None:
        try:
            server.shutdown()
            server.server_close()
        except Exception as exc:  # pragma: no cover - defensive
            log("server shutdown error: {}".format(exc))

    dispatcher = _state.get("dispatcher")
    if dispatcher is not None:
        try:
            dispatcher.unregister()
        except Exception as exc:  # pragma: no cover - defensive
            log("dispatcher unregister error: {}".format(exc))

    guard = _state.get("guard")
    if guard is not None:
        try:
            guard.terminate()
        except Exception as exc:  # pragma: no cover - defensive
            log("dialog guard stop error: {}".format(exc))

    restart_event = _state.get("restart_event")
    restart_handler = _state.get("restart_handler")
    try:
        if restart_event is not None and restart_handler is not None:
            restart_event.remove(restart_handler)
    except Exception:
        pass
    try:
        app = adsk.core.Application.get()
        app.unregisterCustomEvent(config.RESTART_EVENT_ID)
    except Exception:
        pass
    try:
        if config.BUSY_FILE.exists():
            config.BUSY_FILE.unlink()
    except Exception:
        pass

    _state.clear()
    log("Fusion360MCP stopped.")
