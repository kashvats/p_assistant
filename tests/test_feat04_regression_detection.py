from __future__ import annotations

from living_assistant.evaluation import compare_benchmark
from living_assistant.learning.regression_detection import detect_metric_regression


def _agg(times, memory=None):
    memory = memory or [100.0] * len(times)
    runs = [
        {"ok": True, "duration_seconds": t, "peak_rss_mb": m}
        for t, m in zip(times, memory, strict=True)
    ]
    times_sorted = sorted(times)
    memory_sorted = sorted(memory)
    middle = len(times) // 2
    return {
        "all_passed": True,
        "runs": runs,
        "median_seconds": times_sorted[middle],
        "median_peak_rss_mb": memory_sorted[middle],
    }


def test_stable_regression_beyond_budget_is_detected():
    result = detect_metric_regression(
        [1.00, 1.01, 0.99, 1.00, 1.02],
        [1.20, 1.21, 1.19, 1.20, 1.22],
        10,
    )
    assert result["statistical"] is True
    assert result["regression_pct"] >= 19
    assert result["noise_floor_pct"] < result["regression_pct"]
    assert result["passed"] is False


def test_noisy_point_estimate_does_not_false_positive():
    result = detect_metric_regression(
        [0.70, 1.30, 0.85, 1.15, 1.00],
        [0.78, 1.42, 0.90, 1.22, 1.12],
        10,
    )
    assert result["budget_exceeded"] is True
    assert result["noise_floor_pct"] >= result["regression_pct"]
    assert result["passed"] is True


def test_too_few_samples_falls_back_to_existing_budget_rule():
    result = detect_metric_regression([1.0], [1.2], 10)
    assert result["statistical"] is False
    assert result["fallback"] == "insufficient_samples"
    assert result["passed"] is False


def test_compare_benchmark_reports_statistical_details_for_latency_and_memory():
    baseline = _agg([1.00, 1.01, 0.99, 1.00, 1.02], [100, 101, 99, 100, 100])
    candidate = _agg([1.20, 1.21, 1.19, 1.20, 1.22], [101, 100, 100, 101, 99])
    result = compare_benchmark(baseline, candidate, 10, 10)
    assert result["passed"] is False
    assert result["statistical_detection"]["latency"]["passed"] is False
    assert result["statistical_detection"]["memory"]["passed"] is True


def test_legacy_aggregate_without_raw_runs_preserves_percentage_behavior():
    baseline = {"all_passed": True, "median_seconds": 1.0, "median_peak_rss_mb": 100}
    candidate = {"all_passed": True, "median_seconds": 1.20, "median_peak_rss_mb": 105}
    bad = compare_benchmark(baseline, candidate, 10, 10)
    good = compare_benchmark(baseline, candidate, 25, 10)
    assert bad["passed"] is False and bad["latency_regression_pct"] == 20.0
    assert good["passed"] is True
