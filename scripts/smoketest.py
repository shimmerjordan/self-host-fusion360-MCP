"""Comprehensive end-to-end smoke test against a LIVE Fusion bridge.

Run after the add-in is loaded (and after `python scripts/rpc.py system.reload`
when iterating on op code):

    python scripts/smoketest.py

Starts from a fresh document and exercises (nearly) every tool. Prints PASS/FAIL
per step and a tally; exits non-zero if anything failed.
"""

import base64
import json
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
_tally = {"pass": 0, "fail": 0}
_failures = []


def _record(ok, label, note=""):
    _tally["pass" if ok else "fail"] += 1
    if not ok:
        _failures.append(label)
    print("[{}] {}{}".format("OK  " if ok else "FAIL", label, ("  <- " + note) if note else ""))


def step(label, op, params=None, check=None):
    try:
        result = client.call(op, params or {})
    except FusionMCPError as exc:
        _record(False, label, "ERROR " + str(exc).splitlines()[0])
        return None
    ok, note = True, ""
    if check:
        try:
            ok, note = check(result)
        except Exception as exc:  # noqa: BLE001
            ok, note = False, "check raised " + str(exc)
    if not note:
        rs = json.dumps(result, ensure_ascii=False)
        note = rs if len(rs) <= 140 else rs[:140] + "..."
    _record(ok, label, note)
    return result


def section(title):
    print("\n--- {} ---".format(title))


