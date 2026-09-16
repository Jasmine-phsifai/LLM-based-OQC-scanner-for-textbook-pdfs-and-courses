"""Run one bounded Codex CLI image-batch live smoke."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from ocrllm import (
    CodexCLISettings,
    Config,
    RecognitionExecutionPolicy,
    VisionModelSettings,
)
from ocrllm.errors import ConfigError, OCRLLMError, ProviderError
from ocrllm.processor_output import ProcessorOutput
from ocrllm.processors.recognize_images import recognize_images
from ocrllm.provider_error_disposition import get_provider_error_disposition


def parse_arguments(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse one explicit image batch and Codex CLI model selection."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", required=True, action="append", type=Path)
    parser.add_argument("--model", default="gpt-5.6-luna")
    parser.add_argument("--effort", default="low")
    parser.add_argument("--timeout", type=float, default=1800.0)
    parser.add_argument("--fast", action="store_true")
    return parser.parse_args(argv)


def run_codex_cli_image_smoke(arguments: argparse.Namespace) -> dict[str, object]:
    """Perform exactly one Codex CLI batch recognition call."""
    images = tuple(arguments.image)
    config = Config(
        provider=CodexCLISettings(
            model=arguments.model,
            reasoning_effort=arguments.effort,
            fast_mode=arguments.fast,
            timeout_seconds=arguments.timeout,
            max_images_per_call=len(images),
        ),
        vision_model=VisionModelSettings(name=arguments.model),
        execution=RecognitionExecutionPolicy(maximum_images_per_request=len(images)),
    )
    output = recognize_images(images, profile="board", config=config)
    return {
        "status": "passed",
        "recognition": _safe_recognition_summary(
            output,
            model=arguments.model,
            image_count=len(images),
        ),
    }


def _safe_recognition_summary(
    output: ProcessorOutput,
    *,
    model: str,
    image_count: int,
) -> dict[str, object]:
    """Validate one-call evidence without exposing recognized content."""
    metadata = output.metadata
    if (
        output.status != "complete"
        or metadata.get("provider") != "codex_cli"
        or metadata.get("model") != model
        or metadata.get("image_count") != image_count
        or metadata.get("provider_call_count") != 1
    ):
        raise ConfigError(
            "Codex CLI live recognition returned unexpected result identity.",
            code="CONFIG_INVALID",
        ) from None
    return {
        "model": model,
        "image_count": image_count,
        "provider_call_count": 1,
        "markdown_chars": len(output.markdown),
    }


def main(argv: Sequence[str] | None = None) -> int:
    arguments = parse_arguments(argv)
    try:
        summary = run_codex_cli_image_smoke(arguments)
    except OCRLLMError as error:
        scope = (
            get_provider_error_disposition(error).scope
            if isinstance(error, ProviderError)
            else None
        )
        print(
            json.dumps(
                {"status": "failed", "error": {"code": error.code, "scope": scope}},
                sort_keys=True,
                separators=(",", ":"),
            )
        )
        return 1
    except Exception:
        print(
            json.dumps(
                {
                    "status": "failed",
                    "error": {"code": "UNEXPECTED_SAFE_FAILURE", "scope": None},
                },
                sort_keys=True,
                separators=(",", ":"),
            )
        )
        return 1
    print(json.dumps(summary, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
