"""Initial source metadata extraction using ffprobe."""

from __future__ import annotations

import json
import logging
import subprocess
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class VideoMetadataError(Exception):
    """Raised when ffprobe cannot extract usable video metadata."""


@dataclass(frozen=True)
class VideoMetadata:
    duration_seconds: float | None
    width: int | None
    height: int | None
    fps: float | None
    codec: str | None


def _optional_float(value: Any) -> float | None:
    if value in (None, "", "N/A"):
        return None
    return float(value)


def _frame_rate(value: Any) -> float | None:
    if value in (None, "", "N/A", "0/0"):
        return None
    return float(Fraction(value))


def extract_video_metadata(path: Path) -> VideoMetadata:
    try:
        result = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration:stream=codec_type,codec_name,width,height,avg_frame_rate,r_frame_rate,duration",
                "-of",
                "json",
                str(path),
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=30,
        )
        probe_result = json.loads(result.stdout)
        streams = probe_result.get("streams", [])
        video_stream = next(
            stream for stream in streams if stream.get("codec_type") == "video"
        )
        format_info = probe_result.get("format", {})
        duration = _optional_float(video_stream.get("duration"))
        if duration is None:
            duration = _optional_float(format_info.get("duration"))
        frame_rate = video_stream.get("avg_frame_rate") or video_stream.get(
            "r_frame_rate"
        )
        return VideoMetadata(
            duration_seconds=duration,
            width=video_stream.get("width"),
            height=video_stream.get("height"),
            fps=_frame_rate(frame_rate),
            codec=video_stream.get("codec_name"),
        )
    except (
        OSError,
        subprocess.SubprocessError,
        ValueError,
        KeyError,
        StopIteration,
        TypeError,
    ) as error:
        logger.exception("Could not extract metadata for %s", path)
        raise VideoMetadataError("Video metadata extraction failed") from error
