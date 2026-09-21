"""Backward-compatible import alias. Implementation moved to living_assistant.agents.prompts."""
import importlib as _importlib
import sys as _sys
_impl = _importlib.import_module("living_assistant.agents.prompts")
_sys.modules[__name__] = _impl
