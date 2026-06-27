"""Fusion360MCP add-in entry point.

This thin shim only bootstraps the real implementation, which lives in the
uniquely named ``fusion_mcp_addin`` sub-package next to this file. Keeping the
implementation in a uniquely named package avoids ``sys.path`` collisions with
other add-ins (many add-ins naively insert their own folder onto sys.path).

Fusion calls ``run(context)`` when the add-in starts and ``stop(context)`` when
it stops or Fusion exits.
"""

import os
import sys
import traceback

import adsk.core

# Make the add-in folder importable so ``import fusion_mcp_addin`` resolves.
_THIS_DIR = os.path.dirname(os.path.realpath(__file__))
if _THIS_DIR not in sys.path:
    sys.path.insert(0, _THIS_DIR)


def _purge_package_modules():
    """Drop cached package modules so a Stop->Run reloads edited code.

    Fusion keeps modules in sys.modules across Stop/Run, so without this an
    updated add-in would only take effect after a full Fusion restart.
    """
    for name in [m for m in sys.modules if m == "fusion_mcp_addin" or m.startswith("fusion_mcp_addin.")]:
        del sys.modules[name]


def run(context):
    try:
        _purge_package_modules()
        import fusion_mcp_addin
        fusion_mcp_addin.start()
    except Exception:
        try:
            adsk.core.Application.get().userInterface.messageBox(
                "Fusion360MCP failed to start:\n\n" + traceback.format_exc()
            )
        except Exception:
            pass


def stop(context):
    try:
        import fusion_mcp_addin
        fusion_mcp_addin.stop()
    except Exception:
        # Never raise from stop(); just surface to the log if possible.
        try:
            import fusion_mcp_addin
            fusion_mcp_addin.log("stop() error:\n" + traceback.format_exc())
        except Exception:
            pass
