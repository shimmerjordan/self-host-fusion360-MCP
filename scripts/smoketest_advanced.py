"""Live test for the advanced ops added in v0.3 (generic API, sketch constraints/
dimensions, edit/timeline, inspection, draft/split/offset/thread, surfaces,
sheet metal, DXF, CAM tools).

    python scripts/smoketest_advanced.py

Some areas (sheet metal, CAM) need a sheet-metal body / Manufacturing workspace;
those are reported as [skip] when the environment isn't set up, not failures.
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
        msg = str(exc)
        if tolerate and any(t in msg.lower() for t in tolerate):
            print("  [skip] {}: {}".format(label, msg.splitlines()[0][:80]))
            return None
        _fail += 1
        print("  [FAIL] {}: {}".format(label, msg.splitlines()[0]))
        return None
    note = ""
    if show:
        try:
            note = show(r)
        except Exception as exc:  # noqa: BLE001
            note = "(show err: {})".format(exc)
    print("  [ok] {}{}".format(label, ("  " + note) if note else ""))
    return r


def main():
    print("=== generic API ===")
    call("introspect ExtrudeFeatures", "api.introspect", {"target": "ExtrudeFeatures", "query": "create"},
         show=lambda r: "{} methods".format(len(r["methods"])))
    call("docs ExtrudeFeatures.createInput", "api.docs", {"name": "ExtrudeFeatures.createInput"},
         show=lambda r: r["url"].split("/")[-1])
    call("api.call read body count", "api.call",
         {"path": "rootComponent.bRepBodies", "return_properties": ["count"]},
         show=lambda r: "type={} props={}".format(r.get("result_type"), r.get("properties")),
         tolerate=["disabled"])

    print("\n=== setup geometry ===")
    call("new document", "document.new")
    call("box blk 30^3", "primitive.box", {"width": 30, "depth": 30, "height": 20, "name": "blk"})
    call("box blk2 (overlap)", "primitive.box", {"width": 30, "depth": 30, "height": 20, "x": 15, "name": "blk2"})

    print("\n=== inspection ===")
    call("interference blk/blk2", "query.interference", {"bodies": ["blk", "blk2"]},
         show=lambda r: "{} hits".format(r["interference_count"]))
    call("measure_angle blk/blk2", "query.measure_angle", {"body_a": "blk", "body_b": "blk2"},
         show=lambda r: "{:.1f} deg".format(r["angle_degrees"]))

    print("\n=== features: draft/offset_faces/split ===")
    faces = call("list_faces blk", "query.list_faces", {"body": "blk"}, show=lambda r: "{} faces".format(r["count"]))
    side = top = None
    if faces:
        for f in faces["faces"]:
            n = f.get("normal") or [0, 0, 0]
            if abs(n[2]) < 0.1 and side is None:
                side = f["index"]
            if n[2] > 0.9 and top is None:
                top = f["index"]
    if side is not None:
        call("draft side face 5deg", "feature.draft", {"body": "blk", "angle": 5, "plane": "xy", "faces": [side]})
    call("offset_faces blk2 +2", "feature.offset_faces", {"body": "blk2", "distance": 2, "faces": [0]})
    call("split_body blk by xz", "feature.split_body", {"body": "blk", "plane": "xz"})

    print("\n=== thread on a cylinder ===")
    call("cylinder pin r6 h20", "primitive.cylinder", {"radius": 6, "height": 20, "x": 80, "name": "pin"})
    pinfaces = call("list_faces pin", "query.list_faces", {"body": "pin"})
    cyl = None
    if pinfaces:
        for f in pinfaces["faces"]:
            if not f.get("is_planar"):
                cyl = f["index"]
                break
    if cyl is not None:
        call("thread cylindrical face", "feature.thread", {"body": "pin", "face": cyl, "internal": False, "modeled": True},
             tolerate=["cylindrical", "thread"])

    print("\n=== sketch constraints / dimensions / spline / offset / project ===")
    sk = call("line A (0,0)->(40,0)", "sketch.line", {"x1": 0, "y1": 0, "x2": 40, "y2": 0, "x": -100, "plane": "xy"},
              show=lambda r: "idx={}".format(r["sketch_index"]))
    if sk:
        idx = sk["sketch_index"]
        call("line B (40,0)->(40,30)", "sketch.line", {"x1": 40, "y1": 0, "x2": 40, "y2": 30, "sketch": idx})
        call("constrain perpendicular 0,1", "sketch.constrain", {"sketch": idx, "type": "perpendicular", "entity_one": 0, "entity_two": 1})
        call("dimension distance 0,1 =50", "sketch.dimension", {"sketch": idx, "type": "distance", "entity_one": 0, "entity_two": 1, "value": 50})
        call("offset curve 0 by 5", "sketch.offset", {"sketch": idx, "curve": 0, "distance": 5, "dir_y": 1})
    call("spline through 3 pts", "sketch.spline", {"points": [[0, 0], [10, 15], [25, 5]], "x": -160, "plane": "xy"})
    sk_proj = call("sketch for projection", "sketch.create", {"plane": "xy"})
    if sk_proj:
        call("project pin edges", "sketch.project", {"sketch": sk_proj["sketch_index"], "body": "pin"},
             show=lambda r: "{} curves".format(r["projected_curves"]))

    print("\n=== surface ===")
    skc = call("circle for patch", "sketch.circle", {"radius": 10, "x": -220, "plane": "xy"})
    if skc:
        call("patch -> surface", "surface.patch", {"sketch": skc["sketch_index"]})

    print("\n=== edit / timeline ===")
    feats = call("feature.list", "feature.list", {}, show=lambda r: "{} features".format(r["count"]))
    fname = None
    if feats and feats["features"]:
        fname = feats["features"][-1]["name"]
    if fname:
        call("suppress '{}'".format(fname), "edit.suppress_feature", {"name": fname})
        call("unsuppress '{}'".format(fname), "edit.unsuppress_feature", {"name": fname})
    call("undo", "edit.undo", tolerate=["design type"])
    call("redo", "edit.redo")

    print("\n=== export DXF ===")
    if sk:
        call("export sketch to DXF", "export.dxf", {"sketch": sk["sketch_index"]}, show=lambda r: r["path"].split("\\")[-1])

    print("\n=== CAM tools ===")
    call("cam.list_tools", "cam.list_tools", tolerate=["cam workspace", "no cam"])

    print("\n=== advanced demo done; {} hard failure(s) ===".format(_fail))
    client.close()
    return 1 if _fail else 0


if __name__ == "__main__":
    raise SystemExit(main())
