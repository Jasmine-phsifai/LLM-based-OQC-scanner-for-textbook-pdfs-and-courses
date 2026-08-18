# Legacy App Boundary

This directory contains the old OCRLLM application and compatibility surface.

## Allowed Work Here

- Fixing old GUI behavior.
- Fixing `launch_gui.bat` and legacy launch flow.
- Maintaining old Codex, Google, DashScope, and OpenAI-compatible mode routing.
- Reading old processors as behavior references.
- Running or updating legacy tests when maintaining the old app.

## Not Allowed As A New Direction

- Do not make new downstream projects import from this directory.
- Do not treat `legacy_app.OCRLLM` as the future public API.
- Do not move large files wholesale into `src/ocrllm`.
- Do not solve new library packaging by adding more behavior to the old app.

## Porting Rule

When behavior needs to become part of the new library, port a tested vertical
slice into `src/ocrllm/` and keep this directory as reference or compatibility
code.

## Working Diary Rule

Any time a bug is fixed (or only diagnosed) in `legacy_app/`, add an entry
below stating: what broke, the true root cause, the fix, and whether the same
class of defect can re-emerge in `src/ocrllm/` when that vertical slice is
ported. If it can re-emerge, write an explicit `WARNING FOR src/ocrllm` line
so it is not silently re-introduced during porting.

### 2026-08-18: path handling and silent-refusal "fake success"

**1. Windows path failures were misdiagnosed by users as "path too long".**
Root cause was almost always different:
- `AppConfig.__post_init__` (`config.py`) defaulted `output_dir`/`temp_dir` to
  `os.path.dirname(__file__)/output|temp` — inside the installed package
  directory. This breaks on any machine where the install location isn't
  writable and makes output invisible/non-portable. Fixed: default now comes
  from `OCRLLM_HOME` env var or `Path.home() / "OCRLLM"`, built with
  `pathlib`.
- `pdf_renderer.pdf_to_images` used the raw PDF filename stem (e.g.
  `"数理统计 "` with a trailing space, taken verbatim from the source
  filename) as a directory component. Windows `CreateDirectory` silently
  drops trailing dots/spaces from path components, which makes
  `os.makedirs` raise `WinError 3: The system cannot find the path
  specified` even though the path "looks" fine in Python. This is not a
  "too long" problem, it is an un-sanitized path component. Fixed: added
  `sanitize_path_component()` in `core/utils.py` and applied it to the PDF
  render dir. `video.py` already had `_safe_output_stem`/`_debug_dir_name`
  sanitizers but only applied them when the caller passed an explicit
  `output_stem`; the default (source-filename-derived) stem bypassed
  sanitization — also fixed.
