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


### 2026-08-18 (session 5): isolated QSettings tests leaked registry keys (D6)

**What broke.** `legacy_app/tests/qsettings_test_isolation.py` created a unique
organization `OCRLLMTests-<uuid>` per test and cleaned it up with
`QSettings.clear()` + `sync()`. 60 orphaned `HKCU\Software\OCRLLMTests-<uuid>`
keys had accumulated on the development machine.

**True root cause.** `QSettings.clear()` removes values, not the key itself. On
Windows the organization key survives with zero values, so every run leaves one
empty tree behind. The teardown was not "never executed" as previously recorded
in the defect register; it executed and simply did not do what it claimed.

**Fix.** New `legacy_app/tests/delete_test_qsettings_tree.py`:
- `delete_test_qsettings_tree(org)` recursively deletes the tree with `winreg`
  and refuses any organization name outside the `OCRLLMTests-` prefix, so it
  cannot be pointed at the real `HKCU\Software\OCRLLM` settings.
- `delete_orphaned_test_qsettings_trees()` purges leftovers; running the module
  directly deleted all 60 orphans (each verified to hold zero values first).
`qsettings_test_isolation.restore()` now calls the per-org deletion.

**WARNING FOR src/ocrllm.** Same class, different resource: a cleanup call that
looks like it releases a resource but only empties it. `src/ocrllm` has the
equivalent shape in `output/delete_image_resume_state.py` and in the temp/
snapshot directories created by `imaging/snapshot_image_group.py`. When porting
or extending those, assert the resource is *gone*, not merely empty, and make
the teardown assertion part of the test rather than trusting the API name.

### 2026-08-18: refusal contracts, Codex timeout, and partial-batch failure truth

**Task A — short apology refusals escaped the legacy oracle.** What broke:
`looks_like_refusal()` recognized only the original 11 Chinese phrases, so
short refusals beginning with an apology, including English `Sorry`, could be
reported as OCR content. Root cause: the marker set lagged observed provider
wording and matching was case-sensitive. Fix: added the requested Chinese and
English markers, case-folded matching, and retained the 200-visible-character
cap so an apology quoted inside a long transcription remains valid content.
Carry-forward judgement: yes, every provider validator in `src/ocrllm` needs
the same short-refusal coverage and long-transcription exemption when this
oracle is mirrored.

**Task B — the Codex vision timeout was too short for real OCR batches.** What
broke: the config default, runner fallback, and GUI control all selected 600
seconds, while the GUI could not represent values above 3600 seconds. Root
cause: three duplicated defaults drifted from the operating requirement. Fix:
raised both defaults to 1800 seconds and the GUI maximum to 7200 seconds;
`TimeoutExpired` still fails immediately and is not retried. Carry-forward
judgement: yes, a future Codex adapter should have one authoritative timeout
default and a UI/config range capable of representing it.

## 2026-08-19 — PDF parallel render dies with "broken data stream" (fixed)

What broke: Codex mode on a 581-page PDF aborted at page-render time with
`OSError: broken data stream when reading image file`, raised from the
decode-verify inside `imaging/pdf_renderer.py::_render_one_page`. The log
showed `Importing JpegImagePlugin` once per worker thread — all 8 threads hit
`Image.open()` while PIL's lazy, non-thread-safe codec registry was still
initializing, a known source of transient decode failures. The verify step
(added 2026-08-18 to catch truncated files) treated one transient failure as
fatal for the whole task, and `quality` was silently ignored (`pix.save` was
called without `jpg_quality`).

Fix: (1) `Image.init()` in the main thread before spawning render workers;
(2) on verify failure, re-encode that page via PIL from the pixmap samples
(`_pixmap_to_pil`, handles alpha/CMYK) instead of failing the task; (3) pass
`jpg_quality=quality` to `pix.save`; (4) render errors now carry the 1-based
page number. Verified: 8 renderer/atomic tests pass plus a live 6-page
parallel-render smoke.

Carry-forward judgement: yes. WARNING FOR src/ocrllm: when the PDF slice is
ported, (a) never let worker threads perform PIL's first `Image.open` —
initialize the registry up front; (b) a decode-verify guard must have a
fallback encoder or per-page retry, or it converts a transient glitch into a
whole-task failure on large documents; (c) don't accept a `quality` parameter
that the MuPDF save path ignores.

## 2026-08-19 — resume "vanished": data-root relocation orphaned all checkpoints (fixed)

What broke: after commit f1c9c11 moved the default output dir from the app
root to `~/OCRLLM/output`, `CheckpointManager` (rooted at
`output_dir/.checkpoints`) started looking in a brand-new empty directory.
The 40+ real checkpoints under `<repo>/output/.checkpoints` became invisible,
so the startup 继续任务 banner showed nothing — the user experienced this as
"resume features disappeared". No checkpoint was ever deleted; the app was
looking in the wrong place. Secondary issue: when a checkpoint is found but
rejected by `is_compatible` (prompt/batch/page-range mismatch), only a log
line was written — the GUI stayed silent.

