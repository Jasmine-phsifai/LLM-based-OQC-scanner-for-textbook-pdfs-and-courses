"""Prove slot state survives an operating-system process termination."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import time

from ocrllm import Config, RecognitionPreferences, recognize

from write_test_image import write_test_image


_CHILD_PROGRAM = r"""
from pathlib import Path
import sys
import time

from ocrllm import Config, RecognitionPreferences, recognize


class BlockingSecondPassProvider:
    resume_identity = "m2-process-kill-provider-v1"

    def __init__(self, marker: Path) -> None:
        self.calls = 0
        self.marker = marker

    def recognize_images(self, image_paths, *, prompt, config):
        self.calls += 1
        if self.calls == 1:
            return "# Persisted first draft\n"
        self.marker.write_text("second pass entered", encoding="utf-8")
        time.sleep(300)
        raise AssertionError("parent should terminate this process")


source, output_dir, marker, temp_dir = map(Path, sys.argv[1:5])
recognize(
    source,
    config=Config(
        provider=BlockingSecondPassProvider(marker),
        output_dir=output_dir,
        temp_dir=temp_dir,
        preferences=RecognitionPreferences(draft_candidates=2, review_passes=1),
    ),
)
"""


class CompletingProvider:
    resume_identity = "m2-process-kill-provider-v1"

    def __init__(self) -> None:
        self.calls = 0

    def recognize_images(self, image_paths, *, prompt, config):
        self.calls += 1
        return f"# Resumed pass {self.calls}\n"


def _wait_until(path: Path, *, timeout_seconds: float = 15.0) -> None:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if path.is_file():
            return
        time.sleep(0.02)
    raise AssertionError(f"child did not create {path.name} before timeout")


def test_process_kill_preserves_paid_slot_and_resume_pays_only_missing(
    tmp_path: Path,
) -> None:
    source = write_test_image(tmp_path / "board.png")
    output_dir = tmp_path / "output"
    marker = tmp_path / "second-pass-entered.txt"
    temp_dir = tmp_path / "snapshots"
    repo_root = Path(__file__).resolve().parents[1]
    environment = dict(os.environ)
    existing_pythonpath = environment.get("PYTHONPATH")
    environment["PYTHONPATH"] = os.pathsep.join(
        part
        for part in (str(repo_root / "src"), existing_pythonpath)
        if part
    )
    child = subprocess.Popen(
        [
            sys.executable,
            "-c",
            _CHILD_PROGRAM,
            str(source),
            str(output_dir),
            str(marker),
            str(temp_dir),
        ],
        cwd=repo_root,
        env=environment,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        _wait_until(marker)
    finally:
        if child.poll() is None:
            child.terminate()
            try:
                child.wait(timeout=10)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait(timeout=10)

    assert child.returncode != 0
    state_path = output_dir / "board_board.ocrllm-state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    assert [slot["slot_id"] for slot in state["slots"]] == ["draft"]
    assert not (output_dir / "board_board.md").exists()

    provider = CompletingProvider()
    result = recognize(
        source,
        config=Config(
            provider=provider,
            output_dir=output_dir,
            temp_dir=temp_dir,
            resume=True,
            preferences=RecognitionPreferences(draft_candidates=2, review_passes=1),
        ),
    )

    assert provider.calls == 2
    assert result.markdown == "# Resumed pass 2\n"
    assert [slot["reused"] for slot in result.metadata["workflow_slots"]] == [
        True,
        False,
        False,
    ]
    completed_state = json.loads(state_path.read_text(encoding="utf-8"))
    assert [slot["slot_id"] for slot in completed_state["slots"]] == [
        "draft",
        "draft_2",
        "consensus_review",
    ]
