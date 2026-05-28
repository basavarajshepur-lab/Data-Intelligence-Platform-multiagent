"""
Metadata Intelligence Agent — Demo CLI

Usage:
    python demo.py samples/customer_accounts.csv
    python demo.py samples/transaction_schema.json
    python demo.py samples/risk_positions.sql
    python demo.py samples/customer_accounts.csv --output-dir outputs/
"""

import argparse
import json
import os
import sys
from pathlib import Path

import yaml
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table
from rich.text import Text
from rich import box

from src.agent import MetadataAgent
from src.config import AgentConfig
from src.extractors import extract
from src.schema import DatasetMetadata, QualityScore, SensitivityLevel

console = Console()


SENSITIVITY_COLORS = {
    "public": "green",
    "internal": "blue",
    "confidential": "yellow",
    "restricted": "red",
    "secret": "bold red",
}

PASS_FAIL = {True: "[bold green]PASS[/bold green]", False: "[bold red]FAIL[/bold red]"}


def _sensitivity_badge(level: SensitivityLevel) -> Text:
    color = SENSITIVITY_COLORS.get(level.value, "white")
    return Text(f" {level.value.upper()} ", style=f"bold {color} on black")


def print_header(dataset_name: str) -> None:
    console.print(
        Panel.fit(
            f"[bold cyan]Metadata Intelligence Agent[/bold cyan]\n"
            f"[dim]Banking-grade metadata generation with BCBS 239 evals and PII guardrails[/dim]\n"
            f"[bold]Dataset:[/bold] {dataset_name}",
            border_style="cyan",
        )
    )


def print_quality_report(quality: QualityScore, dataset_name: str) -> None:
    console.print("\n[bold]QUALITY EVALUATION REPORT[/bold]")

    score_table = Table(box=box.ROUNDED, show_header=True, header_style="bold cyan")
    score_table.add_column("Dimension", style="bold", width=28)
    score_table.add_column("Score", justify="right", width=10)
    score_table.add_column("Weight", justify="right", width=8)
    score_table.add_column("Status", justify="center", width=8)

    dimensions = [
        ("Completeness", quality.completeness, "30%"),
        ("PII Detection", quality.pii_detection, "25%"),
        ("Type Consistency", quality.type_consistency, "20%"),
        ("Banking Standards (BCBS 239)", quality.banking_standards, "15%"),
        ("Sensitivity Consistency", quality.sensitivity_consistency, "10%"),
    ]

    for name, dim, weight in dimensions:
        score_str = f"{dim.score:.1f}/100"
        status = PASS_FAIL[dim.passed]
        score_table.add_row(name, score_str, weight, status)

    console.print(score_table)

    overall_color = "green" if quality.passed else "red"
    console.print(
        f"\n  Overall Score: [{overall_color}]{quality.overall_score:.1f}/100[/{overall_color}]  "
        + PASS_FAIL[quality.passed]
    )

    if quality.guardrails_applied:
        console.print("\n[bold yellow]GUARDRAILS APPLIED[/bold yellow]")
        for msg in quality.guardrails_applied:
            console.print(f"  [yellow]⚑[/yellow] {msg}")

    all_issues = []
    all_warnings = []
    for _, dim, _ in dimensions:
        all_issues.extend(dim.issues)
        all_warnings.extend(dim.warnings)

    if all_issues:
        console.print("\n[bold red]ISSUES (must resolve)[/bold red]")
        for issue in all_issues:
            console.print(f"  [red]✗[/red] {issue}")

    if all_warnings:
        console.print("\n[bold yellow]WARNINGS[/bold yellow]")
        for warning in all_warnings[:8]:  # Limit display to 8
            console.print(f"  [yellow]⚠[/yellow] {warning}")
        if len(all_warnings) > 8:
            console.print(f"  [dim]...and {len(all_warnings) - 8} more (see full output file)[/dim]")


def print_pii_summary(metadata: DatasetMetadata) -> None:
    pii_fields = metadata.pii_fields
    if not pii_fields:
        console.print("\n[bold]PII SUMMARY[/bold]  [green]No PII fields detected[/green]")
        return

    console.print(f"\n[bold]PII SUMMARY[/bold]  [yellow]{len(pii_fields)} field(s) contain personal data[/yellow]")

    pii_table = Table(box=box.SIMPLE, show_header=True, header_style="dim")
    pii_table.add_column("Field", style="bold")
    pii_table.add_column("PII Type")
    pii_table.add_column("Sensitivity")
    pii_table.add_column("Guardrail Applied")

    for field in sorted(pii_fields, key=lambda f: f.sensitivity_level.rank, reverse=True):
        color = SENSITIVITY_COLORS.get(field.sensitivity_level.value, "white")
        sens_text = f"[{color}]{field.sensitivity_level.value.upper()}[/{color}]"
        pii_table.add_row(
            field.name,
            field.pii_type.value if field.pii_type else "—",
            sens_text,
            "[yellow]Yes[/yellow]" if field.guardrail_applied else "No",
        )

    console.print(pii_table)


