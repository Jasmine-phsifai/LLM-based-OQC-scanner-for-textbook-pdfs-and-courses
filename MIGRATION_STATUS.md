# OCRLLM Migration Status

This is a navigation aid. The authoritative current state, open defects, and
documentation rules are in
[`docs/ACTIVE_STATE_AND_RULES.md`](docs/ACTIVE_STATE_AND_RULES.md). If this
file and that file differ, that file wins.

## Current Status

Last synchronized: 2026-08-25.

The repository has two boundaries:

| Boundary | Status | Use |
|---|---|---|
| `src/ocrllm/` | Active library | New imports, stable API, root tests. |
| `legacy_app/` | Maintained compatibility app | GUI, CLI, FastAPI, social workflows, and behavior reference. |

The active library has GO coverage for the image contract, local OCR, the
development JSONL worker, provider error disposition, credential scheduling,
image resume, installed inline-type checking through `py.typed` and static-only
public facade exports, and a bounded
source distribution that contains only the active package and required build
metadata rather than the legacy app or working-directory artifacts. Stage M
Phase 1 maturation is offline implementation-complete:

- shipped: lazy DashScope catalog checks, atomic file-backed image state, an
  opt-in disposition-gated candidate model queue, candidate and final-output
  spend disclosure,
  model-aware credential blocking, scout-failure attribution, and slot-indexed
  intra-request checkpoints with an explicit v1-to-v2 identity migration;
  atomic Markdown/state temporary names are compact and do not repeat public
  destination basenames near the traditional Windows path boundary; a process-local
  output claim keeps concurrent batch/direct-thread Markdown and state ownership
  consistent; #071 narrowed only the top-level batch container to an exact
  `tuple` while preserving each item's existing atomic path or grouped
  `Sequence` contract. A complete read-only preflight rejects invalid sources,
  existing or duplicate output targets, and unsupported media before gates,
  claims, executors, snapshots, directories, or provider calls; the never-consumed
  `Config.progress`,
  generic `Config.cache_dir`, and four dormant PDF-only placeholders are
  removed rather than promoted into unproven callback, persistence, or PDF
  APIs; Google `RESOURCE_EXHAUSTED` classification gives explicit RPM/TPM/RPD
  or rate-window markers priority over quota-advisory prose, preserving
  provider-scoped rate limiting versus model-scoped spent quota; frozen worker
  progress remains separate, while local OCR retains its
  zero-network model-loading contract; resume source hashing is bounded on
  actual snapshot reads, and fresh provider/local-OCR results are rejected
  before checkpoint or final publication if those owned bytes no longer match
  the recorded request identity; terminal candidate failures retain local
  per-model ledger counts while reporting their sum at the top level, including
  checkpoint output failures and pre-dispatch zero-call catalog failures;
  failures after processor return while saving/validating state, publishing
  Markdown, or constructing the result likewise report only the current
  invocation's calls, including zero for completed-state replay;
  snapshot cleanup after a normal processor return follows the same rule, and
  local-OCR post-inference snapshot verification explicitly reports zero;
  batch outcomes preserve those structured item-local errors, while shared-gate
  cancellation before callable entry reports zero rather than a fabricated
  paid attempt and provider-raised cancellation after entry remains one;
  this is call/attempt disclosure; the native Google image adapter additionally
  accumulates provider-reported per-model input/output usage for fresh successful
  passes, preserving missing values as unknown; all no-cost exit criteria pass at product checkpoint
  `700cc05` through the clean-archive evidence recorded by `5d966e1` (root 1203
  passed; exact archive 1193 passed and 10 expected skips);
- open: the Stage M DashScope live exit smoke and live re-verification of
  provider account/model quota semantics. #104 confirmed the canonical Beijing
  endpoint but found no nonempty built-in DashScope credential in the current
  Process/User/Machine environment or legacy QSettings, so no request was made;
