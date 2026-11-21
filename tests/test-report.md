# Test Report

Date: 2026-10-26

## Results

| Scope | Command | Outcome |
| --- | --- | --- |
| API and processing | `.venv/bin/python -m pytest tests processing/tests -q` | 5 passed, 1 skipped |
| Backend skeleton | `.venv/bin/python -m pytest backend/tests -q` | No tests collected; this is accepted by the backend CI workflow |
| Frontend JavaScript | CI-equivalent `node --check` over `frontend/src/**/*.js` | Skipped: no JavaScript source files found |

## Coverage Notes

- The processing smoke test is opt-in and was skipped because `MULTIMODAL_SMOKE_VIDEO` was not provided.
- The API background-job test replaces the processing pipeline with a mock; it does not run the ML tools.
- These results do not validate Whisper, openSMILE, pose inference, OpenPose, or browser end-to-end behavior.

## Follow-up Sample Run

- `tests/testvideo/cat_dog.mp4` contains AV1 video and Opus audio. The multimodal pipeline extracted audio features, but OpenCV decoded zero pose frames; the strengthened smoke test correctly fails for this input.
- A temporary H.264/AAC transcode passed the smoke test with 25 sampled frames and one openSMILE feature window. MediaPipe detected no person landmarks, and Whisper returned no transcript segments. These empty detections are plausible for this clip, but it does not validate positive pose detection or speech transcription.
- The source video was left unchanged, and the transcode was kept outside the repository.
