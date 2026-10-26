from __future__ import annotations

import copy
import json
import os
import subprocess
import tempfile
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional


BASE_DIR = Path(__file__).resolve().parents[2]
POSE_MODEL_PATH = Path(os.getenv('MEDIAPIPE_POSE_MODEL', BASE_DIR / 'models/pose_landmarker_lite.task'))


@dataclass
class ProcessingStatus:
    video_id: str
    status: str = 'queued'
    message: str = ''
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec='seconds'))


class MultimodalProcessingPipeline:
    """Run CPU-capable media tools and return timestamp-normalized results."""

    def __init__(self, video_id: str, source_path: str | Path):
        self.video_id = video_id
        self.source_path = Path(source_path)
        self.status = ProcessingStatus(video_id=video_id, status='queued', message='Pipeline initialized')

    def run(self) -> Dict[str, object]:
        if not self.source_path.is_file():
            raise FileNotFoundError(f'Media file does not exist: {self.source_path}')

        started = time.perf_counter()
        self.status.status = 'processing'
        metadata = self._probe_media()
        audio_present = metadata['audio'] is not None
        with tempfile.TemporaryDirectory(prefix='multimodal-') as temp_dir:
            audio_path = Path(temp_dir) / 'audio.wav'
            if audio_present:
                self._extract_audio(audio_path)

            pose = self._timed_tool('mediapipe_pose', lambda: self._run_pose(self.source_path))
            audio_features = self._timed_tool(
                'opensmile',
                lambda: self._run_opensmile(audio_path) if audio_present else self._skipped('openSMILE', 'No audio stream'),
            )
            transcripts = self._timed_tool(
                'whisper',
                lambda: self._run_whisper(audio_path) if audio_present else self._skipped('faster-whisper', 'No audio stream'),
            )

        outputs = (pose, audio_features, transcripts)
        warnings = [output.get('error') for output in outputs if output.get('status') in ('failed', 'unavailable')]
        result = {
            'video_id': self.video_id,
            'source_metadata': metadata,
            'pose': pose,
            'audio_features': audio_features,
            'transcripts': transcripts,
            'timeline_alignment': {
                'method': 'actual media timestamps in seconds',
                'time_unit': 'seconds',
            },
            'processing': {
                'duration_seconds': round(time.perf_counter() - started, 3),
                'tools': {
                    'mediapipe_pose': pose['duration_seconds'],
                    'opensmile': audio_features['duration_seconds'],
                    'whisper': transcripts['duration_seconds'],
                },
                'process_peak_rss_mb': self._peak_rss_mb(),
            },
        }
        self.status.status = 'completed_with_warnings' if warnings else 'completed'
        self.status.message = '; '.join(str(warning) for warning in warnings) if warnings else 'Processing finished.'
        return result

    def _probe_media(self) -> Dict[str, Any]:
        command = [
            'ffprobe', '-v', 'error', '-show_streams', '-show_format', '-of', 'json', str(self.source_path)
        ]
        completed = subprocess.run(command, capture_output=True, text=True, check=True)
        probe = json.loads(completed.stdout)
        video = next((stream for stream in probe.get('streams', []) if stream.get('codec_type') == 'video'), None)
        audio = next((stream for stream in probe.get('streams', []) if stream.get('codec_type') == 'audio'), None)
        if video is None:
            raise ValueError('Input media has no video stream')
        duration = float(video.get('duration') or probe.get('format', {}).get('duration') or 0.0)
        rate = video.get('avg_frame_rate', '0/1').split('/')
        fps = float(rate[0]) / float(rate[1]) if len(rate) == 2 and float(rate[1]) else 0.0
        return {
            'filename': self.source_path.name,
            'duration_seconds': duration,
            'width': int(video.get('width', 0)),
            'height': int(video.get('height', 0)),
            'frame_rate_fps': fps,
            'video_codec': video.get('codec_name'),
            'audio': {'codec': audio.get('codec_name'), 'sample_rate_hz': int(audio.get('sample_rate', 0))} if audio else None,
        }

    def _extract_audio(self, destination: Path) -> None:
        subprocess.run(
            [
                'ffmpeg', '-nostdin', '-v', 'error', '-y', '-i', str(self.source_path), '-map', '0:a:0',
                '-vn', '-ac', '1', '-ar', '16000', '-c:a', 'pcm_s16le', str(destination),
            ],
            capture_output=True,
            text=True,
            check=True,
        )

    @staticmethod
    def _timed_tool(name: str, action: Callable[[], Dict[str, Any]]) -> Dict[str, Any]:
        started = time.perf_counter()
        try:
            result = action()
        except Exception as error:
            result = {'provider': name, 'status': 'failed', 'error': str(error)}
        result['duration_seconds'] = round(time.perf_counter() - started, 3)
        return result

    @staticmethod
    def _skipped(provider: str, reason: str) -> Dict[str, Any]:
        return {'provider': provider, 'status': 'skipped', 'reason': reason}

    @staticmethod
    def _run_pose(source_path: Path) -> Dict[str, Any]:
        if not POSE_MODEL_PATH.is_file():
            return {
                'provider': 'MediaPipe Pose Landmarker',
                'status': 'unavailable',
                'error': f'Pose model not found at {POSE_MODEL_PATH}; set MEDIAPIPE_POSE_MODEL.',
                'coordinate_space': 'normalized_image',
                'frames': [],
            }

        import cv2
        import mediapipe as mp
        from mediapipe.tasks import python as mp_python
        from mediapipe.tasks.python import vision

        options = vision.PoseLandmarkerOptions(
            base_options=mp_python.BaseOptions(model_asset_path=str(POSE_MODEL_PATH)),
            running_mode=vision.RunningMode.VIDEO,
            num_poses=1,
        )
        capture = cv2.VideoCapture(str(source_path))
        frames = []
        sample_interval = 0.5
        next_sample = 0.0
        with vision.PoseLandmarker.create_from_options(options) as detector:
            while True:
                ok, frame = capture.read()
                if not ok:
                    break
                timestamp = capture.get(cv2.CAP_PROP_POS_MSEC) / 1000.0
                if timestamp + 0.001 < next_sample:
                    continue
                next_sample = timestamp + sample_interval
                image = mp.Image(
                    image_format=mp.ImageFormat.SRGB,
                    data=cv2.cvtColor(frame, cv2.COLOR_BGR2RGB),
                )
                result = detector.detect_for_video(image, max(0, round(timestamp * 1000)))
                landmarks = []
                for index, landmark in enumerate(result.pose_landmarks[0] if result.pose_landmarks else []):
                    landmarks.append({
                        'index': index,
                        'x': float(landmark.x),
                        'y': float(landmark.y),
                        'z': float(landmark.z),
                        'visibility': float(landmark.visibility),
                    })
                frames.append({'timestamp_seconds': round(timestamp, 3), 'landmarks': landmarks})
        capture.release()
        return {
            'provider': 'MediaPipe Pose Landmarker',
            'model': POSE_MODEL_PATH.name,
            'status': 'completed',
            'coordinate_space': 'normalized_image',
            'frames': frames,
        }

    @staticmethod
    def _run_opensmile(audio_path: Path) -> Dict[str, Any]:
        import numpy as np
        import opensmile
        import soundfile as sf

        signal, sample_rate = sf.read(str(audio_path), dtype='float32', always_2d=True)
        signal = signal.mean(axis=1) if signal.shape[1] > 1 else signal[:, 0]
        extractor = opensmile.Smile(
            feature_set=opensmile.FeatureSet.eGeMAPSv02,
            feature_level=opensmile.FeatureLevel.Functionals,
        )
        features = extractor.process_signal(signal.astype(np.float32, copy=False), sample_rate)
        values = {str(key): float(value) for key, value in features.iloc[0].items()}
        return {
            'provider': 'openSMILE',
            'status': 'completed',
            'feature_set': 'eGeMAPSv02',
            'feature_level': 'functionals',
            'sample_rate_hz': int(sample_rate),
            'windows': [{'start_seconds': 0.0, 'end_seconds': len(signal) / sample_rate, 'values': values}],
        }

    @staticmethod
    def _run_whisper(audio_path: Path) -> Dict[str, Any]:
        from faster_whisper import WhisperModel

        model_name = os.getenv('WHISPER_MODEL', 'tiny.en')
        model = WhisperModel(model_name, device='cpu', compute_type='int8')
        segments, info = model.transcribe(str(audio_path), beam_size=1, vad_filter=True)
        normalized = [
            {'start_seconds': float(segment.start), 'end_seconds': float(segment.end), 'text': segment.text.strip()}
            for segment in segments
        ]
        return {
            'provider': 'faster-whisper',
            'status': 'completed',
            'model': model_name,
            'language': info.language,
            'language_probability': float(info.language_probability),
            'segments': normalized,
        }

    @staticmethod
    def _peak_rss_mb() -> Optional[float]:
        try:
            with open('/proc/self/status', encoding='utf-8') as status_file:
                for line in status_file:
                    if line.startswith('VmHWM:'):
                        return round(int(line.split()[1]) / 1024, 1)
        except OSError:
            return None
        return None


