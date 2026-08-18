# OCRLLM

Read this first if you are returning to the project after losing context:
`START_HERE.md`.

Then read `MIGRATION_STATUS.md` for the migration history and next steps.
Read `docs/ocrllm_library_go_no_go.md` before implementing any new library
feature; it is the authoritative execution decision.

OCRLLM is an importable Python library under active staged development. Other
projects import it as `ocrllm`. The previous application code was moved into
`legacy_app/` and should be treated as a reference implementation, not as the
dependency surface for new projects.

## Active Direction

The active package is `src/ocrllm`.

Phase 0 contract honesty, Phase 1 real board/image, and Phase 2 versioned JSONL
worker and Phase 2A image-library completion are GO. Local OCR, shared
recognition execution policy, adapter-owned DashScope/model configuration,
provider error disposition, credential scheduling, and image resume are GO.
No later phase is active; Phase 3 PDFium work has not started.

The current verified contract:

- Valid `.png`, `.jpg`, and `.jpeg` files are decoded before provider dispatch.
- The synchronous injected provider receives request-scoped validated snapshots
  isolated from later caller-path changes, not the caller's source paths.
- Provider failures and invalid output become typed, redacted public errors.
- Permission, suspension, concurrency, quota, invalid-request, content-block,
  and transient failures have distinct stable codes plus immutable disposition
  evidence; no automatic retry occurs.
- Results use canonical `source_type="image"` and `profile="board"`.
- File output is optional. `output_dir=None` means in-memory results only.
- Requested Markdown output uses deterministic collision handling and atomic
  publication.
- Pillow is installed only through `ocrllm[image]` and is imported lazily.
- The built-in DashScope adapter is installed only through
  `ocrllm[dashscope]`; plain `import ocrllm` imports neither `openai` nor
  transitive `httpx`.
- `Config.execution` bounds per-request image count, independent batch
  concurrency, and monotonic provider-call starts. `recognize_batch()` remains
  fail-fast and returns one `BatchItemOutcome` per source in caller order, each
  carrying either a result or a typed error, so completed paid work is never
  discarded.

Phase 1 now contains one lazy DashScope vision adapter with offline boundary
tests. It requires immutable `DashScopeSettings` with an explicit region and
OpenAI-compatible endpoint, accepts only `qwen3.7-plus` or the default pinned
`qwen3.7-plus-2026-05-26`, constructs `OpenAI(max_retries=0)`, and sends ordered
Base64 data URLs rather than local paths.

Offline checkpoint `e328253` committed the licensed five-class corpus,
deterministic generators, exact scorers, and integrated manifest-authenticated
live-scoring gate. The current versioned `board.v6` manifest is `37,685` bytes
with SHA-256
`c058a68b4a17d1ed13c74bd31429269fc4287539afeb23e20c8dfb0be6f50a27`.
Its 20 artifacts include 5 images and total `17,914,515` bytes, leaving
`8,299,885` bytes under the 25 MiB corpus limit. The pinned full suite passed
`599` tests; regenerated fixtures were byte-identical and `compileall` passed.
The boundary suite now hits exact one-below, at, and one-above values for every
per-source byte, decoded-pixel, group-count, aggregate-source-byte, and
aggregate-pixel cap; every rejecting integration case proves zero provider
calls.

Runner checkpoint `fb23d1e` is committed. Its offline fake/evidence tests and a
direct live-preflight check pass without a provider/API call. The public live
entrypoint closes over real dependencies and exposes no injection parameters;
the private fake path labels its output `simulated` and cannot set the live gate
to passed. The frozen zero-retry plan is exactly one clean-slide smoke, six
dispatches in run A, and six independently dispatched entries in run B.

The first fixed Beijing gate completed all 13 zero-retry calls on 2026-07-11.
Both full runs completed, but neither passed; Phase 1 remains NO-GO. There were
no provider request failures. The live record separates a real handwriting
quality miss from a deterministic mismatch between reasonable Qwen
Markdown/LaTeX presentation variants and the frozen v1 scorer grammar. The
evidence remains unchanged. The source-corrected unified `board.v6` contract
shows that six handwriting failures were annotation defects and leaves only a
genuinely missed second `+` in the preserved non-thinking output. Its generic
region-verification prompt plus one explicit same-model review pass produced
five passing reviewed probes, including one repaired draft. The v6 gate has 13
recognition invocations and 26 provider calls. See
`docs/phase1_v6_review_workflow_debug_2026-07-11.md`. The local user screenshots
under `docs/` remain untracked, supplemental, and non-redistributable; they are
not part of pass/fail evidence.

