"""Data Lineage Agent — maps field-level data lineage from SQL and pipeline definitions.

Status: STUB — not yet implemented.

Planned capabilities
--------------------
- Parse SQL SELECT statements to trace column-level lineage
- Map source → transformation → target across pipeline stages
- Output lineage graphs compatible with OpenLineage / Marquez
- Populate the data_lineage field on existing DatasetMetadata entries

To implement:
1. Define input (SQL file / dbt manifest / Spark plan)
2. Define output schema (LineageGraph Pydantic model)
3. Add tools: parse_sql_lineage, resolve_table_alias, write_lineage_graph
4. Implement handle_tool_call() and run()
"""

from .base import BaseAgent
from ..config import AgentConfig


class LineageAgent(BaseAgent):
    """Maps field-level data lineage across SQL queries and pipeline stages."""

    @property
    def system_prompt(self) -> str:
        return (
            "You are a data lineage specialist. "
            "Trace the origin of every field in a SQL query or pipeline definition, "
            "following BCBS 239 Principle 2 (data lineage) and DAMA-DMBOK guidelines."
        )

    @property
    def tools(self) -> list[dict]:
        return []  # add tools here when implementing

    def handle_tool_call(self, name: str, inputs: dict) -> str:
        return "Not implemented."

    def run(self, *args, **kwargs):
        raise NotImplementedError("LineageAgent is not yet implemented.")
