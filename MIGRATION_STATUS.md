# OCRLLM Migration Status

This file is a navigation aid. **`docs/ACTIVE_STATE_AND_RULES.md` outranks it**
and carries current state, the open defect register, and the coding and
documentation rules. Read that file first.

## Posture Change, 2026-08-18

The library was built as a feasibility spike on one narrow slice (DashScope +
image). That question is answered: the contract, quality-gate, and error layers
work. The project is now maintained as a product.

Consequences, stated in full in `docs/ACTIVE_STATE_AND_RULES.md`:

- Defects in shipped surface outrank new capability.
- `contracts/` and `worker/` are frozen until a consumer exists.
- `docs/` has one current-state file; the rest are dated historical records.

The approved current work is
`docs/plan_phase1_maturation_and_phase2_audio.md`: mature Phase 1 out of its
trial constraints (live model discovery, flowed output with real resume,
disclosed automatic model-switching recovery), then deliver Phase 2 as an
mp3-only audio recognizer.

Defect repair D1-D7 and the vision/audio provider split are tracked separately
in `docs/plan_phase1_defects_and_provider_split.md`.

Phase 2's original Electron JSONL worker framing is superseded. `worker/` and
`contracts/` are frozen; Phase 2 now means audio.

## Legacy Maintenance Diary

`legacy_app/AGENTS.md` now has a "Working Diary Rule" section. Read its
2026-08-18 entry before touching PDF/video/board path handling or provider
response validation in either `legacy_app/` or `src/ocrllm/` — it records real
root causes (not surface symptoms) for a Windows path-creation failure and a
silent-refusal "fake success" class of bug, plus explicit `WARNING FOR
src/ocrllm` notes so the same defects are not re-introduced when those
vertical slices are ported.

## One-Sentence Summary

The old OCRLLM app has been moved to `legacy_app/`; the active project is an
importable Python library in `src/ocrllm`, with Phase 0, Phase 1, and Phase 2
versioned JSON/JSONL worker GO. Phase 2A image-library completion is also GO;
local OCR, shared execution policy, adapter-owned provider/model configuration,
provider error disposition, credential scheduling, and image resume are GO. No
later phase is active, and Phase 3 PDFium has not started.

## First Files To Read

Use these files to avoid confusing new work, old app code, and suspended future
planning:

```text
docs/ACTIVE_STATE_AND_RULES.md        Current truth, defects, rules. Outranks all.
docs/plan_phase1_maturation_and_phase2_audio.md
                                      Current work.
docs/plan_phase1_defects_and_provider_split.md
                                      Defect repair, in progress separately.
START_HERE.md                         One-screen repo map.
README.md                             Short public overview.
src/ocrllm/README_ACTIVE_LIBRARY.md   Active package boundary.
src/ocrllm/AGENTS.md                  Active package editing rules.
docs/ocrllm_library_go_no_go.md       Phase gates, file responsibilities, and
                                      the migrate/rewrite/reject boundary.
docs/library_migration_decision.md    Foundational library-making rationale.
legacy_app/README_LEGACY.md           Legacy app boundary.
legacy_app/AGENTS.md                  Legacy app editing rules and diary.
docs/ocrllm_module_target_design.md   Target-state module design map.
docs/provider_cost_and_reliability_policy.md
                                      Account-specific provider policy.
Architecture.md                       Suspended future architecture reference.
```

The remaining `docs/phase*`, `*_decision_*`, and `*_checkpoint_*` files are
dated historical records of how past decisions were reached. Do not read them to
learn current state.

## Why This Happened

The previous codebase had useful features, but it was not a clean dependency for
other projects:

- It imported as uppercase `OCRLLM`, while the desired package is lowercase
  `ocrllm`.
- It mixed GUI, CLI, FastAPI, social downloaders, processors, prompts, and core
  logic in one package surface.
- It had no root `pyproject.toml`.
- It defaulted output/temp paths into the package directory.
- It exposed implementation classes before there was a stable library facade.

The active decision is to make a small Python-first library and migrate proven
behavior one vertical slice at a time. Implementations are rewritten behind the
new contract; legacy classes and files are not ported. Exact rules are in
`docs/ocrllm_library_go_no_go.md`.

## What Is Current

Use this:

```text
src/ocrllm/
```

Do not build new integrations on this:

```text
legacy_app/OCRLLM/
```

The current public API is:

```python
from ocrllm import (
    ConcurrencyLimited,
    Config,
    DashScopeSettings,
    VisionModelSettings,
    RecognitionResult,
    recognize,
    recognize_batch,
    OCRLLMError,
    ConfigError,
    DependencyMissing,
    InvalidSource,
    NoSpeechDetected,
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
    UnsupportedFormat,
    Cancelled,
    get_provider_error_disposition,
)
```

Phase 0 and Phase 1 are GO. The active image route validates PNG/JPEG sources and sends
request-scoped snapshots isolated from later caller-path changes to either one
synchronous injected vision provider or exact built-in adapter settings:

```python
from ocrllm import Config, recognize


class Provider:
    def recognize_images(self, image_paths, *, prompt, config):
        return "# Board\n"


result = recognize("board.png", config=Config(provider=Provider()))
```

The built-in route requires explicit regional settings and never guesses an
endpoint from a credential:

```python
from ocrllm import Config, DashScopeSettings, VisionModelSettings, recognize


result = recognize(
    "board.png",
    config=Config(
        provider=DashScopeSettings(
            region="cn-beijing",
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        ),
        vision_model=VisionModelSettings(
            name="qwen3.7-plus-2026-05-26",
        ),
    ),
)
```

The provider receives ordered snapshot paths, not the caller's mutable paths.
It must read them and return before `recognize_images()` returns. The library
then removes the snapshots; a cleanup failure is typed and never silently
reported as success. The active path now provides:

```text
allowed inputs                     PNG, JPG, JPEG
canonical media/profile            image / board
missing/empty/invalid/oversized     fail before provider invocation
provider empty/control-only result  PROVIDER_RESPONSE_INVALID
metadata                            recursively copied and immutable
output_dir=None                     memory-only
existing output                     OUTPUT_EXISTS unless overwrite=True
provider/config secrets             absent from public repr/error/result data
built-in provider/model             dashscope / qwen3.7-plus or pinned snapshot
built-in provider metadata          region, thinking/high-resolution flags,
                                    model, provider, prompt version, image count
public Config boundary              exact Config only; freshly revalidated
```

The built-in DashScope adapter, offline boundary tests, licensed five-class
image corpus, deterministic scorers, and manifest-authenticated live runner are
complete. V17 ran in `cn-beijing`: all 13 recognitions and 52 provider calls
completed without retry, both independent full runs passed, and Run B repaired
exactly one missing handwriting sign without a handwriting-specific route. The
clean committed-wheel gate at `0278b66` also passed. The immutable result is
summarized in `docs/phase1_live_quality_result_v17_2026-07-11.md`. Local OCR is
now available through the same facade. Google, Codex, PDF, audio, and video
adapters do not exist in the active library.

Current package metadata still has no base runtime requirements. It declares
exactly `dev`, `image`, `dashscope`, and `ocr`; `image` installs
`Pillow>=10.4,<13`, `dashscope` installs `openai>=2.30,<3`, and `ocr` installs
the maintained RapidOCR plus ONNX Runtime path. Plain `import ocrllm` must leave
all optional/heavy modules absent from `sys.modules`.

Active PDF policy is decided now even though PDF implementation is not
authorized yet:

- Use PDFium through `pypdfium2`.
- Keep `pypdfium2` behind future `ocrllm[pdf-text]` and
  `ocrllm[pdf-vision]` extras and out of base import. Text-only installs do not
  install Pillow.
- Rewrite PDF rendering and text extraction; do not port PyMuPDF/`fitz` code.
- Start with `pypdfium2>=5.11.0,<5.12` and `Pillow>=10.4,<13`; lock the first CI
  proof to pypdfium2 5.11.0 and Pillow 12.2.0.
- Serialize PDFium calls behind one process-wide lock. Do not port the legacy
  threaded renderer because PDFium is not thread-safe.
- Do not mark PDF supported until the Phase 3 gate in
  `docs/ocrllm_library_go_no_go.md` passes.

Local PDFium feasibility evidence on Windows/Python 3.13:

```text
pypdfium2 5.11.0
PDFium 151.0.7920.0
2-page mixed PDF opened
text page extracted expected content
raster-only page extracted no text
both pages rendered at 1224 x 1584
malformed PDF raised PdfiumError error code 3
wheel size 3,778,234 bytes
installed size 8,306,352 bytes
```

This is a conditional feasibility GO, not active PDF support. Python 3.10,
Unicode, encrypted, hostile, large-document, recognition, cancellation, and
license-notice packaging gates remain.

