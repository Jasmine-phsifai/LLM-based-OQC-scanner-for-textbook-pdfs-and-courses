"""Offline contract tests for the bounded Google PDF live tool."""

from __future__ import annotations

import json
from pathlib import Path
from types import MappingProxyType, SimpleNamespace

import pytest

from ocrllm.pdf.inspect_pdf import inspect_pdf
from tools import run_google_genai_pdf_smoke as smoke
from write_test_image import write_test_image


MODEL = "gemini-test-model"


def test_pdf_live_tool_requires_exactly_sixteen_page_images() -> None:
    common = ["--model", MODEL]
    with pytest.raises(SystemExit):
        smoke.parse_arguments(
            [*common, *sum((["--page-image", f"{i}.png"] for i in range(15)), [])]
        )
    parsed = smoke.parse_arguments(
        [*common, *sum((["--page-image", f"{i}.png"] for i in range(16)), [])]
    )
    assert len(parsed.page_image) == 16


def test_pdf_live_fixture_has_sixteen_real_pdfium_pages(tmp_path: Path) -> None:
    image = write_test_image(tmp_path / "page.png")
    pdf_path = tmp_path / "fixture.pdf"

    smoke._build_pdf_from_images((image,) * 16, pdf_path)

    assert len(inspect_pdf(pdf_path)) == 16


def test_pdf_live_result_summary_excludes_markdown_and_paths(tmp_path: Path) -> None:
    output_directory = tmp_path / "output"
    state_directory = output_directory / "input_board"
    state_directory.mkdir(parents=True)
    output_path = output_directory / "input_board.md"
    private_markdown = (
        "<!-- ocrllm:pdf-pages start=1 end=8 -->\nPRIVATE ONE\n"
        "<!-- ocrllm:pdf-pages start=9 end=16 -->\nPRIVATE TWO\n"
    )
    output_path.write_text(private_markdown, encoding="utf-8")
    state = {
        "state_version": "ocrllm.image-resume.v2",
        "result": {"status": "complete"},
        "slots": [
            {
                "slot_id": "draft",
                "provider": "google",
                "model": MODEL,
                "provider_calls_attempted": 1,
            }
        ],
    }
    for index in range(2):
        (state_directory / f"group-{index}.ocrllm-state.json").write_text(
            json.dumps(state),
            encoding="utf-8",
        )
    result = SimpleNamespace(
        source_type="pdf",
        status="complete",
        markdown=private_markdown,
        output_path=output_path,
        metadata=MappingProxyType(
            {
                "provider": "google",
                "model": MODEL,
                "page_count": 16,
                "pdf_group_count": 2,
                "provider_call_count": 2,
                "current_run_provider_call_count": 2,
                "current_model_token_usage": (
                    {"model": MODEL, "input_tokens": 20, "output_tokens": 4},
                ),
            }
        ),
    )

    summary = smoke._safe_pdf_result_summary(
        result,
        model=MODEL,
        output_directory=output_directory,
    )

    serialized = json.dumps(summary)
    assert summary["provider_call_count"] == 2
    assert summary["checkpoint_count"] == 2
    assert "PRIVATE" not in serialized
    assert str(tmp_path) not in serialized
