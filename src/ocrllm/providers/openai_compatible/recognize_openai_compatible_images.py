"""Recognize one image group through compatible Chat Completions."""

from __future__ import annotations

from ...errors import OCRLLMError
from ..vision_provider_response import VisionProviderResponse
from .build_openai_compatible_image_request import (
    build_openai_compatible_image_request,
)
from .call_openai_compatible_chat import call_openai_compatible_chat
from .parse_openai_compatible_chat_response import (
    parse_openai_compatible_chat_response,
)
from .provider_settings import OpenAICompatibleSettings


def recognize_openai_compatible_images(
    image_paths,
    *,
    prompt: str,
    vendor: str,
    model: str,
    settings: OpenAICompatibleSettings,
    timeout_seconds: float,
) -> VisionProviderResponse:
    """Return one parsed image response with no adapter-owned retry."""
    try:
        request = build_openai_compatible_image_request(
            image_paths,
            prompt=prompt,
            model=model,
        )
    except OCRLLMError as error:
        if "provider_calls_attempted" not in error.details:
            error._add_safe_detail("provider_calls_attempted", 0)
        raise
    call = call_openai_compatible_chat(
        request.kwargs,
        vendor=vendor,
        model=model,
        settings=settings,
        timeout_seconds=timeout_seconds,
    )
    try:
        parsed = parse_openai_compatible_chat_response(
            call.response,
            vendor=vendor,
            model=model,
        )
    except OCRLLMError as error:
        error._add_safe_detail("provider_calls_attempted", 1)
        if not call.client_closed:
            error._add_safe_detail("provider_client_closed", False)
        raise
    return VisionProviderResponse(
        markdown=parsed.text,
        input_tokens=parsed.input_tokens,
        output_tokens=parsed.output_tokens,
        client_closed=call.client_closed,
        request_id=parsed.request_id,
    )
