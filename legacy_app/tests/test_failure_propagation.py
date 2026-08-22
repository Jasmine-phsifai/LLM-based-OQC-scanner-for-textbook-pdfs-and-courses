import os
import subprocess
import tempfile
import unittest

from PIL import Image

from OCRLLM.config import AppConfig, APIConfig
from OCRLLM.core.progress_tracker import ProgressTracker
from OCRLLM.core.task_runner import ProgressReporter
from OCRLLM.processors.board import BoardProcessor
from OCRLLM.processors.pdf import PDFProcessor
from OCRLLM.processors.video import VideoProcessor


class _FailingLLM:
    def set_cancel_event(self, *_args):
        pass

    def chat_with_images(self, *_args, **_kwargs):
        raise RuntimeError("provider rejected model")

    def chat_with_images_contextual(self, *_args, **_kwargs):
        raise RuntimeError("provider rejected model")

    def chat_text(self, *_args, **_kwargs):
        raise RuntimeError("provider rejected model")


class _SingleClientPool:
    pool_size = 1

    def set_cancel_event(self, *_args):
        pass

    def get_single_client(self):
        return _FailingLLM()


class _HotwordOnlyWhenAskedLLM:
    def set_cancel_event(self, *_args):
        pass

    def chat_with_images(self, prompt, *_args, **_kwargs):
        if "热词表" in prompt or "热词1" in prompt:
            return "Linux\nUbuntu\nShell\n命令行\n终端"
        return "## Linux shell demo\n\nScreen shows terminal commands."

    def chat_text(self, *_args, **_kwargs):
        return "Linux\nShell"


class _CodexModeNoTextLLM:
    def set_cancel_event(self, *_args):
        pass

    def chat_with_images(self, *_args, **_kwargs):
        return "## Board\n\nScreen shows terminal commands and a shell prompt."

    def chat_text(self, *_args, **_kwargs):
        raise AssertionError("Codex mode must not call Qwen text hotword extraction")


class _SparseThenClosedPDFLLM:
    def __init__(self):
        self.calls = 0

    def set_cancel_event(self, *_args):
        pass

    def chat_with_images(self, *_args, **_kwargs):
        self.calls += 1
        if self.calls == 1:
            return "<!-- meta:page number=1 -->\n\n短"
        raise RuntimeError("Cannot send a request, as the client has been closed.")


class _OneTimedOutPDFBatchLLM:
    def set_cancel_event(self, *_args):
        pass

    def chat_with_images(self, *_args, image_paths, **_kwargs):
        page_number = int(os.path.basename(image_paths[0]).removeprefix("page").removesuffix(".png"))
        if page_number == 2:
            raise subprocess.TimeoutExpired("codex", 1800)
        return (
            f"<!-- meta:page number={page_number} -->\n\n"
            f"第 {page_number} 页成功正文。" + "有效识别内容" * 80
        )


class _SecondBoardBatchTimesOutLLM:
    def __init__(self):
        self.calls = 0

    def set_cancel_event(self, *_args):
        pass

    def chat_with_images_contextual(self, *_args, **_kwargs):
        self.calls += 1
        if self.calls == 2:
            raise subprocess.TimeoutExpired("codex", 1800)
        return "第一批成功正文。" + "有效识别内容" * 80


class _SecondVideoBatchTimesOutLLM:
    def __init__(self):
        self.calls = 0

    def set_cancel_event(self, *_args):
        pass

    def chat_with_images(self, *_args, image_paths, **_kwargs):
        self.calls += 1
        if self.calls == 2:
            raise subprocess.TimeoutExpired("codex", 1800)
        stem = os.path.splitext(os.path.basename(image_paths[0]))[0]
        return f"<!-- meta:frame id={stem} time=00:10 -->\n\n第一批成功正文。" + "有效识别内容" * 80


def _cfg(tmp: str) -> AppConfig:
    return AppConfig(
        api=APIConfig(api_key="dummy-key"),
    ).with_updates(
        paths={"output_dir": tmp, "temp_dir": tmp},
        concurrency={"llm_parallel_requests": 1, "llm_request_stagger_seconds": 0},
        processing={"batch_size": 1},
        video={"batch_size": 1},
    )


