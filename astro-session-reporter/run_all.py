#!/usr/bin/env python3
import os
import sys
import subprocess
import argparse
import pandas as pd
from dotenv import load_dotenv
import inspect
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import print as rprint
from datetime import datetime

# Import the refactored function
from altaz_stats_calculator import generate_altaz_stats_df
from phd2_error_anaylsis import generate_phd2_analysis_data
from autofocus_analysis import generate_event_dataframes
from final_output.generate_unified_csv import generate_unified_dataframe

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
    color = 'green' if env_loaded else 'red'
    console.print(f"Loading .env from: [cyan]{env_path}[/] (success: [{color}]{env_loaded}[/{color}])")

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

# --- Data collection for Excel --- 
excel_sheets_data = {}
# --- 

# Scripts to run (relative to this directory)
# We will modify this list as we refactor each script
scripts_to_run_as_subprocess = [
    # "altaz_stats_calculator.py", # Will be called directly
    # "autofocus_analysis.py", # Will be called directly
    # "phd2_error_anaylsis.py", # Will be called directly
    # os.path.join("final_output", "generate_unified_csv.py"), # Will be called directly
]

# Original list for status display, including all scripts
all_scripts_display_names = [
    "altaz_stats_calculator.py",
    "autofocus_analysis.py",
    "phd2_error_anaylsis.py",
    os.path.join("final_output", "generate_unified_csv.py"),
]

# Create a table to track script execution status
status_table = Table(title="Script Execution Status")
status_table.add_column("Script", style="cyan")
status_table.add_column("Status", style="green")

# Track statuses separately
statuses = {name: "Pending" for name in all_scripts_display_names}
for script_name in all_scripts_display_names:
    status_table.add_row(script_name, statuses[script_name])

console.print(status_table)

# Prepare environment for subprocess calls - ensure BOTH dirs are passed
env_vars = {**os.environ, "RAW_DIR": raw_dir}
if reports_dir:
    env_vars["REPORTS_DIR"] = reports_dir
    env_vars["FORCE_REPORTS_DIR"] = "1"  # Signal to downstream scripts to prioritize REPORTS_DIR

# Enable debug mode if requested
if args.debug:
    env_vars["DEBUG"] = "1"
    console.print("[bold yellow]Debug mode enabled[/]")

# --- 1. Run Alt/Az Stats Calculator --- 
script_name_altaz = "altaz_stats_calculator.py"
console.print(f"\n[bold blue]=== Running {script_name_altaz} (imported) ===[/]")
try:
    with console.status(f"[bold green]Running {script_name_altaz}...[/]"):
        altaz_df, first_fits_header_df = generate_altaz_stats_df()
        
        # Process AltAz Stats DF
        if not altaz_df.empty:
            excel_sheets_data["AltAz_Stats"] = altaz_df
            console.print(f"[green]  -> {script_name_altaz} (Stats) completed. DataFrame shape: {altaz_df.shape}[/]")
            if args.debug:
                console.print("  AltAz Stats DataFrame Head:")
                console.print(altaz_df.head().to_string())
        else:
            console.print(f"[yellow]  -> {script_name_altaz} (Stats) completed but returned an empty DataFrame.[/]")
        
        # Process First FITS Header DF
        if not first_fits_header_df.empty:
            excel_sheets_data["First_FITS_Header"] = first_fits_header_df
            console.print(f"[green]  -> {script_name_altaz} (First FITS Header) completed. DataFrame shape: {first_fits_header_df.shape}[/]")
            if args.debug:
                console.print("  First FITS Header DataFrame Head:")
                console.print(first_fits_header_df.head().to_string())
        else:
             console.print(f"[yellow]  -> {script_name_altaz} (First FITS Header) completed but returned an empty DataFrame.[/]")

        statuses[script_name_altaz] = "[green]Completed Successfully (Imported)[/green]"
except Exception as e:
    console.print(f"[bold red][ERROR][/] running {script_name_altaz} (imported): {e}")
    statuses[script_name_altaz] = f"[red]Failed (Imported): {e}[/red]"

