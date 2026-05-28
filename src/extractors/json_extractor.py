"""JSON Schema profiler.

Parses a JSON Schema (draft-07 / draft-2020-12) and builds a DatasetProfile.
No sample data is needed - type and constraint information comes from the schema.
"""

import json
import os
from typing import Any, Dict, List, Optional

from ..config import PII_COLUMN_HINTS
from .base import DatasetProfile, FieldProfile


def _detect_pii_hint(name: str) -> tuple[bool, Optional[str]]:
    name_lower = name.lower().replace(" ", "_")
    for pii_type, hints in PII_COLUMN_HINTS.items():
        for hint in hints:
            if hint in name_lower or name_lower in hint:
                return True, pii_type
    return False, None


def _json_type_to_inferred(prop: Dict[str, Any]) -> str:
    t = prop.get("type", "string")
    fmt = prop.get("format", "")
    if isinstance(t, list):
        t = [x for x in t if x != "null"][0] if t else "string"
    if fmt in ("date-time", "datetime"):
        return "datetime"
    if fmt == "date":
        return "date"
    if fmt == "uuid":
        return "uuid"
    mapping = {
        "string": "string",
        "integer": "integer",
        "number": "decimal",
        "boolean": "boolean",
        "array": "array",
        "object": "json",
    }
    return mapping.get(t, "string")


def _flatten_properties(
    schema: Dict[str, Any],
    prefix: str = "",
    required_set: Optional[set] = None,
) -> List[FieldProfile]:
    """Recursively flatten a JSON Schema properties dict into FieldProfiles."""
    profiles: List[FieldProfile] = []
    properties = schema.get("properties", {})
    required_set = required_set or set(schema.get("required", []))

    for name, prop in properties.items():
        full_name = f"{prefix}.{name}" if prefix else name
        inferred = _json_type_to_inferred(prop)
        is_pii, pii_type = _detect_pii_hint(name)

        # Extract constraint hints
        min_val = prop.get("minimum") or prop.get("exclusiveMinimum")
        max_val = prop.get("maximum") or prop.get("exclusiveMaximum")
        min_len = prop.get("minLength")
        max_len = prop.get("maxLength")
        pattern = prop.get("pattern")
        enum = prop.get("enum")

        is_nullable = "null" in prop.get("type", []) if isinstance(prop.get("type"), list) else True
        is_required = name in required_set

        profiles.append(
            FieldProfile(
                name=full_name,
                inferred_type=inferred,
                sample_values=["[MASKED]"] if is_pii else (enum[:3] if enum else []),
                null_count=0 if is_required else 1,
                total_count=1,
                unique_count=None,
                min_value=min_val,
                max_value=max_val,
                is_potential_pii=is_pii,
                potential_pii_type=pii_type,
                extra={
                    "json_schema_type": prop.get("type"),
                    "format": prop.get("format"),
                    "pattern": pattern,
                    "min_length": min_len,
                    "max_length": max_len,
                    "enum": enum,
                    "description": prop.get("description"),
                    "is_required": is_required,
                },
            )
        )

        # Recurse into nested objects
        if prop.get("type") == "object" and "properties" in prop:
            profiles.extend(
                _flatten_properties(prop, prefix=full_name, required_set=set(prop.get("required", [])))
            )

    return profiles


def extract(filepath: str) -> DatasetProfile:
    """Parse a JSON Schema file and return a DatasetProfile."""
    with open(filepath, encoding="utf-8") as f:
        schema = json.load(f)

    dataset_name = (
        schema.get("title")
        or os.path.splitext(os.path.basename(filepath))[0]
    )

    fields = _flatten_properties(schema)

    return DatasetProfile(
        source_file=filepath,
        source_type="json_schema",
        dataset_name=dataset_name,
        fields=fields,
        raw_schema=json.dumps(schema, indent=2)[:4000],  # Truncate for prompt safety
    )
