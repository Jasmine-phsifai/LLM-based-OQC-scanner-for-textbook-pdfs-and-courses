# Plan: Phase 1 Maturation, Then Phase 2 MP3 Audio

Status: **approved current work.** Written 2026-08-18.

Read `docs/ACTIVE_STATE_AND_RULES.md` first. It defines document precedence, the
two policy changes this plan depends on, and the coding rules.

## Relationship To Other Work

```text
Defect repair D1-D7    docs/plan_phase1_defects_and_provider_split.md, Stage 1.
                       IN PROGRESS under a separate agent. Do not duplicate.
Phase 1 maturation     This document, Stage M. Current work.
Phase 2 mp3 audio      This document, Stage A. Not started. Plan only.
Provider modality split  docs/plan_phase1_defects_and_provider_split.md, Stage 2.
                       Prerequisite for Stage A.
```

Stage M and the defect repair touch adjacent code. The boundary is:

| Concern | Owner |
|---|---|
| Refusal detection (D1) | Defect agent |
| Wall-clock bound on a provider call (D2) | Defect agent |
| Preserving completed results when a batch raises (D3) | Defect agent |
| Resume accepting injected providers (D4) | Defect agent |
| Model discovery replacing the fixed allowlist | Stage M |
| Incremental flowed output written as work completes | Stage M |
| Automatic disclosed model-switching recovery | Stage M |
| Freezing `worker/` and `contracts/` | Stage M |

Stage M assumes D1-D4 have landed. If they have not, rebase onto them rather
than reimplementing them.

## Why Phase 1 Is Reopened

Phase 1 reached GO as a feasibility trial: prove one narrow vertical slice can
carry a stable public contract. It did. But several of its constraints exist
only because it was a trial, and they are unacceptable in a product:

- **A hardcoded three-model allowlist.** The account serves 239 models. A model
  becomes unusable because a constant in this repository is stale, not because
  the provider stopped serving it.
- **All-or-nothing output.** A recognition either completes and writes, or
  produces nothing. Long runs discard paid work on interruption.
- **One attempt, no recovery.** A free-tier provider exhausts quota per model.
  The library returns an error and every caller reimplements the same loop.

None of these are design errors. They were correct for a trial and are wrong for
a product. Removing them is the maturation work.

## Stage M — Phase 1 Maturation

### M1. Model discovery replaces the fixed allowlist

Retire the `SUPPORTED_DASHSCOPE_MODELS` frozenset as a gate on caller choice.
See "Policy Change: Model Discovery Replaces The Fixed Allowlist" in
`docs/ACTIVE_STATE_AND_RULES.md` for the reasoning and the constraint that
survives.

Required behavior:

- Fetch the provider's served-model catalog from its own API. For DashScope
  this is `GET {base_url}/models`, verified working against the live account and
  returning 239 entries.
- Validate a caller's model against the live catalog. Unknown means "the
  provider does not serve this", not "this repository has not heard of it".
- Cache the catalog for the process lifetime. Discovery must not add a network
  round trip to every recognition.
- Discovery must be lazy and must never run during plain `import ocrllm`.
- Never make the catalog fetch a hard dependency of recognition. If discovery
  fails, fall back to attempting the caller's explicit model and let the
  provider reject it. A catalog outage must not block a valid request.
- Keep the evidence baseline pinned and named in result metadata. A model
  outside the baseline is usable and must be reported as unproven.

`get_capabilities()` must not claim proven quality for a discovered model.

### M2. Flowed output and true resume

This is the highest-value item in Stage M. Today a recognition writes its result
once, at the end. Interrupt it and the paid work is gone.

Required behavior:

- Results are written incrementally as each unit completes, in caller order,
  not accumulated until the end.
- A run interrupted at any point leaves the completed units on disk in a form
  the next run can reuse.
