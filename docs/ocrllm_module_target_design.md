# OCRLLM Module Target Design

Status: supporting target-state design map.

This document describes the intended completed `ocrllm` Python module as if the
library already exists. It is not a promise that every name below is frozen.
Implementation may change when tests, downstream usage, or dependency reality
prove a better shape.

`docs/ocrllm_library_go_no_go.md` is authoritative for implementation order,
file responsibilities, migration versus rewrite decisions, PDFium, and GO
gates. If this target map conflicts with that execution record, follow the
execution record.

The active implementation remains the Python-first package in `src/ocrllm`.
The Rust/PyO3 plan in `Architecture.md` is suspended future planning.
Phase 0 contract honesty is GO at commit `5018ad0` on the exact clean evidence
recorded in `docs/ocrllm_library_go_no_go.md`; Phase 1 real board/image is GO,
and Phase 2 JSON/JSONL worker is GO. Phase 2A image-library completion is also
GO; no later phase is active and Phase 3 has not started.

## One-Sentence Goal

`ocrllm` is an importable Python library that turns boards, screenshots, PDFs,
audio, and video into structured Markdown through a small public API, explicit
providers, optional dependencies, and tested vertical slices.

## Architectural Judgment

The library must not be a renamed copy of the old application. The old app is a
behavior reference, not a module boundary.

The old codebase contains valuable product knowledge, but its shape is hostile
to library reuse:

- GUI, CLI, FastAPI, downloader, provider, and processor concerns were mixed.
- Runtime output defaults lived too close to package code.
- Large files carried multiple responsibilities.
- Broad exception handling made failure modes hard to trust.
- Internal classes leaked before there was a stable facade.

The correct move is a library extraction, not a heroic rewrite. Build a small
facade first, port one vertical slice at a time, and let downstream imports
prove the boundary before optimizing internals.

## Non-Negotiable Boundaries

- `import ocrllm` must stay lightweight.
- No GUI import at module import time.
- No FastAPI import at module import time.
- No social downloader import at module import time.
- No browser automation import at module import time.
- No `legacy_app` or uppercase `OCRLLM` imports from `src/ocrllm`.
- No output files unless the caller explicitly requests output.
- No package-relative runtime output or temp defaults.
- No public API that exposes legacy processor classes directly.
- No silent catch-all error handling.
- No Rust/PyO3 dependency until the Python module boundary is proven.
- No PyMuPDF or `fitz` in the active package; PDF uses PDFium through
  `pypdfium2` after its phase is authorized.
- No HarmonyOS/ArkTS implementation or compatibility claim in the active
  phases.

## Completed User Experience

The completed package must be boring to import and predictable to call:

```python
from ocrllm import Config, DashScopeSettings, VisionModelSettings, recognize

result = recognize(
    "lecture_board.png",
    config=Config(
        provider=DashScopeSettings(
            region="cn-beijing",
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
            api_key="sk-...",
        ),
        vision_model=VisionModelSettings(name="qwen3.7-plus-2026-05-26"),
    ),
)

print(result.markdown)
```

For batch use:

```python
from ocrllm import Config, DashScopeSettings, recognize_batch

results = recognize_batch(
    ["board.png", "slides.pdf", "lecture.mp4"],
    config=Config(
        provider=DashScopeSettings(
            region="cn-beijing",
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        ),
        pdf_mode="vision",
        output_dir="out",
    ),
)
```

For downstream projects that already own provider clients:

```python
from ocrllm import Config, recognize


class ExistingVisionClient:
    def recognize_images(self, image_paths, *, prompt, config):
        return "# Recognized content\n"


result = recognize(
    "board.jpg",
    config=Config(provider=ExistingVisionClient()),
)
```

The dependency surface supports both modes:

- Built-in provider adapters for normal users.
- Injected provider objects for host applications that already manage clients,
  billing, logging, retries, secrets, and network policy.

## Public API

The public API is small. Everything else is internal unless explicitly
documented.

```python
from ocrllm import (
    Config,
    DashScopeSettings,
    Artifact,
    RecognitionResult,
    CapabilityReport,
    recognize,
    recognize_batch,
    get_capabilities,
    OCRLLMError,
    ConfigError,
    DependencyMissing,
    InvalidSource,
    OutputError,
    OutputExists,
    ProviderError,
    ProviderUnavailable,
    QuotaExhausted,
    RateLimited,
    NoSpeechDetected,
    UnsupportedFormat,
    Cancelled,
)
```

`get_capabilities()` reports `available`, `experimental`, `unavailable`, or
`deferred` for each atomic registry name. Installed code alone does not produce
an `available` result; its atomic subgate and current configuration must agree.
The initial registry is fixed in `docs/ocrllm_library_go_no_go.md` and
distinguishes image formats, PDF text/vision/resume, every audio format plus
short/long flow,
each video container/codec pair, providers, and worker versions. Do not replace
those entries with an aggregate modality label that hides an unavailable format.
Atomic capability status can pass while its phase remains active; phase advance
uses the separate mandatory-capability list in the authoritative GO/NO-GO file.

```python
def get_capabilities(config: Config | None = None) -> tuple[CapabilityReport, ...]:
    ...
```

This function performs no network call and imports no optional package. With no
config it reports local gate/install state and says built-in DashScope needs
explicit region/endpoint settings; API-key presence alone cannot select a
region. With config it evaluates that exact named or injected provider/model and
provider settings. An unverified injected object is `experimental` at most. The
worker query uses zero-argument semantics and never exposes secrets.

### Versioned Contract DTOs

The worker contract uses JSON values only. Direct-Python `Path`, provider
objects, callbacks, and cancellation objects never enter these DTOs.

