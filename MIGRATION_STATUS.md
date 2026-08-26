# OCRLLM Migration Status

This is a navigation aid. The authoritative current state, open defects, and
documentation rules are in
[`docs/ACTIVE_STATE_AND_RULES.md`](docs/ACTIVE_STATE_AND_RULES.md). If this
file and that file differ, that file wins.

## Current Status

Last synchronized: 2026-08-26.

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
  provider-scoped rate limiting versus model-scoped spent quota; #237 also
  preserves Google 503 `high demand` as provider-scoped rate limiting while
  leaving ordinary 5xx errors unavailable and adding no retry; #267 preserves
  production-backed DashScope 403 message-only free-quota markers as model-scoped
  quota exhaustion without exposing private exception text or adding retry/model
  switching; frozen worker progress remains separate, while local OCR retains its
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
  this is call/attempt disclosure; the native Google and OpenAI-compatible
  DashScope image adapters additionally accumulate provider-reported per-model
  input/output usage for fresh successful passes, preserving missing values as
  unknown; all no-cost exit criteria pass at product checkpoint
  `700cc05` through the clean-archive evidence recorded by `5d966e1` (root 1203
  passed; exact archive 1193 passed and 10 expected skips);
- closed by #339: the Stage M DashScope live exit. A credential-isolated current
  catalog returned 241 models and one explicit `qwen3.5-ocr` public formula-board
  recognition passed through the maintained one-call runner. Historical quota
  categories were not deliberately triggered and remain bounded robustness
  evidence, not a reason to keep the basic exit open;
