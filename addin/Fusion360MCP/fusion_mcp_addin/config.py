"""Add-in configuration (standard library only).

The add-in is launched by Fusion, so it cannot rely on a shell environment or a
``.env`` file being loaded. Configuration therefore comes from, in order:

1. Environment variables (if Fusion happens to inherit them).
2. A JSON settings file at ``~/.fusion-mcp/addin.json`` (written by the installer).
3. Built-in defaults.

The shared bearer token lives at ``~/.fusion-mcp/token``. The add-in *creates*
it if missing, so a manual install works without any extra step; the MCP server
reads the very same file, so the token never has to be copied by hand.
"""

import json
import os
import secrets
from pathlib import Path

VERSION = "0.4.0"
EVENT_ID = "fusion360_mcp_request_event"
SERVICE_NAME = "fusion360-mcp-addin"

HOME = Path.home()
CONFIG_DIR = Path(os.environ.get("FUSION_MCP_HOME", str(HOME / ".fusion-mcp")))
TOKEN_FILE = Path(os.environ.get("FUSION_MCP_TOKEN_FILE", str(CONFIG_DIR / "token")))
SETTINGS_FILE = CONFIG_DIR / "addin.json"
LOG_FILE = CONFIG_DIR / "addin.log"

_DEFAULTS = {
    "port": 9000,
    "bind": "127.0.0.1",
    "allow_arbitrary_code": False,
    "request_timeout": 30,
    # Auto-create a new Fusion design document when a build op runs and none is
    # open. Community servers all fail instead; this makes "draw a box" work
    # from a blank Fusion. Runs on the main thread (safe).
    "auto_create_document": True,
}


def _ensure_dir():
    try:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass


def _as_bool(value, default=False):
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    return str(value).strip().lower() in ("1", "true", "yes", "on")


def get_settings():
    """Merge defaults < settings file < environment variables."""
    settings = dict(_DEFAULTS)

    # Settings file (written by the installer).
    try:
        if SETTINGS_FILE.exists():
            loaded = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                settings.update({k: loaded[k] for k in _DEFAULTS if k in loaded})
    except Exception:
        pass

    # Environment overrides.
    if os.environ.get("FUSION_MCP_PORT"):
        try:
            settings["port"] = int(os.environ["FUSION_MCP_PORT"])
        except ValueError:
            pass
    if os.environ.get("FUSION_MCP_BIND"):
        settings["bind"] = os.environ["FUSION_MCP_BIND"]
    if "FUSION_MCP_ALLOW_ARBITRARY_CODE" in os.environ:
        settings["allow_arbitrary_code"] = _as_bool(
            os.environ["FUSION_MCP_ALLOW_ARBITRARY_CODE"]
        )
    if os.environ.get("FUSION_MCP_TIMEOUT"):
        try:
            settings["request_timeout"] = int(os.environ["FUSION_MCP_TIMEOUT"])
        except ValueError:
            pass
    if "FUSION_MCP_AUTO_CREATE_DOCUMENT" in os.environ:
        settings["auto_create_document"] = _as_bool(
            os.environ["FUSION_MCP_AUTO_CREATE_DOCUMENT"]
        )

    settings["allow_arbitrary_code"] = _as_bool(settings["allow_arbitrary_code"])
    settings["auto_create_document"] = _as_bool(settings["auto_create_document"], True)
    return settings


def ensure_token():
    """Return the shared bearer token, generating + persisting it if absent."""
    # Explicit token via env wins (useful for ephemeral setups).
    env_token = os.environ.get("FUSION_MCP_TOKEN")
    if env_token:
        return env_token.strip()

    _ensure_dir()
    try:
        if TOKEN_FILE.exists():
            existing = TOKEN_FILE.read_text(encoding="utf-8").strip()
            if existing:
                return existing
    except Exception:
        pass

    token = secrets.token_urlsafe(32)
    try:
        TOKEN_FILE.write_text(token, encoding="utf-8")
        try:
            os.chmod(TOKEN_FILE, 0o600)
        except Exception:
            pass
    except Exception:
        # If we cannot persist, run without auth rather than crashing. The
        # server bound to 127.0.0.1 still limits exposure.
        return ""
    return token


def log(message):
    """Append a timestamped line to the add-in log (best effort, never raises)."""
    _ensure_dir()
    try:
        # Avoid datetime import cost concerns; time is fine and stdlib.
        import time

        stamp = time.strftime("%Y-%m-%d %H:%M:%S")
        with LOG_FILE.open("a", encoding="utf-8") as fh:
            fh.write("[{}] {}\n".format(stamp, message))
    except Exception:
        pass