class VisionFailurePropagationTests(unittest.TestCase):
    def test_board_raises_when_every_batch_only_writes_error_placeholders(self):
        with tempfile.TemporaryDirectory() as tmp:
            image_path = os.path.join(tmp, "board.png")
            output_path = os.path.join(tmp, "board.md")
            Image.new("RGB", (8, 8), "white").save(image_path)
            proc = BoardProcessor(cfg=_cfg(tmp), llm=_FailingLLM(), api_pool=_SingleClientPool())

            with self.assertRaisesRegex(RuntimeError, "全部.*失败"):
                proc.process([image_path], output_path=output_path, skip_preprocess=True)

            with open(output_path, encoding="utf-8") as f:
                self.assertIn("识别失败", f.read())

    def test_board_partial_timeout_raises_after_writing_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            image_paths = [os.path.join(tmp, f"board{index}.png") for index in range(1, 3)]
            output_path = os.path.join(tmp, "board.md")
            for path in image_paths:
                Image.new("RGB", (8, 8), "white").save(path)
            proc = BoardProcessor(
                cfg=_cfg(tmp), llm=_SecondBoardBatchTimesOutLLM(), api_pool=_SingleClientPool()
            )

            with self.assertRaisesRegex(RuntimeError, r"输出包含识别失败.*2.*board\.md"):
                proc.process(image_paths, output_path=output_path, skip_preprocess=True)

            with open(output_path, encoding="utf-8") as f:
                content = f.read()
            self.assertIn("第一批成功正文", content)
            self.assertIn("批次 2", content)
            self.assertIn("timed out", content)

    def test_pdf_raises_when_every_llm_batch_only_writes_error_placeholders(self):
        with tempfile.TemporaryDirectory() as tmp:
            pdf_path = os.path.join(tmp, "book.pdf")
            output_path = os.path.join(tmp, "book.md")
            import fitz

            doc = fitz.open()
            doc.new_page(width=64, height=64)
            doc.save(pdf_path)
            doc.close()

            proc = PDFProcessor(cfg=_cfg(tmp), llm=_FailingLLM(), api_pool=_SingleClientPool())

            with self.assertRaisesRegex(RuntimeError, "全部.*失败"):
                proc.process(pdf_path, need_formula=True, output_path=output_path)

            with open(output_path, encoding="utf-8") as f:
                self.assertIn("识别失败", f.read())

    def test_pdf_raises_when_failure_placeholders_leave_too_little_real_text(self):
        with tempfile.TemporaryDirectory() as tmp:
            pdf_path = os.path.join(tmp, "book.pdf")
            output_path = os.path.join(tmp, "book.md")
            image_paths = [os.path.join(tmp, "page1.png"), os.path.join(tmp, "page2.png")]
            for path in image_paths:
                Image.new("RGB", (8, 8), "white").save(path)

            import fitz

            doc = fitz.open()
            doc.new_page(width=64, height=64)
            doc.new_page(width=64, height=64)
            doc.save(pdf_path)
            doc.close()

            proc = PDFProcessor(cfg=_cfg(tmp), llm=_SparseThenClosedPDFLLM(), api_pool=_SingleClientPool())

            from unittest.mock import patch
            with patch("OCRLLM.processors.pdf.pdf_to_images", return_value=image_paths):
                with self.assertRaisesRegex(RuntimeError, "识别失败.*有效正文过少"):
                    proc.process(pdf_path, need_formula=True, output_path=output_path)

            with open(output_path, encoding="utf-8") as f:
                content = f.read()
            self.assertIn("client has been closed", content)

    def test_pdf_partial_timeout_raises_after_preserving_all_batch_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            pdf_path = os.path.join(tmp, "book.pdf")
            output_path = os.path.join(tmp, "book.md")
            image_paths = [os.path.join(tmp, f"page{page}.png") for page in range(1, 4)]
            for path in image_paths:
                Image.new("RGB", (8, 8), "white").save(path)

            import fitz

            doc = fitz.open()
            for _ in image_paths:
                doc.new_page(width=64, height=64)
            doc.save(pdf_path)
            doc.close()

            proc = PDFProcessor(cfg=_cfg(tmp), llm=_OneTimedOutPDFBatchLLM(), api_pool=_SingleClientPool())

            from unittest.mock import patch
            with patch("OCRLLM.processors.pdf.pdf_to_images", return_value=image_paths):
                with self.assertRaisesRegex(RuntimeError, r"PDF 输出包含识别失败.*2.*book\.md"):
                    proc.process(pdf_path, need_formula=True, output_path=output_path)

            with open(output_path, encoding="utf-8") as f:
                content = f.read()
            self.assertIn("第 1 页成功正文", content)
            self.assertIn("第 3 页成功正文", content)
            self.assertIn("第 2-2 页识别失败", content)
            self.assertIn("timed out", content)

    def test_video_phase4_raises_when_every_frame_only_writes_error_placeholders(self):
        with tempfile.TemporaryDirectory() as tmp:
            frame_path = os.path.join(tmp, "board_001_010s.jpg")
            Image.new("RGB", (8, 8), "white").save(frame_path)
            proc = VideoProcessor(
                cfg=_cfg(tmp),
                llm=_FailingLLM(),
                reporter=ProgressReporter(),
                tracker=ProgressTracker(),
                api_pool=_SingleClientPool(),
            )

            with self.assertRaisesRegex(RuntimeError, "全部.*失败"):
                proc._phase4_llm(
                    [{"path": frame_path, "timestamp": 10.0, "frame_idx": 1}],
                    [frame_path],
                    tmp,
                    "lecture",
                )

            board_md = os.path.join(tmp, "lecture_板书识别.md")
            with open(board_md, encoding="utf-8") as f:
                content = f.read()
            self.assertIn("meta:frame id=board_001_010s", content)
            self.assertIn("帧 board_001_010s 识别失败", content)

    def test_video_partial_timeout_raises_after_writing_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            frame_paths = [os.path.join(tmp, f"board_00{index}_010s.jpg") for index in range(1, 3)]
            for path in frame_paths:
                Image.new("RGB", (8, 8), "white").save(path)
            frames = [
                {"path": path, "timestamp": 10.0, "frame_idx": index}
                for index, path in enumerate(frame_paths, start=1)
            ]
            proc = VideoProcessor(
                cfg=_cfg(tmp),
                llm=_SecondVideoBatchTimesOutLLM(),
                reporter=ProgressReporter(),
                tracker=ProgressTracker(),
                api_pool=_SingleClientPool(),
            )

            with self.assertRaisesRegex(RuntimeError, r"输出包含识别失败.*2"):
                proc._phase4_llm(frames, frame_paths, tmp, "lecture")

            board_md = os.path.join(tmp, "lecture_板书识别.md")
            with open(board_md, encoding="utf-8") as f:
                content = f.read()
            self.assertIn("第一批成功正文", content)
            self.assertIn("meta:frame id=board_002_010s", content)
            self.assertIn("帧 board_002_010s 识别失败", content)
            self.assertIn("timed out", content)

    def test_video_phase4_propagates_provider_setup_errors_without_placeholders(self):
        from OCRLLM.core.provider_errors import ProviderSetupError

        class SetupFailingLLM:
            def set_cancel_event(self, *_args):
                pass

            def chat_with_images(self, *_args, **_kwargs):
                raise ProviderSetupError(
                    "当前 Python 环境缺少可用 google-genai SDK；请运行 python -m pip install -r requirements.txt"
                )

        with tempfile.TemporaryDirectory() as tmp:
            frame_path = os.path.join(tmp, "board_001_010s.jpg")
            Image.new("RGB", (8, 8), "white").save(frame_path)
            proc = VideoProcessor(
                cfg=_cfg(tmp),
                llm=SetupFailingLLM(),
                reporter=ProgressReporter(),
                tracker=ProgressTracker(),
                api_pool=_SingleClientPool(),
            )

            with self.assertRaisesRegex(ProviderSetupError, "google-genai SDK"):
                proc._phase4_llm(
                    [{"path": frame_path, "timestamp": 10.0, "frame_idx": 1}],
                    [frame_path],
                    tmp,
                    "lecture",
                )

            board_md = os.path.join(tmp, "lecture_板书识别.md")
            if os.path.exists(board_md):
                with open(board_md, encoding="utf-8") as f:
                    self.assertNotIn("批次 1 失败", f.read())

    def test_pdf_llm_propagates_provider_setup_errors_without_placeholders(self):
        from OCRLLM.core.provider_errors import ProviderSetupError

        class SetupFailingLLM:
            def set_cancel_event(self, *_args):
                pass

            def chat_with_images(self, *_args, **_kwargs):
                raise ProviderSetupError(
                    "当前 Python 环境缺少可用 google-genai SDK；请运行 python -m pip install -r requirements.txt"
                )

        with tempfile.TemporaryDirectory() as tmp:
            image_path = os.path.join(tmp, "page1.jpg")
            Image.new("RGB", (8, 8), "white").save(image_path)
            proc = PDFProcessor(
                cfg=_cfg(tmp),
                llm=SetupFailingLLM(),
                reporter=ProgressReporter(),
                tracker=ProgressTracker(),
                api_pool=_SingleClientPool(),
            )

            with self.assertRaisesRegex(ProviderSetupError, "google-genai SDK"):
                proc._do_batch_llm(
                    SetupFailingLLM(),
                    "read page",
                    [image_path],
                    "1-1",
                    1,
                    "read page {page_range}",
                )

    def test_video_phase4_does_not_accept_hotword_only_response_as_board_content(self):
        with tempfile.TemporaryDirectory() as tmp:
            frame_path = os.path.join(tmp, "board_001_010s.jpg")
            Image.new("RGB", (8, 8), "white").save(frame_path)
            proc = VideoProcessor(
                cfg=_cfg(tmp),
                llm=_HotwordOnlyWhenAskedLLM(),
                reporter=ProgressReporter(),
                tracker=ProgressTracker(),
                api_pool=_SingleClientPool(),
            )

            md_path, hotwords, _ = proc._phase4_llm(
                [{"path": frame_path, "timestamp": 10.0, "frame_idx": 1}],
                [frame_path],
                tmp,
                "lecture",
            )

            with open(md_path, encoding="utf-8") as f:
                content = f.read()
            self.assertIn("Screen shows terminal commands", content)
            self.assertEqual(hotwords, ["Linux", "Shell"])

    def test_video_phase4_codex_mode_skips_qwen_text_hotword_extraction(self):
        with tempfile.TemporaryDirectory() as tmp:
            frame_path = os.path.join(tmp, "board_001_010s.jpg")
            Image.new("RGB", (8, 8), "white").save(frame_path)
            cfg = _cfg(tmp).with_updates(codex_vision={"enabled": True})
            proc = VideoProcessor(
                cfg=cfg,
                llm=_CodexModeNoTextLLM(),
                reporter=ProgressReporter(),
                tracker=ProgressTracker(),
                api_pool=_SingleClientPool(),
            )

            md_path, hotwords, _ = proc._phase4_llm(
                [{"path": frame_path, "timestamp": 10.0, "frame_idx": 1}],
                [frame_path],
                tmp,
                "lecture",
            )

            with open(md_path, encoding="utf-8") as f:
                self.assertIn("Screen shows terminal commands", f.read())
            self.assertEqual(hotwords, [])

    def test_video_phase4_codex_mode_raises_instead_of_writing_placeholder(self):
        with tempfile.TemporaryDirectory() as tmp:
            frame_path = os.path.join(tmp, "board_001_010s.jpg")
            Image.new("RGB", (8, 8), "white").save(frame_path)
            cfg = _cfg(tmp).with_updates(codex_vision={"enabled": True})
            proc = VideoProcessor(
                cfg=cfg,
                llm=_FailingLLM(),
                reporter=ProgressReporter(),
                tracker=ProgressTracker(),
                api_pool=_SingleClientPool(),
            )

            with self.assertRaises(RuntimeError):
                proc._phase4_llm(
                    [{"path": frame_path, "timestamp": 10.0, "frame_idx": 1}],
                    [frame_path],
                    tmp,
                    "lecture",
                )

            md_path = os.path.join(tmp, "lecture_板书识别.md")
            if os.path.exists(md_path):
                with open(md_path, encoding="utf-8") as f:
                    self.assertNotIn("批次 1 失败", f.read())


if __name__ == "__main__":
    unittest.main()
