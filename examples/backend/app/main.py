from __future__ import annotations

from pathlib import Path
import uuid
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app.services.multimodal_processing import ProcessingJobManager


BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR.parent / 'frontend' / 'src' / 'assets'
TEMPLATE_DIR = BASE_DIR / 'templates'
UPLOAD_DIR = BASE_DIR.parent.parent / 'data' / 'uploads'
MAX_UPLOAD_BYTES = 1024 ** 3
ALLOWED_VIDEO_SUFFIXES = {'.mp4', '.mov', '.mkv', '.webm'}


app = FastAPI(
    title='Multimodal Video Annotation Platform',
    description='Prototype annotation platform for synchronized multimodal video analysis.',
    version='0.1.0',
)

app.mount('/static', StaticFiles(directory=str(STATIC_DIR)), name='static')

VIDEO_STORE: Dict[str, Dict] = {}
SEGMENT_STORE: Dict[str, List[Dict]] = {}
SUMMARY_STORE: Dict[str, Dict] = {}
PROCESSING_JOBS = ProcessingJobManager()


class VideoCreateRequest(BaseModel):
    title: str = Field(..., min_length=1)
    filename: str = Field(..., min_length=1)
    annotator_id: str = Field(..., min_length=1)


class VideoResponse(BaseModel):
    id: str
    title: str
    filename: str
    annotator_id: str
    status: str = 'uploaded'
    duration_seconds: Optional[float] = None


class SegmentRequest(BaseModel):
    start_frame: int = Field(..., ge=0)
    end_frame: int = Field(..., ge=0)
    start_timestamp: float = 0.0
    end_timestamp: float = 0.0
    video_description: str = ''
    audio_description: str = ''


class SummaryRequest(BaseModel):
    summary: str = Field(..., min_length=1)


class VideoSummaryResponse(BaseModel):
    video_id: str
    annotator_id: str
    summary: str


class ProcessingJobResponse(BaseModel):
    id: str
    video_id: str
    status: str
    created_at: str
    updated_at: str
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


@app.get('/api/health')
def healthcheck() -> Dict[str, str]:
    return {'status': 'ok', 'project': 'multimodal-video-annotation-platform'}


@app.get('/', response_class=HTMLResponse)
def index() -> HTMLResponse:
    html_path = TEMPLATE_DIR / 'index.html'
    return HTMLResponse(content=html_path.read_text(encoding='utf-8'))


@app.get('/api/videos', response_model=List[VideoResponse])
def list_videos() -> List[VideoResponse]:
    return [VideoResponse(**video) for video in VIDEO_STORE.values()]


@app.post('/api/videos', response_model=VideoResponse, status_code=201)
def create_video(payload: VideoCreateRequest) -> VideoResponse:
    video_id = f'video-{len(VIDEO_STORE) + 1:03d}'
    item = {
        'id': video_id,
        'title': payload.title,
        'filename': payload.filename,
        'annotator_id': payload.annotator_id,
        'status': 'uploaded',
        'duration_seconds': None,
    }
    VIDEO_STORE[video_id] = item
    SEGMENT_STORE.setdefault(video_id, [])
    SUMMARY_STORE.setdefault(video_id, {'video_id': video_id, 'annotator_id': payload.annotator_id, 'summary': ''})
    return VideoResponse(**item)


@app.post('/api/videos/{video_id}/upload')
def upload_video(video_id: str, file: UploadFile = File(...)) -> Dict[str, Any]:
    if video_id not in VIDEO_STORE:
        raise HTTPException(status_code=404, detail='Video not found')
    filename = Path(file.filename or '').name
    if Path(filename).suffix.lower() not in ALLOWED_VIDEO_SUFFIXES:
        raise HTTPException(status_code=415, detail='Unsupported video format')

    destination_dir = UPLOAD_DIR / video_id
    destination_dir.mkdir(parents=True, exist_ok=True)
    destination = destination_dir / filename
    temporary = destination.with_name(f'.{destination.name}.{uuid.uuid4().hex}.part')
    size = 0
    try:
        with temporary.open('wb') as output:
            while chunk := file.file.read(1024 * 1024):
                size += len(chunk)
                if size > MAX_UPLOAD_BYTES:
                    raise HTTPException(status_code=413, detail='Video exceeds the 1 GiB upload limit')
                output.write(chunk)
        temporary.replace(destination)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise

    VIDEO_STORE[video_id]['source_path'] = str(destination)
    VIDEO_STORE[video_id]['filename'] = filename
    return {'video_id': video_id, 'filename': filename, 'status': 'uploaded', 'size_bytes': size}


@app.post('/api/videos/{video_id}/processing', response_model=ProcessingJobResponse, status_code=202)
def start_video_processing(video_id: str) -> ProcessingJobResponse:
    video = VIDEO_STORE.get(video_id)
    if video is None:
        raise HTTPException(status_code=404, detail='Video not found')
    source_path = video.get('source_path')
    if not source_path or not Path(source_path).is_file():
        raise HTTPException(status_code=409, detail='Upload a video before starting processing')
    return ProcessingJobResponse(**PROCESSING_JOBS.submit(video_id, source_path))


@app.get('/api/processing/jobs/{job_id}', response_model=ProcessingJobResponse)
def get_processing_job(job_id: str) -> ProcessingJobResponse:
    job = PROCESSING_JOBS.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail='Processing job not found')
    return ProcessingJobResponse(**job)


@app.get('/api/videos/{video_id}/segments')
def get_segments(video_id: str) -> Dict[str, List[Dict]]:
    if video_id not in VIDEO_STORE:
        raise HTTPException(status_code=404, detail='Video not found')
    return {'video_id': video_id, 'segments': SEGMENT_STORE.get(video_id, [])}


@app.post('/api/videos/{video_id}/segments', status_code=201)
def create_segment(video_id: str, payload: SegmentRequest) -> Dict[str, object]:
    if video_id not in VIDEO_STORE:
        raise HTTPException(status_code=404, detail='Video not found')
    segment_id = f'segment-{len(SEGMENT_STORE[video_id]) + 1:03d}'
    item = {
        'id': segment_id,
        'start_frame': payload.start_frame,
        'end_frame': payload.end_frame,
        'start_timestamp': payload.start_timestamp,
        'end_timestamp': payload.end_timestamp,
        'video_description': payload.video_description,
        'audio_description': payload.audio_description,
    }
    SEGMENT_STORE[video_id].append(item)
    return {'video_id': video_id, 'segment': item}


@app.get('/api/videos/{video_id}/summary')
def get_summary(video_id: str) -> VideoSummaryResponse:
    if video_id not in VIDEO_STORE:
        raise HTTPException(status_code=404, detail='Video not found')
    summary = SUMMARY_STORE.get(video_id, {'video_id': video_id, 'annotator_id': 'unknown', 'summary': ''})
    return VideoSummaryResponse(**summary)


@app.post('/api/videos/{video_id}/summary')
def update_summary(video_id: str, payload: SummaryRequest) -> VideoSummaryResponse:
    if video_id not in VIDEO_STORE:
        raise HTTPException(status_code=404, detail='Video not found')
    summary = {
        'video_id': video_id,
        'annotator_id': VIDEO_STORE[video_id]['annotator_id'],
        'summary': payload.summary,
    }
    SUMMARY_STORE[video_id] = summary
    return VideoSummaryResponse(**summary)
