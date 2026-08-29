# Maintainer Product Decisions

This file records durable maintainer decisions that must survive context
compression and agent handoff. It is not a capability claim: code and tests
still decide what is implemented. When an older plan conflicts with a decision
below, agents must surface the conflict and update the active authority before
implementing the older plan.

The current ordered execution queue is `#065 Unified Execution Queue` in
`ACTIVE_STATE_AND_RULES.md`. This file constrains that queue but does not copy
or independently reorder it.

## Planning and documentation

- Detailed planning documents are desirable. Their size is not itself
  over-design: recording alternatives, evidence, rejected paths, and later
  reversals helps future maintainers understand why the code exists.
- Every plan must say whether it is active, adopted, frozen, superseded, or
  historical. A detailed old plan must not silently become the current product
  contract.
- Work-diary entries should distinguish offline regression evidence, clean-wheel
  evidence, live-provider evidence, and capabilities that remain unproven in a
  real request.
- Keep each implementation iteration atomic: one concrete question, defect, or
  proof boundary with explicit success criteria. Do not bundle adjacent future
  architecture merely because it was discovered during the iteration.
- Delegate fixed downloading, installation, and repeated active-check workflows
  to a lightweight subagent. While that workflow runs, the primary agent should
  advance an independent read-only audit, focused regression, or documentation
  task instead of polling or repeating the same procedure.
- Prefer already-authorized media under the maintainer's local `D:\archieve`
  tree for bounded image, audio, PDF, and video execution. Do not crawl or
  download replacement media when a suitable local source already exists, and
  never publish its course content or identifying path in tracked records.
- Treat the maintainer's proxy as always enabled and as the normal
  external-download path. A reported network failure should first trigger a
  check that the proxy was not accidentally disabled or dropped from the child
  environment. Verify that the current endpoint is reachable and explicitly
  propagate proxy variables to the delegated child when its tool does not
  inherit Windows settings. On
  2026-08-26 WinINET and a real PyPI HTTPS probe verified `127.0.0.1:10080`;
  the older `127.0.0.1:7890` endpoint was stale. Recheck rather than hardcoding
  this machine fact into product runtime.
- When a Windows parent will invoke PowerShell `Start-Process`, pass only one
  casing of each proxy name. An environment block containing both `all_proxy`
  and `ALL_PROXY` is accepted by some process paths but `Start-Process` rejects
  it as a duplicate case-insensitive dictionary key before child launch. The
  maintained gate is proven with uppercase `HTTP_PROXY`, `HTTPS_PROXY`, and
  `ALL_PROXY`; do not add product-side environment normalization for this
  operator boundary.
- For bounded DashScope quality trials, prefer live-discovered capable smaller
  models around the maintainer's intended 27B class, including an OCR-tuned or
  general reasoning candidate when currently served. Evaluate formulas, LaTeX,
  Mermaid, future SVG/code, and reasoning—the gaps not already served by
  RapidOCR. Do not hardcode example model names, spend calls on candidates
  clearly worse than RapidOCR for ordinary OCR, or select the current largest
  flagship merely because it is newest.
- After live catalog discovery, `qwen3.5-ocr`-class OCR models and roughly 27B
  general reasoning models such as a currently served Qwen 3.8 candidate are
  maintainer-interest examples, not a permanent allowlist. Prefer the smallest
  currently served candidate that can test formula, LaTeX, Mermaid, SVG/code,
  and reasoning quality; do not turn model evaluation into indefinite
  per-model repair.
- The credential stored by the legacy UI is authorized for one explicitly
  scoped atomic DashScope trial at a time. Discover models before selection and
  cap calls in the task announcement. Reuse permission is not an unlimited
  paid-call budget and does not authorize automatic fallback or a model sweep.
- When a maintained release command has concrete evidence of hanging, give that
  exact stage a visible start message and a hard failure bound. Do not turn one
  stalled dependency preparation into a downloader, cache manager, retry
  policy, or blanket timeout for stages that have not shown the same defect.

## Repository, publication, and UI boundary

- The old `main` belongs to another GitHub account owned by the maintainer. That
  account is temporarily inaccessible because the maintainer cannot currently
  use the required email access. The Jasmine fork and its `master` branch are
  the temporary development path.
- Do not change the old account's default branch, rewrite its role, or describe
  this temporary account-access situation as a product architecture problem.
- The project is not public at present. Do not infer publication, release, or
  compatibility commitments that the maintainer has not made.
- The library does not currently include PyQt6 or another UI layer. UI remains
  in `legacy_app/`; do not add library UI scaffolding in anticipation of a
  future migration.

## Removing configuration and dormant work

"Unused" must not mean only "no current code reference." A configuration field
may belong to frozen work, a paused feature, an older compatibility promise, or
a parallel development line.

Before removing a field or public option, verify and record all of the following:

1. current runtime code does not use it;
2. active or frozen plans do not reserve it for an approved capability;
3. legacy behavior does not require it at the relevant migration boundary;
4. no released external contract depends on it;
5. no parallel branch or handoff is implementing it; and
6. the diary states why removal is preferable to freezing, hiding, or deferring
   the field.

Settings that actively control behavior, such as real concurrency limits, batch
size, or provider request intervals, are not unused merely because their default
is often accepted.

## Batch input and output collisions

- #071 completed the `recognize_batch()` container decision: the top-level
  runtime container must be an exact `tuple`, so top-level lists, generators,
  custom `Sequence` objects, and tuple subclasses are rejected before dispatch.
  This does not narrow the existing per-item contract: an item may remain an
  atomic path or a supported grouped `Sequence`, including an inner list or
  custom sequence.
- Validate the complete batch before provider dispatch. Reject invalid container
  shape, invalid members, and duplicate resolved output targets before spending
  provider calls.
- Preserve already completed paid outcomes when an execution-time item failure
  happens. Do not convert `KeyboardInterrupt`, `SystemExit`, or an unexpected
  programming error into a fabricated item-level source error.
- #248 applies the same principle to native short audio after a successful
  response: a later SDK client-close failure makes the result partial with an
  explicit warning instead of discarding its transcript and token evidence.
  An earlier provider error stays primary and receives only a cleanup flag.
  Apply the analogous proven image fix atomically; do not introduce a generic
  provider lifecycle abstraction merely because both adapters share the bug.
- Normal product layout follows the legacy convention of creating a same-named
  folder beside the source. Cross-media name collisions are therefore unusual.
  Prefer simple duplicate rejection and normal active-call protection over a
  speculative cross-process transaction or locking system.
- **#535 bounds that rule to real targets.** Batch MP3 is memory-only and
  persistent long audio is a separate facade, so no cross-media batch target
  currently exists. If persistent audio intentionally joins batch later, add
  its actual resolved targets to preflight then; do not add a planner now.
- #071 removed the obsolete lazy-iterator machinery while retaining the
  batch-lifetime output owner for valid concurrent execution and race protection;
  do not replace it with speculative cross-process coordination.

## Provider usage accounting

- Keep accounting understandable. Accumulate provider-reported input and output
  tokens by the exact `(vendor, model)` that produced them, together with that
  provider-model's exact dispatched call count.
- Never estimate missing token usage and never turn an unavailable usage value
  into zero. Google and other providers may omit usage on errors, empty replies,
  or interrupted requests.
- Candidate, draft, and review records may remain diagnostic facts, but must not
  grow into a second billing engine. Do not keep adding complex reconstruction
  logic to every rare error exit.
- Distinguish current-invocation usage from historical usage restored from a
  checkpoint.
- Do not create a public per-attempt ledger, price engine, or global mutable
  token manager before a real consumer requires one. Aggregate once at the
  adapter/result boundary and persist only the bounded aggregate needed for
  honest resume reporting.

## File lifecycle and bounded I/O

- Do not roll back the existing file lifecycle protections. They close real
  read, write, close, cleanup, checkpoint, and publication failure paths.
- Some of that protection may be over-defensive or unproven by live use. Do not
  continue enumerating hypothetical filesystem exceptions merely because a new
  branch can be imagined; prefer failures observed in legacy, tests, or live
  product runs.
- Iterations #060-#064 reached the acceptable upper bound for proactive snapshot
  adversary and call-accounting edge work. Keep those fixes, but stop actively
  scanning for more variants unless a real failure or current feature exposes
  one.
- Large-file paths still require bounded streaming plus explicit read, write,
  close, and cleanup handling. Never replace them with whole-file memory loads.

## Live provider evidence

