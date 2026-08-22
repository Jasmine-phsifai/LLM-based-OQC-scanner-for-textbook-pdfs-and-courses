# Active State And Rules

Status: **authoritative and current.** Last verified 2026-08-23 against the
working tree, tests, and recorded commit history.

This file outranks every other document in this repository. Read it before
`docs/ocrllm_library_go_no_go.md`, before `START_HERE.md`, and before any
`phase*` file.

## Document Precedence

Contradictions between documents are resolved in this order. A lower-ranked
file never overrides a higher-ranked one.

```text
1. docs/ACTIVE_STATE_AND_RULES.md     This file. Current truth and rules.
2. docs/plan_phase1_maturation_and_phase2_audio.md
                                      Current work plan; implementation status
                                      is recorded here, not inferred from the
                                      plan text.
3. docs/plan_phase1_defects_and_provider_split.md
                                      Stage 1 history and the not-started
                                      vision/audio split plan.
4. docs/ocrllm_library_go_no_go.md    Execution contract, gates, boundaries.
                                      Its dated verification log is history.
5. MIGRATION_STATUS.md / START_HERE.md  Navigation copies of this state.
6. docs/phase*, *_decision_*, *_checkpoint_*
                                      Immutable historical records. Never cite
                                      them as current state.
```

Every dated phase, decision, checkpoint, and incident file is a frozen record
of one past attempt. It keeps the trace but does not define the present. Read
this file first, then verify the named code and tests before trusting any
historical claim.

## Project Posture Changed

The library was built as a feasibility spike: prove that one narrow vertical
slice (DashScope + image) could carry a stable public contract. That question
is answered. The contract, quality-gate, and error layers work.

**The posture is now a maintained product**, not a probe. This changes three
things:

- Defects in shipped surface outrank new capability. A known false-success path
  is not acceptable because "the phase is complete".
- Structure is justified by an observed failure, not by an anticipated one.
  Anything already built that lacks a consumer is frozen, not extended.
- Documentation is a maintained artifact with a single current-state file, not
  an append-only research log.

Phase 1 is consequently reopened for maturation. "Phase 1 is GO" means the image
path was proven once under trial constraints; it does not mean the image path is
finished. Stage M is **offline implementation-complete**: model catalog
discovery, file-backed state sidecars, opt-in disposition-gated candidate
queues, slot-indexed intra-request checkpoints, spend disclosure, and
model-aware credential blocking have shipped. Its exit gate remains open until
the authorized paid live smoke verifies current provider behavior. The former
standalone Stage 2 vision/audio scaffold was replanned on 2026-08-23: the
working image configuration stays unchanged and the audio-specific
configuration boundary will land with the first executable Stage A1 short-MP3
slice. Stage A1 and A2 have not started.
The built-in Google image adapter is now scoped as a later optional
vertical slice: it reuses the shared vision/candidate/checkpoint contracts and
does not copy legacy retry, audio, GUI, or social architecture. It is planned,
not implemented, and does not block Stage A.
See `docs/plan_phase1_maturation_and_phase2_audio.md`.

## Known Debt In This Repository

Future agents must assume the following and verify before trusting any claim:

- **Fixture byte-reproduction is environment-bound (redesigned 2026-08-19).** The Phase 1 generated-image corpus can only be byte-reproduced in the exact Pillow wheel build that created it; that environment is lost and no installable 12.x build reproduces the pinned pixels. `tests/quality/generators/generate_phase1_fixtures.py` now checks three layers instead: manifest-hash integrity (every environment), same-environment determinism, and reproduction that is byte-strict only under the recorded `GENERATOR_ENVIRONMENT` and pixel-tolerant otherwise. Do not re-baseline the committed images without a maintainer decision: they are the pixels the v17 live evidence was scored against.

- **Quality normalizers v2-v7 are an evidence protocol, not duplicate utilities.**
  The current v7 path executes the cumulative v7→v6→v5→v4→v3→v2 chain,
  and the preserved v17 evidence records each file in its quality code identity.
  Do not merge, delete, or rewrite these stages as routine cleanup. A future
  migration requires byte-for-byte differential normalization and score proof
  over preserved evidence plus an explicit archived-identity strategy.

- **Dated documentation is history.** Old phase and review files deliberately
   retain their original conclusions. Current navigation documents must point
   here and must not repeat those conclusions as present status.
- **Structure runs ahead of demand.** `contracts/` and `worker/` are 1,817
  lines (23% of the library) serving a subprocess protocol with no consumer.
  They are correct and tested; they are also not yet load-bearing.
- **Recognition logic is small.** `processors/`, `profiles/`, and `imaging/`
  total 1,059 lines. Most of the library is contract and validation. That ratio
  is acceptable for a library, but it means new capability is cheap and new
  ceremony is expensive. Bias toward capability.

