from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List


@dataclass
class ProcessingStatus:
    video_id: str
    status: str = 'queued'
    message: str = ''
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat(timespec='seconds'))


class MultimodalProcessingPipeline:
    """Placeholder service for media extraction and alignment tasks.

    The real implementation would integrate OpenPose, openSMILE, Whisper, and
    timeline alignment logic for variable-frame-rate sources.
    """

    def __init__(self, video_id: str):
        self.video_id = video_id
        self.status = ProcessingStatus(video_id=video_id, status='queued', message='Pipeline initialized')

    def run(self) -> Dict[str, object]:
        self.status.status = 'processing'
        self.status.message = 'Extracting metadata, pose, audio features, and transcripts.'

        result = {
            'video_id': self.video_id,
            'source_metadata': {'format': 'mp4', 'frame_rate': 25.0},
            'pose': {'provider': 'OpenPose or MediaPipe fallback', 'frames': []},
            'audio_features': {'provider': 'openSMILE', 'samples': []},
            'transcripts': {'provider': 'Whisper', 'segments': []},
            'timeline_alignment': {
                'method': 'shared per-frame timestamp map with resampling to common axis',
                'notes': 'Variable-frame-rate video is normalized to actual timestamps before alignment.'
            },
        }

        self.status.status = 'completed'
        self.status.message = 'Multimodal processing pipeline finished for the sample prototype.'
        return result


def build_alignment_reference(frame_times: List[float]) -> Dict[str, List[float]]:
    """Return a stable alignment reference based on actual per-frame timestamps."""
    return {'frame_times': list(frame_times)}
