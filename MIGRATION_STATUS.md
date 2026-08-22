# OCRLLM Migration Status

This is a navigation aid. The authoritative current state, open defects, and
documentation rules are in
[`docs/ACTIVE_STATE_AND_RULES.md`](docs/ACTIVE_STATE_AND_RULES.md). If this
file and that file differ, that file wins.

## Current Status

Last synchronized: 2026-08-23.

The repository has two boundaries:

| Boundary | Status | Use |
|---|---|---|
| `src/ocrllm/` | Active library | New imports, stable API, root tests. |
| `legacy_app/` | Maintained compatibility app | GUI, CLI, FastAPI, social workflows, and behavior reference. |

The active library has GO coverage for the image contract, local OCR, the
development JSONL worker, provider error disposition, credential scheduling,
and image resume. Stage M Phase 1 maturation is offline implementation-complete:

- shipped: lazy DashScope catalog checks, atomic file-backed image state, an
  opt-in disposition-gated candidate model queue, complete spend disclosure,
  model-aware credential blocking, scout-failure attribution, and slot-indexed
  intra-request checkpoints with an explicit v1-to-v2 identity migration;
  atomic Markdown/state temporary names are compact and do not repeat public
  destination basenames near the traditional Windows path boundary; a process-local
  output claim keeps concurrent batch/direct-thread Markdown and state ownership
  consistent; finite batch-iterable failures become redacted terminal outcomes
  without discarding earlier paid work; the never-consumed `Config.progress`,
  generic `Config.cache_dir`, and four dormant PDF-only placeholders are
  removed rather than promoted into unproven callback, persistence, or PDF
  APIs; frozen worker progress remains separate, while local OCR retains its
  zero-network model-loading contract;
  all no-cost exit criteria pass through the clean-archive runner at `271d96d`;
- open: the Stage M paid live exit smoke and live re-verification of provider
  account/model quota semantics;
- replanned, in progress: the standalone Stage 2 vision/audio scaffold was
  removed; its audio-specific configuration boundary now lands with executable
  Stage A1 short-MP3 recognition, followed by Stage A2 FileTrans. The A1
  offline slice may proceed independently of the open Stage M paid image smoke;
  its own live gate remains separately budgeted. The provider-independent MP3
  probe now uses lazy `miniaudio>=1.71,<2`, fully decodes bounded five-minute
  snapshots, and rejects the fixture-proven malformed cases before dispatch.
  One local `.mp3` is copied through an open handle to fixed `source.mp3`, with
  a separate 25 MiB local safety ceiling and cleanup ownership;
  FFmpeg/PyAV/Mutagen remain outside the A1 runtime. Audio configuration,
  provider dispatch, persistence, and the public facade are not implemented;
- not started: Stage A2 audio recognition and the active PDFium phase.

The defect register is in
[`docs/ACTIVE_STATE_AND_RULES.md`](docs/ACTIVE_STATE_AND_RULES.md). D1-D7,
F1-F4, and G1-G10 are closed in offline code and tests; the paid Stage M exit
gate remains open. Do not create a second defect list in this file.

## Read Order

1. [`docs/ACTIVE_STATE_AND_RULES.md`](docs/ACTIVE_STATE_AND_RULES.md) for
   current truth, defects, rules, and precedence.
2. [`START_HERE.md`](START_HERE.md) for the one-screen repository map.
3. [`docs/plan_phase1_maturation_and_phase2_audio.md`](docs/plan_phase1_maturation_and_phase2_audio.md)
   for the current Stage M and Stage A plan.
4. [`docs/ocrllm_library_go_no_go.md`](docs/ocrllm_library_go_no_go.md) for
   execution gates and migrate/rewrite/reject boundaries.
5. [`src/ocrllm/README_ACTIVE_LIBRARY.md`](src/ocrllm/README_ACTIVE_LIBRARY.md)
   and [`src/ocrllm/AGENTS.md`](src/ocrllm/AGENTS.md) for package work.
6. [`legacy_app/AGENTS.md`](legacy_app/AGENTS.md) for legacy maintenance and
   the working diary.

## Boundary Rules

- New projects import only `ocrllm`, never `legacy_app.OCRLLM`.
- Port one tested vertical slice at a time; do not copy legacy modules
  wholesale.
