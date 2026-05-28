"""Sensitivity Consistency Eval.

Validates internal consistency rules:
- PII fields must have sensitivity >= their PII type's minimum floor
- Non-PII fields marked RESTRICTED/SECRET should have a rationale in usage_guidance
- Dataset classification must be >= highest field classification
"""

from typing import List

from ..config import EVAL_THRESHOLDS, PII_SENSITIVITY_FLOORS
from ..schema import DatasetMetadata, QualityDimension, SensitivityLevel


def evaluate(metadata: DatasetMetadata) -> QualityDimension:
    issues: List[str] = []
    warnings: List[str] = []
    violations = 0
    total_checks = 0

    for field in metadata.fields:
        total_checks += 1

        # PII sensitivity floor check
        if field.is_pii and field.pii_type:
            floor_str = PII_SENSITIVITY_FLOORS.get(field.pii_type.value)
            if floor_str:
                floor = SensitivityLevel(floor_str)
                if field.sensitivity_level.rank < floor.rank:
                    issues.append(
                        f"Field '{field.name}': sensitivity {field.sensitivity_level.value} is "
                        f"below minimum {floor.value} for PII type {field.pii_type.value}"
                    )
                    violations += 1

        # High-sensitivity non-PII fields should explain why
        is_high = field.sensitivity_level.rank >= SensitivityLevel.RESTRICTED.rank
        if is_high and not field.is_pii:
            if not field.usage_guidance or len(field.usage_guidance) < 20:
                warnings.append(
                    f"Field '{field.name}' is {field.sensitivity_level.value} but not flagged as PII — "
                    f"add usage_guidance to explain the elevated classification"
                )

    # Dataset-level consistency
    total_checks += 1
    max_field_sensitivity = max(
        (f.sensitivity_level for f in metadata.fields),
        key=lambda s: s.rank,
        default=SensitivityLevel.PUBLIC,
    )
    if max_field_sensitivity.rank > metadata.classification.rank:
        issues.append(
            f"Dataset classification ({metadata.classification.value}) is lower than "
            f"highest field classification ({max_field_sensitivity.value})"
        )
        violations += 1

    score = max(0.0, (1 - violations / total_checks) * 100) if total_checks > 0 else 100.0
    threshold = EVAL_THRESHOLDS["sensitivity_consistency"]

    return QualityDimension(
        score=round(score, 1),
        passed=score >= threshold and len(issues) == 0,
        issues=issues,
        warnings=warnings,
    )
