import json
import struct
import wave

from app.services.multimodal_processing import MultimodalProcessingPipeline


def test_pipeline_persists_waveform_and_processing_metadata(tmp_path, monkeypatch):
    source_path = tmp_path / 'sample.mp4'
    source_path.write_bytes(b'video')
    pipeline = MultimodalProcessingPipeline('video-test', source_path)
    monkeypatch.setattr(pipeline, '_probe_media', lambda: {
        'filename': source_path.name,
        'duration_seconds': 0.2,
        'audio': {'codec': 'pcm_s16le', 'sample_rate_hz': 16000},
    })

    def write_audio(destination):
        with wave.open(str(destination), 'wb') as audio:
            audio.setnchannels(1)
            audio.setsampwidth(2)
            audio.setframerate(16000)
            audio.writeframes(struct.pack('<hhhh', 0, 10000, -10000, 0) * 800)

    monkeypatch.setattr(pipeline, '_extract_audio', write_audio)
    monkeypatch.setattr(pipeline, '_run_pose', lambda _: {'status': 'completed'})
    monkeypatch.setattr(pipeline, '_run_opensmile', lambda _: {'status': 'completed'})
    monkeypatch.setattr(pipeline, '_run_whisper', lambda _: {'status': 'completed'})

    result = pipeline.run()

    waveform_path = tmp_path / 'artifacts' / 'waveform.json'
    metadata_path = tmp_path / 'artifacts' / 'processing.json'
    waveform_artifact = json.loads(waveform_path.read_text(encoding='utf-8'))
    processing_artifact = json.loads(metadata_path.read_text(encoding='utf-8'))

    assert result['waveform']['sample_count'] == 3200
    assert len(result['waveform']['points']) == 2
    assert result['waveform']['points'][0]['min'] == -10000 / 32768
    assert result['waveform']['artifact'] == 'artifacts/waveform.json'
    assert waveform_artifact == result['waveform']
    assert processing_artifact == result
    assert result['processing']['status'] == 'Completed'
    assert pipeline.status.status == 'Completed'