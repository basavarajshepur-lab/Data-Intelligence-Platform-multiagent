"""Abstract base class for all agents in the platform.

To add a new agent:
1. Create src/agents/<name>_agent.py
2. Subclass BaseAgent
3. Implement tools (property) and run()
4. Register in src/agents/__init__.py
"""

from abc import ABC, abstractmethod
from typing import Any

import anthropic

from ..config import AgentConfig

_MAX_TURNS = 10


class BaseAgent(ABC):
    """Common scaffolding for Claude-powered agents."""

    def __init__(self, config: AgentConfig | None = None):
        self.config = config or AgentConfig()
        self.config.validate()
        self.client = anthropic.Anthropic(api_key=self.config.api_key)

    @property
    @abstractmethod
    def system_prompt(self) -> str:
        """System prompt sent to Claude on every call."""
        ...

    @property
    @abstractmethod
    def tools(self) -> list[dict]:
        """Tool schemas available to Claude during the agentic loop."""
        ...

    @abstractmethod
    def handle_tool_call(self, name: str, inputs: dict) -> str:
        """Dispatch a tool call and return a JSON-serialisable string result."""
        ...

    @abstractmethod
    def run(self, *args, **kwargs) -> Any:
        """Execute the agent's primary task."""
        ...

    def _agentic_loop(self, messages: list[dict]) -> list[dict]:
        """
        Drive the Claude agentic loop until the final tool is called or
        the model stops. Returns the full conversation messages list.

        Subclasses call this from run(); they detect their terminal tool
        call inside handle_tool_call() by raising StopIteration or by
        setting a flag — or simply by checking the returned messages.
        """
        for _ in range(_MAX_TURNS):
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

            if response.stop_reason == "end_turn":
                break

        return messages
