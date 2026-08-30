from __future__ import annotations

import json
import hashlib
import importlib
import inspect
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from ocrllm import DashScopeSettings, RecognitionResult
from ocrllm.errors import RateLimited
from quality_lab.build_phase1_dispatch_plan import (
    CONFIRMED_PAID_CALL_COUNT,
    RECOGNITION_INVOCATION_COUNT,
    build_phase1_dispatch_plan,
)
from quality_lab.capture_quality_repository_identity import (
    QualityRepositoryIdentity,
)
from quality_lab.load_fixture_manifest import load_fixture_manifest
from quality_lab.run_phase1_quality import (
    Phase1QualityRunnerError,
    _run_phase1_quality_simulated,
    run_phase1_quality,
)


REGION = "ap-southeast-1"
BASE_URL = "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"
SECRET = "offline-runner-secret-sentinel"


def simulated_repository_identity(
    _repository_root: Path,
    relevant_paths: tuple[str, ...],
) -> QualityRepositoryIdentity:
    payload = "\n".join(relevant_paths).encode("utf-8")
    return QualityRepositoryIdentity(
        head_commit="0" * 40,
        relevant_index_sha256=hashlib.sha256(payload).hexdigest(),
        relevant_file_count=len(relevant_paths),
        relevant_tree_clean=True,
    )


class DeterministicClock:
    def __init__(self) -> None:
        self._utc = datetime(2026, 7, 11, tzinfo=timezone.utc)
        self._nanoseconds = 0

    def utc_now(self) -> datetime:
        self._utc += timedelta(milliseconds=1)
        return self._utc

    def monotonic_ns(self) -> int:
        self._nanoseconds += 1_000_000
        return self._nanoseconds


class FakeRecognizer:
    def __init__(
        self,
        *,
        failure_call=None,
        corrupt_call=None,
        leak_call=None,
        leak_base_url_call=None,
        reject_call=None,
        interrupt_call=None,
        checkpoint_observer=None,
        environment_to_rotate=None,
    ):
        self.failure_call = failure_call
        self.corrupt_call = corrupt_call
        self.leak_call = leak_call
        self.leak_base_url_call = leak_base_url_call
        self.reject_call = reject_call
        self.interrupt_call = interrupt_call
        self.checkpoint_observer = checkpoint_observer
        self.environment_to_rotate = environment_to_rotate
        self.calls = []
        self.config_ids = []
        self.manifest = load_fixture_manifest()
        self.fixture_by_filename = {
            Path(artifact.path).name: fixture.id
            for fixture in self.manifest.fixtures
            for artifact in self.manifest.artifacts
            if artifact.id == fixture.artifact_id
        }

    def __call__(self, source, *, config):
        call_index = len(self.calls)
        paths = (source,) if isinstance(source, Path) else tuple(source)
        fixture_ids = tuple(self.fixture_by_filename[path.name] for path in paths)
        self.calls.append((fixture_ids, config))
        self.config_ids.append(id(config))
        if self.checkpoint_observer is not None:
            self.checkpoint_observer(call_index)
        if self.environment_to_rotate is not None:
            self.environment_to_rotate["DASHSCOPE_API_KEY"] = "rotated-secret-sentinel"
        if call_index == self.interrupt_call:
            raise KeyboardInterrupt
        if call_index == self.failure_call:
            raise RateLimited(details={"provider": "dashscope", "http_status": 429})
        markdown = _dispatch_markdown(self.manifest, fixture_ids)
        if call_index == self.corrupt_call:
            markdown = markdown.replace("CHECKSUM: CN-7319", "CHECKSUM: CN-7318", 1)
        if call_index == self.leak_call:
            markdown += f"\n{SECRET}"
        if call_index == self.leak_base_url_call:
            markdown += f"\n{BASE_URL}"
        if call_index == self.reject_call:
            markdown += "\nF99: $x+y$"
        return RecognitionResult(
            markdown=markdown,
            source_type="image",
            profile="board",
            metadata={
                "image_count": len(paths),
                "model": config.vision_model.name,
                "prompt_version": "board.v17",
                "provider_call_count": (
                    config.preferences.draft_candidates
                    + config.preferences.review_passes
                    + 3
                ),
                "draft_candidates": config.preferences.draft_candidates,
                "review_passes": config.preferences.review_passes,
                "standalone_sign_scout_model": (
                    config.provider.standalone_sign_scout_model
                ),
                "standalone_sign_scout_count": 3,
                "standalone_sign_scout_enable_thinking": True,
                "standalone_signs_restored": 0,
                "standalone_sign_scout_abstention_count": 0,
                "standalone_sign_scout_prompt_version": "board-sign-omission.v1",
                "standalone_sign_scout_prompt_sha256": "a" * 64,
                "standalone_sign_scout_prompt_utf8_bytes": 1,
                "provider": "dashscope",
                "profile": "board",
                "provider_region": config.provider.region,
                "enable_thinking": config.provider.enable_thinking,
                "vl_high_resolution_images": (
                    config.provider.vl_high_resolution_images
                ),
            },
        )


