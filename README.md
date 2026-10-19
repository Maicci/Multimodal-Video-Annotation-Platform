# Multimodal Video Annotation Platform

This repository contains a Python-based research prototype for a browser-driven multimodal video annotation system. The codebase is organized into backend, frontend, processing, shared contracts, and documentation areas.

## Features in this initial prototype

- FastAPI backend with health and video APIs
- Video upload and listing endpoints
- Segment and summary endpoints consistent with the specification
- Minimal HTML/CSS/JS browser interface to exercise the annotation workflow
- Clear separation of the research payload from the UI shell

## Run locally

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
python -m pip install -e ./backend
uvicorn backend.app.main:app --reload
```

Visit http://127.0.0.1:8000 in a browser.

Run the backend API tests from the repository root with:

```bash
python -m pytest backend/tests
```

## Project direction

The platform is designed to evolve toward:

- synchronized video and waveform interactions
- multimodal alignment for pose, acoustic features, and speech transcripts
- multi-user annotation with independent data stores
- export and agreement reporting
