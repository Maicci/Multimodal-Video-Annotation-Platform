"""Half-open segment boundaries resolved against actual frame timestamps.

Frame N is the exclusive end sentinel (the end of the video). Nearest
boundary is selected; ties choose the earlier boundary.
"""
from pathlib import Path
import numpy as np
from fastapi import HTTPException
from app.services.frame_timing import FrameTimeline


def timeline_for(video):
    path = Path(video.storage_path).parent.parent / "timelines" / f"{Path(video.stored_filename).stem}.npy"
    if not path.exists():
        raise HTTPException(409, "Frame timing is not ready. Wait for video processing.")
    return FrameTimeline.load(path)


def resolve_segment(video, payload):
    timeline = timeline_for(video)
    boundaries = np.append(timeline.timestamps, timeline.end_time)
    start = int(np.argmin(np.abs(boundaries - payload.start_time)))
    end = int(np.argmin(np.abs(boundaries - payload.end_time)))
    if start >= end:
        raise HTTPException(422, "Select at least one video frame.")
    for supplied, resolved in ((payload.start_frame, start), (payload.end_frame, end)):
        if supplied is not None and supplied != resolved:
            raise HTTPException(422, "Frame and timestamp boundaries do not correspond.")
    return payload.model_copy(update={"start_time": float(boundaries[start]), "end_time": float(boundaries[end]), "start_frame": start, "end_frame": end})
