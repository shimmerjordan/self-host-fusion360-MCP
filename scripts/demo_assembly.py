"""Exercise assembly (components/joints/rigid groups) + CAM against live Fusion.

    python scripts/demo_assembly.py

CAM ops require the Manufacturing workspace to have been opened once; if not, the
CAM section reports the expected "no CAM workspace" hint (not a hard failure).
"""

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


def call(label, op, params=None, show=None, tolerate=None):
    global _fail
    try:
        r = client.call(op, params or {})
    except FusionMCPError as exc:
        line = str(exc).splitlines()[0]
        if tolerate and tolerate.lower() in str(exc).lower():
            print("  [skip] {}: {}".format(label, line))
            return None
        _fail += 1
        print("  [FAIL] {}: {}".format(label, line))
        return None
    note = ""
    if show:
        try:
            note = show(r)
        except Exception as exc:  # noqa: BLE001
            note = "(show error: {})".format(exc)
    print("  [ok] {}{}".format(label, ("  " + note) if note else ""))
    return r


def main():
    print("=== Assembly ===")
    call("new document", "document.new")
    for name in ("base", "arm", "link", "g1", "g2"):
        call("create component '{}'".format(name), "assembly.create_component", {"name": name})
    call("list occurrences", "assembly.list_occurrences", show=lambda r: "{} occ".format(r["count"]))
    call("move arm +20mm Z", "assembly.move_component", {"name": "arm", "dz": 20})
    call("revolute joint base<->arm (z)", "assembly.joint",
         {"component_one": "base", "component_two": "arm", "type": "revolute", "axis": "z"},
         show=lambda r: r.get("created"))
    call("rigid joint base<->link", "assembly.joint",
         {"component_one": "base", "component_two": "link", "type": "rigid"},
         show=lambda r: r.get("created"))
    call("rigid group [g1,g2]", "assembly.rigid_group", {"components": ["g1", "g2"]})
    call("list joints", "assembly.list_joints",
         show=lambda r: "{} joints, {} rigid groups".format(r["count"], r["rigid_groups"]))

    print("\n=== CAM (needs Manufacturing workspace initialised) ===")
    call("a body to machine", "primitive.box", {"width": 40, "depth": 40, "height": 15, "name": "stock"})
    setups = call("cam list setups", "cam.list_setups",
                  show=lambda r: "{} setups".format(r["count"]),
                  tolerate="no cam workspace")
    if setups is not None:
        s = call("create milling setup", "cam.create_setup",
                 {"body": "stock", "name": "Setup1", "operation_type": "milling"},
                 show=lambda r: r.get("name"))
        if s:
            call("add face operation", "cam.create_operation",
                 {"setup": "Setup1", "strategy": "face", "name": "Face1", "tool_diameter": 10},
                 tolerate="tool")
            call("generate (setup)", "cam.generate", {"setup": "Setup1"}, tolerate="tool")
            call("list operations", "cam.list_operations", {"setup": "Setup1"},
                 show=lambda r: "{} ops".format(r["count"]))
    else:
        print("       (CAM skipped — open Fusion's Manufacturing workspace once to enable)")

    print("\n=== assembly/CAM demo done; {} hard failure(s) ===".format(_fail))
    client.close()
    return 1 if _fail else 0


if __name__ == "__main__":
    raise SystemExit(main())
