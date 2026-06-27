"""Marshal RPC calls from the HTTP worker thread onto Fusion's main thread.

Fusion's API must only be touched on the main thread. We use the documented
custom-event mechanism: a worker thread enqueues a job and calls
``app.fireCustomEvent(EVENT_ID, request_id)`` (``fireCustomEvent`` lives on
*Application*, not on the CustomEvent object; ``additionalInfo`` is a string).
The registered handler's ``notify()`` runs on the main thread and *drains all
pending jobs*. A 250 ms backup timer re-fires the event whenever jobs remain, so
a single missed/dropped event can never wedge the queue. Each worker blocks on
its own ``threading.Event`` until the main thread stores a result — giving real
request/response semantics (success OR error), unlike fire-and-forget designs.
"""

import threading
import traceback
import uuid

import adsk.core
import adsk.fusion

from ..config import EVENT_ID
from .protocol import (
    ERR_INTERNAL,
    ERR_TIMEOUT,
    ERR_UNKNOWN_OP,
    OpError,
    hint_for_exception,
)

_DRAIN_SIGNAL = "__drain__"


class _CustomEventHandler(adsk.core.CustomEventHandler):
    def __init__(self, dispatcher):
        super().__init__()
        self._dispatcher = dispatcher

    def notify(self, args):
        # Runs on Fusion's MAIN thread. Drain everything that's pending.
        self._dispatcher._drain()


class Dispatcher:
    def __init__(self, app, registry, request_timeout=30, readonly_ops=None):
        self._app = app
        self._registry = registry
        self._timeout = request_timeout
        self._readonly = set(readonly_ops or [])
        self._pending = {}
        self._lock = threading.Lock()
        self._custom_event = None
        self._handler = None
        self._timer = None
        self._stop = threading.Event()

    # ---- lifecycle ---------------------------------------------------------
    def register(self):
        try:
            self._app.unregisterCustomEvent(EVENT_ID)
        except Exception:
            pass
        self._custom_event = self._app.registerCustomEvent(EVENT_ID)
        self._handler = _CustomEventHandler(self)
        self._custom_event.add(self._handler)

        # Backup drain timer: re-fire while jobs remain (defends against a
        # dropped fireCustomEvent from a worker thread).
        self._stop.clear()
        self._timer = threading.Thread(
            target=self._timer_loop, name="fusion-mcp-drain", daemon=True
        )
        self._timer.start()

    def unregister(self):
        self._stop.set()
        try:
            if self._custom_event and self._handler:
                self._custom_event.remove(self._handler)
        except Exception:
            pass
        try:
            self._app.unregisterCustomEvent(EVENT_ID)
        except Exception:
            pass
        self._custom_event = None
        self._handler = None

    def refresh_readonly(self, readonly_ops):
        """Update the readonly-op set (used after a hot reload)."""
        self._readonly = set(readonly_ops or [])

    def _timer_loop(self):
        while not self._stop.wait(0.25):
            with self._lock:
                has_pending = bool(self._pending)
            if has_pending:
                try:
                    self._app.fireCustomEvent(EVENT_ID, _DRAIN_SIGNAL)
                except Exception:
                    break

    # ---- worker-thread side ------------------------------------------------
    def submit(self, op, params, timeout=None):
        """Block the calling (worker) thread until the op runs on the main thread."""
        if op not in self._registry:
            raise OpError(
                ERR_UNKNOWN_OP,
                "Unknown operation: {}".format(op),
                "Known ops: {}".format(", ".join(sorted(self._registry))),
            )

        request_id = uuid.uuid4().hex
        event = threading.Event()
        box = {}
        with self._lock:
            self._pending[request_id] = {
                "op": op,
                "params": params or {},
                "event": event,
                "box": box,
            }

        # fireCustomEvent lives on Application, not on the CustomEvent object.
        self._app.fireCustomEvent(EVENT_ID, request_id)

        wait_for = self._timeout if timeout is None else timeout
        if not event.wait(wait_for):
            with self._lock:
                self._pending.pop(request_id, None)
            raise OpError(
                ERR_TIMEOUT,
                "Operation timed out after {}s.".format(wait_for),
                "Fusion may be busy, mid-command, or showing a modal dialog. "
                "Close any open dialog and retry. / Fusion 可能正忙或有对话框打开，"
                "请关闭对话框后重试。",
            )

        if "error" in box:
            e = box["error"]
            raise OpError(e["code"], e["message"], e.get("detail", ""))
        return box.get("result")

    # ---- main-thread side --------------------------------------------------
    def _drain(self):
        """Process every pending job (runs on the main thread)."""
        while True:
            with self._lock:
                if not self._pending:
                    return
                request_id = next(iter(self._pending))
                job = self._pending.pop(request_id)
            self._execute(job)

    def _execute(self, job):
        from ..ops._common import Ctx

        box = job["box"]
        op = job["op"]
        try:
            self._terminate_active_command()
            ctx = Ctx()
            mutating = op not in self._readonly
            before = self._snapshot(ctx) if mutating else None

            result = self._registry[op](ctx, job["params"])

            if mutating and isinstance(result, dict):
                after = self._snapshot(ctx)
                delta = self._delta(before, after)
                if delta is not None:
                    result.setdefault("_delta", delta)
            box["result"] = result
        except OpError as oe:
            box["error"] = oe.to_dict()
        except Exception as exc:  # noqa: BLE001 - surface everything to the caller
            detail = traceback.format_exc()
            hint = hint_for_exception(exc)
            if hint:
                detail = hint + "\n---\n" + detail
            box["error"] = {
                "code": ERR_INTERNAL,
                "message": str(exc) or exc.__class__.__name__,
                "detail": detail,
            }
        finally:
            job["event"].set()

    # ---- helpers -----------------------------------------------------------
    def _snapshot(self, ctx):
        """Cheap state snapshot for before/after deltas (body count)."""
        try:
            design = adsk.fusion.Design.cast(ctx.app.activeProduct)
            if design is None:
                return None
            return {"bodies": design.rootComponent.bRepBodies.count}
        except Exception:
            return None

    @staticmethod
    def _delta(before, after):
        if not before or not after:
            return None
        db = after.get("bodies", 0) - before.get("bodies", 0)
        return {
            "bodies_before": before.get("bodies"),
            "bodies_after": after.get("bodies"),
            "bodies_added": db,
        }

    def _terminate_active_command(self):
        """Documented idiom: end any interactive command before mutating."""
        try:
            ui = self._app.userInterface
            if ui.activeCommand and ui.activeCommand != "SelectCommand":
                ui.commandDefinitions.itemById("SelectCommand").execute()
        except Exception:
            pass
