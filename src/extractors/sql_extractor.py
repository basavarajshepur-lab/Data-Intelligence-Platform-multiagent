"""SQL DDL profiler.

Parses CREATE TABLE statements and builds a DatasetProfile.
Handles common SQL dialects (PostgreSQL, Oracle, SQL Server, BigQuery).
"""

import os
import re
from typing import List, Optional, Tuple

from ..config import PII_COLUMN_HINTS
from .base import DatasetProfile, FieldProfile


# Map SQL types to canonical inferred types
SQL_TYPE_MAP = {
    r"varchar|nvarchar|char|nchar|text|clob|string": "string",
    r"int|integer|bigint|smallint|tinyint|number\(\d+\)$": "integer",
    r"decimal|numeric|float|double|real|money|number": "decimal",
    r"bool|boolean|bit": "boolean",
    r"date": "date",
    r"timestamp|datetime|datetime2": "datetime",
    r"uuid|uniqueidentifier|guid": "uuid",
    r"json|jsonb": "json",
    r"blob|bytea|binary|varbinary|raw": "binary",
}


def _normalize_type(sql_type: str) -> str:
    t = sql_type.strip().lower().split("(")[0]
    for pattern, canonical in SQL_TYPE_MAP.items():
        if re.match(pattern, t):
            return canonical
    return "string"


def _detect_pii_hint(name: str) -> Tuple[bool, Optional[str]]:
    name_lower = name.lower().replace(" ", "_")
    for pii_type, hints in PII_COLUMN_HINTS.items():
        for hint in hints:
            if hint in name_lower or name_lower in hint:
                return True, pii_type
    return False, None


def _parse_create_table(ddl: str) -> List[Tuple[str, str, bool, str]]:
    """
    Returns list of (col_name, sql_type, is_nullable, constraints_raw).
    Handles inline NOT NULL, PRIMARY KEY, DEFAULT, REFERENCES.
    """
    # Strip comments
    ddl = re.sub(r"--.*$", "", ddl, flags=re.MULTILINE)
    ddl = re.sub(r"/\*.*?\*/", "", ddl, flags=re.DOTALL)

    # Extract body between first ( and last )
    body_match = re.search(r"\((.+)\)", ddl, re.DOTALL)
    if not body_match:
        return []

    body = body_match.group(1)
    results = []

    for line in body.split(","):
        line = line.strip()
        if not line:
            continue
        # Skip table-level constraints
        if re.match(r"(PRIMARY KEY|UNIQUE|INDEX|FOREIGN KEY|CHECK|CONSTRAINT)\b", line, re.IGNORECASE):
            continue

        # Match column definition: name type [constraints...]
        m = re.match(r"[`\"]?(\w+)[`\"]?\s+(\w+(?:\([^)]*\))?)(.*)", line, re.IGNORECASE)
        if not m:
            continue

        col_name = m.group(1)
        sql_type = m.group(2)
        rest = m.group(3).upper()
        is_nullable = "NOT NULL" not in rest and "PRIMARY KEY" not in rest

        results.append((col_name, sql_type, is_nullable, rest))

    return results


def extract(filepath: str) -> DatasetProfile:
    """Parse a SQL DDL file and return a DatasetProfile."""
    with open(filepath, encoding="utf-8") as f:
        ddl = f.read()

    # Extract table name
    table_match = re.search(r"CREATE\s+(?:TABLE|OR\s+REPLACE\s+TABLE)\s+(?:\w+\.)?[`\"]?(\w+)[`\"]?", ddl, re.IGNORECASE)
    dataset_name = table_match.group(1) if table_match else os.path.splitext(os.path.basename(filepath))[0]

    columns = _parse_create_table(ddl)
    fields: List[FieldProfile] = []

    for col_name, sql_type, is_nullable, constraints_raw in columns:
        inferred = _normalize_type(sql_type)
        is_pii, pii_type = _detect_pii_hint(col_name)

        null_count = 1 if is_nullable else 0

        fields.append(
            FieldProfile(
                name=col_name,
                inferred_type=inferred,
                sample_values=[],
                null_count=null_count,
                total_count=1,
                is_potential_pii=is_pii,
                potential_pii_type=pii_type,
                extra={
                    "sql_type": sql_type,
                    "is_nullable": is_nullable,
                    "constraints_raw": constraints_raw.strip(),
                },
            )
        )

    return DatasetProfile(
        source_file=filepath,
        source_type="sql_ddl",
        dataset_name=dataset_name,
        fields=fields,
        raw_schema=ddl[:4000],
    )
