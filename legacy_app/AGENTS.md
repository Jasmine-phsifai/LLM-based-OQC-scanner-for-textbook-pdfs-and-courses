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

### 2026-08-20: Codex model discovery and Fast mode were missing from settings

**What broke.** The Codex section exposed only a small static model list and
had no way to discover the models available to the installed Codex CLI. It
also had no Fast mode control, so every OCRLLM `codex exec` call ignored the
user's desired priority service tier because the runner deliberately ignores
the user's global Codex configuration.

**True root cause.** The GUI, `CodexVisionConfig`, and
`CodexVisionRunner._build_command` had no shared field for the service tier;
the existing inspection path already called `codex debug models` but kept its
parsed list private and never exposed it to the model combo.

**Fix.** Added persisted `fast_mode` state and an environment override,
passed `-c service_tier="priority"` only when enabled, rejected Fast mode for
models whose directory metadata lacks the priority tier, and added an async
Codex model fetch button that loads image-capable model slugs from
`codex debug models`.

**Carry-forward judgement.** Yes, the same configuration/UI drift can
re-emerge when a Codex-style provider is ported to `src/ocrllm`.

**WARNING FOR src/ocrllm**: provider capability discovery and request options
must share one typed configuration contract; a UI-only speed switch is not a
feature unless the provider command or request payload receives it and the
selected model is checked for support.

### 2026-08-20: Codex CLI could not read Unicode Windows image paths

**What broke.** A 68-video Codex run completed extraction and preprocessing,
then every Phase 4 batch was rejected as unable to read its attached images.
The runner retried each batch three times, so the batch spent minutes per
video without a chance of producing recognition output.

**True root cause.** The selected and processed JPEGs were present, non-empty,
and decoded successfully with Pillow. The exact same JPEG failed through
`codex exec -i` when its original path contained Chinese directory/file names,
but succeeded after copying the bytes to an ASCII-only temporary filename.
The Codex CLI returned exit code 0 with the refusal sentinel, so subprocess
success and model metadata both incorrectly looked healthy.

**Fix.** `CodexVisionRunner` now copies every request's image attachments into
its per-request temporary directory using ASCII filenames before building the
Codex command. It also rejects directories and empty staged files before
launching the subprocess. The original images remain untouched.

**Verification.** A live ASCII-path smoke returned `IMAGE_OK`; the focused
regression test proves a Unicode source path is not passed to Codex and that
the staged bytes are identical. The active video process was stopped after
video 037 Phase 4 so it would not continue spending retries on the known
failure.

**Carry-forward judgement.** Yes, this can re-emerge when a media provider is
ported into `src/ocrllm` if it receives user filesystem paths directly.

**WARNING FOR src/ocrllm**: provider adapters must normalize or snapshot
filesystem inputs into a provider-safe path/byte contract before dispatch;
existence checks alone do not prove that a subprocess can consume a Windows
Unicode path.


## 2026-08-20 — Codex "无法访问附加图片" mass refusals: service-side attachment loss (mitigated)

Symptom: 2026-08-20 12:21–12:37, every Codex vision call (1–8 images) was
refused via the SORRY4OCRLLM path with "无法访问/无法读取附加图片"; 10 calls at
11:59–12:03 had succeeded. All Modern Robotics batch videos failed.

Diagnosis (live, same day): reproduced the EXACT production path —
CodexVisionRunner.recognize with the same failing frames
(D:\univ\...\034_*\processed_frames\*.jpg), same registry config
(gpt-5.6-luna, effort=low, fast_mode/priority, batch 8), and 5 parallel
calls × 8 frames — everything succeeded. Staging, -i attachment, sandbox,
cwd, PATH (base vs OCRLLM env), env vars all ruled out. Conclusion: the
2026-08-18 attachment repair IS valid; the remaining failure is a transient
OpenAI service-side window where codex exec exits 0 but the model never
receives the -i attachments. The old retry (3 tries, 4–8 s apart) cannot
outlive a 16+ minute window, so whole batches aborted.

Fix in core/codex_vision.py: classify image-access refusals
(_is_image_access_refusal, CN+EN markers) and retry them on a dedicated long
schedule (15/45/90/180/300 s) that does NOT consume the 3 regular attempts;
exhaustion raises a message stating the loss is service-side and the task is
resumable. Non-access refusals keep the old short path. 3 new tests in
tests/test_codex_vision.py; suite 232 passed / 1 skipped.

WARNING FOR src/ocrllm: any future Codex-CLI provider must treat "model says
it cannot see the attachment" as transient infrastructure failure with long
backoff — not as a content refusal and not as caller error. CLI exit code 0
does not mean the attachments were delivered.

## 2026-08-20 - CLIProxyAPI direct vision integration

What broke: the legacy app's Codex mode always launched the full local
`codex exec` harness, even when the task only needed a direct multimodal model
request. The existing independent OpenAI-compatible vision path could already
send base64 images, but its model queue only advanced for DashScope's
`FreeTierOnly` error and its chat helper did not recover when a gateway rejected
the streaming image request.

True root cause: CLIProxyAPI v7.2.137 exposes the ChatGPT/Codex subscription at
a local OpenAI-compatible endpoint, but its Codex image bridge can return
429/5xx for a streamed image request. The pinned proxy source maps ordinary
`image_url` parts to Codex `input_image` parts; therefore the OCRLLM-side
compatibility gaps were status-error recovery and payload ordering, not image
base64 encoding. Live testing also showed the current proxy session could serve
text while intermittently returning 500/502 for all image requests, including
the native Codex Responses alias. That residual failure is upstream/proxy-side.

Fix: added opt-in `VisionAPIConfig.advance_queue_on_retriable_errors`, its
environment and QSettings/UI wiring, and a vision-only fallback that advances
the configured model queue on 429/500/502/503/504. Independent vision chat
requests now retry non-stream when the streaming request itself returns one of
those status codes. Chat image payloads put text before image parts, matching
the Codex translator's tested input shape. The independent provider can now be
configured with `http://127.0.0.1:8318/v1` while Codex CLI mode remains disabled.

