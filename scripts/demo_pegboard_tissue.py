"""Build a pegboard-mounted, inverted tissue box on the LIVE Fusion bridge.

Pegboard spec: 30 mm hole pitch, 4.8 mm holes -> Ø4.6 pegs on a 30 mm grid.
IKEA-ish open-front pocket; dispenses from a bottom obround slot (inverted).

Run: python scripts/demo_pegboard_tissue.py   (Fusion must be open, add-in loaded)
"""

import base64
import json
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

c = AddinClient(load_config())


def call(op, **params):
    try:
        r = c.call(op, params)
        d = r.get("_delta") if isinstance(r, dict) else None
        extra = ""
        if isinstance(r, dict):
            for k in ("sketch_index", "body", "feature_name", "index", "min_distance_mm", "mass_g"):
                if k in r:
                    extra = "{}={}".format(k, r[k])
                    break
        print("  [ok] {:<22} {} {}".format(op, extra, "Δ" + str(d.get("bodies_added")) if d else ""))
        return r
    except FusionMCPError as e:
        print("  [FAIL] {:<20} {}".format(op, str(e).splitlines()[0]))
        return None


# ── dimensions (mm) ──────────────────────────────────────────────────────────
W, D, H, T = 125.0, 70.0, 125.0, 2.5          # outer + wall thickness
PEG_D, PEG_LEN = 4.6, 14.0                      # peg dia / length
PEG_DIR = "negative"                            # extrude dir for pegs (flip if they go inward)
PITCH = 30.0
SLOT_W, SLOT_H = 85.0, 18.0                     # bottom dispensing slot


def main():
    print("== Pegboard inverted tissue box ==")
    call("document.new")

    # 1) outer shell, base at z=0, centered in x, y in [0, D]
    call("primitive.box", width=W, depth=D, height=H, x=0, y=D / 2, name="shell")

    # 2) hollow it, opening the FRONT (y=D). cavity walls = T.
    call("primitive.box", width=W - 2 * T, depth=D, height=H - 2 * T, x=0, y=D / 2 + T, name="cav")
    call("body.move", body="cav", dz=T)                       # leave a bottom wall
    call("body.combine", target="shell", tools="cav", operation="cut")

    # 3) front retaining lip (low wall at the bottom-front so the pack can't fall out)
    call("primitive.box", width=W - 2 * T, depth=T, height=35.0, x=0, y=D - T / 2, name="lip")
    call("body.combine", target="shell", tools="lip", operation="join")

    # 4) bottom obround dispensing slot (rectangle + 2 end circles), cut up through the floor
    s = call("sketch.rectangle", width=SLOT_W, height=SLOT_H, mode="center", x=0, y=D / 2, plane="xy")
    if s:
        idx = s["sketch_index"]
        call("sketch.circle", sketch=idx, x=SLOT_W / 2, y=D / 2, radius=SLOT_H / 2)
        call("sketch.circle", sketch=idx, x=-SLOT_W / 2, y=D / 2, radius=SLOT_H / 2)
        call("feature.extrude", sketch=idx, distance=T + 1, direction="positive",
             operation="cut", profile="all")

    # 5) pegboard hooks: 4 pegs on a 30 mm grid. Sketch on a plane 1.5 mm INSIDE the
    #    back wall so the peg overlaps the wall volume (a coincident-only face won't
    #    reliably weld); extrude -Y through and out the back, joined to the shell.
    # NOTE (measured): on this offset XZ plane, sketch-x -> world X, but sketch-y ->
    # world -Z, and offset value maps directly to world Y. So use offset=+1.5 (inside
    # the wall) and pass sketch y = -pz to land at world Z=+pz.
    plane = call("construction.offset_plane", base="xz", offset=1.5)    # world Y=+1.5, inside back wall
    pidx = (plane or {}).get("index")
    if pidx is not None:
        for px in (-PITCH / 2, PITCH / 2):
            for pz in (H - 30.0, H - 60.0):          # two rows, 30 mm apart, near the top
                cs = call("sketch.circle", plane=pidx, x=px, y=-pz, radius=PEG_D / 2)
                if cs:
                    call("feature.extrude", sketch=cs["sketch_index"], distance=PEG_LEN + 1.5,
                         direction=PEG_DIR, operation="join")

    # 6) inspect + capture + export
    call("query.physical_properties", body="shell")
    call("view.orientation", name="iso")
    call("view.fit")
    shot = call("view.screenshot", width=1100, height=850)
    if shot and shot.get("base64"):
        (ROOT / "screenshots").mkdir(exist_ok=True)
        (ROOT / "screenshots" / "pegboard.png").write_bytes(base64.b64decode(shot["base64"]))
        print("  saved screenshots/pegboard.png")
    call("export.step")
    call("export.stl", body="shell")
    c.close()


if __name__ == "__main__":
    main()
