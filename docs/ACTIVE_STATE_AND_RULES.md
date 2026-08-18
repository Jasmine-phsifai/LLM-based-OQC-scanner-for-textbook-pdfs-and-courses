# Active State And Rules

Status: **authoritative and current.** Last verified by live audit 2026-08-18.

This file outranks every other document in this repository. Read it before
`docs/ocrllm_library_go_no_go.md`, before `START_HERE.md`, and before any
`phase*` file.

## Document Precedence

Contradictions between documents are resolved in this order. A lower-ranked
file never overrides a higher-ranked one.

```text
1. docs/ACTIVE_STATE_AND_RULES.md     This file. Current truth and rules.
2. docs/plan_phase1_defects_and_provider_split.md
                                      The approved next slice.
3. docs/ocrllm_library_go_no_go.md    Execution contract, gates, boundaries.
                                      Its dated log sections are history.
4. MIGRATION_STATUS.md / START_HERE.md  Navigation aids.
5. docs/phase*                        Immutable historical records.
                                      Never cite as current state.
```

Every `docs/phase*` file is a frozen record of one past attempt. Several of them
state conclusions that were true only on their own date. Do not read a `phase*`
file to learn what is true now.

## Project Posture Changed

The library was built as a feasibility spike: prove that one narrow vertical
slice (DashScope + image) could carry a stable public contract. That question
is answered. The contract, quality-gate, and error layers work.

**The posture is now a maintained product**, not a probe. This changes three
things:

- Defects in shipped surface outrank new capability. A known false-success path
  is not acceptable because "the phase is complete".
- Structure is justified by an observed failure, not by an anticipated one.
  Anything already built that lacks a consumer is frozen, not extended.
- Documentation is a maintained artifact with a single current-state file, not
  an append-only research log.

## Known Debt In This Repository

Future agents must assume the following and verify before trusting any claim:

- **Documentation lags code.** Several files still describe capabilities as
  absent that shipped, and one normative section still reports a superseded
  NO-GO. Prefer reading code and tests over prose.
- **Structure runs ahead of demand.** `contracts/` and `worker/` are 1,817
  lines (23% of the library) serving a subprocess protocol with no consumer.
  They are correct and tested; they are also not yet load-bearing.
- **Recognition logic is small.** `processors/`, `profiles/`, and `imaging/`
  total 1,059 lines. Most of the library is contract and validation. That ratio
  is acceptable for a library, but it means new capability is cheap and new
  ceremony is expensive. Bias toward capability.

## Verified State, 2026-08-18

Confirmed by execution, not by reading prose. Method noted so it can be redone.

| Property | Result | Method |
|---|---|---|
| Test suite | 987 passed, 1 skipped, 0 failed (87 s) | `python -m pytest -q` |
| Import weight | 78 ms, 114 modules | timed `import ocrllm` |
| Heavy-module isolation | `PIL`, `openai`, `httpx`, `onnxruntime` all absent after plain import | `sys.modules` probe |
| Phase 1 evidence integrity | 107,246 bytes, SHA-256 `6f0454d6…a96b`, exact match to the recorded claim | `Get-FileHash` |
| Pinned model exists | `qwen3.7-plus-2026-05-26` served by the account | live `GET /models` |
| Snapshot isolation | Provider reads original bytes while a concurrent thread overwrites the source | threaded race probe |
| Corrupt-input rejection | zero-byte, truncated, and extension/content mismatch all raise `InvalidSource` before dispatch | live probe |
| Secret redaction | `api_key` absent from `repr`, error message, and error details | live probe |
| Live error mapping | 401, 403 `AllocationQuota.FreeTierOnly`, 404, timeout all mapped to correct type and disposition | live paid probe |

These are load-bearing and must not regress. The error taxonomy and the
snapshot isolation are the two strongest parts of this codebase; build on them.

## Defect Register

Open defects in shipped surface. Severity is impact on a real user, not effort.
Do not close an entry without a test that fails before the fix.

### D1 — Provider refusal text is accepted as success. **High.**

`providers/validate_provider_markdown.py` only asks whether the response
contains a visible character. A model that replies `无法识别图片内容，请重新上传`
or `I'm sorry, I can't help with identifying content in this image` is returned
to the caller as a successful recognition.

This is the exact defect class already diagnosed in production and recorded in
`legacy_app/AGENTS.md` with a `WARNING FOR src/ocrllm` carry-forward note. The
legacy remedy (`core/output_quality.py::looks_like_refusal`) was never ported.

The DashScope adapter does check the OpenAI `message.refusal` **field**. That is
a different thing: production refusals arrive as ordinary `message.content` and
pass every existing check.

Consequence beyond the caller: the Phase 1 quality gate ran through this same
validator, so v17 GO rests on a gate that cannot distinguish a refusal from a
transcription.

### D2 — `Config.timeout_seconds` is not enforced for injected providers. **High.**

`timeout_seconds` is a public field, but it is only threaded into the DashScope
OpenAI client. `recognize()` applies no wall clock. An injected provider that
blocks hangs the caller permanently. Injected providers are the library's only
documented extension point, so this is an unbounded hang on the primary
integration path.

Measured: `timeout_seconds=0.5` against a provider sleeping 3 s returned after
3.05 s.

