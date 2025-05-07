import re
import os
from pathlib import Path
from typing import List
from datetime import datetime, timedelta

from shared.timestamp_utils import parse_any
from utils.session_model import ExposureMeta


EXPOSURE_LINE = re.compile(
    r'^(\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2})\s+Exposure\s+([\d.]+)s\s+image\s+(\d+)#',
    re.IGNORECASE,
)
FILENAME_LINE = re.compile(r'^(Light_\S+\.fit[s]?)$', re.IGNORECASE)

time_fmt = "%Y/%m/%d %H:%M:%S"


def parse_autorun_log(log_path: Path) -> List[ExposureMeta]:
    """Parse a N.I.N.A Autorun log and return ExposureMeta list (UTC)."""
    metas: List[ExposureMeta] = []
    last_meta = None

    with open(log_path, "r", encoding="utf-8") as fh:
        for raw in fh:
            line = raw.strip()
            m_exp = EXPOSURE_LINE.match(line)
            if m_exp:
                start_local_str, exp_s_str, img_num_str = m_exp.groups()
                start_dt = datetime.strptime(start_local_str, time_fmt)
                exposure_s = float(exp_s_str)
                end_dt = start_dt + timedelta(seconds=exposure_s)
                last_meta = ExposureMeta(
                    image_num=int(img_num_str),
                    fits_name="",  # placeholder until next line supplies it
                    exposure_s=exposure_s,
                    autorun_line_dt_utc=parse_any(start_dt.isoformat()),
                )
                metas.append(last_meta)
                continue

            if last_meta and not last_meta.fits_name:
                m_fn = FILENAME_LINE.match(line)
                if m_fn:
                    last_meta.fits_name = m_fn.group(1)
    return metas 