Verification: focused provider/settings tests passed 21; the broader edited
legacy slice passed 47; compileall and git diff checks passed. A separate
CLIProxyAPI v7.2.137 instance is running on localhost port 8318 with an
isolated auth directory and successful Codex OAuth. Its authenticated
`/v1/models` endpoint returns 10 models, including gpt-5.5 and the gpt-5.6
family. Text-only Chat Completions succeeds. Image requests reached the proxy
but ended in its current 500/502 upstream failure window, so no successful
end-to-end image result is claimed from this session.

Carry-forward judgement: yes. **WARNING FOR src/ocrllm**: an OpenAI-compatible
provider adapter must distinguish stream transport failure from model refusal,
offer a non-stream fallback for gateways that cannot stream multimodal Codex
responses, and make status-code-to-candidate switching an explicit policy.
Do not copy the legacy shared-provider settings field into the new library.

## 2026-08-22 — 补录 6b2d9eb 的媒体失败项修复（功能已加入，但存在开放缺陷）

**补录范围。** 提交 `6b2d9eb` 同时包含三组变化。CLIProxyAPI vision fallback 已在该提交的
日记条目中记录；Codex model discovery / Fast mode 后来另有条目。真正漏记的是 audio、board、
video 的失败项修复及 video 长路径/中间文件保留变化。本条只恢复这段历史，不把未经测试的功能
追认为成熟实现。

**当时要解决的问题。** 三条 legacy 管线会把失败分段、失败批次或失败帧留在 Markdown 中，
但用户只能整项重跑或手工改文件。该提交增加三个 GUI 修复入口和对应 processor API：从既有
Markdown 找失败标记，只重付失败单元，成功后替换相应标记，部分失败则保留未修复项。video
还会在板书失败时保留帧/预处理产物，并把部分 Phase 4/5 输出路径交给 `long_path()`。

**本次代码与测试复核。** 提交新增/修改的测试覆盖 Codex settings、独立 vision provider 的
stream→non-stream fallback、429/5xx 候选切换、payload 顺序与 Windows 临时图片关闭；没有测试
引用 `find_failed_segments`、`find_failed_batches`、`repair`、`repair_board`、三个 `_run_repair`
入口或新增 long-path 行为。原日记记录的 live proxy 图片请求全部停在 500/502，不能据此声明
端到端图片成功。2026-08-22 从 `legacy_app` 目录重跑现存相关测试为 **26 passed / 3.10s**；
这只证明已存在的 provider/settings/writer 测试仍绿，不证明 media repair 正确。

**已观察、尚未修复。** 本次逐行复核确认以下开放缺陷：

1. `VideoProcessor.repair_board()` 把 `processed_frame_manifest.json` 当 list 迭代，但
   `_save_phase3_manifest()` 写的是 `{"items": [...]}`；正常 manifest 会让修复在 `item.get`
   处抛出未捕获的 `AttributeError`。
2. video 修复会静默跳过已丢失的帧文件，且未把它们加入 `still_failed`；若另有帧修复成功，
   方法可能在 Markdown 仍有失败标记时返回成功。失败批次还按**当前** batch size 重新展开，
   配置漂移后可能选错帧。
3. video 清理只因板书失败保留中间文件；若只有音频分段失败，仍删除提取出的音频，之后 GUI
   提供的音频修复会因源文件不存在而失败。
4. audio 修复按当前配置重新切段，只以分段序号关联旧 Markdown，没有持久化原始时间边界、
   源文件/请求指纹或切分参数；配置或输入漂移后可能把文字写到错误区间。
5. board 修复仅用 basename 映射原图。重名文件会覆盖，含逗号文件名会被 marker parser
   拆开；部分图片能解析时仍可能替换整批 placeholder。
6. audio、board、video 都用 `Path.write_text()` 原地覆盖唯一的付费 Markdown。进程终止、磁盘
   错误或部分写入可破坏原有成果；本提交没有 crash/atomicity 回归。
7. 独立 vision 的普通 proxy 500/502 被转成 `FreeTierExhaustedError` 以复用候选切换，旧 UI
   因而可能把普通上游故障误报为“免费额度耗尽”。该语义问题也未在本提交解决。

**Carry-forward judgement.** 是，而且不应直接移植当前实现。

**WARNING FOR src/ocrllm**: audio/video/board 的 resume/repair 应扩展现有 typed、versioned
sidecar 与 slot/batch checkpoint，记录稳定单元 ID、源快照、切分参数、prompt/provider/model
身份和每次付费尝试，并以原子替换发布 state 与 Markdown。不得把本地化 Markdown regex 当作
恢复状态源，也不得按当前配置重建旧单元。未来 Codex/OpenAI-compatible adapter 可以借鉴
text-first payload 和 stream fallback，但候选切换必须沿用显式 disposition，不得复用
quota-specific exception 表示普通 5xx。Windows 深目录还需覆盖临时后缀后的最终路径测试。

## 2026-08-22 — video repair 产物边界崩溃、假成功与音频误删（已修复）

**现象与根因。** 对 `6b2d9eb` 的补录审计发现三个相互关联的已建功能缺陷：

1. `_save_phase3_manifest()` 写入 `{"items": [...]}`，但 `repair_board()` 直接迭代顶层 JSON；
   正常修复会在字符串 `items` 上调用 `.get()` 并崩溃。
2. manifest 明确指向已丢失的 processed frame 时，该帧被静默排除。只要同批另一帧修复成功，
   Markdown 虽仍含失败 marker，方法却可能返回成功。
3. `_prune_completed_outputs()` 只因板书失败保留中间件。只有录音分段失败时，它仍删除
   `{stem}.mp3`，使 GUI 随后提供的音频修复必然缺源文件。

**修复。** `repair_board()` 现在按 writer 的 dict schema 读取并校验 `items`，跳过畸形条目且
对损坏 JSON 留 warning；没有 manifest 映射时仍允许既有 source-frame fallback，但 manifest
明确指向丢失文件时会把稳定 frame ID 加入 unresolved 集。可用帧照常重试并写回，任何不可用
帧仍保留显式失败 marker，最终抛出带 ID 的 partial-failure，而不是假成功。目标 ID 用 set 去掉
了原来循环内反复构造列表的查重。cleanup 复用 `AudioProcessor.find_failed_segments()`，仅在录音
Markdown 仍有失败分段时保留提取音频；干净 transcript 仍按原策略清掉可重建 mp3，没有笼统
保留全部中间文件。

