import os
import tempfile
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtCore import QSettings
from PyQt5.QtWidgets import QApplication, QMessageBox

from OCRLLM.config import AppConfig
from OCRLLM.gui.app import QCRMainWindow
from OCRLLM.gui.settings_dialog import SettingsDialog
from qsettings_test_isolation import isolated_settings, use_isolated_qsettings


class CodexSettingsDialogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self):
        use_isolated_qsettings(self)

    def test_codex_toggle_only_swaps_visual_model_and_can_restore(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = AppConfig().with_updates(paths={"output_dir": tmp, "temp_dir": tmp})
            dlg = SettingsDialog(None, cfg)
            dlg._vision_provider_input.setText("ioasis")
            dlg._vision_url_input.setText("https://vision.example/v1")
            dlg._vision_model_combo.setCurrentText("qwen-vl-max")
            dlg._pending_vision_model = "qwen-vl-max"

            dlg._codex_enabled_cb.setChecked(True)

            self.assertEqual(dlg._pending_vision_model, "gpt-5.5")
            self.assertEqual(dlg._vision_provider_input.text(), "ioasis")
            self.assertEqual(dlg._vision_url_input.text(), "https://vision.example/v1")

            dlg._codex_enabled_cb.setChecked(False)

            self.assertEqual(dlg._pending_vision_model, "qwen-vl-max")
            self.assertEqual(dlg._vision_provider_input.text(), "ioasis")
            dlg.deleteLater()
            self._app.processEvents()

    def test_codex_mode_apply_does_not_require_api_key_and_runs_first_check(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = AppConfig().with_updates(paths={"output_dir": tmp, "temp_dir": tmp})
            dlg = SettingsDialog(None, cfg)
            dlg._api_key_input.setText("")
            dlg._codex_enabled_cb.setChecked(True)
            dlg._codex_reasoning_combo.setCurrentText("medium")
            dlg._codex_fast_mode_cb.setChecked(True)
            dlg._codex_parallel_input.setValue(6)
            dlg._codex_stagger_input.setValue(2.5)
            dlg._codex_vision_batch_input.setValue(7)
            dlg._codex_video_batch_input.setValue(8)

            with patch("OCRLLM.gui.settings_dialog.inspect_codex_cli") as inspect, \
                    patch.object(SettingsDialog, "accept") as accept, \
                    patch.object(QMessageBox, "warning") as warning:
                inspect.return_value.ok = True
                inspect.return_value.message = "ok"
                dlg._on_apply()

            inspect.assert_called_once()
            self.assertEqual(inspect.call_args.args[0].model, "gpt-5.5")
            self.assertTrue(inspect.call_args.args[0].fast_mode)
            self.assertEqual(inspect.call_args.args[0].parallel_requests, 6)
            accept.assert_called_once()
            warning.assert_not_called()
            applied = dlg.apply_config()
            self.assertEqual(applied.codex_vision.parallel_requests, 6)
            self.assertEqual(applied.codex_vision.request_stagger_seconds, 2.5)
            self.assertEqual(applied.codex_vision.vision_batch_size, 7)
            self.assertEqual(applied.codex_vision.video_frame_batch_size, 8)
            self.assertTrue(applied.codex_vision.fast_mode)
            self.assertEqual(applied.concurrency.llm_parallel_requests, 6)
            self.assertEqual(applied.concurrency.llm_request_stagger_seconds, 2.5)
            self.assertEqual(applied.processing.batch_size, 7)
            self.assertEqual(applied.video.batch_size, 8)
            dlg.deleteLater()
            self._app.processEvents()

    def test_codex_runtime_controls_are_restored_from_qsettings(self):
        settings = isolated_settings()
        settings.setValue("ui/codex_parallel_requests", 11)
        settings.setValue("ui/codex_request_stagger_seconds", 4.5)
        settings.setValue("ui/codex_vision_batch_size", 12)
        settings.setValue("ui/codex_video_frame_batch_size", 13)
        settings.setValue("ui/codex_fast_mode", True)
        settings.sync()

        with tempfile.TemporaryDirectory() as tmp:
            cfg = AppConfig().with_updates(paths={"output_dir": tmp, "temp_dir": tmp})
            dlg = SettingsDialog(None, cfg)

            self.assertEqual(dlg._codex_parallel_input.value(), 11)
            self.assertEqual(dlg._codex_stagger_input.value(), 4.5)
            self.assertEqual(dlg._codex_vision_batch_input.value(), 12)
            self.assertEqual(dlg._codex_video_batch_input.value(), 13)
            self.assertTrue(dlg._codex_fast_mode_cb.isChecked())
            dlg.deleteLater()
            self._app.processEvents()

    def test_settings_dialog_preserves_stored_codex_model(self):
        settings = isolated_settings()
        settings.setValue("ui/codex_model", "gpt-5.4-mini")
        settings.sync()

        with tempfile.TemporaryDirectory() as tmp:
            cfg = AppConfig().with_updates(paths={"output_dir": tmp, "temp_dir": tmp})
            dlg = SettingsDialog(None, cfg)

            self.assertEqual(dlg._codex_model_combo.currentText(), "gpt-5.4-mini")
            dlg.deleteLater()
            self._app.processEvents()

    def test_vision_queue_error_switch_setting_round_trips(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = AppConfig().with_updates(paths={"output_dir": tmp, "temp_dir": tmp})
            dlg = SettingsDialog(None, cfg)
            dlg._vision_advance_queue_cb.setChecked(True)

            applied = dlg.apply_config()

            self.assertTrue(applied.vision_api.advance_queue_on_retriable_errors)
            dlg.deleteLater()
            self._app.processEvents()

    def test_codex_fetch_models_repopulates_model_combo(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = AppConfig().with_updates(paths={"output_dir": tmp, "temp_dir": tmp})
            dlg = SettingsDialog(None, cfg)

            def run_fetch(_fn, on_done):
                on_done(["gpt-5.6-luna", "gpt-5.5"], None)

            with patch.object(dlg, "_run_fetch_async", side_effect=run_fetch), \
                    patch.object(QMessageBox, "information"):
                dlg._on_codex_fetch_models_clicked()

            self.assertEqual(
                [dlg._codex_model_combo.itemText(i) for i in range(dlg._codex_model_combo.count())],
                ["gpt-5.6-luna", "gpt-5.5"],
            )
            dlg.deleteLater()
            self._app.processEvents()

    def test_codex_model_apply_survives_dialog_reopen_and_main_window_sync(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = AppConfig().with_updates(paths={"output_dir": tmp, "temp_dir": tmp})
            dlg = SettingsDialog(None, cfg)
            dlg._api_key_input.setText("")
            dlg._codex_enabled_cb.setChecked(True)
            dlg._codex_model_combo.setCurrentText("gpt-5.4-mini")

            with patch("OCRLLM.gui.settings_dialog.inspect_codex_cli") as inspect, \
                    patch.object(SettingsDialog, "accept") as accept, \
                    patch.object(QMessageBox, "warning") as warning:
                inspect.return_value.ok = True
                inspect.return_value.message = "ok"
                dlg._on_apply()

            inspect.assert_called_once()
            self.assertEqual(inspect.call_args.args[0].model, "gpt-5.4-mini")
            accept.assert_called_once()
            warning.assert_not_called()
            dlg.deleteLater()
            self._app.processEvents()

            reopened = SettingsDialog(None, cfg)
            self.assertTrue(reopened._codex_enabled_cb.isChecked())
            self.assertEqual(reopened._codex_model_combo.currentText(), "gpt-5.4-mini")
            reopened.deleteLater()
            self._app.processEvents()

            window = QCRMainWindow(cfg=cfg)
            window._sync_api_from_ui()
            self.assertTrue(window._cfg.codex_vision.enabled)
            self.assertEqual(window._cfg.codex_vision.model, "gpt-5.4-mini")
            self.assertEqual(window._cfg.models.vision_model, "gpt-5.4-mini")
            window.deleteLater()
            self._app.processEvents()

    def test_settings_dialog_is_resizable_and_larger_by_default(self):
        cfg = AppConfig()
        dlg = SettingsDialog(None, cfg)

        self.assertTrue(dlg.isSizeGripEnabled())
        self.assertGreaterEqual(dlg.minimumWidth(), 840)
        self.assertGreaterEqual(dlg.minimumHeight(), 640)
        dlg.deleteLater()
        self._app.processEvents()

    def test_main_window_sync_uses_codex_runtime_controls(self):
        settings = isolated_settings()
        settings.setValue("ui/codex_vision_enabled", True)
        settings.setValue("ui/codex_parallel_requests", 9)
        settings.setValue("ui/codex_request_stagger_seconds", 1.5)
        settings.setValue("ui/codex_vision_batch_size", 10)
        settings.setValue("ui/codex_video_frame_batch_size", 11)
        settings.setValue("ui/codex_fast_mode", True)
        settings.sync()

        with tempfile.TemporaryDirectory() as tmp:
            cfg = AppConfig().with_updates(paths={"output_dir": tmp, "temp_dir": tmp})
            window = QCRMainWindow(cfg=cfg)
            window._sync_api_from_ui()

            self.assertTrue(window._cfg.codex_vision.enabled)
            self.assertEqual(window._cfg.codex_vision.parallel_requests, 9)
            self.assertEqual(window._cfg.codex_vision.request_stagger_seconds, 1.5)
            self.assertEqual(window._cfg.codex_vision.vision_batch_size, 10)
            self.assertEqual(window._cfg.codex_vision.video_frame_batch_size, 11)
            self.assertTrue(window._cfg.codex_vision.fast_mode)
            self.assertEqual(window._cfg.concurrency.llm_parallel_requests, 9)
            self.assertEqual(window._cfg.concurrency.llm_request_stagger_seconds, 1.5)
            self.assertEqual(window._cfg.processing.batch_size, 10)
            self.assertEqual(window._cfg.video.batch_size, 11)
            window.deleteLater()
            self._app.processEvents()


if __name__ == "__main__":
    unittest.main()