def test_fake_runner_executes_exact_plan_with_fresh_configs_and_safe_evidence(
    tmp_path: Path,
) -> None:
    fake = FakeRecognizer()
    clock = DeterministicClock()
    evidence_path = tmp_path / "phase1-quality.json"

    evidence = _run_phase1_quality_simulated(
        region=REGION,
        base_url=BASE_URL,
        evidence_path=evidence_path,
        confirm_paid_calls=CONFIRMED_PAID_CALL_COUNT,
        environment={"DASHSCOPE_API_KEY": SECRET},
        recognize_callable=fake,
        utc_now=clock.utc_now,
        monotonic_ns=clock.monotonic_ns,
        repository_identity_callable=simulated_repository_identity,
    )

    manifest = load_fixture_manifest()
    expected_plan = build_phase1_dispatch_plan(manifest)
    assert len(fake.calls) == RECOGNITION_INVOCATION_COUNT
    assert tuple(call[0] for call in fake.calls) == tuple(
        entry.fixture_ids for entry in expected_plan
    )
    assert len(set(fake.config_ids)) == RECOGNITION_INVOCATION_COUNT
    for (fixture_ids, config), entry in zip(fake.calls, expected_plan, strict=True):
        expected_languages = tuple(
            dict.fromkeys(
                language
                for fixture_id in fixture_ids
                for fixture in manifest.fixtures
                if fixture.id == fixture_id
                for language in fixture.languages
            )
        )
        assert config.input_languages == expected_languages
        assert type(config.provider) is DashScopeSettings
        assert config.provider.api_key is None
        assert config.timeout_seconds == 180.0
        assert config.preferences.draft_candidates == 1
        assert config.preferences.review_passes == 0
        assert (
            config.provider.standalone_sign_scout_model
            == "qwen3.7-plus-2026-05-26"
        )
        assert entry.fixture_ids == fixture_ids

    assert evidence["state"] == "complete"
    assert evidence["active_attempt"] is None
    assert evidence["summary"]["recognize_invocations"] == 13
    assert evidence["summary"]["planned_provider_calls"] == 52
    assert evidence["summary"]["reported_provider_calls"] == 52
    assert evidence["summary"]["completed_full_runs"] == 2
    assert evidence["summary"]["passed_full_runs"] == 2
    assert evidence["summary"]["simulated_plan_passed"] is True
    assert evidence["summary"]["phase1_gate_passed"] is False
    assert tuple(inspect.signature(run_phase1_quality).parameters) == (
        "region",
        "base_url",
        "evidence_path",
        "confirm_paid_calls",
        "repository_root",
    )
    with pytest.raises(TypeError, match="unexpected keyword"):
        run_phase1_quality(
            region=REGION,
            base_url=BASE_URL,
            evidence_path=tmp_path / "public-injection.json",
            confirm_paid_calls=CONFIRMED_PAID_CALL_COUNT,
            recognize_callable=fake,  # type: ignore[call-arg]
        )
    assert evidence["execution"] == {
        "mode": "simulated",
        "injected_dependencies": [
            "environment",
            "recognize_callable",
            "utc_now",
            "monotonic_ns",
            "repository_identity_callable",
        ],
    }
    assert len(evidence["full_runs"][0]["dispatches"]) == 6
    assert len(evidence["full_runs"][1]["dispatches"]) == 6
    payload = evidence_path.read_text(encoding="utf-8")
    assert SECRET not in payload
    assert BASE_URL not in payload
    assert json.loads(payload) == evidence


