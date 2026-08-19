from __future__ import annotations

import importlib
from pathlib import Path

import pytest

from ocrllm import AllCandidatesExhausted, Config, RecognitionExecutionPolicy, VisionModelSettings, recognize, recognize_batch
from ocrllm.errors import ProviderError, QuotaExhausted
from ocrllm.providers.dashscope.provider_settings import DashScopeSettings
from ocrllm.providers.dashscope.resolve_dashscope_model import resolve_dashscope_model

from write_test_image import write_test_image


def _settings() -> DashScopeSettings:
    return DashScopeSettings(
        region="cn-beijing",
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        api_key="test-key",
    )


def test_dashscope_accepts_a_model_from_the_provider_catalog(monkeypatch) -> None:
    resolver = importlib.import_module(
        "ocrllm.providers.dashscope.resolve_dashscope_model"
    )
    monkeypatch.setattr(
        resolver,
        "fetch_dashscope_model_catalog",
        lambda settings: frozenset({"model-served-only-by-provider"}),
    )

    assert (
        resolve_dashscope_model(
            "model-served-only-by-provider",
            settings=_settings(),
        )
        == "model-served-only-by-provider"
    )


class _InterruptibleProvider:
    resume_identity = "stage-m-provider-v1"

    def __init__(self) -> None:
        self.calls: list[str] = []
        self.fail_second_call = True

    def recognize_images(self, image_paths, *, prompt, config):
        name = image_paths[0].name
        self.calls.append(name)
        if name == "second.png" and self.fail_second_call:
            raise ProviderError("temporary failure", code="PROVIDER_UNAVAILABLE")
        return f"# {name}\n"


def test_batch_preserves_completed_units_and_resume_reuses_them(
    tmp_path: Path,
) -> None:
    sources = [
        write_test_image(tmp_path / "first.png"),
        write_test_image(tmp_path / "second.png"),
    ]
    output_dir = tmp_path / "output"
    provider = _InterruptibleProvider()
    config = Config(
        provider=provider,
        output_dir=output_dir,
        execution=RecognitionExecutionPolicy(max_parallel_requests=1),
    )

    outcomes = recognize_batch(sources, config=config)

    assert outcomes[0].result is not None
    assert outcomes[1].error is not None
    first_output = outcomes[0].result.output_path
    assert first_output is not None and first_output.is_file()
    assert first_output.with_name(
        f"{first_output.stem}.ocrllm-state.json"
    ).is_file()

    provider.fail_second_call = False
    resumed = recognize_batch(
        sources,
        config=Config(
            provider=provider,
            output_dir=output_dir,
            resume=True,
            execution=RecognitionExecutionPolicy(max_parallel_requests=1),
        ),
    )

    assert [outcome.result.markdown for outcome in resumed] == [
        "# first.png\n",
        "# second.png\n",
    ]
    assert provider.calls == ["first.png", "second.png", "second.png"]


class _CandidateProvider:
    resume_identity = "candidate-provider-v1"

    def __init__(self, *, recover: bool = True) -> None:
        self.models: list[str | None] = []
        self.recover = recover

    def recognize_images(self, image_paths, *, prompt, config):
        model = config.vision_model.name
        self.models.append(model)
        if model == "quota-model" or not self.recover:
            raise QuotaExhausted(
                "model quota exhausted",
                details={"failure_scope": "model"},
            )
        return "# Recovered\n"


def test_candidate_chain_switches_only_on_model_quota_and_reports_ledger(tmp_path):
    source = write_test_image(tmp_path / "board.png")
    provider = _CandidateProvider()

    result = recognize(
        source,
        config=Config(
            provider=provider,
            vision_model=VisionModelSettings(
                name="quota-model",
                candidate_models=("quota-model", "recovery-model"),
            ),
        ),
    )

    assert provider.models == ["quota-model", "recovery-model"]
    assert result.metadata["model"] == "recovery-model"
    assert result.metadata["model_evidence"] == "unproven"
    assert result.metadata["model_proven"] is False
    assert [dict(attempt) for attempt in result.metadata["model_attempts"]] == [
        {
            "model": "quota-model",
            "outcome": "PROVIDER_QUOTA_EXHAUSTED",
            "disposition": "stop",
        },
        {"model": "recovery-model", "outcome": "success"},
    ]


def test_candidate_chain_raises_after_the_last_model_and_names_it(tmp_path):
    source = write_test_image(tmp_path / "board.png")
    provider = _CandidateProvider(recover=False)

    with pytest.raises(AllCandidatesExhausted) as captured:
        recognize(
            source,
            config=Config(
                provider=provider,
                vision_model=VisionModelSettings(
                    name="quota-model",
                    candidate_models=("quota-model", "last-model"),
                ),
            ),
        )

    assert provider.models == ["quota-model", "last-model"]
    assert captured.value.details["all_candidates_exhausted"] is True
    assert captured.value.details["last_model"] == "last-model"