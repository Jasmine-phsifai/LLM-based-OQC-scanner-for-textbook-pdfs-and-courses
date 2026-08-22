import builtins
import unittest
from unittest.mock import patch

import httpx
from pathlib import Path
from types import SimpleNamespace

from OCRLLM.core.providers.google_provider import (
    ClassifiedGoogleError,
    GoogleErrorKind,
    GoogleProviderClient,
    GoogleProviderFailure,
    classify_google_error,
    google_retry_delay_seconds,
)
from OCRLLM.config import AppConfig


class GoogleProviderErrorTests(unittest.TestCase):
    def test_missing_google_genai_reports_current_python_and_install_command(self):
        cfg = AppConfig().with_updates(google_api={"enabled": True, "api_key": "AIza-test"})
        client = GoogleProviderClient(cfg=cfg)
        real_import = builtins.__import__

        def fail_google_import(name, *args, **kwargs):
            if name == "google" or name.startswith("google."):
                raise ImportError("google SDK missing in this environment")
            return real_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=fail_google_import):
            with self.assertRaisesRegex(
                RuntimeError,
                r"(?s)当前 Python 环境.*python -m pip install -r requirements\.txt.*google-genai>=1\.53\.0",
            ):
                client._get_client()

    def test_missing_google_types_reports_actionable_message_before_reading_image(self):
        cfg = AppConfig().with_updates(google_api={"enabled": True, "api_key": "AIza-test"})
        client = GoogleProviderClient(cfg=cfg)
        real_import = builtins.__import__

        def fail_google_types_import(name, *args, **kwargs):
            if name == "google.genai":
                raise ImportError("google.genai.types missing")
            return real_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=fail_google_types_import):
            with self.assertRaisesRegex(
                RuntimeError,
                r"(?s)当前 Python 环境.*python -m pip install -r requirements\.txt.*google-genai>=1\.53\.0",
            ):
                client._make_image_part("D:/does/not/exist.jpg")

    def test_google_audio_default_chain_prefers_pro_before_flash_and_lite(self):
        cfg = AppConfig().with_updates(google_api={"enabled": True, "api_key": "AIza-test"})
        client = GoogleProviderClient(cfg=cfg)

        chain = client._audio_chain()
        pro_positions = [idx for idx, model in enumerate(chain) if "pro" in model.lower()]
        flash_positions = [
            idx
            for idx, model in enumerate(chain)
            if "flash" in model.lower() or "lite" in model.lower()
        ]

        self.assertTrue(pro_positions, chain)
        self.assertTrue(flash_positions, chain)
        self.assertLess(min(pro_positions), min(flash_positions), chain)

    def test_audio_switches_to_flash_after_pro_rate_limit_retries_are_exhausted(self):
        cfg = AppConfig().with_updates(
            google_api={
                "enabled": True,
                "api_key": "AIza-test",
                "audio_model": "gemini-2.5-pro",
                "audio_model_queue": ["gemini-2.5-flash"],
            },
        )
        client = GoogleProviderClient(cfg=cfg)
        calls: list[str] = []

        def fake_retry(model: str, _invoke, _max_retries: int, text_validator=None) -> str:
            calls.append(model)
            if model == "gemini-2.5-pro":
                raise GoogleProviderFailure(ClassifiedGoogleError(
                    GoogleErrorKind.RATE_LIMIT,
                    should_switch_model=False,
                    should_retry_same_model=True,
                    message="429 Too Many Requests: rate limit exceeded",
                ))
            return "flash transcript"

        client._retry_same_model = fake_retry

        text = client._call_with_model_switch(
            "gemini-2.5-pro",
            client._audio_chain(),
            "audio",
            lambda _model: "",
            max_retries=2,
        )

        self.assertEqual(text, "flash transcript")
        self.assertEqual(calls, ["gemini-2.5-pro", "gemini-2.5-flash"])

    def test_quota_exhaustion_switches_model_without_retrying_same_model(self):
        classified = classify_google_error(RuntimeError(
            "RESOURCE_EXHAUSTED: You exceeded your current quota, "
            "please check your plan and billing details."
        ))

        self.assertEqual(classified.kind, GoogleErrorKind.QUOTA_EXHAUSTED)
        self.assertTrue(classified.should_switch_model)
        self.assertFalse(classified.should_retry_same_model)

    def test_json_quota_exhaustion_switches_candidate_without_same_model_retry(self):
        cfg = AppConfig().with_updates(google_api={"enabled": True, "api_key": "AIza-test"})
        client = GoogleProviderClient(cfg=cfg)
        client._sleep_with_cancel = lambda _seconds: None
        calls: list[str] = []
        quota_error = (
            '{"error":{"code":429,"status":"RESOURCE_EXHAUSTED",'
            '"message":"You exceeded your current quota, please check your plan and billing details."}}'
        )
        classified = classify_google_error(RuntimeError(quota_error))

        self.assertEqual(classified.kind, GoogleErrorKind.QUOTA_EXHAUSTED)
        self.assertTrue(classified.should_switch_model)
        self.assertFalse(classified.should_retry_same_model)

        def invoke(model: str) -> str:
            calls.append(model)
            if model == "gemini-quota-spent":
                return quota_error
            return "fallback result"

        result = client._call_with_model_switch(
            "gemini-quota-spent",
            ["gemini-fallback"],
            "vision",
            invoke,
            max_retries=3,
        )

        self.assertEqual(result, "fallback result")
        self.assertEqual(calls, ["gemini-quota-spent", "gemini-fallback"])

    def test_json_rate_limit_retries_same_candidate_without_switching(self):
        cfg = AppConfig().with_updates(google_api={"enabled": True, "api_key": "AIza-test"})
        client = GoogleProviderClient(cfg=cfg)
        client._sleep_with_cancel = lambda _seconds: None
        calls: list[str] = []
        rate_limit_error = (
            '{"error":{"code":429,"status":"RESOURCE_EXHAUSTED",'
            '"message":"You exceeded your current quota; check your plan and billing details. '
            'Rate limit exceeded: RPM window."}}'
        )

        def invoke(model: str) -> str:
            calls.append(model)
            if len(calls) == 1:
                return rate_limit_error
            return "retry result"

        result = client._call_with_model_switch(
            "gemini-rate-limited",
            ["gemini-fallback"],
            "vision",
            invoke,
            max_retries=3,
        )

        self.assertEqual(result, "retry result")
        self.assertEqual(calls, ["gemini-rate-limited", "gemini-rate-limited"])

    def test_json_payment_failure_remains_billing_error(self):
        classified = classify_google_error(RuntimeError(
            '{"error":{"code":400,"status":"FAILED_PRECONDITION",'
            '"message":"Payment method declined; billing account requires attention."}}'
        ))

        self.assertEqual(classified.kind, GoogleErrorKind.BILLING)
        self.assertTrue(classified.should_switch_model)
        self.assertFalse(classified.should_retry_same_model)

    def test_rate_limit_retries_same_model_before_user_visible_failure(self):
        classified = classify_google_error(RuntimeError(
            "429 Too Many Requests: rate limit exceeded for current project"
        ))

        self.assertEqual(classified.kind, GoogleErrorKind.RATE_LIMIT)
        self.assertFalse(classified.should_switch_model)
        self.assertTrue(classified.should_retry_same_model)

    def test_internal_server_error_retries_same_model(self):
        classified = classify_google_error(RuntimeError(
            "500 INTERNAL. An internal error has occurred. Please retry."
        ))

        self.assertEqual(classified.kind, GoogleErrorKind.BAD_RESPONSE)
        self.assertFalse(classified.should_switch_model)
        self.assertTrue(classified.should_retry_same_model)

    def test_404_model_error_switches_to_next_candidate(self):
        classified = classify_google_error(RuntimeError(
            '{"error":{"code":404,"status":"NOT_FOUND","message":"models/gemini-old is not found"}}'
        ))

        self.assertEqual(classified.kind, GoogleErrorKind.INVALID_MODEL)
        self.assertTrue(classified.should_switch_model)
        self.assertFalse(classified.should_retry_same_model)

    def test_network_error_retries_same_model(self):
        classified = classify_google_error(TimeoutError("timed out while connecting"))

        self.assertEqual(classified.kind, GoogleErrorKind.NETWORK)
        self.assertFalse(classified.should_switch_model)
        self.assertTrue(classified.should_retry_same_model)

    def test_remote_protocol_disconnect_is_retryable_network_error(self):
        classified = classify_google_error(httpx.RemoteProtocolError(
            "Server disconnected without sending a response."
        ))

        self.assertEqual(classified.kind, GoogleErrorKind.NETWORK)
        self.assertFalse(classified.should_switch_model)
        self.assertTrue(classified.should_retry_same_model)

    def test_ssl_unexpected_eof_text_is_retryable_network_error(self):
        classified = classify_google_error(RuntimeError(
            "[SSL: UNEXPECTED_EOF_WHILE_READING] EOF occurred in violation of protocol (_ssl.c:1017)"
        ))

        self.assertEqual(classified.kind, GoogleErrorKind.NETWORK)
        self.assertFalse(classified.should_switch_model)
        self.assertTrue(classified.should_retry_same_model)

    def test_google_503_high_demand_retries_same_model(self):
        classified = classify_google_error(RuntimeError(
            "503 UNAVAILABLE. {'error': {'code': 503, 'message': "
            "'This model is currently experiencing high demand. Spikes in demand are usually temporary. "
            "Please try again later.', 'status': 'UNAVAILABLE'}}"
        ))

        self.assertEqual(classified.kind, GoogleErrorKind.RATE_LIMIT)
        self.assertFalse(classified.should_switch_model)
        self.assertTrue(classified.should_retry_same_model)

    def test_rate_limit_waits_across_minute_window(self):
        classified = classify_google_error(RuntimeError(
            "429 Too Many Requests: rate limit exceeded for current project"
        ))

        self.assertGreaterEqual(google_retry_delay_seconds(classified, attempt=1), 60.0)

    def test_retry_delay_honors_google_retry_info(self):
        classified = classify_google_error(RuntimeError(
            '{"error":{"code":429,"status":"RESOURCE_EXHAUSTED",'
            '"message":"Rate limit exceeded",'
            '"details":[{"@type":"type.googleapis.com/google.rpc.RetryInfo",'
            '"retryDelay":"73s"}]}}'
        ))

        self.assertEqual(google_retry_delay_seconds(classified, attempt=1), 73.0)

    def test_long_audio_retries_top_level_google_400_json_error_text(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            audio_path = Path(tmp) / "lecture.mp3"
            audio_path.write_bytes(b"fake audio")
            calls: list[str] = []

            class FakeFiles:
                def upload(self, file):
                    return SimpleNamespace(name="files/test", state="ACTIVE")

                def get(self, name):
                    return SimpleNamespace(name=name, state="ACTIVE")

            class FakeModels:
                def generate_content(self, model, contents):
                    calls.append(model)
                    if len(calls) < 3:
                        return SimpleNamespace(
                            text='{"code":400,"status":"INVALID_ARGUMENT","message":"json failed"}'
                        )
                    return SimpleNamespace(text="老师开始讲课，今天我们继续讨论数据库事务。")

            cfg = AppConfig().with_updates(
                google_api={
                    "enabled": True,
                    "api_key": "AIza-test",
                    "audio_model": "gemini-3.5-flash",
                    "audio_model_queue": ["gemini-3.5-flash"],
                },
            )
            client = GoogleProviderClient(cfg=cfg)
            client._client = SimpleNamespace(files=FakeFiles(), models=FakeModels())
            client._sleep_with_cancel = lambda _seconds: None

            text = client.transcribe_long_audio(
                str(audio_path),
                model="gemini-3.5-flash",
                max_retries=3,
            )

            self.assertIn("老师开始讲课", text)
            self.assertEqual(calls, ["gemini-3.5-flash"] * 3)

    def test_provider_reuses_successful_model_after_switchable_failures(self):
        cfg = AppConfig().with_updates(google_api={"enabled": True, "api_key": "AIza-test"})
        client = GoogleProviderClient(cfg=cfg)
        calls: list[str] = []

        def fake_retry(model: str, _invoke, _max_retries: int, text_validator=None) -> str:
            calls.append(model)
            if model == "broken-image-model":
                raise GoogleProviderFailure(ClassifiedGoogleError(
                    GoogleErrorKind.INVALID_MODEL,
                    should_switch_model=True,
                    should_retry_same_model=False,
                    message="404 model not found",
                ))
            return f"ok:{model}"

        client._retry_same_model = fake_retry

        first = client._call_with_model_switch(
            "broken-image-model",
            ["broken-image-model", "gemini-flash-latest"],
            "vision",
            lambda _model: "",
            max_retries=1,
        )
        second = client._call_with_model_switch(
            "broken-image-model",
            ["broken-image-model", "gemini-flash-latest"],
            "vision",
            lambda _model: "",
            max_retries=1,
        )

        self.assertEqual(first, "ok:gemini-flash-latest")
        self.assertEqual(second, "ok:gemini-flash-latest")
        self.assertEqual(calls, ["broken-image-model", "gemini-flash-latest", "gemini-flash-latest"])

    def test_chat_text_uses_text_chain_without_image_preview_models(self):
        cfg = AppConfig().with_updates(
            google_api={
                "enabled": True,
                "api_key": "AIza-test",
                "text_model": "gemini-3.5-flash",
                "vision_model_queue": ["gemini-2.5-flash-image-preview"],
                "audio_model_queue": ["gemini-2.5-flash"],
            },
        )
        client = GoogleProviderClient(cfg=cfg)
        captured = {}

        def fake_call(primary, chain, kind, _invoke, _max_retries):
            captured["primary"] = primary
            captured["chain"] = chain
            captured["kind"] = kind
            return "ok"

        client._call_with_model_switch = fake_call

        self.assertEqual(client.chat_text("extract hotwords"), "ok")
        self.assertEqual(captured["primary"], "gemini-3.5-flash")
        self.assertEqual(captured["kind"], "text")
        self.assertIn("gemini-2.5-flash", captured["chain"])
        self.assertNotIn("gemini-2.5-flash-image-preview", captured["chain"])

    def test_long_audio_switches_model_when_content_validator_rejects(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            audio_path = Path(tmp) / "lecture.mp3"
            audio_path.write_bytes(b"fake audio")
            calls: list[str] = []

            class FakeFiles:
                def upload(self, file):
                    return SimpleNamespace(name="files/test", state="ACTIVE")

                def get(self, name):
                    return SimpleNamespace(name=name, state="ACTIVE")

            class FakeModels:
                def generate_content(self, model, contents):
                    calls.append(model)
                    if model == "gemini-bad":
                        return SimpleNamespace(text="根据您提供的板书内容，为您提取热词表如下：线性规划")
                    return SimpleNamespace(text="老师开始讲课，今天我们继续讨论线性规划的内点法。")

            cfg = AppConfig().with_updates(
                google_api={
                    "enabled": True,
                    "api_key": "AIza-test",
                    "audio_model_queue": ["gemini-good"],
                },
            )
            client = GoogleProviderClient(cfg=cfg)
            client._client = SimpleNamespace(files=FakeFiles(), models=FakeModels())

            text = client.transcribe_long_audio(
                str(audio_path),
                model="gemini-bad",
                max_retries=1,
                text_validator=lambda value: "不是课堂转写" if "热词表" in value else None,
            )

            self.assertIn("老师开始讲课", text)
            self.assertEqual(calls, ["gemini-bad", "gemini-good"])


if __name__ == "__main__":
    unittest.main()
