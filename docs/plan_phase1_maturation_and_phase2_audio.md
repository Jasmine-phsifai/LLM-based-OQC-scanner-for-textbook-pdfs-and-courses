# Plan: Phase 1 Maturation, Then Phase 2 MP3 Audio

Status: **approved current work; Stage M offline implementation complete, live
exit gate open.** Updated 2026-08-22.

Read `docs/ACTIVE_STATE_AND_RULES.md` first. It defines document precedence, the
two policy changes this plan depends on, and the coding rules.

## Relationship To Other Work

```text
Defect repair D1-D7    docs/plan_phase1_defects_and_provider_split.md, Stage 1.
                       CLOSED 2026-08-18. Do not duplicate.
Phase 1 maturation     This document, Stage M. Offline implementation complete;
                       paid live exit smoke remains open.
Phase 2 mp3 audio      This document, Stage A1/A2. Not started. Plan only.
Audio config boundary docs/plan_phase1_defects_and_provider_split.md, Stage 2.
                       Lands with the first executable Stage A1 slice.
```

Stage M and the defect repair touch adjacent code. The boundary is:

| Concern | Owner |
|---|---|
| Refusal detection (D1) | Defect agent |
| Wall-clock bound on a provider call (D2) | Defect agent |
| Preserving completed results when a batch raises (D3) | Defect agent |
| Resume accepting injected providers (D4) | Defect agent |
| Model discovery replacing the fixed allowlist | Stage M |
| Incremental flowed output written as work completes | Stage M |
| Automatic disclosed model-switching recovery | Stage M |
| Freezing `worker/` and `contracts/` | Stage M |

Stage M assumes D1-D4 have landed. They have landed, and the residual D4
intra-request checkpoint limitation closed with slot-indexed state persistence
and resume identity v2.

## Why Phase 1 Is Reopened

Phase 1 reached GO as a feasibility trial: prove one narrow vertical slice can
carry a stable public contract. It did. But several of its constraints exist
only because it was a trial, and they are unacceptable in a product:

- **A hardcoded three-model allowlist.** The account serves 239 models. A model
  becomes unusable because a constant in this repository is stale, not because
  the provider stopped serving it.
- **All-or-nothing output.** A recognition either completes and writes, or
  produces nothing. Long runs discard paid work on interruption.
- **One attempt, no recovery.** A free-tier provider exhausts quota per model.
  The library returns an error and every caller reimplements the same loop.

None of these are design errors. They were correct for a trial and are wrong for
a product. Removing them is the maturation work.

## Stage M — Phase 1 Maturation

### M1. Model discovery replaces the fixed allowlist

Retire the `SUPPORTED_DASHSCOPE_MODELS` frozenset as a gate on caller choice.
See "Policy Change: Model Discovery Replaces The Fixed Allowlist" in
`docs/ACTIVE_STATE_AND_RULES.md` for the reasoning and the constraint that
survives.

Required behavior:

- Fetch the provider's served-model catalog from its own API. For DashScope
  this is `GET {base_url}/models`, verified working against the live account and
  returning 239 entries.
- Validate a caller's model against the live catalog. Unknown means "the
  provider does not serve this", not "this repository has not heard of it".
- Cache successful catalogs for 600 seconds. Discovery must not add a network
  round trip to every recognition; an expired successful catalog remains usable
  during a refresh outage.
- Discovery must be lazy and must never run during plain `import ocrllm`.
- A first catalog failure must fail closed with retryable
  `PROVIDER_CATALOG_UNAVAILABLE`; do not send an unverified model to a paid
  provider call when the catalog is unavailable.
- Keep the evidence baseline pinned and named in result metadata. A model
  outside the baseline is usable and must be reported as unproven.

`get_capabilities()` must not claim proven quality for a discovered model.

### M2. Flowed output and true resume

This is the highest-value item in Stage M. Today a recognition writes its result
once, at the end. Interrupt it and the paid work is gone.

Required behavior:

- Results are written incrementally as each unit completes, in caller order,
  not accumulated until the end.
- A run interrupted at any point leaves the completed units on disk in a form
  the next run can reuse.
- Resume is available two ways:
  - **Manual:** the caller passes `resume=True` and the run continues from
    whatever is already on disk.
  - **Automatic:** an interrupted or partially failed run preserves completed
    units without the caller having asked in advance. Preservation is not
    opt-in. Discarding paid work is never the default.
