from __future__ import annotations

from io import BytesIO
from pathlib import Path

import pytest

from app.services.video_storage import VideoTooLargeError, store_video


def test_store_video_preserves_bytes_and_normalizes_extension(tmp_path: Path) -> None:
    content = b"unchanged video bytes"
    storage_directory = tmp_path / "videos"

    stored_video = store_video(
        BytesIO(content),
        original_filename="sample.MOV",
        storage_directory=storage_directory,
        max_size_bytes=len(content),
    )

    assert stored_video.path.parent == storage_directory
    assert stored_video.filename.endswith(".mov")
    assert stored_video.path.name == stored_video.filename
    assert stored_video.path.read_bytes() == content
    assert stored_video.size_bytes == len(content)


def test_store_video_removes_partial_file_when_size_limit_is_exceeded(
    tmp_path: Path,
) -> None:
    storage_directory = tmp_path / "videos"

    with pytest.raises(VideoTooLargeError):
        store_video(
            BytesIO(b"video bytes"),
            original_filename="sample.mp4",
            storage_directory=storage_directory,
            max_size_bytes=5,
        )

    assert list(storage_directory.iterdir()) == []


def test_store_video_removes_partial_file_when_source_read_fails(
    tmp_path: Path,
) -> None:
    class FailingSource(BytesIO):
        def read(self, size: int = -1) -> bytes:
            if self.tell() == 0:
                return super().read(4)
            raise OSError("source read failed")

    storage_directory = tmp_path / "videos"

    with pytest.raises(OSError, match="source read failed"):
        store_video(
            FailingSource(b"video bytes"),
            original_filename="sample.mp4",
            storage_directory=storage_directory,
            max_size_bytes=100,
        )

    assert list(storage_directory.iterdir()) == []
