"""The HTTP client's mock mode (lets everything run without Fusion)."""

import base64

from fusion_mcp.client import AddinClient
from fusion_mcp.config import load_config


def _client():
    return AddinClient(load_config(mock=True))


def test_generic_mock_call():
    result = _client().call("feature.extrude", {"sketch": 0, "distance": 10})
    assert result["mock"] is True
    assert result["op"] == "feature.extrude"
    assert result["params"]["distance"] == 10


def test_mock_screenshot_is_valid_base64_png():
    result = _client().call("view.screenshot", {"width": 100, "height": 50})
    assert result["mime"] == "image/png"
    assert result["width"] == 100
    decoded = base64.b64decode(result["base64"])
    assert decoded[:8] == b"\x89PNG\r\n\x1a\n"  # PNG magic


def test_mock_query_shape():
    result = _client().call("query.list_bodies")
    assert result["count"] == 0
    assert result["items"] == []
