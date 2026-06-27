"""Safely merge a stdio MCP server entry into claude_desktop_config.json.

Thin CLI wrapper around ``fusion_mcp.clientconfig`` (the canonical merge logic,
also used by the web UI). Kept as a standalone script for the Windows installer.
"""

import argparse
import json
import sys
from pathlib import Path

try:
    from fusion_mcp.clientconfig import default_config_path, merge_config
except ImportError:  # running before the package is on sys.path
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))
    from fusion_mcp.clientconfig import default_config_path, merge_config


def _parse_env(pairs):
    env = {}
    for pair in pairs or []:
        if "=" not in pair:
            raise SystemExit("--env expects KEY=VALUE, got: " + pair)
        key, value = pair.split("=", 1)
        env[key] = value
    return env


def main(argv=None):
    parser = argparse.ArgumentParser(description="Merge an MCP server into claude_desktop_config.json")
    parser.add_argument("--name", required=True)
    parser.add_argument("--command")
    parser.add_argument("--arg", dest="args", action="append", default=[])
    parser.add_argument("--env", dest="env", action="append", default=[])
    parser.add_argument("--config", help="Override config path")
    parser.add_argument("--remove", action="store_true")
    args = parser.parse_args(argv)

    if not args.remove and not args.command:
        parser.error("--command is required unless --remove is given")

    path = Path(args.config) if args.config else default_config_path()
    result = merge_config(
        path, name=args.name, command=args.command,
        args=args.args, env=_parse_env(args.env), remove=args.remove,
    )
    if result["warning"]:
        sys.stderr.write("WARNING: " + result["warning"] + "\n")
    sys.stderr.write("{} server '{}' in {}\n".format(result["action"], args.name, result["path"]))
    if result["backup"]:
        sys.stderr.write("backup: " + result["backup"] + "\n")
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
