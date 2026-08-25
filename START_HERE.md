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
do not exist. #150 activated Stage A2 planning from a real 301.056-second public
video probe. #151 now implements and live-proves standalone
`recognize_long_mp3()` for one Google Files MP3 longer than 300 seconds and no
longer than the current 9.5-hour single-prompt limit. It owns the source,
uploads once, waits within the configured timeout, generates once, deletes the
remote file, and closes the client. Chunking, resume, fallback, batch/worker
support, and video integration remain later gates. #152 narrows A2b to one open
choice: chunk only the 9.5-to-10-hour overflow, or use fixed ordered chunks for
every persisted long-MP3 run so ordinary lectures can resume without replay.
No chunk/checkpoint implementation is authorized until that choice is made.
#153 also corrects the frozen capability registry's long-MP3 reason: it now
names the direct live-proven Files facade but remains `deferred` because no
shared worker route was added.

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
or retained sensitive/output data. #115 makes Google image failures equally
honest about dispatch: catalog/model-selection and other pre-generate failures
report zero recognition calls, while a failure inside `generate_content`
reports one. The smallest native Google short-audio
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
complete. #114 re-proved the maintained short-audio runner after those changes:
one committed 0.5-second MP3 completed on `gemini-2.5-flash` with one provider
call, usage 55/2, and no retry, second probe, credential leak, or temporary
residue. #070 then proved live cancellation after one settled
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
as three honest item outcomes. #078 completed P1-c PDF-through-image/resume.
#120 answered P1-d no: the library does not consume legacy localized repair
Markdown, so ordinary resume remains its PDF recovery path and no `repair_pdf`
compatibility parser is built. P1-e video is now active. #120 added
provider-free `inspect_video()` for one MP4 through a lazy OpenCV extra; #121
adds bounded coarse comparison, count-driven negative-feedback calibration,
and complete-directory retained JPEG publication through
`extract_video_frames()`. #122 recognizes ordered frame groups, #123 extracts a
validated MP3 so a separate audio config/provider can recognize it, and #124
keeps exact frame indices/timestamps on every settled frame-group outcome.
#125 distinguishes a truly silent MP4 from corrupt declared audio without
parsing FFmpeg logs. #126 adds public `recognize_video()` with separate image
and audio configs and a typed `VideoRecognitionOutcome` that retains honest
branch results/errors and media artifacts. #129 adds explicit, provider-free
`compose_video_result()` for complete or partial returned outcomes; it keeps
ordered frames and audio in separate sections without publishing a file or
inventing time alignment. #130 then built the exact current clean archive,
installed its wheel outside the repository, and re-proved that complete local
video path while keeping plain package import lightweight. #131 fixes the
density safety cap so it retains the final video candidate instead of possibly
ending early. #132 fixes shared output-stem truncation to use the existing
Windows UTF-16-unit budget while preserving complete Unicode characters. #133
uses ceiling partition counts so a maximum-length stable segment is not rounded
into too few retained intervals. #134's post-change Google video run proved the
image and partial-composition paths but lost the failed audio branch's safe error
evidence. #135 adds the maintained, redacted combined-video smoke runner with
separate image/audio configs and exact-or-unknown branch call evidence. #205
removes its obsolete shared-model CLI assumption: current runs require separate
`--image-model` and `--audio-model` values from one live catalog and validate
each branch against its configured model. The next bounded live run must use it
with a controlled one-image-group fixture. #206 completes that proof with
distinct current-catalog models: one image call returned typed
`PROVIDER_UNAVAILABLE`, while one audio call succeeded and preserved its own
200/14 token usage in an honest two-asset partial outcome. There was no retry
or model switch. #207 takes that exact image-failed/audio-success shape through
public atomic Markdown publication on real local media and confirms the error,
audio text, assets, calls, and audio-only usage remain honest. #136's
first such attempt lost its external asynchronous session identifier after the
runner completed, so it proves no provider outcome; the next controller must
poll that exact session and preserve safe JSON before cleanup. #137 did so: one
image call succeeded, one audio call returned `PROVIDER_QUOTA_EXHAUSTED`, and
the public outcome/composition honestly preserved a two-asset partial result
without retry or model switching. #138 then makes the public outcome reject
frame/audio paths outside its exact lexical `output_root/frames/*` and optional
`output_root/audio.mp3` layout before composition. #139 makes composed
current-run provider calls exact-or-unknown: any settled provider branch that
lacks reliable call evidence makes the total `None`; only a proven
pre-dispatch video/audio parsing branch contributes zero.
#140 rejects a contradictory video outcome that reports
`VIDEO_NO_AUDIO_STREAM` while also retaining `audio.mp3`; invalid public state
now stops at construction instead of becoming a complete composed result.
#141 fixes status propagation: a partial frame or audio child remains partial
in both `VideoRecognitionOutcome` and `compose_video_result()`.
#142 rejects a non-image `RecognitionResult` inside a video frame group before
it can be composed under the Frames section.
#143 re-proves the current facade from a clean externally installed wheel and
guards the package example so fully failed outcomes remain structured evidence
instead of being passed to `compose_video_result()`.
#144 adds separate `publish_video_result()` final Markdown publication for an
already-settled complete or partial outcome and an explicit caller path. It
reuses atomic output without changing memory-only composition or provider
dispatch. Cancellation refinement and resume follow from these observed
outcomes. #145 proves the current cancellation asymmetry with no provider calls:
image cancellation returns branch evidence, audio cancellation can hide an
already completed image branch, dual cancellation still parses media, and
silent video ignores an audio-only signal. The maintainer must choose returned
branch cancellation (recommended) or propagated cancellation with a new bounded
way to recover settled work before implementation. The audio slice
has no hidden retry, fallback, upload, persistence, resume, or worker-registry
claim. #146 additionally proves the new publication entry from an offline clean
wheel installed outside the repository, including actual Markdown publication,
overwrite safety, asset-collision refusal, packaged typing marker, and lazy
heavy dependencies. #147 updated only the wheel Summary to name the then-shipped
image, PDF, short-audio, and video surfaces; #151 supersedes that exact text with
image, PDF, audio, and video after the standalone long-MP3 facade shipped. The
earlier dual-wheel comparison proves extras, dependencies, members, and runtime
payloads did not change. The queue explicitly
records #148's frame-scan correction: the actual source final frame now always
participates in bounded comparison, so a scene change after the last five-second
grid position cannot disappear before negative-feedback selection. #149 then
proved a source-lifecycle defect: replacing the MP4 between coarse scan
and retained-JPEG decode can mix selection metadata from the old bytes with
frames from the new bytes while returning success. #211 closes it with one
library-owned streamed snapshot under `output_dir`; inspection, comparison,
retained decode, and combined audio extraction consume that path before cleanup.
No public video-temp parameter or legacy format was added. The queue still
stops further proactive
filesystem/accounting edge scans.

