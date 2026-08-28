# Plan: Provider Entity, Batch Engine, And Video Pipeline Decomposition

Status: **approved 2026-08-28; documentation aligned, implementation not started.**
This is the active authority for the next library iteration. Where older
documents conflict with the decisions below, this file wins and the older entry
carries an OBSOLETE marker pointing here. Read
[`ACTIVE_STATE_AND_RULES.md`](ACTIVE_STATE_AND_RULES.md) first for document
precedence and coding rules.

## Why This Refactor Exists

Three structural problems in the current `src/ocrllm` package:

1. The video pipeline is a black box. `recognize_video_to_markdown.py` hides
   inspect, frame extraction, frame deduplication, recognition, audio
   extraction, chunking, and composition inside one long function. A caller who
   already extracted frames or audio cannot enter mid-pipeline.
2. Video owns a dedicated resume layer. `video_job_state.py` and its seventeen
   sibling modules maintain a journal format that serves only video and
   duplicates the image and long-audio resume systems.
3. There is no first-class provider object. `Config.provider` holds one
   provider per call; there is no fallback chain, no multi-provider
   concurrency, and no retry loop anywhere (the DashScope client runs with
   `max_retries=0`).

Goals, in priority order (architecture, then maintainability, then
functionality; effort is explicitly not a constraint):

1. Expose the video pipeline as public step functions, with a thin orchestrator
   `recognize_video` for the full chain.
2. Introduce `ProviderEntity`: one entity is one (vendor, model) pair of pure
   frozen data. Recognition functions accept one entity, a flat list (ordered
   fallback chain), or a nested list (API pool with one thread per sub-list).
3. Delete the video-specific resume layer. Video resume routes to image-batch
   resume plus audio-batch resume on the same Markdown file.

Frozen prior decisions remain in force: no social-media crawling anywhere in
scope; `repair` stays experimental with no production logic (it assumes a
Markdown failure record equals one ocrllm recognition failure and only covers
lost resume records or intermediates); Electron frontends call this library
only through a Python/Rust backend, never directly.

## Locked Decisions

- **D1, pool dead sub-list.** When every provider inside one sub-list of a
  nested provider list is exhausted, that sub-list's remaining assigned batches
  are recorded failed (batch range, last provider, last error code,
  description). They never spill over to other sub-lists. The global run
  continues; failed slots stay visible in the Markdown and are resumable later.
- **D2, retry policy keyed on canonical error codes.** `retry_policy` maps the
  library's canonical codes (`PROVIDER_RATE_LIMITED`, …, from `errors.py`) to
  `(strategy, extra_retries, wait_seconds)`. Raw HTTP status codes stay in
  error `details` for the final accumulated report. The existing
  `map_dashscope_error.py` / `map_google_genai_error.py` modules already
  produce canonical codes and are reused unchanged.
- **D3, default batch size.** When `batch_size` is not passed, it resolves once
  per run to `min(default_image_batch_size)` across the flattened provider
  list. Failover never re-chunks; re-chunking would destroy slot identity and
  resume.
- **D4, naming.** The merged-output functions are
  `recognize_images_to_markdown` and `recognize_audio_to_markdown`.
  `recognize_batch` keeps its one-Markdown-per-image semantics.
- **D5, intermediate file lifecycle.** Only files the `recognize_video`
  orchestrator extracts from a video input are owned intermediates: deleted
  after successful completion, kept on failure (resume needs them).
  `keep_intermediates=True` disables deletion even on success. Files the caller
  extracted and passed into `dedupe_video_frames` or
  `recognize_*_to_markdown` are never deleted. Ownership is recorded at
  creation time through the existing owned-media fingerprint mechanism, never
  inferred from paths. Sidecars are state, not intermediates: they are kept
  after success so repeat calls skip already-paid work, matching the image
  resume convention.
- **D6, separate provider arguments.** The orchestrator takes
  `image_providers` and `audio_providers` as two independent arguments.

### Retry policy semantics

`retry_policy: dict[canonical_code, (strategy, extra_retries, wait_seconds)]`
with `strategy` in `{"error", "next", "current"}`:

- `"error"` (request-invalid class, e.g. `PROVIDER_REQUEST_INVALID:
  ("error", 1, 1)`): retry on the same provider up to `extra_retries` times
  with `wait_seconds` between attempts; on overflow record a
  `ProviderFailureRecord` at error severity and advance.
