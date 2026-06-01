"""Data Quality Agent.

Profiles a dataset and produces a DAMA-DMBOK quality report with
Great Expectations-compatible expectation rules.

System prompt and configuration are loaded from agents/quality_agent.md.

Agentic loop (max 8 turns):
  1. get_field_statistics — returns null rates, unique counts, value ranges
  2. write_quality_report — Claude writes DAMA dimension scores + GE expectations
"""

import json
from pathlib import Path
from typing import Any

from .base import BaseAgent
from .loader import load_agent
from .tools.quality_tools import (
    GET_FIELD_STATISTICS_SCHEMA,
    WRITE_QUALITY_REPORT_SCHEMA,
    get_field_statistics,
)
from ..config import AgentConfig
from ..extractors import extract
from ..extractors.base import DatasetProfile
from ..schema import (
    DamaDimension,
    DataQualityReport,
    FieldExpectation,
    FieldQualityResult,
)

_MD_CONFIG, _SYSTEM_PROMPT = load_agent("quality_agent")


class DataQualityAgent(BaseAgent):
    """Profiles datasets and generates DAMA-DMBOK quality reports."""

    def __init__(self, config: AgentConfig | None = None):
        super().__init__(config)
        self._report_raw: dict | None = None
        self._profile: DatasetProfile | None = None
        self._tools = [GET_FIELD_STATISTICS_SCHEMA, WRITE_QUALITY_REPORT_SCHEMA]

    @property
    def system_prompt(self) -> str:
        return _SYSTEM_PROMPT

    @property
    def tools(self) -> list[dict]:
        return self._tools

    def handle_tool_call(self, name: str, inputs: dict) -> str:
        if name == "get_field_statistics":
            if self._profile is None:
                return json.dumps({"error": "No profile loaded."})
            stats = get_field_statistics(self._profile, inputs.get("field_names", []))
            return json.dumps(stats)

        if name == "write_quality_report":
            self._report_raw = inputs
            return "Quality report accepted."

        return "Tool not available."

    def run(self, file_path: str) -> DataQualityReport:
        """
        Profile a file and return a DataQualityReport.

        Parameters
        ----------
        file_path : str
            Path to a .csv, .json, or .sql file.
        """
        self._profile = extract(str(file_path))
        self._report_raw = None

        dataset_name = self._profile.dataset_name
        field_list = ", ".join(f.name for f in self._profile.fields)

        user_msg = f"""Perform a comprehensive data quality assessment on the following dataset.

Dataset: {dataset_name}
Source type: {self._profile.source_type}
Row count: {self._profile.row_count or 'unknown'}
Fields ({len(self._profile.fields)}): {field_list}

Steps:
1. Call get_field_statistics with ALL field names to retrieve the full statistical profile.
2. Analyse each field across the six DAMA-DMBOK dimensions:
   completeness, consistency, accuracy, timeliness, uniqueness, validity.
3. For each field, generate Great Expectations-compatible expectations based on the observed statistics.
4. Call write_quality_report with the complete quality assessment.

Score each DAMA dimension 0–100. Pass threshold is 75 overall.
Flag critical issues (score < 50 on any dimension).
Generate at least one Great Expectations expectation per field."""

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

            if self._report_raw is not None:
                break

        if self._report_raw is None:
            raise RuntimeError("DataQualityAgent did not produce a quality report.")

        return self._parse_report(self._report_raw, dataset_name)

    def _parse_report(self, raw: dict, dataset_name: str) -> DataQualityReport:
        # Parse DAMA dimensions
        dim_names = ["completeness", "consistency", "accuracy", "timeliness", "uniqueness", "validity"]
        dimensions: dict[str, DamaDimension] = {}
        for dim in dim_names:
            d = raw.get("dimensions", {}).get(dim, {})
            dimensions[dim] = DamaDimension(
                score=float(d.get("score", 0)),
                issues=d.get("issues", []),
                notes=d.get("notes", ""),
            )

        # Parse field quality results
        field_quality = []
        for fq in raw.get("field_quality", []):
            expectations = [
                FieldExpectation(
                    expectation_type=e.get("expectation_type", ""),
                    kwargs=e.get("kwargs", {}),
                )
                for e in fq.get("expectations", [])
            ]
            field_quality.append(
                FieldQualityResult(
                    field_name=fq["field_name"],
                    completeness_score=float(fq.get("completeness_score", 0)),
                    issues=fq.get("issues", []),
                    warnings=fq.get("warnings", []),
                    expectations=expectations,
                    quality_notes=fq.get("quality_notes", ""),
                )
            )

        return DataQualityReport(
            dataset_name=raw.get("dataset_name", dataset_name),
            overall_score=float(raw.get("overall_score", 0)),
            passed=bool(raw.get("passed", False)),
            dimensions=dimensions,
            field_quality=field_quality,
            critical_issues=raw.get("critical_issues", []),
            recommendations=raw.get("recommendations", []),
        )
