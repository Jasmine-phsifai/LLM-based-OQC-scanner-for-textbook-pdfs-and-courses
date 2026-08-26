"""Recognize and persist one ordered long-MP3 interval plan."""

from __future__ import annotations

from pathlib import Path

from ..audio.build_long_audio_interval_prompt import build_long_audio_interval_prompt
from ..audio.build_long_audio_interval_upload_snapshot import (
    build_long_audio_interval_upload_snapshot,
)
from ..audio.build_long_audio_interval_windows import build_long_audio_interval_windows
from ..audio.build_long_audio_no_speech_slot import build_long_audio_no_speech_slot
from ..audio.build_long_audio_settled_slot import build_long_audio_settled_slot
from ..audio.compose_long_audio_interval_output import (
    compose_long_audio_interval_output,
)
from ..audio.fingerprint_long_audio_request import (
    LONG_AUDIO_REQUEST_IDENTITY_VERSION,
    fingerprint_long_audio_request,
)
from ..audio.long_audio_partial_state import (
    LONG_AUDIO_PARTIAL_STATE_VERSION,
    LongAudioPartialState,
)
from ..audio.materialize_long_audio_interval import materialize_long_audio_interval
from ..audio.reuse_long_audio_partial_state import reuse_long_audio_partial_state
from ..audio.save_long_audio_partial_state_atomically import (
    save_long_audio_partial_state_atomically,
)
from ..errors import NoSpeechDetected, OCRLLMError
from ..providers.google_genai.recognize_uploaded_mp3 import recognize_uploaded_mp3
from ..raise_if_cancelled import raise_if_cancelled
from .build_long_mp3_processor_output import build_long_mp3_processor_output


def recognize_long_mp3_intervals(
    snapshot,
    *,
    config,
    interval_minutes: int,
    state_path: Path,
    saved_state,
):
    """Dispatch missing windows serially and save each paid prefix."""
    model = config.audio_model.name
    assert type(model) is str
    windows = build_long_audio_interval_windows(
        duration_seconds=snapshot.duration_seconds,
        interval_minutes=interval_minutes,
    )
    plan = tuple(
        fingerprint_long_audio_request(
            source_sha256=snapshot.sha256,
            mode="interval",
            provider="google",
            model=model,
            transport="google_files",
            window=window,
        )
        for window in windows
    )
    slots = (
        ()
        if saved_state is None
        else reuse_long_audio_partial_state(saved_state, plan)
    )
    current_calls = 0
    current_usage: list[tuple[int | None, int | None]] = []
    for window in windows[len(slots) :]:
        raise_if_cancelled(config.cancellation)
        try:
            with materialize_long_audio_interval(
                snapshot.path,
                window=window,
            ) as segment:
                upload = build_long_audio_interval_upload_snapshot(
                    segment,
                    duration_seconds=(
                        window.actual_end_seconds - window.actual_start_seconds
                    ),
                )
                try:
                    response = recognize_uploaded_mp3(
                        upload,
                        prompt=build_long_audio_interval_prompt(window),
                        config=config,
                    )
                    current_calls += 1
                    output = build_long_mp3_processor_output(
                        upload,
                        response,
                        config=config,
                    )
                    slot = build_long_audio_settled_slot(
                        output,
                        window_index=window.index,
                        request_fingerprint=plan[window.index],
                    )
                    current_usage.append(
                        (response.input_tokens, response.output_tokens)
                    )
                except NoSpeechDetected as error:
                    current_calls += error.details.get("provider_calls_attempted", 1)
                    slot = build_long_audio_no_speech_slot(
                        window_index=window.index,
                        request_fingerprint=plan[window.index],
                        model=model,
                        error=error,
                    )
                    current_usage.append((None, None))
                except OCRLLMError as error:
                    attempted = error.details.get("provider_calls_attempted", 0)
                    error._add_safe_detail(
                        "provider_calls_attempted",
                        current_calls + attempted,
                    )
                    raise
                slots = slots + (slot,)
                save_long_audio_partial_state_atomically(
                    state_path,
                    LongAudioPartialState(
                        state_version=LONG_AUDIO_PARTIAL_STATE_VERSION,
                        identity_version=LONG_AUDIO_REQUEST_IDENTITY_VERSION,
                        mode="interval",
                        interval_minutes=interval_minutes,
                        request_fingerprints=plan,
                        slots=slots,
                    ),
                )
        except OCRLLMError as error:
            if "provider_calls_attempted" not in error.details:
                error._add_safe_detail("provider_calls_attempted", current_calls)
            raise
    return compose_long_audio_interval_output(
        snapshot,
        slots,
        current_calls=current_calls,
        current_usage=tuple(current_usage),
    ), current_calls
