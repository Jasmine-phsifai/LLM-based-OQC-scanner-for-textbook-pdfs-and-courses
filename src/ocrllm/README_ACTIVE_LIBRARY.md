# Active OCRLLM Python Library

`src/ocrllm/` is the importable package for new integrations. The legacy desktop
application remains under `legacy_app/` as a behavior reference; new code must
import `ocrllm` only.

Read the repository-root `AGENTS.md` first. It is the top authority. Current
migration order and proof are recorded in
`../../docs/plan_provider_entity_batch_refactor.md` and
`../../docs/ACTIVE_STATE_AND_RULES.md`.

## Install

The base package has no runtime dependency. Install only the media/provider
extras used by the caller:

```powershell
pip install -e .
pip install -e ".[image,google]"
pip install -e ".[audio,google]"
pip install -e ".[pdf-vision,google]"
pip install -e ".[video,image,audio]"
pip install -e ".[image,dashscope]"
```

Available extras:

- `image`: Pillow image validation and snapshots;
- `audio`: MP3 validation plus FFmpeg-backed interval materialization;
- `video`: MP4 inspection and frame/audio extraction;
- `pdf-vision`: PDFium rendering for vision recognition;
- `google`: native Google GenAI adapters;
- `dashscope`: DashScope OpenAI-compatible image adapter;
- `ocr`: local RapidOCR text extraction.

Plain `import ocrllm` remains lightweight: it does not import OpenCV, NumPy,
Pillow, miniaudio, FFmpeg helpers, provider SDKs, or network clients.

## Public provider models

`ProviderModel` represents one exact vendor/model plus validated task
capabilities, planning defaults, controlled adapter settings, and inert finite
retry-rule data. The package ships only a small set of bounded live-proven
presets:

```python
from ocrllm import (
    DASHSCOPE_QWEN3_5_OCR_CN_BEIJING,
    GOOGLE_GEMINI_2_5_FLASH,
    ProviderModel,
)
```

Use `list_google_genai_models()` for the current Google catalog. Catalog rows do
not prove OCR quality, audio support, recommended batch size, or retry policy;
unverified rows are not emitted as guessed presets.

## Images

The visible merged-image flow separates planning from provider work:

```python
from ocrllm import (
    GOOGLE_GEMINI_2_5_FLASH,
    batchify_images,
    recognize_images_to_markdown,
    repair_images_to_markdown,
    resume_images_to_markdown,
)

batches = batchify_images(
    tuple(image_paths),
    provider=GOOGLE_GEMINI_2_5_FLASH,
)
result = recognize_images_to_markdown(
    batches,
    provider=GOOGLE_GEMINI_2_5_FLASH,
    image_task="detail_ocr",
)
```

`batchify_images()` accepts an exact nonempty source tuple and an explicit
positive batch size, a provider model, or both. Explicit size wins; omitted size
uses the smallest positive recommendation across all validated scalar, flat, or
nested candidates. It validates all image groups, preserves order, writes
nothing, and makes no provider call.

Merged recognition accepts the exact batch tuple and one model, one nonempty
exact built-in flat model list, or one nonempty exact list of nonempty exact
model lists. A flat lane visits candidates serially at most once per unresolved
slot and stops at first success. Nested lane `j` owns absolute slots
`j, j + lane_count, ...`; lanes advance independently with one active slot each,
without barriers, stealing, or cross-lane rescue. A nested plan is limited to 32
lanes. Successful fallback returns ordinary complete/partial output with one
warning and bounded `provider_failures`. A wholly failed slot retains only its
terminal candidate.

All outcomes are checkpointed in one sidecar. Complete work writes one ordered
Markdown and removes state. Mixed settlement writes failed-slot markers and
retains state. Zero settlement retains state, creates no new Markdown, and
raises `AllCandidatesExhausted`. Resume requires the exact source/group/task
identity, reuses settled slots, and calls providers only for unresolved work.
Each resume invocation starts every supplied lane from its first candidate; lane
topology and cursors are not persisted.

Experimental `repair_images_to_markdown()` is only for a current OCRLLM partial
Markdown after its ordinary sidecar has been lost. It requires the explicit
current batches, provider topology, and image task; an omitted output uses the
same deterministic rule as recognition. A still-present sidecar is rejected in
favor of ordinary resume. Repair parses only exact library failed-slot comments,
keeps absolute nested-lane assignment, runs serially, writes every paid success
back before advancing, and never creates repair state or accepts legacy
Markdown.

## Audio

Audio preparation is explicit and currently accepts MP3:

```python
from ocrllm import (
    GOOGLE_GEMINI_2_5_FLASH,
    recognize_audio_to_markdown,
    repair_audio_to_markdown,
    resume_audio_to_markdown,
    split_audio,
)

slices = split_audio(
    audio_path,
    provider=GOOGLE_GEMINI_2_5_FLASH,
)
# Or use interval_minutes=-1 for one whole-source range.

result = recognize_audio_to_markdown(
    slices,
    provider=GOOGLE_GEMINI_2_5_FLASH,
)
```

`split_audio()` returns an exact tuple of immutable `AudioSlice` identities. An
exact `-1` selects the whole source; a positive exact integer selects minutes;
an explicit value wins over provider defaults. Planning fully decodes duration,
uses the existing 30-second boundary context for intervals, creates no physical
clips/state/output, and makes no provider call.

Merged audio recognition accepts one model, one nonempty exact built-in flat
list, or one nonempty exact list of nonempty exact model lists. It writes all
ordered slots into one Markdown, checkpoints each speech/no-speech/failure
outcome, and continues after ordinary provider failure. Nested lane `j` owns
absolute slots `j, j + lane_count, ...`; lanes advance independently with one
active request-owned interval clip each and never steal or rescue another lane's
work. Whole audio through 300 seconds uses native inline transport; longer whole
audio and explicit intervals use Google Files. Provider file/client cleanup
failure is surfaced without claiming false success.

