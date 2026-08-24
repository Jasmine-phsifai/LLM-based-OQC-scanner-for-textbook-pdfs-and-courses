"""Shared prompt for exact speech-transcription routes."""

from ..providers.google_genai.parse_google_genai_audio_response import (
    NO_SPEECH_SENTINEL,
)


AUDIO_TRANSCRIPTION_PROMPT = (
    "Transcribe all speech in this audio faithfully as Markdown. Return only the "
    "transcript. If and only if the audio contains no speech, return exactly "
    f"{NO_SPEECH_SENTINEL}."
)
