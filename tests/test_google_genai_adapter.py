"""Failing-first contract for the native Google GenAI image vertical slice."""

from __future__ import annotations

import importlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

import ocrllm
from ocrllm import Config, VisionModelSettings, recognize as recognize_public
from ocrllm.errors import (
    ConfigError,
    Cancelled,
    DependencyMissing,
    InvalidSource,
    ProviderError,
    ProviderContentBlocked,
    ProviderPermissionDenied,
    ProviderRequestInvalid,
    ProviderUnavailable,
    QuotaExhausted,
    RateLimited,
)
from tests.write_test_image import write_test_image


MODEL = "gemini-2.5-flash"


def _google_settings(*, api_key: str | None = "test-only-google-key"):
    return ocrllm.GoogleGenAISettings(api_key=api_key)


class _Part:
    @staticmethod
    def from_bytes(*, data: bytes, mime_type: str):
        return {"data": data, "mime_type": mime_type}


class _HttpOptions:
    def __init__(self, *, timeout: int) -> None:
        self.timeout = timeout


class _Models:
    def __init__(self) -> None:
        self.list_calls = 0
        self.generate_calls: list[dict[str, object]] = []

    def list(self):
        self.list_calls += 1
        return (
            SimpleNamespace(
                name="models/gemini-2.5-flash",
                supported_actions=["generateContent"],
            ),
            SimpleNamespace(
                name="models/text-embedding-004",
                supported_actions=["embedContent"],
            ),
            SimpleNamespace(
                name="models/gemini-image-only",
                supported_actions=["generateContent"],
            ),
            SimpleNamespace(
                name="models/no-actions",
                supported_actions=None,
            ),
            _HostileCatalogRow(),
        )

    def generate_content(self, *, model: str, contents):
        self.generate_calls.append({"model": model, "contents": contents})
        return SimpleNamespace(
            text="# recognized\n",
            candidates=(),
            usage_metadata=SimpleNamespace(
                prompt_token_count=123,
                candidates_token_count=45,
            ),
        )


class _Client:
    def __init__(self, models: _Models) -> None:
        self.models = models
        self.closed = False

    def close(self) -> None:
        self.closed = True


class _HostileCatalogRow:
    name = "models/hostile"

    @property
    def supported_actions(self):
        raise RuntimeError("PRIVATE-CATALOG-ROW")


class _FakeGoogleModule:
    types = SimpleNamespace(HttpOptions=_HttpOptions, Part=_Part)

    def __init__(self) -> None:
        self.models = _Models()
        self.clients: list[_Client] = []
        self.client_kwargs: list[dict[str, object]] = []

    def Client(self, **kwargs):
        self.client_kwargs.append(kwargs)
        client = _Client(self.models)
        self.clients.append(client)
        return client


class _CheckpointAwareCancellation:
    """Cancel only after the first workflow slot is durably visible."""

    def __init__(self, state_path: Path) -> None:
        self.state_path = state_path
        self.observed_draft = False

    def is_set(self) -> bool:
        if not self.state_path.is_file():
            return False
        document = json.loads(self.state_path.read_text(encoding="utf-8"))
        slots = document["slots"]
        self.observed_draft = (
            document["result"]["status"] == "partial"
            and document["result"]["markdown"] == ""
            and len(slots) == 1
            and slots[0]["slot_id"] == "draft"
        )
        return self.observed_draft


def test_google_settings_is_public_exact_frozen_and_secret_safe():
    settings = _google_settings(api_key="GOOGLE-SECRET-9f31")

    assert type(settings).__name__ == "GoogleGenAISettings"
    assert "GOOGLE-SECRET-9f31" not in repr(settings)
    assert type(Config(provider=settings).provider) is type(settings)

    class SettingsSubclass(type(settings)):
        pass

    with pytest.raises(ConfigError, match="exact GoogleGenAISettings"):
        Config(provider=SettingsSubclass(api_key="test-only"))


def test_google_dependency_is_lazy_and_typed(monkeypatch):
    loader = importlib.import_module("ocrllm.providers.google_genai.load_google_genai")
    original_import = __import__

    def missing_google(name, *args, **kwargs):
        if name == "google" or name.startswith("google.genai"):
            raise ModuleNotFoundError("test-only missing google-genai")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr("builtins.__import__", missing_google)
    with pytest.raises(DependencyMissing) as captured:
        loader.load_google_genai()
    assert captured.value.details["extra"] == "google"