```python
JSONValue = None | bool | int | float | str | list["JSONValue"] | dict[str, "JSONValue"]
WorkerProtocolVersion = Literal["ocrllm.v1alpha1", "ocrllm.v1alpha2"]


@dataclass(frozen=True, slots=True)
class SourceDescriptor:
    media_type: Literal["image", "pdf", "audio", "video"]
    uri: str


@dataclass(frozen=True, slots=True)
class ImageRecognitionRequest:
    protocol_version: Literal["ocrllm.v1alpha1"]
    command: Literal["recognize"]
    request_id: str
    sources: tuple[SourceDescriptor, ...]
    provider: Literal["dashscope"]
    model: str | None
    input_languages: tuple[str, ...]
    output_language: str | None
    profile: Literal["board"]
    options: Mapping[str, JSONValue]


@dataclass(frozen=True, slots=True)
class PdfRecognitionRequest:
    protocol_version: Literal["ocrllm.v1alpha2"]
    command: Literal["recognize"]
    request_id: str
    sources: tuple[SourceDescriptor, ...]
    provider: Literal["dashscope"] | None
    model: str | None
    input_languages: tuple[str, ...]
    output_language: str | None
    profile: None
    options: Mapping[str, JSONValue]


RecognitionRequest = ImageRecognitionRequest | PdfRecognitionRequest


@dataclass(frozen=True, slots=True)
class CapabilitiesCommand:
    protocol_version: WorkerProtocolVersion
    command: Literal["capabilities"]
    request_id: str


@dataclass(frozen=True, slots=True)
class CancelCommand:
    protocol_version: WorkerProtocolVersion
    command: Literal["cancel"]
    request_id: str


@dataclass(frozen=True, slots=True)
class AcceptedEvent:
    protocol_version: WorkerProtocolVersion
    event: Literal["accepted"]
    request_id: str


@dataclass(frozen=True, slots=True)
class ProgressEvent:
    protocol_version: WorkerProtocolVersion
    event: Literal["progress"]
    request_id: str
    stage: str
    completed: int
    total: int | None
    unit: str


@dataclass(frozen=True, slots=True)
class WarningEvent:
    protocol_version: WorkerProtocolVersion
    event: Literal["warning"]
    request_id: str
    code: str
    message: str
    details: Mapping[str, JSONValue]


@dataclass(frozen=True, slots=True)
class ErrorEvent:
    protocol_version: WorkerProtocolVersion
    event: Literal["error"]
    request_id: str | None
    code: str
    message: str
    retryable: bool
    details: Mapping[str, JSONValue]


@dataclass(frozen=True, slots=True)
class CapabilityReport:
    name: str
    status: Literal["available", "experimental", "unavailable", "deferred"]
    reason: str


@dataclass(frozen=True, slots=True)
class CapabilitiesEvent:
    protocol_version: WorkerProtocolVersion
    event: Literal["capabilities"]
    request_id: str
    capabilities: tuple[CapabilityReport, ...]


@dataclass(frozen=True, slots=True)
class ResultEvent:
    protocol_version: WorkerProtocolVersion
    event: Literal["result"]
    request_id: str
    result: "RecognitionResult"
```

BCP-47 tags are used for language fields. Canonical transport media types are
`image`, `pdf`, `audio`, and `video`; `board` is an image profile, not a media
type. `RecognitionRequest.sources` is nonempty, preserves caller order, and
contains one media type; mixed media belongs in independent batch requests.
For `ocrllm.v1alpha1`, every source is an image and every `uri` is an absolute
RFC 8089 `file:` URI. HTTP(S), relative paths, and provider credentials are
rejected. Phase 3 adds PDF fields under `ocrllm.v1alpha2`; it does not silently
widen `v1alpha1`. `v1alpha2` carries one PDF file URI with `profile=null`;
text mode requires `provider=None` and default `vision_model`, while vision requires
`provider="dashscope"` and permits a model or its documented default. Added
options are exactly `pdf_mode`, `pdf_pages`, `pdf_password`,
`pdf_allow_partial`, and `resume`; resume defaults false, requires output, and
conflicts with overwrite.

### `recognize`

```python
def recognize(
    source: str | Path | Sequence[str | Path],
    *,
    config: Config | None = None,
) -> RecognitionResult:
    ...
```

Purpose:

- Recognize one source.
- Recognize a same-type group, such as multiple board screenshots that share
  context.
- Route by file type.
- Return exactly one `RecognitionResult`.

Rules:

- A mixed-type list belongs in `recognize_batch`, not `recognize`.
- A multi-source `recognize` call is image-only. PDF, audio, and video accept
  exactly one source until a later gate defines grouped semantics.
- Missing files must fail before provider calls.
- Unsupported extensions must raise `UnsupportedFormat`.
- Provider configuration problems must raise `ConfigError`.
- Provider runtime failures must raise a provider-specific public error.
- Partial output is allowed only when represented explicitly in the result.

### `recognize_batch`

```python
def recognize_batch(
    sources: Iterable[str | Path | Sequence[str | Path]],
    *,
    config: Config | None = None,
) -> list[RecognitionResult]:
    ...
```

Purpose:

- Recognize independent sources.
- Return one result per input item.
- Preserve input order.
- Allow safe per-item failure policy later without changing the single-file API.

Default behavior is fail-fast. A later `BatchPolicy` can add
`continue_on_error` without changing `recognize`.

### `Config` and `DashScopeSettings`

`Config` is immutable and safe to pass across calls.

Target fields:

```python
@dataclass(frozen=True, slots=True)
class DashScopeSettings:
    region: str
    base_url: str
    enable_thinking: bool = False
    vl_high_resolution_images: bool = True
    standalone_sign_scout_model: str | None = None


@dataclass(frozen=True, slots=True)
class RecognitionPreferences:
    draft_candidates: int = 1
    review_passes: int = 0


@dataclass(frozen=True, slots=True)
class Config:
    provider: str | object | None = field(default=None, repr=False)
    api_key: str | None = field(default=None, repr=False)
    model: str | None = None
    dashscope: DashScopeSettings | None = field(default=None, repr=False)
    preferences: RecognitionPreferences = field(default_factory=RecognitionPreferences)
    profile: str | None = None
    input_languages: tuple[str, ...] = ()
    output_language: str | None = None
    pdf_mode: Literal["text", "vision"] | None = None
    pdf_pages: tuple[int, ...] | None = None
    pdf_password: str | None = field(default=None, repr=False)
    pdf_allow_partial: bool = False
    output_dir: str | Path | None = None
    temp_dir: str | Path | None = None
    cache_dir: str | Path | None = None
    timeout_seconds: float = 120.0
    resume: bool = False
    overwrite: bool = False
    cancellation: object | None = field(default=None, repr=False)
    extra: Mapping[str, JSONValue] = field(default_factory=dict, repr=False)
```

