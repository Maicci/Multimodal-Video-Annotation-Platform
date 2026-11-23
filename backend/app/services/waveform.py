"""Generate compact waveform peaks on the video's time axis."""
import json
from pathlib import Path
import subprocess
from tempfile import NamedTemporaryFile
import numpy as np


def waveform_path(video_path):
    path = Path(video_path)
    return path.parent.parent / "waveforms" / f"{path.stem}.json"


def generate_waveform(video_path):
    info = json.loads(subprocess.run([
        "ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(video_path),
    ], check=True, capture_output=True, text=True).stdout)
    duration = float(info["format"]["duration"])
    has_audio = any(stream["codec_type"] == "audio" for stream in info["streams"])
    peaks = []
    if has_audio:
        raw = subprocess.run([
            "ffmpeg", "-v", "error", "-i", str(video_path), "-map", "0:a:0", "-ac", "1",
            "-af", "aresample=1000:async=1:first_pts=0", "-ar", "1000", "-f", "s16le", "-",
        ], check=True, capture_output=True).stdout
        samples = np.frombuffer(raw, dtype="<i2").astype(float) / 32768
        count = max(1, min(2000, int(duration * 20)))
        edges = np.linspace(0, max(1, int(duration * 1000)), count + 1).astype(int)
        peaks = [float(np.max(np.abs(samples[a:b]))) if len(samples[a:b]) else 0 for a, b in zip(edges[:-1], edges[1:])]
    result = {"duration": duration, "status": "completed" if has_audio else "no_audio", "peaks": peaks}
    target = waveform_path(video_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(mode="w", dir=target.parent, suffix=".tmp", delete=False) as temporary:
        temporary.write(json.dumps(result))
        temporary_path = Path(temporary.name)
    try:
        temporary_path.replace(target)
    finally:
        temporary_path.unlink(missing_ok=True)
    return result


def load_waveform(video_path):
    path = waveform_path(video_path)
    if path.exists():
        return json.loads(path.read_text())
    return generate_waveform(video_path)
