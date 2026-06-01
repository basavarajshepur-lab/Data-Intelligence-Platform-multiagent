# CLAUDE.md — Metadata Intelligence Agent

## Project overview

An AI-powered, agentic metadata generation platform for global banking institutions.
Takes CSV datasets, JSON Schemas, or SQL DDL as input (via file upload, Gmail, or Google Drive)
and produces structured metadata catalogue entries conforming to BCBS 239, UK GDPR, and
enterprise data governance standards.

The agent is memory-backed (SQLite), fetches live regulatory updates from BIS/ICO/FCA/EBA,
and is designed to be extended with additional data-function agents.

## Stack

- Python 3.11+
- Anthropic Claude API (claude-sonnet-4-6) with tool use and prompt caching
- Pydantic v2 for schema validation
- pandas for CSV profiling
- Streamlit for the web UI
- fpdf2 for PDF export
- python-docx for Word export
- Rich for CLI output
- PyYAML for human-readable output
- google-api-python-client + google-auth-oauthlib for Gmail / Drive connectors
- sqlite3 (stdlib) for agent memory

## Project structure

```
metadata-agent/
├── app.py                         # Streamlit web UI (primary entry point)
├── demo.py                        # CLI entry point
├── watcher.py                     # Background Gmail/Drive watcher (hourly poll)
├── requirements.txt
├── .env.example
├── .streamlit/config.toml         # Navy/blue banking theme
├── samples/                       # 8 example inputs (CSV, JSON Schema, SQL DDL)
├── outputs/                       # Generated metadata + memory DB (gitignored)
│   └── memory.db                  # SQLite: runs, field_glossary, regulation_cache
└── src/
    ├── agents/                    # All agents live here
    │   ├── base.py                # BaseAgent ABC — subclass to add new agents
    │   ├── metadata_agent.py      # MetadataAgent — primary agent (4 tools)
    │   ├── lineage_agent.py       # DataLineageAgent — STUB, not yet implemented
    │   └── quality_agent.py       # DataQualityAgent — STUB, not yet implemented
    ├── regulations/               # Real-time regulatory content
    │   └── fetcher.py             # RSS fetch from BIS/ICO/FCA/EBA, 24-hour cache
    ├── memory/                    # Persistent agent memory
    │   └── memory_store.py        # store_run, search_glossary, regulation_cache helpers
    ├── connectors/                # External input sources
    │   ├── google_auth.py         # Shared OAuth2 (Gmail + Drive)
    │   ├── gmail_connector.py     # List emails with attachments, download
    │   └── drive_connector.py     # List and download Drive files
    ├── extractors/                # Input parsers — CSV, JSON Schema, SQL DDL
    │   ├── base.py                # DatasetProfile and FieldProfile dataclasses
    │   ├── csv_extractor.py
    │   ├── json_extractor.py
    │   └── sql_extractor.py
    ├── guardrails/                # Policy enforcement (runs before evals)
    │   ├── pii_guardrail.py       # PII sensitivity floor enforcement
    │   └── sensitivity_guardrail.py
    ├── evals/                     # Quality scoring (runs after guardrails)
    │   ├── eval_runner.py         # Orchestrates 5 dimensions, computes weighted score
    │   ├── completeness.py        # 30% weight
    │   ├── pii_consistency.py     # 25%
    │   ├── type_validator.py      # 20%
    │   ├── banking_standards.py   # 15%
    │   └── sensitivity_consistency.py  # 10%
    ├── exporters/                 # Download format generators
    │   ├── csv_exporter.py
    │   ├── pdf_exporter.py
    │   └── word_exporter.py
    ├── schema.py                  # Pydantic models (DatasetMetadata, FieldMetadata, etc.)
    └── config.py                  # Banking constants: PII floors, eval thresholds, patterns
```

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env
# Add ANTHROPIC_API_KEY to .env
streamlit run app.py
```

## Running the agent

```bash
# Web UI (recommended — Upload, Gmail, or Drive input)
streamlit run app.py

# Background watcher (auto-processes Gmail/Drive every hour)
python watcher.py
python watcher.py --interval 30   # every 30 minutes
python watcher.py --once          # single poll (for Task Scheduler)

# CLI
python demo.py samples/customer_accounts.csv
python demo.py samples/trade_confirmations.csv --output-dir outputs/
```

## Agent architecture

### MetadataAgent tool loop (up to 6 turns)

1. `search_field_glossary` — look up prior PII/sensitivity for matching field names
2. `get_regulation_updates` — fetch live BIS/ICO/FCA/EBA guidance (24-hour cached)
3. `get_dataset_history` — understand the existing catalogue landscape
4. `generate_dataset_metadata` — produce the final structured output

### Adding a new agent

1. Create `src/agents/<name>_agent.py`
2. Subclass `BaseAgent` from `src/agents/base.py`
3. Implement `system_prompt`, `tools`, `handle_tool_call()`, `run()`
4. Register in `src/agents/__init__.py`

See `lineage_agent.py` and `quality_agent.py` for documented stubs.

### Regulation fetcher

`src/regulations/fetcher.py` polls four RSS feeds:

| Source | Framework | Feed |
|--------|-----------|------|
| BIS BCBS | BCBS_239 | bis.org/rss/bcbs.rss |
| ICO | UK_GDPR | ico.org.uk news RSS |
| FCA | FCA | fca.org.uk/news/rss.xml |
| EBA | EBA | eba.europa.eu/rss.xml |

Items are cached in `regulation_cache` table. Cache TTL is 24 hours.
The agent calls `get_regulation_updates(frameworks=[...])` to retrieve current guidance.

## Architecture decisions

**Guardrails before evals** — Guardrails fix policy violations (PII sensitivity floors). Evals then
score the already-corrected output. This separates enforcement from measurement.

**Agentic loop with memory tools** — `tool_choice: any` forces at least one tool call per turn.
Claude searches the enterprise glossary first, checks live regulations, then generates metadata.
This ensures cross-dataset consistency and current compliance flags.

**Prompt caching** — The system prompt is cached using `cache_control: {type: ephemeral}`.
Reduces input token cost by ~90% on repeated runs.

**PII masking in extractor** — Suspected PII columns are masked before any values appear in the
Claude prompt. Values never leave the local machine for PII fields.

**Live regulation context** — Instead of hard-coding regulatory text, the agent fetches current
guidance from official RSS feeds. 24-hour cache balances freshness with latency.

## Eval thresholds

| Dimension | Weight | Pass threshold |
|-----------|--------|----------------|
| Completeness | 30% | 70/100 |
| PII Detection | 25% | 80/100 |
| Type Consistency | 20% | 75/100 |
| Banking Standards | 15% | 70/100 |
| Sensitivity Consistency | 10% | 90/100 |
| **Overall gate** | — | **75/100** |

Sensitivity consistency is non-negotiable — failures block the quality gate regardless of overall score.

## Key files to read first

- `src/schema.py` — all data models; understand before touching anything else
- `src/config.py` — banking constants, PII floors, eval thresholds
- `src/agents/base.py` — BaseAgent ABC; read before writing a new agent
- `src/agents/metadata_agent.py` — tool definitions and agentic loop
- `src/regulations/fetcher.py` — regulation RSS sources and caching

## Environment variables

| Variable | Required | Description |
|----------|----------|-------------|
| `ANTHROPIC_API_KEY` | Yes | Anthropic API key |

Google OAuth credentials (`credentials.json`, `google_token.json`) are stored in the
project root and are gitignored.