- `"next"` (authentication/permission/quota class, e.g. `("next", 1, 1)`):
  retry up to the bound; on overflow record a `ProviderFailureRecord` at info
  severity and advance.
- `"current"` (stay-and-back-off class, e.g. `PROVIDER_RATE_LIMITED:
  ("current", 6, 10)`, `PROVIDER_CONCURRENCY_LIMITED: ("current", 10, 30)`,
  `PROVIDER_UNAVAILABLE: ("current", 10, 10)`): back off in place up to the
  bound; on overflow record a `ProviderFailureRecord` at info severity and
  advance.
- Every strategy records a `ProviderFailureRecord` on overflow: each provider
  keeps its own last-overflow code plus description. The strategies differ only
  in retry behavior and final-report severity.
- Unknown codes fall back to a safe `("next", 0, 0)` default; no policy ever
  spins indefinitely. Construction validates strategy membership and bounds
  (`0 <= extra_retries <= 32`, `0 <= wait_seconds <= 600`).
- Policies are per-vendor module-level presets (`GOOGLE_RETRY_POLICY`,
  `DASHSCOPE_RETRY_POLICY`). Entities reference a preset by default and may
  override per model; the dict is never copied into every prefab.

### Error accumulation and terminal states

- `ProviderFailureRecord(vendor, model_id, last_code, last_http_status,
  description, attempts, severity)`: one per overflowed provider.
- `BatchFailureRecord(batch_range, last_provider, last_code, description)`:
  one per failed batch.
- Terminal states: (a) all batches settled with some providers overflowed —
  `status="complete"`, records ride on `RecognitionResult.warnings`; (b) some
  batches failed — `status="partial"`, the Markdown is published with failed
  markers, records in warnings/metadata; (c) everything failed — raise the
  existing `AllCandidatesExhausted` carrying both record lists. One failed
  batch never aborts the run. The final report distinguishes "recognition
  completed but some providers never worked" from "no provider completed the
  work".

### Capability model

Entity capability flags: `supports_plain_ocr` (ordinary OCR, no thinking or
caller prompt required), `supports_detail_ocr` (LaTeX-formula-capable
unconventional OCR), `supports_audio`. Constructor invariant:
`supports_detail_ocr=True` with `supports_plain_ocr=False` raises `ValueError`.
New error class `ProviderCapabilityMismatch(OCRLLMError)`, code
`PROVIDER_CAPABILITY_MISMATCH` (registered in `STABLE_ERROR_CODES`), not a
`ProviderError` subclass: it means the caller passed an incapable provider, so
it aborts immediately, never retries, never accumulates, and names the missing
capability. `recognize_images_to_markdown(..., detail=False)` requires
`supports_plain_ocr`; `detail=True` requires `supports_detail_ocr`; audio
functions require `supports_audio`.

### Invocation model

Entities are pure frozen data and never hold callables or secrets. Executable
code lives in an adapter registry `ADAPTERS: dict[str, ProviderAdapter]` keyed
by `entity.adapter`: `"dashscope_openai"`, `"google_genai"`,
`"openai_compatible"` (registry slot only now; future vllm/ollama reuse it via
`base_url` with zero dedicated code), `"rapidocr_local"`. Adapters implement
`recognize_images` / `recognize_audio`, own every SDK quirk (including the
Google long-audio Files upload/poll/delete lifecycle), and run with SDK retries
disabled — retry is the engine's job.

Entity fields: `vendor`, `model_id`, `adapter`, `api_key_env`, `base_url`
(`None` means the vendor default endpoint), the three capability flags,
`default_image_batch_size` (`1` for non-thinking models),
`default_audio_minutes` (default 30, chosen from context size, stability, and
hard provider ceilings), `max_output_tokens`, `retry_policy`. Credentials are
resolved by the adapter from `api_key_env`; explicit overrides travel in
per-call `CallOptions`, never in the entity.

The prefab catalog (`providers/catalog/`) contains only models verified
against the live API. First families: the Gemini flash line and the Qwen-VL
line already in use. Function-interface rewrites begin only after the first
prefabs are live-verified.

### Concurrency and token accounting

