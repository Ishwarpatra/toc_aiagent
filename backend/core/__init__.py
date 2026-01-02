"""Compatibility shim so tests can import `core.*` while sources live under
`python_imply.core`.

This module imports the real submodules from `python_imply.core` and inserts
them into `sys.modules` as `core.<submodule>` so statements like
`from core.product import ProductConstructionEngine` work when tests are run
from the repository root.
"""
import importlib
import sys

_SUBMODULES = ["product", "models", "agents", "validator", "repair"]

for _name in _SUBMODULES:
    mod = importlib.import_module(f"python_imply.core.{_name}")
    # expose as attribute on this package
    globals()[_name] = mod
    # ensure import machinery can find `core.<name>`
    sys.modules[f"core.{_name}"] = mod
