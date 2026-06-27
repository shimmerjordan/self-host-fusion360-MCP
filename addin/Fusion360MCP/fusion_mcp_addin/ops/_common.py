"""Shared helpers + the op registry.

Every operation is a function ``fn(ctx, params) -> result`` registered with the
``@op(...)`` decorator. ``ctx`` is a fresh :class:`Ctx` built on the main thread
for each call. All lengths crossing the API are **millimetres**; Fusion's
internal database unit is centimetres, so conversion happens here, once, at the
boundary — this is the single most common source of 10x bugs in community tools.
"""

import adsk.core
import adsk.fusion

from ..bridge.protocol import (
    ERR_INVALID_PARAMS,
    ERR_NO_ACTIVE_DESIGN,
    ERR_NOT_FOUND,
    OpError,
)

# --- registry ---------------------------------------------------------------
REGISTRY = {}
OPS_META = []
# Shared runtime handles (e.g. the active Dispatcher) for system ops like
# system.reload. Lives in _common because _common is never hot-reloaded, so the
# objects survive a reload and stay referenced by the dispatcher.
RUNTIME = {}


def op(name, summary="", readonly=False, destructive=False, idempotent=False, params=None):
    def deco(fn):
        if name in REGISTRY:
            raise RuntimeError("duplicate op registration: " + name)
        REGISTRY[name] = fn
        OPS_META.append(
            {
                "name": name,
                "summary": summary,
                "readonly": bool(readonly),
                "destructive": bool(destructive),
                "idempotent": bool(idempotent),
                "params": params or [],
            }
        )
        return fn

    return deco


# --- param validation --------------------------------------------------------
_MISSING = object()


def require(params, key, types=None):
    value = params.get(key, _MISSING)
    if value is _MISSING:
        raise OpError(ERR_INVALID_PARAMS, "Missing required parameter: '{}'".format(key))
    if types is not None and not isinstance(value, types):
        raise OpError(
            ERR_INVALID_PARAMS,
            "Parameter '{}' must be {}.".format(key, _type_name(types)),
        )
    return value


def optional(params, key, default=None, types=None):
    value = params.get(key, default)
    if value is None:
        return default
    if types is not None and not isinstance(value, types):
        raise OpError(
            ERR_INVALID_PARAMS,
            "Parameter '{}' must be {}.".format(key, _type_name(types)),
        )
    return value


def _type_name(types):
    if isinstance(types, tuple):
        return " or ".join(t.__name__ for t in types)
    return types.__name__


