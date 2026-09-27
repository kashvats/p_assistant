import json
import logging
from dataclasses import dataclass
from tests.test_orchestrator_reliability import test_case_a_strict_result_validation, \
    test_case_b_cross_step_loop_detection, test_case_c_jev_loop_breaker_content_length, \
    test_case_d_context_ordering, test_case_e_active_tool_check, test_case_f_taskstate_fingerprint, \
    test_case_g_taskstate_audit_summary, test_case_h_filesystem_write_verification, \
    test_case_i_tool_routing_bm25_fallback, test_case_j_tool_routing_core_tools, \
    test_case_k_loop_injection_hard_stop

logging.basicConfig(level=logging.INFO)

@dataclass
class EvalMetric:
    id: str
    name: str
    description: str
    weight: float
    passed: bool = False

METRICS = [
    EvalMetric("M01", "Strict Boolean Provenance", "Tool success (ok_result) tracks provenance rather than defaulting true", 1.0),
    EvalMetric("M02", "Hard Loop Blockers", "Cross-step tool repetitions are blocked and fed back to context", 1.5),
    EvalMetric("M03", "Premature Exit Prevention", "Jev goal_achieved requires minimum output tokens to fire", 1.0),
    EvalMetric("M04", "Context Priority Alignment", "Current request is placed at the end of the payload for max model attention", 1.0),
    EvalMetric("M05", "Hallucination Defense", "Jev security gate is skipped for hallucinatory non-existent tools", 1.0),
    EvalMetric("M06", "State Fingerprinting", "Task state hashes account for unordered kwargs correctly", 0.5),
    EvalMetric("M07", "Audit State Retention", "Task trace summaries are retained perfectly for the loop breaker", 1.0),
    EvalMetric("M08", "Artifact Verification", "File system writes verify post-write file existence", 1.5),
    EvalMetric("M09", "Resilient Tool Routing", "Orchestrator falls back to BM25 search if Jev scores tools poorly", 1.0),
    EvalMetric("M10", "Core Tools Preservation", "Catalog search is always active for self-discovery", 0.5),
    EvalMetric("M11", "Context Burn Prevention", "Loops yield stop messages before burning context window limit", 1.5),
]

def run_eval_harness():
    print("--- Running Orchestrator Evaluation Harness ---")
    
    # We cheat slightly by mapping tests directly to metrics
    # In a full framework, this would dynamically execute PyTest nodes
    test_map = [
        ("M01", test_case_a_strict_result_validation, True),
        ("M02", test_case_b_cross_step_loop_detection, False),
        ("M03", test_case_c_jev_loop_breaker_content_length, True),
        ("M04", test_case_d_context_ordering, True),
        ("M05", test_case_e_active_tool_check, True),
        ("M06", test_case_f_taskstate_fingerprint, False),
        ("M07", test_case_g_taskstate_audit_summary, False),
        ("M08", test_case_h_filesystem_write_verification, True),
        ("M09", test_case_i_tool_routing_bm25_fallback, True),
        ("M10", test_case_j_tool_routing_core_tools, True),
        ("M11", test_case_k_loop_injection_hard_stop, True),
    ]
    
    # Needs mock orchestrator fixture
    from tests.test_orchestrator_reliability import mock_orchestrator
    
    total_weight = sum(m.weight for m in METRICS)
    passed_weight = 0.0
    
    for metric_id, test_func, needs_mock in test_map:
        metric = next(m for m in METRICS if m.id == metric_id)
        try:
            if needs_mock:
                # Some tests need tmp_path (M08)
                if metric_id == "M08":
                    from pathlib import Path
                    import tempfile
                    with tempfile.TemporaryDirectory() as td:
                        test_func(Path(td))
                else:
                    test_func(mock_orchestrator())
            else:
                test_func()
            metric.passed = True
            passed_weight += metric.weight
            print(f"[PASS] {metric.id}: {metric.name}")
        except Exception as e:
            print(f"[FAIL] {metric.id}: {metric.name} - {e}")
            
    score = (passed_weight / total_weight) * 100
    print(f"\nFinal Reliability Score: {score:.1f}%")
    
    with open("eval_results.json", "w") as f:
        json.dump([{"id": m.id, "name": m.name, "passed": m.passed} for m in METRICS], f, indent=2)

if __name__ == "__main__":
    run_eval_harness()
