"""Server config resolution + friendly error rendering."""

import fusion_mcp.config as cfgmod
from fusion_mcp.errors import auth_hint, connection_hint, op_error_message


def test_token_env_priority(monkeypatch):
    monkeypatch.setenv("FUSION_MCP_TOKEN", "abc")
    assert cfgmod.resolve_token() == "abc"


def test_token_file_fallback(monkeypatch, tmp_path):
    monkeypatch.delenv("FUSION_MCP_TOKEN", raising=False)
    token_file = tmp_path / "tok"
    token_file.write_text("filetok", encoding="utf-8")
    monkeypatch.setenv("FUSION_MCP_TOKEN_FILE", str(token_file))
    assert cfgmod.resolve_token() == "filetok"


def test_urls():
    cfg = cfgmod.load_config(addin_url="http://host:9000")
    assert cfg.rpc_url == "http://host:9000/rpc"
    assert cfg.health_url == "http://host:9000/health"
    assert cfg.ops_url == "http://host:9000/ops"


def test_overrides_applied():
    cfg = cfgmod.load_config(mock=True, allow_arbitrary_code=True, transport="http")
    assert cfg.mock is True
    assert cfg.allow_arbitrary_code is True
    assert cfg.transport == "http"


def test_op_error_message_contains_parts():
    msg = op_error_message({"code": "not_found", "message": "no body", "detail": "idx 9"})
    assert "not_found" in msg
    assert "no body" in msg
    assert "idx 9" in msg


def test_hints_are_bilingual_and_specific():
    hint = connection_hint("http://127.0.0.1:9000")
    assert "http://127.0.0.1:9000" in hint
    assert "Fusion" in hint
    assert "host.docker.internal" in hint  # Docker reminder present
    assert "401" in auth_hint()
