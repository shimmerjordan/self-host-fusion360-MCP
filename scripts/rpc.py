"""Dev helper: call the live Fusion bridge directly (real, not mock).

Usage:
    python scripts/rpc.py health
    python scripts/rpc.py ops
    python scripts/rpc.py <op> '<json-params>'
    python scripts/rpc.py document.new
    python scripts/rpc.py sketch.rectangle '{"width":20,"height":20}'

Reads the token from ~/.fusion-mcp/token (via the normal config resolution).
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from fusion_mcp.client import AddinClient  # noqa: E402
from fusion_mcp.config import load_config  # noqa: E402
from fusion_mcp.errors import FusionMCPError  # noqa: E402


def main(argv):
    if not argv:
        print(__doc__)
        return 2
    op = argv[0]
    params = {}
    if len(argv) > 1 and argv[1].strip():
        params = json.loads(argv[1])

    client = AddinClient(load_config())
    try:
        if op == "health":
            result = client.health()
        elif op == "ops":
            result = {"ops": client.list_ops()}
        else:
            result = client.call(op, params)
        text = json.dumps(result, ensure_ascii=False, indent=2)
        print(text if len(text) < 6000 else text[:6000] + "\n... [truncated]")
        return 0
    except FusionMCPError as exc:
        print("ERROR:\n" + str(exc))
        return 1
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
