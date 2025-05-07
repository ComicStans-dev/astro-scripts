from typing import List

from utils.session_model import ExposureMeta, ImageFrame, GuideFrame, GuideEvent
from shared.timestamp_utils import within


def associate(expos: List[ExposureMeta], images: List[ImageFrame], guides: List[GuideFrame], events: List[GuideEvent], tol_filename: float = 60.0):
    """Populate links and confidence on ExposureMeta list."""

    # Index images by filename for fast lookup
    image_by_name = {im.fits_name: im for im in images}

    for meta in expos:
        # 1) attach image
        img = image_by_name.get(meta.fits_name)
        conf = 0.0
        if img:
            meta.image_frame = img
            conf = 1.0
        else:
            # fallback by time overlap
            for im in images:
                if within(im.start_dt_utc, meta.autorun_line_dt_utc, tol_filename):
                    meta.image_frame = im
                    conf = 0.5
                    break

        meta.confidence = conf

        # 2) guide frames subset
        if meta.image_frame:
            im = meta.image_frame
            meta.guide_frames = [g for g in guides if im.start_dt_utc <= g.abs_dt_utc <= im.end_dt_utc]
            meta.guide_events = [ev for ev in events if im.start_dt_utc <= ev.abs_dt_utc <= im.end_dt_utc]

    return expos 