Latest Phase 0 gate evidence on the recorded Windows reference host, from code
checkpoint `5018ad0` plus the final phase-transition documentation tree on
2026-07-10:

```text
root tests                         141 passed
                                  (138 active-library, 3 course-tool tests)
wheel size                         31,151 bytes
wheel SHA-256                      FD983CA90944F545A4B670F33A8ABF015712E1DDAC8F866BB4703E0A465C707D
isolated no-deps install          135,213 bytes
Python 3.10, 30 fresh processes   wall median/p95/max 58.642/108.161/114.861 ms
                                   CPU median/p95/max 46.875/78.125/78.125 ms
Python 3.13, 30 fresh processes   wall median/p95/max 22.865/30.880/31.043 ms
                                   CPU median/p95/max 23.438/31.250/31.250 ms
plain-import optional modules     PIL, pypdfium2, openai all absent
base runtime requirements         none
native binaries in base wheel     none
declared extras                    dev, image
clean image installed delta       15,814,896 bytes
clean image Pillow                12.3.0
clean generated-PNG recognition   complete, source_type=image, profile=board
```

The exact gate ran the authoritative test/build/isolated-target/timing commands.
For the image-extra proof it generated an 8-by-6 PNG inside the fresh image venv
after installing the wheel, then decoded and recognized that file; this replaces
the stale reference to a nonexistent committed `tests/fixtures/images/valid.png`.
All Phase 0 numeric and behavior gates passed at that historical checkpoint.
Phase 0 alone did not make recognition quality available. Current checkpoint
`e328253` supplies the licensed Phase 1 corpus and scorer separately. The first
live result now exists and is a recorded NO-GO: 13 calls completed, zero of two
full runs passed.

The historical Phase 0 verification entrypoints used were:

```powershell
& D:\Anaconda\envs\OCRLLM\python.exe -m pytest -q -p no:cacheprovider
& D:\Anaconda\python.exe -m build --wheel --outdir $wheelDir
& D:\Anaconda\envs\OCRLLM\python.exe -m pip install --no-deps --target $targetDir $wheel.FullName
& D:\Anaconda\envs\OCRLLM\python.exe -m venv $imageVenv
& $imagePython -m pip install "$($wheel.FullName)[image]"
```

The 30-process/two-warm-up timing loop, metadata/native guard, outside-repo
import, deterministic PNG generator, and image recognition assertions were run
exactly as recorded in `docs/ocrllm_library_go_no_go.md`.

A later Python 3.10 repeat measured 48.978 ms median with one 155.312 ms maximum
and failed the draft maximum-100-ms rule. A post-build run then measured 70.477
ms wall median/108.311 ms p95, while a separate unchanged-package probe measured
36.382/40.744 ms wall and 31.250/46.875 ms process CPU median/p95. The final gate
uses 30 fresh processes after two warm-ups: wall median <= 100 ms/p95 <= 200 ms
and process-CPU median <= 60 ms/p95 <= 100 ms; maxima remain diagnostic. This
change separates package CPU work from bounded scheduler/antivirus noise rather
than waiving a CPU or percentile failure.

HarmonyOS/ArkTS integration is deferred. It is not an active feature, phase, or
compatibility claim.

## Historical Legacy Social-Long Course Path

The Bilibili/social downloader still lives under `legacy_app/OCRLLM/`. It is a
read-only behavior reference for this migration, not a public `ocrllm` library
API or an active test surface.

Detailed incident history, implementation map, verification commands, and
operational rules are in:

```text
docs/legacy_bilibili_social_long_debug_record.md
```

The recorded multi-part Bilibili command was:

```powershell
$env:PYTHONPATH='legacy_app'
D:\Anaconda\envs\OCRLLM\python.exe -m OCRLLM.cli social_long `
  "https://www.bilibili.com/video/BV1nJ411z7fe?p=33" `
  --parts 1-33 --resume -o output\bilibili_cs231n_full
```

Expected per-part output is exactly two Markdown files:

```text
*_板书识别.md
*_录音识别.md
```

The Bilibili comments and per-part danmaku context is written separately to:

```text
bilibili_social_context.md
```

This legacy path has resume support for existing downloads, completed video
phases, and in-flight DashScope FileTrans task IDs. Keep new downstream
projects importing `ocrllm`; do not expose this legacy processor as a new public
library boundary.

For multi-part YouTube course playlists, the equivalent recorded legacy
workflow is documented here:

```text
docs/legacy_youtube_playlist_social_long_workflow.md
```

The recorded command used the same legacy CLI boundary:

```powershell
$env:PYTHONPATH='legacy_app'
D:\Anaconda\envs\OCRLLM\python.exe -m OCRLLM.cli social_long `
  "https://youtube.com/playlist?list=PLggLP4f-rq02vX0OQQ5vrCxbJrzamYDfx&si=6VZ5fem42kqyyasd" `
  --parts 1-97 --resume -o output\youtube_modern_robotics_full
```

The 2026-07-06 YouTube playlist run is still legacy compatibility work, not a
public `ocrllm` API. It fixed and documents these additional runtime rules:

- YouTube playlist probe results must expose flat entries and route to
  `social_long`, not `social_short`.
- Non-Bilibili yt-dlp downloads must allow playlists and map `--parts` to
  `playlist_items`.
- Codex social-long video recognition caps the effective video frame batch size
  at 1 to avoid incomplete multi-frame markers.
- Video debug temp directory names must be Windows-safe and stable for YouTube
  titles.
- Social-long part output directories must strip trailing spaces/dots after
  legacy truncation, and long per-part artifact stems must shorten before
  Windows path limits are reached.
- Resume skip checks must accept an existing clean board/audio markdown pair
  before changing artifact stems, otherwise completed parts can be duplicated.
- DashScope FileTrans sidecars must be shortened using the resolved absolute
  `.tmp` path length.

The 2026-07-06 Bilibili CS231n run exposed and fixed these legacy runtime
problems:

- Multi-part Bilibili pages must route to `social_long`, not short-video mode.
- Requested part failures must fail the whole selected run instead of returning
  a partial course.
- Bilibili MP4 downloads need reusable `.part` downloads and existing-file
  reuse.
- Shared comments must be fetched once from the course AID; danmaku must be
  fetched per part CID.
- The old XML danmaku endpoint can return Bilibili 412/risk-control HTML, so
  the fallback path uses the segmented protobuf danmaku API.
- Each part is complete only with exactly `*_板书识别.md` and
  `*_录音识别.md`.
- FileTrans task IDs must survive process interruption so resume can continue
  polling instead of resubmitting the same long audio.
- Video resume must trust valid phase artifacts when a checkpoint was not
  marked complete before process exit.
- Social media GUI input must accept free-form text and Markdown-style pasted
  links, not only lines beginning with `http`.

Historical completion evidence recorded for the supervised Bilibili course
run; this is not current active-library evidence:

```text
33 part directories
33 downloaded MP4 files
33 *_板书识别.md files
33 *_录音识别.md files
0 FileTrans task sidecars
bilibili_social_context.md contained github.com/Divsigma/Courses and per-part danmaku
Focused legacy tests: 40 passed
Root active-library tests: 5 passed
```

## Legacy Codex/Filetrans Robustness Status

As of 2026-07-06, Codex video recognition and DashScope Filetrans audio
recognition remain legacy compatibility work in `legacy_app/`, not public
`ocrllm` API.

The July 2026 robustness fixes changed the legacy runtime behavior in these
ways:

- Codex CLI image-recognition subprocesses are launched with Windows
  no-window subprocess flags and closed stdin.
- Codex CLI nonzero exits and empty results are retried once and summarized,
  instead of dumping prompts or CLI diagnostics into board Markdown.
- In Codex mode, Phase 4 batch/per-frame failures are hard failures; they no
  longer create placeholder Markdown that looks complete.
- Codex mode skips the Qwen text hotword extraction step that made a Codex run
  appear to route through Qwen after image recognition.
- Filetrans cost logging uses the cached duration probe instead of the removed
  `_get_duration` method.
- Board-only reruns with `--phases 2 3 4` preserve existing audio transcripts
  instead of invalidating Phase 5 artifacts.

Historical evidence recorded by the 2026-07-06 audit:

```text
40 target course folders scanned
40 folders had exactly the expected board/audio Markdown pair
0 folders had known dirty markers
53 focused legacy regression tests passed
0 active legacy video checkpoints remained
```

Use `docs/legacy_filetrans_codex_debug_record.md` as behavior evidence. Do not
change or rerun this path for an active-library phase gate.

## Active Execution Decision And Target Design

`docs/ocrllm_library_go_no_go.md` is the controlling implementation record. It
defines:

- the current GO and NO-GO boundaries,
- one responsibility for each target file,
- which legacy behaviors to preserve,
- which implementations must be rewritten,
- which legacy areas are rejected or deferred,
- exact phase gates and verification commands.