def print_compliance_summary(metadata: DatasetMetadata) -> None:
    c = metadata.compliance
    console.print("\n[bold]COMPLIANCE FLAGS[/bold]")

    flags = [
        ("GDPR applicable", c.gdpr_applicable),
        ("UK GDPR applicable", c.uk_gdpr_applicable),
        ("Right to erasure applicable", c.right_to_erasure_applicable),
        ("Consent required", c.consent_required),
        ("Cross-border transfer restrictions", c.cross_border_transfer_restrictions),
    ]

    for label, value in flags:
        icon = "[yellow]⚑[/yellow]" if value else "[dim]○[/dim]"
        console.print(f"  {icon} {label}")

    if c.regulatory_frameworks:
        frameworks = ", ".join(f.value for f in c.regulatory_frameworks)
        console.print(f"\n  Regulatory frameworks: [cyan]{frameworks}[/cyan]")
    if c.retention_period:
        console.print(f"  Retention period: [cyan]{c.retention_period}[/cyan]")
    if c.data_residency_requirements:
        console.print(f"  Data residency: [cyan]{c.data_residency_requirements}[/cyan]")


def save_outputs(metadata: DatasetMetadata, output_dir: str) -> tuple[str, str]:
    os.makedirs(output_dir, exist_ok=True)
    base = metadata.dataset_name.replace(" ", "_").lower()

    yaml_path = os.path.join(output_dir, f"{base}_metadata.yaml")
    json_path = os.path.join(output_dir, f"{base}_metadata.json")

    data = json.loads(metadata.model_dump_json())

    with open(yaml_path, "w", encoding="utf-8") as f:
        yaml.dump(data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    return yaml_path, json_path


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Metadata Intelligence Agent — generate banking-grade metadata from datasets"
    )
    parser.add_argument("input", help="Path to input file (.csv, .json, .sql)")
    parser.add_argument(
        "--output-dir",
        default="outputs",
        help="Directory to save metadata files (default: outputs/)",
    )
    parser.add_argument(
        "--model",
        default="claude-sonnet-4-6",
        help="Claude model to use (default: claude-sonnet-4-6)",
    )
    args = parser.parse_args()

    if not os.path.exists(args.input):
        console.print(f"[red]Error: File not found: {args.input}[/red]")
        sys.exit(1)

    dataset_name = Path(args.input).stem
    print_header(dataset_name)

    # Step 1: Extract profile
    with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), console=console) as progress:
        task = progress.add_task("Extracting dataset profile...", total=None)
        try:
            profile = extract(args.input)
        except Exception as e:
            console.print(f"[red]Extraction failed: {e}[/red]")
            sys.exit(1)
        progress.update(task, description=f"[green]Profile extracted — {len(profile.fields)} fields[/green]")

    console.print(
        f"\n  Source: [cyan]{profile.source_type}[/cyan]  |  "
        f"Fields: [cyan]{len(profile.fields)}[/cyan]  |  "
        f"Rows: [cyan]{profile.row_count or 'schema only'}[/cyan]"
    )

    pii_hints = sum(1 for f in profile.fields if f.is_potential_pii)
    if pii_hints:
        console.print(f"  [yellow]⚑ {pii_hints} potential PII field(s) detected by heuristic — awaiting AI review[/yellow]")

    # Step 2: Generate metadata
    with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), console=console) as progress:
        task = progress.add_task("Generating metadata with Claude...", total=None)
        try:
            config = AgentConfig(model=args.model)
            agent = MetadataAgent(config)
            metadata, quality = agent.generate(profile)
        except EnvironmentError as e:
            console.print(f"\n[red]{e}[/red]")
            console.print("[dim]Set ANTHROPIC_API_KEY in your .env file or environment.[/dim]")
            sys.exit(1)
        except Exception as e:
            console.print(f"\n[red]Agent error: {e}[/red]")
            sys.exit(1)
        progress.update(task, description="[green]Metadata generated, guardrails applied, evals complete[/green]")

    # Step 3: Print reports
    console.print(
        f"\n  Dataset classification: "
        + str(_sensitivity_badge(metadata.classification))
        + f"  Domain: [cyan]{metadata.data_domain.value}[/cyan]"
    )

    print_quality_report(quality, dataset_name)
    print_pii_summary(metadata)
    print_compliance_summary(metadata)

    # Step 4: Save outputs
    yaml_path, json_path = save_outputs(metadata, args.output_dir)
    console.print(f"\n[bold green]Output saved:[/bold green]")
    console.print(f"  YAML: [cyan]{yaml_path}[/cyan]")
    console.print(f"  JSON: [cyan]{json_path}[/cyan]")

    if not quality.passed:
        console.print(
            "\n[bold red]Quality gate NOT passed.[/bold red] "
            "Review issues above before using this metadata in production."
        )
        sys.exit(2)
    else:
        console.print(
            f"\n[bold green]Quality gate passed[/bold green] "
            f"({quality.overall_score:.1f}/100). Metadata is ready for data catalogue ingestion."
        )


if __name__ == "__main__":
    main()
