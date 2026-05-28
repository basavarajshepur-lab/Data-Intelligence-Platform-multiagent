# CLAUDE.md — Metadata Intelligence Agent

## Project overview

An AI-powered metadata generation agent for global banking institutions. Takes CSV datasets,
JSON Schemas, or SQL DDL as input and produces structured metadata catalogue entries conforming
to BCBS 239, UK GDPR, and enterprise data governance standards.

## Stack

- Python 3.11+
- Anthropic Claude API (claude-sonnet-4-6) with tool use and prompt caching
- Pydantic v2 for schema validation
- pandas for CSV profiling
- Rich for CLI output
- PyYAML for human-readable output

## Project structure

```
metadata-agent/
├── demo.py                        # CLI entry point
├── requirements.txt
├── samples/                       # Example inputs (CSV, JSON Schema, SQL DDL)
│   ├── customer_accounts.csv
│   ├── transaction_schema.json
│   └── risk_positions.sql
├── outputs/                       # Generated metadata files (gitignored)
└── src/
    ├── agent.py                   # Main Claude agent (tool use, prompt caching)
    ├── schema.py                  # Pydantic models (DatasetMetadata, FieldMetadata, etc.)
    ├── config.py                  # Banking constants: PII floors, eval thresholds, patterns
    ├── extractors/                # Input parsers — CSV, JSON Schema, SQL DDL
    │   ├── __init__.py            # Auto-dispatch by file extension
    │   ├── base.py                # DatasetProfile and FieldProfile dataclasses
    │   ├── csv_extractor.py
    │   ├── json_extractor.py
    │   └── sql_extractor.py
    ├── guardrails/                # Policy enforcement (runs before evals)
    │   ├── __init__.py            # Guardrail pipeline
    │   ├── pii_guardrail.py       # PII sensitivity floor enforcement
    │   └── sensitivity_guardrail.py  # Dataset-level classification consistency
    └── evals/                     # Quality scoring (runs after guardrails)
        ├── __init__.py
        ├── eval_runner.py         # Orchestrates all 5 dimensions, computes weighted score
        ├── completeness.py        # Field metadata completeness (30% weight)
        ├── pii_consistency.py     # AI vs heuristic PII agreement (25%)
        ├── type_validator.py      # Declared type vs inferred type (20%)
        ├── banking_standards.py   # BCBS 239 + GDPR compliance checks (15%)
        └── sensitivity_consistency.py  # Internal consistency of sensitivity (10%)
```

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env
# Add ANTHROPIC_API_KEY to .env
```

## Running the agent

```bash
python demo.py samples/customer_accounts.csv
python demo.py samples/transaction_schema.json
python demo.py samples/risk_positions.sql
python demo.py <your_file> --output-dir outputs/
```

## Architecture decisions

**Guardrails before evals** — Guardrails fix policy violations (PII sensitivity floors). Evals then
score the already-corrected output. This separates enforcement from measurement.

**Tool use for structured output** — `tool_choice: {type: tool}` forces valid JSON matching
the Pydantic schema. No text parsing or regex extraction.

**Prompt caching** — The ~1,200 token banking standards system prompt is cached using
`cache_control: {type: ephemeral}`. Reduces input token cost by ~90% on repeated runs.

**PII masking in extractor** — Suspected PII columns (detected by name heuristics) are masked
before any values appear in the Claude prompt. Values never leave the local machine for PII fields.

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

## Adding a new extractor

1. Create `src/extractors/<format>_extractor.py` with `extract(filepath) -> DatasetProfile`
2. Register it in `src/extractors/__init__.py`

## Adding a new eval

1. Create `src/evals/<name>.py` with `evaluate(metadata, profile) -> QualityDimension`
2. Add it to `src/evals/eval_runner.py` with a weight (weights must sum to 1.0)

## Key files to read first

- `src/schema.py` — all data models; understand this before touching anything else
- `src/config.py` — banking constants, PII floors, eval thresholds (change behaviour here, not in logic files)
- `src/agent.py` — the Claude integration; METADATA_TOOL defines the structured output contract

## Environment variables

| Variable | Required | Description |
|----------|----------|-------------|
| `ANTHROPIC_API_KEY` | Yes | Anthropic API key |

## Output files

Each run writes two files to `outputs/`:
- `{dataset}_metadata.yaml` — human-readable, for Git review and data steward sign-off
- `{dataset}_metadata.json` — machine-readable, for data catalogue API ingestion (Collibra, Atlan, DataHub)
