"""Standalone doctor runner (no pip install required).

Usage: python scripts/doctor.py [--mock] [--addin-url URL] [--token T]
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))

from fusion_mcp.cli import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main(["doctor"] + sys.argv[1:]))
