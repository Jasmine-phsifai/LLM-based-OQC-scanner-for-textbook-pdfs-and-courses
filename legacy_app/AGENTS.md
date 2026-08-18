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

### 2026-08-18 (session 3): video "five phase" model is the wrong abstraction

Status: **diagnosed and fixed in the same session.** The diagnosis below was
written before any code change; the "What changed" section at the end records
the fix.

**Where the design lives.** `processors/video.py::VideoProcessor.process`
(phase list `[1..5]`), `processors/video_pipeline.py` (the five
`VideoPhase` subclasses + `build_video_phase_chain`), and
`gui/tabs/video_tab.py::_build_ui` (five always-checked `QCheckBox`,
`self._phases[1..5]`). Checkpointing is
`core/checkpoint.py` with `total_items=5` and `completed_indices` holding
phase numbers.

**The structural error.** Video actually contains two independent products:
an *audio* pipeline (extract → transcribe) and a *frame* pipeline
(extract frames → preprocess → recognize). The code models them as one
linear chain of five ordinal steps. Ordinal numbering forces a total order
on two things that have no order between them, and it makes "phase 5" mean
both "the last step" and "the audio product", which is where every reported
inconsistency comes from. The only genuine cross-link is *hotwords*: phase 4
extracts hotwords from the board markdown and phase 5 feeds them to ASR
(`video.py::_phase5_asr`, `_extract_hotwords_from_md`). That is an optional
quality boost, not a structural dependency, but the linear chain encodes it
as one.

**Concrete failures traced to it:**

1. *Audio-only follow-up run is impossible.* Reported case A (ticking only
   box 5 after a 1–4 run) fails, and the reason is not the checkbox — it is
   `video.py::_prune_completed_outputs`, which runs on every successful
   completion where phase 4 was selected and **deletes** the extracted
   `{stem}.mp3`, `frame_info.json`, the `提取帧/` directory, the phase-3
   processed-frame directory and manifest, and the hotword table. After a
   1–4 run the audio file the user would need is already gone, so phase 5
   alone has nothing to transcribe (`AudioRecognizePhase.execute` hits the
   `音频文件不存在，跳过语音识别` branch and *returns True*, i.e. reports
   success while doing nothing — a second bug: a no-op is indistinguishable
   from a completed transcription in the result dict).

2. *Frame-only re-run silently destroys the transcript.* Reported case B.
   `FrameExtractPhase.execute` calls `_clear_invalidated_phase_artifacts`
   with `{3,4,5}`; `_artifact_invalidations_for_context` only spares
   phase 5 when 5 is *not* selected. So re-running the full tick set to
   redo bad board recognition deletes `{stem}_录音识别.md` and re-pays for
   ASR. Conversely, re-running to redo bad ASR requires phase 1 (audio
   extract), which requires nothing be pruned — but the pruning already
   happened. Whether the re-run overwrites or preserves the other product
   depends on which boxes are ticked, in a way no user can predict from the
   UI. The UI offers no "re-recognize frames, keep transcript" and no
   "re-transcribe, keep board" operation at all.

3. *Resume is phase-granular, so it is nearly worthless for the expensive
   phase.* `IncrementalMDWriter(md_path, total_slots=total_batches)` in
   `_phase4_llm` is constructed with the default `truncate=True` and no
   `seed_slots(...)` call, unlike the PDF path which does seed. A crash at
   batch 79/80 therefore discards all 79 paid recognitions and re-runs the
   whole phase. `BoardRecognizePhase.can_resume` only answers
   "does a complete-looking board markdown already exist", never "which
   batches are done".

4. *Resume is discarded on any parameter edit.* `Checkpoint.is_compatible`
   compares `expected_extra` exactly, and that dict includes `phases` and
   `prompt_template`. Changing the tick set or touching the prompt after a
   crash silently invalidates the checkpoint and restarts from zero. The
   GUI never passes `resume=True` on a normal run either — resume is
   reachable only through the startup "⏩ 继续任务" banner
   (`gui/app.py::_run_resume_checkpoint` →
   `VideoProcessor.resume_options_from_checkpoint`), and the checkpoint is
   deleted on success, so "resume" exists only for crashed runs and cannot
   express "reuse what's on disk for a deliberate partial re-run".

