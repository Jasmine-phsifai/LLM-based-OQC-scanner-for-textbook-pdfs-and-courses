# OCRLLM

OCRLLM is a Python recognition library under staged migration. New projects
import `ocrllm`; `legacy_app/` is the maintained compatibility application and
behavior reference, not the new dependency boundary.

## Current State

Current truth is maintained in
[`docs/ACTIVE_STATE_AND_RULES.md`](docs/ACTIVE_STATE_AND_RULES.md). Read it
before relying on any dated phase, decision, checkpoint, review, or incident
record. Those files preserve history and do not override current status.

As of 2026-08-25:

- Phase 0 contract honesty, the Phase 1 image gate, the Phase 2 development
  worker, and Phase 2A image-library completion are GO.
- Stage M is offline implementation-complete: lazy DashScope catalog checks,
  atomic file-backed image state, opt-in disposition-gated candidate recovery,
  complete spend disclosure, model-aware credential blocking, and slot-indexed
  intra-request checkpoints are shipped. Its paid live exit smoke remains open.
- The former standalone Stage 2 vision/audio scaffold was removed. Native
  Google inline short MP3 and Files-based single-request long MP3 paths are
  implemented and live-proven; both remain memory-only. Long-audio chunking,
  resume, and long-audio video routing remain unavailable.
- The first PDFium vision slice is implemented and live-proven. `recognize(one.pdf)`
  uses serial eight-page image groups, ordinary image resume sidecars, and
  stable range markers. Its bounded Google exit gate completed 16 pages in two
  calls with two complete checkpoints and no retained rendered pages; PDF
  repair will not consume legacy application's Markdown format; ordinary
  image-sidecar resume remains the library recovery path.
- Provider-free video inspection and retained-frame extraction are available.
  `inspect_video(one.mp4)` writes nothing; `extract_video_frames()` performs a
  bounded five-second coarse scan that always compares the actual final frame,
  count-driven negative-feedback selection, and complete-directory JPEG
  publication. `recognize_video_frames()` feeds
  the exact ordered retained-frame tuple through the existing image path in
  groups of at most eight and returns honest batch outcomes. It is memory-only;
  `extract_video_audio()` now atomically publishes a fully decoded mono MP3
  through the lazy video extra. Frame and audio recognition use separate
  `Config` objects, so their providers can differ. `recognize_video()` now
  settles both branches into a typed `VideoRecognitionOutcome`; an outcome
  cannot claim that the audio stream is absent while retaining an MP3 artifact,
  an explicitly partial child result keeps the video partial, and frame-group
  results must describe images.
  `compose_video_result()` can explicitly turn a returned complete or partial
  outcome into a standard memory-only video `RecognitionResult` with separate
  frame and audio sections. Its current-run provider-call total is an integer
  only when every settled branch supplies exact evidence; otherwise it is
  `None`, never a guessed zero. `publish_video_result()` can instead atomically
  publish the same complete or partial composition to an explicit caller-owned
  path, with opt-in overwrite. Long-audio video routing, video resume, and
  worker routing are not implemented yet.
- Native Google image, inline short-MP3, and single-request Google Files long-MP3
  adapters are implemented. Legacy
  compatibility work and carry-forward warnings remain recorded in
  `legacy_app/AGENTS.md`.
- Built wheels include the standard `py.typed` marker and static-only lazy-facade
  exports. An isolated installed-wheel Pyright probe resolves documented public
  types and rejects an invalid `Config` argument without making runtime imports
  eager.

The authoritative defect register is in
[`docs/ACTIVE_STATE_AND_RULES.md`](docs/ACTIVE_STATE_AND_RULES.md). D1-D7,
F1-F4, and G1-G10 are closed in offline code and tests; only the paid Stage M
exit gate and live provider-account/model-quota re-verification remain open.

## Active Library

The active package is `src/ocrllm/`. Its current image/PDF contract:

- accepts valid PNG, JPG, and JPEG sources;
- decodes and validates sources before provider dispatch;
- gives providers request-scoped snapshots, not mutable caller paths;
- rejects empty, control-only, and refusal-shaped provider output;
- exposes typed, redacted errors and immutable disposition evidence;
- returns `source_type="image"` and `profile="board"`;
- keeps output in memory unless `output_dir` is supplied;
- publishes Markdown and resume state atomically;
- keeps Pillow, OpenAI, HTTPX, OpenCV, NumPy, and other heavy dependencies lazy
  at base import;
