"""Agent domain package.

The legacy ``living_assistant.agents`` module became this package.  Re-export its
public implementation so existing imports continue to work while related agent
modules live under one domain.
"""
from .agents import *  # noqa: F401,F403