def test_monkeypatching_mutable_dependency_globals_cannot_claim_live_evidence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runner_module = importlib.import_module("quality_lab.run_phase1_quality")
    fake = FakeRecognizer()
    monkeypatch.setattr(runner_module, "recognize", fake)
    monkeypatch.setattr(
        runner_module,
        "capture_quality_repository_identity",
        simulated_repository_identity,
    )

    evidence = _run(fake, tmp_path / "monkeypatched-dependencies.json")

    assert len(fake.calls) == 13
    assert evidence["execution"]["mode"] == "simulated"
    assert "recognize_callable" in evidence["execution"]["injected_dependencies"]
    assert evidence["summary"]["simulated_plan_passed"] is True
    assert evidence["summary"]["phase1_gate_passed"] is False


def test_provider_failure_aborts_after_one_invocation_without_retry(tmp_path: Path) -> None:
    evidence_path = tmp_path / "provider-failure.json"
    pre_call_checkpoints = []
    fake = FakeRecognizer(
        failure_call=0,
        checkpoint_observer=lambda _call: pre_call_checkpoints.append(
            json.loads(evidence_path.read_text(encoding="utf-8"))
        ),
    )

    evidence = _run(fake, evidence_path)

    assert len(fake.calls) == 1
    assert evidence["state"] == "aborted"
    assert evidence["summary"]["recognize_invocations"] == 1
    assert evidence["terminal_failure"]["stage"] == "provider"
    assert evidence["terminal_failure"]["code"] == "PROVIDER_RATE_LIMITED"
    assert evidence["request_contract"]["runner_retry_count"] == 0
    assert evidence["request_contract"]["sdk_retry_count"] == 0
    assert pre_call_checkpoints[0]["summary"]["recognize_invocations"] == 1
    assert pre_call_checkpoints[0]["active_attempt"]["attempt_index"] == 0


def test_gate_failure_is_recorded_but_both_full_runs_continue(tmp_path: Path) -> None:
    fake = FakeRecognizer(corrupt_call=1)

    evidence = _run(fake, tmp_path / "gate-failure.json")

    assert len(fake.calls) == 13
    assert evidence["state"] == "complete"
    assert evidence["full_runs"][0]["status"] == "complete"
    assert evidence["full_runs"][0]["passes"] is False
    assert evidence["full_runs"][1]["status"] == "complete"
    assert evidence["full_runs"][1]["passes"] is True
    assert evidence["summary"]["phase1_gate_passed"] is False
    failed = evidence["full_runs"][0]["dispatches"][0]
    assert failed["scorer"]["status"] == "gate_failed"
    assert failed["scorer"]["report"]["failure_codes"]


def test_credential_in_provider_output_is_never_persisted(tmp_path: Path) -> None:
    fake = FakeRecognizer(leak_call=0)
    evidence_path = tmp_path / "redacted.json"

    evidence = _run(fake, evidence_path)

    assert len(fake.calls) == 1
    assert evidence["state"] == "aborted"
    assert evidence["terminal_failure"]["stage"] == "result_contract"
    assert SECRET not in evidence_path.read_text(encoding="utf-8")


def test_base_url_in_provider_output_is_never_persisted(tmp_path: Path) -> None:
    fake = FakeRecognizer(leak_base_url_call=0)
    evidence_path = tmp_path / "base-url-redacted.json"

    evidence = _run(fake, evidence_path)

    assert len(fake.calls) == 1
    assert evidence["state"] == "aborted"
    assert evidence["terminal_failure"]["stage"] == "result_contract"
    assert BASE_URL not in evidence_path.read_text(encoding="utf-8")