- accepts exactly one PDF through the direct facade, snapshots at most 100 MiB,
  and lazily loads `pypdfium2` only when PDF recognition is requested;
- renders at most eight ordered pages per image request and removes rendered
  PNGs after each settled group;
- publishes `<stem>_board.md` and, when output is configured, keeps ordinary
  child image outputs/checkpoints in the same-named `<stem>_board/` directory;
- rejects PDF in `recognize_batch()` in this first slice and exposes no page,
  password, partial-result, or text-mode settings.
- exposes `inspect_video()` separately for one local MP4 when the `video` extra
  is installed; this inspection API performs no recognition or output writes.
- exposes `extract_video_frames()` for an explicit output parent; it creates a
  same-stem directory containing ordered `frames/frame-<index>.jpg` files and
  rejects an existing target instead of overwriting or resuming it. Selection
  compares a five-second coarse grid plus the exact final frame; a scene that
  appears entirely between those samples can be missed.
- exposes memory-only `recognize_video_frames()` for a nonempty exact tuple of
  library `RetainedVideoFrame` values; it reuses image preflight and recognition
  in ordered groups of at most eight and creates no video-specific provider.
- exposes `extract_video_audio()` for one explicit `.mp3` target under an
  existing plain directory; it stages, fully decodes, and atomically publishes
  the first audio track without imposing the short recognizer's duration limit.
- keeps exact frame indices and timestamps on every settled video-frame group,
  including typed failures and undispatched cancellation, so callers do not
  have to reconstruct group membership after recognition. A public video
  outcome is accepted only when those ordered group identities exactly cover
  its retained frames; invalid outcomes cannot report `complete` first.
- distinguishes a valid MP4 with no audio stream (`VIDEO_NO_AUDIO_STREAM`) from
  a declared audio stream that is corrupt or cannot be decoded (`VIDEO_INVALID`).
- exposes `recognize_video()` as one Python-library orchestration call with
  explicit image and audio configs; it retains frames and extracted MP3,
  preserves each branch's result or typed error, and computes honest
  `complete`, `partial`, or `failed` status without publishing final Markdown.
  Its outcome requires the exact lexical `output_root/frames/*` and optional
  `output_root/audio.mp3` layout; it does not resolve path or symlink aliases.
- exposes `compose_video_result()` as a provider-free explicit second step for
  a returned complete or partial video outcome. It keeps ordered frame and
  audio sections separate, preserves stable failure codes, reports retained
  media as assets, and accumulates provider-reported tokens by model. It does
  not infer audio/frame alignment or accept a fully failed outcome.
- exposes `publish_video_result()` as the separate final-output step. It accepts
  the same settled outcome plus an explicit output path, atomically publishes
  Markdown without overwriting by default, and returns the standard video
  result with a verified `output_path`. The Markdown target cannot replace a
  retained frame or audio asset. It adds no recognition, resume, or legacy-format
  behavior.

The local OCR mode is available through the `ocr` extra. It is text extraction,
not a formula/table/layout-equivalent replacement for the vision workflow. The
JSONL worker is a development capability with a frozen v1alpha1 contract;
packaged Electron compatibility is not claimed.

### Install from this checkout

```powershell
pip install ".[image,dashscope,pdf-vision,video]"
```

### Built-in DashScope example

```python
from ocrllm import Config, DashScopeSettings, VisionModelSettings, recognize


result = recognize(
    "board.jpg",
    config=Config(
        provider=DashScopeSettings.for_region("cn-beijing"),
        vision_model=VisionModelSettings(
            name="qwen3.7-plus-2026-05-26",
        ),
    ),
)
print(result.markdown)
```

The API key comes from `DashScopeSettings(api_key=...)` or the configured
credential environment. Never commit or print a key. The pinned model and the
exact Beijing v17 workflow are the live quality baseline. Other served models
may be selectable through catalog discovery but are reported as unproven until
measured.

### Injected-provider example

```python
from ocrllm import Config, recognize


class Provider:
    def recognize_images(self, image_paths, *, prompt, config):
        return "# Recognized board\n"


result = recognize("board.jpg", config=Config(provider=Provider()))
print(result.markdown)
```

The same facade accepts one PDF when `ocrllm[pdf-vision]` is installed. It uses
the configured vision provider and board profile; no separate PDF provider
protocol exists.

