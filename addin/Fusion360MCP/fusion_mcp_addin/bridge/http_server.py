"""Local HTTP server for the bridge (runs on a daemon worker thread).

Endpoints
---------
GET  /health  -> liveness + capability flags (no auth; never touches adsk.*)
GET  /ops     -> list of op names + metadata (no auth; static data only)
POST /rpc     -> {"op", "params"} executed on Fusion's main thread (bearer auth)

Only operational results cross as JSON; auth/parse faults use HTTP 4xx.
"""

import hmac
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

from . import protocol


class BridgeServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, address, context):
        super().__init__(address, _BridgeHandler)
        self.ctx = context


class _BridgeHandler(BaseHTTPRequestHandler):
    server_version = "Fusion360MCP/" + protocol.__dict__.get("__version__", "0.1.0")
    protocol_version = "HTTP/1.1"

    # ---- helpers -----------------------------------------------------------
    def _send_json(self, code, payload):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        try:
            self.wfile.write(body)
        except Exception:
            pass

    def _auth_ok(self):
        token = self.server.ctx.get("token")
        if not token:
            return True  # auth disabled (token could not be persisted)
        header = self.headers.get("Authorization", "")
        prefix = "Bearer "
        if not header.startswith(prefix):
            return False
        return hmac.compare_digest(header[len(prefix):], token)

    def _log(self, message):
        log = self.server.ctx.get("log")
        if log:
            log(message)

    # ---- routes ------------------------------------------------------------
    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/health":
            self._send_json(
                200,
                {
                    "ok": True,
                    "service": "fusion360-mcp-addin",
                    "version": self.server.ctx.get("version", "0.1.0"),
                    "auth_required": bool(self.server.ctx.get("token")),
                    "allow_arbitrary_code": bool(
                        self.server.ctx.get("config", {}).get("allow_arbitrary_code")
                    ),
                    "op_count": len(self.server.ctx.get("meta", [])),
                },
            )
        elif path == "/ops":
            meta = self.server.ctx.get("meta", [])
            self._send_json(
                200,
                {"ok": True, "ops": [m["name"] for m in meta], "meta": meta},
            )
        else:
            self._send_json(404, protocol.err("not_found", "No such endpoint: " + path))

    def do_POST(self):
        path = urlparse(self.path).path
        if path != "/rpc":
            self._send_json(404, protocol.err("not_found", "No such endpoint: " + path))
            return

        if not self._auth_ok():
            self._send_json(
                401,
                protocol.err(
                    "unauthorized",
                    "Missing or invalid bearer token.",
                    "Set the Authorization header to 'Bearer <token>'. The token "
                    "lives in ~/.fusion-mcp/token.",
                ),
            )
            return

        try:
            length = int(self.headers.get("Content-Length") or 0)
            raw = self.rfile.read(length) if length else b""
            data = json.loads(raw.decode("utf-8")) if raw else {}
        except Exception as exc:
            self._send_json(400, protocol.err("bad_request", "Invalid JSON body.", str(exc)))
            return

        op = data.get("op")
        params = data.get("params") or {}
        if not isinstance(op, str) or not op:
            self._send_json(
                400, protocol.err("bad_request", "Missing 'op' (string) in request body.")
            )
            return
        if not isinstance(params, dict):
            self._send_json(
                400, protocol.err("bad_request", "'params' must be an object.")
            )
            return

        dispatcher = self.server.ctx["dispatcher"]
        try:
            result = dispatcher.submit(op, params)
            self._send_json(200, protocol.ok(result))
        except protocol.OpError as oe:
            # Operational failure -> 200 + ok:false (uniform parsing on the server).
            self._send_json(200, protocol.err(oe.code, oe.message, oe.detail))
        except Exception as exc:  # noqa: BLE001
            self._send_json(
                500, protocol.err("internal_error", str(exc) or "Unhandled error.")
            )

    # ---- silence default stderr logging; route to our log file -------------
    def log_message(self, fmt, *args):
        try:
            self._log("http: " + (fmt % args))
        except Exception:
            pass
