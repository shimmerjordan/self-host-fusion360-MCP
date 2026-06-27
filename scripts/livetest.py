"""Comprehensive end-to-end test against a LIVE Fusion bridge (real, not mock).

Unlike the mock test suite, this drives the *actual* adsk.* API inside Fusion,
so it catches real API-shape bugs (wrong method names, enum paths, mm<->cm
errors) that mocks cannot. It exercises EVERY registered op at least once and
asserts millimetre correctness where it is cheap to verify (a 20x20x10 box must
report a 20x20x10 bounding box and a 4000 mm^3 volume).

Run after the add-in is loaded (and after `system.reload` picks up edits):
    python scripts/livetest.py
    python scripts/livetest.py --reload     # hot-reload ops first, then test
    python scripts/livetest.py --section C   # run a single section

Prints PASS/FAIL per step, a per-section tally, and a final failure digest.
"""

import argparse
import base64
import os
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
_results = []  # (section, label, ok, note)
_section = "?"


def section(name):
    global _section
    _section = name
    print("\n=== Section {} ===".format(name))


def call(op, params=None):
    return client.call(op, params or {})


def step(label, op, params=None, check=None):
    """Run one op; record PASS/FAIL. `check(result)->(ok,note)` for assertions."""
    try:
        result = call(op, params or {})
    except FusionMCPError as exc:
        _results.append((_section, label, False, "ERROR " + str(exc).splitlines()[0]))
        print("  [FAIL] {}  <- {}".format(label, str(exc).splitlines()[0]))
        return None
    ok, note = True, ""
    if check:
        try:
            ok, note = check(result)
        except Exception as exc:  # noqa: BLE001
            ok, note = False, "check raised " + repr(exc)
    if not note:
        import json
        rs = json.dumps(result, ensure_ascii=False)
        note = rs if len(rs) <= 120 else rs[:120] + "..."
    _results.append((_section, label, ok, note))
    print("  [{}] {}  <- {}".format("PASS" if ok else "FAIL", label, note))
    return result