- **Active atomic output no longer amplifies user filenames, but arbitrary deep
  Windows paths remain unsupported.** Markdown and image-resume state writers use
  a fixed `.ocrllm-<uuid>.tmp` sibling instead of repeating the full destination
  basename. Deterministic Windows tests prove a 228-unit Markdown path and its
  243-unit canonical sidecar can publish and resume under a simulated traditional
  259-UTF-16-unit boundary. Public Markdown and `.ocrllm-state.json` names did not
  change. This closes suffix-induced overflow only; it is not general `\\?\`
  extended-path support, and a deeper directory can still exceed the OS limit.

- **Same-target output/state ownership is consistent for supported in-process
  concurrency.** Every file-producing `recognize()` claims its resolved target
  without waiting before provider dispatch, rechecks output existence under that
  claim, and holds ownership through all slot/completed checkpoints, Markdown
  publication, and result construction. `recognize_batch()` shares one thread-safe
  claim owner across all items and retains every acquired target until all
  dispatched work settles, so sequential or non-overlapping colliding items cannot
  both report success even with `overwrite=True`. A duplicate gets `OUTPUT_EXISTS`
  before its provider runs; after the batch exits, ordinary sequential reuse is
  allowed again. Event-coordinated tests cover direct state/Markdown races and the
  longer batch lifetime. This is deliberately process-local; separate processes
  targeting one output directory are not coordinated, and no cross-process
  transaction is claimed.

- **Batch input iteration cannot erase settled work.** `recognize_batch()`
  accepts finite iterables and converts an ordinary failure while opening or
  advancing the iterable into one final, redacted `SOURCE_INVALID` outcome at
  that input position. Earlier successful or failed outcomes remain available,
  including when iteration breaks while fail-fast handling is marking remaining
  inputs `CANCELLED`. Process-control exceptions such as `KeyboardInterrupt`
  and `SystemExit` still propagate. This is a finite-batch contract, not a
  streaming or infinite-input API.

- **Injected-provider protocol lookup is pre-dispatch configuration work.** If
  reading an injected object's required `recognize_images` method raises, the
  call now returns redacted `CONFIG_INVALID` with
  `provider_calls_attempted=0`; the candidate-attempt ledger records the same
  zero. A provider request has not begun merely because method discovery
  failed. Ordinary exceptions raised after entering the callable method remain
  provider failures and count as attempted calls.

- **Completed image resume honors pre-set cancellation without losing saved
  work.** After validating the completed state's source/request identity and
  final Markdown digest, the reuse branch checks the Event-compatible signal
  before output validation or publication. Cancellation raises typed
  `CANCELLED`, makes no provider call, and leaves both state and Markdown bytes
  unchanged; a later uncancelled resume still reuses them with zero calls.

- **Open: an all-slots-reusable partial checkpoint may still bypass
  cancellation.** A partial v2 state whose saved slots already satisfy every
  workflow pass can assemble and publish without reaching a provider start
  check. Audit this path with a direct failing regression before changing
  checkpoint or cancellation ordering; do not assume the completed-state fix
  covers partial replay.

- **Automatic image checkpoint targets are preflighted before dispatch.** When
  `resume=False` but stable provider identity enables paid-work checkpoints, an
  existing non-file canonical sidecar target, including a dangling symbolic link,
  now raises `OUTPUT_PATH_INVALID` before a provider call. The preflight uses
  lexical existence so it cannot erase a broken link by treating it as absent.
  Strict `resume=True` loading retains its existing `RESUME_STATE_INVALID`
  classification. This is a no-write structural preflight, not a promise that
  later permission or filesystem races can be predicted.
  Checkpoint eligibility uses the exact built-in `DashScopeSettings` type or a
  caller-declared injected `resume_identity`; a user provider's class name has
  no effect. This keeps eligibility aligned with configuration, dispatch, and
  resume fingerprinting.

- **Legacy media repair is open debt, not a porting template.** The normal
  video manifest crash, missing-frame false success, and failed-audio cleanup
  deletion found in commit `6b2d9eb` are fixed with direct regressions. Audio,
  board, and video repair now atomically publish each successful retry before
  the next cancellable operation, and cancellation/provider setup errors remain
  visible. Short-audio repair now requires a versioned sidecar containing exact
  source hashes and millisecond unit windows, so current chunk settings cannot
  reinterpret an old failed segment. Standalone board repair now binds exact
  ordered source bytes and saved batch membership through its own versioned
  sidecar instead of parsing filenames. Production board recognition now publishes
  a repairable skeleton before dispatch, atomically checkpoints every settled batch,
  and propagates cancellation/provider setup failures. Video Phase 4 now expands an
  ordinary failed request into exact per-frame failure markers while it still knows
  membership; repair rejects ambiguous historical batch-only markers instead of using
  today's batch size. The exact findings are recorded in
  `legacy_app/AGENTS.md`. New library modalities must extend typed, versioned
  checkpoint state and atomic publication rather than copy localized
  Markdown-regex repair.

- **Legacy independent-vision failover no longer lies about quota.** When the
  explicit `advance_queue_on_retriable_errors` option advances after an
  ordinary 429/5xx, the client now uses a neutral internal signal, suppresses
  the "free quota exhausted" notification, and preserves the original
  provider exception if all candidates fail. Only explicit free-tier markers
  use `FreeTierExhaustedError` and its existing warning. This is a legacy-only
  correction; the active library already has typed quota, throttle, and
  unavailable-provider dispositions.

- **Legacy Google JSON quota wording is classified consistently.** The
  established Google message "You exceeded your current quota ... check your
  plan and billing details" now maps to `QUOTA_EXHAUSTED` whether it arrives
  as plain SDK text or inside a 429 JSON error. The advisory word "billing"
  no longer mislabels that payload as a payment failure. Generic 429 /
  `RESOURCE_EXHAUSTED`, explicit rate-limit markers, genuine payment errors,
  and 5xx retry behavior are unchanged. DashScope-specific `FreeTierOnly`
  markers are not part of this Google contract.

## Verified State, 2026-08-22

Confirmed by execution, not by reading prose. Method noted so it can be redone.

| Property | Result | Method |
|---|---|---|
| Test suite | 1059 passed, 0 skipped, 0 failed (86.68 s) | `D:\Anaconda\envs\OCRLLM\python.exe -m pytest -q -p no:cacheprovider` |
| Import weight | 0.86 ms wall median, 1.49 ms p95; 0 ms CPU median, 15.63 ms p95 | clean-wheel gate, 30 measured fresh processes after two warm-ups |
| Heavy-module isolation | `PIL`, `pypdfium2`, `openai`, `httpx`, `onnxruntime`, and `legacy_app` absent after plain import | outside-repository clean-wheel `sys.modules` probe |
| Phase 1 evidence integrity | 107,246 bytes, SHA-256 `6f0454d6…a96b`, exact match to the recorded claim | `Get-FileHash` |
| Pinned model exists | `qwen3.7-plus-2026-05-26` served by the account | live `GET /models` |
| Snapshot isolation | Provider reads original bytes while a concurrent thread overwrites the source | threaded race probe |
| Corrupt-input rejection | zero-byte, truncated, and extension/content mismatch all raise `InvalidSource` before dispatch | live probe |
| Secret redaction | `api_key` absent from `repr`, error message, and error details | live probe |
| Live error mapping | 401, 403 `AllocationQuota.FreeTierOnly`, 404, timeout all mapped to correct type and disposition | live paid probe |

These are load-bearing and must not regress. The error taxonomy and the
snapshot isolation are the two strongest parts of this codebase; build on them.

## Defect Register

Severity is impact on a real user, not implementation effort. D1-D7 are closed,
including the residual D4 limitation (closed 2026-08-22 by `cd7429c`). Of the
Stage M findings G1-G10 are closed in offline code and tests. The Stage M exit
gate is still open because its paid live smoke has not run; closing a code
finding does not imply that current provider-account behavior was live-proven.
Do not close an entry without a test that fails before the fix.

All seven entries were addressed on 2026-08-18, following Stage 1 of
`docs/plan_phase1_defects_and_provider_split.md`. Regression coverage for D1-D4
lives in `tests/test_defect_register_regressions.py`. The current full-suite
command is:

```powershell
& 'D:\Anaconda\envs\OCRLLM\python.exe' -m pytest -q -p no:cacheprovider
```

The exact result is refreshed by the verification command before each status
update. No paid live call is implied by an offline pass.

### D1 — Provider refusal text is accepted as success. **High. Fixed 2026-08-18.**

Marker coverage was extended on 2026-08-18 for apology-prefixed refusals.

`providers/validate_provider_markdown.py` only asked whether the response
contained a visible character. A model that replied `无法识别图片内容，请重新上传`
or `I'm sorry, I can't help with identifying content in this image` was returned
to the caller as a successful recognition.

Fix: `providers/looks_like_refusal.py` ports the behaviour statement of the
legacy `core/output_quality.py::looks_like_refusal` remedy and is applied inside
`validate_provider_markdown`, so both the injected and built-in paths are
covered. A refusal raises `ProviderError` with the new stable code
`PROVIDER_REFUSED_RECOGNITION` and `details["reason"] == "refusal"`; empty or
control-only output keeps `PROVIDER_RESPONSE_INVALID` with
`details["reason"] == "empty"`. The new code's disposition is registered as
`("change_source", "request")`: the model declined a well-formed request, so the
source is what must change. Detection is capped at 300 visible characters, so a
long transcription containing a refusal phrase is still accepted.

Closed HTML comments are ignored by both visibility and refusal inspection as
of 2026-08-23. A comment-only response is therefore
`PROVIDER_RESPONSE_INVALID`/`empty`, while a refusal phrase hidden in a comment
cannot reject real visible Markdown. Accepted output is still returned exactly
as supplied; comments are removed only from the validation view. The bounded
helper handles closed `<!-- ... -->` blocks across lines. It deliberately does
not claim full Markdown parsing, code-fence awareness, or malformed/unclosed
comment handling.

Provider Markdown must also be strictly UTF-8 encodable as of 2026-08-23. An
exact Python string containing an unpaired surrogate is rejected centrally as
`PROVIDER_RESPONSE_INVALID` with `details["reason"] == "invalid_encoding"`.
This prevents both a memory-only false success and a raw `UnicodeEncodeError`
while hashing a paid checkpoint. The value is rejected rather than repaired
with replacement characters, so published recognition content is never
silently changed.

Offline Phase 1 quality scorer re-run after the change: 70 passed
(`pytest tests/test_run_phase1_quality.py tests/test_quality_gate_application.py
tests/test_score_recognition_result.py tests/test_verify_fixture_artifacts.py`).
No committed corpus expectation changed.

Not addressed by this fix: the Phase 1 v17 GO ran through the old validator, so
that gate could not distinguish a refusal from a transcription. The GO is not
re-established by this change.

### D2 — `Config.timeout_seconds` is not enforced for injected providers. **High. Fixed 2026-08-18.**

`timeout_seconds` was only threaded into the DashScope OpenAI client, so an
injected provider that blocked hung the caller permanently.

Fix: the worker-thread design from S1.2 was chosen over renaming the field,
because `timeout_seconds` is a public field and a caller expects it to bind.
`providers/bounded_provider_call.py` runs each injected-provider call on a
pre-warmed daemon worker thread and joins it with `Config.timeout_seconds`,
raising `ProviderError(code="PROVIDER_TIMEOUT", retryable=True)` when the bound
elapses. The abandoned thread is disclosed in the error as
`details["abandoned_provider_thread"] = True`. The worker is started and parked
*before* the request-start gate is awaited, so thread startup does not disturb
the measured provider cadence, and it never dispatches when the gate raises
instead of releasing. Built-in DashScope calls keep their transport timeout and
are not wrapped.

Known limit: a wedged provider thread cannot be killed. It is abandoned as a
daemon thread rather than allowed to block interpreter shutdown.

Cadence timing uses `time.perf_counter()` as of 2026-08-23. The repository's
Windows Python 3.10 runtime implements `time.monotonic()` with 15.625 ms
`GetTickCount64()` resolution, which could lose most of a short configured
interval at a tick boundary. `perf_counter()` is the high-resolution monotonic
QPC clock in that runtime. A deterministic quantized-clock regression proves a
30 ms permit cannot collapse to one 15.625 ms tick, and integration tests
measure provider entry with the same high-resolution clock. This guarantees
gate authorization spacing; arbitrary thread scheduling and remote network
send time remain outside an exact wall-clock guarantee.

### D3 — `recognize_batch` discards completed paid work on any failure. **High. Fixed 2026-08-18.**

**Signature change, taken deliberately.** `recognize_batch` now returns
`list[BatchItemOutcome]` instead of `list[RecognitionResult]`.
`BatchItemOutcome` carries `index` and exactly one of `result` or `error`, so a
caller reads successes and failures from the same ordered list.

Normal execution remains a bounded worker pool with caller order and fail-fast.
The first failure aborts the start gate and cancels pending futures; calls that
were already dispatched — and therefore already paid for — are drained and
settled, and every source that was never attempted gets a `Cancelled` outcome so
the returned list matches the caller's source order. If the finite source iterable
itself raises an ordinary exception, a final redacted `SOURCE_INVALID` outcome
represents the input position that could not be read instead of hiding all earlier
outcomes behind that raw exception.

### D4 — Image resume does not cover the case that loses money. **Medium. Fixed 2026-08-18.**

Two changes, both using the existing versioned job-state format. No second
checkpoint format was introduced.

1. `resume=True` is no longer rejected outright for injected providers. Reuse is
   opt-in and caller-declared: the provider must expose a nonempty
   `resume_identity` string that changes whenever its recognition behaviour
   changes. Without it the previous `ConfigError` still fires, now naming the
   attribute. The library cannot infer behavioural equivalence of two injected
   objects, so equivalence is never inferred silently.
2. The job-state file is **retained** after successful publication instead of
   being deleted. That single change is what makes a batch resume at item
   granularity: re-running the same batch reuses each completed item's state,
   spends nothing on it, and re-pays only for the items that failed. The
   now-unreachable `output/delete_image_resume_state.py` was removed.

Consequence to know: `output_dir` accumulates one `<stem>.ocrllm-state.json`
beside each published Markdown file. That file is the proof of paid work; do not
prune it as clutter.

Checkpointing inside one request is closed by Stage M2 (see "Stage M
Implementation Status"): each workflow pass now persists as it completes and
`resume=True` reuses persisted passes at slot granularity.

### D5 — Local OCR is not runnable in the maintained development environment. **Medium. Fixed 2026-08-18.**

`local_ocr/load_rapidocr.py` imports `rapidocr` (the 3.x API), while
`D:\Anaconda\envs\OCRLLM` only provided `rapidocr-onnxruntime 1.4.4`, which
exposes a different module and a different result API.

Fix: `rapidocr` 3.9.2 is installed in `D:\Anaconda\envs\OCRLLM`, matching the
`ocr` extra pin `rapidocr>=3.9,<4` in `pyproject.toml`. The `DependencyMissing`
details now name the required distribution and call out
`rapidocr-onnxruntime` as an incompatible substitute. The code was not taught a
second backend API: one supported engine, matched by the environment.

Verify:

```powershell
& 'D:\Anaconda\envs\OCRLLM\python.exe' -c "from rapidocr import RapidOCR; import importlib.metadata as m; print(m.version('rapidocr'))"
```

### D6 — The legacy test suite leaks registry keys. **Low. Fixed 2026-08-18.**

`QSettings.clear()` removes values but leaves the organization key, so each run
left an empty `HKCU\Software\OCRLLMTests-<uuid>` tree behind.

Fix: `legacy_app/tests/delete_test_qsettings_tree.py` deletes the tree in
teardown and refuses any organization name outside the `OCRLLMTests-` prefix.
The 60 orphaned keys present on the development machine were deleted by running
that module directly; all 60 held zero values.

### D7 — `RecognitionResult` prose drift. **Low. Fixed 2026-08-18.**

The field is `source_type`. `Architecture.md` described its values as
`"board" | "pdf" | "video" | "audio" | "office"`; board is a `profile`, not a
source type. Corrected there. `docs/ocrllm_module_target_design.md` was already
correct: `SourceDescriptor.media_type`, `Artifact.media_type`, and
`ProcessorOutput.media_type` are real, distinct fields and are not drift.


## Structure Decisions

### Keep and maintain

- `errors.py`, `provider_error_disposition.py`, and the DashScope error mapping.
  Correct, live-verified, and the foundation for every future provider.
- `imaging/snapshot_image_group.py` and the validation chain. Correct and
  race-proof.
- `config.py` immutability and exact-type validation.

### Keep but freeze

`contracts/` and `worker/` stay in the tree. They are tested and they encode a
real decision about process isolation. Do not delete them.

**Freeze confirmed 2026-08-18. They are closed to change.** No new fields, no
new commands or events, no protocol version bump, and no new tests. They have no
consumer, and 1,817 lines is already 23% of the library.

A future slice that needs to change them must first produce the consumer that
justifies the change, in the same slice. Note that
`contracts/image_recognition_request.py` hardcodes
`provider: Literal["dashscope"]` and `profile: Literal["board"]`, so the protocol
cannot represent modality splitting or audio. That revision belongs to whichever
slice delivers a real consumer, and to no slice before it.

When a Phase 1 change makes a frozen contract inaccurate, record the divergence
in this file and move on. Do not chase the contract into sync.

### Reconsider before reuse

The three-scout standalone-sign quorum costs four provider calls per image. In
the v17 evidence it restored exactly one sign across 26 dispatches. Keep the
code; it is careful and correct. Do not treat it as the default workflow for
future providers or media types without re-measuring its yield on that provider.

## Coding Rules

These are additive to the implementation directive in
`docs/ocrllm_library_go_no_go.md`, which remains in force.

1. **One file, one responsibility, named for that responsibility.** This rule
   stays. It has been applied past its purpose in places: an 8-line file for a
   single predicate costs more navigation than it saves. Group trivially small
   pure helpers with their only caller.
2. **Validate at boundaries, once.** Do not re-validate an already-validated
   immutable value on every internal hop.
3. **No success without content.** Empty, control-only, *and refusal-shaped*
   provider output are all failures. See D1.
4. **No unbounded wait.** Every path that can block on an external party must
   have a caller-visible bound. See D2.
5. **Never destroy paid work.** Any operation that has already spent money must
   surface what succeeded, even when a later item fails. See D3.
6. **No hidden cost.** Revised 2026-08-18; see "Policy Change: Disclosed
   Automatic Recovery" below. Automatic retry and model switching are now
   permitted, but only when the caller opted in and every attempt is disclosed.
   Silent extra paid calls remain forbidden.
7. **New structure requires a failing case.** Add an abstraction when a real
   failure demands it, not when one is imagined.
8. **Legacy evidence is a warning, not inheritance.** A failure observed in the
   legacy parent deserves a focused check when that capability is ported. Do not
   assume the new library has the same defect or add a defense before proving the
   analogous path exists.
9. **Sustainability includes comprehension.** Defensive code must cover real side
   effects without making the child product stronger or wider than the legacy app.
   The maintenance cost paid by the next agent is part of the design cost.

## Google Robustness Test Authority

Updated 2026-08-23. The maintainer directly authorizes bounded Google API use for
image and audio robustness tests without a separate budget request. Google is free
for this account and is valuable precisely because real calls frequently expose
quota-window limits, temporary overload, API errors, empty replies, unsupported
formats, and excessive-image limits. These are expected test outcomes, not reasons
to weaken validation or report false success.

Select models from the live Google catalog rather than a hardcoded list. Audio is
supported by fewer Google models than images, so verify current audio capability
before dispatch; native multimodal models are valid candidates when served. Keep
calls purposeful and bounded, preserve exact outcomes, never print credentials, and
submit only authorized data. This authority does not activate a deferred provider
adapter or social-media feature. The detailed operational policy is
`docs/provider_cost_and_reliability_policy.md`.

Real legacy incidents have higher evidence weight than code-only suspicions but do
not prove inheritance. In particular, Windows paths beyond roughly 260 characters
caused failures across multiple legacy stages. The source record is the 2026-08-18
path-handling entry in `legacy_app/AGENTS.md`. Test the analogous boundary when a
filesystem-producing child capability is actually ported; do not pre-build a generic
path framework for capabilities that do not yet exist.

## Policy Change: Disclosed Automatic Recovery

Decided 2026-08-18. This **reverses** part of the earlier rule in
`docs/ocrllm_library_go_no_go.md` that reads:

> Perform no automatic model switch, key rotation, paid-provider fallback, or
> hidden retry in the first adapter.

That rule existed to prevent *undisclosed* paid calls. It was correct about the
harm and too broad about the mechanism. A provider on a free tier returns
`QuotaExhausted` on a per-model basis, and a library that cannot move to the
next free model forces every caller to reimplement the same loop.

The rule is replaced by four conditions. All four must hold.

1. **Opt-in.** Automatic recovery happens only when the caller supplies an
   explicit candidate list. No default candidate chain. An unconfigured call
   behaves exactly as it does today: one attempt, then a typed error.
2. **Disclosed.** Every attempt appears in an ordered attempt ledger in the
   result metadata and in the error details: model tried, disposition, and
   outcome. A caller must be able to reconstruct exactly what was spent.
3. **Disposition-gated.** Switching triggers only when an approved failure is
   explicitly model-scoped: quota exhausted, unavailable, or permission denied
   for that model. Account-, credential-, provider-, and request-scoped failures
   stop. Never switch on a generic failure, `PROVIDER_RESPONSE_INVALID`, or a
   refusal.
4. **Bounded.** A maximum attempt count and a terminating error when the whole
   chain is exhausted. No unbounded loop, no silent give-up.

The behavior oracle is `legacy_app/OCRLLM/core/llm_client.py`, functions
`_vision_fallback_chain`, `_call_with_free_tier_fallback`, and
`_notify_free_tier_switch`. Legacy already orders the caller's primary model
first, slides down the chain on free-tier exhaustion only, notifies the user on
every switch, and raises a distinct "all exhausted" error at the end. Port that
behavior statement, not the file.

## Policy Change: Model Discovery Replaces The Fixed Allowlist

Decided 2026-08-18. The three-model DashScope allowlist in
`resolve_dashscope_model.py` is retired as a gate on caller choice.

The allowlist was protecting a real thing: live quality evidence is measured
against one pinned model snapshot, and silently changing models invalidates it.
That protection is preserved by separating two concepts that were conflated:

- **The evidence baseline** stays pinned and named in result metadata. A quality
  claim always states which model produced it.
- **Caller model choice** is validated against the provider's live catalog, not
  against a hardcoded set. An unknown model fails because the provider does not
  serve it, not because a constant in this repository is out of date.

A model outside the evidence baseline is usable and must be reported as
unproven, not blocked. Do not silently imply baseline quality for a model that
was never gated.

Implementation status: shipped. Since 2026-08-22 the static set is deleted;
catalog validation applies to every non-pinned model, and only the pinned v17
baseline bypasses the catalog because its proof is the live gate itself. The
policy text above now matches the code.

Relevant measurement: the `board.v17` prompt against `qwen3.5-ocr` produced 16
completion tokens and no usable output, while the pinned model produced a full
transcription from the same prompt and image. Prompt and model class are
coupled. Discovery makes a model *selectable*; it does not make it *proven*.

## Stage M Implementation Status, refreshed 2026-08-22

Stage M is **offline implementation-complete**. The following behavior is
shipped and tested offline:

- Non-baseline DashScope model names can be checked against a lazy provider
   catalog. Successful catalogs have a 600-second TTL; expired catalogs remain
   usable during refresh failure; a first catalog failure is surfaced as the
   retryable `PROVIDER_CATALOG_UNAVAILABLE` error. The catalog path is lazy.
- File-backed image recognition writes versioned state atomically before
   publishing Markdown. Re-running a compatible batch can reuse completed
   request outputs. Within one request, each completed workflow pass persists
   as a slot in the same sidecar before the next paid call starts, and
   `resume=True` pays only for missing passes. Injected-provider resume still
   requires a caller-declared nonempty `resume_identity`.
- An explicit `VisionModelSettings.candidate_models` queue is attempted in
   caller order and advances only when quota exhaustion, unavailability, or
   permission denial is explicitly model-scoped. Account-, credential-, and
   provider-scoped failures stop. The queue is bounded and opt-in; a single-model
   call retains its original typed failure. Every attempt discloses outcome and
   paid-call count, and chain exhaustion raises the distinct
   `ALL_CANDIDATES_EXHAUSTED` code with its canonical account-wide disposition,
   not the final candidate's model scope.
- DashScope free-tier and unpurchased-commodity quota codes are mapped to model
   scope, so the credential pool blocks that model rather than the account;
   account suspension remains account-wide. This distinction is offline-tested
   but has not been re-proven against the live account in this update.
- Scout failures name the scout model and never advance the primary candidate
   queue. Injected typed errors retain only an allowlisted canonical
   `failure_scope`; arbitrary provider details remain discarded.

Every non-paid Stage M exit criterion now passes. Commit `2e9c770` passed the
reusable clean-archive runner in `tools/run_stage_m_offline_gate.ps1`: its
archived suite reported 1059 passed and one expected optional-RapidOCR skip,
fixture verification and compilation passed, the wheel was 150,795 bytes, and
the no-deps target was 736,133 bytes. Fresh `image` and `image,dashscope`
profiles added 16,424,795 and 40,997,504 bytes respectively and passed their
offline smokes. Plain import stayed below every documented wall and process-CPU
budget in both Python environments. The built-in adapter now proves dispatch of
a catalog-served model unknown to this repository, and an operating-system
process-termination test proves a completed paid slot survives and resume pays
only for the missing slots. `worker/` and `contracts/` are unchanged and frozen.

The Stage M exit gate has **not** passed because its paid live catalog and
end-to-end smoke still requires an explicit maintainer budget. No paid provider
request occurred in the offline gate. Do not convert this no-cost proof into a
claim about current provider-account or model-quota semantics.

### Stage M Findings

These are current implementation findings, not historical phase failures.
Their identifiers are stable so plans, tests, and future diary entries can
refer to the same issue.

#### G1 — Attempt ledger cannot reconstruct spend. **High. Closed 2026-08-22.**

`cd7429c` added `provider_calls_attempted` to every successful or typed-failure
`model_attempts` entry and a `workflow_slots` disclosure in result metadata.
Pre-dispatch configuration failures now add a `fix_request` ledger entry with
zero provider calls and `model: null`: no provider model was tried, and
caller-controlled invalid text cannot leak through public error details. If a
fixed scout model fails catalog resolution after a paid primary pass, the same
entry retains that prior call count and names the setup workflow pass.

#### G2 — Recovery is quota-only. **Medium. Closed 2026-08-22; scope corrected 2026-08-23.**

The opt-in candidate loop advances for quota exhaustion, unavailability, and
permission denial only when the disposition is model-scoped. It stops for
account quota, provider outage, credential denial, authentication failure,
response-invalid, refusal, and every other wider or unapproved failure. This
scope rule was corrected after regressions proved that account quota and a
provider-wide outage each spent an unnecessary sibling candidate. Exhaustion
wrapping occurs only when the caller configured a candidate list; it removes the
last candidate's model scope so `ALL_CANDIDATES_EXHAUSTED` keeps its canonical
account-wide disposition. Single-model failures retain their original public
identity.

#### G3 — Account blocks prevent eligible model candidates. **Medium. Closed offline 2026-08-22; live semantics pending exit gate.**

Known DashScope free-tier and unpurchased-commodity quota codes now carry model
scope and create only a model block in the credential pool; account suspension
continues to block every model. Tests prove sibling-model acquisition remains
available after model quota. No paid call ran in this update, so whether the
provider still applies those product states per model must be rechecked by the
Stage M live smoke rather than presented as live-proven fact.

#### G4 — Chain exhaustion has the wrong public identity. **Medium. Closed 2026-08-22.**

`AllCandidatesExhausted` no longer subclasses `QuotaExhausted`. It is a direct
`ProviderError` with the new stable code `ALL_CANDIDATES_EXHAUSTED`
(non-retryable, disposition `("stop", "account")`), so callers can distinguish
"the entire configured chain ended" from "one model exhausted." The class moved
from the deleted `all_candidates_exhausted.py` shim into `errors.py`.

#### G5 — Proven-model metadata is too broad. **Medium. Closed 2026-08-22.**

The retired static set lost both remaining roles. `model_evidence` metadata is
now `"proven"` only for the pinned v17 baseline `DEFAULT_DASHSCOPE_MODEL`;
every other model is selectable but `"unproven"`. Catalog validation in
`resolve_dashscope_model` now applies to every non-pinned model (formerly the
static set bypassed it); the pinned baseline keeps its bypass because its proof
is the v17 live gate, not a catalog row. `SUPPORTED_DASHSCOPE_MODELS` is
deleted. The later `resolve_dashscope_maximum_images` shell was also deleted:
its unused model argument always produced the same limit already imposed by
the library, so its candidate could never affect the effective limit or source.

#### G6 — Resume identity version is stale for candidate queues. **Medium. Closed 2026-08-22.**

Closed by `cd7429c` (the Stage M2 slot-resume slice, reviewed and cherry-picked
from the unmerged `stage-m2` branch). The identity version is now explicit:
`ocrllm.image-request.v2`, stored in every new state file. A v1 state is
rejected with `RESUME_STATE_MISMATCH` naming both versions; the v2 document
also hashes the board and sign-scout prompt versions. Nothing migrates; a v1
state is treated as foreign work. See the M2 section below.

#### G7 — Flowed output is not implemented. **Medium. Closed 2026-08-22.**

Closed by `cd7429c` at request granularity: each completed workflow pass
(draft, review, each sign scout) persists immediately as a slot in the
versioned sidecar before the next paid call starts, and `resume=True` seeds
from persisted slots and pays only for missing passes. Batch granularity was
already covered by D3/D4 (one output file plus one retained state sidecar per
item). Proven at the state-machine boundary by `tests/test_m2_slot_resume.py`
and at the operating-system boundary by
`tests/test_m2_process_kill_resume.py`, which terminates a child process after
its second pass starts and then resumes from the first persisted slot.

#### G8 — Scout failures are attributed to the primary model. **Medium. Closed 2026-08-22.**

Every workflow-pass failure now carries its resolved `failed_model`. The outer
candidate ledger distinguishes a scout failure from a primary-model failure,
records the scout identity, and raises without advancing the primary candidate
queue. A built-in DashScope regression proves one primary call plus one failed
scout call and no candidate switch.

#### G10 — Candidate validation is weaker than primary validation. **Low. Closed 2026-08-22.**

`VisionModelSettings` now validates `name` and every `candidate_models` entry
through one shared exact-text predicate (nonempty, already-trimmed, no control
characters), so the recovery chain can no longer accept a name the primary
field would reject.

#### G9 — Catalog outage fail-open. **Closed 2026-08-19.**

Commit `4c5293d` made first-fetch catalog failure retryable and fail closed,
while retaining the last successful catalog during refresh outages.

## Legacy Status, 2026-08-23

Seven legacy durability/repair-hardening slices are complete. `repair_board()` reads the
normal `{"items": [...]}` manifest, accounts for unavailable processed frames
as explicit partial failures, and video cleanup retains extracted audio while
failed transcript segments remain. Audio, board, and video repair now publish
each successful retry through a shared same-directory atomic text writer before
another provider call can be cancelled. Board no longer swallows cancellation
or provider-setup failures. Short-audio outputs now persist source/input SHA-256,
exact millisecond windows, stable unit IDs, splitter metadata, and request audit
metadata in a versioned adjacent manifest. Repair fails before provider dispatch
when that identity is missing or inconsistent. Production short-ASR now publishes
that manifest plus an all-unfinished Markdown checkpoint before dispatch, uses a
bounded rolling request window, and atomically republishes every settled segment.
Cancellation or provider setup failure stops new submissions, drains already-running
calls, preserves their successes, and then propagates. Standalone board outputs now
persist exact ordered source fingerprints, saved batch membership, stable unit IDs, and
machine-readable batch status. Repair resolves renamed sources by bytes, rejects
missing/corrupt/drifted identity before dispatch, and no longer relies on comma-split or
duplicate basenames. Production board recognition now publishes an all-repairable
Markdown skeleton before dispatch, atomically republishes each success or ordinary
failure, and propagates cancellation/provider setup errors without losing prior paid
work. Video batch failures now persist exact frame IDs, and ambiguous old batch-only
outputs fail before provider dispatch instead of being reinterpreted with current
configuration. The media-repair identity queue is closed; earlier fixes remain recorded
history, not proof that all compatibility paths are defect-free.
## New And Fixed In This Working Update

Video repair no longer reconstructs historical failures from today's batch size:

- `_phase4_batch_one()` converts every ordinary failed multi-frame request into one
  existing frame metadata marker and one failure marker per exact frame. Production
  therefore persists repair identities while membership is known instead of saving an
  ambiguous batch ordinal.
- `repair_board()` repairs only explicit frame IDs. The current-batch expansion and
  batch-placeholder replacement branches were deleted. Historical outputs containing
  only `批次 N 失败` are rejected before frame loading, progress callbacks, or provider
  dispatch because their original membership cannot be proved.
- A proposed video sidecar was rejected after code review showed it would preserve an
  avoidable batch abstraction. Per-frame markers already form the legacy repair unit;
  this fix removes more production code than it adds and does not create a schema or
  generic media framework.
- Two direct regressions failed before implementation. The video/resume/failure/quality/
  writer set passed 40 tests in 26.31 s; the offline legacy suite excluding the real
  ffmpeg e2e and deferred import-time Bilibili diagnostic passed 272 tests with one
  explicit live-Google skip in 90.30 s. `py_compile` and `git diff --check` passed. No
  provider, network, active-library, frozen-boundary, or social-media behavior changed.

The current-batch grouping in partial Phase 4 resume remains an efficiency characteristic,
not a repair-identity path: it can cause re-payment but cannot redirect a historical failed
batch. It is unchanged pending separate evidence.

### Previous working update: production board checkpoints

Production board recognition now checkpoints every batch:

- After saving its existing versioned identity sidecar and before the first provider
  request, `BoardProcessor.process()` atomically publishes one repairable failed slot
  per saved batch with the explicit reason `任务未完成`. This reuses the existing marker
  and repair contract; no new status or checkpoint schema was added.
- Each successful or ordinary failed batch replaces only its fixed slot and atomically
  republishes the whole ordered Markdown before progress callbacks or later cancellation
  checks. Cancellation and provider setup failures propagate unchanged, leaving the
  current and later slots repairable while preserving prior paid successes.
- Four direct regressions failed before implementation. The checkpoint/identity/repair/
  failure set passed 26 tests; the offline legacy suite excluding the real ffmpeg e2e
  and deferred import-time Bilibili diagnostic passed 270 tests with one explicit live-
  Google skip. The final runs took 25.46 s and 87.96 s respectively. `py_compile` and
  `git diff --check` passed. No provider, network,
  active-library, frozen-boundary, or social-media behavior changed.

Video failed-batch identity was still open at that checkpoint and is closed by the current
update above.

### Previous working update: stable standalone board identity

Standalone board repair now has stable source and batch identity:

- Before its first provider request, `BoardProcessor.process()` atomically publishes a
  versioned `.board-repair.json` sidecar. It records exact ordered source size/SHA-256,
  stable item and batch IDs, exact batch membership, and prompt/preprocessing audit
  metadata. Markdown carries one machine-readable index/unit/status marker per batch.
- Repair validates schema/version, source collection, item and unit IDs, complete batch
  coverage, and Markdown mapping before dispatch. Missing/corrupt/unsupported state,
  source-byte drift, extra/missing inputs, or presentation-unit drift fails closed.
- Sources are resolved by exact bytes rather than basename. Rename therefore remains
  safe, while comma-containing names and duplicate basenames cannot redirect a paid
  retry. Prompt, model, and preprocessing remain mutable repair-attempt choices; the
  immutable unit is the original source-byte membership, not one past transformation.
- Six regressions failed before implementation. The final identity/repair/failure set
  passed 22 tests; the offline legacy suite excluding the real ffmpeg e2e and the
  import-time live-Bilibili diagnostic passed 266 tests with one explicit live-Google
  skip. Compilation and diff checks passed. No provider, paid, active-library, or
  frozen-boundary behavior changed. A broad run exposed that the Bilibili diagnostic
  performs public HTTP during collection; it timed out and remains open test debt.

Video failed-batch identity was still open at that checkpoint and is closed by the current
update above.

### Previous working update: production short-ASR checkpoints

Production short-ASR durably checkpoints paid parallel work:

- Before the first provider request, `_short_asr()` publishes the versioned repair
  manifest and a complete Markdown skeleton whose slots are explicitly unfinished.
- It submits only a rolling window bounded by the configured worker count. The
  coordinator consumes futures in completion order and atomically republishes the
  complete ordered document after every settled success or ordinary failure.
- Cancellation and provider setup failure stop further submission and cancel work
  that has not started. Already-running calls are drained so successful responses are
  checkpointed before the terminal error is propagated; cancellation takes precedence
  if both terminal conditions occur.
- Three direct regressions first failed. Five checkpoint tests plus audio-repair tests
  passed 16 tests; the legacy suite excluding the real ffmpeg e2e file passed 258 tests
  with one explicit live-Google skip. `py_compile` and diff checks passed. No provider,
  network, active-library, or frozen-boundary behavior changed.

Video failed-batch identity was still open at that checkpoint and is closed by the current
update above.

### Previous working update: stable audio repair identity

Short-audio repair has a stable unit-identity contract:

- `_short_asr()` publishes a versioned `.audio-repair.json` sidecar containing
  SHA-256 and size for both the selected source and actual ASR input, exact
  actual/logical millisecond windows, a source-and-window-derived unit ID,
  splitter settings, and original model/prompt/hotword hashes for audit.
- `repair()` validates schema, source bytes, ASR-input bytes, contiguous windows,
  unit IDs, and the Markdown-to-manifest segment map before any provider call.
  Missing, corrupt, unsupported, source-drifted, or presentation-mismatched state
  fails closed; old output is not silently re-split with today's settings.
- Failed windows are regenerated from saved `-ss`/`-t` bounds. The current chunk
  duration and context configuration is not consulted. The domain identity error
  is deliberately distinct from ordinary recognition `RuntimeError`, so the
  existing audio/video GUI summaries preserve its explanation rather than
  collapsing it into a generic “all segments failed” result.
- Three regressions failed before the implementation. The final focused
  audio/video/resume/failure/GUI set passed 112 tests; the legacy suite excluding
  the real ffmpeg e2e file passed 253 tests with one explicit live-Google skip.
  Compilation and diff checks passed. No provider, network, active-library, or
  frozen-boundary behavior changed.

Board batch/basename and video failed-batch identity were still open at that checkpoint
and are closed by later updates above.

### Previous working update: atomic repair publication

Legacy repair publication now has one explicit durability contract:

- `write_text_atomically()` stages UTF-8 text in a unique file beside the
  destination, flushes and fsyncs it, and publishes only with `os.replace()`.
  Encoding, fsync, and replace failures preserve the prior output, clean the
  staging file, and propagate the original exception.
- Audio, board, and video publish a recognized unit immediately after its
  modality-specific failure marker is replaced. A later `CancelledError`
  therefore remains observable without discarding earlier paid success.
- Board now re-raises cancellation and provider setup errors; audio also
  propagates provider setup errors consistently with video. Ordinary partial
  failures retain their prior error contract.
- Twelve direct repair/writer tests passed after five repair regressions first
  failed. The focused repair/resume/failure-propagation set passed 43 tests; the
  legacy suite excluding the real ffmpeg e2e file passed 244 tests with one
  explicit live-Google skip. Compilation passed. No active-library,
  frozen-boundary, network, or provider behavior changed.

Stable board batch/basename and video failed-batch identity were still open at that
checkpoint and are closed by later updates above.
The shared writer is intentionally only a file-publication primitive; localized
marker transformations were not centralized or promoted into a library API.

### Previous working update: video repair artifact boundary

The current legacy video-repair artifact boundary is verified as follows:

- The Phase 3 manifest reader now consumes the writer's dict schema and treats
  malformed entries defensively. An explicitly missing processed artifact is
  not silently replaced by a source fallback; its frame ID remains a failed
  outcome while successful siblings are still published.
- Cleanup reuses `AudioProcessor.find_failed_segments()` and retains only the
  extracted MP3 needed for repair. A clean transcript still permits the prior
  cleanup behavior, so the fix does not become a broad disk-retention switch.
- The three regressions failed before the fix and pass afterward. The focused
  video/audio slice passed 73 tests; the legacy suite excluding the real ffmpeg
  e2e file passed 235 tests with one explicit live-Google skip. Compilation also
  passed. No active-library, frozen-boundary, network, or provider behavior was
  changed. The later working update closed non-atomic/cancellation publication;
  the current update closes the remaining batch-size-dependent repair identity.

### M2. Flowed output and true resume, 2026-08-19

A single `recognize()` call spends up to six provider calls (drafts, review,
three sign scouts). Each completed pass now persists immediately as a
slot-indexed record in the existing `<stem>.ocrllm-state.json` sidecar, and a
crash mid-request discards nothing that was already paid for.

- `image_slot_checkpoint.py` persists one `ImageSlotState` per workflow pass
  (slot id, workflow pass, provider, actual model, validated Markdown with its
  SHA-256, calls attempted) through the existing atomic state writer. No new
  storage backend: the state document gained a `slots` array and is otherwise
  the same versioned sidecar. Slot writes are atomic replaces, so the file is
  valid after every paid call.
- Resume is slot-granular. `resume=True` with a matching fingerprint seeds the
  checkpoint from the persisted slots and pays only for the missing passes; a
  slot is reused only by the same provider **and** model that produced it, so
  a quota fallback to another model never inherits the failed model's passes.
  Preservation is not opt-in: injected providers keep the D4 `resume_identity`
  declaration, and any checkpoint-eligible run persists slots even without
  `resume=True`.
- A partial checkpoint can coexist with an older Markdown after an
  `overwrite=True` run is interrupted. Because state v2 does not persist the
  overwrite authorization or identify that older artifact, `resume=True` now
  rejects this ambiguous pair with `RESUME_STATE_MISMATCH` before dispatching
  another provider call. The caller can move or remove the old Markdown and
  resume from the retained slots. Automatic continuation through that case
  would require explicit prior-output provenance in a future state version;
  the library does not silently infer permission to overwrite.
- **Fingerprint identity break, v1 to v2 (audit finding G6).** Commit
  `a19776d` silently changed the v1 fingerprint by adding `candidate_models`
  to the hashed document. The identity version is now explicit:
  `ocrllm.image-request.v2`, stored in every new state file. A state written
  under v1 is rejected with `RESUME_STATE_MISMATCH` whose details name both
  versions (`state_identity_version` / `request_identity_version`). Upgrade
  behavior: nothing migrates; a v1 state is treated as foreign work and the
  request re-runs only after the caller removes it or runs without
  `resume=True`. The v2 document also hashes the board and sign-scout prompt
  versions, closing a silent-stale-resume hole that v1 left open.
- **Paid-call disclosure (audit finding G1).** `RecognitionResult.metadata`
  now carries `workflow_slots`: per slot the workflow pass, provider, actual
  model, whether the slot was reused from disk, and calls attempted. Every
  `model_attempts` ledger entry — success or typed failure — carries
  `provider_calls_attempted`, so a successful fallback no longer discards what
  the failed candidates spent. Typed failures keep their `workflow_pass` and
  `provider_calls_attempted` details. If a validated paid pass then fails while
  atomically persisting its slot, the `OUTPUT_WRITE_FAILED` error also names
  that workflow pass and the current invocation's attempted-call count. Earlier
  slots remain intact, and no final Markdown is published. A completed-state
  write can separately exceed the 16 MiB sidecar limit after all slots fit,
  because completed state also carries the assembled result. That failure now
  reports the current invocation's total calls across every model attempt while
  deliberately omitting `workflow_pass`: all provider passes succeeded and the
  failure is local final-state materialization. The partial sidecar remains
  resumable; a zero-call resume that reaches the same limit reports zero.

Regression coverage is `tests/test_m2_slot_resume.py`: an injected mid-request
failure proves slot reuse including sign-scout passes, a hand-written v1 state
proves the version-named rejection, a candidate-fallback run proves
failed-model slots are neither reused nor lost, and a prompt-version bump
proves resume identity invalidates. `tests/test_m2_process_kill_resume.py`
adds the stronger operating-system termination proof. The current offline gate
results are recorded in the Stage M status above. No paid live call was made.
`worker/` and `contracts/` are unchanged.

## Documentation Rules

The `docs/` directory contains both current policy and immutable historical
records. This section prevents the historical volume from becoming a second
source of current truth.

1. **One current-state file.** This file. Update it in place; do not add a
   parallel status document.
2. **Historical records are immutable and clearly dated.** A `phase*` file is
   never edited after its gate closes and never cited as current state.
3. **Do not create a decision file and a checkpoint file per slice.** One entry
   in this file plus one dated record if a paid gate ran.
4. **A capability claim names its verification command.** A claim that cannot be
   re-run is not evidence.
5. **When code and documentation disagree, fix the documentation in the same
   change.** A stale doc is a defect, tracked like any other.
6. **Warn, do not imply.** If something is unverified, say so in the sentence
   that describes it.

## Verification Commands

```powershell
& 'D:\Anaconda\envs\OCRLLM\python.exe' -m pytest -q -p no:cacheprovider
& 'D:\Anaconda\envs\OCRLLM\python.exe' -m compileall -q src tests
```

Import-weight check:

```powershell
& 'D:\Anaconda\envs\OCRLLM\python.exe' -c "import sys,time; t=time.perf_counter(); import ocrllm; print(round(time.perf_counter()-t,4), len(sys.modules), [m for m in ('PIL','openai','httpx','onnxruntime') if m in sys.modules])"
```

Credentials for live work are stored by the legacy GUI under
`HKCU\Software\OCRLLM\QCR\ui`. Read them from the registry; never hardcode a key
and never print one. Do not run a paid gate without an explicit budget from the
maintainer.