`docs/ocrllm_module_target_design.md` describes the intended completed Python
library. It is a supporting design map, not the execution queue.

The documents are useful for rebuilding context after memory loss. The
GO/NO-GO record defines allowed boundaries; tests and real downstream imports
provide the evidence for advancing a gate.

## Provider, Preference, Pool, And Local-OCR Decision

The 2026-07-10 implementation brief is accepted as product direction, but its
configuration and pooling sketch is not accepted literally:

- `board` is a recognition profile. Local OCR is an execution
  engine/capability orthogonal to that profile and now reaches the same public
  `recognize()` facade after its engine, optional dependency, fixtures, quality
  threshold, and capability name passed their gates.
- A universal `category + api_key` requirement is invalid because Codex is a
  local authenticated CLI and has no per-call API key. Future provider config
  must be discriminated by adapter category and validate only applicable fields.
- Do not overload `api_key` as `str | tuple[str, ...]`. Immutable workflow config
  will compose provider/model choice, recognition preferences, execution policy
  (batch, in-flight limit, monotonic request-start interval), and retry policy.
  A credential pool is a separate stateful, concurrency-safe runtime scheduler.
- A future pool must account for fair rotation, cooldown/health, last use,
  provider quota domains, and error disposition. It must never persist or print
  raw keys. Multiple Google keys in one project must not be treated as extra
  project quota.
- Model input limits are provider/model capabilities. An impossible request such
  as 100 images for a 10-image model must fail before upload, not surface as an
  opaque provider error.
- Quality/cost/latency preference is task based. Do not hard-code an
  audio-specific "Pro" model rule into generic configuration.
- Durable resume remains versioned completed-unit/remote-task state for later
  long PDF/audio/video jobs. Phase 0 image snapshots are validation isolation,
  not resume state.

Local OCR and shared execution policy are GO. Provider pools, model queues, and
automatic retry/switching remain NO-GO until their own later Phase 2A gates.

## Phase 1 DashScope Decision (2026-07-10)

Phase 1 has one implemented provider baseline with offline boundary tests. This
is not a claim that the recognition-quality or live-provider gate has passed:

- `qwen-vl-max` is now a legacy model and is not the implementation baseline.
  The exact Phase 1 allowlist is `qwen3.7-plus` and
  `qwen3.7-plus-2026-05-26`; omitted `Config.vision_model.name` selects the pinned snapshot.
  The floating alias is allowed for explicit use, but cannot produce the initial
  reproducibility evidence.
- Exact `DashScopeSettings` in `Config.provider` selects the built-in adapter.
  String provider categories are invalid. The settings require an explicit region and full
  OpenAI-compatible `base_url`; the preferred production value is that region's
  workspace-dedicated endpoint. API keys are region-specific, so the adapter
  validates the region/endpoint pairing and never guesses a region or endpoint.
  An existing shared DashScope-domain endpoint may be selected explicitly for a
  legacy integration, but it is never a silent default.
- The settings own `region`, `base_url`, optional secret `api_key`,
  `enable_thinking=False`, `vl_high_resolution_images=True`, and optional fixed
  scout model. Workspace
  endpoints use
  `https://{workspace-id}.{region}.maas.aliyuncs.com/compatible-mode/v1` for
  `ap-northeast-1`, `ap-southeast-1`, `cn-beijing`, `cn-hongkong`, or
  `eu-central-1`. The only shared compatibility endpoints are the matching
  Beijing, Singapore, Hong Kong, and US hosts accepted by the validator.
- Every public call revalidates an exact `Config` before source/provider work.
  Injected providers keep the caller's original `Config` identity. A built-in
  settings provider is snapshotted at the first line of image processing, before
  provider/model resolution, prompt construction, or cancellation inspection;
  its adapter revalidates that isolated copy again. Nested settings are
  reconstructed so callback or frozen-dataclass mutation cannot diverge request
  metadata or bypass endpoint allowlisting.
- Credential lookup remains one value only: explicit
  `DashScopeSettings.api_key`, then `DASHSCOPE_API_KEY`, then `ConfigError`.
  Coding Plan `sk-sp-` keys are rejected
  because they cannot authorize this adapter. The key is redacted everywhere.
- The OpenAI-compatible request reads each validated snapshot and sends a
  MIME-correct Base64 data URL. A local filesystem path is never put in the
  remote JSON. Each complete data URL is at most `10,000,000` UTF-8 bytes, and
  the fully serialized JSON request remains capped at 20 MiB (`20,971,520`
  bytes), both before dispatch.
- DashScope-specific preflight requires both dimensions to be greater than 10
  pixels, an aspect ratio no greater than 200:1, a longest side no greater than
  `7,680`, and the selected model's pixel/image-count constraints. For the
  pinned model with high-resolution image processing enabled, the initial
  per-image provider ceiling is `16,777,216` pixels; the library's 10-image
  group limit remains stricter than the model's published maximum. The adapter
  decodes and encodes the same bounded byte buffer and rechecks the final
  group's `64,000,000` aggregate-pixel cap from those bytes.
- The non-streaming request preserves image order, appends the board prompt last,
  fixes `temperature=0` and `max_completion_tokens=16,384`, and uses
  `chat.completions.with_raw_response.create`. A response succeeds only when the
  partial-response header is absent or `false`, the response model exactly
  matches the request, exactly one choice has index 0, role `assistant`, no
  refusal, `finish_reason="stop"`, and nonempty text after facade validation.
- Construct the synchronous OpenAI client with `max_retries=0`. Cancellation is
  checked before preflight, between image preflights, and immediately before
  dispatch, but a synchronous in-flight HTTP call is not interruptible. The
  first adapter adds no hidden retry, model switch, key rotation, or paid-provider
  fallback.
- Initial quality runs fix `enable_thinking=false` and
  `vl_high_resolution_images=true`. These values are evidence-dependent, not a
  permanent quality promise: changing either one invalidates the affected live
  evidence. Any output truncation signal, including `finish_reason="length"`, is
  `PROVIDER_RESPONSE_INVALID`; truncated Markdown is never successful output.
- Error classification distinguishes retryable throttle
  (`PROVIDER_RATE_LIMITED`), timeout (`PROVIDER_TIMEOUT`), network
  (`PROVIDER_NETWORK`), and service-unavailable (`PROVIDER_UNAVAILABLE`) failures
  from nonretryable authentication, quota/billing, invalid configuration/source,
  and malformed-response failures. Provider quota/billing codes are evaluated
  before a generic HTTP status so permanent account limits are not mislabeled as
  retryable throttling or authentication failures. Documented provider timeout
  codes take precedence over generic 5xx mapping. Unsupported model text is not
  echoed in errors. If request processing and client close both fail, the first
  typed error remains primary with only
  `provider_client_cleanup_failed=true` attached.
- Successful result metadata records `provider`, `model`,
  `prompt_version="board.v6"`, `profile`, `image_count`, `provider_region`,
  `review_passes`, `provider_call_count`, `enable_thinking`, and
  `vl_high_resolution_images`. It never records the API
  key or request body.
- The historical adapter-only implementation checkpoint is commit `a6a8b18`.
  Its final offline gate passed `283` tests, `compileall`, and
  `git diff --check`. A clean wheel was
  `50,970` bytes with SHA-256
  `5502B5ED58D9D049F3640F3AF9AF5C4A8732426C14EA630D01125BD2556245AE`,
  `53` entries, no native/bytecode payload, and no base runtime requirement. Its
  isolated no-deps target was `233,115` bytes. Fresh CPython 3.10.20 and 3.14.3
  imports both left `PIL`, `pypdfium2`, `openai`, and `httpx` unloaded.
- A fresh `ocrllm[image]` empty-target install was `15,907,554` bytes and passed
  a generated-PNG recognition call through the injected-provider path with
  Pillow 12.3.0. A separate fresh `ocrllm[image,dashscope]` empty-target install
  was `40,727,895` bytes, below the 64 MiB gate. Its offline adapter probe used
  Pillow 12.3.0, OpenAI 2.45.0, and HTTPX 0.28.1, constructed the real client
  with `max_retries=0`, and sent no HTTP request.
- The current offline quality checkpoint is commit `e328253`. It commits the
  licensed five-class corpus, deterministic generators, provenance records,
  exact per-language/token, critical-slot, formula, table, and ordered-anchor
  scorers, plus the integrated live-scoring gate. That entrypoint authenticates
  the supplied manifest against a freshly strict-loaded byte-frozen manifest
  before scoring and fails closed when a scoring channel is not applicable.
- The current versioned manifest is exactly `35,400` bytes with SHA-256
  `43c548fdfda1d114b6851def2ce05284cc213bd3478e1e0eea9faa6242a27966`.
  The committed corpus has 20 artifacts, including 5 images, totaling
  `17,914,515` bytes and leaving `8,299,885` bytes of headroom below the 25 MiB
  limit.
