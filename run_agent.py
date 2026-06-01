"""
Unified CLI runner for all agents.

Usage
-----
    python run_agent.py metadata  samples/customer_accounts.csv
    python run_agent.py metadata  samples/risk_positions.sql  --model claude-haiku-4-5-20251001

    python run_agent.py lineage   samples/risk_positions.sql
    python run_agent.py lineage   my_transform.sql  --output outputs/

    python run_agent.py quality   samples/customer_accounts.csv
    python run_agent.py quality   samples/kyc_screening_results.csv  --output outputs/

    python run_agent.py list      # show all available agents
"""

import argparse
import json
import os
import sys
from pathlib import Path

import yaml
from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

sys.path.insert(0, str(Path(__file__).parent))

from src.agents import DataQualityAgent, LineageAgent, MetadataAgent, list_agents
from src.config import AgentConfig
from src.extractors import extract

console = Console()


# ── Helpers ────────────────────────────────────────────────────────────────

def _save(data: dict, name: str, output_dir: str, suffix: str) -> str:
    os.makedirs(output_dir, exist_ok=True)
    path = os.path.join(output_dir, f"{name}_{suffix}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False, default=str)
    return path


def _save_yaml(data: dict, name: str, output_dir: str, suffix: str) -> str:
    os.makedirs(output_dir, exist_ok=True)
    path = os.path.join(output_dir, f"{name}_{suffix}.yaml")
    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
    return path


# ── list ───────────────────────────────────────────────────────────────────

def cmd_list() -> None:
    agents = list_agents()
    table = Table(title="Available Agents", box=box.ROUNDED, show_header=True, header_style="bold cyan")
    table.add_column("Name", style="bold")
    table.add_column("Status")
    table.add_column("Version")
    table.add_column("Model")
    table.add_column("Tools")
    table.add_column("Description")

    for a in agents:
        status_style = "green" if a["status"] == "active" else "yellow"
        table.add_row(
            a["name"],
            f"[{status_style}]{a['status']}[/{status_style}]",
            a["version"],
            a["model"],
            str(len(a["tools"])),
            a["description"],
        )
    console.print(table)


# ── metadata ───────────────────────────────────────────────────────────────

def cmd_metadata(input_path: str, model: str, output_dir: str) -> None:
    console.print(Panel.fit(
        f"[bold cyan]Metadata Agent[/bold cyan]\n[dim]{input_path}[/dim]",
        border_style="cyan",
    ))

    with console.status("Extracting profile..."):
        profile = extract(input_path)
    console.print(f"  Profile: [cyan]{len(profile.fields)} fields[/cyan]"
                  + (f", {profile.row_count} rows" if profile.row_count else ""))

    with console.status("Running agent (this takes 30–90 s)..."):
        agent = MetadataAgent(AgentConfig(model=model))
        metadata, quality = agent.generate(profile)

    status = "[green]PASS[/green]" if quality.passed else "[red]FAIL[/red]"
    console.print(f"\n  Quality: {quality.overall_score:.1f}/100 {status}"
                  f"  |  classification: [bold]{metadata.classification.value.upper()}[/bold]"
                  f"  |  PII fields: {len(metadata.pii_fields)}")

    data = json.loads(metadata.model_dump_json())
    j = _save(data, metadata.dataset_name, output_dir, "metadata")
    y = _save_yaml(data, metadata.dataset_name, output_dir, "metadata")
    console.print(f"\n  [green]Saved:[/green] {j}")
    console.print(f"  [green]Saved:[/green] {y}")


# ── lineage ────────────────────────────────────────────────────────────────

def cmd_lineage(sql_path: str, model: str, output_dir: str) -> None:
    if not sql_path.lower().endswith((".sql", ".ddl")):
        console.print("[red]Lineage agent requires a .sql or .ddl file.[/red]")
        sys.exit(1)

    console.print(Panel.fit(
        f"[bold cyan]Lineage Agent[/bold cyan]\n[dim]{sql_path}[/dim]",
        border_style="cyan",
    ))

    with console.status("Running agent..."):
        agent = LineageAgent(AgentConfig(model=model))
        lineage = agent.run(sql_path)

    bcbs = "[green]YES[/green]" if lineage.bcbs_239_compliant else "[yellow]PARTIAL[/yellow]"
    console.print(f"\n  Fields mapped:  [cyan]{len(lineage.field_lineages)}[/cyan]")
    console.print(f"  Source tables:  [cyan]{', '.join(lineage.source_tables) or 'none'}[/cyan]")
    console.print(f"  Unresolved:     [yellow]{len(lineage.unresolved_fields)}[/yellow]")
    console.print(f"  BCBS 239 compliant: {bcbs}")
    if lineage.bcbs_notes:
        console.print(f"  Notes: [dim]{lineage.bcbs_notes}[/dim]")

    # Field table
    table = Table(box=box.SIMPLE, header_style="dim")
    table.add_column("Target Field", style="bold")
    table.add_column("Type")
    table.add_column("Confidence")
    table.add_column("Sources")
    table.add_column("Transformation")
    for fl in lineage.field_lineages:
        srcs = ", ".join(f"{s.table}.{s.column}" for s in fl.source_fields) or "—"
        table.add_row(
            fl.target_field,
            fl.lineage_type,
            fl.confidence,
            srcs,
            (fl.transformation or "—")[:60],
        )
    console.print(table)

    data = json.loads(lineage.model_dump_json())
    j = _save(data, lineage.dataset_name, output_dir, "lineage")
    console.print(f"\n  [green]Saved:[/green] {j}")


# ── quality ────────────────────────────────────────────────────────────────

def cmd_quality(input_path: str, model: str, output_dir: str) -> None:
    console.print(Panel.fit(
        f"[bold cyan]Data Quality Agent[/bold cyan]\n[dim]{input_path}[/dim]",
        border_style="cyan",
    ))

    with console.status("Running agent..."):
        agent = DataQualityAgent(AgentConfig(model=model))
        report = agent.run(input_path)

    status = "[green]PASS[/green]" if report.passed else "[red]FAIL[/red]"
    console.print(f"\n  Overall score: [bold]{report.overall_score:.1f}/100[/bold] {status}")

    # Dimension table
    table = Table(box=box.ROUNDED, header_style="bold cyan")
    table.add_column("DAMA Dimension", style="bold")
    table.add_column("Score", justify="right")
    table.add_column("Status", justify="center")
    table.add_column("Top Issue")

    for dim_name, dim in report.dimensions.items():
        score_style = "green" if dim.score >= 75 else ("yellow" if dim.score >= 50 else "red")
        top_issue = dim.issues[0] if dim.issues else dim.notes or "—"
        table.add_row(
            dim_name.title(),
            f"[{score_style}]{dim.score:.0f}[/{score_style}]",
            "[green]PASS[/green]" if dim.score >= 75 else "[red]FAIL[/red]",
            top_issue[:70],
        )
    console.print(table)

    if report.critical_issues:
        console.print("\n[bold red]Critical issues:[/bold red]")
        for issue in report.critical_issues:
            console.print(f"  [red]✗[/red] {issue}")

    if report.recommendations:
        console.print("\n[bold yellow]Recommendations:[/bold yellow]")
        for rec in report.recommendations[:5]:
            console.print(f"  [yellow]→[/yellow] {rec}")

    # GE expectations summary
    total_expectations = sum(len(fq.expectations) for fq in report.field_quality)
    console.print(f"\n  Great Expectations rules generated: [cyan]{total_expectations}[/cyan]")

    data = json.loads(report.model_dump_json())
    j = _save(data, report.dataset_name, output_dir, "quality")
    console.print(f"  [green]Saved:[/green] {j}")


# ── Entry point ────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Metadata Intelligence Platform — run any agent from the CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "agent",
        choices=["metadata", "lineage", "quality", "list"],
        help="Agent to run",
    )
    parser.add_argument(
        "input",
        nargs="?",
        help="Input file path (.csv / .json / .sql)",
    )
    parser.add_argument(
        "--model",
        default="claude-sonnet-4-6",
        help="Claude model (default: claude-sonnet-4-6)",
    )
    parser.add_argument(
        "--output",
        default="outputs",
        help="Output directory (default: outputs/)",
    )
    args = parser.parse_args()

    if args.agent == "list":
        cmd_list()
        return

    if not args.input:
        console.print("[red]Error: input file is required for this agent.[/red]")
        sys.exit(1)

    if not Path(args.input).exists():
        console.print(f"[red]Error: file not found: {args.input}[/red]")
        sys.exit(1)

    if args.agent == "metadata":
        cmd_metadata(args.input, args.model, args.output)
    elif args.agent == "lineage":
        cmd_lineage(args.input, args.model, args.output)
    elif args.agent == "quality":
        cmd_quality(args.input, args.model, args.output)


if __name__ == "__main__":
    main()