- No file in the codebase used the `\\?\` extended-length prefix, so any
  path that does legitimately exceed ~260 chars (deep `temp_dir` nesting +
  long Chinese titles) fails outright. Added `long_path()` helper and made
  `ensure_dir` retry with it on `OSError`. This is a narrower, real fix,
  layered under the sanitize fix, not a replacement for it.
- **WARNING FOR src/ocrllm**: when PDF phase (Phase 3) is implemented, do not
  default `output_dir`/`temp_dir` inside `src/ocrllm/`; do not build any
  filesystem path segment directly from a user-supplied filename stem
  without stripping trailing dots/spaces and reserved characters first.

**2. Batch-level "success" hides embedded per-page/per-frame failures.**
Not a bug in the failure-tracking itself (each processor does track
`success=False` correctly and embeds a `<!-- ... 识别失败 ... -->` HTML
comment). The real gap: `output_quality.failed_placeholder_quality_reason`
only raises when failures dominate the file (few chars per unit); a PDF
with e.g. 2/116 failed batches still reports as a completed/successful file
in the GUI batch summary, with the failure only visible if the user opens
the markdown and finds the HTML comment. This is a UX/observability gap,
not a correctness gap — flagging here because Phase 3 (PDF) in the new
library should decide, up front, whether partial-batch failure is
surfaced as a first-class field in the result object (not just embedded in
markdown text).
- **WARNING FOR src/ocrllm**: `RecognitionResult`/PDF batch results should
  expose a structured `failed_units` (page/frame indices) field, not rely on
  callers grepping markdown for a failure marker string.

**3. Real "fake success": non-empty model refusal text accepted as valid
recognition.** This is the actual cause of the "video recognition all
failed but no error shown" report. `google_provider._validate_text` only
rejects genuinely empty responses; a 200 OK response containing text like
"无法识别：当前未能获取到该图片内容" is non-empty, so it passes. In
`processors/video.py::_phase4_batch_one`, the only content check was
`_has_expected_batch_frame_markers` — a *structural* check (are the
`<!-- meta:frame ... -->` markers present), which model refusal text often
satisfies too, so `success=True` was set on outright refusals. Same
structural-only gap existed in `pdf.py::_do_batch_llm` (page-header count
check) and `board.py` (no content check at all). Fixed: added
`output_quality.looks_like_refusal()` (short text containing phrases like
"无法识别"/"无法读取"/"请重新上传") and wired it into all three processors'
per-batch and per-page/per-frame fallback paths, plus into
`failed_placeholder_quality_reason`'s marker list and `board.py`/`video.py`
final quality gates (video/board previously had **no** file-level quality
gate at all — only `pdf.py` called
`failed_placeholder_quality_reason`).
- **WARNING FOR src/ocrllm**: any provider adapter (DashScope, Google,
  Codex, local) must validate response *content*, not just structural
  shape/non-emptiness, before treating a batch/frame as recognized. This
  needs a shared validator in the new library's provider-adapter layer
  (analogous decision already exists for audio in
  `docs/provider_error_disposition_decision_2026-07-12.md` — read that
  before choosing where the image/video equivalent lives), applied
  uniformly across every media type instead of ad hoc per-processor.

Live-API reproduction (2026-08-18, follow-up session): ran against the real
Codex CLI (`codex-cli 0.144.5`, model `gpt-5.5`) through the actual
`CodexVisionRunner.recognize()` production path, no mocks:
- Cross-drive paths (images on `D:`, throwaway `-C` cwd on `C:` temp),
  fullwidth-colon + Chinese directory names, batches of 1/2/4/5 images,
  4-way concurrency, and 3 repeated runs of the same 5-image batch all
  recognized correctly every time — **no evidence that Codex CLI's
  `--sandbox read-only` / `-C <throwaway tempdir>` / `-i <absolute path>`
  mechanism itself drops or fails to attach a healthy image file.** The
  attachment mechanism is not the bug.
- Confirmed the real trigger directly: feeding Codex CLI a **zero-byte**
  or **truncated** JPEG produces exit code 0 (no exception, no retry
  trigger) and a plain-text reply of "无法读取" / "图片无法读取" — this
  exactly reproduces the user-reported "无法识别：当前未能获取到该图片内容"
  pattern. **The bug is corrupt image files reaching the recognizer, not
  a code-level attachment/path defect in the Codex call itself.**
- Traced why a corrupt file can exist at all: none of the three image
  write paths were atomic or verified — `imaging/pdf_renderer.py`
  (`pix.save(img_path)`), `core/utils.py::resize_image_if_needed`
  (`img.save(dest, ...)`), and `imaging/preprocess.py::imwrite_unicode`
  (`encoded.tofile(path)`) all wrote directly to the final path. A
  cancelled task, killed process, or disk-full mid-write during any of
  these (all run inside `ThreadPoolExecutor` workers, and this app has a
  first-class `CancelledError`/cancel-button flow) leaves a truncated file
  at the exact path the recognizer later reads, with the previous run's
  render/extract stage reporting success because the write call itself
  didn't raise. Fixed: added `core/utils.py::atomic_save_image()` (save to
  a sibling temp path, verify decodable with `PIL.Image.open().load()`,
  then `os.replace`) and applied the same temp+`os.replace` pattern
  directly in `pdf_renderer.py` and `imwrite_unicode`. This closes the
  window between "file write started" and "file is a complete, decodable
  image" — a half-written file now never becomes visible under its real
  name, and a genuinely failed write raises instead of being silently
  read back later as a "the model can't see it" refusal.
- **This is the root cause combined with the fake-success detection gap
  above**: `looks_like_refusal()` (already wired into pdf/board/video)
  catches it *after* it happens and turns it into a visible failure
  instead of silent success; the atomic-write fix here prevents the
  corrupt file from being produced in the first place. Both layers matter:
  atomic writes reduce how often this occurs, refusal detection catches
  the residual cases (corrupt source scan, provider-side transient
  decode failure, unusual page content that genuinely triggers a model
  refusal for non-corruption reasons).
- **WARNING FOR src/ocrllm**: when porting PDF/video/board recognition,
  every image-producing write (render, frame-extract, resize) must be
  atomic with a decode-verify step before the file is considered to exist
  at its final path — do not port `pix.save(path)` / `img.save(path)` /
  `arr.tofile(path)` call sites verbatim.

