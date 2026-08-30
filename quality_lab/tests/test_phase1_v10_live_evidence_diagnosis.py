"""Re-score the preserved v10 formula output under the v11 safe dialect."""

import json
from pathlib import Path

from quality_lab.load_fixture_manifest import load_fixture_manifest
from quality_lab.score_recognition_result import score_recognition_result


EVIDENCE_PATH = (
    Path(__file__).parent.parent.parent
    / "evidence"
    / "phase1"
    / "phase1-quality-v10-2026-07-11-cn-beijing.json"
)


def test_v10_run_a_formula_text_groups_are_source_equivalent_and_perfect():
    evidence = json.loads(EVIDENCE_PATH.read_text(encoding="utf-8"))
    manifest = load_fixture_manifest()
    record = evidence["full_runs"][0]["dispatches"][3]

    report = score_recognition_result(
        manifest,
        manifest.live_dispatch_order[record["manifest_sequence"]],
        record["markdown"],
    )

    assert report.passes
    assert report.failures == ()
    assert report.formula_score is not None
    assert (
        report.formula_score.signature_accuracy.numerator,
        report.formula_score.signature_accuracy.denominator,
    ) == (12, 12)
    assert (
        report.formula_score.atom_precision.numerator,
        report.formula_score.atom_precision.denominator,
    ) == (133, 133)
    assert (
        report.formula_score.critical_accuracy.numerator,
        report.formula_score.critical_accuracy.denominator,
    ) == (108, 108)
