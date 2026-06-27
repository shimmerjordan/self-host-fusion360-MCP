"""Friendly, bilingual error mapping.

Whatever we raise here becomes the error text the MCP client (Claude) shows the
user, so the messages double as troubleshooting hints.
"""


class FusionMCPError(RuntimeError):
    """Any user-facing failure from the server layer."""


def connection_hint(addin_url):
    return (
        "Cannot reach the Fusion add-in bridge at {url}.\n"
        "无法连接到 Fusion 加载项桥：{url}。\n"
        "Checklist / 排查清单:\n"
        "  1. Is Fusion 360 running? / Fusion 360 是否已启动？\n"
        "  2. Is the 'Fusion360MCP' add-in started? (Utilities > ADD-INS > Scripts and Add-Ins)\n"
        "     'Fusion360MCP' 加载项是否已运行？(实用程序 > 加载项 > 脚本和加载项)\n"
        "  3. Does the port match? Add-in default 9000; server uses FUSION_ADDIN_URL.\n"
        "     端口是否一致？加载项默认 9000；服务器用 FUSION_ADDIN_URL。\n"
        "  4. In Docker, FUSION_ADDIN_URL must be http://host.docker.internal:9000.\n"
        "     Docker 中 FUSION_ADDIN_URL 必须是 http://host.docker.internal:9000。\n"
        "Run 'fusion-mcp doctor' for a full diagnosis. / 运行 'fusion-mcp doctor' 获取完整诊断。"
    ).format(url=addin_url)


def auth_hint():
    return (
        "Authentication failed (401). The server token does not match the add-in token.\n"
        "鉴权失败 (401)。服务器令牌与加载项令牌不一致。\n"
        "Both read ~/.fusion-mcp/token. In Docker, pass the host token via FUSION_MCP_TOKEN.\n"
        "两端都读取 ~/.fusion-mcp/token。Docker 中请通过 FUSION_MCP_TOKEN 传入宿主令牌。"
    )


def op_error_message(error):
    """Render an op-level error dict from the add-in into readable text."""
    code = error.get("code", "error")
    message = error.get("message", "Operation failed.")
    detail = error.get("detail", "")
    text = "[{}] {}".format(code, message)
    if detail:
        text += "\n" + detail
    return text
