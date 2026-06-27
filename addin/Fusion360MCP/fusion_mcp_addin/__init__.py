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
    )
    dispatcher.register()
    RUNTIME["dispatcher"] = dispatcher

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

    _state.update(server=server, thread=thread, dispatcher=dispatcher)
    log(
        "Fusion360MCP started on http://{}:{} (auth={}, arbitrary_code={}, ops={})".format(
            cfg["bind"],
            cfg["port"],
            "on" if token else "off",
            "on" if cfg["allow_arbitrary_code"] else "off",
            len(REGISTRY),
        )
    )


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

    _state.clear()
    log("Fusion360MCP stopped.")
