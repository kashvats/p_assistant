"""Command-line interface package.

The public ``living_assistant.cli:app`` entry point is preserved while command
implementations live in :mod:`living_assistant.cli.commands`.
"""

from .commands import *  # noqa: F401,F403
