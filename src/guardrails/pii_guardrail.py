"""PII Guardrail.

Ensures PII fields are never below their minimum required sensitivity level.
Any upgrade is logged so the eval report can surface it.

This runs BEFORE evals so that eval scores reflect the guardrailed output.
"""

from typing import List, Tuple

from ..config import PII_SENSITIVITY_FLOORS
from ..schema import FieldMetadata, SensitivityLevel


def _sensitivity_rank(level: SensitivityLevel) -> int:
    return level.rank


def apply(fields: List[FieldMetadata]) -> Tuple[List[FieldMetadata], List[str]]:
    """
    Returns (corrected fields, list of guardrail messages).
    Mutates sensitivity_level and sets guardrail_applied on affected fields.
    """
    messages: List[str] = []

    for field in fields:
        if not field.is_pii or field.pii_type is None:
            continue

        floor_str = PII_SENSITIVITY_FLOORS.get(field.pii_type.value)
        if not floor_str:
            continue

        floor = SensitivityLevel(floor_str)
        if _sensitivity_rank(field.sensitivity_level) < _sensitivity_rank(floor):
            original = field.sensitivity_level.value
            field.sensitivity_level = floor
            msg = (
                f"UPGRADED '{field.name}': {original} -> {floor.value} "
                f"(PII guardrail - {field.pii_type.value} minimum is {floor.value})"
            )
            field.guardrail_applied = msg
            messages.append(msg)

    return fields, messages
