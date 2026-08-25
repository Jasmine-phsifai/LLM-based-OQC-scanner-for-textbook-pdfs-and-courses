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
- Normal product layout follows the legacy convention of creating a same-named
  folder beside the source. Cross-media name collisions are therefore unusual.
  Prefer simple duplicate rejection and normal active-call protection over a
  speculative cross-process transaction or locking system.
- #071 removed the obsolete lazy-iterator machinery while retaining the
  batch-lifetime output owner for valid concurrent execution and race protection;
  do not replace it with speculative cross-process coordination.

## Provider usage accounting

- Keep accounting understandable. Accumulate provider-reported input and output
  tokens by the exact model that produced them, together with that model's call
  count.
- Never estimate missing token usage and never turn an unavailable usage value
  into zero. Google and other providers may omit usage on errors, empty replies,
  or interrupted requests.
- Candidate, draft, and review records may remain diagnostic facts, but must not
  grow into a second billing engine. Do not keep adding complex reconstruction
  logic to every rare error exit.
- Distinguish current-invocation usage from historical usage restored from a
  checkpoint.

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
- **Open #152 A2b chunk scope.** Choose whether the persisted A2b path (A) splits
  only audio above Google's 9.5-hour single-prompt ceiling, or (B, recommended)
  uses fixed ordered chunks for every long MP3 so ordinary lecture failures can
  resume without replaying all settled work. A minimizes calls but does not
  address the main unstable-provider recovery case. B consumes more request
  quota and requires a fixed overlap policy. Keep the existing A2a entry as the
  explicit one-shot option either way; do not add a configurable/adaptive
  threshold before this choice is made.
- **Recommended complete #152 answer.** Choose B, require the caller's original
  MP3 to remain available and strongly unchanged during resume instead of
  storing a second long-lived full copy, and begin with the legacy-evidenced
  fixed 1,800-second logical windows plus 30 seconds of boundary context. Ask
  the model to emit only the logical range; do not add programmatic transcript
  similarity/deduplication in the first slice. This one yes/no decision freezes
  chunk scope, source ownership, and overlap handling without creating public
  chunk controls or a generic checkpoint system.

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
- The difficult provider work is mechanical live verification of the real model
  catalog, error codes, retry/switch behavior, and terminal outcomes. Do not
  install a generic policy such as "retry six times". Retry decisions must be
  supported by evidence for the specific provider and error scope.
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
- **Open #127 cancellation choice.** `image_config` and `audio_config` may carry
  different cancellation signals, but the current facade treats them
  asymmetrically: image cancellation becomes settled frame outcomes and lets
  audio continue, while audio cancellation propagates and hides an already
  settled frame result; silent video can ignore that audio signal entirely.
  Choose one public contract before implementation: (A, recommended) branch
  cancellation settles in existing `frame_error`/`audio_error`, preserves the
  other branch, and skips pre-cancelled audio extraction; if both signals are
  already set, stop before output. (B) any branch cancellation aborts the whole
  call, which requires a larger way to carry already-paid outcomes without
  losing them. Keeping the current asymmetry is not an option. Do not add a new
  status, branch hierarchy, checkpoint, or extractor cancellation framework as
  part of this choice.
  #145 executed the exact public matrix without provider calls: image-only
  cancellation returns a partial outcome and lets audio run; audio-only
  cancellation hides one completed image branch by raising; both signals still
  perform media extraction before raising; silent video ignores audio-only
  cancellation and returns complete/absent. Legacy production evidence requires
  settled paid work to survive cancellation but cannot choose return-versus-
  raise for this non-persistent API. Maintainer selection of A or B is still
  required before implementation.
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
  to historical explicitly marked Markdown compatibility. #120 answered no;
  the next authority is the ordered P1-e video slice, not repair or provider
  generalization.
