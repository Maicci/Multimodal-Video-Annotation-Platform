# Multimodal Video Annotation Platform

This repository contains a Python-based research prototype for a browser-driven multimodal video annotation system.

To try the current frontend and backend together, use the Docker setup in
[`test-space/README.md`](test-space/README.md).

## Features

- React + TypeScript frontend
- FastAPI backend
- PostgreSQL database
- Administrator and annotator roles
- Video upload and processing
- Video assignment to annotators
- Timestamp- and frame-based annotation segments
- Visual and audio descriptions
- Whole-video summaries
- Annotation submission and review
- Audio transcription
- JSON and CSV annotation export
- Docker-based development environment
- Automated backend tests

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


This platform is under development.