def approx(a, b, tol=0.02):
    return abs(float(a) - float(b)) <= tol


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--reload", action="store_true", help="hot-reload ops before testing")
    ap.add_argument("--section", default=None, help="run only this section letter")
    args = ap.parse_args(argv)

    only = args.section.upper() if args.section else None

    def want(letter):
        return only is None or only == letter

    # health
    try:
        h = client.health()
        print("bridge ok: v{} ops={} arbitrary_code={}".format(
            h.get("version"), h.get("op_count"), h.get("allow_arbitrary_code")))
    except Exception as exc:  # noqa: BLE001
        print("bridge NOT reachable:", str(exc).splitlines()[0])
        print("Is Fusion running with the add-in loaded?")
        return 2

    if args.reload:
        try:
            r = call("system.reload")
            print("reloaded: {} -> {} ops ({} modules)".format(
                r.get("ops_before"), r.get("ops_after"), len(r.get("reloaded_modules", []))))
        except FusionMCPError as exc:
            print("system.reload failed:", str(exc).splitlines()[0])

    # ---------------- A: document + units ----------------
    if want("A"):
        section("A document + units")
        step("document.new", "document.new", check=lambda r: (bool(r.get("document")), r.get("document")))
        step("units.set mm", "units.set", {"units": "mm"}, lambda r: (r.get("units") == "mm", r.get("units")))
        step("units.get", "units.get", {}, lambda r: (r.get("units") == "mm", r.get("units")))
        step("document.info", "document.info", {}, lambda r: (r.get("bodies") == 0, "bodies={}".format(r.get("bodies"))))
        step("document.list", "document.list", {}, lambda r: (len(r.get("documents", [])) >= 1, "n={}".format(len(r.get("documents", [])))))

    # ---------------- B: sketches ----------------
    if want("B"):
        section("B sketches")
        step("sketch.rectangle 30x20 xy", "sketch.rectangle", {"width": 30, "height": 20, "plane": "xy"},
             lambda r: (r.get("profiles", 0) >= 1, "idx={} profiles={}".format(r.get("sketch_index"), r.get("profiles"))))
        step("sketch.rectangle center mode", "sketch.rectangle", {"width": 10, "height": 10, "mode": "center", "plane": "xy"},
             lambda r: (r.get("profiles", 0) >= 1, "profiles={}".format(r.get("profiles"))))
        step("sketch.circle r5", "sketch.circle", {"radius": 5, "plane": "xy"},
             lambda r: (r.get("profiles", 0) >= 1, "profiles={}".format(r.get("profiles"))))
        step("sketch.circle diameter", "sketch.circle", {"diameter": 8, "plane": "xy"})
        step("sketch.line", "sketch.line", {"x1": 0, "y1": 0, "x2": 20, "y2": 10, "plane": "xy"})
        step("sketch.polygon hex r10", "sketch.polygon", {"radius": 10, "sides": 6, "plane": "xy"},
             lambda r: (r.get("profiles", 0) >= 1, "profiles={}".format(r.get("profiles"))))
        step("sketch.arc 3pt", "sketch.arc", {"x1": 0, "y1": 0, "x2": 5, "y2": 5, "x3": 10, "y3": 0, "plane": "xy"})
        step("sketch.create named on xz", "sketch.create", {"plane": "xz", "name": "scratch"},
             lambda r: (r.get("sketch_name") == "scratch", r.get("sketch_name")))
        step("query.list_sketches", "query.list_sketches", {}, lambda r: (r.get("count", 0) >= 7, "count={}".format(r.get("count"))))

    # ---------------- C: primitives + mm correctness ----------------
    if want("C"):
        section("C primitives (mm correctness)")
        step("primitive.box 20x20x10 'box'", "primitive.box", {"width": 20, "depth": 20, "height": 10, "name": "box"},
             lambda r: (r.get("body") == "box", "delta={}".format(r.get("_delta"))))
        step("verify box bbox + volume", "query.get_body", {"body": "box"},
             lambda r: (
                 approx((r.get("bbox_mm") or {}).get("size", [0, 0, 0])[0], 20)
                 and approx((r.get("bbox_mm") or {}).get("size", [0, 0, 0])[1], 20)
                 and approx((r.get("bbox_mm") or {}).get("size", [0, 0, 0])[2], 10)
                 and approx(r.get("volume_mm3", 0), 4000, tol=1.0),
                 "size={} vol={}".format((r.get("bbox_mm") or {}).get("size"), r.get("volume_mm3"))))
        step("primitive.cylinder r5 h20 'cyl'", "primitive.cylinder", {"radius": 5, "height": 20, "name": "cyl"},
             lambda r: (r.get("body") == "cyl", r.get("body")))
        step("verify cyl volume ~pi*25*20", "query.get_body", {"body": "cyl"},
             lambda r: (approx(r.get("volume_mm3", 0), 3.14159265 * 25 * 20, tol=5.0), "vol={}".format(r.get("volume_mm3"))))
        step("primitive.sphere r8 'ball'", "primitive.sphere", {"radius": 8, "name": "ball"},
             lambda r: (r.get("body") == "ball", r.get("body")))
        step("verify ball volume ~4/3 pi r^3", "query.get_body", {"body": "ball"},
             lambda r: (approx(r.get("volume_mm3", 0), 4.0 / 3 * 3.14159265 * 8 ** 3, tol=20.0), "vol={}".format(r.get("volume_mm3"))))

    # ---------------- D: features (fillet/chamfer/shell) ----------------
    if want("D"):
        section("D features: fillet / chamfer / shell")
        step("feature.fillet box r2", "feature.fillet", {"body": "box", "radius": 2},
             lambda r: (r.get("feature") == "fillet", "bodies={}".format(r.get("body_count"))))
        step("feature.chamfer cyl d1", "feature.chamfer", {"body": "cyl", "distance": 1})
        step("feature.shell ball t1", "feature.shell", {"body": "ball", "thickness": 1})

    # ---------------- E: extrude / revolve from sketch ----------------
    if want("E"):
        section("E extrude / revolve")
        rect = step("sketch.rectangle 40x10 xy for extrude", "sketch.rectangle", {"width": 40, "height": 10, "plane": "xy"},
                    lambda r: ("sketch_index" in r, "idx={}".format(r.get("sketch_index"))))
        if rect:
            step("feature.extrude 5mm", "feature.extrude", {"sketch": rect["sketch_index"], "distance": 5},
                 lambda r: (r.get("feature") == "extrude", "bodies={}".format(r.get("body_count"))))
        prof = step("sketch.rectangle for revolve (offset on xz)", "sketch.rectangle",
                    {"width": 4, "height": 20, "x": 10, "y": 0, "plane": "xz"},
                    lambda r: ("sketch_index" in r, "idx={}".format(r.get("sketch_index"))))
        if prof:
            step("feature.revolve around z 360", "feature.revolve",
                 {"sketch": prof["sketch_index"], "axis": "z", "angle": 360},
                 lambda r: (r.get("feature") == "revolve", "bodies={}".format(r.get("body_count"))))

    # ---------------- F: patterns / mirror / move ----------------
    if want("F"):
        section("F patterns / mirror / move")
        step("feature.rectangular_pattern cyl x3", "feature.rectangular_pattern",
             {"body": "cyl", "count": 3, "spacing": 25, "axis": "x"})
        step("feature.circular_pattern ball x4", "feature.circular_pattern",
             {"body": "ball", "count": 4, "angle": 360, "axis": "z"})
        step("feature.mirror box across yz", "feature.mirror", {"body": "box", "plane": "yz"})
        step("body.move box +z50", "body.move", {"body": "box", "dz": 50},
             lambda r: (r.get("moved_mm") == [0.0, 0.0, 50.0], "moved={}".format(r.get("moved_mm"))))

    # ---------------- G: sweep / loft ----------------
    if want("G"):
        section("G sweep / loft")
        pr = call("sketch.circle", {"radius": 2, "plane": "xy"})
        pa = call("sketch.line", {"x1": 0, "y1": 0, "x2": 0, "y2": 40, "plane": "xz"})
        step("feature.sweep circle along line", "feature.sweep",
             {"profile_sketch": pr["sketch_index"], "path_sketch": pa["sketch_index"]},
             lambda r: (r.get("feature") == "sweep", "bodies={}".format(r.get("body_count"))))
        s1 = call("sketch.circle", {"radius": 8, "plane": "xy"})
        cp = call("construction.offset_plane", {"base": "xy", "offset": 30})
        s2 = call("sketch.circle", {"radius": 3, "plane": cp["index"]})
        step("feature.loft two circles", "feature.loft",
             {"sketches": [s1["sketch_index"], s2["sketch_index"]]},
             lambda r: (r.get("feature") == "loft", "bodies={}".format(r.get("body_count"))))

    # ---------------- H: body ops (combine / rename / visible / delete) ----------------
    if want("H"):
        section("H body ops")
        call("primitive.box", {"width": 10, "depth": 10, "height": 10, "name": "t1"})
        call("primitive.box", {"width": 10, "depth": 10, "height": 10, "x": 5, "name": "t2"})
        step("body.combine t1+t2 join", "body.combine", {"target": "t1", "tools": "t2", "operation": "join"},
             lambda r: (True, "remaining={}".format(r.get("remaining_bodies"))))
        step("body.rename t1->merged", "body.rename", {"body": "t1", "name": "merged"},
             lambda r: (r.get("name") == "merged", r.get("name")))
        step("body.set_visible merged false", "body.set_visible", {"body": "merged", "visible": False},
             lambda r: (r.get("is_visible") is False, "vis={}".format(r.get("is_visible"))))
        step("body.set_visible merged true", "body.set_visible", {"body": "merged", "visible": True},
             lambda r: (r.get("is_visible") is True, "vis={}".format(r.get("is_visible"))))
        call("primitive.box", {"width": 5, "depth": 5, "height": 5, "name": "trash"})
        step("body.delete trash", "body.delete", {"body": "trash"},
             lambda r: (r.get("deleted") == "trash", "remaining={}".format(r.get("remaining_bodies"))))

    # ---------------- I: parameters ----------------
    if want("I"):
        section("I parameters")
        step("parameter.create width=40mm", "parameter.create", {"name": "twidth", "expression": "40 mm"},
             lambda r: (approx(r.get("value_internal_cm", 0), 4.0), "cm={}".format(r.get("value_internal_cm"))))
        step("parameter.list", "parameter.list", {}, lambda r: (r.get("count", 0) >= 1, "count={}".format(r.get("count"))))
        step("parameter.get twidth", "parameter.get", {"name": "twidth"}, lambda r: (r.get("name") == "twidth", r.get("expression")))
        step("parameter.set twidth=50mm", "parameter.set", {"name": "twidth", "expression": "50 mm"},
             lambda r: (approx(r.get("value_internal_cm", 0), 5.0), "cm={}".format(r.get("value_internal_cm"))))
        step("parameter.delete twidth", "parameter.delete", {"name": "twidth"},
             lambda r: (r.get("deleted") == "twidth", "ok"))

    # ---------------- J: construction + queries ----------------
    if want("J"):
        section("J construction + queries")
        step("construction.offset_plane xy+25", "construction.offset_plane", {"base": "xy", "offset": 25},
             lambda r: (approx(r.get("offset_mm", 0), 25), "idx={}".format(r.get("index"))))
        step("query.list_bodies", "query.list_bodies", {}, lambda r: (r.get("count", 0) >= 1, "count={}".format(r.get("count"))))
        step("query.list_components", "query.list_components", {}, lambda r: (r.get("count", 0) >= 1, "count={}".format(r.get("count"))))
        step("query.bounding_box", "query.bounding_box", {}, lambda r: (not r.get("empty", True), "bbox={}".format(r.get("bbox_mm"))))
        step("query.summary", "query.summary", {}, lambda r: (r.get("counts", {}).get("bodies", 0) >= 1, "counts={}".format(r.get("counts"))))

    # ---------------- K: material ----------------
    if want("K"):
        section("K material / appearance")
        lst = step("material.list_appearances filter=steel", "material.list_appearances", {"filter": "steel", "limit": 5},
                   lambda r: (r.get("count", 0) >= 1, "count={}".format(r.get("count"))))
        if lst and lst.get("appearances"):
            name = lst["appearances"][0]["name"]
            step("material.set_appearance on cyl", "material.set_appearance", {"body": "cyl", "name": name},
                 lambda r: (r.get("appearance", "") != "", "applied={}".format(r.get("appearance"))))

    # ---------------- L: view ----------------
    if want("L"):
        section("L view")
        step("view.orientation iso", "view.orientation", {"name": "iso"}, lambda r: (r.get("orientation") == "iso", r.get("orientation")))
        step("view.orientation front", "view.orientation", {"name": "front"})
        step("view.fit", "view.fit", {}, lambda r: (r.get("fitted") is True, "ok"))
        shot = step("view.screenshot 800x600", "view.screenshot", {"width": 800, "height": 600},
                    lambda r: (base64.b64decode(r.get("base64", ""))[:8] == b"\x89PNG\r\n\x1a\n",
                               "png {} bytes".format(len(base64.b64decode(r.get("base64", ""))))))
        if shot and shot.get("base64"):
            out = ROOT / "screenshots"
            out.mkdir(exist_ok=True)
            (out / "livetest.png").write_bytes(base64.b64decode(shot["base64"]))

    # ---------------- M: export ----------------
    if want("M"):
        section("M export")
        for fmt, op in (("stl", "export.stl"), ("step", "export.step"), ("iges", "export.iges"),
                        ("f3d", "export.f3d"), ("3mf", "export.threemf")):
            res = step("export {}".format(fmt), op, {},
                       lambda r: (bool(r.get("path")), r.get("path")))
            if res and res.get("path"):
                step("  {} on disk".format(fmt), "units.get", {},
                     (lambda p: (lambda r: (os.path.exists(p), p)))(res["path"]))

    # ---------------- N: document.save (soft) ----------------
    if want("N"):
        section("N document.save (first-save may soft-fail)")
        step("document.save", "document.save", {"description": "livetest"},
             lambda r: (True, "saved={} reason={}".format(r.get("saved"), r.get("reason", ""))))

    # ---------------- summary ----------------
    total = len(_results)
    passed = sum(1 for _, _, ok, _ in _results if ok)
    failed = total - passed
    print("\n" + "=" * 60)
    print("TOTAL: {} passed, {} failed, {} steps".format(passed, failed, total))
    if failed:
        print("\nFAILURES:")
        for sec, label, ok, note in _results:
            if not ok:
                print("  [{}] {}  <- {}".format(sec, label, note))
    client.close()
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