Design rules:

- `output_dir=None` means memory-only result.
- `temp_dir=None` means a safe OS temp location, not a package directory.
- `cache_dir=None` means a platform cache location, not a package directory.
- API keys belong to adapter settings or their documented environment variable.
- `provider=None` is valid only for local PDF `text` mode. Image, PDF `vision`,
  audio, and video requests raise `ConfigError` without a required provider;
  the library never triggers an implicit paid call.
- Phase 1 accepts an injected provider object or exact `DashScopeSettings`
  selecting the built-in adapter. String provider categories are invalid. The
  settings require explicit `region` and full OpenAI-compatible `base_url`.
  The adapter uses `Config.vision_model.name` when set and otherwise pins
  `qwen3.7-plus-2026-05-26`. The
  exact model allowlist is that snapshot plus `qwen3.7-plus`; every other value
  is `CONFIG_INVALID`.
- API keys are region-specific. Validate the `DashScopeSettings.region` and
  `base_url` pair before dispatch. Prefer a workspace-dedicated endpoint;
  accept an existing shared DashScope-domain endpoint only when explicitly
  selected. Never guess a region, workspace, or legacy endpoint.
- Initial evidence uses `enable_thinking=False` and
  `vl_high_resolution_images=True`. A different value is allowed only as an
  explicit configuration and requires its own live-quality evidence.
- The public boundary accepts only an exact `Config`, not a subclass, and
  freshly revalidates the entire value before source or provider work. That
  validation preserves the caller's object identity so injected providers
  receive the exact `Config` they were given. Named built-in image processing
  snapshots config as its first action, before provider/model resolution,
  prompt construction, or cancellation inspection, and the adapter revalidates
  that isolated copy. `Config` reconstructs nested `DashScopeSettings` at each
  snapshot, so callback mutation or `object.__setattr__` cannot diverge request
  metadata or bypass endpoint allowlisting.
- Config loading from files can exist, but it must not happen implicitly on
  `import ocrllm`.
- `profile=None` selects the modality's only approved profile; for Phase 1 image
  recognition that profile is `board`.
- A PDF request requires explicit `pdf_mode`. `pdf_pages=None` means every page;
  otherwise it is a nonempty ordered tuple of unique one-based indices.
- `pdf_password` is secret data: never log, serialize into results, or echo it
  in errors. `pdf_allow_partial=False` is the default.
- Generated/custom repr omits provider objects, `api_key`, `dashscope`,
  `pdf_password`, `cancellation`, and `extra`. Tests place unique
  sentinels in each and assert none appears in repr, errors, events, logs, or
  serialized results.
- Routing and evidence-affecting provider options belong in an approved immutable
  provider-settings value such as `DashScopeSettings`, not an exploding list of
  top-level fields. `extra` remains an extension surface for injected providers;
  the built-in adapter does not hide required routing decisions there.
- Provider objects and cancellation objects are direct-Python conveniences.
  They are never serialized into worker requests. Direct-Python progress has
  no public contract until a real consumer proves its units and lifecycle.
- Model queues and key pools are deferred until one-provider failure handling
  is complete and measured need exists.

Future configuration boundaries are recorded, not authorized for Phase 1:

- `board` is a recognition profile, not an execution engine. A possible local
  OCR engine is orthogonal to profile selection and remains unapproved work.
- Do not introduce four generic provider categories now. OpenAI-compatible
  transport, provider SDKs, local engines, and subprocess/session tools have
  different requirements and are not a closed public enum. A future Codex
  subprocess/session adapter, in particular, cannot require an API key.
- If later evidence requires policy objects, provider, model, execution, retry,
  and recognition-preferences policies are immutable values. A credential pool
  is stateful operational infrastructure and remains separate from them.
- `api_key` remains one optional string for the approved adapter path; do not
  change it to a scalar-or-tuple union. Any future multi-credential pool needs a
  separate explicit API and decision covering fair selection, cooldown, and
  provider/model quota and error domains.

### `RecognitionResult`

`RecognitionResult` is the only normal successful return type.
`Artifact` and `RecognitionResult` live in their separate contract files listed
below; they are shown together here only to make the relationship explicit.

Target fields:

```python
@dataclass(frozen=True, slots=True)
class Artifact:
    kind: str
    uri: str
    media_type: str


@dataclass(frozen=True, slots=True)
class RecognitionResult:
    protocol_version: str
    request_id: str
    markdown: str
    source_type: Literal["image", "pdf", "audio", "video"]
    status: Literal["complete", "partial"] = "complete"
    output_uri: str | None = None
    artifacts: tuple[Artifact, ...] = ()
    hotwords: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    metadata: Mapping[str, JSONValue] = field(default_factory=dict)
```

Design rules:

- `markdown` is always the primary result.
- `output_uri` is `None` unless the caller requested file output.
- `artifacts` contains final user-meaningful files, not internal temp files.
- Every artifact URI must resolve to an existing final artifact when the result
  is created.
- Partial output is `status="partial"`; it is never disguised as complete.
- `hotwords` is non-empty only when a processor extracts useful terms.
- `warnings` contains degraded-but-successful conditions.
- `metadata` is structured, stable enough for debugging, and not required for
  normal user workflows.
- Config/result/event JSON mappings are deep-copied and recursively frozen;
  nested caller dict/list mutation cannot change stored contract state.

### Public Errors

Every error type communicates the failure category without requiring
string matching.

```text
OCRLLMError          Base public exception.
ConfigError         Invalid or missing caller configuration.
DependencyMissing   A requested optional capability is not installed.
InvalidSource       Missing, unreadable, corrupt, empty, or unsafe input.
OutputError         Base class for output path and write failures.
OutputExists        OutputError for an existing target without overwrite/resume.
ProviderError       Provider call failed for a non-quota reason.
RateLimited         Provider temporarily throttled this request; retryable.
QuotaExhausted      Provider quota, billing, or purchase state blocks spending.
ProviderUnavailable Provider service is temporarily unavailable; retryable.
NoSpeechDetected    Valid audio contained no scored speech.
UnsupportedFormat   The source cannot be routed to a supported processor.
Cancelled           Caller cancellation was honored.
```

Rules:

- Every `OCRLLMError` exposes a stable `.code` from the authoritative code list;
  callers never branch on message text.
- No bare `except Exception` in processor or provider paths unless immediately
  wrapped into a public error with useful context.
- Preserve provider HTTP status, model name, and request category in redacted
  error details when the provider supplies them; use `None` for unavailable
  values.
- Secret values must never appear in exception messages.

## Package Layout

Target layout:

```text
src/ocrllm/
  __init__.py                       Public re-exports only.
  recognize.py                      recognize.
  recognize_batch.py                recognize_batch.
  config.py                         Immutable Config.
  validate_config.py                Fresh validation preserving caller identity.
  snapshot_config.py                Isolated validated Config copy.
  raise_if_cancelled.py             Event-compatible typed cancellation check.
  result.py                         Direct-Python compatibility re-export.
  processor_output.py               Internal processor outcome DTO.
  build_recognition_result.py       Public result construction/validation.
  errors.py                         Public typed failures.
  get_capabilities.py               Installed/configured/proven capabilities.
  detect_source_type.py             Source-type detection only.
  validate_source.py                File validation only.
  validate_same_type_group.py       Same-type group validation only.
  fingerprint_recognition_request.py Canonical non-secret request SHA-256.
  freeze_json_value.py              Recursive immutable JSON copy.
  thaw_json_value.py                Fresh JSON serialization copy.

  contracts/
    worker_protocol_version.py      Supported worker-version type alias.
    source_descriptor.py            One JSON-safe source descriptor.
    image_recognition_request.py    `ocrllm.v1alpha1` image request DTO.
    pdf_recognition_request.py      `ocrllm.v1alpha2` PDF request DTO.
    recognition_request.py          Public request union only.
    capabilities_command.py         Capability-query command DTO.
    cancel_command.py               Active-job cancellation command DTO.
    recognition_result.py           Complete/partial result DTO.
    artifact.py                     One final artifact descriptor.
    accepted_event.py               Recognition-accepted event DTO.
    progress_event.py               Progress event DTO.
    warning_event.py                Redacted degraded-success event DTO.
    error_event.py                  Typed redacted error DTO.
    capability_report.py            Four-state capability DTO.
    capabilities_event.py           Capability-response event DTO.
    result_event.py                 Successful-result event DTO.
    source_fingerprint.py           Source URI/size/SHA-256 DTO.
    completed_unit.py               Resumable completed-unit DTO.
    remote_task.py                  Resumable provider-task DTO.
    transcript_segment.py           One timestamped transcript segment.
    transcription_result.py         Structured ordered transcription result.
    job_state.py                    Versioned aggregate resume state.

  processors/
    recognize_images.py              Image recognition with board profile.
    recognize_pdf.py                 PDF composition.
    recognize_audio.py               Audio transcription and assembly.
    recognize_video.py               Board/audio video composition.

  providers/
    vision_provider.py               Vision capability protocol.
    resolved_vision_provider.py      Provider callable and safe identity data.
    short_audio_provider.py          Synchronous short-audio protocol.
    long_audio_provider.py           Resumable long-audio protocol.
    resolve_vision_provider.py       Explicit vision-provider resolution.
    map_injected_provider_error.py   Safe injected-provider error mapping.
    validate_provider_markdown.py    Nonempty/non-control text validation.
    dashscope/
      provider_settings.py           Immutable region/endpoint/request settings.
      resolve_dashscope_credential.py Exact credential lookup and validation.
      resolve_dashscope_model.py     Exact model allowlist and pinned default.
      load_openai.py                 Lazy OpenAI dependency/version guard.
      build_dashscope_image_request.py Exact-byte preflight and JSON request.
      create_dashscope_openai_client.py No-retry client construction.
      parse_dashscope_raw_response.py Partial-header/raw parse boundary.
      parse_dashscope_image_response.py Strict complete-choice parsing.
      recognize_images.py            One DashScope vision request.
      transcribe_short_audio.py       One synchronous short-audio request.
      submit_filetrans.py             Submit one long-audio task.
      poll_filetrans.py               Poll one persisted long-audio task.
      download_filetrans_result.py    Fetch one terminal transcript.
      map_dashscope_error.py         DashScope-to-public error mapping.

  imaging/
    decode_image.py                  Bounded path-to-bytes image read.
    decode_image_bytes.py            Exact-buffer Pillow decode/validation.
    decoded_image_info.py            Validated dimensions/pixels/format DTO.
    snapshot_image_group.py          Bounded stable provider-visible snapshots.
    normalize_image.py               Provider-required format conversion.
    resize_image.py                  Provider size-limit enforcement.

  profiles/
    build_board_prompt.py            BCP-47-aware board prompt construction.

  pdf/
    require_pdfium.py                Lazy import and version guard.
    pdfium_lock.py                   Process-wide PDFium serialization.
    inspect_pdf.py                   Document validation and page metadata.
    extract_pdf_page_text.py         One-page full-Unicode text extraction.
    calculate_pdf_render_scale.py    DPI/side/pixel limit calculation.
    render_pdf_page.py               One-page lossless rendering.
    rendered_pdf_page.py             Internal temporary-page descriptor.
    classify_pdf_page.py             Deferred; do not create without new gate.

  media/
    find_ffmpeg.py                   ffmpeg and ffprobe discovery.
    probe_media_duration.py          Duration probing.
    convert_audio.py                 Provider input conversion.
    split_audio.py                   Long audio chunking.
    merge_transcript_segments.py     Timestamp-ordered transcript assembly.
    extract_video_audio.py           Video-to-audio extraction.
    extract_video_frames.py          Ordered frame sampling.
    deduplicate_video_frames.py      Near-identical frame removal.
    merge_video_recognition.py       Timestamp-ordered video assembly.

  output/
    build_output_path.py             Stable collision-safe naming.
    write_markdown_atomically.py      Atomic optional Markdown output.
    load_job_state.py                 Versioned resume-state load.
    save_job_state_atomically.py      Atomic resume-state save.
    delete_job_state.py               Validated state cleanup.

  worker/
    read_jsonl_command.py             Read one versioned worker command.
    write_jsonl_event.py              Write protocol events only.
    run_worker_job.py                 Run one isolated child and relay events.
    run_worker_control_loop.py        Commands and 5-second process-tree kill.
    __main__.py                       Production resolver and loop entrypoint.

tests/
  fakes/
    fake_vision_provider.py          Deterministic image response only.
  quality/
    load_fixture_manifest.py         Manifest parsing and validation.
    normalize_content_units.py       NFKC/scoring normalization only.
    calculate_token_metrics.py       Recall and precision only.
    score_formula_signatures.py      Formula signature comparison only.
    score_table_cells.py             Coordinate-based table scoring only.
    calculate_wer.py                 Latin word error rate only.
    calculate_cer.py                 CJK character error rate only.
    calculate_timestamp_errors.py    Median/maximum boundary error only.
    assert_quality_thresholds.py     Apply predeclared phase thresholds.
```

