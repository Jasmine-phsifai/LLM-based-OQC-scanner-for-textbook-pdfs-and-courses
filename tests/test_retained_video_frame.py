"""Public value contract for one library-retained video frame."""

from pathlib import Path

import pytest

from ocrllm import RetainedVideoFrame


def test_retained_video_frame_rejects_non_jpeg_path() -> None:
    with pytest.raises(ValueError, match="must use the .jpg extension"):
        RetainedVideoFrame(0, 0.0, Path("frame-00000000.png"))
