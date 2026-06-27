"""Shared client-config helpers: add-in settings, token, and the multi-AI
connector registry (config snippets + safe merge into client config files).

This is the canonical home for the merge logic that the Windows installer's
``install/claude_config_merge.py`` now delegates to, and that the web UI uses.
"""

import json
import os
import secrets
import shutil
import sys
import time
from pathlib import Path

# ── local config paths (mirror the add-in's, respecting FUSION_MCP_HOME) ──────
CONFIG_DIR = Path(os.environ.get("FUSION_MCP_HOME", str(Path.home() / ".fusion-mcp")))
ADDIN_SETTINGS_PATH = CONFIG_DIR / "addin.json"
TOKEN_PATH = Path(os.environ.get("FUSION_MCP_TOKEN_FILE", str(CONFIG_DIR / "token")))

SETTINGS_DEFAULTS = {
    "port": 9000,
    "bind": "127.0.0.1",
    "allow_arbitrary_code": False,
    "request_timeout": 30,
    "auto_create_document": True,
}
_BOOL_KEYS = {"allow_arbitrary_code", "auto_create_document"}
_INT_KEYS = {"port", "request_timeout"}


# ── add-in settings (addin.json) ─────────────────────────────────────────────
def read_settings():
    """Merge built-in defaults with ~/.fusion-mcp/addin.json (defaults win for
    missing keys; unknown keys in the file are preserved on read)."""
    data = {}
    try:
        if ADDIN_SETTINGS_PATH.exists():
            loaded = json.loads(ADDIN_SETTINGS_PATH.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                data = loaded
    except Exception:
        data = {}
    merged = dict(SETTINGS_DEFAULTS)
    merged.update({k: v for k, v in data.items()})
    return merged


def write_settings(updates):
    """Validate + write known keys into addin.json, preserving unknown keys.
    Returns the merged settings."""
    current = {}
    try:
        if ADDIN_SETTINGS_PATH.exists():
            loaded = json.loads(ADDIN_SETTINGS_PATH.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                current = loaded
    except Exception:
        current = {}

    for key, value in (updates or {}).items():
        if key in _INT_KEYS:
            current[key] = int(value)
        elif key in _BOOL_KEYS:
            current[key] = bool(value)
        elif key == "bind":
            current[key] = str(value)
        # ignore unknown keys from the client to avoid junk

    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    ADDIN_SETTINGS_PATH.write_text(
        json.dumps(current, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    merged = dict(SETTINGS_DEFAULTS)
    merged.update(current)
    return merged


# ── shared token ─────────────────────────────────────────────────────────────
def read_token():
    try:
        if TOKEN_PATH.exists():
            return TOKEN_PATH.read_text(encoding="utf-8").strip()
    except Exception:
        pass
    return ""


def regenerate_token():
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    token = secrets.token_urlsafe(32)
    TOKEN_PATH.write_text(token, encoding="utf-8")
    try:
        os.chmod(TOKEN_PATH, 0o600)
    except Exception:
        pass
    return token


def mask_token(token):
    if not token:
        return ""
    if len(token) <= 8:
        return "•" * len(token)
    return token[:4] + "…" + token[-4:]


# ── claude_desktop_config.json (and similar) safe merge ──────────────────────
def default_config_path():
    if os.name == "nt":
        base = os.environ.get("APPDATA", str(Path.home() / "AppData" / "Roaming"))
        return Path(base) / "Claude" / "claude_desktop_config.json"
    return Path.home() / "Library" / "Application Support" / "Claude" / "claude_desktop_config.json"


def _load_json_obj(path):
    if not path.exists():
        return {}, None
    text = path.read_text(encoding="utf-8")
    if not text.strip():
        return {}, None
    try:
        data = json.loads(text)
        if not isinstance(data, dict):
            return {}, "existing config was not a JSON object; starting fresh"
        return data, None
    except json.JSONDecodeError as exc:
        return {}, "existing config is not valid JSON ({}); a backup was kept".format(exc)


def _backup(path):
    if path.exists():
        stamp = time.strftime("%Y%m%d-%H%M%S")
        backup = path.with_name(path.name + ".bak-" + stamp)
        shutil.copy2(path, backup)
        return backup
    return None


def merge_config(config_path, name, command=None, args=None, env=None, remove=False):
    """Add/update/remove an mcpServers entry, preserving everything else.
    Backs up the file first. Idempotent. Returns a result dict."""
    path = Path(config_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    data, warning = _load_json_obj(path)
    backup = _backup(path)

    servers = data.get("mcpServers")
    if not isinstance(servers, dict):
        servers = {}
    data["mcpServers"] = servers

    if remove:
        existed = servers.pop(name, None) is not None
        action = "removed" if existed else "absent"
    else:
        entry = {"command": command, "args": list(args or [])}
        if env:
            entry["env"] = dict(env)
        action = "updated" if name in servers else "added"
        servers[name] = entry

    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    return {
        "action": action,
        "path": str(path),
        "backup": str(backup) if backup else None,
        "warning": warning,
        "servers": sorted(servers.keys()),
    }


# ── multi-AI connector registry ──────────────────────────────────────────────
def server_invocation():
    """Best command to launch the stdio server: the installed console script if
    on PATH, else `<python> -m fusion_mcp`. Returns (command, base_args)."""
    exe = shutil.which("fusion-mcp")
    if exe:
        return exe, []
    return sys.executable, ["-m", "fusion_mcp"]


# Future AIs: add a dict here + a branch in generate_snippet().
CONNECTORS = [
    {"id": "claude-desktop", "name": "Claude Desktop", "transport": "stdio", "can_apply": True,
     "doc": "https://modelcontextprotocol.io/quickstart/user"},
    {"id": "claude-code", "name": "Claude Code", "transport": "stdio", "can_apply": False,
     "doc": "https://docs.anthropic.com/en/docs/claude-code/mcp"},
    {"id": "cursor", "name": "Cursor", "transport": "stdio", "can_apply": False,
     "doc": "https://docs.cursor.com/context/model-context-protocol"},
    {"id": "vscode", "name": "VS Code (MCP)", "transport": "stdio", "can_apply": False,
     "doc": "https://code.visualstudio.com/docs/copilot/chat/mcp-servers"},
    {"id": "generic-stdio", "name": "Generic MCP client (stdio)", "transport": "stdio", "can_apply": False,
     "doc": "https://modelcontextprotocol.io"},
    {"id": "remote-http", "name": "Remote / HTTP connector", "transport": "http", "can_apply": False,
     "doc": "https://docs.anthropic.com/en/docs/agents-and-tools/remote-mcp-servers"},
]


def _stdio_entry(name, command, args):
    return {"mcpServers": {name: {"command": command, "args": args + ["run"]}}}


def generate_snippet(connector_id, name="fusion360", transport="stdio",
                     http_host="127.0.0.1", http_port=8765):
    """Return {language, snippet, config_path, can_apply, notes} for a connector."""
    command, base_args = server_invocation()
    host = "127.0.0.1" if http_host in ("0.0.0.0", "", None) else http_host
    url = "http://{}:{}/mcp".format(host, http_port)

    if connector_id == "claude-desktop":
        entry = _stdio_entry(name, command, base_args)
        return {
            "language": "json",
            "snippet": json.dumps(entry, indent=2, ensure_ascii=False),
            "config_path": str(default_config_path()),
            "can_apply": True,
            "notes": "Merge into claude_desktop_config.json, then fully restart Claude Desktop. "
                     "/ 合并进 claude_desktop_config.json 后，完全退出并重开 Claude Desktop。",
        }
    if connector_id == "claude-code":
        cli = "claude mcp add {} -- {} {} run".format(name, command, " ".join(base_args)).replace("  ", " ")
        return {
            "language": "bash",
            "snippet": cli,
            "config_path": ".mcp.json (project scope)",
            "can_apply": False,
            "notes": "Run in your project; or add the JSON to .mcp.json. / 在项目目录运行，或写入 .mcp.json。",
        }
    if connector_id in ("cursor", "vscode", "generic-stdio"):
        entry = _stdio_entry(name, command, base_args)
        paths = {
            "cursor": "~/.cursor/mcp.json (or project .cursor/mcp.json)",
            "vscode": ".vscode/mcp.json",
            "generic-stdio": "your client's MCP config",
        }
        return {
            "language": "json",
            "snippet": json.dumps(entry, indent=2, ensure_ascii=False),
            "config_path": paths[connector_id],
            "can_apply": False,
            "notes": "stdio MCP server entry. / 通用 stdio MCP 服务器条目。",
        }
    if connector_id == "remote-http":
        run_cmd = "{} {} run --transport http --host 0.0.0.0 --port {}".format(
            command, " ".join(base_args), http_port).replace("  ", " ")
        return {
            "language": "text",
            "snippet": "# 1) Start the HTTP server (needs: pip install 'fusion-mcp[http]'):\n"
                       + run_cmd
                       + "\n\n# 2) In your AI client, add a custom/remote MCP connector at:\n"
                       + url,
            "config_path": url,
            "can_apply": False,
            "notes": "Bind 0.0.0.0 only if you must reach it from another host; keep the bearer "
                     "token on and firewall the port. / 仅在需跨主机访问时绑定 0.0.0.0，务必保留令牌并设置防火墙。",
        }
    raise ValueError("unknown connector: " + str(connector_id))