**失败优先证据与验证。** 新增 `tests/test_video_repair.py`。修前三个回归为 **3 failed**：分别
精确落在 manifest `AttributeError`、缺帧假成功和 mp3 被删除；修后 video/audio/cleanup 相关集
**73 passed / 36.37s**。除真实 ffmpeg e2e 文件外的 legacy 全量为
**235 passed, 1 skipped / 51.00s**，skip 是显式 live Google model discovery；
`compileall -q OCRLLM tests` 通过。没有网络、provider 或付费调用。

**仍开放。** 本轮没有把 regex-in-Markdown repair 追认为成熟设计。failed batch 仍按当前
batch size 重新展开，audio 仍按当前切分配置重建旧分段；三条 repair 仍用非原子 `write_text()`。
进一步复核还确认：audio/video 在循环中已有成功付费结果后若取消，会在发布前直接抛出而丢掉
本轮成功；board 的宽泛 `except Exception` 会把 `CancelledError` 吞成普通批次失败。这些问题
必须另立失败测试与原子发布/稳定身份任务，不能由本轮绿灯掩盖。

**Carry-forward judgement.** 是。**WARNING FOR src/ocrllm**: 未来 audio/video vertical slice
必须把恢复所需 source snapshot、原始单元边界与 request identity 放进 versioned sidecar；缺失
artifact 必须成为显式 outcome。cleanup 只能删除已证明可重建且不再被失败恢复引用的文件；取消
必须先原子保存已付费成功槽位再传播。不要移植 localized Markdown marker 作为状态源。

## 2026-08-22 — media repair 原子发布与取消语义（已修复）

**现象与根因。** audio、board、video repair 都先把成功结果留在内存，循环结束才直接
`Path.write_text()` 覆盖唯一 Markdown。第二个 provider 调用若取消，第一个已经付费得到的成功
会随异常丢失；写入/替换失败也可能截断旧成果。board 的 `except Exception` 还会吞掉
`CancelledError` 和 provider setup error，把取消或环境缺失误报成普通批次失败。audio 同样会把
provider setup error 降格为普通失败。

**修复与结构选择。** 新增单一职责 `core/write_text_atomically.py`：在目标同目录独占创建短名
临时文件，以 UTF-8 写入、flush、`fsync` 后只用 `os.replace()` 发布；编码、fsync 或 replace
失败均清理临时文件、保留旧输出并传播原异常。三个 processor 保留各自不同的 marker 变换，
每个单元识别成功后先确认 marker 恰好替换一次，再原子发布，然后才记录结果并进入下一次可取消
操作。没有引入共享 regex/finalizer，也没有把 legacy marker 变成新库 API。board 显式传播取消
与 setup error，audio 补齐 setup error 传播，video 保留既有传播契约。

**失败优先证据与验证。** 修前五条直接回归为 **5 failed, 3 passed / 2.09s**：audio/video
取消丢成功、board 吞取消，以及 audio/board setup error 被误分类。修后 writer + 三条 repair
直接集为 **12 passed / 5.78s**；repair/resume/failure-propagation focused 集为
**43 passed / 22.41s**；除真实 ffmpeg e2e 外的 legacy 全量为
**244 passed, 1 skipped / 65.93s**，唯一 skip 是显式 live Google model discovery；四个修改模块
`py_compile` 通过。没有网络、provider 或付费调用。

**已观察、仍开放。** `pdf.py`、`CheckpointManager.save()`、`IncrementalMDWriter.flush()` 仍有
各自旧的直接写或确定性临时名/吞写错策略；本轮没有把不同状态契约强行并入 repair writer。
同进程并发 repair 仍是最后替换者胜出，原子文件替换不等于逻辑锁。更关键的是 audio segment、
board batch/basename、video failed batch 仍按当前配置和本地化 Markdown 重建身份；下一原子任务
应先定义持久化 identity，而不是继续增长 regex。

**Carry-forward judgement.** 是。**WARNING FOR src/ocrllm**: 新库恢复链必须在 typed、versioned
sidecar 中原子保存每个已付费 slot，取消前先提交成功；文件发布失败必须显式失败。原子 replace
只解决破坏性覆盖，不能替代稳定 source/request/unit identity 或并发协调。不要移植本轮的
localized Markdown marker 变换。

## 2026-08-22 — audio repair 配置漂移可修错时间段（已修复）

**现象与根因。** `AudioProcessor.repair()` 只从 Markdown 取得“分段 N”，随后按当前
`asr_short_chunk_seconds` 重新 `_split_audio()` 并取 `chunks[N-1]`。原输出若是一整个两分钟单元，
后来配置改成一分钟，“分段 1”会静默变成开头一分钟；源文件同路径换字节也不会阻止 provider
调用。Markdown 已有显示时间，但没有原始 actual window、强源指纹或版本化机器身份。

**修复与兼容政策。** 新增 `processors/audio_repair_manifest.py`。每次 short-ASR 输出都在 Markdown
旁原子保存 v1 sidecar：原始 source 和实际 ASR input 的 size/SHA-256、input duration、splitter/
fallback 参数、model/prompt/hotwords 审计哈希，以及 actual/logical 毫秒窗口与 stable unit ID。
repair 在任何 provider 调用前严格校验 schema/version、源字节、连续窗口、unit ID 和 Markdown
meta 映射，然后只按保存的窗口直接复用完整输入或执行 `ffmpeg -ss/-t`。current chunk/context
配置不再参与。没有 sidecar 的旧版输出明确拒绝，不做可能修错内容的 best-effort fallback。
`AudioRepairIdentityError` 不继承普通识别 `RuntimeError`，所以现有 audio/video GUI generic
汇总会显示具体 identity 错误，不再把它吞成“全部分段修复失败”。

**失败优先证据与验证。** 修前配置漂移、source drift、missing identity 为
**3 failed, 2 passed / 3.64s**。修后 direct identity/writer/extraction 集
**11 passed / 1.22s**；audio/video/resume/failure/GUI focused 集
**112 passed / 34.12s**；除真实 ffmpeg e2e 外的 legacy 全量
**253 passed, 1 skipped / 44.40s**，唯一 skip 是显式 live Google discovery；相关模块
`py_compile` 与 `git diff --check` 通过。没有网络、provider 或付费调用。