- Resume is available two ways:
  - **Manual:** the caller passes `resume=True` and the run continues from
    whatever is already on disk.
  - **Automatic:** an interrupted or partially failed run preserves completed
    units without the caller having asked in advance. Preservation is not
    opt-in. Discarding paid work is never the default.
- Order is preserved regardless of completion order.
- Writes stay atomic. A crash mid-write must not leave a corrupt file. Legacy
  already learned this the hard way; see the atomic-write entries in
  `legacy_app/AGENTS.md`.

**Behavior oracle:** `legacy_app/OCRLLM/core/incremental_writer.py`, class
`IncrementalMDWriter`. Port the behavior statement, never the file. The parts
that matter:

- Slot-indexed writes (`write_slot`) so parallel completion still yields ordered
  output.
- `seed_slots()` to restore already-completed slots before resuming, with
  `truncate=not bool(restored_slots)` so a resume does not blank the file.
- Contiguous incremental flush: only append the run of slots that is complete
  from the front, keeping the file valid at every instant.
- A dirty flag so that if an incremental append fails, finalize rewrites in
  full rather than leaving a half-written file.

**Known legacy defect not to inherit:** the legacy PDF path seeds slots on
resume; the legacy video path did not, which made phase-4 resume
phase-granular and discarded batch work on a late crash. Both are recorded in
`legacy_app/AGENTS.md`. Seed slots on every path.

### M3. Disclosed automatic recovery with model switching

See "Policy Change: Disclosed Automatic Recovery" in
`docs/ACTIVE_STATE_AND_RULES.md`. All four conditions there are binding: opt-in,
disclosed, disposition-gated, bounded.

Required behavior:

- The caller supplies an ordered candidate model list. Their primary model is
  tried first and is never tried twice.
- On a disposition meaning "this model cannot serve the request", advance to the
  next candidate. On any other failure, stop and raise.
- The account's live free-tier behavior to handle: DashScope returns HTTP 403
  with provider code `AllocationQuota.FreeTierOnly` and message "Free quota
  exhausted", already mapped correctly to `QuotaExhausted` with disposition
  `stop` / scope `account`. Note the scope is `account`, not `model` — the
  mapping is right for a single-model call but the recovery layer must decide
  per candidate, because a different model on the same account may still have
  free quota. Verify this against the live account before assuming either way,
  and record the finding.
- When every candidate is exhausted, raise a distinct terminating error naming
  the last model tried.
- Every attempt is recorded in an ordered ledger exposed in result metadata and
  in error details.

**Behavior oracle:** `legacy_app/OCRLLM/core/llm_client.py`,
`_vision_fallback_chain`, `_call_with_free_tier_fallback`,
`_notify_free_tier_switch`. Legacy already orders the primary first, slides only
on free-tier exhaustion, notifies on every switch, and raises an
all-exhausted error. The user-configured queue is stored as
`vision_model_queue` in the legacy GUI settings.

Recovery must compose with M2: a switch mid-run must not discard units already
recognized by the previous model. Record which model produced each unit.

### M4. Freeze `worker/` and `contracts/`

Closed to change. No new fields, commands, events, protocol version bumps, or
tests. If a Stage M change makes a frozen contract inaccurate, record the
divergence in `docs/ACTIVE_STATE_AND_RULES.md` and move on.

Known divergences to expect: `image_recognition_request.py` pins
`provider: Literal["dashscope"]` and `profile: Literal["board"]`, and its
`model` field assumes a single fixed model rather than a candidate list.

### M5. Cut process overhead

The documentation rules in `docs/ACTIVE_STATE_AND_RULES.md` apply. Concretely:

- No per-slice decision file plus checkpoint file. One entry in
  `ACTIVE_STATE_AND_RULES.md`, plus one dated record only if a paid gate ran.
- No new `phase*` document.
- Group trivially small pure helpers with their only caller rather than adding
  more single-predicate files.

### Stage M exit gate

