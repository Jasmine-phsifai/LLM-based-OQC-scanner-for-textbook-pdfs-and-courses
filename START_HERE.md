# START HERE: OCRLLM Repo Map

This repo currently contains two codebases. Treat the directory boundary as a
hard signal before editing or importing anything.

**Read `docs/ACTIVE_STATE_AND_RULES.md` first.** It outranks every other file,
including this one, and it carries current state, the open defect register, and
the coding and documentation rules.

Current state lives in `docs/ACTIVE_STATE_AND_RULES.md`. Dated phase, decision,
checkpoint, review, and incident files keep history only; they never override
that file. Verify capability claims against the named code and tests.

## Active New Library

Path: `src/ocrllm/`

Use for:

- New importable package: `ocrllm`
- Stable public API work
- New downstream project dependencies
- Root test suite under `tests/`

Read in this order:

```text
docs/ACTIVE_STATE_AND_RULES.md        Current truth, defects, rules. Outranks all.
docs/plan_phase1_maturation_and_phase2_audio.md
                                      Current work plan; Stage M is partially
                                      implemented and still open.
docs/plan_phase1_defects_and_provider_split.md
                                      Stage 1 closed; Stage 2 provider split
                                      is not started.
docs/ocrllm_library_go_no_go.md       Phase gates, file responsibilities,
                                      migrate/rewrite/reject boundary.
src/ocrllm/README_ACTIVE_LIBRARY.md   Package boundary and capability surface.
src/ocrllm/AGENTS.md                  Package editing rules.
MIGRATION_STATUS.md                   Navigation aid.
docs/ocrllm_module_target_design.md   Target-state module map.
docs/provider_cost_and_reliability_policy.md
                                      Account-specific provider policy.
```

Other documents named in this read order remain current for their bounded
purpose. Files with `phase*`, `*_decision_*`, `*_checkpoint_*`, `*_review_*`,
or `*_incident_*` names are dated history; consult them only to understand how
a past decision was reached, never to learn current state.

Public import shape:

```python
from ocrllm import Config, DashScopeSettings, VisionModelSettings, recognize
```

Current phase: **Phase 1 maturation, Stage M partially implemented**. Phase 0
contract honesty, the Phase 1 image gate, the Phase 2 development worker, and
Phase 2A image-library completion are GO. Stage M has shipped lazy DashScope
catalog checks, atomic file-backed image state, an opt-in candidate queue, and
slot-indexed intra-request checkpoints with an explicit v1-to-v2 resume
identity migration. Its complete attempt-spend disclosure,
disposition-gated recovery, and model-aware pool behavior remain open. Stage 2
vision/audio provider splitting and Stage A mp3 recognition are not started.

The public image facade decodes PNG/JPEG inputs before provider dispatch,
passes request-scoped validated snapshots to an injected provider, rejects
empty/control-only/refusal-shaped output, returns typed redacted errors, and
reports canonical `source_type="image"` with `profile="board"`. File output
is optional and atomic; `output_dir=None` stays memory-only. Pillow remains
lazy during plain `import ocrllm`.

Phase 1 uses one unified `board.v17` workflow for printed, projected,
handwritten, formula, table, and ordered-image inputs. The Beijing live gate
completed all 13 recognitions and exactly 52 provider calls with no retry or
terminal failure. Both independent six-dispatch runs passed. Run A required no
restoration; Run B restored exactly one missing handwriting sign through the
same generic two-of-three omission-scout path used for every image class.

Preserve
`evidence/phase1/phase1-quality-v17-2026-07-11-cn-beijing.json`: 107,246
bytes, SHA-256
`6f0454d634dbe76f68f29c07a4c0ced4a047c080e46bb75dda2cb84ffca3a96b`.
The clean Git-archive gate at `0278b66` is historical evidence for the image and
worker boundaries. The current allowed work is Stage M maturation under
`docs/plan_phase1_maturation_and_phase2_audio.md`; its exit gate has not passed.

The active library has a region-bound in-memory credential scheduler and
request/batch image resume. Candidate switching is opt-in and currently
quota-gated; it is not yet complete recovery. PDF, audio, and video support
remain unavailable. Local user PDFs/screenshots under `docs/` are untracked
supplemental material, not redistributable gate evidence.

