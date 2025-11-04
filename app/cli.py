"""
Simple CLI using Click directly (no Typer) to avoid version conflicts.
"""

import click
import json
import sys
from pathlib import Path

from etl.load_csvs import ingest_all
from etl.validators import validate_all
from app.services.query import get_finish_code_tree, get_all_finish_codes, get_finish_code_specs, get_all_specifications


@click.group()
def cli():
    """Hazardous Finishes Data Engine CLI"""
    pass


@cli.command()
@click.option('--input-dir', default='data/inputs', help='Directory containing CSV files')
@click.option('--db', default='data/hazardous_finishes.sqlite', help='Path to SQLite database')
@click.option('--schema', default='db/schema.sql', help='Path to schema.sql file')
@click.option('--output', default=None, help='Path to write JSON ingestion report')
def ingest(input_dir, db, schema, output):
    """Ingest CSV files into SQLite database."""
    click.echo(f"\nIngesting CSV files from: {input_dir}")
    click.echo(f"Target database: {db}\n")

    try:
        report = ingest_all(input_dir, db, schema)

        if output is None:
            output_path = Path("data/outputs")
            output_path.mkdir(parents=True, exist_ok=True)
            output = str(output_path / "ingest_report.json")

        with open(output, "w") as f:
            json.dump(report, f, indent=2)

        click.secho("✓ Ingestion complete\n", fg='green', bold=True)
        click.echo(f"Status: {report['status']}")
        click.echo(f"Files loaded: {len(report['loaded_files'])}")

        if report['loaded_files']:
            click.echo("\nLoaded files:")
            for filename, info in report['loaded_files'].items():
                click.echo(f"  {filename}: {info['rows']} rows (SHA256: {info['sha256'][:16]}...)")

        val_report = report['validation_report']
        if val_report['status'] == 'pass':
            click.secho("\n✓ Validation passed", fg='green')
        elif val_report['status'] == 'warnings':
            click.secho(f"\n⚠ Validation passed with {val_report['warning_count']} warning(s)", fg='yellow')
        else:
            click.secho(f"\n✗ Validation failed with {val_report['error_count']} error(s)", fg='red')

        click.echo(f"\nFull report written to: {output}\n")

        if report['status'] == 'failed':
            sys.exit(1)

    except Exception as e:
        click.secho(f"Error: {e}", fg='red', err=True)
        sys.exit(1)


@cli.command()
@click.option('--db', default='data/hazardous_finishes.sqlite', help='Path to SQLite database')
def validate(db):
    """Run validation checks on database."""
    click.echo(f"\nValidating database: {db}\n")

    try:
        import sqlite3
        conn = sqlite3.connect(db)
        report = validate_all(conn)
        conn.close()

        click.echo(f"Status: {report['status']}")
        click.echo(f"Errors: {report['error_count']}")
        click.echo(f"Warnings: {report['warning_count']}\n")

        if report['errors']:
            click.secho("Errors:", fg='red', bold=True)
            for error in report['errors']:
                click.echo(f"  • [{error['table']}.{error['column']}] {error['issue']}: {error['details']}")

        if report['warnings']:
            click.secho("\nWarnings:", fg='yellow', bold=True)
            for warning in report['warnings']:
                click.echo(f"  • [{warning['table']}.{warning['column']}] {warning['issue']}: {warning['details']}")

        if report['status'] == 'pass':
            click.secho("\n✓ All validation checks passed\n", fg='green')
        elif report['status'] == 'warnings':
            click.secho("\n⚠ Validation passed with warnings\n", fg='yellow')
        else:
            click.secho("\n✗ Validation failed\n", fg='red')
            sys.exit(1)

    except Exception as e:
        click.secho(f"Error: {e}", fg='red', err=True)
        sys.exit(1)


@cli.command()
@click.argument('finish_code')
@click.option('--db', default='data/hazardous_finishes.sqlite', help='Path to SQLite database')
@click.option('--output', default=None, help='Write output to JSON file')
@click.option('--compact', is_flag=True, help='Compact JSON output')
def show(finish_code, db, output, compact):
    """Display full finish code hierarchy as JSON."""
    try:
        result = get_finish_code_tree(finish_code, db)

        indent = None if compact else 2
        json_str = json.dumps(result, indent=indent)

        if output:
            with open(output, "w") as f:
                f.write(json_str)
            click.secho(f"✓ Output written to: {output}", fg='green')
        else:
            click.echo(json_str)

        if "error" in result:
            sys.exit(1)

    except Exception as e:
        click.secho(f"Error: {e}", fg='red', err=True)
        sys.exit(1)


