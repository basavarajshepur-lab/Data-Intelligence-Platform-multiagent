"""Metadata Intelligence Agent.

Agentic loop (max 6 turns):
  1. search_field_glossary   — cross-dataset PII/sensitivity consistency
  2. get_dataset_history     — understand the data landscape
  3. get_regulation_updates  — fetch live regulatory guidance (BIS/ICO/FCA/EBA)
  4. generate_dataset_metadata — produce the structured output

Prompt caching is applied to the system prompt to reduce cost on repeated runs.
"""

import json
from typing import Any

from .base import BaseAgent
from ..config import AgentConfig
from ..extractors.base import DatasetProfile
from ..guardrails import apply_all
from ..evals import run as run_evals
from ..schema import (
    ComplianceInfo,
    DataDomain,
    DataType,
    DatasetMetadata,
    FieldConstraints,
    FieldMetadata,
    PIIType,
    QualityScore,
    RegulatoryFramework,
    SensitivityLevel,
)

try:
    from ..memory.memory_store import (
        get_run_history,
        glossary_size,
        search_glossary,
        store_run,
    )
    _MEMORY_OK = True
except Exception:
    _MEMORY_OK = False

try:
    from ..regulations.fetcher import get_regulation_context
    _REGULATIONS_OK = True
except Exception:
    _REGULATIONS_OK = False

_MAX_TURNS = 6

# ── System prompt ───────────────────────────────────────────────────────────

_SYSTEM_PROMPT = """You are a senior data architect and metadata specialist at a global systemically important bank (G-SIB). You have 20 years of experience across data governance, risk data aggregation, and regulatory compliance.

Your expertise spans:
- BCBS 239 (Risk Data Aggregation and Risk Reporting) — you understand all 11 principles
- GDPR and UK GDPR — you know when data is personal, sensitive, or special category
- DAMA-DMBOK data management framework — you write metadata that data consumers can actually use
- Banking data domains: Customer, Account, Transaction, Risk, Market Data, Reference, Regulatory
- PII identification in financial services: you know that sort codes + account numbers = payment data, IBANs = cross-border, NI numbers = government-linked

When generating metadata you MUST:

1. Write descriptions a data analyst could act on immediately. "Unique customer identifier" is too vague. "UUID assigned at account opening, used as the foreign key to join customer, account, and transaction datasets" is specific.

2. Identify ALL PII fields precisely. In banking these include:
   - Direct identifiers: name, email, phone, address, DOB, NI/SSN, passport
   - Financial identifiers: account number, sort code, IBAN, card number (PAN), CVV
   - Indirect identifiers: IP address, device ID, transaction patterns that could identify someone
   - Special category (GDPR Art. 9): health conditions (credit insurance), political views, trade union membership

3. Apply sensitivity levels correctly:
   - PUBLIC: aggregated stats, published rates, reference data
   - INTERNAL: operational data with no PII (transaction counts, system IDs)
   - CONFIDENTIAL: PII (name, email, phone, address, DOB)
   - RESTRICTED: financial identifiers (account numbers, sort codes, IBANs), government IDs
   - SECRET: card numbers (PAN), CVVs, biometric data, authentication credentials

4. Write usage_guidance that prevents misuse. Include: who can access, how to handle in non-prod environments, join key usage, aggregation requirements.

5. Flag data lineage where inferable from field names and context.

6. Note BCBS 239 compliance requirements for risk datasets: data lineage, reconciliation keys, quality indicators.

7. Be precise about regulatory frameworks. Don't mark BCBS_239 unless the dataset is genuinely risk/market/regulatory data.

AGENTIC TOOLS — use in this order:
1. search_field_glossary: ALWAYS call first with all field names. Use prior definitions to enforce cross-dataset consistency.
2. get_regulation_updates: Call when processing risk, market, or personal data to get the latest official guidance from BIS, ICO, FCA, or EBA. Use the returned updates to sharpen compliance flags and retention periods.
3. get_dataset_history: Optionally call to understand the existing data landscape and populate related_datasets.
4. generate_dataset_metadata: Call last with the complete metadata."""