**已观察、尚未修复。** `_short_asr()` 的生产并行循环仍把所有结果留在 `ordered`，直到全部
future 完成才写 Markdown/manifest；任一 future 抛 `CancelledError` 会越过最终发布，丢掉其他
已经付费成功的分段。repair 的逐单元原子发布没有覆盖生产识别。board 仍以 basename 和可被逗号
拆坏的 marker 恢复批次，video failed-batch 仍按 current batch size 展开。并发 repair 仍没有
revision/CAS；当前 GUI 单任务降低了发生面，但不等于库级保证。

**Carry-forward judgement.** 是。**WARNING FOR src/ocrllm**: 音频 vertical slice 必须在 provider
前生成强 source/input fingerprint 和稳定毫秒 unit ID，并在每次付费成功后把 slot 原子写入
versioned sidecar；取消必须先发布已完成 slot。ordinal 与 Markdown 时间只用于展示，不能作为
恢复身份；修改 prompt/model 可以形成新 attempt，但不得改变 unit identity。

## 2026-08-22 — production short-ASR 取消丢失已付费结果（已修复）

**现象与根因。** `_short_asr()` 原先一次提交全部分段，把 future 结果只保存在内存 `ordered`
列表，直到所有任务结束才首次写 Markdown 与 repair manifest。任一 future 或 progress reporter
抛 `CancelledError` 会越过最终写入，丢掉已经成功的付费结果；provider setup failure 还会被
worker 降格成普通分段失败。即使用户取消，已全量提交的队列也可能继续扩大调用成本。

**修复。** provider dispatch 前先发布版本化 repair manifest 与全未完成 Markdown skeleton。
生产循环改为最多 worker 数的 rolling window，由 coordinator 用 `wait(FIRST_COMPLETED)` 消费
乱序完成，并在每个成功或普通失败落入固定 slot 后原子发布完整文档。取消/setup failure 会停止
新提交、取消尚未运行的 future、排空已运行的有界调用并保存其中成功，最后传播 terminal error；
两者同时出现时取消优先。没有修改通用 `BaseProcessor` iterator，也没有让 worker 线程写文件。

**失败优先证据与验证。** 修前三条核心回归为 **3 failed / 4.15s**：取消无输出、乱序完成无
中间快照、首次 dispatch 前无 checkpoint。最终五条 checkpoint 测试与 audio repair 集为
**16 passed / 2.34s**；除真实 ffmpeg e2e 外 legacy 全量为
**258 passed, 1 skipped / 62.02s**，唯一 skip 是显式 live Google discovery；相关模块
`py_compile` 与 `git diff --check` 通过。没有网络、provider 或付费调用。

**仍开放。** board batch 仍靠可被逗号拆坏的本地化 marker 与 basename 恢复身份；video
failed-batch 仍按 current batch size 解释历史失败。并发运行同一输出仍没有 revision/CAS，当前
GUI 单任务只缩小发生面，不构成库级保证。

**Carry-forward judgement.** 是。**WARNING FOR src/ocrllm**: 音频批处理必须在首次 dispatch 前
建立 typed/versioned slots；提交采用有界 rolling window；取消停止新工作但排空已运行调用，并在
传播前原子提交每个已付费成功。不要使用“全量 submit 后等待”或只在整批结束时保存的实现。

## 2026-08-23 — standalone board repair 按文件名误选图片（已修复）

**现象与根因。** `find_failed_batches()` 把本地化注释括号内文本按逗号切分，合法文件名
`chapter, part.png` 会变成两个不存在的名字；`repair()` 再用 `{basename: path}` 建表，不同目录
同 basename 时后者静默覆盖前者。同路径图片换字节也没有校验。结果可能是明确失败，也可能把
另一张图片付费识别后写进原批次，属于静默数据污染。

**修复与兼容政策。** 新增 `processors/board_repair_manifest.py`。生产首次 provider dispatch 前
原子写 v1 sidecar，保存每张有序原图 size/SHA-256、stable item ID、精确 batch membership/unit
ID，以及 batch size、prompt hash、skip-preprocess 审计值。Markdown 每批写机器可读
`meta:board-batch index/unit/status`；repair 严格验证 schema/version、哈希、完整 batch 覆盖、unit
重算、Markdown 映射和 supplied source 多重集，再按 exact-byte bucket 解析当前路径。rename 可用，
逗号/括号/重复 basename 不参与身份；旧输出无 sidecar、损坏/未知版本、图片或 Markdown 漂移都在
零 provider 调用时拒绝，不提供 unsafe fallback。每个成功 retry 仍通过 atomic writer 发布。

不可变边界是原始 source bytes + batch membership。repair 允许改变 prompt/model/preprocessing，
因此没有把某次 crop/resize provider input 冻结进 unit；这些值属于新 attempt，不是源身份。

**失败优先证据与验证。** 修前六条 identity 回归为 **6 failed / 12.34s**。最终
identity/repair/failure focused 集 **22 passed / 27.71s**；排除真实 ffmpeg e2e 与 import-time live
Bilibili diagnostic 的 offline legacy 广集 **266 passed, 1 skipped / 50.74s**，唯一 skip 是显式
live Google discovery；相关模块 `py_compile` 与 `git diff --check` 通过。没有 provider 或付费调用。

**已观察、尚未修复。** production `BoardProcessor.process()` 仍将所有结果保留到循环末尾，且
`except Exception` 会吞 provider 抛出的 `CancelledError` 和 setup failure。下一次取消检查可越过
最终 Markdown 发布，丢掉前面已付费成功；setup 缺失也会被降格为普通批次失败。video repair 的
failed-batch 仍按 current batch size 解释历史 index。并发同一输出仍无 revision/CAS。

**Carry-forward judgement.** 是。**WARNING FOR src/ocrllm**: 图像批处理恢复必须持久化强 source
fingerprint、原始有序 unit membership 与机器可读 slot 状态；不要按 basename、逗号分隔展示文本或
current batch size 重建。repair attempt 可改变 prompt/model/preprocessing，但不得改变 source unit；
生产取消必须先原子保存已付费成功再传播。

## 2026-08-23 — pytest collection 隐式访问 Bilibili 网络（仅观察，未修复）

