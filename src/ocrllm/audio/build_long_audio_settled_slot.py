"""Build one reusable paid long-audio slot."""

from __future__ import annotations

import hashlib

from ..processor_output import ProcessorOutput
from .long_audio_settled_slot import LongAudioSettledSlot


def build_long_audio_settled_slot(
    output: ProcessorOutput,
    *,
    window_index: int,
    request_fingerprint: str,
) -> LongAudioSettledSlot:
    """Keep the exact transcript, usage, and cleanup result of one call."""
    usage = output.metadata["current_model_token_usage"][0]
    return LongAudioSettledSlot(
        window_index=window_index,
        request_fingerprint=request_fingerprint,
        markdown=output.markdown,
        markdown_sha256=hashlib.sha256(output.markdown.encode("utf-8")).hexdigest(),
        provider=output.metadata["provider"],
        model=output.metadata["model"],
        transport=output.metadata["transport"],
        provider_calls_attempted=output.metadata["provider_call_count"],
        input_tokens=usage["input_tokens"],
        output_tokens=usage["output_tokens"],
        status=output.status,
        warnings=output.warnings,
        provider_file_cleanup_succeeded=output.metadata["remote_file_deleted"],
        provider_client_cleanup_succeeded=output.metadata["provider_client_closed"],
    )
