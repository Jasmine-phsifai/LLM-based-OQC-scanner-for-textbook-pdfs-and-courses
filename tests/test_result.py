"""Tests for immutable, JSON-safe public recognition results."""

from __future__ import annotations

import math

import pytest

from ocrllm import RecognitionResult


def test_result_metadata_is_deep_copied_and_recursively_immutable():
    caller_metadata = {
        "nested": {"values": [1, 2]},
        "finite": 1.25,
    }

    result = RecognitionResult(
        markdown="# Board\n",
        source_type="image",
        profile="board",
        metadata=caller_metadata,
    )
    caller_metadata["nested"]["values"].append(3)

    assert result.metadata["nested"]["values"] == (1, 2)
    with pytest.raises(TypeError):
        result.metadata["new"] = "value"
    with pytest.raises(TypeError):
        result.metadata["nested"]["new"] = "value"
    with pytest.raises(AttributeError):
        result.metadata["nested"]["values"].append(4)


@pytest.mark.parametrize("invalid_value", [math.inf, -math.inf, math.nan, object()])
def test_result_metadata_rejects_non_json_values(invalid_value):
    with pytest.raises(ValueError):
        RecognitionResult(
            markdown="# Board\n",
            source_type="image",
            metadata={"invalid": invalid_value},
        )


def test_result_metadata_rejects_reference_cycles():
    cyclic: dict[str, object] = {}
    cyclic["self"] = cyclic

    with pytest.raises(ValueError):
        RecognitionResult(
            markdown="# Board\n",
            source_type="image",
            metadata=cyclic,
        )


def test_result_rejects_board_as_a_transport_media_type():
    with pytest.raises(ValueError, match="canonical media type"):
        RecognitionResult(
            markdown="# Board\n",
            source_type="board",  # type: ignore[arg-type]
            profile="board",
        )


def test_result_constructor_is_keyword_only_to_avoid_positional_field_rebinding():
    with pytest.raises(TypeError):
        RecognitionResult("# Board\n", "image", None)  # type: ignore[misc]


def test_result_preserves_one_shot_hotwords_and_warnings():
    result = RecognitionResult(
        markdown="# Board\n",
        source_type="image",
        hotwords=iter(("gene", "protein")),  # type: ignore[arg-type]
        warnings=iter(("faint", "cropped")),  # type: ignore[arg-type]
    )

    assert result.hotwords == ("gene", "protein")
    assert result.warnings == ("faint", "cropped")
