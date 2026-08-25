"""Tests for immutable processor output normalization."""

from __future__ import annotations

from ocrllm.processor_output import ProcessorOutput


def test_processor_output_preserves_one_shot_hotwords_and_warnings():
    output = ProcessorOutput(
        media_type="image",
        markdown="# Board\n",
        hotwords=iter(("gene", "protein")),  # type: ignore[arg-type]
        warnings=iter(("faint", "cropped")),  # type: ignore[arg-type]
    )

    assert output.hotwords == ("gene", "protein")
    assert output.warnings == ("faint", "cropped")