- Full suite green, with failing-first tests for M1, M2, M3.
- Import weight unchanged: under 150 ms, no heavy module in `sys.modules` after
  plain `import ocrllm`.
- A recognition interrupted mid-run leaves completed units on disk, and a
  resumed run does not re-pay for them. Proven by a test that kills work
  mid-flight, not by inspection.
- A caller can select a model the repository has never heard of, and it works.
- A caller-configured candidate chain survives a simulated per-model quota
  exhaustion and reports every attempt.
- `worker/` and `contracts/` unchanged in the diff.
- One live smoke, budget approved in advance, proving the DashScope path still
  works end to end.

## Stage A — Phase 2: MP3-Only Audio Recognizer

**Not started. Plan only. Do not begin until Stage M exits.**

Phase 2's original framing was an Electron JSONL worker. That is superseded:
the worker is frozen and Phase 2 is redefined as the first audio capability.

### Scope

One media type, one container: **mp3 in, Markdown transcript out.** Nothing
else.

Explicitly out of scope: wav, m4a, flac, video, ffmpeg-based conversion,
speaker diarization, real-time streaming, and hotword feedback loops. Each of
those is a later gate. The value of this stage is proving the audio contract on
the narrowest possible surface, exactly as Phase 1 proved the image contract.

### Prerequisites

- Stage M complete. Audio runs are long; flowed output and resume are not
  optional for them.
- The vision/audio provider split from
  `docs/plan_phase1_defects_and_provider_split.md` Stage 2. Audio must be able
  to use a different provider from vision. The maintainer already runs it this
  way: `audio_model = qwen3-asr-flash-filetrans` on DashScope while
  `vision_model = gpt-5.4-mini` elsewhere.

### Provider note

DashScope is the right provider for audio. The maintainer considers it expensive
for per-frame image work and appropriate for audio. The account serves
`qwen3-asr-flash-*` and `fun-asr-flash-*` families; verify against the live
catalog at implementation time rather than trusting this list.

Long audio uses a submit/poll/download task flow rather than a single synchronous
call. `docs/ocrllm_library_go_no_go.md` already reserves
`providers/dashscope/submit_filetrans.py`, `poll_filetrans.py`, and
`download_filetrans_result.py` for this. Legacy behavior and its failure history
are recorded in `docs/legacy_filetrans_codex_debug_record.md`.

### Behavior requirements

- Validate the mp3 before any provider call, the way images are validated
  today. A zero-byte or truncated file fails before money is spent.
- Duration probe with an explicit dependency error when the probe tool is
  absent. Never guess duration.
- Short and long paths split on a documented duration threshold. The long path
  is resumable by provider task ID; an interrupted poll must not resubmit and
  re-pay.
- Transcript segments are written incrementally under M2. A long transcription
  that dies at 90% keeps 90%.
- A failed or refused transcription is never presented as a transcript. This is
  D1's rule applied to audio, and legacy shipped exactly this bug.
- `NoSpeechDetected` already exists in the public error set and must be used
  rather than returning an empty success.

### Stage A exit gate

- Full suite green with offline fake-provider tests covering validation,
  routing, segment ordering, resume, and every error path.
- `import ocrllm` weight unchanged; audio dependencies lazy behind an extra.
- One real mp3 transcribed end to end, with resume proven by interrupting a
  long run and continuing it without re-paying.
- Capability reported per modality: audio available, video still unavailable.

## Rules For Whoever Executes This

- Follow `docs/ACTIVE_STATE_AND_RULES.md`. Update it in place as items close.
- Write the failing test before the fix.
- Read credentials from `HKCU\Software\OCRLLM\QCR\ui`. Never hardcode or print a
  key. Never run a paid gate without an explicit budget from the maintainer.
- `legacy_app/` is the behavior oracle. Port behavior statements and fixtures;
  never copy a legacy file.
- Keep the working-diary rule in root `AGENTS.md`. Anything observed and not
  fixed still gets written down.