An injected provider is an integration seam, not live quality evidence. The
provider must return one Markdown `str` synchronously. Resume requires its
nonempty `resume_identity` attribute. Structured adapter responses are internal
and are not a public injected-provider return contract.

## Boundaries

Read these files in order:

```text
docs/ACTIVE_STATE_AND_RULES.md
START_HERE.md
MIGRATION_STATUS.md
docs/plan_phase1_maturation_and_phase2_audio.md
docs/ocrllm_library_go_no_go.md
src/ocrllm/README_ACTIVE_LIBRARY.md
src/ocrllm/AGENTS.md
legacy_app/README_LEGACY.md
legacy_app/AGENTS.md
```

Do not:

- import `legacy_app.OCRLLM` from a new project;
- copy legacy processors wholesale into `src/ocrllm`;
- add GUI, FastAPI, social downloading, browser automation, or heavy media
  imports to the base library;
- use PyMuPDF or `fitz` for active PDF work; the approved path is PDFium
  through `pypdfium2`;
- treat `output/`, `temp/`, `ocrllm_social_e2e/`, caches, or screenshots as
  source-of-truth evidence;
- start HarmonyOS/ArkTS, Rust/PyO3, long-audio chunking/resume, video recognition
  beyond the ordered P1-e slice, or PDF repair outside the approved phase gate.

## History Trace

Detailed history remains in the dated Markdown records. The current migration
milestones are kept here only as a pointer:

| Commit | Recorded change |
|---|---|
| `0278b66` | Clean Phase 1 v17 image evidence and package gate passed. |
| `2db456a` | Phase 2 development worker gate passed. |
| `8025406` | D1-D7 defect repair closed. |
| `2f39428` | F1-F4 audit findings and legacy false-success/timeout protections closed. |
| `a19776d` | Stage M model discovery and candidate-queue work landed. |
| `4c5293d` | First-fetch DashScope catalog outage changed to fail closed. |
| `9ff2e34` | Legacy parallel PDF render initialization and decode fallback fixed. |
| `7672c13` | Legacy resume continuity restored after data-root relocation. |
| `78a2fa6` | Legacy repair-range expansion and partial-failure reporting fixed. |
| `42c0f75` | Legacy settings/model fetch moved to the current picker boundary. |

The full incident trace and carry-forward warnings are in
[`legacy_app/AGENTS.md`](legacy_app/AGENTS.md). Historical phase conclusions
are immutable; current status is never inferred from them.

## Historical References

Important decisions and incident histories remain available without being
mistaken for current status:

- migration rationale and target architecture:
  [`docs/library_migration_decision.md`](docs/library_migration_decision.md) and
  [`docs/ocrllm_module_target_design.md`](docs/ocrllm_module_target_design.md)
- provider, error, credential-pool, local-OCR, and resume decisions:
  [`MIGRATION_STATUS.md`](MIGRATION_STATUS.md#historical-provider-and-resume-decisions)
- Phase 1 and Phase 2 evidence chronology:
  [`docs/phase1_implementation_record.md`](docs/phase1_implementation_record.md)
  and [`docs/phase2_live_worker_result_2026-07-12.md`](docs/phase2_live_worker_result_2026-07-12.md)
- legacy social-long and FileTrans/Codex workflows:
  [`MIGRATION_STATUS.md`](MIGRATION_STATUS.md#historical-legacy-workflows)

Superseded counts, NO-GO conclusions from earlier attempts, the old fixed model
allowlist, and the original Electron Phase 2 framing are retained as obsolete
history in the dated records and Git history. They are not current claims.

## Verification

Offline active-library checks:

```powershell
& 'D:\Anaconda\envs\OCRLLM\python.exe' -m pytest -q -p no:cacheprovider
& 'D:\Anaconda\envs\OCRLLM\python.exe' -m compileall -q src tests
& 'D:\Anaconda\envs\OCRLLM\python.exe' -c "import sys,time; sys.path.insert(0, 'src'); t=time.perf_counter(); import ocrllm; print(round(time.perf_counter()-t, 4), len(sys.modules), [m for m in ('PIL','openai','httpx','onnxruntime') if m in sys.modules])"
```

The clean Git-archive wheel, isolated-install, outside-repository import, and
heavy-module checks are defined in
[`docs/ocrllm_library_go_no_go.md`](docs/ocrllm_library_go_no_go.md). Do not
run a paid live gate without an explicit maintainer budget and confirmed
region/endpoint.
