# Plan: Phase 1 Defect Repair And Vision/Audio Provider Split

Status: **Stage 1 closed; Stage 2 not started.** Updated 2026-08-19.

> Current work for everyone else is
> `docs/plan_phase1_maturation_and_phase2_audio.md`. Do not duplicate Stage 1
> here; rebase onto it. Stage 2 of this document remains the prerequisite for
> the Phase 2 audio work described in that plan.

Read `docs/ACTIVE_STATE_AND_RULES.md` first. It defines document precedence, the
defect register referenced here, and the coding rules this plan must follow.

## Scope

Two stages, in order. Stage 1 is not optional and does not run in parallel with
Stage 2.

```text
Stage 1   Repair D1-D4 in shipped surface.        CLOSED 2026-08-18.
Stage 2   Split provider configuration by modality (vision / audio).
Stage 3   Phase 2 continuation.                   Not in this plan.
```

Phase 2 work resumes only after Stage 2 lands, because the Phase 2 wire contract
must be revised by whichever slice introduces the modality split. See
"Contract impact" below.

## Background A Future Agent Needs

### Why Stage 1 comes first

The library reached its Phase 1 GO through a quality gate that used
`validate_provider_markdown` as its only false-success guard. That guard cannot
distinguish a refusal from a transcription (D1). Every quality conclusion drawn
before D1 is fixed carries that uncertainty. Repairing it is therefore not
maintenance; it is restoring the meaning of the existing evidence.

D2 and D3 are unbounded-hang and paid-work-loss defects on the primary
integration path. Both have already occurred in `legacy_app` in a different
form. `legacy_app/AGENTS.md` records the originals.

### Why the provider split is the right next capability

This is **not** a new idea being introduced. The legacy application already
binds modality to provider independently, and the maintainer runs it that way in
production. Current stored configuration:

| Setting | Value |
|---|---|
| `vision_model` | `gpt-5.4-mini` |
| `audio_model` | `qwen3-asr-flash-filetrans` |
| `google_vision_model` | `gemini-2.5-flash` |
| `google_audio_model` | `gemini-3.1-pro-preview` |

Vision and audio run on **different providers** simultaneously. This is exactly
the "proven user-visible behavior" the migration matrix in
`docs/ocrllm_library_go_no_go.md` instructs the library to preserve.

The active `Config` **cannot express it.** It has a single `provider` slot plus
a single `vision_model`. Any audio slice built on the current shape would either
force audio onto the vision provider or bolt on a parallel path. The split must
land before audio, not after.

Cost background, from the maintainer: DashScope is the right choice for audio
and expensive for per-frame image work; Google has a free tier with refreshing
window limits; Codex offers large allowances on small models. The library does
not encode these preferences — it must simply make them expressible.

### What is deliberate and must not be "fixed"

A previous review misread these as defects. They are documented decisions:

- **One provider adapter in Phase 1.** Google and Codex are recorded in the
  migration matrix as `Future optional adapters after a real gate is approved`.

Two items formerly listed here were **reversed on 2026-08-18**. The fixed model
allowlist is retired in favour of live catalog discovery, and automatic
model-switching recovery is permitted under four binding conditions. See the two
"Policy Change" sections in `docs/ACTIVE_STATE_AND_RULES.md` before acting on
any older statement about either.

A relevant measurement: running the `board.v17` prompt against `qwen3.5-ocr`
produced 16 completion tokens and no usable output, while the pinned model
produced a full transcription from the same prompt and image. Prompts are
coupled to model class. Adding a model is a prompt-contract change, not a list
edit.

## Stage 1 — Defect Repair (historical execution record; closed)

### S1.1 Refusal detection (D1)

Add a refusal check to the shared validation path so it protects every provider,
present and future.

- New file `providers/looks_like_refusal.py`, single responsibility.
- Port the behavior statement from `legacy_app/OCRLLM/core/output_quality.py`,
  not the file. Legacy is the behavior oracle, not the source.
- Trigger conditions must be conservative. A refusal is short, lacks recognized
  structure, and matches known refusal shapes in Chinese and English. A long
  transcription that happens to contain the word "sorry" is not a refusal.
- On detection raise `ProviderError` with a distinct code
  (`PROVIDER_REFUSED_RECOGNITION`) so callers can separate it from a malformed
  response. Register its disposition in `provider_error_disposition.py`.
- Wire it into `providers/validate_provider_markdown.py` so both the injected
  and built-in paths are covered.

Tests must include: genuine short transcriptions that must **not** trigger
(false-positive protection is the hard part), Chinese and English refusals,
mixed refusal-plus-partial-content, and a refusal reaching the quality scorer.

**Re-run the Phase 1 offline quality scorer after this lands.** If any committed
corpus expectation changes, that is a finding to record, not a threshold to
adjust.

### S1.2 Caller-visible timeout (D2)

Enforce `Config.timeout_seconds` as a wall clock around the whole provider
interaction, not only inside the DashScope client.

- The synchronous injected-provider call cannot be interrupted in-process.
  Do not pretend otherwise. Two acceptable designs; pick one and document why:
  - Run the provider call on a worker thread with a bounded join, raise a typed
    timeout, and mark the abandoned thread in metadata. Honest but leaks a
    thread.
  - Declare `timeout_seconds` adapter-only, rename it, and document that
    injected providers must self-bound.