V8 later proved that generative consensus preserves formula case only
stochastically and still misses the plus. The current offline contract is
`board.v10`: one Qwen3.7 text transcript plus two explicit Qwen-VL Max
standalone-sign scouts and a deterministic, prose-isolating quorum merge. Two
handwriting trials and the formula regression pass; the 628-test suite passes.
V10 completed both runs and one passed, then exposed insufficient two-scout
quorum, a safe formula-dialect gap, and a Markdown-separator false restoration.
V11 uses a two-of-three scout quorum, excludes thematic breaks, and narrowly
normalizes safe single-letter `\text{X}` formula forms. Its 647-test suite
passes; fresh complete v11 evidence is pending, so Phase 1 remains NO-GO. See
`docs/phase1_v11_three_scout_and_formula_dialect_2026-07-11.md`.

V12 replaces full-transcript scouts with strict sign-only ledgers and forbids
model-created diagram captions in the primary. Two targeted primaries and all
three independent handwriting ledgers pass their acceptance checks; 661
offline tests pass. The complete gate aborted at the first no-sign smoke image
because the protocol did not define a valid empty ledger. This is a shared
workflow defect, not a handwriting split. Phase 1 remains NO-GO. See
`docs/phase1_v12_literal_primary_and_sign_ledger_2026-07-11.md`.

V13 keeps that unified profile and makes invalid auxiliary scout output a
counted abstention. Exact `NONE` handles no-sign images, two valid scouts still
form quorum, and an existing primary sign blocks a conflicting insertion at the
same anchors. Targeted printed-slide and handwriting probes pass; complete v13
offline verification passes 667 tests; the complete live result is recorded
below. See
`docs/phase1_v13_auxiliary_scout_abstention_2026-07-11.md`.

The complete v13 live gate returned all 52 calls but exposed three local merger
defects: anchor-line sign conflicts, Unicode/LaTeX sign equivalence, and unsafe
insertion inside tables. Handwriting itself reached complete recall and
critical accuracy in both runs. Phase 1 remains NO-GO; see
`docs/phase1_live_quality_result_v13_2026-07-11.md`.

V14 fixes those merger rules without changing providers or routing: anchor-line
signs block conflicts, equivalent Unicode/ASCII/LaTeX relations count as
already represented, and GFM table rows are protected from insertion. All 685
offline tests pass; complete live evidence is pending. See
`docs/phase1_v14_structural_sign_guard_2026-07-11.md`.

The complete v14 gate returned all 52 calls. One full run passed; the other
failed only because two scout abstentions left no quorum for one missing
handwriting plus. Both tables and every other structural regression now pass.
Phase 1 remains NO-GO; see
`docs/phase1_live_quality_result_v14_2026-07-11.md`.

V15 keeps the same unified profile and 52-call shape but uses three independent
thinking-enabled pinned Qwen3.7 sign scouts. Targeted probes recover both
handwriting pluses in eight of eight thinking calls; a defensive extractor
retains only exact allowlisted rows before two-of-three quorum and all v14
guards. All 696 offline tests pass; live evidence is pending. See
`docs/phase1_v15_thinking_scout_and_allowlist_extraction_2026-07-11.md`.

The complete v15 gate returned all 52 calls with zero scout abstentions. One
run failed only a diagram arrow restored into handwriting; the other failed
only source-equivalent one-letter `\mathrm{X}` outside the restricted formula
dialect. Phase 1 remains NO-GO; see
`docs/phase1_live_quality_result_v15_2026-07-11.md`.

V16 prevents auxiliary restoration of ambiguous directional arrows and adds a
strict formula dialect that accepts only one-letter `\mathrm{X}` inside exact
labeled formulas. The unified profile, provider count, truth, and quorum remain
unchanged. All 706 offline tests pass; live evidence is pending. See
`docs/phase1_v16_arrow_exclusion_and_formula_dialect_2026-07-11.md`.

The complete v16 gate returned all 52 calls. One full run passed; the other
failed only one missing handwriting plus despite three usable scouts. Arrow
exclusion and formula dialect v7 both pass live. Phase 1 remains NO-GO; see
`docs/phase1_live_quality_result_v16_2026-07-11.md`.

