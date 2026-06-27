"""Safe Claude-config merge: never clobber existing servers; back up; idempotent."""

import json

import claude_config_merge as ccm


def _read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_add_preserves_existing(tmp_path):
    cfg = tmp_path / "claude_desktop_config.json"
    cfg.write_text(
        json.dumps({"mcpServers": {"existing": {"command": "x", "args": []}}, "otherKey": 1}),
        encoding="utf-8",
    )
    result = ccm.merge_config(cfg, name="fusion360", command="fusion-mcp", args=[])
    data = _read(cfg)
    assert "existing" in data["mcpServers"]
    assert "fusion360" in data["mcpServers"]
    assert data["otherKey"] == 1
    assert result["action"] == "added"
    assert result["backup"] is not None  # pre-existing file was backed up


def test_idempotent_update(tmp_path):
    cfg = tmp_path / "c.json"
    ccm.merge_config(cfg, name="fusion360", command="a", args=[])
    result = ccm.merge_config(cfg, name="fusion360", command="b", args=["run"])
    data = _read(cfg)
    assert data["mcpServers"]["fusion360"]["command"] == "b"
    assert data["mcpServers"]["fusion360"]["args"] == ["run"]
    assert result["action"] == "updated"


def test_remove(tmp_path):
    cfg = tmp_path / "c.json"
    ccm.merge_config(cfg, name="fusion360", command="a")
    result = ccm.merge_config(cfg, name="fusion360", remove=True)
    data = _read(cfg)
    assert "fusion360" not in data["mcpServers"]
    assert result["action"] == "removed"


def test_malformed_config_is_backed_up_not_lost(tmp_path):
    cfg = tmp_path / "c.json"
    cfg.write_text("{ this is not valid json", encoding="utf-8")
    result = ccm.merge_config(cfg, name="fusion360", command="a")
    assert result["warning"] is not None
    assert result["backup"] is not None
    data = _read(cfg)
    assert "fusion360" in data["mcpServers"]


def test_creates_parent_dirs_when_absent(tmp_path):
    cfg = tmp_path / "nested" / "dir" / "c.json"
    result = ccm.merge_config(cfg, name="fusion360", command="a")
    assert cfg.exists()
    assert result["backup"] is None


def test_env_block(tmp_path):
    cfg = tmp_path / "c.json"
    ccm.merge_config(cfg, name="fusion360", command="a", env={"K": "V"})
    data = _read(cfg)
    assert data["mcpServers"]["fusion360"]["env"] == {"K": "V"}