Fix: `config.py::_existing_legacy_data_root()` — when OCRLLM_HOME is unset
and a legacy root still holds `output/.checkpoints`, keep using it; only
fresh installs fall through to `~/OCRLLM`. Priority: explicit PathConfig >
OCRLLM_HOME > existing legacy data root > `~/OCRLLM`. `pdf.py` now also
surfaces checkpoint-incompatibility to the progress reporter.

Also added `tests/test_pdf_render_fresh_process.py`: the PIL codec-registry
race (previous entry) is only reproducible in a fresh interpreter with cold
multi-threaded first decode; every in-process test was structurally unable to
hit it. The new test renders a 40-page PDF with 8 workers in a subprocess.

Carry-forward judgement: yes, twice over. WARNING FOR src/ocrllm:
(1) never change a default data directory without a migration/continuity
path — silent relocation orphans user state (checkpoints, outputs, resume);
(2) concurrency/init-order bugs need at least one fresh-subprocess
integration test; a warm pytest process masks lazy-init races permanently.

**Task C — Codex had no machine-readable refusal contract.** What broke: a
successful CLI exit containing refusal prose was indistinguishable from OCR
content, while phrase guessing is incomplete and language-dependent. Root
cause: the prompt did not tell Codex how to signal an impossible image task and
the runner did not parse such a signal. Fix: the prompt now requires the exact
`SORRY4OCRLLM, because {原因}` response, and the runner recognizes it only at
the start, retries within the existing bounded attempt loop, then raises with
the extracted reason; a sentinel appearing mid-transcription remains content.
Carry-forward judgement: this can re-emerge in any Codex-style provider port.
**WARNING FOR src/ocrllm**: a codex-style provider port needs the sentinel
contract, not phrase guessing.

**Task D — partial batch failures were still reported as success.** What
broke: PDF, board, and video workers returned or tracked `success=False` and
wrote failure placeholders, but their orchestrators only rejected all-failed
or low-content output. A mostly successful job therefore passed the ratio gate
despite a timeout. Root cause: the per-batch flags were counted and discarded
instead of becoming a terminal job outcome. Fix: each orchestrator now records
failed page ranges or batch numbers, finalizes the output first so paid partial
work and placeholders remain resumable, preserves the more-specific quality
gate diagnostic when it applies, and otherwise raises with the failed units
and output path. Carry-forward judgement: this is a direct risk for every
future batch-orchestration port. **WARNING FOR src/ocrllm**: batch
orchestration ports must never turn a timeout into a placeholder-as-success.

## 2026-08-19 — cancelling a false-failed task deleted paid output (fixed)

What broke: a task could finish writing a useful transcript or recognition
markdown and still be reported as failed because one batch, page, or provider
cleanup step raised afterward. The task then appeared in the resume list. Using
the list's delete/cancel action called `CheckpointManager.remove_with_artifacts`
and deleted the checkpoint's recorded output with `os.remove` or `shutil.rmtree`.
That deletion bypassed the Windows Recycle Bin, so the successful result was
not recoverable through normal desktop recovery.

True root cause: the cleanup method treated an incomplete checkpoint as proof
that its output was disposable. Checkpoint state and output validity are
different facts; a checkpoint can be incomplete while its output contains
valuable paid work or a complete result with a false terminal error.

Fix: `CheckpointManager.cancel()` now removes only the checkpoint and preserves
all generated output. `remove_with_artifacts()` is non-destructive by default;
output deletion requires the explicit `delete_outputs=True` keyword. The resume
dialog now labels the action as cancellation, explains that results are kept,
and calls `cancel()` directly. Regression tests cover PDF, audio, and video
outputs plus the dialog action.

Carry-forward judgement: yes. **WARNING FOR src/ocrllm**: checkpoint dismissal,
retry, and terminal error handling must never delete published recognition
artifacts implicitly. Any destructive cleanup must be a separate explicit
operation, and a partial/falsely failed result must remain durable and
inspectable.

## 2026-08-19 — 模型配置页面 (settings_dialog / model_picker) UI defect pass (fixed 1-5, 7; verified-not-fixed 6)

Seven user-reported UI problems in the model configuration page, fixed except
item 6 which was explicitly deferred by the user to a verify-and-document-only
scope this session.

