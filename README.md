# Metadata Intelligence Agent

An AI-powered, agentic metadata generation system for global banking institutions. Upload a CSV dataset, JSON Schema, or SQL DDL — or pull a file directly from Gmail or Google Drive — and get a fully curated metadata catalogue entry in under two minutes, conforming to BCBS 239, UK GDPR, and enterprise data governance standards.

The agent maintains a persistent memory of every run. On each new dataset it searches the enterprise field glossary for matching field names, ensuring PII classification and sensitivity levels stay consistent across your entire data catalogue.

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
- **Cross-dataset consistency** — agent looks up prior definitions before generating, so `account_number` is always RESTRICTED across every dataset

---

## Web Interface

Launch with `streamlit run app.py`.

### Input — three ways to load a file

| Tab | How it works |
|-----|--------------|
| **Upload File** | Drag-and-drop or browse for a local `.csv`, `.json`, or `.sql` file. Sample datasets included. |
| **From Gmail** | Connect your Google account once; the tab lists every email in your inbox that has a CSV/JSON/SQL attachment. Click any attachment to process it. |
| **From Google Drive** | Browses your Drive for supported files, newest first. Search by name. Click to download and process. |

Eight sample datasets are included to try immediately:

| Sample file | Domain | Fields | Expected score |
|-------------|--------|--------|----------------|
| `customer_accounts.csv` | Retail banking | 18 | 88–95% |
| `transaction_schema.json` | Payments | 26 | 88–95% |
| `risk_positions.sql` | Market risk | 42 | 88–95% |
| `collateral_register.csv` | Collateral management | 25 | 73–80% |
| `kyc_screening_results.csv` | AML / KYC | 22 | 70–78% |
| `interest_rate_curves.json` | Treasury / rates | 23 | 72–80% |
| `system_access_log.sql` | IT / audit | 26 | 70–76% |
| `trade_confirmations.csv` | Fixed income trading | 30 | 75–82% |

After selecting a file from any tab, the extractor profiles it locally — no API call yet — and shows a field preview table with inferred types, null rates, and PII heuristic flags.

> Suspected PII columns are **masked before any values leave your machine**. The Claude prompt only sees column names and statistics, never the actual values.

Click **Generate Metadata** to send the profile to Claude.

### Results tabs

| Tab | What it shows |
|-----|---------------|
| **Overview** | Dataset description, business context, usage guidance, PII summary, dataset classification details |
| **Fields** | Full field inventory table — filterable by PII status, sensitivity level, or name search. Select any field for a full detail panel: constraints, lineage, business rules, guardrail notices |
| **Quality Report** | Overall score (0–100) with pass/fail, dimension breakdown with progress bars, issues list, warnings list, guardrails applied |
| **Compliance** | GDPR/UK GDPR flags, regulatory frameworks, retention period, data residency, PII field register colour-coded by sensitivity |
| **Raw YAML** | Full metadata as syntax-highlighted YAML — copy button included |

### Download formats

| Format | Best for | Contents |
|--------|----------|----------|
| **CSV** | Data catalogue ingestion, Excel review | Flat field inventory with all metadata columns, dataset header block |
| **PDF** | Stakeholder review, governance documentation | Cover page, field table, PII register, compliance section, quality report |
| **Word (.docx)** | Data steward annotation and sign-off | Full editable document with colour-coded sensitivity cells, all sections |
| **YAML** | API ingestion (Collibra, Atlan, DataHub) | Machine-readable full metadata, same structure as local output files |

### Sidebar

- Enter your **Anthropic API key** (or set `ANTHROPIC_API_KEY` in `.env`)
- Select **model**: Sonnet 4.6 (recommended), Haiku 4.5 (faster/cheaper), Opus 4.7 (most capable)
- **Run History** — last 6 datasets processed, with domain, field count, and quality score at a glance
- After a run: quick stats panel and a clear/reset button

---

## Connecting Gmail and Google Drive

### One-time setup

