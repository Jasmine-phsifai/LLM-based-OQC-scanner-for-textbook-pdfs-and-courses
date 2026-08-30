"""Credential-free presets for image models proven through live calls."""

from __future__ import annotations

from typing import Final

from .dashscope.provider_settings import DashScopeSettings
from .google_genai.provider_settings import GoogleGenAISettings
from .provider_model import ProviderModel


GOOGLE_GEMINI_2_5_FLASH: Final = ProviderModel(
    vendor="google",
    model="gemini-2.5-flash",
    adapter_id="google_genai",
    settings=GoogleGenAISettings(),
)

DASHSCOPE_QWEN3_5_OCR_CN_BEIJING: Final = ProviderModel(
    vendor="dashscope",
    model="qwen3.5-ocr",
    adapter_id="dashscope_openai_compatible",
    settings=DashScopeSettings.for_region("cn-beijing"),
)
