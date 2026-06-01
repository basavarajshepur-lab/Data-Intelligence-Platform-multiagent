"""SQL lineage tool implementations for LineageAgent.

Uses sqlglot for dialect-agnostic SQL parsing and column-level lineage extraction.
Supports: ansi, postgres, oracle, mysql, bigquery, tsql, spark, duckdb.
"""

from typing import Any


# ── Tool schemas (passed to Claude) ───────────────────────────────────────

EXTRACT_SQL_LINEAGE_SCHEMA: dict[str, Any] = {
    "name": "extract_sql_lineage",
    "description": (
        "Parse a SQL query and extract column-level lineage using static analysis. "
        "Returns source tables, output column names, derivation expressions, and "
        "whether each column is direct, derived (expression), or aggregated. "
        "Call this first with the full SQL before writing the lineage graph."
    ),
    "input_schema": {
        "type": "object",
        "required": ["sql"],
        "properties": {
            "sql": {
                "type": "string",
                "description": "The SQL SELECT statement or full DDL to analyse",
            },
            "dialect": {
                "type": "string",
                "description": "SQL dialect: ansi, postgres, oracle, mysql, bigquery, tsql, spark",
                "default": "ansi",
            },
        },
    },
}

WRITE_LINEAGE_GRAPH_SCHEMA: dict[str, Any] = {
    "name": "write_lineage_graph",
    "description": (
        "Write the final, enriched field-level lineage graph. "
        "Call this after analysing the SQL and the field glossary."
    ),
    "input_schema": {
        "type": "object",
        "required": ["dataset_name", "source_tables", "field_lineages"],
        "properties": {
            "dataset_name": {"type": "string"},
            "source_tables": {"type": "array", "items": {"type": "string"}},
            "bcbs_239_compliant": {"type": "boolean"},
            "bcbs_notes": {"type": "string"},
            "unresolved_fields": {"type": "array", "items": {"type": "string"}},
            "field_lineages": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["target_field", "source_fields", "lineage_type", "confidence"],
                    "properties": {
                        "target_field": {"type": "string"},
                        "source_fields": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "table": {"type": "string"},
                                    "column": {"type": "string"},
                                },
                            },
                        },
                        "transformation": {"type": "string"},
                        "lineage_type": {
                            "type": "string",
                            "enum": ["direct", "derived", "aggregated", "constant"],
                        },
                        "confidence": {
                            "type": "string",
                            "enum": ["HIGH", "MEDIUM", "LOW"],
                        },
                        "bcbs_note": {"type": "string"},
                    },
                },
            },
        },
    },
}


# ── Tool implementations ───────────────────────────────────────────────────

def extract_sql_lineage(sql: str, dialect: str = "ansi") -> dict:
    """
    Parse SQL and return column-level lineage using sqlglot.

    Returns a dict with:
      source_tables  — physical tables referenced
      ctes           — CTE names defined in the query
      output_fields  — list of {name, expression, source_columns, lineage_type}
      error          — set if parsing failed
    """
    import json

    try:
        import sqlglot
        import sqlglot.expressions as exp
    except ImportError:
        return {"error": "sqlglot not installed. Run: pip install sqlglot"}

    result: dict = {
        "dialect": dialect,
        "source_tables": [],
        "ctes": [],
        "output_fields": [],
        "error": None,
    }

    try:
        statement = sqlglot.parse_one(sql, dialect=dialect, error_level=sqlglot.ErrorLevel.RAISE)
    except Exception as exc:
        # Try without dialect as fallback
        try:
            statement = sqlglot.parse_one(sql, error_level=sqlglot.ErrorLevel.RAISE)
            result["dialect"] = "ansi (fallback)"
        except Exception:
            result["error"] = str(exc)
            return result

    # Source tables (exclude CTEs)
    cte_names = {cte.alias.upper() for cte in statement.find_all(exp.CTE)}
    result["ctes"] = list(cte_names)

    for table in statement.find_all(exp.Table):
        name = table.name
        if name and name.upper() not in cte_names and name not in result["source_tables"]:
            result["source_tables"].append(name)

    # Output columns
    selects = list(statement.selects) if hasattr(statement, "selects") else []
    if not selects:
        result["error"] = "No SELECT clause found — pass a SELECT statement for lineage analysis."
        return result

    for col_expr in selects:
        output_name = col_expr.alias_or_name or str(col_expr)
        sql_expr = col_expr.sql(dialect=dialect)

        # Determine lineage type
        has_agg = any(isinstance(n, exp.AggFunc) for n in col_expr.walk())
        is_literal = isinstance(col_expr.unalias(), (exp.Literal, exp.Boolean, exp.Null))

        if is_literal:
            lineage_type = "constant"
        elif has_agg:
            lineage_type = "aggregated"
        elif isinstance(col_expr.unalias(), exp.Column):
            lineage_type = "direct"
        else:
            lineage_type = "derived"

        # Extract referenced source columns
        source_columns = []
        for ref in col_expr.find_all(exp.Column):
            src = {
                "column": ref.name,
                "table": ref.table or "unknown",
            }
            if src not in source_columns:
                source_columns.append(src)

        result["output_fields"].append(
            {
                "name": output_name,
                "expression": sql_expr,
                "source_columns": source_columns,
                "lineage_type": lineage_type,
            }
        )

    return result
