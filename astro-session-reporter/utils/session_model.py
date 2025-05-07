from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional

__all__ = [
    "ImageFrame",
    "GuideFrame",
    "GuideEvent",
    "ExposureMeta",
]

@dataclass
class ImageFrame:
    fits_name: str
    start_dt_utc: datetime
    end_dt_utc: datetime
    ra_deg: float
    dec_deg: float
    alt_deg: float
    az_deg: float
    exposure_s: float
    mean_pix: float
    std_pix: float

@dataclass
class GuideFrame:
    abs_dt_utc: datetime
    ra_pix: float
    dec_pix: float

@dataclass
class GuideEvent:
    abs_dt_utc: datetime
    type: str
    details: str = ""

@dataclass
class ExposureMeta:
    image_num: int
    fits_name: str
    exposure_s: float
    autorun_line_dt_utc: datetime

    # Convenience links (populated later)
    image_frame: Optional[ImageFrame] = None
    guide_frames: List[GuideFrame] = field(default_factory=list)
    guide_events: List[GuideEvent] = field(default_factory=list)
    confidence: float = 0.0 