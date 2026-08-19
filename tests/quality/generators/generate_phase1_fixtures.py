"""Write or check all generated Phase 1 quality images.

The check runs three independent stages, each guarding a distinct property:

1. integrity — every committed file must match its manifest SHA-256. This is
   the tamper gate. It holds in every environment because it never
   regenerates anything.
2. determinism — two generations in the current environment must produce
   identical bytes. This catches nondeterminism inside the generator
   (iteration order, timestamps, temporary state). It holds in every
   environment.
3. reproduction — a fresh generation is compared with the committed corpus.
   Encoded PNG/JPEG bytes depend on the rasterizer and codec builds inside
   the Pillow wheel, so byte-identical output is required only when the
   current environment exactly matches GENERATOR_ENVIRONMENT. Any other
   environment is checked for decoded-pixel equivalence within the
   documented tolerance below.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

import PIL
from PIL import Image, ImageChops, features

from .generate_bilingual_slide import generate_bilingual_slide
from .generate_calibration_table import generate_calibration_table
from .generate_formula_board import generate_formula_board
from .generate_projected_slide_derivative import (
    generate_projected_slide_derivative,
)


GENERATED_FILENAMES = (
    "bilingual_printed_slide.png",
    "bilingual_printed_slide_projected.jpg",
    "formula_board.png",
    "calibration_table.png",
)

# The environment that produced the committed corpus. Only the Pillow
# version was pinned at commit time; the FreeType build and platform inside
# that wheel were never recorded, and Pillow 12.3.0 win_amd64 with FreeType
# 2.14.3 does not reproduce the committed bytes. The unknown fields stay
# None, so no environment claims a byte-strict match until a maintainer
# re-baselines the corpus and records the full environment here.
GENERATOR_ENVIRONMENT = {
    "pillow": "12.3.0",
    "freetype": None,
    "platform": None,
}

# Reproduction tolerance for environments other than GENERATOR_ENVIRONMENT.
# Chosen 2026-08-19 as roughly 1.5x the drift measured between the original
# generator environment and Pillow 12.3.0 / FreeType 2.14.3 / win32, whose
# worst fixture differed in 4.31% of pixels with a mean channel delta of
# 2.34. That drift is glyph-edge antialiasing from a different rasterizer
# build; the rendered content is identical.
MAX_CHANGED_PIXEL_FRACTION = 0.065
MAX_MEAN_CHANNEL_DELTA = 3.5

_MANIFEST_PATH = (
    Path(__file__).resolve().parents[2] / "fixtures" / "phase1" / "manifest.json"
)


@dataclass(frozen=True, slots=True)
class PixelDrift:
    """Decoded-pixel difference between two images of identical geometry."""

    changed_fraction: float
    mean_channel_delta: float


def generate_phase1_fixtures(output_directory: Path) -> tuple[Path, ...]:
    """Generate the four repo-owned images into one explicit directory."""
    output_directory.mkdir(parents=True, exist_ok=True)
    clean_slide = generate_bilingual_slide(
        output_directory / GENERATED_FILENAMES[0]
    )
    projected = generate_projected_slide_derivative(
        clean_slide,
        output_directory / GENERATED_FILENAMES[1],
    )
    formula = generate_formula_board(output_directory / GENERATED_FILENAMES[2])
    table = generate_calibration_table(output_directory / GENERATED_FILENAMES[3])
    return clean_slide, projected, formula, table


def current_generator_environment() -> dict[str, str | None]:
    """Return the rendering environment of this process."""
    return {
        "pillow": PIL.__version__,
        "freetype": features.version("freetype2"),
        "platform": sys.platform,
    }


def generator_environment_matches() -> bool:
    """True only when every recorded environment field is known and matches."""
    current = current_generator_environment()
    return all(
        recorded is not None and recorded == current[field]
        for field, recorded in GENERATOR_ENVIRONMENT.items()
    )


def measure_pixel_drift(first: Path, second: Path) -> PixelDrift:
    """Return decoded-pixel drift between two images, or fail on geometry."""
    with Image.open(first) as first_image, Image.open(second) as second_image:
        first_image.load()
        second_image.load()
        if (
            first_image.format != second_image.format
            or first_image.mode != second_image.mode
            or first_image.size != second_image.size
        ):
            raise RuntimeError(
                f"fixture geometry differs: {first.name} vs {second.name}"
            )
        total_pixels = first_image.size[0] * first_image.size[1]
        difference = ImageChops.difference(
            first_image.convert("RGB"), second_image.convert("RGB")
        )
    histogram = difference.convert("L").histogram()
    changed = total_pixels - histogram[0]
    mean_delta = (
        sum(level * count for level, count in enumerate(histogram)) / total_pixels
    )
    return PixelDrift(
        changed_fraction=changed / total_pixels,
        mean_channel_delta=mean_delta,
    )


def check_phase1_fixtures(committed_directory: Path) -> str:
    """Verify integrity, determinism, and reproduction of the corpus.

    Returns "byte-identical" when the current environment matches the
    recorded generator environment and a fresh generation reproduces the
    committed bytes, otherwise a "pixel-equivalent (...)" summary carrying
    the worst measured drift.
    """
    pinned = _load_pinned_image_records()
    _verify_committed_bytes(committed_directory, pinned)
    with tempfile.TemporaryDirectory(
        prefix="ocrllm-phase1-fixtures-"
    ) as first_temporary, tempfile.TemporaryDirectory(
        prefix="ocrllm-phase1-fixtures-"
    ) as second_temporary:
        first = generate_phase1_fixtures(Path(first_temporary))
        second = generate_phase1_fixtures(Path(second_temporary))
        _verify_deterministic(first, second)
        if generator_environment_matches():
            _verify_byte_reproduction(first, pinned)
            return "byte-identical"
        worst = _verify_pixel_reproduction(first, committed_directory)
        return (
            "pixel-equivalent (generator environment differs from the"
            f" recorded one; worst changed {worst.changed_fraction:.2%},"
            f" mean channel delta {worst.mean_channel_delta:.2f})"
        )


def _load_pinned_image_records() -> dict[str, tuple[str, int]]:
    """Read the committed manifest's SHA-256 and byte pins by filename."""
    document = json.loads(_MANIFEST_PATH.read_text(encoding="utf-8"))
    records: dict[str, tuple[str, int]] = {}
    for artifact in document["artifacts"]:
        if artifact["role"] != "fixture-image":
            continue
        name = PurePosixPath(artifact["path"]).name
        if name in GENERATED_FILENAMES:
            records[name] = (artifact["sha256"], artifact["bytes"])
    if set(records) != set(GENERATED_FILENAMES):
        raise RuntimeError("the manifest does not pin every generated fixture")
    return records


