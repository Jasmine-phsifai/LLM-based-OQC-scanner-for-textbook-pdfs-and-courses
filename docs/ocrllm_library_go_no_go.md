# OCRLLM Library Go/No-Go Execution Decision

Status: active execution contract for gates and boundaries, **outranked by
`docs/ACTIVE_STATE_AND_RULES.md` for all current status**.

Decision date: 2026-07-12. Precedence and current state revised 2026-08-18.

Read `docs/ACTIVE_STATE_AND_RULES.md` before this file. It carries current
state, the open defect register, and the coding and documentation rules. Where
this file and that file disagree, that file wins.

The dated narrative entries appended under "Verification Commands" are an
immutable record of past attempts. Each states a conclusion that was true only
on its own date, and many read "Phase 1 remains NO-GO" because that was true
when written. Do not cite any of them as current state. Current shipped status,
open defects, and next work are only in
`docs/ACTIVE_STATE_AND_RULES.md`.

This file remains authoritative for phase gates, file responsibilities, and the
migrate/rewrite/reject boundary. Tests and runtime trials establish evidence and
gate status; they do not override a NO-GO or deferred boundary. Only an explicit
update to this decision can change a boundary.

## Implementation Directive

Use the following as the prompt for every active-library change:

> Work only in the current phase. Preserve proven user-visible behavior, not
> legacy class or file structure. Write the public behavior and failure tests
> first. Put each function in a file named for that function and give each file
> one responsibility. Keep `import ocrllm` free of optional media, provider,
> GUI, server, and downloader imports. Do not claim a modality is supported
> until its GO gate passes with real input. Do not return success with empty
> Markdown, missing required artifacts, swallowed provider failures, or stale
> paths. Do not import from `legacy_app`. For active PDF work use PDFium through
> `pypdfium2`; do not add PyMuPDF. Stop when a required dependency, credential,
> license notice, fixture, or runtime proof is unavailable and record the
> blocker instead of substituting an untested design.

Before coding:

1. Read `START_HERE.md`, `MIGRATION_STATUS.md`, and this file.
2. Identify the current phase in `MIGRATION_STATUS.md`.
3. State which behavior is being preserved and which legacy files are only
   references.
4. State the pass/fail gate before editing.
5. Reject work that crosses a deferred or NO-GO boundary below.

After coding:

1. Run the phase's offline tests.
2. Run the phase's real smoke test when the gate requires one.
3. Build and install a wheel in an isolated target.
4. Prove `import ocrllm` did not load optional heavy modules.
5. Update `MIGRATION_STATUS.md` with commands, results, and remaining NO-GO
   items.

## Product Decision

GO:

- A Python-first recognition engine under `src/ocrllm/`.
- A small direct Python API.
- Optional image, PDF, audio, video, and provider dependencies.
- A versioned JSON-safe contract established before non-Python adapters depend
  on the engine.
- A one-job JSONL worker for Electron after the real image slice passes.
- PDFium through `pypdfium2` as the only active PDF rendering and text-layer
  engine.
- Porting one tested behavior slice at a time from the legacy app.

NO-GO:

- Copying legacy processors, provider clients, server modules, or configuration
  modules into `src/ocrllm/`.
- PyMuPDF, `fitz`, MuPDF, or another AGPL PDF engine in the active package.
- GUI, FastAPI, social downloader, browser automation, or launcher behavior in
  the core library.
- Returning placeholder Markdown or treating partial/missing required output as
  success.
- A Rust/PyO3 rewrite.
- A single bundle advertised as lightweight while it contains every modality,
  provider, GUI, server, and media dependency.
- Publishing empty extras such as `ocrllm[pdf-text]` before they install and
  enable a tested feature.

DEFERRED:

- HarmonyOS and ArkTS integration. Do not implement it in the active phases and
  do not claim compatibility. A future decision may evaluate an HTTP client or
  a separate native bridge after the Python, Electron, PDF, audio, and video
  contracts are stable.
- Browser React service integration. Preserve a JSON-safe contract now; build a
  service only after the core modalities are useful and a service product is
  explicitly requested. A browser React app cannot import a Python wheel
  directly, so no direct React compatibility claim is technically honest.
- Offline VLM/ASR models, GPU packages, Office documents, social downloads, and
  native/WASM engines.

## Historical Gate Baseline

The following records the Phase 0/1/2 transition baseline as of 2026-07-12. It
is retained for gate provenance, not as a current implementation inventory.

- Phase 0 is GO at commit `5018ad0`. Phase 1 is GO after the passing v17 live
  gate and the clean committed-wheel proof at `0278b66`. Phase 2 is GO after
  the production live worker gate and clean proof at `60ce473` plus the formal
  decision. Phase 2A image-library completion is GO; no later phase is active
  and Phase 3 has not started.
- The active package validates and decodes PNG/JPEG sources before invoking an
  injected provider, rejects empty provider output, returns canonical
  `source_type="image"`, and represents board recognition as `profile="board"`.
- The active image path snapshots validated source bytes for the provider. The
  provider call returns before snapshot cleanup begins, so providers must consume
  the paths synchronously and must not retain them. Snapshot creation/write and
  otherwise-successful cleanup failures raise typed `OUTPUT_WRITE_FAILED`; when a
  typed recognition failure is already active, it remains primary and records
  redacted `snapshot_cleanup_failed=true` detail.
- The injected and built-in `image.board.png`, `image.board.jpeg`, and
  `provider.dashscope.vision` capabilities are `available`. Their unified v17
  board workflow passed both independent Beijing full-corpus runs and the clean
  base, image, and image-plus-DashScope packaging profiles. Earlier failed gates
  remain immutable historical evidence.
- `worker.jsonl.v1alpha1` is `available` as a development worker with an
  explicitly configured Python executable. Packaged Electron compatibility
  remains a Phase 6 gate.
- Phase 2A image-library completion is GO. Local OCR, shared execution policy,
  adapter-owned DashScope/model configuration, provider error disposition,
  credential scheduling, and image resume passed their independent gates. See
  `image_library_completion_decision_2026-07-12.md`.
- PDF, audio, and video remain unsupported by the active package.
- At the Phase 0 transition, package metadata had no base runtime requirements
  and advertised exactly `dev,image`. The current tree still has no base
  requirements and now advertises exactly `dev,image,dashscope,ocr`; `image`
  installs `Pillow>=10.4,<13`, `dashscope` installs `openai>=2.30,<3`, and `ocr`
  installs maintained RapidOCR plus ONNX Runtime. No
  empty PDF, audio, video, or `all` extra is published. The Phase 0 wheel
  measurements below predate the `dashscope` extra and remain historical
  Phase 0 evidence.
- `Config` repr omits provider objects, `api_key`, `dashscope`,
  `cancellation`, and `extra`. Boundary tests use unique sentinels so
  these values cannot leak through repr, public errors, or results.
- Every public `recognize()` call rejects `Config` subclasses and freshly
  revalidates the exact caller `Config` before source/provider work. Injected
  providers receive that original object identity. For a named built-in
  provider, image processing snapshots config as its first action, before
  provider/model resolution, prompt construction, or cancellation inspection;
  the adapter revalidates that isolated snapshot again. Nested
  `DashScopeSettings` and `RecognitionExecutionPolicy` are reconstructed at
  each snapshot, so callback mutation or `object.__setattr__` cannot diverge the
  request from its metadata, smuggle an endpoint past the allowlist, or bypass
  execution limits.
- The original offline quality checkpoint is commit `e328253`. The current
  versioned `board.v6` manifest is exactly `37,685` bytes with SHA-256
  `c058a68b4a17d1ed13c74bd31429269fc4287539afeb23e20c8dfb0be6f50a27`.
  It authenticates 20 committed artifacts, including 5 images, totaling
  `17,914,515` bytes with `8,299,885` bytes of headroom below the 25 MiB corpus
  ceiling. The checkpoint contains the exact licensed corpus, deterministic
  generators, provenance, per-language/token, critical-slot, formula, table,
  and ordered-anchor scorers, and integrated manifest-authenticated
  live-scoring gate. V6 keeps one unified board capability, corrects the
  source-derived handwriting truth, and separates required recall content from
  optional faint source content used only to avoid false precision penalties.
- The scorer entrypoint authenticates the caller's manifest against a freshly
  strict-loaded byte-frozen manifest before scoring. It fails closed for
  non-applicable channels instead of treating missing evidence as a pass. On the
  pinned OCRLLM environment, the full offline suite passed `568` tests, the
  generator reproduced every committed generated image byte-for-byte, and
  `compileall` passed.
- The guarded evidence runner is committed at `fb23d1e` (full commit
  `fb23d1e40d4594ed1da8e244945ae7ccb9568efd`). Offline fake/evidence tests and
  direct no-network live preflight passed without a provider/API call. Preflight
  bound the strict manifest and artifacts, exact import origins, closed public
  signature, and clean Git identity for 98 tracked relevant files to that full
  commit.
- Boundary checkpoint `5aaa854` (full commit
  `5aaa8545a8b73277fa728861be5510cb0a073d84`) hits exact one-below, at, and
  one-above values for the per-source byte, decoded-pixel, group-count,
  aggregate-source-byte, and aggregate-pixel caps. Every rejecting integration
  path proves zero provider calls; aggregate-source rejection also precedes
  temporary-directory access. Together with the already exact provider-request
  limits, the pinned suite now passes `568` tests, fixture generation remains
  byte-identical, and `compileall` passes without a provider/API call.
- On 2026-07-11 the user confirmed canonical region `cn-beijing` and the
  key-matching endpoint. The fixed plan then invoked all 13 calls with zero
  runner retries. Both six-dispatch runs completed, zero passed, no provider
  request failed, and no terminal runner failure occurred. The evidence is
  preserved at
  `evidence/phase1/phase1-quality-2026-07-11-cn-beijing.json`; its SHA-256 is
  `cfb2ee423eafecbc87190f9e30d39439f0ea0a865d1a0348a140f67d8088fa23`.
  Phase 1 remains NO-GO.
- Pushed packaging hotfix `3414f47` corrected a filename-ignore defect without
  weakening secret-ignore patterns. The legitimate
  `resolve_dashscope_api_key.py` / `resolve_dashscope_api_key` names matched the
  existing `*_api_key*` protection, so the hotfix renamed them to
  `resolve_dashscope_credential.py` / `resolve_dashscope_credential` and updated
  all imports, tests, and documentation. A clean Git-archive build from full
  commit `3414f47e5b44a6d5fe2023012ebf2cf361f96a61` produced a `50,094`-byte
  wheel; its isolated no-deps install passed an explicit test-key resolver
  round-trip without a provider network call.
- The clean package proof for `5aaa854` archives that exact commit. Its wheel is
  `51,281` bytes with SHA-256
  `23e0068b4525a437052254d8929f0d7ab7706efd5ff48447d04572c796909d93`, 52
  entries, zero base runtime requirements, and no native or bytecode payload.
  The isolated no-deps target contains 103 files totaling `233,665` bytes.
  Plain import leaves Pillow, PDFium, OpenAI, and HTTPX unloaded, and the
  explicit test-key credential resolver passes. Thirty measured processes
  after two discarded warm-ups pass the Base import budgets: Python 3.10.20
  wall median/p95/max `51.9831/75.8686/77.3612` ms and CPU
  `46.875/78.125/78.125` ms; Python 3.13.5 wall
  `50.79575/61.3618/62.4312` ms and CPU `46.875/62.5/62.5` ms.
- The separate clean optional profiles for `5aaa854` pass too. Image uses
  Pillow 12.3.0, adds `15,904,714` bytes, preserves lazy import, and completes
  a generated-PNG recognition call through the injected-provider path. Image +
  DashScope uses Pillow 12.3.0, OpenAI 2.45.0, and HTTPX 0.28.1, adds
  `40,677,554` bytes, preserves lazy base import, and constructs and closes the
  real client with `max_retries=0` without HTTP. Both pass the 25 MiB and 64 MiB
  ceilings. No external provider/API HTTP request was made. Result-recording
  edits limited to this decision file and `MIGRATION_STATUS.md` do not change
  wheel inputs; this still does not replace the required final decision-time
  rerun after live evidence or a later packaged-input/dependency change.
- A secret-safe local configuration audit found that
  `HKCU:\Software\OCRLLM\QCR\ui` stores a full HTTPS `base_url` whose API key is
  an exact match for the current `DASHSCOPE_API_KEY` under an ordinal string
  comparison that never prints either secret. It uses host
  `dashscope.aliyuncs.com`, exact path `/compatible-mode/v1`, and no query. The
  registry stores no region/location, and no DashScope-related region variable
  was found in the checked Process/User/Machine scopes. This is explicit stored
  endpoint evidence for the current key. The user's 2026-07-11 confirmation now
  authorizes `cn-beijing` and that endpoint for the fixed Phase 1 run.
- Account-specific cost and reliability inputs are recorded in
  `provider_cost_and_reliability_policy.md`; they do not activate Google, Codex,
  FileTrans, pools, or switching during Phase 1. The complete implementation,
  agent-review, and atomic-writer ledger is `phase1_implementation_record.md`.
- The historical Phase 1 adapter-only implementation checkpoint is commit
  `a6a8b18`. Its final offline gate passed `283` tests, `compileall`, and
  `git diff --check`. The wheel was `50,970` bytes with SHA-256
  `5502B5ED58D9D049F3640F3AF9AF5C4A8732426C14EA630D01125BD2556245AE`,
  `53` entries, no native/bytecode payload, and no base runtime requirement. Its
  isolated no-deps target was `233,115` bytes. Fresh CPython 3.10.20 and 3.14.3
  imports left `PIL`, `pypdfium2`, `openai`, and `httpx` unloaded.
- The clean `ocrllm[image]` empty-target install was `15,907,554` bytes and
  passed a generated-PNG recognition call through the injected-provider path
  with Pillow 12.3.0. The separate clean `ocrllm[image,dashscope]` empty-target
  install was `40,727,895` bytes, below the 64 MiB gate. Its offline adapter
  probe used Pillow 12.3.0, OpenAI 2.45.0, and HTTPX 0.28.1, constructed the real
  client with `max_retries=0`, and sent no HTTP request.
- The exact clean Phase 0 gate on the final phase-transition tree reported 141
  tests passed. The wheel was 31,151 bytes with SHA-256
  `FD983CA90944F545A4B670F33A8ABF015712E1DDAC8F866BB4703E0A465C707D`; its
  isolated no-deps target was 135,213 bytes, with no base requirements or native
  files. An outside-repository import reported version `0.1.0` and
  `forbidden modules []`.
- The same clean gate measured Python 3.10 fresh-import wall
  median/p95/max 58.6417/108.1609/114.8606 ms and process-CPU
  46.875/78.125/78.125 ms. Python 3.13 measured wall
  22.86505/30.8795/31.0431 ms and process-CPU 23.4375/31.25/31.25 ms.
- A fresh `ocrllm[image]` environment installed Pillow 12.3.0 with a
  15,814,896-byte delta. Pillow remained absent after base import, and a
  deterministically generated temporary PNG completed recognition through an
  injected provider.
- A real `qwen-vl-max` image call succeeded in an earlier isolated trial, but
  Alibaba now lists that model as legacy. The historical trial remains
  feasibility evidence only; it is neither the Phase 1 model baseline nor a
  capability gate.
- A Windows/Python 3.13 PDFium trial passed with pypdfium2 5.11.0 and PDFium
  151.0.7920.0: text extraction distinguished a text page from a raster-only
  page, both pages rendered at 1224 by 1584, and malformed input raised
  `PdfiumError` with error code 3. Python 3.10 installation remains a Phase 3
  gate.
- The tested Windows amd64 pypdfium2 wheel was 3,778,234 bytes compressed and
  8,306,352 bytes installed. Twenty warm-cache fresh-process imports had a
  98.442 ms median; the first cold-cache observation was 279.718 ms. This is an
  optional feature cost, not part of the base import budget.
- An earlier pre-Phase-0 baseline verification built a 9,283-byte wheel with
  SHA-256
  `166ACEC563B88203A7C8D1F616AB5838192D40501DC8837A5AA99B78EF865D0C` and
  installed to 26,152 bytes. Thirty measured fresh processes after two warm-ups
  gave CPython 3.10.20 wall median/p95 39.768/45.556 ms and CPU
  31.250/46.875 ms; CPython 3.13.5 gave wall 26.265/37.334 ms and CPU
  31.250/31.250 ms. Pillow, pypdfium2, and openai were absent from `sys.modules`
  after every base import; metadata had no base runtime requirement or native
  binary.
- The reference host for those import thresholds is Windows 11 Home x64 build
  10.0.26200, Intel Core i7-1260U, 16,890,388,480 visible bytes of RAM, using the
  two AMD64 CPython interpreters above. A different reference host must record
  its own baseline; it does not erase the absolute size or lazy-import gates.
