"""Re-score preserved v2 output against the source-corrected board truth."""

import json
from pathlib import Path

from quality_lab.load_fixture_manifest import load_fixture_manifest
from quality_lab.score_recognition_result import score_recognition_result


EVIDENCE_PATH = (
    Path(__file__).parent.parent.parent
    / "evidence"
    / "phase1"
    / "phase1-quality-v2-2026-07-11-cn-beijing.json"
)


def test_v2_outputs_isolate_the_one_missing_handwritten_plus():
    evidence = json.loads(EVIDENCE_PATH.read_text(encoding="utf-8"))
    manifest = load_fixture_manifest()
    expected_passes = (True, True, False, True, True, True)
    handwriting_failures = ("text_critical_accuracy_below_one",)

    smoke = score_recognition_result(
        manifest,
        manifest.live_dispatch_order[0],
        evidence["smoke"]["markdown"],
    )
    assert smoke.passes
    for run in evidence["full_runs"]:
        reports = tuple(
            score_recognition_result(
                manifest,
                manifest.live_dispatch_order[sequence],
                dispatch["markdown"],
            )
            for sequence, dispatch in enumerate(run["dispatches"])
        )
        assert tuple(report.passes for report in reports) == expected_passes
        assert reports[2].failures == handwriting_failures
        assert (
            reports[2].text_score.recall.numerator,
            reports[2].text_score.recall.denominator,
        ) == (29, 30)
        assert (
            reports[2].text_score.precision.numerator
            == reports[2].text_score.precision.denominator
        )
        assert reports[2].critical_slot_score is not None
        assert reports[2].critical_slot_score.passes