# --- 2. Run PHD2 Error Analysis --- 
script_name_phd2 = "phd2_error_anaylsis.py"
console.print(f"\n[bold blue]=== Running {script_name_phd2} (imported) ===[/]")
try:
    with console.status(f"[bold green]Running {script_name_phd2}...[/]"):
        phd2_results_df, phd2_summary_df, first_phd2_header_df = generate_phd2_analysis_data()
        
        # Process PHD2 Per Image Stats DF
        if not phd2_results_df.empty:
            excel_sheets_data["PHD2_Per_Image_Stats"] = phd2_results_df
            console.print(f"[green]  -> {script_name_phd2} (Per Image) completed. DataFrame shape: {phd2_results_df.shape}[/]")
            if args.debug:
                console.print("  Per Image Results DataFrame Head:")
                console.print(phd2_results_df.head().to_string())
        else:
            console.print(f"[yellow]  -> {script_name_phd2} (Per Image) completed but returned an empty DataFrame.[/]")

        # Process PHD2 Overall Summary DF
        if not phd2_summary_df.empty:
            excel_sheets_data["PHD2_Overall_Summary"] = phd2_summary_df
            console.print(f"[green]  -> {script_name_phd2} (Overall Summary) completed. DataFrame shape: {phd2_summary_df.shape}[/]")
            if args.debug:
                console.print("  Overall Summary DataFrame:")
                console.print(phd2_summary_df.to_string())
        else:
            console.print(f"[yellow]  -> {script_name_phd2} (Overall Summary) completed but returned an empty DataFrame.[/]")
        
        # Process First PHD2 Header DF
        if not first_phd2_header_df.empty:
            excel_sheets_data["PHD2_Log_Header"] = first_phd2_header_df
            console.print(f"[green]  -> {script_name_phd2} (PHD2 Log Header) completed. DataFrame shape: {first_phd2_header_df.shape}[/]")
            if args.debug:
                console.print("  PHD2 Log Header DataFrame Head:")
                console.print(first_phd2_header_df.head().to_string())
        else:
            console.print(f"[yellow]  -> {script_name_phd2} (PHD2 Log Header) completed but returned an empty DataFrame.[/]")

        statuses[script_name_phd2] = "[green]Completed Successfully (Imported)[/green]"
except Exception as e:
    console.print(f"[bold red][ERROR][/] running {script_name_phd2} (imported): {e}")
    statuses[script_name_phd2] = f"[red]Failed (Imported): {e}[/red]"

# --- 3. Run Autofocus Analysis (Event Extraction) --- 
script_name_autofocus = "autofocus_analysis.py"
console.print(f"\n[bold blue]=== Running {script_name_autofocus} (imported) ===[/]")
try:
    with console.status(f"[bold green]Running {script_name_autofocus}...[/]"):
        event_dfs_dict = generate_event_dataframes()
        if event_dfs_dict:
            console.print(f"[green]  -> {script_name_autofocus} completed. Found {len(event_dfs_dict)} event types.[/]")
            for event_type, df in event_dfs_dict.items():
                sheet_name = event_type.replace('_', ' ').title().replace(' ', '') + "_Events"
                if df.empty:
                    console.print(f"[yellow]    - Event type '{event_type}' is empty, skipping sheet.[/]")
                    continue
                excel_sheets_data[sheet_name] = df
                console.print(f"[green]    - Added sheet: '{sheet_name}', DataFrame shape: {df.shape}[/]")
                if args.debug:
                    console.print(f"      DataFrame Head for {sheet_name}:")
                    console.print(df.head().to_string())
        else:
            console.print(f"[yellow]  -> {script_name_autofocus} completed but returned no event DataFrames.[/]")
        statuses[script_name_autofocus] = "[green]Completed Successfully (Imported)[/green]"
except Exception as e:
    console.print(f"[bold red][ERROR][/] running {script_name_autofocus} (imported): {e}")
    statuses[script_name_autofocus] = f"[red]Failed (Imported): {e}[/red]"

# --- 4. Run Unified CSV Generation --- 
script_name_unified = os.path.join("final_output", "generate_unified_csv.py")
# Normalize display name for dictionary key consistency
script_display_name_unified = os.path.normpath(script_name_unified)