**现象与根因。** #014 广集只排除真实 ffmpeg `test_social_e2e.py` 后，pytest 收集
`tests/test_bilibili_api.py` 即在模块顶层运行真实 Bilibili API 查询和 `curl -sIL b23.tv`。短链接
请求 15 秒超时，整套测试以 collection error 中断；导入测试模块本身就有外部副作用，所谓 offline
广集并不诚实。此前网络可用时该文件没有产生 test case 计数，因此绿灯掩盖了隐式联网。

**当前证据与临时边界。** 失败结果为 **1 collection error / 20.94s**，异常是
`subprocess.TimeoutExpired`。排除该 diagnostic 与 social e2e 后为
**266 passed, 1 skipped / 50.74s**。本轮没有重试网络，也没有修改该文件，以免混入 board identity
原子任务；已进入下一循环队列。

**Carry-forward judgement.** 是。**WARNING FOR src/ocrllm**: 默认单元/回归测试的 collection 与
import 必须零网络、零凭据、零外部进程副作用；live diagnostics 必须放到显式 opt-in marker 或独立
script，并以清晰 preflight/timeout 报告，不能靠网络恰好可用来维持“全量绿”。

## 2026-08-23 — production board 取消丢失已付费批次（已修复）

**现象与根因。** `BoardProcessor.process()` 虽然在 provider 前保存了稳定 repair sidecar，但 Markdown
只在整个批次循环结束后写一次。首批成功后，若 reporter 在下一批检查时取消，最终写入会被越过，已付费
正文全部丢失；provider 内抛出的 `CancelledError` 或 `ProviderSetupError` 又会被 broad
`except Exception` 吞成普通失败，隐藏真实终止原因。

**修复。** sidecar 保存后立即用既有 `render_board_batch_failure(..., "任务未完成")` 为所有批次建立
固定 slot，并原子发布完整 Markdown。每个成功或普通失败只替换自己的 slot，随后立即通过既有 atomic
writer 发布；成功在 content callback 前保存。取消直接传播，setup failure 经既有 chain predicate
识别后传播，当前及后续未完成 slot 保持可修复。没有增加 `unfinished` schema、通用 executor 或跨
modality 抽象。

**失败优先证据与验证。** 修前四条回归为 **4 failed / 6.49s**，分别证明首次 dispatch 无 Markdown、
reporter 取消丢首批、provider cancellation/setup 被吞。修后 board checkpoint/identity/repair/failure
集 **26 passed / 25.46s**；排除真实 ffmpeg e2e 与延期的 import-time Bilibili diagnostic 后，legacy
离线广集 **270 passed, 1 skipped / 87.96s**，唯一 skip 是显式 live Google discovery。相关文件
`py_compile` 与 `git diff --check` 通过；无网络/provider/付费调用。

**Carry-forward judgement.** 是。**WARNING FOR src/ocrllm**: 图像批处理必须在首次 provider dispatch
前持久化 typed/versioned slot，并在每个付费成功后、任何可取消 callback 前原子提交。取消/setup
failure 必须传播且不能破坏已提交 slot。不要移植本次 localized failed-marker skeleton；新库应扩展现有
typed checkpoint state。legacy video historical batch identity 仍需独立证据，不能据此预建通用媒体框架。

## 2026-08-23 — video repair 用当前 batch size 误解历史失败（已修复）

**现象与根因。** Phase 4 普通异常只写 `<!-- 批次 N 失败 -->`，没有保存该批实际包含哪些帧。
`repair_board()` 按当前 `_phase4_batch_size()` 重新切分 `frame_info.json`；例如原 batch size=2 的历史
batch 2 本应是第 3、4 帧，设置改为 1 后会静默重试第 2 帧并把正文写回旧失败位置。

**修复与兼容边界。** 生产失败时已经持有精确 `frames`，所以不再保存含糊 batch marker，而是立即为
每帧写已有 meta marker 与 `帧 <id> 识别失败`。repair 只消费显式 frame ID；发现任何旧 batch-only
marker 时，在读取 frame artifact、报告进度或 provider 调用前明确拒绝并要求重新执行板书识别。删除按
当前配置展开 batch、拼装候选结果和替换 batch placeholder 的全部分支。显式逐帧旧输出继续兼容；无法
证明成员的旧 batch 输出不做猜测。没有新增 sidecar/schema 或通用媒体抽象。

**失败优先证据与验证。** 两条回归修前为 **2 failed / 5.42s**，分别证明生产缺少精确 frame identity
与旧 batch marker 会实际触发错误 provider 调用。最终 video repair/resume/failure/quality/writer 集
**40 passed / 26.31s**；离线 legacy 广集 **272 passed, 1 skipped / 90.30s**，唯一 skip 是显式 live
Google discovery。相关三个 Python 文件 `py_compile`、`git diff --check` 通过；无网络/provider/付费调用。

**Carry-forward judgement.** 是。**WARNING FOR src/ocrllm**: 新库遇到批请求失败时，应在 typed state
中把失败落到请求时已知的精确 source/unit slot，不得只保存可被配置重新解释的 batch ordinal。这里使用
逐帧 localized Markdown 是 legacy 现有 repair unit 的减法修复，不是新库应复制的持久化格式。

## 2026-08-23 — 独立视觉普通 429/5xx 被误报为免费额度耗尽（已修复）

**现象与根因。** 独立 vision provider 启用 `advance_queue_on_retriable_errors` 后，普通 429/5xx
会被 `_should_advance_vision_queue()` 选中，但四个 wire error 出口都把它包装成
`FreeTierExhaustedError`。候选链因此调用“免费额度耗尽”GUI notifier；若候选全失败，又把原始
503 等异常改写成“所有免费额度模型均已耗尽”。显式 opt-in 切候选本身是已有产品能力，错误在于
复用了带配额含义的控制异常。

**修复。** 增加窄作用域 `VisionQueueAdvanceError` 保存原始异常，Chat Completions 与 Responses
统一按“明确 quota”或“普通临时错误”创建对应信号。候选链改名为
`_call_with_model_fallback()`：只有前一种信号调用 quota notifier；后一种静默切换并在候选耗尽时
重新抛出原始 provider 异常。没有改变 429/5xx 设置、调用顺序、重试次数或 UI。