Create these files only when their phase begins. The Phase 0 split is complete
at commit `5018ad0`; Phase 1 builds on `recognize.py`, `recognize_batch.py`, and
`processors/recognize_images.py`. Do not recreate the removed `api.py` or
`processors/board.py` stubs. The rule is one file, one named responsibility. Do
not create empty scaffolding for later phases.

## Layering

Allowed dependency direction:

```text
errors/config/contracts
        |
validation/detection/capabilities
        |
providers   imaging/pdf/media/output
        \       |       |       /
             processors
                 |
       recognize/recognize_batch
                 |
             __init__.py
```

Rules:

- `__init__.py` re-exports only public names.
- `recognize.py` and `recognize_batch.py` orchestrate; they do not perform OCR,
  PDF rendering, ASR, or ffmpeg work directly.
- Processors call helpers and providers.
- Helpers do not call processors.
- Providers do not know about output files.
- Output writers do not know about providers.
- Processors never write final Markdown or construct `RecognitionResult`.
  `recognize.py` calls output helpers, then `build_recognition_result.py` exactly
  once. Long processors may call job-state helpers at unit boundaries.
- Tests may use public APIs first and internals only for narrow unit coverage.

## Processor Contracts

Each processor is a vertical slice with the same basic shape:

```python
@dataclass(frozen=True, slots=True)
class ProcessorOutput:
    media_type: Literal["image", "pdf", "audio", "video"]
    status: Literal["complete", "partial"]
    markdown: str
    artifacts: tuple[Artifact, ...]
    hotwords: tuple[str, ...]
    warnings: tuple[str, ...]
    metadata: Mapping[str, JSONValue]


def recognize_<type>(
    paths: Sequence[Path],
    *,
    config: Config,
    provider: object | None,
) -> ProcessorOutput:
    ...
```

The exact function signature can change, but the responsibility must not.

### Image Processor: Board Profile

Initial Phase 0 and Phase 1 input:

- `.jpg`
- `.jpeg`
- `.png`

BMP, WebP, TIFF, HEIC, and HEIF remain unavailable until valid fixtures pass
decoder, provider, packaging, and clean-install tests. HEIC/HEIF also requires
an explicitly approved optional decoder dependency.

Responsibilities:

- Validate files.
- Normalize images only when needed.
- Preserve multi-image order.
- Enforce 25 MiB/source, 24,000,000 pixels/image, 10 images/group,
  100 MiB aggregate source, and 64,000,000 aggregate pixels before provider
  invocation; process decoded images sequentially.
- For the OpenAI-compatible adapter, read snapshots into MIME-correct Base64 data
  URLs instead of sending local paths. Enforce `10,000,000` UTF-8 bytes per
  complete data URL and 20 MiB (`20,971,520` bytes) for the fully serialized JSON.
- Enforce provider/model preflight in addition to generic limits. The initial
  DashScope baseline requires each dimension greater than 10 pixels, aspect ratio
  at most 200:1, longest side at most `7,680` pixels, and at most `16,777,216`
  pixels/image when `vl_high_resolution_images=True`.
- Decode and Base64-encode the same bounded byte buffer, then recalculate the
  final `64,000,000` aggregate-pixel cap from those exact buffers. Snapshot or
  caller-path replacement must not bypass provider preflight.
- Copy validated bytes into bounded stable snapshots and pass only those paths
  to the synchronous provider method. The provider must finish consuming them
  before it returns; cleanup starts only after that return, and no provider may
  retain the paths for background work.
- Build the board prompt.
- Call a vision-capable provider.
- Return `ProcessorOutput` with nonempty Markdown.

Must not:

- Import GUI code.
- Decide provider billing policy.
- Hide provider failures as empty Markdown.

Snapshot creation, write, and otherwise-successful cleanup failures are typed
`OUTPUT_WRITE_FAILED` errors. If provider/recognition work already raised a
typed public error, preserve that primary error and attach only redacted
`snapshot_cleanup_failed=true` detail before the error crosses the facade.

### PDF Processor

Input:

- `.pdf`

Responsibilities:

- Open and close documents through `pypdfium2` only.
- Support explicit `text` and `vision` modes. Report `auto` as `deferred`; do not
  create it until a new decision defines and passes a classifier corpus.
- Extract text layers through PDFium `get_text_bounded()` so supplementary
  Unicode is not limited by the UCS-2 `get_text_range()` path.
- Render vision-mode pages through PDFium.
- Batch pages predictably.
- Preserve one-based page order with
  `<!-- ocrllm:page index=N -->` markers in Markdown.
- Support resume when output is long-running.
- Translate encrypted, malformed, empty, out-of-range, and oversized inputs to
  typed failures before provider calls.

Must not:

- Make PDF dependencies required for image-only installs.
- Write temporary pages into the package directory.
- Import PyMuPDF or `fitz`.
- Call PDFium concurrently from multiple threads. Serialize all calls behind one
  process-wide lock or use process isolation only after measurement.
- Implement a second vision client; vision mode composes the image processor
  with the board profile.
- Claim success for a selected text-mode page with no usable text.
- Default to lossy page artifacts before PNG-versus-JPEG recognition accuracy
  has been measured; Phase 3 starts with PNG.
- Put rendered temporary pages in public `Artifact` values. A rendered page is
  an internal `RenderedPdfPage` and is deleted after the image processor has
  consumed it.

### Audio Processor

Phase 4 trial capabilities; each remains unavailable until its own atomic
format/flow subgate passes:

