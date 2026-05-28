"""Guardrail pipeline. Runs in order: PII → sensitivity → returns messages."""

from typing import List, Tuple

from ..schema import DatasetMetadata
from . import pii_guardrail, sensitivity_guardrail


def apply_all(metadata: DatasetMetadata) -> Tuple[DatasetMetadata, List[str]]:
    """Apply all guardrails in sequence. Returns (metadata, all messages)."""
    all_messages: List[str] = []

    metadata.fields, pii_msgs = pii_guardrail.apply(metadata.fields)
    all_messages.extend(pii_msgs)

    metadata, sens_msgs = sensitivity_guardrail.apply(metadata)
    all_messages.extend(sens_msgs)

    return metadata, all_messages
