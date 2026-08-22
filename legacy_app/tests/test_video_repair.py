import json
from pathlib import Path

import pytest

from OCRLLM.config import AppConfig
from OCRLLM.core.task_runner import CancelledError
from OCRLLM.processors.video import VideoProcessor
from OCRLLM.processors.video_pipeline import VideoProcessContext
from OCRLLM.processors.video_pipeline_selection import VideoPipelineSelection


class _RecordingVisionLLM:
    def __init__(self):
        self.image_calls: list[list[str]] = []

    def set_cancel_event(self, *_args):
        pass

    def chat_with_images(self, *_args, image_paths, **_kwargs):
        self.image_calls.append(list(image_paths))
        return "修复后的板书内容"


class _SingleClientPool:
    pool_size = 1

    def set_cancel_event(self, *_args):
        pass


class _CancelAfterOneVisionLLM:
    def __init__(self):
        self.calls = 0

    def chat_with_images(self, *_args, **_kwargs):
        self.calls += 1
        if self.calls == 1:
            return "第一帧已修复"
        raise CancelledError("任务已取消")


def _video_processor(tmp_path: Path, batch_size: int = 1):
    llm = _RecordingVisionLLM()
    cfg = AppConfig().with_updates(
        paths={"output_dir": str(tmp_path), "temp_dir": str(tmp_path)},
        video={"batch_size": batch_size},
    )
    processor = VideoProcessor(cfg=cfg, llm=llm, api_pool=_SingleClientPool())
    return processor, llm


def _write_frame_info(output_dir: Path, frames: list[dict]):
    (output_dir / "frame_info.json").write_text(
        json.dumps(frames, ensure_ascii=False),
        encoding="utf-8",
    )


def test_repair_board_reads_the_manifest_shape_written_by_phase3(tmp_path):
    original = tmp_path / "frame_001.jpg"
    processed = tmp_path / "processed_frame_001.jpg"
    original.write_bytes(b"original")
    processed.write_bytes(b"processed")
    frame = {"path": str(original), "timestamp": 10.0, "frame_idx": 1}
    _write_frame_info(tmp_path, [frame])
    processor, llm = _video_processor(tmp_path)
    processor._save_phase3_manifest(str(tmp_path), [frame], [str(processed)])
    board_path = tmp_path / "lecture_板书识别.md"
    board_path.write_text(
        "<!-- meta:frame id=frame_001 time=00:10 -->\n\n"
        "<!-- 帧 frame_001 识别失败: provider error -->",
        encoding="utf-8",
    )

    result = processor.repair_board("lecture.mp4", str(tmp_path))

    assert result == str(board_path)
    assert llm.image_calls == [[str(processed)]]
    assert "识别失败" not in board_path.read_text(encoding="utf-8")


def test_repair_board_reports_missing_processed_frames_after_partial_success(tmp_path):
    originals = [tmp_path / f"frame_00{index}.jpg" for index in (1, 2)]
    for original in originals:
        original.write_bytes(b"original")
    processed = tmp_path / "processed_frame_001.jpg"
    processed.write_bytes(b"processed")
    missing_processed = tmp_path / "processed_frame_002.jpg"
    frames = [
        {"path": str(path), "timestamp": float(index * 10), "frame_idx": index}
        for index, path in enumerate(originals, start=1)
    ]
    _write_frame_info(tmp_path, frames)
    processor, llm = _video_processor(tmp_path, batch_size=2)
    processor._save_phase3_manifest(
        str(tmp_path),
        frames,
        [str(processed), str(missing_processed)],
    )
    board_path = tmp_path / "lecture_板书识别.md"
    board_path.write_text(
        "<!-- 批次 1 失败: provider error -->",
        encoding="utf-8",
    )

    with pytest.raises(RuntimeError, match=r"frame_002"):
        processor.repair_board("lecture.mp4", str(tmp_path))

    assert llm.image_calls == [[str(processed)]]
    repaired = board_path.read_text(encoding="utf-8")
    assert "修复后的板书内容" in repaired
    assert "帧 frame_002 识别失败" in repaired


def test_cleanup_keeps_extracted_audio_when_transcript_has_failed_segments(tmp_path):
    audio_path = tmp_path / "lecture.mp3"
    transcript_path = tmp_path / "lecture_录音识别.md"
    info_path = tmp_path / "frame_info.json"
    audio_path.write_bytes(b"audio")
    transcript_path.write_text("（分段 1 识别失败: timeout）", encoding="utf-8")
    info_path.write_text("[]", encoding="utf-8")
    context = VideoProcessContext(
        video_path="lecture.mp4",
        output_dir=str(tmp_path),
        frames_dir=str(tmp_path / "frames"),
        debug_dir=str(tmp_path),
        info_path=str(info_path),
        stem="lecture",
        selection=VideoPipelineSelection(frames=False, audio=True),
    )
    processor = VideoProcessor.__new__(VideoProcessor)

    processor._prune_completed_outputs(context)

    assert audio_path.exists()
    assert transcript_path.exists()
    assert not info_path.exists()


def test_video_repair_publishes_success_before_cancellation(tmp_path):
    originals = [tmp_path / f"frame_00{index}.jpg" for index in (1, 2)]
    processed = [tmp_path / f"processed_frame_00{index}.jpg" for index in (1, 2)]
    for path in [*originals, *processed]:
        path.write_bytes(b"image")
    frames = [
        {"path": str(path), "timestamp": float(index * 10), "frame_idx": index}
        for index, path in enumerate(originals, start=1)
    ]
    _write_frame_info(tmp_path, frames)
    processor, _ = _video_processor(tmp_path)
    processor.llm = _CancelAfterOneVisionLLM()
    processor._save_phase3_manifest(
        str(tmp_path),
        frames,
        [str(path) for path in processed],
    )
    board_path = tmp_path / "lecture_板书识别.md"
    board_path.write_text(
        "<!-- meta:frame id=frame_001 time=00:10 -->\n\n"
        "<!-- 帧 frame_001 识别失败: timeout -->\n\n"
        "<!-- meta:frame id=frame_002 time=00:20 -->\n\n"
        "<!-- 帧 frame_002 识别失败: timeout -->",
        encoding="utf-8",
    )

    with pytest.raises(CancelledError):
        processor.repair_board("lecture.mp4", str(tmp_path))

    content = board_path.read_text(encoding="utf-8")
    assert "第一帧已修复" in content
    assert "帧 frame_001 识别失败" not in content
    assert "帧 frame_002 识别失败" in content
