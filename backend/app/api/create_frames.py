# This script extracts 100 thumbnail frames from a video file and saves them as JPEG images for the video player timeline.

from pathlib import Path
import subprocess
import json

# Hardcoded path for test video and output directory
VIDEO_PATH = Path("../storage/videos/example.mp4")
OUTPUT_DIR = Path("../storage/videos/example_frames")

# Create output directory if it does not exist
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Get video duration with ffprobe
result = subprocess.run(
    [
        "ffprobe",
        "-v", "error",
        "-show_entries", "format=duration",
        "-of", "json",
        str(VIDEO_PATH),
    ],
    capture_output=True,
    text=True,
    check=True,
)

data = json.loads(result.stdout)
duration = float(data["format"]["duration"])

# Create about 100 thumbnails evenly across the video
fps_value = 100 / duration

subprocess.run(
    [
        "ffmpeg",
        "-i",
        str(VIDEO_PATH),
        "-vf",
        f"fps={fps_value},scale=240:-1",
        "-q:v",
        "6",
        str(OUTPUT_DIR / "%d.jpg"),
    ],
    check=True,
)

print("100 thumbnails generated successfully.")
