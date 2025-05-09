import os
import re
import glob
import math
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from dotenv import load_dotenv
from utils.paths import RAW_DIR, out_path

from astropy.io import fits
from astropy.coordinates import SkyCoord, EarthLocation, AltAz
from astropy.time import Time
import astropy.units as u
import sep  # NEW: Source Extractor library for star detection and HFR
from astroplan import moon_illumination  # NEW: moon illumination
from astropy.coordinates import get_moon  # NEW: moon position

try:
    import zoneinfo
    local_zone = zoneinfo.ZoneInfo("America/Los_Angeles")
except ImportError:
    import pytz
    local_zone = pytz.timezone("America/Los_Angeles")

# Load environment variables from .env file
load_dotenv()

###################################################
# USER SETTINGS
###################################################
# The raw data directory is now read once, centrally, from utils.paths
if not RAW_DIR:
    raise ValueError("RAW_DIR (or legacy DIRECTORY) not set in environment variables or .env file.")

# Observer's approximate location is now loaded from the .env file.
# Ensure your .env file contains lines like:
# OBSERVER_LAT="##.####"     # Latitude in decimal degrees (North positive)
# OBSERVER_LON="##.###"    # Longitude in decimal degrees (East positive)
# OBSERVER_HEIGHT="##"       # Height above reference ellipsoid (approx. AMSL) in meters
observer_lat = os.getenv("OBSERVER_LAT")
observer_lon = os.getenv("OBSERVER_LON")
observer_height = os.getenv("OBSERVER_HEIGHT")

if not all([observer_lat, observer_lon, observer_height]):
    raise ValueError("Observer location (LAT, LON, HEIGHT) not found in .env file or environment variables.")

try:
    observer_location = EarthLocation(
        lat=float(observer_lat) * u.deg,
        lon=float(observer_lon) * u.deg,
        height=float(observer_height) * u.m
    )
except ValueError as e:
    raise ValueError(f"Error converting observer location from .env to numbers: {e}")

def parse_local_time_from_filename(fname):
    """
    Parses a substring 'YYYYMMDD-HHMMSS' from the filename and interprets it as
    local time (America/Los_Angeles).

    Example match: '..._20250227-214521_...'
      -> naive datetime(2025, 2, 27, 21, 45, 21)
      -> localized to PST/PDT
    """
    # Updated regex pattern to allow an optional .fit/.fits extension
    pattern = r".*_(\d{8})-(\d{6})_.*(?:\.fits?)?$"
    match = re.match(pattern, fname)
    if not match:
        return None

    date_part = match.group(1)  # e.g. "20250227"
    time_part = match.group(2)  # e.g. "214521"
    dt_str = date_part + time_part  # "20250227214521"

    # Parse as naive datetime
    dt_naive = datetime.strptime(dt_str, "%Y%m%d%H%M%S")

    # Localize to PST/PDT
    local_dt = dt_naive.replace(tzinfo=local_zone)

    # If you really do want to shift by a day, uncomment:
    # local_dt += timedelta(days=1)

    return local_dt

def calc_altaz(local_dt, ra_deg, dec_deg):
    """
    Convert local_dt (datetime with tzinfo=America/Los_Angeles)
    to UTC, then compute Alt/Az.
    """
    dt_utc = local_dt.astimezone(zoneinfo.ZoneInfo("UTC"))
    obs_time_utc = Time(dt_utc)

    coord = SkyCoord(ra=ra_deg * u.deg, dec=dec_deg * u.deg, frame="icrs")
    altaz_frame = AltAz(obstime=obs_time_utc, location=observer_location)
    altaz = coord.transform_to(altaz_frame)
    return float(altaz.alt.deg), float(altaz.az.deg)

def get_radec_from_header(header):
    """
    Return (RA, DEC) in degrees from header, or (0,0) if missing.
    """
    if "RA" in header and "DEC" in header:
        return float(header["RA"]), float(header["DEC"])
    return float(header.get("CRVAL1", 0.0)), float(header.get("CRVAL2", 0.0))

def get_image_stats(fits_hdul):
    """
    Return mean and std dev of the primary HDU's data.
    """
    data = fits_hdul[0].data
    return float(np.mean(data)), float(np.std(data))

