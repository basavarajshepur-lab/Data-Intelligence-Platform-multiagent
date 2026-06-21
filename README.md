# Data Intelligence Platform (Metadata curation, Lineage, Data Quality)

An AI-powered, multi-agent data governance platform for global banking institutions. Three specialised Claude agents — **Metadata**, **Lineage**, and **Data Quality** — work together to automate the most time-consuming parts of data governance: cataloguing datasets, mapping field-level lineage, and profiling data quality.

All agents are driven by editable markdown files in `agents/`, maintain a persistent SQLite memory, fetch live regulatory updates from BIS/ICO/FCA/EBA, and can receive files from a local upload, Gmail attachment, or Google Drive.

BIS: Bank for International Settlements
ICO: Information Commissioner's Office
FCA: Financial Conduct Authority
EBA: European Banking AuthorityWhat They Do

BIS: Serves as a bank for central banks and fosters global monetary stability.
ICO: UK's independent body set up to uphold information rights and data privacy.
FCA: Regulates financial services firms and financial markets in the UK.
EBA: Regulates and supervises the banking sector across all European Union countries.

Built as a portfolio project demonstrating the intersection of AI engineering and banking data governance.

---

## Quick start

```bash
git clone https://github.com/basavarajshepur-lab/metadata-agent.git
cd metadata-agent
pip install -r requirements.txt
cp .env.example .env          # add ANTHROPIC_API_KEY
streamlit run app.py          # web UI at http://localhost:8501
```

---

## The three agents

| Agent | Command | Input | Output | Standards |
|-------|---------|-------|--------|-----------|
| **Metadata** | `run_agent.py metadata` | CSV / JSON Schema / SQL DDL | Metadata catalogue entry — field descriptions, PII flags, sensitivity, compliance | BCBS 239, UK GDPR, DAMA-DMBOK |
| **Lineage** | `run_agent.py lineage` | SQL SELECT file | Field-level lineage graph — source columns, transformations, BCBS 239 flags | BCBS 239 Principle 2 |
| **Data Quality** | `run_agent.py quality` | CSV / JSON Schema / SQL DDL | DAMA-DMBOK quality report — 6 dimension scores, Great Expectations rules | DAMA-DMBOK, BCBS 239 Principles 3–6 |

---

## Running the agents — CLI

Use `run_agent.py` to run any agent from the terminal.

### List all agents

```bash
python run_agent.py list
```

Shows name, status, version, model, tool count, and description for every agent defined in `agents/`.

---

### Metadata Agent

Generates a banking-grade metadata catalogue entry for any dataset.

```bash
# Basic usage
python run_agent.py metadata samples/customer_accounts.csv
python run_agent.py metadata samples/transaction_schema.json
python run_agent.py metadata samples/risk_positions.sql

# Custom output directory
python run_agent.py metadata samples/trade_confirmations.csv --output outputs/

# Faster / cheaper model
python run_agent.py metadata samples/customer_accounts.csv --model claude-haiku-4-5-20251001
```

**Output files** written to `outputs/`:
- `{dataset}_metadata.json` — machine-readable, for catalogue API ingestion
- `{dataset}_metadata.yaml` — human-readable, for Git review and steward sign-off

**What the agent does in the loop (up to 6 turns):**

| Turn | Tool | What happens |
|------|------|-------------|
| 1 | `search_field_glossary` | Looks up prior PII/sensitivity for every field name — enforces cross-dataset consistency |
| 2 | `get_regulation_updates` | Fetches live guidance from BIS, ICO, FCA, EBA — sharpens compliance flags |
| 3 | `get_dataset_history` *(optional)* | Reads the catalogue landscape — populates `related_datasets` |
| 4 | `generate_dataset_metadata` | Produces structured JSON matching the Pydantic schema |

---

### Lineage Agent

Maps field-level data lineage from a SQL SELECT query. Conforms to BCBS 239 Principle 2.

```bash
# Map lineage from a SQL file
python run_agent.py lineage samples/risk_positions.sql

# Custom output directory
python run_agent.py lineage my_transform.sql --output outputs/
```

**Input:** any `.sql` or `.ddl` file containing a SELECT statement.
Supports all major SQL dialects: `ansi`, `postgres`, `oracle`, `mysql`, `bigquery`, `tsql`, `spark`, `duckdb`.