def build_alignment_reference(frame_times: List[float]) -> Dict[str, List[float]]:
    """Return a stable alignment reference based on actual per-frame timestamps."""
    return {'frame_times': list(frame_times)}


class ProcessingJobManager:
    """Single-process, in-memory queue for the prototype API."""

    def __init__(self) -> None:
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix='media-job')
        self._jobs: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.Lock()

    def submit(self, video_id: str, source_path: str | Path) -> Dict[str, Any]:
        job_id = f'job-{uuid.uuid4().hex[:12]}'
        now = datetime.now(timezone.utc).isoformat(timespec='seconds')
        job = {
            'id': job_id,
            'video_id': video_id,
            'status': 'queued',
            'created_at': now,
            'updated_at': now,
            'result': None,
            'error': None,
        }
        with self._lock:
            self._jobs[job_id] = job
        self._executor.submit(self._run_job, job_id, video_id, Path(source_path))
        return self.get(job_id) or job

    def get(self, job_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            job = self._jobs.get(job_id)
            return copy.deepcopy(job) if job else None

    def _run_job(self, job_id: str, video_id: str, source_path: Path) -> None:
        self._update(job_id, status='processing')
        try:
            result = MultimodalProcessingPipeline(video_id, source_path).run()
            tool_outputs = (result['pose'], result['audio_features'], result['transcripts'])
            status = 'completed_with_warnings' if any(
                output['status'] in ('failed', 'unavailable') for output in tool_outputs
            ) else 'completed'
            self._update(job_id, status=status, result=result)
        except Exception as error:
            self._update(job_id, status='failed', error=str(error))

    def _update(self, job_id: str, **updates: Any) -> None:
        with self._lock:
            job = self._jobs[job_id]
            job.update(updates)
            job['updated_at'] = datetime.now(timezone.utc).isoformat(timespec='seconds')
