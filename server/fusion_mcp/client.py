"""HTTP client to the in-Fusion add-in bridge.

In ``mock`` mode it returns synthetic results so the server, tests, and Docker
image work with no Fusion installed.
"""

import logging

import httpx

from .config import ServerConfig
from .errors import FusionMCPError, auth_hint, connection_hint, op_error_message

logger = logging.getLogger("fusion_mcp.client")

# A 1x1 transparent PNG, used by mock screenshots so the Image path stays valid.
_MOCK_PNG_1X1 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk"
    "+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
)

_CONNECT_EXCEPTIONS = (
    httpx.ConnectError,
    httpx.ConnectTimeout,
    httpx.ReadTimeout,
    httpx.RemoteProtocolError,
    httpx.PoolTimeout,
)


class AddinClient:
    def __init__(self, config: ServerConfig):
        self.config = config
        self._client = None

    def _http(self):
        if self._client is None:
            # trust_env=False: the bridge is always a LOCAL loopback address, so it
            # must bypass any system proxy (HTTP_PROXY/ALL_PROXY). Without this, a
            # running proxy (e.g. Clash on 127.0.0.1:7897) intercepts the request
            # and returns 502.
            self._client = httpx.Client(timeout=self.config.timeout, trust_env=False)
        return self._client

    def _headers(self):
        if self.config.token:
            return {"Authorization": "Bearer " + self.config.token}
        return {}

    def call(self, op, params=None):
        """Execute an op on Fusion and return its ``result`` (or raise)."""
        params = params or {}
        if self.config.mock:
            return _mock_result(op, params)

        try:
            resp = self._http().post(
                self.config.rpc_url,
                json={"op": op, "params": params},
                headers=self._headers(),
            )
        except _CONNECT_EXCEPTIONS as exc:
            raise FusionMCPError(connection_hint(self.config.addin_url)) from exc

        if resp.status_code == 401:
            raise FusionMCPError(auth_hint())
        if resp.status_code >= 400:
            raise FusionMCPError(
                "Bridge HTTP {}: {}".format(resp.status_code, resp.text[:500])
            )

        try:
            data = resp.json()
        except Exception as exc:  # noqa: BLE001
            raise FusionMCPError("Add-in returned a non-JSON response.") from exc

        if not data.get("ok", False):
            raise FusionMCPError(op_error_message(data.get("error", {})))
        return data.get("result")

    def health(self):
        if self.config.mock:
            return {
                "ok": True,
                "service": "mock",
                "version": "mock",
                "auth_required": False,
                "op_count": 0,
                "mock": True,
            }
        try:
            resp = self._http().get(self.config.health_url)
            return resp.json()
        except _CONNECT_EXCEPTIONS as exc:
            raise FusionMCPError(connection_hint(self.config.addin_url)) from exc

    def list_ops(self):
        if self.config.mock:
            return []
        try:
            resp = self._http().get(self.config.ops_url)
            return resp.json().get("ops", [])
        except _CONNECT_EXCEPTIONS as exc:
            raise FusionMCPError(connection_hint(self.config.addin_url)) from exc

    def close(self):
        if self._client is not None:
            self._client.close()
            self._client = None


def _mock_result(op, params):
    if op == "view.screenshot":
        return {
            "mime": "image/png",
            "base64": _MOCK_PNG_1X1,
            "width": params.get("width", 1280),
            "height": params.get("height", 720),
            "mock": True,
        }
    if op.startswith("query.") or op.endswith(".list") or op.endswith("list_appearances"):
        return {"mock": True, "op": op, "count": 0, "items": []}
    return {"mock": True, "op": op, "params": params}
