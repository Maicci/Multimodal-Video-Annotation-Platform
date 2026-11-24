# Sprint 2 processing foundations

Video preparation and transcription use `QUEUED`, `RUNNING`, `COMPLETED`, and
`FAILED`. Startup migrates the previous video states `PENDING` and `PROCESSING`.
Video preparation saves failure details, visible in the administrator video list.

After a video is ready, an administrator can choose **Transcribe audio**. This
creates a persisted job and responds immediately; the background task runs the
CPU `faster-whisper` model. Transcription status and failures appear separately
from video readiness. A failed transcript does not block annotation. Starting
again creates a new attempt; an active attempt prevents duplicate jobs and video
deletion. Successful job results remain in PostgreSQL across restarts.

When the latest transcription completes, **View transcript** opens the saved
text beside a video preview. Click a timestamp to seek and play that passage,
then compare what you hear with the generated words. The viewer shows the model
and detected language, and explicitly reports when no speech was recognized.
Use **Close** or Escape to return to the video list. The viewer and processing
controls are available only to administrators; reviewers and annotators cannot
retrieve these results through the API either.

API:

- `POST /api/videos/{video_id}/transcription`: administrator only; returns 202
  with the new queued job. Returns 409 for active jobs or videos not yet ready.
- `GET /api/processing/jobs/{job_id}`: administrator only; includes state,
  model, timestamps, error, and the automatic result when complete.
- `GET /api/videos`: includes the latest `transcription_job_id`, status and
  error for administrators. These fields are null for other roles.

Annotators cannot start jobs or retrieve automatic transcripts. Transcript text
is not rendered in the annotation workspace.

The Docker backend includes the `whisper` dependency extra. `WHISPER_MODEL`
defaults to the multilingual `tiny` model. Its first use downloads weights;
`WHISPER_CACHE_DIR` points to the persistent `whisper_models` Docker volume.
The audio is decoded by FFmpeg into mono 16 kHz PCM and passed directly to the
model as samples. No GPU is required. CPU jobs are serialized in this process.

## Run and verify

```sh
docker compose -f test-space/compose.yaml up -d --build backend frontend
docker compose -f test-space/compose.yaml exec -T -w /workspace/backend backend pytest -q
docker compose -f test-space/compose.yaml exec -T -w /workspace/backend -e RUN_WHISPER_SMOKE=1 backend pytest tests/api/test_whisper_smoke.py -q
```

The optional real-model test generates speech with FFmpeg's Flite source,
uploads the resulting video, starts transcription through the API, and checks
for recognized words. It uses an isolated test database schema. The normal
suite tests job transitions, persistence, access rules, duplicate prevention,
failure visibility, and retry/restart handling without downloading a model.
The Playwright transcript-viewer test uses a controlled transcript response
with a real uploaded video to check playback, timestamps, closing, empty/error
states, and hidden controls for other roles. It does not measure Whisper accuracy.

## Prototype limits

This runner assumes **one API process**, as configured in the local Compose
setup. On startup, queued/running work from the previous process is marked
failed with a restart explanation. It can then be retried; failed video preparation
currently requires uploading the video again. This prevents silently stuck jobs,
but is not a durable distributed worker or automatic retry system. Do not deploy
multiple API workers with this recovery mechanism. A dedicated queue worker and
the remaining modalities belong to the broader Sprint 3 integration work (#32).

The generated-speech smoke test validates wiring and basic transcription, not
accuracy across languages, accents, noise, or the project's research dataset.
