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

# Robust path normalization using pathlib
def normalize_path(p):
    if not p:
        return None
    try:
        resolved = Path(p).expanduser().resolve(strict=False)
        return str(resolved)
    except Exception as e:
        print(f"[paths] WARNING: Could not normalize path '{p}': {e}")
        return os.path.abspath(p)

RAW_DIR_RAW = RAW_DIR
REPORTS_DIR_RAW = raw_reports_dir
RAW_DIR = normalize_path(RAW_DIR_RAW)
REPORTS_DIR = normalize_path(REPORTS_DIR_RAW)

if os.getenv("DEBUG"):
    print(f"[paths] RAW_DIR (raw): {RAW_DIR_RAW}")
    print(f"[paths] RAW_DIR (normalized): {RAW_DIR}")
    print(f"[paths] REPORTS_DIR (raw): {REPORTS_DIR_RAW}")
    print(f"[paths] REPORTS_DIR (normalized): {REPORTS_DIR}")

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