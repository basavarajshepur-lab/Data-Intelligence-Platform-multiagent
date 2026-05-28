"""Eval runner. Orchestrates all five evaluation dimensions and computes overall score."""

from ..config import EVAL_THRESHOLDS
from ..extractors.base import DatasetProfile
from ..schema import DatasetMetadata, QualityScore
from . import completeness, pii_consistency, type_validator, banking_standards, sensitivity_consistency

# Dimension weights (must sum to 1.0)
WEIGHTS = {
    "completeness": 0.30,
    "pii_detection": 0.25,
    "type_consistency": 0.20,
    "banking_standards": 0.15,
    "sensitivity_consistency": 0.10,
}


def run(metadata: DatasetMetadata, profile: DatasetProfile, guardrail_messages: list) -> QualityScore:
    """Run all evals and return a QualityScore."""

    comp = completeness.evaluate(metadata)
    pii = pii_consistency.evaluate(metadata, profile)
    types = type_validator.evaluate(metadata, profile)
    banking = banking_standards.evaluate(metadata)
    sensitivity = sensitivity_consistency.evaluate(metadata)

    overall = (
        comp.score * WEIGHTS["completeness"]
        + pii.score * WEIGHTS["pii_detection"]
        + types.score * WEIGHTS["type_consistency"]
        + banking.score * WEIGHTS["banking_standards"]
        + sensitivity.score * WEIGHTS["sensitivity_consistency"]
    )

    passed = (
        overall >= EVAL_THRESHOLDS["overall"]
        and comp.passed
        and pii.passed
        and sensitivity.passed  # Sensitivity is non-negotiable
    )

    return QualityScore(
        completeness=comp,
        pii_detection=pii,
        type_consistency=types,
        banking_standards=banking,
        sensitivity_consistency=sensitivity,
        overall_score=round(overall, 1),
        passed=passed,
        guardrails_applied=guardrail_messages,
    )