- replanned, in progress: the standalone Stage 2 vision/audio scaffold was
  removed; its audio-specific configuration boundary now lands with executable
  Stage A1 short-MP3 recognition, followed by provider-specific Stage A2 long
  audio. #150 supersedes FileTrans-first ordering: the first A2a implementation
  target is native Google Files because it is authorized for bounded live proof;
  DashScope FileTrans remains a later independent provider route. The A1
  offline slice may proceed independently of the open Stage M paid image smoke;
  bounded Google image/audio live work is already authorized without a separate
  budget request. DashScope may reuse the legacy UI credential for one declared,
  bounded atomic trial after live catalog discovery, with a fixed call cap and
  no newest-flagship default. The provider-independent MP3
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
  bounded-memory full decode, the Google 9.5-hour/2 GB transport ceilings,
  typed cleanup evidence, and no eager SDK/media imports. Its generated
  307.98-second live input discovered 37 models, made one
  `gemini-2.5-flash` generation, reported usage 9,893/25, deleted the remote
  file, closed the client, and left no residue. Chunking/resume is A2b; video
  integration waits for #127 cancellation, while #211 has closed the former
  #149 snapshot-placement blocker. #216 additionally guarantees the client-close
  attempt still runs if remote deletion raises `KeyboardInterrupt` or
  `SystemExit`, while preserving that exact signal and local snapshot cleanup.
  #152
  confirms A2b needs an audio-specific versioned sidecar rather than generalized
  image state, but leaves one maintainer choice: chunk only above 9.5 hours, or
  use fixed chunks for every persisted long-MP3 run so ordinary lectures can
  resume without replay. #208 further records that the 9.5-hour check is only a
  provider transport ceiling: at Google's documented 32 audio tokens per second,
  it exceeds the selected-model input limit of live-proven `gemini-2.5-flash`.
  The recommended complete A2b contract is fixed chunks for every persisted run,
  caller-retained strongly matching source, and prompt-only 1,800/30 overlap
  handling; it remains unimplemented pending maintainer approval. #209 now
  reuses the one catalog response to reject before upload when audio alone, at
  the documented 32 tokens per second, meets or exceeds the selected model's
  advertised input limit. It adds no lookup or guessed prompt reserve and does
  not claim that every smaller request fits. #210 live-confirms that the current
  50-model catalog populates a positive-integer input limit on the explicit
  `gemini-2.5-flash` row through exactly one catalog-only operation, with no
  Files upload or generation. #153 corrects
  the frozen capability registry's stale
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
F1-F4, and G1-G10 are closed in offline code and tests; #339 closes the Stage M
live exit without claiming a broad model-quality or quota sweep. Do not create a
second defect list in this file.

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
The bounded DashScope live gate used the approved Beijing endpoint and closed in
#339 with one explicit model and one recognition call. Future DashScope quality,
quota, or error-category probes remain separately bounded. Google image/audio
robustness tests are authorized without a separate budget request.

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
  #149 source snapshot placement was still open at #183 and is closed by #211.
  An externally installed clean
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
  #202 proves the current negative-feedback selector retains one OCR-relevant
  transient edit without another detector: a sampled text line affecting about
  2.29% of the thumbnail clears accumulated drift and survives as the middle of
  retained frames 0/5/19. Legacy offers no stronger guarantee below roughly 2%,
  so no refine/pHash port, threshold change, or tuned regression was added.
  #203 sends that identical untuned transient-text MP4 through one authorized
  live Google call. Catalog discovery found 37 models; `gemini-2.5-flash`
  recognized both distinctive tokens from retained frames 0/5/19 in one image
  group, while silent audio made zero calls and composition completed with
  three assets. Usage was 1111 input / 55 output tokens; no residue or leak.
  #204 supplies the balanced nuisance-motion evidence: a real five-minute MP4
  with a small alternating cursor produced 61 candidates but calibrated to six
  published frames within the 5–10 target, while pixel checks proved three
  retained Slide A frames and three Slide B frames across the major transition.
  No threshold or cursor/subtitle detector was added.
  #205 updates the maintained live gate to match the already-public branch
  separation: Google combined-video smoke now requires independent image/audio
  model arguments, validates both against one current catalog before dispatch,
  checks each result against its own model, and preserves same-model aggregation
  or distinct-model usage. This is evidence tooling, not a new provider layer or
  public runtime API.
  #206 then invokes that gate once on a real five-second speech-and-text MP4.
  The exploratory `gemini-2.5-pro` image call returned `PROVIDER_UNAVAILABLE`,
  while the separate `gemini-2.5-flash` audio call succeeded with 200/14 usage;
  composition retained an honest two-asset partial result. No retry, fallback,
  product-code change, or provider generalization followed.
  #207 strengthens the existing real local MP4 regression through public final
  Markdown publication for the same all-image-failed/audio-success shape. The
  stable frame error, audio Markdown and usage, two retained assets, exact call
  total, partial status, and atomic cleanup remain available to Python callers;
  no runtime or API change was needed.
  #149 finds no further ordinary-content selector defect, then proves the next
  parsing-lifecycle gap with two real same-shape MP4s: replacing the source
  after coarse scan makes retained JPEGs come from new bytes while candidate
  thumbnails and indices came from old bytes, and the call reports success.
  #211 selects and ships the library-owned route: one hidden streamed snapshot
  under `output_dir` feeds inspection, comparison, retained decode, and combined
  audio extraction, then is removed. No public temp parameter, legacy format,
  whole-video memory copy, or generic media cache was added.
  #212 proves that cleanup on a corrupt post-snapshot parse and both pre-set
  branch-cancellation exits removes that hidden MP4 and releases its in-process
  output claim. The tests accept either future #127 cancellation contract and
  therefore do not freeze the current asymmetry; no runtime code changed.
  #213 proves that exact commit `2d49959` ships both new video lifecycle modules
  and `py.typed` in a 246,802-byte clean-archive wheel. A no-index/no-dependency
  external install resolves the public video callables and distribution metadata
  from the installed target without loading heavy media, provider, HTTP, or
  legacy modules. No package manifest or runtime change was required.
  #214 reserves the exact `output_root/audio.mp3` media path during final video
  Markdown publication even when the settled video is silent. A real silent MP4
  now gets typed `OUTPUT_PATH_INVALID` instead of a Markdown file disguised at
  the audio path, while retained JPEG bytes and cleanup remain intact. No wider
  output-directory policy or provider contract changed.
  #215 confirms #214 is not a general filename-extension policy. Final video
  publication writes UTF-8 Markdown to the complete caller-owned path; `.md` is
  recommended but not enforced. A mandatory suffix would be a new breaking
  product decision, not migration compatibility or a proven runtime defect.
  #217 re-audits the combined Python-library boundary and confirms that the two
  public configs already provide executable image/audio separation: branch
  provider, model, execution policy, cancellation, and temporary storage do not
  cross. Real local MP4 regressions for multigroup retention, distinct Unicode
  temp roots, and independent branch failure pass together with lightweight
  import. No runtime, provider abstraction, legacy format, or new live claim was
  justified.
  #218 fixes the active video facade's explicit-submodule import order. The two
  same-named function modules are now tiny initialization-safe definitions and
  the package binds their functions once, so a submodule-first import cannot
  replace the root callable with a module. Heavy video/audio backends, provider
  SDKs, recognition execution, and legacy remain deferred; the frozen worker
  collision is unchanged.
  #219 restores standard runtime type evaluation after #218's `TYPE_CHECKING`-
  only names made `typing.get_type_hints()` fail. Only the pure-Python public
  signature types load with the thin video facades; recognition execution and
  every optional dependency remain lazy.
  #220 applies the same proven collision fix only to public video composition
  and publication. Their functions are initialization-safe and root-bound,
  while composition, result-building, atomic output, recognition, and optional
  dependency implementations remain lazy. No package-wide proxy was added.
  #221 proves that complete four-function repair from exact clean commit
  `fbcca0c` as a wheel installed outside the repository. Both root-first and
  explicit-submodule-first imports preserve callable identity and exact runtime
  type hints, while recognition/output execution and every optional backend or
  provider remain unloaded. No packaging or runtime correction was required.
  #222 rechecks valid sub-five-second MP4s and confirms the current selector
  honestly returns one stable representative or opening/final changed frames.
  Interior scenes that both appear and disappear between those samples remain
  the documented #170 fine-gap limit; legacy samples even less at this seam, so
  no special short-clip sampler or refinement port was added.
  #223 verifies the other three public provider-free video functions retain
  callable identity, signatures, runtime type hints, and optional-dependency
  isolation in both root-first and implementation-module-first imports. Their
  nested modules cannot overwrite root attributes, so #218's eager-binding fix
  was intentionally not generalized.
  #224 fixes standalone video-audio source drift: the public extractor now
  owns one streamed MP4 snapshot for inspection, probing, extraction, and
  validation. Combined video reuses its existing #211 snapshot through one
  narrow private stable-source helper, avoiding a second whole-video copy.
  Real 440/880 Hz same-path replacement coverage proves output remains tied to
  the inspected bytes and all hidden source/staging paths are cleaned. No
  public API, provider, dependency, cancellation, or legacy format changed.
  #225 refreshes the real combined-video gate after that lifecycle change. One
  five-second synthetic speech-and-text MP4 completed through two independent
  Google configs on `gemini-2.5-flash`: one image-group call, one audio call,
  complete two-asset composition, and aggregated 796/17 token usage. The sole
  runner invocation exited 0 with no secret/content/path/raw-response leak or
  temporary residue. No runtime or provider abstraction changed.
  #227 prevents standalone `inspect_video()` from returning metadata combined
  from two ordinary same-path MP4 versions. It compares validated filesystem
  identity before inspection and after container-duration reading, then raises
  typed `SOURCE_INVALID` on change. The no-output API still avoids copying or
  hashing the whole video, and container duration remains authoritative for
  VFR input; this is bounded ordinary-change detection, not an adversarial
  integrity guarantee.
  #228 proves that exact #227 runtime from a clean, externally installed wheel.
  The 247,991-byte wheel contains the inspector and `py.typed`; its public
  function remains import-light and rejects a real two-MP4 caller-path overwrite
  with exact `SOURCE_INVALID`. A separate 108-test bounded audit found no next
  justified runtime defect inside the settled video scope, so no speculative
  lock, hash, snapshot, provider framework, or decision-bound code was added.
  #238 later supplies new contradictory real-media evidence: a valid one-second
  video stream with twelve-second AAC was rejected because the frame grid used
  the longer container duration. Coarse frame seeks are now bounded by the
  decoded stream's frame-count/FPS estimate; public container duration, exact
  final-frame PTS, VFR behavior, selector density, and provider behavior remain
  unchanged.
  #239 clean-builds exact `9b4d110` and confirms the dependency-empty base,
  two-entry `[video]` extra, package members, and `py.typed`, but does not close
  the normal installed-video gate. Bounded network delivery stalled, while a
  later offline install proved that cache metadata did not include the actual
  OpenCV wheel payload. No package defect was reproduced, so dependency pins,
  runtime code, and installer surface remain unchanged; installed real-MP4
  proof waits for the declared dependency payloads to be obtainable.
  #241 separately closes the post-#238 live-service question without claiming
  installed-extra success. One two-frame/one-second video stream with twelve
  seconds of audio passed public local preflight, then two independent Google
  configs completed one image call and one audio call. The outcome/composition
  retained JPEG plus MP3, reported 1,021/41 tokens, and left no credential or
  temporary residue. No runtime, dependency, retry, model switch, shared config,
  or provider abstraction changed.
  #242 completes deterministic image-provider preflight for the two public
  video entries: an injected object must expose callable `recognize_images`
  before MP4/JPEG work begins. Generic image recognition retains its pass-local
  execution check and therefore its workflow/model-attempt evidence. The final
  offline suite passes 1,502; no public API, provider framework, dependency,
  media behavior, or open-decision boundary changed.
  #243 completes the safely separable part of video cancellation preflight:
  both configs must expose a callable `is_set` member before any MP4 work, but
  the check does not invoke it. This prevents deterministic malformed-config
  failures after video snapshot/frame/audio work without choosing #127's
  cancellation outcome. The full offline suite passes 1,504; public API,
  providers, dependencies, output and media behavior remain unchanged.
  #244 removes the accidental cwd fallback from both public retained-video
  entries. Their required `output_dir` now accepts only a nonempty exact string
  or `Path`; malformed and signature-external values produce typed
  `OUTPUT_PATH_INVALID` before source/media work. The full offline suite passes
  1,510 without adding a generic path layer, long-path policy, dependency, or
  provider/media change.
  #245 verifies that `recognize_long_mp3()` results already satisfy the video
  outcome/composition contract, but rejects two premature integration shapes:
  manual low-level construction as the mature facade, and short-recognition
  failure as an automatic duration router. The ordered implementation gate is
  #127 first, then one-copy/one-decode selection of exactly one short or Files
  adapter; #152 remains required for 9.5-to-10-hour audio and persisted recovery.
  No runtime or public boundary changed; 84 focused tests pass.
  #246 rechecks #239 from exact commit `1e9cd87`: the clean 259,383-byte wheel
  retains an empty base and the exact two-dependency `[video]` extra, but the
  only normal pip attempt timed out downloading imageio-ffmpeg. Installed import
  and real-MP4 proof therefore remain open. No retry, alternate installer, pin,
  vendoring, runtime, or package-boundary change was made; 127 source-tree video
  tests pass and the disposable external root was removed.
  #247 completes the symmetric public regression for separated video branches:
  a real MP4 with successful frame recognition and one failed audio-provider
  call now proves partial outcome through final atomic Markdown publication,
  retaining frame text, JPEGs, MP3, stable error, and exact call accounting.
  This is test evidence only; runtime, provider policy, dependencies, #127, and
  #152 are unchanged, and the 127-test video set passes.
  #248 preserves a successfully parsed native short-audio response when only
  Google client close fails. Standalone and combined-video callers now receive
  a partial result with transcript, warning, call/token evidence, and explicit
  cleanup state; primary provider errors retain precedence. The complete
  offline suite passes 1,513. The analogous image close-only loss is recorded
  for a later atomic correction; no shared lifecycle framework was added.
  #249 fixes that native-image analogue locally. A parsed image response now
  survives SDK client-close failure as a partial result with warning, explicit
  cleanup state, and unchanged call/token evidence; primary errors still win.
  Real-MP4 coverage proves the independent audio provider still settles and
  final composition retains both branches. PDF combination also preserves a
  partial child status instead of reporting false complete. The full offline
  suite passes 1,517; no public API, dependency, provider framework, retry,
  fallback, legacy format, or frozen-boundary change was made.
  #250 proves the same image cleanup partial through two ordered successful
  video frame groups and final publication using one real multiscene MP4. The
  first group is partial, the second and audio are complete, while ordered
  Markdown, ten JPEGs, MP3, one warning, three calls, and per-model tokens all
  survive. Runtime was already correct and remains unchanged; the full offline
  suite passes 1,518.
  #251 truthfully leaves the normal installed-video gate open. Exact commit
  `20c9fd4` produced one 250,405-byte, 237-member wheel with correct empty base,
  extras/video requirements, package files, `py.typed`, and no native payload.
  The only fresh `[video,audio,image]` pip attempt did not commit, while its
  wrapper lost the original process's final exit diagnostics. No installed
  import/media claim or package/dependency failure is inferred; no retry, pin,
  installer, runtime, or API change was made.
  #252 adds a public 16-page PDF regression for #249's cleanup-partial image
  result. Two ordered eight-page groups publish as partial when the first is
  usable-but-partial and the second complete; both child sidecars preserve
  their own cleanup facts. Ordinary resume reuses them with zero provider calls
  while retaining the final Markdown and warning. Runtime was already correct;
  no PDF-level ledger, legacy repair format, retry, API, or dependency was added,
  and the full offline suite passes 1,519.
  #253 keeps the ordinary installed-video gate open with better failure
  evidence. The exact `b91d5d0` archive produced the same healthy 250,405-byte,
  237-member wheel, but the only fresh `[video,audio,image]` pip attempt exited
  1 after 26.064 seconds when the remote host reset the proxied
  `files.pythonhosted.org` connection while fetching imageio-ffmpeg (Windows
  10054). Nothing was installed and no installed-media claim followed. The
  disposable root was removed; runtime, metadata, dependencies, and API remain
  unchanged.
  #254 directly proves the provider-free audio extractor on one valid ten-hour
  audible MP4: the 146,920,984-byte input became a fully decoded and atomically
  published 144,000,512-byte MP3 in 54.886 seconds, then the disposable root
  was removed. Shorter independent measurements and legacy history provide no
  FFmpeg timeout failure evidence. The fixed 600-second per-process bound stays;
  no dynamic timeout, long-audio video routing, #127/#152 choice, API, or
  dependency was added.
  #255 proves the A2a local long-MP3 preflight stays memory-bounded through one
  real 9.5-hour file. Fixed 1 MiB snapshot copying plus 4,096-frame miniaudio
  streaming held fresh-process peak working set near 35.4 MiB for 301 seconds,
  one hour, and 9.5 hours despite file growth from 1.2 to 136.8 MB; all owned
  snapshots were removed. Full decode remains because it catches metadata/frame
  mismatch. No probe, API, dependency, Files lifecycle, chunking, video routing,
  #127, or #152 change was made.
  #256 runs one real one-hour MP3 through the public Google Files facade. The
  current 37-model catalog served `gemini-2.5-flash`; recognition ended honestly
  as `PROVIDER_RESPONSE_INVALID` after 32.203 seconds with no retry or fallback,
  and all local owned files were removed. The exposed diagnostics gap is fixed:
  future provider failures report a default disposition scope plus positive
  remote-file/client cleanup booleans when those resources existed. This does
  not claim the failed call's previously undisclosed remote-delete result or
  add retry, model switching, chunking, video routing, #127, or #152 behavior.
  #257 leaves ordinary installed-video execution open after the sole clean
  `[video,audio,image]` pip attempt timed out fetching imageio-ffmpeg. Its wheel
  audit reproduced a real backend-dependent manifest drift: Hatchling 1.31.0
  included repository-only `ocrllm/AGENTS.md`, while 1.32.0 omitted it. The
  wheel now explicitly excludes that one file and the maintained gate checks
  the actual member set. Both backends produce 237-member, approximately
  250.4-KiB wheels without the instructions; no dependency, runtime, API, or
  installed-media claim changed.
  #259 makes subsequent clean-gate delivery evidence bounded and recoverable:
  all seven optional-profile pip installs reuse one process-tree controller,
  expose a validated 30–3,600 second overall timeout (1,200 by default), use
  zero pip retries, and cap each connection wait at 30 seconds. A Windows
  PowerShell blank-exit-code defect in that controller was found by local fake
  children and corrected by retaining the native process handle before wait.
  Success, explicit nonzero exit, and timeout now pass offline regressions; no
  package dependency, runtime API, alternate installer, or installed-video
  claim changed, so the ordinary delivery gate remains open.
  #260 then exercises that bound with one clean-archive
  `[video,audio,image]` install. The 250,431-byte/237-member wheel remains
  healthy, but fresh pip exited 1 after 31.250 seconds without finding a
  `miniaudio>=1.71,<2` candidate and installed nothing. Official PyPI still
  exposes a 1.71 Windows CPython 3.10 x64 wheel matching the selected
  interpreter's leading compatibility tag, so this run does not justify a pin,
  extra, runtime, or installer change; its retained diagnostics cannot identify
  the exact delivery-layer cause. No installed-media claim follows and the gate
  remains open.
  #261 exercises the already live-proven video facade at its next controlled
  grouping boundary. The maintained Google runner now requires a one- or
  two-group expectation and performs provider-free frame-selection preflight
  before catalog/provider access; mismatches stop at zero calls. One 60-second
  synthetic video retained ten frames as ordered 8+2 groups. The first image
  group and separate audio branch each made one call and returned
  `PROVIDER_RESPONSE_INVALID`; the second image group remained an undispatched
  `CANCELLED` suffix with deliberately unknown call evidence. No composition,
  retry, fallback, model switch, token invention, or residue followed. This is
  runner-only robustness evidence, not a public planner or product API change;
  the complete offline suite passes 1,532 tests.
  #262 makes future failed Google video probes diagnostically useful without
  repeating #261. Missing response/candidate text now carries the fixed safe
  reason `missing_text`, and a mixed audio no-speech sentinel carries
  `invalid_no_speech_marker`. The maintained runner forwards only those plus
  the existing `empty`, `invalid_encoding`, and `refusal` reasons; arbitrary
  detail stays redacted. #261 itself remains unclassified beyond its recorded
  error code. Legacy retry/model switching was not ported, no live call or
  public API changed, and the complete offline suite passes 1,535 tests.
  #287 uses the first permitted post-basic bounded stress gate to classify the
  current two-frame-group failure after #262/#282. Two provider-free public
  preflights retained the same ten grayscale frames as ordered 8+2 groups, and
  audio extraction produced a nonempty MP3. One current-catalog runner made one
  first-group image call (`PROVIDER_RESPONSE_INVALID/missing_text`) and one
  independent pure-tone audio call (`invalid_no_speech_marker`); fail-fast left
  the second image group undispatched with unknown call evidence. Outcome was
  failed, composition did not start, and no asset/token evidence was invented.
  Exit was 1 after 12,742.019 ms with one safe JSON, empty stderr, no leak, and
  no residue. This content-free fixture proves honest failure settlement, not a
  two-group success path or causality from #282. No runtime, runner, API,
  dependency, retry/fallback, provider policy, legacy/social, #127/#152, or
  frozen boundary changed; the full offline suite remains 1,548 passed.
  #288 independently proves the corresponding content-bearing success path
  without replaying #287's failure fixture. A deterministic 60-second MP4 with
  large visible scene text and locally synthesized authorized speech retained
  ten frames as ordered 8+2 groups and a nonempty MP3. One current-catalog
  runner completed both image groups in exactly two image calls, completed the
  separate audio branch in one call, and composed eleven assets with verified
  usage of 5,214 input and 231 output tokens. Exit was 0 after 16.927 seconds
  with one safe JSON, empty stderr, no retry/fallback/model switch, leak, or
  residue. This proves only the capped two-group Google path with separate
  image/audio configs; it does not establish long-load, other-provider, retry,
  fallback, or long-audio behavior and changes no runtime or public API.
  #289 makes one later unchanged run of the still-open ordinary installed
  combined-video gate from exact `f674dab`. A pre-armed outer deadline and
  direct .NET Process controller retained exact exit 1 after 1,220,452.865 ms.
  The maintained archive stage reached its 1,200-second timeout while uv
  reported imageio-ffmpeg, NumPy, and OpenCV downloads; pytest never emitted
  `test session starts`, so wheel construction, profiles, and installed public
  video execution did not begin. This remains bounded external delivery
  evidence, not a package/runtime defect. No retry, policy change, provider
  call, or residue followed, and the installed combined-video proof stays open.
  #290 compares the legacy parent's Google failure evidence with all three
  active native adapters. Recorded refusal, empty/no-speech, 429 quota/window,
  503 high-demand, ordinary unavailable, model, authentication, permission, and
  request-invalid shapes are already typed and redacted; no runtime change is
  justified. A separate 400/`FAILED_PRECONDITION` payment example differs—
  active maps it request-invalid while legacy called it billing—but its source
  is explicitly code-only rather than a real incident. It remains frozen until
  native SDK evidence confirms the exact shape; no speculative payment marker,
  retry/fallback policy, billing layer, or provider abstraction was added.
  #291 performs one bounded current-catalog Google audio capability-mismatch
  gate. Official Gemma 4 documentation excludes audio from the live-served
  `gemma-4-26b-a4b-it`; one locally decoded 8.038141-second MP3 through the
  maintained public runner returns the already-correct
  `PROVIDER_UNAVAILABLE/model/recognition` result in 4.516 seconds. There is no
  retry, fallback, model switch, leak, residue, or runtime/API change. The safe
  failure output does not expose generation-attempt count, so that evidence is
  recorded as unknown. This is not a hardcoded capability list, model-by-model
  probe, stress framework, or provider abstraction.
  #292 fixes one public parallel-batch fail-fast race. Under a controlled legal
  completion order, both initial futures were terminal but the collector saw
  the success before the typed failure and started a third paid provider call.
  The failing worker now aborts the existing shared start gate before re-raising
  its `OCRLLMError`. The causal public regression changes from three calls to
  two; the initial success/failure and cancelled suffix remain ordered, and
  already-started work still settles. No scheduler, new lock, retry, result
  schema, provider API call, or #127 cancellation choice was added.
  #293 validates one current near-wire-limit Google image request without
  changing the package. A deterministic 14,922,997-byte JPEG produced an exact
  active-builder upper bound of 19,899,869 bytes, 100,131 below the 20,000,000
  local ceiling. One maintained `gemini-2.5-flash` run discovered 37 models and
  succeeded with one call, usage 595/43, exit 0, empty stderr, no leak, and no
  residue. This single payload does not justify raising the limit, retaining a
  large fixture, probing sizes/models, or adding a stress/benchmark framework.
  #294 resolves the former #127 video cancellation decision with maintainer-
  selected Route A. One cancelled branch now settles in the existing frame or
  audio error and preserves the other branch; pre-cancelled audio skips MP3
  extraction, and dual pre-cancellation stops before source/output work. Four
  public regressions replace the prior permissive matrix. No new result type,
  exception carrier, checkpoint, coordinator, or extractor cancellation API
  was added. #152 separately selects recoverable Route B with explicit whole
  and integer-minute interval modes. #304 then selected a private fixed 30
  seconds of context on each side of every interior logical interval, exact
  logical/actual temporary resume identity, and no text-similarity deduplication.
  No chunk implementation landed in either decision iteration.
  #263 leaves the ordinary combined `[video,audio,image]` installed gate open.
  One clean `a83205a` wheel and fresh CPython 3.10.20/pip 23.0.1 venv reached an
  HTTP-200 40.2 MB OpenCV wheel download, then recorded no progress. The
  delegated operator had omitted an explicit overall deadline and returned
  before terminal exit, so the owned process tree was subsequently terminated
  and its root removed; no distribution or partial `cv2` artifact was committed.
  Treat this as incomplete operator evidence, not a product or dependency
  failure. Future download tasks must enforce their bound before launch.
  #264 moves that exact combined proof into the maintained clean gate instead
  of repeating one-off operators. The gate now has a `video,audio,image`
  profile that reuses the existing bounded installer, installs only the union
  of declared extras, and runs the installed public video recognition,
  composition, and publication path on a real generated MP4 with independent
  image/audio Configs and deterministic offline provider seams. It verifies
  retained JPEG ordering, MP3 validation, call/token accounting, assets,
  publication, and temporary cleanup while proving the Google SDK is absent.
  The individual `[video]` profile and package metadata are unchanged. The
  package/video neighbor set passes 80 tests and the full offline suite passes
  1,536; because the clean gate was not run in this iteration, installed
  combined-video delivery remains an open gate. A later bounded run may be
  followed by separately scoped, capped robustness stress tests.
  #265 executes that maintained gate once from exact commit `7ff38c4` under a
  3,600-second outer watchdog and the existing stage bounds. It reaches only
  archived-source dependency preparation: uv exits 1 after failing to
  download/extract `opencv-python==4.13.0.92`, naming an extraction I/O failure,
  a network timeout, and its current 30-second HTTP timeout. No tests, wheel,
  profile, combined-video proof, or provider call follows. The process, gate
  root, and wrapper logs are clean, while the local gate regressions pass 5
  tests and compileall succeeds. Treat this as one terminal delivery failure,
  not justification for timeout/index/cache/pin/retry changes; the installed
  combined-video gate remains open.
  #268 re-runs the same maintained gate once from exact `6386401`. Its own
  archived-source stage times out terminally at the declared 1,200-second bound
  after one uv PID reports progress for imageio-ffmpeg, NumPy, and OpenCV; no
  explicit retry/restart, pytest, wheel, optional profile, installed-video path,
  or provider call follows. The delegated outer wrapper briefly exits after
  colliding with PowerShell's read-only `$PID`, then attaches a corrected
  watchdog to the same gate process without retaining the attachment time.
  Therefore the stage timeout is valid, while a continuously pre-armed outer
  bound is not claimed. All owned processes and temporary roots are gone. This
  remains external pre-test delivery evidence and does not justify immediate
  replay or dependency/installer changes; the combined installed gate stays open.
  #269 adds the missing public built-in DashScope proof for #267: an explicit
  two-model tuple makes one 403 message-only free-quota call on the first model
  and one successful call on the second. The final ledger reports both calls,
  both clients close, and a one-slot credential pool blocks only the first model
  while remaining account- and credential-available. Private error/key text is
  absent. Runtime and provider policy are unchanged; the full offline suite
  passes 1,540.
  #272 preserves a successfully parsed built-in DashScope image response when
  only client close fails. It reuses the existing internal vision response
  cleanup bit, so callers receive partial Markdown, one provider-specific
  warning, exact call evidence, and `provider_client_closed=False`; primary
  provider errors retain precedence. A one-slot credential pool records one
  success and no block/failure because local cleanup is not provider failure.
  The full offline suite passes 1,542. No public response protocol, provider
  framework, retry/fallback, dependency, legacy format, or frozen boundary was
  added. #273 closes the separately observed empty model identity in an
  implicit-default DashScope `model_attempts` row. The ledger now names the
  pinned baseline used by the actual request on success, provider failure, and
  output failure, while caller config and resume identity remain implicit.
  Explicit candidates, injected providers, catalog/configuration failures, public
  APIs, and provider policy are unchanged; 113 related and all 1,542 offline tests
  pass.
  #274 makes the maintained archived-source gate stage observable without
  replaying it: pytest now uses `-ra` rather than `-q`, so its session header
  positively marks that uv dependency preparation completed and test execution
  began. The single uv process, 1,200-second total bound, requirements, resolver,
  network/cache/retry behavior, and cleanup are unchanged. Gate-control tests
  pass 5 and all 1,542 offline tests pass. No download or clean gate ran; the
  ordinary installed combined-video proof and later stress gate remain open.
  #275 adds direct public evidence for #273's output-failure branch without a
  runtime change. One implicit built-in DashScope draft succeeds, atomic slot
  persistence fails, and the typed ledger names the pinned baseline with exactly
  one call and no fabricated token usage. No final Markdown, state, or temporary
  file survives; 92 related and all 1,542 offline tests pass.
  #276's intended one-image/one-short-audio Google refresh produced no valid live
  evidence because its delegated wrapper retained neither exact child exit nor
  either runner's safe terminal JSON; runner invocation, call counts, and
  outcomes remain unknown. Cleanup and secret scanning passed, no replay was
  made, and a zero-network isolated import still resolved this workspace. No
  product change follows from the operator failure. The maintained Google
  runner/adapter set passes 93 tests and the full offline suite passes 1,542.
  Future stress robustness tests remain separate atomic gates after valid basic
  installed/live proof, with explicit question, scale/call bounds, deadline,
  failure criteria, and cleanup rather than a general provider load framework.
  #277 fixes one active video outcome-boundary defect. A real corrupt-audio
  partial result retained the correct typed extraction failure but also exposed
  its internal traceback. The facade now clears traceback/cause/context from
  settled frame/audio errors immediately before returning the outcome, without
  flattening error facts, changing calls/assets, or selecting #127 cancellation
  semantics. The causal regression failed before the change; 105 video
  neighbors and all 1,542 offline tests pass afterward.
  #278 rejects impossible negative token counts at the existing shared
  aggregation boundary. A public caller-created audio result previously made a
  composed video publish negative per-model usage; the invalid optional row is
  now omitted while `None`, zero, and nonnegative per-model accumulation retain
  their existing meanings. The audit separately confirmed that standalone
  audio's one-call `provider_call_count` and the composer's compatibility read
  are intentional, so no duplicate current-run field was added. The causal
  regression failed before the change; 140 neighbors and all 1,543 tests pass.
  #279 attempted the single later ordinary clean-package gate run permitted
  after #274, but its one-use outer wrapper lost repository-path quoting before
  the maintained script started. PowerShell rejected the truncated `-File`
  argument in about one second, so no archive, download, pytest, wheel install,
  combined-video path, or provider call ran. The exact temporary wrapper was
  inspected and removed without replay. This is invalid operator evidence, not
  a package failure; the installed combined-video gate remains open and later
  bounded pressure robustness tests still follow valid basic installed/live
  proof.
  #280 fixes silent annotation loss at the existing result boundary. Both
  `RecognitionResult` and `ProcessorOutput` previously validated one-shot
  `hotwords`/`warnings` iterables and then converted the exhausted values to
  empty tuples. They now snapshot once, validate, and store that same tuple,
  preserving the existing normalization behavior without changing batch tuple
  policy or adding an abstraction. Two causal regressions failed before the
  fix; 74 adjacent tests and all 1,545 offline tests pass afterward. A bounded
  re-audit found no justified additional video composition/publication change.
  #281 validly refreshes the free-tier short-audio public path from exact commit
  `2844513`: live catalog 37, `gemini-2.5-flash`, one provider call, usage 55/2,
  exit 0, empty stderr, and no secret/current temp residue. The paired image
  child started and terminated, but its one-use PowerShell harness mixed async
  stdout reading with `ReadToEnd()` and discarded exit/JSON; image calls and
  outcome remain unknown and were not replayed. No product/runner change follows
  from that operator-evidence failure. All 1,545 offline tests still pass.
  #282 fixes the same proven one-shot consumption pattern at the shared Google
  response parser. Candidate safety inspection previously exhausted a valid
  iterator before candidate-part text fallback, producing a false
  `missing_text` provider failure. One local tuple snapshot now serves both
  reads; missing/unreadable candidates retain the prior safe failure. No generic
  iterable layer or provider-policy change was added. The causal regression
  failed before the fix; 144 Google neighbors and all 1,546 offline tests pass.
  #283 attempted one later terminal run of the maintained clean gate from exact
  commit `8a97dce`, but the encoded child PowerShell's default execution policy
  rejected the `.ps1` before the first stage. Empty stdout and a 905-byte
  policy-error stderr prove that no archive, download, pytest, wheel,
  installed-video, credential, or provider work began. Numeric exit and elapsed
  were not retained, so this remains invalid operator evidence and was not
  replayed; no package or gate defect is inferred. This repeated an already
  recorded local launch prerequisite: a future disposable child must use
  process-only `-ExecutionPolicy Bypass` while retaining exit/timing,
  without changing machine policy or delivery settings. The ordinary combined
  install proof remains open; later capped stress robustness tests still follow
  valid basic installed/live proof.
  #284 then entered the unchanged maintained gate from exact `6f3e8e4` with the
  known process-only execution-policy prerequisite. The gate ended at its own
  1,200-second archive dependency/pytest timeout after 1,202.327091 seconds;
  archive expansion and uv download markers appeared, but the pytest header,
  wheel, profiles, combined installed-video proof, credentials, and provider
  calls did not. This is terminal external delivery evidence, not a package
  runtime failure, and was not replayed. Its numeric exit remained null; a
  zero-network `exit 7` child proved that this host's Windows PowerShell
  `Start-Process -PassThru` also returns null after WaitForExit/Refresh. Future
  evidence collection should use direct .NET Process APIs or a small explicit
  status channel without changing the maintained gate or delivery policy. All
  owned roots/processes were cleared; the ordinary combined install gate and
  later bounded stress gate remain open in that order.
  #285 fixes one post-settlement public video lifecycle defect. When both image
  and audio work had completed but final request-owned source-snapshot deletion
  failed, the context exit previously discarded the built outcome and all
  recognition text/call evidence while leaving final JPEG/MP3 assets. The exact
  cleanup error now carries `stage=video_snapshot_cleanup` and is retained as
  `VideoRecognitionOutcome.snapshot_cleanup_error`; an otherwise complete
  outcome becomes partial and can still be composed or atomically published
  with its recognized work, call/token evidence, fixed warning, and
  `video_cleanup_error_code`. Other errors are unchanged. The causal regression
  failed first, video neighbors pass 117, result/import neighbors pass 39, and
  all 1,548 offline tests pass. No generic lifecycle layer, cleanup retry,
  resume/provider policy, #127/#152, legacy/social, or frozen boundary changed.
  #286 closes the invalid #281 image refresh with one valid terminal run from
  exact clean commit `074c287`. The maintained routine runner discovered 37
  current models, completed one `gemini-2.5-flash` image request in 21,785 ms,
  and reported one provider call plus usage 595/414 before exiting 0 with empty
  stderr. Primary review found no exact credential, credential pattern, source
  path, live process, new image snapshot root, or wrapper residue. Direct .NET
  Process APIs fixed only the one-use exit-evidence path; runtime, runner,
  dependencies, public API, retries/fallback, and provider policy did not
  change. Later pressure robustness tests may exercise this live-proven flow as
  separate single-question, capped, deadline-controlled and cleanup-verified
  gates, not as a generic load framework.
  #229 removes the sole exact duplicate import found by a bounded reduction
  audit: `VideoRecognitionOutcome` remains module-bound for runtime type hints
  and is no longer rebound inside `recognize_video()`. No public contract,
  import graph, provider/media behavior, or package boundary changed; the audit
  rejected broader mechanical cleanup without an equally explicit reason.
  #230 keeps the standalone long-MP3 public API stable under ordinary Python
  import order. Explicitly importing `ocrllm.recognize_long_mp3` no longer
  replaces the root callable with a module; only the lightweight facade is
  package-bound, while decoding and Google Files execution stay lazy. A real
  301-second MP3 and injected one-call lifecycle verified snapshot ownership
  and cleanup without adding legacy compatibility or A2b behavior.
  #231 proves that changed import boundary from a clean, externally installed
  wheel of exact commit `9f515ad`. The long-MP3 facade and all four bound video
  facades retain callable identity and standard runtime type hints under both
  import orders, while optional recognition/media/provider dependencies remain
  lazy. No runtime, manifest, dependency, provider, or legacy behavior changed.
  #232 fixes the same ordinary import collision for the primary `recognize`
  and `recognize_batch` APIs. Both root functions are now initialization-bound
  and runtime-type-hintable, while batch preflight, output claims, validation,
  execution, media, and provider work remain invocation-lazy. Recognition
  behavior and media/provider separation are unchanged; installed-wheel proof
  follows as a separate bounded gate because the import boundary changed.
  #233 completes that gate from exact commit `79ad5d0`: one clean wheel installed
  outside the repository preserves callable identity and runtime type hints for
  the two primary, long-MP3, and four video facades under both import orders.
  Package/distribution origins are external, while preflight, output claims,
  validation, processors, adapters, and optional dependencies remain lazy.
  No runtime, API, manifest, dependency, provider, media, or legacy behavior
  changed.
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
  #295 does not supersede that historical slice or close the current all-extra
  gate. From exact clean commit `bfdc877`, the active `127.0.0.1:10080` proxy
  reached PyPI and was explicitly propagated to one unchanged maintained gate,
  but the one-use wrapper lost stdout, stderr, and numeric exit evidence after
  about 20 minutes. The gate cleaned its temporary root. Archived tests, wheel,
  optional profiles, and installed combined-video execution are therefore all
  unknown, not failed or passed. No library boundary, dependency, or runtime
  changed; the next attempt must first prove its local status channel and must
  not immediately replay this download workflow.
  #296 proves that prerequisite without another download: a disposable local
  Python `subprocess.run()` probe retained exact exits 0 and 7, both output
  streams, and timeout output. A separate owned parent/descendant probe proved
  exact Windows tree termination after the outer timeout, while all five
  existing gate process regressions passed. The probes were deleted and no new
  controller or package boundary was added. The installed combined-video
  result remains unknown and open.
  #297 closes the bounded video long-audio integration seam that #245 left
  behind #127. One retained extracted MP3 is copied to one request-owned
  snapshot and fully decoded once; duration at or below 300 seconds selects the
  existing inline adapter, while greater duration through 9.5 hours selects the
  existing Google Files lifecycle. A real generated 301-second MP4 reached
  Files exactly once, never entered short recognition, preserved separate image
  work and the retained audio artifact, and removed its owned audio snapshot.
  General `recognize()` routing, A2b chunks/resume/repair, and the private
  9.5-to-10-hour range remain unchanged. #304 subsequently closed the A2b
  overlap choice at a private fixed 30 seconds per side without implementing
  chunking. #305 adds only the internal deterministic interval planner: exact
  integer-minute logical windows, clamped 30-second physical context, tuple
  order, and immutable identity fields. Media cutting, provider dispatch,
  temporary persistence, public routing, and repair remain later slices. #306
  repairs the clean gate's first post-build check: Windows PowerShell had split
  multiline `python -c` source and supplied `is` as the apparent wheel path.
  The three wheel-content assertions now live in the single-purpose
  `tools/check_built_wheel.py`; no package runtime changed. Its clean rerun
  passed archive tests and base installation, then found the real installed
  target at 1,265,634 bytes above the historical 1 MiB cap. #307 measures
  624,362 bytes of source, 545,781 bytes of installer bytecode, 59,025 bytes of
  metadata, and 36,455 bytes of package documentation, with no accidental
  tests/legacy/media payload. It retains this real-disk measurement and raises
  only the base target cap to 1.5 MiB; the 256 KiB wheel cap remains unchanged.
  Its clean rerun passes base and the first six optional profiles, then fresh
  pip reports no candidate for the video OpenCV range. #308 proves from current
  official PyPI metadata and a no-cache dry resolution that 4.13.0.90 and
  4.13.0.92 remain compatible with Windows CPython 3.10 and that 4.13.0.92 plus
  NumPy 2.2.6 resolves through the active proxy. The tested bounded pin is not
  changed for one transient empty candidate response.
  #309 then stages the exact media wheels once through the proxy; video installs
  and its media smoke passes, proving the pin and runtime, before the measured
  254,451,578-byte delta exceeds the original unproven 220 MiB estimate. #310
  confirms 245.1 MB of expected uncompressed OpenCV, NumPy, and bundled
  imageio-ffmpeg payload, raises video to 260 MiB, and preserves the existing
  sum rule by raising combined video+audio+image to 293 MiB. No dependency,
  runtime, or profile membership changes.
  The next gate installs combined video but its embedded fake patches the old
  standalone short-audio processor, so the audio branch honestly settles an
  error and `outcome.status` is not complete. #311 changes only the gate seam to
  `processors.recognize_video_mp3.recognize_short_mp3`, matching shipped #297;
  no public/runtime compatibility wrapper is added. The final exact `d80170f`
  clean gate passes all eight profiles; combined video+audio+image measures
  272,322,996 bytes and its installed public recognize/compose/publish smoke
  completes with two retained frames, one image call, and one audio snapshot.
  #312 adds the next internal A2b seam without exposing chunked recognition:
  one validated interval window materializes one request-owned temporary MP3
  beside an already-owned source, using the legacy-proven Google shape of mono
  16 kHz / 64 kbps FFmpeg re-encoding. The context manager removes the segment
  after success, consumer failure, or backend failure; it does not retain
  legacy chunk directories or add parallel splitting, dispatch, resume, repair,
  retry, or provider generalization. The `audio` extra now includes the existing
  pinned lazy imageio-ffmpeg dependency. Its isolated size ceiling becomes
  100 MiB and audio+Google becomes 140 MiB; combined video+audio+image remains
  293 MiB because the same FFmpeg distribution was already in that dependency
  union. The exact `a9dc6e6` clean gate exits 0: audio is 91,174,290 bytes,
  audio+Google is 130,218,489 bytes, its installed interval smoke cleans the
  temporary segment, and every existing profile plus combined video remains
  green without a provider call.
  #313 adds the missing strong source fact for that future state. The existing
  bounded MP3 snapshot copy hashes each completely written chunk and propagates
  the canonical SHA-256 through short, long, and video route wrappers. It adds
  no second scan, provider work, public metadata, state file, or image-slot
  dependency. Source and adjacent media/provider tests pass. The exact
  `b9ae0c9` clean gate exits 0: 1,581 archived tests pass with one expected
  skip, the wheel is 259,949 bytes, all optional profiles pass, and the
  installed interval plus combined-video smokes clean up without a provider
  call.
  #314 then stabilizes the missing output-affecting prompt fact before request
  identity. `audio.long.interval.v1` maps original actual/logical bounds to the
  uploaded clip, keeps physical padding as context only, and requests neither
  timestamps nor legacy markers. A shared audio-only validator preserves the
  materializer's existing input rejection. The complete 1,586-test source suite
  passes; no provider, state, dispatch, resume, repair, or public API is added.
  Exact `5047a00` clean-install proof exits 0 with 1,585 archived tests passing,
  one expected skip, all profiles and media smokes green, and no cloud call.
  Its 261,349-byte wheel is only 795 bytes below the maintained ceiling, so the
  next runtime slice must first inspect real distributable reduction rather
  than automatically raising the budget or merging clear responsibilities.
  #315 audits all 247 wheel members and finds no removable runtime module or
  accidental payload. It excludes only `README_ACTIVE_LIBRARY.md` from wheels,
  while retaining it in Git/sdist, because METADATA already contains the root
  README and no resource consumer reads the detailed source document. The root
  README's stale short-only video sentence is corrected. One worktree wheel is
  247,533 bytes with 14,611 bytes of headroom; all 1,587 source tests pass.
  A 169,681-byte worktree sdist retains the detailed README and excludes
  tests/legacy. Exact clean commit `4c9e31b` then passes 1,586 archived tests
  with one expected skip, all installed profiles and media smokes, and no cloud
  call. Its wheel/base measure 247,533/1,249,562 bytes. The first wrapper never
  launched a child because Windows rejected duplicate-case proxy variables;
  the corrected uppercase-only environment passes.
  #316 adds the audio-specific, secret-free request fingerprint needed before
  paid interval results can be persisted. It covers the owned source SHA-256,
  explicit whole/interval mode, provider/model, prompt version, and exact
  interval identity without adding a sidecar, dispatcher, repair parser, or
  public API. The full source suite passes 1,605 tests. Exact clean commit
  `d590835` then passes 1,604 archived tests with one expected skip, all
  installed profiles and media smokes, and no cloud call; its wheel/base measure
  248,791/1,255,390 bytes.
  #317 adds the minimum audio-owned in-memory partial state: an ordered request
  fingerprint plan and its completed serial prefix. Each slot preserves the
  paid Markdown/digest, provider/model, calls, nullable token usage, and honest
  partial warnings. It does not add serialization, persistence, dispatch,
  resume, repair, or public API. All 1,619 source tests pass. Exact clean commit
  `5580da1` then passes 1,618 archived tests with one expected skip, all
  profiles and media smokes without cloud I/O; wheel/base measure
  250,819/1,266,497 bytes.
  #318 gives that state one deterministic, audio-specific UTF-8 JSON schema and
  strict parser. It preserves Unicode, ordering, warnings, and nullable usage,
  and rejects duplicate keys, missing/extra fields, unsupported versions, and
  invalid settled facts. It adds no filesystem I/O, resume routing, provider
  work, repair parser, or public API. All 1,629 source tests pass. Exact commit
  `3724dc3` passes the clean installed gate with 1,628 archived tests and one
  expected skip, a 252,828-byte wheel, all profiles and local media smokes
  green, no cloud I/O, and complete cleanup.
  #319 adds only caller-path audio state file I/O: bounded actual reads and a
  complete sibling write/flush/fsync/close before atomic replacement. It
  preserves old state and primary-error precedence, including process-control
  cleanup, and has one bounded near-260-character Windows regression. It does
  not add filename policy, dispatch, repair, final output, or public API. All
  1,650 source tests pass. Exact commit `a601555` passes the clean installed
  gate with 1,649 archived tests and one expected skip, a 255,474-byte wheel,
  all profiles and local media smokes green, no cloud I/O, and complete cleanup.
  #320 adds only the pure loaded-state/current-plan reuse gate. Exact validated
  state plus an exact current fingerprint tuple returns the same settled
  prefix; any plan length/order/content drift fails as
  `RESUME_STATE_MISMATCH`. It adds no path, I/O, provider, dispatch, repair,
  composition, authentication, or public API. All 1,666 source tests pass;
  exact clean installed commit `da8f0af` passes with 1,665 archived tests and
  one expected skip, a 256,150-byte wheel, all profiles and local media smokes
  green, no cloud I/O, and complete cleanup.
  #321 selects the library-owned long-audio publication layout:
  `output_dir/<normalized audio stem>/result.md` plus one temporary resume
  sidecar in that same-name directory. Both whole-file and optional exact-
  integer-minute interval modes remain in scope. The next slice is only path
  definition and structural preflight. Collision ownership must distinguish a
  new run from the existing directory required by resume; repair, legacy
  formats, provider classes, fallback pools, and dispatch remain separate.
  #322 implements the lifecycle-neutral internal plan for the normalized job
  root, `result.md`, and `.ocrllm-long-audio-resume.json`. It performs no writes,
  rejects a non-directory output parent and overlong Windows paths, and leaves
  existing-root handling to the next explicit new-run/resume ownership gate.
  All 1,675 source tests pass. Exact commit `a9fb1d0` passes the clean installed
  gate with 1,674 archived tests and one expected skip, a 257,558-byte wheel,
  all profiles and local media smokes green, no cloud I/O, and complete cleanup.
  #323 adds the explicit new-run/resume ownership preflight. New work rejects
  any existing root; resume requires the directory and fixed regular sidecar
  and rejects an existing final result. It writes and parses nothing, ignores
  unrelated sibling entries, and keeps overwrite/repair/dispatch separate.
  Fixed filenames now have one source of truth. All 1,692 source tests pass;
  exact commit `782220d` passes the clean installed gate with 1,691 archived
  tests and one expected skip, a 258,617-byte wheel, all profiles and local
  media smokes green, no cloud I/O, and complete cleanup. The shared
  `ResumeStateError` default still incorrectly names image although PDF/audio
  now use the type; its narrow wording fix precedes the next audio slice.
  #324 corrects that one shared default to media-neutral saved recognition
  state wording. Codes, retryability, hierarchy, and explicit caller messages
  do not change. The focused error/resume set passes 81 tests and all 1,693
  source tests pass. Exact commit `0b415f2` passes the clean installed gate with
  1,692 archived tests and one expected skip, a 258,616-byte wheel, every
  profile and local media smoke green, no cloud I/O, and complete cleanup.
  Proxy TCP passed but pre-gate proxied PyPI HTTPS probes timed out; the
  unchanged wheelhouse required no download. The next consumer is the existing
  public whole-file long-MP3 route, not a new orchestration wrapper.
  #325 connects that consumer. `recognize_long_mp3()` keeps its memory-only
  default, while `output_dir` selects a fixed same-name job directory. One
  settled whole-file result is saved before atomic `result.md` publication;
  exact `resume=True` reuses it with zero new provider calls. Request identity
  now includes transport, and state preserves provider-file/client cleanup
  facts. Interval dispatch, repair, overwrite, fallback, generalized
  transactions, and legacy formats remain out of scope. All 1,702 source tests
  pass. Exact commit `e378556` passes the clean installed gate with 1,700
  archived tests and one expected skip, a 260,753-byte wheel, all profiles and
  local media smokes green, no cloud I/O, and complete gate cleanup.
  #326 fixes the existing Google Files route's silent bypass of the active
  provider-start gate. One Files lifecycle now claims one permit before SDK and
  network work; catalog/upload/poll/generate/cleanup are not miscounted as
  separate starts. All 1,703 source tests pass. Interval dispatch and a second
  limiter remain unimplemented. Exact commit `c8a8c72` passes the clean gate
  with 1,702 archived tests and one optional skip, a 260,782-byte wheel, all
  profiles and local smokes green, no cloud I/O, and complete cleanup.
  #327 adds the selected persistent interval mode to that same public facade.
  `interval_minutes` accepts only an exact positive integer and requires
  `output_dir`; requests remain serial and each settled speech/no-speech slot is
  saved before temporary-segment cleanup. Resume may recover the saved minutes
  when the argument is omitted and reuses only the exact ordered prefix. The
  state schema narrowly migrates exact v2 whole-file states to v3 whole mode.
  Repair, parallelism, retry/fallback, provider classes, legacy formats, video
  routing, and worker changes remain absent. All 1,719 source tests pass. #330
  closes the clean installed proof at exact `56e7cc8`: archive 1,718 passed
  with one optional skip, wheel 266,907 bytes, base 1,350,210 bytes, all eight
  profiles and local media smokes green, no cloud I/O, and complete cleanup.
  #331 reached Google Files with one real 601-second two-window input but
  returned `PROVIDER_RESPONSE_INVALID`, published no result, and did not close
  the live gate. #332 keeps exact safe provider-attempt and persisted-window
  counts on interval failure so the next bounded run can distinguish upload,
  generation, and reusable-prefix outcomes without exposing content or paths.
  Exact commit `8b37e81` passes the clean installed gate with 1,722 archived
  tests and one optional skip, a 266,940-byte wheel, 1,350,517-byte base target,
  all profiles and local media smokes green, no cloud I/O, and complete cleanup.
  #333's later retained live state proves slot 0 complete after one Google call
  (usage 12,688/65,494) while slot 1 and final publication remain open. #334
  adds only safe maintenance-runner access to the existing public interval
  resume; all 1,724 source tests pass. The live resume preserved slot 0 but
  failed before a new generation with zero current calls. #335 adds only a safe
  fixed native-operation discriminator for mapped SDK failures; all 1,725
  source tests pass. Retry/fallback remained unchanged and live success was open.
  Exact commit `d2819c0` passes the clean installed gate with 1,724 archived
  tests and one optional skip, wheel 266,993 bytes, base 1,351,006 bytes, all
  profiles/smokes green, and cleanup complete. A retained-state live resume
  then proved the zero-call failure occurs in Files `upload`; slot 0 remains
  reusable and the live success gate remained open at that point.
  #336 adds one twice-validated ASCII SDK class name only for otherwise unknown
  native Google errors. It records no provider text and changes no retry policy;
  all 1,725 source tests pass. A bounded live resume must identify the actual
  upload exception family before retry/fallback policy is selected.
  Exact `8a738fa` passes the clean installed gate with 1,724 archived tests and
  one optional skip, wheel 267,086 bytes, base 1,351,735 bytes, all profiles and
  smokes green. Live evidence identifies the upload error as `ReadTimeout` with
  zero new generation calls. #337 maps the fixed HTTP-client timeout MRO family
  to existing retryable `PROVIDER_TIMEOUT`; all 1,726 source tests pass and no
  automatic retry/fallback is added.
  Exact `90fd0e4` passes the clean installed gate with 1,725 archived tests and
  one optional skip, wheel 267,184 bytes, base 1,352,572 bytes, all profiles and
  smokes green. One bounded caller-owned live resume then reused slot 0 and made
  exactly one missing call (total/current 2/1), published the result, removed
  state, and proved remote/client cleanup. The Google interval live gate is
  closed; automatic retry/fallback remains a later decision.
  #339 closes the bounded DashScope catalog/connectivity/lifecycle exit with
  one non-flagship formula-board request. #340 preserves compatible-endpoint
  prompt/completion usage through the existing per-model accumulator and passes
  the exact `ec1839c` clean installed gate. #341 adds one narrow video consumer
  for the proven long-audio settlement primitives: whole remains default and an
  exact-positive-integer `audio_interval_minutes` selects serial intervals.
  Video owns the temporary state path, retains paid prefixes on failure, removes
  state only after a clean audio snapshot exit, and never creates the standalone
  `audio/result.md`. Public video resume and repair parsing remain unavailable.
  Exact `67c52c2` passes the clean installed gate: 1,754 archived tests pass
  with one optional RapidOCR skip, wheel 268,897 bytes, base 1,359,287 bytes,
  all profiles and local video/combined publication smokes green, no cloud I/O,
  and complete cleanup.
  #342 narrows the next proof surface rather than changing the library API: the
  maintained Google video runner can pass an exact integer-minute interval,
  require its precomputed audio-call count, keep a caller-owned output directory
  on failure, and reject successful runs that leave the temporary audio sidecar
  or nested standalone publication. Its one bounded live run settled honestly
  as failed: the image branch made one unsuccessful call and the first audio
  interval timed out during Files upload before generation, with zero settled
  intervals and a closed client. This proves the failure boundary, not the
  interval success path, and does not claim public video resume.
  #343 then settled one real interval but exposed a runner-only evidence defect:
  the required failure sidecar was rejected before branch summaries were
  emitted. The corrected runner requires state removal only for complete
  interval outcomes and preserves paid state on partial/failed outcomes; the
  obscured provider failure was not replayed or reconstructed.
  #344 live-proves the corrected runner emits an auditable `video_outcome` for
  real model-scoped 429 failures in both branches, including exact calls and
  audio cleanup. No interval settled, so retained-sidecar live proof and the
  complete interval success gate remain open.
  #345 defers an audio-only video resume after proving it would replay paid
  image groups and lacks short-audio/source/finalization state. The maintainer
  selected the high-level fixed-result resumable job in #347; the current
  three-step API stays non-resumable and does not gain finalize/discard.
  #347 also separates the audio duration gates already implied by A2b: whole
  Google Files requests retain the 9.5-hour ceiling, while exact-integer-minute
  interval mode accepts a source through the private 10-hour product ceiling.
  Mode and interval identity remain temporary resume data and repair remains an
  independent failed-range text side path.
  #349 release-proves that route-aware boundary and the subsequent full-frame
  removal from exact clean commit `3c09cde`: 1,768 archive tests passed with one
  skip, all maintained isolated install profiles succeeded, and local
  audio/image/PDF/video/combined-media smokes passed. Pillow 12.3.0 was supplied
  as the declared compatible wheel through the active proxy; no dependency bound,
  persistent installer configuration, or provider behavior changed.
  #350 makes the existing video sidecar lifecycle match that contract: complete
  clean long-audio results remove state, while partial provider-cleanup results
  return unchanged and retain settled state. It adds no video resume consumer,
  state format, retry, or provider behavior.
  #351's one post-fix Google run reached the 37-model catalog, then one image
  generation and the first audio Files upload each timed out. The redacted
  outcome preserved exact call/settlement/cleanup facts and no residue, but no
  interval completed; the live success gate remains open without retry or model
  switching at that revision.
  #353 made the maintained runner preserve total monotonic elapsed time. #354
  then closes the complete interval gate on exact clean commit `2e3ead0`: one
  five-frame `gemini-2.5-flash` image request and exactly two three-minute Google
  Files audio requests for a 301.0235-second artifact all completed, followed by
  a complete six-asset composition with 13,602 input / 872 output tokens. Remote
  and client cleanup, absence of a remaining sidecar, task cleanup, proxy
  health, and repository cleanliness were verified. Total runner time was
  790.609 seconds;
  no per-stage duration, product-default timeout change, retry, fallback, or
  model switch is claimed.
  #355 rejects publication-only recovery as the selected high-level video job:
  it would add a journal while preserving none of the paid image/audio work the
  resume feature exists to protect. The first public job must immediately own
  and consume fixed `result.md` plus one source/media-plan-bound journal for
  settled frame groups and short/whole/interval audio work. The current
  three-step API remains non-resumable. Runtime implementation waits on the
  maintainer's terminal-failure choice; the recommended rule retains settled
  paid work, publishes no final file while any required unit is missing, raises
  the typed error, and lets explicit resume retry only the missing work.

## Obsolete Prose Kept For Trace

#348 removes the legacy board-corner/cropping branch rather than porting it.
Legacy board images and video candidates now preserve the complete field of
view, matching the already-full-frame active library video and PDF paths. The
crop/perspective module, board ROI detector/config, ROI occlusion rejection,
GUI toggle, and CLI option are gone. Only a read-only historical manifest field
is accepted for repair identity; it cannot select the deleted behavior.

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
