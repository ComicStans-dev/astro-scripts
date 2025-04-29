#!/usr/bin/env python3
import os
import sys
import subprocess
import argparse
from dotenv import load_dotenv
import inspect
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import print as rprint

# Initialize rich console
console = Console()

# Parse command-line arguments
parser = argparse.ArgumentParser(description="Run all astro-session reporters.")
parser.add_argument('--debug', action='store_true', help='Enable debug output')
parser.add_argument('--reports-dir', help='Override REPORTS_DIR environment variable')
args = parser.parse_args()

# Display title - use a wider panel with explicit width
title_panel = Panel(
    "[bold blue]Astro Session Reporter[/]",
    subtitle="[italic]Analyzing astrophotography session data[/]",
    width=80
)
console.print(title_panel, justify="center")

# Calculate path to the parent directory where .env is stored
script_path = os.path.abspath(inspect.getfile(inspect.currentframe()))
script_dir = os.path.dirname(script_path)
parent_dir = os.path.dirname(script_dir)
env_path = os.path.join(parent_dir, ".env")

# Load environment variables from the correct location
env_loaded = load_dotenv(dotenv_path=env_path)

if args.debug:
    console.print(f"Loading .env from: [cyan]{env_path}[/] (success: [{'green' if env_loaded else 'red'}{env_loaded}[/])")

# Validate required environment variables
raw_dir = os.getenv("RAW_DIR") or os.getenv("DIRECTORY")
reports_dir = os.getenv("REPORTS_DIR")

# Allow command line override of reports_dir
if args.reports_dir:
    reports_dir = args.reports_dir
    console.print(f"Using reports directory from command line: [cyan]{reports_dir}[/]")

if not raw_dir:
    console.print("[bold red]ERROR:[/] RAW_DIR (or legacy DIRECTORY) environment variable not set")
    sys.exit(1)

# Print diagnostics to help debug path issues
console.print(f"Using RAW_DIR: [green]{raw_dir}[/]")
console.print(f"Using REPORTS_DIR: [green]{reports_dir or '[yellow](not set, will use RAW_DIR as fallback)[/]'}[/]")

# Scripts to run (relative to this directory)
scripts = [
    "altaz_stats_calculator.py",
    "autofocus_analysis.py",
    "phd2_error_anaylsis.py",
]

# Create a table to track script execution status
status_table = Table(title="Script Execution Status")
status_table.add_column("Script", style="cyan")
status_table.add_column("Status", style="green")

# Track statuses separately
statuses = ["Pending"] * len(scripts)
for i, script in enumerate(scripts):
    status_table.add_row(script, statuses[i])

console.print(status_table)

# Run each script in a separate subprocess to keep behaviour identical and
# ensure that running one script failing does not poison the state of others.

# Prepare environment for subprocess calls - ensure BOTH dirs are passed
env_vars = {**os.environ, "RAW_DIR": raw_dir}
if reports_dir:
    env_vars["REPORTS_DIR"] = reports_dir
    env_vars["FORCE_REPORTS_DIR"] = "1"  # Signal to downstream scripts to prioritize REPORTS_DIR

# Enable debug mode if requested
if args.debug:
    env_vars["DEBUG"] = "1"
    console.print("[bold yellow]Debug mode enabled[/]")

for i, script in enumerate(scripts):
    with console.status(f"[bold green]Running {script}...[/]"):
        console.print(f"\n[bold blue]=== Running {script} ===[/]")
        try:
            # Use full path to script
            script_path = os.path.join(script_dir, script)
            subprocess.run([sys.executable, script_path], env=env_vars, check=True)
            statuses[i] = "[green]Completed Successfully[/]"
        except subprocess.CalledProcessError as exc:
            console.print(f"[bold red][ERROR][/] {script} exited with status {exc.returncode}")
            statuses[i] = f"[red]Failed (Exit Code: {exc.returncode})[/]"
            # Continue to next script rather than aborting the entire pipeline
            continue

# Display final status
final_table = Table(title="Script Execution Status")
final_table.add_column("Script", style="cyan")
final_table.add_column("Status")

for i, script in enumerate(scripts):
    final_table.add_row(script, statuses[i])

console.print("\n[bold green]Final Status:[/]")
console.print(final_table)
console.print("\n[bold green]All processing complete![/]") 