- The second option is cheaper and more honest; the first is what a caller
  expects from a public field. Choose deliberately and record the choice in
  `docs/ACTIVE_STATE_AND_RULES.md`.
- Whichever is chosen, the current silent no-op must not survive.

### S1.3 Batch results that survive partial failure (D3)

`recognize_batch` must stop destroying paid work.

- Keep ordering. Keep the bounded worker pool. Keep fail-fast as an option.
- Add a per-item outcome so a caller can retrieve successes alongside failures.
  Prefer an explicit result union over exception-swallowing.
- Default behavior change is acceptable here and should be taken: silently
  losing paid results is worse than a signature change on a 0.1.0 library.
- Cancellation semantics must stay correct: when the batch aborts, in-flight
  work is still cancelled and the start gate still aborts.

Tests: failure at first, middle, and last item; concurrent and serial paths;
verification that successes retain their `output_path` when `output_dir` is set.

### S1.4 Resume that matches the batch (D4)

- Allow resume for injected providers, or state in code and docs precisely why
  it cannot be allowed. The current `ConfigError` has no recorded rationale.
- Extend checkpointing so a batch resumes at item granularity. Per-request
  caching alone does not address D3.
- Reuse the existing atomic write and versioned job-state helpers. Do not invent
  a second checkpoint format.

### S1.5 Housekeeping

- D5: pin the environment. Either install `rapidocr>=3.9,<4` into
  `D:\Anaconda\envs\OCRLLM` or make `load_rapidocr` state the distribution
  mismatch explicitly. A capability that cannot run on the development machine
  must not report `available` without qualification.
- D6: fix the teardown in `legacy_app/tests/qsettings_test_isolation.py` and
  remove the orphaned `HKCU\Software\OCRLLMTests-*` keys.
- D7: correct `source_type` / `media_type` drift in prose.

### Stage 1 exit gate (passed)

- Full suite green, with new failing-first tests for D1-D4.
- Import weight unchanged: under 150 ms, no heavy module in `sys.modules`.
- Offline Phase 1 quality scorer re-run and its result recorded.
- No paid live call required for Stage 1. Do not spend budget here.

## Stage 2 — Vision/Audio Provider Split

### Target shape

Replace the single provider slot with one explicit binding per modality. Audio
is **declared but not implemented** in this stage; the slice delivers the shape
and the validation, not audio recognition.

```python
Config(
    vision=ModalityBinding(provider=DashScopeSettings(...), model=VisionModelSettings(...)),
    audio=ModalityBinding(provider=DashScopeSettings(...), model=AudioModelSettings(...)),
)
```

Design constraints:

- Each binding pairs a provider with a model for that modality only. A vision
  model name is never accepted in an audio binding.
- Bindings are independent. Configuring vision must not require configuring
  audio, and the two may use different providers and different credentials.
- `image_mode="ocr"` (local OCR) remains a vision binding with no provider.
- Immutability, exact-type validation, and secret redaction rules apply
  unchanged to every new settings type.
- `get_capabilities()` must report per-modality status so a caller can discover
  that vision is available while audio is declared-but-unavailable.

### Migration of the existing surface

`Config.provider` and `Config.vision_model` are public. Two options:

- **Preferred:** accept both shapes for one release. Old fields map onto the
  vision binding; supplying both old and new raises `ConfigError`. Remove the
  old fields in the following version.
- **Acceptable:** break at 0.2.0 with a clear error message naming the
  replacement, given there is no external consumer yet.

Confirm with the maintainer which applies before writing code. Do not guess.

### Attempting audio is out of scope

Do not implement transcription, FileTrans submission, polling, or media probing
in this stage. Those have their own gate. This stage ends when a caller can
*express* an audio binding and receive a clear "declared, not available"
capability report.

### Contract impact — read before touching `worker/`

`contracts/image_recognition_request.py` pins `provider: Literal["dashscope"]`
and `profile: Literal["board"]`. The worker protocol therefore cannot carry the
modality split.

Do not pre-emptively rewrite the protocol. Per
`docs/ACTIVE_STATE_AND_RULES.md`, `contracts/` and `worker/` are frozen until a
consumer exists. When Phase 2 resumes with a real consumer, revising
`ocrllm.v1alpha1` to `v1alpha2` is part of *that* slice, and this plan's Stage 2
is the reason the revision is needed. Record the dependency; do not act on it
early.

### Stage 2 exit gate

- Full suite green.
- Import weight unchanged.
- A caller can construct independent vision and audio bindings with different
  providers, matching the stored legacy configuration shown above.
- `get_capabilities()` distinguishes available vision from declared audio.
- One live vision smoke through the new shape, budget approved in advance,
  proving the split did not disturb the working DashScope path.

## Rules For Whoever Executes This

- Follow the coding and documentation rules in
  `docs/ACTIVE_STATE_AND_RULES.md`. Update that file in place as items close;
  do not create a decision file and a checkpoint file per stage.
- Write the failing test before the fix. A defect closed without a
  previously-failing test is not closed.
- Read credentials from `HKCU\Software\OCRLLM\QCR\ui`. Never hardcode or print
  a key. Never run a paid gate without an explicit budget.
- `legacy_app/` is the behavior oracle. Port the behavior statement and its
  fixture; never copy a legacy file.
- Keep the working-diary rule in root `AGENTS.md`. Anything observed and not
  fixed still gets written down.