5. *Progress bar can never reach 100% on a partial tick set.* Not true —
   `_build_phase_weights` only adds weights for selected phases and
   `ProgressTracker` normalizes them — but the weights are static constants
   (`1/3/2/4/2`) unrelated to actual frame count, video length, or provider
   speed, so the bar's rate is meaningless. It also reports phases 1, 2 and
   5 as `phase_total=1`, i.e. a single 0%→100% jump for the two slowest
   real-time operations (ffmpeg extraction and ASR).

6. *Hotword collection is order-dependent and mostly random.* In
   `_phase4_llm` the completion loop does `hotwords = hw` (assignment, not
   accumulation) over out-of-order `as_completed` results, so the final
   hotword list is whichever batch happened to finish last and returned a
   non-empty list. Hotwords then flow into ASR quality.

7. *`skip_audio` duplicates the tick state.* `video_tab._run` computes
   `skip_audio = 5 not in phases` and passes both, then
   `_normalize_phases` and `AudioRecognizePhase.should_run` each re-derive
   the same condition. Two sources of truth for one user intent, and
   `_artifact_invalidations_for_context` keys off both.

**Intended direction (agreed shape, implementation pending):** replace the
five ordinal phases with two named pipelines that share the model list,
fallback logic, and resume machinery but own their own artifacts and their
own re-run switch — `audio` (extract → transcribe) and `frames`
(extract → preprocess → recognize) — with hotwords demoted to an optional
input that is read from disk if present and skipped if absent, never a
scheduling constraint. Stop pruning inputs that a later partial re-run
needs, or make pruning an explicit user choice. Make resume batch-granular
for the recognition step and independent per pipeline.

- **WARNING FOR src/ocrllm**: video support is not started in the new
  library. Do **not** port the five-ordinal-phase model. Model video as two
  independently runnable, independently resumable pipelines from the start;
  make the recognition step's resume unit the batch, not the phase; keep
  the hotword link a soft optional input; and never let a successful run
  delete an artifact that a partial re-run of the *other* pipeline would
  need. The same trap exists for any future multi-product source type
  (e.g. PDF text layer + page images).
- **WARNING FOR src/ocrllm**: a step that finds its input missing must not
  `return True`/report success (the `音频文件不存在，跳过语音识别` branch).
  Missing input is either a typed error or an explicit "skipped" state in
  the result object — never silent success.

**What changed.** New `processors/video_pipeline_selection.py` holds
`VideoPipelineSelection` (three booleans: `frames`, `audio`,
`audio_extract_only`) and the `AUDIO_STEPS = (1, 5)` /
`FRAME_STEPS = (2, 3, 4)` grouping. Step numbers 1–5 were deliberately kept as
stable identifiers so checkpoint files, CLI `--phases`, `registry.py`,
`SocialLongVideoProcessor`, `api/server.py` and the resume banner
(`checkpoint.py::_looks_actually_done` reads `extra["phases"]`) keep working
unchanged; `from_legacy_steps()` translates the old tick set. Concretely:

- `video_pipeline.py`: `_artifact_invalidations_for_context` replaced by
  `_downstream_steps_in_same_pipeline(context, step, inclusive)`. Invalidation
  can no longer cross the pipeline boundary in either direction. `inclusive`
  distinguishes "recovery failed, redo this step too" from "this step just
  recomputed, drop what follows it".
- `video.py::_prune_completed_outputs`: now deletes only free-to-regenerate
  intermediates (mp3, `frame_info.json`, `提取帧/`, phase-3 dir + manifest,
  merged board MD). Board MD, transcript MD and the hotword table are never
  deleted. Gated by a new `cleanup_intermediates` argument.
- `AudioRecognizePhase.execute`: re-extracts the mp3 from the video when it is
  missing (a free operation) and raises if that fails, instead of returning
  success without transcribing.
- `video.py::_load_phase4_partial_slots` + `_phase4_llm(restored_slots=...)`:
  batch-granular resume driven by the board markdown itself rather than a
  second checkpoint schema. A crash at batch 79/80 now re-runs one batch.
- `_phase4_llm` accumulates hotwords across batches instead of `hotwords = hw`.
- `_checkpoint_compat_extra`: pipeline selection no longer participates in
  checkpoint compatibility, so changing the tick set reuses on-disk artifacts
  instead of restarting from zero.
