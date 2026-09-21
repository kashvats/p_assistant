from __future__ import annotations

import living_assistant.evaluation as public_eval
from living_assistant.learning import evaluation as learning_eval
from living_assistant.learning.eval_engine import EvaluationEngine
from living_assistant.learning.eval_measure import compare_benchmark, measure_command
from living_assistant.learning.eval_store import EvaluationStore


def test_evaluation_compatibility_facade_preserves_public_symbols():
    assert public_eval.EvaluationStore is EvaluationStore
    assert public_eval.EvaluationEngine is EvaluationEngine
    assert public_eval.measure_command is measure_command
    assert public_eval.compare_benchmark is compare_benchmark
    assert learning_eval.EvaluationStore is EvaluationStore
    assert learning_eval.EvaluationEngine is EvaluationEngine


def test_evaluation_responsibilities_live_in_split_modules():
    assert EvaluationStore.__module__ == "living_assistant.learning.eval_store"
    assert EvaluationEngine.__module__ == "living_assistant.learning.eval_engine"
    assert measure_command.__module__ == "living_assistant.learning.eval_measure"
    assert compare_benchmark.__module__ == "living_assistant.learning.eval_measure"
