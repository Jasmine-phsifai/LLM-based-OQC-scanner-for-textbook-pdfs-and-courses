"""Run one fixed, content-free public merged-audio Google scenario."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections.abc import Mapping
from pathlib import Path

from ocrllm import (
    GOOGLE_GEMINI_2_5_FLASH,
    ProviderModel,
    recognize_audio_to_markdown,
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
    before = _source_facts(source)
    slices = split_audio(source, interval_minutes=args.interval_minutes)
    if args.flat_fallback:
        provider = [_unserved_audio_provider(), GOOGLE_GEMINI_2_5_FLASH]
    elif args.unserved_only:
        provider = _unserved_audio_provider()
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
    parser.add_argument("--timeout-seconds", type=float, default=600.0)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--flat-fallback", action="store_true")
    parser.add_argument("--unserved-only", action="store_true")
    args = parser.parse_args()
    if (
        args.interval_minutes != -1 and args.interval_minutes <= 0
        or args.expected_slots <= 0
        or args.expected_current_calls < 0
        or args.expected_reused_slots < 0
        or args.expected_reused_slots > args.expected_slots
        or args.timeout_seconds <= 0
    ):
        parser.error("numeric scenario arguments are outside their fixed bounds")
    if args.interval_minutes == -1 and args.expected_slots != 1:
        parser.error("whole mode requires exactly one expected slot")
    if args.flat_fallback and args.unserved_only:
        parser.error("provider scenario modes are mutually exclusive")
    if args.resume and (args.flat_fallback or args.unserved_only):
        parser.error("fixed provider failure scenarios are fresh-only")
    if args.unserved_only and args.expected_current_calls != 0:
        parser.error("unserved-only expects zero generation calls")
    return args


def _provider_mode(args: argparse.Namespace) -> str:
    if args.flat_fallback:
        return "flat_fallback"
    if args.unserved_only:
        return "unserved_only"
    return "scalar"


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


if __name__ == "__main__":
    raise SystemExit(main())
