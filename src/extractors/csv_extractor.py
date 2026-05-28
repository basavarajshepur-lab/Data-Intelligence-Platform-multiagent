"""CSV dataset profiler.

Extracts field statistics from a CSV file without logging PII values.
Suspected PII columns are masked before any values leave this module.
"""

import os
import re
from typing import List

import pandas as pd

from ..config import PII_COLUMN_HINTS
from .base import DatasetProfile, FieldProfile


def _detect_pii_hint(col: str) -> tuple[bool, str | None]:
    """Check column name against known PII name patterns."""
    col_lower = col.lower().replace(" ", "_")
    for pii_type, hints in PII_COLUMN_HINTS.items():
        for hint in hints:
            if hint in col_lower or col_lower in hint:
                return True, pii_type
    return False, None


def _safe_samples(series: pd.Series, is_pii: bool, n: int = 5) -> List[str]:
    """Return up to n non-null sample values, masked if PII suspected."""
    non_null = series.dropna()
    if len(non_null) == 0:
        return []
    samples = non_null.head(n).astype(str).tolist()
    return ["[MASKED]"] * len(samples) if is_pii else samples


def extract(filepath: str) -> DatasetProfile:
    """Profile a CSV file and return a DatasetProfile."""
    df = pd.read_csv(filepath, nrows=10_000, low_memory=False)
    dataset_name = os.path.splitext(os.path.basename(filepath))[0]
    fields: List[FieldProfile] = []

    for col in df.columns:
        series = df[col]
        is_pii, pii_type = _detect_pii_hint(col)

        inferred = str(series.dtype)
        # Refine type label
        if pd.api.types.is_integer_dtype(series):
            inferred = "integer"
        elif pd.api.types.is_float_dtype(series):
            inferred = "decimal"
        elif pd.api.types.is_bool_dtype(series):
            inferred = "boolean"
        elif pd.api.types.is_datetime64_any_dtype(series):
            inferred = "datetime"
        else:
            # Try to detect date strings
            sample_str = series.dropna().head(3).astype(str).tolist()
            if any(re.match(r"\d{4}-\d{2}-\d{2}", s) for s in sample_str):
                inferred = "date"
            elif any(re.match(r"[0-9a-f]{8}-[0-9a-f]{4}-", s.lower()) for s in sample_str):
                inferred = "uuid"
            else:
                inferred = "string"

        min_val = max_val = avg_len = None
        if not is_pii:
            if pd.api.types.is_numeric_dtype(series):
                min_val = float(series.min()) if series.notna().any() else None
                max_val = float(series.max()) if series.notna().any() else None
            elif inferred == "string":
                lengths = series.dropna().astype(str).str.len()
                if len(lengths) > 0:
                    avg_len = float(lengths.mean())

        fields.append(
            FieldProfile(
                name=col,
                inferred_type=inferred,
                sample_values=_safe_samples(series, is_pii),
                null_count=int(series.isna().sum()),
                total_count=len(series),
                unique_count=int(series.nunique()),
                min_value=min_val,
                max_value=max_val,
                avg_length=avg_len,
                is_potential_pii=is_pii,
                potential_pii_type=pii_type,
            )
        )

    return DatasetProfile(
        source_file=filepath,
        source_type="csv",
        dataset_name=dataset_name,
        fields=fields,
        row_count=len(df),
        file_size_bytes=os.path.getsize(filepath),
    )