- Order is preserved regardless of completion order.
- Writes stay atomic. A crash mid-write must not leave a corrupt file. Legacy
  already learned this the hard way; see the atomic-write entries in
  `legacy_app/AGENTS.md`.

**Behavior oracle:** `legacy_app/OCRLLM/core/incremental_writer.py`, class
`IncrementalMDWriter`. Port the behavior statement, never the file. The parts
that matter:

- Slot-indexed writes (`write_slot`) so parallel completion still yields ordered
  output.
- `seed_slots()` to restore already-completed slots before resuming, with
  `truncate=not bool(restored_slots)` so a resume does not blank the file.
- Contiguous incremental flush: only append the run of slots that is complete
  from the front, keeping the file valid at every instant.
- A dirty flag so that if an incremental append fails, finalize rewrites in
  full rather than leaving a half-written file.

**Known legacy defect not to inherit:** the legacy PDF path seeds slots on
resume; the legacy video path did not, which made phase-4 resume
phase-granular and discarded batch work on a late crash. Both are recorded in
`legacy_app/AGENTS.md`. Seed slots on every path.

### M3. Disclosed automatic recovery with model switching

Implementation status: offline complete. The paid live exit smoke must still
verify current provider-account behavior.

See "Policy Change: Disclosed Automatic Recovery" in
`docs/ACTIVE_STATE_AND_RULES.md`. All four conditions there are binding: opt-in,
disclosed, disposition-gated, bounded.

Required behavior:

- The caller supplies an ordered candidate model list. Their primary model is
  tried first and is never tried twice.
- On an approved error whose disposition is explicitly model-scoped, advance to
  the next candidate. Account-, credential-, provider-, and request-scoped
  failures stop and raise even when their error code is otherwise recoverable.
- DashScope codes `AllocationQuota.FreeTierOnly`, `CommodityNotPurchased`, and
  `FreeQuotaExceeded` are mapped to model scope, so sibling candidates remain
  eligible; account suspension remains account-scoped. This is proven offline
  against mapper and credential-pool tests, not re-proven against the live
  account. The paid exit smoke must verify the provider still behaves this way.
- When every candidate is exhausted, raise a distinct terminating error naming
  the last model tried.
- Every attempt is recorded in an ordered ledger exposed in result metadata and
  in error details.

**Behavior oracle:** `legacy_app/OCRLLM/core/llm_client.py`,
`_vision_fallback_chain`, `_call_with_free_tier_fallback`,
`_notify_free_tier_switch`. Legacy already orders the primary first, slides only
on free-tier exhaustion, notifies on every switch, and raises an
all-exhausted error. The user-configured queue is stored as
`vision_model_queue` in the legacy GUI settings.

Recovery must compose with M2: a switch mid-run must not discard units already
recognized by the previous model. Record which model produced each unit.

### M4. Freeze `worker/` and `contracts/`

Closed to change. No new fields, commands, events, protocol version bumps, or
tests. If a Stage M change makes a frozen contract inaccurate, record the
divergence in `docs/ACTIVE_STATE_AND_RULES.md` and move on.

Known divergences to expect: `image_recognition_request.py` pins
`provider: Literal["dashscope"]` and `profile: Literal["board"]`, and its
`model` field assumes a single fixed model rather than a candidate list.

### M5. Cut process overhead

The documentation rules in `docs/ACTIVE_STATE_AND_RULES.md` apply. Concretely:

- No per-slice decision file plus checkpoint file. One entry in
  `ACTIVE_STATE_AND_RULES.md`, plus one dated record only if a paid gate ran.
- No new `phase*` document.
- Group trivially small pure helpers with their only caller rather than adding
  more single-predicate files.

### Stage M exit gate

- Full suite green, with failing-first tests for M1, M2, M3.
- Import weight unchanged: under 150 ms, no heavy module in `sys.modules` after
  plain `import ocrllm`.
- A recognition interrupted mid-run leaves completed units on disk, and a
  resumed run does not re-pay for them. Proven by a test that kills work
  mid-flight, not by inspection.
- A caller can select a model the repository has never heard of, and it works.
- A caller-configured candidate chain survives a simulated per-model quota
  exhaustion and reports every attempt.