Provider calls stay synchronous; pool mode runs one thread per sub-list
(`ThreadPoolExecutor`, `max_workers = number of sub-lists`). No asyncio. A
thread-safe `TokenLedger` per run accumulates input/output tokens by entity and
feeds the existing `metadata["current_model_token_usage"]` convention;
per-batch usage is also written into slot checkpoints as resume evidence. One
`ProviderRequestStartGate` per run is shared by all pool threads through the
existing ContextVar mechanism; a `Cancelled` in any thread aborts the gate, and
dispatched-but-unsettled work is settled before the pool exits. In-flight
synchronous SDK calls remain uninterruptible (existing documented limitation).

### Scope discipline

No full model catalogs; no dynamic pool rebalancing; minimal tests; the
`openai_compatible` adapter is a registry placeholder that raises a
not-implemented error until a real consumer lands. The entity engine performs
one recognition call per batch (single prompt, single pass); the multi-pass
board workflow (draft/review/scout) stays exclusive to the `Config` line and
is not ported. The DashScope credential pool stays a separate layer: entities
use one key per `api_key_env` in this iteration, and pool integration is
follow-up work that must reconcile double-backoff.

## Target Public API

```text
inspect_video(source) -> VideoInfo                                  # exists
extract_video_frames(source, *, output_dir=...)                     # exists
dedupe_video_frames(paths, ...) -> tuple[Path, ...]                 # new public wrapper
extract_video_audio(source, ...) -> Path                            # exists
chunk_audio(source, *, interval_minutes=None, provider=None)        # new

recognize_images_to_markdown(image_paths, *, providers, batch_size=None,
                             detail=False, output=None) -> RecognitionResult
recognize_audio_to_markdown(audio_paths, *, providers, output=None) -> RecognitionResult

resume_images_to_markdown(md_path, *, providers) -> RecognitionResult
resume_audio_to_markdown(md_path, *, providers) -> RecognitionResult
resume_video(md_path, *, image_providers, audio_providers) -> RecognitionResult

recognize_video(source, *, image_providers, audio_providers,
                image_batch_size=None, audio_interval_minutes=None,
                detail=False, output=None, keep_intermediates=False) -> RecognitionResult
```

- `providers` accepts `ProviderEntity | list[ProviderEntity] |
  list[list[ProviderEntity]]` and is required.
- `chunk_audio` requires at least one of `interval_minutes` / `provider`;
  `interval_minutes=-1` means no chunking; an explicit interval wins over
  `provider.default_audio_minutes`; provider duration limits are validated
  later at recognition time, not in `chunk_audio`.
- Default output locations: single image/audio → the source's own directory;
  batch images → the parent of the folder holding the images; batch audio →
  the parent of the folder holding the audio; video → the video's own
  directory (`<stem>.md`). `output` is always explicit-optional.
- Audio batching is one slot per chunk; there is no images-per-call batch size
  for audio.
- Video runs use a work directory `<stem>.ocrllm-work/` beside the Markdown
  holding `frames/`, audio chunks, and sidecars. Success without
  `keep_intermediates` deletes it; failure keeps it for resume. Caller-owned
  frames/audio never enter this directory.

### Breaking changes (to be recorded in release notes)

- `recognize_video_to_markdown` is removed.
- `recognize_video` changes signature (`image_config`/`audio_config` →
  `image_providers`/`audio_providers`), returns `RecognitionResult` instead of
  `VideoRecognitionOutcome`, and becomes resumable.
- `recognize`, `recognize_batch`, `recognize_long_mp3`,
  `recognize_video_frames` keep working unchanged.

## State And Resume Model