V17 keeps the three-scout, 52-call unified workflow but conditions omission
scouts on the quoted primary transcript. Three targeted calls on the exact
failed v16 result agree only on the missing `foreign gene + I:V` plus. Exact
dynamic prompt hashes are recorded; all prior guards remain. All 712 offline
tests pass. See
`docs/phase1_v17_conditioned_omission_scout_2026-07-11.md`.

The committed v17 Beijing gate completed all 13 recognitions and exactly 52
provider calls with no retry or terminal failure. Both independent six-dispatch
runs passed. Run A needed no restoration; Run B handwriting passed after
exactly one two-of-three omission-scout restoration, while formula, table, and
ordered-image guards remained clean. The 107,246-byte atomic evidence has
SHA-256
`6f0454d634dbe76f68f29c07a4c0ced4a047c080e46bb75dda2cb84ffca3a96b`.
The clean Git-archive gate at `0278b66` then passed 712 tests, built a 67,266-byte
wheel, and passed base, `image`, and Beijing `image,dashscope` profiles. Phase 1
is GO; see `docs/phase1_live_quality_result_v17_2026-07-11.md`.

Phase 2 checkpoint 1 now freezes all three `ocrllm.v1alpha1` input commands as
immutable DTOs with strict JSON, canonical UUID/file-URI, exact-field, option
default, redaction, and canonical-serialization tests. The frozen command
fixture includes Chinese, emoji, spaces, and all command literals. Event DTOs,
the control loop, cancellation, and the Node harness were deliberately outside
that first checkpoint. See
`docs/phase2_worker_command_contract_2026-07-11.md`.

Phase 2 checkpoint 2 freezes all six output event shapes and corrects duplicated
result-envelope identity. An explicit fail-closed adapter preserves the direct
Phase 1 result while producing JSON-safe worker payloads; sensitive warning and
error details are recursively redacted. Worker stdin/stdout, child isolation,
cancellation, and the Node harness remain pending. See
`docs/phase2_worker_event_contract_2026-07-11.md`.

Phase 2 checkpoint 3 adds a strict 1 MiB binary stdin JSONL reader, compact
UTF-8 partial-write-safe/flushed event writer, and typed error-event builder
with canonical request-ID recovery. Full verification passes 778 tests. Process
creation, control, cancellation, and the Node harness remain pending. See
`docs/phase2_worker_jsonl_io_2026-07-11.md`.

Phase 2 checkpoint 4 adds public, zero-network reporting for all 19 atomic
capabilities and a nonblocking injected-manager control loop. Exact pinned
Beijing v17 config is distinguished from merely offline-valid workflows.
In-memory concurrency and a real Python subprocess prove JSON-only output,
fallback errors, and Unicode/long-path round trips. The real recognition child
manager, five-second process-tree cancellation, production entrypoint, Node
harness, and live smoke remain. See
`docs/phase2_capability_control_loop_2026-07-12.md`.

Phase 2 checkpoint 5 adds the real one-job spawned manager. Only canonical JSON
values cross the Windows spawn/pipe boundary; the child reparses commands and
the parent reparses bounded events. Busy, wrong cancel, child failures, terminal
invariants, EOF cleanup, and real child-plus-grandchild cancellation within five
seconds pass. The production image child, module entrypoint, Node harness, and
live smoke remain. See `docs/phase2_isolated_job_manager_2026-07-12.md`.

Phase 2 checkpoint 6 adds the production image-command adapter. It converts
absolute file URIs, builds the exact credential-free Beijing v17 configuration,
and invokes the existing unified `board` facade once for each ordered image
group. No handwriting route, fallback, or retry exists. Typed facade errors
remain owned by the isolated-child wrapper. The module entrypoint, Node harness,
and live smoke remain. See
`docs/phase2_production_image_job_2026-07-12.md`.

Phase 2 checkpoint 7 adds `python -m ocrllm.worker` as a small standard-stream
launcher over the isolated manager and unified image job. Real offline
subprocess tests prove no-key capabilities and spawned-child `SOURCE_NOT_FOUND`
handling; unexpected diagnostics expose only exception types. The Node harness
and live smoke remain. See
`docs/phase2_production_worker_entrypoint_2026-07-12.md`.

Phase 2 checkpoint 8 adds a shell-free standard-library Node harness that
strictly validates every stdout line. Fixture output preserves Chinese, emoji,
spaces, and long paths; a real recognition child plus grandchild is cancelled
and proven gone within the five-second contract. Only the Beijing live worker
smoke remains before the Phase 2 GO decision. See
`docs/phase2_node_worker_harness_2026-07-12.md`.

