"""Simulated Claude conversation that builds a complete part via the MCP tools.

Each step prints the user's natural-language prompt and the tool call Claude would
make, then executes it against the live Fusion bridge. Builds an L-shaped mounting
bracket, inspects mass, screenshots it, and exports STEP/STL.

    python scripts/demo_conversation.py
"""

import base64
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "server"))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from fusion_mcp.client import AddinClient  # noqa: E402
from fusion_mcp.config import load_config  # noqa: E402
from fusion_mcp.errors import FusionMCPError  # noqa: E402

client = AddinClient(load_config())
_fail = 0


def user(text):
    print("\n\U0001f9d1  User: " + text)


def tool(op, params=None, show=None):
    global _fail
    params = params or {}
    print("   \U0001f527  {}({})".format(op, ", ".join("{}={}".format(k, v) for k, v in params.items())))
    try:
        r = client.call(op, params)
    except FusionMCPError as exc:
        _fail += 1
        print("      ❌ " + str(exc).splitlines()[0])
        return None
    if show:
        try:
            print("      → " + show(r))
        except Exception:
            pass
    return r


def main():
    user("新建一个设计,我要做一个 L 形安装支架。")
    tool("document.new")

    user("先做一块 120×80×6mm 的底板。")
    tool("primitive.box", {"width": 120, "depth": 80, "height": 6, "name": "base"},
         show=lambda r: "created '{}'".format(r["body"]))

    user("在后边缘竖一块 80×6×50mm 的立板。")
    tool("primitive.box", {"width": 80, "depth": 6, "height": 50, "y": -37, "name": "wall"},
         show=lambda r: "created '{}'".format(r["body"]))

    user("把这两块合并成一个零件。")
    tool("body.combine", {"target": "base", "tools": "wall", "operation": "join"},
         show=lambda r: "joined -> {} body".format(r.get("remaining_bodies")))

    user("所有边都倒 R2 圆角,看起来精致些。")
    tool("feature.fillet", {"body": "base", "radius": 2},
         show=lambda r: r.get("feature_name"))

    user("底板四角钻 4 个 Ø6 的安装通孔。")
    for i, (hx, hy) in enumerate([(-50, -30), (50, -30), (-50, 30), (50, 30)], 1):
        tool("feature.hole", {"diameter": 6, "x": hx, "y": hy, "plane": "xy", "through_all": True})

    user("记一个参数:板厚 plate_thk = 6mm,方便以后改。")
    tool("parameter.create", {"name": "plate_thk", "expression": "6 mm"},
         show=lambda r: "{} = {}".format(r["name"], r["expression"]))

    user("这个支架用钢做的话多重?")
    tool("query.physical_properties", {"body": "base"},
         show=lambda r: "mass = {:.1f} g, volume = {:.0f} mm³".format(r["mass_g"], r["volume_mm3"]))

    user("给我看看等轴测的样子。")
    tool("view.orientation", {"name": "iso"})
    tool("view.fit")
    shot = tool("view.screenshot", {"width": 1100, "height": 800},
                show=lambda r: "{} bytes PNG".format(len(base64.b64decode(r["base64"]))))
    if shot and shot.get("base64"):
        (ROOT / "screenshots").mkdir(exist_ok=True)
        out = ROOT / "screenshots" / "bracket.png"
        out.write_bytes(base64.b64decode(shot["base64"]))
        print("      \U0001f4f8 saved {}".format(out))

    user("导出 STEP 和 STL 给我。")
    tool("export.step", {}, show=lambda r: r["path"])
    tool("export.stl", {}, show=lambda r: r["path"])

    print("\n=== conversation done; {} failure(s) ===".format(_fail))
    client.close()
    return 1 if _fail else 0


if __name__ == "__main__":
    raise SystemExit(main())
