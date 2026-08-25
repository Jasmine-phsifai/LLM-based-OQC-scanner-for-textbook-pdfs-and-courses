# Plan: Phase 1 Maturation, Then Phase 2 MP3 Audio

> **Status boundary, 2026-08-23:** this detailed plan is retained for evidence,
> alternatives, and completed Stage M history. Stage M is offline
> implementation-complete. Any ordering or provider direction that conflicts
> with `#065 Unified Execution Queue` in `ACTIVE_STATE_AND_RULES.md` is
> superseded. The #066 transport audit proved that the legacy built-in Google
> path is native `google-genai`; current execution follows that native image
> path, with public short audio and bounded live proof early. A possible Google
> compatibility transport and the future local-compatible path are separate,
> later work. The authority queue, not this historical sequence, controls
> current work.

Status: **retained detailed plan; Stage M offline implementation complete, paid
live exit gate open; Stage A1 local MP3 snapshot/probe implemented; current
ordering is authority #065.** Updated 2026-08-23.

Read `docs/ACTIVE_STATE_AND_RULES.md` first. It defines document precedence, the
two policy changes this plan depends on, and the coding rules.

## Relationship To Other Work

```text
Defect repair D1-D7    docs/plan_phase1_defects_and_provider_split.md, Stage 1.
                       CLOSED 2026-08-18. Do not duplicate.
Phase 1 maturation     This document, Stage M. Offline implementation complete;
                       paid live exit smoke remains open.
Phase 2 mp3 audio      This document, Stage A1/A2. A1 snapshot/probe implemented;
                       recognition remains in progress. A2 not started.
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

**In progress. The provider-independent A1 local MP3 snapshot/probe seam is
implemented; audio configuration, provider call, response mapping, persistence,
and the public facade are not. The Stage 2 audio configuration boundary lands
with the rest of A1, not as unused scaffolding. A1 does not wait on Stage M's
independent paid image smoke; its own live gate remains separately budgeted.**
The final budget sentence is superseded by authority #065: bounded Google
image/audio live work is pre-authorized, while paid DashScope remains budgeted.

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
- The local snapshot ceiling is 25 MiB as a resource bound, not a claim about
  any provider. Copy from one opened regular-file handle to fixed `source.mp3`,
  reject size change during the copy, flush and fsync before probing, and own
  cleanup for the entire future provider call. The selected adapter separately
  preflights its exact encoded request envelope.
- Validate MP3 structure before any provider call. A zero-byte, wrong-format,
  malformed, zero-decoded-frame, or detectably incomplete file fails before
  money is spent. Do not claim universal truncation detection: an MP3 cut on a
  valid frame boundary without Xing/VBRI or an external expected length is also
  a valid shorter MP3 and cannot be distinguished locally.
- The first executable probe uses lazy `miniaudio>=1.71,<2` under `[audio]`.
  It consumes MP3-specific metadata on the immutable snapshot, then fully
  exhausts the MP3 stream while discarding PCM chunks and counting decoded
  frames. The selected decoder reports exact frame equality for the committed
  valid CBR, VBR, and ID3 fixtures, so any reported/decoded mismatch is rejected.
  The provider duration boundary is enforced on decoded duration; the probe
  never silently switches protocols.
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
  identity while the snapshot context is still open, then clean the snapshot
  and publish Markdown. A cleanup failure must leave paid work recoverable from
  that state rather than falsely report final success. `resume=True` may reuse
  the exact result with zero provider calls. A1 has no chunks, segments, task
  IDs, or partial-transcript recovery.
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

### Stage A2 — Provider-specific long MP3

- #150 supersedes FileTrans-first ordering. #151 implements and live-proves A2a
  with one 307.98-second input. A2a is one standalone native Google
  Files lifecycle for one local MP3 longer than A1's 300-second ceiling: discover
  the current catalog, upload once, wait within a bound, generate once, delete
  the remote file during cleanup, and close the client. Prove it with one
  bounded authorized live request before adding chunking or video integration.
- A2a has no chunking, resume, parallel splitting, model switching, fallback,
  shared provider base class, or video orchestration. A failed or refused
  transcription is never presented as a transcript, and cleanup failure must
  not hide the primary result or error.
- A2b may add the smallest evidence-driven Google chunk/checkpoint route after
  A2a succeeds. Duration remains the routing input toward the private ten-hour
  product ceiling, subject to current provider size and duration limits.
- #152 selects Route B: A2a remains the explicit one-shot operation and the
  recoverable route uses fixed ordered intervals for every persisted long-MP3
  run. Interval length is caller-configured as an exact positive integer number
  of minutes; no fractional, adaptive, provider-selected threshold is accepted.
- #208/#304 narrow that contract further: resume depends on the caller's
  original MP3 remaining present with a strong matching identity, so the
  library does not retain another potentially 2 GB source copy. Each interior
  logical interval receives a private fixed 30 seconds of context on each side,
  and the model is asked to return only the logical range. There is no public
  overlap option or programmatic transcript deduplication.
- #305 implements the pure exact-window planner. #312 implements one internal
  context-managed FFmpeg materialization from one already-owned MP3 and one
  planned window. It re-encodes mono 16 kHz / 64 kbps to disk and removes the
  temporary segment after use. Serial provider dispatch, source/request/window
  state identity, per-paid-result persistence, final assembly, and repair remain
  later independent slices.
- #313 computes the strong source SHA-256 while the existing bounded snapshot
  copy is already streaming the original MP3. Short, long, and video-selected
  snapshot facts retain that digest without another source read. Use it with
  the original resolved URI and byte size in the future A2b request identity;
  do not publish it as result metadata or treat it alone as a complete state.
  Exact clean commit `b9ae0c9` passes every installed profile and both maintained
  media smokes without a provider call; the shipped wheel is 259,949 bytes.
- #314 fixes the output-affecting interval prompt before request fingerprinting.
  `audio.long.interval.v1` states actual original-source bounds, the uploaded
  clip's zero-time anchor, the logical original-source bounds, and their
  clip-relative offsets. It asks for only logical-range Markdown and no legacy
  markers/timestamps. Hash this version in the next request-identity slice;
  do not combine that work with persistence or provider dispatch.
  Exact clean commit `5047a00` passes every installed profile and media smoke;
  its 261,349-byte wheel leaves 795 bytes under the maintained ceiling. Audit
  the existing distributable for justified reduction before adding identity
  runtime files, without weakening one-file/one-responsibility structure.
- #315 completes that reduction audit. Runtime modules are intentional; the
  only justified removal from the wheel is the non-runtime detailed package
  README, which remains in Git/sdist while standard METADATA retains the root
  README. The measured worktree wheel falls from 261,349 to 247,533 bytes.
  Exact clean commit `4c9e31b` passes every installed profile and media smoke
  without cloud I/O. Request identity is unblocked as the next atomic slice.
- The A2a 9.5-hour duration check is not complete selected-model preflight:
  Google's documented 32 audio tokens per second makes the full duration
  1,094,400 audio tokens before the prompt, above the current documented
  1,048,576 input limit of the live-proven `gemini-2.5-flash`. SDK model-list
  rows expose optional `input_token_limit`, but the active name-only parser
  discards it. Specify a narrow model-aware rule separately; do not hide this
  gap with a hardcoded model table, guessed prompt reserve, or automatic chunk
  policy.
- #209 adds the narrow model-aware rule that needs no guessed reserve: consume
  the existing catalog pager once and reject before upload only when
  `ceil(decoded_seconds * 32)` already meets or exceeds the selected row's
  advertised positive input limit. Missing optional metadata preserves the
  current provider path; malformed selected metadata is a typed provider
  response failure. Do not reinterpret this audio-only rejection as proof that
  every smaller audio-plus-prompt request fits.
- #210 live-confirms the current endpoint supplies that optional field for the
  explicit live-proven `gemini-2.5-flash` row. One catalog-only operation found
  50 current models and a positive-integer input limit, then closed the client;
  it made no Files, generation, token-count, model-get, retry, or fallback call.
  Keep this as transport evidence, not a hardcoded catalog snapshot or a claim
  that every catalog model accepts audio.
- #211 closes the separate video source-lifecycle blocker: the library streams
  one hidden request-owned MP4 under `output_dir`, and the full frame plus audio
  parse consumes that path before cleanup. Keep A2b audio state independent;
  do not reuse the transient video snapshot as a persistent resume source.
- A2b uses its own versioned audio state and a strong source/request/segment
  identity. It may reuse generic fingerprint and atomic-write behavior, but it
  must not generalize or import image slot semantics. The first slice remains
  serial and owns one complete upload/generate/delete lifecycle per missing
  segment.
- DashScope FileTrans remains a later independent provider path. When it is
  implemented, add its explicit long-model identity, persist its task ID and
  strong source/request identity before polling, and resume a matching task
  without resubmission. Do not copy the legacy stat-only fingerprint,
  deterministic temporary name, localized recovery regex, or automatic
  protocol fallback.
- #316 implements only the audio request-identity prerequisite. The canonical
  digest binds source content, whole/interval mode, provider/model, the relevant
  prompt version, and every exact interval coordinate/index. It contains no
  secret or path and adds no state or provider work. The next slice may define
  the minimum audio-owned partial state consumed by serial persistence; do not
  import image slot types or combine state, dispatch, resume, and repair at once.

### Stage A exit gate

- A1 and each A2 provider slice have their own full-suite, import, capability,
  and live gates; A1 does not claim Files, FileTrans, or long-audio maturity.
- A1 offline fake-provider tests cover exact one-call routing, source snapshot
  and validation, typed response failures, cancellation, completed-result
  recovery, and output failure. A2a tests cover upload/readiness/generation,
  remote cleanup, typed failures, and cancellation before remote work. Later
  A2b tests cover segment ordering and incremental recovery.
- A1 probe integration tests use committed synthetic CBR, VBR, and ID3-tagged
  MP3 fixtures plus empty, deterministic random, one-frame, incomplete-tail, and
  corrupted-middle cases. Their manifest pins hashes and expected decoded frame
  counts. A developer-only generator accepts an explicit FFmpeg path; ordinary
  tests and the installed package never invoke FFmpeg. Five-minute and request-
  size boundaries are unit-tested from probe results rather than by committing
  large media files.
- `import ocrllm` weight unchanged; audio dependencies lazy behind an extra.
- A1: one bounded real short MP3 transcribed end to end.
- A2a completed by #151: one bounded real MP3 longer than 300 seconds, with one
  upload, one generation, verified remote deletion, and client cleanup. A2b separately proves interrupted
  work can resume without replaying settled provider calls.
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
