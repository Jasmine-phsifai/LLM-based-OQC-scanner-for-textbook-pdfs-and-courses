# OCRLLM

OCRLLM is an importable Python recognition library for images, PDFs, MP3 audio,
and provider-free video inspection/extraction. New projects import `ocrllm`;
`legacy_app/` is the maintained desktop compatibility application and behavior
reference, not the new dependency boundary.

Read these files before changing the package:

1. [`AGENTS.md`](AGENTS.md) — top repository authority;
2. [`docs/plan_provider_entity_batch_refactor.md`](docs/plan_provider_entity_batch_refactor.md)
   — current provider/media migration order;
3. [`docs/ACTIVE_STATE_AND_RULES.md`](docs/ACTIVE_STATE_AND_RULES.md) — work log
   and defect evidence;
4. [`src/ocrllm/README_ACTIVE_LIBRARY.md`](src/ocrllm/README_ACTIVE_LIBRARY.md)
   — current public API guide;
5. [`MIGRATION_STATUS.md`](MIGRATION_STATUS.md) — navigation and history index.

## Current product boundary

- `src/ocrllm/` is the active package.
- `tests/` verifies public behavior.
- `quality_lab/` contains on-demand quality evidence, not default tests.
- `legacy_app/` remains a separate UI application and parent behavior reference.
- Social-media downloading/recognition is deferred.
- `contracts/` and `worker/` remain frozen until a real consumer justifies a
  same-slice protocol change.

The current media boundaries are:

```text
images -> batchify_images -> recognize/resume one merged image Markdown
PDF    -> current recognize(Config) renders fail-fast groups of up to 8 pages
MP3    -> split_audio -> recognize/resume one merged audio Markdown
video  -> inspect/extract full frames and audio -> use the image/audio flows
```

The provider-model PDF path is not yet merged-image-backed. The current product
choice is whether to expose caller-owned page extraction before the existing
merged-image APIs, or add a separate one-call provider-model PDF lifecycle.
Earlier wording that described the future merged route as already shipped was
incorrect and was fixed by iteration #687.

The obsolete combined video recognition, journal, outcome, composition, and
publication surface has been removed after its merged image/audio replacements
and both ordinary resumes passed bounded real gates. There is no compatibility
wrapper and no replacement combined lifecycle.

## Install

The base package has no runtime dependencies:

```powershell
pip install -e .
```

Install only the required extras:

```powershell
pip install -e ".[image,google]"
pip install -e ".[audio,google]"
pip install -e ".[pdf-vision,google]"
pip install -e ".[video,image,audio]"
pip install -e ".[image,dashscope]"
pip install -e ".[ocr]"
```

Plain `import ocrllm` remains lightweight and does not load media backends,
provider SDKs, or network clients.

## Merged images

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

Planning writes nothing and makes no provider call. Recognition owns ordered
slots, one Markdown, atomic state, scalar/flat fallback or fixed nested lanes,
per-model usage, and ordinary resume. Nested lanes own fixed round-robin slots,
advance independently with one active slot each, and never rescue another lane.
Settled slots are not replayed.

Use ordinary `resume_images_to_markdown()` while the sidecar exists. If that
state was lost but a current OCRLLM partial Markdown remains,
`repair_images_to_markdown()` can trust the caller's explicit current batches,
read only strict failed-slot markers, and replace each newly settled marker
atomically. It creates no replacement state and does not accept legacy formats.

## Merged audio

```python
from ocrllm import (
    GOOGLE_GEMINI_2_5_FLASH,
    recognize_audio_to_markdown,
    repair_audio_to_markdown,
    resume_audio_to_markdown,
    split_audio,
)

slices = split_audio(audio_path, provider=GOOGLE_GEMINI_2_5_FLASH)
result = recognize_audio_to_markdown(
    slices,
    provider=GOOGLE_GEMINI_2_5_FLASH,
)
```

An explicit `interval_minutes=-1` selects the whole MP3; positive exact integers
select minute windows. Planning returns immutable range identities without
creating clips. Recognition materializes at most one active interval, writes
ordered slots into one Markdown, supports scalar/flat fallback or fixed nested
lanes, and resumes only failed or unresolved work. A nested plan assigns absolute
slots round-robin and allows one active request-owned clip per lane; lanes do not
rescue or steal another lane's work. Short whole audio uses native inline input;
long whole and interval work use the provider Files lifecycle.

If an interval partial Markdown survives after its ordinary sidecar is lost,
`repair_audio_to_markdown()` accepts the explicit original MP3 and derives only
failed logical ranges from strict OCRLLM headings. It reconstructs the fixed
30-second context, writes every speech/no-speech success atomically, and saves no
split parameters or repair state. Whole-audio failure has no partial Markdown
and is not repairable after state loss.

Nested audio is live-proven across separate invocations: a fresh two-lane call
retained three failed slots after network/rate-limit errors, and one later
ordinary resume settled those exact slots in three generations, published one
ordered Markdown, and removed state. This is explicit resume, not hidden retry.

## Stateless media resume routing

Backend callers may use `resume_video()` only as a discriminator-based alias for
one already-extracted media plan:

```python
result = resume_video(
    image_batches,
    media_type="image",
    providers=provider_plan,
    output_path=image_markdown,
)
```

Use `media_type="audio"` with an exact `AudioSlice` tuple for the other branch.
The router does not accept a video path, split media, discover state, coordinate
two outputs, compose a result, or own cleanup.

## Provider-free video

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
audio_path = extract_video_audio(
    video_path,
    output_path=output_parent / "audio.mp3",
)
audio_slices = split_audio(audio_path, interval_minutes=-1)
```

Frame extraction retains complete uncropped JPEGs selected through bounded
negative feedback and final-frame inclusion. It does not find board corners,
crop, deskew, or apply perspective correction. Audio extraction atomically
publishes a fully decoded mono MP3 and distinguishes no audio stream from corrupt
audio.

The caller owns public extraction outputs and chooses independent image/audio
providers, recognition calls, Markdown targets, and resume calls.

## Verification

Use the maintained environment and run only tests affected by a change:

```powershell
& 'D:\Anaconda\envs\OCRLLM\python.exe' -m pytest tests/test_lightweight_import.py -q
& 'D:\Anaconda\envs\OCRLLM\python.exe' -m pytest tests/test_inspect_video.py tests/test_extract_video_frames.py tests/test_extract_video_audio.py -q
```

Real media/provider scenarios are scripts under `tools/` plus a diary record.
They are re-run when their subsystem changes, not on every edit. The installed
profile gate is `tools/run_stage_m_offline_gate.ps1`; it builds an isolated wheel
and exercises base, media, provider, and visible video extraction/planning
profiles.
