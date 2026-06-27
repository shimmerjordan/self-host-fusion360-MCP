"""Bilingual preflight diagnostics: `fusion-mcp doctor`."""

import sys

from .client import AddinClient
from .config import DEFAULT_TOKEN_PATH, ServerConfig
from .errors import FusionMCPError

# A few ops that must exist if the add-in is the matching version.
CORE_OPS = [
    "document.new",
    "sketch.rectangle",
    "feature.extrude",
    "feature.fillet",
    "export.stl",
    "view.screenshot",
]


def _p(msg=""):
    print(msg, file=sys.stdout, flush=True)


def run_doctor(config: ServerConfig):
    status_ok = True
    _p("=== Fusion360 MCP doctor / 自检 ===")
    _p("addin_url  : {}".format(config.addin_url))
    _p("transport  : {}".format(config.transport))
    _p("mock       : {}".format(config.mock))
    if config.token:
        _p("token      : present ({} chars) / 已配置".format(len(config.token)))
    else:
        _p("token      : MISSING / 缺失 — expected at {}".format(DEFAULT_TOKEN_PATH))
        _p("             (The add-in creates it on first start. / 加载项首次启动会自动生成。)")

    client = AddinClient(config)

    if config.mock:
        _p("")
        _p("[MOCK] Live checks skipped; server + tools import OK. / 模拟模式，跳过实连检查。")
        client.close()
        _p("")
        _p("Result: PASS (mock)")
        return 0

    # 1) Health
    _p("")
    try:
        health = client.health()
        _p(
            "[OK] Bridge reachable. version={} auth_required={} ops={} arbitrary_code={}".format(
                health.get("version"),
                health.get("auth_required"),
                health.get("op_count"),
                health.get("allow_arbitrary_code"),
            )
        )
    except FusionMCPError as exc:
        _p("[FAIL] Bridge unreachable. / 无法连接加载项桥。")
        _p(str(exc))
        client.close()
        _p("")
        _p("Result: FAIL")
        return 2

    # 2) Op reconciliation
    try:
        ops = set(client.list_ops())
        missing = [o for o in CORE_OPS if o not in ops]
        if missing:
            status_ok = False
            _p(
                "[WARN] Add-in is missing expected ops: {} — version mismatch? "
                "/ 加载项缺少预期算子，可能版本不一致。".format(", ".join(missing))
            )
        else:
            _p("[OK] Core ops present ({} total). / 核心算子齐全。".format(len(ops)))
    except FusionMCPError as exc:
        _p("[WARN] Could not list ops: {}".format(exc))

    # 3) Live read-only call
    try:
        client.call("query.summary")
        _p("[OK] query.summary executed — a design is open. / 查询成功，存在活动设计。")
    except FusionMCPError as exc:
        first_line = str(exc).splitlines()[0] if str(exc) else ""
        _p(
            "[INFO] query.summary did not return a design. Open or create one in "
            "Fusion. / 请在 Fusion 中打开或新建一个设计。 ({})".format(first_line)
        )

    client.close()
    _p("")
    _p("Result: {}".format("PASS" if status_ok else "WARN"))
    return 0 if status_ok else 1
