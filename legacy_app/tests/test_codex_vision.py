import os
import json
import sys
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from OCRLLM.config import AppConfig, CodexVisionConfig
from OCRLLM.core.codex_vision import (
    CODEX_VISION_BATCH_SIZE,
    CODEX_VISION_DEFAULT_MODEL,
    CODEX_VISION_FAST_SERVICE_TIER,
    CODEX_VISION_MAX_PARALLEL,
    CodexCLIUnavailableError,
    CodexVisionRunner,
    _run_probe,
    apply_codex_vision_runtime_limits,
    fetch_codex_vision_models,
    inspect_codex_cli,
    migrate_stored_codex_vision_model,
    normalize_codex_vision_model,
)
from OCRLLM.core.llm_client import LLMClient


@contextmanager
def _closed_temp_image(suffix=".png"):
    image_file = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
    try:
        image_file.write(b"image")
    finally:
        image_file.close()
    try:
        yield image_file.name
    finally:
        os.unlink(image_file.name)


class CodexVisionRunnerTests(unittest.TestCase):
    def test_default_codex_vision_model_is_current_codex_default(self):
        cfg = CodexVisionConfig()

        self.assertEqual(cfg.model, "gpt-5.5")
        self.assertEqual(cfg.reasoning_effort, "medium")
        self.assertEqual(cfg.parallel_requests, CODEX_VISION_MAX_PARALLEL)
        self.assertEqual(cfg.vision_batch_size, CODEX_VISION_BATCH_SIZE)

    def test_stored_codex_model_is_preserved(self):
        self.assertEqual(migrate_stored_codex_vision_model("gpt-5.4-mini"), "gpt-5.4-mini")
        self.assertEqual(normalize_codex_vision_model(""), CODEX_VISION_DEFAULT_MODEL)
        self.assertEqual(normalize_codex_vision_model("gpt-5.3-codex-spark"), "gpt-5.3-codex-spark")
        self.assertEqual(normalize_codex_vision_model("gpt-5.4-mini"), "gpt-5.4-mini")

    def test_runner_uses_read_only_ask_style_exec_without_tools(self):
        cfg = AppConfig(
            codex_vision=CodexVisionConfig(
                enabled=True,
                command="codex",
                model="gpt-5.4-mini",
                reasoning_effort="medium",
            )
        )
        calls = []

        def fake_run(cmd, **kwargs):
            calls.append(cmd)
            self.assertEqual(kwargs["encoding"], "utf-8")
            self.assertEqual(kwargs["errors"], "replace")
            output_path = cmd[cmd.index("--output-last-message") + 1]
            with open(output_path, "w", encoding="utf-8") as f:
                f.write("OCR TEXT")
            return SimpleNamespace(returncode=0, stdout="", stderr="")

        with _closed_temp_image() as image_path, \
                patch("OCRLLM.core.codex_vision.shutil.which", return_value="/usr/bin/codex"), \
                patch("OCRLLM.core.codex_vision.subprocess.run", side_effect=fake_run):
            result = CodexVisionRunner(cfg.codex_vision).recognize("read", [image_path])

        self.assertEqual(result, "OCR TEXT")
        cmd = calls[0]
        self.assertIn("exec", cmd)
        self.assertIn("--ephemeral", cmd)
        self.assertIn("--ignore-user-config", cmd)
        self.assertIn("--ignore-rules", cmd)
        self.assertIn("--skip-git-repo-check", cmd)
        self.assertIn("--sandbox", cmd)
        self.assertEqual(cmd[cmd.index("--sandbox") + 1], "read-only")
        self.assertIn("--ask-for-approval", cmd)
        self.assertEqual(cmd[cmd.index("--ask-for-approval") + 1], "never")
        self.assertIn("-m", cmd)
        self.assertEqual(cmd[cmd.index("-m") + 1], "gpt-5.4-mini")
        self.assertIn('model_reasoning_effort="medium"', cmd)
        self.assertEqual(cmd[-2], "--")
        self.assertIn("用户原始提示:\nread", cmd[-1])
        for disabled in ["shell_tool", "browser_use", "computer_use", "apps", "multi_agent", "image_generation"]:
            disable_positions = [i for i, part in enumerate(cmd) if part == "--disable"]
            self.assertTrue(any(cmd[i + 1] == disabled for i in disable_positions))

    def test_runner_stages_unicode_image_paths_before_codex(self):
        calls = []

        with tempfile.TemporaryDirectory(prefix="OCRLLM-板书-") as source_dir:
            source = Path(source_dir) / "板书图片.jpg"
            source.write_bytes(b"image payload")

            def fake_run(cmd, **_kwargs):
                calls.append(cmd)
                image_path = Path(cmd[cmd.index("-i") + 1])
                self.assertTrue(image_path.is_file())
                self.assertTrue(str(image_path).isascii())
                self.assertEqual(image_path.read_bytes(), source.read_bytes())
                output_path = Path(cmd[cmd.index("--output-last-message") + 1])
                output_path.write_text("OCR TEXT", encoding="utf-8")
                return SimpleNamespace(returncode=0, stdout="", stderr="")

            with patch("OCRLLM.core.codex_vision.shutil.which", return_value="codex"), \
                    patch("OCRLLM.core.codex_vision.subprocess.run", side_effect=fake_run):
                result = CodexVisionRunner(CodexVisionConfig(enabled=True)).recognize(
                    "read", [str(source)]
                )

        self.assertEqual(result, "OCR TEXT")
        self.assertEqual(len(calls), 1)
        self.assertNotIn(str(source), calls[0])

    def test_runner_passes_fast_service_tier_when_enabled(self):
        cfg = CodexVisionConfig(enabled=True, fast_mode=True)
        runner = CodexVisionRunner(cfg)

        with patch.object(runner, "_build_command", wraps=runner._build_command) as build_command:
            command = runner._build_command(
                command="codex",
                prompt="read",
                image_paths=["page.png"],
                cwd=".",
                output_path="result.md",
            )

        build_command.assert_called_once()
        self.assertIn(f'service_tier="{CODEX_VISION_FAST_SERVICE_TIER}"', command)

    def test_probe_passes_windows_no_window_kwargs(self):
        seen_kwargs = {}

        def fake_run(_cmd, **kwargs):
            seen_kwargs.update(kwargs)
            return SimpleNamespace(returncode=0, stdout="ok", stderr="")

        with patch("OCRLLM.core.codex_vision.windows_no_window_kwargs", return_value={"creationflags": 123}), \
                patch("OCRLLM.core.codex_vision.subprocess.run", side_effect=fake_run):
            result = _run_probe(["codex", "--version"])

        self.assertEqual(result.returncode, 0)
        self.assertEqual(seen_kwargs["creationflags"], 123)

    def test_runner_retries_transient_nonzero_codex_result(self):
        cfg = AppConfig(
            codex_vision=CodexVisionConfig(
                enabled=True,
                command="codex",
                model="gpt-5.4-mini",
            )
        )
        calls = []

        def fake_run(cmd, **_kwargs):
            calls.append(cmd)
            if len(calls) == 1:
                return SimpleNamespace(
                    returncode=1,
                    stdout="Reading additional input from stdin...\nsession id: test-session\nuser\n用户原始提示:\nsecret",
                    stderr="",
                )
            output_path = cmd[cmd.index("--output-last-message") + 1]
            with open(output_path, "w", encoding="utf-8") as f:
                f.write("OCR TEXT")
            return SimpleNamespace(returncode=0, stdout="", stderr="")

        with _closed_temp_image() as image_path, \
                patch("OCRLLM.core.codex_vision.shutil.which", return_value="/usr/bin/codex"), \
                patch("OCRLLM.core.codex_vision.subprocess.run", side_effect=fake_run), \
                patch("OCRLLM.core.codex_vision.time.sleep"):
            result = CodexVisionRunner(cfg.codex_vision).recognize("read", [image_path])

        self.assertEqual(result, "OCR TEXT")
        self.assertEqual(len(calls), 2)

    def test_image_access_refusal_gets_long_backoff_and_extra_retries(self):
        cfg = AppConfig(
            codex_vision=CodexVisionConfig(enabled=True, command="codex", model="gpt-5.4-mini")
        )
        calls = []

        def fake_run(cmd, **_kwargs):
            calls.append(cmd)
            output_path = cmd[cmd.index("--output-last-message") + 1]
            with open(output_path, "w", encoding="utf-8") as f:
                if len(calls) <= 4:
                    f.write("SORRY4OCRLLM, because 无法访问所附的 5 张图片。")
                else:
                    f.write("OCR TEXT")
            return SimpleNamespace(returncode=0, stdout="", stderr="")

        sleeps = []
        with _closed_temp_image() as image_path, \
                patch("OCRLLM.core.codex_vision.shutil.which", return_value="/usr/bin/codex"), \
                patch("OCRLLM.core.codex_vision.subprocess.run", side_effect=fake_run), \
                patch("OCRLLM.core.codex_vision.time.sleep", side_effect=sleeps.append):
            result = CodexVisionRunner(cfg.codex_vision).recognize("read", [image_path])

        self.assertEqual(result, "OCR TEXT")
        # 4 次“看不到附件”拒绝均按长退避计划重试，不消耗常规重试次数
        self.assertEqual(len(calls), 5)
        self.assertEqual(sleeps[:4], [15.0, 45.0, 90.0, 180.0])

    def test_image_access_refusal_exhaustion_reports_service_side_loss(self):
        cfg = AppConfig(
            codex_vision=CodexVisionConfig(enabled=True, command="codex", model="gpt-5.4-mini")
        )

        def fake_run(cmd, **_kwargs):
            output_path = cmd[cmd.index("--output-last-message") + 1]
            with open(output_path, "w", encoding="utf-8") as f:
                f.write("SORRY4OCRLLM, because cannot access the attached images")
            return SimpleNamespace(returncode=0, stdout="", stderr="")

        with _closed_temp_image() as image_path, \
                patch("OCRLLM.core.codex_vision.shutil.which", return_value="/usr/bin/codex"), \
                patch("OCRLLM.core.codex_vision.subprocess.run", side_effect=fake_run), \
                patch("OCRLLM.core.codex_vision.time.sleep"):
            with self.assertRaises(CodexCLIUnavailableError) as ctx:
                CodexVisionRunner(cfg.codex_vision).recognize("read", [image_path])

        message = str(ctx.exception)
        self.assertIn("服务端持续丢失图片附件", message)
        self.assertIn("可稍后恢复重跑", message)

    def test_non_image_access_refusal_keeps_short_retry_path(self):
        cfg = AppConfig(
            codex_vision=CodexVisionConfig(enabled=True, command="codex", model="gpt-5.4-mini")
        )
        calls = []

        def fake_run(cmd, **_kwargs):
            calls.append(cmd)
            output_path = cmd[cmd.index("--output-last-message") + 1]
            with open(output_path, "w", encoding="utf-8") as f:
                f.write("SORRY4OCRLLM, because 图片内容过于模糊")
            return SimpleNamespace(returncode=0, stdout="", stderr="")

        with _closed_temp_image() as image_path, \
                patch("OCRLLM.core.codex_vision.shutil.which", return_value="/usr/bin/codex"), \
                patch("OCRLLM.core.codex_vision.subprocess.run", side_effect=fake_run), \
                patch("OCRLLM.core.codex_vision.time.sleep"):
            with self.assertRaises(CodexCLIUnavailableError) as ctx:
                CodexVisionRunner(cfg.codex_vision).recognize("read", [image_path])

        self.assertEqual(len(calls), 3)
        self.assertIn("Codex 拒绝识别", str(ctx.exception))

    def test_runner_failure_summary_does_not_dump_prompt(self):
        cfg = AppConfig(
            codex_vision=CodexVisionConfig(
                enabled=True,
                command="codex",
                model="gpt-5.4-mini",
            )
        )

        def fake_run(_cmd, **_kwargs):
            return SimpleNamespace(
                returncode=1,
                stdout=(
                    "Reading additional input from stdin...\n"
                    "session id: test-session\n"
                    "user\n"
                    "用户原始提示:\n"
                    "<!-- meta:frame id=board_001_010s time=00:10 -->\n"
                    "secret prompt text"
                ),
                stderr="",
            )

        with _closed_temp_image() as image_path, \
                patch("OCRLLM.core.codex_vision.shutil.which", return_value="/usr/bin/codex"), \
                patch("OCRLLM.core.codex_vision.subprocess.run", side_effect=fake_run), \
                patch("OCRLLM.core.codex_vision.time.sleep"):
            with self.assertRaises(CodexCLIUnavailableError) as ctx:
                CodexVisionRunner(cfg.codex_vision).recognize("read", [image_path])

        message = str(ctx.exception)
        self.assertIn("Codex CLI exited with code 1", message)
        self.assertIn("session id: test-session", message)
        self.assertNotIn("用户原始提示", message)
        self.assertNotIn("secret prompt text", message)
        self.assertNotIn("\n", message)

    def test_llm_client_can_use_codex_vision_without_api_key(self):
        cfg = AppConfig(codex_vision=CodexVisionConfig(enabled=True))
        with patch("OCRLLM.core.llm_client.CodexVisionRunner") as runner_cls:
            runner_cls.return_value.recognize.return_value = "TEXT"
            client = LLMClient(cfg)
            result = client.chat_with_images("read", ["a.png"], max_retries=1)

        self.assertEqual(result, "TEXT")
        runner_cls.return_value.recognize.assert_called_once_with("read", ["a.png"])

    def test_runtime_limits_use_codex_specific_controls(self):
        cfg = AppConfig().with_updates(
            codex_vision={
                "enabled": True,
                "parallel_requests": 7,
                "request_stagger_seconds": 3.5,
                "vision_batch_size": 8,
                "video_frame_batch_size": 9,
            },
            concurrency={"llm_parallel_requests": 99},
            processing={"batch_size": 20},
            video={"batch_size": 30},
        )

        limited = apply_codex_vision_runtime_limits(cfg)

        self.assertEqual(limited.concurrency.llm_parallel_requests, 7)
        self.assertEqual(limited.concurrency.llm_request_stagger_seconds, 3.5)
        self.assertEqual(limited.processing.batch_size, 8)
        self.assertEqual(limited.video.batch_size, 9)

    def test_env_codex_mode_applies_runtime_limits_for_cli_entrypoints(self):
        with patch.dict(os.environ, {
            "OCRLLM_CODEX_VISION_ENABLED": "1",
            "OCRLLM_CODEX_PARALLEL_REQUESTS": "6",
            "OCRLLM_CODEX_REQUEST_STAGGER_SECONDS": "2.5",
            "OCRLLM_CODEX_VISION_BATCH_SIZE": "7",
            "OCRLLM_CODEX_VIDEO_FRAME_BATCH_SIZE": "8",
            "OCRLLM_CODEX_FAST_MODE": "1",
        }, clear=True):
            cfg = AppConfig.from_env()

        self.assertTrue(cfg.codex_vision.enabled)
        self.assertEqual(cfg.models.vision_model, "gpt-5.5")
        self.assertEqual(cfg.codex_vision.parallel_requests, 6)
        self.assertEqual(cfg.codex_vision.request_stagger_seconds, 2.5)
        self.assertEqual(cfg.codex_vision.vision_batch_size, 7)
        self.assertEqual(cfg.codex_vision.video_frame_batch_size, 8)
        self.assertTrue(cfg.codex_vision.fast_mode)
        self.assertEqual(cfg.concurrency.llm_parallel_requests, 6)
        self.assertEqual(cfg.concurrency.llm_request_stagger_seconds, 2.5)
        self.assertEqual(cfg.processing.batch_size, 7)
        self.assertEqual(cfg.video.batch_size, 8)

    def test_probe_decodes_utf8_output_when_locale_is_cp1252(self):
        script = "import sys; sys.stdout.buffer.write('识图完成 ŝ'.encode('utf-8'))"

        result = _run_probe([sys.executable, "-c", script])

        self.assertEqual(result.returncode, 0)
        self.assertIn("识图完成 ŝ", result.stdout)


