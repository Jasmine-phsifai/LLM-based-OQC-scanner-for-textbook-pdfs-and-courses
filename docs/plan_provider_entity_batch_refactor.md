# Plan: Provider Entity, Batch Engine, And Video Pipeline Decomposition

Status: **approved 2026-08-28; execution plan. Documentation pre-alignment
done at `bdda8f4`; implementation not started.**

This is the active authority for the next library iteration, registered as
entry #568 in [`ACTIVE_STATE_AND_RULES.md`](ACTIVE_STATE_AND_RULES.md). Where
older
documents conflict, this file wins and the older entry carries an OBSOLETE
marker pointing here. Read `ACTIVE_STATE_AND_RULES.md` first for document
precedence and coding rules. All paths are relative to the repository root;
the package root is `src/ocrllm/`.

## 1. Why This Refactor Exists

1. The video pipeline is a black box: `recognize_video_to_markdown.py` (590
   lines) hides inspect → extract frames → dedupe → recognize → extract audio
   → chunk → recognize → compose inside one function. A caller who already
   extracted frames or audio cannot enter mid-pipeline.
2. Video owns a dedicated resume layer: `video_job_state.py` plus sixteen
   siblings maintain a journal format serving only video, duplicating the
   image and long-audio resume systems.
3. There is no first-class provider object: `Config.provider` holds one
   provider per call; no fallback chain, no multi-provider concurrency, no
   retry loop anywhere (the DashScope client runs `max_retries=0`;
   `provider_error_disposition.py` metadata is consumed only by the credential
   pool and the model-candidate gate).

Goals, in priority order (architecture, then maintainability, then
functionality; effort is explicitly not a constraint): expose the pipeline as
public step functions with a thin orchestrator; introduce pure-data
`ProviderEntity` objects accepted as single / flat-list / nested-list; delete
the video resume layer and route video resume to image-batch plus audio-batch
resume on one Markdown file.

Frozen prior decisions remain in force: no social-media crawling in scope;
`repair` stays experimental (assumes one Markdown failure marker equals one
ocrllm failure; covers only lost resume records or intermediates); Electron
frontends call this library only through a Python/Rust backend.

## 2. Locked Decisions

- **D1, pool dead sub-list.** When every provider in one sub-list of a nested
  provider list is exhausted, that sub-list's remaining assigned batches are
  recorded failed (batch range, last provider, last code, description). No
  spillover to other sub-lists. The run continues; failed slots stay visible
  in the Markdown and are resumable.
- **D2, retry policy keyed on canonical codes.** `retry_policy` maps
  `errors.py` canonical codes (e.g. `PROVIDER_RATE_LIMITED`) to
  `(strategy, extra_retries, wait_seconds)`, not HTTP statuses. Raw HTTP
  status stays in error `details` for the final report. The existing
  `map_dashscope_error.py` / `map_google_genai_error.py` produce canonical
  codes and are reused unchanged.
- **D3, default batch size.** Unset `batch_size` resolves once per run to
  `min(default_image_batch_size)` across the flattened provider list.
  Failover never re-chunks (re-chunking destroys slot identity and resume).
- **D4, naming.** `recognize_images_to_markdown` /
  `recognize_audio_to_markdown`; `recognize_batch` keeps its
  one-Markdown-per-image semantics.
- **D5, intermediate lifecycle.** Only files the `recognize_video`
  orchestrator extracts from a video input are owned intermediates: deleted
  on success, kept on failure (resume needs them);
  `keep_intermediates=True` opts out. Caller-supplied frames/audio are never
  deleted. Ownership is recorded at creation via the owned-media fingerprint
  mechanism, never inferred from paths. Sidecars are state, not
  intermediates: kept after success so repeat calls skip paid work (the
  image-resume convention).
- **D6, separate provider arguments.** The orchestrator takes
  `image_providers` and `audio_providers` independently.

### 2.1 Retry policy semantics