- replanned, in progress: the standalone Stage 2 vision/audio scaffold was
  removed; its audio-specific configuration boundary now lands with executable
  Stage A1 short-MP3 recognition, followed by provider-specific Stage A2 long
  audio. #150 supersedes FileTrans-first ordering: the first A2a implementation
  target is native Google Files because it is authorized for bounded live proof;
  DashScope FileTrans remains a later independent provider route. The A1
  offline slice may proceed independently of the open Stage M paid image smoke;
  bounded Google image/audio live work is already authorized without a separate
  budget request, while DashScope live work still requires a recognized
  credential and explicit maintainer budget. The provider-independent MP3
  probe now uses lazy `miniaudio>=1.71,<2`, fully decodes bounded five-minute
  snapshots, and rejects the fixture-proven malformed cases before dispatch.
  The user-facing `audio` extra remains independent, while `dev` also carries
  miniaudio and Google GenAI so the shipped short-audio tests run their real
  probe and SDK boundary in a clean development profile; the base distribution
  remains dependency-empty. #110 repaired that exact clean-gate dependency
  mirror and passed 1325 archived tests with one expected skip, a 202,692-byte
  wheel, and all six isolated profiles without a provider call.
  One local `.mp3` is copied through an open handle to fixed `source.mp3`, with
  a separate 25 MiB local safety ceiling and cleanup ownership;
  FFmpeg/PyAV/Mutagen remain outside the A1 runtime. Exact public audio
  configuration, facade dispatch, and in-memory result construction are now
  implemented for one native Google inline MP3 of at most 300 seconds, with a
  conservative provider envelope below 20,000,000 bytes. Pre-set cancellation
  stops before snapshot/copy/decode and is checked again before dispatch; the
  synchronous SDK call itself is not interruptible. Persistence, resume, groups,
  long audio, Files upload, retries, and fallback are not implemented in A1. The
  #097 returned an honest provider-scoped `PROVIDER_UNAVAILABLE` with no false
  success or snapshot residue and was not retried. After the maintained runner
  was simplified and its process contract was tightened, #103 refreshed the
  same bounded path successfully: catalog 37, exactly one provider call, and
  Google-reported input/output usage 150/9, with no retry or residue;
- implemented and live-proven for one provider-specific single request: Stage
  A2a long-audio recognition. #150 ran an audible 301.056-second MP4 through public
  `recognize_video()` without network. Five frames completed through one
  injected image call; the audio branch made zero provider calls and returned
  typed `SOURCE_TOO_LARGE`, so the outcome was honestly partial and retained
  its MP3. A2a is one standalone native Google Files upload, bounded readiness
  wait, generation, and remote deletion for an MP3 longer than 300 seconds.
  #151 ships public `recognize_long_mp3()` with chunked source snapshotting,
  bounded-memory full decode, the Google 9.5-hour/2 GB single-request ceilings,
  typed cleanup evidence, and no eager SDK/media imports. Its generated
  307.98-second live input discovered 37 models, made one
  `gemini-2.5-flash` generation, reported usage 9,893/25, deleted the remote
  file, closed the client, and left no residue. Chunking/resume is A2b; video
  integration waits for #127 cancellation and #149 snapshot placement. #152
  confirms A2b needs an audio-specific versioned sidecar rather than generalized
  image state, but leaves one maintainer choice: chunk only above 9.5 hours, or
  use fixed chunks for every persisted long-MP3 run so ordinary lectures can
  resume without replay. #153 corrects the frozen capability registry's stale
  long-MP3 reason to name this direct live-proven API while preserving its
  `deferred` worker-registration status;
- implemented and live-proven: the first PDFium vision slice. One PDF
  becomes serial eight-page image groups, ordinary image sidecars preserve
  settled work, range markers preserve group order, and rendered pages have a
  bounded lifetime. No PDF settings, PDF worker contract, repair, PyMuPDF,
  whole-file memory load, or arbitrary page selection was added.

