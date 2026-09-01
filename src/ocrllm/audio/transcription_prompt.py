"""Shared prompt for exact speech-transcription routes."""

from .no_speech_sentinel import NO_SPEECH_SENTINEL


AUDIO_TRANSCRIPTION_PROMPT_VERSION = "audio.transcription.v1"


AUDIO_TRANSCRIPTION_PROMPT = (
    "Transcribe all speech in this audio faithfully as Markdown. Return only the "
    "transcript. If and only if the audio contains no speech, return exactly "
    f"{NO_SPEECH_SENTINEL}."
)