1. Go to [console.cloud.google.com](https://console.cloud.google.com) and create a project
2. Enable **Gmail API** and **Google Drive API**
3. Go to **APIs & Services → OAuth consent screen** → External → add yourself as a test user
4. Go to **APIs & Services → Credentials → Create OAuth client ID** → type: **Desktop App**
5. Download the credentials file and rename it `credentials.json`

### Connecting in the app

1. Open the app → **From Gmail** tab
2. Upload `credentials.json` when prompted
3. Click **Authorize Gmail & Drive** — your browser opens for Google sign-in
4. Sign in and grant read-only access
5. Click **Done / Refresh** — both Gmail and Drive tabs are now active

The agent only requests **read-only** scopes (`gmail.readonly`, `drive.readonly`). It cannot send emails or modify files.

> If Google shows an "app not verified" warning, click **Advanced → Go to metadata-agent (unsafe)**. This is expected for apps in test mode that haven't gone through Google's review process.

---

## Background watcher — automatic processing

The watcher polls Gmail and Google Drive on a schedule and runs the metadata agent on any new attachments automatically, without you having to click anything in the UI.

### Starting the watcher

Open a **second terminal** alongside the Streamlit app and run:

```bash
# Poll every 60 minutes, runs until Ctrl+C (default)
python watcher.py

# Poll every 30 minutes
python watcher.py --interval 30

# Poll once and exit — useful for testing or Task Scheduler
python watcher.py --once
```

Logs are printed to the terminal and saved to `outputs/watcher.log`.

### How it works

```
Every hour:
  Gmail → find emails with .csv / .json / .sql attachments
         → skip files already recorded in processed_sources table
         → download new ones → run metadata agent → save to memory DB

  Drive → list .csv / .json / .sql files, newest first
         → skip already-processed (tracked by file ID + modifiedTime)
         → re-uploaded files get a new modifiedTime, so are reprocessed
         → download → run metadata agent → save to memory DB
```

Files are never processed twice. If you re-upload a Drive file or re-send an email with a corrected dataset, the watcher detects the change and reprocesses it automatically.

### Run automatically with Windows Task Scheduler

To have the watcher run even when you are not at your computer:

1. Press **Win + R**, type `taskschd.msc`, press Enter
2. Click **Create Basic Task** → name it `Metadata Agent Watcher`
3. Trigger: **Daily** → check **Repeat task every: 1 hour**
4. Action: **Start a program**
   - Program: `python`
   - Arguments: `"C:\Users\basav\OneDrive\Documents\Portfolio\metadata-agent\watcher.py" --once`
   - Start in: `C:\Users\basav\OneDrive\Documents\Portfolio\metadata-agent`
5. Click **Finish**

Using `--once` with Task Scheduler is cleaner than a long-running process — the scheduler controls the timing and restarts the script if it crashes.

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
Input sources
  ├── File upload (local)
  ├── Gmail attachment
  └── Google Drive file
         │
         ▼
   Extractor ── statistical profiling, PII heuristics, values masked for PII fields
         │
         ▼
   MetadataAgent (src/agents/metadata_agent.py) — agentic loop, max 6 turns
     │
     ├─ Turn 1  search_field_glossary(all field names)
     │          └─ SQLite glossary → prior PII/sensitivity for consistency
     │
     ├─ Turn 2  get_regulation_updates(frameworks)
     │          └─ RSS fetch from BIS · ICO · FCA · EBA (24-hour cache)
     │             Returns live guidance to sharpen compliance flags
     │
     ├─ Turn 3  [optional] get_dataset_history()
     │          └─ Catalogue summary → populates related_datasets
     │
     └─ Turn 4  generate_dataset_metadata(...)
                └─ Structured JSON output matching Pydantic schema
         │
         ▼
   Guardrails ── PII sensitivity floors enforced, dataset classification consistency
         │
         ▼
   Evals ─────── 5-dimension quality scoring, BCBS 239 + GDPR checks, pass/fail gate
         │
         ▼
   Memory store ── persist run + field glossary to SQLite (outputs/memory.db)
         │
         ├── Web UI (Streamlit) ────── interactive results, 5 tabs, 4 download formats
         └── CLI (demo.py) ────────── Rich terminal output, YAML + JSON files
```

### Real-time regulatory updates

The agent calls `get_regulation_updates` during the agentic loop to fetch the latest guidance from official regulatory RSS feeds:

| Source | Framework | What it monitors |
|--------|-----------|-----------------|
| BIS / Basel Committee | BCBS_239 | Risk data aggregation publications |
| ICO | UK_GDPR | UK data protection guidance and enforcement notices |
| FCA | FCA | Consumer data rules, financial crime, reporting standards |
| EBA | EBA | Supervisory reporting, data standards |

Results are cached in `outputs/memory.db` for 24 hours. Stale cache is auto-refreshed on the next agent call. The returned updates are passed directly into the Claude context so compliance flags, retention periods, and regulatory framework tags reflect current official guidance rather than training data.

### Adding a new agent

All agents live in `src/agents/` and extend `BaseAgent`:

```python
from src.agents.base import BaseAgent

class MyNewAgent(BaseAgent):
    @property
    def system_prompt(self) -> str: ...

    @property
    def tools(self) -> list[dict]: ...

    def handle_tool_call(self, name: str, inputs: dict) -> str: ...

    def run(self, *args, **kwargs): ...
```

Two stubs are already provided as templates: `lineage_agent.py` (field-level SQL lineage) and `quality_agent.py` (DAMA-DMBOK quality profiling).

### Agent memory

The agent uses a local SQLite database (`outputs/memory.db`) with three tables:

| Table | Contents | Purpose |
|-------|----------|---------|
| `runs` | Dataset name, domain, classification, field count, quality score, full metadata JSON | Run history shown in sidebar |
| `field_glossary` | Per-field: name, PII type, sensitivity level, data type, description, source dataset | Consistency lookup on every new run |
| `regulation_cache` | RSS items from BIS/ICO/FCA/EBA with headline, URL, summary, fetched timestamp | 24-hour regulation cache for the agent tool |

On each generation, Claude first calls `search_field_glossary` with all field names from the new dataset. If a field like `account_number` was classified RESTRICTED in a previous run, that prior definition is included in the context so Claude applies the same classification — preventing drift across datasets.

### Guardrails (pre-eval enforcement)

Guardrails run before evals so the quality score reflects the corrected output.

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
├── app.py                         # Streamlit web UI (primary entry point)
├── demo.py                        # CLI entry point
├── requirements.txt
├── .env.example                   # API key template
├── .streamlit/
│   └── config.toml                # Navy/blue banking theme
├── samples/
│   ├── customer_accounts.csv      # 18-field retail banking customer dataset (scores ~88–95%)
│   ├── transaction_schema.json    # 26-field payment transaction JSON Schema (scores ~88–95%)
│   ├── risk_positions.sql         # 42-field trading book risk positions DDL (scores ~88–95%)
│   ├── collateral_register.csv    # 25-field collateral management register (scores ~73–80%)
│   ├── kyc_screening_results.csv  # 22-field AML/KYC screening results (scores ~70–78%)
│   ├── interest_rate_curves.json  # Rate curve snapshot JSON Schema (scores ~72–80%)
│   ├── system_access_log.sql      # 26-field system audit/access log DDL (scores ~70–76%)
│   └── trade_confirmations.csv    # 30-field fixed income trade confirms (scores ~75–82%)
├── outputs/                       # Generated metadata + memory DB (gitignored)
│   └── memory.db                  # SQLite: runs, field_glossary, regulation_cache
└── src/
    ├── agents/                    # All agents — subclass BaseAgent to add new ones
    │   ├── base.py                # BaseAgent ABC (system_prompt, tools, handle_tool_call, run)
    │   ├── metadata_agent.py      # MetadataAgent — 4-tool agentic loop
    │   ├── lineage_agent.py       # DataLineageAgent — stub (SQL field-level lineage)
    │   └── quality_agent.py       # DataQualityAgent — stub (DAMA-DMBOK profiling)
    ├── regulations/               # Real-time regulatory content
    │   └── fetcher.py             # RSS fetch from BIS/ICO/FCA/EBA, 24-hour cache
    ├── memory/                    # Persistent agent memory (SQLite)
    │   └── memory_store.py        # store_run, search_glossary, regulation_cache helpers
    ├── connectors/                # External input sources
    │   ├── google_auth.py         # Shared OAuth2 for Gmail + Drive
    │   ├── gmail_connector.py     # List emails with attachments, download files
    │   └── drive_connector.py     # List and download Drive files
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
    ├── exporters/                 # Download format generators
    │   ├── csv_exporter.py        # Flat field inventory CSV
    │   ├── pdf_exporter.py        # Structured PDF catalogue document (fpdf2)
    │   └── word_exporter.py       # Editable Word document (python-docx)
    ├── schema.py                  # Pydantic models — DatasetMetadata, FieldMetadata, etc.
    └── config.py                  # Banking constants: PII floors, eval thresholds, patterns
```

---

## Design decisions

**Agentic loop instead of forced single call.** The agent now runs a multi-turn loop (max 6 turns). On the first turn Claude calls `search_field_glossary` to check prior definitions, optionally calls `get_dataset_history` for landscape context, then calls `generate_dataset_metadata` with a fully informed response. `tool_choice: any` ensures a tool is always used, preventing open-ended text responses.

**Memory for cross-dataset consistency.** Without memory, the same field `account_number` might be classified RESTRICTED in one run and CONFIDENTIAL in another. The SQLite glossary gives Claude the prior classification as explicit context, making consistency measurable and automatic.

**Why tool use instead of prompt-to-text?** `tool_choice` forces Claude to return valid JSON matching the Pydantic schema every time. No text parsing, no regex extraction from prose, no malformed output.

**Why guardrails before evals?** Guardrails fix known policy violations (e.g. a card number field classified CONFIDENTIAL instead of SECRET). Evals then score the already-corrected output. This separates enforcement from measurement — the policy is guaranteed met before scoring begins.

**Why prompt caching?** The system prompt encodes ~1,200 tokens of banking standards context (BCBS 239, GDPR rules, PII taxonomy). Caching it with `cache_control: ephemeral` cuts input token cost by ~90% across repeated runs.

**Why mask PII in the extractor?** The extractor runs before any API call. Column names that match PII heuristics trigger value masking so actual data never appears in the Claude prompt — reducing exposure even if an API call were intercepted or logged.

**Why read-only OAuth scopes?** The agent only needs to read files. `gmail.readonly` and `drive.readonly` are the minimum permissions. The agent cannot send emails, modify Drive files, or access any other Google service.

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

**Add a new input connector** — implement `list_files()` and `download_file()` in `src/connectors/`, then add a tab in `app.py` that sets `st.session_state["_staged_bytes"]` and `st.session_state["_staged_name"]`.

**Add a new agent** — subclass `BaseAgent` in `src/agents/`, implement `system_prompt`, `tools`, `handle_tool_call()`, and `run()`. See `lineage_agent.py` and `quality_agent.py` for documented stubs.

**Connect to a data catalogue** — the YAML/JSON output follows a generic structure. Write a thin adapter that maps the fields to your catalogue's API (Collibra, Atlan, DataHub, Alation).

---

## Tech stack

| Component | Library | Purpose |
|-----------|---------|---------|
| AI agent | `anthropic` | Agentic loop with memory tools, structured output via tool use, prompt caching |
| Web UI | `streamlit` | Upload, Gmail/Drive tabs, results tabs, download buttons |
| Schema validation | `pydantic v2` | Type enforcement and model validation |
| Data profiling | `pandas` | CSV statistical profiling and type inference |
| Agent memory | `sqlite3` (stdlib) | Field glossary, run history, regulation cache |
| Live regulations | `urllib.request` + `xml.etree` (stdlib) | RSS fetch from BIS, ICO, FCA, EBA |
| Google connectors | `google-api-python-client`, `google-auth-oauthlib` | Gmail and Drive read-only access |
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
