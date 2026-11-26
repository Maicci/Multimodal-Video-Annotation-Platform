"""Persisted background transcription jobs for the single-process prototype."""
import logging
import os
import subprocess
import tempfile
import wave
from threading import Lock
from importlib.metadata import version
from pathlib import Path

from psycopg.types.json import Jsonb
import numpy as np
from app.db.database import Database

logger = logging.getLogger(__name__)
_worker_lock = Lock()


def transcribe(source: str, model_name: str) -> dict:
    from faster_whisper import WhisperModel

    # Audio is extracted explicitly so a missing track is reported as a failed
    # job instead of being mistaken for a successfully transcribed silent clip.
    with tempfile.TemporaryDirectory(prefix="transcription-") as directory:
        audio = Path(directory) / "audio.wav"
        extraction = subprocess.run([
            "ffmpeg", "-nostdin", "-v", "error", "-y", "-i", source,
            "-map", "0:a:0", "-vn", "-ac", "1", "-af", "aresample=16000:async=1:first_pts=0", "-ar", "16000", "-c:a", "pcm_s16le", str(audio),
        ], capture_output=True, text=True)
        if extraction.returncode:
            raise ValueError("Audio extraction failed. Check that the video has a valid audio track.")
        model = WhisperModel(model_name, device="cpu", compute_type="int8",
                             download_root=os.getenv("WHISPER_CACHE_DIR", "/workspace/models"))
        with wave.open(str(audio), "rb") as pcm:
            samples = np.frombuffer(pcm.readframes(pcm.getnframes()), dtype="<i2").astype(np.float32) / 32768.0
        segments, info = model.transcribe(samples, beam_size=1, vad_filter=True)
        return {
            "provider": "faster-whisper", "version": version("faster-whisper"),
            "model": model_name, "device": "cpu", "compute_type": "int8",
            "language": info.language,
            "segments": [{"start_seconds": float(s.start), "end_seconds": float(s.end), "text": s.text.strip()} for s in segments],
        }


def run_transcription(database_url: str, job_id: str) -> None:
    with _worker_lock:
        _run_transcription(database_url, job_id)


def _run_transcription(database_url: str, job_id: str) -> None:
    database = Database(database_url)
    with database.connect() as connection:
        job = connection.execute("""
            UPDATE processing_jobs SET status = 'RUNNING', started_at = CURRENT_TIMESTAMP
            WHERE id = %s AND status = 'QUEUED'
            RETURNING video_id, model
        """, (job_id,)).fetchone()
        if job is None:
            return
        video = connection.execute("SELECT storage_path FROM videos WHERE id = %s", (job["video_id"],)).fetchone()
    try:
        result = transcribe(video["storage_path"], job["model"])
        with database.connect() as connection:
            connection.execute("""
                UPDATE processing_jobs SET status = 'COMPLETED', result = %s,
                    finished_at = CURRENT_TIMESTAMP WHERE id = %s AND status = 'RUNNING'
            """, (Jsonb(result), job_id))
    except Exception as error:
        logger.exception("Transcription job %s failed", job_id)
        message = f"{type(error).__name__}: {str(error)[:1000]}"
        if isinstance(error, ImportError):
            message = "Whisper is not installed. Rebuild the backend with the whisper dependency extra."
        with database.connect() as connection:
            connection.execute("""
                UPDATE processing_jobs SET status = 'FAILED', error = %s,
                    finished_at = CURRENT_TIMESTAMP WHERE id = %s AND status = 'RUNNING'
            """, (message, job_id))


def recover_interrupted_jobs(database: Database) -> None:
    # This application currently runs one API process. An interrupted task is
    # made explicitly retryable instead of remaining "running" after restart.
    with database.connect() as connection:
        connection.execute("""
            UPDATE processing_jobs SET status = 'FAILED',
                error = 'Processing interrupted by server restart. Start transcription again.',
                finished_at = CURRENT_TIMESTAMP WHERE status IN ('QUEUED', 'RUNNING')
        """)
        connection.execute("""
            UPDATE videos SET processing_status = 'FAILED',
                processing_error = 'Video processing interrupted by server restart. Upload the video again.',
                updated_at = CURRENT_TIMESTAMP WHERE processing_status IN ('QUEUED', 'RUNNING')
        """)
