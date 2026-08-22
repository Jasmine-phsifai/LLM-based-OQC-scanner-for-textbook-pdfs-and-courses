"""Kill-mid-request regression tests for slot-indexed resume (Stage M2)."""

from __future__ import annotations

import hashlib
import importlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from ocrllm import (
    Config,
    DashScopeSettings,
    ProviderError,
    QuotaExhausted,
    RecognitionPreferences,
    ResumeStateError,
    VisionModelSettings,
    recognize,
)

from write_test_image import write_test_image


def _state_document(output_dir: Path, stem: str = "board_board") -> dict:
    state_path = output_dir / f"{stem}.ocrllm-state.json"
    return json.loads(state_path.read_text(encoding="utf-8"))


class InterruptibleSlotProvider:
    """Pay per call, then raise after a caller-chosen number of slots."""

    resume_identity = "m2-slot-provider-v1"

    def __init__(self, *, fail_after: int | None = None) -> None:
        self.fail_after = fail_after
        self.calls: list[str] = []

    def recognize_images(self, image_paths, *, prompt, config):
        self.calls.append(prompt)
        if self.fail_after is not None and len(self.calls) > self.fail_after:
            raise ProviderError("killed mid-request", code="PROVIDER_UNAVAILABLE")
        return f"# Response {len(self.calls)}\n"


def _slot_config(
    provider: object,
    output_dir: Path,
    *,
    resume: bool = False,
) -> Config:
    return Config(
        provider=provider,
        output_dir=output_dir,
        preferences=RecognitionPreferences(draft_candidates=2, review_passes=1),
        resume=resume,
    )


def test_interrupted_request_keeps_paid_slots_and_resume_pays_only_missing(
    tmp_path: Path,
) -> None:
    source = write_test_image(tmp_path / "board.png")
    output_dir = tmp_path / "output"
    provider = InterruptibleSlotProvider(fail_after=2)

    with pytest.raises(ProviderError) as killed:
        recognize(source, config=_slot_config(provider, output_dir))

    assert killed.value.details["workflow_pass"] == "consensus_review"
    assert killed.value.details["provider_calls_attempted"] == 3
    assert len(provider.calls) == 3
    assert not (output_dir / "board_board.md").exists()

    interrupted_state = _state_document(output_dir)
    assert interrupted_state["state_version"] == "ocrllm.image-resume.v2"
    assert interrupted_state["identity_version"] == "ocrllm.image-request.v2"
    assert [slot["slot_id"] for slot in interrupted_state["slots"]] == [
        "draft",
        "draft_2",
    ]
    assert interrupted_state["result"]["markdown"] == ""

    provider.fail_after = None
    result = recognize(
        source,
        config=_slot_config(provider, output_dir, resume=True),
    )

    assert len(provider.calls) == 4
    assert result.markdown == "# Response 4\n"
    slots = [dict(slot) for slot in result.metadata["workflow_slots"]]
    assert slots == [
        {
            "slot_id": "draft",
            "workflow_pass": "draft",
            "provider": None,
            "model": None,
            "reused": True,
            "provider_calls_attempted": 0,
        },
        {
            "slot_id": "draft_2",
            "workflow_pass": "draft_2",
            "provider": None,
            "model": None,
            "reused": True,
            "provider_calls_attempted": 0,
        },
        {
            "slot_id": "consensus_review",
            "workflow_pass": "consensus_review",
            "provider": None,
            "model": None,
            "reused": False,
            "provider_calls_attempted": 1,
        },
    ]
    completed_state = _state_document(output_dir)
    assert completed_state["result"]["markdown"] == "# Response 4\n"
    assert len(completed_state["slots"]) == 3

    recognize(source, config=_slot_config(provider, output_dir, resume=True))
    assert len(provider.calls) == 4


