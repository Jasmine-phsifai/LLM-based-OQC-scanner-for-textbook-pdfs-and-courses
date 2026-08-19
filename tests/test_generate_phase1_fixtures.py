"""Protect the deterministic Phase 1 fixture-generation contract."""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from PIL import Image, ImageFont

from tests.quality.generators.generate_phase1_fixtures import (
    GENERATED_FILENAMES,
    MAX_CHANGED_PIXEL_FRACTION,
    MAX_MEAN_CHANNEL_DELTA,
    generator_environment_matches,
    measure_pixel_drift,
)
from tests.quality.generators.load_quality_font import (
    FONT_BYTES,
    FONT_SHA256,
)
from tests.quality.generators.phase1_fixture_content import (
    CANONICAL_FORMULAS,
    FORMULA_ORDER_ANCHOR,
    SLIDE_CARDS,
    SLIDE_ORDER_ANCHOR,
    SLIDE_SUBTITLE,
    SLIDE_TITLE,
    TABLE_HEADERS,
    TABLE_ROWS,
    TABLE_TITLE,
    VISIBLE_FORMULAS,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
PHASE1_ROOT = REPOSITORY_ROOT / "tests" / "fixtures" / "phase1"
IMAGE_DIRECTORY = PHASE1_ROOT / "images"
FONT_DIRECTORY = REPOSITORY_ROOT / "tests" / "quality" / "assets" / "fonts"
GENERATOR_DIRECTORY = REPOSITORY_ROOT / "tests" / "quality" / "generators"
CORPUS_LIMIT_BYTES = 25 * 1024 * 1024

EXPECTED_IMAGE_ARTIFACTS = {
    "bilingual_printed_slide.png": {
        "bytes": 269_337,
        "sha256": "5c1d8b7c4de3aa469007b0da0fba8c42a1646226854651a10f244591d57f7696",
        "format": "PNG",
        "mode": "RGB",
        "size": (2560, 1440),
        "rgb_sha256": "130b9c856cdae134b499a49a6d5788abd03324013106d381c82c6a2ea36327c4",
    },
    "bilingual_printed_slide_projected.jpg": {
        "bytes": 328_537,
        "sha256": "f3c906cab2755eee3dc9b6291bc06da188008c02a1e6a55c73304993a6f1d7f4",
        "format": "JPEG",
        "mode": "RGB",
        "size": (2880, 1800),
        "rgb_sha256": "e1ce6caacc4efe068e6d8093e2c554d478852d257f86fa4d0c6e4fa3c0c1e361",
    },
    "formula_board.png": {
        "bytes": 116_507,
        "sha256": "b329e0734d406e8a02404a66df0f8178a7b7ee7335818aa6bea42a236a8ecb7b",
        "format": "PNG",
        "mode": "RGB",
        "size": (2560, 1600),
        "rgb_sha256": "702080e7d0fee25a1fc5fe7d990fc724485aec2003f374cc28984f3b4bb0eced",
    },
    "calibration_table.png": {
        "bytes": 98_496,
        "sha256": "f5c3834984653559add7bec7b9b64eba39937dcfd388b516a9b4607ef4d2ef18",
        "format": "PNG",
        "mode": "RGB",
        "size": (2560, 1440),
        "rgb_sha256": "cedce02e10d3f38c3db90722426f2f8e3da900163d5c0e9f2acb5e0e5793d38d",
    },
    "handwritten_whiteboard.jpg": {
        "bytes": 593_407,
        "sha256": "bcb0dcbf3c62fdecab3f01d32a30cfe0d6ded9f676edcae7a2e4109248908b1d",
        "format": "JPEG",
        "mode": "RGB",
        "size": (2560, 1920),
        "rgb_sha256": "dfeff41c74e5c0e39b3c79ffcffb116e2dc379365aca5797c98d40087d15a29c",
    },
}

EXPECTED_SUPPORT_ARTIFACTS = {
    "NotoSansCJKsc-Regular.otf": (
        FONT_BYTES,
        FONT_SHA256,
    ),
    "OFL-1.1.txt": (
        4_599,
        "1d361a8f8e8ce6e68457dcd93fb56e162e6baa3bbb7e7573a290d44399f6b57e",
    ),
    "provenance.json": (
        1_000,
        "990c4c4731066146718aa367599d64976a854cc596592d291c1ba13b08c1e47a",
    ),
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _run_generator_cli(*arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "tests.quality.generators.generate_phase1_fixtures",
            *arguments,
        ],
        cwd=REPOSITORY_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def test_generator_cli_check_verifies_committed_fixtures() -> None:
    completed = _run_generator_cli(
        "--check",
        "--output-directory",
        str(IMAGE_DIRECTORY),
    )

    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert completed.stderr == ""
    if generator_environment_matches():
        assert completed.stdout.strip() == (
            "Phase 1 generated fixtures are byte-identical."
        )
    else:
        assert completed.stdout.startswith(
            "Phase 1 generated fixtures verified: pixel-equivalent"
        )


def test_generator_cli_write_emits_expected_fixtures(tmp_path: Path) -> None:
    completed = _run_generator_cli(
        "--write",
        "--output-directory",
        str(tmp_path),
    )

    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert completed.stderr == ""
    assert {path.name for path in tmp_path.iterdir()} == set(GENERATED_FILENAMES)
    printed_lines = completed.stdout.splitlines()
    assert len(printed_lines) == len(GENERATED_FILENAMES)
    for line, name in zip(printed_lines, GENERATED_FILENAMES):
        printed_name, _, printed_sha256 = line.partition(" ")
        assert printed_name == name
        assert len(printed_sha256) == 64
        assert all(character in "0123456789abcdef" for character in printed_sha256)
    for line, filename in zip(printed_lines, GENERATED_FILENAMES):
        generated = tmp_path / filename
        committed = IMAGE_DIRECTORY / filename
        if generator_environment_matches():
            assert line == f"{filename} {EXPECTED_IMAGE_ARTIFACTS[filename]['sha256']}"
            assert generated.read_bytes() == committed.read_bytes()
        else:
            drift = measure_pixel_drift(generated, committed)
            assert drift.changed_fraction <= MAX_CHANGED_PIXEL_FRACTION
            assert drift.mean_channel_delta <= MAX_MEAN_CHANNEL_DELTA


def test_generator_cli_check_rejects_one_byte_of_drift(tmp_path: Path) -> None:
    for filename in GENERATED_FILENAMES:
        shutil.copyfile(IMAGE_DIRECTORY / filename, tmp_path / filename)
    drifted_path = tmp_path / GENERATED_FILENAMES[0]
    drifted_path.write_bytes(drifted_path.read_bytes() + b"drift")

    completed = _run_generator_cli(
        "--check",
        "--output-directory",
        str(tmp_path),
    )

    assert completed.returncode != 0
    assert f"fixture bytes drifted: {drifted_path.name}" in completed.stderr


@pytest.mark.parametrize("filename", tuple(EXPECTED_IMAGE_ARTIFACTS))
def test_phase1_image_artifact_is_hash_and_pixel_pinned(filename: str) -> None:
    expected = EXPECTED_IMAGE_ARTIFACTS[filename]
    image_path = IMAGE_DIRECTORY / filename

    assert image_path.stat().st_size == expected["bytes"]
    assert _sha256(image_path) == expected["sha256"]
    with Image.open(image_path) as image:
        image.load()
        assert image.format == expected["format"]
        assert image.mode == expected["mode"]
        assert image.size == expected["size"]
        assert hashlib.sha256(image.tobytes()).hexdigest() == expected["rgb_sha256"]


def test_font_license_and_provenance_are_hash_pinned() -> None:
    assert {path.name for path in FONT_DIRECTORY.iterdir()} == set(
        EXPECTED_SUPPORT_ARTIFACTS
    )
    for filename, (expected_bytes, expected_sha256) in (
        EXPECTED_SUPPORT_ARTIFACTS.items()
    ):
        path = FONT_DIRECTORY / filename
        assert path.stat().st_size == expected_bytes
        assert _sha256(path) == expected_sha256

    provenance_path = FONT_DIRECTORY / "provenance.json"
    provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
    assert provenance["artifact_bytes"] == FONT_BYTES
    assert provenance["artifact_sha256"] == FONT_SHA256
    assert provenance["artifact_path"] == (
        "tests/quality/assets/fonts/NotoSansCJKsc-Regular.otf"
    )
    assert provenance["license_spdx"] == "OFL-1.1"
    assert provenance["license_path"] == "tests/quality/assets/fonts/OFL-1.1.txt"

    license_text = (FONT_DIRECTORY / "OFL-1.1.txt").read_text(encoding="utf-8")
    assert "SIL OPEN FONT LICENSE Version 1.1 - 26 February 2007" in license_text
    font = ImageFont.truetype(FONT_DIRECTORY / "NotoSansCJKsc-Regular.otf", size=24)
    assert font.getname() == ("Noto Sans CJK SC", "Regular")


def test_whiteboard_provenance_matches_committed_derivative() -> None:
    provenance_path = PHASE1_ROOT / "licenses" / "handwritten_whiteboard_provenance.json"
    assert _sha256(provenance_path) == (
        "6e2abcb00a37ce273945c1e67f803ddf999737ff5a771d1761459427a99d9cb9"
    )
    provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
    expected = EXPECTED_IMAGE_ARTIFACTS["handwritten_whiteboard.jpg"]

    assert provenance["license_spdx"] == "CC0-1.0"
    assert provenance["redistribution"] == "allowed"
    assert provenance["fixture_path"] == (
        "tests/fixtures/phase1/images/handwritten_whiteboard.jpg"
    )
    assert provenance["fixture_bytes"] == expected["bytes"]
    assert provenance["fixture_sha256"] == expected["sha256"]
    assert (provenance["fixture_width"], provenance["fixture_height"]) == expected[
        "size"
    ]

    license_path = REPOSITORY_ROOT / provenance["license_path"]
    assert license_path.stat().st_size == 7_048
    assert _sha256(license_path) == provenance["license_sha256"]
    assert provenance["license_sha256"] == (
        "a2010f343487d3f7618affe54f789f5487602331c0a8d03f49e9a7c547cf0499"
    )

    permission_path = PHASE1_ROOT / "licenses" / "repo_owned_fixture_data.md"
    assert _sha256(permission_path) == (
        "335b08e0a4934db20b528deb6517a0d760841ea3e4d2fd000be0509c080502a6"
    )
    assert "LicenseRef-OCRLLM-Repo-Owned-Test-Data" in permission_path.read_text(
        encoding="utf-8"
    )


def test_generated_content_meets_phase1_fixture_minimums() -> None:
    slide_units = (SLIDE_TITLE, SLIDE_SUBTITLE, SLIDE_ORDER_ANCHOR) + tuple(
        line for card in SLIDE_CARDS for line in card
    )
    assert len(SLIDE_CARDS) == 8
    assert all(len(card) == 6 for card in SLIDE_CARDS)
    assert len(slide_units) == 51
    assert len(set(card[-1] for card in SLIDE_CARDS)) == 8
    assert any("\u4e00" <= character <= "\u9fff" for character in slide_units[1])

    assert len(VISIBLE_FORMULAS) == len(CANONICAL_FORMULAS) == 12
    assert [formula_id for formula_id, _ in VISIBLE_FORMULAS] == [
        formula_id for formula_id, _ in CANONICAL_FORMULAS
    ]
    canonical_text = "\n".join(formula for _, formula in CANONICAL_FORMULAS)
    for required_syntax in ("_{", "^{", r"\le", r"\ge", r"\times", "-"):
        assert required_syntax in canonical_text

    assert len(TABLE_HEADERS) == 6
    assert len(TABLE_ROWS) == 5
    assert all(len(row) == len(TABLE_HEADERS) for row in TABLE_ROWS)
    assert len(TABLE_ROWS) * (len(TABLE_HEADERS) - 1) == 25
    assert any("\u4e00" <= character <= "\u9fff" for character in TABLE_TITLE)

    assert SLIDE_ORDER_ANCHOR.startswith("ORDER-FIRST:")
    assert FORMULA_ORDER_ANCHOR.startswith("ORDER-LAST:")
    assert SLIDE_ORDER_ANCHOR != FORMULA_ORDER_ANCHOR


def test_complete_phase1_corpus_stays_below_25_mib() -> None:
    artifact_roots = (PHASE1_ROOT, FONT_DIRECTORY, GENERATOR_DIRECTORY)
    artifacts = [
        path
        for root in artifact_roots
        for path in root.rglob("*")
        if path.is_file() and "__pycache__" not in path.parts
    ]
    assert artifacts
    assert not [path for path in artifacts if path.is_symlink()]

    total_bytes = sum(path.stat().st_size for path in artifacts)
    assert total_bytes <= CORPUS_LIMIT_BYTES, (
        f"Phase 1 corpus/support artifacts use {total_bytes:,} bytes; "
        f"limit is {CORPUS_LIMIT_BYTES:,} bytes"
    )