- Runner checkpoint `fb23d1e` is committed at full commit
  `fb23d1e40d4594ed1da8e244945ae7ccb9568efd`. Its offline fake/evidence tests
  pass; at that checkpoint the complete pinned suite passed `546` tests, the
  four generated images remained byte-identical, and `compileall` passed.
  Direct no-network
  preflight verified the strict manifest and artifacts, exact repository import
  origins, the closed public signature
  `(region, base_url, evidence_path, confirm_paid_calls, repository_root)`, and a
  clean Git identity covering 98 tracked relevant files at that exact commit.
  No provider/API call was made.
- The runner freezes exactly 13 zero-retry invocations: one clean-slide smoke,
  then six manifest dispatches in run A and the same six independently
  dispatched in run B. V6 explicitly performs two same-model provider calls per
  recognition, so its paid-call confirmation is 26 while the dispatch order
  remains 13. The live entrypoint closes over real dependencies and
  cannot accept test injections. The private simulated path records its injected
  dependencies and can pass only `simulated_plan_passed`, never
  `phase1_gate_passed`.
- At startup the runner establishes exact import origins, strict manifest and
  artifact validity, code/Git identity, and the environment credential. Before
  and after each call it rechecks the applicable manifest, input, code/Git, and
  credential invariants; final postflight repeats the full identity checks. It
  atomically checkpoints the active attempt before each call and the raw
  Markdown, hashes, metadata, elapsed time, and complete scorer metrics
  afterward. Both SDK and runner retry counts are zero; a provider or identity
  failure aborts without another call.
- Evidence writes flush and `fsync` the temporary file, publish the first
  checkpoint with an exclusive hard link, and update it with normal atomic
  `os.replace`. The writer does not explicitly `fsync` the containing directory,
  so it does not promise persistence across sudden power loss beyond normal
  filesystem link/replace guarantees.
- Boundary checkpoint `5aaa854` (full commit
  `5aaa8545a8b73277fa728861be5510cb0a073d84`) adds exact one-below, at, and
  one-above cases for the per-source byte, decoded-pixel, group-count,
  aggregate-source-byte, and aggregate-pixel caps. The rejecting
  per-source/pixel/count/aggregate integration cases all prove zero provider
  calls; aggregate-source rejection additionally precedes temporary-directory
  access. The complete pinned suite passes `568` tests, generated fixture
  bytes remain identical, and `compileall` passes without a provider/API call.
- Pushed packaging hotfix `3414f47` fixed a filename-ignore defect without
  weakening secret protection. The legitimate module/function formerly named
  `resolve_dashscope_api_key.py` / `resolve_dashscope_api_key` matched the
  existing `*_api_key*` secret-ignore pattern; the hotfix renamed them to
  `resolve_dashscope_credential.py` / `resolve_dashscope_credential` and updated
  imports, documentation, and tests. A clean Git-archive build from full commit
  `3414f47e5b44a6d5fe2023012ebf2cf361f96a61` produced a `50,094`-byte wheel.
  Its isolated no-deps install imported `Config` and the resolver and passed an
  explicit test-key round-trip. No provider network call was made.
- The clean package proof for `5aaa854` uses a Git archive, not the working
  directory. It produced a `51,281`-byte wheel with SHA-256
  `23e0068b4525a437052254d8929f0d7ab7706efd5ff48447d04572c796909d93`, 52
  entries, zero base runtime requirements, and no native or bytecode payload.
  Its isolated no-deps target has 103 files totaling `233,665` bytes. Plain
  import leaves Pillow, PDFium, OpenAI, and HTTPX unloaded, and the explicit
  test-key credential resolver passes. Thirty measured processes after two
  discarded warm-ups pass the import budgets: Python 3.10.20 wall
  median/p95/max `51.9831/75.8686/77.3612` ms and CPU
  `46.875/78.125/78.125` ms; Python 3.13.5 wall
  `50.79575/61.3618/62.4312` ms and CPU `46.875/62.5/62.5` ms.
- The separate clean optional profiles for `5aaa854` also pass. Image uses
  Pillow 12.3.0, adds `15,904,714` bytes, preserves lazy import, and completes
  a generated-PNG recognition call through the injected-provider path. Image +
  DashScope uses Pillow 12.3.0, OpenAI 2.45.0, and HTTPX 0.28.1, adds
  `40,677,554` bytes, preserves lazy base import, and constructs and closes the
  real zero-retry client without HTTP. Both remain below their 25 MiB and 64 MiB
  ceilings. No external provider/API HTTP request was made. Decision-only
  result-recording edits do not change wheel inputs; the decision-time profile
  rerun remains required after live evidence or any later
  packaged-input/dependency change.
- A secret-safe local configuration audit found that
  `HKCU:\Software\OCRLLM\QCR\ui` stores a full HTTPS `base_url` whose API key is
  an exact match for the current `DASHSCOPE_API_KEY` under an ordinal string
  comparison that never prints either secret. The endpoint uses host
  `dashscope.aliyuncs.com`, exact path `/compatible-mode/v1`, and no query. That
  registry key stores no region/location value, and no DashScope-related region
  variable was found in the checked Process/User/Machine scopes. This recovers
  the key's configured endpoint. On 2026-07-11 the user explicitly confirmed
  that Aliyun API workflows always use Beijing, authorizing canonical region
  `cn-beijing` with that stored endpoint for the fixed Phase 1 live gate.
- Account-specific billing/reliability guidance is recorded separately in
  `docs/provider_cost_and_reliability_policy.md`. Qwen image calls are billed
  independently; FileTrans ASR is covered by the user's token package for later
  large audio tests; Google is free but less stable; and Codex Mini 5.4 is
  inexpensive and stable but not free. None of those later workflows becomes
  active during Phase 1.
- `docs/phase1_implementation_record.md` records every pushed checkpoint, the
  parallel agent/audit contributions, the atomic evidence-writer guarantees and
  power-loss caveat, current verification, and the exact live resume point.
- The user-supplied screenshots currently present under `docs/` are local,
  supplemental, and non-redistributable. They may help manual development, but
  they remain untracked and cannot enter pass/fail evidence. They are not part
  of the committed licensed corpus.

The current offline checkpoint verification entrypoints are:

```powershell
uv run --no-project --isolated --with 'Pillow==12.3.0' `
  --with 'pytest>=8,<10' --with 'openai>=2.30,<3' `
  --python 'D:\Anaconda\envs\OCRLLM\python.exe' `
  python -m pytest -q -p no:cacheprovider
uv run --no-project --isolated --with 'Pillow==12.3.0' `
  --python 'D:\Anaconda\envs\OCRLLM\python.exe' `
  python -m tests.quality.generators.generate_phase1_fixtures --check