console.print(f"\n[bold blue]=== Running {script_display_name_unified} (imported) ===[/]")
try:
    with console.status(f"[bold green]Running {script_display_name_unified}...[/]"):
        # The RAW_DIR for generate_unified_dataframe will be implicitly set 
        # by the environment variable passed from run_all.py to its child processes/imports.
        # If generate_unified_dataframe needs specific data from other DFs collected in run_all.py,
        # those would need to be passed as arguments here.
        # For now, it does its own parsing based on RAW_DIR.
        unified_df = generate_unified_dataframe(raw_dir_override=raw_dir) # Pass raw_dir explicitly
        
        if not unified_df.empty:
            excel_sheets_data["Unified_Report"] = unified_df
            console.print(f"[green]  -> {script_display_name_unified} completed. DataFrame shape: {unified_df.shape}[/]")
            if args.debug:
                console.print("  Unified DataFrame Head:")
                console.print(unified_df.head().to_string())
        else:
            console.print(f"[yellow]  -> {script_display_name_unified} completed but returned an empty DataFrame.[/]")
        statuses[script_display_name_unified] = "[green]Completed Successfully (Imported)[/green]"
except Exception as e:
    console.print(f"[bold red][ERROR][/] running {script_display_name_unified} (imported): {e}")
    statuses[script_display_name_unified] = f"[red]Failed (Imported): {e}[/red]"

# --- Run other scripts as subprocesses (for now) ---
# This loop should now be empty if all scripts are refactored
if scripts_to_run_as_subprocess:
    console.print("\n[bold yellow]Warning: Some scripts are still configured to run as subprocesses.[/]")
for script_path_segment in scripts_to_run_as_subprocess:
    script_display_name = os.path.normpath(script_path_segment) # Normalize for consistent dict key
    with console.status(f"[bold green]Running {script_display_name}...[/]"):
        console.print(f"\n[bold blue]=== Running {script_display_name} (subprocess) ===[/]")
        try:
            # Use full path to script
            full_script_path = os.path.join(script_dir, script_path_segment)
            subprocess.run([sys.executable, full_script_path], env=env_vars, check=True, capture_output=True, text=True)
            statuses[script_display_name] = "[green]Completed Successfully (Subprocess)[/green]"
        except subprocess.CalledProcessError as exc:
            console.print(f"[bold red][ERROR][/] {script_display_name} exited with status {exc.returncode}")
            console.print(f"  Stdout:\n{exc.stdout}")
            console.print(f"  Stderr:\n{exc.stderr}")
            statuses[script_display_name] = f"[red]Failed (Subprocess - Exit Code: {exc.returncode})[/red]"
            # Continue to next script rather than aborting the entire pipeline
            continue
        except Exception as e:
            console.print(f"[bold red][ERROR][/] An unexpected error occurred with {script_display_name}: {e}")
            statuses[script_display_name] = f"[red]Failed (Subprocess - Unexpected Error)[/red]"
            continue

# --- TODO: Implement Excel Writing --- 
if excel_sheets_data:
    console.print("\n[bold cyan]Collected DataFrames for Excel (to be implemented):[/]")
    for sheet_name, df_item in excel_sheets_data.items():
        console.print(f"  - Sheet: '{sheet_name}', Shape: {df_item.shape}")

    # --- Actual Excel Writing --- 
    excel_filename = f"astro_session_report_{datetime.now().strftime('%Y%m%d-%H%M%S')}.xlsx"
    # Ensure reports_dir is valid, defaulting if necessary
    output_excel_dir = reports_dir
    if not output_excel_dir:
        # Fallback to a subfolder in the current working directory of run_all.py if REPORTS_DIR isn't set
        # This typically would be the astro-session-reporter directory itself.
        output_excel_dir = os.path.join(script_dir, "output_excel_reports") 
        os.makedirs(output_excel_dir, exist_ok=True)
        console.print(f"[yellow]REPORTS_DIR not set, saving Excel to: {output_excel_dir}[/]")
    
    output_excel_path = os.path.join(output_excel_dir, excel_filename)

    try:
        with pd.ExcelWriter(output_excel_path, engine='openpyxl') as writer:
            for sheet_name, df_to_write in excel_sheets_data.items():
                df_to_write.to_excel(writer, sheet_name=sheet_name, index=False)
        console.print(f"\n[bold green]SUCCESS:[/] Excel report generated at: [cyan]{output_excel_path}[/]")
    except Exception as e:
        console.print(f"\n[bold red]ERROR writing Excel file {output_excel_path}: {e}[/]")
    # --- 

# Display final status
final_table = Table(title="Script Execution Status")
final_table.add_column("Script", style="cyan")
final_table.add_column("Status")

for script_name_disp in all_scripts_display_names:
    final_table.add_row(script_name_disp, statuses[script_name_disp])

console.print("\n[bold green]Final Status:[/]")
console.print(final_table)
console.print("\n[bold green]All processing complete![/]") 