**Output file** written to `outputs/`:
- `{dataset}_lineage.json` — OpenLineage-compatible lineage graph

**Example terminal output:**

```
Fields mapped:  12
Source tables:  positions, risk_factors, market_data
Unresolved:     0
BCBS 239 compliant: YES

Target Field          Type         Confidence  Sources
──────────────────────────────────────────────────────────────────────
position_id           direct       HIGH        positions.position_id
market_value          aggregated   HIGH        positions.quantity · market_data.price
delta_01              derived      HIGH        risk_factors.delta · positions.notional
unrealised_pnl        derived      MEDIUM      positions.cost_basis · market_data.price
```

**What the agent does in the loop (up to 8 turns):**

| Turn | Tool | What happens |
|------|------|-------------|
| 1 | `extract_sql_lineage` | `sqlglot` parses the SQL — returns source tables, output columns, expressions, lineage type (direct / derived / aggregated) |
| 2 | `search_field_glossary` | Cross-references output column names against the enterprise catalogue |
| 3 | `write_lineage_graph` | Claude writes enriched lineage with BCBS 239 compliance flags and descriptions |

**Lineage types:**

| Type | Meaning | Example |
|------|---------|---------|
| `direct` | Column copied unchanged | `SELECT customer_id` |
| `derived` | Expression applied | `SELECT amount * fx_rate AS base_amount` |
| `aggregated` | Aggregate function | `SELECT SUM(amount) AS total` |
| `constant` | Hardcoded value | `SELECT 'GBP' AS ccy` |

---

### Data Quality Agent

Profiles a dataset across all six DAMA-DMBOK quality dimensions and generates Great Expectations rules.

```bash
# Quality assessment on any supported file
python run_agent.py quality samples/customer_accounts.csv
python run_agent.py quality samples/kyc_screening_results.csv
python run_agent.py quality samples/risk_positions.sql

# Custom output directory
python run_agent.py quality samples/collateral_register.csv --output outputs/
```

**Output file** written to `outputs/`:
- `{dataset}_quality.json` — full quality report with dimension scores and GE expectations

**Example terminal output:**

```
Overall score: 81.4/100  PASS

DAMA Dimension    Score  Status  Top Issue
──────────────────────────────────────────────────────────────────────
Completeness        88   PASS    —
Consistency         85   PASS    —
Accuracy            79   PASS    credit_score range 300–850 not validated
Timeliness          72   PASS    last_login has no freshness SLA defined
Uniqueness          90   PASS    —
Validity            74   PASS    kyc_status allows unexpected value 'legacy'

Great Expectations rules generated: 34
```

**What the agent does in the loop (up to 8 turns):**

| Turn | Tool | What happens |
|------|------|-------------|
| 1 | `get_field_statistics` | Returns null rates, unique counts, value ranges, derived quality flags from the dataset profile |
| 2 | `write_quality_report` | Claude scores all 6 DAMA dimensions, generates GE expectations per field, writes recommendations |

**DAMA-DMBOK dimensions assessed:**

| Dimension | What is checked | BCBS 239 link |
|-----------|----------------|---------------|
| **Completeness** | Null rates, mandatory field population | Principle 4 |
| **Consistency** | Cross-field rules, referential integrity | Principle 3 |
| **Accuracy** | Range checks, pattern validation | Principle 3 |
| **Timeliness** | Data freshness, processing lag | Principle 5 |
| **Uniqueness** | Duplicate detection at key field level | Principle 3 |
| **Validity** | Business rule conformance, allowed values | Principle 6 |

---

## Customising agent behaviour — markdown definitions

Each agent is defined in a markdown file in `agents/`. **Edit these files to change agent behaviour without touching Python code.**

```
agents/
├── metadata_agent.md    ← system prompt + YAML config
├── lineage_agent.md     ← system prompt + YAML config
└── quality_agent.md     ← system prompt + YAML config
```

**File format:**

```markdown
---
name: lineage-agent
model: claude-sonnet-4-6
max_turns: 8
tools:
  - extract_sql_lineage
  - search_field_glossary
  - write_lineage_graph
status: active
---

You are a data lineage specialist...
(rest of file = system prompt sent verbatim to Claude)
```

