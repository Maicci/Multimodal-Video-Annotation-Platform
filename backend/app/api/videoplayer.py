"""

"""
from app.repositories.video_repository import find_video_by_id
from app.db.models.video import Video
from app.api.dependencies import Connection
from app.services.frame_timing import FrameTimeline
from pathlib import Path
from typing import Annotated
from fastapi import APIRouter, HTTPException, Depends, Query
from app.api.video_access import media_user
from fastapi.responses import FileResponse

router = APIRouter(dependencies=[Depends(media_user)])

def _timeline_path(video: Video) -> Path:
    return Path(video.storage_path).parent.parent / "timelines" / f"{Path(video.stored_filename).stem}.npy"


def _thumbnail_path(video: Video, thumbnail: int) -> Path:
    return Path(video.storage_path).parent.parent / "thumbnails" / Path(video.stored_filename).stem / f"{thumbnail}.jpg"


# Route to stream the video
@router.get("/videos/{video_id}/stream")
def stream_video(video_id: str, connection: Connection):
    video = find_video_by_id(connection, video_id)

    if video is None:
        raise HTTPException(
            status_code=404,
            detail="Video not found",
        )

    video_path = Path(video.storage_path)

    if not video_path.exists():
        raise HTTPException(
            status_code=404,
            detail="Video file not found",
        )

    return FileResponse(
        path=video_path,
        media_type=video.mime_type,
    )

# Route to get the timeline information
@router.get("/videos/{video_id}/timeline")
def get_timeline(video_id: str, connection: Connection):
    video = find_video_by_id(connection, video_id)

    if video is None:
        raise HTTPException(
            status_code=404,
            detail="Video not found",
        )

    timeline_path = _timeline_path(video)

    if not timeline_path.exists():
        raise HTTPException(
            status_code=404,
            detail="Timeline not found",
        )

    timeline = FrameTimeline.load(timeline_path, duration=video.duration_seconds)

    return {
        "frame_count": timeline.frame_count,
        "duration": timeline.end_time,
        "boundaries": [*timeline.timestamps.tolist(), timeline.end_time],
    }

# Route to get the frame number for a given time
@router.get("/videos/{video_id}/frame")
def get_frame(
    video_id: str,
    time: Annotated[float, Query(allow_inf_nan=False)],
    connection: Connection,
):
    video = find_video_by_id(connection, video_id)

    if video is None:
        raise HTTPException(
            status_code=404,
            detail="Video not found",
        )

    timeline_path = _timeline_path(video)

    if not timeline_path.exists():
        raise HTTPException(
            status_code=404,
            detail="Timeline not found",
        )

    timeline = FrameTimeline.load(timeline_path, duration=video.duration_seconds)

    return {
        "frame": timeline.time_to_frame(time),
    }

# Route to get the time for a given frame number
# Route to get the time for a given frame number
@router.get("/videos/{video_id}/frame-time")
def get_frame_time(
    video_id: str,
    frame: Annotated[int, Query(ge=0)],
    connection: Connection,
):
    video = find_video_by_id(connection, video_id)

    if video is None:
        raise HTTPException(
            status_code=404,
            detail="Video not found",
        )

    timeline_path = _timeline_path(video)

    if not timeline_path.exists():
        raise HTTPException(
            status_code=404,
            detail="Timeline not found",
        )

    timeline = FrameTimeline.load(timeline_path, duration=video.duration_seconds)

    if frame >= timeline.frame_count:
        raise HTTPException(422, f"Frame must be between 0 and {timeline.frame_count - 1}")
    return {
        "time": timeline.frame_to_time(frame),
    }

# Route to get a thumbnail image for a given frame number
@router.get("/videos/{video_id}/thumbnails/{thumbnail}")
def get_thumbnail(
    video_id: str,
    thumbnail: int,
    connection: Connection,
):
    video = find_video_by_id(connection, video_id)

    if video is None:
        raise HTTPException(
            status_code=404,
            detail="Video not found",
        )

    thumbnail_path = _thumbnail_path(video, thumbnail)

    if not thumbnail_path.exists():
        raise HTTPException(
            status_code=404,
            detail="Thumbnail not found",
        )

    return FileResponse(
        path=thumbnail_path,
        media_type="image/jpeg",
    )


@router.get("/videos/{video_id}/waveform")
def waveform(video_id: str, connection: Connection):
    from app.services.waveform import load_waveform
    video = find_video_by_id(connection, video_id)
    if video is None:
        raise HTTPException(404, "Video not found")
    try:
        return load_waveform(video.storage_path)
    except Exception:
        raise HTTPException(503, "Waveform processing failed. Try again after processing completes.")