def test_keyboard_interrupt_is_checkpointed_then_reraised(tmp_path: Path) -> None:
    fake = FakeRecognizer(interrupt_call=0)
    evidence_path = tmp_path / "interrupted.json"

    with pytest.raises(KeyboardInterrupt):
        _run(fake, evidence_path)

    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    assert len(fake.calls) == 1
    assert evidence["state"] == "aborted"
    assert evidence["active_attempt"] is None
    assert evidence["summary"]["recognize_invocations"] == 1
    assert evidence["terminal_failure"]["code"] == "RECOGNIZE_INTERRUPTED"


def test_smoke_scorer_rejection_cannot_pass_even_when_full_runs_pass(
    tmp_path: Path,
) -> None:
    fake = FakeRecognizer(reject_call=0)

    evidence = _run(fake, tmp_path / "smoke-rejected.json")

    assert len(fake.calls) == 13
    assert evidence["state"] == "complete"
    assert evidence["smoke"]["scorer"]["status"] == "rejected"
    assert evidence["summary"]["passed_full_runs"] == 2
    assert evidence["summary"]["simulated_plan_passed"] is False
    assert evidence["summary"]["phase1_gate_passed"] is False


def test_completed_run_summary_is_current_in_next_pre_call_checkpoint(
    tmp_path: Path,
) -> None:
    evidence_path = tmp_path / "current-summary.json"
    pre_call_checkpoints = []
    fake = FakeRecognizer(
        failure_call=7,
        checkpoint_observer=lambda call: (
            pre_call_checkpoints.append(
                json.loads(evidence_path.read_text(encoding="utf-8"))
            )
            if call == 7
            else None
        ),
    )

    _run(fake, evidence_path)

    checkpoint = pre_call_checkpoints[0]
    assert checkpoint["full_runs"][0]["status"] == "complete"
    assert checkpoint["summary"]["completed_full_runs"] == 1
    assert checkpoint["summary"]["passed_full_runs"] == 1
    assert checkpoint["summary"]["recognize_invocations"] == 8


def test_credential_rotation_aborts_after_one_call_without_disclosing_keys(
    tmp_path: Path,
) -> None:
    environment = {"DASHSCOPE_API_KEY": SECRET}
    fake = FakeRecognizer(environment_to_rotate=environment)
    evidence_path = tmp_path / "rotated-key.json"

    evidence = _run(fake, evidence_path, environment=environment)

    payload = evidence_path.read_text(encoding="utf-8")
    assert len(fake.calls) == 1
    assert evidence["state"] == "aborted"
    assert evidence["terminal_failure"]["stage"] == "credential"
    assert evidence["terminal_failure"]["code"] == "CREDENTIAL_CHANGED_DURING_CALL"
    assert SECRET not in payload
    assert "rotated-secret-sentinel" not in payload


