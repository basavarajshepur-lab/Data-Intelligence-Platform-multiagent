"""Data Quality Agent — runs automated profiling and quality checks on datasets.

Status: STUB — not yet implemented.

Planned capabilities
--------------------
- Profile a dataset and produce a DataQualityReport
- Detect nulls, duplicates, outliers, referential integrity violations
- Generate Great Expectations-compatible expectation suites
- Score against DAMA-DMBOK data quality dimensions:
    completeness, consistency, accuracy, timeliness, uniqueness, validity
- Write quality_notes back to existing DatasetMetadata entries

To implement:
1. Define input (DatasetProfile or raw file path)
2. Define output schema (DataQualityReport Pydantic model)
3. Add tools: profile_dataset, check_referential_integrity, generate_expectations
4. Implement handle_tool_call() and run()
"""

from .base import BaseAgent
from ..config import AgentConfig


class DataQualityAgent(BaseAgent):
    """Profiles datasets and generates quality reports aligned with DAMA-DMBOK dimensions."""

    @property
    def system_prompt(self) -> str:
        return (
            "You are a data quality engineer specialising in financial services data. "
            "Apply DAMA-DMBOK quality dimensions and BCBS 239 Principles 3–6 "
            "(accuracy, completeness, timeliness, adaptability) to profile datasets "
            "and generate actionable quality rules and expectation suites."
        )

    @property
    def tools(self) -> list[dict]:
        return []  # add tools here when implementing

    def handle_tool_call(self, name: str, inputs: dict) -> str:
        return "Not implemented."

    def run(self, *args, **kwargs):
        raise NotImplementedError("DataQualityAgent is not yet implemented.")
