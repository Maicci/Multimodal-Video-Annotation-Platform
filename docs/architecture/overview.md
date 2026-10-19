# Architecture overview

The prototype follows the specification in a staged, maintainable way.

## Layers

1. Browser client: video playback shell, waveform placeholder UI, segment annotation form.
2. FastAPI service: video and annotation endpoints, status tracking, export-ready API surface.
3. Processing layer: modular pipeline for metadata extraction, pose features, acoustic features, and Whisper transcripts.
4. Persistence layer: relational database and object storage can be introduced without changing the API boundary.

## Key design decisions

- Use a shared temporal reference built from actual per-frame timestamps instead of nominal frame rate assumptions.
- Keep segment data and whole-video summary separate to match the annotation model.
- Store annotator ownership explicitly so concurrent work remains isolated.
- Keep multimodal processing behind a service boundary so the project can swap OpenPose, MediaPipe, or RTMPose later.