# ── Tool schemas ────────────────────────────────────────────────────────────

_MEMORY_TOOLS: list[dict[str, Any]] = [
    {
        "name": "search_field_glossary",
        "description": (
            "Search the enterprise field glossary for fields matching the given names. "
            "Returns prior PII classification, sensitivity level, data type, and descriptions. "
            "Use to enforce cross-dataset consistency."
        ),
        "input_schema": {
            "type": "object",
            "required": ["field_names"],
            "properties": {
                "field_names": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "All field names from the current dataset profile",
                }
            },
        },
    },
    {
        "name": "get_dataset_history",
        "description": "Retrieve summaries of previously catalogued datasets to understand the data landscape.",
        "input_schema": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "default": 10}
            },
        },
    },
]

_REGULATION_TOOL: dict[str, Any] = {
    "name": "get_regulation_updates",
    "description": (
        "Fetch the latest regulatory guidance from official sources (BIS BCBS, ICO, FCA, EBA). "
        "Call this when processing risk data, personal data, or any dataset that needs BCBS 239 "
        "or GDPR compliance flags to ensure the most current rules are applied."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "frameworks": {
                "type": "array",
                "items": {
                    "type": "string",
                    "enum": ["BCBS_239", "UK_GDPR", "FCA", "EBA"],
                },
                "description": "Frameworks to check for recent updates",
            }
        },
    },
}

_METADATA_TOOL: dict[str, Any] = {
    "name": "generate_dataset_metadata",
    "description": "Generate comprehensive, banking-grade metadata for a dataset",
    "input_schema": {
        "type": "object",
        "required": [
            "description", "business_context", "data_domain",
            "classification", "data_classification_rationale",
            "fields", "compliance", "usage_guidance",
        ],
        "properties": {
            "description": {"type": "string"},
            "business_context": {"type": "string"},
            "data_domain": {"type": "string", "enum": [d.value for d in DataDomain]},
            "sub_domain": {"type": "string"},
            "classification": {"type": "string", "enum": [s.value for s in SensitivityLevel]},
            "data_classification_rationale": {"type": "string"},
            "source_system": {"type": "string"},
            "usage_guidance": {"type": "string"},
            "known_limitations": {"type": "string"},
            "related_datasets": {"type": "array", "items": {"type": "string"}},
            "fields": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": [
                        "name", "display_name", "description", "business_context",
                        "data_type", "is_pii", "sensitivity_level", "usage_guidance",
                    ],
                    "properties": {
                        "name": {"type": "string"},
                        "display_name": {"type": "string"},
                        "description": {"type": "string"},
                        "business_context": {"type": "string"},
                        "data_type": {"type": "string", "enum": [d.value for d in DataType]},
                        "format": {"type": "string"},
                        "is_pii": {"type": "boolean"},
                        "pii_type": {"type": "string", "enum": [p.value for p in PIIType]},
                        "sensitivity_level": {"type": "string", "enum": [s.value for s in SensitivityLevel]},
                        "is_key_field": {"type": "boolean"},
                        "usage_guidance": {"type": "string"},
                        "example_usage": {"type": "string"},
                        "business_rules": {"type": "string"},
                        "data_lineage": {"type": "string"},
                        "quality_notes": {"type": "string"},
                        "tags": {"type": "array", "items": {"type": "string"}},
                        "constraints": {
                            "type": "object",
                            "properties": {
                                "nullable": {"type": "boolean"},
                                "unique": {"type": "boolean"},
                                "min_value": {"type": "number"},
                                "max_value": {"type": "number"},
                                "min_length": {"type": "integer"},
                                "max_length": {"type": "integer"},
                                "pattern": {"type": "string"},
                                "allowed_values": {"type": "array", "items": {"type": "string"}},
                                "foreign_key_ref": {"type": "string"},
                                "precision": {"type": "integer"},
                                "scale": {"type": "integer"},
                            },
                        },
                    },
                },
            },
            "compliance": {
                "type": "object",
                "required": ["gdpr_applicable", "uk_gdpr_applicable"],
                "properties": {
                    "gdpr_applicable": {"type": "boolean"},
                    "uk_gdpr_applicable": {"type": "boolean"},
                    "regulatory_frameworks": {
                        "type": "array",
                        "items": {"type": "string", "enum": [r.value for r in RegulatoryFramework]},
                    },
                    "data_residency_requirements": {"type": "string"},
                    "retention_period": {"type": "string"},
                    "cross_border_transfer_restrictions": {"type": "boolean"},
                    "consent_required": {"type": "boolean"},
                    "right_to_erasure_applicable": {"type": "boolean"},
                    "lawful_basis": {"type": "string"},
                },
            },
        },
    },
}

