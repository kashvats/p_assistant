"""Backward-compatible import alias. Implementation moved to living_assistant.desktop.approval_ui."""
import importlib as _importlib
import sys as _sys
_impl = _importlib.import_module("living_assistant.desktop.approval_ui")
_sys.modules[__name__] = _impl