class CodexInspectionTests(unittest.TestCase):
    def test_fetch_codex_vision_models_returns_image_models_only(self):
        models_payload = {
            "models": [
                {"slug": "gpt-5.5", "input_modalities": ["text", "image"]},
                {"slug": "text-only", "input_modalities": ["text"]},
                {"slug": "gpt-5.5", "input_modalities": ["text", "image"]},
            ]
        }

        with patch("OCRLLM.core.codex_vision.shutil.which", return_value="/usr/bin/codex"), \
                patch("OCRLLM.core.codex_vision.subprocess.run") as run:
            run.return_value = SimpleNamespace(returncode=0, stdout=json.dumps(models_payload), stderr="")
            models = fetch_codex_vision_models(CodexVisionConfig(command="codex"))

        self.assertEqual(models, ["gpt-5.5"])

    def test_inspection_rejects_fast_mode_for_model_without_priority_tier(self):
        models_payload = {
            "models": [
                {
                    "slug": "gpt-5.4-mini",
                    "input_modalities": ["text", "image"],
                    "service_tiers": [],
                    "supported_reasoning_levels": [{"effort": "medium"}],
                }
            ]
        }

        def fake_run(cmd, **_kwargs):
            if cmd[-1] == "--version":
                return SimpleNamespace(returncode=0, stdout="codex-cli 0.144.5", stderr="")
            if cmd == ["codex", "--help"]:
                return SimpleNamespace(returncode=0, stdout="--ask-for-approval", stderr="")
            if cmd[:2] == ["codex", "exec"]:
                return SimpleNamespace(
                    returncode=0,
                    stdout="--image --model --sandbox --disable --ephemeral --ignore-user-config --ignore-rules --output-last-message",
                    stderr="",
                )
            return SimpleNamespace(returncode=0, stdout=json.dumps(models_payload), stderr="")

        with patch("OCRLLM.core.codex_vision.shutil.which", return_value="/usr/bin/codex"), \
                patch("OCRLLM.core.codex_vision.subprocess.run", side_effect=fake_run):
            report = inspect_codex_cli(CodexVisionConfig(model="gpt-5.4-mini", fast_mode=True))

        self.assertFalse(report.ok)
        self.assertIn("不支持 Fast mode", report.message)
    def test_inspection_rejects_missing_image_or_disable_support(self):
        def fake_run(cmd, **_kwargs):
            if cmd[-1] == "--version":
                return SimpleNamespace(returncode=0, stdout="codex-cli 0.135.0", stderr="")
            if cmd == ["codex", "--help"]:
                return SimpleNamespace(returncode=0, stdout="Usage: codex\n  --ask-for-approval\n", stderr="")
            if cmd[:2] == ["codex", "exec"]:
                return SimpleNamespace(returncode=0, stdout="Usage: codex exec\n  --image\n  --sandbox\n", stderr="")
            return SimpleNamespace(returncode=0, stdout='{"models":[]}', stderr="")

        with patch("OCRLLM.core.codex_vision.shutil.which", return_value="/usr/bin/codex"), \
                patch("OCRLLM.core.codex_vision.subprocess.run", side_effect=fake_run):
            report = inspect_codex_cli(CodexVisionConfig(model="gpt-5.3-codex-spark"))

        self.assertFalse(report.ok)
        self.assertIn("--disable", report.message)

    def test_inspection_uses_current_default_for_empty_model(self):
        models_payload = {
            "models": [
                {
                    "slug": "gpt-5.5",
                    "input_modalities": ["text", "image"],
                    "supported_reasoning_levels": [{"effort": "medium"}],
                }
            ]
        }

        def fake_run(cmd, **_kwargs):
            if cmd[-1] == "--version":
                return SimpleNamespace(returncode=0, stdout="codex-cli 0.142.0", stderr="")
            if cmd == ["codex", "--help"]:
                return SimpleNamespace(returncode=0, stdout="Usage: codex\n  --ask-for-approval\n", stderr="")
            if cmd[:2] == ["codex", "exec"]:
                return SimpleNamespace(
                    returncode=0,
                    stdout=(
                        "Usage: codex exec\n"
                        "  --image\n  --model\n  --sandbox\n  --disable\n"
                        "  --ephemeral\n  --ignore-user-config\n  --ignore-rules\n"
                        "  --output-last-message\n"
                    ),
                    stderr="",
                )
            if cmd == ["codex", "debug", "models"]:
                import json
                return SimpleNamespace(returncode=0, stdout=json.dumps(models_payload), stderr="")
            return SimpleNamespace(returncode=1, stdout="", stderr="unexpected command")

        with patch("OCRLLM.core.codex_vision.shutil.which", return_value="/usr/bin/codex"), \
                patch("OCRLLM.core.codex_vision.subprocess.run", side_effect=fake_run):
            report = inspect_codex_cli(CodexVisionConfig(model=""))

        self.assertTrue(report.ok)
        self.assertIn("model=gpt-5.5", report.message)

    def test_inspection_explains_windowsapps_codex_access_denied(self):
        windowsapps_codex = (
            r"C:\Program Files\WindowsApps\OpenAI.Codex_26.616.4196.0_x64__2p2nqsd0c76g0"
            r"\app\resources\codex.exe"
        )

        with patch("OCRLLM.core.codex_vision.shutil.which", return_value=windowsapps_codex), \
                patch("OCRLLM.core.codex_vision.os.name", "nt"), \
                patch("OCRLLM.core.codex_vision.subprocess.run", side_effect=PermissionError("Access is denied")):
            report = inspect_codex_cli(CodexVisionConfig())

        self.assertFalse(report.ok)
        self.assertIn("WindowsApps", report.message)
        self.assertIn("Codex CLI", report.message)

    def test_runner_rejects_more_than_five_images(self):
        cfg = CodexVisionConfig(enabled=True)
        runner = CodexVisionRunner(cfg)

        with self.assertRaises(CodexCLIUnavailableError):
            runner.recognize("read", [f"{i}.png" for i in range(CODEX_VISION_BATCH_SIZE + 1)])

    def test_runner_uses_configured_image_limit(self):
        cfg = CodexVisionConfig(enabled=True, vision_batch_size=7, video_frame_batch_size=7)
        runner = CodexVisionRunner(cfg)

        with self.assertRaises(CodexCLIUnavailableError):
            runner.recognize("read", [f"{i}.png" for i in range(8)])


if __name__ == "__main__":
    unittest.main()
