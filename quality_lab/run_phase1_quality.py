"""Execute the frozen Phase 1 smoke and two full quality runs."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
import platform
import sys
import time
from collections.abc import Callable, Mapping, Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ocrllm import (
    Config,
    DashScopeSettings,
    OCRLLMError,
    RecognitionResult,
    RecognitionPreferences,
    VisionModelSettings,
    __version__ as OCRLLM_VERSION,
    recognize,
)
from ocrllm.profiles.build_board_prompt import build_board_prompt
from ocrllm.profiles.build_board_sign_scout_prompt import (
    SIGN_SCOUT_PROMPT_VERSION,
    build_board_sign_scout_prompt_template,
)
from ocrllm.profiles.build_board_symbol_audit_prompt import (
    build_board_symbol_audit_prompt,
)
from ocrllm.providers.dashscope.build_dashscope_image_request import (
    MAX_COMPLETION_TOKENS,
)

from quality_lab.build_phase1_dispatch_plan import (
    CONFIRMED_PAID_CALL_COUNT,
    PROVIDER_CALLS_PER_RECOGNITION,
    RECOGNITION_INVOCATION_COUNT,
    Phase1DispatchPlanEntry,
    build_phase1_dispatch_plan,
)
from quality_lab.capture_quality_repository_identity import (
    QualityRepositoryIdentity,
    capture_quality_repository_identity,
)
from quality_lab.fixture_manifest import (
    ArtifactRecord,
    FixtureRecord,
    Phase1FixtureManifest,
)
from quality_lab.hash_quality_bundle import (
    Phase1CodeIdentity,
    QualityCodeBundle,
    hash_quality_bundle,
)
from quality_lab.load_fixture_manifest import load_fixture_manifest
from quality_lab.score_recognition_result import score_recognition_result
from quality_lab.serialize_recognition_quality_report import (
    serialize_recognition_quality_report,
)
from quality_lab.validate_phase1_recognition_result import (
    validate_phase1_recognition_result,
)
from quality_lab.verify_quality_import_origins import (
    QualityImportOrigins,
    verify_quality_import_origins,
)
from quality_lab.verify_fixture_artifacts import verify_fixture_artifacts
from quality_lab.write_quality_evidence_atomically import (
    QualityEvidenceWriteError,
    write_quality_evidence_atomically,
)


DEFAULT_REPOSITORY_ROOT = Path(__file__).parents[1]
PHASE1_TIMEOUT_SECONDS = 180.0
_TEMPERATURE = 0
_SCHEMA_VERSION = "ocrllm.phase1-quality-evidence.v17"
_MANIFEST_RELATIVE_PATH = "quality_lab/fixtures/phase1/manifest.json"
_BOUND_OUTPUT_ROOTS = (
    "src/ocrllm",
    "quality_lab",
)


class Phase1QualityRunnerError(RuntimeError):
    """The live runner could not safely start or preserve its evidence."""


def _run_phase1_quality_engine(
    *,
    region: str,
    base_url: str,
    evidence_path: str | Path,
    confirm_paid_calls: int,
    repository_root: str | Path,
    execution_mode: str,
    injected_dependencies: tuple[str, ...],
    environment: Mapping[str, str],
    recognize_callable: Callable[..., RecognitionResult],
    utc_now: Callable[[], datetime],
    monotonic_ns: Callable[[], int],
    repository_identity_callable: Callable[..., QualityRepositoryIdentity],
) -> dict[str, object]:
    """Run exactly 13 synchronous invocations and checkpoint all outcomes."""

    if type(confirm_paid_calls) is not int or confirm_paid_calls != CONFIRMED_PAID_CALL_COUNT:
        raise Phase1QualityRunnerError(
            f"--confirm-paid-calls must equal {CONFIRMED_PAID_CALL_COUNT}"
        )
    if not callable(recognize_callable):
        raise TypeError("recognize_callable must be callable")
    if not callable(repository_identity_callable):
        raise TypeError("repository_identity_callable must be callable")
    if not callable(utc_now) or not callable(monotonic_ns):
        raise TypeError("clock dependencies must be callable")
    if execution_mode not in {"live", "simulated"}:
        raise ValueError("execution_mode must be live or simulated")
    if type(injected_dependencies) is not tuple or any(
        type(value) is not str or not value for value in injected_dependencies
    ):
        raise TypeError("injected_dependencies must be an exact text tuple")
    if execution_mode == "live" and injected_dependencies:
        raise Phase1QualityRunnerError("live execution cannot declare test dependencies")
    if execution_mode == "simulated" and not injected_dependencies:
        raise Phase1QualityRunnerError("simulated execution must declare test dependencies")

    unresolved_root = Path(repository_root)
    if unresolved_root.is_symlink() or not unresolved_root.is_dir():
        raise Phase1QualityRunnerError("repository_root must be a real directory")
    root = unresolved_root.resolve(strict=True)
    import_origins = verify_quality_import_origins(root, runner_file=__file__)
    target = Path(evidence_path)
    _require_safe_new_evidence_path(root, target)
    source_environment = environment
    credential = _require_environment_credential(source_environment)
    settings = DashScopeSettings(region=region, base_url=base_url)
    manifest = load_fixture_manifest(root / _MANIFEST_RELATIVE_PATH)
    verify_fixture_artifacts(manifest, repository_root=root)
    plan = build_phase1_dispatch_plan(manifest)
    code_identity = hash_quality_bundle(root)
    relevant_paths = _relevant_repository_paths(manifest, code_identity)
    repository_identity = _capture_repository_identity(
        root,
        relevant_paths,
        repository_identity_callable,
    )
    plan_records = [_serialize_plan_entry(entry) for entry in plan]
    evidence = _initial_evidence(
        manifest=manifest,
        plan_records=plan_records,
        code_identity=code_identity,
        repository_identity=repository_identity,
        import_origins=import_origins,
        execution_mode=execution_mode,
        injected_dependencies=injected_dependencies,
        region=region,
        base_url=base_url,
        started_utc=_timestamp(utc_now),
    )
    _checkpoint(
        target,
        evidence,
        credential=credential,
        base_url=base_url,
        replace_existing=False,
    )

    fixture_by_id = {fixture.id: fixture for fixture in manifest.fixtures}
    artifact_by_id = {artifact.id: artifact for artifact in manifest.artifacts}
    terminal_failure: dict[str, object] | None = None
    interrupt_to_raise: KeyboardInterrupt | None = None
    for entry in plan:
        dispatch = manifest.live_dispatch_order[entry.manifest_sequence]
        source_artifacts = _source_artifacts(
            entry,
            fixture_by_id=fixture_by_id,
            artifact_by_id=artifact_by_id,
        )
        source_paths = tuple(root / artifact.path for artifact in source_artifacts)
        input_languages = _input_languages(entry, fixture_by_id=fixture_by_id)
        try:
            prompt = build_board_symbol_audit_prompt(
                build_board_prompt(
                    input_languages,
                    manifest.evidence_contract.output_language,
                )
            )
            _verify_unchanged_manifest(root, manifest)
            _verify_unchanged_code(root, code_identity)
            _verify_unchanged_repository(
                root,
                relevant_paths,
                repository_identity,
                repository_identity_callable,
            )
            _verify_dispatch_inputs(source_paths, source_artifacts)
            config = _build_config(
                manifest,
                settings=settings,
                input_languages=input_languages,
            )
            started_utc = _timestamp(utc_now)
            started_ns = _monotonic_value(monotonic_ns)
            _verify_unchanged_environment_credential(
                source_environment,
                credential,
            )
        except Exception as error:
            terminal_failure = {
                "stage": "preflight",
                "code": "PRECALL_IDENTITY_INVALID",
                "exception_type": type(error).__name__,
                "retryable": False,
            }
            evidence["state"] = "aborted"
            evidence["terminal_failure"] = terminal_failure
            _mark_active_run_aborted(evidence, entry)
            evidence["finished_utc"] = _timestamp(utc_now)
            _update_summary(evidence)
            _checkpoint(
                target,
                evidence,
                credential=credential,
                base_url=base_url,
                replace_existing=True,
            )
            break
        active_attempt = {
            **_serialize_plan_entry(entry),
            "started_utc": started_utc,
            "input_languages": list(input_languages),
            "prompt_utf8_bytes": len(prompt.encode("utf-8")),
            "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
        }
        evidence["active_attempt"] = active_attempt
        evidence_summary = _require_mapping(evidence["summary"], "summary")
        evidence_summary["recognize_invocations"] = (
            _require_integer(
                evidence_summary["recognize_invocations"],
                "summary.recognize_invocations",
            )
            + 1
        )
        _checkpoint(
            target,
            evidence,
            credential=credential,
            base_url=base_url,
            replace_existing=True,
        )

        try:
            source: Path | tuple[Path, ...] = (
                source_paths[0] if entry.kind == "single" else source_paths
            )
            result = recognize_callable(source, config=config)
        except KeyboardInterrupt as error:
            failure = _credential_change_failure(source_environment, credential) or {
                "stage": "runner",
                "code": "RECOGNIZE_INTERRUPTED",
                "exception_type": "KeyboardInterrupt",
                "retryable": False,
            }
            record = _failed_dispatch_record(
                entry,
                active_attempt=active_attempt,
                finished_utc=_timestamp(utc_now),
                elapsed_ns=_elapsed_ns(started_ns, monotonic_ns),
                failure=failure,
                source_artifacts=source_artifacts,
            )
            _attach_dispatch_record(evidence, entry, record)
            terminal_failure = record["failure"]  # type: ignore[assignment]
            interrupt_to_raise = error
        except OCRLLMError as error:
            failure = _credential_change_failure(
                source_environment,
                credential,
            ) or _public_error_evidence(
                error,
                credential=credential,
                base_url=base_url,
            )
            record = _failed_dispatch_record(
                entry,
                active_attempt=active_attempt,
                finished_utc=_timestamp(utc_now),
                elapsed_ns=_elapsed_ns(started_ns, monotonic_ns),
                failure=failure,
                source_artifacts=source_artifacts,
            )
            _attach_dispatch_record(evidence, entry, record)
            terminal_failure = record["failure"]  # type: ignore[assignment]
        except Exception as error:
            failure = _credential_change_failure(source_environment, credential) or {
                "stage": "runner",
                "code": "UNEXPECTED_RECOGNIZE_EXCEPTION",
                "exception_type": type(error).__name__,
                "retryable": False,
            }
            record = _failed_dispatch_record(
                entry,
                active_attempt=active_attempt,
                finished_utc=_timestamp(utc_now),
                elapsed_ns=_elapsed_ns(started_ns, monotonic_ns),
                failure=failure,
                source_artifacts=source_artifacts,
            )
            _attach_dispatch_record(evidence, entry, record)
            terminal_failure = record["failure"]  # type: ignore[assignment]
        else:
            finished_utc = _timestamp(utc_now)
            elapsed_ns = _elapsed_ns(started_ns, monotonic_ns)
            credential_failure = _credential_change_failure(
                source_environment,
                credential,
            )
            if credential_failure is not None:
                record = _failed_dispatch_record(
                    entry,
                    active_attempt=active_attempt,
                    finished_utc=finished_utc,
                    elapsed_ns=elapsed_ns,
                    failure=credential_failure,
                    source_artifacts=source_artifacts,
                )
                _attach_dispatch_record(evidence, entry, record)
                terminal_failure = record["failure"]  # type: ignore[assignment]
            else:
                try:
                    validate_phase1_recognition_result(
                        result,
                        plan_entry=entry,
                        contract=manifest.evidence_contract,
                        provider_region=region,
                    )
                    _require_sensitive_absent(
                        result.markdown,
                        forbidden_values=(credential, base_url),
                    )
                    _verify_unchanged_manifest(root, manifest)
                    _verify_dispatch_inputs(source_paths, source_artifacts)
                    _verify_unchanged_code(root, code_identity)
                    _verify_unchanged_repository(
                        root,
                        relevant_paths,
                        repository_identity,
                        repository_identity_callable,
                    )
                except Exception as error:
                    if isinstance(
                        error,
                        (TypeError, ValueError, Phase1QualityRunnerError),
                    ):
                        failure: dict[str, object] = {
                            "stage": "result_contract",
                            "code": "RESULT_CONTRACT_INVALID",
                            "message": str(error),
                            "retryable": False,
                        }
                    else:
                        failure = {
                            "stage": "result_contract",
                            "code": "POSTCALL_VERIFICATION_FAILED",
                            "exception_type": type(error).__name__,
                            "retryable": False,
                        }
                    record = _failed_dispatch_record(
                        entry,
                        active_attempt=active_attempt,
                        finished_utc=finished_utc,
                        elapsed_ns=elapsed_ns,
                        failure=failure,
                        source_artifacts=source_artifacts,
                    )
                    _attach_dispatch_record(evidence, entry, record)
                    terminal_failure = record["failure"]  # type: ignore[assignment]
                else:
                    record = _successful_dispatch_record(
                        entry,
                        active_attempt=active_attempt,
                        finished_utc=finished_utc,
                        elapsed_ns=elapsed_ns,
                        result=result,
                        source_artifacts=source_artifacts,
                        manifest=manifest,
                        dispatch=dispatch,
                    )
                    _attach_dispatch_record(evidence, entry, record)
                    scorer_evidence = _require_mapping(record["scorer"], "scorer")
                    if scorer_evidence["status"] == "internal_failure":
                        terminal_failure = _require_mapping(
                            scorer_evidence["failure"],
                            "scorer failure",
                        )

        evidence["active_attempt"] = None
        if terminal_failure is not None:
            evidence["state"] = "aborted"
            evidence["terminal_failure"] = terminal_failure
            _mark_active_run_aborted(evidence, entry)
            evidence["finished_utc"] = _timestamp(utc_now)
        else:
            _complete_run_when_ready(evidence, entry)
        _update_summary(evidence)
        _checkpoint(
            target,
            evidence,
            credential=credential,
            base_url=base_url,
            replace_existing=True,
        )
        if terminal_failure is not None:
            break

    if terminal_failure is None:
        try:
            verify_fixture_artifacts(manifest, repository_root=root)
            _verify_unchanged_manifest(root, manifest)
            _verify_unchanged_code(root, code_identity)
            _verify_unchanged_repository(
                root,
                relevant_paths,
                repository_identity,
                repository_identity_callable,
            )
            _verify_unchanged_environment_credential(
                source_environment,
                credential,
            )
            if verify_quality_import_origins(root, runner_file=__file__) != import_origins:
                raise Phase1QualityRunnerError("import origins changed during the run")
        except Exception as error:
            terminal_failure = {
                "stage": "postflight",
                "code": "POSTFLIGHT_IDENTITY_CHANGED",
                "exception_type": type(error).__name__,
                "retryable": False,
            }
            evidence["state"] = "aborted"
            evidence["terminal_failure"] = terminal_failure
        else:
            evidence["state"] = "complete"
        evidence["finished_utc"] = _timestamp(utc_now)

    _update_summary(evidence)
    _checkpoint(
        target,
        evidence,
        credential=credential,
        base_url=base_url,
        replace_existing=True,
    )
    if interrupt_to_raise is not None:
        raise interrupt_to_raise
    return evidence


def _initial_evidence(
    *,
    manifest: Phase1FixtureManifest,
    plan_records: list[dict[str, object]],
    code_identity: Phase1CodeIdentity,
    repository_identity: QualityRepositoryIdentity,
    import_origins: QualityImportOrigins,
    execution_mode: str,
    injected_dependencies: tuple[str, ...],
    region: str,
    base_url: str,
    started_utc: str,
) -> dict[str, object]:
    plan_payload = json.dumps(
        plan_records,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    scout_prompt_template = build_board_sign_scout_prompt_template()
    return {
        "schema_version": _SCHEMA_VERSION,
        "state": "running",
        "started_utc": started_utc,
        "finished_utc": None,
        "execution": {
            "mode": execution_mode,
            "injected_dependencies": list(injected_dependencies),
        },
        "manifest": {
            "corpus_id": manifest.corpus_id,
            "sha256": manifest.raw_sha256,
            "bytes": manifest.raw_bytes,
        },
        "repository_identity": _serialize_repository_identity(
            repository_identity
        ),
        "import_origins": _serialize_import_origins(import_origins),
        "code_identity": _serialize_code_identity(code_identity),
        "environment": {
            "python": platform.python_version(),
            "implementation": platform.python_implementation(),
            "platform": platform.platform(),
            "distributions": {
                name: _distribution_version(name)
                for name in ("ocrllm", "Pillow", "openai", "httpx")
            },
        },
        "request_contract": {
            "source_type": manifest.evidence_contract.source_type,
            "profile": manifest.evidence_contract.profile,
            "provider": manifest.evidence_contract.provider,
            "model": manifest.evidence_contract.model,
            "prompt_version": manifest.evidence_contract.prompt_version,
            "draft_candidates": manifest.evidence_contract.draft_candidates,
            "review_passes": manifest.evidence_contract.review_passes,
            "standalone_sign_scout_model": (
                manifest.evidence_contract.standalone_sign_scout_model
            ),
            "standalone_sign_scout_count": (
                manifest.evidence_contract.standalone_sign_scout_count
            ),
            "standalone_sign_scout_enable_thinking": (
                manifest.evidence_contract.standalone_sign_scout_enable_thinking
            ),
            "standalone_sign_scout_prompt_version": SIGN_SCOUT_PROMPT_VERSION,
            "standalone_sign_scout_prompt_template_sha256": hashlib.sha256(
                scout_prompt_template.encode("utf-8")
            ).hexdigest(),
            "standalone_sign_scout_prompt_template_utf8_bytes": len(
                scout_prompt_template.encode("utf-8")
            ),
            "provider_calls_per_recognition": PROVIDER_CALLS_PER_RECOGNITION,
            "provider_region": region,
            "base_url_sha256": hashlib.sha256(base_url.encode("utf-8")).hexdigest(),
            "endpoint_kind": (
                "workspace" if ".maas.aliyuncs.com" in base_url else "shared"
            ),
            "timeout_seconds": int(PHASE1_TIMEOUT_SECONDS),
            "temperature": _TEMPERATURE,
            "max_completion_tokens": MAX_COMPLETION_TOKENS,
            "enable_thinking": manifest.evidence_contract.enable_thinking,
            "vl_high_resolution_images": (
                manifest.evidence_contract.vl_high_resolution_images
            ),
            "credential_source": "DASHSCOPE_API_KEY",
            "sdk_retry_count": 0,
            "runner_retry_count": 0,
            "model_fallback": False,
            "key_rotation": False,
            "success_request_id_available": False,
            "request_id_limitation": (
                "The public success result exposes no provider request ID; "
                "independence is proven by the frozen invocation plan and code identity."
            ),
        },
        "dispatch_plan": {
            "sha256": hashlib.sha256(plan_payload).hexdigest(),
            "entries": plan_records,
        },
        "active_attempt": None,
        "smoke": None,
        "full_runs": [
            {"run_index": 1, "status": "pending", "passes": None, "dispatches": []},
            {"run_index": 2, "status": "pending", "passes": None, "dispatches": []},
        ],
        "summary": {
            "planned_recognize_invocations": RECOGNITION_INVOCATION_COUNT,
            "planned_provider_calls": CONFIRMED_PAID_CALL_COUNT,
            "recognize_invocations": 0,
            "reported_provider_calls": 0,
            "completed_full_runs": 0,
            "passed_full_runs": 0,
            "simulated_plan_passed": False,
            "phase1_gate_passed": False,
        },
        "terminal_failure": None,
    }


def _successful_dispatch_record(
    entry: Phase1DispatchPlanEntry,
    *,
    active_attempt: dict[str, object],
    finished_utc: str,
    elapsed_ns: int,
    result: RecognitionResult,
    source_artifacts: tuple[ArtifactRecord, ...],
    manifest: Phase1FixtureManifest,
    dispatch: object,
) -> dict[str, object]:
    markdown_payload = result.markdown.encode("utf-8")
    try:
        report = score_recognition_result(
            manifest,
            dispatch,  # type: ignore[arg-type]
            result.markdown,
        )
    except ValueError as error:
        scorer: dict[str, object] = {
            "status": "rejected",
            "failure": {
                "stage": "scorer",
                "code": "SCORER_REJECTED",
                "message": str(error),
                "retryable": False,
            },
            "report": None,
        }
    except Exception as error:
        scorer = {
            "status": "internal_failure",
            "failure": {
                "stage": "scorer",
                "code": "SCORER_INTERNAL_FAILURE",
                "exception_type": type(error).__name__,
                "retryable": False,
            },
            "report": None,
        }
    else:
        try:
            serialized_report = serialize_recognition_quality_report(report)
        except Exception as error:
            scorer = {
                "status": "internal_failure",
                "failure": {
                    "stage": "scorer",
                    "code": "SCORER_INTERNAL_FAILURE",
                    "exception_type": type(error).__name__,
                    "retryable": False,
                },
                "report": None,
            }
        else:
            scorer = {
                "status": "passed" if report.passes else "gate_failed",
                "failure": None,
                "report": serialized_report,
            }
    return {
        **active_attempt,
        "finished_utc": finished_utc,
        "elapsed_ms": elapsed_ns // 1_000_000,
        "input_artifacts": [_serialize_artifact(item) for item in source_artifacts],
        "provider": {"status": "success", "failure": None},
        "result_contract": {
            "status": "passed",
            "metadata": dict(result.metadata),
        },
        "markdown": result.markdown,
        "markdown_utf8_bytes": len(markdown_payload),
        "markdown_sha256": hashlib.sha256(markdown_payload).hexdigest(),
        "scorer": scorer,
        "failure": None,
    }


def _failed_dispatch_record(
    entry: Phase1DispatchPlanEntry,
    *,
    active_attempt: dict[str, object],
    finished_utc: str,
    elapsed_ns: int,
    failure: dict[str, object],
    source_artifacts: tuple[ArtifactRecord, ...],
) -> dict[str, object]:
    return {
        **active_attempt,
        "finished_utc": finished_utc,
        "elapsed_ms": elapsed_ns // 1_000_000,
        "input_artifacts": [_serialize_artifact(item) for item in source_artifacts],
        "provider": {
            "status": "failed" if failure["stage"] == "provider" else "not_confirmed",
            "failure": failure,
        },
        "result_contract": {"status": "not_run", "metadata": None},
        "markdown": None,
        "markdown_utf8_bytes": None,
        "markdown_sha256": None,
        "scorer": {"status": "not_run", "failure": None, "report": None},
        "failure": failure,
    }


def _attach_dispatch_record(
    evidence: dict[str, object],
    entry: Phase1DispatchPlanEntry,
    record: dict[str, object],
) -> None:
    if entry.phase == "smoke":
        if evidence["smoke"] is not None:
            raise Phase1QualityRunnerError("smoke evidence was already recorded")
        evidence["smoke"] = record
        return
    runs = _require_list(evidence["full_runs"], "full_runs")
    run = _require_mapping(runs[entry.run_index - 1], "full run")  # type: ignore[operator]
    dispatches = _require_list(run["dispatches"], "full run dispatches")
    if any(item.get("attempt_index") == entry.attempt_index for item in dispatches):
        raise Phase1QualityRunnerError("dispatch evidence would be duplicated")
    dispatches.append(record)
    run["status"] = "running"


def _complete_run_when_ready(
    evidence: dict[str, object], entry: Phase1DispatchPlanEntry
) -> None:
    if entry.phase != "full" or entry.manifest_sequence != 5:
        return
    runs = _require_list(evidence["full_runs"], "full_runs")
    run = _require_mapping(runs[entry.run_index - 1], "full run")  # type: ignore[operator]
    dispatches = _require_list(run["dispatches"], "full run dispatches")
    if len(dispatches) != 6:
        raise Phase1QualityRunnerError("a full run did not contain six dispatches")
    run["status"] = "complete"
    run["passes"] = all(
        item["scorer"]["status"] == "passed"  # type: ignore[index]
        for item in dispatches
    )


def _mark_active_run_aborted(
    evidence: dict[str, object], entry: Phase1DispatchPlanEntry
) -> None:
    if entry.phase != "full":
        return
    runs = _require_list(evidence["full_runs"], "full_runs")
    run = _require_mapping(runs[entry.run_index - 1], "full run")  # type: ignore[operator]
    run["status"] = "aborted"
    run["passes"] = False


def _update_summary(evidence: dict[str, object]) -> None:
    runs = _require_list(evidence["full_runs"], "full_runs")
    completed = sum(item["status"] == "complete" for item in runs)
    passed = sum(item["status"] == "complete" and item["passes"] is True for item in runs)
    summary = _require_mapping(evidence["summary"], "summary")
    summary["completed_full_runs"] = completed
    summary["passed_full_runs"] = passed
    summary["reported_provider_calls"] = _reported_provider_call_count(evidence)
    smoke = evidence["smoke"]
    smoke_accepted = bool(
        type(smoke) is dict
        and smoke.get("provider", {}).get("status") == "success"
        and smoke.get("result_contract", {}).get("status") == "passed"
        and smoke.get("scorer", {}).get("status") in {"passed", "gate_failed"}
    )
    plan_passed = bool(
        evidence["state"] == "complete"
        and smoke_accepted
        and completed == 2
        and passed == 2
        and summary["recognize_invocations"] == RECOGNITION_INVOCATION_COUNT
        and summary["reported_provider_calls"] == CONFIRMED_PAID_CALL_COUNT
    )
    execution = _require_mapping(evidence["execution"], "execution")
    summary["simulated_plan_passed"] = bool(
        execution["mode"] == "simulated" and plan_passed
    )
    summary["phase1_gate_passed"] = bool(
        execution["mode"] == "live" and plan_passed
    )


def _reported_provider_call_count(evidence: dict[str, object]) -> int:
    records: list[object] = [evidence.get("smoke")]
    for run in evidence.get("full_runs", []):
        if type(run) is dict:
            records.extend(run.get("dispatches", []))
    result = 0
    for record in records:
        if type(record) is not dict:
            continue
        result_contract = record.get("result_contract")
        if type(result_contract) is not dict or result_contract.get("status") != "passed":
            continue
        metadata = result_contract.get("metadata")
        if type(metadata) is not dict:
            continue
        provider_call_count = metadata.get("provider_call_count")
        if type(provider_call_count) is int and provider_call_count > 0:
            result += provider_call_count
    return result


def _build_config(
    manifest: Phase1FixtureManifest,
    *,
    settings: DashScopeSettings,
    input_languages: tuple[str, ...],
) -> Config:
    contract = manifest.evidence_contract
    if contract.provider != "dashscope":
        raise Phase1QualityRunnerError(
            "The frozen Phase 1 contract requires the DashScope adapter."
        )
    return Config(
        provider=DashScopeSettings(
            region=settings.region,
            base_url=settings.base_url,
            api_key=settings.api_key,
            enable_thinking=contract.enable_thinking,
            vl_high_resolution_images=contract.vl_high_resolution_images,
            standalone_sign_scout_model=contract.standalone_sign_scout_model,
        ),
        vision_model=VisionModelSettings(name=contract.model),
        preferences=RecognitionPreferences(
            draft_candidates=contract.draft_candidates,
            review_passes=contract.review_passes,
        ),
        profile=contract.profile,
        input_languages=input_languages,
        output_language=contract.output_language,
        timeout_seconds=PHASE1_TIMEOUT_SECONDS,
    )


def _source_artifacts(
    entry: Phase1DispatchPlanEntry,
    *,
    fixture_by_id: dict[str, FixtureRecord],
    artifact_by_id: dict[str, ArtifactRecord],
) -> tuple[ArtifactRecord, ...]:
    try:
        return tuple(
            artifact_by_id[fixture_by_id[fixture_id].artifact_id]
            for fixture_id in entry.fixture_ids
        )
    except KeyError as exc:
        raise Phase1QualityRunnerError("dispatch references missing fixture evidence") from exc


def _input_languages(
    entry: Phase1DispatchPlanEntry,
    *,
    fixture_by_id: dict[str, FixtureRecord],
) -> tuple[str, ...]:
    return tuple(
        dict.fromkeys(
            language
            for fixture_id in entry.fixture_ids
            for language in fixture_by_id[fixture_id].languages
        )
    )


def _verify_dispatch_inputs(
    paths: tuple[Path, ...], artifacts: tuple[ArtifactRecord, ...]
) -> None:
    for path, artifact in zip(paths, artifacts, strict=True):
        if path.is_symlink() or not path.is_file():
            raise Phase1QualityRunnerError("dispatch input is missing or linked")
        payload = path.read_bytes()
        if (
            len(payload) != artifact.bytes
            or hashlib.sha256(payload).hexdigest() != artifact.sha256
        ):
            raise Phase1QualityRunnerError("dispatch input differs from the manifest")


def _verify_unchanged_manifest(
    root: Path,
    expected: Phase1FixtureManifest,
) -> None:
    current = load_fixture_manifest(root / _MANIFEST_RELATIVE_PATH)
    if current != expected:
        raise Phase1QualityRunnerError("manifest changed during the run")


def _verify_unchanged_code(root: Path, expected: Phase1CodeIdentity) -> None:
    if hash_quality_bundle(root) != expected:
        raise Phase1QualityRunnerError("runtime or scorer code changed during the run")


def _verify_unchanged_repository(
    root: Path,
    relevant_paths: tuple[str, ...],
    expected: QualityRepositoryIdentity,
    identity_callable: Callable[..., QualityRepositoryIdentity],
) -> None:
    current = _capture_repository_identity(root, relevant_paths, identity_callable)
    if current != expected:
        raise Phase1QualityRunnerError("repository identity changed during the run")


def _capture_repository_identity(
    root: Path,
    relevant_paths: tuple[str, ...],
    identity_callable: Callable[..., QualityRepositoryIdentity],
) -> QualityRepositoryIdentity:
    identity = identity_callable(root, relevant_paths)
    if type(identity) is not QualityRepositoryIdentity:
        raise TypeError(
            "repository_identity_callable must return QualityRepositoryIdentity"
        )
    return identity


def _relevant_repository_paths(
    manifest: Phase1FixtureManifest,
    code_identity: Phase1CodeIdentity,
) -> tuple[str, ...]:
    paths = {
        _MANIFEST_RELATIVE_PATH,
        *(artifact.path for artifact in manifest.artifacts),
        *(
            item.path
            for bundle in (
                code_identity.runtime,
                code_identity.quality,
                code_identity.packaging,
            )
            for item in bundle.files
        ),
    }
    return tuple(sorted(paths))


def _require_environment_credential(environment: Mapping[str, str]) -> str:
    if not isinstance(environment, Mapping):
        raise TypeError("environment must be a mapping")
    credential = environment.get("DASHSCOPE_API_KEY")
    if (
        type(credential) is not str
        or not credential
        or credential != credential.strip()
        or credential.startswith("sk-sp-")
    ):
        raise Phase1QualityRunnerError(
            "DASHSCOPE_API_KEY must contain one valid non-Coding-Plan credential"
        )
    return credential


def _verify_unchanged_environment_credential(
    environment: Mapping[str, str],
    expected: str,
) -> None:
    try:
        current = _require_environment_credential(environment)
    except Exception as exc:
        raise Phase1QualityRunnerError(
            "DASHSCOPE_API_KEY could not be reverified"
        ) from exc
    if current != expected:
        raise Phase1QualityRunnerError("DASHSCOPE_API_KEY changed during the run")


def _credential_change_failure(
    environment: Mapping[str, str],
    expected: str,
) -> dict[str, object] | None:
    try:
        _verify_unchanged_environment_credential(environment, expected)
    except Phase1QualityRunnerError:
        return {
            "stage": "credential",
            "code": "CREDENTIAL_CHANGED_DURING_CALL",
            "retryable": False,
        }
    return None


def _require_safe_new_evidence_path(root: Path, target: Path) -> None:
    resolved = target.resolve(strict=False)
    if os.path.lexists(target):
        raise Phase1QualityRunnerError("evidence path must not already exist")
    if any(
        resolved.is_relative_to((root / relative).resolve(strict=False))
        for relative in _BOUND_OUTPUT_ROOTS
    ):
        raise Phase1QualityRunnerError("evidence path must stay outside source and corpus roots")


def _public_error_evidence(
    error: OCRLLMError,
    *,
    credential: str,
    base_url: str,
) -> dict[str, object]:
    stage = "provider" if error.code.startswith("PROVIDER_") else "library"
    evidence = {
        "stage": stage,
        "code": error.code,
        "retryable": error.retryable,
        "message": str(error),
        "details": dict(error.details),
    }
    if _contains_sensitive_text(evidence, (credential, base_url)):
        return {
            "stage": "redaction",
            "code": "SENSITIVE_VALUE_LEAK_PREVENTED",
            "retryable": False,
        }
    return evidence


def _require_sensitive_absent(
    value: str,
    *,
    forbidden_values: tuple[str, ...],
) -> None:
    if any(item in value for item in forbidden_values):
        raise Phase1QualityRunnerError("provider output contained a sensitive value")


def _contains_sensitive_text(value: object, forbidden_values: tuple[str, ...]) -> bool:
    if type(value) is str:
        return any(item in value for item in forbidden_values)
    if isinstance(value, Mapping):
        return any(
            _contains_sensitive_text(key, forbidden_values)
            or _contains_sensitive_text(item, forbidden_values)
            for key, item in value.items()
        )
    if isinstance(value, (list, tuple)):
        return any(_contains_sensitive_text(item, forbidden_values) for item in value)
    return False


def _checkpoint(
    path: Path,
    evidence: dict[str, object],
    *,
    credential: str,
    base_url: str,
    replace_existing: bool,
) -> None:
    try:
        write_quality_evidence_atomically(
            path,
            evidence,
            credential=credential,
            forbidden_values=(base_url,),
            replace_existing=replace_existing,
        )
    except QualityEvidenceWriteError as exc:
        raise Phase1QualityRunnerError("quality evidence checkpoint failed") from exc


def _serialize_plan_entry(entry: Phase1DispatchPlanEntry) -> dict[str, object]:
    return {
        "attempt_index": entry.attempt_index,
        "phase": entry.phase,
        "run_index": entry.run_index,
        "manifest_sequence": entry.manifest_sequence,
        "kind": entry.kind,
        "fixture_ids": list(entry.fixture_ids),
        "ordered_request_id": entry.ordered_request_id,
    }


def _serialize_artifact(artifact: ArtifactRecord) -> dict[str, object]:
    return {
        "id": artifact.id,
        "path": artifact.path,
        "bytes": artifact.bytes,
        "sha256": artifact.sha256,
    }


def _serialize_repository_identity(
    identity: QualityRepositoryIdentity,
) -> dict[str, object]:
    return {
        "head_commit": identity.head_commit,
        "relevant_index_sha256": identity.relevant_index_sha256,
        "relevant_file_count": identity.relevant_file_count,
        "relevant_tree_clean": identity.relevant_tree_clean,
    }


def _serialize_import_origins(origins: QualityImportOrigins) -> dict[str, object]:
    return {
        "runtime_package": origins.runtime_package,
        "runtime_relative_root": origins.runtime_relative_root,
        "quality_package": origins.quality_package,
        "quality_relative_root": origins.quality_relative_root,
        "runner_relative_path": origins.runner_relative_path,
        "matches_repository": origins.matches_repository,
    }


def _serialize_code_identity(identity: Phase1CodeIdentity) -> dict[str, object]:
    return {
        "bundle_algorithm": "sha256-length-framed-path-and-bytes-v1",
        "runtime": _serialize_bundle(identity.runtime),
        "quality": _serialize_bundle(identity.quality),
        "packaging": _serialize_bundle(identity.packaging),
    }


def _serialize_bundle(bundle: QualityCodeBundle) -> dict[str, object]:
    return {
        "name": bundle.name,
        "sha256": bundle.sha256,
        "file_count": len(bundle.files),
        "files": [
            {"path": item.path, "bytes": item.bytes, "sha256": item.sha256}
            for item in bundle.files
        ],
    }


def _timestamp(clock: Callable[[], datetime]) -> str:
    value = clock()
    if type(value) is not datetime or value.tzinfo is None:
        raise Phase1QualityRunnerError("UTC clock must return an aware datetime")
    return value.astimezone(timezone.utc).isoformat(timespec="microseconds").replace(
        "+00:00", "Z"
    )


def _monotonic_value(clock: Callable[[], int]) -> int:
    value = clock()
    if type(value) is not int or value < 0:
        raise Phase1QualityRunnerError("monotonic clock must return a non-negative integer")
    return value


def _elapsed_ns(started: int, clock: Callable[[], int]) -> int:
    finished = _monotonic_value(clock)
    if finished < started:
        raise Phase1QualityRunnerError("monotonic clock moved backwards")
    return finished - started


def _distribution_version(name: str) -> str:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError as exc:
        if name == "ocrllm":
            return OCRLLM_VERSION
        raise Phase1QualityRunnerError(
            f"required distribution is not installed: {name}"
        ) from exc


def _require_mapping(value: object, context: str) -> dict[str, Any]:
    if type(value) is not dict:
        raise Phase1QualityRunnerError(f"{context} evidence is not an object")
    return value


def _require_list(value: object, context: str) -> list[Any]:
    if type(value) is not list:
        raise Phase1QualityRunnerError(f"{context} evidence is not an array")
    return value


def _require_integer(value: object, context: str) -> int:
    if type(value) is not int or value < 0:
        raise Phase1QualityRunnerError(f"{context} must be a non-negative integer")
    return value


def _run_phase1_quality_simulated(
    *,
    region: str,
    base_url: str,
    evidence_path: str | Path,
    confirm_paid_calls: int,
    environment: Mapping[str, str],
    recognize_callable: Callable[..., RecognitionResult],
    utc_now: Callable[[], datetime],
    monotonic_ns: Callable[[], int],
    repository_identity_callable: Callable[..., QualityRepositoryIdentity],
    repository_root: str | Path = DEFAULT_REPOSITORY_ROOT,
) -> dict[str, object]:
    """Exercise the paid-call plan with fakes without producing live evidence."""

    return _run_phase1_quality_engine(
        region=region,
        base_url=base_url,
        evidence_path=evidence_path,
        confirm_paid_calls=confirm_paid_calls,
        repository_root=repository_root,
        execution_mode="simulated",
        injected_dependencies=(
            "environment",
            "recognize_callable",
            "utc_now",
            "monotonic_ns",
            "repository_identity_callable",
        ),
        environment=environment,
        recognize_callable=recognize_callable,
        utc_now=utc_now,
        monotonic_ns=monotonic_ns,
        repository_identity_callable=repository_identity_callable,
    )


def _make_live_phase1_quality_runner(
    *,
    engine: Callable[..., dict[str, object]],
    environment: Mapping[str, str],
    recognize_callable: Callable[..., RecognitionResult],
    utc_now: Callable[[], datetime],
    monotonic_ns: Callable[[], int],
    repository_identity_callable: Callable[..., QualityRepositoryIdentity],
) -> Callable[..., dict[str, object]]:
    """Close immutable live dependencies outside the public call signature."""

    def live_runner(
        *,
        region: str,
        base_url: str,
        evidence_path: str | Path,
        confirm_paid_calls: int,
        repository_root: str | Path = DEFAULT_REPOSITORY_ROOT,
    ) -> dict[str, object]:
        """Run the guarded live Phase 1 smoke and two full quality passes."""

        return engine(
            region=region,
            base_url=base_url,
            evidence_path=evidence_path,
            confirm_paid_calls=confirm_paid_calls,
            repository_root=repository_root,
            execution_mode="live",
            injected_dependencies=(),
            environment=environment,
            recognize_callable=recognize_callable,
            utc_now=utc_now,
            monotonic_ns=monotonic_ns,
            repository_identity_callable=repository_identity_callable,
        )

    live_runner.__name__ = "run_phase1_quality"
    live_runner.__qualname__ = "run_phase1_quality"
    return live_runner


def _system_utc_now() -> datetime:
    return datetime.now(timezone.utc)


run_phase1_quality = _make_live_phase1_quality_runner(
    engine=_run_phase1_quality_engine,
    environment=os.environ,
    recognize_callable=recognize,
    utc_now=_system_utc_now,
    monotonic_ns=time.monotonic_ns,
    repository_identity_callable=capture_quality_repository_identity,
)


def main(argv: Sequence[str] | None = None) -> int:
    """Parse the guarded live CLI and return a stable process exit code."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--region", required=True)
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--evidence", required=True, type=Path)
    parser.add_argument("--confirm-paid-calls", required=True, type=int)
    arguments = parser.parse_args(argv)
    try:
        evidence = run_phase1_quality(
            region=arguments.region,
            base_url=arguments.base_url,
            evidence_path=arguments.evidence,
            confirm_paid_calls=arguments.confirm_paid_calls,
        )
    except (Phase1QualityRunnerError, OCRLLMError, ValueError, TypeError) as error:
        print(f"Phase 1 quality runner stopped safely: {error}", file=sys.stderr)
        return 2
    final_bytes = arguments.evidence.read_bytes()
    print(f"evidence_sha256={hashlib.sha256(final_bytes).hexdigest()}")
    summary = _require_mapping(evidence["summary"], "summary")
    return 0 if summary["phase1_gate_passed"] is True else 5


if __name__ == "__main__":
    raise SystemExit(main())
