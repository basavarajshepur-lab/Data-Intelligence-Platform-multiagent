"""Sensitivity Guardrail.

Ensures dataset-level classification is at least as high as the highest
field-level sensitivity. A dataset cannot be "internal" if it contains
a "restricted" field.
"""

from typing import List, Tuple

from ..schema import DatasetMetadata, FieldMetadata, SensitivityLevel


def apply(metadata: DatasetMetadata) -> Tuple[DatasetMetadata, List[str]]:
    """
    Raise dataset classification if any field exceeds it.
    Returns (metadata, guardrail messages).
    """
    messages: List[str] = []

    max_field_level = max(
        (f.sensitivity_level for f in metadata.fields),
        key=lambda s: s.rank,
        default=SensitivityLevel.PUBLIC,
    )

    if max_field_level.rank > metadata.classification.rank:
        original = metadata.classification.value
        metadata.classification = max_field_level
        msg = (
            f"UPGRADED dataset classification: {original} -> {max_field_level.value} "
            f"(sensitivity guardrail - dataset cannot be lower than its most sensitive field)"
        )
        messages.append(msg)

    return metadata, messages
