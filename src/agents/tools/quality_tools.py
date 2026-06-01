"""Data quality tool implementations for DataQualityAgent.

Uses the DatasetProfile (already computed by the extractor) to provide
statistical context that Claude interprets into DAMA-DMBOK quality rules
and Great Expectations-compatible expectation suites.
"""

import json
from typing import Any

from ...extractors.base import DatasetProfile


# ── Tool schemas (passed to Claude) ───────────────────────────────────────

GET_FIELD_STATISTICS_SCHEMA: dict[str, Any] = {
    "name": "get_field_statistics",
    "description": (
        "Return profiling statistics for one or more fields: null rate, unique count, "
        "inferred type, value range, average length, and sample values. "
        "Call with all field names at the start to understand the full dataset profile."
    ),
    "input_schema": {
        "type": "object",
        "required": ["field_names"],
        "properties": {
            "field_names": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Field names to retrieve statistics for",
            }
        },
    },
}

WRITE_QUALITY_REPORT_SCHEMA: dict[str, Any] = {
    "name": "write_quality_report",
    "description": (
        "Write the final data quality report after analysing all fields. "
        "Include DAMA-DMBOK dimension scores, per-field results, "
        "Great Expectations-compatible expectations, and recommendations."
    ),
    "input_schema": {
        "type": "object",
        "required": ["dataset_name", "overall_score", "passed", "dimensions", "field_quality"],
        "properties": {
            "dataset_name": {"type": "string"},
            "overall_score": {"type": "number", "minimum": 0, "maximum": 100},
            "passed": {"type": "boolean"},
            "dimensions": {
                "type": "object",
                "description": "Six DAMA-DMBOK quality dimensions",
                "properties": {
                    dimension: {
                        "type": "object",
                        "properties": {
                            "score": {"type": "number"},
                            "issues": {"type": "array", "items": {"type": "string"}},
                            "notes": {"type": "string"},
                        },
                    }
                    for dimension in [
                        "completeness", "consistency", "accuracy",
                        "timeliness", "uniqueness", "validity",
                    ]
                },
            },
            "field_quality": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["field_name", "completeness_score", "issues"],
                    "properties": {
                        "field_name": {"type": "string"},
                        "completeness_score": {"type": "number"},
                        "issues": {"type": "array", "items": {"type": "string"}},
                        "warnings": {"type": "array", "items": {"type": "string"}},
                        "expectations": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "expectation_type": {"type": "string"},
                                    "kwargs": {"type": "object"},
                                },
                            },
                        },
                        "quality_notes": {"type": "string"},
                    },
                },
            },
            "critical_issues": {"type": "array", "items": {"type": "string"}},
            "recommendations": {"type": "array", "items": {"type": "string"}},
        },
    },
}


# ── Tool implementations ───────────────────────────────────────────────────

def get_field_statistics(profile: DatasetProfile, field_names: list[str]) -> dict:
    """
    Return profiling statistics for the requested fields.
    Returns all fields if field_names is empty.
    """
    target = set(field_names) if field_names else None
    stats = {}

    for fp in profile.fields:
        if target and fp.name not in target:
            continue

        field_stat: dict[str, Any] = {
            "name": fp.name,
            "inferred_type": fp.inferred_type,
            "null_count": fp.null_count,
            "total_count": fp.total_count,
            "null_rate_pct": round(fp.null_rate * 100, 1),
            "unique_count": fp.unique_count,
            "is_potential_pii": fp.is_potential_pii,
        }

        if fp.min_value is not None:
            field_stat["min_value"] = str(fp.min_value)
            field_stat["max_value"] = str(fp.max_value)

        if fp.avg_length is not None:
            field_stat["avg_length"] = round(fp.avg_length, 1)

        if not fp.is_potential_pii and fp.sample_values:
            field_stat["sample_values"] = fp.sample_values[:5]

        # Derived quality flags
        field_stat["flags"] = []
        if fp.null_rate > 0.1:
            field_stat["flags"].append(f"HIGH_NULLS ({fp.null_rate:.0%})")
        if fp.total_count > 0 and fp.unique_count == fp.total_count:
            field_stat["flags"].append("ALL_UNIQUE (potential key field)")
        if fp.total_count > 0 and fp.unique_count == 1:
            field_stat["flags"].append("SINGLE_VALUE (possible constant or flag)")

        stats[fp.name] = field_stat

    return stats
