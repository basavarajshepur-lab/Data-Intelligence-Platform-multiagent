# Metadata Intelligence Agent

An AI-powered metadata generation agent for global banking institutions. Upload a CSV dataset, JSON Schema, or SQL DDL — get a fully curated metadata catalogue entry in under two minutes, conforming to BCBS 239, UK GDPR, and enterprise data governance standards.

Built as a portfolio project demonstrating the intersection of AI engineering and banking data governance.

---

## Quick start

```bash
git clone https://github.com/YOUR_USERNAME/metadata-agent.git
cd metadata-agent
pip install -r requirements.txt
cp .env.example .env          # add your ANTHROPIC_API_KEY
streamlit run app.py          # opens at http://localhost:8501
```

---

## What it does

Takes raw datasets or schemas as input. Returns structured metadata with:

- **Field-level definitions** — precise business descriptions a data analyst can act on immediately
- **Data types and constraints** — inferred from actual data or schema definitions
- **PII classification** — identifies name, email, account numbers, sort codes, IBANs, NI numbers, card numbers, and 14 other PII types with exact PII type labelling
- **Sensitivity levels** — PUBLIC / INTERNAL / CONFIDENTIAL / RESTRICTED / SECRET, aligned with bank data classification policy
- **Usage guidance** — how to access, join, and handle the data, including non-prod masking requirements
- **Regulatory flags** — GDPR applicability, lawful basis, retention period, cross-border transfer restrictions
- **BCBS 239 compliance indicators** — data lineage, reconciliation keys, quality flags, source system traceability
- **Quality score** — 5-dimension eval with a hard pass/fail gate before catalogue ingestion

---

## Web Interface

Launch with `streamlit run app.py`. The UI has four sections.

### Upload and preview

Drop a file or click a sample dataset button. The extractor profiles it locally — no API call yet — and shows a field preview table with inferred types, null rates, and PII heuristic flags.

> Suspected PII columns are **masked before any values leave your machine**. The Claude prompt only sees column names and statistics, never the actual values.

Click **Generate Metadata** to send the profile to Claude. A spinner shows progress (typically 30–90 seconds depending on file size and model).

### Results tabs

| Tab | What it shows |
|-----|---------------|
| **Overview** | Dataset description, business context, usage guidance, PII summary, dataset classification details |
| **Fields** | Full field inventory table — filterable by PII status, sensitivity level, or name search. Select any field for a full detail panel: constraints, lineage, business rules, guardrail notices |
| **Quality Report** | Overall score (0–100) with pass/fail, dimension breakdown with progress bars, issues list, warnings list, guardrails applied |
| **Compliance** | GDPR/UK GDPR flags, regulatory frameworks, retention period, data residency, PII field register colour-coded by sensitivity |
| **Raw YAML** | Full metadata as syntax-highlighted YAML — copy button included |

### Download formats

Four export formats available after generation:

| Format | Best for | Contents |
|--------|----------|----------|
| **CSV** | Data catalogue ingestion, Excel review | Flat field inventory with all metadata columns, dataset header block |
| **PDF** | Stakeholder review, governance documentation | Cover page, field table, PII register, compliance section, quality report |
| **Word (.docx)** | Data steward annotation and sign-off | Full editable document with colour-coded sensitivity cells, all sections |
| **YAML** | API ingestion (Collibra, Atlan, DataHub) | Machine-readable full metadata, same structure as local output files |

### Sidebar

- Enter your **Anthropic API key** (or set `ANTHROPIC_API_KEY` in `.env`)
- Select **model**: Sonnet 4.6 (recommended), Haiku 4.5 (faster/cheaper), Opus 4.7 (most capable)
- After a run: quick stats panel and a clear/reset button

---

## CLI (alternative to the web UI)

```bash
# Analyse a CSV dataset
python demo.py samples/customer_accounts.csv

# Analyse a JSON Schema
python demo.py samples/transaction_schema.json

# Analyse a SQL DDL
python demo.py samples/risk_positions.sql

# Custom output directory
python demo.py samples/customer_accounts.csv --output-dir my_outputs/

# Use a different model
python demo.py samples/customer_accounts.csv --model claude-opus-4-7
```

The CLI writes `{dataset}_metadata.yaml` and `{dataset}_metadata.json` to the output directory and prints a quality report to the terminal using Rich.

---

## Architecture