@cli.command()
@click.argument('finish_code')
@click.option('--db', default='data/hazardous_finishes.sqlite', help='Path to SQLite database')
@click.option('--output', default=None, help='Write output to JSON file')
@click.option('--compact', is_flag=True, help='Compact JSON output')
def specs(finish_code, db, output, compact):
    """List all unique specifications for a finish code."""
    try:
        result = get_finish_code_specs(finish_code, db)

        if output:
            indent = None if compact else 2
            with open(output, "w") as f:
                json.dump(result, f, indent=indent)
            click.secho(f"✓ Output written to: {output}", fg='green')
            return

        if "error" in result:
            click.secho(f"Error: {result['error']}", fg='red')
            if "available_codes" in result:
                click.echo("\nAvailable finish codes:")
                for code in result["available_codes"]:
                    click.echo(f"  {code}")
            sys.exit(1)

        # Display results in human-readable format
        click.echo(f"\nSpecifications for finish code: {click.style(result['finish_code'], bold=True)}")
        click.echo(f"Total unique specifications: {result['spec_count']}\n")

        if result['specifications']:
            click.secho("Unique Specifications:", fg='cyan', bold=True)
            for spec in result['specifications']:
                click.echo(f"  • {spec}")

            if result['steps_with_specs']:
                click.echo(f"\n{click.style('Used in SFT Steps:', fg='cyan', bold=True)}")
                for step in result['steps_with_specs']:
                    # Check if this step has multiple alternative specs
                    spec_list = step.get('associated_specs_list', [])
                    if len(spec_list) > 1:
                        # Multiple specs = alternatives (OR relationship)
                        click.echo(f"  [{step['step_order']}] {step['sft_code']:15s} → Any of:")
                        for spec in spec_list:
                            click.echo(f"      • {spec}")
                    else:
                        # Single spec
                        click.echo(f"  [{step['step_order']}] {step['sft_code']:15s} → {step['associated_specs']}")
                    click.echo(f"      {click.style(step['description'], dim=True)}")
        else:
            click.secho("No specifications found for this finish code.", fg='yellow')

        click.echo()

    except Exception as e:
        click.secho(f"Error: {e}", fg='red', err=True)
        sys.exit(1)


@cli.command()
@click.option('--db', default='data/hazardous_finishes.sqlite', help='Path to SQLite database')
@click.option('--format', 'output_format', type=click.Choice(['table', 'csv', 'json'], case_sensitive=False),
              default='table', help='Output format')
@click.option('--output', default=None, help='Write output to file')
def list_specs(db, output_format, output):
    """List all unique specifications across all finish codes."""
    try:
        result = get_all_specifications(db)

        if output_format == 'json':
            # JSON output
            json_str = json.dumps(result, indent=2)
            if output:
                with open(output, 'w') as f:
                    f.write(json_str)
                click.secho(f"✓ JSON written to: {output}", fg='green')
            else:
                click.echo(json_str)

        elif output_format == 'csv':
            # CSV output - ready for materials mapping
            import csv
            import io

            csv_buffer = io.StringIO()
            writer = csv.writer(csv_buffer)

            # Header
            writer.writerow(['specification', 'usage_count', 'sft_codes', 'finish_codes'])

            # Data rows
            for spec_data in result['specifications']:
                writer.writerow([
                    spec_data['spec'],
                    spec_data['usage_count'],
                    ';'.join(spec_data['sft_codes']),
                    ';'.join(spec_data['finish_codes'][:5]) + ('...' if len(spec_data['finish_codes']) > 5 else '')
                ])

            csv_output = csv_buffer.getvalue()

            if output:
                with open(output, 'w') as f:
                    f.write(csv_output)
                click.secho(f"✓ CSV written to: {output}", fg='green')
            else:
                click.echo(csv_output)

        else:
            # Table output (default)
            click.echo(f"\n{click.style('All Specifications', fg='cyan', bold=True)}")
            click.echo(f"Total unique specifications: {result['total_specs']}\n")

            if result['specifications']:
                for spec_data in result['specifications']:
                    click.echo(f"{click.style(spec_data['spec'], bold=True)}")
                    click.echo(f"  Used in: {spec_data['usage_count']} finish codes")
                    click.echo(f"  SFT steps: {', '.join(spec_data['sft_codes'][:5])}")
                    if len(spec_data['sft_codes']) > 5:
                        click.echo(f"             ... and {len(spec_data['sft_codes']) - 5} more")
                    click.echo()
            else:
                click.secho("No specifications found in database.", fg='yellow')

    except Exception as e:
        click.secho(f"Error: {e}", fg='red', err=True)
        import traceback
        traceback.print_exc()
        sys.exit(1)


