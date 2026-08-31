# Active Library Boundary

This file adds package-local rules for `src/ocrllm/`. The repository-root
`AGENTS.md` is the top authority and wins on every conflict.

## Current Authority

- Section 0 of `../../docs/plan_provider_entity_batch_refactor.md` is the
  current provider/media migration board.
- `README_ACTIVE_LIBRARY.md` describes the public package surface, but code and
  tests remain the capability truth when prose lags.
- `../../docs/ACTIVE_STATE_AND_RULES.md`,
  `../../docs/ocrllm_library_go_no_go.md`, and old numbered work entries are
  historical evidence, not current instructions.
- Keep chronological evidence in the plan, migration status, and Chinese work
  diary. Do not grow another iteration transcript in this file.

## Package Boundary

- `src/ocrllm/` is the importable library for downstream users. Do not import
  from `legacy_app` or uppercase `OCRLLM`; legacy code is behavior evidence only.
- Do not copy whole legacy modules or expose legacy processor classes without a
  deliberately tested public facade.
- Keep `import ocrllm` dependency-light. Load Pillow, PDFium, FFmpeg helpers,
  provider SDKs, and other optional media dependencies only inside the feature
  that needs them.
- Keep GUI, FastAPI, browser automation, social downloaders, and application
  launch behavior outside this package.
- Keep the package-root facade small, file output optional where the public
  contract allows it, and provider behavior behind explicit adapters or the
  retained injected-provider escape path.
- One file has one responsibility. Public function names and filenames must
  describe the behavior they actually own.

## Current Media Boundary

### Images and audio

- Images use visible exact-tuple planning through `batchify_images()`, then the
  merged image recognition, ordinary resume, or narrow experimental repair API.
- Audio input is currently MP3. `split_audio()` accepts exact `-1`, a positive
  integer-minute interval, or a provider default; recognition, resume, and
  experimental repair remain separate visible calls.
- Image and audio repair only recover current OCRLLM failed-slot markers after
  ordinary state is lost. They do not consume legacy formats, reconstruct saved
  parameters, or create another repair state system.
- Do not hide planning, recognition, resume, repair, output ownership, or
  provider selection inside a new generic media lifecycle.

### Video

- Keep provider-free `inspect_video()`, `extract_video_frames()`, and
  `extract_video_audio()`, plus their public frame/info/error values.
- Extracted video/PDF images remain complete frames/pages. Do not add blackboard
  corner detection, ROI cropping, deskew, or perspective correction.
- The caller composes extracted frames with the merged image APIs and extracted
  audio with the audio APIs, using independent providers and Markdown targets.
- `resume_video()` is only a stateless one-branch router over already planned
  image batches or audio slices.
- The combined video recognizer, journal, outcome, composition, publication,
  and video-owned state family was deleted. Do not recreate it, wrap it for
  compatibility, or add a replacement combined lifecycle.

### PDF and deferred surfaces

- The existing direct PDF facade uses PDFium and the original `Config`/
  injected-provider grouped-image path. It is not the provider-model merged
  image path. Do not add PyMuPDF or `fitz`; the active PDF backend is
  `pypdfium2`.
- Route A is selected. `extract_pdf_pages()` publishes one complete caller-owned
  ordered PNG directory; callers compose it with existing image planning,
  recognition, resume, and repair. Do not add a PDF manifest, page DTO, provider
  parameter, PDF state, automatic cleanup, or a one-call PDF lifecycle.
- Social-media recognition/downloading, PDF text mode, full model-catalog
  mirrors, WAV/M4A widening, shared worker registration, Rust/PyO3, and a
  combined video lifecycle remain deferred. HarmonyOS/ArkTS integration is also
  outside the active library plan. The maintainer must reactivate any of these
  explicitly.

## Provider Boundary

- `ProviderModel` entities are the primary configured path; the shipped
  injected-provider path remains an independent escape hatch.
- Admit only a small set of real-tested presets. Discover live model catalogs at
  runtime instead of hardcoding every vendor model as an asserted entity.
- Capability flags, planning defaults, adapter settings, and retry rules require
  official or real-run evidence. Keep retry maps empty when no same-model
  recovery has proved a finite policy.
- Ordered fallback and fixed nested lanes belong to the explicit merged-media
  owners. Adapters must not silently retry, switch models, rotate keys, or reach
  providers outside the supplied plan.
- Reject incompatible media/provider capability combinations before dispatch.
  Never report empty, control-only, refusal-shaped, or otherwise invalid provider
  output as success.
- Every external operation needs a caller-visible bound. Preserve canonical,
  redacted, honest failure evidence and exact-or-unknown call/token accounting.
- Follow the root provider-test authority for live Google/DashScope use,
  credential privacy, authorized media, proxy checks, and bounded reruns.

## Architecture And Testing

- `contracts/` and `worker/` are frozen. Do not edit or extend them until the
  maintainer authorizes a real consumer.
- Port or repair one vertical slice at a time. Do not add a generic scheduler,
  transaction framework, cross-process lock, compatibility wrapper, provider
  pool, or second batch abstraction without a current proven consumer.
- Preserve source ordering, settled work, output safety, honest partial failure,
  and existing concurrency bounds. For new filesystem-producing features,
  follow the root long-Windows-path evidence rule.
- Root `tests/` prove public behavior, not the source tree. Reuse existing
  feature test files; mock only true system boundaries and do not monkeypatch
  internal `ocrllm` seams.
- Real media/provider proof belongs in a maintained `tools/` scenario plus a
  Markdown verdict. Run tests and scenarios only for the changed subsystem; a
  green offline suite does not replace live provider evidence.

## Work Records

- Keep each heartbeat atomic and update `../../docs/work_diary_zh.md` in Chinese.
- Update `../../MIGRATION_STATUS.md` when the active boundary changes and keep
  section 0 of the current plan synchronized with decisions and evidence.
- Record failures honestly, including evidence-capture failures. Do not turn a
  missing log, timeout, quota event, or transient provider failure into invented
  product behavior.
- Follow the root Git workflow: preserve unrelated files, review the complete
  diff, commit the iteration, and push to `origin`.
