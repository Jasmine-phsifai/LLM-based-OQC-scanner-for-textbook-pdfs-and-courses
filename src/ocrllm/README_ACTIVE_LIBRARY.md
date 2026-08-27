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
    recognize_video_to_markdown,
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
Its bounded paid live exit was closed by #339. The former standalone Stage 2
provider-splitting scaffold was removed; audio-specific configuration now lands
with executable Stage A1 short-MP3 recognition. The bounded direct slice is
implemented and live-proven: the
public direct facade copies one local MP3 to a compact owned snapshot, fully
decodes it through lazy `ocrllm[audio]`, and can send one bounded native inline
request through lazy `ocrllm[google]`. This path remains experimental and
memory-only despite its successful #069 public-result gate. Stage A2a
standalone Google Files long-MP3 recognition is also implemented and
live-proven; its whole-file public facade now has optional publication and
resume. `recognize_video()` selects inline audio through 300 seconds or
whole-file Files above 300 seconds by default. Its optional
`audio_interval_minutes` selects ordered Files intervals using an exact positive
integer number of minutes; settled state is written under the video-owned output
root and removed only after a complete clean audio result. Failed and partial
audio outcomes retain any settled state. The low-level `recognize_video()` call
does not consume retained state. The high-level
`recognize_video_to_markdown()` call now owns
one complete video journal, validates all saved media/request identity before
dispatch, and resumes only missing image/audio work;
interval mode nevertheless accepts sources through the private 10-hour product
ceiling. Install `ocrllm[audio]` for both its
lazy MP3 decoder and interval FFmpeg backend; neither loads during plain import.
An audio-only resume flag would still replay paid image groups and cannot bind
an existing output root to the source video or short-audio result. The shipped
high-level job instead owns one temporary journal and atomic `result.md`
publication. A terminal no-speech result with a proved failed Google
audio-client close preserves the existing warning and exposes
`audio_provider_client_closed=False`, including after zero-call resume; generic
provider-error details are not lifted into the combined result. If recognized
or no-speech short audio settles but its journal update fails, the typed save
error retains the known provider-call and client-close facts; a recognized
or exact Google no-speech settlement also retains current model usage. Exact
no-speech usage is saved with the audio state, but a zero-call resume does not
relabel that history as current usage. It does not claim an unsaved resumable
unit.
The current three-step API remains non-resumable and gains no finalize/discard
protocol.
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
  revalidated copy;
- rejects an already-set cancellation signal after deterministic config and
  source-shape validation but before the provider start gate, output/temp
  directory creation, image snapshotting, or provider work. The typed error
  reports exact zero calls; built-in provider request metadata is snapshotted
  before observing a user-defined cancellation callback;
- rechecks cancellation after a completed sidecar is atomically saved and
  before Markdown publication; cancellation in that interval leaves the
  complete sidecar reusable and a later resume publishes with zero new calls;
- rejects groups above `Config.execution.maximum_images_per_request` before
  source/provider work. `recognize_batch()` requires an exact top-level `tuple`,
  preserves the existing per-item atomic path or grouped `Sequence` contract,
  and preflights every source and resolved output target before any batch-created
  filesystem or provider work. Valid jobs remain ordered and fail-fast, report
  one `BatchItemOutcome` per source, and retain output-target ownership until
  every dispatched batch item settles. An already-cancelled batch still
  validates the complete tuple/member shape and deterministic configuration,
  then returns ordered cancellation/not-attempted outcomes before source reads,
  output/resume inspection, audio credential resolution, or executor creation;
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
Compatible-endpoint `prompt_tokens` and `completion_tokens` are preserved as
nullable input/output counts and accumulated by exact model across fresh
draft/review/scout calls. If opt-in candidate recovery advances to another
model, usage from every already-settled model remains ordered in the final
success or terminal typed error. Missing or malformed usage remains unknown and
cannot discard otherwise valid recognized Markdown.
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
A successfully parsed Google image response is preserved as `partial`, with an
explicit warning and `provider_client_closed=False`, if only SDK client cleanup
fails. An earlier provider or parse error remains primary and records the
cleanup failure. This does not add retry, fallback, or a public structured
provider-response contract.

The experimental direct Google short-audio facade:

- requires `ocrllm[audio,google]`, exact `GoogleGenAISettings`, and exact
  `AudioModelSettings(name=...)`;
