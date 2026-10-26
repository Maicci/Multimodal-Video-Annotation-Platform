# Processing prototype



## Install and run

Install the optional backend set with `python -m pip install -r requirements-ml.txt`. Install FFmpeg and FFprobe separately. Download the [MediaPipe Pose Landmarker Lite task model](https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_lite/float16/1/pose_landmarker_lite.task) to `models/pose_landmarker_lite.task`, or set `MEDIAPIPE_POSE_MODEL` to its path. Faster-whisper uses `tiny.en` on CPU with int8 by default; set `WHISPER_MODEL` to choose another model. The first Whisper run downloads its model.

Create a video using `POST /api/videos`, upload the media as multipart field `file` to `POST /api/videos/{video_id}/upload`, then start work with `POST /api/videos/{video_id}/processing`. The response contains a job ID; poll `GET /api/processing/jobs/{job_id}` for `queued`, `processing`, `completed`, `completed_with_warnings`, or `failed`. Uploads are limited to 1 GiB and `.mp4`, `.mov`, `.mkv`, or `.webm` extensions.

The queue and job state live only in this server process. Restarting the server loses job status; this is deliberately a minimal prototype, not a durable queue or a multi-worker deployment.

## OpenPose feasibility and backend decision

OpenPose supports CPU-only and GPU-backed build configurations, but a successful build and inference test have not been completed for this prototype. Its buildability is therefore unverified, not disproven. Keep MediaPipe Pose Landmarker Lite as the prototype backend because it is integrated and has a successful sample-video run recorded below. Revisit OpenPose if its output quality or compatibility becomes a requirement, and verify it with a build and sample inference before switching.

## Normalized output

All timestamps are seconds from the media start. Each tool has `provider`, `status`, and `duration_seconds`; tool errors are isolated so another tool can still return results.

- `pose`: `coordinate_space: normalized_image`; `frames` contain `timestamp_seconds` and `landmarks`. Each landmark has its model index and normalized `x`, `y`, `z`, and `visibility` values. Frames are sampled at up to 2 Hz.
- `audio_features`: `feature_set: eGeMAPSv02`, `feature_level: functionals`, `sample_rate_hz`, and `windows`; each window has start/end seconds and a feature-name-to-number `values` object. The current functionals level yields one full-clip window (88 values for the selected configuration).
- `transcripts`: model, language, language probability, and `segments`; each segment has `start_seconds`, `end_seconds`, and `text`.
- `source_metadata`: filename, duration, dimensions, frame rate, video codec, and optional audio codec/sample rate.
- `processing`: end-to-end duration, tool durations, and process peak resident memory where Linux `/proc` is available.

## Sample measurement

Measured in a single run with a 10-second, 640 x 426, 10-fps H.264/AAC fixture (MediaPipe's sample person image repeated as video, with the short JFK speech clip). Hardware and software environment details were not recorded; timings and memory use will vary by environment. The benchmark model files were already downloaded; model download time is excluded. The tool durations include backend initialization and inference; the pipeline duration also includes FFmpeg audio extraction.

| Stage | Result | Wall time |
| --- | --- | ---: |
| MediaPipe Pose Lite | 20 frames sampled; 20 detections, 33 landmarks each | 1.44 s |
| openSMILE eGeMAPSv02 | 88 functionals | 0.84 s |
| faster-whisper tiny.en, CPU int8 | 2 timestamped transcript segments | 1.43 s |
| Full pipeline | all three stages plus audio extraction | 3.84 s |

Observed process peak RSS was about 650 MiB in this run. Treat this as a rough reference, not a minimum resource requirement; allow additional memory for model cache and input storage. Larger Whisper models, higher pose sampling rates, and concurrent workers increase resource use. This is a single synthetic 10-second sample, not a throughput guarantee. The speech was recognized as “And so my fellow Americans ask not what your country can do for you / ask what you can do for your”.

## Reproduction fixture

The benchmark used the [MediaPipe pose image](https://storage.googleapis.com/mediapipe-assets/pose.jpg) and [Whisper JFK audio fixture](https://raw.githubusercontent.com/openai/whisper/main/tests/jfk.flac); neither is checked into this repository. The pipeline decodes audio to mono 16 kHz PCM with FFmpeg and passes the signal directly to openSMILE, so the `soxi`/`mediainfo` programs are not needed. `av<19` is pinned because PyAV 19 failed the faster-whisper decode call during validation.