- `worker/` and `contracts/` unchanged in the diff.
- One live smoke, budget approved in advance, proving the DashScope path still
  works end to end.

## Google Image Follow-on — Built-in Adapter

**Investigated 2026-08-23. Plan only. Do not implement before Stage M exits.
This does not block Stage A.**

### Decision and boundary

Two implementation paths were compared:

1. Add `GoogleSettings` beside the current single `Config.provider` field now.
   This looks small but would also require special cases in configuration
   normalization, DashScope-only scout behavior and evidence metadata,
   capability reporting, and image resume identity.
2. Add the Google image adapter through an explicit vision-provider resolver
   without redesigning audio or replacing the proven image configuration.

Choose path 2 after its exact resolver design is proven by failing tests. It
avoids an unrelated audio abstraction and keeps one owner for
candidate routing, request pacing, checkpointing, attempt disclosure, refusal
detection, and Markdown validation. The Google adapter translates one SDK call
and its failures; it must not copy legacy `GoogleProviderClient` or introduce a
second retry/model-switch loop.

Explicitly out of scope: Google audio and Files API, text chat, contextual chat
history, GUI/QSettings, provider priority toggles, credential pools, persistent
"last successful model" routing, video policy, and every social workflow.

### Smallest useful slice

- Add immutable, secret-redacted Google provider settings and a separate
  optional `google` dependency extra. Load the official `google-genai` SDK only
  inside the adapter; plain `import ocrllm` and capability inspection remain
  lightweight.
- Discover models lazily with the provider's `models.list()` API and a bounded
  timeout. Accept only catalog entries that advertise `generateContent` and
  normalize the `models/` prefix. Catalog presence makes a model selectable,
  not quality-proven or necessarily free. Do not hardcode the legacy model
  names or assume every catalog entry has free quota.
- Build one ordered inline-image request from the active library's already
  validated snapshot paths, append the prompt, make one synchronous
  `generate_content` call, and close the client. Use the SDK transport timeout;
  cancellation remains pre-dispatch because the synchronous call cannot be
  interrupted honestly.
- Parse top-level response text and the documented candidate/content/part text
  fallback. Empty, missing, blocked, truncated, JSON-error-shaped, or otherwise
  invalid output is a typed failure and still passes through the common
  provider-Markdown validator.
- Map Google failures into the existing public error vocabulary with safe
  provider/model details and a truthful `failure_scope`. The established exact
  quota wording (`You exceeded your current quota ... check your plan and
  billing details`) is distinct from generic 429/`RESOURCE_EXHAUSTED`; explicit
  RPM/TPM/RPD/rate markers take precedence. Do not copy DashScope-only
  `FreeTierOnly` or `FreeAllocationQuotaExceeded` markers. Actual payment or
  billing failure must not be mislabeled as quota merely to reuse candidate
  switching. Before implementation, decide whether the existing account-stopped
  error is honest for that observed state; if it is not, add one narrow billing
  error rather than distorting an existing code.
- Give the built-in adapter a stable, secret-free resume identity containing
  provider name, model, prompt versions, and output-affecting Google settings.
  Bump the image request identity version if its canonical document changes;
  never silently reinterpret v2 state.
- Report Google separately in capabilities and result metadata. A catalog-only
  adapter is experimental; only the bounded live gate below can support a live
  availability claim, and it does not establish board-prompt quality.

### Verification sequence

1. Failing-first offline tests for exact settings types, immutability, secret
   redaction, missing/incompatible SDK, lazy imports, resolver selection, ordered
   image/MIME request construction, timeout conversion, client cleanup, response
   parsing, and redacted error mapping.
2. Reuse the existing candidate and checkpoint tests with Google-shaped fake
   SDK responses. Prove that eligible model-scoped failures advance the
   caller's explicit queue while window rate limits, generic 5xx/503 overload,
   invalid responses, empty output, safety blocks, and refusals do not. Google
   image handling starts with one transport attempt; any later retry belongs to
   an explicit shared execution policy, not a hidden adapter loop. Prove attempt
   disclosure and zero-call resume without putting retry policy in the adapter.
3. Prove Google and DashScope have distinct secret-free fingerprints and that
   model/output-setting changes invalidate reuse. Run the full suite and import
   weight gate without loading Google, OpenAI, Pillow, or network clients during
   plain import.
