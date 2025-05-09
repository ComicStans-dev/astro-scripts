#!/usr/bin/env python3
"""
phd2_error_analysis.py

Final version that:
  1) Finds the Autorun log and PHD2 log in a given directory.
  2) Parses:
     - Image exposures (start/end) + .fits filename from the Autorun log
       (now pulling DATE-OBS from FITS headers for the actual timestamp)
     - Guide frames (RA/DEC in px) + star-lost events from the PHD2 log
  3) Computes per-image RMS in arcsec & microns + star-lost count
  4) Outputs a table in the console and saves CSV with:
     Image#, .fits name, times, star-lost, RMS RA/DEC/Total (arcsec & µm), frames used
  5) Also prints/saves an overall RMS for the entire session.

Check the user-defined constants and regex patterns to match your actual log styles.
"""

import re
import os
import math
import csv
import pandas as pd # Added for DataFrame
from datetime import datetime, timedelta
from astropy.io import fits  # Added to read FITS headers

# Path helpers for directories
from utils.paths import RAW_DIR, out_path

# Filenames or partial prefixes for the logs:
AUTORUN_LOG_PREFIX = "Autorun_Log"  # e.g. "Autorun_Log_2025-01-25_202645.txt"
PHD2_LOG_PREFIX    = "PHD2_GuideLog" # e.g. "PHD2_GuideLog_2025-01-25_201743.txt"
AUTORUN_EXT        = ".txt"
PHD2_EXT           = ".txt"

# Guide camera scale:
PIXEL_SCALE_ARCSEC = 6.45  # arcsec per pixel
PIXEL_SIZE_UM      = 3.8   # microns per pixel

# Raw data directory (logs + FITS)
if not RAW_DIR:
    raise ValueError("RAW_DIR (or legacy DIRECTORY) not set in environment variables or .env file.")

# Global debug flag for this module
DEBUG_MODE = os.getenv("DEBUG") == "1"

def dbg(msg: str):
    """Print debug message if DEBUG=1 env var is set."""
    if DEBUG_MODE:
        print(msg)

# -------------------------
# 1) Locate the log files
# -------------------------
def find_all_files_with_prefix(dir_path, prefix, extension):
    """
    Search 'dir_path' for all files that start with 'prefix' and end with 'extension'.
    Returns a sorted list of matching file paths.
    """
    matches = [fname for fname in os.listdir(dir_path) if fname.startswith(prefix) and fname.endswith(extension)]
    if not matches:
        return []
    matches.sort()
    return [os.path.join(dir_path, m) for m in matches]

