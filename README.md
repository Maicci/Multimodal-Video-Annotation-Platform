# Multimodal Video Annotation Platform

This repository contains a Python-based research prototype for a browser-driven multimodal video annotation system.

## Features in this initial prototype

- FastAPI backend with health and video APIs
- Video upload and listing endpoints
- In-memory background processing jobs with status polling
- Optional CPU pipeline for MediaPipe Pose, openSMILE, and Whisper transcription
- Segment and summary endpoints consistent with the specification
- Minimal HTML/CSS/JS browser interface to exercise the annotation workflow
- Clear separation of the research payload from the UI shell

## Run locally

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
python -m pip install -e ./examples/backend
uvicorn examples.backend.app.main:app --reload
```

Visit http://127.0.0.1:8000 in a browser.

For multimodal processing, install `requirements-ml.txt`, put the MediaPipe Pose Landmarker Lite model at `models/pose_landmarker_lite.task` (or set `MEDIAPIPE_POSE_MODEL`), then create a video, upload it, and start a job:

```bash
python -m pip install -r requirements-ml.txt
curl -X POST http://127.0.0.1:8000/api/videos -H 'Content-Type: application/json' \
	-d '{"title":"Sample","filename":"sample.mp4","annotator_id":"annotator-1"}'
curl -X POST http://127.0.0.1:8000/api/videos/video-001/upload -F 'file=@sample.mp4'
curl -X POST http://127.0.0.1:8000/api/videos/video-001/processing
curl http://127.0.0.1:8000/api/processing/jobs/<job-id>
```

The pose backend decision, normalized result schemas, and sample measurements are in [docs/processing.md](docs/processing.md).

## Project direction

The platform is designed to evolve toward:

- synchronized video and waveform interactions
- multimodal alignment for pose, acoustic features, and speech transcripts
- multi-user annotation with independent data stores
- export and agreement reporting
