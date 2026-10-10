"""
Autonomous Git Change Manager & Checkpoint Subsystem (Milestone 5 / Feature F11).
Living Assistant - Software Company Governance & Recovery Engine.

Canonical implementation has moved to `living_assistant.system.git_manager`.
This module re-exports GitChangeManager, TaskBaseline, CheckpointRecord,
and RollbackResult for 100% backward compatibility.
"""

from __future__ import annotations

from living_assistant.system.git_manager import (
    CheckpointRecord,
    GitChangeManager,
    RollbackResult,
    TaskBaseline,
)

__all__ = [
    "GitChangeManager",
    "TaskBaseline",
    "CheckpointRecord",
    "RollbackResult",
]
