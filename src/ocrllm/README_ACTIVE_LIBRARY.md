# Active Library Package

This directory is the new `ocrllm` Python package. It is the only codebase in
this repo intended for direct import by other projects.

## Public Contract

```python
from ocrllm import (
    AllCandidatesExhausted,
    AudioModelSettings,
    BatchItemOutcome,
    Cancelled,
    CapabilityReport,
    ConcurrencyLimited,
    Config,
    ConfigError,
    CredentialPoolPolicy,
    DashScopeCredential,
    DashScopeCredentialPool,
    DashScopeCredentialPoolReport,
    DashScopeCredentialSlotReport,
    DashScopeSettings,
    DependencyMissing,
    GoogleGenAISettings,
    InvalidSource,
    LocalOCRSettings,
    NoSpeechDetected,
    NoTextDetected,
    OCRBackendError,
    OCRLLMError,
    OutputError,
    OutputExists,
    PDFError,
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
    RetainedVideoFrame,
    ResumeStateError,
    UnsupportedFormat,
    VideoError,
    VideoInfo,
    VideoRecognitionOutcome,
    VisionModelSettings,
    compose_video_result,
    extract_video_audio,
    extract_video_frames,
    recognize,
    recognize_batch,
    recognize_long_mp3,
    recognize_video,
    recognize_video_frames,
    get_capabilities,
    get_provider_error_disposition,
    inspect_video,
    list_google_genai_models,
    publish_video_result,
)
```

The wheel includes an empty `py.typed` marker. This makes the inline annotations
in the installed package discoverable through the standard typed-package
contract. Static-only facade exports make documented top-level imports precise:
an isolated installed-wheel Pyright 1.1.408 probe resolves `Config` and
`RecognitionResult`, and rejects a string passed to `Config.timeout_seconds`.
This adds no runtime dependency and does not eagerly import optional providers.

Phase 0 contract honesty, Phase 1 real board/image, the Phase 2 development
worker, and Phase 2A image-library completion are GO. Stage M is offline
implementation-complete: lazy DashScope catalog validation, atomic file-backed
image state, opt-in disposition-gated candidate recovery, complete
attempt-spend disclosure, model-aware credential scheduling, and slot-indexed
intra-request checkpoints with explicit v1-to-v2 resume identity are shipped.
Its paid live exit smoke remains open. The former standalone Stage 2
provider-splitting scaffold was removed; audio-specific configuration now lands
with executable Stage A1 short-MP3 recognition. The bounded direct slice is
implemented and live-proven: the
public direct facade copies one local MP3 to a compact owned snapshot, fully
decodes it through lazy `ocrllm[audio]`, and can send one bounded native inline
request through lazy `ocrllm[google]`. This path remains experimental and
memory-only despite its successful #069 public-result gate. Stage A2a
standalone Google Files long-MP3 recognition is also implemented and
live-proven; A2b chunk/resume and long-audio video routing remain unavailable.
The first PDFium vision slice is implemented and live-proven. #120 rejected
legacy-Markdown repair, so ordinary image-sidecar resume remains its recovery
path.

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
- resolves exact `GoogleGenAISettings` through the native lazy
  `ocrllm[google]` adapter. Call `list_google_genai_models(settings)` for the
  current real-time `generateContent` catalog; model support is not hardcoded,
  and ordinary `import ocrllm` does not import `google-genai`;
- composes exact `VisionModelSettings` and fails known model/group mismatches
  before source/provider work;
- freshly revalidates an exact public `Config`; injected providers retain the
  caller's config identity, while the built-in adapter uses an isolated,
  revalidated copy.
- rejects groups above `Config.execution.maximum_images_per_request` before
  source/provider work. `recognize_batch()` requires an exact top-level `tuple`,
  preserves the existing per-item atomic path or grouped `Sequence` contract,
  and preflights every source and resolved output target before any batch-created
  filesystem or provider work. Valid jobs remain ordered and fail-fast, report
  one `BatchItemOutcome` per source, and retain output-target ownership until
  every dispatched batch item settles;
