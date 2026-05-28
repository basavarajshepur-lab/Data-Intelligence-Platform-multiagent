"""Auto-dispatch extractor based on file extension."""

import os

from .base import DatasetProfile
from . import csv_extractor, json_extractor, sql_extractor


def extract(filepath: str) -> DatasetProfile:
    """Extract a DatasetProfile from any supported file type."""
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"Input file not found: {filepath}")

    ext = os.path.splitext(filepath)[1].lower()

    if ext == ".csv":
        return csv_extractor.extract(filepath)
    elif ext in (".json", ".jsonschema"):
        return json_extractor.extract(filepath)
    elif ext in (".sql", ".ddl"):
        return sql_extractor.extract(filepath)
    else:
        raise ValueError(
            f"Unsupported file type: {ext}. Supported: .csv, .json, .jsonschema, .sql, .ddl"
        )
