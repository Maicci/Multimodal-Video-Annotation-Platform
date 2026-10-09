# Multimodal Video Annotation Platform

This repository contains a Python-based research prototype for a browser-driven multimodal video annotation system.

## Features in this initial prototype

- FastAPI backend with health and video APIs
- Video upload and listing endpoints
- Segment and summary endpoints consistent with the specification
- Minimal HTML/CSS/JS browser interface to exercise the annotation workflow
- Clear separation of the research payload from the UI shell

## Run locally

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
uvicorn app.main:app --reload
```

Visit http://127.0.0.1:8000 in a browser.

## Project direction

The platform is designed to evolve toward:

- synchronized video and waveform interactions
- multimodal alignment for pose, acoustic features, and speech transcripts
- multi-user annotation with independent data stores
- export and agreement reporting
