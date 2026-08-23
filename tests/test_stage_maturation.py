from __future__ import annotations

import importlib
from pathlib import Path

import pytest

from ocrllm import AllCandidatesExhausted, Config, RecognitionExecutionPolicy, VisionModelSettings, recognize, recognize_batch
from ocrllm.errors import (
    ConfigError,
    ProviderError,
    ProviderPermissionDenied,
    ProviderUnavailable,
    QuotaExhausted,
)
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


def test_candidate_chain_advances_on_quota_and_reports_ledger(tmp_path):
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
            "provider_calls_attempted": 1,
        },
        {"model": "recovery-model", "outcome": "success", "provider_calls_attempted": 1},
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
    assert captured.value.details["provider_calls_attempted"] == 2
    assert captured.value.code == "ALL_CANDIDATES_EXHAUSTED"
    assert not isinstance(captured.value, QuotaExhausted)


def test_all_candidates_exhausted_has_distinct_code_and_disposition() -> None:
    from ocrllm import get_provider_error_disposition

    error = AllCandidatesExhausted()

    assert error.code == "ALL_CANDIDATES_EXHAUSTED"
    assert error.retryable is False
    disposition = get_provider_error_disposition(error)
    assert (disposition.action, disposition.scope) == ("stop", "account")


def test_unpinned_former_static_set_model_reports_unproven_evidence(tmp_path):
    source = write_test_image(tmp_path / "board.png")
    provider = _CandidateProvider()

    result = recognize(
        source,
        config=Config(
            provider=provider,
            vision_model=VisionModelSettings(name="qwen3.7-plus"),
        ),
    )

    assert result.metadata["model"] == "qwen3.7-plus"
    assert result.metadata["model_evidence"] == "unproven"
    assert result.metadata["model_proven"] is False


class _DispositionProvider:
    resume_identity = "disposition-provider-v1"

    def __init__(self, failures: dict[str, object]) -> None:
        self.models: list[str | None] = []
        self._failures = failures

    def recognize_images(self, image_paths, *, prompt, config):
        model = config.vision_model.name
        self.models.append(model)
        failure = self._failures.get(model)
        if failure is not None:
            raise failure
        return "# Served\n"


def test_candidate_chain_advances_on_permission_denied_and_unavailable(tmp_path):
    source = write_test_image(tmp_path / "board.png")
    provider = _DispositionProvider(
        {
            "denied-model": ProviderPermissionDenied(
                "model lacks permission",
                details={"failure_scope": "model"},
            ),
            "down-model": ProviderUnavailable(
                "model unavailable",
                details={"failure_scope": "model"},
            ),
        }
    )

    result = recognize(
        source,
        config=Config(
            provider=provider,
            vision_model=VisionModelSettings(
                name="denied-model",
                candidate_models=("denied-model", "down-model", "serving-model"),
            ),
        ),
    )

    assert provider.models == ["denied-model", "down-model", "serving-model"]
    assert result.metadata["model"] == "serving-model"
    attempts = [dict(attempt) for attempt in result.metadata["model_attempts"]]
    assert [attempt["outcome"] for attempt in attempts] == [
        "PROVIDER_PERMISSION_DENIED",
        "PROVIDER_UNAVAILABLE",
        "success",
    ]
    assert [attempt["disposition"] for attempt in attempts[:2]] == [
        "quarantine_credential",
        "retry",
    ]


def test_candidate_chain_does_not_advance_on_authentication_failure(tmp_path):
    source = write_test_image(tmp_path / "board.png")
    provider = _DispositionProvider(
        {"bad-key-model": ProviderError("bad key", code="PROVIDER_AUTHENTICATION")}
    )

    with pytest.raises(ProviderError) as captured:
        recognize(
            source,
            config=Config(
                provider=provider,
                vision_model=VisionModelSettings(
                    name="bad-key-model",
                    candidate_models=("bad-key-model", "never-tried-model"),
                ),
            ),
        )

    assert captured.value.code == "PROVIDER_AUTHENTICATION"
    assert provider.models == ["bad-key-model"]


def test_candidate_chain_does_not_advance_on_credential_permission_denial(tmp_path):
    source = write_test_image(tmp_path / "board.png")
    provider = _DispositionProvider(
        {
            "denied-model": ProviderPermissionDenied(
                "credential lacks permission",
                details={"failure_scope": "credential"},
            )
        }
    )

    with pytest.raises(ProviderPermissionDenied) as captured:
        recognize(
            source,
            config=Config(
                provider=provider,
                vision_model=VisionModelSettings(
                    name="denied-model",
                    candidate_models=("denied-model", "never-tried-model"),
                ),
            ),
        )

    assert captured.value.details["failure_scope"] == "credential"
    assert provider.models == ["denied-model"]