def test_google_credential_precedence_and_missing_error(monkeypatch):
    resolver = importlib.import_module(
        "ocrllm.providers.google_genai.resolve_google_genai_credential"
    )
    monkeypatch.setenv("GOOGLE_API_KEY", "google-env")
    monkeypatch.setenv("GEMINI_API_KEY", "gemini-env")

    assert resolver.resolve_google_genai_credential(_google_settings()) == "test-only-google-key"
    assert resolver.resolve_google_genai_credential(_google_settings(api_key=None)) == "google-env"
    monkeypatch.delenv("GOOGLE_API_KEY")
    assert resolver.resolve_google_genai_credential(_google_settings(api_key=None)) == "gemini-env"
    monkeypatch.delenv("GEMINI_API_KEY")
    with pytest.raises(ConfigError) as captured:
        resolver.resolve_google_genai_credential(_google_settings(api_key=None))
    assert captured.value.code == "CONFIG_MISSING"

    malformed = "bad\nPRIVATE-GOOGLE-KEY-82d1"
    monkeypatch.setenv("GOOGLE_API_KEY", malformed)
    with pytest.raises(ConfigError) as captured:
        resolver.resolve_google_genai_credential(_google_settings(api_key=None))
    assert captured.value.code == "CONFIG_INVALID"
    assert malformed not in str(captured.value)
    assert malformed not in repr(captured.value.details)


def test_google_credential_rejects_internal_whitespace_without_echo(monkeypatch):
    resolver = importlib.import_module(
        "ocrllm.providers.google_genai.resolve_google_genai_credential"
    )
    malformed = "PRIVATE GOOGLE KEY 5f20"
    monkeypatch.setenv("GOOGLE_API_KEY", malformed)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    with pytest.raises(ConfigError) as captured:
        resolver.resolve_google_genai_credential(_google_settings(api_key=None))

    assert captured.value.code == "CONFIG_INVALID"
    assert malformed not in str(captured.value)
    assert malformed not in repr(captured.value.details)


def test_google_catalog_filters_generate_content_normalizes_ids_and_closes(monkeypatch):
    catalog = importlib.import_module(
        "ocrllm.providers.google_genai.list_google_genai_models"
    )
    fake = _FakeGoogleModule()
    monkeypatch.setattr(catalog, "load_google_genai", lambda: fake)

    models = ocrllm.list_google_genai_models(
        _google_settings(), timeout_seconds=7.5
    )

    assert models == ("gemini-2.5-flash", "gemini-image-only")
    assert fake.models.list_calls == 1
    assert fake.clients[0].closed is True
    assert fake.client_kwargs[0]["api_key"] == "test-only-google-key"
    assert fake.client_kwargs[0]["http_options"].timeout == 7500


def test_google_request_uses_bounded_snapshot_bytes_and_prompt_last(tmp_path):
    builder = importlib.import_module(
        "ocrllm.providers.google_genai.build_google_genai_image_request"
    )
    image = write_test_image(tmp_path / "source.png")

    request = builder.build_google_genai_image_request(
        (image,), prompt="recognize", model=MODEL
    )

    assert request.model == MODEL
    assert request.contents[-1] == "recognize"
    assert request.contents[0].mime_type == "image/png"
    assert request.contents[0].data == image.read_bytes()
    assert request.inline_byte_count == image.stat().st_size
    assert request.wire_byte_upper_bound >= request.inline_byte_count
    assert request.wire_byte_upper_bound <= builder.MAX_GOOGLE_INLINE_BYTES


def test_google_response_returns_text_and_optional_usage():
    parser = importlib.import_module(
        "ocrllm.providers.google_genai.parse_google_genai_response"
    )
    response = SimpleNamespace(
        text="# recognized\n",
        candidates=(),
        usage_metadata=SimpleNamespace(
            prompt_token_count=123,
            candidates_token_count=45,
        ),
    )

    parsed = parser.parse_google_genai_response(response, model=MODEL)

    assert parsed.markdown == "# recognized\n"
    assert parsed.input_tokens == 123
    assert parsed.output_tokens == 45

    without_usage = parser.parse_google_genai_response(
        SimpleNamespace(text="# recognized\n", candidates=(), usage_metadata=None),
        model=MODEL,
    )
    assert without_usage.input_tokens is None
    assert without_usage.output_tokens is None


