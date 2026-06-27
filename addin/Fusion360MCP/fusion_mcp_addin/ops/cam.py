"""CAM (Manufacturing) operations: setups, operations, toolpaths, post (G-code).

Prerequisite: the document must have a Manufacturing (CAM) product. Open the
**Manufacturing** workspace in Fusion at least once so it is initialised; the ops
return a clear hint if it is missing. Lengths are millimetres (converted to cm).
"""

import os

import adsk.cam
import adsk.core

from ._common import op, optional, require
from ..bridge.protocol import ERR_NOT_FOUND, OpError


def _get_cam(ctx):
    doc = ctx.app.activeDocument
    try:
        cam_product = doc.products.itemByProductType("CAMProductType") if doc else None
    except Exception:
        cam_product = None
    if not cam_product:
        raise OpError(
            ERR_NOT_FOUND,
            "No CAM workspace. Open the Manufacturing workspace in Fusion once to "
            "initialise it. / 没有 CAM 工作区，请在 Fusion 里打开一次「制造」工作区。",
        )
    return adsk.cam.CAM.cast(cam_product)


def _find_setup(cam, name):
    for i in range(cam.setups.count):
        if cam.setups.item(i).name == name:
            return cam.setups.item(i)
    raise OpError(ERR_NOT_FOUND, "Setup '{}' not found.".format(name))


def _find_operation(setup, name):
    for i in range(setup.operations.count):
        if setup.operations.item(i).name == name:
            return setup.operations.item(i)
    raise OpError(ERR_NOT_FOUND, "Operation '{}' not found in setup '{}'.".format(name, setup.name))


def _local_tool_libraries():
    mgr = adsk.cam.CAMManager.get()
    libs = mgr.libraryManager.toolLibraries
    root_url = libs.urlByLocation(adsk.cam.LibraryLocations.LocalLibraryLocation)
    assets = []

    def walk(url, depth=0):
        if depth > 4:
            return
        try:
            for a in libs.childAssetURLs(url):
                assets.append(a)
        except Exception:
            pass
        try:
            for f in libs.childFolderURLs(url):
                walk(f, depth + 1)
        except Exception:
            pass

    walk(root_url)
    return libs, assets


def _pick_tool(lib_index=0, tool_index=0):
    """Best-effort: return a Tool from the local library, or None."""
    try:
        libs, assets = _local_tool_libraries()
        if not assets:
            return None
        lib = libs.toolLibrary(assets[min(lib_index, len(assets) - 1)])
        if lib.count == 0:
            return None
        return lib.item(min(tool_index, lib.count - 1))
    except Exception:
        return None


@op("cam.list_setups", summary="List CAM setups and their operations.", readonly=True)
def list_setups(ctx, params):
    cam = _get_cam(ctx)
    out = []
    for i in range(cam.setups.count):
        s = cam.setups.item(i)
        out.append({
            "name": s.name,
            "is_valid": s.isValid,
            "operations": [s.operations.item(j).name for j in range(s.operations.count)],
        })
    return {"count": cam.setups.count, "setups": out}


@op("cam.list_operations", summary="List operations in a setup (name, has_toolpath, valid).", readonly=True)
def list_operations(ctx, params):
    cam = _get_cam(ctx)
    setup = _find_setup(cam, require(params, "setup", str))
    out = []
    for i in range(setup.operations.count):
        o = setup.operations.item(i)
        out.append({"name": o.name, "has_toolpath": o.hasToolpath, "is_valid": o.isValid})
    return {"setup": setup.name, "count": setup.operations.count, "operations": out}


@op("cam.create_setup", summary="Create a milling/turning/cutting setup around a body.")
def create_setup(ctx, params):
    cam = _get_cam(ctx)
    body = ctx.get_body(require(params, "body", (int, str)))
    name = optional(params, "name", None, types=str)
    op_type = str(optional(params, "operation_type", "milling", types=str)).lower()
    type_map = {
        "milling": adsk.cam.OperationTypes.MillingOperation,
        "turning": adsk.cam.OperationTypes.TurningOperation,
        "cutting": adsk.cam.OperationTypes.JetOperation,
    }
    if op_type not in type_map:
        raise OpError(ERR_NOT_FOUND, "operation_type must be milling/turning/cutting.")
    setup_input = cam.setups.createInput(type_map[op_type])
    setup_input.models = [body]
    if name:
        setup_input.name = name
    setup = cam.setups.add(setup_input)
    return {"name": setup.name, "operation_type": op_type, "body": body.name}


