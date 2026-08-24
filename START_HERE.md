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
docs/MAINTAINER_PRODUCT_DECISIONS.md  Maintainer choices preserved across handoffs;
                                      scope changes still require authority updates.
docs/plan_phase1_maturation_and_phase2_audio.md
                                      Retained Stage M/A detail; authority #065
                                      controls current ordering and providers.
docs/plan_phase1_defects_and_provider_split.md
                                      Stage 1 history; standalone Stage 2 was
                                      superseded by executable slices.
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

Minimal import example:

```python
from ocrllm import Config, GoogleGenAISettings, VisionModelSettings, recognize
```

Current phase: **Phase 1 maturation, Stage M offline implementation complete**. Phase 0
contract honesty, the Phase 1 image gate, the Phase 2 development worker, and
Phase 2A image-library completion are GO. Stage M has shipped lazy DashScope
catalog checks, atomic file-backed image state, an opt-in candidate queue, and
slot-indexed intra-request checkpoints with an explicit v1-to-v2 resume
identity migration, complete attempt-spend disclosure, disposition-gated
recovery, model-aware pool behavior, and correct scout-failure attribution.
Its DashScope live exit smoke remains open because the current workspace has no
nonempty recognized DashScope credential and no explicit paid-call budget. The
canonical Beijing endpoint is already confirmed. The former standalone Stage 2
scaffold was removed from the queue. The bounded Stage A1 direct slice is
implemented and live-proven: the lazy
`miniaudio>=1.71,<2` local MP3 probe, deterministic validation corpus, bounded
compact-name snapshot, exact audio-model configuration, native Google inline
request, public facade, and in-memory result are implemented for one MP3 of at
most 300 seconds. Persistence, resume, groups, upload, and long-audio routing
do not exist. Stage A2 has not started.

#110 re-proved the distributable boundary after the recent audio changes. A
clean archive ran 1325 tests with one expected skip, built a 202,692-byte wheel,
and passed dependency-empty base import plus audio, image, DashScope, Google,
combined audio+Google, and installed public PDF profiles without provider calls.

The ordered current work is `#065 Unified Execution Queue` in
`docs/ACTIVE_STATE_AND_RULES.md`. Its bounded legacy-provider audit and native
`google-genai` direct-Python image slice are complete. The #067 live gate found
37 current models; `gemini-2.5-flash` completed one image and one eight-image
group in one call each, reported real input/output usage, and returned a typed
credential-scope authentication error for the invalid-key probe. The shared
capability/worker registry remains frozen at 20 and does not claim Google worker
support. #113 reduced the maintained routine image check to one recognition
instead of replaying the historical group and invalid-key probes; its bounded
refresh found 37 models and completed one call with usage 595/443, with no retry
or retained sensitive/output data. The smallest native Google short-audio
direct API is live-proven for one memory-only MP3 and a bounded native inline
request below 20,000,000 bytes.
#068 first returned honest `PROVIDER_QUOTA_EXHAUSTED` / `model` on
`gemini-3.1-pro-preview`. #069 then selected `gemini-2.5-flash`: a
3.468888889-second, 26,488-byte synthetic MP3 produced one successful public
result in exactly one provider call with input/output usage 150/10; its separate
invalid-key probe returned credential-scoped authentication. No transcript was
published, so this proves the result boundary rather than transcription
quality. #107 additionally makes every error inside that adapter state whether
the one recognition call was actually attempted: zero before
`generate_content`, one after entering it. #108 also preserves that count when
the call succeeds but later owned-audio-snapshot cleanup fails. P0-c is
complete. #070 then proved live cancellation after one settled
Google image draft and resume of only the missing review: two total provider
calls, the draft reused with zero replay calls, and a complete published result.
P1-a is complete. #071 completed P1-b: `recognize_batch()` now requires an
exact top-level tuple while preserving each item's existing atomic-path or
grouped-`Sequence` contract, and validates the entire batch plus output targets
before any snapshot, directory, executor, or provider work. Two live groups of
eight images completed in order with exactly two total Google calls and complete
published state. #105 separately re-proved the exact-tuple, tuple-subclass,
same-stem collision, and later-corrupt-source behavior through public imports
from a freshly installed wheel; every invalid case made zero provider calls and
left no output/temp residue. #109 also proves an exact serial MP3 tuple keeps an
ordered success, a one-call provider failure, and an undispatched cancellation
as three honest item outcomes. #078 completed P1-c PDF-through-image/resume. Bounded P1-d
manual PDF repair is the immediate decision point, but #080 proved that a
single failed-range marker cannot recover an unattempted suffix under the
current serial fail-fast loop. #102 reduced the product choice to whether
historical legacy Markdown with an explicit `第 N` / `第 N-M 页识别失败` marker
is an intentional new-library compatibility input; implementation remains
paused for that confirmation. #106 confirmed that the general repair wording in
the maintainer-decision file is conditional, then fixed the recommended yes-path:
a separate `repair_pdf` facade, strict pre-dispatch marker/page validation, one
bounded request per original marker, span-based atomic replacement after every
success, and no active-producer/checkpoint change. The audio slice has no hidden
retry, fallback, upload, persistence, resume, or worker-registry claim. The
queue explicitly stops further proactive filesystem/accounting edge scans.

