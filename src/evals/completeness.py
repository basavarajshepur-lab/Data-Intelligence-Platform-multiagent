"""Completeness Eval.

Scores how completely each field's metadata has been populated.
Weights reflect importance to a data consumer: description and business_context
matter most; constraints and lineage are secondary but still counted.
"""

from typing import List

from ..config import EVAL_THRESHOLDS, FIELD_COMPLETENESS_WEIGHTS
from ..schema import DatasetMetadata, FieldMetadata, QualityDimension


def _field_score(field: FieldMetadata) -> float:
    """Return completeness score 0-100 for a single field."""
    score = 0.0
    weights = FIELD_COMPLETENESS_WEIGHTS

    if field.description and len(field.description.strip()) > 10:
        score += weights["description"] * 100

    if field.business_context and len(field.business_context.strip()) > 10:
        score += weights["business_context"] * 100

    if field.data_type:
        score += weights["data_type"] * 100

    if field.sensitivity_level:
        score += weights["sensitivity_level"] * 100

    if field.usage_guidance and len(field.usage_guidance.strip()) > 10:
        score += weights["usage_guidance"] * 100

    # Constraints: partial credit if at least nullable is set
    if field.constraints is not None:
        score += weights["constraints"] * 100

    if field.data_lineage and len(field.data_lineage.strip()) > 5:
        score += weights["data_lineage"] * 100

    return min(score, 100.0)


def evaluate(metadata: DatasetMetadata) -> QualityDimension:
    if not metadata.fields:
        return QualityDimension(
            score=0.0,
            passed=False,
            issues=["No fields found in metadata"],
        )

    field_scores = [_field_score(f) for f in metadata.fields]
    avg_score = sum(field_scores) / len(field_scores)

    issues: List[str] = []
    warnings: List[str] = []

    # Flag fields with very low completeness
    for field, fs in zip(metadata.fields, field_scores):
        if fs < 40:
            issues.append(f"Field '{field.name}' completeness critically low ({fs:.0f}/100)")
        elif fs < 70:
            warnings.append(f"Field '{field.name}' missing some metadata (score: {fs:.0f}/100)")

    # Dataset-level checks
    if not metadata.description or len(metadata.description) < 20:
        issues.append("Dataset description is missing or too brief")
    if not metadata.business_context or len(metadata.business_context) < 20:
        warnings.append("Dataset business_context is missing or too brief")
    if not metadata.usage_guidance or len(metadata.usage_guidance) < 20:
        warnings.append("Dataset usage_guidance is missing or too brief")

    threshold = EVAL_THRESHOLDS["completeness"]
    return QualityDimension(
        score=round(avg_score, 1),
        passed=avg_score >= threshold,
        issues=issues,
        warnings=warnings,
    )
