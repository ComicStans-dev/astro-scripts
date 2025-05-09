import csv
import os
import sys
import pandas as pd # Added for DataFrame
from pathlib import Path
from datetime import datetime
from typing import List
import argparse

# Ensure package relative imports work when script run directly
PACKAGE_DIR = Path(__file__).resolve().parents[1]
if str(PACKAGE_DIR) not in sys.path:
    sys.path.insert(0, str(PACKAGE_DIR))

# CLI argument parsing
parser = argparse.ArgumentParser(description="Generate unified CSV correlating FITS, guiding, and event data.")
parser.add_argument("--raw-dir", help="Directory containing raw FITS and log files. Overrides RAW_DIR env var if provided.")
args, _unknown = parser.parse_known_args()

# Relative imports
from correlator.associate import associate
from parsers.autorun_parser import parse_autorun_log
from parsers.fits_parser import parse_fits_headers
from parsers.phd2_parser import parse_phd2_log
from utils.paths import RAW_DIR as RAW_DIR_ENV, out_path


COLS = [
    "fits_name","start_dt_utc","end_dt_utc","ra_deg","dec_deg","alt_deg","az_deg",
    "exposure_s","rms_ra_as","rms_dec_as","rms_tot_as","star_lost_cnt","mean_pix","std_pix","confidence"
]


PIXEL_SCALE_ARCSEC = 6.45


def rms(vals):
    import math
    if not vals:
        return None
    return math.sqrt(sum(v*v for v in vals) / len(vals))


def compute_rms(gframes: List):
    import math
    ra_as = [g.ra_pix * PIXEL_SCALE_ARCSEC for g in gframes]
    dec_as = [g.dec_pix * PIXEL_SCALE_ARCSEC for g in gframes]
    tot_as = [math.sqrt(r*r + d*d) for r,d in zip(ra_as, dec_as)]
    return rms(ra_as), rms(dec_as), rms(tot_as)


def generate_unified_dataframe(raw_dir_override=None):
    """Parses all required logs and FITS files, associates them, and returns a unified DataFrame."""
    raw_dir_final = raw_dir_override if raw_dir_override else RAW_DIR_ENV
    if not raw_dir_final:
        print("[generate_unified_csv] ERROR: RAW_DIR not set.")
        return pd.DataFrame() # Return empty DataFrame on error
    
    raw = Path(raw_dir_final)
    if not raw.exists():
        print(f"[generate_unified_csv] ERROR: Raw directory does not exist: {raw}")
        return pd.DataFrame()

    # Locate log files - allow for possibility of no logs for robustness
    autorun_log_path = next(raw.glob("Autorun_Log*.txt"), None)
    phd2_log_path = next(raw.glob("PHD2_GuideLog*.txt"), None)
    fits_files = list(raw.glob("Light_*.fit*")) # Handles .fit and .fits

    if not autorun_log_path:
        print(f"[generate_unified_csv] WARNING: Autorun_Log not found in {raw}. Unified data might be incomplete.")
        expos = []
    else:
        expos = parse_autorun_log(autorun_log_path)

    if not phd2_log_path:
        print(f"[generate_unified_csv] WARNING: PHD2_GuideLog not found in {raw}. Guiding data will be missing.")
        guides, events = [], []
    else:
        guides, events, _ = parse_phd2_log(phd2_log_path)

    if not fits_files:
        print(f"[generate_unified_csv] WARNING: No FITS files (Light_*.fit*) found in {raw}. Image data will be missing.")
        images = []
    else:
        images = parse_fits_headers(fits_files)

    # Associate data (modifies expos in-place)
    if expos and (images or guides or events): # Only associate if there's something to associate
        associate(expos, images, guides, events)
    elif not expos:
        print("[generate_unified_csv] No exposure metadata to drive association.")
        return pd.DataFrame()

    data_for_df = []
    for meta in expos:
        if not meta.image_frame: # Skip if no associated image frame
            if os.getenv("DEBUG") == "1":
                print(f"[generate_unified_csv DEBUG] Skipping exposure num {meta.image_num} (no image_frame associated).")
            continue
        
        ra_rms, dec_rms, tot_rms = None, None, None
        if meta.guide_frames: # Compute RMS only if guide frames exist
             ra_rms, dec_rms, tot_rms = compute_rms(meta.guide_frames)

        star_lost_count = len([ev for ev in meta.guide_events if ev.type=="star_lost"]) if meta.guide_events else 0
        
        # Format datetimes as ISO strings for DataFrame compatibility
        start_dt_iso = meta.image_frame.start_dt_utc.isoformat() if meta.image_frame.start_dt_utc else None
        end_dt_iso = meta.image_frame.end_dt_utc.isoformat() if meta.image_frame.end_dt_utc else None

        row_dict = {
            COLS[0]: meta.image_frame.fits_name,
            COLS[1]: start_dt_iso,
            COLS[2]: end_dt_iso,
            COLS[3]: meta.image_frame.ra_deg,
            COLS[4]: meta.image_frame.dec_deg,
            COLS[5]: meta.image_frame.alt_deg,
            COLS[6]: meta.image_frame.az_deg,
            COLS[7]: meta.image_frame.exposure_s,
            COLS[8]: ra_rms,
            COLS[9]: dec_rms,
            COLS[10]: tot_rms,
            COLS[11]: star_lost_count,
            COLS[12]: meta.image_frame.mean_pix,
            COLS[13]: meta.image_frame.std_pix,
            COLS[14]: meta.confidence,
        }
        data_for_df.append(row_dict)
    
    if not data_for_df:
        print("[generate_unified_csv] No data rows were generated for the unified report.")
        return pd.DataFrame()
        
    return pd.DataFrame(data_for_df, columns=COLS)


def main():
    # raw_dir_final is determined by argparse or ENV inside generate_unified_dataframe if called by run_all
    # If run standalone, args.raw_dir can be used, or RAW_DIR_ENV will be used by default.
    unified_df = generate_unified_dataframe(raw_dir_override=args.raw_dir)

    if __name__ == "__main__": # Only write CSV if run as a script
        if not unified_df.empty:
            out_csv_path = out_path(f"unified_{datetime.now():%Y%m%d-%H%M%S}.csv")
            try:
                unified_df.to_csv(out_csv_path, index=False)
                print(f"[generate_unified_csv] Unified CSV written to: {out_csv_path}")
            except Exception as e:
                print(f"[generate_unified_csv] Error writing unified CSV to {out_csv_path}: {e}")
        else:
            print("[generate_unified_csv] No data to write to unified CSV.")
    
    return unified_df # Return for potential import use


if __name__ == "__main__":
    main() 