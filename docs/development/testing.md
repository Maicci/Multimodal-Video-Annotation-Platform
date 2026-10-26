# Testing

Run backend tests from the repository root with `python -m pytest backend/tests`.
The processing integration smoke test is opt-in and is skipped unless
`MULTIMODAL_SMOKE_VIDEO` points to a video file with an audio stream. Install the
optional ML dependencies and pose model as described in [processing.md](../processing.md),
then run it with:

```sh
MULTIMODAL_SMOKE_VIDEO=/path/to/video-with-audio.mp4 python -m pytest processing/tests/integration/test_pipeline_smoke.py
```

The smoke test runs MediaPipe Pose, openSMILE, and faster-whisper against that
video and checks tool status, decoded pose frames, and audio feature windows.
Transcript segments may be empty for clips without speech. It is not required by
the main test suite or the processing CI job.