4. Use the maintainer's standing Google authorization for one
   bounded live catalog fetch and one small authorized image request against a
   catalog-served image-capable model. Preserve real outcomes for window quota,
   overload, API error, empty reply, unsupported format, and excessive image
   count; add only narrow mappings or local limits supported by that evidence.

Legacy offline evidence currently proves catalog filtering and the narrow
quota/rate distinction, but not Google image-count or unsupported-format limits.
Those are live-test targets, not reasons to invent provider limits in advance.

## Stage A — Phase 2: MP3-Only Audio Recognizer

**Not started. Boundary-audited for offline implementation. The Stage 2 audio
configuration boundary lands with A1, not as unused scaffolding. A1 does not
wait on Stage M's independent paid image smoke; its own live gate remains
separately budgeted.**

Phase 2's original framing was an Electron JSONL worker. That is superseded:
the worker is frozen and Phase 2 is redefined as the first audio capability.

### Scope

One media type, one container: **mp3 in, Markdown transcript out.** Nothing
else.

Explicitly out of scope: wav, m4a, flac, video, ffmpeg-based conversion,
speaker diarization, real-time streaming, and hotword feedback loops. Each of
those is a later gate. The value of this stage is proving the audio contract on
the narrowest possible surface, exactly as Phase 1 proved the image contract.

### Prerequisites

- Reuse Stage M's proven source snapshot, redaction, atomic output, cancellation,
  and typed completed-result state patterns. A1 has one synchronous result, so
  it does not need chunk/segment flow or provider-task state. A2 does.
- The audio configuration boundary from
  `docs/plan_phase1_defects_and_provider_split.md` Stage 2 lands in A1. Audio
  must use a provider, credential, and model independently of vision. The
  maintainer already runs it this way: FileTrans uses
  `qwen3-asr-flash-filetrans` on DashScope while vision may use another
  provider.

### Provider note

