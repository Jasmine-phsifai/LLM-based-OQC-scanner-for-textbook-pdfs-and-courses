# Active Library Package

This directory is the new `ocrllm` Python package. It is the only codebase in
this repo intended for direct import by other projects.

## Public Contract

```python
from ocrllm import (
    Cancelled,
    CapabilityReport,
    ConcurrencyLimited,
    Config,
    ConfigError,
    DashScopeSettings,
    DependencyMissing,
    InvalidSource,
    LocalOCRSettings,
    NoSpeechDetected,
    OCRLLMError,
    OutputError,
    OutputExists,
    ProviderError,
    ProviderAccountSuspended,
    ProviderContentBlocked,
    ProviderErrorDisposition,
    ProviderPermissionDenied,
    ProviderRequestInvalid,
    ProviderUnavailable,
    QuotaExhausted,
    RateLimited,
    RecognitionExecutionPolicy,
    RecognitionPreferences,
    RecognitionResult,
    UnsupportedFormat,
    VisionModelSettings,
    recognize,
    recognize_batch,
    get_capabilities,
    get_provider_error_disposition,
)
```

Phase 0 contract honesty, Phase 1 real board/image, the Phase 2 development
worker, and Phase 2A image-library completion are GO. Stage M is partially
implemented: lazy DashScope catalog validation, atomic file-backed image state,
and an opt-in candidate queue are shipped. Complete attempt disclosure,
disposition-gated recovery, model-aware credential scheduling, flowed output,
and resume identity migration remain open. Stage 2 provider splitting, Phase 2
audio, and Phase 3 PDFium are not started.

The current image facade:

- accepts `.png`, `.jpg`, and `.jpeg`;
- decodes and validates every input before provider dispatch;
- copies validated bytes into request-scoped snapshots isolated from later
  caller-path changes;
- passes those ordered snapshots to one synchronous injected provider;
- rejects invalid provider output and maps failures to typed/redacted errors;
- returns `source_type="image"` and `profile="board"`;
- keeps output in memory unless `output_dir` requests atomic Markdown output;
- loads Pillow lazily from the optional `ocrllm[image]` extra.
- resolves the exact `DashScopeSettings` provider value as the built-in
  OpenAI-compatible adapter, while keeping `openai` and `httpx` lazy behind
  `ocrllm[dashscope]`; string provider categories are invalid;
- composes exact `VisionModelSettings` and fails known model/group mismatches
  before source/provider work;
- freshly revalidates an exact public `Config`; injected providers retain the
  caller's config identity, while the built-in adapter uses an isolated,
  revalidated copy.
- rejects groups above `Config.execution.maximum_images_per_request` before
  source/provider work and bounds ordered, fail-fast `recognize_batch()` jobs
  that report one `BatchItemOutcome` per source;
- applies one monotonic provider-start interval to every draft/review/scout
  call in a direct operation or across one concurrent batch.
- distinguishes provider permission, suspension, concurrency, quota,
  invalid-request, content-block, and transient failures and exposes immutable
  disposition evidence; adapters do not hide retries. The processor's explicit
  candidate queue performs bounded, disclosed recovery for quota exhaustion,
  provider unavailability, and model-scoped permission denial only.

The built-in DashScope board/image capability is available under the bounded
Phase 1 contract. The v17 Beijing gate completed exactly 52 provider calls with
no retry; both independent full-corpus runs passed. Run B repaired exactly one
missing handwriting sign through generic two-of-three omission consensus; no
handwriting route or model split exists. The committed Git-archive wheel then
passed base, `image`, and `image,dashscope` clean profiles.
`get_capabilities()` reports every known atomic capability without a network
call or optional import. With an explicit config, it reports that exact
workflow's proven status rather than treating installed code as sufficient.
Phase 2 exposes a spawned one-job manager with bounded JSON event bridging and
verified five-second descendant cancellation. The production image job adapter
reuses the same unified facade once per ordered group, fixes the Beijing v17
configuration, and adds no handwriting route, fallback, or retry.
`python -m ocrllm.worker` now composes that adapter with the isolated manager;
the shell-free Node JSONL, Unicode-path, and descendant-cancellation gates pass.
The Beijing live production-worker smoke and clean committed-source proof also
pass; `worker.jsonl.v1alpha1` is available. This remains a development worker,
not packaged Electron compatibility.
The direct facade now also has an available explicit local-OCR mode backed by
lazy maintained RapidOCR/ONNX Runtime dependencies in the `ocr` extra. It makes
zero provider/network calls and warns that OCR text extraction is not equivalent
to formula/table/layout-aware vision. Its clean committed and fresh-extra gates
pass.
The adapter requires an explicit matching region and endpoint, disables OpenAI
SDK retries, and builds Base64 data URLs rather than sending local paths. The
v17 evidence candidate uses one
thinking-enabled pinned Qwen3.7 transcript plus three independent
thinking-enabled omission ledgers from the same pinned model, each conditioned
on the quoted inert primary. Only exact allowlisted records can reach
two-of-three deterministic quorum; scout prose and unsupported punctuation
cannot enter the result. Directional-arrow insertion is forbidden while
complete primary transcription remains unchanged. Exact dynamic scout-prompt
hashes and byte counts are returned in metadata.
Qwen-VL Max remains an explicit supported scout option but is not the Phase 1
evidence baseline. A DashScope in-memory credential scheduler, model-aware
blocking, candidate recovery, and request/batch image resume are available;
there is no cross-process pool state. PDF, audio, and video remain unavailable.
Local user screenshots are uncommitted
supplemental material and never replace the committed corpus in pass/fail
evidence.

## Current Maturation Boundary

The authoritative defect register is in
`../../docs/ACTIVE_STATE_AND_RULES.md`. D1-D7, F1-F4, and G1-G10 are closed in
offline code and tests. Stage M remains open at its paid live exit smoke, and
the offline model/account quota distinction is not claimed live-proven. A crash
inside one `recognize()` call preserves completed workflow slots in the atomic
state sidecar so resume pays only for missing work.

Read `../../docs/ACTIVE_STATE_AND_RULES.md` first: it carries current state, the
defect register, and the coding rules. Then read
`../../docs/ocrllm_library_go_no_go.md` for file responsibilities, GO gates, and
the migrate/rewrite/reject boundary.

## Belongs Here

- Stable public API code.
- Provider interfaces and small provider adapters after they are tested.
- Dependency-light processing code that can be imported safely.
- Behavior ported from `legacy_app/` one tested vertical slice at a time.

## Does Not Belong Here

- PyQt GUI code.
- FastAPI server code.
- Social downloader integrations.
- Desktop launcher behavior.
- Package-relative runtime output defaults.
- Direct imports from `legacy_app` or uppercase `OCRLLM`.
- PyMuPDF or `fitz`; the future PDF slice uses PDFium through `pypdfium2`.
- HarmonyOS/ArkTS code or compatibility claims; that work is deferred.

## Tests

Use the root test suite for this package:

```powershell
uv run --no-project --isolated --with 'Pillow==12.3.0' `
  --with 'pytest>=8,<10' --with 'openai>=2.30,<3' `
  --python 'D:\Anaconda\envs\OCRLLM\python.exe' `
  python -m pytest -q -p no:cacheprovider
```

The import contract must stay true:

```powershell
& 'D:\Anaconda\envs\OCRLLM\python.exe' -c `
  "import sys; sys.path.insert(0, 'src'); import ocrllm; print(ocrllm.__version__)"
```
