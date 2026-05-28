"""Metadata Intelligence Agent.

Uses Claude with structured tool use to generate banking-grade metadata
from a DatasetProfile. Prompt caching is applied to the large system prompt
to reduce cost on repeated runs.
"""

import json
from typing import Any, Dict

import anthropic

from .config import AgentConfig
from .extractors.base import DatasetProfile
from .guardrails import apply_all
from .evals import run as run_evals
from .schema import (
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

SYSTEM_PROMPT = """You are a senior data architect and metadata specialist at a global systemically important bank (G-SIB). You have 20 years of experience across data governance, risk data aggregation, and regulatory compliance.

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

7. Be precise about regulatory frameworks. Don't mark BCBS_239 unless the dataset is genuinely risk/market/regulatory data."""

METADATA_TOOL: Dict[str, Any] = {
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
            "description": {"type": "string", "description": "Clear dataset description (2-3 sentences)"},
            "business_context": {"type": "string", "description": "Business use, who uses it, how it fits the wider data landscape"},
            "data_domain": {"type": "string", "enum": [d.value for d in DataDomain]},
            "sub_domain": {"type": "string"},
            "classification": {"type": "string", "enum": [s.value for s in SensitivityLevel]},
            "data_classification_rationale": {"type": "string", "description": "Why this classification level was chosen"},
            "source_system": {"type": "string", "description": "Source system name if inferable"},
            "usage_guidance": {"type": "string", "description": "How to use this dataset, access requirements, join guidance"},
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
                        "display_name": {"type": "string", "description": "Human-readable name"},
                        "description": {"type": "string", "description": "Precise field description"},
                        "business_context": {"type": "string"},
                        "data_type": {"type": "string", "enum": [d.value for d in DataType]},
                        "format": {"type": "string", "description": "e.g. ISO 8601, UUID v4, ISO 4217"},
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


def _build_user_message(profile: DatasetProfile) -> str:
    return f"""Generate comprehensive banking-grade metadata for the following dataset.

{profile.to_prompt_context()}

Be precise about PII classification, sensitivity levels, and regulatory obligations.
For every field, write descriptions and business context that a data analyst can act on immediately.
Apply BCBS 239 lineage and quality principles where appropriate."""


def _parse_tool_result(raw: Dict[str, Any], dataset_name: str) -> DatasetMetadata:
    """Convert the raw tool-use output dict into a validated DatasetMetadata."""

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


class MetadataAgent:
    """Main agent. Call generate() with a DatasetProfile to get a DatasetMetadata."""

    def __init__(self, config: AgentConfig | None = None):
        self.config = config or AgentConfig()
        self.config.validate()
        self.client = anthropic.Anthropic(api_key=self.config.api_key)

    def generate(self, profile: DatasetProfile) -> tuple[DatasetMetadata, QualityScore]:
        """
        Generate metadata, apply guardrails, run evals.
        Returns (DatasetMetadata with quality_score populated, QualityScore).
        """
        user_message = _build_user_message(profile)

        response = self.client.messages.create(
            model=self.config.model,
            max_tokens=self.config.max_tokens,
            system=[
                {
                    "type": "text",
                    "text": SYSTEM_PROMPT,
                    # Cache the system prompt — it's large and reused across calls
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            messages=[{"role": "user", "content": user_message}],
            tools=[METADATA_TOOL],
            tool_choice={"type": "tool", "name": "generate_dataset_metadata"},
        )

        # Extract tool use block
        tool_block = next(
            (b for b in response.content if b.type == "tool_use"),
            None,
        )
        if not tool_block:
            raise RuntimeError("Agent did not return a tool_use block. Check model response.")

        raw = tool_block.input
        raw["dataset_name"] = profile.dataset_name

        metadata = _parse_tool_result(raw, profile.dataset_name)

        # Guardrails run first (fix issues before scoring)
        metadata, guardrail_messages = apply_all(metadata)

        # Evals run on the guardrailed output
        quality = run_evals(metadata, profile, guardrail_messages)
        metadata.quality_score = quality

        return metadata, quality