```
Input (CSV / JSON Schema / SQL DDL)
    │
    ▼
Extractor ─── statistical profiling, PII heuristics, values masked for PII fields
    │
    ▼
Claude Agent ─ tool-use structured output, system prompt cached (~90% token saving)
    │
    ▼
Guardrails ─── PII sensitivity floors enforced, dataset classification consistency
    │
    ▼
Evals ──────── 5-dimension quality scoring, BCBS 239 + GDPR checks, pass/fail gate
    │
    ├── Web UI (Streamlit) ────── interactive results, 5 tabs, 4 download formats
    │
    └── CLI (demo.py) ────────── Rich terminal output, YAML + JSON files
```

### Guardrails (pre-eval enforcement)

Guardrails run before evals so the quality score reflects the corrected output, not the raw AI output.

| Guardrail | Rule |
|-----------|------|
| PII Sensitivity Floor | name/email/phone → CONFIDENTIAL min; account numbers/sort codes/IBANs → RESTRICTED; card numbers/CVVs → SECRET |
| Dataset Classification | Dataset classification cannot be lower than the highest field sensitivity level |
| PII Type Required | Any field with `is_pii: true` must have an explicit `pii_type` |

### Eval dimensions

| Dimension | Weight | Pass threshold | What it checks |
|-----------|--------|----------------|----------------|
| Completeness | 30% | 70/100 | All required metadata fields populated with meaningful content |
| PII Detection | 25% | 80/100 | AI PII flags vs column-name heuristics and extractor detection |
| Type Consistency | 20% | 75/100 | Declared data types match what was inferred from actual data |
| Banking Standards | 15% | 70/100 | BCBS 239 lineage, GDPR compliance fields, key field identification |
| Sensitivity Consistency | 10% | 90/100 | Internal consistency of PII flags and sensitivity levels |

Overall gate: **75/100 weighted average**. Sensitivity consistency is non-negotiable — a failure blocks the gate regardless of overall score.

---

## Supported input formats

| Format | Extension | Notes |
|--------|-----------|-------|
| CSV dataset | `.csv` | First 10,000 rows profiled; suspected PII columns masked before sampling |
| JSON Schema | `.json` | Draft-07 and draft-2020-12 supported; nested objects flattened |
| SQL DDL | `.sql` `.ddl` | PostgreSQL, Oracle, SQL Server, BigQuery dialects |

---

## Example metadata output (single field)

```yaml
- name: national_insurance
  display_name: National Insurance Number
  description: UK National Insurance number uniquely identifying the individual for
    tax and social security purposes. Format NI [A-Z]{2}[0-9]{6}[A-Z].
  business_context: Collected for KYC/AML verification and HMRC tax reporting. Subject
    to strict need-to-know access controls.
  data_type: string
  format: "[A-Z]{2}[0-9]{6}[A-Z]"
  constraints:
    nullable: true
    unique: true
    pattern: ^[A-CEGHJ-PR-TW-Z]{2}\d{6}[A-D]$
  is_pii: true
  pii_type: national_id
  sensitivity_level: restricted
  is_key_field: false
  usage_guidance: Access restricted to KYC and Compliance teams only. Never include
    in analytics exports or dashboards. Mask in non-production environments. Audit
    log all access.
  business_rules: Must match HMRC format. Only collected after KYC onboarding completed.
  data_lineage: Customer-provided during onboarding, validated against HMRC format regex
  tags: [pii, restricted, kyc, regulatory, hmrc]
```

---

## Project structure

```
metadata-agent/
├── app.py                         # Streamlit web UI
├── demo.py                        # CLI entry point
├── requirements.txt
├── .env.example                   # API key template
├── .streamlit/
│   └── config.toml                # Navy/blue banking theme
├── samples/
│   ├── customer_accounts.csv      # 18-field retail banking customer dataset
│   ├── transaction_schema.json    # 26-field payment transaction JSON Schema
│   └── risk_positions.sql         # 42-field trading book risk positions DDL
├── outputs/                       # Generated metadata files (gitignored)
└── src/
    ├── agent.py                   # Claude API integration (tool use, prompt caching)
    ├── schema.py                  # Pydantic models — DatasetMetadata, FieldMetadata, etc.
    ├── config.py                  # Banking constants: PII floors, eval thresholds, patterns
    ├── extractors/                # Input parsers
    │   ├── base.py                # DatasetProfile and FieldProfile dataclasses
    │   ├── csv_extractor.py
    │   ├── json_extractor.py
    │   └── sql_extractor.py
    ├── guardrails/                # Policy enforcement (runs before evals)
    │   ├── pii_guardrail.py       # PII sensitivity floor enforcement
    │   └── sensitivity_guardrail.py
    ├── evals/                     # Quality scoring (runs after guardrails)
    │   ├── eval_runner.py         # Orchestrates 5 dimensions, computes weighted score
    │   ├── completeness.py
    │   ├── pii_consistency.py
    │   ├── type_validator.py
    │   ├── banking_standards.py
    │   └── sensitivity_consistency.py
    └── exporters/                 # Download format generators
        ├── csv_exporter.py        # Flat field inventory CSV
        ├── pdf_exporter.py        # Structured PDF catalogue document (fpdf2)
        └── word_exporter.py       # Editable Word document (python-docx)
```

