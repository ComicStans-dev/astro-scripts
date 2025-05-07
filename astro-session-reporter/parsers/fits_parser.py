from pathlib import Path
from typing import List
from astropy.io import fits
from shared.timestamp_utils import parse_any
from utils.session_model import ImageFrame
from datetime import timedelta


HEADER_KEYS = [
    "DATE-OBS",
    "EXPTIME",
    "RA",
    "DEC",
    "ALT",
    "AZ",
    "OBJECT",
    "NAXIS1",
    "NAXIS2",
]


def parse_fits_headers(fits_files: List[Path]) -> List[ImageFrame]:
    frames: List[ImageFrame] = []
    for fp in fits_files:
        try:
            hdr = fits.getheader(fp)
        except Exception as exc:
            print(f"[fits_parser] Cannot read header for {fp}: {exc}")
            continue

        try:
            start_dt = parse_any(hdr.get("DATE-OBS"))
        except Exception as exc:
            print(f"[fits_parser] Invalid DATE-OBS in {fp}: {exc}")
            continue

        exposure_s = float(hdr.get("EXPTIME", hdr.get("EXPOSURE", 0.0)))
        end_dt = start_dt + timedelta(seconds=exposure_s)

        ra_deg = float(hdr.get("RA", 0.0))
        dec_deg = float(hdr.get("DEC", 0.0))

        alt_deg = float(hdr.get("ALT", hdr.get("ALT_DEG", 0.0)))
        az_deg = float(hdr.get("AZ", hdr.get("AZ_DEG", 0.0)))

        frame = ImageFrame(
            fits_name=fp.name,
            start_dt_utc=start_dt,
            end_dt_utc=end_dt,
            ra_deg=ra_deg,
            dec_deg=dec_deg,
            alt_deg=alt_deg,
            az_deg=az_deg,
            exposure_s=exposure_s,
            mean_pix=float(hdr.get("MEAN_PIX", 0.0)),
            std_pix=float(hdr.get("STD_PIX", 0.0)),
        )
        frames.append(frame)
    return frames 