**What you can change by editing a `.md` file:**

| What you edit | Effect |
|---|---|
| The markdown body | Changes Claude's persona, priorities, and instructions |
| `model:` | Switches to Haiku (faster/cheaper) or Opus (more capable) |
| `max_turns:` | Controls how many tool calls Claude can make |
| `tools:` list | Documents which tools this agent uses (for reference) |

Changes take effect the next time you run the agent — no Python restart needed.

---

## Web Interface (Metadata Agent only)

Launch with `streamlit run app.py`. The web UI runs the **Metadata Agent**.

### Input — three ways to load a file

| Tab | How it works |
|-----|--------------|
| **Upload File** | Drag-and-drop or browse for a local `.csv`, `.json`, or `.sql` file. Sample datasets included. |
| **From Gmail** | Connect your Google account once; the tab lists every email with a CSV/JSON/SQL attachment. Click any attachment to process it. |
| **From Google Drive** | Browses your Drive for supported files, newest first. Search by name. Click to download and process. |

Eight sample datasets are included:

| Sample file | Domain | Fields | Expected metadata score |
|-------------|--------|--------|------------------------|
| `customer_accounts.csv` | Retail banking | 18 | 88–95% |
| `transaction_schema.json` | Payments | 26 | 88–95% |
| `risk_positions.sql` | Market risk | 42 | 88–95% |
| `collateral_register.csv` | Collateral management | 25 | 73–80% |
| `kyc_screening_results.csv` | AML / KYC | 22 | 70–78% |
| `interest_rate_curves.json` | Treasury / rates | 23 | 72–80% |
| `system_access_log.sql` | IT / audit | 26 | 70–76% |
| `trade_confirmations.csv` | Fixed income trading | 30 | 75–82% |

> Suspected PII columns are **masked before any values leave your machine**. The Claude prompt only sees column names and statistics, never actual values.

### Results tabs

| Tab | What it shows |
|-----|---------------|
| **Overview** | Dataset description, business context, usage guidance, PII summary, classification details |
| **Fields** | Full field inventory — filterable by PII status, sensitivity, or name. Select any field for a full detail panel |
| **Quality Report** | 5-dimension eval score with pass/fail, issues, warnings, guardrails applied |
| **Compliance** | GDPR/UK GDPR flags, regulatory frameworks, retention period, PII register |
| **Raw YAML** | Full metadata as syntax-highlighted YAML |

### Download formats

| Format | Best for |
|--------|----------|
| **CSV** | Data catalogue ingestion (Collibra, Atlan, DataHub), Excel review |
| **PDF** | Stakeholder review and governance sign-off |
| **Word (.docx)** | Data steward annotation and approval |
| **YAML** | Machine-readable API ingestion |

---

## Connecting Gmail and Google Drive

### One-time setup

