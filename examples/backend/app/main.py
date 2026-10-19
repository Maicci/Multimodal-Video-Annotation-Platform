from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field


EXAMPLES_ROOT = Path(__file__).resolve().parents[2]
STATIC_DIR = EXAMPLES_ROOT / 'frontend' / 'src' / 'assets'
TEMPLATE_DIR = Path(__file__).resolve().parent / 'templates'


app = FastAPI(
    title='Multimodal Video Annotation Platform',
    description='Prototype annotation platform for synchronized multimodal video analysis.',
    version='0.1.0',
)

app.mount('/static', StaticFiles(directory=str(STATIC_DIR)), name='static')

VIDEO_STORE: Dict[str, Dict] = {}
SEGMENT_STORE: Dict[str, List[Dict]] = {}
SUMMARY_STORE: Dict[str, Dict] = {}


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