**证据。** 新增/加固回归覆盖普通 429 成功 failover 不通知、普通 503 全失败保留异常、Responses
503 中性 failover，以及明确 `AllocationQuota.FreeTierOnly` 仍通知并切换。修前 **2 failed,
12 passed / 7.53s**；修后 `tests/test_vision_provider.py` **15 passed / 2.88s**。无 live/provider 调用。
排除真实 ffmpeg e2e 与延期的 import-time Bilibili diagnostic 后，离线广集为
**275 passed, 1 skipped / 43.57s**；唯一 skip 是显式 live Google discovery。`py_compile` 与
`git diff --check` 通过。

**Carry-forward judgement.** 是。**WARNING FOR src/ocrllm**：临时 provider failure 与 quota
exhaustion 即使都能触发候选恢复，也必须是不同 disposition；不能让内部复用改变用户文案或最终
异常。active library 已有对应 typed 边界，本次未修改。

## 2026-08-23 — Google 明确 quota JSON 被 advisory billing 文案误分类（已修复）

**现象与根因。** `classify_google_error()` 对非 JSON 的 `RESOURCE_EXHAUSTED: You exceeded your
current quota, please check your plan and billing details.` 返回 `QUOTA_EXHAUSTED`。同一内容放进标准
429 JSON 后，`_classify_google_json_error()` 却先匹配 `billing` 单词而返回 `BILLING`。两个类型都
允许切候选，所以只断言模型调用顺序会假绿，错误类型和后续用户说明仍不诚实。

**证据纠正。** 原观察把 `FreeTierOnly` / `FreeAllocationQuotaExceeded` 当成可能的 Google marker；
仓库代码、历史和 Google 说明均不支持，两者属于 DashScope compatibility 路径。Google 429 /
`RESOURCE_EXHAUSTED` 覆盖多种额度窗口，不能整体升级成 quota exhaustion。

**修复。** 只识别已有回归证据的 Google 组合文案 `you exceeded your current quota` +
`check your plan and billing details`，且已有 rate limit/RPM/TPM/RPD 标记仍优先。该窄判断放在 generic
billing 和 429 分支前。普通 429 继续同模型重试，503 high demand 继续重试，真实 payment/billing
仍是 `BILLING`；没有新增配置、调用或抽象。

**证据。** 直接 classifier 断言修前为 **1 failed, 19 passed / 2.09s**。第一版修复后，加强后的
“quota advisory + RPM marker”回归继续发现 billing 抢先：focused **1 failed, 20 passed / 1.38s**，
离线广集 **1 failed, 277 passed, 1 skipped / 71.89s**。最终 Google error 集
**21 passed / 0.99s**，Google 相关四文件 **61 passed / 14.38s**，legacy 离线广集
**278 passed, 1 skipped / 69.24s**。唯一 skip 是显式 live Google discovery；无 provider 调用。

**Carry-forward judgement.** 是。**WARNING FOR src/ocrllm**：新增 Google provider 时必须把普通
429 窗口限流、明确 quota exhaustion 与真实 billing failure 分开建模；不能因它们可能都切候选就
只测调用顺序，也不得复用 DashScope marker。

## 2026-08-23 — pytest collection 隐式访问 Bilibili 网络（已修复）

**现象与范围复核。** 早先“仅观察”条目记录了 `tests/test_bilibili_api.py` 在 import 时直接创建
`curl_cffi.Session`、访问 Bilibili 首页/finger/view API，并启动两个 `curl -sIL b23.tv` 子进程。
它没有 test function 或 assertion，实际是临时 live diagnostic 误用 `test_*.py` 名称。root pytest
因 `testpaths=["tests"]` 不收集 legacy，但显式 `pytest legacy_app/tests` 或 `pytest .` 会在 collection
联网。修复只处理测试隔离，不修改 downloader、Bilibili API production code 或 social product behavior。

**两条路径与选择。** 路径一把脚本改成环境变量控制的 live pytest test；路径二保留 manual
diagnostic，改为非 test 文件并用函数/main guard 显式执行。选择二：原文件没有可验证的 pass/fail
contract，social media 又已延期，把它升级成 formal live CI test 会发明新语义。文件改名为
`diagnose_bilibili_api.py`，唯一入口 `diagnose_bilibili_api()` 与文件名一致，只有直接运行脚本才调用；
所有 session GET 和 curl subprocess 都有 15 秒 timeout。

**失败优先证据与修复。** 新 import-safety regression 用 fake `curl_cffi.requests.Session` 和 patched
`subprocess.run` 禁止任何外部工作，再用 `runpy.run_path()` 导入 diagnostic。旧文件在 Session 构造处
稳定 **1 failed / 0.14s**，没有真实网络。修后 focused 为 **1 passed / 0.04s**；collect-only 只发现
这个 offline regression，diagnostic 本身不被收集或执行。explicit live 入口仍是
`python legacy_app/tests/diagnose_bilibili_api.py`，本轮没有运行它。

**Carry-forward judgement.** 是。**WARNING FOR src/ocrllm**：所有默认 import、collection 和 capability
检查必须零网络、零凭据、零外部进程副作用。需要 live 验证时，使用明确的 opt-in test 或 guarded
diagnostic，并把 optional dependency import 和 bounded external calls 放在执行入口内；不要只靠文件名
排除，因为 broad repository collection 仍可能导入它。

## 2026-08-23 — 短音频普通失败可被包装成成功结果（仅观察）

**现象。** Stage A1 边界审计重新检查 legacy short-ASR 路径时确认：普通 provider 异常可以被转换成
失败说明文字，随后仍作为 segment 内容汇总并返回输出路径。单 segment 请求因此可能生成看似正常的
Markdown；非空的拒答或“没有语音”文字也缺少可靠的 typed failure 边界。本轮只记录真实旧行为，没有
修改 legacy production code，也没有运行 provider。

**暂不修复原因。** social 已延期，而本轮目标是收窄新库 A1；直接重写旧音频调用会同时触及旧 GUI、
模型路由和恢复格式，不能作为小修混入。后续若维护 legacy 音频，必须先写失败优先回归，证明 provider
error、refusal、empty 和 no-speech 都不会发布成功 transcript。

**Carry-forward judgement.** 是。**WARNING FOR src/ocrllm**：A1 必须把 provider error、empty、refusal
和 no-speech 映射成明确异常，失败时不发布 Markdown、不返回成功路径；不得复制 legacy 的失败文本回填、
隐藏协议 fallback 或依模型名猜协议。

