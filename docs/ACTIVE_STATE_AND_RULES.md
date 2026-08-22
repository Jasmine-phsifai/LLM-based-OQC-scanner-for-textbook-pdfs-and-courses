# Active State And Rules

Status: **authoritative and current.** Last verified 2026-08-22 against the
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
finished. Stage M is **partially implemented**: model catalog discovery,
file-backed state sidecars, opt-in candidate queues, and slot-indexed
intra-request checkpoints shipped, but the attempt-ledger, recovery-policy,
credential-pool, evidence-label, and candidate-validation gaps remain open
below. Stage 2 vision/audio provider splitting and Stage A mp3 recognition have
not started. See `docs/plan_phase1_maturation_and_phase2_audio.md`.

## Known Debt In This Repository

Future agents must assume the following and verify before trusting any claim:

- **Fixture byte-reproduction is environment-bound (redesigned 2026-08-19).** The Phase 1 generated-image corpus can only be byte-reproduced in the exact Pillow wheel build that created it; that environment is lost and no installable 12.x build reproduces the pinned pixels. `tests/quality/generators/generate_phase1_fixtures.py` now checks three layers instead: manifest-hash integrity (every environment), same-environment determinism, and reproduction that is byte-strict only under the recorded `GENERATOR_ENVIRONMENT` and pixel-tolerant otherwise. Do not re-baseline the committed images without a maintainer decision: they are the pixels the v17 live evidence was scored against.

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

## Verified State, 2026-08-19

Confirmed by execution, not by reading prose. Method noted so it can be redone.

| Property | Result | Method |
|---|---|---|
| Test suite | 1030 passed, 0 skipped, 0 failed (114 s) | `D:\Anaconda\envs\OCRLLM\python.exe -m pytest -q -p no:cacheprovider` with empty `PYTHONPATH` |
| Import weight | 112 ms, 122 modules, no heavy module loaded (2026-08-22 single process; consistent with the 131 ms median / 222 ms max five-process probe of 2026-08-19) | timed plain import with `src` on `sys.path` |
| Heavy-module isolation | `PIL`, `openai`, `httpx`, `onnxruntime` all absent after plain import | `sys.modules` probe |
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
Stage M findings, G6, G7, and G9 are closed; G1 is partially addressed; G2,
G3, G4, G5, G8, and G10 remain open. Do not close an entry without a test that
fails before the fix.

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

### D3 — `recognize_batch` discards completed paid work on any failure. **High. Fixed 2026-08-18.**

**Signature change, taken deliberately.** `recognize_batch` now returns
`list[BatchItemOutcome]` instead of `list[RecognitionResult]`.
`BatchItemOutcome` carries `index` and exactly one of `result` or `error`, so a
caller reads successes and failures from the same ordered list.

Execution semantics are unchanged: bounded worker pool, caller order, fail-fast.
The first failure aborts the start gate and cancels pending futures; calls that
were already dispatched — and therefore already paid for — are drained and
settled, and every source that was never attempted gets a `Cancelled` outcome so
the returned list always matches the caller's source order.

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
3. **Disposition-gated.** Switching triggers only on dispositions that mean
   "this model or credential cannot serve the request" — quota exhausted,
   unavailable, permission denied. Never on a generic failure, never on
   `PROVIDER_RESPONSE_INVALID`, and never on a refusal.
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

Implementation status: the catalog path is shipped for names outside the
static set, but the static set still bypasses catalog validation. That is the
remaining discovery/evidence mismatch tracked by G5; the policy above is the
target behavior, not a claim that M1 has passed.

Relevant measurement: the `board.v17` prompt against `qwen3.5-ocr` produced 16
completion tokens and no usable output, while the pinned model produced a full
transcription from the same prompt and image. Prompt and model class are
coupled. Discovery makes a model *selectable*; it does not make it *proven*.

## Stage M Implementation Status, refreshed 2026-08-22

Stage M is **partially implemented**. The following behavior is shipped and
tested offline:

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
   caller order and currently advances on `PROVIDER_QUOTA_EXHAUSTED` only. The
   queue is bounded and its attempts are visible, but the ledger and terminal
   error contract are not complete; see G1, G2, and G4 below.

The Stage M exit gate has **not** passed. Full disposition-gated recovery,
model-aware credential scheduling, complete spend disclosure (the G1
remainder), and the live catalog/end-to-end smoke remain open. The
offline suite and import probe must be refreshed by command output before this
section's measured counts are changed. `worker/` and `contracts/` remain
unchanged and frozen.

