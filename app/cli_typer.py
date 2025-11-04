"""
Command-line interface for hazardous finishes data engine.

Provides commands for:
- CSV ingestion
- Data validation
- Finish code queries
- Data exploration
"""

import json
import sys
from pathlib import Path
from typing import Optional

import typer
from rich import print as rprint
from rich.console import Console
from rich.table import Table

from etl.load_csvs import ingest_all
from etl.validators import validate_all
from app.services.query import get_finish_code_tree, get_all_finish_codes

# Initialize Typer app
app = typer.Typer(
    name="hazard-cli",
    help="Hazardous Finishes Data Engine CLI",
    add_completion=False
)

console = Console()


@app.command()
def ingest(
    input_dir: str = typer.Option(
        default="data/inputs",
        help="Directory containing CSV files"
    ),
    db: str = typer.Option(
        default="db/engine.sqlite",
        help="Path to SQLite database"
    ),
    schema: str = typer.Option(
        default="db/schema.sql",
        help="Path to schema.sql file"
    ),
    output_report: Optional[str] = typer.Option(
        default=None,
        help="Path to write JSON ingestion report (default: data/outputs/ingest_report.json)"
    )
):
    """
    Ingest CSV files into SQLite database.

    Loads all CSV files from INPUT_DIR into database at DB path.
    Records SHA256 hashes and row counts for lineage tracking.
    Runs validation checks after ingestion.

    Example:
        hazard-cli ingest --input data/inputs --db db/engine.sqlite
    """
    console.print(f"\n[bold blue]Ingesting CSV files from:[/bold blue] {input_dir}")
    console.print(f"[bold blue]Target database:[/bold blue] {db}\n")

    try:
        # Run ingestion
        report = ingest_all(input_dir, db, schema)

        # Determine output path
        if output_report is None:
            output_path = Path("data/outputs")
            output_path.mkdir(parents=True, exist_ok=True)
            output_report = str(output_path / "ingest_report.json")

        # Write report
        with open(output_report, "w") as f:
            json.dump(report, f, indent=2)

        # Display summary
        console.print("[bold green]✓ Ingestion complete[/bold green]\n")

        console.print(f"[bold]Status:[/bold] {report['status']}")
        console.print(f"[bold]Files loaded:[/bold] {len(report['loaded_files'])}")

        if report['loaded_files']:
            table = Table(title="Loaded Files")
            table.add_column("File", style="cyan")
            table.add_column("Rows", justify="right", style="magenta")
            table.add_column("SHA256", style="dim")

            for filename, info in report['loaded_files'].items():
                table.add_row(filename, str(info['rows']), info['sha256'][:16] + "...")

            console.print(table)

        # Display validation results
        val_report = report['validation_report']
        if val_report['status'] == 'pass':
            console.print("\n[bold green]✓ Validation passed[/bold green]")
        elif val_report['status'] == 'warnings':
            console.print(f"\n[bold yellow]⚠ Validation passed with {val_report['warning_count']} warning(s)[/bold yellow]")
            for warning in val_report['warnings']:
                console.print(f"  [yellow]WARNING:[/yellow] {warning['details']}")
        else:
            console.print(f"\n[bold red]✗ Validation failed with {val_report['error_count']} error(s)[/bold red]")
            for error in val_report['errors']:
                console.print(f"  [red]ERROR:[/red] {error['details']}")

        # Display ingestion errors
        if report['errors']:
            console.print(f"\n[bold red]Ingestion errors:[/bold red]")
            for error in report['errors']:
                console.print(f"  [red]{error['file']}:[/red] {error['error']}")

        console.print(f"\n[dim]Full report written to: {output_report}[/dim]\n")

        # Exit with error code if ingestion failed
        if report['status'] == 'failed':
            sys.exit(1)

    except FileNotFoundError as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        sys.exit(1)
    except Exception as e:
        console.print(f"[bold red]Unexpected error:[/bold red] {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


@app.command()
def validate(
    db: str = typer.Option(
        default="db/engine.sqlite",
        help="Path to SQLite database"
    )
):
    """
    Run validation checks on database.

    Validates:
    - Referential integrity (foreign keys)
    - Completeness (required fields)
    - Data formats (CAS numbers, JSON, ranges)

    Example:
        hazard-cli validate --db db/engine.sqlite
    """
    console.print(f"\n[bold blue]Validating database:[/bold blue] {db}\n")

    try:
        import sqlite3
        conn = sqlite3.connect(db)

        report = validate_all(conn)
        conn.close()

        # Display results
        console.print(f"[bold]Status:[/bold] {report['status']}")
        console.print(f"[bold]Errors:[/bold] {report['error_count']}")
        console.print(f"[bold]Warnings:[/bold] {report['warning_count']}\n")

        if report['errors']:
            console.print("[bold red]Errors:[/bold red]")
            for error in report['errors']:
                console.print(f"  • [{error['table']}.{error['column']}] {error['issue']}: {error['details']}")

        if report['warnings']:
            console.print("\n[bold yellow]Warnings:[/bold yellow]")
            for warning in report['warnings']:
                console.print(f"  • [{warning['table']}.{warning['column']}] {warning['issue']}: {warning['details']}")

        if report['status'] == 'pass':
            console.print("\n[bold green]✓ All validation checks passed[/bold green]\n")
        elif report['status'] == 'warnings':
            console.print("\n[bold yellow]⚠ Validation passed with warnings[/bold yellow]\n")
        else:
            console.print("\n[bold red]✗ Validation failed[/bold red]\n")
            sys.exit(1)

    except FileNotFoundError:
        console.print(f"[bold red]Error:[/bold red] Database not found: {db}")
        sys.exit(1)
    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


@app.command()
def show(
    finish_code: str = typer.Argument(..., help="Finish code to query (e.g., BP27)"),
    db: str = typer.Option(
        default="db/engine.sqlite",
        help="Path to SQLite database"
    ),
    output: Optional[str] = typer.Option(
        default=None,
        help="Write output to JSON file instead of stdout"
    ),
    compact: bool = typer.Option(
        default=False,
        help="Compact JSON output (no pretty-printing)"
    )
):
    """
    Display full finish code hierarchy as JSON.

    Returns complete tree with:
    - Parsed code components (substrate, finish, seq_id)
    - Ordered SFT steps
    - Materials per step
    - Chemicals with hazard flags and weight percentages
    - Provenance (CSV SHAs, load timestamps)

    Example:
        hazard-cli show BP27
        hazard-cli show BP27 --output output.json
    """
    try:
        result = get_finish_code_tree(finish_code, db)

        # Format JSON
        json_str = json.dumps(result, indent=None if compact else 2)

        if output:
            with open(output, "w") as f:
                f.write(json_str)
            console.print(f"[bold green]✓ Output written to:[/bold green] {output}")
        else:
            # Print to stdout (without Rich formatting for clean JSON)
            print(json_str)

        # Exit with error if finish code not found
        if "error" in result:
            sys.exit(1)

    except FileNotFoundError:
        console.print(f"[bold red]Error:[/bold red] Database not found: {db}")
        console.print(f"[dim]Run 'hazard-cli ingest' first to load data[/dim]")
        sys.exit(1)
    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


@app.command()
def list_codes(
    db: str = typer.Option(
        default="db/engine.sqlite",
        help="Path to SQLite database"
    )
):
    """
    List all finish codes in database.

    Example:
        hazard-cli list-codes
    """
    console.print(f"\n[bold blue]Finish codes in database:[/bold blue] {db}\n")

    try:
        codes = get_all_finish_codes(db)

        if not codes:
            console.print("[yellow]No finish codes found in database[/yellow]")
            console.print("[dim]Run 'hazard-cli ingest' to load data[/dim]\n")
            return

        table = Table(title=f"Finish Codes ({len(codes)} total)")
        table.add_column("Code", style="cyan", no_wrap=True)
        table.add_column("Substrate", style="green")
        table.add_column("Finish", style="magenta")
        table.add_column("Seq", justify="right", style="yellow")
        table.add_column("Description", style="dim")

        for code in codes:
            table.add_row(
                code['code'],
                code['substrate'],
                code['finish_applied'],
                str(code['seq_id']),
                code['description'] or ""
            )

        console.print(table)
        console.print()

    except FileNotFoundError:
        console.print(f"[bold red]Error:[/bold red] Database not found: {db}")
        sys.exit(1)
    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        sys.exit(1)


@app.command()
def version():
    """Display version information."""
    from app import __version__ as app_version
    console.print(f"\n[bold]Hazardous Finishes Data Engine[/bold]")
    console.print(f"Version: {app_version}")
    console.print(f"Python: {sys.version.split()[0]}\n")


if __name__ == "__main__":
    app()
