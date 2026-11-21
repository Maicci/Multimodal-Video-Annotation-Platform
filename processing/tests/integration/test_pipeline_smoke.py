import os
from pathlib import Path

import pytest


def test_pipeline_processes_video_with_all_tools():
    source = os.environ.get('MULTIMODAL_SMOKE_VIDEO')
    if not source:
        pytest.skip('Set MULTIMODAL_SMOKE_VIDEO to a video with audio to run the ML smoke test.')

    source_path = Path(source).expanduser()
    if not source_path.is_file():
        pytest.fail(f'MULTIMODAL_SMOKE_VIDEO is not a file: {source_path}')

    from app.services.multimodal_processing import MultimodalProcessingPipeline

    result = MultimodalProcessingPipeline('smoke-test', source_path).run()

    assert result['source_metadata']['audio'] is not None
    for tool_name in ('pose', 'audio_features', 'transcripts'):
        output = result[tool_name]
        assert output['status'] == 'completed', output
        assert isinstance(output['duration_seconds'], (int, float))

    assert result['pose']['frames'], 'Pose backend did not decode any video frames.'
    assert result['audio_features']['windows'], 'openSMILE returned no feature windows.'
    assert isinstance(result['transcripts']['segments'], list)