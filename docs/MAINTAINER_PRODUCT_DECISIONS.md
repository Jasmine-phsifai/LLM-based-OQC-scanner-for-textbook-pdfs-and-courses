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
  next authority item is the already-bounded P1-d manual repair in
  [`ACTIVE_STATE_AND_RULES.md`](ACTIVE_STATE_AND_RULES.md#p1-d--minimal-pdf-repair-after-stable-markers).
  Do not create a parallel queue or start provider generalization here.