## 2026-08-24 — legacy GUI launcher rejected an existing OCRLLM environment (fixed)

**What broke.** Double-clicking `launch_gui.bat` stopped with “conda was not
found” on the current Windows account, and there was no OCRLLM desktop entry.
The intended interpreter already existed at
`D:\Anaconda\envs\OCRLLM\python.exe`, and it could import PyQt5, so the error
was a launcher failure rather than a missing application environment.

**True root cause and fix.** The launcher required `conda` or `conda.bat` to be
on `PATH` even when the complete named environment was already installed. It
also had LF-only line endings, unlike the existing CRLF setup script. The BAT
now uses the verified environment interpreter directly and retains the old
conda activation path only as a fallback. `.gitattributes` pins both legacy
BAT files to CRLF. A desktop shortcut named `OCRLLM Legacy.lnk` was created in
the current account's resolved OneDrive Desktop and points only to the tracked
launcher; it stores no provider credential.

**Verification.** Before the fix, `cmd.exe /d /c "legacy_app\launch_gui.bat
--help"` returned 1 with the conda error. After the fix, the same command
returned 0 with the GUI argument help. A real `--spawn 1` run returned 0 and
created one new Python GUI process from the intended environment. No provider
API was called and no credential was read, printed, or written.

**Carry-forward judgement.** Limited. The active `src/ocrllm` package has no
GUI or BAT launcher and must not acquire one for compatibility. The general
risk can reappear in future optional command entrypoints: environment presence
must be checked by the executable actually needed, not inferred only from a
shell activation command being on `PATH`. No `WARNING FOR src/ocrllm` is
needed until such a launcher is intentionally added.

## 2026-08-26: automatic board cropping silently discarded recognition pixels

**Observed and fixed.** The legacy board-image path defaulted to
`ImagePreprocessor.auto_crop_board()`, which selected a contour or guessed
quadrilateral and could apply a perspective transform. The legacy video path
sampled frames to infer one `board_roi`, then used only that rectangle for
blank/occlusion decisions, comparison thumbnails, and the JPEG sent to
recognition. These assumptions fail on separated boards, sliding boards, and a
board beside a projector screen; a plausible crop could silently remove valid
content. PDF rendering did not use this module.

**Change.** The complete crop/perspective module was deleted. The unrelated
Unicode OpenCV writer moved to `imwrite_unicode.py`; board preparation moved to
`prepare_board_image.py` and now either copies the exact complete image bytes or
performs aspect-preserving full-field downscaling/conversion. Automatic and
manual quadrilateral arguments, the video ROI detector, ROI-only candidate
JPEGs, ROI-based occlusion rejection, ROI configuration fields, GUI checkbox,
and CLI option were removed. New repair manifests record
`full-frame-resize-v1`. The old `skip_preprocess` field is accepted only while
reading historical manifests and cannot select deleted behavior.

**Verification.** Direct full-frame tests preserve all four corner pixels,
exact source dimensions, exact bytes when no resize is needed, and both outer
edges of a saved video candidate. Focused board/failure tests passed 28/28;
neighboring video/GUI/config tests passed 30/30. The bounded legacy suite passed
281 tests with one expected skip, excluding only the deferred real
social-download E2E and the maintainer's protected untracked test.

**Carry-forward judgement. WARNING FOR src/ocrllm.** The active library was
checked and already retains complete video frames and PDF-rendered pages; it has
no analogous corner/ROI/perspective stage today. Do not add one later. Frame
selection may use private comparison thumbnails, but every image sent to OCR or
published as a retained asset must preserve the complete source field of view.

## 2026-08-26: deleted crop configuration and wording survived module removal

**Observed and fixed.** The executable corner/ROI/perspective module was already
gone, but `ImagingConfig` still exposed four unused denoise/Canny/contour fields,
and the video progress surface still called complete-frame resizing “crop and
resize.” The imaging and processor READMEs also described the deleted module as
present. These leftovers could mislead a later maintainer into rebuilding the
rejected operation.

**Change and verification.** The unused config class and `AppConfig.imaging`
field were deleted. The private resize class/function, runtime labels, and
current READMEs and resume-chain guide now say complete-frame
aspect-preserving resize; stable phase-3 keys and manifests were left unchanged.
A regression proves that an actual downscale preserves the aspect ratio and both
outer image edges, and another proves the deleted crop config is absent.

**Carry-forward judgement. WARNING FOR src/ocrllm.** The active package still
contains no such config or executable geometry-changing stage. Keep it that way:
comparison thumbnails may be resized privately, and full pages/frames may be
uniformly bounded, but never expose corner, contour, ROI, or perspective options
for recognition inputs.

## 2026-08-26: deleted imaging section remained in config update whitelist

**Observed and fixed.** `AppConfig.imaging` and the executable crop module were
already gone, but `_SECTION_NAMES` still accepted `imaging`. An API
`config_overrides` request could therefore pass the section-name check and then
crash with `AttributeError` while reading a field that no longer exists. The
stale name is deleted, and the full-frame regression now requires the override
to be rejected with `TypeError` at the configuration boundary.

The unused `STEP_FRAME_PREPROCESS` constant and the architecture-diagram node
for deleted `preprocess.py` were also removed. Stable numeric phase 3 remains,
because current checkpoints use it for complete-frame resizing. The historical
repair-manifest `skip_preprocess` reader remains read-only and cannot select any
crop behavior. Focused legacy full-frame/PDF tests passed 5/5; active video/PDF
full-frame tests passed 3/3. The bounded legacy suite passed 266 tests with one
expected skip after excluding three deferred social-download E2E files and the
maintainer's protected untracked test; the active suite passed 1,782/1,782.

**Carry-forward judgement. WARNING FOR src/ocrllm.** No analogous active-library
config, export, or implementation exists. Keep temporal frame selection and
full-page/full-frame scaling distinct from rejected spatial cropping.

## 2026-08-27: stale migration prose still listed board-region extraction

