import re
from pathlib import Path
from typing import List, Tuple, Optional
from datetime import datetime, timedelta

from shared.timestamp_utils import parse_any
from utils.session_model import GuideFrame, GuideEvent


time_fmt = "%Y-%m-%d %H:%M:%S"

DATA_LINE = re.compile(
    r'^(\d+),(\d+\.\d+),"Mount",([-+\d.]+),([-+\d.]+),([-+\d.]+),([-+\d.]+),',
)

STAR_LOST_PAT = re.compile(r'.*Guide star lost')
GUIDE_BEGINS_PAT = re.compile(r'Guiding Begins at (\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})')


def parse_phd2_log(log_path: Path) -> Tuple[List[GuideFrame], List[GuideEvent], Optional[datetime]]:
    guides: List[GuideFrame] = []
    events: List[GuideEvent] = []
    guiding_start: datetime | None = None

    with open(log_path, "r", encoding="utf-8") as fh:
        for raw in fh:
            line = raw.strip()
            mbeg = GUIDE_BEGINS_PAT.search(line)
            if mbeg:
                guiding_start = datetime.strptime(mbeg.group(1), time_fmt)
                continue

            if STAR_LOST_PAT.search(line):
                if guiding_start is None:
                    continue
                parts = line.split(" ")
                dt_str = " ".join(parts[:2])
                ev_dt = parse_any(dt_str)
                events.append(GuideEvent(abs_dt_utc=ev_dt, type="star_lost", details=""))
                continue

            mdata = DATA_LINE.match(line)
            if mdata and guiding_start:
                frame_idx = int(mdata.group(1))
                rel_t = float(mdata.group(2))
                ra_pix = float(mdata.group(3))
                dec_pix = float(mdata.group(4))
                abs_dt = guiding_start + timedelta(seconds=rel_t)
                guides.append(GuideFrame(abs_dt_utc=abs_dt, ra_pix=ra_pix, dec_pix=dec_pix))

    return guides, events, guiding_start 