- `video_tab.py`: five ordinal checkboxes replaced by two pipeline checkboxes
  plus a 保留中间文件 opt-out; when the selected pipelines already have output,
  a 复用 / 重跑 / 取消 dialog runs before the worker starts. Path conventions
  stay in `VideoProcessor.existing_products`/`default_output_dir` so the GUI
  never re-derives artifact filenames.
- Progress phase names are prefixed by pipeline (`板书·智能抽帧`,
  `录音·语音识别`).

Legacy suite: 198 passed, 1 skipped (excluding `test_social_e2e.py`, which
needs ffmpeg on PATH, and the pre-existing `test_gui_app.py` settings-UI
failures below).

### 2026-08-18 (session 3, second finding): the previous session's atomic-write fix was itself broken

Found while running the suite for the refactor above. The 2026-08-18 follow-up
entry's atomic-write fix built its temp path as `f"{dest}.tmp{os.getpid()}"` —
i.e. the real extension stopped being the last suffix. Both PyMuPDF
(`pix.save`) and PIL (`img.save`) infer the output format from the extension,
so:

- `imaging/pdf_renderer.py` raised
  `ValueError: Image format tmp11788 not in ('png', ..., 'jpg', ...)` on every
  page render.
- `core/utils.py::atomic_save_image` (used by `resize_image_if_needed`, which
  the PDF, board and video paths all call) would fail the same way for every
  image large enough to need resizing.

`imaging/preprocess.py::imwrite_unicode` was unaffected only by luck — it
writes raw encoded bytes with `tofile`, so the extension is irrelevant there.
Fixed by adding `core/utils.py::atomic_temp_path()` (`{stem}.tmp{pid}{ext}`)
and routing all three call sites through it.

Also fixed in the same pass: `config.py::__post_init__` called `Path.home()`
unguarded, and `Path.home()` raises `RuntimeError("Could not determine home
directory.")` whenever HOME/USERPROFILE is absent — a cleared subprocess
environment, a service account, some CI shells. That made `AppConfig()`
unconstructible, i.e. the whole app dead, not just the default path wrong.
Now falls back to `tempfile.gettempdir()/OCRLLM`.

- **WARNING FOR src/ocrllm**: this is a fix that shipped without ever being
  executed. A "safety" change to a write path is still a change to the write
  path. When the atomic-image-write rule is carried into the new library, the
  temp name must keep the real extension last, and there must be a test that
  actually writes and re-reads a JPEG/PNG through the helper.
- **WARNING FOR src/ocrllm**: never let a process-wide config constructor call
  something that can raise on a hostile-but-legal environment (`Path.home()`,
  `os.getlogin()`, `socket.gethostname()`). Config construction must not be a
  failure point.

### 2026-08-18 (session 3): observed but NOT fixed

Recorded per the diary rule; no work done on these.

- `tests/test_gui_app.py` has four failures unrelated to video, all
  `AttributeError: 'QCRMainWindow' object has no attribute '_api_key_input'`
  (`test_api_settings_body_is_scrollable`,
  `test_external_vision_provider_changes_do_not_overwrite_model_input`,
  `test_external_vision_provider_keeps_explicit_model_when_provider_alias_changes`,
  `test_external_vision_provider_model_input_is_separate_from_provider`). The
  API-settings widget was renamed and the tests were not updated, so the
  external-vision-provider settings UI currently has **no** working test
  coverage.
- `tests/test_gui_app.py::test_run_resume_checkpoint_supports_audio_tasks`
  intermittently kills the interpreter with a Windows access violation
  (`0xC0000005`) when the file runs inside a larger pytest session. It passes
  when the file is run alone. Suspected Qt object lifetime / `deleteLater`
  ordering across tests, not a product bug — but it silently truncates suite
  results, which is how the two regressions above went unnoticed.
- `tests/test_social_e2e.py` fails at collection without ffmpeg on PATH, so a
  default `pytest tests` run reports zero tests. Collection should be skipped,
  not errored, when ffmpeg is absent.
- Progress weights for video are static constants (`1/3/2/4/2`) unrelated to
  frame count or video length, and steps 1, 2 and 5 report `phase_total=1`, so
  ffmpeg extraction and ASR are single 0%→100% jumps. Left as-is.
- `processors/social/short_video.py` has its own separate "6 phases" ordinal
  model. Not touched. It likely has the same abstraction problem and should be
  reviewed before anything is ported from it.