Phase 2 checkpoint 9 adds the opt-in production-worker live scenario and a
machine-readable result record. Two provider timeouts are preserved rather than
hidden; a final independent Beijing job completed the pinned four-call unified
`board` workflow with all four stdout events validated by Node. The clean
committed-source proof passes and the Phase 2 gate is GO. See
`docs/phase2_live_worker_result_2026-07-12.md`.

Phase 2A checkpoint 1 adds explicit `Config(image_mode="ocr")` routing through
the same direct facade, immutable confidence settings, a lazy maintained
RapidOCR adapter, typed local-OCR errors, deterministic ordered Markdown, and an
`ocr` optional extra. Unit, generated-image, and two authorized screenshot
offline gates and committed clean/fresh-install proof pass. The capability is
available. See
`docs/local_ocr_implementation_checkpoint_2026-07-12.md`.

Provider cost/reliability assumptions are recorded in
`docs/provider_cost_and_reliability_policy.md`. The complete checkpoint,
parallel-review, and atomic-writer history is in
`docs/phase1_implementation_record.md`.

Pushed packaging hotfix `3414f47` renamed `resolve_dashscope_api_key.py` /
`resolve_dashscope_api_key` to `resolve_dashscope_credential.py` /
`resolve_dashscope_credential`. The old legitimate filename matched the
existing `*_api_key*` secret-ignore pattern; the rename fixed that defect
without weakening secret protection. A clean Git-archive build from the hotfix
produced a `50,094`-byte wheel and passed an isolated explicit-key resolver
round-trip without a provider call.

The active library has an in-memory region-bound DashScope credential pool. It
has no automatic retries or model fallback, persistent/cross-process pool
state, resume/checkpoint support, PDF recognition, audio
recognition, or video recognition. Those features must enter through their own
approved phases rather than through the injected-provider scaffold.

Active PDF work will use PDFium through `pypdfium2`. PyMuPDF/`fitz` is
legacy-only and must not enter `src/ocrllm`. HarmonyOS/ArkTS compatibility is
deferred and is not an active claim.

The old Rust/PyO3 rewrite plan in `Architecture.md` is suspended and kept only
as a future reference.

## Current Public API

Install the current image and provider extras together for the built-in adapter:

```bash
pip install "ocrllm[image,dashscope]"
```

The built-in call shape is explicit about its regional endpoint:

```python
from ocrllm import Config, DashScopeSettings, VisionModelSettings, recognize


settings = DashScopeSettings(
    region="cn-beijing",
    base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
    # api_key="...",  # Or set DASHSCOPE_API_KEY.
)
result = recognize(
    "board.jpg",
    config=Config(
        provider=settings,
        vision_model=VisionModelSettings(
            name="qwen3.7-plus-2026-05-26",
        ),
    ),
)
print(result.markdown)
```

Supply the key through `DashScopeSettings.api_key` or `DASHSCOPE_API_KEY`; Coding Plan
`sk-sp-` credentials are not accepted. This account uses Beijing; do not
substitute another region. Only the floating alias `qwen3.7-plus` and the
default pinned snapshot `qwen3.7-plus-2026-05-26` belong to the proven Phase 1
contract.

For multiple independently authorized keys in the same Beijing region, supply
one stateful pool instead of `api_key`. A failed call is never retried with the
next key; only a later independent primary or scout call observes updated pool
state.

```python
from ocrllm import (
    CredentialPoolPolicy,
    DashScopeCredential,
    DashScopeCredentialPool,
)


pool = DashScopeCredentialPool(
    region="cn-beijing",
    credentials=(
        DashScopeCredential(credential_id="primary", api_key="..."),
        DashScopeCredential(credential_id="secondary", api_key="..."),
    ),
    policy=CredentialPoolPolicy(max_in_flight_per_credential=1),
)
settings = DashScopeSettings(
    region="cn-beijing",
    base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
    credential_pool=pool,
)
```

The injected-provider contract remains available to host applications that own
their clients and network policy. The library validates and snapshots the image
before calling the provider; this offline example is contract evidence, not
recognition-quality evidence.

```python
from ocrllm import Config, recognize


class Provider:
    def recognize_images(self, image_paths, *, prompt, config):
        return "# Recognized board\n"


result = recognize("board.jpg", config=Config(provider=Provider()))
print(result.markdown)
print(result.source_type)  # image
print(result.profile)      # board
```

