"""Asynchronous processing entry point for uploaded videos."""

from __future__ import annotations
from pathlib import Path
from app.services.frame_timing import FrameTimeline
import logging
from contextlib import closing
import json
import shutil
import subprocess

from app.services.waveform import generate_waveform
import psycopg
from app.db.database import Database
from app.repositories.video_repository import (
    complete_video_processing,
    fail_video_processing,
    save_timeline_info,
    start_video_processing,
)

logger = logging.getLogger(__name__)

def generate_thumbnails(
    video_path: str | Path,
    output_dir: str | Path,
    thumbnail_count: int = 12,
) -> None:
    video_path = Path(video_path)
    output_dir = Path(output_dir)

    output_dir.mkdir(parents=True, exist_ok=True)

    result = subprocess.run(
        [
            "ffprobe",
            "-v", "error",
            "-show_entries", "format=duration",
            "-of", "json",
            str(video_path),
        ],
        capture_output=True,
        text=True,
        check=True,
    )

    data = json.loads(result.stdout)
    duration = float(data["format"]["duration"])

    if duration <= 0:
        raise ValueError("Video duration must be positive")
    fps_value = thumbnail_count / duration

    subprocess.run(
        [
            "ffmpeg",
            "-i",
            str(video_path),
            "-vf",
            f"fps={fps_value},scale=240:-1",
            "-q:v",
            "6",
            "-frames:v",
            str(thumbnail_count),
            str(output_dir / "%d.jpg"),
        ],
        check=True,
    )

    generated = sorted(output_dir.glob("*.jpg"), key=lambda path: int(path.stem))
    if not generated:
        raise ValueError("No thumbnails were generated")
    for number in range(1, thumbnail_count + 1):
        target = output_dir / f"{number}.jpg"
        if not target.exists():
            shutil.copyfile(generated[-1], target)


def _mark_failed(database_url: str, video_id: str) -> None:
    try:
        with closing(Database(database_url).connect()) as connection:
            fail_video_processing(connection, video_id)
    except psycopg.Error:
        logger.exception("Could not mark video %s as failed", video_id)


def process_video(video_id: str, database_url: str, video_path: str | Path, timeline_path: str | Path, thumbnails_dir: str | Path) -> None:
    try:
        with closing(Database(database_url).connect()) as connection:
            if not start_video_processing(connection, video_id):
                logger.error("Could not start processing for video %s", video_id)
                return
    except psycopg.Error:
        logger.exception("Could not update processing status for video %s", video_id)
        return

    try:
        timeline = FrameTimeline.from_video(video_path)
        Path(timeline_path).parent.mkdir(parents=True, exist_ok=True)
        timeline.save(timeline_path)

        # Record the timeline in the database right after it is saved
        with closing(Database(database_url).connect()) as connection:
            save_timeline_info(
                connection,
                video_id,
                timeline_path=str(timeline_path),
                frame_count=timeline.frame_count,
                is_vfr=not timeline.is_constant_frame_rate(),
            )

        generate_thumbnails(video_path, thumbnails_dir)
        generate_waveform(video_path)
        with closing(Database(database_url).connect()) as connection:
            complete_video_processing(connection, video_id)
    except Exception:
        logger.exception("Processing failed for video %s", video_id)
        _mark_failed(database_url, video_id)
        return

    logger.info("Video %s processing completed", video_id)
