# Metadata Intelligence Agent

An AI-powered metadata generation agent for global banking institutions. Feed it a CSV, JSON Schema, or SQL DDL — it returns a curated metadata catalogue entry conforming to BCBS 239, UK GDPR, and enterprise data governance standards.

Built as a portfolio project demonstrating the intersection of AI engineering and banking data governance.

---

## What it does

Takes raw datasets or schemas as input. Returns a structured metadata file with:

- **Field-level definitions** — precise business descriptions a data analyst can act on
- **Data types and constraints** — inferred from actual data or schema definitions
- **PII classification** — identifies name, email, account numbers, sort codes, IBANs, NI numbers, card numbers, and 14 other PII types
- **Sensitivity levels** — PUBLIC / INTERNAL / CONFIDENTIAL / RESTRICTED / SECRET aligned with bank data classification policy
- **Usage guidance** — how to access, join, and handle the data, including non-prod masking requirements
- **Regulatory flags** — GDPR applicability, retention period, cross-border transfer restrictions
- **BCBS 239 compliance indicators** — data lineage, reconciliation keys, quality flags
- **Quality score** — 5-dimension eval with pass/fail gate before catalogue ingestion

---

## Architecture

```
Input (CSV / JSON Schema / SQL DDL)
    ↓
Extractor  — statistical profiling, PII heuristics, no PII values logged
    ↓
Claude Agent  — tool-use structured output, prompt caching on system prompt
    ↓
Guardrails  — PII sensitivity floors, dataset classification consistency
    ↓
Evals  — 5-dimension quality scoring, BCBS 239 checks, GDPR completeness
    ↓
Output (YAML + JSON metadata files)
```

### Guardrails (pre-eval enforcement)

| Guardrail | Rule |
|-----------|------|
| PII Sensitivity Floor | Name/email/phone → CONFIDENTIAL minimum; account numbers/sort codes/IBANs → RESTRICTED; card numbers → SECRET |
| Dataset Classification | Dataset sensitivity cannot be lower than its most sensitive field |
| PII Type Required | `is_pii: true` fields must have an explicit `pii_type` |

### Eval dimensions

| Dimension | Weight | Threshold | What it checks |
|-----------|--------|-----------|----------------|
| Completeness | 30% | 70/100 | All required metadata fields populated with meaningful content |
| PII Detection | 25% | 80/100 | AI PII flags vs column name heuristics and extractor detection |
| Type Consistency | 20% | 75/100 | Declared data types match what was inferred from actual data |
| Banking Standards | 15% | 70/100 | BCBS 239 lineage, GDPR compliance fields, key field identification |
| Sensitivity Consistency | 10% | 90/100 | Internal consistency of PII flags and sensitivity levels |

Overall gate: 75/100 weighted average, with sensitivity_consistency non-negotiable.

---

## Supported input formats

| Format | Extension | Notes |
|--------|-----------|-------|
| CSV dataset | `.csv` | First 10,000 rows profiled; suspected PII columns masked before sampling |
| JSON Schema | `.json` | Draft-07 and draft-2020-12 supported; nested objects flattened |
| SQL DDL | `.sql` | PostgreSQL, Oracle, SQL Server, BigQuery dialects |

---

## Output

Two files are written per run:

**`{dataset}_metadata.yaml`** — human-readable, designed for Git version control and peer review

**`{dataset}_metadata.json`** — machine-readable, designed for data catalogue API ingestion (Collibra, Alation, Atlan, DataHub)

### Example output (single field)

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

## Setup

```bash
# Clone and install
git clone <repo>
cd metadata-agent
pip install -r requirements.txt

# Add API key
cp .env.example .env
# Edit .env and add your ANTHROPIC_API_KEY
```

---

## Usage

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

---

## Design decisions

**Why tool use instead of prompt-to-text?** Structured output via `tool_choice: {type: tool}` forces Claude to return valid JSON matching the metadata schema every time. No parsing heuristics, no regex extraction from prose.

**Why guardrails before evals?** Guardrails fix known violations (e.g. a card number field marked CONFIDENTIAL instead of SECRET). Evals then score the corrected output. This separates "enforce the policy" from "measure quality."

**Why prompt caching?** The system prompt is ~1,200 tokens of banking standards context. Caching it cuts input token cost by ~90% on repeated runs across a dataset catalogue.

**Why mask PII in the extractor?** The extractor runs before the AI sees any data. Suspected PII column names trigger masking so actual values never appear in the prompt, reducing data leakage risk even if the API call were intercepted.

---

## Banking standards encoded

- **BCBS 239** — Risk data aggregation: data lineage, key field identification, quality flags, source system traceability
- **UK GDPR** — PII classification, lawful basis, retention period, right to erasure, cross-border transfer restrictions
- **DAMA-DMBOK** — Data stewardship fields: owner, steward, domain, sub-domain
- **ISO 8000** — Data quality indicators embedded in field metadata
- **FCA Handbook** — 7-year retention for regulated financial data
- **PSD2** — Payment data handling (IBAN, sort code, account number) sensitivity floors

---

## Extending the agent

**Add a new extractor:** Implement `extract(filepath: str) -> DatasetProfile` in `src/extractors/` and register it in `src/extractors/__init__.py`.

**Add a new eval:** Implement `evaluate(metadata: DatasetMetadata) -> QualityDimension` and register it in `src/evals/eval_runner.py` with a weight.

**Add a new guardrail:** Implement `apply(...)` in `src/guardrails/` and add it to the pipeline in `src/guardrails/__init__.py`.

**Connect to a data catalogue:** The JSON output follows a generic structure. Map fields to your catalogue's API (Collibra, Atlan, DataHub) in a thin adapter layer.

---

## Tech stack

- **Claude API** (Anthropic) — structured metadata generation via tool use with prompt caching
- **Pydantic v2** — schema validation and type enforcement
- **pandas** — CSV profiling and type inference
- **PyYAML** — human-readable output
- **Rich** — console UI

---

## About

Built by a Senior Product Owner with 19 years in banking data and AI, currently at Deutsche Bank CDO. This project demonstrates how generative AI can automate the most time-consuming part of data governance work — writing metadata that's actually useful to downstream consumers.

The same agent pattern could be extended to:
- Automated data lineage documentation from SQL query logs
- Data contract generation from microservice APIs
- Regulatory reporting field mapping (COREP, FINREP, AnaCredit)
- Data quality rule generation from constraints and business rules