Strategies: `"error"` (request-invalid class), `"next"` (fail-over class),
`"current"` (stay-and-back-off class). On each `ProviderError`, the engine
retries the same provider up to `extra_retries` times with `wait_seconds`
between attempts. On overflow — for **every** strategy — it records a
`ProviderFailureRecord` and advances to the next provider. The strategies
differ only in retry behavior and report severity: `"error"` records at error
severity, `"next"`/`"current"` at info severity.

Preset shape (per-vendor module constants `GOOGLE_RETRY_POLICY`,
`DASHSCOPE_RETRY_POLICY`; entities reference presets, per-model override
allowed, dicts never copied per prefab):

```text
PROVIDER_REQUEST_INVALID      ("error",   1,  1)
PROVIDER_AUTHENTICATION /
PROVIDER_PERMISSION_DENIED /
PROVIDER_ACCOUNT_SUSPENDED /
PROVIDER_QUOTA_EXHAUSTED      ("next",    1,  1)
PROVIDER_RATE_LIMITED         ("current", 6, 10)
PROVIDER_CONCURRENCY_LIMITED  ("current", 10, 30)
PROVIDER_UNAVAILABLE          ("current", 10, 10)
PROVIDER_TIMEOUT / PROVIDER_NETWORK ("current", 3, 5)
```

Unknown codes default to `("next", 0, 0)` — never spin on an unlisted code.
Constructor validation: strategy membership, `0 <= extra_retries <= 32`,
`0 <= wait_seconds <= 600`; no infinite waits.

### 2.2 Error accumulation and terminal states

- `ProviderFailureRecord(vendor, model_id, last_code, last_http_status,
  description, attempts, severity)` — one per overflowed provider.
- `BatchFailureRecord(batch_range, last_provider, last_code, description)` —
  one per failed batch.
- Terminal states: (a) all batches settled with provider overflows →
  `status="complete"`, all records on `RecognitionResult.warnings`; (b) some
  batches failed → `status="partial"`, Markdown published with failed
  markers, records in warnings/metadata; (c) everything failed → raise the
  existing `AllCandidatesExhausted` with `details["provider_failures"]` and
  `details["batch_failures"]` plus `provider_calls_attempted` and
  `settled_model_usage` attached via the existing helpers. One failed batch
  never aborts the run. The report always distinguishes "completed but some
  providers never worked" from "no provider completed the work".

### 2.3 Capability model

Entity flags: `supports_plain_ocr`, `supports_detail_ocr`
(LaTeX-formula-capable OCR), `supports_audio`. Constructor invariant:
`supports_detail_ocr=True` requires `supports_plain_ocr=True`, else
`ValueError`. New error `ProviderCapabilityMismatch(OCRLLMError)`, code
`PROVIDER_CAPABILITY_MISMATCH` (register in `STABLE_ERROR_CODES`), **not** a
`ProviderError` subclass: the caller passed an incapable provider, so it
aborts immediately, never retries, never accumulates, and names the missing
capability. Gating: `recognize_images_to_markdown(detail=False)` requires
`supports_plain_ocr`, `detail=True` requires `supports_detail_ocr`; audio
functions require `supports_audio`.

### 2.4 Invocation model

Entities are pure frozen data — no callables, no secrets. Executable code
lives in `ADAPTERS: dict[str, ProviderAdapter]` keyed by `entity.adapter`:
`"dashscope_openai"`, `"google_genai"`, `"openai_compatible"` (registry
placeholder; calling it raises `ConfigError`/`CONFIG_INVALID` until a real
consumer lands; future vllm/ollama reuse it via `base_url` with zero
dedicated code), `"rapidocr_local"`.

Adapter contract:

```python
class ProviderAdapter(Protocol):
    def recognize_images(
        self, image_paths: Sequence[Path], *,
        prompt: str, entity: ProviderEntity, options: CallOptions,
    ) -> AdapterResponse: ...

    def recognize_audio(
        self, audio_snapshot: Path, *,
        prompt: str, entity: ProviderEntity, options: CallOptions,
    ) -> AdapterResponse: ...
```