### D3 — `recognize_batch` discards completed paid work on any failure. **High.**

The current contract is fail-fast: one failure raises and the caller receives no
results for the items that already succeeded and were already paid for.

This is the same defect class already fixed once in `legacy_app`
(phase-granular resume discarding batch work on a late crash), re-emerged one
layer up. Fail-fast is a reasonable default; silently destroying paid results is
not.

### D4 — Image resume does not cover the case that loses money. **Medium.**

`resume=True` is rejected for injected providers (`ConfigError: Image resume
requires exact DashScopeSettings or local OCR mode`), and it checkpoints per
whole request rather than within a batch. It does not address D3.

### D5 — Local OCR is not runnable in the maintained development environment. **Medium.**

`local_ocr/load_rapidocr.py` imports `rapidocr` (the 3.x API).
`D:\Anaconda\envs\OCRLLM` provides `rapidocr-onnxruntime 1.4.4`, which exposes
`rapidocr_onnxruntime`. The capability's GO evidence came from a throwaway
isolated environment with `rapidocr 3.9.1` and exactly one real-engine test.
The feature is green in evidence and non-functional on the development machine.

### D6 — The legacy test suite leaks registry keys. **Low.**

`legacy_app/tests/qsettings_test_isolation.py` has left roughly 58 orphaned
`HKCU\Software\OCRLLMTests-<uuid>` keys. Its teardown path has never executed
successfully, which also means that path is untested.

### D7 — `RecognitionResult` prose drift. **Low.**

Some documents describe a `media_type` attribute. The field is `source_type`.

## Structure Decisions

### Keep and maintain

- `errors.py`, `provider_error_disposition.py`, and the DashScope error mapping.
  Correct, live-verified, and the foundation for every future provider.
- `imaging/snapshot_image_group.py` and the validation chain. Correct and
  race-proof.
- `config.py` immutability and exact-type validation.

### Keep but freeze

`contracts/` and `worker/` stay in the tree. They are tested and they encode a
real decision about process isolation. Do not delete them.

Do not extend them either, until a consumer exists. Note that
`contracts/image_recognition_request.py` hardcodes `provider: Literal["dashscope"]`
and `profile: Literal["board"]`, so the protocol cannot represent the provider
split described in the next-slice plan. When a consumer appears, that contract
is revised as part of the same slice that produces the consumer — not before.

### Reconsider before reuse

The three-scout standalone-sign quorum costs four provider calls per image. In
the v17 evidence it restored exactly one sign across 26 dispatches. Keep the
code; it is careful and correct. Do not treat it as the default workflow for
future providers or media types without re-measuring its yield on that provider.

## Coding Rules

These are additive to the implementation directive in
`docs/ocrllm_library_go_no_go.md`, which remains in force.

1. **One file, one responsibility, named for that responsibility.** This rule
   stays. It has been applied past its purpose in places: an 8-line file for a
   single predicate costs more navigation than it saves. Group trivially small
   pure helpers with their only caller.
2. **Validate at boundaries, once.** Do not re-validate an already-validated
   immutable value on every internal hop.
3. **No success without content.** Empty, control-only, *and refusal-shaped*
   provider output are all failures. See D1.
4. **No unbounded wait.** Every path that can block on an external party must
   have a caller-visible bound. See D2.
5. **Never destroy paid work.** Any operation that has already spent money must
   surface what succeeded, even when a later item fails. See D3.
6. **No hidden cost.** No automatic retry, model switch, key rotation, or
   provider fallback inside an adapter. This rule is deliberate and stays.
   Compute and expose disposition; let the caller act.
7. **New structure requires a failing case.** Add an abstraction when a real
   failure demands it, not when one is imagined.

## Documentation Rules

The `docs/` directory holds 54 files and 8,699 lines for a 7,824-line library.
That ratio is the problem this section fixes.

1. **One current-state file.** This file. Update it in place; do not add a
   parallel status document.
2. **Historical records are immutable and clearly dated.** A `phase*` file is
   never edited after its gate closes and never cited as current state.
3. **Do not create a decision file and a checkpoint file per slice.** One entry
   in this file plus one dated record if a paid gate ran.
4. **A capability claim names its verification command.** A claim that cannot be
   re-run is not evidence.
5. **When code and documentation disagree, fix the documentation in the same
   change.** A stale doc is a defect, tracked like any other.
6. **Warn, do not imply.** If something is unverified, say so in the sentence
   that describes it.

## Verification Commands

```powershell
& 'D:\Anaconda\envs\OCRLLM\python.exe' -m pytest -q -p no:cacheprovider
& 'D:\Anaconda\envs\OCRLLM\python.exe' -m compileall -q src tests
```

Import-weight check:

```powershell
& 'D:\Anaconda\envs\OCRLLM\python.exe' -c "import sys,time; t=time.perf_counter(); import ocrllm; print(round(time.perf_counter()-t,4), len(sys.modules), [m for m in ('PIL','openai','httpx','onnxruntime') if m in sys.modules])"
```

Credentials for live work are stored by the legacy GUI under
`HKCU\Software\OCRLLM\QCR\ui`. Read them from the registry; never hardcode a key
and never print one. Do not run a paid gate without an explicit budget from the
maintainer.