1/2. Fetching models froze the whole dialog and, for DashScope, never actually
loaded fetched names into the combo (only a count popup). Root cause: `_refresh_bailian_models`,
`_refresh_google_models`, and `_on_codex_check_clicked` ran their network/subprocess
call directly on the GUI thread with only a `self.repaint()` before it — no event
pumping happened until the call returned. Fix: added `SettingsDialog._run_fetch_async`
(fire-and-forget, `ThreadPoolExecutor` + `QTimer` poll, callback runs on the GUI
thread) for scan/Codex-check, and `SettingsDialog._wait_for_future` (submits to
the same executor, then pumps `QApplication.processEvents()` while waiting) for
the two call sites that need a synchronous bool return (Apply-time validation
gates: `_validate_google_environment_if_needed`, `_refresh_bailian_models` return
value used at dialog-init). `_refresh_bailian_models` now also repopulates
`_vision_model_combo` from `model_catalog.list_vision_models()` after a
successful fetch instead of only showing a message box.

3. `QFont("Microsoft YaHei", ...)` was hardcoded in `gui/app.py`, `gui/model_picker.py`,
`gui/widgets.py`. Not bundled, not guaranteed present outside Windows. Replaced
family with `""` (unset) so Qt/the OS supplies whatever CJK-capable font is
already the app default, keeping only point size/weight.

4. `test_gui_app.py::test_api_settings_body_is_scrollable` asserted
`QCRMainWindow._api_scroll`, a main-window attribute that no longer exists
because API/model settings moved into `SettingsDialog` long ago. Replaced with
`test_api_settings_dialog_body_is_scrollable`, which opens `SettingsDialog`
directly and asserts it contains a resizable `QScrollArea`. Full legacy suite
(excluding the ffmpeg-only `test_social_e2e.py`): 220 passed, 1 skipped.

5. DashScope's own model selection (`主视觉模型` combo + picker button + 降级队列
+ `音频模型` row) lived in a separate "模型选择" group box far below the DashScope
API-key group, with Google/Codex/独立 Provider groups physically in between —
the "split into two parts" the user reported. Per user decision, generalized
the pattern used by Google/Codex (credentials + model selection inside one
group box): moved that whole block into `dash_group`, added a one-line label
noting the field is shared and gets overwritten when Codex or the independent
Provider is enabled (it always was one shared `_pending_vision_model`/combo;
this only fixes the visual placement, not the underlying sharing — that is
item 6).

6. **Verified true, NOT fixed (delayed by explicit user decision).** Image
(3 providers: DashScope/Codex/independent OpenAI-compatible) and audio (2:
DashScope/Google) recognition are each a single active-provider priority chain,
not independently selectable parallel providers. Confirmed in code:
`core/provider_selection.py` (`uses_codex_for_vision` > `uses_independent_vision_provider`
> `uses_google_for_vision`, mutually exclusive by construction) and
`config.models.vision_model` / `asr_model` are single fields — `settings_dialog.py`
literally overwrites `_pending_vision_model` with the Codex model string when
Codex is toggled on (`_on_codex_enabled_changed`), and the independent Provider's
"扫描模型" button also writes into that same combo. Real per-modality parallel
provider selection needs: (a) `AppConfig` schema change to per-provider model
fields instead of one shared field per modality, (b) `provider_selection.py`
redesigned from a priority chain to an explicit selector, (c) dispatch changes
in `llm_client.py`, `processors/video.py`, `processors/social/long_video.py`
wherever `cfg.codex_vision.enabled` / `cfg.vision_api.enabled` gate behavior.
This is a real backend redesign, not a UI fix — prior subagents' warning was
correct.

7. `ModelPickerDialog` ("选择模型..." next to DashScope's model row) already
read a merged builtin+cached-catalog list, but `_classify_bailian_vision_model`
silently returned `None` (dropped the model entirely) for any live-fetched
name that didn't match a hardcoded `vl`/`ocr`/`omni`/`qwen3.5`/`qwen3.6` pattern
written against a months-old account snapshot — so new real models never
appeared regardless of the "类型过滤" radio choice, which looked like a broken
filter but was actually models missing from the list. Fixed in
`core/model_catalog.py`: unmatched non-audio names now get a `general` fallback
kind instead of being dropped; audio/vision ASR exclusion (a real mechanism
difference, not a stale label) is unchanged. Also added a real "🔄 拉取最新模型"
button inside `ModelPickerDialog` itself (`on_fetch_live` callback, backed by
`model_catalog.refresh_bailian_models`, run off the GUI thread via its own
small `ThreadPoolExecutor` + `QTimer` poll) — previously the picker had no
fetch action of its own and only showed whatever was last cached by the
outer dialog's separate refresh button.

No stored QSettings/API-key state was touched by any of the above; no
in-flight OCR/recognition task code paths were changed.

**WARNING FOR src/ocrllm**: none of `src/ocrllm`'s provider/model-catalog
design has this per-modality single-active-provider coupling yet (it doesn't
have a settings GUI), but if one is ever added, design the model field as
per-provider from the start — retrofitting a shared field later (as legacy
did) is what created item 6's blocker.

