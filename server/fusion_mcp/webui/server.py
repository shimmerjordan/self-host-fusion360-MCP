"""Local config dashboard: a stdlib http.server serving a single-page UI + a
small JSON API. Loopback-only by default; /api/* requires a per-session token
(injected into the page) to block drive-by CSRF from other local pages.
"""

import hmac
import json
import secrets
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from .. import __version__, clientconfig
from ..client import AddinClient
from ..config import load_config
from ..errors import FusionMCPError

_INDEX = Path(__file__).parent / "index.html"


def _status():
    cfg = load_config()
    out = {
        "version": __version__,
        "server": {
            "addin_url": cfg.addin_url,
            "transport": cfg.transport,
            "http_host": cfg.http_host,
            "http_port": cfg.http_port,
            "mock": cfg.mock,
        },
        "settings": clientconfig.read_settings(),
        "token_present": bool(clientconfig.read_token()),
    }
    client = AddinClient(cfg)
    try:
        health = client.health()
        bridge = {"reachable": True}
        bridge.update(health)
        try:
            bridge["ops"] = len(client.list_ops())
        except Exception:
            pass
        out["bridge"] = bridge
    except FusionMCPError as exc:
        out["bridge"] = {"reachable": False, "error": str(exc).splitlines()[0]}
    except Exception as exc:  # noqa: BLE001
        out["bridge"] = {"reachable": False, "error": str(exc)}
    finally:
        client.close()
    return out


class _Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    # ── helpers ──────────────────────────────────────────────────────────────
    def _send(self, code, body, content_type="application/json; charset=utf-8"):
        if isinstance(body, (dict, list)):
            body = json.dumps(body, ensure_ascii=False)
        data = body.encode("utf-8") if isinstance(body, str) else body
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        try:
            self.wfile.write(data)
        except Exception:
            pass

    def _authed(self):
        token = self.server.session_token
        return hmac.compare_digest(self.headers.get("X-Fusion-UI-Token", ""), token)

    def _body(self):
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b""
        return json.loads(raw.decode("utf-8")) if raw else {}

    def log_message(self, *args):
        pass  # quiet

    # ── routes ───────────────────────────────────────────────────────────────
    def do_GET(self):
        path = urlparse(self.path).path
        if path in ("/", "/index.html"):
            html = _INDEX.read_text(encoding="utf-8").replace("__SESSION_TOKEN__", self.server.session_token)
            self._send(200, html, "text/html; charset=utf-8")
            return
        if not path.startswith("/api/"):
            self._send(404, {"error": "not found"})
            return
        if not self._authed():
            self._send(401, {"error": "missing or invalid UI session token"})
            return
        try:
            if path == "/api/status":
                self._send(200, _status())
            elif path == "/api/settings":
                self._send(200, clientconfig.read_settings())
            elif path == "/api/token":
                tok = clientconfig.read_token()
                self._send(200, {"present": bool(tok), "masked": clientconfig.mask_token(tok), "token": tok})
            elif path == "/api/connectors":
                self._send(200, {"connectors": clientconfig.CONNECTORS})
            else:
                self._send(404, {"error": "not found"})
        except Exception as exc:  # noqa: BLE001
            self._send(500, {"error": str(exc)})

    def do_POST(self):
        path = urlparse(self.path).path
        if not path.startswith("/api/"):
            self._send(404, {"error": "not found"})
            return
        if not self._authed():
            self._send(401, {"error": "missing or invalid UI session token"})
            return
        try:
            body = self._body()
            if path == "/api/settings":
                merged = clientconfig.write_settings(body)
                self._send(200, {"ok": True, "settings": merged,
                                 "note": "Reload the add-in in Fusion (Stop->Run) for changes to take effect."})
            elif path == "/api/token/regenerate":
                self._send(200, {"ok": True, "token": clientconfig.regenerate_token()})
            elif path == "/api/connectors/snippet":
                self._send(200, clientconfig.generate_snippet(
                    body.get("id", "claude-desktop"),
                    name=body.get("name", "fusion360"),
                    transport=body.get("transport", "stdio"),
                    http_host=body.get("http_host", "127.0.0.1"),
                    http_port=int(body.get("http_port", 8765)),
                ))
            elif path == "/api/connectors/apply":
                command, base_args = clientconfig.server_invocation()
                result = clientconfig.merge_config(
                    clientconfig.default_config_path(),
                    name=body.get("name", "fusion360"),
                    command=command, args=base_args + ["run"],
                )
                self._send(200, {"ok": True, "result": result})
            else:
                self._send(404, {"error": "not found"})
        except Exception as exc:  # noqa: BLE001
            self._send(400, {"error": str(exc)})


def serve(host="127.0.0.1", port=8088, open_browser=True):
    httpd = ThreadingHTTPServer((host, port), _Handler)
    httpd.session_token = secrets.token_urlsafe(24)
    url = "http://{}:{}/".format("127.0.0.1" if host in ("0.0.0.0", "") else host, port)
    print("Fusion MCP config UI: " + url)
    print("(loopback-only; session token protects the local API)")
    if open_browser:
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped.")
    finally:
        httpd.server_close()
    return 0
