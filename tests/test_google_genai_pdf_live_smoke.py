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
        [
            *common,
            "--route-a",
            *sum((["--page-image", f"{i}.png"] for i in range(16)), []),
        ]
    )
    assert len(parsed.page_image) == 16
    assert parsed.route_a is True


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
    output_path.write_bytes(private_markdown.encode("utf-8"))
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


def test_pdf_route_a_result_summary_excludes_markdown_and_paths(
    tmp_path: Path,
) -> None:
    page_directory = tmp_path / "pages"
    page_directory.mkdir()
    page_paths = tuple(
        write_test_image(page_directory / f"page-{page_number:06d}.png")
        for page_number in range(1, 17)
    )
    batches = (page_paths[:8], page_paths[8:])
    output_path = tmp_path / "output" / "input_board.md"
    output_path.parent.mkdir()
    private_markdown = (
        "## OCRLLM image slot 1 (1-8)\n\nPRIVATE ONE\n\n"
        "## OCRLLM image slot 2 (9-16)\n\nPRIVATE TWO\n"
    )
    output_path.write_bytes(private_markdown.encode("utf-8"))
    result = SimpleNamespace(
        source_type="image",
        profile=smoke.ROUTE_A_IMAGE_TASK,
        status="complete",
        markdown=private_markdown,
        output_path=output_path,
        warnings=(),
        metadata=MappingProxyType(
            {
                "slot_count": 2,
                "settled_slot_count": 2,
                "reused_slot_count": 0,
                "provider_call_count": 2,
                "historical_provider_model_usage": (),
                "current_provider_model_usage": (
                    {
                        "vendor": "google",
                        "model": MODEL,
                        "calls": 2,
                        "input_tokens": 20,
                        "output_tokens": 4,
                    },
                ),
            }
        ),
    )

    summary = smoke._safe_route_a_result_summary(
        result,
        model=MODEL,
        output_path=output_path,
        page_paths=page_paths,
        batches=batches,
    )

    serialized = json.dumps(summary)
    assert summary["page_count"] == 16
    assert summary["batch_count"] == 2
    assert summary["provider_call_count"] == 2
    assert summary["state_retained"] is False
    assert "PRIVATE" not in serialized
    assert str(tmp_path) not in serialized


def test_pdf_route_a_rejects_an_unproven_model_before_source_or_catalog_work() -> None:
    arguments = SimpleNamespace(
        page_image=[Path("missing.png")] * 16,
        model=MODEL,
        timeout=1.0,
        route_a=True,
    )

    with pytest.raises(smoke.ConfigError) as captured:
        smoke.run_google_genai_pdf_smoke(arguments)

    assert captured.value.code == "CONFIG_INVALID"
