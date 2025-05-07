import csv
import os
import sys
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


def main():
    raw_dir_final = args.raw_dir if args.raw_dir else RAW_DIR_ENV
    if not raw_dir_final:
        print("[generate_unified_csv] ERROR: RAW_DIR not set via env or --raw-dir argument")
        sys.exit(1)
    raw = Path(raw_dir_final)
    if not raw.exists():
        print(f"[generate_unified_csv] ERROR: Raw directory does not exist: {raw}")
        sys.exit(1)
    autorun_log = next(raw.glob("Autorun_Log*.txt"), None)
    phd2_log = next(raw.glob("PHD2_GuideLog*.txt"), None)
    fits_files = list(raw.glob("Light_*.fit*"))

    expos = parse_autorun_log(autorun_log)
    images = parse_fits_headers(fits_files)
    guides, events, _ = parse_phd2_log(phd2_log)

    associate(expos, images, guides, events)

    out_csv = out_path(f"unified_{datetime.now():%Y%m%d-%H%M%S}.csv")
    with open(out_csv, "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(COLS)
        for meta in expos:
            if not meta.image_frame:
                continue
            ra_rms, dec_rms, tot_rms = compute_rms(meta.guide_frames)
            writer.writerow([
                meta.image_frame.fits_name,
                meta.image_frame.start_dt_utc.isoformat(),
                meta.image_frame.end_dt_utc.isoformat(),
                meta.image_frame.ra_deg,
                meta.image_frame.dec_deg,
                meta.image_frame.alt_deg,
                meta.image_frame.az_deg,
                meta.image_frame.exposure_s,
                ra_rms,
                dec_rms,
                tot_rms,
                len([ev for ev in meta.guide_events if ev.type=="star_lost"]),
                meta.image_frame.mean_pix,
                meta.image_frame.std_pix,
                meta.confidence,
            ])
    print(f"Unified CSV written to: {out_csv}")


if __name__ == "__main__":
    main() 