@cli.command()
@click.option('--db', default='data/hazardous_finishes.sqlite', help='Path to SQLite database')
def list_codes(db):
    """List all finish codes in database."""
    click.echo(f"\nFinish codes in database: {db}\n")

    try:
        codes = get_all_finish_codes(db)

        if not codes:
            click.secho("No finish codes found in database", fg='yellow')
            click.echo("Run 'hazard-cli ingest' to load data\n")
            return

        click.echo(f"Found {len(codes)} finish codes:\n")
        for code in codes:
            click.echo(f"  {code['code']:10s}  {code['substrate']:12s}  {code['finish_applied']:12s}  {code['description'] or ''}")
        click.echo()

    except Exception as e:
        click.secho(f"Error: {e}", fg='red', err=True)
        sys.exit(1)


@cli.command()
@click.argument('finish_code')
@click.option('--db', default='data/hazardous_finishes.sqlite', help='Path to SQLite database')
def tree(finish_code, db):
    """Display finish code hierarchy as readable tree."""
    try:
        result = get_finish_code_tree(finish_code, db)

        if "error" in result:
            click.secho(f"Error: {result['error']}", fg='red')
            if "available_codes" in result:
                click.echo("\nAvailable finish codes:")
                for code in result["available_codes"]:
                    click.echo(f"  {code}")
            sys.exit(1)

        # Display tree
        parsed = result['parsed']
        click.echo(f"\n{click.style(result['finish_code'], fg='cyan', bold=True)}: {parsed['finish_description']}")
        click.echo(f"├─ Substrate: {parsed['substrate']['code']} - {parsed['substrate']['description'][:60]}")
        click.echo(f"├─ Finish Applied: {parsed['finish_applied']['code']} - {parsed['finish_applied']['description'][:60]}")
        click.echo(f"└─ Sequence ID: {parsed['seq_id']}")

        click.echo(f"\n{click.style('Process Steps:', fg='yellow', bold=True)}")

        for i, step in enumerate(result['steps']):
            is_last_step = (i == len(result['steps']) - 1)
            step_prefix = "└─" if is_last_step else "├─"
            indent = "   " if is_last_step else "│  "

            step_title = f'Step {step["step_order"]}: {step["sft_code"]}'
            click.echo(f"\n{step_prefix} {click.style(step_title, bold=True)}")
            click.echo(f"{indent} Group: {step['parent_group'] or 'N/A'}")
            click.echo(f"{indent} Description: {step['description'][:70]}")

            if step['associated_specs']:
                specs = [s.strip() for s in step['associated_specs'].split(',')]
                if len(specs) > 1:
                    specs_title = click.style('Specifications (any of):', fg='green')
                else:
                    specs_title = click.style('Specification:', fg='green')
                click.echo(f"{indent} {specs_title}")
                for spec in specs:
                    click.echo(f"{indent}   • {spec}")

            if step['materials']:
                materials_title = click.style('Materials:', fg='magenta')
                click.echo(f"{indent} {materials_title}")
                for mat in step['materials']:
                    mat_variant = (' ' + mat['variant']) if mat['variant'] else ''
                    click.echo(f"{indent}   • {mat['base_spec']}{mat_variant}")

                    if mat['chemicals']:
                        for chem in mat['chemicals']:
                            hazard = f" [Hazard Level {chem['default_hazard_level']}]" if chem['default_hazard_level'] else ""
                            click.echo(f"{indent}     - {chem['name']}{hazard}")
            else:
                no_materials_msg = click.style('Materials: (not loaded yet)', dim=True)
                click.echo(f"{indent} {no_materials_msg}")

        click.echo()

    except Exception as e:
        click.secho(f"Error: {e}", fg='red', err=True)
        import traceback
        traceback.print_exc()
        sys.exit(1)


@cli.command()
def version():
    """Display version information."""
    click.echo("\nHazardous Finishes Data Engine")
    click.echo("Version: 0.1.0")
    click.echo(f"Python: {sys.version.split()[0]}\n")


if __name__ == '__main__':
    cli()