@pytest.mark.parametrize(
    ("failure", "expected_code", "expected_disposition"),
    [
        (
            QuotaExhausted(
                "account quota exhausted",
                details={"failure_scope": "account"},
            ),
            "PROVIDER_QUOTA_EXHAUSTED",
            "stop",
        ),
        (
            ProviderUnavailable(
                "provider service unavailable",
                details={"failure_scope": "provider"},
            ),
            "PROVIDER_UNAVAILABLE",
            "retry",
        ),
    ],
)
def test_candidate_chain_does_not_change_models_for_non_model_failure_scope(
    tmp_path,
    failure,
    expected_code,
    expected_disposition,
):
    source = write_test_image(tmp_path / "board.png")
    provider = _DispositionProvider({"first-model": failure})

    with pytest.raises(ProviderError) as captured:
        recognize(
            source,
            config=Config(
                provider=provider,
                vision_model=VisionModelSettings(
                    name="first-model",
                    candidate_models=("never-tried-model",),
                ),
            ),
        )

    assert type(captured.value) is type(failure)
    assert captured.value.code == expected_code
    assert (
        captured.value.details["failure_scope"]
        == failure.details["failure_scope"]
    )
    assert captured.value.details["failed_model"] == "first-model"
    assert provider.models == ["first-model"]
    assert [dict(attempt) for attempt in captured.value.details["model_attempts"]] == [
        {
            "model": "first-model",
            "outcome": expected_code,
            "disposition": expected_disposition,
            "provider_calls_attempted": 1,
        }
    ]


def test_single_model_failure_keeps_its_original_public_identity(tmp_path):
    source = write_test_image(tmp_path / "board.png")
    provider = _DispositionProvider(
        {"only-model": ProviderUnavailable("service unavailable")}
    )

    with pytest.raises(ProviderUnavailable) as captured:
        recognize(
            source,
            config=Config(
                provider=provider,
                vision_model=VisionModelSettings(name="only-model"),
            ),
        )

    assert captured.value.code == "PROVIDER_UNAVAILABLE"
    assert provider.models == ["only-model"]


def test_chain_exhaustion_wraps_an_advance_eligible_last_failure(tmp_path):
    from ocrllm import get_provider_error_disposition

    source = write_test_image(tmp_path / "board.png")
    provider = _DispositionProvider(
        {
            "quota-model": QuotaExhausted(
                "model quota exhausted",
                details={"failure_scope": "model"},
            ),
            "denied-model": ProviderPermissionDenied(
                "model lacks permission",
                details={"failure_scope": "model"},
            ),
        }
    )

    with pytest.raises(AllCandidatesExhausted) as captured:
        recognize(
            source,
            config=Config(
                provider=provider,
                vision_model=VisionModelSettings(
                    name="quota-model",
                    candidate_models=("quota-model", "denied-model"),
                ),
            ),
        )

    assert captured.value.code == "ALL_CANDIDATES_EXHAUSTED"
    assert captured.value.details["last_model"] == "denied-model"
    assert "failure_scope" not in captured.value.details
    assert get_provider_error_disposition(captured.value).scope == "account"


def test_configuration_failure_is_recorded_in_the_attempt_ledger(tmp_path, monkeypatch):
    resolver = importlib.import_module(
        "ocrllm.providers.dashscope.resolve_dashscope_model"
    )
    monkeypatch.setattr(
        resolver,
        "fetch_dashscope_model_catalog",
        lambda settings: frozenset(),
    )
    source = write_test_image(tmp_path / "board.png")
    config = Config(
        provider=_settings(),
        vision_model=VisionModelSettings(
            name="typo-model",
            candidate_models=("typo-model",),
        ),
    )

    with pytest.raises(ConfigError, match="DashScope does not serve") as captured:
        recognize(source, config=config)

    attempts = [
        dict(attempt) for attempt in captured.value.details["model_attempts"]
    ]
    assert attempts == [
        {
            "model": None,
            "outcome": "CONFIG_INVALID",
            "disposition": "fix_request",
            "provider_calls_attempted": 0,
        }
    ]


def test_candidate_chain_counts_prior_spend_before_configuration_failure(
    tmp_path,
    monkeypatch,
) -> None:
    processor = importlib.import_module("ocrllm.processors.recognize_images")
    real_resolve = processor.resolve_vision_provider

    def reject_recovery_model(config):
        if config.vision_model.name == "invalid-recovery-model":
            raise ConfigError("test-only recovery model configuration failure")
        return real_resolve(config)

    monkeypatch.setattr(processor, "resolve_vision_provider", reject_recovery_model)
    source = write_test_image(tmp_path / "board.png")
    provider = _CandidateProvider()

    with pytest.raises(ConfigError) as captured:
        recognize(
            source,
            config=Config(
                provider=provider,
                vision_model=VisionModelSettings(
                    name="quota-model",
                    candidate_models=("invalid-recovery-model",),
                ),
            ),
        )

    assert captured.value.details["provider_calls_attempted"] == 1
    assert [
        dict(attempt) for attempt in captured.value.details["model_attempts"]
    ] == [
        {
            "model": "quota-model",
            "outcome": "PROVIDER_QUOTA_EXHAUSTED",
            "disposition": "stop",
            "provider_calls_attempted": 1,
        },
        {
            "model": None,
            "outcome": "CONFIG_INVALID",
            "disposition": "fix_request",
            "provider_calls_attempted": 0,
        },
    ]
    assert provider.models == ["quota-model"]
