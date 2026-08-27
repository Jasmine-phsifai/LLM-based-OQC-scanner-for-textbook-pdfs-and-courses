from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
NODE_HARNESS = REPOSITORY_ROOT / "tests" / "node" / "verify_worker_protocol.mjs"
FIXTURE_ENTRYPOINT = REPOSITORY_ROOT / "tests" / "worker_fixture_entrypoint.py"
CANCELLATION_ENTRYPOINT = (
    REPOSITORY_ROOT / "tests" / "worker_cancellation_entrypoint.py"
)


def _run_node_scenario(scenario: str, entrypoint: Path, temporary_root: Path) -> dict:
    node = _find_node_executable()
    completed = subprocess.run(
        [
            node,
            str(NODE_HARNESS),
            scenario,
            sys.executable,
            str(entrypoint),
            str(temporary_root),
        ],
        cwd=REPOSITORY_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
        timeout=45,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert completed.stderr == ""
    return json.loads(completed.stdout)


def _find_node_executable() -> str:
    """Find Node on PATH or beside the Python environment running this gate."""
    node = shutil.which("node")
    if node is not None:
        return node
    sibling = Path(sys.executable).with_name(
        "node.exe" if sys.platform == "win32" else "node"
    )
    if sibling.is_file():
        return str(sibling)
    raise AssertionError("Phase 2 Node gate requires a Node executable")


def test_node_harness_validates_fixture_stdout_and_unicode_round_trip(tmp_path) -> None:
    result = _run_node_scenario("fixture", FIXTURE_ENTRYPOINT, tmp_path)

    assert result["scenario"] == "fixture"
    assert result["lines_validated"] == 4
    assert "%E8%AF%BE%E7%A8%8B%20%F0%9F%93%9A" in result["source_uri"]


def test_node_harness_cancels_child_and_grandchild_within_five_seconds(
    tmp_path,
) -> None:
    result = _run_node_scenario(
        "cancellation",
        CANCELLATION_ENTRYPOINT,
        tmp_path,
    )

    assert result["scenario"] == "cancellation"
    assert result["lines_validated"] == 2
    assert result["elapsed_milliseconds"] <= 5000