def main():
    print("=== Fusion360 MCP comprehensive live test ===")
    try:
        h = client.health()
        _record(h.get("ok", False), "health", "v{} ops={}".format(h.get("version"), h.get("op_count")))
    except Exception as exc:  # noqa: BLE001
        print("Bridge not reachable:", exc)
        return 2

    section("document")
    step("document.new", "document.new")
    step("document.list", "document.list", {}, lambda r: (len(r.get("documents", [])) >= 1, None))

    section("primitives")
    step("box 'cube' 20^3", "primitive.box", {"width": 20, "depth": 20, "height": 20, "name": "cube"},
         lambda r: (r.get("_delta", {}).get("bodies_added") == 1, "delta ok"))
    step("box 'boxC' 16^3 @x=50", "primitive.box", {"width": 16, "depth": 16, "height": 16, "x": 50, "name": "boxC"})
    step("cylinder 'tube' r10 h24 @x=100", "primitive.cylinder", {"radius": 10, "height": 24, "x": 100, "name": "tube"})
    step("sphere 'ball' r8 @x=-50", "primitive.sphere", {"radius": 8, "name": "ball"})

    section("features on bodies")
    step("fillet cube r3", "feature.fillet", {"body": "cube", "radius": 3})
    step("chamfer boxC d2", "feature.chamfer", {"body": "boxC", "distance": 2})
    step("shell tube 2mm", "feature.shell", {"body": "tube", "thickness": 2})

    section("sketch -> extrude / revolve")
    rect = step("sketch.rectangle 30x10 (xy)", "sketch.rectangle", {"width": 30, "height": 10, "x": -120, "plane": "xy"},
                lambda r: ("sketch_index" in r, "idx={}".format(r.get("sketch_index"))))
    if rect:
        step("extrude rect 5mm", "feature.extrude", {"sketch": rect["sketch_index"], "distance": 5})
    circ = step("sketch.circle r6 (xy) @-160", "sketch.circle", {"radius": 6, "x": -160, "plane": "xy"})
    if circ:
        step("extrude circle 12mm", "feature.extrude", {"sketch": circ["sketch_index"], "distance": 12})
    step("sketch.arc 3-point", "sketch.arc", {"x1": 0, "y1": 0, "x2": 5, "y2": 8, "x3": 10, "y3": 0, "x": 200})
    # revolve a profile offset from the Y axis (does not cross it)
    revr = step("sketch.rectangle 4x20 @x=20 (xy)", "sketch.rectangle",
                {"width": 4, "height": 20, "x": 20, "y": -10, "plane": "xy", "mode": "corner"})
    if revr:
        step("revolve around Y 360", "feature.revolve",
             {"sketch": revr["sketch_index"], "axis": "y", "angle": 360})

    section("patterns / mirror")
    step("rectangular_pattern cube x*3 sp30", "feature.rectangular_pattern",
         {"body": "cube", "axis": "x", "count": 3, "spacing": 30})
    step("circular_pattern boxC z*6", "feature.circular_pattern",
         {"body": "boxC", "axis": "z", "count": 6, "angle": 360})
    step("mirror tube across yz", "feature.mirror", {"body": "tube", "plane": "yz"})

    section("boolean combine")
    step("box 't1' @x=250", "primitive.box", {"width": 10, "depth": 10, "height": 10, "x": 250, "name": "t1"})
    step("box 't2' @x=255", "primitive.box", {"width": 10, "depth": 10, "height": 10, "x": 255, "name": "t2"})
    step("combine t1 + t2 (join)", "body.combine", {"target": "t1", "tools": "t2", "operation": "join"})

    section("loft (with construction plane) + sweep")
    s1 = step("sketch.circle r10 (xy) @400", "sketch.circle", {"radius": 10, "x": 400, "plane": "xy"})
    plane = step("construction.offset_plane xy +20", "construction.offset_plane", {"base": "xy", "offset": 20})
    pidx = (plane or {}).get("index")
    if s1 and pidx is not None:
        s2 = step("sketch.circle r5 on offset plane", "sketch.circle", {"radius": 5, "x": 400, "plane": pidx})
        if s2:
            step("loft circle->circle", "feature.loft",
                 {"sketches": [s1["sketch_index"], s2["sketch_index"]]})
    pprof = step("sketch.circle r2 (xy) @500", "sketch.circle", {"radius": 2, "x": 500, "plane": "xy"})
    ppath = step("sketch.line path (xz) up 30", "sketch.line",
                 {"x1": 500, "y1": 0, "x2": 500, "y2": 30, "plane": "xz"})
    if pprof and ppath:
        step("sweep profile along path", "feature.sweep",
             {"profile_sketch": pprof["sketch_index"], "path_sketch": ppath["sketch_index"]})

    section("parameters")
    step("parameter.create depth=40mm", "parameter.create", {"name": "depth", "expression": "40 mm"})
    step("parameter.set depth=45mm", "parameter.set", {"name": "depth", "expression": "45 mm"},
         lambda r: (abs(r.get("value_internal_cm", 0) - 4.5) < 1e-6, "val_cm={}".format(r.get("value_internal_cm"))))
    step("parameter.get depth", "parameter.get", {"name": "depth"})
    step("parameter.list", "parameter.list", {}, lambda r: (r.get("count", 0) >= 1, "n={}".format(r.get("count"))))
    step("parameter.delete depth", "parameter.delete", {"name": "depth"})

    section("material")
    step("material.list_appearances", "material.list_appearances", {},
         lambda r: (r.get("count", 0) >= 0, "n={}".format(r.get("count"))))

    section("body ops")
    step("body.rename cube->MainCube", "body.rename", {"body": "cube", "name": "MainCube"})
    step("body.set_visible ball false", "body.set_visible", {"body": "ball", "visible": False})
    step("body.move boxC dz=5", "body.move", {"body": "boxC", "dz": 5})

    section("view")
    for o in ("home", "front", "top", "right", "iso"):
        step("view.orientation " + o, "view.orientation", {"name": o})
    step("view.fit", "view.fit")
    shot = step("view.screenshot 800x600", "view.screenshot", {"width": 800, "height": 600},
                lambda r: (base64.b64decode(r.get("base64", ""))[:8] == b"\x89PNG\r\n\x1a\n",
                           "{} bytes".format(len(base64.b64decode(r.get("base64", ""))))))
    if shot and shot.get("base64"):
        (ROOT / "screenshots").mkdir(exist_ok=True)
        (ROOT / "screenshots" / "smoketest.png").write_bytes(base64.b64decode(shot["base64"]))

    section("export (all formats)")
    for fmt, op in (("stl", "export.stl"), ("step", "export.step"),
                    ("iges", "export.iges"), ("f3d", "export.f3d")):
        try:
            res = client.call(op, {})
            _record(os.path.exists(res.get("path", "")), "export " + fmt, os.path.basename(res.get("path", "")))
        except FusionMCPError as exc:
            msg = str(exc).lower()
            if "restrict" in msg or "licens" in msg:
                print("[SKIP] export " + fmt + "  <- license-restricted (expected on personal license)")
            else:
                _record(False, "export " + fmt, "ERROR " + str(exc).splitlines()[0])

    section("query")
    step("query.list_bodies", "query.list_bodies", {}, lambda r: (r.get("count", 0) >= 1, "n={}".format(r.get("count"))))
    step("query.list_components", "query.list_components")
    step("query.list_sketches", "query.list_sketches", {}, lambda r: (r.get("count", 0) >= 1, "n={}".format(r.get("count"))))
    step("query.bounding_box", "query.bounding_box")
    step("query.get_body MainCube", "query.get_body", {"body": "MainCube"})
    step("query.summary", "query.summary", {}, lambda r: (True, "bodies={}".format(r.get("counts", {}).get("bodies"))))

    section("units")
    step("units.get", "units.get")
    step("units.set mm", "units.set", {"unit": "mm"})

    print("\n=== {} passed, {} failed ===".format(_tally["pass"], _tally["fail"]))
    if _failures:
        print("FAILURES: " + ", ".join(_failures))
    client.close()
    return 1 if _tally["fail"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