& 'D:\Anaconda\envs\OCRLLM\python.exe' -m compileall -q src tests
```

The exact clean archive/build/install/import sequence for `3414f47` is recorded
under `Verification Commands` in `docs/ocrllm_library_go_no_go.md`.

Primary references: [Model Studio visual understanding and model
status](https://www.alibabacloud.com/help/en/model-studio/vision-model), [image
input and Chat Completions request
fields](https://www.alibabacloud.com/help/en/model-studio/qwen-api-via-openai-chat-completions),
[region and workspace base
URLs](https://www.alibabacloud.com/help/en/model-studio/base-url), and the
[OpenAI Python retry
configuration](https://github.com/openai/openai-python#retries).

## What Is Suspended

`Architecture.md` contains a Rust/PyO3 v3 rewrite plan. That plan is currently
suspended. It is not the implementation path for the next work item.

Rust can come back later only after:

- The Python import contract works.
- At least one real downstream project imports `ocrllm`.
- The module boundary to rewrite is stable.
- Tests can compare behavior against the Python implementation.

HarmonyOS/ArkTS is also deferred. Do not add a native bridge, ArkTS client, or
compatibility claim without a new explicit decision after the active library
and its distribution contracts are stable.

## What Was Moved

The old app package moved from repo root to:

```text
legacy_app/OCRLLM/
```

The old root launcher aliases were removed to avoid confusing the migrated repo
layout with the pre-migration app layout:

```text
start.bat
ocrllmstart.bat
legacy_app/start.bat
```

The preserved historical GUI launcher is:

```text
legacy_app/launch_gui.bat
```

That launcher runs `python -m OCRLLM.main` from `legacy_app/`, not
`python main.py`, because `main.py` lives at `legacy_app/OCRLLM/main.py`.

The old tests/docs/scripts moved to:

```text
legacy_app/tests/
legacy_app/docs/
legacy_app/README.md
legacy_app/requirements.txt
legacy_app/environment.yml
```

## What To Do Next

Completed phase: **Phase 2A -- image library completion**. Phase 2 is GO at
`2db456a77f3aa9d7bbf8f69f89c1f8dfb640e8cf` and its clean Git-archive proof
passes. Local OCR, shared execution policy, adapter-owned DashScope/model
configuration, provider error disposition, credential scheduling, and image
resume are GO. No later phase is active; Phase 3 has not started.

Phase 2A recovery rules:

1. New callers use `python -m ocrllm.worker` and the frozen
   `ocrllm.v1alpha1` JSONL contract.
2. Printed, projected, and handwritten content remain one `board` workflow; do
   not add a handwriting route to address test or prompt quality gaps.
3. Preserve the Phase 2 live evidence and Node cancellation fixtures.
4. Keep the worker development-only with an explicitly configured Python
   executable. Do not claim packaged Electron compatibility before Phase 6.
5. Preserve the completed local-OCR and shared execution-policy checkpoints;
   implement provider transport/model configuration next, then provider error
   taxonomies/credential pools and image resume as separate gates. Do
   not start Phase 3 PDFium, Phase 4 audio/FileTrans, or another deferred
   capability.

The active decision and exact local-OCR gates are in
`docs/image_library_completion_decision_2026-07-12.md`.

Phase 2A checkpoint 1 implements local OCR through `recognize()` with explicit
`image_mode="ocr"`, immutable confidence settings, a lazy maintained RapidOCR
adapter, four typed error categories, ordered multi-image Markdown, zero-call
metadata, and the optional `ocr` extra. The 870-test base suite, fresh real
engine test, two authorized screenshot probes, clean committed wheel, and fresh
331,832,087-byte OCR-extra install pass. `image.ocr.rapidocr` is available. See
`docs/local_ocr_implementation_checkpoint_2026-07-12.md`.

Formal local-OCR graduation commit `2b87d34` also passes its clean archive,
installed capability, base dependency/import, and timing proof.

Phase 2A checkpoint 2 adds public immutable `RecognitionExecutionPolicy`,
pre-upload configurable image limits, bounded ordered `recognize_batch()`
parallelism, and one monotonic start gate covering every provider call in a
direct operation or batch. Parallel failure aborts work that has not reached
the provider. Pushed commits `12c221b` and `40df1a9` pass the 895-test pinned
suite, fixture identity, static checks, and a clean 117,093-byte wheel/import
budget. See `docs/phase2a_recognition_execution_policy_2026-07-12.md`.

Phase 2A checkpoint 3 removes the pre-1.0 string/duplicate provider shape.
`DashScopeSettings` now selects and owns the current OpenAI-compatible adapter
plus optional secret credential; `VisionModelSettings` owns model identity and
a stricter image capability. Effective model/group limits fail before upload,
while the worker converts its unchanged wire model string internally. Pushed
decision `fb3ef8f` and implementation `3dd1ba3` pass 912 tests plus one optional
skip, fixture identity, static/lazy checks, and clean base plus
`image,dashscope` profiles. See
`docs/provider_workflow_configuration_checkpoint_2026-07-12.md`.

Phase 2A checkpoint 4 adds five missing stable provider failures for permission,
account suspension, concurrency, invalid request, and content blocking plus
immutable pool-facing `ProviderErrorDisposition`. DashScope now maps documented
code/type/status precedence and account-shared rate/concurrency domains without
echoing raw messages. Injected providers and the unchanged worker error envelope
accept the taxonomy. Pushed decision `c33f64e` and implementation `54e2e72`
pass 960 tests plus one optional skip, fixture/static/lazy gates, and a clean
122,440-byte wheel/installed mapping proof. See
`docs/provider_error_disposition_checkpoint_2026-07-12.md`.

Phase 2A checkpoint 5 adds a region-bound, concurrency-safe DashScope
credential scheduler without introducing retry. It fairly balances later
independent primary/scout requests, enforces per-key caps and bounded
cancellation-aware waits, and applies stable credential/model/account/provider
health state without exposing secrets. Pushed decision `0cd2f56`, implementation
`d4d444c`, and packaging repair `a84bfb2` pass 975 tests plus one optional skip,
fixture identity, static/lazy checks, and a clean 130,497-byte installed-wheel
pool probe. The first archive build exposed and preserved the ignored-source
defect before the repair. See
`docs/dashscope_credential_pool_checkpoint_2026-07-12.md`.

Phase 2A checkpoint 6 implements strict versioned image resume for exact
built-in DashScope and local OCR without retrying partial calls. Ordered source
bytes and output-affecting settings bind one completed processor output; keys,
pool state, and runtime objects are excluded. State-only and matching
state-plus-output crash windows reuse with zero recognition calls, while
corrupt/stale/edited work fails closed. Decision `bb75039` and implementation
`f7465db` pass 987 tests plus one optional skip, fixture/static/lazy gates, and
a clean 143,072-byte installed-wheel interruption/resume probe. See
`docs/image_resume_checkpoint_2026-07-12.md`.

Checkpoint 6 implements the production image-command adapter without adding a
second recognition workflow. Absolute file URIs become platform paths, the
exact credential-free Beijing v17 config is constructed, and the existing
`recognize()` facade handles the complete ordered image group exactly once.
Printed and handwritten content remain one `board` capability. The module
entrypoint, Node harness, and live smoke remain required. See
`docs/phase2_production_image_job_2026-07-12.md`.

Checkpoint 7 implements `python -m ocrllm.worker` as a thin launcher over the
production control loop, isolated manager, and unified image callable. Offline
subprocess tests prove no-key capabilities and a real spawned-child typed source
failure with JSON-only stdout and empty stderr. The Node harness and live smoke
remain required. See
`docs/phase2_production_worker_entrypoint_2026-07-12.md`.

Checkpoint 8 implements the shell-free Node harness and an independent strict
validator for every worker event shape. Unicode path round-trip and real
child-plus-grandchild cancellation pass; the complete cancellation scenario is
about 3.32 seconds. Only the opt-in Beijing live production-worker smoke remains
before the Phase 2 GO decision. See
`docs/phase2_node_worker_harness_2026-07-12.md`.

Checkpoint 9 implements and runs the opt-in live Node scenario against the
production module. Two typed provider timeouts are preserved; the successful
independent run completed the exact pinned Beijing four-call `board` workflow,
validated four stdout events, and stored only non-private hashes/counts. A clean
proof of full commit `60ce473eb4f177f7c382dc5db7cc6bbca6ea63b0` passes.
All Phase 2 gates are satisfied and `worker.jsonl.v1alpha1` is available. See
`docs/phase2_live_worker_result_2026-07-12.md`.

Checkpoint 1 completes the input side of item 1: all three v1alpha1 commands
have immutable DTOs, strict parsing, explicit defaults, canonical serialization,
and one frozen JSONL fixture. It passes 33 focused tests and the 745-test full
suite. The next checkpoint is the six event shapes and the explicit wire-result
adapter; do not start the process control loop on an unfrozen output contract.
See `docs/phase2_worker_command_contract_2026-07-11.md`.

Checkpoint 2 completes the six event DTOs and frozen event JSONL fixture. It
keeps protocol/request identity only in the event envelope and uses an explicit
adapter rather than mutating the direct Phase 1 result. Command plus event tests
pass 51 cases; the full suite passes 763. The next checkpoint owns bounded
stdin reading and protocol-only flushed stdout writing, not the process control
loop yet. See `docs/phase2_worker_event_contract_2026-07-11.md`.

Checkpoint 3 adds bounded binary stdin reading, protocol-only compact UTF-8
stdout writing, partial-write completion, flush proof, oversized-record
draining, and typed error-event construction with canonical request-ID recovery.
The command/event/I/O suite passes 66 tests and the full suite passes 778. The
next checkpoint is a deterministic no-job capability/error/EOF control loop;
do not combine its first proof with recognition process concurrency. See
`docs/phase2_worker_jsonl_io_2026-07-11.md`.

Checkpoint 4 implements the public 19-name atomic capability registry and a
control loop over a nonblocking injected `WorkerJobManager`. It passes real OS
pipe tests, invalid-record recovery, concurrent partial-write serialization,
stable internal-error mapping, and exact-config status tests. The focused suite
passes 100 and the full suite passes 794. Next implement the isolated process
manager and five-second descendant cancellation; do not expose a production
entrypoint before that boundary passes. See
`docs/phase2_capability_control_loop_2026-07-12.md`.

Checkpoint 5 implements the spawned one-job manager and five-second process-tree
cancellation. The first Windows attempt proved immutable mapping proxies cannot
cross spawn by pickle; the accepted design serializes/reparses canonical JSON at
both command and event boundaries. Normal, typed failure, internal failure,
mismatched ID, missing terminal, busy, wrong cancel, matching cancel, and EOF
tree cleanup tests pass. The full suite passes 807. Next add only the production
image-job adapter; keep the entrypoint and live smoke separate. See
`docs/phase2_isolated_job_manager_2026-07-12.md`.

Preserve every earlier Phase 1 evidence file unchanged. The passing decision is
bound to v17 evidence SHA-256
`6f0454d634dbe76f68f29c07a4c0ced4a047c080e46bb75dda2cb84ffca3a96b`
and the clean package proof at `0278b66`.

The historical v2 correction explicitly
requires labeled standalone formulas, Unicode inline relations, and exact
handwritten spelling/capitalization. Its separate fail-closed normalizer accepts
only the observed content-preserving presentation forms and standalone
horizontal rules. The full suite passes `568` tests. Diagnostic scoring of the
preserved v1 raw outputs makes the smoke and every non-handwriting dispatch pass
while both handwriting dispatches retain the same seven failure codes. This is
not new live evidence and does not authorize another billed run.

Clean package proof for full commit
`9dc4e7a8d9f113c1ea001105335829494086d003` passes. The wheel is 52,602 bytes
with SHA-256
`8ce3a51f2367bdfa3255f8ca23f1b95fd46176e728edec3ef4369da1c626f385`;
its isolated no-deps target is 237,251 bytes with zero base requirements and no
native payload. Python 3.10 and 3.13 pass the 30-sample wall/CPU import budgets.
Image and Image + DashScope add 15,918,041 and 40,837,813 bytes respectively;
the generated-PNG recognition and offline Beijing client-construction probes
pass without provider HTTP. See `docs/phase1_implementation_record.md` for the
recorded disk-contention and wrong-origin measurement incidents.

A zero-network v2 preflight passed at full commit
`2d5a693e53ba3395aa08c530c4dbdea693295097`. It verified 99 clean relevant
files, 20 artifacts, the v2 manifest/prompt/evidence contracts, the fixed
13-call plan, credential presence, Beijing settings, and an absent new evidence
path. Repeat it from the exact future paid-run commit; this result neither makes
a provider call nor authorizes one.

The first fixed v2 live gate then completed at full commit
`94d5187ff8718f2683f67e4c5f75e95c3a9d9070`: 13 calls, zero retries, zero
provider failures, two complete runs, and zero passing runs. The evidence is
`evidence/phase1/phase1-quality-v2-2026-07-11-cn-beijing.json`, 78,235 bytes,
SHA-256
`03275cf5922a46dd59fc75e4ab6dc6499e3aeea973190f1d3a6f48b0c556df0b`.
Projected slide, formula board, and calibration table passed twice. Printed and
ordered requests exposed undeclared U+2A7E relation typography; handwriting
exposed undeclared line-leading U+2192 diagram connectors. Phase 1 remains
NO-GO. The next correction must be versioned and keep wrong content and inline
arrows fail-closed.

That correction is now implemented as `board.v3` /
`labeled-latex-restricted.v3`. It maps only U+2A7E/U+2A7D relation typography
and line-leading U+2192 diagram connectors. Inline arrows, wrong relations, and
wrong values remain failures. The full suite passes `574` tests, fixture bytes
are identical, and compilation passes. Diagnostic scoring makes all preserved
v2 non-handwriting dispatches pass while handwriting retains the same seven
quality failures. A clean v3 package proof and meaningful handwriting-quality
improvement are still required before another full gate.

Post-v2 exploratory work is recorded in
`docs/phase1_exploratory_robustness_2026-07-11.md`. Thirteen requests tested
v3 handwriting, deterministic crops, four private dense optimization
screenshots, thinking mode, Qwen3.5-OCR chat/Responses, and
`qwen-vl-ocr-latest`. The private screenshots all completed; no tested
handwriting path passed. Qwen-VL-OCR returned HTTP 403, and Qwen3.5-OCR's
document-parsing response exposed a temporary signed OSS URL, so neither enters
the allowlist. The handwriting manifest also omits a visible label and requires
a complete source-derived reannotation before another handwriting gate.

The temporary split recommendation is withdrawn. The user required one unified
`board` capability, and the subsequent source audit proved the apparent gap was
mostly fixture error: the source says `Enzymens`, includes
`R-DNA / Replasmid`, has case-ambiguous cursive labels, and contains real faint
micro-labels omitted from precision truth. Crop, legacy-prompt, and high-
resolution controls did not change the disputed readings. Thinking mode did
capture the one genuinely missed second `+`.

`board.v4` now keeps the unified capability, pins thinking mode for the live
contract, separates required recall truth from optional source precision truth,
and version-controls line-leading Unicode/LaTeX diagram connectors. The
37,492-byte manifest SHA-256 is
`b0a38e364ca7e8a2b799548304a219392b5570ab515187ec72d52cd785bfbbb0`.
The isolated full suite passes 583 tests, generated fixture bytes are identical,
and `compileall` passes. Read
`docs/phase1_unified_board_handwriting_debug_2026-07-11.md` for the evidence.
Phase 1 remains NO-GO only until two fresh complete v4 live runs pass.

V4 live attempt 1 is preserved at
`evidence/phase1/phase1-quality-v4-2026-07-11-cn-beijing.json`, 27,245 bytes,
SHA-256
`49e5a3981d13137c5a8ca543b96290bf3b30595ed5cd6d19ca58362c19134015`.
It made one smoke invocation, received retryable DashScope HTTP 500
`internal_server_error`, and aborted with `PROVIDER_UNAVAILABLE` before any full
run. This is transport-failure evidence, not a recognition-quality result. Do
not overwrite or resume it; a later attempt must use a new complete plan and
new evidence path. See
`docs/phase1_live_quality_result_v4_attempt1_2026-07-11.md`.

V4 attempt 2 is preserved separately at
`evidence/phase1/phase1-quality-v4-attempt2-2026-07-11-cn-beijing.json`, 57,929
bytes, SHA-256
`936edd25c72d3d58f0d70fed4621c603ced023eca572901a8cf773d62635cc6e`.
It invoked seven calls. Smoke plus all five single fixtures returned; printed,
projected, formula, and table passed. Handwriting had 29/30 required recall,
33/40 precision, 5/6 critical-token accuracy, and 10/10 critical slots. It
still missed the center `+`; two line-leading ASCII `->` connectors caused four
false unexpected critical tokens. The run-A ordered request then timed out and
the runner aborted before run B. Preserve this partial evidence. The next
offline correction may accept only line-leading ASCII connectors with corruption
tests, but must still solve the genuinely missing `+`. See
`docs/phase1_live_quality_result_v4_attempt2_2026-07-11.md`.

The post-attempt correction is `board.v5` /
`labeled-latex-restricted.v5` / evidence schema v5. It adds a generic internal
region-by-region verification pass that inventories repeated standalone marks,
not a handwriting-specific prompt. It accepts ASCII `->` only as a
line-leading diagram connector; inline `A -> B` and other content remain
visible. Source reinspection adds the second genuine `RG` occurrence and the
visible `OR` label to optional precision truth. The center `+` remains required.

Two targeted built-in-provider calls wrote Markdown through the library's
atomic writer. Both reached 30/30 recall, 6/6 critical tokens, 10/10 critical
slots, and zero unexpected critical tokens. One passed directly; the other was
below English precision only under incomplete v4 optional truth and passes
after the two verified source labels are included. Truncated or guessed sequence
labels remain unmatched. The 37,661-byte v5 manifest SHA-256 is
`d602d38cbaf6433338d371fbe0d42e8dd4fd3be55811ee428f2333127c0f276d`.
The isolated suite passes 588 tests, fixtures are byte-identical, `compileall`
passes, and changed Python files pass Ruff. Commit/push v5, repeat the clean
preflight, then run a new v5 evidence path; Phase 1 remains NO-GO meanwhile.

The complete v5 gate is preserved at
`evidence/phase1/phase1-quality-v5-2026-07-11-cn-beijing.json`, 95,483 bytes,
SHA-256
`0ceb74a7f05ed2ca5cbcac8eb3eb1c340dfac4bf43ceb84e6883cbe4c40e2343`.
All 13 calls returned, both full runs completed, and run B passed all six
dispatches. Run A failed only handwriting: 30/30 recall, 38/40 precision, 6/6
critical-token accuracy, and 10/10 slots, but one unexpected critical token.
The model hallucinated `111110` from six plasmid hatch strokes. Do not accept
those digits as optional truth. Add a generic hatch/fill/texture exclusion to
the prompt and test it without splitting `board` or weakening the gate. See
`docs/phase1_live_quality_result_v5_2026-07-11.md`.

Post-v5 diagnostics are recorded comprehensively in
`docs/phase1_v6_review_workflow_debug_2026-07-11.md`: 28 provider calls, 27
complete results, and one timeout. Single-pass hatch wording removed the
`111110` hallucination but still missed the center `+` stochastically. Broad and
focused crops were inconsistent; explicit glyph counting did not fix recall;
seeds 1234, 42, 3407, and 20260711 reproducibly missed the same `+`. Those paths
are rejected.

Three readable draft-to-review trials all passed, including one that repaired a
failing draft. JSON-string framing was too opaque and failed twice. The final
line-by-line quoted framing is both injection-resistant and readable; two actual
production `RecognitionPreferences(review_passes=1)` probes passed with 30/30
recall, 6/6 critical tokens, zero unexpected critical tokens, and metadata
reporting two provider calls.

`board.v6` implements that explicit one-model workflow. Review defaults off;
only an exact `RecognitionPreferences(review_passes=1)` enables one review. A
review failure fails the whole request, and only reviewed Markdown can be
returned or atomically written. The manifest is 37,685 bytes with SHA-256
`c058a68b4a17d1ed13c74bd31429269fc4287539afeb23e20c8dfb0be6f50a27`.
The gate remains 13 ordered recognition invocations but precommits 26 provider
calls and requires all 26 to be reported before GO. The isolated suite passes
599 tests; generated fixtures, compilation, Ruff, and diff checks pass. Commit
and push v6, then run a new clean 26-call evidence path.

The complete v6 gate is preserved at
`evidence/phase1/phase1-quality-v6-2026-07-11-cn-beijing.json`, 97,150 bytes,
SHA-256
`bc256bfbdc73f7d5f80806eb95767d4e68f17cb512f76c9e6daaba5278504707`.
All 13 recognition invocations and 26 provider calls returned, both full runs
completed, and run A passed. Handwriting passed in both runs: review fixed the
missing operator without hallucinating hatch digits. Run B failed only the
formula board because review changed source lowercase `s_4` to uppercase `S_4`.
The exact formula gate correctly rejected that one unexpected atom. Do not
accept uppercase as truth. Make v7 review conservative about changing exact
draft identifiers/case, then test handwriting repair and formula preservation.
See `docs/phase1_live_quality_result_v6_2026-07-11.md`.

That v7 wording experiment is rejected. Two handwriting trials still omitted
the center `+`, and two formula trials still changed `s_4` to `S_4`; all four
reviewed results failed after eight successful provider calls. The accepted
v8 design uses the same unified prompt and profile to produce two independent
drafts, then performs one pixel-grounded consensus review. The targeted
consensus result passed handwriting at 30/30 required recall and 10/10 slots,
and passed the formula board at 12/12 signatures and 133/133 atoms. One formula
consensus attempt timed out without publishing output; one bounded final-only
recovery reused the two complete drafts and passed.

`RecognitionPreferences(draft_candidates=2, review_passes=1)` explicitly opts
into the three-call workflow; defaults remain one candidate and no review. No
handwriting/formula branching exists. V8 evidence precommits 13 recognition
invocations and 39 provider calls. The 37,712-byte manifest SHA-256 is
`7200d16ea44b365301ce491bd3353433520d6c8ba2cc686debe6562173623e35`;
the isolated suite passes 608 tests. Complete offline preflight, commit/push,
then run a new clean v8 evidence path. See
`docs/phase1_v8_consensus_workflow_debug_2026-07-11.md`.

V8 live attempt 1 is preserved at
`evidence/phase1/phase1-quality-v8-2026-07-11-cn-beijing.json`, 59,675 bytes,
SHA-256
`fd34fb9f3ec7d37674ba7f779f3db743a36b76af81371a27090e8c1b7d75fe94`.
Smoke and five Run A single fixtures completed. Formula passed perfectly, but
handwriting again missed one genuine standalone `+` at 29/30 recall and 5/6
critical-token accuracy. The ordered request then timed out on draft 1 after
120.954 seconds; Run A did not complete and Run B never started. Preserve this
attempt without retry. Consensus solved destructive formula mutation but not
the stochastic small-mark omission. See
`docs/phase1_live_quality_result_v8_attempt1_2026-07-11.md`.

Post-v8 experiments reject v9 generative disagreement review, Qwen3.7 Max, and
heterogeneous generative rewriting. V9 could repair one handwriting trial but
mutated byte-identical perfect formula drafts and could not recover a plus
omitted by both inputs. Qwen3.7 Max missed the same plus. The exact legacy
`qwen-vl-max` model consistently captured both plus signs but was weaker on
source spelling.

`board.v10` uses one Qwen3.7 symbol-audited transcript plus two explicit
Qwen-VL Max visual-sign scouts, then restores only standalone sign events agreed
by both scouts at matching text anchors. Scout prose never enters output, and
there is no generative final rewrite. Two handwriting trials pass after zero
and one deterministic restoration respectively; the formula draft stays
byte-identical and perfect. Defaults remain one call; the workflow requires
explicit `standalone_sign_scout_model="qwen-vl-max"`.

The v10 manifest is 37,853 bytes with SHA-256
`15a7018084cd1d53c82acbf260bb19095ccb29664cc357beaaaefd9044b8f971`.
The isolated suite passes 628 tests. Commit/push, repeat clean preflight, then
run the fixed 13-recognition/39-call Beijing gate with 180-second per-call
timeouts. See `docs/phase1_v10_sign_scout_workflow_debug_2026-07-11.md`.

The complete v10 gate is preserved at
`evidence/phase1/phase1-quality-v10-2026-07-11-cn-beijing.json`, 98,351 bytes,
SHA-256
`8c86c7117efa6ad7e999bad3180e861981a27598788cfaaeb526472ae65b9c54`.
All 13 recognitions and 39 calls returned; both runs completed and Run B passed.
Run A handwriting still missed one plus with zero restoration. Run A formula
was provider-complete but the scorer rejected safe `\text{}` presentation.
Post-run inspection also found the passing ordered request restored a Markdown
`---` separator, not source content. V11 must exclude thematic breaks, use a
2-of-3 scout quorum, and narrowly normalize safe single-symbol `\text{}` forms.
See `docs/phase1_live_quality_result_v10_2026-07-11.md`.

`board.v11` addresses the three verified v10 defects. It uses three Qwen-VL Max
scouts with a two-of-three anchored sign quorum, excludes repeated Markdown
hyphen/equal thematic breaks from sign evidence, and adds formula dialect v6.
The dialect unwraps only exact single-ASCII-letter `\text{X}` groups inside
valid labeled formulas; broader forms remain rejected. Preserved v10 Run A
formula output re-scores perfectly at 12/12 signatures and 133/133 atoms.

The v11 plan is 13 recognitions and 52 fixed calls with 180-second timeouts.
The 37,853-byte manifest SHA-256 is
`3b5c5392b1e10ed40261ac08dc5fbf692f0b451c6c13c4c71a44b710f28ec86b`;
647 isolated tests pass. See
`docs/phase1_v11_three_scout_and_formula_dialect_2026-07-11.md`.

V11 live evidence completed all 13 recognitions and 52 calls with no transport
failure. Both runs failed only handwriting. Run A had complete recall but
invented diagram captions reduced precision to 38/58; Run B both missed one plus
and invented diagram-description sections. No sign was restored in either run.
Every non-handwriting dispatch passed, including formula dialect v6. Preserve
the 104,026-byte evidence SHA-256
`44b74fdb0ba57662a6c49193c6c203b147b88a723bed8698b983fb9f1a59465f`.
Do not add more full-transcript scouts. Test literal-caption exclusion and a
strict sign-only scout ledger next. See
`docs/phase1_live_quality_result_v11_2026-07-11.md`.

Targeted v12 probes change the failed request shape rather than adding more
calls. Two independent Qwen3.7 primaries with literal-caption exclusion both
pass handwriting without invented descriptions. Three independent Qwen-VL Max
scouts return the same strict `SIGN | BEFORE | AFTER` ledger containing both
plus and both minus occurrences with literal neighbors.

`board.v12` strictly parses that ledger; extra prose, headings, fences,
thematic breaks, unsupported signs, overlong neighbors, or malformed records
fail the request. Only parsed sign/anchor events reach the two-of-three merger.
The 37,853-byte manifest SHA-256 is
`e2813e006d4de8db3b4b2fe3ef99a1e658935d98290e2a1735d75d4e80a164f6`;
661 isolated tests pass. The complete gate remains 13 recognitions and 52 calls.
See `docs/phase1_v12_literal_primary_and_sign_ledger_2026-07-11.md`.

The frozen v12 live gate from pushed commit `05adc64` aborted at its first
bilingual printed-slide smoke recognition. Four provider calls were attempted,
but the strict sign merger rejected the scout responses before scoring because
the protocol had no valid whole-ledger empty result. No full run began and no
selective retry was made. Preserve the 29,606-byte atomic evidence SHA-256
`ea16775eec1aea7af79681e1f90b76ca075864e9b8e9b1b00dc1c90d125282ea`.
This is a shared board-workflow protocol defect; do not split handwriting into
a separate path. Define an exact empty sign ledger and retain fail-closed
handling for all other malformed scout output.

V13 keeps the primary authoritative and makes the auxiliary channel safely
optional. Exact `NONE` is a valid empty ledger; a malformed ledger abstains as a
whole and increments result metadata; quorum still needs two distinct valid
scouts. The merger now blocks any insertion where the primary already has a
supported standalone sign between the same anchors, even when the scout sign
differs. Targeted Beijing probes returned `NONE` three-of-three on the printed
slide and recovered the missing handwriting plus three-of-three. The
37,853-byte manifest SHA-256 is
`890f67941bc2783bc81f91ab42b1290fb4ad1df4c722cb2f458e762dd9ad1522`.
The focused suite passes 96 tests and the exact isolated repository suite passes
667 tests.
See `docs/phase1_v13_auxiliary_scout_abstention_2026-07-11.md`.

The v13 live gate completed all 13 recognitions and 52 calls from pushed commit
`74d155e`; both full runs failed without a terminal provider error. Handwriting
had full recall and critical accuracy twice but received one extra plus twice.
Run B projected content duplicated source `≥` already represented as LaTeX
`\ge`. Both tables were broken by five sign lines inserted between GFM rows.
Preserve the 98,101-byte evidence SHA-256
`b10b88eeeba94f637165ddf32b95eb3ff3e3e02d4ccdd254ad9fbfe39bec67f1`.
V14 must include anchor lines in sign-conflict checks, recognize equivalent
sign spellings, and protect table blocks. Do not split handwriting routing.

V14 implements those three local rules. Conflict windows now include both
anchor lines; Unicode, ASCII, and supported LaTeX greater/less-equal forms count
as the same represented sign; and insertions touching outer-pipe GFM table rows
are blocked. The code never inspects fixture class or handwriting status. The
37,853-byte manifest SHA-256 is
`dae74f4da207d01e311f5756a204e557ca6e6982073024d2e48b672315febb07`;
37 direct structural tests, 153 wider tests, and all 685 isolated repository
tests pass. See `docs/phase1_v14_structural_sign_guard_2026-07-11.md`.

The v14 gate completed all 13 recognitions and 52 calls from pushed commit
`ff25461`; Run B passed completely and Run A failed only handwriting. The Run A
primary missed one plus, two scouts abstained, and one valid scout could not
form quorum. Both tables, both projected slides, both formulas, and both ordered
dispatches pass; every v13 structural regression is gone. Preserve the
103,074-byte evidence SHA-256
`48c4fb2f78d0bff36aae6e022074d173e85fbf8cdfa792a81bc04bef01fe067a`.
Do not reduce quorum to one or split handwriting routing. Measure a larger fixed
independent scout pool under the same strict parser and structural guards.

Post-v14 probes reject merely scaling Qwen-VL Max: seven handwriting calls
produce inconsistent and sometimes broad false-plus ledgers. Thinking-enabled
Qwen3.7 finds both genuine pluses in eight of eight calls across two prompt
versions; non-thinking finds the delicate plus only once in five calls. V15
therefore uses three independent thinking-enabled pinned Qwen3.7 scouts with
the same two-of-three quorum and all v14 guards. A defensive line extractor
retains only exact allowlisted records and discards unsupported punctuation.
The 37,864-byte manifest SHA-256 is
`9c5fe09635142c457c464d52f2c4bba8e78964f61e3c06cb4b786d8bf6bf3c11`;
159 focused and all 696 isolated tests pass. See
`docs/phase1_v15_thinking_scout_and_allowlist_extraction_2026-07-11.md`.

The v15 gate completed all 13 recognitions and 52 calls from pushed commit
`248c627` in about 67 minutes 27 seconds. Both full runs completed with zero
scout abstentions. Run A failed only when an auxiliary diagrammatic `←` was
inserted into otherwise complete handwriting. Run B handwriting passed with
one safe restoration, but formula failed only because source-equivalent
one-letter `\mathrm{X}` is outside dialect v6. Preserve the 99,223-byte
evidence SHA-256
`65dad6a47206562c526f643bab600d87e0f68987f443cc6757e7f07ec9fff95b`.
V16 must exclude directional arrows from auxiliary restoration and narrowly
unwrap one-letter `\mathrm{X}` in labeled formulas. Do not split handwriting.

V16 implements exactly those changes. Auxiliary extraction now permits only
`+`, `-`, `=`, `<=`, `>=`, `≤`, and `≥`; directional arrows can still appear
in the primary but can never be inserted by scouts. Formula dialect v7 unwraps
only one ASCII letter in `\mathrm{X}` inside exact labeled math wrappers, after
all v6 normalization; broader Roman groups remain rejected. The 37,864-byte
manifest SHA-256 is
`12b5234850d885926ea01161c31643ae2050728bd377c86e44784377d00abde9`;
99 focused and all 706 isolated tests pass. See
`docs/phase1_v16_arrow_exclusion_and_formula_dialect_2026-07-11.md`.

The v16 gate completed all 13 recognitions and 52 calls from pushed commit
`73da992` in about 66 minutes 17 seconds. Run B passed completely; Run A failed
only handwriting at 29/30 recall and 5/6 critical signs. All three scout
responses were usable but did not form a second-plus quorum, so zero signs were
restored. Arrow exclusion and formula dialect v7 both pass live. Preserve the
103,882-byte evidence SHA-256
`4395c84ed0efa8d3567bdf5f14a35a8dad8d3412a52fdb5a9e8359ca355ea139`.
Do not split handwriting or lower quorum. Compare a generic primary-conditioned
omission ledger with a larger fixed scout pool before raising the call plan.

The primary-conditioned design wins the bounded comparison without increasing
the pool. Three independent Qwen3.7 calls on the exact failed v16 primary each
return only `+ | foreign gene | I:V`, with no existing-plus or arrow report.
V17 binds the quoted inert primary to all three omission scouts, records the
template identity plus exact per-dispatch prompt hashes, and treats quorum rows
as missing occurrences rather than a full inventory. Same-location checks,
relation equivalence, tables, arrow exclusion, extraction, and two-of-three
quorum remain. The 37,864-byte manifest SHA-256 is
`4ec1440f531e88492eb06795a29308256a5718c2748625ce2ad9b1230807e393`;
89 focused and all 712 isolated tests pass. See
`docs/phase1_v17_conditioned_omission_scout_2026-07-11.md`.

The bounded JSONL worker, direct local OCR, and shared recognition execution
policy, adapter-owned DashScope/model configuration, and provider error
disposition are now GO. Credential scheduling is the next Phase 2A task; image
resume follows as a separate slice. PDF, audio, video,
HTTP service, HarmonyOS, Rust, Office, social, GPU, and offline-model work remain
outside the current slice.

## Do Not Do This

- Do not import `legacy_app.OCRLLM` from new downstream projects.
- Do not copy whole legacy files into `src/ocrllm`.
- Do not expose legacy processors as public API.
- Do not freeze a `1.0` API until real downstream usage proves it.
- Do not make the Rust plan active again without a measured reason.
- Do not add PyMuPDF or `fitz` to the active package; Phase 3 uses PDFium through
  `pypdfium2`.
- Do not start a later phase before the current GO gate passes.
- Do not begin or claim HarmonyOS/ArkTS compatibility.
- Do not claim support from code existence, mocks, installed dependencies, or
  historical logs alone.
- Do not make a paid provider call outside the versioned confirmed call plan, or
  before the intended Git/import/manifest/artifact preflight is clean and the
  new evidence path is proven absent.
- Do not pass fake callables or clocks into the public live runner or relabel
  simulated evidence as live. The public signature intentionally exposes no
  dependency-injection parameters.
- Do not retry one failed paid dispatch. Preserve the failed complete-run
  evidence and start a separately dispatched full run only under a new explicit
  decision.
- Do not claim the evidence checkpoint survives every sudden power loss. File
  data is flushed and `fsync`ed before atomic link/replace, but the containing
  directory is not explicitly `fsync`ed.

## Done Criteria For This Migration Step

- `START_HERE.md` gives an immediate visual split between active, legacy, and
  suspended areas.
- Root `README.md` explains the active path.
- `MIGRATION_STATUS.md` explains what changed and what to do next.
- `src/ocrllm/` is clearly marked as the active importable package.
- `Architecture.md` is clearly marked as suspended future planning.
- `legacy_app/` is clearly marked as old app/reference code.
- New tests prove the active import contract.
- `docs/ocrllm_library_go_no_go.md` is the single authoritative execution
  record and all navigation docs point to it.
- PDFium is the only active PDF decision; PyMuPDF is explicitly legacy-only.
- HarmonyOS/ArkTS is explicitly deferred.