# ── Helper functions ────────────────────────────────────────────────────────

def _build_user_message(profile: DatasetProfile) -> str:
    if _MEMORY_OK:
        n = glossary_size()
        memory_hint = (
            f"\n\nThe enterprise glossary contains {n} field definitions from past runs. "
            f"Call search_field_glossary with all {len(profile.fields)} field names now."
            if n > 0
            else "\n\n(Enterprise glossary is empty — check it first, then generate.)"
        )
    else:
        memory_hint = ""

    return f"""Generate comprehensive banking-grade metadata for the following dataset.

{profile.to_prompt_context()}{memory_hint}

Be precise about PII classification, sensitivity levels, and regulatory obligations.
For every field, write descriptions and business context that a data analyst can act on immediately.
Apply BCBS 239 lineage and quality principles where appropriate."""


def _parse_tool_result(raw: dict[str, Any], dataset_name: str) -> DatasetMetadata:
    fields = []
    for f in raw.get("fields", []):
        constraints_raw = f.get("constraints") or {}
        constraints = FieldConstraints(**{k: v for k, v in constraints_raw.items() if v is not None})
        pii_type_raw = f.get("pii_type")
        pii_type = PIIType(pii_type_raw) if pii_type_raw else None
        fields.append(
            FieldMetadata(
                name=f["name"],
                display_name=f.get("display_name", f["name"].replace("_", " ").title()),
                description=f.get("description", ""),
                business_context=f.get("business_context", ""),
                data_type=DataType(f.get("data_type", "string")),
                format=f.get("format"),
                constraints=constraints,
                is_pii=f.get("is_pii", False),
                pii_type=pii_type,
                sensitivity_level=SensitivityLevel(f.get("sensitivity_level", "internal")),
                is_key_field=f.get("is_key_field", False),
                usage_guidance=f.get("usage_guidance", ""),
                example_usage=f.get("example_usage"),
                business_rules=f.get("business_rules"),
                data_lineage=f.get("data_lineage"),
                quality_notes=f.get("quality_notes"),
                tags=f.get("tags", []),
            )
        )

    compliance_raw = raw.get("compliance", {})
    reg_frameworks = []
    for rf in compliance_raw.get("regulatory_frameworks", []):
        try:
            reg_frameworks.append(RegulatoryFramework(rf))
        except ValueError:
            pass

    compliance = ComplianceInfo(
        gdpr_applicable=compliance_raw.get("gdpr_applicable", False),
        uk_gdpr_applicable=compliance_raw.get("uk_gdpr_applicable", False),
        regulatory_frameworks=reg_frameworks,
        data_residency_requirements=compliance_raw.get("data_residency_requirements"),
        retention_period=compliance_raw.get("retention_period"),
        cross_border_transfer_restrictions=compliance_raw.get("cross_border_transfer_restrictions", False),
        consent_required=compliance_raw.get("consent_required", False),
        right_to_erasure_applicable=compliance_raw.get("right_to_erasure_applicable", False),
        lawful_basis=compliance_raw.get("lawful_basis"),
    )

    return DatasetMetadata(
        dataset_name=raw.get("dataset_name", dataset_name),
        description=raw.get("description", ""),
        business_context=raw.get("business_context", ""),
        data_domain=DataDomain(raw.get("data_domain", "reference")),
        sub_domain=raw.get("sub_domain"),
        classification=SensitivityLevel(raw.get("classification", "internal")),
        data_classification_rationale=raw.get("data_classification_rationale", ""),
        source_system=raw.get("source_system"),
        fields=fields,
        compliance=compliance,
        usage_guidance=raw.get("usage_guidance", ""),
        known_limitations=raw.get("known_limitations"),
        related_datasets=raw.get("related_datasets", []),
    )


