"""Wire protocol shared (by contract) with the MCP server.

Request  (POST /rpc):  {"op": "feature.extrude", "params": {...}}
Response (success):    {"ok": true,  "result": {...}}
Response (op failure): {"ok": false, "error": {"code": "...", "message": "...", "detail": "..."}}

Operational failures (no active design, bad params, op error) are returned with
HTTP 200 + ``ok=false`` so the server can parse them uniformly. Only transport
faults (bad auth, malformed JSON) use HTTP 4xx.
"""

# Error codes (kept in sync with server/fusion_mcp/errors.py).
ERR_NO_ACTIVE_DESIGN = "no_active_design"
ERR_UNKNOWN_OP = "unknown_op"
ERR_INVALID_PARAMS = "invalid_params"
ERR_NOT_FOUND = "not_found"
ERR_NOT_ALLOWED = "not_allowed"
ERR_TIMEOUT = "timeout"
ERR_FUSION = "fusion_error"
ERR_INTERNAL = "internal_error"


class OpError(Exception):
    """An operation-level error that maps cleanly to the wire format."""

    def __init__(self, code, message, detail=""):
        super().__init__(message)
        self.code = code
        self.message = message
        self.detail = detail

    def to_dict(self):
        return {"code": self.code, "message": self.message, "detail": self.detail}


def ok(result=None):
    return {"ok": True, "result": result}


def err(code, message, detail=""):
    return {"ok": False, "error": {"code": code, "message": message, "detail": detail}}


def hint_for_exception(exc):
    """Map a raw Fusion exception to an actionable, bilingual hint (best effort)."""
    msg = str(exc).lower()
    if "profile" in msg:
        return (
            "The sketch may have no closed profile to use. Ensure the sketch forms a "
            "closed region. / 草图可能没有可用的闭合轮廓，请确保草图闭合。"
        )
    if "nonetype" in msg or "no active" in msg or "activeproduct" in msg:
        return (
            "No active design/object. Open or create a design first (or enable "
            "auto_create_document). / 没有活动设计或对象，请先创建设计。"
        )
    if "out of range" in msg or "index" in msg:
        return (
            "An index is out of range. List items first with the query.* / parameter.* "
            "tools. / 索引越界，请先用 query.* / parameter.* 列出可用项。"
        )
    if "restrict" in msg or "not allowed" in msg or "licens" in msg:
        return (
            "This operation is restricted by your Fusion license (e.g. IGES/SAT export "
            "on a personal-use license). Use STEP/STL/F3D instead. / 该操作受 Fusion "
            "许可限制（如个人版禁用 IGES 导出），请改用 STEP/STL/F3D。"
        )
    if "compute failed" in msg or "regeneration" in msg or "self-inter" in msg:
        return (
            "The feature failed to compute (bad geometry/dimensions). Try different "
            "values. / 特征计算失败（几何或尺寸不合理），请换参数。"
        )
    return ""