def hfr_stats(data, thresh_sigma: float = 3.0):
    """Return (mean_hfr, std_hfr, n_stars) for a 2-D numpy array.

    Uses `sep` to detect sources and compute the half-flux radius (HFR).
    Values are in pixels.  If no stars are found, returns (nan, nan, 0).
    """
    # Determine if debug output is enabled via environment variable
    debug_hfr = os.getenv("DEBUG") == "1"
    try:
        # SEP expects float32, contiguous array
        data_f32 = np.ascontiguousarray(data.astype(np.float32))
        # Build background model & subtract
        bkg = sep.Background(data_f32)
        
        if debug_hfr:
            print(f"[altaz_stats DEBUG hfr_stats] Background RMS: {bkg.globalrms:.4f}")
            
        data_sub = data_f32 - bkg.back()
        
        current_threshold = thresh_sigma * bkg.globalrms
        if debug_hfr:
            print(f"[altaz_stats DEBUG hfr_stats] Detection Threshold (sigma * RMS): {current_threshold:.4f}")
            
        objects = sep.extract(data_sub, thresh_sigma * bkg.globalrms)
        
        num_detected_objects = len(objects)
        if debug_hfr:
            print(f"[altaz_stats DEBUG hfr_stats] Number of objects detected by sep.extract: {num_detected_objects}")
            
        if num_detected_objects == 0:
            return np.nan, np.nan, 0
            
        # Create an array of radii, one for each object
        # All objects will use the same max integration radius of 6.0 pixels
        radii_arr = np.full(num_detected_objects, 6.0)

        # half-flux radius for each source (0.5 => HFR)
        half_r, flags = sep.flux_radius( # MODIFIED: Expect only 2 return values
            data_sub,
            objects['x'], objects['y'],
            radii_arr,      # MODIFIED: Use an array of radii
            0.5,            # 50 % flux radius
            subpix=5
        )
        
        # Filter out problematic HFR calculations based on flags if necessary
        # For now, we'll use all valid HFR values returned
        valid_hfr = half_r[np.isfinite(half_r) & (flags == 0)]

        if debug_hfr:
            print(f"[altaz_stats DEBUG hfr_stats] Raw HFR values: {half_r}")
            print(f"[altaz_stats DEBUG hfr_stats] SEP flags: {flags}")
            print(f"[altaz_stats DEBUG hfr_stats] Valid HFR values after filtering: {valid_hfr}")

        if len(valid_hfr) == 0:
            return np.nan, np.nan, num_detected_objects # Still report num_detected_objects

        return float(np.mean(valid_hfr)), float(np.std(valid_hfr)), int(len(valid_hfr))
    except Exception as e:
        if debug_hfr:
            print(f"[altaz_stats] hfr_stats failed: {e}")
        return np.nan, np.nan, 0

def moon_parameters(local_dt: datetime, target_coord: SkyCoord):
    """Return dict with moon_alt, moon_sep, moon_illum (0-100%)."""
    try:
        # Convert local datetime to UTC astropy Time
        t_utc = Time(local_dt.astimezone(zoneinfo.ZoneInfo("UTC")))
        moon_icrs = get_moon(t_utc, location=observer_location)
        moon_altaz = moon_icrs.transform_to(AltAz(obstime=t_utc, location=observer_location))
        illum_frac = moon_illumination(t_utc)  # 0-1
        separation = moon_icrs.separation(target_coord).deg
        return {
            "moon_alt": float(moon_altaz.alt.deg),
            "moon_sep": float(separation),
            "moon_illum": float(illum_frac * 100.0)
        }
    except Exception as e:
        if os.getenv("DEBUG") == "1":
            print(f"[altaz_stats] moon_parameters failed: {e}")
        return {"moon_alt": np.nan, "moon_sep": np.nan, "moon_illum": np.nan}

