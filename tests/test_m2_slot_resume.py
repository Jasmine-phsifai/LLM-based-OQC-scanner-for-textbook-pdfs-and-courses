"""Kill-mid-request regression tests for slot-indexed resume (Stage M2)."""

from __future__ import annotations

import hashlib
import importlib
import json
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest

from ocrllm import (
    AllCandidatesExhausted,
    Config,
    DashScopeSettings,
    OutputError,
    ProviderError,
    QuotaExhausted,
    RecognitionPreferences,
    ResumeStateError,
    VisionModelSettings,
    recognize,
    recognize_batch,
)
from ocrllm.providers.vision_provider_response import VisionProviderResponse

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
    overwrite: bool = False,
) -> Config:
    return Config(
        provider=provider,
        output_dir=output_dir,
        preferences=RecognitionPreferences(draft_candidates=2, review_passes=1),
        resume=resume,
        overwrite=overwrite,
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


def test_batch_rejects_later_partial_state_with_existing_output_before_dispatch(
    tmp_path: Path,
) -> None:
    first = write_test_image(tmp_path / "first.png")
    later = write_test_image(tmp_path / "later.png")
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    later_output = output_dir / "later_board.md"
    later_output.write_text("previous published output", encoding="utf-8")
    seed_provider = InterruptibleSlotProvider(fail_after=1)

    with pytest.raises(ProviderError):
        recognize(
            later,
            config=_slot_config(
                seed_provider,
                output_dir,
                overwrite=True,
            ),
        )

    state_path = output_dir / "later_board.ocrllm-state.json"
    state_before = state_path.read_bytes()
    state = _state_document(output_dir, "later_board")
    assert [slot["slot_id"] for slot in state["slots"]] == ["draft"]
    assert state["result"]["markdown"] == ""
    batch_provider = InterruptibleSlotProvider()

    with pytest.raises(ResumeStateError) as captured:
        recognize_batch(
            (first, later),
            config=_slot_config(
                batch_provider,
                output_dir,
                resume=True,
            ),
        )

    assert captured.value.code == "RESUME_STATE_MISMATCH"
    assert batch_provider.calls == []
    assert not (output_dir / "first_board.md").exists()
    assert not (output_dir / "first_board.ocrllm-state.json").exists()
    assert later_output.read_text(encoding="utf-8") == "previous published output"
    assert state_path.read_bytes() == state_before


def test_review_checkpoint_failure_reports_spend_and_keeps_prior_slots(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = write_test_image(tmp_path / "board.png")
    output_dir = tmp_path / "output"
    provider = InterruptibleSlotProvider()
    saver = importlib.import_module("ocrllm.output.save_image_resume_state_atomically")
    real_replace = saver.os.replace
    replace_count = 0

    def fail_review_checkpoint_replace(source_path, destination_path):
        nonlocal replace_count
        replace_count += 1
        if replace_count == 3:
            raise OSError("test-only review checkpoint replace failure")
        return real_replace(source_path, destination_path)

    monkeypatch.setattr(saver.os, "replace", fail_review_checkpoint_replace)

    with pytest.raises(OutputError) as captured:
        recognize(source, config=_slot_config(provider, output_dir))

    assert captured.value.code == "OUTPUT_WRITE_FAILED"
    assert captured.value.details["workflow_pass"] == "consensus_review"
    assert captured.value.details["provider_calls_attempted"] == 3
    assert len(provider.calls) == 3
    assert not (output_dir / "board_board.md").exists()
    partial_state = _state_document(output_dir)
    assert [slot["slot_id"] for slot in partial_state["slots"]] == [
        "draft",
        "draft_2",
    ]
    assert list(output_dir.glob(".*.tmp")) == []


def test_interrupted_overwrite_resume_rejects_old_output_before_provider_call(
    tmp_path: Path,
) -> None:
    source = write_test_image(tmp_path / "board.png")
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    output_path = output_dir / "board_board.md"
    output_path.write_text("previous published output", encoding="utf-8")
    provider = InterruptibleSlotProvider(fail_after=2)

    with pytest.raises(ProviderError):
        recognize(
            source,
            config=_slot_config(provider, output_dir, overwrite=True),
        )

    state_path = output_dir / "board_board.ocrllm-state.json"
    partial_state = state_path.read_bytes()
    calls_before_resume = len(provider.calls)
    provider.fail_after = None

    with pytest.raises(ResumeStateError) as captured:
        recognize(
            source,
            config=_slot_config(provider, output_dir, resume=True),
        )

    assert captured.value.code == "RESUME_STATE_MISMATCH"
    assert len(provider.calls) == calls_before_resume
    assert output_path.read_text(encoding="utf-8") == "previous published output"
    assert state_path.read_bytes() == partial_state


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
            raise QuotaExhausted(
                "per-model quota spent",
                details={"failure_scope": "model"},
            )
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
            preferences=RecognitionPreferences(
                draft_candidates=1,
                review_passes=1,
            ),
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
    assert [
        (slot["slot_id"], slot["model"]) for slot in persisted["slots"]
    ] == [
        ("draft", "quota-model"),
        ("draft", "recovery-model"),
        ("review", "recovery-model"),
    ]


def test_fallback_preserves_settled_token_usage_from_every_model(
    tmp_path: Path,
) -> None:
    source = write_test_image(tmp_path / "board.png")
    output_dir = tmp_path / "output"

    class Provider:
        resume_identity = "m2-token-fallback-provider-v1"

        def __init__(self) -> None:
            self.calls: list[str] = []

        def recognize_images(self, image_paths, *, prompt, config):
            model = config.vision_model.name
            self.calls.append(model)
            if model == "model-a" and self.calls.count(model) == 2:
                raise QuotaExhausted(
                    "per-model quota spent",
                    details={"failure_scope": "model"},
                )
            input_tokens, output_tokens = (
                (10, 2) if model == "model-a" else (3, 1)
            )
            return VisionProviderResponse(
                markdown=f"# {model} response {self.calls.count(model)}\n",
                input_tokens=input_tokens,
                output_tokens=output_tokens,
            )

    provider = Provider()
    result = recognize(
        source,
        config=Config(
            provider=provider,
            output_dir=output_dir,
            vision_model=VisionModelSettings(
                name="model-a",
                candidate_models=("model-b",),
            ),
            preferences=RecognitionPreferences(draft_candidates=1, review_passes=1),
        ),
    )

    assert provider.calls == ["model-a", "model-a", "model-b", "model-b"]
    assert result.metadata["current_run_provider_call_count"] == 4
    assert tuple(
        dict(usage) for usage in result.metadata["current_model_token_usage"]
    ) == (
        {"model": "model-a", "input_tokens": 10, "output_tokens": 2},
        {"model": "model-b", "input_tokens": 6, "output_tokens": 2},
    )


def test_exhausted_fallback_preserves_settled_token_usage_from_every_model(
    tmp_path: Path,
) -> None:
    source = write_test_image(tmp_path / "board.png")

    class Provider:
        resume_identity = "m2-token-exhaustion-provider-v1"

        def __init__(self) -> None:
            self.calls: list[str] = []

        def recognize_images(self, image_paths, *, prompt, config):
            model = config.vision_model.name
            self.calls.append(model)
            if self.calls.count(model) == 2:
                raise QuotaExhausted(
                    "per-model quota spent",
                    details={"failure_scope": "model"},
                )
            input_tokens, output_tokens = (
                (10, 2) if model == "model-a" else (3, 1)
            )
            return VisionProviderResponse(
                markdown=f"# {model} draft\n",
                input_tokens=input_tokens,
                output_tokens=output_tokens,
            )

    provider = Provider()
    with pytest.raises(AllCandidatesExhausted) as captured:
        recognize(
            source,
            config=Config(
                provider=provider,
                vision_model=VisionModelSettings(
                    name="model-a",
                    candidate_models=("model-b",),
                ),
                preferences=RecognitionPreferences(
                    draft_candidates=1,
                    review_passes=1,
                ),
            ),
        )

    assert provider.calls == ["model-a", "model-a", "model-b", "model-b"]
    assert captured.value.details["provider_calls_attempted"] == 4
    assert tuple(
        dict(usage) for usage in captured.value.details["settled_model_usage"]
    ) == (
        {
            "model": "model-a",
            "input_count": 10,
            "output_count": 2,
            "unit": "tokens",
        },
        {
            "model": "model-b",
            "input_count": 3,
            "output_count": 1,
            "unit": "tokens",
        },
    )


def test_fallback_checkpoint_failure_counts_every_model_attempt(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = write_test_image(tmp_path / "board.png")
    output_dir = tmp_path / "output"
    provider = _ModelAwareProvider(quota_model="quota-model")
    saver = importlib.import_module("ocrllm.output.save_image_resume_state_atomically")
    real_replace = saver.os.replace
    replace_count = 0

    def fail_recovery_draft_checkpoint(source_path, destination_path):
        nonlocal replace_count
        replace_count += 1
        if replace_count == 2:
            raise OSError("test-only recovery checkpoint failure")
        return real_replace(source_path, destination_path)

    monkeypatch.setattr(saver.os, "replace", fail_recovery_draft_checkpoint)

    with pytest.raises(OutputError) as captured:
        recognize(
            source,
            config=Config(
                provider=provider,
                output_dir=output_dir,
                vision_model=VisionModelSettings(
                    name="quota-model",
                    candidate_models=("recovery-model",),
                ),
                preferences=RecognitionPreferences(
                    draft_candidates=1,
                    review_passes=1,
                ),
            ),
        )

    assert captured.value.code == "OUTPUT_WRITE_FAILED"
    assert captured.value.details["workflow_pass"] == "draft"
    assert captured.value.details["provider_calls_attempted"] == 3
    assert [
        dict(attempt) for attempt in captured.value.details["model_attempts"]
    ] == [
        {
            "model": "quota-model",
            "outcome": "PROVIDER_QUOTA_EXHAUSTED",
            "disposition": "stop",
            "provider_calls_attempted": 2,
        },
        {
            "model": "recovery-model",
            "outcome": "OUTPUT_WRITE_FAILED",
            "provider_calls_attempted": 1,
        },
    ]
    assert provider.calls == [
        "quota-model",
        "quota-model",
        "recovery-model",
    ]
    assert not (output_dir / "board_board.md").exists()
    partial_state = _state_document(output_dir)
    assert [slot["slot_id"] for slot in partial_state["slots"]] == ["draft"]
    assert {slot["model"] for slot in partial_state["slots"]} == {"quota-model"}
    assert list(output_dir.glob(".*.tmp")) == []


def test_completed_state_failure_counts_calls_across_model_fallback(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = write_test_image(tmp_path / "board.png")
    output_dir = tmp_path / "output"
    provider = _ModelAwareProvider(quota_model="quota-model")
    saver = importlib.import_module("ocrllm.output.save_image_resume_state_atomically")
    real_serialize = saver.serialize_image_resume_state

    def limit_after_each_partial_state(state):
        raw = real_serialize(state)
        if not state.markdown:
            monkeypatch.setattr(saver, "_MAX_STATE_BYTES", len(raw) + 1)
        return raw

    monkeypatch.setattr(
        saver,
        "serialize_image_resume_state",
        limit_after_each_partial_state,
    )

    with pytest.raises(OutputError) as captured:
        recognize(
            source,
            config=Config(
                provider=provider,
                output_dir=output_dir,
                vision_model=VisionModelSettings(
                    name="quota-model",
                    candidate_models=("recovery-model",),
                ),
                preferences=RecognitionPreferences(
                    draft_candidates=1,
                    review_passes=1,
                ),
            ),
        )

    assert captured.value.code == "OUTPUT_WRITE_FAILED"
    assert captured.value.details["provider_calls_attempted"] == 4
    assert "workflow_pass" not in captured.value.details
    assert provider.calls == [
        "quota-model",
        "quota-model",
        "recovery-model",
        "recovery-model",
    ]
    assert not (output_dir / "board_board.md").exists()
    partial_state = _state_document(output_dir)
    assert [
        (slot["slot_id"], slot["model"]) for slot in partial_state["slots"]
    ] == [
        ("draft", "quota-model"),
        ("draft", "recovery-model"),
        ("review", "recovery-model"),
    ]
    assert list(output_dir.glob(".*.tmp")) == []


def test_completed_state_failure_preserves_paid_slots_from_every_model_for_resume(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = write_test_image(tmp_path / "board.png")
    output_dir = tmp_path / "output"

    class Provider:
        resume_identity = "m2-qualified-model-slot-provider-v1"

        def __init__(self) -> None:
            self.calls: list[tuple[str, str]] = []

        def recognize_images(self, image_paths, *, prompt, config):
            model = config.vision_model.name
            workflow_pass = (
                "review" if "BEGIN FALLIBLE DRAFT DATA" in prompt else "draft"
            )
            self.calls.append((model, workflow_pass))
            if model == "model-a" and workflow_pass == "review":
                raise QuotaExhausted(
                    "per-model quota spent",
                    details={"failure_scope": "model"},
                )
            return f"# {model} {workflow_pass}\n"

    provider = Provider()
    config = Config(
        provider=provider,
        output_dir=output_dir,
        vision_model=VisionModelSettings(
            name="model-a",
            candidate_models=("model-b",),
        ),
        preferences=RecognitionPreferences(draft_candidates=1, review_passes=1),
    )
    saver = importlib.import_module("ocrllm.output.save_image_resume_state_atomically")
    real_save = saver.save_image_resume_state_atomically

    def fail_completed_state(state_path, state):
        if state.markdown:
            raise OutputError(
                "test-only completed-state failure",
                code="OUTPUT_WRITE_FAILED",
            )
        return real_save(state_path, state)

    monkeypatch.setattr(
        saver,
        "save_image_resume_state_atomically",
        fail_completed_state,
    )

    with pytest.raises(OutputError) as captured:
        recognize(source, config=config)

    assert captured.value.code == "OUTPUT_WRITE_FAILED"
    assert provider.calls == [
        ("model-a", "draft"),
        ("model-a", "review"),
        ("model-b", "draft"),
        ("model-b", "review"),
    ]
    partial_state = _state_document(output_dir)
    assert [
        (slot["slot_id"], slot["model"]) for slot in partial_state["slots"]
    ] == [
        ("draft", "model-a"),
        ("draft", "model-b"),
        ("review", "model-b"),
    ]

    calls_before_resume = tuple(provider.calls)
    monkeypatch.setattr(
        saver,
        "save_image_resume_state_atomically",
        real_save,
    )
    result = recognize(source, config=replace(config, resume=True))

    assert provider.calls == [*calls_before_resume, ("model-a", "review")]
    assert result.markdown == "# model-b review\n"
    assert result.metadata["current_run_provider_call_count"] == 1
    assert [dict(attempt) for attempt in result.metadata["model_attempts"]] == [
        {
            "model": "model-a",
            "outcome": "PROVIDER_QUOTA_EXHAUSTED",
            "disposition": "stop",
            "provider_calls_attempted": 1,
        },
        {
            "model": "model-b",
            "outcome": "success",
            "provider_calls_attempted": 0,
        },
    ]
    assert [
        (slot["slot_id"], slot["model"], slot["reused"])
        for slot in result.metadata["workflow_slots"]
    ] == [
        ("draft", "model-b", True),
        ("review", "model-b", True),
    ]
    completed_state = _state_document(output_dir)
    assert [
        (slot["slot_id"], slot["model"]) for slot in completed_state["slots"]
    ] == [
        ("draft", "model-a"),
        ("draft", "model-b"),
        ("review", "model-b"),
    ]


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
