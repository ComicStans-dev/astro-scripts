# astro_session_reporter/utils/paths.py
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# For astro-scripts, the .env file is expected to be in the parent directory 
# (G:\My Drive\Dane's Files\Projects\Python\astro-scripts)

# Calculate path to the parent directory (..) relative to this script's location
script_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # astro-session-reporter
parent_dir = os.path.dirname(script_dir)  # astro-scripts
env_path = os.path.join(parent_dir, ".env")

# Load environment variables from the precise .env location
env_loaded = load_dotenv(dotenv_path=env_path)

# Debug output
print(f"[paths] Loading .env from: {env_path} (success: {env_loaded})")
if not env_loaded:
    print(f"[paths] WARNING: Could not load .env file from {env_path}")
    # Fallback - try current directory
    env_loaded = load_dotenv()
    print(f"[paths] Fallback load from current directory: {env_loaded}")

# -----------------------------------------------------------------------------
# Path helper for the astro-session-reporter package.
#
#  • RAW_DIR      – directory that contains the raw session files (FITS + logs)
#  • REPORTS_DIR  – directory where all generated CSV/plots will be written.
#
# Both variables are optional so that the library can still function if only
# one of them is provided.  Fallbacks:
#   – If RAW_DIR is missing, we fall back to the deprecated environment var
#     "DIRECTORY" for backward-compatibility.
#   – If REPORTS_DIR is missing, the raw directory is used so behaviour stays
#     identical to the original scripts.
# -----------------------------------------------------------------------------

# Backward compatibility layer for the old name "DIRECTORY" -------------------
_legacy_raw_dir = os.getenv("DIRECTORY")

# New canonical names ---------------------------------------------------------
RAW_DIR = os.getenv("RAW_DIR", _legacy_raw_dir)

# REPORTS_DIR may be absent; if so, we write alongside the raw data just like
# the original code did.
raw_reports_dir = os.getenv("REPORTS_DIR", RAW_DIR)

# Clean up any potential control characters in paths
def clean_path(path):
    if path is None:
        return None
    # Replace any non-printable characters except allowed path separators with nothing
    return Path(path).resolve().as_posix()

# Clean the paths to prevent control character issues
RAW_DIR = clean_path(RAW_DIR)
REPORTS_DIR = clean_path(raw_reports_dir)

# Special flag to ensure REPORTS_DIR is respected in subprocess
if os.getenv("FORCE_REPORTS_DIR") == "1" and REPORTS_DIR == RAW_DIR and os.getenv("REPORTS_DIR"):
    print("FORCE_REPORTS_DIR flag detected - ensuring REPORTS_DIR is used")
    REPORTS_DIR = clean_path(os.getenv("REPORTS_DIR"))

# Simplified debug output - only show it in verbose mode or if there's an apparent issue
if os.getenv("DEBUG") or REPORTS_DIR == RAW_DIR:
    print(f"[paths] RAW_DIR: {RAW_DIR}")
    print(f"[paths] REPORTS_DIR: {REPORTS_DIR}")

# -----------------------------------------------------------------------------
# Public helpers
# -----------------------------------------------------------------------------

def ensure_reports_dir() -> str:
    """Create the REPORTS_DIR (if needed) and return its absolute path."""
    if REPORTS_DIR is None:
        raise ValueError("REPORTS_DIR is not set")
    
    try:
        os.makedirs(REPORTS_DIR, exist_ok=True)
    except Exception as e:
        print(f"[paths] ERROR creating directory {REPORTS_DIR}: {e}")
        # Create a fallback directory in the current directory
        fallback_dir = os.path.join(os.getcwd(), "output")
        print(f"[paths] Using fallback directory: {fallback_dir}")
        os.makedirs(fallback_dir, exist_ok=True)
        return fallback_dir
        
    return REPORTS_DIR


def out_path(filename: str) -> str:
    """Return an absolute path inside REPORTS_DIR for the given *filename*."""
    # Use an absolute path if REPORTS_DIR is explicitly set
    output_path = os.path.join(ensure_reports_dir(), filename)
    # Only print path for debugging
    if os.getenv("DEBUG") == "1":
        print(f"[paths] Writing to: {output_path}")
    return output_path


# Convenience alias for migration period -------------------------------------
# Some existing code still imports `OUTPUT_DIR`/`ensure_output_dir`; keep them
# around to avoid breaking imports, but emit a gentle warning the first time
# they are used.

import warnings as _warnings


def _warn_deprecated(name: str, new: str):
    _warnings.warn(
        f"{name} is deprecated.  Use {new} from astro_session_reporter.utils.paths instead.",
        DeprecationWarning,
        stacklevel=3,
    )


def ensure_output_dir():  # pragma: no cover – retained for compatibility
    _warn_deprecated("ensure_output_dir", "ensure_reports_dir")
    return ensure_reports_dir()


# Old OUTPUT_DIR alias --------------------------------------------------------
OUTPUT_DIR = REPORTS_DIR