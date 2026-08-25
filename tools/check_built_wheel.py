"""Check the base wheel's required and forbidden package files."""

from __future__ import annotations

from pathlib import Path
import sys
import zipfile


def check_built_wheel(wheel_path: Path) -> None:
    """Reject a wheel missing markers or containing repository-only documents."""
    with zipfile.ZipFile(wheel_path) as wheel:
        names = set(wheel.namelist())

    if "ocrllm/__init__.py" not in names:
        raise ValueError("wheel is missing the package")
    if "ocrllm/py.typed" not in names:
        raise ValueError("wheel is missing py.typed")
    if "ocrllm/AGENTS.md" in names:
        raise ValueError("wheel contains repository-only instructions")
    if "ocrllm/README_ACTIVE_LIBRARY.md" in names:
        raise ValueError("wheel contains repository-only package documentation")


def main(argv: list[str]) -> int:
    """Validate the one wheel path passed by the release gate."""
    if len(argv) != 2:
        raise SystemExit("usage: check_built_wheel.py WHEEL_PATH")
    check_built_wheel(Path(argv[1]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