#072 has implemented P1-c offline: `recognize(one.pdf)` lazily uses
`ocrllm[pdf-vision]`, snapshots at most 100 MiB without whole-file Python reads,
renders one page at a time and one serial group of eight at a time, reuses the
ordinary image checkpoints, and publishes ordered range-marked Markdown plus a
same-named state directory. A real local 16-page PDFium probe and focused
cancel/resume tests pass; `recognize_batch()` intentionally rejects PDF for this
first slice. Its initial bounded Google exit attempt made zero provider calls
because the current Windows profile then had no Google credential.

#073 upgrades the isolated `pdf-vision` package smoke from a one-page backend
probe to a public 16-page installed-wheel run. It requires two serial groups of
eight through an injected no-network provider, two complete ordinary image
sidecars, ordered range-marked final output, and no snapshot or rendered-PNG
residue. This was packaging/runtime evidence, later complemented by #078 live.

#075 rechecked all implemented credential sources without reading or printing
a secret. Neither `GOOGLE_API_KEY`, `GEMINI_API_KEY`, nor the current account's
legacy `OCRLLM/QCR` QSettings key `ui/google_api_key` is available; the probe
succeeded and made zero provider calls. #076 then restored the legacy settings
entry path and the maintainer populated the existing QSettings source.

#078 completed P1-c. A foreground, no-retry `gemini-2.5-flash` run discovered
37 current models and recognized a 16-page PDF through exactly two serial
eight-page image requests. It reported aggregate usage of 4,802 input and 117
output tokens, published ordered output with two complete child checkpoints,
retained no rendered pages, cleaned both temporary roots, and exposed no key or
OCR body. Combined with the earlier offline resume and installed-wheel proofs,
the immediate queue is the P1-d compatibility-scope choice: support only
explicitly marked historical legacy failures, or freeze repair behind ordinary
resume. Widening active partial-state semantics is not recommended.
Provider generalization remains deferred.

All no-cost Stage M exit criteria pass at product checkpoint `700cc05`, with
the clean-archive evidence recorded by `5d966e1`. The root suite reported 1203
passed; the exact archive suite reported 1193 passed and 10 expected skips.
`tools/run_stage_m_offline_gate.ps1` reruns the exact Git-archive suite,
fixture/compile checks, clean wheel and outside-repository import guards,
dependency profiles, generated-image smoke, and offline DashScope construction.
It also runs installed public PDF recognition with an injected provider. It
makes no external provider request.

The public image facade decodes PNG/JPEG inputs before provider dispatch,
passes request-scoped validated snapshots to an injected provider, rejects
empty/control-only/refusal-shaped or non-UTF-8 output, returns typed redacted
errors, and reports canonical `source_type="image"` with `profile="board"`.
File output is optional and atomic; `output_dir=None` stays memory-only. Pillow
remains lazy during plain `import ocrllm`.

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
worker boundaries. The current allowed work follows the #065 queue in the
authority file. The detailed maturation/audio plan is retained as history and
bounded design evidence where it does not conflict with that queue.

The active library has a region-bound in-memory credential scheduler and
request/batch image resume. Candidate switching is opt-in, bounded,
disposition-gated, and fully disclosed offline. Experimental direct Google
short-audio recognition is live-proven but remains memory-only; its published
gate is not a transcription-quality evaluation. PDF repair, long audio,
persisted/resumable audio, and video remain unavailable. Local user
PDFs/screenshots under `docs/` are untracked
supplemental material, not redistributable gate evidence.

The defect register is only in `docs/ACTIVE_STATE_AND_RULES.md`. D1-D7,
F1-F4, and G1-G10 are closed in offline code and tests. Stage M itself remains
open only at that credential- and budget-gated live exit; provider-account
semantics are not claimed live-proven by the offline closure.

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

Before reporting completion, run the maintained clean-archive gate:

```powershell
& .\tools\run_stage_m_offline_gate.ps1
```

Its implementation and budgets are defined in
`docs/ocrllm_library_go_no_go.md`. Do not run the DashScope live gate until a
recognized credential and explicit paid-call budget exist, the exact
region/`base_url` is confirmed, and the runner's Git/import, manifest, artifact,
and credential preflight passes.

Active-library migration tests must not modify or run the legacy suite as a
phase gate. Create fixtures and tests under root `tests/`. Legacy commands and
tests are historical reference unless a separate legacy-maintenance request
explicitly authorizes that work.
