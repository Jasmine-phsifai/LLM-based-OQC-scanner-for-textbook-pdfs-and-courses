"""Run one fixed, content-free public merged-audio Google scenario."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from collections.abc import Mapping
from pathlib import Path

from ocrllm import (
    GOOGLE_GEMINI_2_5_FLASH,
    ProviderModel,
    recognize_audio_to_markdown,
    repair_audio_to_markdown,
    resume_audio_to_markdown,
    split_audio,
)
from ocrllm.errors import OCRLLMError


UNSERVED_MODEL = "ocrllm-intentionally-unserved-audio-fallback-probe"
FALLBACK_WARNING = (
    "Recognition completed after one or more provider candidates failed."
)


def main() -> int:
    args = _parse_args()
    source = args.audio
    output = args.output
    state = output.with_name(f"{output.stem}.ocrllm-state.json")
    try:
        before = _source_facts(source)
        slices = split_audio(source, interval_minutes=args.interval_minutes)
    except OCRLLMError as error:
        print(
            json.dumps(
                {
                    "status": "error",
                    "stage": "source_preflight",
                    "code": error.code,
                    "provider_calls_attempted": _nonnegative_int(
                        error.details.get("provider_calls_attempted")
                    ),
                    "output": _artifact_summary(output),
                    "state_exists": os.path.lexists(state),
                },
                sort_keys=True,
            )
        )
        return 1
    except (OSError, ValueError):
        print(
            json.dumps(
                {
                    "status": "runner_invalid",
                    "stage": "source_preflight",
                    "output": _artifact_summary(output),
                    "state_exists": os.path.lexists(state),
                },
                sort_keys=True,
            )
        )
        return 2
    if args.repair:
        provider = [
            [GOOGLE_GEMINI_2_5_FLASH],
            [_unserved_audio_provider()],
        ]
    elif args.flat_fallback:
        provider = [_unserved_audio_provider(), GOOGLE_GEMINI_2_5_FLASH]
    elif args.unserved_only:
        provider = _unserved_audio_provider()
    elif args.nested_lanes:
        provider = [
            [GOOGLE_GEMINI_2_5_FLASH],
            [GOOGLE_GEMINI_2_5_FLASH],
        ]
    else:
        provider = GOOGLE_GEMINI_2_5_FLASH
    if len(slices) != args.expected_slots:
        print(
            json.dumps(
                {
                    "status": "runner_invalid",
                    "reason": "unexpected_slot_count",
                    "slot_count": len(slices),
                    "sources_unchanged": _source_facts(source) == before,
                },
                sort_keys=True,
            )
        )
        return 2
    if args.repair:
        return _run_repair_scenario(
            args,
            source=source,
            output=output,
            state=state,
            slices=slices,
            provider=provider,
            before=before,
        )

    try:
        if args.resume:
            result = resume_audio_to_markdown(
                slices,
                provider=provider,
                output_path=output,
                timeout_seconds=args.timeout_seconds,
            )
        else:
            result = recognize_audio_to_markdown(
                slices,
                provider=provider,
                output_path=output,
                timeout_seconds=args.timeout_seconds,
            )
    except OCRLLMError as error:
        print(
            json.dumps(
                {
                    "status": "error",
                    "provider_mode": _provider_mode(args),
                    "lane_count": 2 if args.nested_lanes else 1,
                    "code": error.code,
                    "provider_calls_attempted": _nonnegative_int(
                        error.details.get("provider_calls_attempted")
                    ),
                    "failed_slots": _safe_failed_slots(
                        error.details.get("failed_slots")
                    ),
                    "output_exists": output.is_file(),
                    "state_exists": state.is_file(),
                    "sources_unchanged": _source_facts(source) == before,
                },
                sort_keys=True,
            )
        )
        return 1

    output_bytes = output.read_bytes() if output.is_file() else None
    result_bytes = result.markdown.encode("utf-8")
    summary = {
        "status": result.status,
        "provider_mode": _provider_mode(args),
        "lane_count": 2 if args.nested_lanes else 1,
        "planning_mode": "whole" if args.interval_minutes == -1 else "interval",
        "duration_seconds": slices[-1].logical_end_seconds,
        "slot_count": result.metadata.get("slot_count"),
        "settled_slot_count": result.metadata.get("settled_slot_count"),
        "no_speech_slot_count": result.metadata.get("no_speech_slot_count"),
        "reused_slot_count": result.metadata.get("reused_slot_count"),
        "provider_call_count": result.metadata.get("provider_call_count"),
        "current_provider_model_usage": _safe_usage_documents(
            result.metadata.get("current_provider_model_usage")
        ),
        "historical_provider_model_usage": _safe_usage_documents(
            result.metadata.get("historical_provider_model_usage")
        ),
        "failed_slots": _safe_failed_slots(result.metadata.get("failed_slots")),
        "provider_failures": _safe_provider_failures(
            result.metadata.get("provider_failures")
        ),
        "warning_count": len(result.warnings),
        "output_exists": output_bytes is not None,
        "output_matches_result": output_bytes == result_bytes,
        "output_byte_size": None if output_bytes is None else len(output_bytes),
        "output_sha256": (
            None if output_bytes is None else hashlib.sha256(output_bytes).hexdigest()
        ),
        "state_exists": state.is_file(),
        "sources_unchanged": _source_facts(source) == before,
    }
    passed = (
        result.status == "complete"
        and summary["slot_count"] == args.expected_slots
        and summary["settled_slot_count"] == args.expected_slots
        and summary["reused_slot_count"] == args.expected_reused_slots
        and summary["provider_call_count"] == args.expected_current_calls
        and _usage_call_count(summary["historical_provider_model_usage"])
        == args.expected_historical_calls
        and summary["output_exists"] is True
        and summary["output_matches_result"] is True
        and summary["state_exists"] is False
        and summary["sources_unchanged"] is True
        and _fallback_evidence_matches(
            result.warnings,
            summary["provider_failures"],
            enabled=args.flat_fallback,
        )
    )
    summary["gate"] = "passed" if passed else "not_passed"
    print(json.dumps(summary, sort_keys=True))
    return 0 if passed else 1


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--audio", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--interval-minutes", type=int, required=True)
    parser.add_argument("--expected-slots", type=int, required=True)
    parser.add_argument("--expected-current-calls", type=int, required=True)
    parser.add_argument("--expected-reused-slots", type=int, default=0)
    parser.add_argument("--expected-historical-calls", type=int, default=0)
    parser.add_argument("--timeout-seconds", type=float, default=600.0)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--flat-fallback", action="store_true")
    parser.add_argument("--unserved-only", action="store_true")
    parser.add_argument("--nested-lanes", action="store_true")
    parser.add_argument("--repair", action="store_true")
    args = parser.parse_args()
    if (
        args.interval_minutes != -1 and args.interval_minutes <= 0
        or args.expected_slots <= 0
        or args.expected_current_calls < 0
        or args.expected_reused_slots < 0
        or args.expected_reused_slots > args.expected_slots
        or args.expected_historical_calls < 0
        or args.timeout_seconds <= 0
    ):
        parser.error("numeric scenario arguments are outside their fixed bounds")
    if args.interval_minutes == -1 and args.expected_slots != 1:
        parser.error("whole mode requires exactly one expected slot")
    if sum(
        (args.flat_fallback, args.unserved_only, args.nested_lanes, args.repair)
    ) > 1:
        parser.error("provider scenario modes are mutually exclusive")
    if args.resume and (args.flat_fallback or args.unserved_only or args.repair):
        parser.error("fixed provider failure scenarios are fresh-only")
    if args.unserved_only and args.expected_current_calls != 0:
        parser.error("unserved-only expects zero generation calls")
    if args.nested_lanes and (
        args.interval_minutes <= 0 or args.expected_slots < 2
    ):
        parser.error("nested-lanes requires a multi-slot interval scenario")
    if args.repair and (
        args.interval_minutes != 1
        or args.expected_slots != 2
        or args.expected_current_calls != 1
        or args.expected_reused_slots != 0
        or args.expected_historical_calls != 0
    ):
        parser.error("repair requires the fixed two-slot, one-call-per-stage gate")
    return args


def _provider_mode(args: argparse.Namespace) -> str:
    if args.repair:
        return "repair"
    if args.flat_fallback:
        return "flat_fallback"
    if args.unserved_only:
        return "unserved_only"
    if args.nested_lanes:
        return "nested"
    return "scalar"


def _run_repair_scenario(
    args: argparse.Namespace,
    *,
    source: Path,
    output: Path,
    state: Path,
    slices,
    provider,
    before: tuple[int, str],
) -> int:
    try:
        partial = recognize_audio_to_markdown(
            slices,
            provider=provider,
            output_path=output,
            timeout_seconds=args.timeout_seconds,
        )
    except OCRLLMError as error:
        _print_repair_error(
            error,
            stage="fresh",
            source=source,
            output=output,
            state=state,
            before=before,
        )
        return 1

    valid_partial, partial_usage, partial_failed = _validate_fresh_partial(
        partial,
        source=source,
        output=output,
        state=state,
        before=before,
    )
    if not valid_partial:
        print(
            json.dumps(
                {
                    "status": "runner_invalid",
                    "stage": "fresh_partial",
                    "result_status": partial.status,
                    "provider_call_count": partial.metadata.get(
                        "provider_call_count"
                    ),
                    "failed_slots": partial_failed,
                    "output_exists": output.is_file(),
                    "state_exists": state.is_file(),
                    "sources_unchanged": _sources_unchanged(source, before),
                },
                sort_keys=True,
            )
        )
        return 2
    assert partial_usage is not None
    partial_summary = _artifact_summary(output)
    try:
        state.unlink()
    except (OSError, ValueError):
        print(
            json.dumps(
                {
                    "status": "runner_invalid",
                    "stage": "state_loss",
                    "output": partial_summary,
                    "state_exists": state.is_file(),
                    "sources_unchanged": _sources_unchanged(source, before),
                },
                sort_keys=True,
            )
        )
        return 2

    try:
        repaired = repair_audio_to_markdown(
            source,
            provider=GOOGLE_GEMINI_2_5_FLASH,
            output_path=output,
            timeout_seconds=args.timeout_seconds,
        )
    except OCRLLMError as error:
        _print_repair_error(
            error,
            stage="repair",
            source=source,
            output=output,
            state=state,
            before=before,
        )
        return 1

    return _finish_repair_scenario(
        repaired,
        source=source,
        output=output,
        state=state,
        slices=slices,
        before=before,
        partial_summary=partial_summary,
        partial_usage=partial_usage,
    )


def _validate_fresh_partial(
    partial,
    *,
    source: Path,
    output: Path,
    state: Path,
    before: tuple[int, str],
) -> tuple[
    bool,
    dict[str, str | int | None] | None,
    dict[str, int | str] | None,
]:
    partial_bytes = _read_file_bytes(output)
    partial_usage = _strict_google_usage(
        partial.metadata.get("current_provider_model_usage")
    )
    partial_failed = _strict_failed_slot(
        partial.metadata.get("failed_slots"),
        model=UNSERVED_MODEL,
        code="PROVIDER_UNAVAILABLE",
    )
    valid = (
        partial.status == "partial"
        and partial.source_type == "audio"
        and partial.output_path == output
        and partial.warnings == ()
        and _is_exact_int(partial.metadata.get("slot_count"), 2)
        and _is_exact_int(partial.metadata.get("settled_slot_count"), 1)
        and _is_exact_int(partial.metadata.get("reused_slot_count"), 0)
        and _is_exact_int(partial.metadata.get("provider_call_count"), 1)
        and partial.metadata.get("historical_provider_model_usage") == ()
        and partial_usage is not None
        and partial_failed is not None
        and partial.metadata.get("provider_failures") is None
        and partial_bytes is not None
        and partial_bytes == partial.markdown.encode("utf-8")
        and state.is_file()
        and _sources_unchanged(source, before)
    )
    return valid, partial_usage, partial_failed


def _finish_repair_scenario(
    repaired,
    *,
    source: Path,
    output: Path,
    state: Path,
    slices,
    before: tuple[int, str],
    partial_summary: dict[str, object],
    partial_usage: dict[str, str | int | None],
) -> int:
    output_bytes = _read_file_bytes(output)
    usage = _strict_google_usage(
        repaired.metadata.get("current_provider_model_usage")
    )
    failed_slots = _safe_failed_slots(repaired.metadata.get("failed_slots"))
    summary = {
        "status": repaired.status,
        "gate": "not_passed",
        "provider_mode": "repair",
        "planning_mode": "interval",
        "duration_seconds": slices[-1].logical_end_seconds,
        "slot_count": repaired.metadata.get("slot_count"),
        "settled_slot_count": repaired.metadata.get("settled_slot_count"),
        "repair_marker_count": repaired.metadata.get("repair_marker_count"),
        "repaired_slot_count": repaired.metadata.get("repaired_slot_count"),
        "no_speech_repaired_slot_count": repaired.metadata.get(
            "no_speech_repaired_slot_count"
        ),
        "fresh_provider_call_count": 1,
        "fresh_provider_model_usage": (partial_usage,),
        "repair_provider_call_count": repaired.metadata.get(
            "provider_call_count"
        ),
        "repair_provider_model_usage": (
            () if usage is None else (usage,)
        ),
        "failed_slots": failed_slots,
        "warning_count": len(repaired.warnings),
        "partial_output": partial_summary,
        "output": _artifact_summary(output),
        "output_matches_result": (
            output_bytes is not None
            and output_bytes == repaired.markdown.encode("utf-8")
        ),
        "state_exists": os.path.lexists(state),
        "sources_unchanged": _sources_unchanged(source, before),
    }
    passed = (
        repaired.status == "complete"
        and repaired.source_type == "audio"
        and repaired.output_path == output
        and _is_exact_int(summary["slot_count"], 2)
        and _is_exact_int(summary["settled_slot_count"], 2)
        and _is_exact_int(summary["repair_marker_count"], 1)
        and _is_exact_int(summary["repaired_slot_count"], 1)
        and _is_exact_int(summary["repair_provider_call_count"], 1)
        and usage is not None
        and repaired.metadata.get("failed_slots") is None
        and repaired.metadata.get("provider_failures") is None
        and repaired.warnings == ()
        and "OCRLLM_FAILED_AUDIO_SLOT" not in repaired.markdown
        and summary["output_matches_result"] is True
        and summary["output"] != partial_summary
        and summary["state_exists"] is False
        and summary["sources_unchanged"] is True
    )
    summary["gate"] = "passed" if passed else "not_passed"
    print(json.dumps(summary, sort_keys=True))
    return 0 if passed else 1


def _print_repair_error(
    error: OCRLLMError,
    *,
    stage: str,
    source: Path,
    output: Path,
    state: Path,
    before: tuple[int, str],
) -> None:
    print(
        json.dumps(
            {
                "status": "error",
                "provider_mode": "repair",
                "stage": stage,
                "code": error.code,
                "provider_calls_attempted": _nonnegative_int(
                    error.details.get("provider_calls_attempted")
                ),
                "current_provider_model_usage": _safe_usage_documents(
                    error.details.get("current_provider_model_usage")
                ),
                "failed_slots": _safe_failed_slots(
                    error.details.get("failed_slots")
                ),
                "output": _artifact_summary(output),
                "state_exists": os.path.lexists(state),
                "sources_unchanged": _sources_unchanged(source, before),
                "provider_cleanup_failed": _provider_cleanup_failed(error),
                "provider_client_closed": _optional_bool(
                    error.details.get("provider_client_closed")
                ),
                "remote_file_deleted": _optional_bool(
                    error.details.get("remote_file_deleted")
                ),
            },
            sort_keys=True,
        )
    )


def _artifact_summary(path: Path) -> dict[str, object]:
    try:
        if not path.is_file():
            return {"exists": False}
        size, digest = _source_facts(path)
    except (OSError, ValueError):
        return {"exists": None}
    return {"exists": True, "size": size, "sha256": digest}


def _read_file_bytes(path: Path) -> bytes | None:
    try:
        return path.read_bytes() if path.is_file() else None
    except (OSError, ValueError):
        return None


def _sources_unchanged(path: Path, before: tuple[int, str]) -> bool:
    try:
        return _source_facts(path) == before
    except (OSError, ValueError):
        return False


def _strict_google_usage(
    value: object,
) -> dict[str, str | int | None] | None:
    if not isinstance(value, (tuple, list)) or len(value) != 1:
        return None
    row = value[0]
    if not isinstance(row, Mapping):
        return None
    calls = row.get("calls")
    input_tokens = row.get("input_tokens")
    output_tokens = row.get("output_tokens")
    if (
        row.get("vendor") != "google"
        or row.get("model") != GOOGLE_GEMINI_2_5_FLASH.model
        or type(calls) is not int
        or calls != 1
        or not _optional_count(input_tokens)
        or not _optional_count(output_tokens)
    ):
        return None
    return {
        "vendor": "google",
        "model": GOOGLE_GEMINI_2_5_FLASH.model,
        "calls": 1,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
    }


def _strict_failed_slot(
    value: object,
    *,
    model: str,
    code: str,
) -> dict[str, int | str] | None:
    if not isinstance(value, (tuple, list)) or len(value) != 1:
        return None
    row = value[0]
    index = row.get("slot_index") if isinstance(row, Mapping) else None
    if not isinstance(row, Mapping) or (
        type(index) is not int
        or index != 1
        or row.get("provider") != "google"
        or row.get("model") != model
        or row.get("code") != code
    ):
        return None
    return {
        "slot_index": 1,
        "provider": "google",
        "model": model,
        "code": code,
    }


def _optional_count(value: object) -> bool:
    return value is None or (type(value) is int and value >= 0)


def _is_exact_int(value: object, expected: int) -> bool:
    return type(value) is int and value == expected


def _optional_bool(value: object) -> bool | None:
    return value if type(value) is bool else None


def _provider_cleanup_failed(error: OCRLLMError) -> bool:
    return bool(
        error.details.get("provider_file_cleanup_failed") is True
        or error.details.get("remote_file_deleted") is False
        or error.details.get("provider_client_cleanup_failed") is True
        or error.details.get("provider_client_closed") is False
    )


def _unserved_audio_provider() -> ProviderModel:
    return ProviderModel(
        vendor="google",
        model=UNSERVED_MODEL,
        adapter_id="google_genai",
        settings=GOOGLE_GEMINI_2_5_FLASH.settings,
        supports_plain_ocr=True,
        supports_detail_ocr=True,
        supports_audio=True,
        default_image_batch_size=8,
        default_audio_minutes=30,
        retry_rules={},
    )


def _source_facts(path: Path) -> tuple[int, str]:
    digest = hashlib.sha256()
    byte_size = 0
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            byte_size += len(chunk)
            digest.update(chunk)
    return byte_size, digest.hexdigest()


def _nonnegative_int(value: object) -> int | None:
    return value if type(value) is int and value >= 0 else None


def _safe_failed_slots(value: object) -> tuple[dict[str, int | str], ...]:
    if not isinstance(value, (tuple, list)):
        return ()
    safe: list[dict[str, int | str]] = []
    for item in value:
        if not isinstance(item, Mapping):
            continue
        index = item.get("slot_index")
        provider = item.get("provider")
        model = item.get("model")
        code = item.get("code")
        if (
            type(index) is int
            and index >= 0
            and type(provider) is str
            and provider
            and type(model) is str
            and model
            and type(code) is str
            and code
        ):
            safe.append(
                {
                    "slot_index": index,
                    "provider": provider,
                    "model": model,
                    "code": code,
                }
            )
    return tuple(safe)


def _safe_provider_failures(
    value: object,
) -> tuple[dict[str, int | str], ...]:
    if not isinstance(value, (tuple, list)):
        return ()
    safe: list[dict[str, int | str]] = []
    for item in value:
        if not isinstance(item, Mapping):
            continue
        index = item.get("slot_index")
        vendor = item.get("vendor")
        model = item.get("model")
        code = item.get("code")
        if (
            type(index) is int
            and index >= 0
            and type(vendor) is str
            and vendor
            and type(model) is str
            and model
            and type(code) is str
            and code
        ):
            safe.append(
                {
                    "slot_index": index,
                    "vendor": vendor,
                    "model": model,
                    "code": code,
                }
            )
    return tuple(safe)


def _fallback_evidence_matches(
    warnings: tuple[str, ...],
    provider_failures: object,
    *,
    enabled: bool,
) -> bool:
    if not enabled:
        return not provider_failures
    return warnings == (FALLBACK_WARNING,) and provider_failures == (
        {
            "slot_index": 0,
            "vendor": "google",
            "model": UNSERVED_MODEL,
            "code": "PROVIDER_UNAVAILABLE",
        },
    )


def _safe_usage_documents(
    value: object,
) -> tuple[dict[str, str | int | None], ...]:
    if not isinstance(value, (tuple, list)):
        return ()
    safe: list[dict[str, str | int | None]] = []
    for item in value:
        if not isinstance(item, Mapping):
            continue
        vendor = item.get("vendor")
        model = item.get("model")
        calls = item.get("calls")
        input_tokens = item.get("input_tokens")
        output_tokens = item.get("output_tokens")
        if (
            type(vendor) is str
            and vendor
            and type(model) is str
            and model
            and type(calls) is int
            and calls >= 0
            and (input_tokens is None or type(input_tokens) is int)
            and (output_tokens is None or type(output_tokens) is int)
        ):
            safe.append(
                {
                    "vendor": vendor,
                    "model": model,
                    "calls": calls,
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                }
            )
    return tuple(safe)


def _usage_call_count(value: object) -> int | None:
    if not isinstance(value, (tuple, list)):
        return None
    calls = tuple(
        row.get("calls") for row in value if isinstance(row, Mapping)
    )
    if len(calls) != len(value) or any(
        type(count) is not int or count < 0 for count in calls
    ):
        return None
    return sum(calls)


if __name__ == "__main__":
    raise SystemExit(main())