- Keep GUI, FastAPI, social downloading, browser automation, and heavy media
  dependencies out of plain `import ocrllm`.
- `worker/` and `contracts/` are frozen until a real consumer justifies a
  protocol revision in the same slice.
- Active PDF work uses PDFium through `pypdfium2`; do not add PyMuPDF or
  `fitz`.
- HarmonyOS/ArkTS and the Rust/PyO3 rewrite are deferred/suspended and are not
  current work.
- `output/`, `temp/`, caches, and local screenshots are runtime or supplemental
  artifacts, not architecture evidence.

## Verification

Run from the repository root with the maintained environment:

```powershell
& 'D:\Anaconda\envs\OCRLLM\python.exe' -m pytest -q -p no:cacheprovider
& 'D:\Anaconda\envs\OCRLLM\python.exe' -m compileall -q src tests
& 'D:\Anaconda\envs\OCRLLM\python.exe' -c "import sys,time; sys.path.insert(0, 'src'); t=time.perf_counter(); import ocrllm; print(round(time.perf_counter()-t, 4), len(sys.modules), [m for m in ('PIL','openai','httpx','onnxruntime') if m in sys.modules])"
```

The clean Git-archive wheel, isolated install, outside-repository import, and
heavy-module guard are defined in
[`docs/ocrllm_library_go_no_go.md`](docs/ocrllm_library_go_no_go.md). A paid
live gate requires an explicit maintainer budget and confirmed region/endpoint.

## History Trace

Detailed records remain in dated Markdown files. This table keeps the migration
route without presenting old conclusions as current status.

| Commit | Trace |
|---|---|
| `cd7429c` | Stage M2 slot-indexed intra-request checkpoints and resume identity v2. |
| `0278b66` | Phase 1 v17 image evidence and clean package gate. |
| `2db456a` | Phase 2 development worker gate. |
| `8025406` | D1-D7 defect repair. |
| `2f39428` | F1-F4 audit closure and legacy refusal/timeout/partial-failure protections. |
| `a19776d` | Stage M model discovery and candidate queue. |
| `4c5293d` | DashScope catalog first-fetch failure changed to fail closed. |
| `3c6e985` | Legacy PDF batch retry and provider classification fixes. |
| `b8d42a2` | Legacy checkpoint visibility/resume filtering fix. |
| `6f2bf8a` | Legacy PDF repair-mode workflow. |
| `78a2fa6` | Legacy repair-range expansion and partial-failure reporting. |
| `42c0f75` | Legacy settings/model fetch moved to the current picker boundary. |

The complete legacy incident trace, including carry-forward warnings for future
library ports, is in [`legacy_app/AGENTS.md`](legacy_app/AGENTS.md). Historical
`docs/phase*`, decision, checkpoint, and review files are immutable records;
read them only to understand why a past decision was made.

## Historical Record Index

This appendix restores the important material that used to be embedded in this
navigation file. It is history, not a second current-state document. The
linked records are the detailed source; the summaries here are deliberately
short.

### Why The Migration Happened (historical rationale)

The old application imported as uppercase `OCRLLM` and combined GUI, CLI,
FastAPI, social downloading, providers, prompts, and recognition processors in
one surface. It also had no root package metadata, used package-relative
runtime paths, and exposed implementation classes before a stable facade
existed. The migration therefore moved the application to `legacy_app/` and
rewrote proven behavior behind the small `src/ocrllm/` contract. This rationale
remains valid; the old architecture is not a pending implementation plan.
See [`docs/library_migration_decision.md`](docs/library_migration_decision.md)
and [`docs/ocrllm_module_target_design.md`](docs/ocrllm_module_target_design.md).

### Historical Gate Decisions

- Phase 0 established the importable package and boundary contract. Its exact
  measurements are historical and remain in
  [`docs/ocrllm_library_go_no_go.md`](docs/ocrllm_library_go_no_go.md).
- Phase 1 progressed from exploratory `board.v*` workflows to the pinned
  `board.v17` Beijing evidence and clean package gate at `0278b66`. The evidence
  and every intermediate failure remain in the `phase1_*` records.
- Phase 2 froze the development JSONL worker and process-isolation contract;
  its live result is preserved in
  [`docs/phase2_live_worker_result_2026-07-12.md`](docs/phase2_live_worker_result_2026-07-12.md).