# -------------------------
# 2) Parse the Autorun Log
# -------------------------
def parse_autorun_log(log_path):
    """
    Reads lines from an autorun log to extract:
      - image_num
      - start_dt/end_dt (overridden with the DATE-OBS value from the FITS header if available)
      - filename (from lines that match .fits pattern)
    
    Example lines:
      2025/01/25 20:29:07 Exposure 300.0s image 1#
      Light_LDN 1625_300.0s_Bin1_gain252_20250125-203409_-20.0C_0001.fits
    
    Returns a list of dicts, each dict like:
      {
        "image_num": 1,
        "start_dt": datetime(...),
        "end_dt": datetime(...),
        "filename": "Light_...",
        "exposure_s": 300.0  # exposure in seconds
      }
    """
    if not log_path or not os.path.exists(log_path):
        print(f"Autorun log not found: {log_path}")
        return []

    images = []
    time_format = "%Y/%m/%d %H:%M:%S"

    # Pattern for exposure lines
    # e.g. "2025/01/25 20:29:07 Exposure 300.0s image 1#"
    exposure_pat = re.compile(
        r'^(\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2})\s+Exposure\s+([\d.]+)s\s+image\s+(\d+)#'
    )
    # Pattern for .fits lines
    # e.g. "Light_LDN 1625_300.0s_Bin1_gain252_20250125-203409_-20.0C_0001.fits"
    fits_pat = re.compile(r'^(Light_\S+\.fit[s]?)$', re.IGNORECASE)

    last_image_dict = None

    with open(log_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()

            # 1) Check if it's an "Exposure" line
            m_exp = exposure_pat.match(line)
            if m_exp:
                start_str   = m_exp.group(1)    # "2025/01/25 20:29:07"
                exposure_s  = float(m_exp.group(2))  # 300.0
                img_num     = int(m_exp.group(3))    # 1

                start_dt = datetime.strptime(start_str, time_format)
                last_image_dict = {
                    "image_num": img_num,
                    "start_dt":  start_dt,
                    "exposure_s": exposure_s,
                    "end_dt":    start_dt + timedelta(seconds=exposure_s),
                    "filename":  None
                }
                images.append(last_image_dict)
                continue

            # 2) If we have an active "last_image_dict", see if this line is a .fits filename.
            # If so, try to override the timestamp using the FITS header DATE-OBS.
            if last_image_dict is not None and last_image_dict["filename"] is None:
                m_fits = fits_pat.match(line)
                if m_fits:
                    filename_str = m_fits.group(1)  # the entire matched line
                    last_image_dict["filename"] = filename_str
                    try:
                        # Assume the FITS file is in the same directory as the log file.
                        fits_file_path = os.path.join(os.path.dirname(log_path), filename_str)
                        header = fits.getheader(fits_file_path)
                        date_obs = header.get('DATE-OBS')
                        if date_obs:
                            # DATE-OBS is expected in ISO format, e.g., '2025-03-01T03:58:35.470867'
                            obs_dt = datetime.fromisoformat(date_obs)
                            last_image_dict["start_dt"] = obs_dt
                            last_image_dict["end_dt"] = obs_dt + timedelta(seconds=last_image_dict["exposure_s"])
                    except Exception as e:
                        print(f"Error reading FITS header from {fits_file_path}: {e}")

    # Fallback: if the autorun log never listed FITS names, map exposures to the directory's FITS files
    log_dir = os.path.dirname(log_path)
    try:
        fits_files = sorted(
            fname for fname in os.listdir(log_dir)
            if fname.lower().endswith(('.fit', '.fits'))
        )
        for img_dict, fname in zip(images, fits_files):
            if img_dict.get("filename") is None:
                img_dict["filename"] = fname
    except Exception:
        # If directory listing fails, silently continue
        pass
    return images

# -------------------------
# 3) Parse the PHD2 Guide Log
# -------------------------
def parse_phd2_log(log_path):
    """
    Gather:
      - frames[]: each with abs_time, ra_pix, dec_pix
      - star_lost_times[]: datetimes of "Guide star lost"

    PHD2 lines:
      "Guiding Begins at 2025-01-25 20:17:44"
      Then lines like:
        1,0.576,"Mount",-0.057,0.104,-0.097,0.071, ...
      Also possible star-lost lines:
        2025/01/25 20:32:10 [Guide] Guide star lost
    """
    if not log_path or not os.path.exists(log_path):
        print(f"PHD2 log not found: {log_path}")
        return [], []

    frames = []
    star_lost_times = []

    time_format_phd2 = "%Y-%m-%d %H:%M:%S"
    current_session_start = None

    # Regex for data lines
    guide_data_pat = re.compile(
        r'^(\d+),([\d.]+),"Mount",([-+\d.]+),([-+\d.]+),([-+\d.]+),([-+\d.]+),'
    )

    with open(log_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()

            # 1) "Guiding Begins at 2025-01-25 20:17:44"
            mbeg = re.search(r'Guiding Begins at (\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})', line)
            if mbeg:
                dt_str = mbeg.group(1)
                current_session_start = datetime.strptime(dt_str, time_format_phd2)
                continue

            # 2) star lost line?
            mlost = re.search(r'^(\S+\s+\S+).*Guide star lost', line)
            if mlost:
                lost_dt_str = mlost.group(1)
                tried = False
                for fmt in ["%Y/%m/%d %H:%M:%S", "%Y-%m-%d %H:%M:%S"]:
                    try:
                        lost_dt = datetime.strptime(lost_dt_str, fmt)
                        star_lost_times.append(lost_dt)
                        tried = True
                        break
                    except ValueError:
                        pass
                if not tried:
                    pass

            # 3) Guide data line, e.g. "1,0.576,"Mount",-0.057,0.104,-0.097,0.071,..."
            mdata = guide_data_pat.match(line)
            if mdata and current_session_start:
                frame_idx = int(mdata.group(1))
                rel_t     = float(mdata.group(2))
                ra_raw    = float(mdata.group(5))
                dec_raw   = float(mdata.group(6))

                abs_time  = current_session_start + timedelta(seconds=rel_t)
                frames.append({
                    "abs_time": abs_time,
                    "ra_pix":   ra_raw,
                    "dec_pix":  dec_raw
                })

    return frames, star_lost_times

# -------------------------
# 4) Compute RMS per image
# -------------------------
def compute_rms_for_image(image, frames):
    """
    For a single image [start_dt, end_dt], gather frames, compute RMS RA/DEC/Total in arcsec + µm.
    Returns a dict with the values plus n_frames used.
    """
    start_t = image["start_dt"]
    end_t   = image["end_dt"]

    subset = [fr for fr in frames if start_t <= fr["abs_time"] <= end_t]
    n = len(subset)

    if n == 0:
        return {
            "rms_ra_as": None, "rms_dec_as": None, "rms_total_as": None,
            "rms_ra_um": None, "rms_dec_um": None, "rms_total_um": None,
            "n_frames":  0
        }

    ra_as  = [fr["ra_pix"]  * PIXEL_SCALE_ARCSEC for fr in subset]
    dec_as = [fr["dec_pix"] * PIXEL_SCALE_ARCSEC for fr in subset]
    ra_um  = [fr["ra_pix"]  * PIXEL_SIZE_UM     for fr in subset]
    dec_um = [fr["dec_pix"] * PIXEL_SIZE_UM     for fr in subset]

    def rms(vals):
        return math.sqrt(sum(v*v for v in vals) / len(vals))

    total_as = [math.sqrt(rx*rx + dx*dx) for (rx,dx) in zip(ra_as, dec_as)]
    total_um = [math.sqrt(rx*rx + dx*dx) for (rx,dx) in zip(ra_um, dec_um)]

    return {
        "rms_ra_as":    rms(ra_as),
        "rms_dec_as":   rms(dec_as),
        "rms_total_as": rms(total_as),
        "rms_ra_um":    rms(ra_um),
        "rms_dec_um":   rms(dec_um),
        "rms_total_um": rms(total_um),
        "n_frames":     n
    }

def count_star_lost_for_image(image, star_lost_times):
    """Number of star-lost events in [start_dt, end_dt]."""
    s = image["start_dt"]
    e = image["end_dt"]
    return sum(1 for t in star_lost_times if s <= t <= e)

def compute_overall_rms(frames):
    """Compute overall RMS for the entire session's frames."""
    if not frames:
        return None

    ra_pix_vals  = [fr["ra_pix"] for fr in frames]
    dec_pix_vals = [fr["dec_pix"] for fr in frames]

    def rms(vals):
        return math.sqrt(sum(v*v for v in vals) / len(vals))

    ra_as_vals  = [v * PIXEL_SCALE_ARCSEC for v in ra_pix_vals]
    dec_as_vals = [v * PIXEL_SCALE_ARCSEC for v in dec_pix_vals]
    tot_as_vals = [math.sqrt((r*r)+(d*d)) for r,d in zip(ra_as_vals, dec_as_vals)]

    ra_um_vals  = [v * PIXEL_SIZE_UM for v in ra_pix_vals]
    dec_um_vals = [v * PIXEL_SIZE_UM for v in dec_pix_vals]
    tot_um_vals = [math.sqrt((r*r)+(d*d)) for r,d in zip(ra_um_vals, dec_um_vals)]

    return {
        "ra_as":  rms(ra_as_vals),
        "dec_as": rms(dec_as_vals),
        "tot_as": rms(tot_as_vals),
        "ra_um":  rms(ra_um_vals),
        "dec_um": rms(dec_um_vals),
        "tot_um": rms(tot_um_vals),
    }

# Create a dictionary of PHD2 parameter descriptions - add after the "def parse_phd2_log_header(log_path):" function
def get_phd2_parameter_descriptions():
    """Returns a dictionary with descriptions for PHD2 log header parameters"""
    return {
        "PHD2 version": "Version number of the PHD2 software used",
        "Log version": "Version number of the log format (should be 2.5)",
        "Log enabled at": "Timestamp when logging was started",
        "Guiding Status": "Status message for when guiding began",
        "Exposure": "Guide camera exposure time in seconds",
        "Pixel scale": "Size of guide camera pixels in arcseconds",
        "Camera": "Model of guide camera used",
        "Mount": "Type of mount connected to PHD2",
        "X guide algorithm": "Algorithm used for RA axis guiding",
        "Y guide algorithm": "Algorithm used for DEC axis guiding",
        "Algorithm": "Guiding algorithm used (usually 'Hysteresis')",
        "Dither": "Indicates which axes are being dithered during guiding",
        "Dither scale": "Amount of random offset applied during dithering",
        "Image noise reduction": "Type of noise reduction applied to guide camera images",
        "Guide-frame time lapse": "Time between guide frames in seconds",
        "Binning": "Binning level used for guide camera",
        "Focal length": "Focal length of the guide scope in millimeters",
        "Search region": "Size of search area for guide star in pixels",
        "Star mass tolerance": "Allowed percentage change in guide star brightness",
        "Star position tolerance": "Allowed sudden change in star position (pixels)",
        "Equipment Profile": "Name of the equipment profile being used",
        "gain": "Guide camera gain setting",
        "full size": "Full resolution of the guide camera in pixels",
        "pixel size": "Physical size of guide camera pixels in microns",
        "xAngle": "Calibration angle for RA axis in degrees",
        "xRate": "Guide rate for RA axis (multiple of sidereal)",
        "yAngle": "Calibration angle for DEC axis in degrees",
        "yRate": "Guide rate for DEC axis (multiple of sidereal)",
        "parity": "Mount calibration parity values",
        "Hysteresis": "Damping factor to reduce oscillations (0-1)",
        "Aggression": "How aggressively corrections are applied (0-1)",
        "Minimum move": "Smallest correction that will be sent to mount (pixels)",
        "RA Aggressiveness": "How aggressively PHD2 corrects RA errors (0-1)",
        "RA Hysteresis": "Damping factor for RA corrections (0-100%)",
        "RA Min move": "Minimum mount movement in RA to respond to errors (pixels)",
        "Dec Aggressiveness": "How aggressively PHD2 corrects DEC errors (0-1)",
        "Dec Hysteresis": "Damping factor for DEC corrections (0-100%)",
        "Dec Min move": "Minimum mount movement in DEC to respond to errors (pixels)",
        "DEC guide mode": "Type of declination guiding (auto, north, south, etc.)",
        "Backlash comp": "Amount of declination backlash compensation (ms)",
        "pulse": "Backlash compensation pulse duration in milliseconds",
        "Calibration step": "Distance in pixels between calibration steps",
        "Max RA duration": "Maximum pulse length for RA corrections (ms)",
        "Max DEC duration": "Maximum pulse length for Dec corrections (ms)",
        "RA Guide Speed": "Mount RA guiding speed as a multiple of sidereal rate",
        "Dec Guide Speed": "Mount DEC guiding speed as a multiple of sidereal rate",
        "CalibrationState": "Status of mount calibration",
        "Timestamp": "Type of timestamps used in the log",
        "Cal Dec": "Declination coordinate used during calibration",
        "Last Cal Issue": "Problems encountered during the last calibration",
        "Dec": "Current declination of the telescope",
        "Hour angle": "Current hour angle of the telescope",
        "Pier side": "Side of pier the telescope is on (East/West)",
        "Rotator pos": "Position angle of the camera rotator",
        "Lock position": "Reference position of the guide star",
        "Star position": "Current position of the guide star",
        "HFD": "Half-flux diameter of the guide star (measure of focus)",
        "XSize": "Width of guide camera chip in pixels",
        "YSize": "Height of guide camera chip in pixels",
        "BinningX": "Horizontal binning factor (1=no binning)",
        "BinningY": "Vertical binning factor (1=no binning)",
        "MaxADU": "Maximum pixel value supported by the guide camera",
        "CalibrationDetails": "Information about the calibration process",
        "INFO": "Additional information messages from PHD2",
        "Calibration Dec": "Declination coordinate used during calibration",
        "Calibration RA": "Right ascension coordinate used during calibration",
        "CalibrationDistance": "Length of calibration movement in pixels",
        "DecSwapEnabled": "Whether PHD2 can automatically swap declination direction",
        "UseDecComp": "Whether declination compensation is enabled",
        "AO": "Adaptive optics device information if present",
        "Last Cal": "When the last calibration was performed",
        "Polar alignment error": "Amount of polar alignment error detected (arcmin)",
        "Side of pier": "Telescope position relative to mount (east or west)",
        "FastSwitch": "Whether fast DEC direction switching is enabled"
    }
    
# Update the parse_phd2_log_header function to add descriptions to the DataFrame
def parse_phd2_log_header(log_path):
    """
    Parse the header section of a PHD2 log file and extract key parameters
    Returns a DataFrame with the header information.
    """
    header_data = []
    parameter_values = {}
    
    try:
        if DEBUG_MODE:
            print(f"[phd2_analysis] Parsing PHD2 header from {log_path}")
        
        # Read the log file
        header_lines = []
        data_section_found = False
        
        with open(log_path, 'r') as f:
            for line in f:
                line = line.strip()
                # Skip empty lines in the header
                if not line:
                    continue
                    
                # Stop when the data section marker is found
                if line.startswith("Frame,Time,"):
                    data_section_found = True
                    break
                
                # Collect header lines
                header_lines.append(line)
        
        if not data_section_found:
            print(f"[phd2_analysis] Warning: Data section marker not found in {log_path}")
        
        if DEBUG_MODE:
            print(f"[phd2_analysis] Found {len(header_lines)} header lines in PHD2 log")
            
        # Get the parameter descriptions
        parameter_descriptions = get_phd2_parameter_descriptions()

        # Process each header line and extract key information
        for line_num, line in enumerate(header_lines):
            # Special handling for the first line which has the version information
            if line_num == 0 and "PHD2 version" in line and "Log version" in line and "Log enabled at" in line:
                try:
                    # Direct string splitting to extract components
                    version_and_log_part, timestamp_part = line.split("Log enabled at", 1)
                    phd_version_part, log_version_part = version_and_log_part.split("Log version", 1)
                    
                    # Clean up extracted values
                    phd_version = phd_version_part.replace("PHD2 version", "").replace(",", "").strip()
                    parameter_values["PHD2 version"] = phd_version if phd_version else "Not specified"
                    
                    log_version = log_version_part.strip()
                    # Remove any trailing periods from log version (sometimes it's "2.5.")
                    if log_version.endswith('.'):
                        log_version = log_version[:-1]
                    parameter_values["Log version"] = log_version
                    
                    parameter_values["Log enabled at"] = timestamp_part.strip()
                    dbg(f"[phd2_analysis DEBUG] Parsed first line: PHD2 version='{phd_version}', Log version='{log_version}', Log enabled at='{timestamp_part.strip()}'")
                except Exception as e:
                    print(f"[phd2_analysis] Error parsing version line: {e}")
                    parameter_values["PHD2 Header Line 1"] = line  # Fallback
                continue
        
            # Special handling for 'Guiding Begins at' line
            if "Guiding Begins at" in line:
                parameter_values["Guiding Status"] = line
                dbg(f"[phd2_analysis DEBUG] Found Guiding Begins line: {line}")
                continue
            
            # Special handling for key equipment information lines
            if any(key in line for key in ["Pixel scale", "Camera", "Mount", "guide algorithm"]):
                dbg(f"[phd2_analysis DEBUG] Found equipment line: {line}")
            
            # Special handling for 'INFO:' lines
            if line.startswith("INFO:"):
                info_content = line.replace("INFO:", "").strip()
                parameter_values["INFO"] = parameter_values.get("INFO", "") + info_content + "; "
                dbg(f"[phd2_analysis DEBUG] Found INFO line: {info_content}")
                continue
            
            # General Key = Value parsing for all other lines
            if "=" in line:
                try:
                    # Handle case where line has multiple KEY=VALUE pairs
                    if line.count("=") > 1 and "," in line:
                        # Line like "Dither = both axes, Dither scale = 1.000, ..."
                        parts = line.split(',')
                        for part in parts:
                            if "=" in part:
                                key, value = part.split("=", 1)
                                parameter_values[key.strip()] = value.strip()
                                dbg(f"[phd2_analysis DEBUG] Found multi-part KV: {key.strip()}='{value.strip()}'")
                    
                    # Special handling for Y guide algorithm line which has a complex format
                    elif "Y guide algorithm" in line and "Minimum move" in line and "Aggression" in line:
                        # Parse complex Y guide algorithm line
                        # Example: "Y guide algorithm = Resist Switch, Minimum move = 0.100 Aggression = 30% FastSwitch = enabled"
                        try:
                            # Extract Y guide algorithm
                            algo_part = line.split("Y guide algorithm =", 1)[1].split(",", 1)[0].strip()
                            parameter_values["Y guide algorithm"] = algo_part
                            dbg(f"[phd2_analysis DEBUG] Parsed Y algorithm: Y guide algorithm='{algo_part}'")
                            
                            # Extract remaining parts
                            remaining = line.split(",", 1)[1] if "," in line else ""
                            
                            # Extract Minimum move
                            if "Minimum move =" in remaining:
                                min_move_part = remaining.split("Minimum move =", 1)[1].split("Aggression =", 1)[0].strip()
                                parameter_values["Minimum move"] = min_move_part
                                dbg(f"[phd2_analysis DEBUG] Parsed Y min move: Minimum move='{min_move_part}'")
                            
                            # Extract Aggression
                            if "Aggression =" in remaining:
                                aggression_part = remaining.split("Aggression =", 1)[1].split("FastSwitch =", 1)[0].strip()
                                parameter_values["Aggression"] = aggression_part
                                dbg(f"[phd2_analysis DEBUG] Parsed Y aggression: Aggression='{aggression_part}'")
                            
                            # Extract FastSwitch
                            if "FastSwitch =" in remaining:
                                fast_switch = remaining.split("FastSwitch =", 1)[1].strip()
                                parameter_values["FastSwitch"] = fast_switch
                                dbg(f"[phd2_analysis DEBUG] Parsed FastSwitch: FastSwitch='{fast_switch}'")
                        except Exception as e:
                            print(f"[phd2_analysis] Error parsing Y guide algorithm line: {e}")
                            parameter_values["Y guide algorithm line"] = line
                    else:
                        # Simple KEY=VALUE line
                        key, value = line.split("=", 1)
                        parameter_values[key.strip()] = value.strip()
                        dbg(f"[phd2_analysis DEBUG] Found simple KV: {key.strip()}='{value.strip()}'")
                except Exception as e:
                    print(f"[phd2_analysis] Error parsing key-value line: {e}")
                    parameter_values[f"PHD2 Header Line {line_num+1}"] = line  # Fallback
                continue
                
            # Any other lines that don't match the above patterns
            dbg(f"[phd2_analysis DEBUG] Unclassified line: {line}")
            parameter_values[f"PHD2 Header Line {line_num+1}"] = line
        
        # Consolidate INFO lines if multiple were found
        if "INFO" in parameter_values:
            parameter_values["INFO"] = parameter_values["INFO"].strip("; ")
        
        if DEBUG_MODE:
            print(f"[phd2_analysis] Extracted {len(parameter_values)} parameters from header")
        
        # Convert collected parameters to DataFrame format with descriptions
        for key, value in parameter_values.items():
            description = parameter_descriptions.get(key, "")
            header_data.append({"Parameter": key, "Value": value, "Description": description})
            
    except Exception as e:
        print(f"[phd2_analysis] Error parsing PHD2 header from {log_path}: {e}")

    return pd.DataFrame(header_data)

# -------------------------
# 5) Main Data Generation Workflow (New Function)
# -------------------------
def generate_phd2_analysis_data():
    # 1) Find logs
    autorun_log_files = find_all_files_with_prefix(RAW_DIR, AUTORUN_LOG_PREFIX, AUTORUN_EXT)
    phd2_log_files    = find_all_files_with_prefix(RAW_DIR, PHD2_LOG_PREFIX, PHD2_EXT)

    # Initialize return values
    per_image_df = pd.DataFrame()
    overall_summary_df = pd.DataFrame()
    first_phd2_header_df = pd.DataFrame()

    if not autorun_log_files:
        print("[phd2_analysis] Error: Could not find any Autorun logs.")
        return per_image_df, overall_summary_df, first_phd2_header_df # Return empty DataFrames
    if not phd2_log_files:
        print("[phd2_analysis] Error: Could not find any PHD2 logs.")
        return per_image_df, overall_summary_df, first_phd2_header_df

    autorun_log_path = autorun_log_files[-1]
    if DEBUG_MODE:
        print(f"[phd2_analysis] Using Autorun Log: {autorun_log_path}")
        print(f"[phd2_analysis] Found PHD2 Logs: {[os.path.basename(p) for p in phd2_log_files]}\n")

    # 2) Parse logs
    images = parse_autorun_log(autorun_log_path)
    
    all_frames = []
    all_star_lost_times = []
    first_log_processed = False

    for phd2_log_path_item in phd2_log_files:
        # Parse header only from the first log file found
        if not first_log_processed:
            first_phd2_header_df = parse_phd2_log_header(phd2_log_path_item)
            first_log_processed = True

        if DEBUG_MODE:
            print(f"[phd2_analysis] Parsing PHD2 Log: {phd2_log_path_item}")
        frames_segment, star_lost_segment = parse_phd2_log(phd2_log_path_item)
        all_frames.extend(frames_segment)
        all_star_lost_times.extend(star_lost_segment)
        if DEBUG_MODE and frames_segment:
            print(f"  -> Found {len(frames_segment)} frames, time range: {frames_segment[0]['abs_time']} to {frames_segment[-1]['abs_time']}")
        elif DEBUG_MODE:
            print(f"  -> No frames found in this segment.")

    all_frames.sort(key=lambda f: f['abs_time'])
    all_star_lost_times = sorted(list(set(all_star_lost_times)))

    if DEBUG_MODE:
        fits_files = [f for f in os.listdir(RAW_DIR) if f.lower().endswith(('.fit', '.fits'))]
        dbg(f"[phd2_analysis DEBUG] FITS files in RAW_DIR: {fits_files}")
        dbg(f"[phd2_analysis DEBUG] Autorun log image filenames: {[img['filename'] for img in images]}")
        for img in images:
            dbg(f"[phd2_analysis DEBUG] Image {img['filename']} start: {img['start_dt']}")
        if all_frames:
            dbg(f"[phd2_analysis DEBUG] Total combined guide frames: {len(all_frames)}")
            dbg(f"[phd2_analysis DEBUG] First 5 combined guide frame times: {[fr['abs_time'] for fr in all_frames[:5]]}")
            dbg(f"[phd2_analysis DEBUG] Last 5 combined guide frame times: {[fr['abs_time'] for fr in all_frames[-5:]]}")
        else:
            dbg("[phd2_analysis DEBUG] No guide frames parsed from any PHD2 log.")

    if not images:
        print("[phd2_analysis] No image exposures found in Autorun log.")
    if not all_frames:
        print("[phd2_analysis] No guide frames found in PHD2 log.")

    # 3) Compute per-image RMS + star-lost
    results_list = [] # Store dictionaries for DataFrame creation
    for img in images:
        metrics   = compute_rms_for_image(img, all_frames)
        lost_cnt  = count_star_lost_for_image(img, all_star_lost_times)
        row = {
            "Img#":            img["image_num"],
            "FITS_File":       img["filename"] or "N/A",
            "Start":           img["start_dt"].strftime("%Y-%m-%d %H:%M:%S"),
            "End":             img["end_dt"].strftime("%Y-%m-%d %H:%M:%S"),
            "Lost":            lost_cnt,
            "RMS_RA_as":       metrics["rms_ra_as"],
            "RMS_DEC_as":      metrics["rms_dec_as"],
            "RMS_TOT_as":      metrics["rms_total_as"],
            "RMS_RA_um":       metrics["rms_ra_um"],
            "RMS_DEC_um":      metrics["rms_dec_um"],
            "RMS_TOT_um":      metrics["rms_total_um"],
            "FramesUsed":      metrics["n_frames"]
        }
        results_list.append(row)
    
    per_image_df = pd.DataFrame(results_list)

    # 4) Compute overall RMS across all frames
    overall_summary_data = compute_overall_rms(all_frames)
    overall_summary_df = pd.DataFrame()
    if overall_summary_data:
        overall_summary_df = pd.DataFrame([
            {
                "Description": "Overall RMS (arcsec)", 
                "RA": overall_summary_data['ra_as'], 
                "DEC": overall_summary_data['dec_as'], 
                "Total": overall_summary_data['tot_as']
            },
            {
                "Description": "Overall RMS (µm)",     
                "RA": overall_summary_data['ra_um'], 
                "DEC": overall_summary_data['dec_um'], 
                "Total": overall_summary_data['tot_um']
            }
        ])

    # 5) Print the results as a table (if debug or run standalone)
    if DEBUG_MODE or (__name__ == "__main__" and not per_image_df.empty):
        def fmt_display(v):
            return f"{v:.2f}" if (v is not None and isinstance(v, (int, float))) else "N/A"

        print("\n[phd2_analysis] Per-Image Results:")
        header_display = [
            "Img#","FITS_File","Start","End","Lost",
            "RMS_RA_as","RMS_DEC_as","RMS_TOT_as",
            "RMS_RA_um","RMS_DEC_um","RMS_TOT_um","FramesUsed"
        ]
        print(", ".join(header_display))
        for r_dict in results_list:
            print(f"{r_dict['Img#']}, {r_dict['FITS_File']}, "
                  f"{r_dict['Start']}, {r_dict['End']}, {r_dict['Lost']}, "
                  f"{fmt_display(r_dict['RMS_RA_as'])}, {fmt_display(r_dict['RMS_DEC_as'])}, {fmt_display(r_dict['RMS_TOT_as'])}, "
                  f"{fmt_display(r_dict['RMS_RA_um'])}, {fmt_display(r_dict['RMS_DEC_um'])}, {fmt_display(r_dict['RMS_TOT_um'])}, "
                  f"{r_dict['FramesUsed']}")

        if not overall_summary_df.empty:
            print("\n[phd2_analysis] Overall RMS across all frames:")
            print(f"  RA:  {overall_summary_data['ra_as']:.2f} arcsec, DEC: {overall_summary_data['dec_as']:.2f} arcsec, TOT: {overall_summary_data['tot_as']:.2f} arcsec")
            print(f"  RA:  {overall_summary_data['ra_um']:.2f} µm,    DEC: {overall_summary_data['dec_um']:.2f} µm,    TOT: {overall_summary_data['tot_um']:.2f} µm")
        else:
            print("\n[phd2_analysis] No frames for overall RMS (empty frames list?).")

    return per_image_df, overall_summary_df, first_phd2_header_df # Return all three DFs

def main():
    per_image_df, overall_summary_df, first_phd2_header_df = generate_phd2_analysis_data()

    if __name__ == "__main__": # Only write CSV if run as a script
        if not per_image_df.empty:
            # 6) Write CSV to the same folder
            csv_name = f"phd2_analysis_{datetime.now():%Y%m%d-%H%M%S}.csv"
            csv_path = out_path(csv_name)
            print(f"\n[phd2_analysis] Saving results to CSV: {csv_path}")

            # For CSV, we might want to format numbers as strings like before
            # Or, keep them as numbers and let Excel/etc handle formatting.
            # For simplicity here, we write the DataFrame as is.
            per_image_df.to_csv(csv_path, index=False)

            # Append overall summary to the CSV
            if not overall_summary_df.empty:
                with open(csv_path, "a", newline="", encoding="utf-8") as out_file:
                    writer = csv.writer(out_file)
                    writer.writerow([]) # Blank line separator
                    writer.writerow(["Overall RMS Summary:"])
                overall_summary_df.to_csv(csv_path, mode='a', header=True, index=False)
            
            # Also write the PHD2 header to its own CSV if run standalone
            if not first_phd2_header_df.empty:
                header_csv_name = f"phd2_header_{datetime.now():%Y%m%d-%H%M%S}.csv"
                header_csv_path = out_path(header_csv_name)
                try:
                    first_phd2_header_df.to_csv(header_csv_path, index=False)
                    print(f"[phd2_analysis] PHD2 Header saved to: {header_csv_path}")
                except Exception as e:
                    print(f"[phd2_analysis] Error writing PHD2 header CSV: {e}")
            
            print("[phd2_analysis] Done.")
        else:
            print("[phd2_analysis] No data generated to write to CSV.")
    
    # For run_all.py to potentially use even if not writing CSV here
    return per_image_df, overall_summary_df, first_phd2_header_df

if __name__ == "__main__":
    main()
