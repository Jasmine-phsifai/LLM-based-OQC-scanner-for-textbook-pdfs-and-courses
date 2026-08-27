from __future__ import annotations

import hashlib
import json
from pathlib import Path


FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "audio" / "a1"


def test_a1_mp3_fixture_manifest_matches_every_committed_artifact() -> None:
    manifest = json.loads((FIXTURE_ROOT / "manifest.json").read_text("utf-8"))

    assert manifest["schema"] == "ocrllm.a1-mp3-fixtures.v1"
    assert manifest["validation_contract"] == (
        "accept means accepted by the decoder contract, not a claim of "
        "pristine MPEG bitstream provenance"
    )
    assert manifest["synthetic_input"] == (
        "sine=frequency=997:sample_rate=44100:duration=0.500"
    )
    expected_names = {
        "valid_cbr.mp3",
        "valid_vbr.mp3",
        "valid_id3.mp3",
        "one_frame.mp3",
        "incomplete_tail.mp3",
        "corrupted_middle.mp3",
    }
    assert {item["filename"] for item in manifest["fixtures"]} == expected_names
    assert {path.name for path in (FIXTURE_ROOT / "mp3").glob("*.mp3")} == (
        expected_names
    )

    for item in manifest["fixtures"]:
        data = (FIXTURE_ROOT / "mp3" / item["filename"]).read_bytes()
        assert len(data) == item["byte_size"]
        assert hashlib.sha256(data).hexdigest() == item["sha256"]
        assert item["channel_count"] == 1
        assert item["sample_rate_hz"] == 44_100


def test_a1_mp3_fixture_provenance_is_present() -> None:
    permission = (FIXTURE_ROOT / "repo_owned_fixture_data.md").read_text("utf-8")
    normalized_permission = " ".join(permission.split())
    assert "no recorded human speech" in normalized_permission
    assert "LicenseRef-OCRLLM-Repo-Owned-Test-Data" in permission