- `.wav` with PCM signed 16-bit audio.
- `.mp3` with MPEG Layer III audio.
- `.m4a` with AAC-LC audio.

AAC, FLAC, Ogg, Opus, and WMA extensions are deferred until one licensed fixture
per extension/codec passes probe, conversion, live transcription, packaging,
and cleanup tests.

Responsibilities:

- Probe duration.
- Choose direct transcription or chunked transcription.
- Preserve timestamps when available.
- Merge transcript chunks into coherent Markdown.

Must not:

- Swallow failed chunks silently.
- Require video dependencies for audio-only use.
- Mix provider retry policy into audio splitting code.
- Extract hotwords in the first audio slice. `RecognitionResult.hotwords` stays
  empty until a separately gated `extract_hotwords.py` behavior is justified.

### Video Processor

Phase 5 trial capabilities; each remains unavailable until its own atomic
container/codec subgate passes. Phase 5 advances only when both pass:

- `.mp4` with H.264 video and optional AAC audio.

AVI, MKV, MOV, FLV, WMV, and other codec/container combinations are deferred
until one licensed fixture per advertised combination passes probe, extraction,
recognition, packaging, and cleanup tests.

Responsibilities:

- Extract audio.
- Sample frames.
- Deduplicate near-identical frames.
- Recognize visual board/slide content.
- Transcribe audio.
- Merge visual and transcript streams into one Markdown document.

Must not:

- Own the generic audio processor.
- Own generic ffmpeg discovery.
- Make social downloader behavior part of core video recognition.

### Deferred Input Types

Office documents, social URLs, and browser content are outside the active
library phases. Do not add `.doc`, `.docx`, `.ppt`, `.pptx`, HTML, or social
download routing without a new explicit product decision after the core four
modalities are GO.

## Provider Contracts

Provider adapters are replaceable. Processors must depend on capabilities,
not vendor classes.

Minimum target capabilities:

```python
@dataclass(frozen=True, slots=True)
class TranscriptSegment:
    text: str
    start_seconds: float | None
    end_seconds: float | None
    language: str | None
    confidence: float | None
    provider_segment_id: str | None


@dataclass(frozen=True, slots=True)
class TranscriptionResult:
    status: Literal["complete", "partial"]
    segments: tuple[TranscriptSegment, ...]
    warnings: tuple[str, ...]
    metadata: Mapping[str, JSONValue]


class VisionProvider(Protocol):
    def recognize_images(
        self,
        image_paths: Sequence[Path],
        *,
        prompt: str,
        config: Config,
    ) -> str:
        ...


class ShortAudioProvider(Protocol):
    def transcribe_short_audio(
        self,
        audio_path: Path,
        *,
        prompt: str | None,
        config: Config,
    ) -> TranscriptionResult:
        ...


class LongAudioProvider(Protocol):
    def submit_long_audio(self, audio_path: Path, *, config: Config) -> RemoteTask:
        ...

    def poll_long_audio(self, task: RemoteTask, *, config: Config) -> RemoteTask:
        ...

    def download_long_audio_result(
        self,
        task: RemoteTask,
        *,
        config: Config,
    ) -> TranscriptionResult:
        ...
```

Segments are ordered, nonempty, and satisfy `0 <= start <= end` when timestamps
exist; confidence is `None` or in `[0, 1]`. Timestamp-required capability gates
fail when the provider returns `None`. Provider adapters return these DTOs;
processors never recover timestamps from Markdown.

Provider resolution:

```text
Config.provider is an object       -> use it directly after capability checks.
Config.provider == "dashscope"     -> require DashScopeSettings, validate the
                                      region/base_url pair, and load lazily.
Config.provider is another string  -> raise ConfigError.
Config.provider is None            -> allow local PDF text only; otherwise raise
                                      ConfigError and never spend implicitly.
```

Critical rule: provider adapters own HTTP details, authentication, request
format, and response parsing. Processors own media-specific workflow.

The injected-provider and built-in DashScope implementations for
`image.board.png`, `image.board.jpeg`, and `provider.dashscope.vision` are
`available`. Their offline, live Beijing, repeatability, and clean-package gates
passed under the unified v17 board workflow. This Phase 1 result authorizes
Phase 2 only; it does not authorize PDF, audio, video, or another provider.

## Optional Dependencies

The base install must import without optional dependencies. Phase 0's image extra
supports valid-image decoding tests, and fake-provider image tests remain
offline.

Target extras:

```text
ocrllm[image]    Pillow>=10.4,<13 for lazy image decoding and conversion.
ocrllm[pdf-text] pypdfium2>=5.11.0,<5.12 without Pillow.
ocrllm[pdf-vision] pypdfium2>=5.11.0,<5.12 and Pillow>=10.4,<13.
ocrllm[dashscope] Lazy openai>=2.30,<3 for the first DashScope vision adapter.
ocrllm[audio]    Do not create until Phase 4 proves exact Python requirements;
                 ffmpeg remains external.
ocrllm[video]    Do not create until Phase 5; include approved audio requirements
                 and do not bundle ffmpeg.
ocrllm[all]      All supported optional features.
ocrllm[dev]      Test and development tools.
```

The current Phase 1 distribution declares exactly `dev`, `image`, and
`dashscope`; all later target extras above remain uncreated. Base runtime
requirements are empty. Plain `import ocrllm` must not import `PIL`, `openai`,
or transitive `httpx`.

Rules:

- Missing optional dependencies must raise `DependencyMissing` with the exact
  required extra name.
- Optional dependency imports must live inside the function or module that
  needs them.
- Importing `ocrllm` must not require ffmpeg, PyQt, FastAPI, browser tools,
  provider SDKs/clients, or their transitive HTTP client.
- `ocrllm[pdf-text]` and `ocrllm[pdf-vision]` must use PDFium through
  `pypdfium2`; PyMuPDF/`fitz` is rejected.
- PDF binary distributions must include pypdfium2, PDFium, and bundled
  dependency license notices.
- `ocrllm[all]` must not exist until every included extra is independently GO.
- Every phase must pass the exact base/profile installed-size and import budgets
  in `docs/ocrllm_library_go_no_go.md`; recording a number without meeting its
  threshold is not GO.

## Output And Resume

The default result is in memory.

When `output_dir` is set:

- Create the directory if needed.
- For the initial image contract, use `{source_stem}_{profile}.md` for one image
  and `{first_stem}_plus_{additional_count}_{profile}.md` for an ordered group.
- PDF uses `{source_stem}_{pdf_mode}.md`; audio uses
  `{source_stem}_transcript.md`; video uses `{source_stem}_video.md`.
- If the target exists, raise `OutputExists` unless `overwrite=True` or an
  applicable explicit resume state is set.
- Write through a sibling temporary file and replace atomically.
- Return the Markdown URI in `RecognitionResult.output_uri`.
- Store only final user-meaningful files in `RecognitionResult.artifacts`.

Resume support applies to a completed image recognition unit and these
long-running processors:

- Image groups, after the complete processor output exists but before final
  publication.
- PDF.
- Audio.
- Video.

Version 1 uses no caller-selected or hidden state location. With final output
`lecture_vision.md`, state is the sibling
`lecture_vision.ocrllm-state.json`. `resume=True` requires `output_dir` and
conflicts with `overwrite=True`.

```python
@dataclass(frozen=True, slots=True)
class SourceFingerprint:
    uri: str
    byte_size: int
    sha256: str


@dataclass(frozen=True, slots=True)
class CompletedUnit:
    unit_id: str
    markdown: str
    artifact_uris: tuple[str, ...]
    artifact_sha256: Mapping[str, str]
    metadata: Mapping[str, JSONValue]


@dataclass(frozen=True, slots=True)
class RemoteTask:
    provider: str
    kind: str
    task_id: str
    source_sha256: str
    state: Literal["submitted", "running", "succeeded", "failed", "cancelled"]


@dataclass(frozen=True, slots=True)
class JobState:
    state_version: Literal["ocrllm.job.v1"]
    request_fingerprint: str
    processor_name: str
    processor_version: str
    sources: tuple[SourceFingerprint, ...]
    completed_units: tuple[CompletedUnit, ...]
    remote_tasks: tuple[RemoteTask, ...]
    final_markdown_sha256: str | None
```

The request fingerprint includes source fingerprints, processor/version,
provider/model, languages, profile/mode, page selection, and safety settings.
It excludes API keys, PDF passwords, output location, and cancellation objects.
Save after each completed unit and immediately after a remote task ID;
reject corrupt or mismatched state instead of silently starting over. Before
completion, persist the final Markdown hash, atomically replace the output, then
delete state. If a crash leaves state plus output, matching hashes finish without
provider calls and mismatched hashes fail. Completed-unit Markdown is plaintext
beside caller-selected output, so the caller owns directory permissions. Resume
of an encrypted PDF must reopen/authenticate with the current password before
state reuse; store only whether a password was supplied, never its value.

## Configuration And Secrets

Secret lookup order:

```text
Explicit DashScopeSettings.api_key
DASHSCOPE_API_KEY for the Phase 1 built-in adapter
ConfigError
```

Future provider adapters define and test their own environment variable before
their phase begins. There is no provider-agnostic fallback secret.

Rules:

- Never persist API keys.
- Never print API keys.
- Never include API keys in exceptions, warnings, result metadata, or logs.
- Do not silently fall back to a different paid provider.
- Do not infer a DashScope endpoint from a key or environment variable. Region
  and full base URL are explicit immutable settings because keys do not cross
  regions. Prefer workspace-dedicated endpoints; a legacy shared endpoint is an
  explicit compatibility choice only.
- The synchronous OpenAI-compatible client uses `max_retries=0`. It checks
  cancellation before preflight, between image preflights, and immediately
  before dispatch, but cannot interrupt an in-flight synchronous HTTP call.
- Build image inputs as Base64 data URLs, never caller or snapshot filesystem
  paths. Reject output truncation such as `finish_reason="length"` as an invalid
  provider response.
- Preserve image order, put the board prompt last, use `temperature=0` and
  `max_completion_tokens=16,384`, and call the raw-response SDK boundary. Accept
  `x-dashscope-partialresponse` only when absent or `false`; require the exact
  requested model and one index-0 `assistant` choice with no refusal and
  `finish_reason="stop"`.
- Distinguish temporary rate limiting (`PROVIDER_RATE_LIMITED`) and service
  availability (`PROVIDER_UNAVAILABLE`) from permanent quota/billing
  (`PROVIDER_QUOTA_EXHAUSTED`). Provider billing/quota codes take precedence
  over generic HTTP status; documented provider timeout codes take precedence
  over generic 5xx handling; and the adapter performs no retry. Invalid model
  strings are never echoed in public error data.
- Preserve a primary typed request error when client cleanup also fails, adding
  only `provider_client_cleanup_failed=true`; a cleanup-only failure is an
  invalid provider response.
- Successful image metadata records provider/model, `board.v6`, profile, image
  count, region, review passes, provider-call count, and the thinking/high-
  resolution flags, never credentials or request/source content.

