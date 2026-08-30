"""Build the one frozen smoke-plus-two-runs Phase 1 dispatch plan."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from quality_lab.fixture_manifest import Phase1FixtureManifest


RECOGNITION_INVOCATION_COUNT = 13
PROVIDER_CALLS_PER_RECOGNITION = 4
CONFIRMED_PAID_CALL_COUNT = (
    RECOGNITION_INVOCATION_COUNT * PROVIDER_CALLS_PER_RECOGNITION
)


@dataclass(frozen=True, slots=True)
class Phase1DispatchPlanEntry:
    """One library recognition invocation in immutable execution order."""

    attempt_index: int
    phase: Literal["smoke", "full"]
    run_index: int | None
    manifest_sequence: int
    kind: Literal["single", "ordered"]
    fixture_ids: tuple[str, ...]
    ordered_request_id: str | None


def build_phase1_dispatch_plan(
    manifest: Phase1FixtureManifest,
) -> tuple[Phase1DispatchPlanEntry, ...]:
    """Return one smoke and two complete copies of the six manifest dispatches."""

    if type(manifest) is not Phase1FixtureManifest:
        raise TypeError("manifest must be an exact Phase1FixtureManifest")
    dispatches = manifest.live_dispatch_order
    if len(dispatches) != 6 or tuple(item.sequence for item in dispatches) != tuple(
        range(6)
    ):
        raise ValueError("Phase 1 requires exactly six contiguous manifest dispatches")

    plan: list[Phase1DispatchPlanEntry] = []
    smoke = dispatches[0]
    plan.append(
        Phase1DispatchPlanEntry(
            attempt_index=0,
            phase="smoke",
            run_index=None,
            manifest_sequence=smoke.sequence,
            kind=smoke.kind,
            fixture_ids=smoke.fixture_ids,
            ordered_request_id=smoke.ordered_request_id,
        )
    )
    for run_index in (1, 2):
        for dispatch in dispatches:
            plan.append(
                Phase1DispatchPlanEntry(
                    attempt_index=len(plan),
                    phase="full",
                    run_index=run_index,
                    manifest_sequence=dispatch.sequence,
                    kind=dispatch.kind,
                    fixture_ids=dispatch.fixture_ids,
                    ordered_request_id=dispatch.ordered_request_id,
                )
            )

    result = tuple(plan)
    if len(result) != RECOGNITION_INVOCATION_COUNT or tuple(
        item.attempt_index for item in result
    ) != tuple(range(RECOGNITION_INVOCATION_COUNT)):
        raise AssertionError("the frozen recognition plan is internally inconsistent")
    return result
