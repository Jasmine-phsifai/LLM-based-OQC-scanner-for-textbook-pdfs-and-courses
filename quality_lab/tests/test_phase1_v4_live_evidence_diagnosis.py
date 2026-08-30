"""Re-score immutable partial v4 output after the v5 source/presentation fix."""

import json
from pathlib import Path

from quality_lab.load_fixture_manifest import load_fixture_manifest
from quality_lab.score_recognition_result import score_recognition_result


EVIDENCE_PATH = (
    Path(__file__).parent.parent.parent
    / "evidence"
    / "phase1"
    / "phase1-quality-v4-attempt2-2026-07-11-cn-beijing.json"
)


def test_v4_handwriting_output_keeps_only_the_genuinely_missing_plus_failure():
    evidence = json.loads(EVIDENCE_PATH.read_text(encoding="utf-8"))
    manifest = load_fixture_manifest()
    successful_records = (evidence["smoke"], *evidence["full_runs"][0]["dispatches"][:5])

    reports = tuple(
        score_recognition_result(
            manifest,
            manifest.live_dispatch_order[record["manifest_sequence"]],
            record["markdown"],
        )
        for record in successful_records
    )

    assert tuple(report.passes for report in reports) == (
        True,
        True,
        True,
        False,
        True,
        True,
    )
    handwriting = reports[3]
    assert handwriting.failures == ("text_critical_accuracy_below_one",)
    assert (handwriting.text_score.recall.numerator, handwriting.text_score.recall.denominator) == (29, 30)
    assert handwriting.text_score.unexpected_critical_indexes == ()
    assert handwriting.critical_slot_score is not None
    assert handwriting.critical_slot_score.passes
