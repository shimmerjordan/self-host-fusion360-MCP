"""Gated arbitrary-code execution.

DISABLED by default. Enable only if you understand the risk: arbitrary Python
runs inside Fusion with full API access. Turn on with the add-in setting
``allow_arbitrary_code: true`` (and the server's ``--allow-arbitrary-code``).
"""

import contextlib
import io

import adsk
import adsk.core
import adsk.fusion

from ._common import op, require
from ..bridge.protocol import ERR_NOT_ALLOWED, OpError
from .. import config


@op(
    "script.run",
    summary="Execute arbitrary Fusion Python (DISABLED unless explicitly enabled). "
    "Globals: adsk, app, ui, design, root. Set a 'result' variable to return it.",
    destructive=True,
)
def run_script(ctx, params):
    if not config.get_settings().get("allow_arbitrary_code"):
        raise OpError(
            ERR_NOT_ALLOWED,
            "Arbitrary code execution is disabled. / 任意代码执行已禁用。",
            "Enable allow_arbitrary_code in ~/.fusion-mcp/addin.json and restart the add-in.",
        )
    code = require(params, "code", str)
    namespace = {
        "adsk": adsk,
        "app": ctx.app,
        "ui": ctx.ui,
        "design": adsk.fusion.Design.cast(ctx.app.activeProduct),
        "root": ctx.root() if adsk.fusion.Design.cast(ctx.app.activeProduct) else None,
        "result": None,
    }
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        exec(code, namespace)  # noqa: S102 - intentional, gated execution
    return {"stdout": buffer.getvalue(), "result": repr(namespace.get("result"))}
