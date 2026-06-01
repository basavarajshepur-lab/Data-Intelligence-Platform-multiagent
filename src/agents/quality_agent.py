"""Data Quality Agent — DAMA-DMBOK profiling and Great Expectations rule generation.

System prompt and configuration are loaded from agents/quality_agent.md.
Edit that file to change the agent's behaviour without touching Python code.

Status: STUB — tools not yet implemented.
See agents/quality_agent.md for the full specification.
"""

from .base import BaseAgent
from .loader import load_agent

_MD_CONFIG, _SYSTEM_PROMPT = load_agent("quality_agent")


class DataQualityAgent(BaseAgent):
    """Profiles datasets and generates quality reports aligned with DAMA-DMBOK dimensions."""

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
            "DataQualityAgent is not yet implemented. "
            "See agents/quality_agent.md for the specification."
        )
