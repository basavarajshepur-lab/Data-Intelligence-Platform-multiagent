"""Agent definition loader.

Each agent is defined in a markdown file at agents/<agent_name>.md.
The file uses YAML front matter for configuration and the markdown body
as the system prompt sent verbatim to Claude.

File format
-----------
    ---
    name: metadata-agent
    description: One-line description shown in the UI
    version: "1.0"
    model: claude-sonnet-4-6
    max_turns: 6
    tools:
      - search_field_glossary
      - get_regulation_updates
      - generate_dataset_metadata
    ---

    You are a senior data architect...
    (rest of the system prompt in plain markdown)

Usage
-----
    from src.agents.loader import load_agent

    config, system_prompt = load_agent("metadata_agent")
    print(config["model"])        # claude-sonnet-4-6
    print(system_prompt[:80])     # You are a senior data architect...
"""

from pathlib import Path

import yaml

# Agents directory is at the project root, alongside app.py
_AGENTS_DIR = Path(__file__).parent.parent.parent / "agents"


def load_agent(agent_name: str) -> tuple[dict, str]:
    """
    Load an agent's configuration and system prompt from its markdown file.

    Parameters
    ----------
    agent_name : str
        Filename without extension, e.g. "metadata_agent".

    Returns
    -------
    (config, system_prompt)
        config         — dict parsed from YAML front matter (empty dict if absent)
        system_prompt  — str body of the markdown file (the prompt sent to Claude)

    Raises
    ------
    FileNotFoundError if agents/<agent_name>.md does not exist.
    """
    md_path = _AGENTS_DIR / f"{agent_name}.md"
    if not md_path.exists():
        raise FileNotFoundError(
            f"Agent definition not found: {md_path}\n"
            f"Create agents/{agent_name}.md to define this agent."
        )

    content = md_path.read_text(encoding="utf-8")

    if content.startswith("---"):
        parts = content.split("---", 2)
        if len(parts) == 3:
            config = yaml.safe_load(parts[1].strip()) or {}
            system_prompt = parts[2].strip()
            return config, system_prompt

    # No front matter — treat the whole file as the system prompt
    return {}, content.strip()


def list_agents() -> list[dict]:
    """Return a summary of every agent found in the agents/ directory."""
    if not _AGENTS_DIR.exists():
        return []

    agents = []
    for md_file in sorted(_AGENTS_DIR.glob("*.md")):
        try:
            config, prompt = load_agent(md_file.stem)
            agents.append(
                {
                    "name": config.get("name", md_file.stem),
                    "file": md_file.name,
                    "description": config.get("description", ""),
                    "version": config.get("version", "—"),
                    "model": config.get("model", "—"),
                    "tools": config.get("tools", []),
                    "status": config.get("status", "active"),
                }
            )
        except Exception:
            pass
    return agents