@op("cam.create_operation", summary="Add an operation to a setup by strategy (e.g. face/pocket2d/adaptive2d/drill/contour2d).")
def create_operation(ctx, params):
    cam = _get_cam(ctx)
    setup = _find_setup(cam, require(params, "setup", str))
    strategy = require(params, "strategy", str)
    name = optional(params, "name", None, types=str)
    op_input = setup.operations.createInput(strategy)
    if name:
        op_input.name = name
    # Assign a real cutting tool so the toolpath can actually generate (faust
    # omitted this, which is why its toolpaths often fail).
    assigned_tool = None
    try:
        tool = _pick_tool(
            int(optional(params, "tool_library", 0, types=int)),
            int(optional(params, "tool_index", 0, types=int)),
        )
        if tool is not None:
            op_input.tool = tool
            assigned_tool = True
    except Exception:
        assigned_tool = False
    diameter = optional(params, "tool_diameter", None, types=(int, float))
    stepdown = optional(params, "stepdown", None, types=(int, float))
    stepover = optional(params, "stepover", None, types=(int, float))
    if diameter is not None:
        op_input.toolDiameter = adsk.core.ValueInput.createByReal(ctx.mm2cm(diameter))
    if stepdown is not None:
        op_input.maximumStepdown = adsk.core.ValueInput.createByReal(ctx.mm2cm(stepdown))
    if stepover is not None:
        op_input.maximumStepover = adsk.core.ValueInput.createByReal(ctx.mm2cm(stepover))
    operation = setup.operations.add(op_input)
    return {"name": operation.name, "setup": setup.name, "strategy": strategy, "tool_assigned": bool(assigned_tool)}


@op("cam.list_tools", summary="List cutting tools available in the local tool library (first N).", readonly=True)
def list_tools(ctx, params):
    _get_cam(ctx)  # ensure CAM workspace exists
    limit = int(optional(params, "limit", 20, types=int))
    libs, assets = _local_tool_libraries()
    tools = []
    for asset in assets:
        if len(tools) >= limit:
            break
        try:
            lib = libs.toolLibrary(asset)
        except Exception:
            continue
        for i in range(lib.count):
            if len(tools) >= limit:
                break
            try:
                t = lib.item(i)
                desc = t.description if hasattr(t, "description") else None
                tools.append({"library_index": assets.index(asset), "tool_index": i, "description": desc})
            except Exception:
                pass
    return {"library_count": len(assets), "tools": tools}


@op("cam.generate", summary="Generate toolpaths (one operation, a whole setup, or all).")
def generate(ctx, params):
    cam = _get_cam(ctx)
    if bool(optional(params, "all", False, types=bool)):
        cam.generateAllToolpaths(False).wait()
        return {"generated": True, "scope": "all"}
    setup_name = optional(params, "setup", None, types=str)
    op_name = optional(params, "operation", None, types=str)
    if setup_name and op_name:
        setup = _find_setup(cam, setup_name)
        cam.generateToolpath(_find_operation(setup, op_name)).wait()
        return {"generated": True, "scope": "operation", "operation": op_name}
    if setup_name:
        setup = _find_setup(cam, setup_name)
        ops = adsk.core.ObjectCollection.create()
        for i in range(setup.operations.count):
            ops.add(setup.operations.item(i))
        cam.generateToolpath(ops).wait()
        return {"generated": True, "scope": "setup", "setup": setup_name}
    raise OpError(ERR_NOT_FOUND, "Provide all=true, or a setup (and optional operation).")


@op("cam.post_process", summary="Post-process a setup/operation to a G-code file.")
def post_process(ctx, params):
    cam = _get_cam(ctx)
    setup = _find_setup(cam, require(params, "setup", str))
    op_name = optional(params, "operation", None, types=str)
    post = str(optional(params, "post_processor", "fanuc", types=str))
    units = str(optional(params, "units", "mm", types=str)).lower()
    output_folder = optional(params, "output_folder", None, types=str)
    if not output_folder:
        output_folder = os.path.join(os.path.expanduser("~"), "fusion-mcp-exports", "nc")
    os.makedirs(output_folder, exist_ok=True)

    post_config = os.path.join(cam.genericPostFolder, post + ".cps")
    unit_opt = (
        adsk.cam.PostOutputUnitOptions.MillimetersOutput
        if units == "mm"
        else adsk.cam.PostOutputUnitOptions.InchesOutput
    )
    post_input = adsk.cam.PostProcessInput.create(setup.name, post_config, output_folder, unit_opt)
    post_input.isOpenInEditor = False
    if op_name:
        cam.postProcess(_find_operation(setup, op_name), post_input)
    else:
        cam.postProcess(setup, post_input)
    return {"setup": setup.name, "post_processor": post, "output_folder": output_folder, "units": units}