# --- context -----------------------------------------------------------------
class Ctx:
    """Convenience accessors built on Fusion's main thread."""

    def __init__(self):
        self.app = adsk.core.Application.get()
        self.ui = self.app.userInterface

    # active product / design
    def design(self):
        product = self.app.activeProduct
        design = adsk.fusion.Design.cast(product)
        if design is None:
            raise OpError(
                ERR_NO_ACTIVE_DESIGN,
                "No active Fusion design. Open or create a Design document first. "
                "/ 没有活动的 Fusion 设计，请先打开或新建一个设计文档。",
            )
        return design

    def root(self):
        return self.design().rootComponent

    def ensure_design(self):
        """Like design(), but auto-creates a new design document if none is open
        (when auto_create_document is enabled). Use this in build/creation ops."""
        design = adsk.fusion.Design.cast(self.app.activeProduct)
        if design is not None:
            return design
        from .. import config as _config

        if _config.get_settings().get("auto_create_document", True):
            try:
                self.app.documents.add(
                    adsk.core.DocumentTypes.FusionDesignDocumentType
                )
            except Exception as exc:  # noqa: BLE001
                raise OpError(
                    ERR_NO_ACTIVE_DESIGN,
                    "No active design and auto-create failed. / 无活动设计且自动新建失败。",
                    str(exc),
                )
            design = adsk.fusion.Design.cast(self.app.activeProduct)
            if design is not None:
                return design
        raise OpError(
            ERR_NO_ACTIVE_DESIGN,
            "No active Fusion design. Open/create one, or enable auto_create_document. "
            "/ 没有活动设计；请新建一个或启用 auto_create_document。",
        )

    def ensure_root(self):
        return self.ensure_design().rootComponent

    def units(self):
        return self.design().fusionUnitsManager

    # unit conversion (mm <-> cm)
    @staticmethod
    def mm2cm(value):
        return float(value) / 10.0

    @staticmethod
    def cm2mm(value):
        return float(value) * 10.0

    def len_mm(self, value):
        """ValueInput for a length given in millimetres."""
        return adsk.core.ValueInput.createByReal(self.mm2cm(value))

    @staticmethod
    def by_expr(expr):
        return adsk.core.ValueInput.createByString(str(expr))

    @staticmethod
    def angle_deg(value):
        return adsk.core.ValueInput.createByString("{} deg".format(value))

    def point_mm(self, x, y, z=0.0):
        return adsk.core.Point3D.create(self.mm2cm(x), self.mm2cm(y), self.mm2cm(z))

    # entity lookup
    def get_body(self, ref):
        bodies = self.root().bRepBodies
        if isinstance(ref, bool):  # guard: bool is an int subclass
            raise OpError(ERR_INVALID_PARAMS, "body reference must be an index or name")
        if isinstance(ref, int):
            if ref < 0 or ref >= bodies.count:
                raise OpError(
                    ERR_NOT_FOUND,
                    "Body index {} out of range (0..{}).".format(ref, bodies.count - 1),
                )
            return bodies.item(ref)
        if isinstance(ref, str):
            body = bodies.itemByName(ref)
            if body is None:
                raise OpError(ERR_NOT_FOUND, "No body named '{}'.".format(ref))
            return body
        raise OpError(ERR_INVALID_PARAMS, "body must be an index (int) or name (str).")

    def get_sketch(self, ref):
        sketches = self.root().sketches
        if isinstance(ref, int):
            if ref < 0 or ref >= sketches.count:
                raise OpError(
                    ERR_NOT_FOUND,
                    "Sketch index {} out of range (0..{}).".format(ref, sketches.count - 1),
                )
            return sketches.item(ref)
        if isinstance(ref, str):
            sk = sketches.itemByName(ref)
            if sk is None:
                raise OpError(ERR_NOT_FOUND, "No sketch named '{}'.".format(ref))
            return sk
        raise OpError(ERR_INVALID_PARAMS, "sketch must be an index (int) or name (str).")

    def get_plane(self, ref):
        """Accept 'xy'/'xz'/'yz', a construction-plane index, a planar face
        reference {"body": ref, "face": index}, or default xy."""
        root = self.root()
        if ref is None:
            return root.xYConstructionPlane
        if isinstance(ref, dict):
            return self.get_planar_face(ref.get("body"), ref.get("face"))
        if isinstance(ref, str):
            key = ref.strip().lower()
            mapping = {
                "xy": root.xYConstructionPlane,
                "xz": root.xZConstructionPlane,
                "yz": root.yZConstructionPlane,
            }
            if key in mapping:
                return mapping[key]
            raise OpError(ERR_INVALID_PARAMS, "plane must be one of xy/xz/yz or an index.")
        if isinstance(ref, int):
            planes = root.constructionPlanes
            if ref < 0 or ref >= planes.count:
                raise OpError(ERR_NOT_FOUND, "Construction plane index {} out of range.".format(ref))
            return planes.item(ref)
        raise OpError(ERR_INVALID_PARAMS, "plane must be 'xy'/'xz'/'yz', an index, or {body,face}.")

    def get_planar_face(self, body_ref, face_index):
        body = self.get_body(body_ref)
        faces = body.faces
        if not isinstance(face_index, int) or face_index < 0 or face_index >= faces.count:
            raise OpError(
                ERR_NOT_FOUND,
                "Face index {} out of range (0..{}). Use query.list_faces.".format(
                    face_index, faces.count - 1
                ),
            )
        face = faces.item(face_index)
        try:
            is_planar = face.geometry.surfaceType == adsk.core.SurfaceTypes.PlaneSurfaceType
        except Exception:
            is_planar = False
        if not is_planar:
            raise OpError(
                ERR_INVALID_PARAMS,
                "Face {} is not planar; pick a flat face (query.list_faces shows is_planar).".format(
                    face_index
                ),
            )
        return face

    def get_axis(self, ref):
        root = self.root()
        key = str(ref).strip().lower()
        mapping = {
            "x": root.xConstructionAxis,
            "y": root.yConstructionAxis,
            "z": root.zConstructionAxis,
        }
        if key in mapping:
            return mapping[key]
        raise OpError(ERR_INVALID_PARAMS, "axis must be 'x', 'y', or 'z'.")

    @staticmethod
    def feature_operation(name):
        ops = {
            "new": adsk.fusion.FeatureOperations.NewBodyFeatureOperation,
            "newbody": adsk.fusion.FeatureOperations.NewBodyFeatureOperation,
            "join": adsk.fusion.FeatureOperations.JoinFeatureOperation,
            "cut": adsk.fusion.FeatureOperations.CutFeatureOperation,
            "intersect": adsk.fusion.FeatureOperations.IntersectFeatureOperation,
            "newcomponent": adsk.fusion.FeatureOperations.NewComponentFeatureOperation,
        }
        key = str(name).strip().lower()
        if key not in ops:
            raise OpError(
                ERR_INVALID_PARAMS,
                "operation must be one of new/join/cut/intersect/newcomponent.",
            )
        return ops[key]

    @staticmethod
    def collection(items):
        coll = adsk.core.ObjectCollection.create()
        for it in items:
            coll.add(it)
        return coll


# --- summaries (used by query ops) ------------------------------------------
def bbox_mm(bbox):
    if bbox is None:
        return None
    return {
        "min": [bbox.minPoint.x * 10.0, bbox.minPoint.y * 10.0, bbox.minPoint.z * 10.0],
        "max": [bbox.maxPoint.x * 10.0, bbox.maxPoint.y * 10.0, bbox.maxPoint.z * 10.0],
        "size": [
            (bbox.maxPoint.x - bbox.minPoint.x) * 10.0,
            (bbox.maxPoint.y - bbox.minPoint.y) * 10.0,
            (bbox.maxPoint.z - bbox.minPoint.z) * 10.0,
        ],
    }


def body_summary(body, index):
    try:
        volume_cm3 = body.volume
    except Exception:
        volume_cm3 = None
    return {
        "index": index,
        "name": body.name,
        "is_solid": body.isSolid,
        "is_visible": body.isVisible,
        "volume_mm3": (volume_cm3 * 1000.0) if volume_cm3 is not None else None,
        "bbox_mm": bbox_mm(getattr(body, "boundingBox", None)),
    }
