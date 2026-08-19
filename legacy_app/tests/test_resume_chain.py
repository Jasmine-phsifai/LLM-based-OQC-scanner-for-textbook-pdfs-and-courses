import os
import tempfile
import time
import unittest

from OCRLLM.core.checkpoint import Checkpoint, CheckpointManager
from OCRLLM.processors.pdf import PDFProcessor
from OCRLLM.processors.video import VideoProcessor
from OCRLLM.processors.video_pipeline import (
    AudioRecognizePhase,
    BoardRecognizePhase,
    FrameExtractPhase,
    VideoPhase,
    VideoProcessContext,
)
from OCRLLM.processors.video_pipeline_selection import VideoPipelineSelection


class ResumeContractTests(unittest.TestCase):
    def test_pdf_resume_options_restore_original_contract(self):
        checkpoint = Checkpoint(
            task_type="pdf",
            source_path="book.pdf",
            output_path="book_识别.md",
            total_items=3,
            extra={
                "page_range": [11, 20],
                "page_offset": 10,
                "batch_size": 10,
                "prompt_template": "custom-prompt",
            },
        )

        self.assertEqual(
            PDFProcessor.resume_options_from_checkpoint(checkpoint),
            {
                "pdf_path": "book.pdf",
                "need_formula": True,
                "output_path": "book_识别.md",
                "page_range": (11, 20),
                "prompt_template": "custom-prompt",
                "resume": True,
            },
        )

    def test_video_resume_options_restore_original_contract(self):
        checkpoint = Checkpoint(
            task_type="video",
            source_path="lecture.mp4",
            output_path="out/lecture",
            total_items=5,
            extra={
                "stem": "lecture",
                "phases": [1, 2, 3, 4],
                "skip_audio": True,
                "prompt_template": "board-prompt",
            },
        )

        self.assertEqual(
            VideoProcessor.resume_options_from_checkpoint(checkpoint),
            {
                "video_path": "lecture.mp4",
                "output_dir": "out/lecture",
                "phases": [1, 2, 3, 4],
                "skip_audio": True,
                "prompt_template": "board-prompt",
                "audio_prompt_template": None,
                "resume": True,
            },
        )

    def test_video_resume_options_restore_output_stem_when_present(self):
        checkpoint = Checkpoint(
            task_type="video",
            source_path="long-lecture.mp4",
            output_path="out/long-lecture",
            total_items=5,
            extra={
                "stem": "001_short_a1b2c3d4e5",
                "output_stem": "001_short_a1b2c3d4e5",
                "source_stem": "long-lecture",
                "phases": [1, 2, 3, 4, 5],
                "skip_audio": False,
            },
        )

        options = VideoProcessor.resume_options_from_checkpoint(checkpoint)

        self.assertEqual(options["output_stem"], "001_short_a1b2c3d4e5")
        self.assertEqual(options["video_path"], "long-lecture.mp4")

    def test_video_debug_dir_name_is_windows_safe_for_youtube_titles(self):
        name = VideoProcessor._debug_dir_name("003_Modern Robotics, Chapters 2 and 3 ")

        self.assertTrue(name.startswith("video_debug_"))
        self.assertFalse(name.endswith((" ", ".")))
        self.assertRegex(name, r"_[0-9a-f]{10}$")
        for char in '<>:"/\\|?*':
            self.assertNotIn(char, name)

    def test_list_incomplete_returns_latest_first(self):
        with tempfile.TemporaryDirectory() as tmp:
            src1 = os.path.join(tmp, "a.pdf")
            src2 = os.path.join(tmp, "b.mp4")
            open(src1, "w", encoding="utf-8").close()
            open(src2, "w", encoding="utf-8").close()

            mgr = CheckpointManager(tmp)
            cp1 = Checkpoint("pdf", src1, os.path.join(tmp, "a.md"), 3)
            cp2 = Checkpoint("video", src2, os.path.join(tmp, "b"), 5)
            cp1.updated_at = time.time() - 10
            cp2.updated_at = time.time()
            mgr.save(cp1)
            mgr.save(cp2)

            listed = mgr.list_incomplete()
            self.assertEqual([cp.task_type for cp in listed], ["video", "pdf"])

    def test_select_incomplete_preserves_preferred_checkpoint(self):
        with tempfile.TemporaryDirectory() as tmp:
            src1 = os.path.join(tmp, "a.pdf")
            src2 = os.path.join(tmp, "b.mp4")
            open(src1, "w", encoding="utf-8").close()
            open(src2, "w", encoding="utf-8").close()

            mgr = CheckpointManager(tmp)
            pdf_cp = Checkpoint("pdf", src1, os.path.join(tmp, "a.md"), 3)
            video_cp = Checkpoint("video", src2, os.path.join(tmp, "b"), 5)
            pdf_cp.updated_at = time.time()
            video_cp.updated_at = time.time() - 10
            mgr.save(pdf_cp)
            mgr.save(video_cp)

            selected = mgr.select_incomplete(preferred_key=video_cp.resume_key)

            self.assertIsNotNone(selected)
            self.assertEqual(selected.resume_key, video_cp.resume_key)


