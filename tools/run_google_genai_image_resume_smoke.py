"""Prove one bounded Google image cancellation and partial resume."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from ocrllm import (
    Config,
    GoogleGenAISettings,
    RecognitionPreferences,
    VisionModelSettings,
    recognize,
)
from ocrllm.errors import Cancelled, ConfigError, OCRLLMError


def parse_arguments(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse one explicit eight-image cancellation/resume gate."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", required=True)
    parser.add_argument(
        "--image",
        required=True,
        type=Path,
        nargs=8,
        metavar="IMAGE",
        help="exactly eight explicit image paths",
    )
    parser.add_argument("--timeout", type=float, default=120.0)
    return parser.parse_args(argv)


class _CheckpointAwareCancellation:
    """Cancel only after the expected draft slot is durably visible."""

    def __init__(self, state_path: Path, model: str) -> None:
        self._state_path = state_path
        self._model = model
        self.observed_draft = False
        self.observation_invalid = False

    def is_set(self) -> bool:
        if not self._state_path.is_file():
            return False
        try:
            document = json.loads(self._state_path.read_text(encoding="utf-8"))
            slots = document["slots"]
            result = document["result"]
            self.observed_draft = (
                document["state_version"] == "ocrllm.image-resume.v2"
                and result["status"] == "partial"
                and result["markdown"] == ""
                and len(slots) == 1
                and slots[0]["slot_id"] == "draft"
                and slots[0]["workflow_pass"] == "draft"
                and slots[0]["provider"] == "google"
                and slots[0]["model"] == self._model
                and slots[0]["provider_calls_attempted"] == 1
            )
        except Exception:
            self.observation_invalid = True
            return True
        if not self.observed_draft:
            self.observation_invalid = True
        return True


def run_google_genai_image_resume_smoke(
    arguments: argparse.Namespace,
) -> dict[str, object]:
    """Cancel after one settled draft, then resume only the missing review."""
    source_paths = tuple(Path(path) for path in arguments.image)
    if len(source_paths) != 8:
        raise ConfigError(
            "The Google resume live gate requires exactly eight images.",
            code="CONFIG_INVALID",
        ) from None
    settings = GoogleGenAISettings()
    preferences = RecognitionPreferences(review_passes=1)

    with tempfile.TemporaryDirectory(prefix="ocrllm-google-resume-") as temporary:
        temporary_root = Path(temporary)
        input_dir = temporary_root / "input"
        output_dir = temporary_root / "output"
        snapshot_dir = temporary_root / "snapshots"
        input_dir.mkdir()
        copied_paths = _copy_inputs(source_paths, input_dir)
        state_path = output_dir / "image-01_plus_7_board.ocrllm-state.json"
        cancellation = _CheckpointAwareCancellation(state_path, arguments.model)

        try:
            recognize(
                copied_paths,
                config=Config(
                    provider=settings,
                    vision_model=VisionModelSettings(name=arguments.model),
                    preferences=preferences,
                    output_dir=output_dir,
                    temp_dir=snapshot_dir,
                    timeout_seconds=arguments.timeout,
                    cancellation=cancellation,
                ),
            )
        except Cancelled as error:
            interrupted = _safe_interrupted_summary(error, arguments.model)
        else:
            raise ConfigError(
                "The Google resume live gate did not cancel before review.",
                code="CONFIG_INVALID",
            ) from None
        if not cancellation.observed_draft or cancellation.observation_invalid:
            raise ConfigError(
                "The Google resume live gate did not observe the expected checkpoint.",
                code="CONFIG_INVALID",
            ) from None
        partial = _safe_partial_summary(state_path, arguments.model)

        resumed_result = recognize(
            copied_paths,
            config=Config(
                provider=settings,
                vision_model=VisionModelSettings(name=arguments.model),
                preferences=preferences,
                output_dir=output_dir,
                temp_dir=snapshot_dir,
                timeout_seconds=arguments.timeout,
                resume=True,
            ),
        )
        resumed = _safe_resumed_summary(
            resumed_result,
            arguments.model,
            state_path=state_path,
        )

    if temporary_root.exists():
        raise ConfigError(
            "The Google resume live gate temporary directory was not cleaned up.",
            code="CONFIG_INVALID",
        ) from None

    return {
        "status": "passed",
        "model": arguments.model,
        "interrupted": interrupted,
        "partial": partial,
        "resumed": resumed,
    }


def _copy_inputs(source_paths: tuple[Path, ...], input_dir: Path) -> tuple[Path, ...]:
    copied: list[Path] = []
    for index, source_path in enumerate(source_paths, start=1):
        destination = input_dir / f"image-{index:02d}{source_path.suffix.lower()}"
        shutil.copyfile(source_path, destination)
        copied.append(destination)
    return tuple(copied)


def _safe_interrupted_summary(error: Cancelled, model: str) -> dict[str, object]:
    if (
        error.code != "CANCELLED"
        or error.details.get("workflow_pass") != "review"
        or error.details.get("provider_calls_attempted") != 1
    ):
        raise ConfigError(
            "The Google resume live gate returned an unexpected cancellation.",
            code="CONFIG_INVALID",
        ) from None
    usage = _safe_settled_usage(error.details.get("settled_model_usage"), model)
    return {"code": error.code, "provider_call_count": 1, **usage}


def _safe_partial_summary(state_path: Path, model: str) -> dict[str, object]:
    try:
        document = json.loads(state_path.read_text(encoding="utf-8"))
        slots = document["slots"]
        result = document["result"]
        valid = (
            document["state_version"] == "ocrllm.image-resume.v2"
            and result["status"] == "partial"
            and result["markdown"] == ""
            and len(slots) == 1
            and slots[0]["slot_id"] == "draft"
            and slots[0]["provider"] == "google"
            and slots[0]["model"] == model
            and slots[0]["provider_calls_attempted"] == 1
        )
    except Exception:
        valid = False
    if not valid:
        raise ConfigError(
            "The Google resume live gate found an unexpected partial checkpoint.",
            code="CONFIG_INVALID",
        ) from None
    return {"slot_count": 1, "status": "partial"}


def _safe_resumed_summary(
    result: Any,
    model: str,
    *,
    state_path: Path | None = None,
) -> dict[str, object]:
    metadata = getattr(result, "metadata", None)
    if not isinstance(metadata, Mapping):
        raise ConfigError(
            "The Google resume live gate returned unexpected resume evidence.",
            code="CONFIG_INVALID",
        ) from None
    slots = metadata.get("workflow_slots")
    if (
        getattr(result, "source_type", None) != "image"
        or getattr(result, "output_path", None) is None
        or metadata.get("provider") != "google"
        or metadata.get("model") != model
        or metadata.get("provider_call_count") != 1
        or type(slots) is not tuple
        or len(slots) != 2
        or not all(isinstance(slot, Mapping) for slot in slots)
        or slots[0].get("slot_id") != "draft"
        or slots[0].get("reused") is not True
        or slots[0].get("provider_calls_attempted") != 0
        or slots[1].get("slot_id") != "review"
        or slots[1].get("reused") is not False
        or slots[1].get("provider_calls_attempted") != 1
    ):
        raise ConfigError(
            "The Google resume live gate returned unexpected resume evidence.",
            code="CONFIG_INVALID",
        ) from None
    usage = _safe_usage(metadata.get("current_model_token_usage"), model)
    checkpoint_status, output_published = _safe_completed_publication(
        result,
        model,
        state_path=state_path,
    )
    return {
        "checkpoint_status": checkpoint_status,
        "output_published": output_published,
        "provider_call_count": 1,
        "reused_slot_count": 1,
        "fresh_slot_count": 1,
        **usage,
    }


def _safe_completed_publication(
    result: Any,
    model: str,
    *,
    state_path: Path | None,
) -> tuple[str, bool]:
    output_path = Path(result.output_path)
    if state_path is None:
        state_path = output_path.with_name(f"{output_path.stem}.ocrllm-state.json")
    try:
        document = json.loads(state_path.read_text(encoding="utf-8"))
        slots = document["slots"]
        state_result = document["result"]
        valid = (
            document["state_version"] == "ocrllm.image-resume.v2"
            and state_result["status"] == "complete"
            and type(state_result["markdown"]) is str
            and bool(state_result["markdown"].strip())
            and len(slots) == 2
            and [slot["slot_id"] for slot in slots] == ["draft", "review"]
            and all(slot["provider"] == "google" for slot in slots)
            and all(slot["model"] == model for slot in slots)
        )
    except Exception:
        valid = False
    if not valid or not output_path.is_file():
        raise ConfigError(
            "The Google resume live gate found an incomplete final publication.",
            code="CONFIG_INVALID",
        ) from None
    return "complete", True


def _safe_settled_usage(value: object, model: str) -> dict[str, int | None]:
    if (
        type(value) is not tuple
        or len(value) != 1
        or not isinstance(value[0], Mapping)
        or frozenset(value[0]) != {"model", "input_count", "output_count", "unit"}
        or value[0].get("model") != model
        or value[0].get("unit") != "tokens"
    ):
        raise ConfigError(
            "The Google resume live gate returned unexpected settled usage evidence.",
            code="CONFIG_INVALID",
        ) from None
    input_count = value[0].get("input_count")
    output_count = value[0].get("output_count")
    if not _is_optional_token_count(input_count) or not _is_optional_token_count(
        output_count
    ):
        raise ConfigError(
            "The Google resume live gate returned invalid settled usage evidence.",
            code="CONFIG_INVALID",
        ) from None
    return {"input_tokens": input_count, "output_tokens": output_count}


def _safe_usage(value: object, model: str) -> dict[str, int | None]:
    if (
        type(value) is not tuple
        or len(value) != 1
        or not isinstance(value[0], Mapping)
        or value[0].get("model") != model
    ):
        raise ConfigError(
            "The Google resume live gate returned unexpected usage evidence.",
            code="CONFIG_INVALID",
        ) from None
    input_tokens = value[0].get("input_tokens")
    output_tokens = value[0].get("output_tokens")
    if not _is_optional_token_count(input_tokens) or not _is_optional_token_count(
        output_tokens
    ):
        raise ConfigError(
            "The Google resume live gate returned invalid usage evidence.",
            code="CONFIG_INVALID",
        ) from None
    return {"input_tokens": input_tokens, "output_tokens": output_tokens}


def _is_optional_token_count(value: object) -> bool:
    return value is None or (type(value) is int and value >= 0)


def _safe_failure_summary(error: OCRLLMError) -> dict[str, object]:
    return {
        "status": "failed",
        "error": {
            "code": error.code,
            "scope": error.details.get("failure_scope"),
        },
    }


def main(argv: Sequence[str] | None = None) -> int:
    arguments = parse_arguments(argv)
    try:
        summary = run_google_genai_image_resume_smoke(arguments)
    except OCRLLMError as error:
        summary = _safe_failure_summary(error)
        print(json.dumps(summary, sort_keys=True, separators=(",", ":")))
        return 1
    except Exception:
        print(
            json.dumps(
                {"status": "failed", "error": {"code": "UNEXPECTED_SAFE_FAILURE"}},
                sort_keys=True,
                separators=(",", ":"),
            )
        )
        return 1
    print(json.dumps(summary, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