- A fully passing offline suite is a regression floor, not proof that the
  package works as a product. Real provider behavior, response shapes, current
  model availability, network failures, and resume behavior cannot all be
  inferred from code.
- Google image and audio APIs are authorized for bounded live robustness tests.
  Discover the current model catalog live; do not replace discovery with a
  hardcoded support list.
- Routine live verification should use at least one authorized image for an
  implemented image path and one authorized short audio sample for an
  implemented audio path. Provider, batch, checkpoint, or resume changes should
  exercise a small real batch or an interruption/resume flow rather than only a
  success request.
- Treat temporary overload, quota windows, API errors, empty replies,
  unsupported formats, and excessive image counts as useful robustness
  evidence. The library must return honest bounded errors and never a false
  success.
- Do not run long-lived stress tests by default. Use synthetic, committed, or
  explicitly authorized data and never publish credentials or private inputs.
- After a basic media/provider flow is live-proven, later iterations may add
  bounded stress and robustness tests. Each run must answer one stated product
  question, cap input scale and provider calls, verify honest failure and owned
  resource cleanup, and stop at its declared gate. This authorizes deliberate
  scale-up evidence, not indefinite API hammering or a generic provider
  benchmark suite.
- A live resume exercise should prove that completed checkpoint slots are not
  paid for again and only missing work is dispatched after `resume=True`.
- Before live provider work, audit the roughly two months of legacy Google,
  DashScope, and Codex-mode fixes for error handling, retry/switch behavior,
  cancellation, and repair. This should reduce repeated trial and error.
- Apply the legacy-parent rule during that audit: migrate only behavior whose
  analogous path exists in the new library and is still supported by the
  current API. Do not copy legacy patches or architecture wholesale.
- Exercise Google audio live as early as the smallest executable slice permits.
  Getting a real request to run is more valuable than continuing to polish
  isolated offline edge cases before provider behavior is known.

## Audio scale and routing

- The product-wide maximum audio duration is 10 hours.
- Duration is the primary routing signal, but it never overrides a provider's
  own duration ceiling or its file-size, transport-envelope, and token limits.
- Preflight all applicable limits before dispatch. A duration-valid file is not
  automatically valid for a particular provider request.
- **#094 selects settlement-first for direct memory-only short audio.** An
  already-set cancellation signal stops before snapshotting or dispatch. Once
  the one synchronous provider call has begun, it is not interruptible; if the
  signal becomes set during that call and a valid response returns, preserve
  and return the paid transcript, token usage, and cleanup facts. Do not add a
  post-return cancellation check that discards the only result. Persistent long
  audio and high-level video may instead raise cancellation after saving settled
  work because they have an explicit zero-call recovery path; that does not
  authorize state or a result-bearing cancellation wrapper for this direct API.
