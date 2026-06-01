"""Data Lineage Agent — maps field-level lineage from SQL and pipeline definitions.

System prompt and configuration are loaded from agents/lineage_agent.md.
Edit that file to change the agent's behaviour without touching Python code.

Status: STUB — tools not yet implemented.
See agents/lineage_agent.md for the full specification.
"""

from .base import BaseAgent
from .loader import load_agent

_MD_CONFIG, _SYSTEM_PROMPT = load_agent("lineage_agent")


class LineageAgent(BaseAgent):
    """Maps field-level data lineage across SQL queries and pipeline stages."""

    @property
    def system_prompt(self) -> str:
        return _SYSTEM_PROMPT

    @property
    def tools(self) -> list[dict]:
        # Add tool schemas here as they are implemented
        return []

    def handle_tool_call(self, name: str, inputs: dict) -> str:
        return "Not implemented."

    def run(self, *args, **kwargs):
        raise NotImplementedError(
            "LineageAgent is not yet implemented. "
            "See agents/lineage_agent.md for the specification."
        )
