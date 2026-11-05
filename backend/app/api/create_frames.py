# This script extracts frames from a video file and saves them as JPEG images to be used in the video player

from pathlib import Path
import subprocess

# Hardcoded path for test video and output directory
VIDEO_PATH = Path("../storage/videos/example.mp4")
OUTPUT_DIR = Path("../storage/videos/example_frames")

# Create output directory if it does not exist
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Extract 1 thumbnail frame per second
subprocess.run(
    [
        "ffmpeg",
        "-i",
        str(VIDEO_PATH),
        "-vf",
        "fps=1",
        str(OUTPUT_DIR / "%d.jpg"),
    ],
    check=True,
)

print("Frames generated successfully.")