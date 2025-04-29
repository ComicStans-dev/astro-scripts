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
    print("ERROR: DIRECTORY environment variable not set")
    sys.exit(1)

# List of reporter scripts to run
scripts = [
    "altaz_stats_calculator.py",
    "autofocus_analysis.py",
    "phd2_error_anaylsis.py",
]

# Run each script with the same environment
for script in scripts:
    print(f"\n=== Running {script} ===")
    subprocess.run([sys.executable, script], env={**os.environ, "DIRECTORY": directory}, check=True) 