#224 separately proves that standalone `extract_video_audio()` had the same
mutable-caller-path risk between inspection and FFmpeg extraction. It now owns
one streamed snapshot under the output parent. Combined recognition calls the
narrow stable-source implementation with its existing #211 snapshot, so the
shared video is not copied twice. A real same-path 440/880 Hz replacement test
keeps the published MP3 tied to the inspected 440 Hz bytes and leaves no hidden
source or staging file.

#225 then runs the maintained redacted Google combined-video gate exactly once
after that lifecycle change. Two independent configs both explicitly selected
`gemini-2.5-flash`; one retained-frame group and one speech-audio branch each
completed in one generation. The public outcome/composition were complete with
JPEG plus MP3 assets and aggregated 796/17 token usage. Exit was 0 in 9,721 ms,
with no retry, fallback, model switch, credential/content/path/raw-response
leak, or request-owned residue. This refreshes runtime evidence; it does not add
a second audio provider or generalize provider routing.

#227 separately keeps the public no-output `inspect_video()` honest when its
caller path is overwritten during inspection. It compares the validated file
identity around the OpenCV/container-duration reads and rejects an ordinary
change with typed `SOURCE_INVALID`, instead of returning mixed metadata. It
does not copy or hash the entire video and does not claim protection against a
deliberate same-metadata overwrite-and-restore race.