`AdapterResponse(markdown, input_tokens, output_tokens, client_closed)` —
frozen. `CallOptions(cancellation, timeout_seconds, api_key_override,
region)` — frozen, per-call; keeps entities pure. Adapters own SDK loading,
credential resolution from `entity.api_key_env` (explicit override via
`CallOptions`), request building, SDK retries disabled (`max_retries=0` —
retry is the engine's job), error mapping through the existing mappers, and
the Google long-audio Files upload/poll/delete lifecycle.

Entity fields: `vendor`, `model_id`, `adapter`, `api_key_env`, `base_url`
(`None` = vendor default endpoint), the three capability flags,
`default_image_batch_size` (`1` for non-thinking models),
`default_audio_minutes` (default `30`, from context size, stability, and hard
provider ceilings), `max_output_tokens`, `retry_policy`.

Prefab catalog (`providers/catalog/`): only live-verified models. First
families: the Gemini flash line and the Qwen-VL line already in use.
Function-interface rewrites begin only after the first prefabs are
live-verified.

### 2.5 Concurrency and token accounting

Provider calls stay synchronous; pool mode runs one thread per sub-list
(`ThreadPoolExecutor`, `max_workers = len(pool)`). No asyncio. One
thread-safe `TokenLedger` per run accumulates input/output tokens by entity
and feeds `metadata["current_model_token_usage"]` through the existing
`aggregate_model_token_usage` shape; per-batch usage is also written into
slot checkpoints as resume evidence. One `ProviderRequestStartGate` per run
shared by all pool threads through the existing ContextVar mechanism;
`Cancelled` in any thread aborts the gate; dispatched-but-unsettled work is
settled before the pool exits (the `recognize_batch`
`_settle_dispatched_outcomes` pattern). In-flight synchronous SDK calls
remain uninterruptible (existing documented limitation).

### 2.6 Scope discipline

No full model catalogs; no dynamic pool rebalancing; minimal tests. The
entity engine performs one recognition call per batch (single prompt, single
pass); the multi-pass board workflow (draft/review/scout) stays exclusive to
the `Config` line and is not ported — adapters are prompt-agnostic, so a
workflow layer could compose later without adapter changes. The DashScope
credential pool stays a separate key-level layer: entities use one key per
`api_key_env` this iteration (pool integration is follow-up work that must
reconcile double-backoff).

## 3. Target Public API

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

- `providers` is required and accepts `ProviderEntity |
  list[ProviderEntity] | list[list[ProviderEntity]]`.
- `chunk_audio` requires at least one of `interval_minutes`/`provider`;
  `interval_minutes=-1` means no chunking; an explicit interval wins over
  `provider.default_audio_minutes`; provider duration limits surface at
  recognition time, not in `chunk_audio`.
- Audio batching is one slot per chunk; audio has no images-per-call batch
  size.
- Default output locations: single image/audio → the source's own directory;
  batch images → the parent of the folder holding the images; batch audio →
  the parent of the folder holding the audio files; video → the video's own
  directory (`<stem>.md`). `output` is always optional-explicit.
- Video runs stage owned intermediates in `<stem>.ocrllm-work/` beside the
  Markdown (`frames/`, audio chunks, sidecars). Success without
  `keep_intermediates` deletes it; failure keeps it for resume. Caller-owned
  media never enters this directory.

Breaking changes (release notes): `recognize_video_to_markdown` removed;
`recognize_video` signature `image_config`/`audio_config` →
`image_providers`/`audio_providers`, return `VideoRecognitionOutcome` →
`RecognitionResult`, gains resume. `recognize`, `recognize_batch`,
`recognize_long_mp3`, `recognize_video_frames` keep working unchanged.

## 4. State And Resume Model

**Sidecar plan plus Markdown slot ledger.** Every durable path today is
sidecar JSON; no resume-from-Markdown exists. The "Markdown is the
checkpoint" doctrine is satisfied by materializing every slot boundary and
failure record in the Markdown (the repair feature's input); the sidecar is
the verify-before-pay layer, not a second authority.

Sidecar — `<stem>.ocrllm-image-batch.json` / `<stem>.ocrllm-audio-batch.json`
(inside the work directory for video runs), modeled on
`LongAudioPartialState`:

- Ordered request-fingerprint plan (one fingerprint per image batch / audio
  window). Resume requires a byte-identical plan, else
  `RESUME_STATE_MISMATCH` (mirroring `reuse_long_audio_partial_state`).
- **The plan fingerprint excludes provider identity** (sources + batch size +
  detail mode + prompt/profile version only). Resume may pass different
  providers — "change provider and resume" is a hard requirement. Settled
  slots are paid assets, reused regardless.
- Index-aligned settled slots. Images: `ImageBatchSettledSlot` (mirror of
  `LongAudioSettledSlot`: batch index, fingerprint, markdown, sha256,
  provider, model, calls attempted, tokens, status, warnings). Audio: the
  existing `LongAudioSettledSlot` reused verbatim.
- Per-sub-list rotation pointer (last successful provider index).
- Run facts: `resolved_batch_size`, detail mode, audio interval; for
  orchestrator runs, the owned-intermediate fingerprints (D5).

Markdown markers (closed HTML comments, always emitted, parseable by
`batch/batch_markers.py`, strippable by the existing
`providers/remove_closed_html_comments.py`):

```text
<!-- ocrllm:image-group index=3 status=done start=24 end=31 -->
<!-- ocrllm:image-group index=4 status=failed start=32 end=39 last_provider="dashscope" last_code="PROVIDER_QUOTA_EXHAUSTED" description="..." -->
<!-- ocrllm:audio-window index=5 status=done start=120.0 end=180.0 -->
<!-- ocrllm:region images start --> ... <!-- ocrllm:region images end -->
```

The video orchestrator writes both batches into one Markdown; each owns an
`ocrllm:region`, and `batch/rewrite_md_region.py` replaces only the owning
region — this is what lets `resume_video` resume each branch independently
on the same file.

Resume read order: (1) sidecar present and plan identical → verify input
bytes against fingerprints → missing = planned − settled (failed slots are
retried per D1) → dispatch from persisted rotation pointers; no Markdown
parsing. (2) sidecar lost/unusable → `repair` (experimental, explicit):
parse Markdown markers, rebuild the failed-slot list, re-run failed slots
once with the caller's current providers, rewrite the region; no byte
verification (repair's documented limitation).

Lifecycle: full success → Markdown published, owned intermediates deleted
(D5), sidecar kept. Success-with-overflow → partial Markdown with failed
markers, sidecar kept. Total failure → nothing published, everything kept
(the #371 retain-recoverable-gaps doctrine, carried by batch state instead
of a journal).

## 5. Current → Target Map (what exists and is reused)

Provider invocation (§2.4 replaces the funnel, not the mappings):

- Reused as-is: `providers/dashscope/map_dashscope_error.py`,
  `providers/google_genai/map_google_genai_error.py` (canonical codes + raw
  status in details), `errors.py` (`STABLE_ERROR_CODES`,
  `_RETRYABLE_BY_DEFAULT`), token aggregators
  (`aggregate_model_token_usage.py`, `attach_current_model_token_usage_to_error.py`),
  `providers/provider_request_start_gate.py`,
  `providers/validate_provider_markdown.py`,
  `providers/remove_closed_html_comments.py`.
- Adapter bodies ported from: `providers/dashscope/recognize_images.py` (→
  `dashscope_openai`), `providers/google_genai/recognize_images.py` +
  `recognize_short_mp3.py` + `recognize_uploaded_mp3.py` (→ `google_genai`),
  `local_ocr/recognize_images_with_rapidocr.py` (→ `rapidocr_local`, with a
  `ProcessorOutput` → `AdapterResponse` translation).
- Replaced: `resolve_vision_provider.py` importlib selection and the
  `call_vision_provider.py` built-in branch → the adapter registry. Injected
  `VisionProvider` objects keep working on the `Config` line only.
- Prefab seeding facts: `DEFAULT_DASHSCOPE_MODEL="qwen3.7-plus-2026-05-26"`,
  `MAX_COMPLETION_TOKENS=16_384`, Google live catalog
  (`list_google_genai_models`, `get_google_genai_model_input_limit`),
  `GOOGLE_AUDIO_INPUT_TOKENS_PER_SECOND=32`,
  `MAX_SHORT_MP3_DURATION_SECONDS=300`.

Batch/Markdown machinery:

- Reused: `processors/recognize_images.py` per-group engine concepts,
  `recognize_batch.py` executor/gate/settlement pattern,
  `pdf/combine_pdf_group_results.py` marker precedent, the whole long-audio
  state layer (`audio/long_audio_partial_state.py`,
  `audio/long_audio_settled_slot.py`, `reuse/save/load/serialize/parse` — the
  template the batch state mirrors), `output/*` (resolve/build/normalize,
  claim, atomic write, atomic path validation).

Video chain:

- Existing public steps kept: `video/inspect_video.py`,
  `video/extract_video_frames.py`, `video/extract_video_audio.py`,
  `video/snapshot_video_source.py`, `video/prepare_video_media.py`.
- Dedup logic reused, not rewritten: `video/scan_video_frame_candidates.py`
  (5 s sampling, 128 px luminance + 32 px color thumbnails) and
  `video/select_video_frame_candidates.py` (similarity segmentation,
  28–40 frames/hour density target via sensitivity binary search — the
  negative-feedback calibration). `dedupe_video_frames` adds the on-disk
  image-file input path (decode thumbnails from files, same segmentation).
- Audio chunking reused: `audio/build_long_audio_interval_windows.py` (30 s
  context per side), `audio/materialize_long_audio_interval.py`. The `-1`
  sentinel is new spelling mapped to no-chunk in `chunk_audio`.
- Ownership/fingerprint reused: `build_owned_media_fingerprint.py`,
  `hash_video_snapshot.py`, `hash_snapshot_bytes.py`,
  `source_fingerprint_path.py`, `contracts/source_fingerprint.py`.
- Deleted (verified confined to the video chain): §9 list.

## 6. Module Build Spec (new)

### 6.1 `src/ocrllm/providers/`

| File | Responsibility |
|---|---|
| `entity.py` | Frozen `ProviderEntity` + capability invariant + entity fingerprint |
| `adapter.py` | `ProviderAdapter` Protocol (§2.4) |
| `adapter_response.py` | Frozen `AdapterResponse` DTO |
| `call_options.py` | Frozen per-call `CallOptions` |
| `registry.py` | `ADAPTERS` dict + lookup/validation |
| `retry_policy.py` | `RetryPolicy`/`RetryPolicyEntry`, canonical-code keyed, bounds validation |
| `token_ledger.py` | Thread-safe per-entity token accumulator |
| `dashscope/adapter.py` | DashScope adapter (port of `recognize_images.py`; Config → entity+options) |
| `google_genai/adapter.py` | Google adapter (image + short audio + long-audio Files lifecycle) |
| `openai_compatible/adapter.py` | Registry placeholder; raises `ConfigError`/`CONFIG_INVALID` |
| `rapidocr_local/adapter.py` | RapidOCR adapter with `ProcessorOutput`→`AdapterResponse` translation |
| `catalog/__init__.py` | Package marker + `ALL_PREFABS` |
| `catalog/presets.py` | `GOOGLE_RETRY_POLICY`, `DASHSCOPE_RETRY_POLICY` |
| `catalog/gemini.py` | Live-verified Gemini flash prefab tuple |
| `catalog/qwen_vl.py` | Live-verified Qwen-VL prefab tuple |
| `catalog/resolve_entity.py` | Identity pass-through or by-name catalog lookup |

### 6.2 `src/ocrllm/batch/`

| File | Responsibility |
|---|---|
| `normalize_providers.py` | Three input shapes → validated `ProviderPool`; per-modality capability gating |
| `resolve_batch_size.py` | D3: explicit wins, else flattened min, resolved once |
| `fallback_chain.py` | Sub-list rotation (start at last success, full traversal exactly once) + per-error retry evaluation — the only place `retry_policy` is evaluated |
| `error_accumulator.py` | Thread-safe `ProviderFailureRecord`/`BatchFailureRecord` accumulator (defines both) |
| `pool_worker.py` | One sub-list thread: drain assigned batches, settle or record |
| `dispatch.py` | Engine: build pool, one thread per sub-list, round-robin assignment, shared gate/ledger/accumulator → `BatchRunResult` |
| `batch_run_result.py` | Frozen run result (settled slots, failure records, token usage, call count) |
| `image_batch_state.py` | `ImageBatchState`/`ImageGroupPlan`/`ImageBatchSettledSlot` (frozen, validated) |
| `serialize_image_batch_state.py` | State → strict JSON |
| `parse_image_batch_state.py` | JSON → strict state |
| `load_image_batch_state.py` | Bounded optional load (mirrors long-audio load) |
| `save_image_batch_state_atomically.py` | Atomic sibling-temp replace (mirrors long-audio save) |
| `reuse_image_batch_state.py` | Byte-identical plan reuse or `RESUME_STATE_MISMATCH` |
| `audio_batch_state.py` | Thin wrapper: reused `LongAudioPartialState` + rotation/ownership |
| `fingerprint_batch_request.py` | Per-slot fingerprint: sources + mode + batch size + prompt version; **no provider** |
| `batch_markers.py` | Emit/parse `image-group`/`audio-window`/`region` markers |
| `rewrite_md_region.py` | Atomically replace one `ocrllm:region`, preserve others |
| `compose_image_result.py` | `# Images` + `## Image group N` composition + markers |
| `compose_audio_result.py` | `# Audio` + `## Audio window N` composition + markers |
| `resume.py` | Sidecar-first resume: verify inputs, compute missing, restore rotations |
| `repair.py` | Experimental Markdown-only repair |
| `verify_batch_sources.py` | Byte-verify inputs against sidecar fingerprints pre-dispatch |
| `owned_intermediates.py` | Record owned intermediates at creation; delete on success (D5) |

### 6.3 Facades and video (`src/ocrllm/`)

| File | Responsibility |
|---|---|
| `recognize_images_to_markdown.py` (new) | Image batches → one Markdown; default output = parent of images folder |
| `recognize_audio_to_markdown.py` (new) | Audio chunks → one Markdown; default output = parent of audio folder |
| `resume_images_to_markdown.py` (new) | Sidecar-first resume entry for the image batch |
| `resume_audio_to_markdown.py` (new) | Sidecar-first resume entry for the audio batch |
| `resume_video.py` (new) | Route both batch resumes on one Markdown |
| `chunk_audio.py` (new) | Chunking per §3 rules |
| `video/dedupe_video_frames.py` (new) | Public `dedupe_video_frames`: on-disk images → thumbnails → existing segmentation |
| `recognize_video.py` (rewrite) | Thin resumable orchestrator (validate → snapshot → inspect → extract → dedupe → image batch → extract audio → chunk → audio batch → compose → publish) |
| `compose_video_result.py` (reshape) | Existing layout + per-region slot markers |
| `publish_video_result.py` (reshape, minor) | Extend reserved-path set for the new sidecars |
| `errors.py` (change) | `PROVIDER_CAPABILITY_MISMATCH` + `ProviderCapabilityMismatch` |
| `__init__.py` (change) | Export new names; remove `recognize_video_to_markdown`; keep the Config line |

One file, one responsibility, describable in five words; functions over ~150
lines are split.

## 7. Dispatch Engine Semantics

1. `normalize_providers`: single entity → `((e,),)`; flat list → one
   fallback-chain sub-list; nested list → one thread per sub-list, batches
   assigned round-robin (`batch_index % len(pool)`).
2. Pool worker per batch: cancellation check → activate the shared gate →
   walk the sub-list from the persisted rotation pointer, full traversal
   exactly once (a batch never revisits a provider).
3. Per provider: snapshot input (`imaging/snapshot_image_group` for images;
   the existing audio snapshot path for chunks) → `ADAPTERS[entity.adapter]`.
   `ProviderCapabilityMismatch` aborts the whole run immediately.
4. On `ProviderError`: evaluate `entity.retry_policy[error.code]` in
   `fallback_chain.py` only (§2.1 semantics); overflow → record
   `ProviderFailureRecord` (all strategies) → advance.
5. Success → `TokenLedger.record` → settle slot into the checkpoint (sidecar
   + memory) → rotation pointer = this provider.
6. Chain exhausted → `BatchFailureRecord` (D1, no spillover) → next batch.
7. A provider rejecting batch size (`PROVIDER_REQUEST_INVALID`) follows the
   `"error"` strategy; the failed batch is resumable with a different
   provider (plan fingerprint excludes provider identity).
8. Run end: terminal disposition per §2.2.

## 8. Implementation Phases

Each phase is independently testable. Live-API gates touch only adapters and
the prefab catalog.

| Phase | Deliverables | Tests | Gate |
|---|---|---|---|
| 1. Pure data + errors | `errors.py` additions, `entity.py`, `retry_policy.py`, `catalog/presets.py` | `test_errors.py` addition, `test_provider_entity.py`, `test_retry_policy.py` | offline green |
| 2. Adapters | `adapter.py`, `adapter_response.py`, `call_options.py`, `registry.py`, four adapter modules, `token_ledger.py` | fake-SDK translation units mirroring `test_dashscope_adapter.py` | offline green; existing smoke runners drive adapters directly (env-gated) |
| 3. Dispatch engine | `normalize_providers.py`, `resolve_batch_size.py`, `fallback_chain.py`, `error_accumulator.py`, `pool_worker.py`, `dispatch.py`, `batch_run_result.py` | `test_error_accumulator.py`, `test_resolve_batch_size.py`, `test_batch_dispatch.py` | offline green, no network |
| 4. Merged facades + state | `batch/` state family, markers, region rewrite, composers, resume, repair, ownership; `recognize_images_to_markdown.py`, `recognize_audio_to_markdown.py`, `resume_*.py`, `chunk_audio.py` | `test_recognize_images_to_markdown.py`, `test_recognize_audio_to_markdown.py`, `test_chunk_audio.py` (fake adapters) | offline green |
| 5. Video orchestrator | `video/dedupe_video_frames.py`, rewritten `recognize_video.py`, reshaped compose/publish, `__init__.py` | rewritten `test_recognize_video.py`: full-chain fake run, resume routing, intermediate deletion/keep | offline green |
| 6. Prefab catalog + live | `catalog/gemini.py`, `catalog/qwen_vl.py`, `resolve_entity.py` | env-gated prefab smokes: one image batch + one audio batch per family | live evidence recorded under `docs/`; only verified models stay |
| 7. Deletion + docs | §9 execution; navigation docs rewritten to the new API; OBSOLETE-pending markers removed | full suite + updated `test_import_contract.py` / `test_lightweight_import.py` | all green |

Phase 7 documentation scope (the 2026-08-28 pre-alignment at `bdda8f4`
already registered the decision): rewrite the video sections of `README.md`,
`START_HERE.md`, `MIGRATION_STATUS.md`,
`src/ocrllm/README_ACTIVE_LIBRARY.md` to the shipped new API; remove the
"approved, implementation pending" qualifiers; update the
`ocrllm_module_target_design.md` package layout; record completion in
`ACTIVE_STATE_AND_RULES.md`.

## 9. Deletion List And Order

Verified confined to the video chain by repo-wide grep. Delete in dependency
order during Phase 7, after resume parity is proven (fixture video run to
failure → new `resume_video` completes → sidecar-lost repair completes):

1. Leaf validators/serializers: `parse_video_job_state.py`,
   `serialize_video_job_state.py`, `load_video_job_state.py`,
   `save_video_job_state_atomically.py`, `video_job_state_file_limit.py`,
   `validate_video_job_resume.py`, `validate_video_job_resume_request.py`,
   `validate_video_job_resume_image_requests.py`,
   `prepare_video_job_audio_state.py`, `restore_video_job_frames.py`,
   `video_audio_requires_credential_preflight.py`.
2. Job recognizers: `recognize_video_job_frames.py`,
   `recognize_video_job_audio.py`.
3. Core: `video_job_journal.py`, `video_job_state.py`,
   `finalize_video_job.py`.
4. The monolith: `recognize_video_to_markdown.py` and its `__init__.py`
   export.
5. Tests: `test_recognize_video_to_markdown.py`,
   `test_video_job_state_persistence.py`,
   `test_resumable_video_pre_dispatch.py`,
   `test_video_long_audio_settlement.py` (still-meaningful offline assertions
   move into the rewritten `test_recognize_video.py`).

## 10. Risks And Boundaries

- Cancellation across pool threads: gate abort plus settle-dispatched; paid
  work settles before `Cancelled` propagates; usage/call evidence attached
  per the existing convention.
- Credential-pool double-backoff: entities bypass the pool this iteration
  (§2.6); integration is follow-up work.
- `base_url=None` behavior change (documented vendor default endpoint;
  DashScope `https://dashscope.aliyuncs.com/compatible-mode/v1`; explicit
  `base_url` wins; `region` in `CallOptions`) — already registered in
  `ACTIVE_STATE_AND_RULES.md` #568.
- Retry-policy code drift: new canonical codes must register in
  `STABLE_ERROR_CODES` and default safely in `RetryPolicy`.
- Windows path budget (259 UTF-16 units, #132): work directory
  `<stem>.ocrllm-work`, short sidecar names, `frame-XXXXXXXX.jpg` filenames;
  `validate_atomic_output_path` guards extremes.
- D5 safety: deletion touches only paths recorded in `owned_intermediates`
  at creation; caller files are never deleted.
- Board multi-pass workflow is not ported (§2.6) — a deliberate scope
  boundary.

## 11. Verification

1. `python -m pytest tests/ -x -q` (live gates excluded) — all green.
2. `tests/test_import_contract.py` + `tests/test_lightweight_import.py` —
   new public surface lazy-imports cleanly.
3. Offline end-to-end with fake adapters: video → work directory → two-region
   Markdown → kill mid-run → `resume_video` completes → work directory
   deleted; repeat with sidecar removed → repair completes.
4. Live gates (real keys, env-gated): one image batch + one audio batch per
   prefab family; codes, call counts, and token usage recorded under `docs/`.
5. Doc consistency: `grep -r "recognize_video_to_markdown" src/ README.md
   START_HERE.md MIGRATION_STATUS.md` returns only historical/OBSOLETE
   references.

## Critical Files For Implementation

- `src/ocrllm/errors.py` — new code + class
- `src/ocrllm/recognize_video.py` — orchestrator rewrite skeleton
- `src/ocrllm/recognize_video_to_markdown.py` — monolith to replace (plus
  `video_job_state.py`, `video_job_journal.py`,
  `recognize_video_job_frames.py`, `recognize_video_job_audio.py`)
- `src/ocrllm/audio/long_audio_partial_state.py`,
  `audio/long_audio_settled_slot.py`, `audio/reuse_long_audio_partial_state.py`,
  `audio/save_long_audio_partial_state_atomically.py` — batch state template
- `src/ocrllm/processors/recognize_images.py` and `src/ocrllm/recognize_batch.py`
  — dispatch/gate/settlement patterns the engine generalizes
- `src/ocrllm/providers/dashscope/recognize_images.py` and
  `providers/google_genai/recognize_uploaded_mp3.py` — adapter body sources
- `src/ocrllm/video/select_video_frame_candidates.py` — dedup segmentation to expose
- `src/ocrllm/__init__.py` — public surface change