- A later 20-process Python 3.10 repeat measured 48.978 ms median but one
  155.312 ms maximum and failed the draft maximum-100-ms rule. Because a single
  scheduler/antivirus outlier made that rule non-repeatable, the hard timing gate
  now uses 30 measured processes, median, and nearest-rank p95; maximum remains
  recorded diagnostic evidence rather than the pass/fail statistic.
- A subsequent post-build run reached 70.477 ms wall median and 108.311 ms p95,
  while a separate 30-process CPU/wall probe of the unchanged package measured
  Python 3.10 wall 36.382/40.744 ms median/p95 and CPU 31.250/46.875 ms. The gate
  therefore measures both process CPU and user-visible wall time: CPU catches
  package work; the wider wall ceiling tolerates bounded host scheduling noise.
- Direct installed distribution payloads already present on the reference host
  measured Pillow 12.2.0 at 16,070,317 bytes and pypdfium2 5.11.0 at 8,306,352
  bytes in the Python 3.13 environment, and openai 2.30.0 at 6,836,075 bytes in
  the Python 3.10 environment. Python 3.10 did not have pypdfium2 installed.
  These figures exclude transitive dependencies and therefore are evidence, not
  complete profile sizes.
- Legacy behavior is evidence only; it is not an active import or service
  boundary.

Therefore contract honesty, real board/image work, and the versioned JSONL
worker are complete. Phase 2A image-library completion is current. Local OCR
and shared execution policy are GO; provider transport/model configuration is
next. It is not PDF, audio, video, HTTP service, or native work.

Capability status vocabulary is fixed:

- `available`: the implementation, packaging, deterministic tests, and required
  real gate all pass in the reported environment.
- `experimental`: deterministic tests pass, but a required live, packaging, or
  downstream proof remains.
- `unavailable`: implementation, dependency, configuration, or required proof
  is absent.
- `deferred`: intentionally outside the active phases.

Do not use `supported` as a synonym for `experimental`, `unavailable`, or
`deferred`.

Capability names are a fixed lowercase dot-separated registry, not free-form
marketing labels. Report atomic capabilities so one passing format cannot hide
another failing format. Initial names are:

```text
image.board.png
image.board.jpeg
provider.dashscope.vision
provider.dashscope.audio-short
provider.dashscope.filetrans
worker.jsonl.v1alpha1
worker.jsonl.v1alpha2
pdf.text
pdf.vision
pdf.text.resume
pdf.vision.resume
audio.short.wav-pcm-s16
audio.short.mp3-mpeg-layer3
audio.short.m4a-aac-lc
audio.long.wav-pcm-s16
audio.long.mp3-mpeg-layer3
audio.long.m4a-aac-lc
video.mp4-h264
video.mp4-h264-aac
```

Add a registry name in this file before implementing another profile, format,
codec, provider, or worker version. `get_capabilities()` returns every known
name with one four-state status and a concrete reason; it never reports an
aggregate `audio=available` when only one audio format passed.

`get_capabilities(config: Config | None = None)` performs no network call and
does not import optional packages. With `config=None`, it reports local
installation/gate state and reports built-in DashScope as requiring explicit
region/endpoint settings; `DASHSCOPE_API_KEY` presence cannot safely select a
region. With a named provider/model and `DashScopeSettings`, it evaluates that
exact configuration. An injected provider object proves protocol shape offline
but is `experimental` at most unless it exposes a stable capability identity
matching recorded live evidence. The worker `capabilities` command uses the
zero-argument semantics and never returns secret values.

Canonical transport media types are `image`, `pdf`, `audio`, and `video`.
`board` is an image recognition profile and prompt mode; it is not a transport
media type.

PDFium evidence sources:

- [pypdfium2 project, installation, and licensing](https://github.com/pypdfium2-team/pypdfium2)
- [pypdfium2 Python API and thread-safety rules](https://pypdfium2.readthedocs.io/en/stable/python_api.html)
- [PDFium license](https://pdfium.googlesource.com/pdfium/+/refs/heads/main/LICENSE)

## Runtime Boundaries

```text
Python caller
    -> ocrllm public facade
       -> source validation and routing
       -> one modality processor
       -> optional local helpers
       -> one provider capability
       -> RecognitionResult

Electron main process (after Phase 2)
    -> one-job JSONL worker
       -> the same ocrllm public facade

legacy_app
    -> behavior reference and compatibility app only
    -> never imported by src/ocrllm
```

The processor owns the modality workflow. A provider owns authentication,
request construction, response parsing, provider retry classification, and
provider error mapping. A local helper owns one conversion or inspection task.
An output helper owns one output operation. No layer may silently perform the
responsibility of another layer.

## Target File Responsibilities

Create files only when their phase begins. Do not create empty architecture
scaffolding.

### Public facade and contracts

```text
src/ocrllm/__init__.py
    Re-export documented public names only. No logic and no optional imports.

src/ocrllm/recognize.py
    Define recognize(). Validate, route once, call one processor, call output
    helpers if requested, and return one built RecognitionResult.

src/ocrllm/recognize_batch.py
    Define recognize_batch(). Preserve input order and apply explicit batch
    failure policy. Do not duplicate recognize().

src/ocrllm/config.py
    Define immutable caller configuration and compose provider-specific settings.
    No implicit file loading or network access.

src/ocrllm/validate_config.py
    Freshly validate one exact public Config while preserving its identity for
    injected providers.

src/ocrllm/snapshot_config.py
    Create an isolated freshly validated Config for a trusted built-in adapter.

src/ocrllm/raise_if_cancelled.py
    Inspect one Event-compatible cancellation signal and raise typed CANCELLED.

src/ocrllm/result.py
    Direct-Python compatibility re-export only after contract DTOs are added.

src/ocrllm/processor_output.py
    Define the internal immutable media type, complete/partial status, Markdown,
    artifacts, hotwords, warnings, and metadata returned by every processor.

src/ocrllm/build_recognition_result.py
    Combine one ProcessorOutput and optional final Markdown URI into the public
    RecognitionResult. Validate that every public artifact exists.

src/ocrllm/errors.py
    Define public typed failures. Messages must not contain secrets.

src/ocrllm/get_capabilities.py
    Define get_capabilities(config=None). Report what is installed, configured,
    and proven using exactly available, experimental, unavailable, or deferred.

src/ocrllm/contracts/image_recognition_request.py
    Define the exact `ocrllm.v1alpha1` image command, ordered image sources,
    DashScope provider/model, languages, board profile, and allowed options.

src/ocrllm/contracts/pdf_recognition_request.py
    Add a one-PDF command only after the direct Python PDF slice proves its
    minimal provider/model/profile and PDF/common options.

src/ocrllm/contracts/recognition_request.py
    Export only the ImageRecognitionRequest | PdfRecognitionRequest type union.
    Add a new concrete request file before extending this union.

src/ocrllm/contracts/source_descriptor.py
    Define one absolute RFC 8089 file URI and canonical image, PDF, audio, or
    video media type. Do not store provider objects or open file handles.

src/ocrllm/contracts/worker_protocol_version.py
    Define the exact `ocrllm.v1alpha1` | `ocrllm.v1alpha2` version union used by
    shared commands and events.

src/ocrllm/contracts/capabilities_command.py
    Define the version, `capabilities` command literal, and request ID.

src/ocrllm/contracts/cancel_command.py
    Define the version, `cancel` command literal, and active recognition ID.

src/ocrllm/contracts/recognition_result.py
    Define protocol_version, request_id, complete/partial status, Markdown,
    source media type, output URI, artifacts, warnings, and JSON-safe metadata.

src/ocrllm/contracts/artifact.py
    Define one final user-meaningful artifact URI, kind, and media type.

src/ocrllm/contracts/progress_event.py
    Define the `progress` event literal, request_id, stage, completed, total,
    and unit.

src/ocrllm/contracts/warning_event.py
    Define request_id, stable warning code, redacted message, and JSON-safe
    redacted details for degraded-but-successful work.

src/ocrllm/contracts/error_event.py
    Define the `error` event literal, nullable request_id, stable error code,
    redacted message, retryable flag, and JSON-safe redacted details.

src/ocrllm/contracts/capability_report.py
    Define one capability status and reason using the fixed four-state
    vocabulary.

src/ocrllm/contracts/accepted_event.py
    Define the `accepted` event literal and active request ID.

src/ocrllm/contracts/capabilities_event.py
    Define the `capabilities` event literal and capability reports.

src/ocrllm/contracts/result_event.py
    Define the `result` event literal and one RecognitionResult payload.

src/ocrllm/contracts/source_fingerprint.py
    Define source URI, byte size, and SHA-256 used to reject stale resume state.

src/ocrllm/contracts/completed_unit.py
    Define one completed page/segment/frame unit, ordered Markdown, artifact
    fingerprints, and JSON-safe metadata.

src/ocrllm/contracts/remote_task.py
    Define provider, task kind, remote task ID, source fingerprint, and exact
    submitted/running/succeeded/failed/cancelled state.

src/ocrllm/contracts/transcript_segment.py
    Define text, start/end seconds, BCP-47 language, confidence, and provider
    segment ID for one ordered segment.

src/ocrllm/contracts/transcription_result.py
    Define complete/partial status, ordered transcript segments, warnings, and
    JSON-safe metadata. It is structured data, not Markdown.

src/ocrllm/contracts/job_state.py
    Define `ocrllm.job.v1`, request fingerprint, processor/version, sources,
    completed units, remote tasks, and optional final Markdown SHA-256.
```

Initial stable error codes:

```text
SOURCE_NOT_FOUND
SOURCE_UNREADABLE
SOURCE_INVALID
SOURCE_TOO_LARGE
UNSUPPORTED_FORMAT
DEPENDENCY_MISSING
CONFIG_MISSING
CONFIG_INVALID
PROVIDER_AUTHENTICATION
PROVIDER_RATE_LIMITED
PROVIDER_QUOTA_EXHAUSTED
PROVIDER_TIMEOUT
PROVIDER_NETWORK
PROVIDER_UNAVAILABLE
PROVIDER_RESPONSE_INVALID
PDF_BACKEND_UNAVAILABLE
PDF_PASSWORD_REQUIRED
PDF_PASSWORD_INVALID
PDF_INVALID
PDF_PAGE_RANGE_INVALID
NO_SPEECH_DETECTED
OUTPUT_EXISTS
OUTPUT_PATH_INVALID
OUTPUT_WRITE_FAILED
RESUME_STATE_INVALID
RESUME_STATE_MISMATCH
CANCELLED
PROTOCOL_UNSUPPORTED
COMMAND_INVALID
WORKER_BUSY
REQUEST_NOT_ACTIVE
```

Processors may add structured redacted details, but callers must branch on the
stable code rather than message text.

The Phase 0 facade split is complete at commit `5018ad0`. Phase 1 builds on
`recognize.py`, `recognize_batch.py`, and `processors/recognize_images.py`; do
not recreate or expand the removed `api.py` or `processors/board.py` stubs.

### Source validation and routing

```text
src/ocrllm/detect_source_type.py
    Map an allowed extension to one canonical media type. Do not open content or
    call providers; the modality validator must confirm the content.

src/ocrllm/validate_source.py
    Enforce existence, regular-file status, readable size limits, and extension
    policy before processor or provider work.

src/ocrllm/validate_same_type_group.py
    Reject mixed groups passed to recognize(). Accept multi-source groups only
    for image recognition and preserve caller order; PDF, audio, and video
    accept exactly one source in their first approved slices.
```

### Image slice

```text
src/ocrllm/imaging/decode_image.py
    Read one caller or snapshot path into a bounded byte buffer.

src/ocrllm/imaging/decode_image_bytes.py
    Decode and validate exactly one bounded image byte buffer through Pillow.

src/ocrllm/imaging/decoded_image_info.py
    Hold only validated image dimensions, pixel count, and decoded format.

src/ocrllm/imaging/snapshot_image_group.py
    Copy an ordered image group into bounded provider-visible snapshots after
    validation. Yield stable paths only for the synchronous provider call, then
    remove them after that call returns. Map snapshot write/cleanup failures to
    typed errors without replacing an already-active typed recognition failure.

src/ocrllm/imaging/normalize_image.py
    Convert only formats the chosen provider cannot consume directly.

src/ocrllm/imaging/resize_image.py
    Enforce measured provider pixel and byte limits while preserving aspect.

src/ocrllm/profiles/build_board_prompt.py
    Build the board-recognition prompt from validated BCP-47 input/output
    languages. Do not call a provider.

src/ocrllm/processors/recognize_images.py
    Preserve ordered multi-image context, apply the selected image profile
    (initially board), call one vision capability, reject empty output, and
    return ProcessorOutput. Never write final output.
```

Do not port automatic crop, perspective correction, contrast, or HEIC behavior
until a failing representative fixture proves it is required. Then extract only
the needed operation into its own named file.

Initial image safety limits are 25 MiB per source, 24,000,000 decoded pixels per
image, 10 images per same-context group, 100 MiB aggregate source bytes, and
64,000,000 aggregate decoded pixels. For the Phase 1 OpenAI-compatible adapter,
read each validated snapshot and construct a MIME-correct Base64 data URL; never
put a local filesystem path in the remote JSON. Each complete data URL is at
most `10,000,000` UTF-8 bytes. The fully serialized provider JSON request,
including every data URL and the prompt, is at most 20 MiB (`20,971,520` bytes).
Validate every group member, complete data URL, and final serialized size before
the first provider call. Decode, normalize, and close images sequentially; never
retain the whole group's decoded pixel buffers. These are fixed version-1 caps,
not caller overrides.

The DashScope adapter also rejects before dispatch when either dimension is at
most 10 pixels, the long-side/short-side ratio exceeds 200:1, the longest side
exceeds `7,680` pixels, or the selected model's pixel/image limits are violated.
For the pinned
`qwen3.7-plus-2026-05-26` baseline with
`vl_high_resolution_images=true`, the initial provider ceiling is `16,777,216`
pixels per image. The repository's 10-image group cap remains the controlling,
stricter quantity limit. Decode and Base64-encode the same bounded byte buffer;
then recompute the final group's `64,000,000` aggregate-pixel cap from those
exact bytes. A caller-path or snapshot replacement must not create a
time-of-check/time-of-use bypass.

The provider receives only validated snapshot paths, not caller-owned paths.
Those paths remain valid until the synchronous provider method returns and are
deleted before `recognize()` returns or writes final output. A provider must not
return while background work still needs a snapshot. An otherwise-successful
cleanup failure is `OUTPUT_WRITE_FAILED`; if another typed failure is already
active, preserve it and attach only redacted cleanup-failure detail.

Phase 0 and Phase 1 accept `.png`, `.jpg`, and `.jpeg` only. Add BMP, WebP, TIFF,
HEIC, or HEIF only after a valid fixture passes decoder, provider, packaging,
and clean-install tests. HEIC/HEIF remains unavailable while no approved decoder
dependency exists.

`decode_image.py` opens with Pillow, reads dimensions, rejects nonpositive or
over-limit dimensions before full decode, runs `verify()`, reopens, and calls
`load()` inside a closed context. Map `UnidentifiedImageError`, truncated input,
and decoder failures to `SOURCE_INVALID`; map `DecompressionBombWarning` and
`DecompressionBombError` to `SOURCE_TOO_LARGE`. Do not change Pillow's global
pixel-limit setting.

### Quality test files

```text
tests/fakes/fake_vision_provider.py
    Return deterministic Markdown for processor and worker tests only.

tests/fixtures/phase1/manifest.json
    Byte-freeze licenses, hashes, languages, dispatches, expected content,
    critical slots, formulas, tables, and ordered anchors.

tests/quality/generators/generate_phase1_fixtures.py
    Regenerate four repo-owned images and byte-check them against the corpus.

tests/quality/load_fixture_manifest.py
    Strictly parse and validate the frozen Phase 1 evidence contract.

tests/quality/verify_fixture_artifacts.py
    Verify every artifact's path, size, hash, license, and corpus budget.

tests/quality/normalize_content_units.py
    Apply only the fixed NFKC, newline, whitespace, and declared-equivalence
    normalization rules.

tests/quality/calculate_language_token_metrics.py
    Calculate required-token recall and content-unit precision per language.

tests/quality/score_critical_slots.py
    Require exact identifiers, numbers, signs, units, names, and dates.

tests/quality/score_formula_signatures.py
    Compare formula identifiers, values, operators, relations, exponents, and
    subscripts.

tests/quality/score_table_cells.py
    Compare normalized cells by row and column coordinate.

tests/quality/score_ordered_anchors.py
    Require unique anchors to appear in source order.

tests/quality/score_recognition_result.py
    Integrate every Phase 1 scorer only after authenticating the supplied
    manifest against a freshly strict-loaded frozen manifest.

tests/quality/assert_quality_thresholds.py
    Apply only the frozen Phase 1 per-fixture and per-language thresholds.

tests/quality/run_phase1_quality.py
    Execute and checkpoint the guarded smoke plus two full Phase 1 runs.
```

These files stay outside `src/ocrllm` and do not add runtime dependencies.
Audio/video WER, CER, and timestamp scorers remain future phase work; do not
misread their quality contracts below as current files.

### Phase 1 evidence runner checkpoint

Commit `fb23d1e` originally froze one 13-call plan: dispatch 0 is the clean-slide smoke,
then run A executes all six manifest dispatches, then run B independently
executes the same six. Both runner and SDK retry counts are zero. A provider,
identity, result-contract, or internal scorer failure aborts without another
call; a scored threshold failure is recorded and the already frozen plan
continues, never retries that fixture, and cannot be hidden by choosing a better
run.

The public live signature is exactly
`(region, base_url, evidence_path, confirm_paid_calls, repository_root)`. Its
real environment, recognizer, clocks, and Git identity reader are closed over
and cannot be injected through that interface. The private simulated entrypoint
accepts fakes for offline tests, records `mode="simulated"` plus every injected
dependency, and can set only `simulated_plan_passed`; it can never set
`phase1_gate_passed`. Even monkeypatching mutable module globals cannot turn
simulated output into live evidence.

At startup the runner verifies repository import origins, the strict byte-frozen
manifest and all artifacts, the code bundle, the clean Git HEAD/index/working
blobs for every relevant file, and `DASHSCOPE_API_KEY`. Before and after each
call it rechecks the applicable manifest, input, code/Git, and credential
invariants; final postflight repeats full artifact and import-origin checks. The
committed direct preflight at full commit
`fb23d1e40d4594ed1da8e244945ae7ccb9568efd` authenticated 98 tracked relevant
files and made no provider/API call. At that checkpoint, the CLI confirmation
guard rejected any value other than 13 before settings or preflight; the recorded `12` check
exited safely, created no evidence, and made no call. An example shared endpoint
used by offline tests is not evidence of the caller's region or `base_url`. V6
keeps those 13 recognition invocations but explicitly makes two provider calls
per recognition; its confirmation guard is 26 and its result metadata plus
summary must report all 26 before GO.

The runner writes an initial checkpoint, a pre-call checkpoint naming the active
attempt and incremented invocation count, and a post-call checkpoint containing
raw Markdown, its byte count/hash, result metadata, elapsed time, and complete
serialized scorer metrics. Credential and full `base_url` values are rejected
from evidence. Each JSON update is written to a temporary file, flushed and
file-`fsync`ed; initial publication uses an exclusive hard link and later
updates use normal atomic `os.replace`. There is no explicit containing-directory
`fsync`, so this is the normal atomic link/replace guarantee, not a promise of
checkpoint persistence across sudden power loss.

Current Phase 1 provider-boundary tests are:

```text
tests/test_validate_source.py
    Hit exact below/at/above source-byte, decoded-pixel, group-count, aggregate
    source-byte, and aggregate-pixel limits.

tests/test_recognize_validation.py
    Prove every rejecting image/group limit stops before provider dispatch.

tests/test_lightweight_import.py
    Keep PIL, openai, and httpx absent after plain public import.

tests/test_dashscope_settings.py
    Prove exact settings types, region/endpoint pairs, and nested copies.

tests/test_dashscope_provider_boundaries.py
    Prove model/key resolution, typed error precedence, Config snapshots,
    metadata, cancellation, and dependency/client boundaries.

tests/test_build_dashscope_image_request.py
    Prove ordered exact-buffer preflight, payload serialization, and all limits.

tests/test_dashscope_adapter.py
    Prove one no-retry raw-response call, strict parsing, cleanup, and redaction.
```

### Provider layer

```text
src/ocrllm/providers/vision_provider.py
    Define the vision capability protocol.

src/ocrllm/providers/short_audio_provider.py
    Define the synchronous short-audio capability protocol in Phase 4.

src/ocrllm/providers/long_audio_provider.py
    Define the submit, poll, and result-fetch lifecycle for resumable long audio
    in Phase 4.

src/ocrllm/providers/resolve_vision_provider.py
    Resolve an injected object or an exact built-in adapter-settings value. Never
    silently switch to a different paid provider.

src/ocrllm/providers/resolved_vision_provider.py
    Hold one resolved callable plus safe provider/model identity metadata.

src/ocrllm/providers/map_injected_provider_error.py
    Convert untrusted injected-provider failures into secret-safe public errors.

src/ocrllm/providers/validate_provider_markdown.py
    Require nonempty non-control-only text from any vision provider.

src/ocrllm/providers/dashscope/provider_settings.py
    Validate immutable routing, optional secret credential, and
    evidence-affecting settings without environment lookup, dependency load, or
    network client.

src/ocrllm/providers/dashscope/resolve_dashscope_credential.py
    Resolve DashScopeSettings.api_key, then DASHSCOPE_API_KEY, and reject Coding
    Plan keys.

src/ocrllm/providers/dashscope/resolve_dashscope_model.py
    Accept only the Phase 1 floating alias or pinned snapshot and choose the
    pinned snapshot when Config.vision_model.name is omitted.

src/ocrllm/providers/dashscope/build_dashscope_image_request.py
    Read exact snapshot bytes, validate provider limits, build ordered Base64
    data URLs plus prompt, and measure the JSON body before dispatch.

src/ocrllm/providers/dashscope/create_dashscope_openai_client.py
    Construct one synchronous OpenAI-compatible client with max_retries=0.

src/ocrllm/providers/dashscope/load_openai.py
    Lazy-load and version-check openai>=2.30,<3 or raise DependencyMissing.

src/ocrllm/providers/dashscope/parse_dashscope_raw_response.py
    Reject provider partial-response headers and parse the raw response safely.

src/ocrllm/providers/dashscope/parse_dashscope_image_response.py
    Require the requested model and one complete non-refusal assistant choice.

src/ocrllm/providers/dashscope/recognize_images.py
    Perform one DashScope vision request and parse one response.

src/ocrllm/providers/dashscope/transcribe_short_audio.py
    Perform one synchronous short-audio request and return TranscriptionResult.

src/ocrllm/providers/dashscope/submit_filetrans.py
    Submit one long-audio FileTrans task and return RemoteTask.

src/ocrllm/providers/dashscope/poll_filetrans.py
    Poll one persisted FileTrans task and return its updated RemoteTask.

src/ocrllm/providers/dashscope/download_filetrans_result.py
    Fetch and validate one terminal TranscriptionResult.

src/ocrllm/providers/dashscope/map_dashscope_error.py
    Map authentication, temporary rate limit, permanent quota/billing, timeout,
    network, service availability, invalid request, and malformed response to
    public errors.
```

Provider model queues and key pools remain NO-GO during provider workflow
completion. They become a later Phase 2A slice only after enabled provider
categories have stable error taxonomies and tests prove the pool policy.

Future provider architecture is recorded here without authorizing it:

- A recognition profile such as `board` describes the task; the execution
  strategy is orthogonal. Phase 2A now authorizes a local OCR strategy without
  treating it as an API provider or a handwriting-specific profile.
- Do not freeze four provider categories now. OpenAI-compatible transport,
  direct provider SDKs, local engines, and subprocess/session tools have
  different contracts and are not a closed current enum. In particular, a
  future Codex session/subprocess adapter cannot require an API key.
- Immutable provider, model, execution, retry, and recognition-preferences
  policies stay separate from a stateful credential pool. Credentials belong
  to adapter settings; never broaden one credential to a scalar-or-tuple field.
- A future credential pool requires an explicit decision covering fair
  selection, cooldown, and provider/model quota and error domains. It remains
  outside the current provider transport/model configuration slice.

Phase 1 provider policy is concrete:

- The first vision adapter uses DashScope's OpenAI-compatible Chat Completions
  API through lazy `openai>=2.30,<3`. Do not add the DashScope SDK to the image
  path.
- For image recognition, `Config.provider` accepts an injected vision-capable
  object or exact `DashScopeSettings` selecting the built-in
  OpenAI-compatible adapter. String provider categories are invalid. `None`
  raises `ConfigError` at resolution; the library never initiates an implicit
  paid request. PDF `text` mode is local and requires no provider settings.
- Built-in `DashScopeSettings` requires explicit `region` and full
  OpenAI-compatible `base_url`. Prefer the
  workspace-dedicated endpoint for that region. Validate the endpoint/region
  pair because API keys are region-specific; never infer a region or endpoint.
  Existing shared DashScope domains are accepted only when the caller explicitly
  selects the matching legacy endpoint.
- `DashScopeSettings` owns `region`, `base_url`, optional secret `api_key`,
  `enable_thinking=False`, `vl_high_resolution_images=True`, and optional
  fixed `standalone_sign_scout_model`. Supported
  workspace regions are `ap-northeast-1`, `ap-southeast-1`, `cn-beijing`,
  `cn-hongkong`, and `eu-central-1`, using exact URL shape
  `https://{workspace-id}.{region}.maas.aliyuncs.com/compatible-mode/v1`.
  Explicit shared compatibility pairs are:

  | Region | Exact shared base URL |
  |---|---|
  | `ap-southeast-1` | `https://dashscope-intl.aliyuncs.com/compatible-mode/v1` |
  | `cn-beijing` | `https://dashscope.aliyuncs.com/compatible-mode/v1` |
  | `cn-hongkong` | `https://cn-hongkong.dashscope.aliyuncs.com/compatible-mode/v1` |
  | `us-east-1` | `https://dashscope-us.aliyuncs.com/compatible-mode/v1` |

  Reject non-HTTPS URLs, ports, credentials, query/fragment text, alternate
  paths, unknown regions, and mismatched region/host pairs.
- Credential order is explicit `DashScopeSettings.api_key`, then
  `DASHSCOPE_API_KEY`, then `ConfigError`. Reject `sk-sp-` Coding Plan
  credentials because they cannot
  authorize this adapter.
- The built-in DashScope adapter uses `Config.vision_model.name` when set and
  otherwise uses the pinned `qwen3.7-plus-2026-05-26` baseline. The exact allowlist is that
  snapshot plus the explicit floating alias `qwen3.7-plus`; every other model is
  `CONFIG_INVALID`. `qwen-vl-max` is legacy and must not be the default. Evidence
  for the pinned snapshot does not transfer to the floating alias. Invalid model
  text is never echoed in a public error message or detail.
- The initial quality request sets `enable_thinking=false` and
  `vl_high_resolution_images=true`. These choices remain subject to corpus
  evidence; changing either invalidates affected live evidence.
- Preserve caller image order, append the board prompt after every image, set
  `temperature=0`, and set `max_completion_tokens=16,384`.
- Default request timeout is 120 seconds.
- Perform no automatic model switch, key rotation, paid-provider fallback, or
  hidden retry in the first adapter.
- Construct the synchronous `OpenAI` client with `max_retries=0`; the SDK's
  built-in retry default is not allowed to create undisclosed extra paid calls.
- Map permission, account suspension, concurrency, quota, content block, and
  invalid provider request separately from authentication, rate, timeout,
  network, unavailability, and malformed response. Inspect safe provider codes
  before generic status mapping. A bounded private message fallback may only
  identify the documented concurrency phrase and is never stored or emitted.
  DashScope rate/concurrency limits are account-scoped; another key in the same
  account is not fresh quota. Provider codes `RequestTimeOut`,
  `InternalError.Timeout`, and `ResponseTimeout` map to retryable
  `PROVIDER_TIMEOUT` before generic 5xx handling. Expose immutable disposition
  evidence but do not perform its action here.
- Add retry/backoff only in a later decision with retry-classification tests and
  cancellation-aware delays.
- Direct-Python cancellation is checked before provider preflight, between
  ordered image preflights, and immediately before dispatch. The synchronous
  adapter does not claim it can interrupt an in-flight HTTP call. Phase 2 adds
  hard cancellation by terminating the isolated worker job process.
- Call `chat.completions.with_raw_response.create` and treat the response as
  complete only when `x-dashscope-partialresponse` is absent or normalizes to
  `false`. Header value `true` or any other value is
  `PROVIDER_RESPONSE_INVALID`.
- Parsed output must report the exact requested model and exactly one choice
  with index 0, role `assistant`, `refusal=None`, and `finish_reason="stop"`.
  Any malformed shape, different model, refusal, non-text content, truncation
  such as `finish_reason="length"`, or final empty/control-only Markdown maps to
  `PROVIDER_RESPONSE_INVALID`. Never publish truncated Markdown as complete or
  partial success.
- Successful image metadata includes `provider`, `model`,
  `prompt_version="board.v3"`, `profile`, `image_count`, `provider_region`,
  `enable_thinking`, and `vl_high_resolution_images`; it never includes a key,
  endpoint credential, request body, or source content.
- Always close a constructed client. If request processing and close both fail,
  preserve the primary typed error and add only the safe boolean detail
  `provider_client_cleanup_failed=true`; a close-only failure is
  `PROVIDER_RESPONSE_INVALID`.

Primary evidence for this policy is Alibaba's [visual-understanding model and
limit reference](https://www.alibabacloud.com/help/en/model-studio/vision-model),
[OpenAI-compatible Chat Completions
reference](https://www.alibabacloud.com/help/en/model-studio/qwen-api-via-openai-chat-completions),
and [region/workspace base URL
reference](https://www.alibabacloud.com/help/en/model-studio/base-url), plus the
OpenAI Python client's [retry configuration](https://github.com/openai/openai-python#retries).

### PDFium slice

```text
src/ocrllm/pdf/require_pdfium.py
    Lazy-import pypdfium2, enforce the tested version range, and raise a typed
    dependency error. Do not open documents.

src/ocrllm/pdf/pdfium_lock.py
    Own the one process-wide lock that serializes every PDFium call.

src/ocrllm/pdf/inspect_pdf.py
    Validate/open one PDF, return JSON-safe page metadata, and close it.

src/ocrllm/pdf/extract_pdf_page_text.py
    Extract one page with get_text_bounded(), normalize it, and close text/page
    objects. Do not use get_text_range(), which cannot represent full Unicode.

src/ocrllm/pdf/calculate_pdf_render_scale.py
    Enforce DPI, longest-side, and total-pixel limits for one page.

src/ocrllm/pdf/render_pdf_page.py
    Render and losslessly encode one bounded page, close bitmap/page/document
    objects, and return one internal rendered-page descriptor.

src/ocrllm/pdf/rendered_pdf_page.py
    Define one temporary PNG path, one-based page index, width, and height. It is
    not a public Artifact and must be deleted after image recognition.

src/ocrllm/pdf/classify_pdf_page.py
    Future auto-mode classifier. Do not create this file until an auto-mode
    fixture corpus and gate are approved.

src/ocrllm/processors/recognize_pdf.py
    Validate page selection, call text extraction or compose the proven image
    processor with the board profile over rendered pages, add stable page
    markers, and return ProcessorOutput. Never write final output.
```

PDF rules:

- The verified optional dependency target is
  `pypdfium2>=5.11.0,<5.12` plus `Pillow>=10.4,<13`.
- CI locks the first implementation trial to pypdfium2 5.11.0 and records the
  bundled PDFium build before widening the range.
- `pypdfium2` imports only inside PDF modules.
- Do not call PDFium concurrently from multiple threads. Use serialized calls
  behind one process-wide lock. Use process-based parallelism only after
  benchmarks justify it; each process renders and saves its own page and returns
  only a path/descriptor, never a full bitmap through multiprocessing.
- Ship the pypdfium2, PDFium, and bundled dependency license notices with every
  binary distribution.
- PDFium's permissive license is the reason it replaces PyMuPDF here, but this
  decision is not blanket legal approval. If the exact wheel's notices/SBOM
  cannot be reproduced in the distributed artifact, PDF packaging is NO-GO.
- Initial internal render limits are 200 DPI, 4096 pixels on the longest side,
  and 16,777,216 rendered pixels per page. They are fixed in the first PDF
  contract; changing them requires boundary-test evidence and a decision update.
- Reject a PDF larger than 100 MiB or more than 500 pages with
  `SOURCE_TOO_LARGE` before rendering or provider calls. These are safety caps,
  not claims that a 500-page recognition job is cheap.
- Version 1 PDF modes are explicit: `text` or `vision`. Do not silently publish
  an `auto` mode before the classifier corpus passes.
- `text` mode fails if a selected page has no usable text unless the caller
  explicitly permits partial results.
- `text` mode preserves PDFium text in page order but does not claim paragraph,
  table, formula, or reading-order reconstruction. Callers requiring those use
  `vision` mode.
- `vision` mode renders every selected page and reuses the image provider path
  with the board profile.
- Start with lossless PNG page artifacts. JPEG remains NO-GO until formula,
  small-text, and handwriting accuracy is compared.
- Calculate render scale exactly as:

  ```python
  scale = min(
      dpi / 72,
      max_side / max(width_points, height_points),
      (max_pixels / (width_points * height_points)) ** 0.5,
  )
  ```
- Reject nonpositive page width or height as `PDF_INVALID` before calculating
  scale.
- Every page begins with `<!-- ocrllm:page index=N -->` in returned Markdown.
- Page indices in the public API are one-based. Internal PDFium indices are
  zero-based and must not leak.
- Check cancellation before opening and between pages. Do not claim that an
  in-process native render can be interrupted safely mid-call.
- Encrypted, malformed, empty, out-of-range, and oversized PDFs have typed
  failures before provider calls.
- Never return `PdfDocument`, `PdfPage`, `PdfTextPage`, `PdfBitmap`, or a PIL
  view backed by a live PDFium buffer across the PDF helper boundary. Copy or
  save the page before closing every native object.
- Direct Python PDF settings are not part of the current `Config`. Introduce
  only settings consumed by the first executable PDF slice. Reconsider the
  earlier arbitrary-page, password, and caller-controlled partial-result ideas
  against legacy's contiguous page range and durable failure markers; do not
  implement them merely because old planning named them.
- Any Phase 3 worker extension must use a new version rather than widening
  `ocrllm.v1alpha1`. Define its option keys only after the Python PDF contract
  passes, then add matching JSON fixtures without altering the frozen image
  fixtures.

### Audio slice

```text
src/ocrllm/media/find_ffmpeg.py
    Locate ffmpeg and ffprobe or raise a typed dependency error.

src/ocrllm/media/probe_media_duration.py
    Return duration from ffprobe with a documented fallback and timeout.

src/ocrllm/media/convert_audio.py
    Convert unsupported provider input to a documented mono/sample-rate format.

src/ocrllm/media/split_audio.py
    Split long audio with explicit overlap and ordered segment metadata.

src/ocrllm/media/merge_transcript_segments.py
    Merge timestamped transcript segments in source order and mark partial gaps.

src/ocrllm/processors/recognize_audio.py
    Orchestrate the short or long provider flow, reject all-failed segments, and
    return the merged transcript in ProcessorOutput. Never write final output.
```

Preserve the legacy distinction between short ASR and resumable long FileTrans,
including persisted remote task IDs. Rewrite the implementation. Do not port the
2,000-line legacy processor, its inheritance, or its failure-text placeholders.
The Phase 4 trial set is WAV/PCM signed 16-bit, MP3/MPEG Layer III, and
M4A/AAC-LC. Do not advertise a format until its licensed fixture passes probe,
conversion, live provider, packaging, and cleanup gates. Hotword extraction is
deferred; `RecognitionResult.hotwords` remains empty in the first audio slice.
Provider adapters return `TranscriptionResult` with structured segments; do not
parse timestamps or task state back out of provider prose or Markdown.

### Video slice

```text
src/ocrllm/media/extract_video_audio.py
    Extract the audio track with ffmpeg and validate the output.

src/ocrllm/media/extract_video_frames.py
    Extract ordered candidate frames with timestamps.

src/ocrllm/media/deduplicate_video_frames.py
    Remove near-identical frames using a tested threshold.

src/ocrllm/media/merge_video_recognition.py
    Merge timestamped visual recognition and transcript streams in source order.

src/ocrllm/processors/recognize_video.py
    Compose the proven image and audio processors. Require the outputs requested
    by the caller, delegate ordered assembly without fabricating paths, and
    return ProcessorOutput. Never write final output.
```

Video does not own generic audio recognition, ffmpeg discovery, image decoding,
or provider retry policy. Video is NO-GO until the image and audio processors
are both GO. The first Phase 5 format is MP4 with H.264 video and optional AAC
audio. Do not advertise another container/codec pair until its own licensed
fixture passes probe, extraction, recognition, packaging, and cleanup gates.

### Output and resume

```text
src/ocrllm/output/build_output_path.py
    Build deterministic, Windows-safe names without overwriting by accident.

src/ocrllm/output/write_markdown_atomically.py
    Atomically write ProcessorOutput.markdown only when output_dir is set. It is
    called by the public facade, never by a processor or provider.

src/ocrllm/output/load_job_state.py
    Load explicit versioned resume state for long jobs.

src/ocrllm/output/save_job_state_atomically.py
    Atomically persist versioned resume state beside caller-selected output.

src/ocrllm/output/delete_job_state.py
    Delete validated state after final output is durable.

src/ocrllm/fingerprint_recognition_request.py
    SHA-256 canonical JSON for sources, processor/version, provider/model,
    languages, profile/mode, selection, and safety settings, excluding secrets,
    output location and cancellation objects.

src/ocrllm/freeze_json_value.py
    Deep-copy JSON mappings to MappingProxyType and arrays to tuples; reject
    unsupported objects and non-finite floats.

src/ocrllm/thaw_json_value.py
    Convert frozen JSON mappings/tuples to fresh dicts/lists for serialization.
```

Do not use package-relative output directories. Do not treat Markdown as the
only state store until task IDs, source hashes, processor version, and requested
phases can be represented and validated. A completed result must name only final
artifacts that exist.

Resume policy is fixed:

- Long processors may call job-state helpers at unit boundaries; only the
  public facade calls the final Markdown writer/result builder.
- `resume=False` is the default. `resume=True` requires `output_dir` and cannot
  be combined with `overwrite=True`.
- State is sibling JSON named `{final_markdown_stem}.ocrllm-state.json`; callers
  do not choose a hidden package/cache path in version 1.
- State version is `ocrllm.job.v1`. It stores source URI/size/SHA-256, canonical
  request fingerprint, processor name/version, ordered completed units, remote
  task IDs, and an optional final Markdown SHA-256. It never stores API keys,
  PDF passwords, environment values, or raw provider request headers.
- Completed-unit Markdown is plaintext beside the caller-selected output. The
  caller owns that directory's permissions. For an encrypted PDF, reopen and
  authenticate the unchanged source with the currently supplied password before
  reading or reusing state; a missing/wrong password fails even when hashes
  match. The request fingerprint stores only `password_supplied=true/false`,
  never the password.
- Save state after every completed page/segment and immediately after receiving
  a remote FileTrans task ID. A resumed run reuses only completed units whose
  source, request, processor, and artifact fingerprints all match.
- Corrupt state raises `RESUME_STATE_INVALID`. Any source/request/processor
  mismatch raises `RESUME_STATE_MISMATCH`; do not silently start over or reuse
  partial data.
- Before final output, save state with the final Markdown SHA-256, atomically
  write the Markdown, then delete state. If a crash leaves both files, matching
  hashes complete without provider work; a mismatch raises
  `RESUME_STATE_MISMATCH`.

Output policy is fixed for the initial image contract:

- `output_dir=None` writes nothing.
- A single image uses `{source_stem}_{profile}.md`.
- An ordered image group uses `{first_stem}_plus_{additional_count}_{profile}.md`.
- A PDF uses `{source_stem}_{pdf_mode}.md` (`text` or `vision`).
- Audio uses `{source_stem}_transcript.md`.
- Video uses `{source_stem}_video.md`.
- If the target exists and neither explicit resume nor `overwrite=True` applies,
  raise `OUTPUT_EXISTS`. Never overwrite or add an unreported suffix silently.
- Normalize the source stem to Unicode NFC, replace ASCII control characters
  and Windows-forbidden `< > : " / \\ | ? *` with `_`, strip trailing spaces and
  dots, use `source` if empty, and cap the stem at 96 Unicode code points.
  Profiles are registered internal ASCII slugs, never raw user filename text.
- An invalid/non-directory output location raises `OUTPUT_PATH_INVALID`.
- Atomic writes use a unique sibling temporary file, UTF-8, flush plus `fsync`,
  then `os.replace`. Remove the temporary file after a failed write and raise
  `OUTPUT_WRITE_FAILED` without reporting a final artifact.

### Electron worker

```text
src/ocrllm/worker/read_jsonl_command.py
    Read exactly one UTF-8 versioned command from stdin.

src/ocrllm/worker/write_jsonl_event.py
    Write accepted, progress, warning, result, or error events to stdout.

src/ocrllm/worker/run_worker_job.py
    Execute one recognition request in an isolated child process and relay its
    events.

src/ocrllm/worker/run_worker_control_loop.py
    Read commands, allow one child job, answer capabilities, and enforce the
    5-second cancellation process-tree kill.

src/ocrllm/worker/__main__.py
    Call the control loop with the production provider resolver. Parse no
    secrets from command-line arguments.

tests/worker_fixture_entrypoint.py
    Call the same control loop with a deterministic fake provider for the Node
    protocol harness. This file is test-only and is not a public provider.
```

Stdout is protocol-only. Diagnostics go to stderr. The Electron renderer never
spawns the worker and never receives provider credentials; the Electron main
process owns both responsibilities.

The initial protocol version is `ocrllm.v1alpha1`. Every stdin and stdout record
is one UTF-8 JSON object followed by `\n`; embedded newlines are JSON-escaped.
The worker accepts only these command shapes:

| `command` | Required fields | Behavior |
|---|---|---|
| `capabilities` | `protocol_version`, `command`, `request_id` | Return capability reports without starting recognition. |
| `recognize` | `protocol_version`, `command`, `request_id`, nonempty ordered `sources`, `provider`, `model`, `input_languages`, `output_language`, `profile`, `options` | Start one isolated recognition job. |
| `cancel` | `protocol_version`, `command`, active recognition `request_id` | Terminate that job's process tree within 5 seconds and emit `CANCELLED`. |

The worker emits only these event shapes:

| `event` | Required fields |
|---|---|
| `capabilities` | `protocol_version`, `event`, `request_id`, `capabilities` |
| `accepted` | `protocol_version`, `event`, `request_id` |
| `progress` | `protocol_version`, `event`, `request_id`, `stage`, `completed`, `total`, `unit` |
| `warning` | `protocol_version`, `event`, `request_id`, `code`, `message`, `details` |
| `result` | `protocol_version`, `event`, `request_id`, `result` |
| `error` | `protocol_version`, `event`, `request_id`, `code`, `message`, `retryable`, `details` |

For `ocrllm.v1alpha1`, `request_id` is a canonical UUID string; every source is
an absolute RFC 8089 `file:` URI with media type `image`; `provider` is exactly
`dashscope`; and `profile` is exactly `board`. The only option keys are:

| Option | Type and default |
|---|---|
| `output_directory_uri` | Absolute `file:` URI or `null`; default `null`. |
| `overwrite` | Boolean; default `false`. |
| `timeout_seconds` | Number in `(0, 600]`; default `120`. |

Missing options use those defaults. Unknown keys fail with `CONFIG_INVALID` and
are never ignored. Provider credentials are absent from commands, arguments,
stdout, and results. The Electron main process passes `DASHSCOPE_API_KEY` only
in the worker environment.

At most one recognition is in flight; a second `recognize` command returns
`WORKER_BUSY`. Cancelling a different ID returns `REQUEST_NOT_ACTIVE`. An
unsupported version returns `PROTOCOL_UNSUPPORTED`. Invalid JSON or an invalid
command returns `COMMAND_INVALID`; `request_id` is `null` only when no valid ID
can be recovered. During Phase 2, invalid/unsupported input errors use the
worker's own `ocrllm.v1alpha1` as the output `protocol_version`. The control loop
continues reading `capabilities` and `cancel` while recognition runs.

## Legacy Migration Matrix

| Legacy area | Preserve | Rewrite in active library | Reject or defer |
|---|---|---|---|
| `processors/board.py` | Ordered image context and nonempty Markdown outcome | `recognize_images.py`, validation, profiles, provider call, ProcessorOutput construction | Processor class, inheritance, implicit output |
| `imaging/preprocess.py` | Only operations proven by failing fixtures | One operation per named file | Wholesale preprocessing pipeline |
| `imaging/pdf_renderer.py` | Page order, selection, bounded render size | Entire renderer with PDFium/pypdfium2 | PyMuPDF/fitz implementation |
| `processors/pdf.py` | Text-versus-vision modes, page markers, resumable long work | Entire processor as composition over PDFium and the image path | RapidOCR in first PDF slice, legacy inheritance, empty success |
| `processors/audio.py` | Short/long split, timestamps, FileTrans task-ID resume | Probe, convert, split, submit, poll, merge as separate files | Failure text presented as transcript, processor class |
| `processors/video_pipeline.py` | Ordered phase semantics and timestamped frames | Composition over image/audio/media helpers | Fabricated artifact paths, success with missing required phase |
| `core/llm_client.py` | Provider capability concepts and typed quota intent | Small provider adapters and public error mapping | Monolithic client, global fallback policy, broad catches |
| incremental writer/checkpoints | Resume after interruption and atomic writes | Explicit versioned job state and atomic output helpers | Package-hidden state and unverified Markdown-only checkpoints |
| `api/server.py` | Submit/status/cancel concepts as product research | A future separately authorized service | Current server, wildcard CORS, arbitrary host paths, in-memory jobs |
| GUI, CLI launchers, social processors | Nothing required by core recognition | Nothing | Keep in `legacy_app` only |
| Codex and Google modes | Behavior reference only | Future optional adapters after a real gate is approved | Phase 1 implementation |

Migration means reusing a tested behavior statement and fixture. It never means
copying a legacy file and renaming imports.

## Recognition Quality Evidence

Commit `e328253` provides the licensed Phase 1 recognition corpus, deterministic
generators, exact scorers, and integrated manifest-authenticated live-scoring
gate. Its byte-frozen manifest is `35,400` bytes with SHA-256
`f0df9e7cd1dab282bec73a75717af150ecf34b3cd04567a2bef300b38a39df42`.
The 20 authenticated artifacts include 5 images and total `17,914,515` bytes,
leaving `8,299,885` bytes below the 25 MiB limit. The pinned full suite passed
`554` tests, the generator byte-identity check passed, and `compileall` passed.
The integrated scorer
strict-loads the frozen manifest again, requires exact manifest equality, and
fails closed for non-applicable score channels before it can apply thresholds.
The guarded evidence runner is committed separately at `fb23d1e`; its offline
fake/evidence tests pass without a provider/API call.

That offline evidence does not make image recognition `available`. The first
live gate completed on 2026-07-11, but the smoke and both independently
dispatched full-corpus runs failed.

> **Superseded 2026-08-18.** The NO-GO statement that stood here described the
> first live gate only. Phase 1 reached GO on the v17 gate; see the top of this
> file and `docs/ACTIVE_STATE_AND_RULES.md`. That GO carries one qualification:
> the gate's false-success guard cannot detect provider refusal text (defect
> D1), so Phase 1 quality conclusions must be re-confirmed after D1 is repaired.

Preserve the frozen v1 evidence and do not lower or reinterpret its thresholds.
PDFium remains only a backend feasibility spike; PDF, audio, and video
recognition remain unavailable under their later gates.

The user-supplied screenshots currently present under `docs/` are local,
supplemental, non-redistributable, and remain untracked. Keep them uncommitted.
They may support manual inspection but cannot be scored gate fixtures, modify
thresholds, or supplement the committed licensed Phase 1 corpus in pass/fail
evidence.

Rules for every recognition-quality gate:

- Keep scorers and fixtures under root `tests/`; never modify or import legacy
  tests. The committed corpus is at most 25 MiB. Generate long audio and
  synthetic video locally from committed licensed components.
- Before a live run, commit a manifest containing fixture ID, SHA-256, source or
  deterministic generator, SPDX license or explicit repo-owned permission,
  redistribution status, BCP-47 languages, expected content units, critical
  values, and expected timestamps. Do not use private legacy outputs or
  unverified downloaded course material.
- Normalize scorer input with Unicode NFKC, normalized line endings, and
  collapsed whitespace. Case-fold only fields declared case-insensitive. Never
  discard digits, decimal points, signs, relations, units, exponents, or
  subscripts. Declare equivalent forms such as `×` and `\times` before a run.
- `required_token_recall = matched_expected_tokens / expected_tokens`. Critical
  identifiers, numbers, signs, units, dates, and names require accuracy `1.00`.
- `content_unit_precision = matched_expected_units / recognized_scored_units`.
  The manifest may exclude neutral Markdown scaffolding declared before the
  run, but not arbitrary explanatory prose added after seeing output. Any
  unreferenced identifier, number, sign, relation, unit, date, table data cell,
  or formula term is a critical false insertion and fails the fixture.
- Formula signatures compare identifiers, numbers, operators, relations,
  exponents, and subscripts against predeclared equivalents. Table scoring uses
  normalized `(row, column)` cells; a correct value in the wrong cell fails.
- Latin speech uses conventional word error rate. CJK speech uses character
  error rate. Report each language independently. Timestamp error is absolute
  recognized-versus-reference boundary error; report median and maximum.
- Thresholds apply per fixture and per language. A corpus average cannot hide a
  failed handwriting, formula, table, or language fixture. Scorer unit tests
  must deliberately alter digits, signs, cell coordinates, order, and
  timestamps and prove those outputs fail.
- Offline fake-provider tests prove validation, routing, scoring, ordering,
  errors, and artifacts, but not recognition. One live smoke proves auth,
  transport, parsing, and nonempty output, but permits `experimental` at most.
  `available` requires two independently dispatched full-corpus live runs, and
  every fixture must pass in both runs. Do not retry only failed fixtures or
  select the better run.
- Record hashes, provider/model, request configuration, prompt/profile version,
  dependency versions, UTC time, elapsed time, and every metric. Never record
  secrets. A provider, model, prompt, preprocessing, render, segmentation, or
  frame-cadence change invalidates affected live evidence.
- Never use another LLM as the pass/fail judge. A threshold failure is NO-GO;
  fix the implementation or explicitly narrow product scope instead of lowering
  a threshold after seeing the output.

### Phase 1 image quality corpus

Checkpoint `e328253` commits the required five fixtures: a synthetic
English/Simplified-Chinese slide with at least 50 scored text units and 8
critical slots; a deterministic perspective, glare, and JPEG derivative; a
CC0/repo-owned handwritten board with at least 25 units and 5 critical slots; a
synthetic board with at least 10 formulas; and a synthetic table with at least
20 data cells, full headers, and 5 critical numeric cells. The frozen dispatch
plan also scores one ordered two-image request with unique first/last anchors.

Both full live runs must meet all of these:

- Printed-slide token recall is at least `0.95` and content-unit precision at
  least `0.90`; handwriting recall is at least `0.85` and precision at least
  `0.85`; critical-slot accuracy is `1.00` on every fixture.
- Formula-signature accuracy is at least `0.90`, with every equality,
  inequality, sign, exponent, subscript, and critical numeric value correct;
  formula content-unit precision is at least `0.90`.
- Table cell accuracy by coordinate is at least `0.95`; all row/column headers
  and critical numeric cells are exact, with no unexpected data cell and no
  row/column transposition.
- The ordered request contains all unique anchors and their first appearances
  follow source order. Markdown is nonempty, but prose/whitespace is not compared
  byte-for-byte.

These results authorize only the tested provider, model, profile, languages,
and fixture classes. They do not prove general handwriting, formula, table, or
language accuracy.

### Phase 3 PDF quality corpus

Keep separate capability evidence for `pdf.text` and `pdf.vision`. Use a
deterministic selected/unselected-page text PDF with at least 100 Latin tokens,
100 CJK characters, supplementary-Unicode sentinels, rotation, and crop boxes;
the mixed text/raster PDF; and a vision PDF generated from the Phase 1 printed,
handwriting, formula, and table fixtures. Encrypted, malformed, empty, and
oversized fixtures are functional failures, not quality-score inputs.

Text-mode acceptance requires token recall at least `0.99` on every selected
text page and content-unit precision at least `0.99`; exact critical values and
Unicode sentinels; one ordered one-based page marker per selected page; no
unexpected critical insertion or anchor from an unselected page; and identical
content units on repeated runs with the pinned PDFium build. A raster-only page
must fail or be named in an explicitly requested partial result. Text mode does
not claim semantic formula/table reconstruction or human reading order.

Vision-mode acceptance requires each page to pass the matching Phase 1 absolute
threshold and score no more than `0.05` below the corresponding direct-image
score from the same run. Critical values remain exact; markers, anchors, and
sections remain in page order. One live smoke and two independent full vision
PDF runs must pass, recording render limits, PDFium build, provider, and model.

### Phase 4 audio quality corpus

Use redistributable real `en-US`, `zh-CN`, and code-switching clips totaling at
most 180 seconds, with at least 100 English words, 150 Chinese characters, and
12 human-checked utterance boundaries. Derive long audio by concatenating the
licensed clips with one-second silences and unique spoken segment IDs. Add
silence and corrupt fixtures for failure behavior.

Both full live runs must meet all of these:

- English WER and Chinese CER are each at most `0.15`; code-switch Latin WER and
  CJK CER are each at most `0.20`; names, numbers, units, and segment IDs are
  exact.
- Short-audio timestamp median error is at most `0.75 s` and maximum `1.50 s`.
  Long-audio WER/CER is at most `0.20`, timestamp median at most `1.00 s`, and
  maximum `2.00 s`.
- Every long-audio segment ID occurs exactly once in order. Partial results name
  missing segments; all-failed input is an error. Silence returns
  `NO_SPEECH_DETECTED`, never invented text or empty success.
- One short live smoke and one FileTrans live smoke pass. If the provider cannot
  supply the required timestamp granularity, timestamp-preserving audio is
  NO-GO; do not fabricate timestamps from order.

### Phase 5 video quality corpus

Generate a deterministic 36-second 1280x720 MP4 with three 12-second H.264
slides, hard cuts, unique slide IDs, scored text, a formula, a table, and six
timestamped licensed utterances. Add one redistributable 60-90 second lecture
excerpt with at least three annotated visual changes, 30 visual content units,
100 spoken words or 150 CJK characters, one formula/table, and eight timeline
events.

With a fixed two-second cadence, the synthetic clip must represent all three
slides, remove duplicates, preserve slide/utterance IDs exactly once in order,
and pass the Phase 1 visual plus Phase 4 audio thresholds. Visual-event error is
at most `2.00 s`; merged-event median is at most `1.00 s` and maximum `2.00 s`.

Both independent real-video live runs require visual token recall at least
`0.90`; formula/table accuracy at least `0.90`; exact critical values and
headers; English WER or CJK CER at most `0.20`; every annotated stable scene;
selected-frame precision at least `0.80`; exact event order; timestamp median at
most `1.00 s` and maximum `2.00 s`; and both requested streams plus final
existing artifacts. Cancellation/resume tests are separate and cannot count as
completed quality evidence.

## Go Gates By Phase

Only one phase may be active at a time.

Capability status and phase advancement are separate decisions:

- An atomic capability becomes `available` when its own implementation,
  packaging, deterministic, and live-quality subgate passes. It does not wait
  for unrelated optional formats in the same phase.
- A phase advances only when every mandatory capability below passes plus every
  cross-cutting bullet in that phase. A phase may remain active while one
  capability is already available.
- Phase 1 mandatory capabilities are `image.board.png`, `image.board.jpeg`, and
  `provider.dashscope.vision`. Phase 2 requires `worker.jsonl.v1alpha1`.
- Phase 3 requires `pdf.text`, `pdf.vision`, `pdf.text.resume`,
  `pdf.vision.resume`, and `worker.jsonl.v1alpha2`; track each status separately
  even though all are mandatory for phase advance.
- Phase 4 requires the WAV/PCM-S16 short and long capabilities plus
  `provider.dashscope.audio-short` and `provider.dashscope.filetrans`. MP3 and
  M4A short/long capabilities are optional atomic subgates; a failure leaves
  only that exact name unavailable and does not block Phase 5.
- Phase 5 requires both `video.mp4-h264` and `video.mp4-h264-aac`.
- Phase 0 is a contract gate and makes no recognition capability available.

### Phase 0: Contract honesty -- GO at `5018ad0`

GO when all are true:

- `ocrllm[image]` installs `Pillow>=10.4,<13`; Pillow is imported lazily only
  when validating/decoding an image.
- Missing, unreadable, empty, oversized, unsupported, and invalid image inputs
  fail before provider invocation.
- Empty provider output fails.
- Provider exceptions are typed and secret-safe.
- Config repr/error/result tests use unique sentinels for provider object, API
  key, PDF password, and provider `extra`; no sentinel appears in output. Event
  sentinel proof is N/A in Phase 0 because event DTOs do not exist; it begins
  with the Phase 2 event contracts.
- `RecognitionResult` metadata is JSON-safe and immutable to callers. Tests
  mutate the caller's original nested dict/list and attempt mutation through the
  result; neither can change stored state.
- Result/source tests use canonical media type `image`; `board` appears only as
  a recognition profile.
- Output collision policy is explicit and tested.
- Empty PDF, audio, video, and all extras are removed from package metadata.
- The isolated base wheel/target and fresh-process import probes pass every Base
  numeric budget in `Dependency Profiles` on both recorded Python versions.

GO is recorded by the exact clean evidence in `Current Truth`. Regress Phase 0
to NO-GO if any condition above stops passing.

### Phase 1: Real board/image -- GO

GO when all are true:

- Offline tests use valid PNG/JPEG files, not arbitrary bytes.
- Tests hit one-below/at/one-above every per-image, aggregate-source,
  aggregate-pixel, group-count, complete-data-URL, and serialized-request cap and
  prove rejection occurs before provider invocation. DashScope tests also cover
  both dimensions around the greater-than-10-pixel minimum, the 200:1 aspect
  ratio, `7,680`-pixel longest side, selected model's pixel limit, and final
  exact-buffer aggregate-pixel recheck.
- A committed, licensed five-class corpus contains the handwriting, projected
  slide, mixed text/formula, table, and ordered multi-image fixtures. Local user
  screenshots remain untracked, supplemental, and uncommitted.
- One lazy real provider adapter passes authentication, quota, timeout,
  temporary-rate-limit, unavailable-service, malformed/truncated response,
  pre-dispatch cancellation, endpoint/region validation, Config mutation,
  exact-model/raw-header parsing, client-cleanup precedence, metadata, and
  redaction tests. It constructs `OpenAI(max_retries=0)`; its synchronous
  in-flight call is documented as non-interruptible. Injected providers keep
  caller Config identity; the built-in adapter uses a freshly validated isolated
  copy.
- One live feasibility smoke returns nonempty structured Markdown for the clean
  slide; this permits `experimental` at most.
- The committed Phase 1 scorer rejects its deliberate corruptions, and two
  independently dispatched full-corpus runs pass every image threshold in
  `Recognition Quality Evidence` without per-fixture retries. Both runs use the
  pinned `qwen3.7-plus-2026-05-26`, `enable_thinking=false`, and
  `vl_high_resolution_images=true`, unless a replacement configuration is
  explicitly decided before collecting new evidence. Truncation fails the run.
- A committed evidence runner passes no-network tests, authenticates the frozen
  manifest and artifacts before dispatch, writes evidence atomically, and
  performs exactly one clean-slide smoke followed by two independent complete
  six-dispatch runs. Any call failure invalidates its complete run; it never
  retries only a failed fixture.
- Plain `import ocrllm` does not import Pillow, the provider SDK/client, or
  transitive `httpx`.
- Clean Image and Image + DashScope installs pass the 25 MiB and 64 MiB profile
  budgets.

Status after offline checkpoint `e328253`, packaging hotfix `3414f47`, runner
checkpoint `fb23d1e`, and the exact boundary completion: the corpus, generators,
artifact authentication, scorers, deliberate-corruption tests, guarded evidence
runner, provider boundary, lazy import, and clean profile work are integrated.
The pinned full suite reports `574 passed`; generator bytes and `compileall`
pass, with no provider/API call. The user-confirmed Beijing region/endpoint gate
is satisfied. The first 13-call live plan completed with both full runs failing;
Phase 1 remains **NO-GO**. See
`phase1_live_quality_result_2026-07-11.md` for the immutable evidence identity,
per-dispatch result, and versioned-correction decision.

The historical `board.v2` correction was implemented without changing the v1
evidence. It declares the labeled-formula grammar and exact handwriting
spelling/case in the prompt. A separate fail-closed normalizer canonicalizes
only inline relation math, missing-colon labeled formulas, strict paired formula
tables, slanted relation commands, and standalone horizontal rules. Diagnostic
application to the preserved raw output makes the smoke and all non-handwriting
dispatches pass; both handwriting dispatches still fail the same seven gates.
This diagnosis is not replacement live evidence and authorizes no paid call.

Clean package proof for the versioned correction is bound to full commit
`9dc4e7a8d9f113c1ea001105335829494086d003`. Its wheel is 52,602 bytes with
SHA-256
`8ce3a51f2367bdfa3255f8ca23f1b95fd46176e728edec3ef4369da1c626f385`;
the isolated no-deps target is 237,251 bytes, with zero base requirements and no
native payload. The origin-bound 30-sample Python 3.10 and 3.13 import probes
pass all wall/CPU budgets. Image adds 15,918,041 bytes and passes generated-PNG
recognition. Image + DashScope adds 40,837,813 bytes, loads OpenAI 2.45.0, and
constructs/closes the real client using the Beijing settings without HTTP.
These result-recording edits do not change packaged inputs.

The first fixed v2 live gate completed at full commit
`94d5187ff8718f2683f67e4c5f75e95c3a9d9070`. All 13 zero-retry provider calls
succeeded and both full runs completed, but zero runs passed. Evidence SHA-256
is `03275cf5922a46dd59fc75e4ab6dc6499e3aeea973190f1d3a6f48b0c556df0b`.
Projected slide, formula board, and calibration table passed twice. Printed and
ordered requests were rejected for U+2A7E `⩾`; handwriting was rejected for
line-leading U+2192 diagram connectors. Preserve v2 unchanged. A separately
versioned correction may normalize only those content-preserving typography and
layout forms, with corruption tests that keep inline arrows, wrong relations,
and wrong values failing. Phase 1 remains NO-GO.

The separately versioned `board.v3` / `labeled-latex-restricted.v3`
correction is implemented. It declares only U+2A7E/U+2A7D relation typography
and line-leading U+2192 diagram connectors as presentation equivalents. Inline
arrows, wrong relations, and wrong values remain failures. The full suite
passes `574` tests; generated fixtures and compilation pass. Diagnostic scoring
of the immutable v2 output passes every non-handwriting dispatch, while both
handwriting dispatches retain their original seven quality failures. V3 has no
live evidence yet and Phase 1 remains NO-GO.

Exploratory evidence after v2 is recorded in
`phase1_exploratory_robustness_2026-07-11.md`; the source audit and correction
are in `phase1_unified_board_handwriting_debug_2026-07-11.md`. The earlier split
recommendation is withdrawn. The fixture had corrected the source's literal
`Enzymens`, omitted `R-DNA / Replasmid`, over-constrained cursive case, and
penalized genuine faint labels. Crop, legacy-prompt, and high-resolution
controls did not change the disputed readings; thinking mode captured the one
genuinely missing second `+`.

Keep one `board` capability. `board.v4` pins thinking mode and source-corrected
required/optional truth without lowering any threshold or adding an ensemble.
Its isolated suite passes 583 tests, fixture bytes are identical, and
compilation passes. Fresh repeated v4 live evidence is still required, so Phase
1 remains NO-GO. The Qwen3.5-OCR signed-URL result remains rejected from the
public contract.

V4 attempt 1 then started from clean commit `a4fc418` and made one smoke call.
DashScope returned retryable HTTP 500 `internal_server_error`; the runner
aborted as `PROVIDER_UNAVAILABLE` with zero full runs. Preserve the 27,245-byte
evidence at
`evidence/phase1/phase1-quality-v4-2026-07-11-cn-beijing.json` (SHA-256
`49e5a3981d13137c5a8ca543b96290bf3b30595ed5cd6d19ca58362c19134015`).
It is transport evidence only. A new attempt must use a new complete plan and
new path.

V4 attempt 2 then invoked seven calls from clean commit `7889244`. Smoke and
all five single fixtures returned, and every non-handwriting single passed.
Handwriting scored 29/30 recall, 33/40 precision, 5/6 critical tokens, and 10/10
critical slots: the center `+` was genuinely missing, while two line-leading
ASCII `->` connectors produced four false critical insertions. The run-A
ordered request timed out and aborted before run B. Preserve the 57,929-byte
evidence at
`evidence/phase1/phase1-quality-v4-attempt2-2026-07-11-cn-beijing.json`
(SHA-256
`936edd25c72d3d58f0d70fed4621c603ced023eca572901a8cf773d62635cc6e`).
Accepting line-leading ASCII connectors requires a versioned corruption-tested
normalizer change; the missing `+` remains a workflow blocker.

That correction is implemented as `board.v5`. Its generic region-verification
instruction captured both standalone plus signs in two targeted atomic-output
calls. The scorer now declares only line-leading ASCII `->` as the observed
layout equivalent and keeps inline arrows visible. Source reinspection adds a
second real `RG` and the visible `OR` label to optional precision truth; guessed
sequence fragments remain penalized. Both targeted outputs pass v5 with 30/30
required recall, 6/6 critical tokens, 10/10 slots, and zero unexpected critical
tokens. The isolated suite passes 588 tests; fixture generation, compilation,
and changed-file Ruff checks pass. Fresh repeated v5 gate evidence is required.

The complete v5 gate then made all 13 calls with zero provider failures. Both
full runs completed; run B passed all six dispatches. Run A failed only
handwriting despite 30/30 recall, 38/40 precision, 6/6 critical tokens, and
10/10 slots: Qwen hallucinated `111110` from six plasmid hatch strokes. Preserve
the 95,483-byte evidence at
`evidence/phase1/phase1-quality-v5-2026-07-11-cn-beijing.json` (SHA-256
`0ceb74a7f05ed2ca5cbcac8eb3eb1c340dfac4bf43ceb84e6883cbe4c40e2343`).
Do not accept the digits or weaken the hard gate. Test a generic hatch/fill/
texture exclusion while keeping one `board` capability.

Post-v5 diagnostics reject prompt-only, crop, glyph-count, and seed-tuning
paths. Four explicit seeds all reproducibly missed the center `+`. Three
readable draft-to-review trials passed, including repair of one failing draft;
two actual production blockquote-framed reviews also passed. JSON-string review
framing failed and is not used. See
`phase1_v6_review_workflow_debug_2026-07-11.md` for all 28 calls.

`board.v6` adds an exact immutable `RecognitionPreferences` object. Review is
off by default; `review_passes=1` makes one additional same-provider/same-model
call, never fallback or best-of-N. Only reviewed Markdown is returned/written,
and review failure fails the request. Metadata records both passes and provider
calls. The v6 gate is 13 ordered recognition invocations and 26 provider calls,
with 26 required in evidence before GO. The isolated suite passes 599 tests;
fixture generation, compilation, Ruff, and diff checks pass. Fresh v6 evidence
is still required.

The complete v6 gate then returned all 13 recognitions and 26 provider calls.
Both full runs completed; run A passed. Handwriting passed in both runs. Run B
failed only because review changed visible lowercase `s_4` to uppercase `S_4`
in F04; the formula hard gate correctly rejected the unexpected atom. Preserve
the 97,150-byte evidence at
`evidence/phase1/phase1-quality-v6-2026-07-11-cn-beijing.json` (SHA-256
`bc256bfbdc73f7d5f80806eb95767d4e68f17cb512f76c9e6daaba5278504707`).
V7 may make review conservative about exact draft identifiers/case; it must not
weaken formula truth or handwriting critical symbols.

### Phase 2: JSON contract and Electron worker

GO when all are true:

- Frozen JSON fixtures cover all three commands and all six event shapes,
  including literals, nullable invalid-command request IDs, defaults, unknown
  option rejection, and the fallback protocol version.
- A Node harness launches the worker without a shell and validates every stdout
  line. Offline schema/result tests launch `tests/worker_fixture_entrypoint.py`;
  one opt-in live smoke launches `python -m ocrllm.worker` with DashScope.
- Chinese, emoji, spaces, and long Windows paths round-trip.
- Cancellation stops provider and child media processes within the declared
  5-second grace by terminating the isolated recognition job process tree. The
  test fails if the job or any descendant remains alive after 5 seconds.
- Phase 2 is development-only and requires an explicitly configured Python
  executable. Do not claim end-user Electron compatibility until the Phase 6
  clean-machine packaged-worker gate passes.

Phase 2 checkpoint 1 freezes all three v1alpha1 command DTOs and their strict
JSON parser/serializer. The frozen fixture covers `capabilities`, `recognize`,
and `cancel`; exact defaults, duplicate keys, non-finite numbers, canonical
UUID/file URIs, languages, unknown fields/options, and secret-safe failures have
direct boundary tests. The direct-Python Phase 1 result remains unchanged.
Event DTOs, the wire-result adapter, worker I/O/control loop, cancellation, Node
harness, and live smoke remain required, so Phase 2 is not GO. See
`phase2_worker_command_contract_2026-07-11.md`.

Phase 2 checkpoint 2 freezes the six event DTOs and event JSONL fixture. It
removes duplicated version/request identity from the nested result payload,
adapts the direct Phase 1 result explicitly, rejects untyped assets, requires an
existing output file before advertising its URI, and reuses recursive detail
redaction. All 51 command/event tests and the 763-test full suite pass. Worker
I/O, process isolation/control, cancellation, Node harness, and live smoke still
remain; Phase 2 is not GO. See
`phase2_worker_event_contract_2026-07-11.md`.

Phase 2 checkpoint 3 implements the bounded binary JSONL reader, sole compact
UTF-8 event writer, and typed error-event conversion. Exact-limit, oversize
drain, invalid UTF-8, incomplete record, partial write, flush, embedded newline,
request-ID recovery, retryability, and redaction tests pass. The full suite
passes 778. There is still no process/control loop, cancellation, Node harness,
or live smoke; Phase 2 is not GO. See
`phase2_worker_jsonl_io_2026-07-11.md`.

Phase 2 checkpoint 4 implements the public atomic capability registry and a
control loop over an injected nonblocking job-manager protocol. Zero-network
status, exact v17 versus experimental workflow, invalid-record recovery,
typed/internal errors, concurrent partial writes, EOF close, and real subprocess
JSON-only/Unicode/fallback behavior pass. The full suite passes 794. The real
child manager, five-second process-tree cancellation, production entrypoint,
Node harness, and live smoke remain; Phase 2 is not GO. See
`phase2_capability_control_loop_2026-07-12.md`.

Phase 2 checkpoint 5 implements a spawned one-job manager and proves matching
cancel/EOF cleanup terminate a real child plus grandchild within five seconds.
Commands and events cross spawn/pipe only as canonical JSON-compatible values;
both sides strictly reconstruct immutable DTOs. Busy, wrong-ID, typed/internal,
mismatched-event, missing-terminal, and bounded-event tests pass. The full suite
passes 807. Production recognition adaptation, module entrypoint, Node harness,
and live smoke remain; Phase 2 is not GO. See
`phase2_isolated_job_manager_2026-07-12.md`.

Phase 2 checkpoint 6 implements production recognition adaptation by reusing
the public facade exactly once per ordered image group. It decodes strict file
URIs and builds the credential-free Beijing v17 `board` configuration. It adds
no handwriting branch, alternate prompt, retry, or fallback. Fourteen focused
tests and the 821-test full suite pass. The module entrypoint, Node harness, and
live smoke remain; Phase 2 is not GO. See
`phase2_production_image_job_2026-07-12.md`.

Phase 2 checkpoint 7 implements the production module entrypoint. It composes
standard streams, the control loop, isolated manager, and unified image job
without credential CLI arguments. Real no-key capabilities and spawned-child
source-failure subprocess tests pass with JSON-only stdout; diagnostics contain
only exception types. The full suite passes 824. The Node harness and live smoke
remain; Phase 2 is not GO. See
`phase2_production_worker_entrypoint_2026-07-12.md`.

Phase 2 checkpoint 8 implements a shell-free Node harness and independent strict
validation of every stdout line. Fixture JSON and long Unicode paths round-trip;
real child-plus-grandchild cancellation completes inside the five-second
contract and proves the descendant PID is gone. The full suite passes 826. The
opt-in Beijing live production-worker smoke remains; Phase 2 is not GO. See
`phase2_node_worker_harness_2026-07-12.md`.

Phase 2 checkpoint 9 implements and passes the opt-in Beijing live production
worker scenario. Two typed timeouts are recorded without automatic retry; the
final independent job validates `accepted`, both progress events, and a complete
result from the pinned four-call unified `board` workflow. Private input and
recognized Markdown are not redistributed. The clean checkpoint proof passes.
Every Phase 2 condition above is satisfied, so Phase 2 is **GO** and public
`worker.jsonl.v1alpha1` status is `available`. This means the development worker
with an explicitly configured Python executable; packaged Electron compatibility
remains gated in Phase 6. The formal GO commit is `2db456a` and its clean
Git-archive proof passes. See
`phase2_live_worker_result_2026-07-12.md`.

### Phase 2A: Image library completion

The order is mandatory: local OCR, provider workflow configuration, stable
provider error taxonomies and credential pools, then image resume. The active
local-OCR GO gates and do-not-do rules are frozen in
`image_library_completion_decision_2026-07-12.md`. PDF/audio/video remain
unsupported and Phase 3 does not start until Phase 2A is complete or a new
explicit decision changes the order.

Phase 2A checkpoint 1 implements the local-OCR direct facade, maintained lazy
RapidOCR adapter, typed errors, optional extra, deterministic tests, and real
offline generated/private-input probes. The base suite passes 870 tests with
one optional-profile skip. Committed clean-wheel and fresh `ocr`-extra gates
pass; `image.ocr.rapidocr` is `available`. See
`local_ocr_implementation_checkpoint_2026-07-12.md`.

Phase 2A checkpoint 2 implements immutable `RecognitionExecutionPolicy`, one
shared hard image-group limit, pre-provider configured-limit rejection,
bounded ordered `recognize_batch()` concurrency, and monotonic all-provider-call
cadence. Parallel failure prevents waiting calls from reaching the provider.
The pinned full suite, fixture identity, static checks, and clean wheel/import
budgets pass. Adapter-owned provider/model configuration follows; pools and
resume remain later gates. See
`phase2a_recognition_execution_policy_2026-07-12.md`.

Phase 2A checkpoint 3 makes adapter-owned configuration the only pre-1.0
built-in shape. Exact `DashScopeSettings` selects the current adapter and owns
its optional secret credential; exact `VisionModelSettings` owns model identity
and a stricter image cap. String categories plus duplicated Config key/model/
DashScope fields are removed. The worker wire format is unchanged. The
912-test pinned suite, fixture identity, static/lazy checks, clean wheel, and
fresh installed mock-transport adapter request pass. Provider error disposition
follows; pools and resume stay later gates. See
`provider_workflow_configuration_checkpoint_2026-07-12.md`.

Phase 2A checkpoint 4 adds stable permission, account-suspension, concurrency,
invalid-request, and content-block errors plus immutable
`ProviderErrorDisposition`. DashScope maps documented provider-code precedence
and safe account/model/credential/request/provider scopes; injected providers
and the unchanged worker error envelope accept every new code. The 960-test
pinned suite, fixtures, static/lazy checks, and a clean installed mapping proof
pass. Credential scheduling is now active; no retry runtime is authorized. See
`provider_error_disposition_checkpoint_2026-07-12.md`.

Phase 2A checkpoint 5 implements the separate stateful DashScope credential
scheduler referenced by immutable adapter settings. Deterministic least-loaded
rotation, per-key concurrency caps, bounded cancellation-aware waits,
credential/model/account/provider health state, explicit recovery, secret-free
reports, and primary/scout sharing pass. The adapter never switches credentials
inside a failed call. The 975-test pinned suite, fixture identity, static/lazy
gates, and exact pushed clean-wheel installed probe pass. The first archive
attempt exposed an ignored validator source and commit `a84bfb2` repairs it with
a narrow source exception while preserving the general secret rule. Image
resume follows; no retry runtime is authorized. See
`dashscope_credential_pool_checkpoint_2026-07-12.md`.

Phase 2A checkpoint 6 implements versioned sibling state for one completed
image group. Exact built-in DashScope and local OCR interruption/resume paths
reuse with zero repeated calls; source/order/request/processor and final output
identity fail closed, while credentials and pool state are excluded. The
987-test pinned suite, fixture/static/lazy checks, and exact pushed clean-wheel
installed resume probe pass. Phase 2A is **GO**. The user's bounded current
scope excludes PDF/audio/video/UI, so no later phase is activated. See
`image_resume_checkpoint_2026-07-12.md`.

### Phase 3: PDFium PDF

GO when all are true:

- `ocrllm[pdf-text]` installs pypdfium2 without Pillow;
  `ocrllm[pdf-vision]` installs pypdfium2 plus Pillow.
- The first reproducible CI lock is pypdfium2 5.11.0 and Pillow 12.2.0.
- The full backend fixture suite passes in clean Windows AMD64 CPython 3.10 and
  3.13 environments. A passing 3.13 spike does not waive the 3.10 gate.
- A clean environment can open, text-extract, and render with PDFium.
- Fixtures cover text-layer, image-only scan, formula-heavy, mixed-language,
  malformed, empty, and out-of-range selection cases.
- Fixtures also cover CJK plus supplementary Unicode, rotation, crop boxes,
  transparency, and a huge-page pixel limit. Add encrypted/password fixtures
  only if encrypted-PDF support is approved for that slice.
- The first slice must define and test mixed text/scanned failure behavior.
  Do not add caller-controlled partial success unless a real product need is
  approved; durable page failure evidence and repairability remain required.
- Text and vision modes preserve page order and page markers.
- `pdf.text` passes every deterministic text-corpus threshold and `pdf.vision`
  passes both independent full-corpus live runs in `Recognition Quality
  Evidence`. Track the two capability statuses separately.
- Vision mode composes the Phase 1 image path with the board profile; it does
  not implement a second vision client.
- PDFium calls are serialized or process-isolated; no unsafe threaded calls.
- A deterministic five-page fake-provider run is interrupted after page two;
  resume makes zero new calls for pages one/two and produces the same ordered
  final Markdown as an uninterrupted run. Separate tests reject corrupt state,
  changed source bytes, changed page selection/model/profile/processor version,
  missing state artifacts, and a mismatched final-output hash. Add encrypted
  resume cases only if encrypted-PDF support is approved.
- `ocrllm.v1alpha2` Node fixtures prove PDF `resume` default/conflict rules and
  the sibling state-file URI round-trip.
- Wheel/application artifacts contain required PDFium dependency notices.
- Plain `import ocrllm` does not import pypdfium2 or Pillow.
- Clean PDF text and PDF vision + DashScope installs pass the 35 MiB and 96 MiB
  profile budgets.
- Windows can delete the source and temporary page files immediately after
  document/bitmap closure.
- A deterministic 120-page PDF is processed twice sequentially. Peak working
  set stays below 512 MiB; after garbage collection, process handles are no more
  than baseline plus 5; and post-pass private bytes grow by no more than 64 MiB
  from pass one to pass two. All source/temp files are immediately deletable.

### Phase 4: Audio

GO when all are true:

- Licensed speech, multilingual speech, silence, corrupt, and long-audio
  fixtures exist.
- Short ASR and long FileTrans each pass a real opt-in provider test.
- The audio scorer rejects deliberate transcript/timestamp corruptions, and two
  independently dispatched short/long corpus runs pass every WER/CER,
  critical-slot, timestamp, and ordering threshold in `Recognition Quality
  Evidence`.
- WAV/PCM signed 16-bit passes short/long probe, conversion, live transcription,
  packaging, and cleanup tests; this is mandatory for phase advance.
- MP3/MPEG Layer III and M4A/AAC-LC are optional atomic subgates. List each
  short/long name as available only after its own probe, conversion, live
  transcription, packaging, and cleanup tests pass; failure does not block the
  phase.
- All-failed segments fail the job; partial success is explicit.
- Timestamps and segment order survive merge.
- FileTrans task IDs survive interruption without duplicate submission.
- A fake FileTrans run stops immediately after atomic task-ID persistence; the
  restarted run polls the same ID with zero new submissions. Corrupt state and
  changed source/provider/model/segmentation settings fail explicitly.
- Missing ffmpeg/ffprobe produces a typed capability error.
- The clean Audio Python install delta is at most 64 MiB; ffmpeg is measured and
  reported separately as an external capability.

### Phase 5: Video

GO when all are true:

- Video reuses the Phase 1 image and Phase 4 audio processors.
- MP4/H.264 with no audio and MP4/H.264 with AAC audio each pass probe,
  extraction, recognition, packaging, and cleanup tests. No other
  container/codec pair is advertised by this phase.
- A synthetic clip proves deterministic extraction and ordering.
- A licensed real lecture excerpt proves frame selection, visual recognition,
  audio transcription, merge, cancellation, resume, and cleanup.
- A deterministic fake-provider run interrupted after one completed frame
  resumes without re-extracting/re-recognizing completed units; changed source,
  frame cadence, provider/model, or processor version rejects state.
- The video scorer rejects deliberate frame/order/timestamp corruptions, and
  two independent real-lecture runs pass every visual, speech, selection, and
  timeline threshold in `Recognition Quality Evidence`.
- Requested visual/audio results cannot be missing from a successful result.
- Returned artifact paths exist and are final.
- The clean Video Python install delta is at most 64 MiB; ffmpeg is not bundled.

### Phase 6: Distribution and downstream proof

GO when all are true:

- Base, image, PDF, audio, video, provider, and worker profiles have recorded
  wheel/bundle size, installed-size delta, cold start, and peak memory, and each
  passes the numeric budget recorded below or a stricter budget added before
  that phase's implementation.
- A clean Python project imports the wheel without `legacy_app`.
- A clean Electron test app consumes the packaged worker.
- An SBOM and third-party license-notice bundle are produced.
- GUI, FastAPI, social downloaders, and unused modalities are absent from
  feature-specific bundles.

HarmonyOS remains deferred after Phase 6 unless a new decision explicitly
activates it.

## Dependency Profiles

Target extras, created only in their phase:

```text
ocrllm                 Public facade and injected fake-provider tests.
ocrllm[image]          Phase 0: Pillow>=10.4,<13 for lazy decode validation.
ocrllm[pdf-text]       pypdfium2>=5.11.0,<5.12 only.
ocrllm[pdf-vision]     pypdfium2>=5.11.0,<5.12 plus Pillow>=10.4,<13.
ocrllm[dashscope]      Phase 1 vision starts with lazy openai>=2.30,<3.
ocrllm[audio]          Not created until the Phase 4 spike identifies and tests
                       exact Python requirements; ffmpeg stays external.
ocrllm[video]          Not created until Phase 5; it includes approved audio
                       requirements and does not bundle ffmpeg.
ocrllm[all]            Only after every included extra is individually GO.
ocrllm[dev]            Tests, build, lint, and fixture tools.
```

The current Phase 1 metadata declares exactly `dev`, `image`, and `dashscope`;
the later extras in this target list do not exist yet. The base distribution has
no runtime requirements.

The base target uses fresh-process imports after two discarded warm-ups, not an
unmeasured cold-cache claim. The actual hard budgets are:

| Profile | Installed-size budget | Import/bundle rule |
|---|---:|---|
| Base | Wheel <= 256 KiB; no-deps target <= 1 MiB | Zero base runtime requirements, zero native binaries, no PIL/pypdfium2/openai/httpx imports; 30 measured fresh processes after two warm-ups. Wall median <= 100 ms and p95 <= 200 ms; process-CPU median <= 60 ms and p95 <= 100 ms. Record maxima diagnostically. |
| Image | Clean installed delta <= 25 MiB | Pillow remains lazy. |
| Image + DashScope | Clean installed delta <= 64 MiB | Pillow, openai, and transitive httpx remain lazy on base import. |
| PDF text | Clean installed delta <= 12 MiB | pypdfium2 remains lazy; Pillow is absent. |
| PDF vision | Clean installed delta <= 35 MiB | pypdfium2 and Pillow remain lazy. |
| PDF vision + DashScope | Clean installed delta <= 96 MiB | Same lazy-import rule; no second vision client. |
| Audio | Python installed delta <= 64 MiB | ffmpeg is an external capability, not bundled. |
| Video | Python installed delta <= 64 MiB | Reuses audio; ffmpeg is not bundled. |

The self-contained Electron worker bundle has no proven size budget yet. Phase
6 is NO-GO until a packaging spike records its runtime, provider, and image
profile sizes and this decision approves a numeric bundle ceiling. Do not call
that bundle lightweight before the ceiling exists and passes. A small base
wheel does not make a media or application bundle lightweight.

## Verification Commands

The exact pinned offline corpus/scorer checkpoint checks are:

```powershell
uv run --no-project --isolated --with 'Pillow==12.3.0' `
  --with 'pytest>=8,<10' --with 'openai>=2.30,<3' `
  --python 'D:\Anaconda\envs\OCRLLM\python.exe' `
  python -m pytest -q -p no:cacheprovider
if ($LASTEXITCODE -ne 0) { throw "pytest failed" }
uv run --no-project --isolated --with 'Pillow==12.3.0' `
  --python 'D:\Anaconda\envs\OCRLLM\python.exe' `
  python -m tests.quality.generators.generate_phase1_fixtures --check
if ($LASTEXITCODE -ne 0) { throw "generated fixture bytes drifted" }
& 'D:\Anaconda\envs\OCRLLM\python.exe' -m compileall -q src tests
if ($LASTEXITCODE -ne 0) { throw "compileall failed" }
```

Do not simplify the generator command to the base environment's bare Python.
That environment currently has Pillow 12.1.1; the frozen image bytes were
verified with the explicit Pillow 12.3.0 overlay above.

For packaging hotfix `3414f47`, the clean-source proof used this method rather
than the working directory:

```powershell
$proofRoot = Join-Path $env:TEMP ("ocrllm-3414f47-" + [guid]::NewGuid())
$archivePath = Join-Path $proofRoot 'source.zip'
$archiveRoot = Join-Path $proofRoot 'source'
$wheelDir = Join-Path $proofRoot 'wheel'
$targetDir = Join-Path $proofRoot 'target'
New-Item -ItemType Directory -Path $proofRoot | Out-Null
New-Item -ItemType Directory -Path $archiveRoot, $wheelDir, $targetDir | Out-Null

git archive --format=zip --output=$archivePath 3414f47
if ($LASTEXITCODE -ne 0) { throw "git archive failed" }
Expand-Archive -LiteralPath $archivePath -DestinationPath $archiveRoot
uv run --no-project --isolated --with 'build>=1.2' `
  --python 'D:\Anaconda\envs\OCRLLM\python.exe' `
  python -m build --wheel --outdir $wheelDir $archiveRoot
if ($LASTEXITCODE -ne 0) { throw "clean archive wheel build failed" }
$wheel = Get-ChildItem -LiteralPath $wheelDir -Filter *.whl | Select-Object -First 1
if ($null -eq $wheel) { throw "wheel build produced no wheel" }
& D:\Anaconda\envs\OCRLLM\python.exe -m pip install --no-deps --target $targetDir $wheel.FullName
if ($LASTEXITCODE -ne 0) { throw "isolated wheel install failed" }

$env:OCRLLM_WHEEL_TARGET = $targetDir
Push-Location $env:TEMP
try {
    & D:\Anaconda\envs\OCRLLM\python.exe -I -c "import os,sys; sys.path.insert(0,os.environ['OCRLLM_WHEEL_TARGET']); from ocrllm import Config; from ocrllm.providers.dashscope.resolve_dashscope_credential import resolve_dashscope_credential; key='offline-package-probe'; assert resolve_dashscope_credential(Config(provider=object(),api_key=key)) == key"
    if ($LASTEXITCODE -ne 0) { throw "isolated credential resolver probe failed" }
} finally {
    Pop-Location
    Remove-Item Env:OCRLLM_WHEEL_TARGET -ErrorAction SilentlyContinue
}
```

Result: full commit `3414f47e5b44a6d5fe2023012ebf2cf361f96a61`,
wheel size `50,094` bytes, isolated explicit-key round-trip passed, and no
provider network call was made.

For a future committed active-library checkpoint, run the complete clean gate
from the repository root. The tests exercise the working tree; the packaging
steps intentionally archive `HEAD`, so do not report the combined result as a
clean checkpoint until the intended changes are committed:

```powershell
$sourceArchive = Join-Path $env:TEMP ("ocrllm-source-" + [guid]::NewGuid() + ".zip")
$sourceRoot = Join-Path $env:TEMP ("ocrllm-source-" + [guid]::NewGuid())
$wheelDir = Join-Path $env:TEMP ("ocrllm-wheel-" + [guid]::NewGuid())
$targetDir = Join-Path $env:TEMP ("ocrllm-target-" + [guid]::NewGuid())
New-Item -ItemType Directory -Path $sourceRoot, $wheelDir, $targetDir | Out-Null

uv run --no-project --isolated --with 'Pillow==12.3.0' `
  --with 'pytest>=8,<10' --with 'openai>=2.30,<3' `
  --python 'D:\Anaconda\envs\OCRLLM\python.exe' `
  python -m pytest -q -p no:cacheprovider
if ($LASTEXITCODE -ne 0) { throw "pytest failed" }
uv run --no-project --isolated --with 'Pillow==12.3.0' `
  --python 'D:\Anaconda\envs\OCRLLM\python.exe' `
  python -m tests.quality.generators.generate_phase1_fixtures --check
if ($LASTEXITCODE -ne 0) { throw "generated fixture bytes drifted" }
& 'D:\Anaconda\envs\OCRLLM\python.exe' -m compileall -q src tests
if ($LASTEXITCODE -ne 0) { throw "compileall failed" }
git archive --format=zip --output=$sourceArchive HEAD
if ($LASTEXITCODE -ne 0) { throw "git archive failed" }
Expand-Archive -LiteralPath $sourceArchive -DestinationPath $sourceRoot
uv run --no-project --isolated --with 'build>=1.2' `
  --python 'D:\Anaconda\envs\OCRLLM\python.exe' `
  python -m build --wheel --outdir $wheelDir $sourceRoot
if ($LASTEXITCODE -ne 0) { throw "wheel build failed" }
$wheel = Get-ChildItem -LiteralPath $wheelDir -Filter *.whl | Select-Object -First 1
if ($null -eq $wheel) { throw "wheel build produced no wheel" }
if ($wheel.Length -gt 262144) { throw "Base wheel exceeds 256 KiB: $($wheel.Length)" }
& D:\Anaconda\envs\OCRLLM\python.exe -m pip install --no-deps --target $targetDir $wheel.FullName
if ($LASTEXITCODE -ne 0) { throw "isolated wheel install failed" }
$installedBytes = (Get-ChildItem -LiteralPath $targetDir -Recurse -File | Measure-Object Length -Sum).Sum
if ($installedBytes -gt 1048576) { throw "Base target exceeds 1 MiB: $installedBytes" }

$env:OCRLLM_WHEEL_TARGET = $targetDir
Push-Location $env:TEMP
try {
    & D:\Anaconda\envs\OCRLLM\python.exe -I -c "import os,sys; sys.path.insert(0,os.environ['OCRLLM_WHEEL_TARGET']); import ocrllm; loaded={n.split('.')[0] for n in sys.modules}; forbidden={'PIL','pypdfium2','openai','httpx'}; assert not loaded & forbidden, loaded & forbidden; print(ocrllm.__version__)"
    if ($LASTEXITCODE -ne 0) { throw "outside-repo import failed" }

    $metadataProbe = "import importlib.metadata as m,sys; d=next(x for x in m.distributions(path=[sys.argv[1]]) if x.metadata['Name']=='ocrllm'); reqs=d.requires or []; base=[r for r in reqs if 'extra ==' not in r]; native=[str(p) for p in (d.files or []) if str(p).lower().endswith(('.pyd','.dll','.so','.dylib','.exe'))]; assert not base, base; assert not native, native"
    & D:\Anaconda\envs\OCRLLM\python.exe -I -c $metadataProbe $targetDir
    if ($LASTEXITCODE -ne 0) { throw "base metadata budget failed" }

    $timingProbe = "import json,sys,time; sys.path.insert(0,sys.argv[1]); c=time.process_time_ns(); w=time.perf_counter_ns(); import ocrllm; wall=(time.perf_counter_ns()-w)/1e6; cpu=(time.process_time_ns()-c)/1e6; loaded={n.split('.')[0] for n in sys.modules}; forbidden={'PIL','pypdfium2','openai','httpx'}; assert not loaded & forbidden, loaded & forbidden; print(json.dumps({'wall':wall,'cpu':cpu}))"
    foreach ($python in @('D:\Anaconda\envs\OCRLLM\python.exe', 'D:\Anaconda\python.exe')) {
        $samples = @()
        foreach ($iteration in 0..31) {
            $raw = & $python -I -c $timingProbe $targetDir
            if ($LASTEXITCODE -ne 0) { throw "import timing probe failed: $python" }
            $samples += ($raw | ConvertFrom-Json)
        }
        $wall = @($samples[2..31].wall | Sort-Object)
        $cpu = @($samples[2..31].cpu | Sort-Object)
        $wallMedian = ($wall[14] + $wall[15]) / 2
        $wallP95 = $wall[28]
        $cpuMedian = ($cpu[14] + $cpu[15]) / 2
        $cpuP95 = $cpu[28]
        if ($wallMedian -gt 100 -or $wallP95 -gt 200 -or $cpuMedian -gt 60 -or $cpuP95 -gt 100) {
            throw "Import budget failed for ${python}: wall=${wallMedian}/${wallP95}ms cpu=${cpuMedian}/${cpuP95}ms"
        }
        "${python}: wall median/p95/max=$wallMedian/$wallP95/$($wall[29])ms; CPU median/p95/max=$cpuMedian/$cpuP95/$($cpu[29])ms"
    }
} finally {
    Pop-Location
    Remove-Item Env:OCRLLM_WHEEL_TARGET
}
```

The isolated import command is the base-profile heavy-module guard. Add the
phase's optional modules to `forbidden` whenever a new extra is introduced.

To reproduce the Phase 0 clean image-extra proof, generate the fixture inside
the fresh environment rather than depending on a repository `valid.png` file:

```powershell
$imageVenv = Join-Path $env:TEMP ("ocrllm-image-venv-" + [guid]::NewGuid())
& D:\Anaconda\envs\OCRLLM\python.exe -m venv $imageVenv
$imagePython = Join-Path $imageVenv 'Scripts\python.exe'
$imageSitePackages = & $imagePython -I -c "import site; print(site.getsitepackages()[0])"
$imageBaselineBytes = (Get-ChildItem -LiteralPath $imageSitePackages -Recurse -File | Measure-Object Length -Sum).Sum
& $imagePython -m pip install "$($wheel.FullName)[image]"
if ($LASTEXITCODE -ne 0) { throw "image extra install failed" }
$imageAfterBytes = (Get-ChildItem -LiteralPath $imageSitePackages -Recurse -File | Measure-Object Length -Sum).Sum
$imageDeltaBytes = $imageAfterBytes - $imageBaselineBytes
if ($imageDeltaBytes -gt 26214400) { throw "Image profile exceeds 25 MiB: $imageDeltaBytes" }
& $imagePython -I -c "import importlib.metadata as m,sys; import ocrllm; assert 'PIL' not in sys.modules; v=m.version('Pillow'); parts=tuple(map(int,v.split('.')[:2])); assert parts >= (10,4) and parts < (13,0), v; print(v)"
if ($LASTEXITCODE -ne 0) { throw "image extra lazy-import proof failed" }

$imageFixture = Join-Path $imageVenv 'generated-valid.png'
$imageSmoke = @'
from pathlib import Path
import sys

from PIL import Image
from ocrllm import Config, recognize

path = Path(sys.argv[1])
Image.new("RGB", (8, 6), color=(32, 96, 160)).save(path, format="PNG")

class Provider:
    def recognize_images(self, image_paths, *, prompt, config):
        assert image_paths[0] != path
        with Image.open(image_paths[0]) as image:
            image.verify()
        return "# Generated fixture recognized\n"

result = recognize(path, config=Config(provider=Provider()))
assert result.status == "complete"
assert result.source_type == "image"
assert result.profile == "board"
assert result.markdown == "# Generated fixture recognized\n"
print(result.status)
'@
$imageSmoke | & $imagePython -I - $imageFixture
if ($LASTEXITCODE -ne 0) { throw "generated image recognition proof failed" }
```

Each later extra uses a separate new venv and real phase fixture. Phase 1 must
install `[image,dashscope]`; Phase 3 must independently install `[pdf-text]` and
`[pdf-vision]`, assert Pillow is absent from the text venv and present in the
vision venv, then run text extraction/rendering; Phase 4 installs `[audio]`; and
Phase 5 installs `[video]`. Installing metadata without executing the capability
fixture is a failed gate.

For every clean profile venv, measure `site-packages` immediately after venv
creation and again after installing the wheel plus extra; the installed delta is
`after - baseline` and includes OCRLLM plus all transitive packages while
excluding the venv's bootstrap pip. Use these exact byte ceilings:

```powershell
$profileLimitBytes = @{
    'image' = 26214400
    'image,dashscope' = 67108864
    'pdf-text' = 12582912
    'pdf-vision' = 36700160
    'pdf-vision,dashscope' = 100663296
    'audio' = 67108864
    'video' = 67108864
}

$profilesByPhase = @{
    'phase0' = @('image')
    'phase1' = @('image', 'image,dashscope')
    'phase3' = @('pdf-text', 'pdf-vision', 'pdf-vision,dashscope')
    'phase4' = @('audio')
    'phase5' = @('video')
}

$expectedDistributions = @{
    'image' = @('Pillow')
    'image,dashscope' = @('Pillow', 'openai')
    'pdf-text' = @('pypdfium2')
    'pdf-vision' = @('pypdfium2', 'Pillow')
    'pdf-vision,dashscope' = @('pypdfium2', 'Pillow', 'openai')
    'audio' = $null
    'video' = $null
}

$phase = 'phase1'  # Set only to the currently authorized phase.
if (-not $profilesByPhase.ContainsKey($phase)) { throw "unknown phase: $phase" }
foreach ($profile in $profilesByPhase[$phase]) {
    $expected = $expectedDistributions[$profile]
    if ($null -eq $expected) {
        throw "record exact expected distributions before measuring: $profile"
    }
    $safeProfile = $profile.Replace(',', '-')
    $profileVenv = Join-Path $env:TEMP ("ocrllm-$safeProfile-venv-" + [guid]::NewGuid())
    & D:\Anaconda\envs\OCRLLM\python.exe -m venv $profileVenv
    if ($LASTEXITCODE -ne 0) { throw "profile venv failed: $profile" }
    $profilePython = Join-Path $profileVenv 'Scripts\python.exe'
    $sitePackages = & $profilePython -I -c "import site; print(site.getsitepackages()[0])"
    $baselineBytes = (Get-ChildItem -LiteralPath $sitePackages -Recurse -File | Measure-Object Length -Sum).Sum
    & $profilePython -m pip install "$($wheel.FullName)[$profile]"
    if ($LASTEXITCODE -ne 0) { throw "profile install failed: $profile" }
    $expectedCsv = $expected -join ','
    $profileProbe = "import importlib.metadata as m,sys; d=m.distribution('ocrllm'); declared=set(d.metadata.get_all('Provides-Extra') or []); requested=set(sys.argv[1].split(',')); missing_extras=requested-declared; assert not missing_extras, missing_extras; [(m.version(name) if name else None) for name in sys.argv[2].split(',')]; print(sorted(declared))"
    & $profilePython -I -c $profileProbe $profile $expectedCsv
    if ($LASTEXITCODE -ne 0) { throw "profile dependency declaration failed: $profile" }
    if ($profile -eq 'image,dashscope') {
        $dashscopeProbe = @'
import sys

from ocrllm import Config, DashScopeSettings, VisionModelSettings

loaded = {name.split(".")[0] for name in sys.modules}
forbidden = {"PIL", "openai", "httpx"}
assert not loaded & forbidden, loaded & forbidden

settings = DashScopeSettings(
    region="cn-beijing",
    base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
    api_key="offline-package-probe",
)
config = Config(
    provider=settings,
    vision_model=VisionModelSettings(name="qwen3.7-plus-2026-05-26"),
)
assert config.provider == settings
assert config.provider is not settings

from ocrllm.providers.dashscope.create_dashscope_openai_client import (
    create_dashscope_openai_client,
)
from ocrllm.providers.dashscope.load_openai import load_openai

openai_module = load_openai()
client = create_dashscope_openai_client(
    openai_module,
    api_key="offline-package-probe",
    settings=settings,
    timeout_seconds=3.0,
)
client.close()
print(openai_module.__version__)
'@
        $dashscopeProbe | & $profilePython -I -
        if ($LASTEXITCODE -ne 0) { throw "DashScope offline package probe failed" }
    }
    $afterBytes = (Get-ChildItem -LiteralPath $sitePackages -Recurse -File | Measure-Object Length -Sum).Sum
    $deltaBytes = $afterBytes - $baselineBytes
    if ($deltaBytes -gt $profileLimitBytes[$profile]) {
        throw "profile size failed: $profile delta=$deltaBytes limit=$($profileLimitBytes[$profile])"
    }
    "$profile installed delta: $deltaBytes bytes"
}
```

PDF phase verification must additionally print:

- pypdfium2 version and PDFium build version,
- rendered page count and ordered dimensions,
- extracted text per selected page,
- clean installed profile delta,
- copied license/notice file locations.

The guarded runner is committed at `fb23d1e`. The user confirmed canonical
region `cn-beijing` and the recovered key-matching Beijing endpoint on
2026-07-11. The first fixed plan then completed 13 paid calls with no retry: one
clean-slide smoke, all six dispatches in run A, then all six independently
dispatched entries in run B. Both full runs failed the frozen gate. Preserve
that evidence unchanged; never rerun only one failed fixture. Simulated evidence
cannot satisfy the live gate.

Real provider evidence must preserve raw Markdown plus the provider/model
identifier, configuration and Git/import/code/corpus/manifest/artifact hashes,
dependency versions, UTC and elapsed time, every scorer metric, nonempty result
status, and typed failure category without printing credentials, the full
endpoint, or other sensitive documents. A later attempt requires a separately
versioned offline contract, deliberate-corruption tests, a new explicit paid-run
decision, and a new evidence path. After both later full runs pass, rerun the
clean profiles and explicitly update this decision; runner success alone does
not change Phase 1 from NO-GO to GO.

The v7 conservative single-draft review experiment is rejected. Both
handwriting finals still missed the required center `+`, and both formula
finals still changed source `s_4` to `S_4`. V8 keeps one unified board profile
and uses two independent drafts plus one pixel-grounded consensus review.
Targeted consensus finals passed handwriting at 30/30 recall and 10/10 slots
and formula at 12/12 signatures and 133/133 atoms. One timed-out consensus
published no output; a bounded final-only recovery reused both drafts and
passed.

V8 defaults to one call and exposes the robust path only through exact
`RecognitionPreferences(draft_candidates=2, review_passes=1)`. Its frozen gate
is 13 recognitions and 39 confirmed provider calls. The manifest is 37,712
bytes with SHA-256
`7200d16ea44b365301ce491bd3353433520d6c8ba2cc686debe6562173623e35`;
the isolated suite passes 608 tests. Full v8 live evidence and clean packaging
profiles remain required, so Phase 1 is still NO-GO. The complete decision and
call ledger are in `phase1_v8_consensus_workflow_debug_2026-07-11.md`.

V8 live attempt 1 did not satisfy that gate. Smoke and five Run A singles
completed; formula passed 12/12 signatures and 133/133 atoms, while handwriting
again missed one required standalone `+` at 29/30 recall and 5/6 critical-token
accuracy. The ordered request timed out on draft 1 after 120.954 seconds, so
Run A did not complete and Run B never started. Preserve the 59,675-byte
evidence with SHA-256
`fd34fb9f3ec7d37674ba7f779f3db743a36b76af81371a27090e8c1b7d75fe94`.
Phase 1 remains NO-GO. See
`phase1_live_quality_result_v8_attempt1_2026-07-11.md`.

Post-v8 diagnostics reject generative v9 disagreement review: it mutated
byte-identical perfect formula drafts and could not repair handwriting when all
Qwen3.7 candidates omitted the plus. Qwen3.7 Max repeated the omission. The
legacy-default `qwen-vl-max` consistently captured both plus signs but was
weaker on prose. V10 uses one Qwen3.7 symbol-audited transcript, two explicit
Qwen-VL Max sign scouts, and a bounded deterministic anchor quorum. Scout prose
cannot enter output and no generative final rewrite occurs.

Two independent handwriting trials pass after zero and one restored signs; the
formula draft remains byte-identical and perfect. The v10 manifest is 37,853
bytes with SHA-256
`15a7018084cd1d53c82acbf260bb19095ccb29664cc357beaaaefd9044b8f971`;
628 isolated tests pass. The clean live plan is still 13 recognitions and 39
provider calls, now with a 180-second timeout. Phase 1 remains NO-GO until that
gate and clean packaging profiles pass. See
`phase1_v10_sign_scout_workflow_debug_2026-07-11.md`.

V10 live evidence completed both runs and all 39 calls; Run B passed. Run A
handwriting still missed one plus with zero restoration, and Run A formula was
scorer-rejected for safe `\text{}` LaTeX. The passing ordered request also
revealed an unsafe false restoration of a Markdown `---` separator. Preserve
the 98,351-byte evidence SHA-256
`8c86c7117efa6ad7e999bad3180e861981a27598788cfaaeb526472ae65b9c54`.
Phase 1 remains NO-GO. See `phase1_live_quality_result_v10_2026-07-11.md`.

V11 excludes Markdown thematic breaks from sign evidence, changes scout voting
to two-of-three, and introduces formula dialect v6 for only safe single-letter
`\text{X}` groups in exact labeled math. The v10 rejected formula re-scores
perfectly, and broader command forms remain rejected. The fixed v11 gate is 13
recognitions and 52 calls. Its 37,853-byte manifest SHA-256 is
`3b5c5392b1e10ed40261ac08dc5fbf692f0b451c6c13c4c71a44b710f28ec86b`;
647 isolated tests pass. Phase 1 remains NO-GO pending live evidence. See
`phase1_v11_three_scout_and_formula_dialect_2026-07-11.md`.

V11 completed all 52 calls, but both runs failed only handwriting. Run A had
30/30 recall and invented diagram captions; Run B also missed one plus. Three
full-transcript scouts restored zero signs in both. Formula v6 and every
non-handwriting dispatch passed twice. Preserve the 104,026-byte evidence
SHA-256
`44b74fdb0ba57662a6c49193c6c203b147b88a723bed8698b983fb9f1a59465f`.
Phase 1 remains NO-GO. See `phase1_live_quality_result_v11_2026-07-11.md`.

V12 targeted probes pass: two caption-restricted Qwen3.7 primaries pass
handwriting, and three Qwen-VL Max scouts independently return the same strict
sign ledger with both plus signs. The production parser fails closed on any
non-ledger prose or unsafe record; scout prose cannot enter Markdown. The v12
manifest is 37,853 bytes with SHA-256
`e2813e006d4de8db3b4b2fe3ef99a1e658935d98290e2a1735d75d4e80a164f6`;
661 isolated tests pass. The full gate then aborted at the first bilingual
printed-slide smoke recognition: four provider calls were attempted, but the
strict protocol had no valid empty-ledger response. No full run began and no
selective retry was made. Preserve the 29,606-byte atomic evidence SHA-256
`ea16775eec1aea7af79681e1f90b76ca075864e9b8e9b1b00dc1c90d125282ea`.
Phase 1 remains NO-GO. See
`phase1_v12_literal_primary_and_sign_ledger_2026-07-11.md`.

V13 treats malformed sign ledgers as counted auxiliary abstentions rather than
discarding an otherwise valid primary transcript. Exact `NONE` is a valid empty
ledger, two valid scouts are still required for quorum, and an existing
supported sign at the same primary anchors blocks conflicting restoration.
Three targeted printed-slide scouts returned `NONE`; three handwriting scouts
recovered the missing plus. The v13 manifest is 37,853 bytes with SHA-256
`890f67941bc2783bc81f91ab42b1290fb4ad1df4c722cb2f458e762dd9ad1522`.
The exact isolated suite passes 667 tests. See
`phase1_v13_auxiliary_scout_abstention_2026-07-11.md`.

The complete v13 live gate returned all 52 calls and both full runs, but neither
passed. Handwriting achieved full recall and critical accuracy twice while one
extra plus was inserted twice; a projected slide duplicated LaTeX `\ge` as
Unicode `≥`; and both GFM tables were broken by five row-interleaved signs.
Preserve the 98,101-byte evidence SHA-256
`b10b88eeeba94f637165ddf32b95eb3ff3e3e02d4ccdd254ad9fbfe39bec67f1`.
Phase 1 remains NO-GO. See
`phase1_live_quality_result_v13_2026-07-11.md`.

V14 includes anchor lines in conflict detection, counts equivalent
Unicode/ASCII/LaTeX relation signs, and protects GFM pipe rows from insertion.
It does not branch by handwriting or fixture class. The v14 manifest is 37,853
bytes with SHA-256
`dae74f4da207d01e311f5756a204e557ca6e6982073024d2e48b672315febb07`;
all 685 isolated tests pass. Phase 1 remains NO-GO pending complete live
evidence. See `phase1_v14_structural_sign_guard_2026-07-11.md`.

The complete v14 run returned all 52 calls. Run B passed; Run A failed only
handwriting after two scout abstentions left no quorum to restore one missing
plus. Both tables and all other dispatches pass, confirming the v13 structural
fixes. Preserve the 103,074-byte evidence SHA-256
`48c4fb2f78d0bff36aae6e022074d173e85fbf8cdfa792a81bc04bef01fe067a`.
Phase 1 remains NO-GO. See
`phase1_live_quality_result_v14_2026-07-11.md`.

V15 keeps one unified board workflow and the 52-call plan, but replaces the
Phase 1 Qwen-VL scout baseline with three independent thinking-enabled pinned
Qwen3.7 sign scouts. Targeted evidence finds both genuine handwriting pluses in
eight of eight thinking calls; non-thinking succeeds only once in five. Only
exact allowlisted rows survive defensive extraction, then two-of-three quorum
and every v14 guard still apply. The v15 manifest is 37,864 bytes with SHA-256
`9c5fe09635142c457c464d52f2c4bba8e78964f61e3c06cb4b786d8bf6bf3c11`;
all 696 isolated tests pass. Phase 1 remains NO-GO pending complete live
evidence. See
`phase1_v15_thinking_scout_and_allowlist_extraction_2026-07-11.md`.

The complete v15 run returned all 52 calls with zero scout abstentions. Run A
failed only a diagrammatic arrow restored into complete handwriting; Run B
handwriting passed with one safe restoration, while formula failed only
source-equivalent one-letter `\mathrm{X}` outside dialect v6. Preserve the
99,223-byte evidence SHA-256
`65dad6a47206562c526f643bab600d87e0f68987f443cc6757e7f07ec9fff95b`.
Phase 1 remains NO-GO. See
`phase1_live_quality_result_v15_2026-07-11.md`.

V16 removes directional arrows from the auxiliary restorable set and upgrades
the formula scorer to restricted dialect v7, which unwraps only one ASCII
letter in `\mathrm{X}` inside exact labeled formulas. The primary can still
transcribe arrows, and broader Roman LaTeX remains rejected. The v16 manifest
is 37,864 bytes with SHA-256
`12b5234850d885926ea01161c31643ae2050728bd377c86e44784377d00abde9`;
all 706 isolated tests pass. Phase 1 remains NO-GO pending complete live
evidence. See `phase1_v16_arrow_exclusion_and_formula_dialect_2026-07-11.md`.

The complete v16 run returned all 52 calls. Run B passed; Run A failed only one
missing handwriting plus after three usable scout responses produced no
second-plus quorum. No arrow was inserted and both formula runs passed dialect
v7. Preserve the 103,882-byte evidence SHA-256
`4395c84ed0efa8d3567bdf5f14a35a8dad8d3412a52fdb5a9e8359ca355ea139`.
Phase 1 remains NO-GO. See
`phase1_live_quality_result_v16_2026-07-11.md`.

V17 conditions each scout on the quoted primary transcript and asks only for
missing arithmetic/relation signs. Three targeted calls on the exact failed v16
primary agree only on `foreign gene + I:V`. The pool remains three, quorum
remains two, and all structural guards remain. Dynamic prompt hashes enter
result metadata and evidence. The v17 manifest is 37,864 bytes with SHA-256
`4ec1440f531e88492eb06795a29308256a5718c2748625ce2ad9b1230807e393`;
all 712 isolated tests pass. See
`phase1_v17_conditioned_omission_scout_2026-07-11.md`.

The complete v17 Beijing gate reported all 52 planned provider calls with no
retry or terminal failure. Both independent full runs passed. Run A required no
restoration; Run B handwriting passed after exactly one generic two-of-three
omission restoration. Formula, table, printed/projected, and ordered-image
dispatches passed unchanged in both runs. Preserve the 107,246-byte evidence
SHA-256
`6f0454d634dbe76f68f29c07a4c0ced4a047c080e46bb75dda2cb84ffca3a96b`.
See `phase1_live_quality_result_v17_2026-07-11.md`.

The clean Git-archive gate then tested committed checkpoint `0278b66`: 712
tests, generated fixture identity, compilation, a 67,266-byte wheel, a
306,163-byte base target, both import timing environments, generated-image
recognition, and the offline Beijing DashScope construction probe passed. The
fresh `image` profile installed 15,987,099 bytes against a 25 MiB ceiling; the
fresh `image,dashscope` profile installed 40,901,589 bytes against a 64 MiB
ceiling. No provider call occurred. Phase 1 is **GO** and Phase 2 is now the
only active implementation phase.

## Current Stage M Offline Exit Runner, 2026-08-23

Use the maintained runner instead of copying the older manual checkpoint blocks
above:

```powershell
& .\tools\run_stage_m_offline_gate.ps1
```

The runner refuses tracked working-tree changes, archives the exact current
commit into a GUID-scoped temporary directory, and runs the full suite, fixture
verification, compilation, clean wheel build, outside-repository base import,
metadata and optional-extra checks, both import timing environments, fresh
`image` and `image,dashscope` profiles, a generated-image injected-provider
smoke, and an offline DashScope client-construction smoke. It verifies import
origin and forbids `PIL`, `pypdfium2`, `openai`, `httpx`, `onnxruntime`, and
`legacy_app` after plain base import. Temporary files are removed in `finally`.

Checkpoint `271d96df837a8bbe3caf271afd966cb0539371d6` passed: archived tests
reported 1089 passed and one expected optional-RapidOCR skip; the wheel was
153,382 bytes and the base target 747,967 bytes; import wall median/p95 was
0.88/2.40 ms in the OCRLLM environment and 0.49/1.21 ms in base Python;
process-CPU median/p95 was 0/15.63 ms and 0/0 ms respectively. The fresh
profile deltas were 16,436,747 bytes (`image`) and 41,009,476 bytes
(`image,dashscope`). No provider request occurred. This closes only the offline
part of the Stage M exit gate;
the paid live smoke still needs an explicit maintainer budget.

## Change Rejection Checklist

Reject a proposed change when any answer is yes:

- Does it import `legacy_app` or uppercase `OCRLLM`?
- Does it add PyMuPDF or `fitz` to the active package?
- Does it add an optional dependency to base import time?
- Does it put more than one responsibility in a new file?
- Does a function live in a file whose name does not describe that function?
- Does it return success with empty content or missing required artifacts?
- Does it expose a legacy processor class as public API?
- Does it put provider retry policy inside media conversion code?
- Does it put output writing inside a provider adapter?
- Does it add GUI, server, downloader, HarmonyOS, Rust, WASM, Office, GPU, or
  offline-model work without a new explicit decision?
- Does it claim support based only on code existence, mocks, historical logs,
  or installed dependencies?
- Does it change an active boundary without updating `MIGRATION_STATUS.md`?

## Documentation Rule

When a phase changes from NO-GO to GO, update all of these in the same commit:

```text
MIGRATION_STATUS.md
README.md
src/ocrllm/README_ACTIVE_LIBRARY.md
docs/ocrllm_library_go_no_go.md
docs/ocrllm_module_target_design.md
```

Record exact commands and results. Do not replace failed or unavailable proof
with planned language.
