"""Generate (or print) the shared bearer token.

The token lives at ``~/.fusion-mcp/token`` and is read by BOTH the add-in and
the server, so it never has to be copied by hand. stdout = the token only;
human messages go to stderr.
"""

import os
import secrets
import sys
from pathlib import Path


def token_path():
    config_dir = Path(os.environ.get("FUSION_MCP_HOME", str(Path.home() / ".fusion-mcp")))
    return config_dir / "token"


def ensure_token():
    path = token_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        if path.exists():
            existing = path.read_text(encoding="utf-8").strip()
            if existing:
                sys.stderr.write("Token already present at {}\n".format(path))
                return existing
    except Exception:
        pass
    token = secrets.token_urlsafe(32)
    path.write_text(token, encoding="utf-8")
    try:
        os.chmod(path, 0o600)
    except Exception:
        pass
    sys.stderr.write("Wrote new token to {}\n".format(path))
    return token


def main():
    print(ensure_token())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