Experimental `repair_audio_to_markdown()` applies only to a current OCRLLM
multi-slot interval partial Markdown after its ordinary sidecar is lost. It
accepts the original MP3, current provider topology, optional existing output,
and timeout. Exact adjacent headings/comments supply failed logical seconds;
the source's decoded duration and the fixed 30-second context reconstruct the
temporary Files request. Speech and typed no-speech replace their markers before
local clip/source cleanup. It restores no interval length, mode, provider, or
historical usage and creates no repair state. A whole-audio failure publishes no
partial Markdown, so it remains non-repairable after state loss.

Resume binds exact source bytes, ranges, and prompt mode. Settled slots are not
replayed; failed/unresolved slots begin the supplied lane from candidate zero.
Provider cursor and retry history are not persisted. A provider can be changed
explicitly between invocations.

The scalar/flat image and audio paths, including fallback and ordinary resume,
have bounded real Google evidence. Fixed two-lane image pooling is live-proven.
Nested audio has complete SDK/FFmpeg concurrency, cleanup, and resume proof; its
first real gate produced honest network/rate-limit failures and retained state.
One later ordinary resume settled those exact three slots with three generations,
published matching Markdown, and removed state. Successful nested audio is now
live-proven across invocations. Same-model retry, other audio formats, and
experimental repair are not implemented.

`resume_video()` is a stateless package-root routing name for backend callers.
It requires exact `media_type="image"` plus already-batched image tuples, or
exact `media_type="audio"` plus an `AudioSlice` tuple. It forwards the provider
tree and optional output to exactly one ordinary resume owner and returns the
same result/error. It does not accept a video path, infer media, find state,
coordinate branches, compose Markdown, or clean extraction outputs.

## PDF

The direct PDF vision facade snapshots one local PDF, renders ordered pages with
PDFium, and reuses the original Config/injected-provider image recognition in
groups of at most eight. Rendered pages are removed after each group. Ordinary
child image sidecars provide resume. This facade does not yet call
`batchify_images()` or the provider-model merged-image recognition/resume APIs,
and it does not parse legacy application repair Markdown.

Install `ocrllm[pdf-vision]` plus the selected image-provider extra. PDF text
extraction, passwords, arbitrary page ranges, and batch-PDF input are not part
of the current direct facade.

## Video inspection and extraction

The library intentionally exposes visible provider-free steps instead of a
combined video recognition lifecycle:

```python
from ocrllm import (
    batchify_images,
    extract_video_audio,
    extract_video_frames,
    inspect_video,
    split_audio,
)

info = inspect_video(video_path)
frames = extract_video_frames(video_path, output_dir=output_parent)
frame_batches = batchify_images(
    tuple(frame.path for frame in frames),
    batch_size=8,
)
audio_path = extract_video_audio(video_path, output_path=output_parent / "audio.mp3")
audio_slices = split_audio(audio_path, interval_minutes=-1)
```

`inspect_video()` writes nothing and reports container duration, stream facts,
dimensions, frame count, and frame rate. It rejects changing caller-path input
rather than mixing facts from two files.

`extract_video_frames()` performs bounded presentation-time sampling, includes
the actual final frame, applies accumulated negative-feedback selection, and
publishes complete ordered JPEGs under one caller-owned same-stem directory. It
does not crop, detect board corners, deskew, or apply perspective correction.

`extract_video_audio()` snapshots the source once, distinguishes no audio stream
from corrupt/undecodable audio, stages and fully decodes mono MP3, atomically
publishes one caller-owned output, and removes request-owned staging.

Image and audio recognition then use their independent merged APIs, providers,
Markdown outputs, and sidecars. The former combined recognition/journal/result
surface has been removed; there is no compatibility wrapper and no replacement
combined lifecycle.

## Direct `recognize()` and `recognize_batch()`

The original direct facade remains available for its shipped image, PDF, short
audio, long-audio, and local OCR contracts. `recognize_batch()` requires an exact
top-level tuple, validates every member and output target before dispatch, keeps
ordering/concurrency bounds, and returns one `BatchItemOutcome` per item.

New image/audio batch integrations should prefer the visible planning plus
merged-recognition APIs above because their slot identity and ordinary resume
contracts are explicit.

## Output and error rules

- Provider credentials, raw response bodies, signed URLs, and user media never
  enter durable state or safe diagnostics.
- Provider generation calls and nullable input/output token totals accumulate by
  exact `(vendor, model)`; unknown counts remain `None`.
- Markdown and state replacement are individually atomic. The package does not
  claim a cross-file transaction or rollback log.
- Windows output paths beyond the supported legacy limit are rejected with a
  typed zero-call error; source-name sanitization is separate from path-length
  support.
- Output and extraction artifacts requested by public functions are caller-owned.
  Request snapshots, rejected frame candidates, and active interval clips are
  library-owned and removed within their call.

## Verification

Real scenarios live under `tools/` and are run only when their subsystem
changes. Code-level tests cover public contracts and branchy logic; they do not
mirror the source-file tree.

Run focused tests from the maintained environment:

```powershell
& 'D:\Anaconda\envs\OCRLLM\python.exe' -m pytest tests/test_lightweight_import.py -q
& 'D:\Anaconda\envs\OCRLLM\python.exe' -m pytest tests/test_inspect_video.py tests/test_extract_video_frames.py tests/test_extract_video_audio.py -q
```

The installed-profile gate is `tools/run_stage_m_offline_gate.ps1`. It builds an
isolated wheel, proves base import and optional extras, and exercises the visible
video inspect/extract/batchify/split flow without provider calls.