Set `output_dir` to request a Markdown file. Without it, recognition stays
in-memory. Add `resume=True` to preserve a completed built-in DashScope or local
OCR result across an interrupted final publication. Resume state is a sibling
`.ocrllm-state.json` file and is removed after the Markdown is durable. Resume
does not support identity-less injected providers and never retries half of a
provider call.

## Repository Map

```text
START_HERE.md                         One-screen new/old/suspended repo map.
AGENTS.md                             Repo-level boundary instructions.
src/ocrllm/                           Active importable library package.
src/ocrllm/README_ACTIVE_LIBRARY.md   Local active-library boundary.
src/ocrllm/AGENTS.md                  Local active-library agent rules.
tests/                                Active library contract and licensed
                                      Phase 1 quality-gate tests.
legacy_app/                           Old GUI/CLI/FastAPI application.
legacy_app/README_LEGACY.md           Local legacy-app boundary.
legacy_app/AGENTS.md                  Local legacy-app agent rules.
docs/                                 Active migration decisions.
docs/ocrllm_library_go_no_go.md       Authoritative execution decision.
docs/provider_workflow_configuration_checkpoint_2026-07-12.md
                                      Current provider/model API checkpoint.
docs/provider_error_disposition_checkpoint_2026-07-12.md
                                      Provider error policy checkpoint.
docs/dashscope_credential_pool_checkpoint_2026-07-12.md
                                      Credential scheduler checkpoint.
docs/image_resume_checkpoint_2026-07-12.md
                                      Image resume and Phase 2A GO checkpoint.
docs/phase1_live_quality_result_2026-07-11.md
                                      First Beijing live-gate result.
Architecture.md                       Suspended future architecture reference.
output/, temp/, ocrllm_social_e2e/    Runtime artifacts, not source.
```

## Legacy Runtime Notes

The old GUI, Codex video mode, Filetrans audio mode, and Bilibili/social-long
workflow are read-only behavior references under `legacy_app/` for this
migration. Historical runtime incident notes live in:

```text
docs/legacy_bilibili_social_long_debug_record.md
docs/legacy_filetrans_codex_debug_record.md
```

For a separately authorized legacy-maintenance task, use the Bilibili record
first when touching multi-part course downloads, comment/danmaku capture,
`social_long --parts`, social URL input, or resume behavior. It is not an
active-library phase gate.

The 2026-07-06 robustness record reported a clean supervised Bilibili CS231n
course run with the following output. Treat this as historical legacy evidence,
not as a currently revalidated active-library test:

```text
33 part directories
33 downloaded MP4 files
33 *_板书识别.md files
33 *_录音识别.md files
0 FileTrans task sidecars
bilibili_social_context.md with shared comments, resource links, and per-part danmaku
```

For any completed legacy course/video folder, the expected per-part recognition
artifacts are exactly these two Markdown files:

```text
*_板书识别.md
*_录音识别.md
```

Known dirty markers include Codex batch/frame placeholders, `Reading additional
input from stdin`, `[WinError 10061]`, embedded Codex diagnostic dumps, or a
missing board/audio Markdown after the job has completed. These checks belong
to the legacy workflow; they are not part of the public `ocrllm` library API.

The historical Bilibili course command is documented in
`docs/legacy_bilibili_social_long_debug_record.md`. It is reference evidence,
not an active-library verification command:

```powershell
$env:PYTHONPATH='legacy_app'
D:\Anaconda\envs\OCRLLM\python.exe -m OCRLLM.cli social_long <bilibili-url> `
  --parts 1-33 --resume -o output\bilibili_cs231n_full
```

## Rules For New Work

- New projects must import only from `ocrllm`, never from `legacy_app`.
- Do not port a legacy module wholesale. Extract one tested vertical slice at a
  time.
- Do not make GUI, FastAPI, social download, or heavyweight media dependencies
  import on `import ocrllm`.
- Do not make package-relative output directories the default.
- Keep the public API boring and stable before revisiting Rust internals.
- Use PDFium through `pypdfium2` for active PDF work; do not port PyMuPDF.
- Follow the phase gates in `docs/ocrllm_library_go_no_go.md`; code existence,
  mocks, and historical output are not enough to mark a feature supported.
- Do not start HarmonyOS/ArkTS work without a new explicit decision.

## Verification

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

These are the pinned offline checkpoint checks. The clean Git-archive wheel
build, isolated install, outside-repo import, and heavy-module guard are in
`docs/ocrllm_library_go_no_go.md`.