- applies one high-resolution monotonic provider-start interval to every
  draft/review/scout call in a direct operation or across one concurrent batch.
- distinguishes provider permission, suspension, concurrency, quota,
  invalid-request, content-block, and transient failures and exposes immutable
  disposition evidence; adapters do not hide retries. The processor's explicit
  candidate queue performs bounded, disclosed recovery for quota exhaustion,
  provider unavailability, and model-scoped permission denial only.

The public injected-provider method returns one Markdown `str`. The structured
response used internally to carry built-in adapter usage is not exported and is
not a public third-party provider contract.

The built-in DashScope board/image capability is available under the bounded
Phase 1 contract. The v17 Beijing gate completed exactly 52 provider calls with
no retry; both independent full-corpus runs passed. Run B repaired exactly one
missing handwriting sign through generic two-of-three omission consensus; no
handwriting route or model split exists. The committed Git-archive wheel then
passed base, `image`, and `image,dashscope` clean profiles.
`get_capabilities()` reports every entry in the frozen shared
capability/worker registry without a network call or optional import. With an
explicit config, it reports that exact registered workflow's proven status
rather than treating installed code as sufficient. Experimental direct facades
may be described separately without implying worker registration.
The direct Google image adapter is experimental. Its current model catalog is
queried only by explicit Google operations, not by import or shared capability
reporting. Public failures distinguish zero recognition calls before
`generate_content()` from one call after entering it; catalog discovery itself
is not counted as a recognition call.

The experimental direct Google short-audio facade:

- requires `ocrllm[audio,google]`, exact `GoogleGenAISettings`, and exact
  `AudioModelSettings(name=...)`;
- accepts exactly one `.mp3` of at most 300 decoded seconds;
- honors an already-set cancellation signal before snapshot/copy/decode and
  checks again before provider dispatch; a synchronous SDK call already in
  progress is not interruptible;
- snapshots and fully decodes the source, then preflights a conservative native
  inline Base64/JSON envelope below 20,000,000 bytes;
- sends the prompt first and one `audio/mpeg` Part second;
- returns an in-memory `RecognitionResult` with `source_type="audio"`, exact
  provider/model/call metadata, duration and byte size, and nullable per-model
  input/output token usage;
- rejects output persistence, `resume=True`, `overwrite=True`, groups, MP3s
  longer than 300 seconds, and false no-speech/refusal success;
- performs no internal retry, model switching, Files upload, cache, fallback,
  or output logging.

The standalone Google Files long-MP3 facade is also experimental:

```python
from ocrllm import AudioModelSettings, Config, GoogleGenAISettings, recognize_long_mp3

result = recognize_long_mp3(
    "lecture.mp3",
    config=Config(
        provider=GoogleGenAISettings(),
        audio_model=AudioModelSettings(name="gemini-2.5-flash"),
        timeout_seconds=600,
    ),
)
```

- requires one fully decoded MP3 longer than 300 seconds and no longer than the
  current Google single-prompt limit of 9.5 hours;
- snapshots through bounded chunked disk I/O, with a 2 GB Files limit, and does
  not load the complete audio or decoded PCM into Python memory;
- discovers the live `generateContent` catalog, uploads once, waits only within
  `timeout_seconds`, generates once, then deletes the remote file and closes the
  client;
- returns an in-memory audio result with exact model/usage/source facts and
  explicit cleanup state; a successful transcript becomes `partial` with a
  warning if remote or client cleanup fails;
- has no chunking, resume, persistence, parallel splitting, fallback, model
  switching, batch support, worker route, or automatic video integration.

The PDF vision facade:

- requires `ocrllm[pdf-vision]` and accepts exactly one `.pdf`;
- snapshots at most 100 MiB with bounded reads, inspects all page sizes before
  dispatch, and serializes every PDFium call behind one process-wide lock;
- renders one page at a time and at most eight PNGs per ordinary image request;
- uses the image facade and its sidecars unchanged, so resume reuses settled
  groups without another provider call;
- requires a pre-existing same-named state path to be an ordinary directory;
  symlinks and Windows junctions fail before rendering or provider dispatch;
