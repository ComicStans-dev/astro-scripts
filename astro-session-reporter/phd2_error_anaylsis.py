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

# -------------------------
# 5) Main Workflow
# -------------------------
def main():
    # 1) Find logs
    autorun_log_files = find_all_files_with_prefix(RAW_DIR, AUTORUN_LOG_PREFIX, AUTORUN_EXT)
    phd2_log_files    = find_all_files_with_prefix(RAW_DIR, PHD2_LOG_PREFIX, PHD2_EXT)

    if not autorun_log_files:
        print("Error: Could not find any Autorun logs.")
        return
    if not phd2_log_files:
        print("Error: Could not find any PHD2 logs.")
        return

    # Assuming the latest autorun log is the one to use if multiple exist
    autorun_log_path = autorun_log_files[-1]
    print(f"Using Autorun Log: {autorun_log_path}")
    print(f"Found PHD2 Logs: {[os.path.basename(p) for p in phd2_log_files]}\n")

    # 2) Parse logs
    images = parse_autorun_log(autorun_log_path)
    
    all_frames = []
    all_star_lost_times = []

    for phd2_log_path_item in phd2_log_files:
        print(f"Parsing PHD2 Log: {phd2_log_path_item}")
        frames_segment, star_lost_segment = parse_phd2_log(phd2_log_path_item)
        all_frames.extend(frames_segment)
        all_star_lost_times.extend(star_lost_segment)
        if frames_segment: # Log if this segment contributed frames
            print(f"  -> Found {len(frames_segment)} frames, time range: {frames_segment[0]['abs_time']} to {frames_segment[-1]['abs_time']}")
        else:
            print(f"  -> No frames found in this segment.")

    # Sort all collected frames by absolute time
    all_frames.sort(key=lambda f: f['abs_time'])
    # Star lost times might not need sorting if they are just checked for existence in a range,
    # but sorting and removing duplicates won't hurt if there's overlap.
    all_star_lost_times = sorted(list(set(all_star_lost_times)))

    # Debug: print all FITS files found in RAW_DIR
    fits_files = [f for f in os.listdir(RAW_DIR) if f.lower().endswith(('.fit', '.fits'))]
    print(f"[DEBUG] FITS files in RAW_DIR: {fits_files}")
    print(f"[DEBUG] Autorun log image filenames: {[img['filename'] for img in images]}")

    # Debug: print all image start times
    for img in images:
        print(f"[DEBUG] Image {img['filename']} start: {img['start_dt']}")

    # Debug: print all guide frame times
    if all_frames:
        print(f"[DEBUG] Total combined guide frames: {len(all_frames)}")
        print(f"[DEBUG] First 5 combined guide frame times: {[fr['abs_time'] for fr in all_frames[:5]]}")
        print(f"[DEBUG] Last 5 combined guide frame times: {[fr['abs_time'] for fr in all_frames[-5:]]}")
    else:
        print("[DEBUG] No guide frames parsed from any PHD2 log.")

    if not images:
        print("No image exposures found in Autorun log.")
    if not all_frames:
        print("No guide frames found in PHD2 log.")

    # 3) Compute per-image RMS + star-lost
    results = []
    for img in images:
        metrics   = compute_rms_for_image(img, all_frames)
        lost_cnt  = count_star_lost_for_image(img, all_star_lost_times)

        row = {
            "image_num":       img["image_num"],
            "filename":        img["filename"] or "N/A",
            "start":           img["start_dt"],
            "end":             img["end_dt"],
            "star_lost_count": lost_cnt,
            "rms_ra_as":       metrics["rms_ra_as"],
            "rms_dec_as":      metrics["rms_dec_as"],
            "rms_total_as":    metrics["rms_total_as"],
            "rms_ra_um":       metrics["rms_ra_um"],
            "rms_dec_um":      metrics["rms_dec_um"],
            "rms_total_um":    metrics["rms_total_um"],
            "frames_used":     metrics["n_frames"]
        }
        results.append(row)

    # 4) Compute overall RMS across all frames
    overall = compute_overall_rms(all_frames)

    # 5) Print the results as a table
    print("Per-Image Results:")
    header = [
        "Img#","FITS_File","Start","End","Lost",
        "RMS_RA_as","RMS_DEC_as","RMS_TOT_as",
        "RMS_RA_um","RMS_DEC_um","RMS_TOT_um","FramesUsed"
    ]
    print(", ".join(header))

    def fmt(v):
        return f"{v:.2f}" if (v is not None) else "N/A"

    for r in results:
        print(f"{r['image_num']}, {r['filename']}, "
              f"{r['start']}, {r['end']}, {r['star_lost_count']}, "
              f"{fmt(r['rms_ra_as'])}, {fmt(r['rms_dec_as'])}, {fmt(r['rms_total_as'])}, "
              f"{fmt(r['rms_ra_um'])}, {fmt(r['rms_dec_um'])}, {fmt(r['rms_total_um'])}, "
              f"{r['frames_used']}")

    if overall:
        print("\nOverall RMS across all frames:")
        print(f"  RA:  {overall['ra_as']:.2f} arcsec, DEC: {overall['dec_as']:.2f} arcsec, TOT: {overall['tot_as']:.2f} arcsec")
        print(f"  RA:  {overall['ra_um']:.2f} µm,    DEC: {overall['dec_um']:.2f} µm,    TOT: {overall['tot_um']:.2f} µm")
    else:
        print("\nNo frames for overall RMS (empty frames list?).")

    # 6) Write CSV to the same folder
    csv_name = f"phd2_analysis_{datetime.now():%Y%m%d-%H%M%S}.csv"
    csv_path = out_path(csv_name)
    print(f"\nSaving results to CSV: {csv_path}")

    with open(csv_path, "w", newline="", encoding="utf-8") as out_file:
        writer = csv.writer(out_file)
        writer.writerow(header)

        for r in results:
            row_csv = [
                r["image_num"],
                r["filename"],
                r["start"],
                r["end"],
                r["star_lost_count"],
                fmt(r["rms_ra_as"]),
                fmt(r["rms_dec_as"]),
                fmt(r["rms_total_as"]),
                fmt(r["rms_ra_um"]),
                fmt(r["rms_dec_um"]),
                fmt(r["rms_total_um"]),
                r["frames_used"]
            ]
            writer.writerow(row_csv)

        writer.writerow([])
        writer.writerow(["Overall RMS across entire session:"])
        if overall:
            writer.writerow([
                "arcsec",
                f"RA={overall['ra_as']:.2f}",
                f"DEC={overall['dec_as']:.2f}",
                f"TOT={overall['tot_as']:.2f}"
            ])
            writer.writerow([
                "microns",
                f"RA={overall['ra_um']:.2f}",
                f"DEC={overall['dec_um']:.2f}",
                f"TOT={overall['tot_um']:.2f}"
            ])
        else:
            writer.writerow(["No frames found."])

    print("Done.")

if __name__ == "__main__":
    main()
