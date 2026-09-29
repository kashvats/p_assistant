"""What counts as knowledge: statuses, evidence levels and the rules that assign them.

Statuses and levels are computed from recorded verifications, never from how
confident a model sounds. An LLM judgement can raise nothing above HYPOTHESIS; a
significant statistical test gives STATISTICALLY_SUPPORTED, not VERIFIED; VERIFIED
needs a reproducible experiment, a successful prediction on data the hypothesis
was not fitted to, or several independent primary sources with no contradiction;
FORMALLY_PROVEN needs a symbolic proof. A valid counterexample contradicts.
"""
from __future__ import annotations

PROJECT_STATUSES = ("RESEARCHING", "HYPOTHESIS", "PARTIALLY_SUPPORTED", "CONTRADICTED", "VERIFIED", "PROVEN",
                    "READY_TO_BUILD", "BUILDING", "IMPLEMENTED")
LEVELS = ("OBSERVED", "DERIVED", "CORRELATED", "STATISTICALLY_SUPPORTED", "PREDICTIVE", "HYPOTHESIS",
          "CAUSALLY_INFERRED", "VERIFIED", "FORMALLY_PROVEN", "CONTRADICTED")
# Status of hypotheses, claims and symbol interpretations.
CLAIM_STATUSES = ("OPEN", "UNRESOLVED", "PARTIALLY_SUPPORTED", "SUPPORTED", "CONTRADICTED", "VERIFIED", "PROVEN")

# Verification methods and what a pass is allowed to establish.
METHODS = {
    "formal_proof": "FORMALLY_PROVEN",          # symbolic proof checked by a CAS
    "reproducible_experiment": "VERIFIED",      # repeated runs, same result, recorded environment
    "prediction_holdout": "PREDICTIVE",         # prediction held on data it was not fitted to
    "independent_sources": "VERIFIED",          # >= MIN_INDEPENDENT_SOURCES primary sources agree, none contradict
    "statistical_test": "STATISTICALLY_SUPPORTED",
    "correlation_test": "CORRELATED",
    "counterexample": "CONTRADICTED",           # only ever fails
    "llm_judgement": "HYPOTHESIS",              # never evidence of truth
}
STRONG_PASS = {"reproducible_experiment", "independent_sources", "prediction_holdout", "formal_proof"}
STRONG_FAIL = {"reproducible_experiment", "formal_proof", "counterexample", "prediction_holdout"}
MIN_INDEPENDENT_SOURCES = 3
ALPHA = 0.01


def assess(verifications: list[dict], supporting: int = 0, contradicting: int = 0) -> tuple[str, str, str]:
    """(status, level, reason) for a hypothesis/claim from its verification records.

    Each verification is {"method", "passed", "stats"?}. ``supporting``/``contradicting``
    count evidence links that are not tests (sources saying so).
    """
    passed = [v for v in verifications if v.get("passed")]
    failed = [v for v in verifications if v.get("passed") is False]
    pass_methods = {v["method"] for v in passed}
    fail_methods = {v["method"] for v in failed}

    if "formal_proof" in pass_methods:
        return "PROVEN", "FORMALLY_PROVEN", "A symbolic proof was checked."
    strong_pass = pass_methods & STRONG_PASS
    strong_fail = fail_methods & STRONG_FAIL
    if strong_fail and not strong_pass:
        return "CONTRADICTED", "CONTRADICTED", f"Failed {', '.join(sorted(strong_fail))}."
    if strong_fail and strong_pass:
        return ("PARTIALLY_SUPPORTED", METHODS[_best(strong_pass)],
                f"Passed {', '.join(sorted(strong_pass))} but failed {', '.join(sorted(strong_fail))}: holds only in part of the scope.")
    if "reproducible_experiment" in pass_methods or "independent_sources" in pass_methods:
        if contradicting:
            return "PARTIALLY_SUPPORTED", "STATISTICALLY_SUPPORTED", f"Verified, but {contradicting} contradicting evidence item(s) remain."
        return "VERIFIED", "VERIFIED", f"Passed {', '.join(sorted(pass_methods & STRONG_PASS))}."
    if "prediction_holdout" in pass_methods:
        return "SUPPORTED", "PREDICTIVE", "Predictions held on unseen data."
    if "statistical_test" in pass_methods:
        return "SUPPORTED", "STATISTICALLY_SUPPORTED", "Statistically significant; not yet tested on new data or reproduced."
    if "correlation_test" in pass_methods:
        return "PARTIALLY_SUPPORTED", "CORRELATED", "Correlated; correlation does not establish cause."
    if failed:
        return "PARTIALLY_SUPPORTED" if supporting else "CONTRADICTED", "HYPOTHESIS", f"Weak tests failed: {', '.join(sorted(fail_methods))}."
    if supporting and contradicting:
        return "PARTIALLY_SUPPORTED", "OBSERVED", f"{supporting} source(s) support it and {contradicting} contradict it."
    if supporting:
        return "PARTIALLY_SUPPORTED", "OBSERVED", f"Stated by {supporting} source(s); not independently tested."
    if contradicting:
        return "CONTRADICTED", "OBSERVED", f"Contradicted by {contradicting} source(s)."
    return "OPEN", "HYPOTHESIS", "Not tested yet."


def _best(methods: set[str]) -> str:
    order = ["formal_proof", "reproducible_experiment", "independent_sources", "prediction_holdout"]
    return next(m for m in order if m in methods)


def project_status(current: str, kind: str, hypotheses: list[dict]) -> str:
    """Roll hypothesis results up to the project. BUILDING/IMPLEMENTED are owned by the builder."""
    if current in ("BUILDING", "IMPLEMENTED"):
        return current
    core = [h for h in hypotheses if (h.get("data") or {}).get("core")] or hypotheses
    statuses = {h.get("status") for h in core}
    software = kind == "software"
    if "PROVEN" in statuses:
        return "READY_TO_BUILD" if software else "PROVEN"
    if "VERIFIED" in statuses:
        return "READY_TO_BUILD" if software else "VERIFIED"
    if statuses & {"SUPPORTED", "PARTIALLY_SUPPORTED"}:
        return "PARTIALLY_SUPPORTED"
    if core and statuses == {"CONTRADICTED"}:
        return "CONTRADICTED"
    if core:
        return "HYPOTHESIS"
    return "RESEARCHING"