- publishes stable `ocrllm:pdf-pages` range markers in source order and removes
  rendered PNGs after each group;
- creates no PDF-specific provider, checkpoint schema, worker contract, page
  selector, password input, partial-success setting, text mode, or retry path;
- is rejected by `recognize_batch()` in this first slice.

Neither direct audio path nor the PDF path is registered in the frozen 20-entry
shared capability/worker contract, and neither is worker support.
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
there is no cross-process pool state. File-producing calls claim one output target
for the duration of a recognition, so direct threads and `recognize_batch()` cannot
split final Markdown from its resume sidecar. The claim is process-local: separate
processes must not target the same output path concurrently. PDF repair, long
audio chunking, and persisted/resumable audio remain unavailable. #120 explicitly rejects
legacy repair-Markdown compatibility. PDF recognition is offline- and
Google-live-proven.

The provider-free video parsing and separately configured recognition slices
are available:

```python
from pathlib import Path

from ocrllm import (
    AudioModelSettings,
    Config,
    GoogleGenAISettings,
    VisionModelSettings,
    extract_video_audio,
    extract_video_frames,
    inspect_video,
    publish_video_result,
    recognize,
    recognize_video,
    recognize_video_frames,
)

info = inspect_video("lecture.mp4")
frames = extract_video_frames("lecture.mp4", output_dir="output")
image_outcomes = recognize_video_frames(
    frames,
    config=Config(
        provider=GoogleGenAISettings(),
        vision_model=VisionModelSettings(name="gemini-2.5-flash"),
    ),
)
video_root = Path("output") / "lecture"
audio_path = extract_video_audio(
    "lecture.mp4",
    output_path=video_root / "audio.mp3",
)
audio_result = recognize(
    audio_path,
    config=Config(
        provider=GoogleGenAISettings(),
        audio_model=AudioModelSettings(name="gemini-2.5-flash"),
    ),
)

video_outcome = recognize_video(
    "another-lecture.mp4",
    output_dir="output",
    image_config=Config(
        provider=GoogleGenAISettings(),
        vision_model=VisionModelSettings(name="gemini-2.5-flash"),
    ),
    audio_config=Config(
        provider=GoogleGenAISettings(),
        audio_model=AudioModelSettings(name="gemini-2.5-flash"),
    ),
)
if video_outcome.status != "failed":
    video_result = publish_video_result(
        video_outcome,
        "output/another-lecture.md",
    )
```