**Observed and fixed.** A legacy migration note still listed “board-region
extraction” as a model-independent capability worth retaining. The executable
crop/perspective module, configuration, GUI/CLI controls, and video ROI path had
already been deleted, so this prose could encourage a future maintainer to
rebuild a deliberately rejected operation. It now names only complete-image
aspect-preserving resize and format conversion, explicitly without board
localization, crop, or perspective correction.

The historical repair-manifest `skip_preprocess` reader remains intentionally
read-only: it cannot select image behavior, and every repair uses the current
full-frame preparation path. Removing that compatibility token would break old
legacy repair records without deleting any executable crop behavior.

**Verification.** The current legacy full-frame regression passed 4/4 and a
fresh runtime-symbol/call-chain audit found no corner, ROI, crop, homography, or
perspective operation. The only remaining Canny use classifies complete blank
frames for temporal selection and does not change recognition pixels.

**Carry-forward judgement. WARNING FOR src/ocrllm.** The active library has no
analogous operation. Keep full-frame comparison thumbnails, uniform full-page
rendering, and aspect-preserving limits distinct from forbidden spatial crop.

## 2026-08-27: PDF partial repair hid its remaining failed pages

**Observed and fixed.** `PDFProcessor.repair()` accepts only one failed page or
one contiguous failed range per HTML marker. When part of a range succeeded, it
joined noncontiguous missing pages into one marker such as `第 2, 4 页识别失败`.
That text was outside `_FAILED_PAGE_RE`, so the next repair pass reported no
failed pages even though failures remained.

The producer now emits one existing single-page marker for every unresolved
page, in original page order. The parser was deliberately not widened: adding
comma-list grammar would preserve an output shape that the application never
needed. A production-path regression repairs pages 1–4 with pages 1 and 3
successful, verifies all four serial provider calls and surrounding/successful
Markdown, then requires the rewritten file to expose pages 2 and 4 again.

**Verification.** The regression failed before the fix with `[] != [2, 4]`.
After the fix, it plus legacy failure propagation passed 13/13; adding the PDF
fresh-process renderer passed 14/14. `compileall` and `git diff --check` passed,
and an independent review found no ordering, exception, or scope regression.
The bounded provider-free legacy gate selected 36 tracked test files plus this
new regression, excluded only three real social E2E files and live Google model
discovery, and passed 267/267 with no skip or provider access.

**Still open.** PDF repair still trusts a caller-selected PDF plus localized
Markdown and still publishes through direct `Path.write_text()`. Those identity
and atomicity weaknesses are separate tasks and were not hidden or expanded
into this marker correction.

**Carry-forward judgement. WARNING FOR src/ocrllm.** The active library has no
PDF repair path and must not copy this localized grammar. If its separate
partial-artifact choice is approved, every artifact it emits must be consumable
by the same strict schema, with source identity and atomic publication.

## 2026-08-27: PDF repair bypassed the shared atomic text writer

**Observed and fixed.** PDF repair was the remaining media-repair path that
published with direct `Path.write_text()`. A successful provider response
followed by an encoding, flush, fsync, or replacement failure could therefore
truncate or partially expose the only existing Markdown. Audio, board, and
video repair already used `core/write_text_atomically.py`.

`PDFProcessor.repair()` now calls that existing writer once after its unchanged
marker transformation. No second writer, transaction, lock, retry, or state
protocol was added. A production-path regression injects `os.replace` failure
after one successful page recognition and requires the exception to propagate,
the original CRLF Markdown bytes to remain exact, the temporary sibling to be
removed, and render/provider counts to remain one each. Before the fix, the
test failed because PDF bypassed the injected atomic boundary and published
normally.

**Verification.** PDF repair, the writer's encoding/fsync/replace regressions,
and failure propagation passed 18/18; `compileall` and `git diff --check` passed.
An independent review reran the same 18 tests and found no blocker. The bounded
provider-free legacy gate selected 36 tracked files, excluded three real social
E2E files plus live Google discovery, and passed 268/268 with no skip or
provider access; the protected untracked test was not collected.

**Still open.** PDF repair continues to trust a caller-selected PDF and
localized page markers without source identity. Atomic publication prevents a
torn replacement; it does not claim cross-process coordination or prove that
the chosen PDF matches the Markdown.

**Carry-forward judgement. WARNING FOR src/ocrllm.** The active library already
uses its own atomic Markdown writer. If repair is later approved, keep that
boundary and add source-bound identity rather than importing this legacy parser.

## 2026-08-27: video tail changes can be omitted before selection

**Observed and fixed.** Legacy video coarse scanning built its
targets with `range(0, total_frames, coarse_skip)` and did not explicitly add
`total_frames - 1`. With the default five-second interval, a meaningful board
change confined to the final almost-five-second tail can therefore remain
unobserved. The refinement pass only scans gaps between existing candidates and
does not create a final-candidate-to-EOF gap. Ordinary segmentation correctly
flushes the last candidate it did observe, so the primary defect is missing EOF
sampling rather than failure to close a segment.

A second bounded defect was in the post-calibration density cap: its uniform
index formula does not force the last selected candidate into the capped output.
For example, capping 11 candidates to 10 selects indices 0 through 9 and omits
index 10.

The coarse target list now conditionally appends `total_frames - 1`; an aligned
final target remains present exactly once and a nonpositive frame count remains
empty. The safety cap now maps its first and last output slots exactly to the
first and last selected candidates while keeping its existing fixed count and
ordering. The initial two regressions failed with seek targets `[0, 50, 100]`
instead of `[0, 50, 100, 149]` and capped endpoint 9 instead of 10. The final
focused set also covers the aligned no-duplicate case and a real six-frame MP4,
and passes 4/4. The adjacent full-frame, capture, and repair set passes 12/12;
the bounded provider-free legacy gate selected 36 tracked files plus this new
focused file and passes 268/268 with no skip, provider, or network access.

No scan interval, comparison threshold, refinement, pHash, blank filtering,
failed-seek behavior, complete-frame publication, crop, ROI, or perspective
operation changed. The fix did not import the active selector or add a shared
sampling abstraction.

**Carry-forward judgement.** The same omission must not re-emerge in future
video work. The active `src/ocrllm` path already explicitly samples the exact
final frame, fails honestly when it cannot decode it, closes the final segment,
and preserves both endpoints under its density cap; its real-MP4 EOF regression
and capped-selector regression both pass. No active-library fix or compatibility
layer is required.
