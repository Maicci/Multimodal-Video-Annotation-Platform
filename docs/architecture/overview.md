# Architecture overview

The prototype follows the specification in a staged, maintainable way.

## Layers

1. Browser client: video playback shell, waveform placeholder UI, segment annotation form.
2. FastAPI service: video and annotation endpoints, status tracking, export-ready API surface.
3. Processing layer: a single-worker in-memory job queue runs metadata extraction, MediaPipe pose, openSMILE features, and Whisper transcription.
4. Persistence layer: relational database and object storage can be introduced without changing the API boundary.

## Key design decisions

- Use a shared temporal reference built from actual per-frame timestamps instead of nominal frame rate assumptions.
- Keep segment data and whole-video summary separate to match the annotation model.
- Store annotator ownership explicitly so concurrent work remains isolated.
- Keep multimodal processing behind a service boundary so the project can swap OpenPose, MediaPipe, or RTMPose later.
- Processing jobs and uploaded video metadata are in memory; uploaded bytes are stored under `data/uploads/`. This is a single-process prototype, not a durable production queue.
- The local pose backend decision and the normalized tool-output contracts are recorded in [processing.md](processing.md).
