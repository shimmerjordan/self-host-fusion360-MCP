"""Tests for the shared client-config helpers (no Fusion needed)."""

import json

from fusion_mcp import clientconfig


def test_merge_preserves_other_servers_and_backs_up(tmp_path):
    cfg = tmp_path / "claude_desktop_config.json"
    cfg.write_text(
        json.dumps({"mcpServers": {"other": {"command": "x", "args": []}}, "keepMe": 1}),
        encoding="utf-8",
    )
    r = clientconfig.merge_config(cfg, "fusion360", command="fusion-mcp", args=["run"])
    assert r["action"] == "added"
    assert r["backup"] is not None
    data = json.loads(cfg.read_text(encoding="utf-8"))
    assert "other" in data["mcpServers"]
    assert "fusion360" in data["mcpServers"]
    assert data["keepMe"] == 1  # unrelated keys preserved

    r2 = clientconfig.merge_config(cfg, "fusion360", command="fusion-mcp", args=["run"])
    assert r2["action"] == "updated"  # idempotent


def test_generate_snippet_claude_desktop_is_valid_json():
    r = clientconfig.generate_snippet("claude-desktop", name="fusion360")
    assert r["can_apply"] is True
    parsed = json.loads(r["snippet"])
    assert "fusion360" in parsed["mcpServers"]
    assert parsed["mcpServers"]["fusion360"]["args"][-1] == "run"


def test_generate_snippet_remote_includes_port():
    r = clientconfig.generate_snippet("remote-http", http_port=9999)
    assert "9999" in r["snippet"]
    assert r["can_apply"] is False


def test_settings_roundtrip_drops_unknown_keys(tmp_path, monkeypatch):
    monkeypatch.setattr(clientconfig, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr(clientconfig, "ADDIN_SETTINGS_PATH", tmp_path / "addin.json")
    assert clientconfig.read_settings()["port"] == 9000  # default when no file
    merged = clientconfig.write_settings(
        {"port": 9100, "allow_arbitrary_code": True, "junk": "x"}
    )
    assert merged["port"] == 9100
    assert merged["allow_arbitrary_code"] is True
    on_disk = json.loads((tmp_path / "addin.json").read_text(encoding="utf-8"))
    assert on_disk["port"] == 9100
    assert "junk" not in on_disk  # unknown keys from client are ignored


def test_mask_token():
    assert clientconfig.mask_token("") == ""
    masked = clientconfig.mask_token("abcdefghijklmnop")
    assert masked.startswith("abcd") and masked.endswith("mnop") and "…" in masked