def test_google_response_falls_back_to_candidate_parts_and_maps_safety_block():
    parser = importlib.import_module(
        "ocrllm.providers.google_genai.parse_google_genai_response"
    )
    response = SimpleNamespace(
        text=None,
        prompt_feedback=SimpleNamespace(block_reason=None),
        candidates=(
            SimpleNamespace(
                finish_reason="STOP",
                content=SimpleNamespace(
                    parts=(SimpleNamespace(text="# first\n"), SimpleNamespace(text="second\n"))
                ),
            ),
        ),
        usage_metadata=None,
    )

    parsed = parser.parse_google_genai_response(response, model=MODEL)
    assert parsed.markdown == "# first\nsecond\n"

    blocked = SimpleNamespace(
        text=None,
        prompt_feedback=SimpleNamespace(block_reason="SAFETY"),
        candidates=(),
        usage_metadata=None,
    )
    with pytest.raises(ProviderContentBlocked) as captured:
        parser.parse_google_genai_response(blocked, model=MODEL)
    assert captured.value.details["failure_scope"] == "request"

    candidate_blocked = SimpleNamespace(
        text=None,
        prompt_feedback=None,
        candidates=(
            SimpleNamespace(
                finish_reason="SAFETY",
                content=SimpleNamespace(parts=()),
            ),
        ),
        usage_metadata=None,
    )
    with pytest.raises(ProviderContentBlocked):
        parser.parse_google_genai_response(candidate_blocked, model=MODEL)


@pytest.mark.parametrize(
    ("code", "status", "message", "expected_type", "failure_scope", "error_code"),
    [
        (429, "RESOURCE_EXHAUSTED", "temporarily rate limited", RateLimited, "provider", None),
        (503, "UNAVAILABLE", "service unavailable", ProviderUnavailable, "provider", None),
        (404, "NOT_FOUND", "model not found", ProviderUnavailable, "model", None),
        (
            400,
            "INVALID_ARGUMENT",
            "unsupported modality for this model",
            ProviderUnavailable,
            "model",
            None,
        ),
        (400, "INVALID_ARGUMENT", "invalid request", ProviderRequestInvalid, "request", None),
        (
            400,
            "INVALID_ARGUMENT",
            "invalid modality parameter",
            ProviderRequestInvalid,
            "request",
            None,
        ),
        (
            400,
            "INVALID_ARGUMENT",
            "request only supports up to 8 images",
            ProviderRequestInvalid,
            "request",
            None,
        ),
        (
            401,
            "UNAUTHENTICATED",
            "authentication failed",
            ProviderError,
            "credential",
            "PROVIDER_AUTHENTICATION",
        ),
        (
            400,
            "INVALID_ARGUMENT",
            "API key not valid",
            ProviderError,
            "credential",
            "PROVIDER_AUTHENTICATION",
        ),
        (
            403,
            "PERMISSION_DENIED",
            "permission denied",
            ProviderPermissionDenied,
            "credential",
            None,
        ),
    ],
)
def test_google_errors_map_to_typed_secret_safe_failures(
    code, status, message, expected_type, failure_scope, error_code
):
    mapper = importlib.import_module(
        "ocrllm.providers.google_genai.map_google_genai_error"
    )
    raw = SimpleNamespace(
        code=code,
        status=status,
        message=f"{message}: PRIVATE-GOOGLE-BODY-41aa",
        details={"error": {"message": "PRIVATE-GOOGLE-BODY-41aa"}},
    )

    mapped = mapper.map_google_genai_error(raw, model=MODEL)

    assert isinstance(mapped, expected_type)
    assert mapped.details["provider"] == "google"
    assert mapped.details["model"] == MODEL
    assert mapped.details["failure_scope"] == failure_scope
    if error_code is not None:
        assert mapped.code == error_code
    assert "PRIVATE-GOOGLE-BODY-41aa" not in str(mapped)
    assert "PRIVATE-GOOGLE-BODY-41aa" not in repr(mapped.details)


