"""
Pydantic models for banking metadata standards.

Aligned with: BCBS 239, UK GDPR, DAMA-DMBOK, ISO 8000, and
global bank data classification frameworks.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator, model_validator


class SensitivityLevel(str, Enum):
    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    RESTRICTED = "restricted"
    SECRET = "secret"

    @property
    def rank(self) -> int:
        return ["public", "internal", "confidential", "restricted", "secret"].index(self.value)


class PIIType(str, Enum):
    NAME = "name"
    EMAIL = "email"
    PHONE = "phone"
    ADDRESS = "address"
    DATE_OF_BIRTH = "date_of_birth"
    NATIONAL_ID = "national_id"           # NI number, SSN, passport
    ACCOUNT_NUMBER = "account_number"
    SORT_CODE = "sort_code"
    IBAN = "iban"
    CARD_NUMBER = "card_number"
    CVV = "cvv"
    TAX_ID = "tax_id"
    BIOMETRIC = "biometric"
    IP_ADDRESS = "ip_address"
    DEVICE_ID = "device_id"
    SPECIAL_CATEGORY = "special_category"  # GDPR Art. 9 - health, religion, ethnicity
    OTHER = "other"


class DataType(str, Enum):
    STRING = "string"
    INTEGER = "integer"
    DECIMAL = "decimal"
    BOOLEAN = "boolean"
    DATE = "date"
    DATETIME = "datetime"
    TIMESTAMP = "timestamp"
    JSON = "json"
    ARRAY = "array"
    BINARY = "binary"
    UUID = "uuid"
    CURRENCY_AMOUNT = "currency_amount"


class DataDomain(str, Enum):
    CUSTOMER = "customer"
    ACCOUNT = "account"
    TRANSACTION = "transaction"
    RISK = "risk"
    MARKET_DATA = "market_data"
    REFERENCE = "reference"
    REGULATORY = "regulatory"
    OPERATIONAL = "operational"
    FINANCIAL = "financial"
    COMPLIANCE = "compliance"


class RegulatoryFramework(str, Enum):
    GDPR = "GDPR"
    UK_GDPR = "UK_GDPR"
    BCBS_239 = "BCBS_239"
    MIFID_II = "MiFID_II"
    DORA = "DORA"
    BASEL_IV = "Basel_IV"
    PSD2 = "PSD2"
    CCPA = "CCPA"
    AML_6AMLD = "6AMLD"
    FCA_HANDBOOK = "FCA_Handbook"


class FieldConstraints(BaseModel):
    nullable: bool = True
    unique: bool = False
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    min_length: Optional[int] = None
    max_length: Optional[int] = None
    pattern: Optional[str] = None
    allowed_values: Optional[List[str]] = None
    foreign_key_ref: Optional[str] = None  # e.g., "customer.customer_id"
    precision: Optional[int] = None
    scale: Optional[int] = None


class FieldMetadata(BaseModel):
    name: str
    display_name: str
    description: str
    business_context: str
    data_type: DataType
    format: Optional[str] = None
    constraints: FieldConstraints = Field(default_factory=FieldConstraints)
    is_pii: bool
    pii_type: Optional[PIIType] = None
    sensitivity_level: SensitivityLevel
    is_key_field: bool = False
    usage_guidance: str
    example_usage: Optional[str] = None
    business_rules: Optional[str] = None
    data_lineage: Optional[str] = None
    quality_notes: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    guardrail_applied: Optional[str] = None

    @field_validator("pii_type")
    @classmethod
    def pii_type_required_when_is_pii(cls, v: Optional[PIIType], info: Any) -> Optional[PIIType]:
        if info.data.get("is_pii") and v is None:
            raise ValueError("pii_type must be specified when is_pii is True")
        return v

    @model_validator(mode="after")
    def pii_sensitivity_floor(self) -> "FieldMetadata":
        """Special category PII must never be below RESTRICTED."""
        if self.pii_type == PIIType.SPECIAL_CATEGORY:
            if self.sensitivity_level.rank < SensitivityLevel.RESTRICTED.rank:
                self.sensitivity_level = SensitivityLevel.RESTRICTED
        return self


class ComplianceInfo(BaseModel):
    gdpr_applicable: bool
    uk_gdpr_applicable: bool = False
    regulatory_frameworks: List[RegulatoryFramework] = Field(default_factory=list)
    data_residency_requirements: Optional[str] = None
    retention_period: Optional[str] = None
    cross_border_transfer_restrictions: bool = False
    consent_required: bool = False
    right_to_erasure_applicable: bool = False
    lawful_basis: Optional[str] = None  # e.g., "Legitimate interest", "Legal obligation"


class QualityDimension(BaseModel):
    score: float
    passed: bool
    issues: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)


class QualityScore(BaseModel):
    completeness: QualityDimension
    pii_detection: QualityDimension
    type_consistency: QualityDimension
    banking_standards: QualityDimension
    sensitivity_consistency: QualityDimension
    overall_score: float
    passed: bool
    guardrails_applied: List[str] = Field(default_factory=list)


class DatasetMetadata(BaseModel):
    # Identity
    dataset_name: str
    dataset_id: Optional[str] = None
    version: str = "1.0.0"

    # Description
    description: str
    business_context: str
    data_domain: DataDomain
    sub_domain: Optional[str] = None

    # Classification
    classification: SensitivityLevel
    data_classification_rationale: str

    # Ownership (optional - may not be inferable from schema alone)
    data_steward: Optional[str] = None
    data_owner: Optional[str] = None
    source_system: Optional[str] = None

    # Schema
    fields: List[FieldMetadata]
    row_count_estimate: Optional[int] = None

    # Compliance
    compliance: ComplianceInfo

    # Usage
    usage_guidance: str
    known_limitations: Optional[str] = None
    related_datasets: List[str] = Field(default_factory=list)

    # Quality
    quality_score: Optional[QualityScore] = None

    # Audit
    generated_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")
    generated_by: str = "Metadata Intelligence Agent v1.0"
    schema_version: str = "BANK-META-v2.0"

    @property
    def pii_fields(self) -> List[FieldMetadata]:
        return [f for f in self.fields if f.is_pii]

    @property
    def restricted_or_above(self) -> List[FieldMetadata]:
        return [
            f for f in self.fields
            if f.sensitivity_level.rank >= SensitivityLevel.RESTRICTED.rank
        ]


# ── Lineage models (DataLineageAgent output) ───────────────────────────────

class LineageSource(BaseModel):
    table: str
    column: str


class FieldLineage(BaseModel):
    target_field: str
    source_fields: List[LineageSource]
    transformation: Optional[str] = None      # e.g. "SUM(amount)", "CASE WHEN..."
    lineage_type: str = "direct"              # direct | derived | aggregated | constant
    confidence: str = "HIGH"                  # HIGH | MEDIUM | LOW
    bcbs_note: Optional[str] = None           # BCBS 239 principle annotation


class DatasetLineage(BaseModel):
    dataset_name: str
    source_sql: Optional[str] = None
    source_tables: List[str] = Field(default_factory=list)
    field_lineages: List[FieldLineage] = Field(default_factory=list)
    unresolved_fields: List[str] = Field(default_factory=list)
    bcbs_239_compliant: bool = False
    bcbs_notes: Optional[str] = None
    generated_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")
    generated_by: str = "lineage-agent v0.1"


# ── Quality models (DataQualityAgent output) ──────────────────────────────

class FieldExpectation(BaseModel):
    """A single Great Expectations-compatible expectation."""
    expectation_type: str             # e.g. expect_column_values_to_not_be_null
    kwargs: Dict[str, Any] = Field(default_factory=dict)


class FieldQualityResult(BaseModel):
    field_name: str
    completeness_score: float         # 0–100
    issues: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    expectations: List[FieldExpectation] = Field(default_factory=list)
    quality_notes: str = ""


class DamaDimension(BaseModel):
    """One of the six DAMA-DMBOK data quality dimensions."""
    score: float                      # 0–100
    issues: List[str] = Field(default_factory=list)
    notes: str = ""


class DataQualityReport(BaseModel):
    dataset_name: str
    overall_score: float
    passed: bool                      # overall_score >= 75
    dimensions: Dict[str, DamaDimension]  # completeness/consistency/accuracy/timeliness/uniqueness/validity
    field_quality: List[FieldQualityResult] = Field(default_factory=list)
    critical_issues: List[str] = Field(default_factory=list)
    recommendations: List[str] = Field(default_factory=list)
    generated_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")
    generated_by: str = "quality-agent v0.1"