class CheckpointCleanupTests(unittest.TestCase):
    def test_cancelling_incomplete_tasks_preserves_generated_outputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            pdf_source = os.path.join(tmp, "book.pdf")
            pdf_output = os.path.join(tmp, "book_识别.md")
            audio_source = os.path.join(tmp, "lecture.mp3")
            audio_output = os.path.join(tmp, "lecture_录音识别.md")
            video_source = os.path.join(tmp, "lecture.mp4")
            video_output = os.path.join(tmp, "lecture")
            for source_path in (pdf_source, audio_source, video_source):
                with open(source_path, "wb") as source_file:
                    source_file.write(b"source")
            with open(pdf_output, "w", encoding="utf-8") as output_file:
                output_file.write("recognized PDF")
            with open(audio_output, "w", encoding="utf-8") as output_file:
                output_file.write("recognized transcript")
            os.makedirs(video_output)
            video_board = os.path.join(video_output, "lecture_板书识别.md")
            video_transcript = os.path.join(video_output, "lecture_录音识别.md")
            for output_path in (video_board, video_transcript):
                with open(output_path, "w", encoding="utf-8") as output_file:
                    output_file.write("recognized video result")

            manager = CheckpointManager(tmp)
            cases = [
                ("pdf", pdf_source, pdf_output, [pdf_output]),
                ("audio", audio_source, audio_output, [audio_output]),
                ("video", video_source, video_output, [video_board, video_transcript]),
            ]

            for task_type, source_path, output_path, preserved_paths in cases:
                checkpoint = Checkpoint(task_type, source_path, output_path, 3)
                manager.save(checkpoint)
                manager.remove_with_artifacts(checkpoint)

                self.assertIsNone(manager.load(task_type, source_path))
                for preserved_path in preserved_paths:
                    self.assertTrue(os.path.exists(preserved_path), preserved_path)

    def test_output_deletion_requires_explicit_opt_in(self):
        with tempfile.TemporaryDirectory() as tmp:
            source_path = os.path.join(tmp, "book.pdf")
            output_path = os.path.join(tmp, "book_识别.md")
            with open(source_path, "wb") as source_file:
                source_file.write(b"source")
            with open(output_path, "w", encoding="utf-8") as output_file:
                output_file.write("recognized PDF")

            manager = CheckpointManager(tmp)
            checkpoint = Checkpoint("pdf", source_path, output_path, 3)
            manager.save(checkpoint)
            manager.remove_with_artifacts(checkpoint, delete_outputs=True)

            self.assertFalse(os.path.exists(output_path))


