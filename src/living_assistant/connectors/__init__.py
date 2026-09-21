"""Connector domain package.

The legacy ``living_assistant.connectors`` module became this package.  Re-export
its public implementation for backwards compatibility.
"""
from .connectors import *  # noqa: F401,F403
from .mobile_bridge import MobileBridge  # noqa: F401
