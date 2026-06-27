"""Viewport operations: screenshot, fit, named orientation."""

import base64
import os
import tempfile

import adsk.core

from ._common import op, optional
from ..bridge.protocol import ERR_FUSION, OpError


@op("view.screenshot", summary="Capture the active viewport as a PNG (returned as base64).", readonly=True)
def screenshot(ctx, params):
    width = int(optional(params, "width", 1280, types=int))
    height = int(optional(params, "height", 720, types=int))
    fit = bool(optional(params, "fit", True, types=bool))
    viewport = ctx.app.activeViewport
    if viewport is None:
        raise OpError(ERR_FUSION, "No active viewport to capture.")
    if fit:
        try:
            viewport.fit()
        except Exception:
            pass
    fd, path = tempfile.mkstemp(suffix=".png")
    os.close(fd)
    try:
        ok = viewport.saveAsImageFile(path, width, height)
        if not ok:
            raise OpError(ERR_FUSION, "saveAsImageFile returned false.")
        with open(path, "rb") as fh:
            data = base64.b64encode(fh.read()).decode("ascii")
    finally:
        try:
            os.remove(path)
        except Exception:
            pass
    return {"mime": "image/png", "base64": data, "width": width, "height": height}


@op("view.fit", summary="Fit the view to the model.", idempotent=True)
def fit(ctx, params):
    viewport = ctx.app.activeViewport
    if viewport is None:
        raise OpError(ERR_FUSION, "No active viewport.")
    viewport.fit()
    return {"fitted": True}


_ORIENTATIONS = {
    "home": "IsoTopRightViewOrientation",
    "iso": "IsoTopRightViewOrientation",
    "top": "TopViewOrientation",
    "bottom": "BottomViewOrientation",
    "front": "FrontViewOrientation",
    "back": "BackViewOrientation",
    "left": "LeftViewOrientation",
    "right": "RightViewOrientation",
}


@op("view.orientation", summary="Set a named camera orientation (home/iso/top/front/...).", idempotent=True)
def orientation(ctx, params):
    name = (optional(params, "name", "iso", types=str) or "iso").lower()
    enum_name = _ORIENTATIONS.get(name)
    if enum_name is None:
        raise OpError(
            "invalid_params",
            "orientation must be one of: " + ", ".join(sorted(_ORIENTATIONS)),
        )
    viewport = ctx.app.activeViewport
    camera = viewport.camera
    camera.viewOrientation = getattr(adsk.core.ViewOrientations, enum_name)
    camera.isSmoothTransition = False
    viewport.camera = camera
    try:
        viewport.refresh()
    except Exception:
        pass
    return {"orientation": name}
