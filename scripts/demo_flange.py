"""Build a realistic part end-to-end through the live bridge: a bolt-circle flange.

Exercises the multi-step modeling chain (primitive -> holes -> pattern of cuts ->
inspection -> export) plus the newer ops (physical_properties, list_faces,
measure_distance, scale, sketch-on-face). Run after the add-in is loaded:

    python scripts/demo_flange.py
"""

import base64
import json
import math
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


def call(label, op, params=None, show=None):
    global _fail
    try:
        r = client.call(op, params or {})
    except FusionMCPError as exc:
        _fail += 1
        print("  [FAIL] {}: {}".format(label, str(exc).splitlines()[0]))
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
    # Flange spec (mm)
    OD, THICK, BORE = 80.0, 10.0, 30.0
    BOLT_CIRCLE_D, BOLT_D, N_BOLTS = 60.0, 8.0, 6

    print("=== Build: bolt-circle flange (OD{} x {}mm, bore {}, {}x M{} on Ø{}) ===".format(
        OD, THICK, BORE, N_BOLTS, int(BOLT_D), BOLT_CIRCLE_D))
    call("new document", "document.new")
    call("base disk Ø{}x{}".format(OD, THICK), "primitive.cylinder",
         {"radius": OD / 2, "height": THICK, "name": "flange"})
    call("center bore Ø{}".format(BORE), "feature.hole",
         {"diameter": BORE, "x": 0, "y": 0, "plane": "xy", "through_all": True})
    for i in range(N_BOLTS):
        ang = 2 * math.pi * i / N_BOLTS
        x = (BOLT_CIRCLE_D / 2) * math.cos(ang)
        y = (BOLT_CIRCLE_D / 2) * math.sin(ang)
        call("bolt hole {}/{}".format(i + 1, N_BOLTS), "feature.hole",
             {"diameter": BOLT_D, "x": round(x, 4), "y": round(y, 4), "plane": "xy", "through_all": True})

    print("\n--- inspect ---")
    call("physical properties", "query.physical_properties", {"body": "flange"},
         show=lambda r: "mass={:.2f} g, volume={:.0f} mm³".format(r["mass_g"], r["volume_mm3"]))
    faces = call("list faces", "query.list_faces", {"body": "flange"},
                 show=lambda r: "{} faces".format(r["count"]))
    call("bounding box", "query.bounding_box",
         show=lambda r: "size={}".format([round(v, 1) for v in r["bbox_mm"]["size"]]))

    print("\n--- sketch on a face (boss via list_faces) ---")
    # pick the top planar face (normal ~ +Z, highest centroid z)
    top_idx = None
    if faces:
        best_z = -1e9
        for f in faces["faces"]:
            if f.get("is_planar") and f.get("normal", [0, 0, 0])[2] > 0.9:
                cz = f.get("centroid_mm", [0, 0, -1e9])[2]
                if cz > best_z:
                    best_z, top_idx = cz, f["index"]
    if top_idx is not None:
        print("  top face index = {}".format(top_idx))
        sk = call("sketch on top face", "sketch.create", {"plane": {"body": "flange", "face": top_idx}})
        if sk:
            call("circle r6 on face", "sketch.circle",
                 {"radius": 6, "x": 0, "y": 0, "sketch": sk["sketch_index"]})
            call("extrude boss +4", "feature.extrude",
                 {"sketch": sk["sketch_index"], "distance": 4, "operation": "join"})

    print("\n--- new-op checks (separate bodies) ---")
    call("box A @x=300", "primitive.box", {"width": 10, "depth": 10, "height": 10, "x": 300, "name": "A"})
    call("box B @x=330", "primitive.box", {"width": 10, "depth": 10, "height": 10, "x": 330, "name": "B"})
    call("measure A<->B", "query.measure_distance", {"body_a": "A", "body_b": "B"},
         show=lambda r: "min dist = {:.1f} mm (expect ~20)".format(r["min_distance_mm"]))
    call("scale A x2", "feature.scale", {"body": "A", "factor": 2.0})

    print("\n--- visualize + export ---")
    call("iso view", "view.orientation", {"name": "iso"})
    call("fit", "view.fit")
    shot = call("screenshot", "view.screenshot", {"width": 1000, "height": 750},
                show=lambda r: "{} bytes".format(len(base64.b64decode(r["base64"]))))
    if shot and shot.get("base64"):
        (ROOT / "screenshots").mkdir(exist_ok=True)
        (ROOT / "screenshots" / "flange.png").write_bytes(base64.b64decode(shot["base64"]))
        print("       saved screenshots/flange.png")
    step = call("export STEP", "export.step", show=lambda r: r["path"])
    call("export STL", "export.stl", show=lambda r: r["path"])

    print("\n=== flange demo done; {} step(s) failed ===".format(_fail))
    client.close()
    return 1 if _fail else 0


if __name__ == "__main__":
    raise SystemExit(main())