The Phase 1 choices track Alibaba's [visual-understanding model and limit
reference](https://www.alibabacloud.com/help/en/model-studio/vision-model),
[OpenAI-compatible Chat Completions
reference](https://www.alibabacloud.com/help/en/model-studio/qwen-api-via-openai-chat-completions),
and [region/workspace base URL
reference](https://www.alibabacloud.com/help/en/model-studio/base-url), plus the
OpenAI Python client's [retry configuration](https://github.com/openai/openai-python#retries).

## Testing Strategy

This decision defines allowed boundaries and required gates. Tests and runtime
trials provide the evidence for a GO status; they do not override a NO-GO or
deferred boundary.

Phase 1 quality proof requires the committed, licensed five-class corpus and
manifest defined in `docs/ocrllm_library_go_no_go.md`. The user-supplied
screenshots under `docs/` remain local, supplemental, non-redistributable, and
uncommitted; they cannot substitute for gate fixtures.

Required test groups:

```text
tests/test_import_contract.py             Public facade and lightweight import.
tests/test_lightweight_import.py           PIL/openai/httpx base-import guard.
tests/test_validate_source.py             Missing/corrupt/oversized input gates.
tests/test_detect_source_type.py          Source detection and mixed groups.
tests/test_config.py                      Config normalization and secrets.
tests/test_errors.py                      Typed, redacted public failures.
tests/test_output.py                      In-memory/file output and collisions.
tests/test_provider_contracts.py          Fake capability checks.
tests/test_recognize_images.py            Image/board-profile vertical slice.
tests/test_dashscope_settings.py           Settings/endpoint/copy boundaries.
tests/test_dashscope_provider_boundaries.py Model/key/error/config boundaries.
tests/test_build_dashscope_image_request.py Exact-buffer and payload limits.
tests/test_dashscope_adapter.py            No-retry raw response and cleanup.
tests/test_jsonl_worker.py                Protocol-only worker events.
tests/test_pdfium_backend.py              Open/text/render/error PDFium behavior.
tests/test_recognize_pdf.py               Text and vision PDF composition.
tests/test_recognize_audio.py             Audio vertical slice.
tests/test_recognize_video.py             Video composition.
```

Network provider tests are opt-in and skipped by default unless required
environment variables are present.

Golden tests are small and reviewable. They prove output structure, not exact
provider wording.

## Completion Criteria

The module can be considered library-complete only when these are true:

- `pip install -e .` works.
- `pip install .` builds a wheel.
- `import ocrllm` works from outside the repo.
- `import ocrllm` has no heavyweight side effects.
- The public facade is documented and tested.
- Image recognition with the board profile works with fake and real providers.
- PDF uses PDFium through pypdfium2 and passes text/vision/error fixtures.
- PDF, audio, and video are separate tested vertical slices.
- Optional dependencies are isolated behind extras.
- Output defaults are safe for installed-package use.
- Errors are typed and do not require string matching.
- At least one downstream project imports the package without using
  `legacy_app`.
- An Electron Node harness consumes the versioned JSONL worker.
- HarmonyOS/ArkTS remains explicitly outside the completion claim.

## Implementation Phases

The exact GO conditions live in `docs/ocrllm_library_go_no_go.md`. The order is
mandatory:

```text
Phase 0  Contract honesty                         GO at 5018ad0
Phase 1  Real board/image and one provider        GO at 0278b66 plus decision
Phase 2  Versioned JSON contract and Electron JSONL worker  GO
Phase 2A Image library completion                                GO
Phase 3  PDFium text/vision PDF slice                    NOT STARTED
Phase 4  Short ASR and resumable FileTrans audio
Phase 5  Video composed from image and audio
Phase 6  Distribution, SBOM, and downstream proof
```

Do not work on two phases concurrently. A later phase starts only after the
current phase's offline and required real gates pass and `MIGRATION_STATUS.md`
records the evidence.

Phase 2A order is local OCR, generalized provider workflow configuration,
provider error taxonomies/credential pools, then image resume. See
`docs/image_library_completion_decision_2026-07-12.md` for the authoritative
slice boundaries.

Phase 2A checkpoint 1 implements the local-OCR facade/adapter and real offline
probes. Clean committed packaging and fresh-extra gates pass, so the capability
is available. Provider workflow configuration is the next slice.

Phase 2 checkpoint 1 implements the three command DTOs plus strict parsing and
serialization. It deliberately left the six event DTOs and worker process
boundary for later slices and kept the existing direct-Python
`RecognitionResult` unchanged.

Phase 2 checkpoint 2 implements that adapter and all six event DTOs. The event
envelope is the single owner of protocol/request identity; the nested worker
result contains result data only. Worker I/O and process control remain pending.

Phase 2 checkpoint 3 implements bounded binary stdin reading and protocol-only
flushed binary stdout writing. Process control, child isolation, cancellation,
and the Node harness remain pending.

Phase 2 checkpoint 4 implements public atomic capability reporting and the
control loop over a nonblocking injected job-manager protocol. The real isolated
process manager and production entrypoint remain pending.

Phase 2 checkpoint 5 implements that isolated one-job manager and five-second
descendant cancellation. The production image job, entrypoint, Node harness,
and live smoke remain pending.

Phase 2 checkpoint 6 implements the production image job as a thin adapter over
the existing unified `board` facade. The entrypoint, Node harness, and live
smoke remain pending.

Phase 2 checkpoint 7 implements the production module entrypoint with explicit
standard-stream composition and secret-safe diagnostics. The Node harness and
live smoke remain pending.

Phase 2 checkpoint 8 implements the shell-free Node harness, cross-language
event validation, Unicode path proof, and descendant cancellation. Only the
live worker smoke remains pending.

Phase 2 checkpoint 9 passes the opt-in Beijing production-worker smoke after
preserving two typed timeout attempts. Only the clean checkpoint proof and
formal GO decision remain pending in that historical checkpoint. The clean proof
now passes and Phase 2 is GO; Phase 3 has not started.

Rust/PyO3, HarmonyOS/ArkTS, browser service, Office, social download, offline
models, GPU bundles, native FFI, and WASM are deferred. They are not Phase 7;
each requires a new explicit decision after Phase 6 or an approved product
priority change.

A browser React application cannot import the Python wheel. Future React use
requires the separately authorized service boundary; the JSON-safe DTOs reduce
future adapter work but are not a current React compatibility claim.

## Rejection Rules

Reject changes that do any of the following:

- Add a dependency that imports on `import ocrllm` without being needed by the
  facade.
- Copy a whole legacy file into the active package.
- Make downstream callers import internal processors for normal use.
- Add global mutable settings as the primary configuration mechanism.
- Add hidden output paths under `src/ocrllm`.
- Add broad exception swallowing around provider or processor logic.
- Put GUI, server, or social downloader behavior into the core library.
- Add PyMuPDF or `fitz` to the active package.
- Call PDFium concurrently from multiple threads.
- Begin a later phase before the current GO gate passes.
- Add HarmonyOS/ArkTS, Rust/PyO3, Office, GPU, WASM, or offline-model work
  without a new explicit decision.

## Reader Reset

When returning after losing context, use this order:

1. `START_HERE.md`
2. `MIGRATION_STATUS.md`
3. `docs/ocrllm_library_go_no_go.md`
4. `docs/library_migration_decision.md`
5. `docs/ocrllm_module_target_design.md`
6. `src/ocrllm/README_ACTIVE_LIBRARY.md`
7. `tests/test_import_contract.py`

The current implementation is smaller than this document. That is intentional.
This file is a map for the completed module, not evidence that the module is
already complete.
