"""Tool registration, schemas, and annotations (mock mode, no Fusion needed)."""

import pytest

from fusion_mcp.app import build_app
from fusion_mcp.config import load_config


@pytest.fixture(scope="module")
def tools():
    mcp, _client = build_app(load_config(mock=True, allow_arbitrary_code=True))
    return {t.name: t for t in mcp._tool_manager.list_tools()}


def test_tool_count(tools):
    assert len(tools) >= 40


def test_core_tools_present(tools):
    for name in [
        "fusion_new_document",
        "fusion_sketch_rectangle",
        "fusion_extrude",
        "fusion_fillet",
        "fusion_chamfer",
        "fusion_shell",
        "fusion_export_stl",
        "fusion_export_step",
        "fusion_screenshot",
        "fusion_list_bodies",
        "fusion_set_parameter",
        "fusion_revolve",
    ]:
        assert name in tools, "missing tool: " + name


def test_read_only_annotation(tools):
    assert tools["fusion_list_bodies"].annotations.readOnlyHint is True
    assert tools["fusion_summary"].annotations.readOnlyHint is True
    assert tools["fusion_get_parameter"].annotations.readOnlyHint is True


def test_destructive_annotation(tools):
    assert tools["fusion_delete_body"].annotations.destructiveHint is True


def test_idempotent_annotation(tools):
    assert tools["fusion_set_parameter"].annotations.idempotentHint is True


def test_every_tool_has_object_schema_and_description(tools):
    for name, tool in tools.items():
        assert isinstance(tool.parameters, dict), name
        assert tool.parameters.get("type") == "object", name
        assert (tool.description or "").strip(), name


def test_script_tool_is_gated():
    mcp, _client = build_app(load_config(mock=True))  # allow_arbitrary_code defaults off
    names = {t.name for t in mcp._tool_manager.list_tools()}
    assert "fusion_run_script" not in names
