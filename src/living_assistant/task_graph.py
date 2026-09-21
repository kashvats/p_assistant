"""Backward-compatible import alias. Implementation moved to living_assistant.agents.task_graph."""
import importlib as _importlib
import sys as _sys
_impl = _importlib.import_module("living_assistant.agents.task_graph")
_sys.modules[__name__] = _impl