- #208 found a concrete gap in that target: the shipped A2a path currently
  preflights Google's provider-wide 9.5-hour duration and 2 GB file limits, but
  not the selected model's input-token limit. [Google's audio documentation](https://ai.google.dev/gemini-api/docs/audio)
  states 32 audio tokens per second, so 9.5 hours is 1,094,400 audio tokens
  before the prompt; the [`gemini-2.5-flash` model page](https://ai.google.dev/gemini-api/docs/models/gemini-2.5-flash)
  currently documents a 1,048,576-token input limit. Treat
  the current A2a ceiling as a transport envelope, not a guarantee for every
  served model. SDK catalog rows expose optional `input_token_limit`, but do not
  invent a prompt reserve, a hardcoded model table, or another provider request
  until the narrow preflight contract is specified.
- #209 implements only the certain subset: reuse the single catalog response,
  and reject before Files upload when `ceil(decoded_seconds * 32)` alone meets
  or exceeds the selected row's advertised positive input limit. Missing
  optional metadata preserves the existing request; malformed present metadata
  is rejected as an invalid provider response. This is not a promise that a
  smaller audio-plus-prompt request fits. No extra lookup, token-count request,
  fixed reserve, model table, or automatic chunking was added.
- #150 made the first long-audio order concrete, and #151 completed its live
  gate. A2a is one standalone native Google Files lifecycle for an MP3 longer than 300
  seconds: upload once, wait within a bound, generate once, and manually delete
  the remote file during cleanup. [Google's Files API documentation](https://ai.google.dev/gemini-api/docs/files)
  says uploaded files otherwise remain for up to 48 hours. The legacy Google
  implementation proves the
  upload/wait/generate shape but does not delete the remote file, so copy its
  behavior only as evidence, not wholesale. The shipped single-request ceiling
  is Google's current 9.5 hours, below the private ten-hour product ceiling;
  A2b must cover the remainder through a separately proven chunk route.
- Do not add chunking, resume, parallel splitting, model switching, provider
  fallback, or video integration to A2a. A2b may add the smallest proven
  chunk/resume route toward the private ten-hour ceiling after A2a succeeds.
  DashScope FileTrans remains a separate future provider path because current
  live authorization is Google, not a reason to prebuild a shared long-audio
  abstraction.
- **Selected #152 A2b direction.** Use Route B for the future recoverable path,
  while preserving an explicit whole-file operation. The caller may explicitly
  select whole-file or interval-chunked recognition. Interval length is a
  configurable exact integer number of minutes; do not accept fractional,
  adaptive, or provider-selected intervals. Persist mode and interval identity
  only while work can resume, then allow that temporary state to be discarded
  after the final result is published. The caller's original MP3 must remain
  present and strongly unchanged during resume instead of storing a second
  long-lived full copy. The interval route uses a private fixed 30 seconds of
  context on each side of an interior logical interval. This is not a public
  parameter. Do not add programmatic transcript similarity/deduplication in the
  first slice.
- **#304 accepts #302 overlap option A.** The legacy
  name `audio_overlap_seconds=30` means 30 seconds of context on *each* side of
  an interior logical interval. Adjacent physical inputs therefore share 60
  seconds, not 30. The model prompt tells each request to return only its logical
  interval and final assembly concatenates results; there is no deterministic
  text deduplication. Average extra submitted duration is consequently about
  100% for one-minute intervals, 20% for five-minute intervals, and 3.3% for
  30-minute intervals. Focused legacy window/checkpoint/repair tests prove this
  shape but provide no live quality comparison. The smallest evidence-backed
  selected contract preserves the parent exactly: fixed 30 seconds per side as
  a private constant, no public overlap parameter, exact actual/logical windows
  in temporary resumable identity, and no text-similarity layer. The maintainer
  explicitly accepts that a one-minute interval can approximately double the
  submitted audio. Do not invent a third duration without real comparative
  evidence.
- **#152 repair boundary.** Repair is a small side path, not the production
  recovery mechanism. It may parse failed-slice text for concrete time ranges
  and resubmit those ranges without depending on retained mode/interval state.
  It does not accept legacy formats, perform broad fuzzy recovery, or justify a
  second checkpoint architecture.
- **#564 keeps #152 deferred until it has a real library-owned input.** Active
  long-audio failures preserve temporary resume state but do not publish a
  failure-text result containing concrete time ranges; `result.md` is published
  only after every request settles. Legacy repair cannot fill this gap because
  it finds localized segment-index markers and then requires a separate
  splitter/identity manifest to recover the saved windows. Do not export or
  parse active resume state for repair, port the legacy manifest, or invent a
  failure document merely to create a repair consumer. Implement the narrow
  range-parser/resubmission side path only after another active capability owns
  and publishes exact source-bound failed-time-range text.
- **#312 A2b media backend boundary.** The first interval materializer uses the
  same FFmpeg re-encode shape proven by legacy Google audio: exact physical
  window, mono 16 kHz, 64 kbps MP3. `ocrllm[audio]` includes the already pinned
  lazy `imageio-ffmpeg` distribution as well as `miniaudio`; do not create a
  second `audio-interval` extra or require an independently configured system
  executable. This is an audio capability and does not change base import.
  Materialized segments live only beside an already request-owned source and
  are context-managed. Do not port legacy persistent stem-derived directories,
  parallel splitting, direct final-path writes, provider/model queues, or repair
  state as part of this backend seam.
- **#313 strong source identity groundwork.** Compute SHA-256 during the one
  existing request-owned MP3 copy and retain it in internal snapshot facts.
  Do not scan a potentially 2 GB source a second time, hash a transient interval
  instead of the original owned bytes, or expose the digest in ordinary result
  metadata. A future audio sidecar must pair this digest and byte size with the
  original file URI and request/window identity; this field alone is not resume.
- **#314 interval prompt boundary.** Before hashing a resumable request, bind
  each uploaded context-padded clip to both its actual original-source range and
  logical return range. The prompt names the clip-zero anchor, treats padding as
  context only, requests no timestamps/markers, and retains the existing
  no-speech sentinel for the requested range. Do not port the legacy localized
  HTML marker format or claim the prompt itself validates model output times.
- **#315 wheel-document boundary.** Keep `README_ACTIVE_LIBRARY.md` as detailed
  repository/source documentation and in the sdist, but do not install it as a
  nonstandard wheel resource. Standard wheel METADATA already carries the root
  README and no runtime consumer reads the detailed file. Enforce both this and
  the existing AGENTS exclusion in the wheel checker; do not delete active code,
  merge clear files, minify text, or raise the size ceiling to avoid this audit.
- **#245 video-integration ordering clarification.** Long Files results already
  fit `VideoRecognitionOutcome`; do not add a second outcome or audio-result
  type. The low-level public functions can be manually composed, but they copy
  the MP4 twice and expose branch settlement to the caller, so this is not the
  mature combined route. Do not route by trying short recognition and catching
  `SOURCE_TOO_LARGE`, or by doing a separate full probe before a facade that
  probes again. Resolve #127 first, then add one retained-MP3 ownership seam
  that decodes once and selects exactly one adapter. The existing one-shot
  300-second-to-model-limit range does not require #152; full 10-hour coverage
  and persisted lecture recovery do.
- **#297 executes the bounded #245 seam.** `recognize_video()` now creates one
  request-owned snapshot of its retained MP3, fully decodes it once, and selects
  exactly one existing Google adapter: inline through 300 seconds, Files above
  300 seconds through the current 9.5-hour single-request ceiling. It does not
  catch short-route failure to choose, change `recognize()`, add an audio result
  type, or implement A2b chunks/resume/repair. The #152 overlap decision still
  owns the 9.5-to-10-hour range and persisted recovery.

## PDF verification scale

- PDF recognition is fundamentally an ordered image-recognition workflow. Reuse
  the image provider and recovery path instead of creating an unrelated PDF LLM
  protocol.
- Each provider request should contain roughly 7-8 pages/images.
- During the first working vertical slice, the total batch count is determined
  by that iteration's objective and the real provider results rather than a
  fixed regression count.
- After the path works, the default programmatic live regression uses 2 batches,
  normally 14-16 pages in total.
- A 600-700 page PDF is acceptable for an explicitly planned stress or endurance
  test, but is not required for every ordinary iteration.
- The first public slice has no arbitrary 500-page ceiling and no page-selection,
  password, text-mode, or partial-result setting. It bounds source bytes, render
  pixels, and live image-group lifetime instead. Add a total-page ceiling only
  after real evidence requires one.
- One provider response covers one 7-8-page group, so the stable Markdown unit is
  an honest one-based page-range marker. Do not fabricate eight per-page bodies
  or introduce a PDF-specific prompt merely to claim finer attribution.
- Google is the available free live API authority for this path. Lack of paid
  OpenAI or desktop access is not a reason to replace live PDF/image evidence
  with offline tests alone.

## Provider direction

- Do not remain indefinitely in "scope first" investigations. Once feasibility
  and boundaries are known, deliver a usable vertical slice and exercise it with
  real requests.
- Follow the actual legacy built-in Google transport: native `google-genai` for
  image and audio. The #066 repository audit found the Google compatibility URL
  only in the generic independent-vision configuration and found no
  Google-specific compatibility live-success or error-history record. #067
  live-verified the native image path, and #069 live-verified one bounded native
  inline short-audio result. Neither proves a compatibility transport or worker
  integration.
- For short bounded A1 audio, parity with the legacy built-in means the same
  native SDK transport, not mechanically copying its all-audio Files upload
  lifecycle. The active direct path deliberately uses one bounded inline MP3
  request. Files upload, polling, remote cleanup, long-audio routing, and
  chunking remain deferred until a real product need justifies that lifecycle.
- Treat a Google OpenAI-compatible transport as a possible later, separate path,
  not as evidence for native behavior. Add it only for a proven need and after
  maintainer confirmation.
- Also preserve an intentional OpenAI-compatible provider direction because
  later local models may expose that protocol. Implement local compatibility as
  a separate future path; a shared wire shape does not prove equivalent models,
  limits, errors, or switching behavior.
- Existing provider paths are not removed merely because Google is prioritized.
  Keep provider-specific request and error behavior explicit; do not force
  different protocols through a misleading common implementation.
- A DashScope credential stored by the legacy UI may be used by a bounded
  credential-isolating controller; the active library must not read QSettings
  or depend on the UI. Discover the live catalog before selection. Prefer
  explicitly selected smaller models intended to test the current quality gap
  in formulas, LaTeX, Mermaid, future SVG code, and reasoning. The maintainer is
  interested in roughly 27B Qwen OCR or general models when actually served,
  but those example names are not a hardcoded support list. Do not spend tests
  on models clearly worse than RapidOCR for ordinary OCR, and do not select
  latest oversized flagship models for DashScope robustness runs.
- The difficult provider work is mechanical live verification of the real model
  catalog, error codes, retry/switch behavior, and terminal outcomes. Do not
  install a generic policy such as "retry six times". Retry decisions must be
  supported by evidence for the specific provider and error scope.
- The combined Google video live runner must declare whether inline or Files
  audio is expected. A Files gate is valid only when its safe evidence confirms
  duration above 300 seconds, Files transport, remote-file deletion, and client
  closure; generic one-call success is insufficient. A delegated launch whose
  outer tool loses exit/stdout/stderr is indeterminate, even when its local
  process and temporary directory disappear. Prove terminal capture on a local
  yielded process before another provider launch rather than blindly replaying.
- A provider success gate must contain content the provider can actually
  recognize. Constant-color frames plus a sine tone can validate local media
  extraction and honest provider rejection, but cannot prove image OCR or audio
  transcription. Use a bounded synthetic video with visible test text and
  intelligible synthetic speech; do not add a semantic-content detector to the
  library or retry a deliberately content-free fixture until it happens to pass.
- Live runner errors may expose only existing allowlisted failure scopes and
  exact boolean remote/client cleanup fields. These are needed to distinguish a
  pre-generation Files failure without retaining provider text, remote IDs,
  source paths, or credentials. Do not infer a provider mapping change when an
  earlier runner omitted those safe details.
- Standard numeric HTTP status and canonical Google RPC status names are also
  acceptable live-run evidence when already present on a typed error. Restrict
  the latter to a finite protocol-status allowlist; never forward arbitrary SDK
  status strings, exception messages, or response bodies. A provider-scoped
  rate limit with successful Files/client cleanup is a valid transient outcome,
  not authority for an adapter-internal retry or immediate model switch.
- **Deferred provider-extension target.** After the core OCRLLM product paths
  are stable, provider integration should become additive: adding a provider
  should primarily mean adding one independently readable provider class (and
  its focused tests), not modifying conditionals throughout media processors or
  the common orchestration path. Each provider class should own its evidenced
  defaults and mappings for request parallelism, reasoning/effort controls,
  model selection within that provider, and provider-specific error handling.
  A future multi-provider pool or fallback policy may coordinate those classes,
  but must preserve the existing typed error scopes and must not pretend that
  shared wire compatibility makes provider behavior interchangeable.
- This is a future architectural constraint, not current implementation
  authority. Do not refactor the already-working Google and DashScope slices
  into a generalized plugin framework before OCRLLM's own image, PDF, audio,
  video, resume, and repair paths are stable. For now, keep provider-specific
  behavior inside the existing provider directories and avoid leaking new
  Google- or DashScope-only branches into shared processors.
  **OBSOLETE (2026-08-28):** the deferral caveat in this bullet is lifted. The
  provider-extension target is now activated in a concrete form: the
  `ProviderEntity` plus adapter-registry design in
  [`plan_provider_entity_batch_refactor.md`](plan_provider_entity_batch_refactor.md)
  (#568 in `ACTIVE_STATE_AND_RULES.md`). That design satisfies this target's
  constraints: one independently readable adapter per provider family,
  provider-owned defaults and error mappings, preserved typed error scopes,
  and no pretense that shared wire compatibility makes providers
  interchangeable. The "retry decisions must be evidence-backed, not a generic
  count" rule is preserved: entity retry policies are per canonical error code
  with bounded attempts, not a blanket retry count.
  **SUPERSEDED (2026-08-29, #569/#571):** the consumer-free registry,
  `ProviderEntity` scaffold, placeholder adapter, and broad preset plan were
  withdrawn before commit. The current plan uses the single name
  `ProviderModel` and requires one direct real consumer in the same vertical
  slice; no registry or provider framework is currently authorized.
- The maintainer has configured the current test account with the existing
  provider sources and an additional free Volcengine OpenAI-compatible source.
  The latter is authorized for future bounded compatibility and robustness
  tests when an OpenAI-compatible feature is actually scheduled. Its presence
  does not activate that feature now, prove model compatibility, or authorize
  hardcoding and repairing models one by one; model discovery and provider
  behavior remain live evidence.
- This direction does not reactivate social-media downloading or recognition.

## Resume and bounded manual repair

- Resume is the primary recovery path.
- Repair is a small manual fallback when the resume sidecar/state is missing or
  unusable, or when historical Markdown exists without compatible state.
- **2026-08-28 proposed batch state model.** The provider-entity refactor
  ([`plan_provider_entity_batch_refactor.md`](plan_provider_entity_batch_refactor.md))
  proposes for future merged-Markdown batch recognition: one sidecar
  plan per batch run (ordered request fingerprints, index-aligned settled
  slots, provider identity excluded so resume may change providers) plus
  parseable `ocrllm:` slot markers in the Markdown. Resume reads the sidecar
  first; the experimental repair path is the Markdown-marker-only fallback
  when the sidecar is lost, and it assumes each failed marker is exactly one
  ocrllm failure. This does not reopen the #120 legacy-Markdown rejection and
  does not settle the open #422 PDF repair artifact choice.
- For PDF image batches, repair identifies the failed range from already
  produced Markdown, resubmits only that range, and preserves successful
  content. This supports delayed retry after a provider is down for hours or a
  daily quota is exhausted.
- Do not build a generic repair workflow or speculative defensive framework.
  Migrate the smallest legacy-proven markers and behavior, and preserve existing
  successful content atomically while applying the repaired range.
- #102 proved that active fail-fast sidecar loss produces no repairable Markdown
  or honest unattempted-suffix identity. The earlier repair intent therefore
  maps only to historical legacy Markdown that already contains an explicit
  one-based failed-page marker. Confirm whether that historical compatibility
  input is intentionally in new-library scope before implementation; do not
  widen the active producer merely to manufacture repair markers.
- #106 clarified the apparent tension inside this section: the general repair
  bullets above describe the desired behavior *if* historical compatibility is
  approved; they do not themselves answer the later, more specific scope gate.
  #120 supplied that answer: no. The new library does not accept legacy
  application's localized repair Markdown as a public input. P1-d is frozen
  behind ordinary resume and no `repair_pdf` compatibility parser is built.

## Video recognition direction

- **2026-08-28 refactor authority, narrowed 2026-08-29.** The provider-model/
  batch refactor
  ([`plan_provider_entity_batch_refactor.md`](plan_provider_entity_batch_refactor.md),
  #568 in `ACTIVE_STATE_AND_RULES.md`) supersedes the video-journal decisions
  in this section as marked below. The earlier plan for a rewritten
  `recognize_video(...)` orchestrator is itself superseded by #579/#581: the
  replacement has visible image/audio steps and no recognition wrapper. Video-
  derived work reuses image-batch and audio-batch resume; whether their outputs
  also enter one cross-media Markdown is the explicit choice 12 below, and two
  independent recognizers must not silently mutate one target. A confirmed
  combined artifact would need one narrow final writer, not another video
  journal. Whether a named stateless `resume_video` exists remains the explicit
  choice 11 below. The video journal and `recognize_video_to_markdown` are deleted only
  after the refactor's replacement gate.
  Full-frame retention, provider separation, paid-work reuse, and
  retain-recoverable-gaps survive unchanged.

- **Full-image retention is mandatory (#348).** Neither legacy nor the active
  library may detect blackboard corners, infer a board ROI, crop to a contour,
  or apply perspective rectification before recognition. Multiple separated or
  sliding boards and board-plus-projector scenes make that operation lossy and
  unreliable. Video-retained frames, ordinary board images, and PDF-rendered
  pages must preserve the complete source frame/page. Size-only downscaling is
  allowed when it preserves the full field of view. Comparison thumbnails used
  only for bounded frame selection are not recognition crops.
  #357 removed the last unused legacy Canny/contour configuration fields and
  corrected remaining runtime/documentation wording that called full-frame
  resizing a crop. Stable legacy phase keys remain only for checkpoint layout;
  they do not select a geometry-changing operation.
  #367 removed the final stale `imaging` config whitelist entry, unused
  preprocessing-named constant, and diagram reference to the deleted module.
  #372 re-audited both trees after the maintainer explicitly reaffirmed that
  this prohibition also covers frames extracted from video and pages rendered
  from PDF. No executable crop module or hidden geometry-changing call remains.
  #376 repeated that audit against the current tree after the rule was raised
  again. The result is unchanged: the deleted legacy module has not returned,
  and active video/PDF recognition still receives complete frames/pages.

- **Resolved video-resume terminal decision (#345/#347): Route A. OBSOLETE
  (2026-08-28 refactor; see the authority bullet above).** The "keep the
  low-level calls non-resumable" clause and the "one video journal" shape are
  superseded: `recognize_video` becomes the resumable orchestrator and no video
  journal is built. The rejection of audio-only resume and publication-only
  recovery survives. Do not add an audio-only
  `resume=True` to `recognize_video()`: current video state cannot preserve paid
  image groups, short audio, source identity, or a terminal cleanup boundary.
  Keep the current recognize/compose/publish calls low-level and non-resumable.
  Later add one high-level resumable video job owning a fixed `result.md` plus
  one video journal; atomic final publication removes its temporary state.
  Do not add finalize/discard to the current three-step API. Public video resume
  remains deferred until that high-level consumer is implemented, so no durable
  frame-group schema is added in advance.

- **#355 rejects publication-only recovery as that high-level job. OBSOLETE
  (2026-08-28 refactor; see the authority bullet above).** The rejection of
  publication-only recovery survives; the "one video journal" state demand is
  superseded by the batch sidecar-plan plus Markdown-marker model. Saving only
  an already-composed Markdown result would cover a narrow crash-before-write
  window but would replay every paid image/audio unit after an earlier failure.
  It would also create a first journal schema that the real resume path must
  immediately replace. The first public high-level job must own the fixed
  root/result and immediately consume one video journal containing
  source/media-plan identity plus settled image and audio work. Whole and
  integer-minute interval audio both remain in scope; short audio needs one
  settled record rather than a second sidecar. Do not ship audio-only,
  one-frame-group-only, or publication-only behavior under the name video
  resume.

- **Resolved #355 terminal-failure choice (#371): retain recoverable gaps.
  OBSOLETE (2026-08-28 refactor; see the authority bullet above).** The
  retain-recoverable-gaps principle survives in the batch engine (failed batches
  recorded, never silently replayed, terminal absence never retried); the
  journal-retention mechanics are superseded. The
  maintainer already required supplier outages and exhausted daily quota to be
  continued hours later through resume, with repair only as the small side path
  when state is lost. Therefore, if a frame group or audio unit still lacks
  recognized content because of cancellation, provider, extraction, decoding,
  or parsing failure, publish no final `result.md`, retain every settled paid
  unit in the journal, and raise the typed failure. A later explicit
  `resume=True` retries only missing work; that is caller-owned retry, not an
  adapter loop. Do not publish a terminal provider-failed partial and delete its
  state. Exact `VIDEO_NO_AUDIO_STREAM` and exact `NoSpeechDetected` are settled
  terminal absence rather than missing work; they are not retried. A job whose
  units are all recognized or terminal absence may publish, including a
  `partial` result caused only by no-speech or cleanup warnings.

- **Resolved public consumer shape (#373). OBSOLETE (2026-08-28 refactor; see
  the authority bullet above).** `recognize_video_to_markdown` is removed; the
  resumable consumer is the rewritten `recognize_video` with
  `image_providers`/`audio_providers`. Add one synchronous importable
  `recognize_video_to_markdown(source, *, output_dir, image_config,
  audio_config, audio_interval_minutes=None, resume=False) -> RecognitionResult`.
  The facade, not either branch `Config`, owns persistence, the normalized
  source-stem root, fixed `result.md`, and the single video journal. Keep
  `recognize_video()` as the existing non-resumable low-level outcome API. Do
  not add `run_video_recognition_job`, `overwrite`, a third cancellation signal,
  or a publication-only/audio-only compatibility stage.

- **#374 implements the resolved consumer and keeps its audio identity narrow.
  OBSOLETE (2026-08-28 refactor; see the authority bullet above).** The shipped
  facade and journal are deleted in the refactor's final phase; whole-file
  default and exact-integer-minute interval audio survive in `chunk_audio` and
  `recognize_audio_to_markdown`.
  Whole-file audio remains the default; explicit interval mode accepts only a
  positive integer number of minutes. Mode and interval minutes may be kept in
  the temporary journal solely for exact resume and are discarded after final
  publication. The later repair side path derives time ranges from failure text
  and does not depend on this state. Future provider classes may eventually own
  provider-specific concurrency, effort, error handling, and fallback policy,
  but that framework starts only after the core library is stable. Current code
  should keep the provider seam usable without implementing the abstraction.

- **Recommended #355 strict defaults unless separately changed. OBSOLETE
  (2026-08-28 refactor; see the authority bullet above).** Journal-digest
  mechanics are superseded; the strict-identity spirit survives as the batch
  sidecar's byte-identical plan rule. Bind resume
  to the exact normalized source path, byte size, and SHA-256; a moved source is
  rejected even when byte-identical. Process resumable frame groups serially so
  each settled paid group is durably journaled before the next dispatch. If a
  matching `result.md` and journal coexist after a crash, validate the result
  digest and remove only the matching journal; mismatches are rejected. These
  choices prefer explicit rejection and an understandable lifecycle over path
  compatibility, parallel checkpoint callbacks, or generalized transactions.

- Video is the next active library line. Start with local parsing, then migrate
  the main legacy negative-feedback frame comparison and retained-image
  behavior before provider recognition.
- Frames and audio are independent pipelines. Retained frames reuse the image
  recognition provider; extracted audio must be able to use a different audio
  provider. Optional hotwords may flow from frames to audio, but must not make
  either pipeline depend on the other.
- Keep this a Python import package: video dependencies are optional and lazy;
  no GUI/PyQt, social downloader, mandatory executable, or heavy import belongs
  in base `import ocrllm`.
- Do not begin with a provider base class, fallback pool, or compatibility
  framework. Add the provider split when both real video media consumers exist.
- #121 keeps the first retained-frame contract deliberately strict: the caller
  supplies an output parent, the library publishes one same-stem directory, and
  any existing target is rejected. There is no overwrite, resume, manifest,
  ROI, pHash, fine scan, or threading claim in this slice.
- #122 keeps retained-frame recognition as a thin memory-only adapter. It
  accepts only the library's exact ordered `RetainedVideoFrame` tuple, groups
  paths at eight or the caller's lower image limit, and reuses
  `recognize_batch()`. Per-group Markdown persistence is rejected because it is
  not a video result or resume contract. This is not legacy-format support and
  does not authorize a provider hierarchy, fallback pool, or video-specific
  vision protocol. The next slice is audio extraction with a genuinely
  independent audio provider binding.
- #123 makes the provider split concrete without changing `Config`: frame
  recognition and extracted-MP3 recognition are two independent calls with two
  independently supplied configs. Audio extraction uses the lazy `video` extra
  and `imageio-ffmpeg`, writes only a same-directory staging file, fully decodes
  it before atomic publication, and rejects existing targets. Extraction has no
  duration ceiling; the current Google short-audio consumer keeps its separate
  300-second/25-MiB limits. Do not add a combined video result, provider base
  class, fallback pool, hotword coupling, long-audio route, or resume contract
  before their observed consumers require them.
- #124 requires every successful, failed, or undispatched frame-recognition
  group to retain its exact ordered frame indices and timestamps. Composition
  must consume this recorded group identity rather than reconstruct membership
  from today's image limit. This is a narrow correction to the existing
  outcome boundary, not authority for a combined result type, final Markdown,
  cleanup transaction, or resume manifest.
- #125 distinguishes a valid silent video from broken audio with
  `VideoError.code == "VIDEO_NO_AUDIO_STREAM"`. Composition may treat only that
  code as an absent optional branch; `VIDEO_INVALID`, backend failure, timeout,
  and provider errors remain real failures. Keep this as a code on the existing
  error class—do not add a no-audio subclass, ffprobe/PyAV dependency, raw
  FFmpeg-log parser, or successful empty transcript.
- #126 makes provider separation executable through one public
  `recognize_video()` call. The caller supplies separate exact image and audio
  `Config` objects; both are validated before media output or provider dispatch.
  The immutable `VideoRecognitionOutcome` retains frames, any extracted MP3,
  ordered frame outcomes or a typed frame error, and exactly one audio result
  or typed audio error. Its complete/partial/failed status is computed; only
  `VIDEO_NO_AUDIO_STREAM` is normal audio absence. Do not turn this into legacy
  Markdown compatibility, a final document format, cleanup transaction, resume
  manifest, provider hierarchy, retry, fallback, or API pool.
- **Resolved #127 cancellation choice: Route A.** `image_config` and
  `audio_config` retain independent signals. One cancelled branch settles in
  the existing `frame_error`/`audio_error`, preserves the other branch, and
  skips its provider work; pre-cancelled audio also skips MP3 extraction. Both
  signals already set stop before source or output work. Iteration #294
  implements this without a new status, exception carrier, branch hierarchy,
  checkpoint, or extractor cancellation framework.
  #145 executed the exact public matrix without provider calls: image-only
  cancellation returns a partial outcome and lets audio run; audio-only
  cancellation hides one completed image branch by raising; both signals still
  perform media extraction before raising; silent video ignores audio-only
  cancellation and returns complete/absent. Legacy production evidence requires
  settled paid work to survive cancellation but could not choose return-versus-
  raise for this non-persistent API. The later Route A selection supersedes this
  historical ambiguity.
  #226 found no later statement that selects either route. “Preserve settled
  paid work” rules out the current loss but does not itself choose return or
  raise. A can reuse the existing branch errors and outcome; B necessarily adds
  a bounded outcome-recovery carrier. The remaining maintainer question is
  therefore was only whether one cancelled branch returned the settled outcome
  or raised with a recoverable carrier. Route A is now selected and implemented;
  do not reintroduce Route B's carrier without a new maintainer decision.
- **#236 video recovery ordering, investigated but not authorized.** Legacy
  production behavior proves that reusing settled paid image groups and keeping
  frame/audio work independent are worthwhile. Do not port its five-phase
  checkpoint, absolute-path identity, file-exists recovery, localized Markdown
  parsing, or repair markers: they omit source bytes and exact request identity
  and have already caused wrong reuse and ambiguous repair. Once #127 is chosen,
  the first bounded candidate is library-owned recovery of exact retained-frame
  groups only. Full audio/video recovery must also wait for #152's stable
  long-audio unit contract. Published Markdown remains output, never state; this
  note does not authorize a schema, resume facade, or repair compatibility API.
- #129 keeps video composition explicit and memory-only. A caller may turn an
  already returned complete or partial `VideoRecognitionOutcome` into one
  standard video `RecognitionResult`; frame groups and audio remain separate
  sections, failed branches retain stable codes, and fully failed outcomes are
  not converted to results. Do not infer audio/frame alignment, auto-publish
  Markdown, create resume state, or copy legacy board/transcript file formats
  as part of this composition boundary.
- #130 proves the current video-composition facade from a freshly built and
  externally installed wheel. Release proofs should build from an explicit
  clean Git-archive root and determine native-command success from its exit code
  plus the expected artifact; Hatchling may print the wheel path on stderr.
  Assert `pyproject.toml` at the chosen archive root instead of guessing an
  extra nesting level. These are proof-harness rules, not reasons to broaden the
  package manifest or add a general build controller.
- #131 requires safety-cap downsampling to retain both the first and final video
  candidates. Losing the last candidate can lose content written only at the
  end of a lecture; preserve exact cap and order without adding a second scene
  detector or changing the 28--40 frames/hour calibration policy.
- #132 measures the existing 96-unit output-stem budget in Windows UTF-16 units,
  not Python code points. Truncation preserves complete characters and the
  existing 259-unit controlled path boundary. This concrete supplementary-
  character fix does not authorize extended-path support, reserved-name work,
  or a general path framework.
- #133 calculates the number of maximum-length video subsegments with ceiling,
  not nearest-integer rounding. A declared maximum is not a target average: do
  not reduce the segment count to save frames. Existing five-second candidate
  quantization and the separate hourly density cap remain unchanged.
- #134 leaves the post-selector Google video gate open. A partial live result is
  useful evidence, but a failed branch's call count cannot be inferred from the
  absence of success metadata. The next live attempt requires a maintained
  combined-video smoke runner that records only stable error code, safe stage,
  and `provider_calls_attempted`; do not add retry, fallback, or provider routing
  to make the gate pass.
- #135 implements that runner as a maintenance tool rather than a public API.
  The gate fixture is controlled to one image group: only one image call, one
  audio call, and complete composition pass. Missing failure-call evidence stays
  unknown instead of becoming zero. Ordinary multi-group video remains valid
  library input; do not duplicate extraction or generalize provider routing to
  make this narrow smoke accept arbitrary media.
- #137 live evidence confirms why the runner must preserve partial outcomes:
  one Google image call succeeded, while one audio call returned
  `PROVIDER_QUOTA_EXHAUSTED`; composition retained both the successful result
  and extracted MP3. Do not retry or switch models inside the current adapter.
  Future caller-owned provider/model routing may consume this typed evidence,
  but this quota event does not authorize building that future layer now.
- #138 treats `VideoRecognitionOutcome.output_root` as an exact lexical layout
  contract, not decorative metadata. Retained frames must use its `frames`
  child and optional audio must use its `audio.mp3`; construction rejects
  mismatches before composition. Do not infer physical containment or add
  `resolve()`, symlink traversal, hashes, manifests, or filesystem sandboxing.
- #139 applies the combined-video runner's exact-or-null evidence rule to the
  standard provider-free composition result. Sum branch call counts only when
  every settled provider branch supplies a valid nonnegative integer; otherwise
  keep `current_run_provider_call_count` present with value `null`. A silent
  stream or typed video/audio parsing failure before provider dispatch is known
  zero. Do not add billing, telemetry, a call ledger, or provider routing.
- #140 rejects `VIDEO_NO_AUDIO_STREAM` together with any `audio_artifact` at
  `VideoRecognitionOutcome` construction. Absence and a retained MP3 cannot
  both be true; do not let composition silently discard the file or invent a
  fourth audio state.
- #141 defines video completion by child status, not merely by the presence of
  child results. Every frame result and a present audio result must be
  `complete`; a `partial` child remains usable but keeps the outcome and its
  provider-free composition `partial`. Do not add a status coordinator or new
  status value.
- #142 makes video frame-group typing explicit at the outcome boundary. Every
  successful frame group carries an exact `RecognitionResult` whose
  `source_type` is `image`; reject a mismatch instead of composing it under the
  Frames heading. Do not generalize this into a media graph or result hierarchy.
- #143 keeps fully failed video outcomes as structured branch evidence. Caller
  examples must inspect `VideoRecognitionOutcome.status` and call
  `compose_video_result()` only for complete or partial outcomes; do not add a
  serializer or exception wrapper merely to make failed outcomes composable.
- #144 keeps video composition and publication as two explicit responsibilities.
  `publish_video_result()` accepts an already-settled complete or partial
  outcome and an explicit caller-owned path, then reuses the existing composer
  and atomic Markdown writer. It refuses overwrite by default and does not
  allow that path to equal one of the outcome's retained media assets, even in
  overwrite mode. It does not derive legacy names, recognize again, create
  resume state, or settle the open
  #127 cancellation choice. Do not add callable-module or custom package-module
  machinery to hide direct same-named submodule imports; the documented public
  boundary is the lazy top-level facade.
- #148 requires the exact final source frame to participate in the bounded
  comparison scan when it is not already on the five-second grid. Keep the
  unchanged density and negative-feedback policy; do not use endpoint coverage
  as authority for a configurable sampler or second scene detector.
- **Resolved #149 video snapshot placement (#211).** Real execution proves that
  replacing
  the caller-owned MP4 between the current scan and selected-frame decode can
  publish JPEGs from different bytes while returning success; the combined
  facade may then extract still another version's audio. The correction must
  stream one request-owned disk snapshot and make inspection, scan, retained
  decode, and both recognition branches consume it. Choose either (A,
  recommended) a hidden snapshot inside `output_dir`, beside the final
  same-stem output root, with no public API expansion, or (B) a new explicit
  video temporary-directory parameter. Do not use whole-file memory, a
  hash-only after-the-fact check, a generic media cache, or separate frame/audio
  snapshots. The maintainer's library-only clarification selects A: the active
  package owns one hidden, streamed, request-lifetime snapshot beside the final
  same-stem root and exposes no video-temp or legacy-compatibility parameter.

## Resolved confirmation and next authority

- #069 confirmed the implemented native inline boundary with one successful
  `gemini-2.5-flash` public result. The result content was validated internally
  but not published, so this is not a transcription-quality evaluation. Keep
  Files upload, long-audio chunking, a secondary Google compatibility transport,
  and the future local-model OpenAI-compatible path deferred.
- #070 completed the P1-a live cancellation/resume proof without replaying the
  settled draft. #071 completed the formerly temporary P1-b tuple/preflight
  clarification and its two-batch live proof. #072 implemented the P1-c offline
  candidate and proved two serial eight-page groups plus one-group-only resume
  with real local PDFium and injected-provider tests. #078 then closed P1-c:
  one foreground `gemini-2.5-flash` run processed 16 pages as exactly two
  serial requests, published two complete child states plus ordered final
  output, reported current-model usage, and retained no rendered pages. The
  former next item was the P1-d manual-repair product decision in
  [`ACTIVE_STATE_AND_RULES.md`](ACTIVE_STATE_AND_RULES.md#p1-d--minimal-pdf-repair-after-stable-markers).
  #080 proved that one failed-range marker cannot recover an unattempted suffix
  under the current serial fail-fast loop; #102 narrowed the remaining decision
  to historical explicitly marked Markdown compatibility. #120 answered no.
  #338 reconfirms that image/audio provider separation is already shipped
  through two independent video configs. #339 closes the bounded Stage M
  DashScope live exit with one current-catalog `qwen3.5-ocr` call. The current
  order therefore advances to the next P1-e consumer: reuse the proven
  whole/interval long-audio processors in video without nesting the standalone
  audio publication or creating provider generalization. Repair remains a later
  narrow side path.

## Open PDF repair artifact choice (#422)

- The active library still does not implement PDF repair and still rejects
  legacy localized repair Markdown. Current fail-fast PDF recognition publishes
  no partial Markdown, so a repair parser alone would have no library-owned
  input.
- Route A (recommended) introduces a separate source-bound
  `*_board.partial.md`. It contains only strict library schema/source identity
  plus already-settled `ocrllm:pdf-pages` ranges. Repair validates the current
  PDF, computes the missing complement, uses the caller's current `Config`, and
  atomically promotes to the canonical Markdown when complete. It stores no old
  provider/model/prompt/batch parameters and does not consume image sidecars.
- Route B keeps repair unavailable and retains ordinary image-sidecar resume or
  an explicit fresh run as the only recovery choices.
- Do not use the canonical final path for incomplete content, accept legacy
  comments, widen `recognize_batch()`, or implement a parser/producer without a
  matching end-to-end consumer. The detailed bounded plan is
  [`plan_pdf_repair_side_path.md`](plan_pdf_repair_side_path.md).
- This is a material output-contract choice. No runtime implementation begins
  until the maintainer selects Route A or Route B.
- **#451 decision-attribution clarification.** The maintainer's earlier
  "first A, second B" answer selected Route A for video branch cancellation
  and Route B for recoverable long-audio whole/interval behavior. Those
  decisions predate this #422 PDF-specific artifact choice and do not select
  either route here. The remaining question is exactly: should failed active
  PDF recognition publish the separate source-bound partial artifact defined
  by Route A, or should Route B preserve no partial aggregate Markdown and keep
  manual PDF repair unavailable? Do not infer an answer from another feature's
  reused route letters.

## Open long-M4A public entry choice (#567)

- Real archive evidence now establishes one concrete additional audio format:
  83 M4A/AAC files exist, including a complete 368.563-second, 7,480,134-byte
  sample. No WAV files were found, so this choice is M4A-only.
- The existing production interval materializer successfully converted that
  complete source once to a fully decoded 368.555-second MP3 without modifying
  the source or retaining temporary files. This proves a narrow M4A-to-existing-
  interval route is locally feasible; it does not prove provider acceptance.
- One bounded Google Files upload attempt stopped before acceptance with the
  current project-level HTTP 400 `FAILED_PRECONDITION`, the same status recently
  observed during catalog access. It made zero generation calls and cannot be
  interpreted as an unsupported-format result. Do not retry or claim native
  Google M4A support from this run.
- Route A (recommended) adds an honestly named `recognize_long_audio()` entry
  for existing MP3 plus M4A only when explicit integer-minute interval mode is
  selected. Existing `recognize_long_mp3()` remains the stable MP3 entry. M4A
  windows are normalized by the already-proven MP3 materializer; whole-file
  native M4A remains deferred.
- Route B adds a parallel `recognize_long_m4a()` entry with the same interval-
  only restriction. It is more literal for the first implementation but creates
  two long-audio public entry families and duplicated documentation.
- Do not silently make `recognize_long_mp3()` accept M4A, add WAV or every
  legacy extension, port DashScope FileTrans, add a generic converter/provider
  framework, or expose whole-file M4A before this API choice is settled.

## Open provider-model and media-batch choices (#571 reconciliation)

The maintainer has approved the decomposed media direction but explicitly
paused each provider/entity and replacement-recognition slice for its relevant
discussion gate. The choices and their phase dependency map are recorded in section 6 of
[`plan_provider_entity_batch_refactor.md`](plan_provider_entity_batch_refactor.md).
No provider-model class, retry engine, registry, static catalog, batch pool,
merged facade, or video deletion begins until its relevant contract is settled;
later unrelated choices do not form one global barrier.

The latest instruction resolves two former choices. The duplicated video
recognition/journal product is abandoned after its image/audio replacement gate;
it is not retained as a compatibility family and is not deleted during this
discussion pause. A failed batch's final accumulator keeps only that batch's
last provider, canonical code, and bounded description, not one overflow record
per attempted provider. The public type name is the implementation-level
`ProviderModel`, with no duplicate `ProviderEntity` alias. The following
choice details remain open or are fixed as marked:

1. Does a flat provider list stop at the first successful recognition
   (recommended), or continue calling providers after success?
2. When recognition completes after earlier provider failures, does the
   function return the completed result with bounded failure records
   (recommended), or raise while attaching the successful result?
3. Are committed presets limited to a few live-proven models plus explicit
   construction/live discovery (recommended), or does the repository freeze
   every currently served Google/DashScope model?
4. With multiple providers and no explicit image batch size, is one common
   size the minimum positive integer default across all flattened candidates
   (recommended), or the first provider's default? Provider-derived omission
   behavior is fixed, so a required explicit size is no longer an alternative.
5. Does every omitted output use `<source-identity>_ocrllm.md`
   (recommended), or do image, audio, and video receive separate suffixes?
   Directory placement is already fixed.
6. With multiple audio-capable providers and no explicit interval, is one
   common interval the minimum positive integer default across all candidates
   (recommended), or the first provider's default? Explicit positive minutes
   and `-1` whole-file mode always win; requiring an interval whenever several
   providers are supplied is no longer an alternative.
7. Are retry rules reduced to finite `extra_retries` and `wait_seconds`, with
   outcome reporting kept outside the rule and one universal "exhausted means
   record and advance" behavior (recommended), or do `error` / `next` /
   `current` retain distinct control meanings that still need to be specified?
8. **Combined provider-model boundary:** does one immutable value contain only
    vendor/model identity, controlled adapter ID, three capabilities,
    capability-dependent defaults, and finite retry rules, while an explicit
    lazy resolver uses separately supplied exact adapter settings and keeps the
    injected Python protocol separate (recommended)? Or does each model carry
    an arbitrary callable/protocol plus a generic invocation-options mapping?
9. **Fixed token contract:** persist one cumulative aggregate per exact
   `(vendor, model)` with exact calls and nullable input/output totals,
   including trustworthy failed-attempt evidence. Treat the loaded value as the
   historical baseline and keep only this invocation's delta in memory. Do not
   persist separate current/history buckets or a per-attempt ledger.
10. **Merged into choice 8:** field ownership and invocation ownership are one
    decision, not two independently selectable contracts.
11. **Fixed routing, open export detail:** `resume_video` is a thin route to the
    ordinary image/audio resume functions and owns no video journal,
    publication transaction, composition, output naming, or cleanup lifecycle.
    Should it be exported from the package root, or remain a documented caller
    composition helper?
12. Does "one Markdown" mean one output per merged image call and one per
    merged audio call (recommended until clarified), or one additional artifact
    containing both branches? Independent recognizers never mutate the same
    target. If the combined artifact is required, is one narrow media-neutral
    composer that consumes settled branch results and publishes once acceptable?

**#572 evidence for choices 1 and 2.** Both the active library's same-provider
model-candidate loop and the legacy DashScope/Google candidate loops stop at
the first valid result. The active path returns success normally and preserves
the attempt ledger in result metadata. `BatchItemOutcome` cannot hold a result
and an error together, so raising after successful fallback would turn valid
work into a failed item and may trigger replay. The recommended contract is
therefore: first valid result stops the flat lane; return it as complete with
one warning and ordered, bounded `metadata["provider_failures"]`; raise only
when recognition remains incomplete. This is evidence and a recommendation,
not maintainer confirmation; both choices remain open.

**#573 evidence for choice 3.** Active image/audio settings already accept
exact caller-selected model IDs, and active Google/DashScope adapters validate
current catalog membership without a committed full catalog. Google and
DashScope official discovery metadata describe availability and some declared
capabilities, but operation-specific OCR/audio suitability and stable defaults
still require separate documentation and bounded real calls. Legacy's large
static lists, cached catalogs, name classifiers, and fallback IDs demonstrate
the stale-catalog cost. Recommended: ship only a few live-proven
`ProviderModel` presets, accept explicit construction of the same type for all
other IDs, and keep vendor discovery as an untrusted query utility rather than
a preset generator or registry. This is not maintainer confirmation; choice 3
remains open and no concrete preset has been selected.

**#574 evidence for choice 4.** Current active and legacy resume paths treat
ordered batch membership as durable work identity, and legacy PDF checkpoints
include the chosen batch size. Recommended: an explicit positive integer wins
unchanged; otherwise resolve one default before grouping as the minimum
positive `default_image_batch_size` across all flattened candidates, persist
that resolved size and exact groups, and never recalculate or re-batch them
during fallback or resume. Flattening here does not allow cross-lane fallback.
First-provider sizing can create oversized fallback groups; lane-local sizing
needs a variable-window planner and extra state; explicit-only contradicts the
maintainer's provider-derived-default requirement. This is not maintainer
confirmation; choice 4 remains open.

**#575 evidence for choice 5.** Active naming currently differs across ordinary
image/PDF output, long audio, and the old video job; legacy adds several
media-specific Chinese names and a multi-image common-prefix guess. Recommended:
an explicit output path wins, while every omitted output resolves to
`<normalized-source-identity>_ocrllm.md`. Single files, PDFs, and videos use the
source stem; a folder batch uses the folder name. New recognition refuses an
existing target, and preflight rejects duplicate targets before provider calls.
Do not auto-number, scan for a plausible old file, add timestamps/hashes, or
build a persistent collision registry. A rare same-stem image/audio collision
uses an explicit output path. The video composition owner passes one explicit
combined target to both settled branches rather than letting them derive two
files. Media-specific suffixes are the viable alternative, but they add three
default branches mainly to hide that rare collision. This is not maintainer
confirmation; choice 5 remains open.

**#576 evidence for choice 6.** Active long-audio persistence already binds
whole/interval mode, the exact positive interval, ordered window fingerprints,
and settled slots; changing the interval is rejected before materialization or
provider dispatch. Legacy Google's 30-minute windows are one provider default,
not a universal limit. Recommended: validate every candidate's audio capability;
an explicit positive integer wins, while explicit `-1` is normalized at the
call boundary to the single internal whole identity (`mode="whole"`, no stored
minutes). If omitted, one provider supplies its positive suggested minutes and
flat/nested shapes use the minimum across all flattened candidates. Resolve and
persist one exact window plan before recognition; fallback and resume never
re-split it. A rejection remains a provider failure, and changing the interval
starts a new plan. First-provider and lane-local defaults make time boundaries
depend on provider scheduling; explicit-only contradicts provider-derived
splitting. Do not add adaptive shrinking, binary search, hidden whole-to-split
fallback, or per-provider window queues. This is not maintainer confirmation;
choice 6 remains open.

**#577 evidence for choice 7.** Active Google and DashScope adapters map raw
SDK/HTTP evidence to canonical OCRLLM codes before any policy decision. A raw
Google `429` can mean model quota exhaustion or temporary provider rate
limiting, and `503` can mean unavailability or high-demand limiting, so raw
numbers cannot be cross-vendor retry keys. Active adapters make one call and
the existing disposition object reports evidence only; it is not a retry
engine. Legacy Google confirms that useful behavior is finite and classified,
and also exposes a naming trap: its `max_retries` value counts total attempts.
Recommended: rules are keyed by canonical code and contain only non-negative
finite `extra_retries` plus non-negative `wait_seconds`; zero means no call
beyond the initial attempt, and waiting occurs only before an extra same-model
attempt. A missing rule means zero extra retries. Success stops immediately;
exhaustion records the last safe failure and advances immediately, while an
empty remaining lane is a resumable batch failure. Capability, source,
configuration, and preflight failures remain outside the table and cause zero
provider calls. Reporting severity is not a rule field: choices 1 and 2 already
decide whether the final outcome is a completed result with bounded failure
evidence or an incomplete error. Structured provider retry-delay hints remain
deferred until one live adapter path needs them; do not add a generic hint
parser, exponential engine, unbounded retry, or learned policy. The supplied
`error` / `next` / `current` examples all have the same eventual transition,
so preserving their labels would duplicate state rather than express behavior.
This is not maintainer confirmation; choice 7 remains open and no runtime was
implemented.

**#578 evidence for choice 8.** Active code already separates built-in and
injected invocation. Exact Google/DashScope settings select lazily imported
operation modules; those adapters own SDK loading, credential resolution,
request/response translation, canonical error mapping, and client cleanup. The
separate `VisionProvider` protocol accepts an opaque Python object for tests and
advanced injection. Legacy shows the cost of merging those roles: its general,
Google, hybrid, API-pool, and Codex clients combine transport selection,
credentials, clients, media routing, retry, fallback, model memory, and CLI
execution. Recommended: built-in `ProviderModel` values store only a validated
transport-level adapter ID, and a small explicit resolver lazily imports known
operation-specific modules. It is not a mutable registry, plugin system,
arbitrary module loader, executable path, or subclass per model. SDK clients,
uploads, credentials, pools, retry state, and lane state never enter the model
value. Credentials remain call/runtime data; the first vertical slice reuses
its existing exact settings type and does not invent a generic credential
registry before a second transport proves a common need. Keep the existing
injected protocol on its existing API instead of automatically wrapping it in
the replacement batch abstraction. This is not maintainer confirmation;
choice 8 remains open and no runtime was implemented.

**#579 evidence for choice 9.** Active Google and DashScope response boundaries
already accept only trustworthy non-negative integer usage. Google can retain
reported usage on a later content-validation error; some failed calls report no
usage at all. The shared aggregator therefore treats a missing dimension as
unknown instead of zero. Long-audio resume persists per-slot usage and exposes
historical totals separately, while image resume prevents current-run double
counting but does not preserve historical token totals. Current aggregators are
also keyed by model string only, which cannot remain the identity once two
vendors may expose the same model ID. Recommended: one bounded aggregate per
exact `(vendor, model)` with exact call count, nullable input/output totals, and
one cumulative persisted value. Count each adapter response once; persist
observed aggregate usage, including safely reported failed-attempt usage,
without retaining a public attempt ledger. #586 later fixes the loaded value as
the historical baseline and current-run deltas as memory-only reporting; no
runtime was implemented.

**#580 evidence for choice 10.** Active code already gives model names,
provider settings, recognition execution policy, adapter implementation and
per-call state different owners. DashScope region/base URL select the endpoint;
its thinking and high-resolution flags alter a request; Google provider
settings currently contain only an optional credential. Prompts, media,
timeouts, cancellation, client/upload lifecycle, calls, tokens and cleanup are
also invocation facts rather than model identity. These two real adapters do
not prove one useful generic call-parameter shape. Legacy demonstrates the
opposite design's cost: provider, model, endpoint, key, protocol, effort,
batching, concurrency, media routing, candidate queues and mutable client/pool
state are spread across interdependent sections and sometimes copied when a
mode changes. Recommended: one frozen value containing vendor, model,
`adapter_id`, explicit plain/detail-image and audio booleans, nullable positive
defaults only for supported tasks, and immutable canonical retry rules. Keep
exact adapter settings separate and reuse the first adapter's shipped settings
type. Do not give unsupported tasks dummy defaults or add a generic options
bag. #585 later merges this field decision into choice 8; the combined boundary
remains open and no runtime was implemented.

**#581 fixed local-execution boundary.** RapidOCR remains the current explicit
`image_mode="ocr"` strategy during the first provider-model vertical slices. It
already lazy-loads optional dependencies, produces the shared result shape,
reports zero provider/network calls, and has a stable completed-result resume
identity; moving it now would not prove the replacement provider consumer.
Future VLLM, Ollama, or other local execution is not excluded: a concrete path
may later use the same controlled `adapter_id` boundary and the same
`ProviderModel` value type. Do not create `LocalProviderModel`, a local model
catalog, placeholder local adapters/extras, an executable path, or a callable
field first. The first Google/DashScope slices do not change RapidOCR settings,
result/error behavior, call/token semantics, or resume identity. This is a
fixed deferral boundary, not another open product choice and not authority to
implement a local adapter.

**#582 evidence for choice 11.** Current image recognition resumes through
`Config.resume=True` and an output-adjacent image sidecar. Current long-audio
recognition owns a different whole/interval sidecar and publication boundary.
`recognize_batch()` has no collective resume state. The shipped
`recognize_video_to_markdown(..., resume=True)` is not a thin router: it rejects
branch persistence and owns a video journal, one result path, source/branch
validation, composition, publication, and cleanup. The low-level
`recognize_video()` is not resumable. #582 therefore rejected any replacement
router that owns coordination, but its recommendation against the public name
was superseded by the maintainer's direct instruction that a video resume
function routes to the ordinary image/audio resume functions. #584 fixes only
that stateless delegation; package-root export remains open. No runtime/export
was changed.

**#583 evidence for choice 12.** Current image and long-audio recognition own
different sidecars and whole-file publication rules. `recognize_batch()`
produces independent item outcomes and rejects duplicate targets; it is not a
merged-document writer. Current PDF, long audio, and the frozen video path all
compose settled child results before one final atomic publication. There is no
generic incremental Markdown update protocol: PDF has successful page-range
markers, while image slot and audio window identities exist only in their JSON
state. Two recognizers directly sharing one target would therefore require the
cross-branch locking, marker parsing, conflict handling, and lifecycle layer the
refactor is removing. The smallest current interpretation is one output per
merged media call. If one combined image/audio artifact is confirmed, the only
recommended extension is a pure explicit final composer with no recognition,
provider, retry, resume, sidecar, path discovery, or cleanup ownership. Choice
12 remains open and no runtime/export was changed.

**#584 decision-gate reconciliation.** The twelve numbered choices are evidence
references, not a flat implementation barrier. The combined 8/10 gate blocks the first
internal provider-model proof; public preset scope, merged-image identity,
fallback, audio, and video publication are gated only when their respective
slices begin. Direct wording still conflicts within choices 1–3, so they remain
open rather than being guessed. Choices 4 and 6 no longer offer explicit-only
input as an alternative because provider-derived omission is fixed. Choice 11
now fixes a stateless route to ordinary image/audio resume and leaves only
package-root export open. This sequencing changes no runtime or public API.

**#585 combines choices 8 and 10.** The current built-in resolver already uses
explicit exact-type branches and lazy imports, while Google and DashScope keep
different validated settings. The runtime-only resolved object may contain its
callable module; that does not make executable state part of durable model
identity. The former choices 8 and 10 therefore described two halves of the
same boundary. Route A is one immutable data value plus a controlled adapter ID
and separately supplied exact settings. Route B is an arbitrary callable plus
generic options. A hybrid would duplicate authority and is not a third option.
No class, adapter, resolver, setting, preset, or public API changed.

**#586 fixes choice 9 without a token ledger.** Current image state preserves
slot call counts but not token totals and clears reused current usage, so
historical image tokens disappear. Current long audio persists token/call facts
inside settled slots and derives current versus historical output from which
slots were loaded; it does not persist two aggregate buckets. The replacement
therefore keeps one cumulative per exact provider-model in the job sidecar and
one current-run delta in memory. Updated failed-attempt evidence is saved before
the next provider attempt. Ordered settled-slot state remains independently
necessary for resume, but is not an itemized billing ledger. Unknown token
dimensions remain unknown. No runtime/state schema changed.

The following are not open implementation shortcuts: audio intervals are
integer minutes; `-1` means no split only at the call boundary; full frames are
retained; image/audio providers are separate; callers compose the visible video
steps and no replacement video black box is planned; video resume delegates to
image and audio batch resume; repair is experimental and does not block
deletion; caller media is never deleted; failed batches retain one terminal
failure; and social-media work stays frozen.
