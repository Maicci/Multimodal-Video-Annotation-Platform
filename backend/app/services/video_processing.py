"""Asynchronous processing entry point for uploaded videos."""

from __future__ import annotations
from pathlib import Path
from app.services.frame_timing import FrameTimeline
import logging
from contextlib import closing
import json
import subprocess

import psycopg
from app.db.database import Database
from app.repositories.video_repository import start_video_processing

logger = logging.getLogger(__name__)

def generate_thumbnails(
    video_path: str | Path,
    output_dir: str | Path,
    thumbnail_count: int = 100,
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
            str(output_dir / "%d.jpg"),
        ],
        check=True,
    )

def process_video(video_id: str, database_url: str, video_path: str | Path, timeline_path: str | Path, thumbnails_dir: str | Path) -> None:
    try:
        with closing(Database(database_url).connect()) as connection:
            if not start_video_processing(connection, video_id):
                logger.error("Could not start processing for video %s", video_id)
                return
    except psycopg.Error:
        logger.exception("Could not update processing status for video %s", video_id)
        return
    timeline = FrameTimeline.from_video(video_path)
    Path(timeline_path).parent.mkdir(parents=True, exist_ok=True)
    timeline.save(timeline_path)
    generate_thumbnails(video_path, thumbnails_dir)
    
    logger.info("Video %s is ready for asynchronous processing", video_id)