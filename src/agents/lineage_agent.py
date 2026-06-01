"""Data Lineage Agent.

Parses a SQL file and produces field-level lineage conforming to BCBS 239 Principle 2.

System prompt and configuration are loaded from agents/lineage_agent.md.

Agentic loop (max 8 turns):
  1. extract_sql_lineage  — sqlglot parses columns, source tables, expressions
  2. search_field_glossary — cross-reference parsed field names with catalogue
  3. write_lineage_graph  — Claude writes enriched lineage with BCBS 239 flags
"""

import json
from pathlib import Path
from typing import Any

from .base import BaseAgent
from .loader import load_agent
from .tools.lineage_tools import (
    EXTRACT_SQL_LINEAGE_SCHEMA,
    WRITE_LINEAGE_GRAPH_SCHEMA,
    extract_sql_lineage,
)
from ..config import AgentConfig
from ..schema import DatasetLineage, FieldLineage, LineageSource

try:
    from ..memory.memory_store import search_glossary
    _MEMORY_OK = True
except Exception:
    _MEMORY_OK = False

_MD_CONFIG, _SYSTEM_PROMPT = load_agent("lineage_agent")

_SEARCH_GLOSSARY_SCHEMA: dict[str, Any] = {
    "name": "search_field_glossary",
    "description": (
        "Look up how fields with the same names were classified in past metadata runs. "
        "Use to cross-reference parsed output column names against existing catalogue entries."
    ),
    "input_schema": {
        "type": "object",
        "required": ["field_names"],
        "properties": {
            "field_names": {
                "type": "array",
                "items": {"type": "string"},
            }
        },
    },
}


class LineageAgent(BaseAgent):
    """Maps field-level data lineage from SQL files (BCBS 239 Principle 2)."""

    def __init__(self, config: AgentConfig | None = None):
        super().__init__(config)
        self._lineage_raw: dict | None = None

        tools = [EXTRACT_SQL_LINEAGE_SCHEMA, WRITE_LINEAGE_GRAPH_SCHEMA]
        if _MEMORY_OK:
            tools.insert(1, _SEARCH_GLOSSARY_SCHEMA)
        self._tools = tools

    @property
    def system_prompt(self) -> str:
        return _SYSTEM_PROMPT

    @property
    def tools(self) -> list[dict]:
        return self._tools

    def handle_tool_call(self, name: str, inputs: dict) -> str:
        if name == "extract_sql_lineage":
            result = extract_sql_lineage(
                sql=inputs["sql"],
                dialect=inputs.get("dialect", "ansi"),
            )
            return json.dumps(result)

        if name == "search_field_glossary" and _MEMORY_OK:
            results = search_glossary(inputs.get("field_names", []))
            return json.dumps(results) if results else "No matching fields in glossary."

        if name == "write_lineage_graph":
            self._lineage_raw = inputs
            return "Lineage graph accepted."

        return "Tool not available."

    def run(self, sql_path: str) -> DatasetLineage:
        """
        Parse a SQL file and return a DatasetLineage.

        Parameters
        ----------
        sql_path : str
            Path to a .sql file containing a SELECT query.
        """
        sql_path = str(sql_path)
        sql_text = Path(sql_path).read_text(encoding="utf-8")
        dataset_name = Path(sql_path).stem

        self._lineage_raw = None

        user_msg = f"""Analyse the SQL below and produce a complete field-level lineage graph.

Dataset name: {dataset_name}

SQL:
```sql
{sql_text}
```

Steps:
1. Call extract_sql_lineage with the SQL above to get the parsed column structure.
2. Call search_field_glossary with all output column names to check the enterprise catalogue.
3. Call write_lineage_graph with the complete, enriched lineage including BCBS 239 compliance flags."""

        messages = [{"role": "user", "content": user_msg}]
        max_turns = int(_MD_CONFIG.get("max_turns", 8))

        for _ in range(max_turns):
            response = self.client.messages.create(
                model=self.config.model,
                max_tokens=self.config.max_tokens,
                system=[
                    {
                        "type": "text",
                        "text": self.system_prompt,
                        "cache_control": {"type": "ephemeral"},
                    }
                ],
                messages=messages,
                tools=self.tools,
                tool_choice={"type": "any"},
            )

            tool_blocks = [b for b in response.content if b.type == "tool_use"]
            if not tool_blocks:
                break

            messages.append({"role": "assistant", "content": response.content})
            tool_results = []
            for block in tool_blocks:
                result = self.handle_tool_call(block.name, block.input)
                tool_results.append(
                    {"type": "tool_result", "tool_use_id": block.id, "content": result}
                )
            messages.append({"role": "user", "content": tool_results})

            if self._lineage_raw is not None:
                break

        if self._lineage_raw is None:
            raise RuntimeError("LineageAgent did not produce a lineage graph.")

        return self._parse_lineage(self._lineage_raw, dataset_name, sql_text)

    def _parse_lineage(self, raw: dict, dataset_name: str, sql_text: str) -> DatasetLineage:
        field_lineages = []
        for fl in raw.get("field_lineages", []):
            sources = [
                LineageSource(
                    table=s.get("table", "unknown"),
                    column=s.get("column", "unknown"),
                )
                for s in fl.get("source_fields", [])
            ]
            field_lineages.append(
                FieldLineage(
                    target_field=fl["target_field"],
                    source_fields=sources,
                    transformation=fl.get("transformation"),
                    lineage_type=fl.get("lineage_type", "direct"),
                    confidence=fl.get("confidence", "MEDIUM"),
                    bcbs_note=fl.get("bcbs_note"),
                )
            )

        return DatasetLineage(
            dataset_name=raw.get("dataset_name", dataset_name),
            source_sql=sql_text,
            source_tables=raw.get("source_tables", []),
            field_lineages=field_lineages,
            unresolved_fields=raw.get("unresolved_fields", []),
            bcbs_239_compliant=raw.get("bcbs_239_compliant", False),
            bcbs_notes=raw.get("bcbs_notes"),
        )
