"""Evaluation compatibility facade split by storage, measurement, and engine concerns."""

from living_assistant.core.config import data_dir
from .eval_store import SCHEMA, EvaluationStore, _now, _json, _decode
from .eval_measure import _kill_tree, measure_command, _aggregate_runs, compare_benchmark
from .eval_engine import (
    DEFAULT_IGNORES,
    EvaluationEngine,
    _sha_text,
    _git,
    _repo_root,
    _reset_eval_worktree,
    _copy_project,
)

__all__ = [
    'SCHEMA', 'DEFAULT_IGNORES', 'EvaluationStore', 'EvaluationEngine',
    'measure_command', 'compare_benchmark', 'data_dir',
]
