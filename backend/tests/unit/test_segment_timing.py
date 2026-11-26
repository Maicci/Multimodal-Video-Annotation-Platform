from types import SimpleNamespace
import numpy as np
import pytest
from fastapi import HTTPException
from app.schemas.segment import SegmentInput
from app.services.segment_timing import resolve_segment


def test_vfr_boundaries_and_repeated_edits(tmp_path):
    original = tmp_path / "original"
    original.mkdir()
    timeline = tmp_path / "timelines"
    timeline.mkdir()
    np.save(timeline / "sample.npy", [0, 0.04, 0.1, 0.18])
    video = SimpleNamespace(storage_path=str(original / "sample.mp4"), stored_filename="sample.mp4", duration_seconds=None)
    payload = SegmentInput(title="Scene", start_time=0.035, end_time=0.175)
    resolved = resolve_segment(video, payload)
    assert (resolved.start_frame, resolved.end_frame) == (1, 3)
    assert (resolved.start_time, resolved.end_time) == (0.04, 0.18)
    for _ in range(100):
        assert resolve_segment(video, resolved) == resolved
    last = resolve_segment(video, SegmentInput(title="All", start_time=0, end_time=0.24))
    assert (last.start_frame, last.end_frame) == (0, 4)
    with pytest.raises(HTTPException):
        resolve_segment(video, SegmentInput(title="Mismatch", start_time=0.04, end_time=0.18, start_frame=2))
    with pytest.raises(HTTPException):
        resolve_segment(video, SegmentInput(title="Empty", start_time=0.01, end_time=0.015))


@pytest.mark.parametrize("timestamps,duration", [([0], 0.033333), ([0, 0.041667], 0.083333)])
def test_segment_can_end_at_exact_video_duration(tmp_path, timestamps, duration):
    (tmp_path / "timelines").mkdir()
    np.save(tmp_path / "timelines" / "clip.npy", timestamps)
    video = SimpleNamespace(storage_path=str(tmp_path / "original" / "clip.mp4"),
                            stored_filename="clip.mp4", duration_seconds=duration)
    payload = SegmentInput(title="Whole clip", start_time=0, end_time=duration)
    resolved = resolve_segment(video, payload)
    assert resolved.end_frame == len(timestamps)
    assert resolved.end_time == duration
    assert resolve_segment(video, resolved) == resolved
    if len(timestamps) == 2:
        legacy = resolved.model_copy(update={"end_time": 0.083334})
        assert resolve_segment(video, legacy, stored=True) == resolved