The current open defect list is only in
`docs/ACTIVE_STATE_AND_RULES.md`: G1 (partial), G2, G3, G4, G5, G8, and G10.
D1-D7 including residual D4, F1-F4, G6, G7, and G9 are closed.

## Legacy Application

Path: `legacy_app/`

Use for:

- Behavior reference and explicitly scoped maintenance for the old GUI, CLI,
  FastAPI, processors, and launchers
- Historical outputs and incident records used to define active-library
  fixtures

Read next:

- `legacy_app/README_LEGACY.md`
- `legacy_app/AGENTS.md`
- `docs/legacy_bilibili_social_long_debug_record.md` for multi-part Bilibili
  course download/recognition recovery.
- `docs/legacy_youtube_playlist_social_long_workflow.md` for YouTube playlist
  course download/recognition recovery.
- `docs/legacy_filetrans_codex_debug_record.md` for Codex/FileTrans recovery.

Do not use as a new dependency boundary:

```python
import legacy_app.OCRLLM
```

## Suspended Future Plan

Path: `Architecture.md`

Status: future plan, currently suspended.

Do not make the Rust/PyO3 rewrite active again until the Python import contract
has real downstream usage and stable module boundaries.

## Runtime Artifacts

These paths are not source-of-truth code:

- `output/`
- `temp/`
- `ocrllm_social_e2e/`
- `.pytest_cache/`
- `__pycache__/`

Do not infer architecture from generated output or temporary files.

## Choose The Edit Location

```text
Need current state or open defects   -> docs/ACTIVE_STATE_AND_RULES.md
Need to know what to build next      -> docs/plan_phase1_maturation_and_phase2_audio.md
Need to change the public library API      -> src/ocrllm/ and tests/
Need to add a downstream import feature    -> src/ocrllm/ and tests/
Need to compare old product behavior       -> legacy_app/
Need to fix or maintain the old app        -> legacy_app/ plus its diary
Need to record migration state             -> MIGRATION_STATUS.md
Need to decide GO/NO-GO or port behavior   -> docs/ocrllm_library_go_no_go.md
Need to debug Bilibili social-long courses -> docs/legacy_bilibili_social_long_debug_record.md
Need to debug YouTube playlist courses    -> docs/legacy_youtube_playlist_social_long_workflow.md
Need to design the completed module shape  -> docs/ocrllm_module_target_design.md
Need to revisit future Rust/PyO3 design    -> Architecture.md
```

## Do Not Cross These Boundaries

- Do not import `legacy_app.OCRLLM` from new downstream projects.
- Do not copy a whole legacy module into `src/ocrllm`.
- Do not let `import ocrllm` pull GUI, FastAPI, social downloader, or heavy
  media dependencies.
- Do not treat `Architecture.md` as the active implementation plan.
- Do not put runtime output defaults inside package directories.
- Do not add PyMuPDF or `fitz` to the active library. Active PDF work uses
  PDFium through `pypdfium2` only after the PDF phase is authorized.
- Do not begin or claim HarmonyOS/ArkTS compatibility. It is deferred by the
  active GO/NO-GO decision.

## Verification Commands

The pinned offline checkpoint checks are:

```powershell
uv run --no-project --isolated --with 'Pillow==12.3.0' `
  --with 'pytest>=8,<10' --with 'openai>=2.30,<3' `
  --python 'D:\Anaconda\envs\OCRLLM\python.exe' `
  python -m pytest -q -p no:cacheprovider
uv run --no-project --isolated --with 'Pillow==12.3.0' `
  --python 'D:\Anaconda\envs\OCRLLM\python.exe' `
  python -m tests.quality.generators.generate_phase1_fixtures --check
& 'D:\Anaconda\envs\OCRLLM\python.exe' -m compileall -q src tests
```

Before reporting completion, run the clean Git-archive wheel build, isolated
install, and outside-repo heavy-module guard in
`docs/ocrllm_library_go_no_go.md`. Do not run the paid live gate until the
exact region/`base_url` is confirmed by the caller and the runner's Git/import,
manifest, artifact, and credential preflight passes.

Active-library migration tests must not modify or run the legacy suite as a
phase gate. Create fixtures and tests under root `tests/`. Legacy commands and
tests are historical reference unless a separate legacy-maintenance request
explicitly authorizes that work.
