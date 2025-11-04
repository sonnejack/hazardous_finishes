#!/usr/bin/env python3
"""Minimal Typer test to isolate the issue."""

import typer

app = typer.Typer()

@app.command()
def test(
    name: str = typer.Option("world"),
    count: int = typer.Option(1)
):
    """Test command."""
    for _ in range(count):
        print(f"Hello {name}!")

if __name__ == "__main__":
    app()
