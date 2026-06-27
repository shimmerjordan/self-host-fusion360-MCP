"""Operation registry.

Importing this package imports every op module, whose ``@op(...)`` decorators
populate ``REGISTRY`` (name -> callable) and ``OPS_META`` (name + flags + docs).
"""

# Import for side effects: each module registers its ops on import.
from . import (  # noqa: F401
    api,
    assembly,
    body,
    cam,
    construction,
    document,
    edit,
    export,
    feature,
    material,
    parameter,
    primitive,
    query,
    script,
    sheetmetal,
    sketch,
    surface,
    system,
    units,
    view,
)
from ._common import OPS_META, REGISTRY

__all__ = ["REGISTRY", "OPS_META"]