def generate_altaz_stats_df():
    fits_files = glob.glob(os.path.join(RAW_DIR, '**', '*.fits'), recursive=True)
    fits_files += glob.glob(os.path.join(RAW_DIR, '**', '*.fit'), recursive=True)
    fits_files.sort()

    if not fits_files:
        print("[altaz_stats] No FITS files found.")
        return pd.DataFrame(), pd.DataFrame() # Return two empty DFs

    data_rows = []
    first_header_data = []
    first_file_processed = False

    for fpath in fits_files:
        fname = os.path.basename(fpath)
        try:
            with fits.open(fpath) as hdul:
                header = hdul[0].header

                # --- Process First Header --- 
                if not first_file_processed:
                    for card in header.cards:
                        key = card.keyword
                        if key in ['COMMENT', 'HISTORY', '']:
                             continue
                        value = str(card.value)
                        comment = card.comment
                        first_header_data.append({
                            "Key": key,
                            "Value": value,
                            "Comment": comment,
                        })
                    first_file_processed = True
                # --- End First Header --- 

                local_dt = parse_local_time_from_filename(fname)
                if local_dt is None:
                    if os.getenv("DEBUG") == "1":
                        print(f"[altaz_stats] Could not parse timestamp from {fname}; skipping.")
                    continue

                ra_deg, dec_deg = get_radec_from_header(header)
                mean_val, std_val = get_image_stats(hdul)

                # NEW: HFR statistics
                mean_hfr, std_hfr, n_stars = hfr_stats(hdul[0].data)

                alt_deg, az_deg = calc_altaz(local_dt, ra_deg, dec_deg)

                # NEW: moon parameters relative to this frame
                target_coord = SkyCoord(ra=ra_deg * u.deg, dec=dec_deg * u.deg, frame="icrs")
                moon_info = moon_parameters(local_dt, target_coord)

                excel_time_str = local_dt.strftime("%Y-%m-%d %H:%M:%S")

                data_rows.append({
                    "filename": fname,
                    "local_time": excel_time_str,
                    "alt_deg": round(alt_deg, 3),
                    "az_deg": round(az_deg, 3),
                    "mean_pix": round(mean_val, 2),
                    "std_pix": round(std_val, 2),
                    "hfr_mean": round(mean_hfr, 3) if not math.isnan(mean_hfr) else np.nan,
                    "hfr_std": round(std_hfr, 3) if not math.isnan(std_hfr) else np.nan,
                    "n_stars": n_stars,
                    "moon_alt": round(moon_info["moon_alt"], 2) if not math.isnan(moon_info["moon_alt"]) else np.nan,
                    "moon_sep": round(moon_info["moon_sep"], 2) if not math.isnan(moon_info["moon_sep"]) else np.nan,
                    "moon_illum": round(moon_info["moon_illum"], 1) if not math.isnan(moon_info["moon_illum"]) else np.nan
                })

                if os.getenv("DEBUG") == "1":
                    friendly_str = local_dt.strftime("%m/%d/%Y %I:%M:%S %p %Z")
                    debug_msg = (
                        f"[altaz_stats] {fname} => LocalTime:{friendly_str}, Alt:{alt_deg:.2f}°, Az:{az_deg:.2f}°, "
                        f"Mean:{mean_val:.2f}, Std:{std_val:.2f}, HFR:{mean_hfr:.2f}±{std_hfr:.2f} (n={n_stars}), "
                        f"MoonIllum:{moon_info['moon_illum']:.1f}%, MoonAlt:{moon_info['moon_alt']:.1f}°, "
                        f"MoonSep:{moon_info['moon_sep']:.1f}°"
                    )
                    print(debug_msg)

        except Exception as e:
            if os.getenv("DEBUG") == "1":
                print(f"[altaz_stats] Error processing {fname}: {e}")

    first_header_df = pd.DataFrame(first_header_data)
    altaz_stats_df = pd.DataFrame(data_rows)
    return altaz_stats_df, first_header_df # Return both DataFrames

def main():
    # Determine the imaging date from the first FITS file (if available)
    # This logic is primarily for naming the standalone CSV.
    # For Excel output, run_all.py will handle the main report naming.
    date_str = datetime.now().strftime("%Y%m%d") # Default date string
    fits_files_check = glob.glob(os.path.join(RAW_DIR, '**', '*.f*'), recursive=True)
    if fits_files_check:
        first_file = os.path.basename(sorted(fits_files_check)[0])
        local_dt_check = parse_local_time_from_filename(first_file)
        if local_dt_check:
            date_str = local_dt_check.strftime("%m-%d-%Y")
        else:
            # Fall back to using the folder name if parsing fails
            base_raw_dir = os.path.basename(os.path.normpath(RAW_DIR))
            if base_raw_dir:
                date_str = base_raw_dir
    else:
        base_raw_dir = os.path.basename(os.path.normpath(RAW_DIR))
        if base_raw_dir:
            date_str = base_raw_dir

    altaz_df, first_header_df = generate_altaz_stats_df() # Get both dataframes

    if __name__ == "__main__": # Only write CSV if run as a script
        if not altaz_df.empty:
            csv_filename = f"altaz_stats_{date_str}.csv"
            output_csv_path = out_path(csv_filename)
            print(f"[altaz_stats] CSV will be saved at: {output_csv_path}")
            altaz_df.to_csv(output_csv_path, index=False)
            # The original print to console logic is now inside generate_altaz_stats_df under DEBUG flag
        else:
            print("[altaz_stats] No data generated to write to CSV.")

        # Optionally write first header to a separate CSV if run standalone
        if not first_header_df.empty:
             header_csv_filename = f"fits_header_first_img_{date_str}.csv"
             header_output_path = out_path(header_csv_filename)
             try:
                 first_header_df.to_csv(header_output_path, index=False)
                 print(f"[altaz_stats] First FITS header saved to: {header_output_path}")
             except Exception as e:
                 print(f"[altaz_stats] Error writing FITS header CSV: {e}")

    return altaz_df, first_header_df # Return both dfs

if __name__ == "__main__":
    main()
