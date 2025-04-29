#!/usr/bin/env python3
import os
import sys
import subprocess
import argparse
from dotenv import load_dotenv
import inspect

# Parse command-line arguments
parser = argparse.ArgumentParser(description="Run all astro-session reporters.")
parser.add_argument('--debug', action='store_true', help='Enable debug output')
parser.add_argument('--reports-dir', help='Override REPORTS_DIR environment variable')
args = parser.parse_args()

# Calculate path to the parent directory where .env is stored
script_path = os.path.abspath(inspect.getfile(inspect.currentframe()))
script_dir = os.path.dirname(script_path)
parent_dir = os.path.dirname(script_dir)
env_path = os.path.join(parent_dir, ".env")

# Load environment variables from the correct location
env_loaded = load_dotenv(dotenv_path=env_path)

if args.debug:
    print(f"Loading .env from: {env_path} (success: {env_loaded})")

# Validate required environment variables
raw_dir = os.getenv("RAW_DIR") or os.getenv("DIRECTORY")
reports_dir = os.getenv("REPORTS_DIR")

# Allow command line override of reports_dir
if args.reports_dir:
    reports_dir = args.reports_dir
    print(f"Using reports directory from command line: {reports_dir}")

if not raw_dir:
    print("ERROR: RAW_DIR (or legacy DIRECTORY) environment variable not set")
    sys.exit(1)

# Print diagnostics to help debug path issues
print(f"Using RAW_DIR: {raw_dir}")
print(f"Using REPORTS_DIR: {reports_dir or '(not set, will use RAW_DIR as fallback)'}")

# Scripts to run (relative to this directory)
scripts = [
    "altaz_stats_calculator.py",
    "autofocus_analysis.py",
    "phd2_error_anaylsis.py",
]

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
    print("Debug mode enabled")

for script in scripts:
    print(f"\n=== Running {script} ===")
    try:
        # Use full path to script
        script_path = os.path.join(script_dir, script)
        subprocess.run([sys.executable, script_path], env=env_vars, check=True)
    except subprocess.CalledProcessError as exc:
        print(f"[ERROR] {script} exited with status {exc.returncode}")
        # Continue to next script rather than aborting the entire pipeline
        continue 