def test_manifest_is_strictly_reloaded_before_first_call(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runner_module = importlib.import_module("quality_lab.run_phase1_quality")
    canonical_loader = runner_module.load_fixture_manifest
    load_count = 0

    def fail_second_load(path):
        nonlocal load_count
        load_count += 1
        if load_count == 2:
            raise ValueError("simulated manifest drift")
        return canonical_loader(path)

    fake = FakeRecognizer()
    monkeypatch.setattr(runner_module, "load_fixture_manifest", fail_second_load)
    evidence = _run(fake, tmp_path / "manifest-drift.json")

    assert load_count == 2
    assert fake.calls == []
    assert evidence["state"] == "aborted"
    assert evidence["terminal_failure"]["code"] == "PRECALL_IDENTITY_INVALID"


def test_post_call_io_failure_is_checkpointed_without_another_call(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runner_module = importlib.import_module("quality_lab.run_phase1_quality")
    canonical_verifier = runner_module._verify_dispatch_inputs
    verification_count = 0

    def fail_second_verification(paths, artifacts):
        nonlocal verification_count
        verification_count += 1
        if verification_count == 2:
            raise OSError("simulated post-call read failure")
        return canonical_verifier(paths, artifacts)

    monkeypatch.setattr(
        runner_module,
        "_verify_dispatch_inputs",
        fail_second_verification,
    )
    fake = FakeRecognizer()
    evidence = _run(fake, tmp_path / "post-call-io-failure.json")

    assert len(fake.calls) == 1
    assert evidence["state"] == "aborted"
    assert evidence["active_attempt"] is None
    assert evidence["terminal_failure"]["code"] == "POSTCALL_VERIFICATION_FAILED"


def test_report_serialization_failure_is_checkpointed_as_scorer_internal_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runner_module = importlib.import_module("quality_lab.run_phase1_quality")

    def fail_serialization(_report):
        raise RuntimeError("simulated serializer defect")

    monkeypatch.setattr(
        runner_module,
        "serialize_recognition_quality_report",
        fail_serialization,
    )
    fake = FakeRecognizer()
    evidence = _run(fake, tmp_path / "serializer-failure.json")

    assert len(fake.calls) == 1
    assert evidence["state"] == "aborted"
    assert evidence["smoke"]["scorer"]["status"] == "internal_failure"
    assert evidence["terminal_failure"]["code"] == "SCORER_INTERNAL_FAILURE"


def test_existing_evidence_and_wrong_confirmation_fail_before_recognition(
    tmp_path: Path,
) -> None:
    fake = FakeRecognizer()
    existing = tmp_path / "existing.json"
    existing.write_text("do not replace", encoding="utf-8")

    with pytest.raises(Phase1QualityRunnerError, match="must not already exist"):
        _run(fake, existing)
    with pytest.raises(Phase1QualityRunnerError, match="must equal 52"):
        clock = DeterministicClock()
        _run_phase1_quality_simulated(
            region=REGION,
            base_url=BASE_URL,
            evidence_path=tmp_path / "wrong-confirmation.json",
            confirm_paid_calls=25,
            environment={"DASHSCOPE_API_KEY": SECRET},
            recognize_callable=fake,
            utc_now=clock.utc_now,
            monotonic_ns=clock.monotonic_ns,
            repository_identity_callable=simulated_repository_identity,
        )
    assert fake.calls == []
    assert existing.read_text(encoding="utf-8") == "do not replace"


def _run(
    fake: FakeRecognizer,
    evidence_path: Path,
    *,
    environment: dict[str, str] | None = None,
):
    clock = DeterministicClock()
    source_environment = (
        {"DASHSCOPE_API_KEY": SECRET} if environment is None else environment
    )
    return _run_phase1_quality_simulated(
        region=REGION,
        base_url=BASE_URL,
        evidence_path=evidence_path,
        confirm_paid_calls=CONFIRMED_PAID_CALL_COUNT,
        environment=source_environment,
        recognize_callable=fake,
        utc_now=clock.utc_now,
        monotonic_ns=clock.monotonic_ns,
        repository_identity_callable=simulated_repository_identity,
    )


def _dispatch_markdown(manifest, fixture_ids):
    return "\n".join(_fixture_markdown(manifest, fixture_id) for fixture_id in fixture_ids)


def _fixture_markdown(manifest, fixture_id):
    fixture = next(item for item in manifest.fixtures if item.id == fixture_id)
    lines = [unit.text for unit in fixture.content_units]
    lines.extend(
        f"{formula.label}: ${formula.accepted_latex[0]}$"
        for formula in fixture.formulas
    )
    if fixture.table is not None:
        headers = [header.accepted[0] for header in fixture.table.headers]
        cells = {(cell.row, cell.column): cell for cell in fixture.table.cells}
        lines.extend(
            (
                "| " + " | ".join(headers) + " |",
                "| " + " | ".join("---" for _ in headers) + " |",
            )
        )
        lines.extend(
            "| "
            + " | ".join(
                cells[(row, column)].accepted[0]
                for column in range(fixture.table.column_count)
            )
            + " |"
            for row in range(fixture.table.row_count)
        )
    return "\n".join(lines)
