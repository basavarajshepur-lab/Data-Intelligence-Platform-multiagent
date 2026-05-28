"""CSV exporter — flat field inventory table for data catalogue ingestion or Excel review."""

import io

import pandas as pd

from ..schema import DatasetMetadata


def export(metadata: DatasetMetadata) -> bytes:
    rows = []
    for f in metadata.fields:
        c = f.constraints
        rows.append({
            "Field Name": f.name,
            "Display Name": f.display_name,
            "Data Type": f.data_type.value,
            "Format": f.format or "",
            "Is PII": "Yes" if f.is_pii else "No",
            "PII Type": f.pii_type.value if f.pii_type else "",
            "Sensitivity Level": f.sensitivity_level.value.upper(),
            "Is Key Field": "Yes" if f.is_key_field else "No",
            "Nullable": "Yes" if c.nullable else "No",
            "Unique": "Yes" if c.unique else "No",
            "Min Value": c.min_value if c.min_value is not None else "",
            "Max Value": c.max_value if c.max_value is not None else "",
            "Min Length": c.min_length if c.min_length is not None else "",
            "Max Length": c.max_length if c.max_length is not None else "",
            "Pattern": c.pattern or "",
            "Allowed Values": "; ".join(c.allowed_values) if c.allowed_values else "",
            "Foreign Key Ref": c.foreign_key_ref or "",
            "Description": f.description,
            "Business Context": f.business_context,
            "Usage Guidance": f.usage_guidance,
            "Business Rules": f.business_rules or "",
            "Data Lineage": f.data_lineage or "",
            "Quality Notes": f.quality_notes or "",
            "Tags": ", ".join(f.tags),
            "Guardrail Applied": "Yes" if f.guardrail_applied else "No",
        })

    buf = io.StringIO()
    # Dataset header block
    buf.write(f"# Metadata Intelligence Agent — {metadata.dataset_name}\n")
    buf.write(f"# Classification: {metadata.classification.value.upper()}\n")
    buf.write(f"# Domain: {metadata.data_domain.value}\n")
    buf.write(f"# Generated: {metadata.generated_at}\n")
    buf.write(f"# Schema version: {metadata.schema_version}\n")
    if metadata.quality_score:
        buf.write(f"# Quality score: {metadata.quality_score.overall_score}/100 — {'PASS' if metadata.quality_score.passed else 'FAIL'}\n")
    buf.write("\n")

    pd.DataFrame(rows).to_csv(buf, index=False)
    return buf.getvalue().encode("utf-8")
