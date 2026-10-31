# Multimodal Video Annotation Platform

This repository contains the starter skeleton for a browser-driven multimodal video annotation system. The `backend` and `frontend` directories are reserved for application development; the runnable example lives in `examples/`.

## Example application

The example is a FastAPI prototype with health, video, segment, and summary endpoints and a minimal browser interface.

Run it from the repository root:

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
python -m pip install -e ./examples/backend
uvicorn examples.backend.app.main:app --reload
```

Visit http://127.0.0.1:8000 in a browser.

## Project direction

The platform is designed to evolve toward:

- synchronized video and waveform interactions
- multimodal alignment for pose, acoustic features, and speech transcripts
- multi-user annotation with independent data stores
- export and agreement reporting

## Contributors

- [esaab](https://github.com/esaab)
