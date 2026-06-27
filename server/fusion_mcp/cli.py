"""Command-line entry point: `fusion-mcp [run|doctor|tools|version]`.

With no subcommand it defaults to ``run`` over stdio — which is exactly how
Claude Desktop / Claude Code launch it.
"""

import argparse
import sys

from . import __version__
from .config import load_config


def _use_utf8_stdout():
    """Make human-facing output crash-proof on GBK consoles (Chinese Windows).

    Tool descriptions and bilingual messages contain characters (mm³, 汉字, ≥)
    that a GBK code page cannot encode, which would raise UnicodeEncodeError.
    Reconfiguring to UTF-8 with errors='replace' avoids that. NOT applied to the
    `run` command, whose stdout carries the MCP JSON-RPC stream.
    """
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def _add_common(parser):
    parser.add_argument("--addin-url", help="Add-in bridge URL (default http://127.0.0.1:9000)")
    parser.add_argument("--token", help="Bearer token (else env / ~/.fusion-mcp/token)")
    parser.add_argument("--mock", action="store_true", help="Run without Fusion (synthetic results)")
    parser.add_argument(
        "--allow-arbitrary-code",
        action="store_true",
        help="Expose the fusion_run_script power tool (security risk)",
    )
    parser.add_argument("--log-level", help="DEBUG/INFO/WARNING/ERROR")


def _config_from_args(args):
    return load_config(
        addin_url=getattr(args, "addin_url", None),
        token=getattr(args, "token", None),
        mock=True if getattr(args, "mock", False) else None,
        allow_arbitrary_code=True if getattr(args, "allow_arbitrary_code", False) else None,
        transport=getattr(args, "transport", None),
        http_host=getattr(args, "host", None),
        http_port=getattr(args, "port", None),
        log_level=getattr(args, "log_level", None),
    )


def build_parser():
    parser = argparse.ArgumentParser(
        prog="fusion-mcp",
        description="Self-hosted Fusion 360 MCP server. / 自托管 Fusion 360 MCP 服务器。",
    )
    sub = parser.add_subparsers(dest="command")

    run = sub.add_parser("run", help="Run the MCP server (default)")
    _add_common(run)
    run.add_argument("--transport", choices=["stdio", "http"], help="Transport (default stdio)")
    run.add_argument("--host", help="HTTP bind host (http transport)")
    run.add_argument("--port", type=int, help="HTTP bind port (http transport)")

    doctor = sub.add_parser("doctor", help="Diagnose the connection to Fusion")
    _add_common(doctor)

    sub.add_parser("tools", help="List registered tools")
    sub.add_parser("version", help="Print version")

    webui = sub.add_parser("webui", help="Launch the local config dashboard in a browser")
    webui.add_argument("--host", default="127.0.0.1", help="Bind host (default 127.0.0.1)")
    webui.add_argument("--port", type=int, default=8088, help="Port (default 8088)")
    webui.add_argument("--no-browser", action="store_true", help="Don't open a browser")
    return parser


def _cmd_run(args):
    from .app import build_app

    config = _config_from_args(args)
    mcp, _client = build_app(config)
    transport = "streamable-http" if config.transport in ("http", "streamable-http") else "stdio"
    if transport == "streamable-http":
        # uvicorn/starlette are only needed for HTTP; fail clearly if absent.
        try:
            import uvicorn  # noqa: F401
        except Exception:
            print(
                "HTTP transport needs extra deps. Install with: pip install 'fusion-mcp[http]'\n"
                "HTTP 传输需要额外依赖：pip install 'fusion-mcp[http]'",
                file=sys.stderr,
            )
            return 1
    mcp.run(transport=transport)
    return 0


def _cmd_doctor(args):
    from .doctor import run_doctor

    return run_doctor(_config_from_args(args))


def _cmd_tools(_args):
    from .app import build_app
    from .config import load_config as _lc

    # List tools in mock mode (no Fusion needed). Include the gated tool too.
    mcp, _client = build_app(_lc(mock=True, allow_arbitrary_code=True))
    try:
        tools = mcp._tool_manager.list_tools()  # noqa: SLF001 - stable enough for CLI
    except Exception as exc:  # pragma: no cover
        print("Could not list tools: {}".format(exc), file=sys.stderr)
        return 1
    print("Registered tools ({}):".format(len(tools)))
    for tool in sorted(tools, key=lambda t: t.name):
        summary = (tool.description or "").strip().splitlines()
        first = summary[0] if summary else ""
        print("  {:<28} {}".format(tool.name, first))
    return 0


def _cmd_webui(args):
    from .webui import serve

    return serve(host=args.host, port=args.port, open_browser=not args.no_browser)


_KNOWN_COMMANDS = {"run", "doctor", "tools", "version", "webui"}


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)

    # Default to `run` when no subcommand is given (e.g. `fusion-mcp` or
    # `fusion-mcp --mock`). This is how Claude Desktop / Code launch it.
    if argv and argv[0] in ("-h", "--help"):
        pass
    elif not argv or argv[0] not in _KNOWN_COMMANDS:
        argv = ["run"] + argv

    args = build_parser().parse_args(argv)

    command = args.command or "run"
    if command in ("version", "tools", "doctor", "webui"):
        _use_utf8_stdout()
    if command == "version":
        print("fusion-mcp {}".format(__version__))
        return 0
    if command == "tools":
        return _cmd_tools(args)
    if command == "doctor":
        return _cmd_doctor(args)
    if command == "webui":
        return _cmd_webui(args)
    return _cmd_run(args)


if __name__ == "__main__":
    raise SystemExit(main())
