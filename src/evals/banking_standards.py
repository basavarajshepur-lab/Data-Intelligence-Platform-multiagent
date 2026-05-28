"""Banking Standards Eval (BCBS 239 + global bank data governance).

Checks compliance against:
- BCBS 239: accuracy, completeness, timeliness indicators, data lineage
- Internal data governance: key field identification, reconciliation support
- Classification completeness: all fields have a sensitivity level

BCBS 239 is the international standard for risk data aggregation and reporting,
directly relevant to any global systemically important bank (G-SIB).
"""

from typing import List

from ..config import BCBS_239_REQUIRED_FIELDS, EVAL_THRESHOLDS
from ..schema import DatasetMetadata, DataDomain, QualityDimension, SensitivityLevel


RISK_DOMAINS = {DataDomain.RISK, DataDomain.MARKET_DATA, DataDomain.REGULATORY, DataDomain.FINANCIAL}


def _check_bcbs239(metadata: DatasetMetadata) -> tuple[float, List[str], List[str]]:
    """BCBS 239 compliance checks. Returns (score_0_to_100, issues, warnings)."""
    score = 100.0
    issues: List[str] = []
    warnings: List[str] = []

    # Principle 2: Data accuracy — key fields should be identified
    key_fields = [f for f in metadata.fields if f.is_key_field]
    if not key_fields:
        warnings.append(
            "BCBS 239 P2 (Accuracy): No key fields identified — "
            "primary/foreign keys should be flagged for reconciliation support"
        )
        score -= 10

    # Principle 3: Completeness — data_lineage on at least 50% of fields
    lineage_count = sum(1 for f in metadata.fields if f.data_lineage and len(f.data_lineage) > 5)
    lineage_pct = lineage_count / len(metadata.fields) if metadata.fields else 0
    if lineage_pct < 0.5:
        warnings.append(
            f"BCBS 239 P3 (Completeness): Only {lineage_pct:.0%} of fields have data_lineage — "
            f"aim for >50% especially for risk datasets"
        )
        score -= 10

    # Principle 6: Adaptability — version field present
    if not metadata.version or metadata.version == "1.0.0":
        warnings.append(
            "BCBS 239 P6 (Adaptability): Version is at default 1.0.0 — "
            "ensure version is managed as schema evolves"
        )
        # Minor — no score deduction

    # Source system — critical for risk data lineage
    if not metadata.source_system:
        if metadata.data_domain in RISK_DOMAINS:
            issues.append(
                "BCBS 239 P3 (Data lineage): source_system missing for risk domain dataset — "
                "required for regulatory reporting traceability"
            )
            score -= 15
        else:
            warnings.append("source_system not specified — recommended for full data lineage")
            score -= 5

    # Regulatory frameworks must include BCBS_239 for risk domains
    from ..schema import RegulatoryFramework
    if metadata.data_domain in RISK_DOMAINS:
        if RegulatoryFramework.BCBS_239 not in metadata.compliance.regulatory_frameworks:
            issues.append(
                "BCBS 239 P1: Risk domain dataset should reference BCBS_239 in regulatory_frameworks"
            )
            score -= 10

    return max(score, 0.0), issues, warnings


def _check_classification(metadata: DatasetMetadata) -> tuple[float, List[str], List[str]]:
    """All fields must have explicit sensitivity classification."""
    score = 100.0
    issues: List[str] = []
    warnings: List[str] = []

    for field in metadata.fields:
        if field.sensitivity_level is None:
            issues.append(f"Field '{field.name}' has no sensitivity_level — required by data classification policy")
            score -= (100 / max(len(metadata.fields), 1))

    return max(score, 0.0), issues, warnings


def _check_gdpr_completeness(metadata: DatasetMetadata) -> tuple[float, List[str], List[str]]:
    """If PII fields exist, GDPR compliance info must be complete."""
    score = 100.0
    issues: List[str] = []
    warnings: List[str] = []

    has_pii = any(f.is_pii for f in metadata.fields)

    if has_pii:
        c = metadata.compliance
        if not c.gdpr_applicable and not c.uk_gdpr_applicable:
            issues.append(
                "GDPR: Dataset contains PII fields but neither GDPR nor UK GDPR is marked applicable"
            )
            score -= 20

        if not c.retention_period:
            warnings.append(
                "GDPR Art. 5(1)(e): retention_period not specified for a dataset containing PII"
            )
            score -= 10

        if not c.lawful_basis:
            warnings.append(
                "GDPR Art. 6: lawful_basis not specified for PII dataset — "
                "document legal basis (e.g., legal obligation, legitimate interest)"
            )
            score -= 10

    return max(score, 0.0), issues, warnings


def evaluate(metadata: DatasetMetadata) -> QualityDimension:
    all_issues: List[str] = []
    all_warnings: List[str] = []
    scores = []

    s, i, w = _check_bcbs239(metadata)
    scores.append(s)
    all_issues.extend(i)
    all_warnings.extend(w)

    s, i, w = _check_classification(metadata)
    scores.append(s)
    all_issues.extend(i)
    all_warnings.extend(w)

    s, i, w = _check_gdpr_completeness(metadata)
    scores.append(s)
    all_issues.extend(i)
    all_warnings.extend(w)

    avg_score = sum(scores) / len(scores)
    threshold = EVAL_THRESHOLDS["banking_standards"]

    return QualityDimension(
        score=round(avg_score, 1),
        passed=avg_score >= threshold and len(all_issues) == 0,
        issues=all_issues,
        warnings=all_warnings,
    )
