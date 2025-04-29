#!/usr/bin/env python3
import os
import sys
import subprocess
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

# Get target directory
directory = os.getenv("DIRECTORY")
if not directory:
    print("ERROR: DIRECTORY environment variable not set in .env file or environment")
    sys.exit(1)

# List of reporter scripts to run
scripts = [
    "astro-session-reporter/altaz_stats_calculator.py",
    "astro-session-reporter/autofocus_analysis.py",
    "astro-session-reporter/phd2_error_anaylsis.py",
]

# Run each script with the same environment
for script in scripts:
    print(f"\n=== Running {script} ===")
    # Pass the directory via environment variable for the sub-scripts
    env_vars = {**os.environ, "DIRECTORY": directory}
    subprocess.run([sys.executable, script], env=env_vars, check=True) 