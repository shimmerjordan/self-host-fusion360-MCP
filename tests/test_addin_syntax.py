"""Compile-check the add-in (which imports ``adsk`` and cannot be imported here).

This catches syntax errors in the in-Fusion code without a Fusion runtime.
"""

import py_compile
from pathlib import Path

ADDIN_DIR = Path(__file__).resolve().parents[1] / "addin" / "Fusion360MCP"


def test_addin_python_files_compile():
    files = list(ADDIN_DIR.rglob("*.py"))
    assert files, "no add-in python files found at " + str(ADDIN_DIR)
    for path in files:
        py_compile.compile(str(path), doraise=True)