### Current Open Stage M Findings

These are current implementation findings, not historical phase failures.
Their identifiers are stable so plans, tests, and future diary entries can
refer to the same issue.

#### G1 — Attempt ledger cannot reconstruct spend. **High. Partially addressed 2026-08-22; narrowed remainder open.**

`cd7429c` added `provider_calls_attempted` to every `model_attempts` ledger
entry (success or typed failure) and a `workflow_slots` disclosure in result
metadata. Still open: configuration failures (raised before any provider
dispatch, e.g. an invalid candidate name) are not entered in the attempt
ledger, so one failure class still leaves no spend record.

#### G2 — Recovery is quota-only. **Medium. Open.**

The candidate loop switches only for `PROVIDER_QUOTA_EXHAUSTED`, although the
approved recovery policy also permits model switching for the configured
unavailable and permission-denied dispositions.

#### G3 — Account blocks prevent eligible model candidates. **Medium. Open.**

The credential pool can record a quota or permission block at account scope.
That account-wide state prevents acquisition for the next candidate even when
the candidate-specific model may still be usable.

#### G4 — Chain exhaustion has the wrong public identity. **Medium. Open.**

`AllCandidatesExhausted` subclasses `QuotaExhausted` and therefore does not yet
give callers a distinct code/disposition for “the entire configured chain
ended” versus “one model exhausted.”

#### G5 — Proven-model metadata is too broad. **Medium. Open.**

The static supported-model set is still treated as evidence-backed metadata,
although the live quality evidence proves only the pinned model with the exact
v17 workflow. Selection and proof status must remain separate.

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
item). Proven by kill-mid-request tests in `tests/test_m2_slot_resume.py`.

#### G8 — Scout failures are attributed to the primary model. **Medium. Open.**

The omission-scout workflow uses a separate fixed scout model, but a scout
failure is raised through the primary candidate loop. Recovery can therefore
switch or retry the wrong model.

#### G10 — Candidate validation is weaker than primary validation. **Low. Open.**

Candidate names reject empty text but do not enforce the primary model field's
exact trimming and control-character rules.

#### G9 — Catalog outage fail-open. **Closed 2026-08-19.**

Commit `4c5293d` made first-fetch catalog failure retryable and fail closed,
while retaining the last successful catalog during refresh outages.

## Legacy Status, 2026-08-19

The legacy diary contains no currently open product bug. The recorded path,
refusal, atomic-write, partial-failure, PDF-render, resume-root, and checkpoint
cancellation defects are fixed and retained as trace in `legacy_app/AGENTS.md`.
The latest checkpoint-cancellation fix preserves generated outputs when a task
is dismissed; it does not delete paid Markdown implicitly. Any legacy issue
found or fixed in a later session still belongs in that diary before the
session closes.

## New And Fixed In This Working Update

These changes are current, verified, and should not be mistaken for open
defects:

- Legacy checkpoint cancellation is now non-destructive by default. Explicit
   output deletion remains available only through `delete_outputs=True`; the
   resume dialog calls the cancellation path and its PDF/audio/video regression
   tests pass.
- Legacy API/model settings are owned by `SettingsDialog`; model discovery and
   picker refresh work is kept off the GUI event loop where the path is
   asynchronous, and the stale main-window test assumptions were updated.
- The Phase 1 fixture checker now verifies manifest integrity, deterministic
   regeneration, and decoded-pixel equivalence when the rendering environment
   is not fully pinned. Its manifest/source pins and tests are synchronized.
- The active suite passed 1,030 tests with an empty `PYTHONPATH` on 2026-08-22;
   the focused legacy checkpoint/GUI suite passed 29 tests and the
   settings/model suite passed 12 tests with 1 environment skip. These counts
   are verification snapshots, not permanent gates for future changes.

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
  `provider_calls_attempted` details.

Regression coverage is `tests/test_m2_slot_resume.py`: a kill-mid-request
fake provider proves persisted slots survive a crash and that a resumed run
pays only for missing slots (including the sign-scout passes), a hand-written
v1 state proves the version-named rejection, a candidate-fallback run proves
failed-model slots are neither reused nor lost, and a prompt-version bump
proves resume identity invalidates. Offline gate: full suite, `compileall`
clean, plain import 117 ms / 122 modules with `PIL`, `openai`, `httpx`, and
`onnxruntime` absent. No paid live call was made. `worker/` and `contracts/`
are unchanged.

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