Install `ocrllm[video]` for provider-free inspection and frame/audio extraction.
The complete native-Google recognition example above requires
`ocrllm[video,image,audio,google]`. `inspect_video()` accepts one local MP4,
validates metadata and a real first-frame decode, returns immutable `VideoInfo`,
writes nothing, and makes no provider call. Its duration comes from the MP4
container rather than `frame_count / FPS`, so variable-frame-rate input does
not receive a fabricated constant-rate duration. MP4 display-rotation metadata
is applied by the pinned OpenCV backend: `VideoInfo` dimensions and retained
JPEG pixels both use the decoded display orientation rather than the encoded
landscape storage dimensions.
`extract_video_frames()` adds five-second coarse thumbnails, bounded
count-driven negative-feedback selection, and ordered immutable
`RetainedVideoFrame` records. Coarse seeks use presentation time and each
retained timestamp is the decoded frame's actual presentation timestamp; FPS
remains informational rather than the timestamp clock. Comparison keeps the
existing 128x128 luminance detail plus a 32x32 color thumbnail, so sampled
color-only scene changes are not erased merely because their grayscale
luminance matches. It publishes validated JPEGs together under
`output/lecture/frames/` and rejects an existing `output/lecture` instead of
overwriting or resuming it. This is not a fine-gap scene detector: content that
appears entirely between two coarse samples can be absent from the retained
tuple. `recognize_video_frames()` accepts only the exact
ordered tuple returned by this library and reuses ordinary image recognition
in groups of at most eight. It is memory-only and returns one existing
`BatchItemOutcome` per group. Every successful result carries exact
`video_frame_indices` and `video_frame_timestamps_seconds` metadata; the same
identity is attached to typed failure details, including an undispatched
cancelled suffix. Deterministic image-provider configuration errors, including
a missing explicit Google vision model, raise before retained-JPEG validation
instead of becoming a failure for the first frame group. This frame-only
function does not compose a video document or persist/resume recognition;
those are separate library responsibilities.
`extract_video_audio()` requires the output parent
to exist, rejects an existing target, and atomically publishes a fully decoded
mono 16 kHz / 32 kbps MP3. Extraction itself has no duration ceiling. The
function raises `VideoError(code="VIDEO_NO_AUDIO_STREAM")` when the MP4 is
valid but has no audio stream; present-but-corrupt or undecodable audio remains
`VIDEO_INVALID`, so callers do not have to parse FFmpeg text. The
current audio recognizer remains the separately installed `audio,google`
short-MP3 slice (maximum 300 decoded seconds and 25 MiB), so longer extracted
tracks fail honestly at recognition. Image and audio providers are selected by
the two separate `Config` objects. `recognize_video()` validates both configs
before reading the source, creating retained media, or dispatching either
provider. It then uses those same proven boundaries and returns a
`VideoRecognitionOutcome`: retained media, ordered
frame-group outcomes or a typed frame error, and an audio result or typed audio
error. A silent MP4 can therefore complete as frame-only, while corrupt audio or
a provider failure remains partial or failed. The call does not compose or
publish final Markdown and does not delete its retained frames or MP3. A
caller should inspect the branch results/errors and top-level status first;
`compose_video_result()` accepts only complete or partial outcomes and leaves a
fully failed outcome as structured failure evidence. An explicitly partial
image-group or audio `RecognitionResult` keeps the video outcome and
later composed result partial; complete means every usable child result is
complete. Successful frame-group outcomes must contain exact image
`RecognitionResult` values; non-image results are rejected before composition.
`VideoRecognitionOutcome` uses an exact lexical artifact layout:
every retained frame path has parent `output_root / "frames"`, and an audio
artifact, when present, is exactly `output_root / "audio.mp3"`.
Retained frame indices must be strictly increasing and their timestamps must
not move backward. Frame-group outcome indices must be the contiguous caller
order `0..n-1`. Every settled group must also carry valid frame indices and
timestamps whose flattened identity exactly equals the retained-frame tuple;
the outcome constructor rejects missing or drifted identity before `status`
can report a misleading completion.
`VIDEO_NO_AUDIO_STREAM` must be carried by a `VideoError` and cannot be paired
with an audio artifact. Manual constructors must reuse
those same `Path` values; the contract does not resolve aliases or symlinks.
`compose_video_result()` is an explicit, provider-free second step for an
already returned complete or partial outcome. It creates one memory-only
`RecognitionResult(source_type="video")` with separate ordered Video frames and
Video audio sections, exact retained-frame identities, honest stable error codes,
all retained media in `assets`, current-run provider-call totals, and
provider-reported input/output tokens accumulated separately by model. It does
not infer a zero from missing branch call evidence: the total is `None` unless
every settled provider branch supplies an exact nonnegative count. A silent
video or video/audio parsing failure before provider dispatch contributes a
known zero. Composition does not align audio text to frame timestamps, publish
a file, parse legacy output, or accept a fully failed outcome.
`publish_video_result()` is the separate provider-free final-output step. It
accepts the same complete or partial outcome and one explicit path, reuses the
same composition, atomically writes Markdown, refuses an existing target by
default, supports explicit `overwrite=True`, and rejects a target that equals
one of the retained frame/audio assets. Its returned standard video result
preserves the composition and has the verified output path. It does not
recognize again, derive a legacy filename, create resume state, or publish a
fully failed outcome. Automatic fallback, resume, and worker routing remain
unavailable. Plain
`import ocrllm` does not import OpenCV, NumPy, or imageio-ffmpeg.
Local user screenshots are uncommitted
supplemental material and never replace the committed corpus in pass/fail
evidence.

## Bounded Google Image Live Smoke