class VideoPhase4ResumeTests(unittest.TestCase):
    def _make_context(self, tmp: str) -> VideoProcessContext:
        return VideoProcessContext(
            video_path="lecture.mp4",
            output_dir=tmp,
            frames_dir=os.path.join(tmp, "提取帧"),
            debug_dir=tmp,
            info_path=os.path.join(tmp, "frame_info.json"),
            stem="lecture",
            selection=VideoPipelineSelection(frames=True, audio=True),
        )

    def _write_frame_info(self, tmp: str, frame_ids: list[str]) -> list[dict]:
        frame_dir = os.path.join(tmp, "提取帧")
        os.makedirs(frame_dir, exist_ok=True)
        frame_results = []
        for index, frame_id in enumerate(frame_ids):
            path = os.path.join(frame_dir, f"{frame_id}.jpg")
            with open(path, "w", encoding="utf-8") as f:
                f.write("frame")
            frame_results.append({"path": path, "timestamp": index * 10.0, "frame_idx": index})
        with open(os.path.join(tmp, "frame_info.json"), "w", encoding="utf-8") as f:
            import json
            json.dump(frame_results, f, ensure_ascii=False)
        return frame_results

    def _write_board_md(self, tmp: str, sections: list[tuple[str, str]]):
        board_path = os.path.join(tmp, "lecture_板书识别.md")
        content = []
        for frame_id, time_str in sections:
            content.extend([
                f"<!-- meta:frame id={frame_id} time={time_str} -->",
                f"内容 {frame_id}",
                "",
            ])
        with open(board_path, "w", encoding="utf-8") as f:
            f.write("\n".join(content))
        return board_path

    def test_phase4_can_resume_when_board_matches_frame_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            frame_ids = ["board_001_010s", "board_002_020s"]
            self._write_frame_info(tmp, frame_ids)
            self._write_board_md(tmp, [("board_001_010s", "0:10"), ("board_002_020s", "0:20")])
            with open(os.path.join(tmp, "lecture_热词表.txt"), "w", encoding="utf-8") as f:
                f.write("梯度\n步长\n")

            processor = VideoProcessor.__new__(VideoProcessor)
            context = self._make_context(tmp)
            phase = BoardRecognizePhase()

            self.assertTrue(phase.can_resume(processor, context))
            self.assertEqual(context.hotwords, ["梯度", "步长"])

    def test_phase4_rejects_board_when_frame_headers_do_not_match(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._write_frame_info(tmp, ["board_001_010s", "board_002_020s"])
            self._write_board_md(tmp, [("board_001_010s", "0:10")])

            processor = VideoProcessor.__new__(VideoProcessor)
            context = self._make_context(tmp)

            self.assertFalse(BoardRecognizePhase().can_resume(processor, context))


class VideoPhase5ResumeTests(unittest.TestCase):
    class _DummyProcessor:
        def __init__(self):
            self.calls = []

        def _phase1_audio_path(self, output_dir, stem):
            return os.path.join(output_dir, f"{stem}.mp3")

        def _phase5_asr(self, *args, **kwargs):
            self.calls.append((args, kwargs))

    def test_audio_phase_forwards_resume_flag_to_audio_processor(self):
        with tempfile.TemporaryDirectory() as tmp:
            audio_path = os.path.join(tmp, "lecture.mp3")
            with open(audio_path, "wb") as f:
                f.write(b"audio")

            context = VideoProcessContext(
                video_path="lecture.mp4",
                output_dir=tmp,
                frames_dir=os.path.join(tmp, "提取帧"),
                debug_dir=tmp,
                info_path=os.path.join(tmp, "frame_info.json"),
                stem="lecture",
                selection=VideoPipelineSelection(frames=False, audio=True),
                audio_prompt_template="audio prompt",
                resume=True,
                audio_path=audio_path,
            )
            processor = self._DummyProcessor()

            self.assertTrue(AudioRecognizePhase().execute(processor, context))

            self.assertEqual(len(processor.calls), 1)
            _args, kwargs = processor.calls[0]
            self.assertEqual(kwargs["prompt_template"], "audio prompt")
            self.assertTrue(kwargs["resume"])


class VideoInvalidationTests(unittest.TestCase):
    class _DummyTracker:
        def start_phase(self, *args, **kwargs):
            pass

        def finish_phase(self, *args, **kwargs):
            pass

    class _DummyCheckpointManager:
        def __init__(self):
            self.saved = []

        def save(self, checkpoint):
            self.saved.append(sorted(checkpoint.completed_indices))

        def save_incremental(self, checkpoint, index):
            checkpoint.mark_completed(index)
            self.saved.append(sorted(checkpoint.completed_indices))

    class _DummyProcessor:
        def __init__(self):
            self.tracker = VideoInvalidationTests._DummyTracker()
            self.checkpoint_mgr = VideoInvalidationTests._DummyCheckpointManager()
            self.cleared = []

        def _clear_invalidated_phase_artifacts(self, output_dir, stem, invalidated):
            self.cleared.append((output_dir, stem, tuple(sorted(invalidated))))

    class _FrameExtractProcessor(_DummyProcessor):
        def _phase2_extract(self, video_path, frames_dir, debug_dir):
            os.makedirs(frames_dir, exist_ok=True)
            frame_path = os.path.join(frames_dir, "board_001_010s.jpg")
            with open(frame_path, "w", encoding="utf-8") as f:
                f.write("frame")
            return [{"path": frame_path, "timestamp": 10.0, "frame_idx": 1}]

    class _DummyPhase(VideoPhase):
        phase_id = 3
        phase_key = "phase3"
        phase_name = "phase3"

        def can_resume(self, processor, context):
            return False

        def execute(self, processor, context):
            return True

    class _ReusablePhase(VideoPhase):
        phase_id = 4
        phase_key = "phase4"
        phase_name = "phase4"

        def __init__(self):
            self.executed = False
            self.resumed = False

        def can_resume(self, processor, context):
            return True

        def on_resume(self, processor, context):
            self.resumed = True

        def execute(self, processor, context):
            self.executed = True
            return True

    def test_frame_phase_invalidation_is_persisted_and_never_touches_audio(self):
        processor = self._DummyProcessor()
        checkpoint = Checkpoint("video", "src.mp4", "out_dir", 5, completed_indices={1, 2, 3, 4, 5})
        context = VideoProcessContext(
            video_path="src.mp4",
            output_dir="out_dir",
            frames_dir="frames",
            debug_dir="debug",
            info_path="info.json",
            stem="demo",
            selection=VideoPipelineSelection(frames=True, audio=True),
        )
        completed = set(checkpoint.completed_indices)

        self._DummyPhase().run(processor, context, checkpoint, completed)

        self.assertEqual(completed, {1, 2, 5})
        self.assertEqual(checkpoint.completed_indices, {1, 2, 3, 5})
        self.assertEqual(processor.checkpoint_mgr.saved[0], [1, 2, 5])
        self.assertEqual(processor.checkpoint_mgr.saved[1], [1, 2, 3, 5])
        self.assertEqual(processor.cleared, [("out_dir", "demo", (3, 4))])

    def test_resume_reuses_valid_artifact_even_when_checkpoint_was_not_marked(self):
        processor = self._DummyProcessor()
        checkpoint = Checkpoint("video", "src.mp4", "out_dir", 5, completed_indices={1, 2, 3})
        context = VideoProcessContext(
            video_path="src.mp4",
            output_dir="out_dir",
            frames_dir="frames",
            debug_dir="debug",
            info_path="info.json",
            stem="demo",
            selection=VideoPipelineSelection(frames=True, audio=True),
            resume=True,
        )
        phase = self._ReusablePhase()
        completed = set(checkpoint.completed_indices)

        self.assertTrue(phase.run(processor, context, checkpoint, completed))

        self.assertTrue(phase.resumed)
        self.assertFalse(phase.executed)
        self.assertIn(4, completed)
        self.assertIn(4, checkpoint.completed_indices)
        self.assertEqual(processor.checkpoint_mgr.saved[-1], [1, 2, 3, 4])

    def test_board_only_frame_extract_preserves_phase5_transcript_artifact(self):
        with tempfile.TemporaryDirectory() as tmp:
            processor = self._FrameExtractProcessor()
            context = VideoProcessContext(
                video_path="src.mp4",
                output_dir=tmp,
                frames_dir=os.path.join(tmp, "frames"),
                debug_dir=os.path.join(tmp, "debug"),
                info_path=os.path.join(tmp, "frame_info.json"),
                stem="demo",
                selection=VideoPipelineSelection(frames=True, audio=False),
            )

            self.assertTrue(FrameExtractPhase().execute(processor, context))

            self.assertEqual(processor.cleared, [(tmp, "demo", (3, 4))])


class VideoPipelineSelectionTests(unittest.TestCase):
    def test_legacy_steps_map_to_pipelines(self):
        self.assertEqual(
            VideoPipelineSelection.from_legacy_steps([1, 2, 3, 4, 5]),
            VideoPipelineSelection(frames=True, audio=True),
        )
        self.assertEqual(
            VideoPipelineSelection.from_legacy_steps([1, 2, 3, 4]),
            VideoPipelineSelection(frames=True, audio=False, audio_extract_only=True),
        )
        self.assertEqual(
            VideoPipelineSelection.from_legacy_steps([1, 5]),
            VideoPipelineSelection(frames=False, audio=True),
        )
        self.assertEqual(
            VideoPipelineSelection.from_legacy_steps(None, skip_audio=True),
            VideoPipelineSelection(frames=True, audio=False, audio_extract_only=True),
        )

    def test_steps_round_trip_to_stable_ids(self):
        self.assertEqual(VideoPipelineSelection(frames=True, audio=True).steps(), [1, 2, 3, 4, 5])
        self.assertEqual(VideoPipelineSelection(frames=True, audio=False).steps(), [2, 3, 4])
        self.assertEqual(VideoPipelineSelection(frames=False, audio=True).steps(), [1, 5])


class VideoCleanupTests(unittest.TestCase):
    def _context(self, tmp: str, selection: VideoPipelineSelection) -> VideoProcessContext:
        return VideoProcessContext(
            video_path="lecture.mp4",
            output_dir=tmp,
            frames_dir=os.path.join(tmp, "提取帧"),
            debug_dir=tmp,
            info_path=os.path.join(tmp, "frame_info.json"),
            stem="lecture",
            selection=selection,
        )

    def _write_all_artifacts(self, tmp: str):
        os.makedirs(os.path.join(tmp, "提取帧"), exist_ok=True)
        paths = {
            "board": os.path.join(tmp, "lecture_板书识别.md"),
            "transcript": os.path.join(tmp, "lecture_录音识别.md"),
            "hotwords": os.path.join(tmp, "lecture_热词表.txt"),
            "audio": os.path.join(tmp, "lecture.mp3"),
            "info": os.path.join(tmp, "frame_info.json"),
            "frame": os.path.join(tmp, "提取帧", "board_001_010s.jpg"),
        }
        for path in paths.values():
            with open(path, "w", encoding="utf-8") as f:
                f.write("x")
        return paths

    def test_cleanup_keeps_paid_output_and_drops_rebuildable_intermediates(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = self._write_all_artifacts(tmp)
            processor = VideoProcessor.__new__(VideoProcessor)

            processor._prune_completed_outputs(
                self._context(tmp, VideoPipelineSelection(frames=True, audio=True))
            )

            self.assertTrue(os.path.exists(paths["board"]))
            self.assertTrue(os.path.exists(paths["transcript"]))
            self.assertTrue(os.path.exists(paths["hotwords"]))
            self.assertFalse(os.path.exists(paths["audio"]))
            self.assertFalse(os.path.exists(paths["info"]))
            self.assertFalse(os.path.isdir(os.path.join(tmp, "提取帧")))

    def test_frames_only_run_never_deletes_the_transcript(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = self._write_all_artifacts(tmp)
            processor = VideoProcessor.__new__(VideoProcessor)

            processor._prune_completed_outputs(
                self._context(tmp, VideoPipelineSelection(frames=True, audio=False))
            )

            self.assertTrue(os.path.exists(paths["transcript"]))

    def test_keep_intermediates_disables_cleanup(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = self._write_all_artifacts(tmp)
            processor = VideoProcessor.__new__(VideoProcessor)
            context = self._context(tmp, VideoPipelineSelection(frames=True, audio=True))
            context.cleanup_intermediates = False

            processor._prune_completed_outputs(context)

            self.assertTrue(os.path.exists(paths["audio"]))
            self.assertTrue(os.path.exists(paths["info"]))


if __name__ == "__main__":
    unittest.main()