def test_google_quota_advisory_is_model_scoped_quota_not_plain_429():
    mapper = importlib.import_module(
        "ocrllm.providers.google_genai.map_google_genai_error"
    )
    raw = SimpleNamespace(
        code=429,
        status="RESOURCE_EXHAUSTED",
        message="You exceeded your current quota, check your plan and billing details",
        details={},
    )

    mapped = mapper.map_google_genai_error(raw, model=MODEL)

    assert isinstance(mapped, QuotaExhausted)
    assert mapped.details["failure_scope"] == "model"


@pytest.mark.parametrize(
    ("raw", "code"),
    [
        (TimeoutError("private"), "PROVIDER_TIMEOUT"),
        (ConnectionError("private"), "PROVIDER_NETWORK"),
        (SimpleNamespace(code=408, status="DEADLINE_EXCEEDED", message="private"), "PROVIDER_TIMEOUT"),
        (SimpleNamespace(code=504, status="DEADLINE_EXCEEDED", message="private"), "PROVIDER_TIMEOUT"),
    ],
)
def test_google_transport_errors_keep_timeout_and_network_codes(raw, code):
    mapper = importlib.import_module(
        "ocrllm.providers.google_genai.map_google_genai_error"
    )

    mapped = mapper.map_google_genai_error(raw, model=MODEL)

    assert mapped.code == code
    assert mapped.details["failure_scope"] == "provider"


def test_google_resolves_as_builtin_and_capability_is_honest():
    resolver = importlib.import_module("ocrllm.providers.resolve_vision_provider")
    config = Config(
        provider=_google_settings(),
        vision_model=VisionModelSettings(name=MODEL),
    )

    resolved = resolver.resolve_vision_provider(config)
    reports = {item.name: item for item in ocrllm.get_capabilities(config)}

    assert resolved.name == "google"
    assert resolved.model == MODEL
    assert resolved.built_in is True
    assert reports["image.board.png"].status == "experimental"
    assert "provider.google.vision" not in reports


def test_public_google_recognition_reports_model_call_and_token_usage(tmp_path, monkeypatch):
    adapter = importlib.import_module("ocrllm.providers.google_genai.recognize_images")
    fake = _FakeGoogleModule()
    monkeypatch.setattr(adapter, "load_google_genai", lambda: fake)
    image = write_test_image(tmp_path / "source.png")

    result = recognize_public(
        image,
        config=Config(
            provider=_google_settings(),
            vision_model=VisionModelSettings(name=MODEL),
        ),
    )

    assert result.markdown == "# recognized\n"
    assert result.metadata["provider"] == "google"
    assert result.metadata["model"] == MODEL
    assert result.metadata["provider_call_count"] == 1
    assert result.metadata["current_model_token_usage"] == (
        {
            "model": MODEL,
            "input_tokens": 123,
            "output_tokens": 45,
        },
    )
    assert len(fake.models.generate_calls) == 1
    assert len(fake.clients) == 1
    assert all(client.closed for client in fake.clients)


def test_google_review_sums_fresh_usage_for_the_same_model(tmp_path, monkeypatch):
    adapter = importlib.import_module("ocrllm.providers.google_genai.recognize_images")
    fake = _FakeGoogleModule()
    monkeypatch.setattr(adapter, "load_google_genai", lambda: fake)
    image = write_test_image(tmp_path / "source.png")

    result = recognize_public(
        image,
        config=Config(
            provider=_google_settings(),
            vision_model=VisionModelSettings(name=MODEL),
            preferences=ocrllm.RecognitionPreferences(review_passes=1),
        ),
    )

    assert result.metadata["provider_call_count"] == 2
    assert result.metadata["current_model_token_usage"] == (
        {"model": MODEL, "input_tokens": 246, "output_tokens": 90},
    )