#228 proves that exact behavior from a clean wheel installed outside the
repository. The installed public function remained lightweight and rejected a
real two-MP4 overwrite with exact `SOURCE_INVALID`; the wheel included the
inspector and `py.typed`. This is distribution evidence, not a new integrity
mechanism or permission to reopen #127/#152.

#229 removes one duplicate `VideoRecognitionOutcome` import left inside the
video facade after #219 had already made that type a required module-scope
binding. Runtime type hints, lazy imports, separate configs, and execution are
unchanged. This is a narrow readability reduction, not authority for mechanical
unused-code deletion.

#230 keeps the standalone `recognize_long_mp3` root API callable after an
explicit import of its same-named submodule. Only its lightweight facade is
bound during package initialization; decoder, processor, Google SDK, and Files
work remain invocation-lazy. A real 301-second MP3 with an injected lifecycle
completed once and removed its owned snapshot.

#231 proves that #230 package boundary from a clean wheel of exact commit
`9f515ad`. All five bound long-MP3/video functions remain callable,
identity-stable, and runtime-type-hintable in root-first and explicit-submodule-
first imports from an external no-dependency install; optional recognition,
media, provider, HTTP, and legacy modules stay unloaded.

#150 additionally exercises an audible 301.056-second MP4 through the public
video facade without network. The image branch retained five frames and made
one injected call; the audio branch made zero provider calls and returned typed
`SOURCE_TOO_LARGE`, leaving the top-level result honestly `partial` and keeping
the extracted MP3. This confirms provider separation and failure honesty, while
also proving that the five-minute A1 audio ceiling is not mature lecture-video
support. #151 completed standalone Google Files A2a independently; integrating
it into video still waits for #127 cancellation semantics. #211 closed the
former #149 source-snapshot placement blocker.

#072 has implemented P1-c offline: `recognize(one.pdf)` lazily uses
`ocrllm[pdf-vision]`, snapshots at most 100 MiB without whole-file Python reads,
renders one page at a time and one serial group of eight at a time, reuses the
ordinary image checkpoints, and publishes ordered range-marked Markdown plus a
same-named state directory. A real local 16-page PDFium probe and focused
cancel/resume tests pass; `recognize_batch()` intentionally rejects PDF for this
first slice. Its initial bounded Google exit attempt made zero provider calls
because the current Windows profile then had no Google credential.
The same-named state path must be an ordinary directory: #116 proves on Windows
that a pre-existing junction is rejected with `OUTPUT_PATH_INVALID` before
render/provider dispatch, while ordinary overwrite/resume directory behavior is
preserved. This is a narrow ownership check, not a filesystem sandbox.

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
P1-d is closed without legacy compatibility. P1-e local parsing and
retained-frame selection, frame recognition, audio extraction, and a concrete
image/audio provider split are implemented. Every frame group retains exact
identity for the next composition/lifecycle slice. Provider generalization
remains deferred.

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
short-audio recognition and standalone single-request Google Files long-MP3
recognition are live-proven but remain memory-only; their published gates are
not transcription-quality evaluations. PDF repair, long-audio chunk/resume,
and persisted/resumable audio remain unavailable. Video recognition is now
available as one typed orchestration facade over retained-frame extraction and
recognition plus independently configured extracted-audio recognition.
Provider-free composition and atomic final Markdown publication are separate
public steps. Video branch resume, long-audio routing, and worker routing remain
unavailable. The request-owned video snapshot implementation is present in a
clean externally installed wheel and does not make plain package import load
heavy media or provider modules. Local user
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