# ── Agent class ─────────────────────────────────────────────────────────────

class MetadataAgent(BaseAgent):
    """
    Generates banking-grade metadata from a DatasetProfile.

    Agentic loop order:
      search_field_glossary → get_regulation_updates → get_dataset_history
      → generate_dataset_metadata
    """

    def __init__(self, config: AgentConfig | None = None):
        super().__init__(config)
        self._metadata_raw: dict | None = None

        tool_list = []
        if _MEMORY_OK:
            tool_list.extend(_MEMORY_TOOLS)
        if _REGULATIONS_OK:
            tool_list.append(_REGULATION_TOOL)
        tool_list.append(_METADATA_TOOL)
        self._tools = tool_list

    @property
    def system_prompt(self) -> str:
        return _SYSTEM_PROMPT

    @property
    def tools(self) -> list[dict]:
        return self._tools

    def handle_tool_call(self, name: str, inputs: dict) -> str:
        if name == "generate_dataset_metadata":
            self._metadata_raw = inputs
            return "Metadata accepted."

        if name == "search_field_glossary" and _MEMORY_OK:
            results = search_glossary(inputs.get("field_names", []))
            return json.dumps(results) if results else "No matching fields in glossary."

        if name == "get_dataset_history" and _MEMORY_OK:
            results = get_run_history(inputs.get("limit", 10))
            return json.dumps(results) if results else "No previous datasets found."

        if name == "get_regulation_updates" and _REGULATIONS_OK:
            return get_regulation_context(
                frameworks=inputs.get("frameworks", []),
                max_age_hours=24,
            )

        return "Tool not available."

    def run(self, profile: DatasetProfile) -> tuple[DatasetMetadata, QualityScore]:
        """Generate metadata, apply guardrails, run evals, persist to memory."""
        self._metadata_raw = None
        messages = [{"role": "user", "content": _build_user_message(profile)}]

        for _turn in range(_MAX_TURNS):
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
                raise RuntimeError("Agent turn produced no tool use.")

            messages.append({"role": "assistant", "content": response.content})

            tool_results = []
            for block in tool_blocks:
                result = self.handle_tool_call(block.name, block.input)
                tool_results.append(
                    {"type": "tool_result", "tool_use_id": block.id, "content": result}
                )
            messages.append({"role": "user", "content": tool_results})

            if self._metadata_raw is not None:
                break

        if self._metadata_raw is None:
            raise RuntimeError(f"Agent did not generate metadata within {_MAX_TURNS} turns.")

        self._metadata_raw["dataset_name"] = profile.dataset_name
        metadata = _parse_tool_result(self._metadata_raw, profile.dataset_name)

        metadata, guardrail_messages = apply_all(metadata)
        quality = run_evals(metadata, profile, guardrail_messages)
        metadata.quality_score = quality

        if _MEMORY_OK:
            try:
                store_run(metadata, quality)
            except Exception:
                pass

        return metadata, quality

    # Backward-compat alias used by demo.py, watcher.py, app.py
    def generate(self, profile: DatasetProfile) -> tuple[DatasetMetadata, QualityScore]:
        return self.run(profile)
