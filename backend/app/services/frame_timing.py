"""
Frame <-> timestamp mapping for videos (CFR and VFR).

Timestamps are read from the container's packet timestamp values with ffprobe.

Usage:
  * Once per video: FrameTimeline.from_video() then .save()
  * Afterwards, every time the video is opened:  FrameTimeline.load()

Prone to changes, depending on how the upload/player is implemented.
 
The saved file holds only the timestamps. The frame number is the position in
the array: timestamps[i] is the display time (seconds) of frame i.

- Audio timeline should be synced with this timeline.
 
"""

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path

import numpy as np

def extract_pts(video_path: str | Path, stream: int = 0) -> np.ndarray:
    """Return the timestamps (seconds) of every frame of a video stream, in display order.

    Packets are stored in decode order, sorting gets the display order. 
    Uses ffprobe subprocess to read the container's packet timestamps.
    """
    cmd = [
        "ffprobe", "-v", "error",
        "-select_streams", f"v:{stream}",
        "-show_entries", "packet=pts_time",
        "-of", "json",
        str(video_path),
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    except subprocess.CalledProcessError as exc:
        raise ValueError(f"ffprobe could not read video: {exc.stderr.strip()}") from exc

    packets = json.loads(result.stdout).get("packets", [])
    pts = [float(p["pts_time"]) for p in packets if "pts_time" in p]
    if not pts:
        raise ValueError("No video frames with timestamps found")
    return np.sort(np.array(pts, dtype=np.float64))

@dataclass
class FrameTimeline:
    """Frame index -> timestamp mapping."""

    timestamps: np.ndarray  # timestamps[i] = timestamps (seconds) of frame i

    def __post_init__(self):
        self.timestamps = np.asarray(self.timestamps, dtype=np.float64)
        if self.timestamps.ndim != 1 or len(self.timestamps) == 0:
            raise ValueError("timestamps must be a non-empty 1-D array")

    # ----- construction / storage -----
    @classmethod
    # Construct a FrameTimeline from a video file.
    def from_video(cls, video_path: str | Path, stream: int = 0) -> "FrameTimeline":
        return cls(extract_pts(video_path, stream))

    # Save the timeline to a .npy file, NumPy binary format.
    def save(self, path: str | Path) -> None: 
        np.save(path, self.timestamps)  # appends .npy if missing

    @classmethod
    # load from .npy file and return a FrameTimeline instance
    def load(cls, path: str | Path) -> "FrameTimeline":
        return cls(np.load(path))

    # ----- basic properties -----
    @property
    # Return the timestamp of the first frame (seconds).
    def start_time(self) -> float:
        return float(self.timestamps[0])

    @property
    # Return the number of frames in the timeline.
    def frame_count(self) -> int:
        return len(self.timestamps)
    
    @property
    # Return the typical duration of one frame.
    def frame_duration(self) -> float:
        """Typical duration of one frame (median delta); used for the last frame."""
        if self.frame_count < 2:
            return 0.0
        return float(np.median(np.diff(self.timestamps)))
 

    @property
    # Return the timestamp of the last frame (seconds).
    def end_time(self) -> float:
        """Time at which the last frame stops being displayed."""
        return float(self.timestamps[-1]) + self.frame_duration

    @property
    # Return the average frames per second (fps) of the timeline.
    def average_fps(self) -> float:
        if self.frame_count < 2:
            return 0.0
        span = self.timestamps[-1] - self.timestamps[0]
        if span > 0:
            return (self.frame_count - 1) / span
        else:
            return 0.0


    def is_constant_frame_rate(self, rtol: float = 0.01, atol: float = 0.0015) -> bool:
        """True if every frame interval matches the typical interval.

        Container timestamps are rounded to the time base (e.g. 1 ms in MKV),
        so a CFR file can show +/- 1 tick of jitter. The tolerance allows
        that jitter but is capped.
        """
        if self.frame_count < 3:
            return True
        deltas = np.diff(self.timestamps)
        median = float(np.median(deltas))
        if median <= 0:
            return False
        tol = max(rtol * median, min(atol, 0.1 * median))
        return bool(np.all(np.abs(deltas - median) <= tol))

    # ----- frame -> timestamp -----
    # Return the timestamp (seconds) of a given frame index.
    def frame_to_time(self, frame: int) -> float:
        if not 0 <= frame < self.frame_count:
            raise IndexError(
                f"frame {frame} out of range (0..{self.frame_count - 1})"
            )
        return float(self.timestamps[frame])

    # ----- timestamp -> frame -----
    # Return the index of the frame being displayed at a given timestamp.
    def time_to_frame(self, t: float, strict: bool = False) -> int:
        """Index of the frame being displayed at time t.

        That is the last frame whose timestamp is <= t. With strict=False, times
        before the first frame clamp to frame 0 and times after the end clamp
        to the last frame. With strict=True those raise ValueError.
        """
        if strict and not (self.start_time <= t < self.end_time):
            raise ValueError(
                f"time {t} outside video range [{self.start_time}, {self.end_time})"
            )
        idx = int(np.searchsorted(self.timestamps, t, side="right")) - 1 # searchsorted returns the index of the first timestamp > t, we want one before that
        frame = max(0, min(idx, self.frame_count - 1)) # clamp to valid range
        return frame