- Phase 2A added local OCR, execution policy, provider error disposition,
  credential scheduling, and image resume. The dated checkpoint records remain
  under `docs/`; current implementation status is in the active-state file.
- PDF feasibility was conditionally accepted for future work using PDFium
  through `pypdfium2`, with no `PyMuPDF`/`fitz` in the active package. The
  feasibility result did not authorize Phase 3 support; the current go/no-go
  gate remains the authority.

### Historical Gate Criteria

The migration's historical definition of “done” required more than source code:
offline tests, compilation, a clean Git-archive wheel, an isolated install,
plain-import dependency isolation, fixture-byte/provenance checks, and a real
provider gate where the phase required one. A failing or unverified gate was to
remain recorded rather than be converted into a pass. The exact commands and
older measurements remain in
[`docs/ocrllm_library_go_no_go.md`](docs/ocrllm_library_go_no_go.md) and the
dated phase records.

### Historical Provider And Resume Decisions

The following decisions are preserved as dated records rather than copied into
the current status prose:

- provider/model configuration:
  [`docs/provider_workflow_configuration_decision_2026-07-12.md`](docs/provider_workflow_configuration_decision_2026-07-12.md)
- error taxonomy and dispositions:
  [`docs/provider_error_disposition_decision_2026-07-12.md`](docs/provider_error_disposition_decision_2026-07-12.md)
- credential-pool fairness and region binding:
  [`docs/dashscope_credential_pool_decision_2026-07-12.md`](docs/dashscope_credential_pool_decision_2026-07-12.md)
- image resume and versioned state:
  [`docs/image_resume_decision_2026-07-12.md`](docs/image_resume_decision_2026-07-12.md)
- local OCR boundary and optional dependency:
  [`docs/local_ocr_implementation_checkpoint_2026-07-12.md`](docs/local_ocr_implementation_checkpoint_2026-07-12.md)
- implementation and review chronology:
  [`docs/phase1_implementation_record.md`](docs/phase1_implementation_record.md)

These records explain why the current package is lightweight, lazy-importing,
typed at public boundaries, secret-redacting, and cautious about paid recovery.
They do not override the current Stage M findings.

### Historical Legacy Workflows

The old application workflows were not deleted during the migration. Their
current boundary and incident history remain in:

- [`docs/legacy_bilibili_social_long_debug_record.md`](docs/legacy_bilibili_social_long_debug_record.md)
- [`docs/legacy_youtube_playlist_social_long_workflow.md`](docs/legacy_youtube_playlist_social_long_workflow.md)
- [`docs/legacy_filetrans_codex_debug_record.md`](docs/legacy_filetrans_codex_debug_record.md)
- [`legacy_app/AGENTS.md`](legacy_app/AGENTS.md)

These records retain the two-Markdown social-long contract, resume/download
sidecars, Codex and FileTrans failure handling, Windows path lessons, and the
carry-forward warnings required when a vertical slice is ported. They are
legacy compatibility history, not active-library capability claims.

### Suspended Or Deferred Directions

The following directions remain traceable but are not current work:

- Rust/PyO3 rewrite: suspended in [`Architecture.md`](Architecture.md).
- HarmonyOS/ArkTS: deferred by the active go/no-go decision.
- Browser/React service: deferred until the core modality contracts are useful.
- Social downloading in `src/ocrllm`: rejected as a new-library boundary;
  retained only in `legacy_app/`.
- Public PDF, audio recognition, and video in the active package: phase-gated
  and unavailable as stated in the current active-state document. A1's internal
  local MP3 snapshot/probe seam is the only implemented audio component.

## Obsolete Prose Kept For Trace

Some old statements were removed from the navigation surface because they were
contradictory, not because their history was unimportant. Treat these as
**obsolete**, not current guidance:

- the old Phase 0/Phase 1 test counts and timing numbers;
- the pre-2026-08-18 claim that Stage M was not started;
- the earlier “no retry, model fallback, or provider switching” policy, which
  was replaced by disclosed opt-in recovery;
- the three-model DashScope allowlist as a caller-choice gate;
- the original Electron-worker-as-Phase-2 framing;
- any historical `Phase 1 remains NO-GO` sentence from a dated attempt before
  the pinned v17 gate.

The original wording remains recoverable in Git history and in the dated
records. It is not silently presented as current behavior.
