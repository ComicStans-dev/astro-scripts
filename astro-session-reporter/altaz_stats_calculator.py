import os
import re
import glob
import math
import numpy as np
from datetime import datetime, timedelta

from astropy.io import fits
from astropy.coordinates import SkyCoord, EarthLocation, AltAz
from astropy.time import Time
import astropy.units as u

try:
    import zoneinfo
    local_zone = zoneinfo.ZoneInfo("America/Los_Angeles")
except ImportError:
    import pytz
    local_zone = pytz.timezone("America/Los_Angeles")


###################################################
# USER SETTINGS
###################################################
# Define the directory containing FITS files
fits_dir = r"G:\My Drive\Dane's Files\Photography\Astrophotography\DSOs\IC1805\02-28-2025\\"

# Observer's approximate location in Beaverton, OR
observer_location = EarthLocation(
    lat=45.5145 * u.deg,
    lon=-122.848 * u.deg,
    height=60 * u.m
)

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

def main():
    # Recursively search for FITS files in the directory and subdirectories.
    fits_files = glob.glob(os.path.join(fits_dir, '**', '*.fits'), recursive=True)
    fits_files += glob.glob(os.path.join(fits_dir, '**', '*.fit'), recursive=True)
    fits_files.sort()

    # Determine the imaging date from the first FITS file (if available)
    if fits_files:
        first_file = os.path.basename(fits_files[0])
        local_dt = parse_local_time_from_filename(first_file)
        if local_dt:
            date_str = local_dt.strftime("%m-%d-%Y")
        else:
            # Fall back to using the folder name if parsing fails
            date_str = os.path.basename(os.path.normpath(fits_dir))
    else:
        # If no FITS files found, still try to use the folder name
        date_str = os.path.basename(os.path.normpath(fits_dir))

    # Generate CSV filename dynamically with the imaging date at the beginning
    csv_filename = f"altaz_stats_{date_str}.csv"
    output_csv_path = os.path.join(fits_dir, csv_filename)

    # Debugging output (optional, can be removed)
    print(f"CSV will be saved at: {output_csv_path}")

    with open(output_csv_path, "w", encoding="utf-8") as csv_out:
        csv_out.write("filename,local_time,alt_deg,az_deg,mean_pix,std_pix\n")

        for fpath in fits_files:
            fname = os.path.basename(fpath)
            try:
                # 1) Parse local time from filename
                local_dt = parse_local_time_from_filename(fname)
                if local_dt is None:
                    print(f"Could not parse timestamp from {fname}; skipping.")
                    continue

                # 2) RA/DEC from FITS header
                with fits.open(fpath) as hdul:
                    header = hdul[0].header
                    ra_deg, dec_deg = get_radec_from_header(header)
                    mean_val, std_val = get_image_stats(hdul)

                # 3) Alt/Az at that local time
                alt_deg, az_deg = calc_altaz(local_dt, ra_deg, dec_deg)

                # 4) Excel-friendly time: "YYYY-MM-DD HH:MM:SS"
                excel_time_str = local_dt.strftime("%Y-%m-%d %H:%M:%S")

                # 5) Write row to CSV
                csv_out.write(f"{fname},{excel_time_str},{alt_deg:.3f},"
                              f"{az_deg:.3f},{mean_val:.2f},{std_val:.2f}\n")

                # Print to console in a friendlier format
                friendly_str = local_dt.strftime("%m/%d/%Y %I:%M:%S %p %Z")
                print(f"{fname} => LocalTime:{friendly_str}, "
                      f"Alt:{alt_deg:.2f}°, Az:{az_deg:.2f}°, "
                      f"Mean:{mean_val:.2f}, Std:{std_val:.2f}")

            except Exception as e:
                print(f"Error processing {fname}: {e}")

if __name__ == "__main__":
    main()
