from pathlib import Path
from app.services.frame_timing import FrameTimeline

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

router = APIRouter()

# Hardcoded path for test videos
VIDEO_PATH = Path("../storage/videos/example.mp4")
# Hardcoded path for test timeline
TIMELINE_PATH = Path("../storage/videos/example_timeline.npy")
# Hardcoded path for test frames
FRAME_DIR = Path("../storage/videos/example_frames")

# Route to stream the video
@router.get("/videos/1/stream")
def stream_video():
    if not VIDEO_PATH.exists():
        raise HTTPException(
            status_code=404,
            detail="Video not found",
        )

    return FileResponse(
        path=VIDEO_PATH,
        media_type="video/mp4",
    )

# Route to get the timeline information
@router.get("/videos/1/timeline")
def get_timeline():
    if not TIMELINE_PATH.exists():
        raise HTTPException(
            status_code=404,
            detail="Timeline not found",
        )

    timeline = FrameTimeline.load(TIMELINE_PATH)

    return {
        "frame_count": timeline.frame_count,
        "duration": timeline.end_time,
    }

# Route to get the frame number for a given time
@router.get("/videos/1/frame")
def get_frame(time: float):
    if not TIMELINE_PATH.exists():
        raise HTTPException(
            status_code=404,
            detail="Timeline not found",
        )

    timeline = FrameTimeline.load(TIMELINE_PATH)

    return {
        "frame": timeline.time_to_frame(time),
    }

# Route to get the time for a given frame number
@router.get("/videos/1/frame-time")
def get_frame_time(frame: int):
    if not TIMELINE_PATH.exists():
        raise HTTPException(
            status_code=404,
            detail="Timeline not found",
        )

    timeline = FrameTimeline.load(TIMELINE_PATH)

    return {
        "time": timeline.frame_to_time(frame),
    }

# Route to get a thumbnail image for a given frame number
@router.get("/videos/1/thumbnails/{thumbnail}")
def get_thumbnail(thumbnail: int):
    thumbnail_path = FRAME_DIR / f"{thumbnail}.jpg"

    if not thumbnail_path.exists():
        raise HTTPException(
            status_code=404,
            detail="Thumbnail not found",
        )

    return FileResponse(
        path=thumbnail_path,
        media_type="image/jpeg",
    )