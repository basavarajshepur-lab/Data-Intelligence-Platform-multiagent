"""Type Consistency Eval.

Validates that the AI-declared data_type is consistent with what the extractor
inferred from the actual data. Mismatches are scored and surfaced as warnings.
"""

from typing import Dict, List, Set

from ..config import EVAL_THRESHOLDS
from ..extractors.base import DatasetProfile
from ..schema import DatasetMetadata, DataType, QualityDimension

# Compatible type groups — types within a group are considered consistent
TYPE_COMPATIBILITY: Dict[str, Set[str]] = {
    "string": {"string", "uuid", "json"},
    "integer": {"integer", "decimal"},
    "decimal": {"decimal", "integer", "currency_amount"},
    "boolean": {"boolean"},
    "date": {"date", "datetime", "timestamp"},
    "datetime": {"datetime", "date", "timestamp"},
    "timestamp": {"timestamp", "datetime"},
    "uuid": {"uuid", "string"},
    "json": {"json", "string", "array"},
    "array": {"array", "json"},
    "binary": {"binary"},
    "currency_amount": {"currency_amount", "decimal"},
}


def _types_compatible(declared: str, inferred: str) -> bool:
    compatible = TYPE_COMPATIBILITY.get(declared, {declared})
    return inferred in compatible


def evaluate(metadata: DatasetMetadata, profile: DatasetProfile) -> QualityDimension:
    issues: List[str] = []
    warnings: List[str] = []

    profile_fields = {fp.name: fp for fp in profile.fields}
    consistent = 0
    total = 0

    for field in metadata.fields:
        fp = profile_fields.get(field.name)
        if fp is None:
            # Field only in metadata, not in profile (e.g., derived field) — skip
            consistent += 1
            total += 1
            continue

        total += 1
        declared = field.data_type.value
        inferred = fp.inferred_type

        if _types_compatible(declared, inferred):
            consistent += 1
        else:
            # Check if it's a minor mismatch (string vs uuid) or major (integer vs boolean)
            major_mismatch = not (
                {"string", "uuid", "json"} & {declared, inferred}
                or {"integer", "decimal"} & {declared} and {"integer", "decimal"} & {inferred}
                or {"date", "datetime", "timestamp"} & {declared, inferred}
            )

            if major_mismatch:
                issues.append(
                    f"Type mismatch for '{field.name}': declared={declared}, "
                    f"inferred={inferred} — significant inconsistency, review required"
                )
                consistent += 0
            else:
                warnings.append(
                    f"Minor type mismatch for '{field.name}': declared={declared}, "
                    f"inferred={inferred} — acceptable but worth verifying"
                )
                consistent += 0.7

    score = (consistent / total * 100) if total > 0 else 100.0
    threshold = EVAL_THRESHOLDS["type_consistency"]

    return QualityDimension(
        score=round(score, 1),
        passed=score >= threshold and len(issues) == 0,
        issues=issues,
        warnings=warnings,
    )