def test_completed_google_resume_makes_no_sdk_call_and_hides_historical_usage(
    tmp_path, monkeypatch
):
    adapter = importlib.import_module("ocrllm.providers.google_genai.recognize_images")
    fake = _FakeGoogleModule()
    monkeypatch.setattr(adapter, "load_google_genai", lambda: fake)
    image = write_test_image(tmp_path / "source.png")
    output_dir = tmp_path / "output"
    first_config = Config(
        provider=_google_settings(),
        vision_model=VisionModelSettings(name=MODEL),
        output_dir=output_dir,
    )

    recognize_public(image, config=first_config)
    client_count = len(fake.clients)
    resumed = recognize_public(
        image,
        config=Config(
            provider=_google_settings(),
            vision_model=VisionModelSettings(name=MODEL),
            output_dir=output_dir,
            resume=True,
        ),
    )

    assert len(fake.clients) == client_count
    assert resumed.metadata["provider_call_count"] == 1
    assert resumed.metadata["current_model_token_usage"] == ()


def test_google_cancel_after_draft_then_resume_pays_only_for_review(
    tmp_path, monkeypatch
):
    adapter = importlib.import_module("ocrllm.providers.google_genai.recognize_images")
    fake = _FakeGoogleModule()
    monkeypatch.setattr(adapter, "load_google_genai", lambda: fake)
    image = write_test_image(tmp_path / "source.png")
    output_dir = tmp_path / "output"
    state_path = output_dir / "source_board.ocrllm-state.json"
    cancellation = _CheckpointAwareCancellation(state_path)
    preferences = ocrllm.RecognitionPreferences(review_passes=1)

    with pytest.raises(Cancelled) as interrupted:
        recognize_public(
            image,
            config=Config(
                provider=_google_settings(),
                vision_model=VisionModelSettings(name=MODEL),
                output_dir=output_dir,
                cancellation=cancellation,
                preferences=preferences,
            ),
        )

    assert cancellation.observed_draft is True
    assert interrupted.value.details["workflow_pass"] == "review"
    assert interrupted.value.details["provider_calls_attempted"] == 1
    assert interrupted.value.details["settled_model_usage"] == (
        {
            "model": MODEL,
            "input_count": 123,
            "output_count": 45,
            "unit": "tokens",
        },
    )
    assert len(fake.models.generate_calls) == 1
    partial = json.loads(state_path.read_text(encoding="utf-8"))
    assert partial["result"]["status"] == "partial"
    assert [slot["slot_id"] for slot in partial["slots"]] == ["draft"]
    assert not (output_dir / "source_board.md").exists()

    resumed = recognize_public(
        image,
        config=Config(
            provider=_google_settings(),
            vision_model=VisionModelSettings(name=MODEL),
            output_dir=output_dir,
            resume=True,
            preferences=preferences,
        ),
    )

    assert len(fake.models.generate_calls) == 2
    assert resumed.metadata["provider_call_count"] == 1
    assert resumed.metadata["current_model_token_usage"] == (
        {"model": MODEL, "input_tokens": 123, "output_tokens": 45},
    )
    assert tuple(dict(slot) for slot in resumed.metadata["workflow_slots"]) == (
        {
            "slot_id": "draft",
            "workflow_pass": "draft",
            "provider": "google",
            "model": MODEL,
            "reused": True,
            "provider_calls_attempted": 0,
        },
        {
            "slot_id": "review",
            "workflow_pass": "review",
            "provider": "google",
            "model": MODEL,
            "reused": False,
            "provider_calls_attempted": 1,
        },
    )


def test_oversized_inline_aggregate_is_rejected_before_sdk_construction(
    tmp_path, monkeypatch
):
    builder = importlib.import_module(
        "ocrllm.providers.google_genai.build_google_genai_image_request"
    )
    adapter = importlib.import_module("ocrllm.providers.google_genai.recognize_images")
    monkeypatch.setattr(builder, "MAX_GOOGLE_INLINE_BYTES", 1)
    sdk_constructed = False

    def fail_if_sdk_is_loaded():
        nonlocal sdk_constructed
        sdk_constructed = True
        raise AssertionError("SDK must not be constructed before inline preflight")

    monkeypatch.setattr(adapter, "load_google_genai", fail_if_sdk_is_loaded)
    first = write_test_image(tmp_path / "first.png")
    second = write_test_image(tmp_path / "second.png")

    with pytest.raises(InvalidSource) as captured:
        recognize_public(
            (first, second),
            config=Config(
                provider=_google_settings(),
                vision_model=VisionModelSettings(name=MODEL),
            ),
        )
    assert captured.value.code == "SOURCE_TOO_LARGE"
    assert sdk_constructed is False
