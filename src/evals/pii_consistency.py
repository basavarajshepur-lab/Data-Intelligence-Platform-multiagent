"""PII Consistency Eval.

Cross-validates the AI's PII flags against:
1. Column name heuristics (name-based hints)
2. Pattern matching on any available sample values

A mismatch (AI says not-PII but heuristic says PII, or vice versa) is flagged.
The eval does NOT override the AI's decision — it only scores consistency
and surfaces conflicts for human review.
"""

import re
from typing import List

from ..config import EVAL_THRESHOLDS, PII_COLUMN_HINTS
from ..extractors.base import DatasetProfile
from ..schema import DatasetMetadata, QualityDimension


def _heuristic_is_pii(field_name: str) -> bool:
    name_lower = field_name.lower().replace(" ", "_")
    for hints in PII_COLUMN_HINTS.values():
        for hint in hints:
            if hint in name_lower:
                return True
    return False


def evaluate(metadata: DatasetMetadata, profile: DatasetProfile) -> QualityDimension:
    issues: List[str] = []
    warnings: List[str] = []

    profile_fields = {fp.name: fp for fp in profile.fields}
    consistent = 0
    total = 0

    for field in metadata.fields:
        total += 1
        heuristic_pii = _heuristic_is_pii(field.name)
        fp = profile_fields.get(field.name)
        extractor_pii = fp.is_potential_pii if fp else False

        # Both agree: consistent
        if field.is_pii == heuristic_pii:
            consistent += 1
        else:
            if heuristic_pii and not field.is_pii:
                # Heuristic suspects PII but AI didn't flag it
                warnings.append(
                    f"Field '{field.name}': heuristic suggests PII but AI did not flag — "
                    f"review manually"
                )
                consistent += 0.5  # Partial credit (AI may be right if name is ambiguous)
            elif field.is_pii and not heuristic_pii:
                # AI flagged PII but heuristic didn't catch it — could be AI being thorough
                consistent += 1  # Benefit of the doubt to the AI
                warnings.append(
                    f"Field '{field.name}': AI flagged as PII ({field.pii_type}) but name "
                    f"heuristic didn't detect it — confirm this is intentional"
                )

        # PII field missing pii_type
        if field.is_pii and field.pii_type is None:
            issues.append(f"PII field '{field.name}' is missing pii_type classification")

        # Extractor and AI disagree
        if fp and extractor_pii and not field.is_pii:
            warnings.append(
                f"Field '{field.name}': extractor detected potential PII "
                f"({fp.potential_pii_type}) but AI marked as not-PII"
            )

    score = (consistent / total * 100) if total > 0 else 100.0
    threshold = EVAL_THRESHOLDS["pii_detection"]

    return QualityDimension(
        score=round(score, 1),
        passed=score >= threshold and len(issues) == 0,
        issues=issues,
        warnings=warnings,
    )
