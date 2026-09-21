from __future__ import annotations

import math
import statistics
from typing import Iterable


def _clean(values: Iterable[float | int | None]) -> list[float]:
    clean: list[float] = []
    for value in values:
        if value is None:
            continue
        try:
            number = float(value)
        except (TypeError, ValueError):
            continue
        if math.isfinite(number) and number >= 0:
            clean.append(number)
    return clean


def _robust_sigma(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    median = statistics.median(values)
    mad = statistics.median(abs(value - median) for value in values)
    mad_sigma = 1.4826 * mad
    # MAD intentionally ignores isolated outliers. For a regression gate we also
    # account for ordinary sample variance and use the larger estimate so noisy
    # benchmarks do not produce false regressions merely because MAD is zero.
    try:
        sample_sigma = statistics.stdev(values)
    except statistics.StatisticsError:
        sample_sigma = 0.0
    return max(mad_sigma, sample_sigma)


def detect_metric_regression(
    baseline_values: Iterable[float | int | None],
    candidate_values: Iterable[float | int | None],
    max_regression_pct: float,
    *,
    minimum_samples: int = 3,
    minimum_noise_floor_pct: float = 1.0,
    confidence_multiplier: float = 1.96,
) -> dict:
    """Compare benchmark samples using a robust sampling-noise floor.

    With fewer than ``minimum_samples`` successful runs, the function deliberately
    falls back to the legacy percentage-budget rule because there is not enough
    data to estimate benchmark noise. With enough samples, a candidate fails only
    when its median regression exceeds both the configured budget and the estimated
    95%-style sampling noise floor.
    """

    baseline = _clean(baseline_values)
    candidate = _clean(candidate_values)
    result = {
        "valid": bool(baseline and candidate),
        "passed": False,
        "baseline_samples": len(baseline),
        "candidate_samples": len(candidate),
        "baseline_median": None,
        "candidate_median": None,
        "regression_pct": None,
        "noise_floor_pct": None,
        "budget_pct": float(max_regression_pct),
        "statistical": False,
        "meaningful_regression": False,
        "budget_exceeded": False,
    }
    if not result["valid"]:
        result["reason"] = "Baseline and candidate require successful numeric samples."
        return result

    baseline_median = float(statistics.median(baseline))
    candidate_median = float(statistics.median(candidate))
    result["baseline_median"] = baseline_median
    result["candidate_median"] = candidate_median
    if baseline_median <= 1e-12:
        regression_pct = 0.0 if candidate_median <= 1e-12 else float("inf")
    else:
        regression_pct = ((candidate_median - baseline_median) / baseline_median) * 100.0
    result["regression_pct"] = round(regression_pct, 2) if math.isfinite(regression_pct) else regression_pct
    result["budget_exceeded"] = regression_pct > float(max_regression_pct)

    if len(baseline) < minimum_samples or len(candidate) < minimum_samples:
        result["passed"] = not result["budget_exceeded"]
        result["fallback"] = "insufficient_samples"
        if not result["passed"]:
            result["reason"] = "Candidate exceeded the configured regression budget; insufficient samples for noise estimation."
        return result

    baseline_sigma = _robust_sigma(baseline)
    candidate_sigma = _robust_sigma(candidate)
    standard_error = math.sqrt(
        (baseline_sigma * baseline_sigma / len(baseline))
        + (candidate_sigma * candidate_sigma / len(candidate))
    )
    sampling_noise_pct = (
        (confidence_multiplier * standard_error / baseline_median) * 100.0
        if baseline_median > 1e-12
        else 0.0
    )
    noise_floor_pct = max(float(minimum_noise_floor_pct), sampling_noise_pct)
    result["statistical"] = True
    result["noise_floor_pct"] = round(noise_floor_pct, 2)
    result["baseline_sigma"] = round(baseline_sigma, 6)
    result["candidate_sigma"] = round(candidate_sigma, 6)
    result["meaningful_regression"] = regression_pct > noise_floor_pct
    result["passed"] = not (result["budget_exceeded"] and result["meaningful_regression"])
    if not result["passed"]:
        result["reason"] = "Candidate regression exceeded both the configured budget and the measured benchmark noise floor."
    elif result["budget_exceeded"]:
        result["reason"] = "Point estimate exceeded the budget but remained within the measured benchmark noise floor."
    return result