**Sidecar plan plus Markdown slot ledger.** No resume-from-Markdown exists
today; every durable path is sidecar JSON. The "Markdown is the checkpoint"
doctrine is satisfied by materializing every slot boundary and failure record
in the Markdown (the repair feature's input), while the sidecar remains the
verify-before-pay acceleration layer.

Sidecar (`<stem>.ocrllm-image-batch.json` / `<stem>.ocrllm-audio-batch.json`,
inside the work directory for video runs):

- Ordered request-fingerprint plan (one fingerprint per image batch / audio
  window). Resume requires a byte-identical plan, else
  `RESUME_STATE_MISMATCH` — mirroring `reuse_long_audio_partial_state`.
- The plan fingerprint excludes provider identity (sources, batch size, detail
  mode, prompt/profile version only). Resume may pass different providers —
  "change provider and resume" is a hard requirement. Settled slots are paid
  assets and are reused regardless.
- Index-aligned settled slots mirroring `LongAudioSettledSlot` (batch index,
  fingerprint, Markdown, sha256, provider, model, tokens, status, warnings).
- Per-sub-list rotation pointer (last successful provider index) so resume
  restarts each fallback chain where the run stopped.
- Run facts: `resolved_batch_size`, detail mode, audio interval; for
  orchestrator runs, the owned-intermediate fingerprints (D5).

Markdown markers (closed HTML comments, always emitted, parseable, strippable
by the existing `remove_closed_html_comments`):

```text
<!-- ocrllm:image-group index=3 status=done start=24 end=31 -->
<!-- ocrllm:image-group index=4 status=failed start=32 end=39 last_provider="dashscope" last_code="PROVIDER_QUOTA_EXHAUSTED" description="..." -->
<!-- ocrllm:audio-window index=5 status=done start=120.0 end=180.0 -->
<!-- ocrllm:region images start --> ... <!-- ocrllm:region images end -->
```

The video orchestrator writes image and audio batches into one Markdown; each
batch owns one `ocrllm:region`, and the rewrite helper replaces only the owning
region so `resume_video` can resume each branch independently on the same file.

Resume read order: (1) sidecar present and plan identical → verify input bytes
against fingerprints → compute missing slots (failed slots are retried per D1)
→ dispatch from persisted rotation pointers, no Markdown parsing; (2) sidecar
lost or unusable → `repair` (experimental, explicit): parse Markdown markers,
rebuild the failed-slot list, re-run failed slots with the caller's current
providers, rewrite the region. Repair performs no byte verification; that is
its documented limitation.

## Module Layout (new)

`providers/`: `entity.py`, `adapter.py`, `adapter_response.py`,
`call_options.py`, `registry.py`, `retry_policy.py`, `token_ledger.py`,
`dashscope/adapter.py`, `google_genai/adapter.py`,
`openai_compatible/adapter.py` (placeholder), `rapidocr_local/adapter.py`,
`catalog/presets.py`, `catalog/gemini.py`, `catalog/qwen_vl.py`,
`catalog/resolve_entity.py`.

`batch/`: `normalize_providers.py`, `resolve_batch_size.py`,
`fallback_chain.py`, `error_accumulator.py`, `pool_worker.py`, `dispatch.py`,
`batch_run_result.py`, `image_batch_state.py`,
`serialize_image_batch_state.py`, `parse_image_batch_state.py`,
`load_image_batch_state.py`, `save_image_batch_state_atomically.py`,
`audio_batch_state.py`, `reuse_image_batch_state.py`,
`fingerprint_batch_request.py`, `batch_markers.py`, `rewrite_md_region.py`,
`compose_image_result.py`, `compose_audio_result.py`, `resume.py`, `repair.py`,
`verify_batch_sources.py`, `owned_intermediates.py`.

Facades: `recognize_images_to_markdown.py`, `recognize_audio_to_markdown.py`,
`resume_images_to_markdown.py`, `resume_audio_to_markdown.py`,
`resume_video.py`, `chunk_audio.py`, `video/dedupe_video_frames.py`, rewritten
`recognize_video.py`, reshaped `compose_video_result.py`, updated `errors.py`
and `__init__.py`.

One file, one responsibility, describable in five words; functions over ~150
lines are split. Existing reusable machinery is reused, not rewritten: the
image resume layer, the long-audio partial-state layer (the state template),
`output/*` atomic writers and claims, both error mappers, token aggregators,
`ProviderRequestStartGate`, and the frame-selection internals
(`scan_video_frame_candidates` / `select_video_frame_candidates`, whose
binary-search density calibration is the negative-feedback deduplication).

## Dispatch Engine Semantics

1. `normalize_providers`: single entity → one sub-list; flat list → one
   fallback-chain sub-list; nested list → one thread per sub-list with
   round-robin batch assignment (`batch_index % len(pool)`).
2. Each pool worker drains its assigned batches: cancellation check, then walk
   the sub-list from the persisted rotation pointer (last success), traversing
   the whole list exactly once per batch.
3. `ProviderCapabilityMismatch` aborts the run immediately. `ProviderError` is
   evaluated only in `fallback_chain.py` against the current provider's
   `retry_policy` (semantics above).
4. Success → `TokenLedger.record`, slot settlement into the checkpoint,
   rotation pointer update.
5. Chain exhausted → `BatchFailureRecord` (no spillover), continue.
6. A provider rejecting batch size (`PROVIDER_REQUEST_INVALID`) follows the
   `"error"` strategy; the failed batch is resumable with a different provider
   because the plan fingerprint excludes provider identity.

## Implementation Phases

1. Pure data and errors: `errors.py` additions, `entity.py`,
   `retry_policy.py`, `catalog/presets.py`.
2. Adapters (offline-portable): adapter protocol/DTO/options/registry, the
   four adapter modules, `token_ledger.py`. Live gate: existing smoke runners
   drive the adapters directly.
3. Dispatch engine (offline): normalize/resolve/fallback/accumulator/worker/
   dispatch/result.
4. Merged-Markdown facades and state (offline): the `batch/` state family,
   markers, region rewrite, composers, resume, repair, ownership, the three
   facades, `chunk_audio`.
5. Video orchestrator (offline): `dedupe_video_frames`, rewritten
   `recognize_video`, reshaped compose/publish, `__init__.py`.
6. Prefab catalog plus live gates: one image batch and one audio batch per
   family against the real APIs; evidence recorded under `docs/`; only
   verified models stay.
7. Deletion and documentation: delete the video job-state layer in dependency
   order (leaf validators/serializers → job recognizers → journal → state →
   finalize → the monolith), update all documentation, run the full suite.

## Deletion List (verified confined to the video chain)

`recognize_video_to_markdown.py`, `video_job_state.py`,
`parse_video_job_state.py`, `serialize_video_job_state.py`,
`load_video_job_state.py`, `save_video_job_state_atomically.py`,
`video_job_journal.py`, `video_job_state_file_limit.py`,
`validate_video_job_resume.py`, `validate_video_job_resume_request.py`,
`validate_video_job_resume_image_requests.py`, `recognize_video_job_frames.py`,
`recognize_video_job_audio.py`, `prepare_video_job_audio_state.py`,
`restore_video_job_frames.py`, `finalize_video_job.py`,
`video_audio_requires_credential_preflight.py`.

Kept shared layers: the image resume layer, the long-audio partial-state
layer, `contracts/source_fingerprint.py`, `output/*`, `errors.py`, token
aggregators, the video media step modules.

## Tests (minimal, per scope discipline)

`test_provider_entity.py`, `test_retry_policy.py`,
`test_error_accumulator.py`, `test_resolve_batch_size.py`,
`test_batch_dispatch.py`, `test_recognize_images_to_markdown.py`,
`test_recognize_audio_to_markdown.py`, `test_chunk_audio.py`, rewritten
`test_recognize_video.py`; updated `test_import_contract.py` /
`test_lightweight_import.py`. Deleted: `test_recognize_video_to_markdown.py`,
`test_video_job_state_persistence.py`, `test_resumable_video_pre_dispatch.py`,
`test_video_long_audio_settlement.py`. Live gates stay opt-in env-gated smokes.

## Risks And Boundaries

- Cancellation across pool threads follows the existing gate-abort plus
  settle-dispatched pattern; in-flight synchronous calls cannot be
  interrupted.
- Credential-pool integration is deferred; entities use one key per
  `api_key_env` this iteration to avoid double-backoff.
- `base_url=None` means the documented vendor default endpoint (DashScope:
  `https://dashscope.aliyuncs.com/compatible-mode/v1`); explicit `base_url`
  wins, `region` stays in `CallOptions`. This is a deliberate behavior change
  from the explicit-endpoint rule and is recorded in
  `ACTIVE_STATE_AND_RULES.md`.
- New canonical error codes must be registered in `STABLE_ERROR_CODES` and
  default safely in `RetryPolicy`.
- Windows path budget (259 UTF-16 units) applies to work directories, sidecar
  names, and frame filenames as today.
- Ownership deletion (D5) touches only paths recorded at creation; caller
  files are never deleted.