---

## Design decisions

**Why tool use instead of prompt-to-text?** `tool_choice: {type: tool}` forces Claude to return valid JSON matching the Pydantic schema every time. No text parsing, no regex extraction from prose, no malformed output.

**Why guardrails before evals?** Guardrails fix known policy violations (e.g. a card number field classified CONFIDENTIAL instead of SECRET). Evals then score the already-corrected output. This separates enforcement from measurement — you know your policy is met before you even look at the score.

**Why prompt caching?** The system prompt encodes ~1,200 tokens of banking standards context (BCBS 239, GDPR rules, PII taxonomy). Caching it with `cache_control: ephemeral` cuts input token cost by ~90% across repeated runs on a dataset catalogue.

**Why mask PII in the extractor?** The extractor runs before any API call. Column names that match PII heuristics (email, account_number, sort_code, etc.) trigger value masking so actual data never appears in the Claude prompt. This reduces data leakage exposure even if an API call were intercepted or logged.

**Why Word and PDF exports?** In banking, metadata approval is a formal governance step. Data stewards need an editable document they can annotate and sign off. PDF is for the read-only record. YAML is for the downstream catalogue API.

---

## Banking standards encoded

| Standard | What is checked |
|----------|-----------------|
| **BCBS 239** | Data lineage, reconciliation key identification, quality flags, source system traceability, version management |
| **UK GDPR / GDPR** | PII classification, lawful basis, retention period, right to erasure, cross-border transfer restrictions, consent tracking |
| **DAMA-DMBOK** | Data steward and owner fields, domain/sub-domain classification, data lifecycle metadata |
| **ISO 8000** | Data quality indicator fields embedded in field-level metadata |
| **FCA Handbook** | 7-year retention flag for regulated financial data |
| **PSD2** | Payment data sensitivity floors (IBAN, sort code, account number) |

---

## Extending the agent

**Add a new input format** — implement `extract(filepath: str) -> DatasetProfile` in `src/extractors/` and register the extension in `src/extractors/__init__.py`.

**Add a new eval dimension** — implement `evaluate(metadata, profile) -> QualityDimension` in `src/evals/` and register it in `eval_runner.py` with a weight. Weights must sum to 1.0.

**Add a new guardrail** — implement `apply(...)` in `src/guardrails/` and add it to the pipeline in `src/guardrails/__init__.py`.

**Add a new export format** — implement `export(metadata: DatasetMetadata) -> bytes` in `src/exporters/` and wire up a download button in `app.py`.

**Connect to a data catalogue** — the YAML/JSON output follows a generic structure. Write a thin adapter that maps the fields to your catalogue's API (Collibra, Atlan, DataHub, Alation).

---

## Tech stack

| Component | Library | Purpose |
|-----------|---------|---------|
| AI agent | `anthropic` | Structured metadata generation via tool use with prompt caching |
| Web UI | `streamlit` | Upload, results tabs, download buttons |
| Schema validation | `pydantic v2` | Type enforcement and model validation |
| Data profiling | `pandas` | CSV statistical profiling and type inference |
| PDF export | `fpdf2` | Structured PDF with field tables, PII register, quality report |
| Word export | `python-docx` | Editable .docx with colour-coded sensitivity cells |
| YAML output | `pyyaml` | Human-readable metadata files |
| CLI display | `rich` | Formatted terminal quality report |
| Config | `python-dotenv` | API key and environment management |

---

## About

Built by a Senior Product Owner with 19 years in banking data and AI, currently at Deutsche Bank CDO. This project demonstrates how generative AI can automate the most time-consuming part of data governance work — writing metadata that is actually useful to downstream data consumers, analysts, and compliance teams.

The same agent pattern can be extended to:
- Automated data lineage documentation from SQL query logs
- Data contract generation from microservice APIs  
- Regulatory reporting field mapping (COREP, FINREP, AnaCredit)
- Data quality rule generation from business constraints
- DORA-compliant critical data element cataloguing
