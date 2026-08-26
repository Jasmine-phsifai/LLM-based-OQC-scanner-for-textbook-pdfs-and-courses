"""Canonical byte schema for long-audio partial state."""

from __future__ import annotations

import hashlib
import json

import pytest

from ocrllm.audio.fingerprint_long_audio_request import (
    LONG_AUDIO_REQUEST_IDENTITY_VERSION,
)
from ocrllm.audio.long_audio_partial_state import (
    LONG_AUDIO_PARTIAL_STATE_VERSION,
    LongAudioPartialState,
)
from ocrllm.audio.long_audio_settled_slot import LongAudioSettledSlot
from ocrllm.audio.parse_long_audio_partial_state import (
    parse_long_audio_partial_state,
)
from ocrllm.audio.serialize_long_audio_partial_state import (
    serialize_long_audio_partial_state,
)
from ocrllm.errors import ResumeStateError


REQUESTS = ("1" * 64, "2" * 64)


def _slot() -> LongAudioSettledSlot:
    markdown = "第一段语音：x² + y²"
    return LongAudioSettledSlot(
        window_index=0,
        request_fingerprint=REQUESTS[0],
        markdown=markdown,
        markdown_sha256=hashlib.sha256(markdown.encode("utf-8")).hexdigest(),
        provider="google",
        model="gemini-2.5-flash",
        transport="google_files",
        provider_calls_attempted=1,
        input_tokens=None,
        output_tokens=None,
        status="partial",
        warnings=("The provider client could not be closed.",),
        provider_file_cleanup_succeeded=True,
        provider_client_cleanup_succeeded=False,
    )


def _state() -> LongAudioPartialState:
    return LongAudioPartialState(
        state_version=LONG_AUDIO_PARTIAL_STATE_VERSION,
        identity_version=LONG_AUDIO_REQUEST_IDENTITY_VERSION,
        request_fingerprints=REQUESTS,
        slots=(_slot(),),
    )


def _document() -> dict[str, object]:
    return json.loads(serialize_long_audio_partial_state(_state()).decode("utf-8"))


def test_canonical_round_trip_preserves_order_unicode_null_usage_and_warning() -> None:
    state = _state()

    first = serialize_long_audio_partial_state(state)
    second = serialize_long_audio_partial_state(state)

    assert first == second
    assert first.endswith(b"\n")
    assert b": " not in first
    assert b", " not in first
    assert "第一段语音" in first.decode("utf-8")
    parsed = parse_long_audio_partial_state(first)
    assert parsed == state
    assert serialize_long_audio_partial_state(parsed) == first


def test_serialized_schema_contains_only_the_settled_state_fields() -> None:
    document = _document()

    assert set(document) == {
        "identity_version",
        "request_fingerprints",
        "slots",
        "state_version",
    }
    assert set(document["slots"][0]) == {
        "input_tokens",
        "markdown",
        "markdown_sha256",
        "model",
        "output_tokens",
        "provider",
        "provider_calls_attempted",
        "provider_client_cleanup_succeeded",
        "provider_file_cleanup_succeeded",
        "request_fingerprint",
        "status",
        "warnings",
        "transport",
        "window_index",
    }
    assert "path" not in _json_text(document)
    assert "metadata" not in _json_text(document)


@pytest.mark.parametrize(
    "mutate",
    [
        lambda document: document.__setitem__("unexpected", True),
        lambda document: document.pop("identity_version"),
        lambda document: document["slots"][0].__setitem__("unexpected", True),
        lambda document: document["slots"][0].pop("model"),
        lambda document: document["slots"][0].__setitem__(
            "markdown_sha256", "0" * 64
        ),
        lambda document: document.__setitem__(
            "state_version", "ocrllm.long-audio-partial.future"
        ),
    ],
)
def test_parser_rejects_schema_drift_and_invalid_slot_facts(mutate) -> None:
    document = _document()
    mutate(document)

    with pytest.raises(ResumeStateError) as captured:
        parse_long_audio_partial_state(json.dumps(document).encode("utf-8"))

    assert captured.value.code == "RESUME_STATE_INVALID"


def test_parser_rejects_duplicate_keys_and_nonfinite_numbers() -> None:
    valid = serialize_long_audio_partial_state(_state()).decode("utf-8").rstrip()
    duplicate = valid.replace(
        '"state_version":"ocrllm.long-audio-partial.v2"',
        '"state_version":"ocrllm.long-audio-partial.v2",'
        '"state_version":"ocrllm.long-audio-partial.v2"',
        1,
    )

    for raw in (duplicate.encode("utf-8"), b'{"value":NaN}'):
        with pytest.raises(ResumeStateError) as captured:
            parse_long_audio_partial_state(raw)
        assert captured.value.code == "RESUME_STATE_INVALID"


def test_serializer_requires_the_exact_validated_state_type() -> None:
    with pytest.raises(TypeError, match="LongAudioPartialState"):
        serialize_long_audio_partial_state(object())


def _json_text(document: object) -> str:
    return json.dumps(document, ensure_ascii=False, sort_keys=True)