def test_resume_rejects_legacy_v1_state_naming_the_version_difference(
    tmp_path: Path,
) -> None:
    source = write_test_image(tmp_path / "board.png")
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    markdown = "# Legacy completed board\n"
    legacy_state = {
        "state_version": "ocrllm.image-resume.v1",
        "request_fingerprint": hashlib.sha256(b"legacy-request").hexdigest(),
        "processor_name": "image.vision.board",
        "processor_version": "image.vision.board.v1",
        "sources": [
            {
                "uri": source.resolve().as_uri(),
                "byte_size": source.stat().st_size,
                "sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
            }
        ],
        "result": {
            "markdown": markdown,
            "media_type": "image",
            "profile": "board",
            "status": "complete",
            "hotwords": [],
            "warnings": [],
            "metadata": {},
        },
        "final_markdown_sha256": hashlib.sha256(
            markdown.encode("utf-8")
        ).hexdigest(),
    }
    (output_dir / "board_board.ocrllm-state.json").write_text(
        json.dumps(legacy_state),
        encoding="utf-8",
    )
    provider = InterruptibleSlotProvider()

    with pytest.raises(ResumeStateError) as captured:
        recognize(source, config=_slot_config(provider, output_dir, resume=True))

    assert captured.value.code == "RESUME_STATE_MISMATCH"
    assert (
        captured.value.details["state_identity_version"]
        == "ocrllm.image-request.v1"
    )
    assert (
        captured.value.details["request_identity_version"]
        == "ocrllm.image-request.v2"
    )
    assert provider.calls == []


