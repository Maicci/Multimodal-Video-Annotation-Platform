from fastapi.testclient import TestClient

from app.main import app


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