1. Go to [console.cloud.google.com](https://console.cloud.google.com) and create a project
2. Enable **Gmail API** and **Google Drive API**
3. **APIs & Services → OAuth consent screen** → External → add yourself as a test user
4. **APIs & Services → Credentials → Create OAuth client ID** → type: Desktop App
5. Download `credentials.json`

### Connecting in the app

1. Open the app → **From Gmail** tab → upload `credentials.json`
2. Click **Authorize Gmail & Drive** — browser opens for Google sign-in
3. Click **Done / Refresh** — both tabs activate

The agent only requests **read-only** scopes. It cannot send emails or modify files.

> If Google shows an "app not verified" warning, click **Advanced → Go to metadata-agent (unsafe)**. Expected for apps in test mode.

---

## Background watcher — automatic processing

The watcher polls Gmail and Google Drive on a schedule and runs the **Metadata Agent** on any new attachments automatically.

```bash
python watcher.py                  # poll every 60 minutes
python watcher.py --interval 30    # poll every 30 minutes
python watcher.py --once           # single poll then exit
```

Logs are printed to the terminal and saved to `outputs/watcher.log`.

Files are never processed twice. Re-uploading a Drive file (new `modifiedTime`) triggers reprocessing.

### Windows Task Scheduler (run automatically)

1. Press **Win + R** → `taskschd.msc`
2. **Create Basic Task** → name: `Metadata Agent Watcher`
3. Trigger: **Daily** → Repeat every **1 hour**
4. Action: **Start a program**
   - Program: `python`
   - Arguments: `"C:\...\metadata-agent\watcher.py" --once`
   - Start in: `C:\...\metadata-agent`

---

## Architecture

```
Input sources
  ├── File upload (local)
  ├── Gmail attachment           ┐
  └── Google Drive file          ┘ connectors/
         │
         ▼
   Extractor ── statistical profiling, PII heuristics, values masked for PII fields
         │
         ├──────────────────────────────────────────────────────────┐
         ▼                                                          ▼
   MetadataAgent (metadata_agent.py)                  LineageAgent (lineage_agent.py)
     Turn 1: search_field_glossary                     Turn 1: extract_sql_lineage (sqlglot)
     Turn 2: get_regulation_updates (RSS)              Turn 2: search_field_glossary
     Turn 3: get_dataset_history                       Turn 3: write_lineage_graph
     Turn 4: generate_dataset_metadata                         │
         │                                                     ▼
         ▼                                             DatasetLineage
   Guardrails + Evals                                 (BCBS 239 Principle 2)
         │
         ▼
   DataQualityAgent (quality_agent.py)
     Turn 1: get_field_statistics
     Turn 2: write_quality_report
         │
         ▼
   DataQualityReport (DAMA-DMBOK 6 dimensions + GE expectations)

All agents → Memory store (outputs/memory.db)
         ├── Web UI (Streamlit) — metadata agent, 3 input tabs, 5 result tabs
         └── CLI (run_agent.py) — all three agents
```

### Agent definitions (markdown-driven)

Each agent reads its system prompt and config from a markdown file:

```
agents/
├── metadata_agent.md   status: active   tools: 4
├── lineage_agent.md    status: active   tools: 3
└── quality_agent.md    status: active   tools: 2
```

Edit the markdown to change agent behaviour. The Python classes handle tool execution only.

### Real-time regulatory updates (Metadata Agent)

| Source | Framework | Feed |
|--------|-----------|------|
| BIS / Basel Committee | BCBS_239 | BIS BCBS RSS |
| ICO | UK_GDPR | ICO news RSS |
| FCA | FCA | FCA news RSS |
| EBA | EBA | EBA RSS |

Cached in `regulation_cache` table for 24 hours. Auto-refreshed on next agent call.

### Agent memory (SQLite)

| Table | Contents |
|-------|----------|
| `runs` | Every metadata run — dataset name, domain, classification, quality score, full JSON |
| `field_glossary` | Per-field definitions indexed by name — used for cross-dataset PII/sensitivity consistency |
| `regulation_cache` | RSS items from BIS/ICO/FCA/EBA — 24-hour TTL |
| `processed_sources` | Gmail/Drive files already processed by the watcher — prevents duplicate runs |

### Guardrails (Metadata Agent — pre-eval enforcement)

| Guardrail | Rule |
|-----------|------|
| PII Sensitivity Floor | name/email/phone → CONFIDENTIAL min; account/sort/IBAN → RESTRICTED; card/CVV → SECRET |
| Dataset Classification | Cannot be lower than the highest field sensitivity level |
| PII Type Required | Any field with `is_pii: true` must carry a `pii_type` |

### Metadata eval dimensions

| Dimension | Weight | Pass | What it checks |
|-----------|--------|------|----------------|
| Completeness | 30% | 70 | All metadata fields populated with meaningful content |
| PII Detection | 25% | 80 | AI PII flags vs column-name heuristics |
| Type Consistency | 20% | 75 | Declared types match inferred types |
| Banking Standards | 15% | 70 | BCBS 239 lineage, GDPR fields, key field identification |
| Sensitivity Consistency | 10% | 90 | PII sensitivity floors and internal consistency |

Overall gate: **75/100**. Sensitivity consistency failure blocks the gate regardless of overall score.

---

## Project structure

```
metadata-agent/
├── app.py                         # Streamlit web UI (Metadata Agent)
├── run_agent.py                   # Unified CLI — runs any agent by name
├── demo.py                        # Legacy CLI for Metadata Agent only
├── watcher.py                     # Background Gmail/Drive watcher
├── requirements.txt
├── .env.example
├── agents/                        # Agent definitions — edit these files
│   ├── metadata_agent.md          # System prompt + config for MetadataAgent
│   ├── lineage_agent.md           # System prompt + config for LineageAgent
│   └── quality_agent.md           # System prompt + config for DataQualityAgent
├── .streamlit/config.toml         # Navy/blue banking theme
├── samples/                       # 8 example input files
├── outputs/                       # Generated files + memory DB (gitignored)
│   ├── memory.db                  # SQLite: runs, glossary, regulations, processed_sources
│   └── watcher.log
└── src/
    ├── agents/                    # Agent implementations
    │   ├── base.py                # BaseAgent ABC — subclass to add new agents
    │   ├── loader.py              # Reads agents/*.md at runtime
    │   ├── metadata_agent.py      # MetadataAgent (4 tools)
    │   ├── lineage_agent.py       # LineageAgent (3 tools, sqlglot)
    │   ├── quality_agent.py       # DataQualityAgent (2 tools, DAMA-DMBOK)
    │   └── tools/
    │       ├── lineage_tools.py   # extract_sql_lineage + write_lineage_graph schemas/impls
    │       └── quality_tools.py   # get_field_statistics + write_quality_report schemas/impls
    ├── regulations/
    │   └── fetcher.py             # RSS fetch from BIS/ICO/FCA/EBA, 24-hour cache
    ├── memory/
    │   └── memory_store.py        # All SQLite helpers
    ├── connectors/
    │   ├── google_auth.py         # Shared OAuth2
    │   ├── gmail_connector.py
    │   └── drive_connector.py
    ├── extractors/
    │   ├── base.py                # DatasetProfile + FieldProfile dataclasses
    │   ├── csv_extractor.py
    │   ├── json_extractor.py
    │   └── sql_extractor.py
    ├── guardrails/
    │   ├── pii_guardrail.py
    │   └── sensitivity_guardrail.py
    ├── evals/
    │   ├── eval_runner.py
    │   ├── completeness.py
    │   ├── pii_consistency.py
    │   ├── type_validator.py
    │   ├── banking_standards.py
    │   └── sensitivity_consistency.py
    ├── exporters/
    │   ├── csv_exporter.py
    │   ├── pdf_exporter.py
    │   └── word_exporter.py
    ├── schema.py                  # All Pydantic models — metadata, lineage, quality
    └── config.py                  # Banking constants: PII floors, eval thresholds
```

---

## Supported input formats

| Format | Extension | Metadata | Lineage | Quality |
|--------|-----------|----------|---------|---------|
| CSV dataset | `.csv` | ✓ | — | ✓ |
| JSON Schema | `.json` | ✓ | — | ✓ |
| SQL DDL | `.sql` `.ddl` | ✓ | — | ✓ |
| SQL SELECT | `.sql` | — | ✓ | — |

---

## Example outputs

### Metadata Agent — single field

```yaml
- name: national_insurance
  display_name: National Insurance Number
  description: UK NI number uniquely identifying the individual for tax and social
    security purposes. Format [A-Z]{2}[0-9]{6}[A-Z].
  data_type: string
  is_pii: true
  pii_type: national_id
  sensitivity_level: restricted
  usage_guidance: Access restricted to KYC and Compliance teams. Never include in
    analytics exports. Mask in non-production environments. Audit log all access.
  tags: [pii, restricted, kyc, regulatory, hmrc]
```

### Lineage Agent — single field

```json
{
  "target_field": "unrealised_pnl",
  "source_fields": [
    { "table": "positions", "column": "cost_basis" },
    { "table": "market_data", "column": "price" }
  ],
  "transformation": "(market_data.price - positions.cost_basis) * positions.quantity",
  "lineage_type": "derived",
  "confidence": "HIGH",
  "bcbs_note": "BCBS 239 P2: lineage traceable to two source tables. Requires daily reconciliation."
}
```

### Data Quality Agent — single field

```json
{
  "field_name": "credit_score",
  "completeness_score": 94.5,
  "issues": ["2 null values on a field used in credit decisioning"],
  "expectations": [
    { "expectation_type": "expect_column_values_to_not_be_null", "kwargs": {} },
    { "expectation_type": "expect_column_values_to_be_between", "kwargs": { "min_value": 300, "max_value": 850 } }
  ],
  "quality_notes": "Null rate 0.6% — acceptable but should be investigated. Range 300–850 per standard credit scoring."
}
```

---

## Design decisions

**Markdown-driven agents.** System prompts live in `agents/*.md`, not in Python. Change the `.md` to change what Claude is told to do — no code change, no restart required. The Python class handles tool execution only.

**Agentic loop with tool selection.** `tool_choice: any` forces at least one tool per turn. Claude chooses which tools to call and in what order based on the system prompt instructions. The loop runs until the terminal tool (`generate_dataset_metadata`, `write_lineage_graph`, or `write_quality_report`) is called.

**sqlglot for SQL lineage.** Pure Python, no database connection required, supports 20+ SQL dialects. Extracts column references and expression types (direct, derived, aggregated, constant) statically before Claude interprets the results.

**Memory for consistency.** Without memory, `account_number` might be RESTRICTED one run and CONFIDENTIAL the next. The field glossary gives Claude explicit prior context on every run.

**Guardrails before evals.** Guardrails fix known policy violations. Evals score the corrected output. Policy compliance is guaranteed before quality measurement begins.

**Prompt caching.** System prompts (~1,200 tokens) are cached with `cache_control: ephemeral`. ~90% input token saving on repeated runs.

**PII masking at extraction.** Suspected PII column values are masked before the first API call. Actual values never appear in the Claude prompt.

---

## Adding a new agent

1. **Create `agents/<name>.md`** with YAML front matter and the system prompt in the body
2. **Create `src/agents/tools/<name>_tools.py`** with tool schemas and Python implementations
3. **Create `src/agents/<name>_agent.py`** — subclass `BaseAgent`, implement `tools`, `handle_tool_call()`, `run()`
4. **Register** in `src/agents/__init__.py`
5. **Add a command** to `run_agent.py`

---

## Banking standards encoded

| Standard | Where applied |
|----------|--------------|
| **BCBS 239** | Metadata: lineage, reconciliation keys, quality flags · Lineage: Principle 2 field-level traceability · Quality: Principles 3–6 accuracy/completeness/timeliness/adaptability |
| **UK GDPR / GDPR** | Metadata: PII classification, lawful basis, retention, right to erasure, cross-border restrictions |
| **DAMA-DMBOK** | Metadata: steward/owner fields, domain classification · Quality: 6 quality dimensions |
| **ISO 8000** | Metadata: quality indicator fields embedded at field level |
| **FCA Handbook** | Metadata: 7-year retention flag for regulated financial data |
| **PSD2** | Metadata: payment data sensitivity floors (IBAN, sort code, account number) |

---

## Tech stack

| Component | Library | Purpose |
|-----------|---------|---------|
| AI agents | `anthropic` | Agentic loops with tool use and prompt caching for all three agents |
| SQL lineage | `sqlglot` | Dialect-agnostic SQL parsing and column-level lineage extraction |
| Web UI | `streamlit` | Upload, Gmail/Drive input tabs, results tabs, download buttons |
| Schema validation | `pydantic v2` | Output models for metadata, lineage, and quality reports |
| Data profiling | `pandas` | CSV statistical profiling and type inference |
| Agent memory | `sqlite3` (stdlib) | Field glossary, run history, regulation cache, processed sources |
| Live regulations | `urllib.request` + `xml.etree` (stdlib) | RSS fetch from BIS, ICO, FCA, EBA |
| Google connectors | `google-api-python-client`, `google-auth-oauthlib` | Gmail and Drive read-only access |
| PDF export | `fpdf2` | Structured PDF with field tables, PII register, quality report |
| Word export | `python-docx` | Editable .docx with colour-coded sensitivity cells |
| YAML output | `pyyaml` | Human-readable metadata files |
| CLI display | `rich` | Formatted terminal output for all agents |
| Config | `python-dotenv` | API key and environment management |

---

## About

Built by a Senior Product Owner with 19 years in banking data and AI, currently at Deutsche Bank CDO. This project demonstrates how generative AI can automate the most time-consuming parts of data governance — writing metadata, tracing lineage, and generating quality rules — at banking-grade standards.