The ordered current work is
[`#065 Unified Execution Queue`](docs/ACTIVE_STATE_AND_RULES.md#065-unified-execution-queue).
PDF recognition is implemented and live-proven: #078 discovered 37 current
Google models, then `gemini-2.5-flash` completed 16 pages as exactly two serial
requests with two complete checkpoints, ordered published output, aggregate
usage 4,802/117, and no retained rendered pages. Content repair remains
unimplemented by the explicit #120 product decision. #079 proved that active
failed Markdown has no defined marker yet: the producer publishes only complete
range sections and raises without final Markdown on a failed group. #080 then
proved that one failed-range marker plus the settled prefix cannot recover a
later unattempted suffix without becoming a second resume path. The maintainer
#120 then confirmed that historical Markdown with a legacy failed-page marker is
not an active-library compatibility input. No `repair_pdf()` or marker parser is
planned under the current contract; ordinary image-sidecar resume remains the
recovery path. Active partial-state semantics are not widened, and localized
legacy regex is not promoted into active identity.
Native Google direct-Python image recognition, experimental memory-only
short-audio recognition, and standalone single-request long-MP3 recognition are now
implemented, with per-model usage reporting when Google supplies it; no general
cross-provider token-usage claim is made. Resume is the primary recovery
path; marker-based PDF repair is intentionally absent after #120.
Offline tests are a regression floor, not live-provider evidence.
P0-a is complete in
[`docs/legacy_provider_error_action_evidence.md`](docs/legacy_provider_error_action_evidence.md).
The transport audit proved that legacy built-in Google uses native
`google-genai`; #067 completed P0-b. Its live gate discovered 37 models and
proved one `gemini-2.5-flash` image plus one eight-image group, one call each,
with input/output usage and an honest credential-scope authentication failure.
The maintained routine image runner now reuses that proof instead of replaying
it: #113 reduced each normal run to catalog discovery plus one single-image
public recognition and added safe catalog/model-selection/recognition failure
stages. Its bounded refresh found 37 models and completed one call with usage
595/443, no retry, output text, credential leak, or residue.
#115 also fixed native Google image failure accounting: catalog/model-selection
and other pre-`generate_content` failures now report zero recognition calls,
while a failure after entering `generate_content` reports one. The shared
provider wrapper preserves that adapter-owned fact without adding a ledger or
retry policy.
The direct API is proven, but the frozen 20-entry shared capability/worker
registry was deliberately unchanged and does not advertise Google worker support.
P0-c is complete. The earlier authorized `gemini-3.1-pro-preview` run remains
recorded as model-scoped `PROVIDER_QUOTA_EXHAUSTED`; #069 then selected
`gemini-2.5-flash` and completed one 3.468888889-second, 26,488-byte synthetic
MP3 through the public facade in exactly one provider call, with input/output
usage 150/10 and a separate credential-scoped invalid-key failure. No transcript
was published, so this is public-result and lifecycle proof, not a
transcription-quality evaluation. The direct path remains experimental and
memory-only. #107 made its failure-side attempted-call value explicit: zero for
adapter failures before `generate_content`, one after the single recognition
dispatch begins. #108 preserves the value of one when recognition succeeds but
owned-snapshot cleanup subsequently fails. Neither adds retries or a billing
ledger. The routine audio
live runner now omits the redundant invalid-key
request and reports a safe catalog/model-selection/recognition failure stage;
historical credential evidence remains unchanged. #114 refreshed that runner
after the later attempted-call and cleanup-accounting changes: one committed
0.5-second MP3 completed on `gemini-2.5-flash` in exactly one provider call,
with usage 55/2 and no retry, second probe, credential leak, or temporary
residue. #070 completed P1-a with eight authorized images: cancellation
observed one persisted draft after one call (usage 2401/1502), resume reused it
without replay and made one fresh review call (usage 4278/1066), then published
a complete result. Total calls were exactly two. #071 completed P1-b with an
exact top-level tuple, zero-side-effect full preflight, and two live ordered
eight-image groups. Both completed with one call each and complete published
state; reported input/output usage was 2401/1131 and 2401/988. #105 then
re-proved the shipped wheel itself from outside the repository: valid tuple
ordering, exact-container rejection, same-stem collision rejection, and a later
corrupt source all matched the public contract, with zero calls and zero
output/temp residue for every invalid case. #109 added a public serial MP3 batch
regression: success, one-call provider failure, and undispatched cancellation
remain ordered item outcomes with honest local call evidence. P1-c PDF through
the existing image/resume path now passes focused tests and a real local
16-page PDFium probe: two ordered eight-page calls, two complete child states,
zero retained rendered PNGs, and a one-call resume after the second group is
interrupted. #078 closed its Google gate with the same two-group shape and no
retry, fallback, or Files lifecycle. #102 narrowed bounded manual repair to one
confirmation: whether explicitly failed ranges in historical legacy Markdown
are an intentional compatibility input. #106 recorded a conditional narrow
implementation shape without treating it as consent. #120 then answered no:
active missing-state suffix recovery remains ordinary resume, and no legacy
marker parser or `repair_pdf` compatibility facade is built.
#085 briefly generalized settled usage around an internal response returned by an
injected test double. #086 found no valid public consumer for that behavior and
reverted it: injected providers return Markdown strings, Google retains its exact
built-in usage path, and the internal response type is not a public contract. The
protocol annotation and public README now state that boundary directly.
#088 maps decode failure of a library-generated PDF page PNG to local
`OUTPUT_WRITE_FAILED` instead of caller `InvalidSource`, preserving settled PDF
state and making no request for the failed group.
#089 then refreshed the real local 16-page PDFium public-facade path: two serial
groups, two complete sidecars, final output, and zero page/snapshot residue.
#116 closes the proven Windows junction escape at the same-named PDF state path:
an existing state object must be an ordinary directory, so a real junction now
fails with `OUTPUT_PATH_INVALID` before render/provider work while an ordinary
pre-existing directory remains valid for overwrite. No general sandbox, lock,
or check/use-race framework was added.
#073 strengthens the isolated installed-wheel proof for that same slice: a
real 16-page PDF must traverse public `recognize()` as two serial groups of
eight, publish two child states plus the final range-marked output, and leave
no rendered PNG or snapshot residue. It changes no public boundary and does
not replace the later successful #078 Google live evidence.
The shared 20-entry capability/worker registry remains unchanged and does not
advertise this direct audio path.
The generic compatibility endpoint and future local-model compatibility remain
separate later directions.

The defect register is in
[`docs/ACTIVE_STATE_AND_RULES.md`](docs/ACTIVE_STATE_AND_RULES.md). D1-D7,
F1-F4, and G1-G10 are closed in offline code and tests; the paid Stage M exit
gate remains open. Do not create a second defect list in this file.

## Read Order

1. [`docs/ACTIVE_STATE_AND_RULES.md`](docs/ACTIVE_STATE_AND_RULES.md) for
   current truth, defects, rules, and precedence.
2. [`docs/MAINTAINER_PRODUCT_DECISIONS.md`](docs/MAINTAINER_PRODUCT_DECISIONS.md)
   for durable maintainer constraints that the authority queue must reflect.
3. [`START_HERE.md`](START_HERE.md) for the one-screen repository map.
4. [`docs/plan_phase1_maturation_and_phase2_audio.md`](docs/plan_phase1_maturation_and_phase2_audio.md)
   for retained detailed Stage M and Stage A reasoning where not superseded by
   the authority queue.
5. [`docs/ocrllm_library_go_no_go.md`](docs/ocrllm_library_go_no_go.md) for
   execution gates and migrate/rewrite/reject boundaries.
6. [`src/ocrllm/README_ACTIVE_LIBRARY.md`](src/ocrllm/README_ACTIVE_LIBRARY.md)
   and [`src/ocrllm/AGENTS.md`](src/ocrllm/AGENTS.md) for package work.
7. [`legacy_app/AGENTS.md`](legacy_app/AGENTS.md) for legacy maintenance and
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
[`docs/ocrllm_library_go_no_go.md`](docs/ocrllm_library_go_no_go.md). A
DashScope live gate requires a nonempty recognized credential and explicit
maintainer budget; the Beijing region/endpoint is already confirmed. Bounded
Google image/audio robustness tests are already authorized without a separate
budget request.

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
- PDF text mode and repair plus long or persisted/resumable audio remain
  phase-gated and unavailable. #120 adds lazy MP4 inspection, #121 adds
  provider-free negative-feedback frame selection plus retained JPEGs, and
  #122 feeds the exact ordered retained-frame tuple through ordinary image
  recognition in groups of at most eight. #123 adds atomic, fully decoded MP3
  extraction; callers use separate image and audio `Config` calls, allowing
  different providers without a provider framework. #124 makes every settled
  frame group self-identifying with exact frame indices and timestamps so later
  composition cannot infer membership from a changed group size. #125 gives a
  truly silent MP4 the distinct `VIDEO_NO_AUDIO_STREAM` code while corrupt
  declared audio remains `VIDEO_INVALID`. Long-audio video routing remains
  unavailable even though #151 ships a separate standalone Files facade; final
  video-document publication is now the separate explicit
  step described below. The direct PDF vision
  facade and its ordinary image-sidecar resume are implemented; the
  experimental direct short-audio API is implemented and live-proven only for
  one in-memory MP3 of at most 300 seconds. Public `recognize_video()` now
  orchestrates the retained-frame and extracted-audio branches with separate
  configs and returns a typed complete/partial/failed outcome while retaining
  owned media. `VIDEO_NO_AUDIO_STREAM` is incompatible with an audio artifact,
  so a manual outcome cannot claim absence while exposing an MP3. A partial
  frame or audio child keeps the outcome and composed result partial. A
  successful frame-group result must describe an image. Its public
  outcome also rejects frame/audio paths outside the exact
  lexical `output_root/frames/*` and optional `output_root/audio.mp3` layout;
  retained frame indices must be strictly increasing and timestamps cannot move
  backward, including for manually constructed outcomes. Frame-group result
  indices must be contiguous caller order `0..n-1`; invalid structures never
  reach a misleading complete status. Every settled frame group must carry a
  valid immutable identity, and the flattened identities must exactly match the
  retained-frame tuple at outcome construction. It does not resolve aliases or
  symlinks.
  Each `RetainedVideoFrame` now requires the library's `.jpg` retained-asset
  suffix at construction. Existing image preflight remains responsible for
  existence and decoded JPEG validation; no filename/index identity or path
  resolution rule was added.
  `compose_video_result()` explicitly
  converts a returned complete
  or partial outcome into a memory-only standard video result with ordered
  frame and audio sections; it does not publish Markdown itself, resume video work,
  route long audio, or expose a worker command. Its composed current-run
  provider-call total is exact when every settled branch supplies evidence and
  otherwise `None`; missing evidence is never converted to zero. Safety-cap
  frame selection now preserves both video endpoints, so density limiting
  cannot silently discard the last retained candidate. Shared output-stem truncation now measures its
  existing 96-unit budget in Windows UTF-16 units, so supplementary characters
  do not overflow retained-frame paths. Maximum-length stable segments now use
  ceiling partition counts instead of rounding down and exceeding the selected
  attempt's bound. `publish_video_result()` now provides a separate atomic
  final-output step for an already-settled complete or partial outcome and one
  explicit caller path. It refuses overwrite by default and returns the same
  standard result with a verified output path; that path cannot replace one of
  the retained media assets, even with overwrite enabled. It does not derive
  legacy names, recognize again, or add recovery state. Cancellation refinement
  and resume remain separate. #145 executes the cancellation matrix and confirms
  the current facade is asymmetric: image cancellation returns branch evidence,
  audio cancellation can raise after a completed image branch, both signals do
  media extraction before raising, and silent video ignores audio-only
  cancellation. Legacy requires preservation of settled paid work but does not
  determine return-versus-raise for this non-persistent API, so #127 remains a
  maintainer choice before implementation.
  A clean wheel from exact commit `de10a2f` now independently proves
  `publish_video_result()` is packaged and externally consumable: nested atomic
  publication, no-overwrite, explicit overwrite, retained-asset collision
  refusal, `py.typed`, and lazy heavy imports all passed without network or
  provider calls. Pyright was unavailable, so no new static-checker result is
  claimed.
  #147 corrected the distribution Summary from the obsolete board/image-only
  scope to image, PDF, short audio, and video. #151 now supersedes that exact
  text with image, PDF, audio, and video after the standalone long-MP3 surface
  shipped. An offline baseline/candidate
  wheel comparison proves identical extras, requirements, member lists, and
  runtime payloads outside generated metadata; external lightweight import also
  passes. This is metadata accuracy, not a new capability.
  #148 fixes the coarse video scan's uncovered tail: the exact final source
  frame is appended when it is not already on the five-second grid, remains
  inside the existing 10,000-candidate bound, and participates in the unchanged
  negative-feedback selection. A real three-second MP4 with a final-frame scene
  change now retains both the opening and final frames; the complete offline
  suite passes 1,432 tests.
  #170 measures the remaining intended coarse-scan boundary with two real MP4s:
  a high-contrast scene entirely between five-second samples is not retained
  when the sampled first/grid/final frames remain unchanged. Caller-facing
  documentation now states this limitation; no fine-gap scan or second scene
  detector was added.
  #171 re-proves the post-#168 video runtime from exact commit `1c0362e` as a
  clean externally installed wheel. The new internal identity reader and
  `py.typed` are packaged; a real local MP4 completes with separate injected
  image/audio calls and composition, while fresh plain import remains free of
  optional media modules.
  #173 fixes a deterministic image-config preflight gap in the combined video
  facade. A missing Google vision model now raises before frame/audio output or
  either provider branch; the provider resolver reuses the same local validator
  instead of maintaining a second copy of those rules.
  #174 applies that zero-I/O deterministic preflight to the independently public
  retained-frame facade. Missing provider or Google vision-model configuration
  now raises before retained-JPEG validation instead of becoming a first-group
  outcome; generic batch settlement and valid group ordering are unchanged.
  #177 proves one real selected video crosses the default group boundary: ten
  retained frames dispatch as ordered 8+2 image calls while the separate audio
  configuration dispatches once, and provider-free composition reports three
  exact current-run calls. No runtime contract changed.
  #180 proves the corresponding later-failure path with the same real media:
  grouping ten retained frames as 3+3+3+1 preserves the first paid image result,
  records the second-call provider failure, cancels both undispatched suffix
  groups, and still completes the separate audio call. The partial composition
  retains every media asset and reports current-run calls as unknown because
  cancelled suffix groups have no call evidence. No runtime contract changed.
  #181 strengthens the real 8+2 success proof with two explicit native Google
  models: final composition preserves image usage as 22 input / 6 output tokens
  and audio usage as 7 input / 2 output tokens while retaining the exact three-
  call total. Public injected providers remain Markdown-only under #086; no
  provider or accounting contract changed.
  #182 upgrades the real 3+3+3+1 later-failure proof to the same native Google
  accounting path. The first image group and independent audio branch retain
  exact 11/3 and 7/2 model usage after the second image call fails; cancelled
  suffix groups keep the overall call total unknown. Request snapshots are
  cleaned and retained assets remain. No runtime contract changed.
  #183 corrects VFR parsing at the provider-free boundary: container duration
  now comes from existing FFmpeg metadata, coarse candidates are sought by
  presentation time, and retained identities use decoded frame PTS instead of
  `frame_index / FPS`. Exact-final-frame and bounded-candidate rules remain;
  #149 source snapshot placement is still open. An externally installed clean
  wheel reproduces the corrected 4.56-second VFR path without eager media imports.
  #184 verifies a real phone-style MP4 display matrix through the public
  provider-free path. The pinned OpenCV backend consistently changes 96x64
  encoded storage to 64x96 display dimensions for inspection, comparison, and
  retained JPEG pixels, so no manual rotation layer or public setting was added.
  #185 fixes grayscale-only selector loss with a small second thumbnail: a real
  equal-luminance red/green MP4 now retains all three sampled scene segments.
  The five-second grid and negative-feedback algorithm remain one bounded
  selector; no histogram or fine-gap detector was added.
  #186 sends that three-frame result through one bounded live Google combined-
  video run. Image and audio each attempted one call and independently returned
  `PROVIDER_RESPONSE_INVALID`; the failed outcome was not composed and no token
  usage was fabricated. The safe runner can now report validated per-model
  usage when a future settled composition actually supplies it.
  #187 proves real local audio corruption does not erase a valid image branch:
  image recognition completes once, audio dispatch remains zero, no MP3/staging
  survives, and composition reports partial with one exact current-run call.
  No cross-branch preflight transaction was added.
  #193 fixes the retained-JPEG writer's concrete Windows non-ASCII path failure:
  OpenCV still owns JPEG encoding and validation, while Python owns compressed-
  byte file I/O. A real MP4 now completes inspection, negative-feedback
  selection, and retained-pixel verification through Chinese source and output
  parent paths without adding a generic path layer or changing the output layout.
  #194 proves that correction from exact commit `a56d0de` as a clean wheel
  installed outside the repository: plain import remains lightweight and one
  real Unicode-path MP4 publishes the expected three retained JPEGs. The
  disposable build/install root was removed and no package boundary changed.
  #195 carries the same Windows non-ASCII boundary through a real audible
  `recognize_video()` call: independently configured image and audio branches
  each settle once, clean their separate snapshots, retain JPEG plus MP3, and
  compose in order. Existing multigroup tests continue to own 8+2 ordering.
  #196 takes that same real outcome through public atomic Markdown publication
  at a non-ASCII target and verifies returned path/content/assets/call metadata
  plus cleanup. No second fixture or publication subsystem was added.
  #197's one post-change Google attempt retained no branch result because its
  external controller confused settled failed outcomes with runner failures and
  discarded valid safe JSON. The maintained runner now distinguishes
  `video_outcome` from `runner_failure`; no live retry or product claim followed.
  #198 measures the selector's previously undisclosed memory cost without
  changing it: a ten-hour five-second grid retains at most 7,201 luminance-plus-
  color candidates, about 133.6 MiB of array payload and about 143.1 MiB measured
  process-private growth. Both representations have proven selection roles, so
  the library now documents this material bound instead of adding an unproven
  packed, spilled, or lower-resolution representation.
  #199 strengthens the real second-JPEG-failure regression: every OpenCV capture
  is closed, no target or staging directory survives, and the Windows source is
  immediately removable. No ordinary lifecycle defect was found. A synthetic
  interruption after successful directory rename can leave a complete target
  while propagating cancellation; it remains part of open #127 rather than
  receiving speculative rollback machinery.
  #200 rechecks the real legacy path boundary on a Windows host with long paths
  disabled. A 247-unit caller output parent produced a 280-unit final JPEG path
  and was rejected as `OUTPUT_PATH_INVALID` with no target, staging artifact,
  or locked disposable root. This is honest bounded failure, not extended-path
  support; no registry-aware preflight or path-rewriting layer was added.
  #201 resolves a documentation ambiguity without changing the facade: a real
  silent MP4 plus invalid audio settings raises `CONFIG_INVALID` before source
  inspection, output creation, or image dispatch. Silent audio becomes a
  frame-only outcome only after both required configs pass zero-I/O preflight;
  callers wanting no audio config use the existing frame-only public functions.
  #149 finds no further ordinary-content selector defect, then proves the next
  parsing-lifecycle gap with two real same-shape MP4s: replacing the source
  after coarse scan makes retained JPEGs come from new bytes while candidate
  thumbnails and indices came from old bytes, and the call reports success.
  A request-owned streamed disk snapshot is the recommended correction, but
  its output-sibling versus explicit public temp-directory contract remains an
  open maintainer choice; no partial snapshot implementation is shipped.
  #150 then proves the next consumer gap with a real 301.056-second local video:
  separate providers and partial outcomes behave honestly, but the current
  five-minute audio adapter rejects before dispatch. #151 completes the
  resulting standalone Google Files A2a slice; the remaining work is A2b
  chunk/resume and later video routing, not more selector tuning, a generic
  provider framework, or an untestable FileTrans-first abstraction.
  A clean archive of commit `c7f30f0` built and installed outside the
  repository without network, kept plain import free of heavy media modules,
  and completed one local video through separate injected image and fake-audio
  calls plus provider-free composition. Package examples now guard fully
  failed outcomes before that composition step.

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
