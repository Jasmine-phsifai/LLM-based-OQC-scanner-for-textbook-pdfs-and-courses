import os
import tempfile
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtGui import QCloseEvent
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QApplication, QDialog, QMessageBox, QScrollArea

from OCRLLM.config import AppConfig
from OCRLLM.core.checkpoint import Checkpoint
from OCRLLM.core.task_runner import ProgressReporter
from OCRLLM.gui.app import QCRMainWindow
from OCRLLM.gui.widgets import IncompleteTasksDialog
from OCRLLM.gui.tabs.video_tab import VideoTab


class _DummyWorker:
    def __init__(self, running=True):
        self.is_running = running
        self.cancel_requested = False

    def request_cancel(self):
        self.cancel_requested = True


class GuiAppCloseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._app = QApplication.instance() or QApplication([])

    def test_close_event_requests_async_cancel_instead_of_blocking(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = AppConfig().with_updates(paths={"output_dir": tmp, "temp_dir": tmp})
            window = QCRMainWindow(cfg=cfg)
            window._worker = _DummyWorker(running=True)
            event = QCloseEvent()

            with patch.object(QMessageBox, "question", return_value=QMessageBox.Yes):
                window.closeEvent(event)

            self.assertFalse(event.isAccepted())
            self.assertTrue(window._worker.cancel_requested)
            self.assertTrue(window._close_after_worker)
            self.assertTrue(window._suppress_worker_dialogs)
            window.deleteLater()
            self._app.processEvents()

    def test_incomplete_tasks_dialog_select_all_resumes_multiple_tasks(self):
        checkpoints = [
            Checkpoint("pdf", "/tmp/a.pdf", "/tmp/a.md", 3),
            Checkpoint("video", "/tmp/b.mp4", "/tmp/b", 5),
        ]

        class _FakeManager:
            def list_incomplete(self):
                return checkpoints

        dlg = IncompleteTasksDialog(_FakeManager())
        dlg._select_all()
        dlg._on_resume()

        self.assertEqual(dlg.action, "resume")
        self.assertEqual(dlg.selected_checkpoints, checkpoints)
        self.assertEqual(dlg.selected_checkpoint, checkpoints[0])
        dlg.deleteLater()
        self._app.processEvents()

    def test_manage_tasks_resumes_multiple_selected_tasks_in_one_batch(self):
        checkpoints = [
            Checkpoint("pdf", "/tmp/a.pdf", "/tmp/a.md", 3),
            Checkpoint("video", "/tmp/b.mp4", "/tmp/b", 5),
        ]

        class _FakeDialog:
            Accepted = QDialog.Accepted

            def __init__(self, *_args, **_kwargs):
                self.action = "resume"
                self.selected_checkpoint = checkpoints[0]
                self.selected_checkpoints = checkpoints

            def exec_(self):
                return QDialog.Accepted

        with tempfile.TemporaryDirectory() as tmp:
            cfg = AppConfig().with_updates(paths={"output_dir": tmp, "temp_dir": tmp})
            window = QCRMainWindow(cfg=cfg)

            with patch("OCRLLM.gui.app.CheckpointManager"), \
                    patch("OCRLLM.gui.app.IncompleteTasksDialog", _FakeDialog), \
                    patch.object(window, "_resume_many", create=True) as resume_many, \
                    patch.object(window, "_on_resume_clicked"):
                window._on_manage_tasks()

            resume_many.assert_called_once_with(checkpoints)
            window.deleteLater()
            self._app.processEvents()

    def test_video_tab_passes_separate_audio_prompt_to_phase5(self):
        with tempfile.TemporaryDirectory() as tmp:
            video_path = os.path.join(tmp, "lecture.mp4")
            with open(video_path, "wb") as f:
                f.write(b"fake video")

            captured = {}

            def start_worker(task):
                task(ProgressReporter())
                return True

            tab = VideoTab(lambda: AppConfig().with_updates(paths={"output_dir": tmp, "temp_dir": tmp}), start_worker)
            tab._video_path.setText(video_path)
            tab._board_prompt._current_text = "board prompt {image_names} {extra_instruction}"
            tab._audio_prompt._current_text = "audio prompt {hotwords_instruction}"
            tab._frames_pipeline.setChecked(False)
            tab._audio_pipeline.setChecked(True)

            def fake_process(self, **kwargs):
                captured.update(kwargs)
                return {"board_md": "", "frames_dir": "", "output_dir": tmp}

            with patch("OCRLLM.processors.video.VideoProcessor.process", fake_process):
                tab._run()

            self.assertEqual(captured["prompt_template"], "board prompt {image_names} {extra_instruction}")
            self.assertEqual(captured["audio_prompt_template"], "audio prompt {hotwords_instruction}")
            self.assertTrue(captured["selection"].audio)
            self.assertFalse(captured["selection"].frames)
            tab.deleteLater()
            self._app.processEvents()

    def test_run_resume_checkpoint_supports_audio_tasks(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = os.path.join(tmp, "lecture.mp3")
            with open(source, "wb") as f:
                f.write(b"fake audio")
            output_path = os.path.join(tmp, "lecture_录音识别.md")
            cp = Checkpoint(
                "audio",
                source,
                output_path,
                2,
                completed_indices={0},
                extra={
                    "hotwords": ["simplex"],
                    "prompt_template": "audio prompt {hotwords_instruction}",
                },
            )
            cfg = AppConfig().with_updates(paths={"output_dir": tmp, "temp_dir": tmp})
            window = QCRMainWindow(cfg=cfg)

            with patch("OCRLLM.processors.audio.AudioProcessor.process", return_value=output_path) as process:
                result = window._run_resume_checkpoint(cp, ProgressReporter())

            self.assertIn("音频续传完成", result)
            process.assert_called_once_with(
                audio_path=source,
                output_path=output_path,
                hotwords=["simplex"],
                prompt_template="audio prompt {hotwords_instruction}",
                resume=True,
            )
            window.deleteLater()
            self._app.processEvents()

    def test_external_vision_provider_model_input_is_separate_from_provider(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = AppConfig().with_updates(paths={"output_dir": tmp, "temp_dir": tmp})
            window = QCRMainWindow(cfg=cfg)
            window._api_key_input.setText("dash-key")
            window._vision_api_enabled_cb.setChecked(True)
            window._vision_provider_input.setText("ioasis")
            window._vision_model_input.setText("gpt-5.5")
            window._vision_api_key_input.setText("oasis-key")
            window._vision_base_url_input.setText("https://oasis.example/v1")

            window._sync_api_from_ui()

            self.assertEqual(window._cfg.vision_api.provider, "ioasis")
            self.assertEqual(window._cfg.models.vision_model, "gpt-5.5")
            window.deleteLater()
            self._app.processEvents()

    def test_external_vision_provider_changes_do_not_overwrite_model_input(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = AppConfig().with_updates(paths={"output_dir": tmp, "temp_dir": tmp})
            window = QCRMainWindow(cfg=cfg)
            window._api_key_input.setText("dash-key")
            window._vision_api_enabled_cb.setChecked(True)
            window._vision_api_key_input.setText("provider-key")
            window._vision_base_url_input.setText("https://vision.example/v1")
            window._vision_provider_input.setText("ioasis")
            window._vision_model_input.setText("gpt-5.5")
            window._pending_audio_model = "qwen3-asr-flash-filetrans"

            window._vision_provider_input.setText("fuckme")
            self.assertEqual(window._vision_model_input.text(), "gpt-5.5")
            self.assertIn("视觉: gpt-5.5", window._api_summary.text())
            self.assertIn("视觉Provider: fuckme", window._api_summary.text())
            self.assertIn("音频: qwen3-asr-flash-filetrans", window._api_summary.text())

            window._sync_api_from_ui()

            self.assertEqual(window._cfg.models.vision_model, "gpt-5.5")
            self.assertEqual(window._cfg.vision_api.provider, "fuckme")
            self.assertEqual(window._cfg.models.asr_model, "qwen3-asr-flash-filetrans")
            window.deleteLater()
            self._app.processEvents()

    def test_external_vision_provider_keeps_explicit_model_when_provider_alias_changes(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = AppConfig().with_updates(paths={"output_dir": tmp, "temp_dir": tmp})
            window = QCRMainWindow(cfg=cfg)
            window._api_key_input.setText("dash-key")
            window._vision_api_enabled_cb.setChecked(True)
            window._vision_provider_input.setText("ioasis")
            window._vision_api_key_input.setText("provider-key")
            window._vision_base_url_input.setText("https://vision.example")
            window._vision_model_input.setText("gpt-5.5")
            window._pending_audio_model = "qwen3-asr-flash-filetrans"
            window._refresh_model_labels()

            window._vision_provider_input.setText("fuckme")
            window._sync_api_from_ui()

            self.assertEqual(window._cfg.models.vision_model, "gpt-5.5")
            self.assertEqual(window._cfg.vision_api.provider, "fuckme")
            self.assertEqual(window._cfg.models.asr_model, "qwen3-asr-flash-filetrans")
            self.assertEqual(window._vision_model_input.text(), "gpt-5.5")
            self.assertIn("视觉: gpt-5.5", window._api_summary.text())
            self.assertIn("视觉Provider: fuckme", window._api_summary.text())
            window.deleteLater()
            self._app.processEvents()

    def test_api_settings_body_is_scrollable(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = AppConfig().with_updates(paths={"output_dir": tmp, "temp_dir": tmp})
            window = QCRMainWindow(cfg=cfg)

            self.assertIsInstance(window._api_scroll, QScrollArea)
            self.assertIs(window._api_scroll.widget(), window._api_body)
            self.assertTrue(window._api_scroll.widgetResizable())
            self.assertEqual(window._api_scroll.verticalScrollBarPolicy(), Qt.ScrollBarAsNeeded)
            window.deleteLater()
            self._app.processEvents()


if __name__ == "__main__":
    unittest.main()