def _verify_committed_bytes(
    committed_directory: Path, pinned: dict[str, tuple[str, int]]
) -> None:
    """Integrity stage: committed files must match the manifest pins."""
    for name in GENERATED_FILENAMES:
        committed_path = committed_directory / name
        if not committed_path.is_file():
            raise RuntimeError(f"missing committed fixture: {committed_path.name}")
        expected_sha256, expected_bytes = pinned[name]
        payload = committed_path.read_bytes()
        if len(payload) != expected_bytes or _sha256(committed_path) != expected_sha256:
            raise RuntimeError(f"fixture bytes drifted: {committed_path.name}")


def _verify_deterministic(
    first: tuple[Path, ...], second: tuple[Path, ...]
) -> None:
    """Determinism stage: two generations in one environment must agree."""
    for first_path, second_path in zip(first, second):
        if _sha256(first_path) != _sha256(second_path):
            raise RuntimeError(
                f"fixture generation is not deterministic: {first_path.name}"
            )


def _verify_byte_reproduction(
    generated: tuple[Path, ...], pinned: dict[str, tuple[str, int]]
) -> None:
    """Reproduction stage, strict form: fresh bytes must equal the pins."""
    for generated_path in generated:
        expected_sha256, expected_bytes = pinned[generated_path.name]
        payload = generated_path.read_bytes()
        if len(payload) != expected_bytes or _sha256(generated_path) != expected_sha256:
            raise RuntimeError(
                f"regenerated fixture bytes differ: {generated_path.name}"
            )


def _verify_pixel_reproduction(
    generated: tuple[Path, ...], committed_directory: Path
) -> PixelDrift:
    """Reproduction stage, tolerant form: decoded pixels must stay close."""
    worst = PixelDrift(changed_fraction=0.0, mean_channel_delta=0.0)
    for generated_path in generated:
        drift = measure_pixel_drift(
            generated_path, committed_directory / generated_path.name
        )
        if (
            drift.changed_fraction > MAX_CHANGED_PIXEL_FRACTION
            or drift.mean_channel_delta > MAX_MEAN_CHANNEL_DELTA
        ):
            raise RuntimeError(
                f"regenerated fixture pixels drifted past tolerance:"
                f" {generated_path.name}"
                f" (changed {drift.changed_fraction:.2%},"
                f" mean channel delta {drift.mean_channel_delta:.2f})"
            )
        if drift.changed_fraction > worst.changed_fraction:
            worst = drift
    return worst


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _default_image_directory() -> Path:
    return Path(__file__).resolve().parents[2] / "fixtures" / "phase1" / "images"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--check", action="store_true")
    parser.add_argument(
        "--output-directory",
        type=Path,
        default=_default_image_directory(),
    )
    arguments = parser.parse_args()
    if arguments.write:
        for path in generate_phase1_fixtures(arguments.output_directory):
            print(f"{path.name} {_sha256(path)}")
    else:
        result = check_phase1_fixtures(arguments.output_directory)
        if result == "byte-identical":
            print("Phase 1 generated fixtures are byte-identical.")
        else:
            print(f"Phase 1 generated fixtures verified: {result}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
