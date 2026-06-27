"""Server configuration, resolved from environment variables + CLI overrides."""

import os
from dataclasses import dataclass
from pathlib import Path

DEFAULT_ADDIN_URL = "http://127.0.0.1:9000"
DEFAULT_TOKEN_PATH = Path.home() / ".fusion-mcp" / "token"


def _as_bool(value, default=False):
    if value is None:
        return default
    return str(value).strip().lower() in ("1", "true", "yes", "on")


def resolve_token():
    """FUSION_MCP_TOKEN > FUSION_MCP_TOKEN_FILE > ~/.fusion-mcp/token > ''."""
    explicit = os.environ.get("FUSION_MCP_TOKEN")
    if explicit:
        return explicit.strip()

    candidates = []
    token_file = os.environ.get("FUSION_MCP_TOKEN_FILE")
    if token_file:
        candidates.append(Path(token_file))
    candidates.append(DEFAULT_TOKEN_PATH)

    for path in candidates:
        try:
            if path.exists():
                value = path.read_text(encoding="utf-8").strip()
                if value:
                    return value
        except Exception:
            continue
    return ""


@dataclass
class ServerConfig:
    addin_url: str = DEFAULT_ADDIN_URL
    token: str = ""
    timeout: float = 30.0
    transport: str = "stdio"  # stdio | http
    http_host: str = "0.0.0.0"
    http_port: int = 8765
    allow_arbitrary_code: bool = False
    mock: bool = False
    log_level: str = "INFO"

    @property
    def rpc_url(self):
        return self.addin_url.rstrip("/") + "/rpc"

    @property
    def health_url(self):
        return self.addin_url.rstrip("/") + "/health"

    @property
    def ops_url(self):
        return self.addin_url.rstrip("/") + "/ops"


def load_config(**overrides):
    cfg = ServerConfig(
        addin_url=os.environ.get("FUSION_ADDIN_URL", DEFAULT_ADDIN_URL),
        token=resolve_token(),
        timeout=float(os.environ.get("FUSION_MCP_TIMEOUT", "30") or 30),
        transport=os.environ.get("FUSION_MCP_TRANSPORT", "stdio"),
        http_host=os.environ.get("FUSION_MCP_HTTP_HOST", "0.0.0.0"),
        http_port=int(os.environ.get("FUSION_MCP_HTTP_PORT", "8765") or 8765),
        allow_arbitrary_code=_as_bool(os.environ.get("FUSION_MCP_ALLOW_ARBITRARY_CODE")),
        mock=_as_bool(os.environ.get("FUSION_MCP_MOCK")),
        log_level=os.environ.get("FUSION_MCP_LOG_LEVEL", "INFO"),
    )
    for key, value in overrides.items():
        if value is not None and hasattr(cfg, key):
            setattr(cfg, key, value)
    return cfg
