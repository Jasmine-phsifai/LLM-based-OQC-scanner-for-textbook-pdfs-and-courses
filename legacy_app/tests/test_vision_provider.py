import os
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

PROJECT_PARENT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_PARENT not in sys.path:
    sys.path.insert(0, PROJECT_PARENT)

from PIL import Image

from OCRLLM.config import AppConfig, APIConfig, ModelConfig, VisionAPIConfig
from OCRLLM.core.llm_client import LLMClient


class VisionProviderConfigTests(unittest.TestCase):
    def test_from_env_keeps_dashscope_base_url_and_adds_optional_vision_provider(self):
        with patch.dict(os.environ, {
            "DASHSCOPE_API_KEY": "dash-key",
            "DASHSCOPE_BASE_URL": "https://dash.example/v1",
            "OCRLLM_VISION_API_KEY": "vision-key",
            "OCRLLM_VISION_BASE_URL": "https://vision.example/v1",
            "OCRLLM_VISION_WIRE_API": "responses",
            "OCRLLM_VISION_MODEL": "oasis-vision-model",
            "OCRLLM_VISION_ADVANCE_QUEUE_ON_RETRIABLE_ERRORS": "true",
        }, clear=True):
            cfg = AppConfig.from_env()

        self.assertEqual(cfg.api.api_key, "dash-key")
        self.assertEqual(cfg.api.base_url, "https://dash.example/v1")
        self.assertTrue(cfg.vision_api.enabled)
        self.assertEqual(cfg.vision_api.api_key, "vision-key")
        self.assertEqual(cfg.vision_api.base_url, "https://vision.example/v1")
        self.assertEqual(cfg.vision_api.wire_api, "responses")
        self.assertTrue(cfg.vision_api.advance_queue_on_retriable_errors)
        self.assertEqual(cfg.models.vision_model, "oasis-vision-model")

    def test_retriable_proxy_error_can_advance_independent_vision_queue(self):
        class ProxyStatusError(RuntimeError):
            status_code = 429

        cfg = AppConfig(
            api=APIConfig(api_key="dash-key"),
            models=ModelConfig(vision_model="primary-model"),
            vision_api=VisionAPIConfig(
                enabled=True,
                api_key="vision-key",
                base_url="https://vision.example/v1",
                advance_queue_on_retriable_errors=True,
                vision_model_queue=["fallback-model"],
            ),
        )
        client = LLMClient(cfg)
        client.vision_client.chat.completions.create = MagicMock(
            side_effect=[
                ProxyStatusError("proxy rate limit"),
                ProxyStatusError("proxy rate limit"),
                ["OCRLLM TEST 12345"],
            ]
        )

        with patch("OCRLLM.core.llm_client._notify_free_tier_switch") as notify_free_tier_switch:
            result = client.chat_with_images("read", [], max_retries=1)

        self.assertEqual(result, "OCRLLM TEST 12345")
        notify_free_tier_switch.assert_not_called()
        calls = client.vision_client.chat.completions.create.call_args_list
        self.assertEqual(calls[0].kwargs["model"], "primary-model")
        self.assertTrue(calls[0].kwargs["stream"])
        self.assertEqual(calls[1].kwargs["model"], "primary-model")
        self.assertFalse(calls[1].kwargs["stream"])
        self.assertEqual(calls[2].kwargs["model"], "fallback-model")

    def test_exhausted_retriable_vision_queue_preserves_provider_error(self):
        class ProxyStatusError(RuntimeError):
            status_code = 503

        cfg = AppConfig(
            api=APIConfig(api_key="dash-key"),
            models=ModelConfig(vision_model="primary-model"),
            vision_api=VisionAPIConfig(
                enabled=True,
                api_key="vision-key",
                base_url="https://vision.example/v1",
                advance_queue_on_retriable_errors=True,
                vision_model_queue=["fallback-model"],
            ),
        )
        client = LLMClient(cfg)
        client.vision_client.chat.completions.create = MagicMock(
            side_effect=[ProxyStatusError("provider unavailable")] * 4
        )

        with patch("OCRLLM.core.llm_client._notify_free_tier_switch") as notify_free_tier_switch:
            with self.assertRaisesRegex(ProxyStatusError, "provider unavailable"):
                client.chat_with_images("read", [], max_retries=1)

        notify_free_tier_switch.assert_not_called()
        self.assertEqual(client.vision_client.chat.completions.create.call_count, 4)

    def test_explicit_free_tier_exhaustion_keeps_quota_switch_notification(self):
        class QuotaStatusError(RuntimeError):
            status_code = 403

        cfg = AppConfig(
            api=APIConfig(api_key="dash-key"),
            models=ModelConfig(vision_model="primary-model"),
            vision_api=VisionAPIConfig(
                enabled=True,
                api_key="vision-key",
                base_url="https://vision.example/v1",
                vision_model_queue=["fallback-model"],
            ),
        )
        client = LLMClient(cfg)
        client.vision_client.chat.completions.create = MagicMock(
            side_effect=[
                QuotaStatusError("AllocationQuota.FreeTierOnly"),
                ["OCRLLM TEST 12345"],
            ]
        )

        with patch("OCRLLM.core.llm_client._notify_free_tier_switch") as notify_free_tier_switch:
            result = client.chat_with_images("read", [], max_retries=1)

        self.assertEqual(result, "OCRLLM TEST 12345")
        notify_free_tier_switch.assert_called_once_with(
            "primary-model", "fallback-model", "vision"
        )

    def test_responses_503_failover_does_not_report_quota_exhaustion(self):
        class ProxyStatusError(RuntimeError):
            status_code = 503

        cfg = AppConfig(
            api=APIConfig(api_key="dash-key"),
            models=ModelConfig(vision_model="primary-model"),
            vision_api=VisionAPIConfig(
                enabled=True,
                api_key="vision-key",
                base_url="https://vision.example/v1",
                wire_api="responses",
                advance_queue_on_retriable_errors=True,
                vision_model_queue=["fallback-model"],
            ),
        )
        client = LLMClient(cfg)
        client.vision_client.responses.create = MagicMock(
            side_effect=[
                ProxyStatusError("provider unavailable"),
                SimpleNamespace(output_text="OCRLLM TEST 12345"),
            ]
        )

        with patch("OCRLLM.core.llm_client._notify_free_tier_switch") as notify_free_tier_switch:
            result = client.chat_with_images("read", [], max_retries=1)

        self.assertEqual(result, "OCRLLM TEST 12345")
        notify_free_tier_switch.assert_not_called()
        calls = client.vision_client.responses.create.call_args_list
        self.assertEqual([call.kwargs["model"] for call in calls], [
            "primary-model",
            "fallback-model",
        ])

    def test_external_vision_stream_status_error_falls_back_to_nonstream(self):
        class ProxyStatusError(RuntimeError):
            status_code = 502

        cfg = AppConfig(
            api=APIConfig(api_key="dash-key"),
            vision_api=VisionAPIConfig(
                enabled=True,
                api_key="vision-key",
                base_url="https://vision.example/v1",
            ),
        )
        client = LLMClient(cfg)
        client.vision_client.chat.completions.create = MagicMock(
            side_effect=[
                ProxyStatusError("streaming image bridge failed"),
                {"choices": [{"message": {"content": "OCRLLM TEST 12345"}}]},
            ]
        )

        result = client.chat_with_images("read", [], max_retries=1)

        self.assertEqual(result, "OCRLLM TEST 12345")
        calls = client.vision_client.chat.completions.create.call_args_list
        self.assertTrue(calls[0].kwargs["stream"])
        self.assertFalse(calls[1].kwargs["stream"])

    def test_responses_payload_carries_image_and_requested_provider_options(self):
        cfg = AppConfig(
            api=APIConfig(api_key="dash-key"),
            vision_api=VisionAPIConfig(
                enabled=True,
                api_key="vision-key",
                base_url="https://vision.example/v1",
                wire_api="responses",
                model_reasoning_effort="high",
                network_access=True,
                disable_response_storage=True,
            ),
        )
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            image_path = tmp.name
        try:
            Image.new("RGB", (8, 8), "white").save(image_path)
            client = LLMClient(cfg)
            payload = client._responses_payload("gpt-5.5", "scan", [image_path])
        finally:
            try:
                os.unlink(image_path)
            except OSError:
                pass

        self.assertEqual(payload["model"], "gpt-5.5")
        self.assertEqual(payload["reasoning"], {"effort": "high"})
        self.assertEqual(payload["tools"], [{"type": "web_search_preview"}])
        self.assertFalse(payload["store"])
        content = payload["input"][0]["content"]
        self.assertEqual(content[0], {"type": "input_text", "text": "scan"})
        self.assertEqual(content[1]["type"], "input_image")
        self.assertTrue(content[1]["image_url"].startswith("data:image/png;base64,"))

    def test_enabled_vision_provider_uses_responses_client_without_free_tier_chain(self):
        cfg = AppConfig(
            api=APIConfig(api_key="dash-key"),
            vision_api=VisionAPIConfig(
                enabled=True,
                api_key="vision-key",
                base_url="https://vision.example/v1",
                wire_api="responses",
            ),
        )
        client = LLMClient(cfg)
        client.vision_client.responses.create = MagicMock(return_value=SimpleNamespace(output_text="OCRLLM TEST 12345"))
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            image_path = tmp.name
        try:
            Image.new("RGB", (8, 8), "white").save(image_path)
            result = client.chat_with_images("read", [image_path], model="gpt-5.5", max_retries=1)
        finally:
            try:
                os.unlink(image_path)
            except OSError:
                pass

        self.assertEqual(result, "OCRLLM TEST 12345")
        client.vision_client.responses.create.assert_called_once()

    def test_enabled_external_vision_provider_chat_omits_dashscope_extra_body(self):
        cfg = AppConfig(
            api=APIConfig(api_key="dash-key"),
            vision_api=VisionAPIConfig(
                enabled=True,
                api_key="vision-key",
                base_url="https://vision.example/v1",
                wire_api="chat",
            ),
        )
        client = LLMClient(cfg)
        client.vision_client.chat.completions.create = MagicMock(return_value=["OCRLLM TEST 12345"])
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            image_path = tmp.name
        try:
            Image.new("RGB", (8, 8), "white").save(image_path)
            result = client.chat_with_images("read", [image_path], model="gpt-vision", max_retries=1)
        finally:
            try:
                os.unlink(image_path)
            except OSError:
                pass

        self.assertEqual(result, "OCRLLM TEST 12345")
        kwargs = client.vision_client.chat.completions.create.call_args.kwargs
        self.assertNotIn("extra_body", kwargs)

    def test_chat_image_payload_places_text_before_images(self):
        cfg = AppConfig(
            api=APIConfig(api_key="dash-key"),
            vision_api=VisionAPIConfig(
                enabled=True,
                api_key="vision-key",
                base_url="https://vision.example/v1",
            ),
        )
        client = LLMClient(cfg)
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            image_path = tmp.name
        try:
            Image.new("RGB", (8, 8), "white").save(image_path)
            content = client._chat_messages_for_images("read", [image_path])[0]["content"]
        finally:
            try:
                os.unlink(image_path)
            except OSError:
                pass

        self.assertEqual(content[0], {"type": "text", "text": "read"})
        self.assertEqual(content[1]["type"], "image_url")

    def test_vision_provider_can_initialize_without_dashscope_key(self):
        cfg = AppConfig(
            api=APIConfig(api_key=""),
            vision_api=VisionAPIConfig(
                enabled=True,
                api_key="vision-key",
                base_url="https://vision.example/v1",
                wire_api="chat",
            ),
        )
        client = LLMClient(cfg)
        client.vision_client.chat.completions.create = MagicMock(return_value=["OCRLLM TEST 12345"])
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            image_path = tmp.name
        try:
            Image.new("RGB", (8, 8), "white").save(image_path)
            result = client.chat_with_images("read", [image_path], model="gpt-vision", max_retries=1)
        finally:
            try:
                os.unlink(image_path)
            except OSError:
                pass

        self.assertEqual(result, "OCRLLM TEST 12345")

    def test_vision_provider_root_base_url_is_normalized_to_v1(self):
        cfg = AppConfig(
            api=APIConfig(api_key="dash-key"),
            vision_api=VisionAPIConfig(
                enabled=True,
                api_key="vision-key",
                base_url="https://vision.example",
                wire_api="chat",
            ),
        )

        client = LLMClient(cfg)

        self.assertEqual(str(client.vision_client.base_url), "https://vision.example/v1/")

    def test_responses_parser_accepts_dict_shape(self):
        response = {
            "output": [{
                "content": [
                    {"text": "OCRLLM"},
                    {"text": " TEST"},
                ],
            }],
        }

        self.assertEqual(LLMClient._extract_responses_text(response), "OCRLLM TEST")

    def test_openai_compatible_stream_parser_accepts_text_and_dict_chunks(self):
        chunks = [
            "OCR",
            {"choices": [{"delta": {"content": "LLM"}}]},
            SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(content=" TEST"))]),
        ]

        self.assertEqual(LLMClient._collect_stream(chunks), "OCRLLM TEST")

    def test_openai_compatible_message_parser_accepts_string_and_dict_responses(self):
        self.assertEqual(LLMClient._extract_message_text(" OCRLLM TEST "), "OCRLLM TEST")

        completion = {
            "choices": [{
                "message": {
                    "content": [
                        {"text": "OCRLLM"},
                        {"text": " TEST"},
                    ],
                },
            }],
        }

        self.assertEqual(LLMClient._extract_message_text(completion), "OCRLLM TEST")


if __name__ == "__main__":
    unittest.main()