The provisional first built-in adapter is DashScope short ASR because it is the
current migration boundary and its documented Qwen3 short path uses the already
required OpenAI-compatible client. Current official documentation says that
path accepts one MP3 as Base64 input, up to five minutes, with a final encoded
request limit of 10 MB (see the official
[speech-model guide](https://help.aliyun.com/en/model-studio/asr-model/) and
[Qwen ASR API reference](https://help.aliyun.com/en/model-studio/qwen-asr-api-reference)).
Treat those as live-gate facts to reverify, not permanent library constants. Do
not add the native DashScope SDK or a second protocol to A1. Google audio remains
a separately selected provider slice and an authorized robustness source; it is
not an implicit fallback.

Long audio uses a submit/poll/download task flow rather than a single synchronous
call. `docs/ocrllm_library_go_no_go.md` already reserves
`providers/dashscope/submit_filetrans.py`, `poll_filetrans.py`, and
`download_filetrans_result.py` for this. Legacy behavior and its failure history
are recorded in `docs/legacy_filetrans_codex_debug_record.md`.

### Stage A1 — Short MP3, First Executable Audio Slice

- Add and immediately consume one exact immutable audio binding containing the
  audio provider and short-ASR model identity. Prefer
  `Config.short_audio: ShortAudioSettings | None`, where the settings hold the
  provider and explicit model. Do not rewrite the image fields or let an
  injected provider hide the model identity.
- Accept exactly one local MP3 path. Reject sequences and URLs. Snapshot its
  bytes before validation or dispatch and use compact internal temporary names
  so a long Windows destination path is not repeated at every atomic-write step.
- Validate MP3 structure before any provider call. A zero-byte, wrong-format,
  malformed, zero-decoded-frame, or detectably incomplete file fails before
  money is spent. Do not claim universal truncation detection: an MP3 cut on a
  valid frame boundary without Xing/VBRI or an external expected length is also
  a valid shorter MP3 and cannot be distinguished locally.
- The first executable probe adds lazy `miniaudio>=1.71,<2` under `[audio]` and
  consumes it immediately. Use MP3-specific metadata on the immutable snapshot,
  then fully exhaust the MP3 stream while discarding PCM chunks and counting
  decoded frames. Reject a material advertised/decoded duration mismatch outside
  a fixture-proven MPEG-frame/encoder-padding tolerance. Enforce the provider
  duration boundary on decoded duration and never silently switch protocols.
- Do not require or bundle FFmpeg for A1. The tested `imageio-ffmpeg` Windows
  binary is about 87.6 MB and GPLv3-configured, while no system FFmpeg exists on
  the target machine; full FFmpeg decode also accepts clean EOF truncation. Keep
  it only as explicit developer fixture-generation/reference tooling. Mutagen is
  metadata-only and GPL-2.0-or-later; PyAV is a much broader FFmpeg distribution;
  neither belongs in the A1 runtime.
- Make one synchronous short-ASR protocol explicit in the adapter. Do not copy
  legacy's hidden SDK-to-OpenAI-compatible fallback or derive models from name
  substrings. Preflight the final Base64 request envelope rather than copying
  legacy's raw-byte threshold.
- Empty, refused, or no-speech responses are typed failures;
  `NoSpeechDetected` already exists for the last case. A provider failure must
  not be written as transcript prose or returned as a successful output path.
- When `output_dir` is present, atomically persist one typed completed-result
  record, bound to exact source bytes and request/protocol/provider/model
  identity, before publishing Markdown. `resume=True` may reuse that exact
  result with zero provider calls. A1 has no chunks, segments, task IDs, or
  partial-transcript recovery.
- Keep miniaudio imported only inside the executable probe. `[audio]` contains
  the MP3 probe dependency; provider clients remain in provider-specific extras.
  Plain `import ocrllm` remains lightweight.
- Do not add hotwords in A1: the selected short protocol has not proven that
  legacy behavior. Do not add automatic retries, candidate models, or provider
  fallback.
- Change only `provider.dashscope.audio-short` and
  `audio.short.mp3-mpeg-layer3` capability statuses when their executable and
  live gates pass. All long-audio, FileTrans, WAV, M4A, and video entries remain
  deferred.

### Stage A2 — Resumable Long MP3 / FileTrans

- Add the separate FileTrans model identity to the audio settings when this
  path consumes it. Short and long protocols remain explicit rather than
  inferred from model names.
- Submit, then atomically persist the provider task ID and strong source/request
  identity before polling. Resume must reuse a matching task without upload or
  resubmission.
- Transcript segments are written incrementally under M2. A long transcription
  that dies at 90% keeps 90%.
- A failed or refused transcription is never presented as a transcript. This is
  D1's rule applied to audio, and legacy shipped exactly this bug.
- Do not copy the legacy stat-only task fingerprint, deterministic temporary
  name, localized Markdown recovery regex, or automatic protocol fallback.

### Stage A exit gate

- A1 and A2 each have their own full-suite, import, capability, and live gates;
  A1 does not claim FileTrans or long-audio maturity.
- A1 offline fake-provider tests cover exact one-call routing, source snapshot
  and validation, typed response failures, cancellation, completed-result
  recovery, and output failure. A2 tests cover provider-task resume, segment
  ordering, and incremental publication.
- A1 probe integration tests use committed synthetic CBR, VBR, and ID3-tagged
  MP3 fixtures plus empty, deterministic random, one-frame, incomplete-tail, and
  corrupted-middle cases. Their manifest pins hashes and expected decoded frame
  counts. A developer-only generator accepts an explicit FFmpeg path; ordinary
  tests and the installed package never invoke FFmpeg. Five-minute and request-
  size boundaries are unit-tested from probe results rather than by committing
  large media files.
- `import ocrllm` weight unchanged; audio dependencies lazy behind an extra.
- A1: one bounded real short MP3 transcribed end to end.
- A2: one bounded real long MP3 plus interrupted polling/resume without
  resubmission or repayment.
- Capability reporting changes atomically with the executable slice; video
  remains unavailable.

## Rules For Whoever Executes This

- Follow `docs/ACTIVE_STATE_AND_RULES.md`. Update it in place as items close.
- Write the failing test before the fix.
- Read credentials from `HKCU\Software\OCRLLM\QCR\ui`. Never hardcode or print a
  key. Never run a paid gate without an explicit budget from the maintainer.
- `legacy_app/` is the behavior oracle. Port behavior statements and fixtures;
  never copy a legacy file.
- Keep the working-diary rule in root `AGENTS.md`. Anything observed and not
  fixed still gets written down.
