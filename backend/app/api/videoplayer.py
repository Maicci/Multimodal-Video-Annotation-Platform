"""

"""
from app.repositories.video_repository import find_video_by_id
from app.api.dependencies import Connection
from app.services.frame_timing import FrameTimeline
from pathlib import Path
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

router = APIRouter()
PROJECT_ROOT = Path(__file__).resolve().parents[3]


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

    video_stem = Path(video.stored_filename).stem

    timeline_path = (
        PROJECT_ROOT
        / "storage"
        / "videos"
        / "timelines"
        / f"{video_stem}.npy"
    )

    if not timeline_path.exists():
        raise HTTPException(
            status_code=404,
            detail="Timeline not found",
        )

    timeline = FrameTimeline.load(timeline_path)

    return {
        "frame_count": timeline.frame_count,
        "duration": timeline.end_time,
    }

# Route to get the frame number for a given time
@router.get("/videos/{video_id}/frame")
def get_frame(
    video_id: str,
    time: float,
    connection: Connection,
):
    video = find_video_by_id(connection, video_id)

    if video is None:
        raise HTTPException(
            status_code=404,
            detail="Video not found",
        )

    video_stem = Path(video.stored_filename).stem

    timeline_path = (
        PROJECT_ROOT
        / "storage"
        / "videos"
        / "timelines"
        / f"{video_stem}.npy"
    )

    if not timeline_path.exists():
        raise HTTPException(
            status_code=404,
            detail="Timeline not found",
        )

    timeline = FrameTimeline.load(timeline_path)

    return {
        "frame": timeline.time_to_frame(time),
    }

# Route to get the time for a given frame number
# Route to get the time for a given frame number
@router.get("/videos/{video_id}/frame-time")
def get_frame_time(
    video_id: str,
    frame: int,
    connection: Connection,
):
    video = find_video_by_id(connection, video_id)

    if video is None:
        raise HTTPException(
            status_code=404,
            detail="Video not found",
        )

    video_stem = Path(video.stored_filename).stem

    timeline_path = (
        PROJECT_ROOT
        / "storage"
        / "videos"
        / "timelines"
        / f"{video_stem}.npy"
    )

    if not timeline_path.exists():
        raise HTTPException(
            status_code=404,
            detail="Timeline not found",
        )

    timeline = FrameTimeline.load(timeline_path)

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

    video_stem = Path(video.stored_filename).stem

    thumbnail_path = (
        PROJECT_ROOT
        / "storage"
        / "videos"
        / "thumbnails"
        / video_stem
        / f"{thumbnail}.jpg"
    )

    if not thumbnail_path.exists():
        raise HTTPException(
            status_code=404,
            detail="Thumbnail not found",
        )

    return FileResponse(
        path=thumbnail_path,
        media_type="image/jpeg",
    )
