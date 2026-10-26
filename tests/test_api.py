import time

from fastapi.testclient import TestClient

from examples.backend.app.main import app


client = TestClient(app)


def test_healthcheck():
    response = client.get('/api/health')
    assert response.status_code == 200
    assert response.json()['status'] == 'ok'


def test_create_video():
    payload = {
        'title': 'Sample video',
        'filename': 'sample.mp4',
        'annotator_id': 'annotator-1',
    }
    response = client.post('/api/videos', json=payload)
    assert response.status_code == 201
    body = response.json()
    assert body['title'] == 'Sample video'
    assert body['filename'] == 'sample.mp4'
    assert body['annotator_id'] == 'annotator-1'


def test_processing_requires_an_uploaded_video():
    response = client.post('/api/videos', json={
        'title': 'Pending video',
        'filename': 'pending.mp4',
        'annotator_id': 'annotator-1',
    })
    video_id = response.json()['id']

    response = client.post(f'/api/videos/{video_id}/processing')

    assert response.status_code == 409


def test_upload_and_background_processing_job(tmp_path, monkeypatch):
    from app.services.multimodal_processing import MultimodalProcessingPipeline

    monkeypatch.setattr('examples.backend.app.main.UPLOAD_DIR', tmp_path)
    monkeypatch.setattr(
        MultimodalProcessingPipeline,
        'run',
        lambda self: {
            'video_id': self.video_id,
            'pose': {'status': 'completed'},
            'audio_features': {'status': 'completed'},
            'transcripts': {'status': 'completed'},
        },
    )
    created = client.post('/api/videos', json={
        'title': 'Process me',
        'filename': 'sample.mp4',
        'annotator_id': 'annotator-1',
    })
    video_id = created.json()['id']
    uploaded = client.post(
        f'/api/videos/{video_id}/upload',
        files={'file': ('sample.mp4', b'prototype video bytes', 'video/mp4')},
    )

    assert uploaded.status_code == 200
    assert uploaded.json()['status'] == 'uploaded'
    assert uploaded.json()['size_bytes'] == len(b'prototype video bytes')

    started = client.post(f'/api/videos/{video_id}/processing')
    assert started.status_code == 202
    job_id = started.json()['id']
    deadline = time.monotonic() + 2
    job = client.get(f'/api/processing/jobs/{job_id}').json()
    while job['status'] in ('queued', 'processing') and time.monotonic() < deadline:
        job = client.get(f'/api/processing/jobs/{job_id}').json()

    assert job['status'] == 'completed'
    assert job['result']['video_id'] == video_id


def test_upload_rejects_unsupported_file_type(tmp_path, monkeypatch):
    monkeypatch.setattr('examples.backend.app.main.UPLOAD_DIR', tmp_path)
    created = client.post('/api/videos', json={
        'title': 'Wrong file',
        'filename': 'document.pdf',
        'annotator_id': 'annotator-1',
    })

    response = client.post(
        f"/api/videos/{created.json()['id']}/upload",
        files={'file': ('document.pdf', b'not a video', 'application/pdf')},
    )

    assert response.status_code == 415