Install `ocrllm[image,google]`, set `GOOGLE_API_KEY` (or `GEMINI_API_KEY`) in
the environment without placing its value on the command line, and run from the
repository root with authorized images:

```powershell
# GOOGLE_API_KEY is already present in this process; do not echo it.
python tools/run_google_genai_image_smoke.py `
  --model gemini-2.5-flash `
  --image tests/fixtures/phase1/images/bilingual_printed_slide.png `
  --timeout 120
```

The routine script performs current catalog discovery and one single-image
public recognition. It prints only a bounded JSON summary with a safe
catalog/model-selection/recognition failure stage, never recognized Markdown,
paths, credentials, or provider text. It does not retry, cache, choose another
model, send an extra invalid-key probe, or fall back to another transport. The
historical one-image, eight-image, and credential gates remain recorded.

## Bounded Google Short-Audio Live Smoke

Install `ocrllm[audio,google]`, set `GOOGLE_API_KEY` (or `GEMINI_API_KEY`) in
the environment without placing its value on the command line, and run one
explicit authorized MP3 from the repository root:

```powershell
# GOOGLE_API_KEY is already present in this process; do not echo it.
python tools/run_google_genai_audio_smoke.py `
  --model gemini-2.5-flash `
  --audio path/to/authorized-short-speech.mp3 `
  --timeout 120
```

The script performs current catalog discovery and one recognition call. It
prints only a bounded JSON summary of status, call count, nullable token usage,
and typed error code/scope; a failure also identifies `catalog`,
`model_selection`, or `recognition` as the safe runner stage. It never prints
the transcript, source path, credential, or raw provider response and does not
retry, choose another model, upload through the Files API, or fall back to
another transport. Credential-error behavior remains independently covered by
historical image and audio gates; routine image and audio runs do not send an
extra invalid-key request. The #068 gate returned
`PROVIDER_QUOTA_EXHAUSTED` / `model` on `gemini-3.1-pro-preview`. The #069 gate
then used `gemini-2.5-flash` and completed one real public result with exactly
one provider call, input/output usage 150/10, and a credential-scoped invalid-key
failure. Its recognized text was validated internally but not published, so the
gate proves this bounded result path rather than transcription quality.

## Bounded Google PDF Live Smoke

Install `ocrllm[pdf-vision,google]`, set `GOOGLE_API_KEY` (or
`GEMINI_API_KEY`) without placing its value on the command line, and invoke
`tools/run_google_genai_pdf_smoke.py` with exactly sixteen authorized
`--page-image` arguments. The tool builds a temporary PDF, discovers the
current catalog, and requires exactly two serial eight-page recognition calls,
two complete child checkpoints, ordered range markers, atomic final output,
current per-model token usage, and zero retained page PNGs. It prints no OCR
body or path and performs no retry, fallback, model switching, or third batch.
The successful #078 gate discovered 37 current models and used
`gemini-2.5-flash` for exactly two serial calls over sixteen pages. It reported
aggregate input/output usage of 4,802/117, two complete child checkpoints,
ordered published output, and zero retained rendered pages. The foreground
process exited 0 after 12.719 seconds with empty stderr, no credential-shaped
captured text, no retry or fallback, and both temporary roots removed.

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
- PyMuPDF or `fitz`; the active PDF slice uses PDFium through `pypdfium2`.
- HarmonyOS/ArkTS code or compatibility claims; that work is deferred.

## Tests

Use the root test suite for this package:

```powershell
uv run --no-project --isolated --with 'Pillow==12.3.0' `
  --with 'pytest>=8,<10' --with 'openai>=2.30,<3' `
  --with 'pypdfium2==5.11.0' --with 'miniaudio>=1.71,<2' `
  --python 'D:\Anaconda\envs\OCRLLM\python.exe' `
  python -m pytest -q -p no:cacheprovider
```

The import contract must stay true:

```powershell
& 'D:\Anaconda\envs\OCRLLM\python.exe' -c `
  "import sys; sys.path.insert(0, 'src'); import ocrllm; print(ocrllm.__version__)"
```