- accepts exactly one `.mp3` of at most 300 decoded seconds;
- honors an already-set cancellation signal before snapshot/copy/decode and
  checks again before provider dispatch; a synchronous SDK call already in
  progress is not interruptible, and a valid response that settles while the
  signal becomes set is returned because this memory-only call has no
  checkpoint from which to recover it;
- snapshots and fully decodes the source, then preflights a conservative native
  inline Base64/JSON envelope below 20,000,000 bytes;
- sends the prompt first and one `audio/mpeg` Part second;
- returns an in-memory `RecognitionResult` with `source_type="audio"`, exact
  provider/model/call metadata, duration and byte size, and nullable per-model
  input/output token usage;
- retains the same provider-reported per-model token row on an exact typed
  no-speech result instead of dropping the completed call's accounting;
- preserves a successfully parsed transcript as `partial`, with an explicit
  warning and `provider_client_closed=False`, if only SDK client cleanup fails;
  an earlier provider error remains primary and records the cleanup failure;
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
        output_dir="transcripts",
    ),
)
```

Set `interval_minutes` to an exact positive integer to make a persistent long
run recoverable at that many minutes per logical request:

```python
result = recognize_long_mp3(
    "lecture.mp3",
    config=Config(
        provider=GoogleGenAISettings(),
        audio_model=AudioModelSettings(name="gemini-2.5-flash"),
        output_dir="transcripts",
    ),
    interval_minutes=10,
)
```

After an interrupted run, repeat the call with `resume=True` in `Config`. The
resume call may omit `interval_minutes` because temporary state retains the
original choice.

- requires one fully decoded MP3 longer than 300 seconds; whole-file mode stops
  at the current Google single-prompt limit of 9.5 hours, while explicit
  interval mode accepts the private product ceiling of 10 hours;
- snapshots through bounded chunked disk I/O, with a 2 GB Files limit, and does
  not load the complete audio or decoded PCM into Python memory;
- discovers the live `generateContent` catalog and rejects before upload when
  the documented 32 audio tokens per second alone meet or exceed the selected
  model row's advertised input limit; absent optional metadata preserves the
  provider path, and this does not claim the prompt also fits;
- uploads once, waits only within `timeout_seconds`, generates once, then deletes
  the remote file and closes the client; client close is still attempted if
  remote deletion is interrupted by `KeyboardInterrupt` or `SystemExit`, while
  that exact process-control exception continues to propagate;
- consumes one configured provider-start permit before SDK and Files workflow
  work; catalog, upload, polling, generation, and cleanup remain one lifecycle,
  not separately paced requests;
- returns an audio result with exact model/usage/source facts and explicit
  cleanup state; with `output_dir`, it first saves the settled paid result,
  atomically publishes `<output_dir>/<audio stem>/result.md`, and then removes
  the temporary state; if the whole-file state save itself fails after the one
  provider call completed, the typed error still reports that one attempted
  call; if final Markdown publication fails after whole or interval settlement,
  the typed error also retains current-run per-model token usage and exact
  remote-file/client-cleanup facts while the reusable state remains in place;
  if publication succeeds but temporary-state removal fails, the published
  result is returned as `partial` with `resume_state_removed=False` and one
  warning, and the caller owns cleanup of the retained sidecar;
- records a paid whole-file no-speech outcome and its provider-reported token
  usage in the same temporary state;
  explicit resume then raises the same typed no-speech result with zero new
  provider calls and no false current-run usage, and the internal sentinel is
  never published as Markdown;
- accepts `resume=True` only with that fixed state present and an unpublished
  final result; an exact whole-file or interval prefix is reused with zero calls
  for settled work, while source/model/prompt/transport/interval drift is rejected;
  after strict state and mode validation, an incomplete prefix requires an
  available Google credential before the source is snapshotted or an interval
  is materialized, while a fully settled state remains credential-free;
- interval mode requires `output_dir`, recognizes missing windows serially, and
  saves every settled speech or no-speech window before starting the next one;
  if every window is no-speech, both the initial typed result and exact
  zero-call resume aggregate remote-file deletion and client-close facts from
  all saved windows;
- has no overwrite, repair integration, parallel splitting, fallback, model
  switching, batch support, worker route, or automatic video integration.

The PDF vision facade:

- requires `ocrllm[pdf-vision]` and accepts exactly one `.pdf`;
- rejects an existing final Markdown before source snapshotting or PDFium work
  unless the configured overwrite/resume mode permits that target;
- snapshots at most 100 MiB with bounded reads, inspects all page sizes before
  dispatch, and serializes every PDFium call behind one process-wide lock;
- renders one page at a time and at most eight PNGs per ordinary image request;
- uses the image facade and its sidecars unchanged, so resume reuses settled
  groups without another provider call;
- accepts provider-free `Config(image_mode="ocr")` when the `ocr` extra is
  installed; final PDF metadata aggregates the uniform RapidOCR engine/version,
  image count, retained-line count, and exact zero-network fact from every
  settled group;
- retains a first-group sidecar when child Markdown publication fails without
  misreporting the intentionally nonempty state directory as a cleanup failure;
  the typed publication error also retains validated current-run per-model token
  usage already stored in that sidecar;
  explicit resume reuses that sidecar with zero new provider calls and publishes
  both child and final PDF Markdown;
- requires a pre-existing same-named state path to be an ordinary directory;
  symlinks and Windows junctions fail before rendering or provider dispatch;
- publishes stable `ocrllm:pdf-pages` range markers in source order and removes
  rendered PNGs after each group;
- creates no PDF-specific provider, checkpoint schema, worker contract, page
  selector, password input, partial-success setting, PDF text-layer mode, or
  retry path;
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
pass. If inference settles but owned snapshot cleanup or final publication
fails, the typed error retains the engine/version and image/retained-line counts
without embedding recognized text or confidence data.
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
processes must not target the same output path concurrently. PDF repair remains
unavailable, and #120 explicitly rejects legacy repair-Markdown compatibility.
Short MP3 remains memory-only; standalone long-MP3 whole/interval publication
and resume are available through `recognize_long_mp3()`. PDF recognition is
offline- and Google-live-proven.

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
    # Optional: use exact integer-minute Files intervals instead of whole mode.
    audio_interval_minutes=10,
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
not receive a fabricated constant-rate duration. If the caller path undergoes
an ordinary overwrite or replacement while those reads are in progress, the
function raises typed `SOURCE_INVALID` instead of returning metadata mixed from
two file versions. This check does not copy or hash the whole video and is not
an adversarial integrity guarantee. MP4 display-rotation metadata
is applied by the pinned OpenCV backend: `VideoInfo` dimensions and retained
JPEG pixels both use the decoded display orientation rather than the encoded
landscape storage dimensions.

The image branch may instead use provider-free local OCR while the audio branch
continues to use Google: pass `image_config=Config(image_mode="ocr")`, keep the
separate Google `audio_config`, and install the union
`ocrllm[video,ocr,audio,google]`. This combination retains complete video frames,
makes zero image-provider/network calls, and does not change the audio provider.
`extract_video_frames()` adds five-second coarse thumbnails, bounded
count-driven negative-feedback selection, and ordered immutable
`RetainedVideoFrame` records. Coarse seeks use presentation time and each
retained timestamp is the decoded frame's actual presentation timestamp; FPS
remains informational rather than the timestamp clock. Comparison keeps the
existing 128x128 luminance detail plus a 32x32 color thumbnail, so sampled
color-only scene changes are not erased merely because their grayscale
luminance matches. This is bounded rather than small: with the five-second
grid, a ten-hour input retains at most 7,201 candidates whose two `uint8`
thumbnail arrays total about 133.6 MiB; measured process-private growth was
about 143.1 MiB at candidate retention. Inputs requiring more than 10,000
candidates are rejected before allocation. It publishes validated JPEGs
together under `output/lecture/frames/` and rejects an existing
`output/lecture` instead of overwriting or resuming it. On Windows, retained
JPEG bytes are written through
Python's file API after OpenCV encoding, so non-ASCII source and output parents
do not depend on OpenCV's filename encoding. Source-derived directory names are
capped, but caller-supplied output parents are not shortened or converted to
Windows extended paths. On a host with Windows long paths disabled, a retained
JPEG path beyond the traditional limit fails with typed `OUTPUT_PATH_INVALID`
and publishes no target or staging artifact. This is not a fine-gap scene
detector: content that appears entirely between two coarse samples can be
absent from the retained tuple. Sampled edits below the calibrated changed-pixel
threshold are likewise not guaranteed, although a real short-lived high-contrast
text line affecting about 2.29% of the comparison thumbnail is retained by the
current accumulated-drift rule. One bounded live Google run then sent retained
frames 0/5/19 in a single image group and confirmed the model output contained
both distinctive `IMPORTANT` and `42` content; silent audio made no provider
call. A separate real five-minute probe alternated a small cursor every second:
61 coarse candidates calibrated to six retained frames while published JPEGs
still represented both sides of one genuine major slide transition.
`recognize_video_frames()` accepts only the exact
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
Each public `RetainedVideoFrame` must name a `.jpg` path, matching the library's
retained-asset format. The existing image preflight still owns file existence
and JPEG byte validation; the value object does not add another decoder or path
resolution policy.
`extract_video_audio()` requires the output parent
to exist, rejects an existing target, streams the caller MP4 into one hidden
request-owned snapshot there, and atomically publishes a fully decoded mono
16 kHz / 32 kbps MP3. Extraction itself has no duration ceiling. The
function raises `VideoError(code="VIDEO_NO_AUDIO_STREAM")` when the MP4 is
valid but has no audio stream; present-but-corrupt or undecodable audio remains
`VIDEO_INVALID`, so callers do not have to parse FFmpeg text. The
combined recognizer uses the separately installed `audio,google` routes: it
owns and fully decodes the extracted MP3 once, then selects inline recognition
through 300 seconds, Google Files whole-audio above 300 seconds through the
9.5-hour single-request ceiling by default, or explicit integer-minute Files
intervals through the private 10-hour product ceiling. It does not try short
recognition first or probe a second copy. Image and audio providers are selected
by the two separate
`Config` objects. Standalone frame extraction and standalone
audio extraction each own one hidden snapshot under their output parent.
Combined video recognition instead owns one shared snapshot under `output_dir`:
inspection, negative-feedback comparison, retained-JPEG decode, and audio
extraction consume that same path without copying the video twice. Every owned
snapshot is removed before its call exits and is never a public asset or legacy
compatibility format. Both public retained-video entries require `output_dir`
to be a nonempty string or `Path`; they reject empty/whitespace strings and
signature-external path-like objects before source access rather than treating
an empty value as the process cwd. `recognize_video()` validates both configs
before reading the source, creating retained media, or dispatching either
provider. That preflight requires each non-null cancellation signal to expose a
callable `is_set` member. When exactly one branch is already cancelled, the call
returns a partial outcome with `Cancelled` in that branch's existing error
field and preserves the other branch; pre-cancelled audio skips MP3 extraction.
When both branches are already cancelled, it raises before source or output
work. A later cancellation raised by either recognition branch is settled the
same way. This adds neither mid-extraction cancellation nor a new outcome type.
For an injected image provider, that
preflight includes its existing callable `recognize_images` contract; the
execution path checks again in case the caller mutates the object. It then uses
those same proven boundaries and returns a `VideoRecognitionOutcome`: retained
media, ordered
frame-group outcomes or a typed frame error, and an audio result or typed audio
error. Silent audio is a media outcome, not a relaxed configuration mode: the
required audio `Config` must still pass preflight before the source is inspected.
A silent MP4 with valid configs can therefore complete as frame-only, while
corrupt audio or an audio-provider failure remains partial or failed. If a
present audio stream cannot be decoded locally, the independent image branch
may still complete; audio makes zero provider calls, carries `VIDEO_INVALID`,
and publishes no MP3.
The call does not compose or publish final Markdown and does not delete its
retained frames or MP3. A
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
Long video audio keeps whole-file recognition as the default. Passing
`audio_interval_minutes` uses the existing serial long-audio interval planner;
the value must be an exact positive built-in integer. Each paid interval is
saved immediately to `output_root / ".ocrllm-video-audio-resume.json"`; a later
failure keeps that state, while clean recognition and snapshot cleanup remove
it before returning. No nested `audio/result.md` or video `result.md` is
created. The low-level `recognize_video()` call cannot consume retained state;
use `recognize_video_to_markdown(..., resume=True)` for the library-owned video
journal and fixed `result.md`. Repair remains a separate future text-range side
path rather than a state consumer.
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
provider-reported input/output tokens accumulated separately by model in first
settled frame-group order, followed by audio. It does
not infer a zero from missing branch call evidence: the total is `None` unless
every settled provider branch supplies an exact nonnegative count. A silent
video or video/audio parsing failure before provider dispatch contributes a
known zero. Composition does not align audio text to frame timestamps, publish
a file, parse legacy output, or accept a fully failed outcome.
`publish_video_result()` is the separate provider-free final-output step. It
accepts the same complete or partial outcome and one explicit path, reuses the
same composition, atomically writes Markdown, refuses an existing target by
default, supports explicit `overwrite=True`, and rejects a target that equals
one of the retained frame/audio assets, including an existing hard-link alias.
The `output_root/audio.mp3` identity remains reserved for video audio even when
the settled video is silent; nonexistent lexical aliases such as
`frames/../audio.mp3` are rejected too, so a Markdown publication cannot make
an absent-audio outcome look like an MP3. The fixed retained
`.ocrllm-video-audio-resume.json` is also reserved, so explicit overwrite cannot
replace settled paid interval state with Markdown. Its
returned standard video result preserves the composition and has the verified
output path. It does not
recognize again, derive a legacy filename, create resume state, or publish a
fully failed outcome. The caller owns the complete filename: publication always
writes UTF-8 Markdown and `.md` is the recommended suffix, but suffixes are not
validated. This is distinct from the exact library-owned media paths above.
Automatic fallback and video worker routing remain unavailable. Resume exists
only through explicit `recognize_video_to_markdown(..., resume=True)`; the
low-level recognize/compose/publish calls remain non-resumable. Plain
`import ocrllm` does not import OpenCV, NumPy, imageio-ffmpeg, recognition
execution helpers, or provider SDKs. The primary single/batch recognition,
standalone long-MP3, and four video facade functions are bound during package
initialization so explicitly importing their same-named submodules cannot
replace the public callables with module objects. Their public annotation types
are available to ordinary `typing.get_type_hints()`, while batch preflight,
output ownership, recognition implementations, and optional dependencies remain
lazy.
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
`model_selection`, or `recognition` as the safe runner stage and preserves only
an allowlisted numeric HTTP status and short structured provider status when
the mapper supplies them. It never prints
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

## Bounded Google Combined-Video Live Smoke

Install `ocrllm[video,image,audio,google]` and run one authorized MP4 through
`tools/run_google_genai_video_smoke.py` with explicit current-catalog
`--image-model` and `--audio-model` values, a video path, a timeout, and the
required `--expected-frame-groups` value of `1` or `2`. Before catalog access,
the runner performs a provider-free retained-frame pass and rejects a controlled
fixture outside that exact expectation. This admits only fixtures preflighted
as at most two image groups; the formal library still supports ordinary input
under its own documented grouping limits. The runner uses separate image and audio `Config`
objects and prints only
catalog/models, branch status, retained/group/asset
counts, stable error codes, exact-or-null calls, and validated per-model token
usage when composition succeeds. It never prints recognition text, paths,
credentials, or raw provider responses and performs no retry or model switch.
Every JSON object is discriminated before its shared pass/fail status:
`report_type="video_outcome"` means the media branches settled, while
`report_type="runner_failure"` means catalog/model/orchestration did not produce
a settled outcome.
For settled branch failures, the runner may also print one fixed safe `reason`:
`empty`, `invalid_encoding`, `missing_text`, `invalid_no_speech_marker`, or
`refusal`. Arbitrary provider detail is never forwarded. A missing reason means
the library cannot safely classify the response more narrowly; it is not proof
of any one provider failure shape.
For a settled outcome to pass, its retained count must match the preflight and
its image group/call count must match the explicit expectation. This extra
local frame pass is a runner safety check, not part of `recognize_video()` and
not a new public planning API.

To exercise the explicit video-audio interval route, also pass the three
arguments `--audio-interval-minutes N`, `--expected-audio-calls M`, and
`--output-dir PATH` together. `N` and `M` are canonical positive integers, the
expected transport must be `google_files`, and `PATH` must be a caller-owned
test directory. The runner checks the exact audio call count against the
recognized duration and interval, and a passing outcome must have removed the
video audio sidecar without creating a nested standalone `result.md`. On a
failure the caller-owned directory remains available for bounded inspection of
the resumable state; the JSON output still exposes only allowlisted error facts
and never prints the directory or saved Markdown. Every JSON outcome and runner
failure also reports total monotonic `elapsed_seconds`, so timing survives the
disposable outer harness without exposing wall-clock metadata. This is a
live-test control, not a second public interval or resume API.
The #342 one-shot 301-second interval run preflighted five retained frames as
one image group. Its image call failed, and its first audio interval timed out
during Google Files upload before generation, so no interval settled and no
sidecar was expected. The runner returned an honest failed outcome after one
total generation call, with a closed audio client, no composition, no leak,
and no residue. This proves the bounded failure path, not interval success; it
was not replayed and does not justify retry or fallback behavior.
The #343 fresh attempt settled one interval before another branch failure, but
the then-current runner incorrectly rejected the required retained sidecar and
reduced the outcome to `CONFIG_INVALID`. The runner now requires sidecar removal
only after a complete interval outcome; partial and failed outcomes may retain
paid state and still emit their safe branch summaries. Nested standalone
publications remain invalid for every outcome. The obscured #343 provider error
was not reconstructed or replayed, so this correction is failure-evidence proof,
not a live interval success claim.
The #344 one-shot verification then returned an actual `video_outcome` for
model-scoped HTTP 429 quota failures in both the image group and first audio
interval. It preserved exact call/error facts and audio remote/client cleanup
without leaking content or leaving residue. No interval settled, so this proves
the corrected general provider-failure reporting path but does not live-prove
the narrower retained-sidecar case or the complete interval success path.
The #351 post-package-gate run reached the 37-model catalog through the active
proxy, then one image generation and the first audio Files upload each returned
`PROVIDER_TIMEOUT`. The image branch reported one attempted call; audio reported
zero generation calls, zero settled intervals, and a closed client. The runner
returned an honest failed `video_outcome`, performed no composition, and left no
task-owned residue. This is another bounded real failure, not interval success
or evidence for automatic retry/model switching. #354 later reran the same
controlled 301-second/two-interval shape once with the supported 600-second
per-operation setting. One five-frame image call and exactly two Google Files
audio calls all completed; composition returned six assets with 13,602 input /
872 output tokens, remote/client cleanup completed, no sidecar remained, and no
task-owned residue remained. The runner's total elapsed time was
790.609 seconds, which does not identify any individual stage duration or change
the product's default timeout. The bounded complete video-interval live gate is
therefore closed without retry, fallback, or model switching.
The #186 robustness run retained three equal-luminance color scenes and made one
image plus one audio call; both returned `PROVIDER_RESPONSE_INVALID`, so the
top-level outcome honestly remained failed and no token usage was invented.
That color-and-tone fixture proves dispatch/error handling, not transcription
quality.
The #206 separate-model run used one synthetic five-second speech-and-text MP4.
One `gemini-2.5-pro` image call returned `PROVIDER_UNAVAILABLE`; the independent
`gemini-2.5-flash` audio call succeeded, and composition retained a two-asset
partial result with only the audio model's validated 200/14 token usage. The
runner exited 1 because its full gate did not pass, but its discriminated JSON
remained a settled `video_outcome`, not a runner failure. No retry or model
switch was performed.
After #224 stabilized audio extraction on the shared video snapshot, #225 ran
the maintained gate exactly once with two independent configs both selecting
the proven `gemini-2.5-flash`. One retained frame formed one successful image
request, the extracted speech formed one successful audio request, and the
complete composition retained the JPEG and MP3 with aggregated 796/17 token
usage. The runner exited 0 in 9,721 ms with no retry, fallback, model switch,
secret/content/path/raw-response disclosure, or request-owned residue. Using
the same model in two configs does not collapse the two branch configurations
or claim support for a second audio provider.
After #238 corrected coarse frame seeking for a shorter video stream inside a
longer audio container, #241 ran that exact shape once through the same gate.
Provider-free preflight retained the exact final visual frame, then independent
image and audio configs each completed one `gemini-2.5-flash` request. The
complete two-asset composition reported 1,021 input / 41 output tokens; the
single runner exited cleanly without retry, model switching, secret/content/path
disclosure, or request-owned residue. This refresh does not change the API or
generalize provider routing.
The #207 real local regression continues that exact all-image-failed and
audio-success shape through `publish_video_result()`. The final file remains
partial, prints the stable frame error beside the successful audio section,
retains JPEG and MP3 assets, and preserves the audio-only usage and exact total
calls without inventing image text.

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
offline code and tests. #339 closed Stage M's bounded DashScope live exit; the
offline model/account quota distinction is not claimed broadly live-proven. A crash
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
