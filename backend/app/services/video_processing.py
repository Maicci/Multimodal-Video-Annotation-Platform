"""Asynchronous processing entry point for uploaded videos."""

from __future__ import annotations

import logging
from contextlib import closing

import psycopg
from app.db.database import Database
from app.repositories.video_repository import start_video_processing

logger = logging.getLogger(__name__)


def process_video(video_id: str, database_url: str) -> None:
    try:
        with closing(Database(database_url).connect()) as connection:
            if not start_video_processing(connection, video_id):
                logger.error("Could not start processing for video %s", video_id)
                return
    except psycopg.Error:
        logger.exception("Could not update processing status for video %s", video_id)
        return
    logger.info("Video %s is ready for asynchronous processing", video_id)