def test_prompt_version_bump_invalidates_resume_identity(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = write_test_image(tmp_path / "board.png")
    output_dir = tmp_path / "output"
    provider = InterruptibleSlotProvider()

    recognize(source, config=_slot_config(provider, output_dir))
    assert len(provider.calls) == 3

    fingerprint_module = importlib.import_module("ocrllm.fingerprint_image_request")
    monkeypatch.setattr(
        fingerprint_module,
        "BOARD_PROMPT_VERSION",
        "board.v-prompt-edit",
    )
    with pytest.raises(ResumeStateError) as captured:
        recognize(source, config=_slot_config(provider, output_dir, resume=True))

    assert captured.value.code == "RESUME_STATE_MISMATCH"
    assert len(provider.calls) == 3


class _ModelAwareProvider:
    """Fail one chosen model on its second call to force a fallback."""

    resume_identity = "m2-model-provider-v1"

    def __init__(self, *, quota_model: str) -> None:
        self.quota_model = quota_model
        self.calls: list[str] = []

    def recognize_images(self, image_paths, *, prompt, config):
        model = config.vision_model.name
        self.calls.append(model)
        if model == self.quota_model and self.calls.count(model) == 2:
            raise QuotaExhausted("per-model quota spent")
        return f"# {model} response {self.calls.count(model)}\n"


def test_fallback_does_not_reuse_or_discard_other_models_paid_slots(
    tmp_path: Path,
) -> None:
    source = write_test_image(tmp_path / "board.png")
    output_dir = tmp_path / "output"
    provider = _ModelAwareProvider(quota_model="quota-model")

    result = recognize(
        source,
        config=Config(
            provider=provider,
            output_dir=output_dir,
            vision_model=VisionModelSettings(
                name="quota-model",
                candidate_models=("recovery-model",),
            ),
            preferences=RecognitionPreferences(draft_candidates=1, review_passes=1),
        ),
    )

    assert provider.calls == [
        "quota-model",
        "quota-model",
        "recovery-model",
        "recovery-model",
    ]
    assert result.markdown == "# recovery-model response 2\n"
    assert [dict(attempt) for attempt in result.metadata["model_attempts"]] == [
        {
            "model": "quota-model",
            "outcome": "PROVIDER_QUOTA_EXHAUSTED",
            "disposition": "stop",
            "provider_calls_attempted": 2,
        },
        {"model": "recovery-model", "outcome": "success", "provider_calls_attempted": 2},
    ]
    slots = [dict(slot) for slot in result.metadata["workflow_slots"]]
    assert [slot["slot_id"] for slot in slots] == ["draft", "review"]
    assert {slot["model"] for slot in slots} == {"recovery-model"}
    assert all(slot["reused"] is False for slot in slots)

    persisted = _state_document(output_dir)
    assert {slot["model"] for slot in persisted["slots"]} == {"recovery-model"}


adapter_module = importlib.import_module("ocrllm.providers.dashscope.recognize_images")


class _FakeOpenAIModule:
    class APITimeoutError(Exception):
        pass

    class APIConnectionError(Exception):
        pass

    class AuthenticationError(Exception):
        pass

    class PermissionDeniedError(Exception):
        pass

    class RateLimitError(Exception):
        pass

    class InternalServerError(Exception):
        pass

    def __init__(self, client: object) -> None:
        self.client = client

    def OpenAI(self, **kwargs):
        return self.client


def _response(content: str, *, model: str):
    message = SimpleNamespace(content=content, refusal=None, role="assistant")
    choice = SimpleNamespace(message=message, finish_reason="stop", index=0)
    return SimpleNamespace(choices=[choice], model=model)


class _ScoutKillClient:
    def __init__(self, *, fail_on_call: int | None) -> None:
        self.fail_on_call = fail_on_call
        self.calls: list[dict] = []
        self.chat = SimpleNamespace(
            completions=SimpleNamespace(
                with_raw_response=SimpleNamespace(create=self.create)
            )
        )

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if self.fail_on_call is not None and len(self.calls) == self.fail_on_call:
            raise _FakeOpenAIModule.APITimeoutError("killed mid-scout")
        model = kwargs["model"]
        content = (
            "# Exact board\n" if model != "qwen-vl-max" else "+ | foreign gene | I:V\n"
        )
        return SimpleNamespace(
            headers={},
            parse=lambda: _response(content, model=model),
        )

    def close(self):
        pass


def _scout_settings() -> DashScopeSettings:
    return DashScopeSettings(
        region="ap-southeast-1",
        base_url="https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
        api_key="test-key",
        standalone_sign_scout_model="qwen-vl-max",
    )


def test_scout_slots_survive_mid_scout_crash_and_resume_pays_missing_scouts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = write_test_image(tmp_path / "board.png", size=(12, 13))
    output_dir = tmp_path / "output"
    client = _ScoutKillClient(fail_on_call=3)
    monkeypatch.setattr(
        adapter_module,
        "load_openai",
        lambda: _FakeOpenAIModule(client),
    )
    monkeypatch.setattr(
        importlib.import_module("ocrllm.providers.dashscope.resolve_dashscope_model"),
        "fetch_dashscope_model_catalog",
        lambda settings: frozenset({"qwen-vl-max"}),
    )

    with pytest.raises(ProviderError) as killed:
        recognize(
            source,
            config=Config(provider=_scout_settings(), output_dir=output_dir),
        )

    assert killed.value.details["workflow_pass"] == "standalone_sign_scout_2"
    assert killed.value.details["provider_calls_attempted"] == 3
    assert len(client.calls) == 3
    interrupted_state = _state_document(output_dir)
    assert [slot["slot_id"] for slot in interrupted_state["slots"]] == [
        "draft",
        "standalone_sign_scout_1",
    ]

    client.fail_on_call = None
    result = recognize(
        source,
        config=Config(
            provider=_scout_settings(),
            output_dir=output_dir,
            resume=True,
        ),
    )

    assert len(client.calls) == 5
    assert [call["model"] for call in client.calls[3:]] == [
        "qwen-vl-max",
        "qwen-vl-max",
    ]
    assert result.markdown == "# Exact board\n"
    slots = [dict(slot) for slot in result.metadata["workflow_slots"]]
    assert [(slot["slot_id"], slot["reused"]) for slot in slots] == [
        ("draft", True),
        ("standalone_sign_scout_1", True),
        ("standalone_sign_scout_2", False),
        ("standalone_sign_scout_3", False),
    ]
    assert slots[0]["model"] == "qwen3.7-plus-2026-05-26"
    assert slots[2]["model"] == "qwen-vl-max"
