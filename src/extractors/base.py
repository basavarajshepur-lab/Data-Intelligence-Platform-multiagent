"""Base data profile model shared across all extractors."""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class FieldProfile:
    """Statistical profile of a single field extracted from a dataset."""

    name: str
    inferred_type: str            # pandas or schema-inferred type
    sample_values: List[str]      # Max 5 non-null samples (masked if PII-suspected)
    null_count: int = 0
    total_count: int = 0
    unique_count: Optional[int] = None
    min_value: Optional[Any] = None
    max_value: Optional[Any] = None
    avg_length: Optional[float] = None
    is_potential_pii: bool = False  # Heuristic flag before AI review
    potential_pii_type: Optional[str] = None
    extra: Dict[str, Any] = field(default_factory=dict)

    @property
    def null_rate(self) -> float:
        if self.total_count == 0:
            return 0.0
        return self.null_count / self.total_count

    @property
    def display_samples(self) -> List[str]:
        """Return masked samples for suspected PII fields."""
        if self.is_potential_pii:
            return ["[MASKED]"] * len(self.sample_values)
        return self.sample_values


@dataclass
class DatasetProfile:
    """Full profile of a dataset passed to the metadata agent."""

    source_file: str
    source_type: str              # "csv", "json_schema", "sql_ddl"
    dataset_name: str
    fields: List[FieldProfile]
    row_count: Optional[int] = None
    file_size_bytes: Optional[int] = None
    raw_schema: Optional[str] = None   # Original DDL or JSON schema string
    extra: Dict[str, Any] = field(default_factory=dict)

    def to_prompt_context(self) -> str:
        """Format profile as structured context for the Claude prompt."""
        lines = [
            f"Dataset: {self.dataset_name}",
            f"Source type: {self.source_type}",
            f"Row count: {self.row_count or 'unknown'}",
            f"Field count: {len(self.fields)}",
            "",
            "FIELDS:",
        ]

        for fp in self.fields:
            lines.append(f"\n  Field: {fp.name}")
            lines.append(f"    Inferred type: {fp.inferred_type}")
            lines.append(f"    Null rate: {fp.null_rate:.1%}")
            if fp.unique_count is not None:
                lines.append(f"    Unique values: {fp.unique_count}")
            if fp.min_value is not None:
                lines.append(f"    Min: {fp.min_value}  Max: {fp.max_value}")
            if fp.avg_length is not None:
                lines.append(f"    Avg length: {fp.avg_length:.1f} chars")
            samples = fp.display_samples
            if samples:
                lines.append(f"    Sample values: {', '.join(str(s) for s in samples[:5])}")
            if fp.is_potential_pii:
                lines.append(f"    *** Potential PII detected (heuristic): {fp.potential_pii_type} ***")

        if self.raw_schema:
            lines.extend(["", "ORIGINAL SCHEMA:", self.raw_schema])

        return "\n".join(lines)
