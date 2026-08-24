# Active State And Rules

Status: **authoritative and current.** Last verified 2026-08-25 against the
working tree, tests, and recorded commit history.

This file outranks every other document in this repository. Read it before
`docs/ocrllm_library_go_no_go.md`, before `START_HERE.md`, and before any
`phase*` file.

## Document Precedence

Contradictions between documents are resolved in this order. A lower-ranked
file never overrides a higher-ranked one.

```text
1. docs/ACTIVE_STATE_AND_RULES.md     This file. Current truth and rules.
2. docs/plan_phase1_maturation_and_phase2_audio.md
                                      Retained detailed Stage M/A plan; #065 in
                                      this file supersedes conflicting order or
                                      provider direction.
3. docs/plan_phase1_defects_and_provider_split.md
                                      Stage 1 history; its standalone provider
                                      split is superseded by executable slices.
4. docs/ocrllm_library_go_no_go.md    Execution contract, gates, boundaries.
                                      Its dated verification log is history.
5. MIGRATION_STATUS.md / START_HERE.md  Navigation copies of this state.
6. docs/phase*, *_decision_*, *_checkpoint_*
                                      Immutable historical records. Never cite
                                      them as current state.
```

Open maintainer choices are preserved in
[`MAINTAINER_PRODUCT_DECISIONS.md`](MAINTAINER_PRODUCT_DECISIONS.md) so that
handoffs do not lose product direction. That record does not silently override
this authority: any accepted choice that changes current behavior or scope must
first be reflected in this file.

Every dated phase, decision, checkpoint, and incident file is a frozen record
of one past attempt. It keeps the trace but does not define the present. Read
this file first, then verify the named code and tests before trusting any
historical claim.

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

Phase 1 is consequently reopened for maturation. "Phase 1 is GO" means the image
path was proven once under trial constraints; it does not mean the image path is
finished. Stage M is **offline implementation-complete**: model catalog
discovery, file-backed state sidecars, opt-in disposition-gated candidate
queues, slot-indexed intra-request checkpoints, spend disclosure, and
model-aware credential blocking have shipped. Its exit gate remains open until
an explicitly authorized DashScope live smoke with a nonempty DashScope
credential verifies current provider behavior. The former
standalone Stage 2 vision/audio scaffold was replanned on 2026-08-23: the
working image configuration stayed unchanged and the audio-specific boundary
landed with the bounded Stage A1 short-MP3 recognition slice. That direct,
experimental slice is implemented and live-proven through native Google GenAI;
it remains memory-only and does not provide persistence, resume, groups,
upload, long-audio routing, or worker support. #151 implements and live-proves
the separate standalone Stage A2a Google Files lifecycle for one MP3 longer
than 300 seconds; it does not alter A1 or route video. A1 did
not wait on the independent Stage M paid image smoke. Bounded Google image and
audio live tests are already authorized without a separate budget request.
DashScope live work still requires a nonempty recognized credential and an
explicit maintainer budget; its canonical Beijing endpoint is already confirmed.
The A1 probe uses lazy `miniaudio>=1.71,<2` for MP3-specific metadata plus
bounded-memory full decode. FFmpeg, PyAV, Mutagen, and external executable
requirements remain outside the A1 runtime. The probe rejects malformed or
undecodable audio, zero decoded frames, and declared/decoded frame mismatch; it
does not claim that every frame-aligned MP3 truncation can be distinguished
from an intentionally shorter valid file.
The independent `audio` extra remains the user-facing A1 runtime profile. The
`dev` extra also includes `miniaudio` because the shipped short-audio adapter
tests execute that real probe rather than treating its dependency as an
expected skip; this does not make audio a base requirement.
#111 corrected two stale Stage A1 reasons in the frozen 20-entry shared
capability/worker registry. The MP3 entry remains `deferred` there because that
status describes worker support, but its reason now names the separately
live-proven experimental direct Google API. The DashScope short-audio entry
likewise says that Stage A1 shipped Google only instead of claiming Stage A1 is
still in the future. No registry name, worker route, or provider behavior changed.
#112 applies the same already-settled distinction to PDF without widening it:
`pdf.vision` now names the implemented, live-proven direct facade, while
`pdf.vision.resume` names its offline-proven reuse of ordinary image sidecars.
Both remain `deferred` in the shared registry because PDF worker registration
does not exist. `pdf.text` and `pdf.text.resume` remain genuinely deferred.
#153 applies the same distinction to the shipped standalone long-MP3 facade.
`audio.long.mp3-mpeg-layer3` remains `deferred` because the frozen shared
registry has no audio worker route, but its reason now names the live-proven
direct Google Files API instead of claiming all Stage A2 work is still future.
No registry name, status, worker contract, provider behavior, or import changed.
#120 resolved P1-d as no: the new library will not accept legacy application's
localized repair Markdown, so manual PDF repair remains unavailable rather than
growing a compatibility parser.
One adjacent pre-existing defect is now proven but intentionally not hidden:
if a process imports `ocrllm.worker.run_worker_control_loop` before resolving
the lazy package attribute `ocrllm.get_capabilities`, Python installs the
same-named submodule on the package and the later facade attribute is not
callable. The straightforward fix changes the frozen worker's import; eager
loading from `ocrllm.__init__` breaks the maintained lightweight-import contract,
and a callable-module workaround is rejected as opaque overdesign. Keep this
open until the worker boundary is explicitly unfrozen.
#110 corrected the clean-archive test environment to include the already
declared `google-genai>=2.9,<3` development dependency. The complete gate for
clean commit `8991b83` then passed 1325 archived tests with one expected skip,
built a 202,692-byte wheel, and passed base import plus all six isolated
profiles, including audio+Google and installed public PDF recognition. No
provider API was called and the disposable gate root was removed. This repairs
the release proof, not the runtime dependency boundary: the base distribution
remains dependency-empty and Google stays an explicit extra.
The snapshot copies one regular local `.mp3` through an open file handle into a
fixed `source.mp3` name, rejects growth/shrink and a 25 MiB local resource
ceiling, closes the caller's handle, then probes those owned bytes before
yielding. Short destination writes fail as output errors instead of being
misreported by the decoder. Source and destination close-only failures are
typed and redacted; an earlier typed or process-control failure remains primary.
An already-set cancellation signal stops before this snapshot work. The native
adapter checks again before request construction and recognition dispatch; it
does not claim to interrupt the synchronous SDK call after dispatch.
This ceiling is not a provider request limit; the selected adapter must
separately preflight a conservative provider-specific bound for its Base64/JSON
envelope.
The earlier proposal that a built-in Google image adapter remain a later
optional slice is superseded by the #065 queue below. The #067 direct-Python
Google image slice is implemented and live-proven. The #066 transport audit proved that the
legacy built-in Google image/audio path uses native `google-genai`; the generic
OpenAI-compatible Google URL was only an independent-provider configuration
hint. The image adapter therefore follows the actual native legacy transport.
The shipped image snapshot closes every source and destination before image
validation or provider dispatch. Short writes and close-only failures become
typed, redacted errors; an earlier library, ordinary, or process-control
failure remains primary, and cleanup state is tracked by the current operation
rather than inherited from a caller's ambient exception.
The preceding one-byte filesystem validation read follows the same local
precedence rule: a close-only failure is typed, while an earlier validation,
ordinary, or process-control failure remains primary.
The subsequent bounded full-image read also preserves its distinct not-found,
invalid-path, memory-limit, and unreadable classifications across open, read,
and close-only failures. If reading already failed, later stream cleanup cannot
replace that typed, ordinary, memory-limit, or process-control primary.
Final Markdown publication requires the temporary text stream to accept every
character before flush, fsync, close, and atomic publication. A short write or
close failure cannot replace an existing target, and later stream cleanup
cannot replace an earlier typed, ordinary, or process-control failure.
Image resume-state publication applies the same lifecycle rule locally to its
binary stream: every serialized byte must be accepted before flush, fsync,
close, and replacement. A failed completed-state save leaves the last valid
partial checkpoint reusable, final Markdown unpublished, and an earlier typed,
ordinary, or process-control failure primary.
Image resume-state loading enforces its 16 MiB limit on the bytes actually read,
not only on a preliminary path size. It reads at most one byte beyond the limit,
so a sidecar that grows after preflight is rejected before parsing or provider
dispatch. Read-time memory failure and close-only failure are typed and
redacted; later close failure cannot replace an earlier typed, ordinary, or
process-control primary.
Completed-resume Markdown validation is bounded by the exact UTF-8 byte length
derived from the Markdown stored in validated state: it reads at most one byte
beyond that length,
rejects early EOF or trailing/grown content before further I/O, and then checks
the saved digest. An edited artifact cannot force an unbounded scan or another
provider call. Read-time memory and close-only failures are typed and redacted,
and stream cleanup cannot replace an earlier primary.
Image request fingerprinting now hashes owned snapshots with both the 25 MiB
per-image and 100 MiB group ceilings enforced on bytes actually read. Missing,
grown, empty, unreadable, memory-failing, or close-failing snapshots become
redacted output failures instead of caller-source errors or unbounded work.
After each fresh provider pass, the checkpoint re-hashes only the owned
snapshots against the recorded size and SHA-256 before adding or saving the new
slot; local OCR performs the same check after inference while the snapshot is
still owned. A mismatch publishes neither a new slot nor final Markdown, and a
failed atomic save no longer changes the checkpoint's in-memory slot view.
This path-based check closes ordinary persistent mutation, not an adversarial
mutate-then-restore race during the provider or OCR call; eliminating that race
would require a larger immutable-byte request boundary.
See `docs/plan_phase1_maturation_and_phase2_audio.md`.

## #065 Unified Execution Queue

This is the only current execution order. The shipped public product recognizes
images through built-in DashScope, native Google GenAI, or an injected vision provider, supports local
OCR, file-backed image checkpoint/resume, and a fail-fast batch API whose
top-level container must be an exact `tuple`. Each tuple item retains the
existing atomic path or grouped `Sequence` source contract. It also has an experimental, memory-only native
Google short-audio path for one MP3 of at most 300 seconds. Its PDF vision slice
is proven offline, in an installed wheel, and live through Google; it renders all
pages through PDFium and reuses the image/resume path in serial groups of eight.
Content repair is not implemented; #120 selected ordinary resume and explicitly
rejected legacy-Markdown compatibility. The queue now advances to the bounded
video-library slice recorded below. The Google adapters report per-model
input/output token usage when the endpoint supplies it. Public injected providers
return Markdown strings and make no token-usage claim. Existing attempt disclosure
counts provider
calls and model/workflow attempts separately from tokens. Resume is the primary
recovery mechanism. The installed package carries the standard `py.typed`
marker, so standards-compliant downstream type checkers can discover its shipped
inline annotations. #101 added static-only public re-exports for the lazy
facade and proved the current installed wheel with standalone Pyright 1.1.408:
a documented valid consumer resolved `Config` and `RecognitionResult` exactly,
while `Config(timeout_seconds="wrong")` failed with `reportArgumentType`.
Runtime import remains lazy, and a source-level guard keeps the static export
set equal to `__all__`.
Hatch derives distribution version metadata from the public
`ocrllm.__version__` assignment; `pyproject.toml` no longer carries a second
hand-maintained version string.
The source-distribution target explicitly publishes only `pyproject.toml`, the
root package README, and `src/ocrllm/` (plus Hatch's benign `.gitignore` and
generated `PKG-INFO`). It does not use the repository worktree as an implicit
release manifest, so legacy/application code, tests, evidence, runtime output,
local settings, and untracked files cannot enter the sdist by default.

### P0-a — Bounded legacy provider-error evidence audit (completed by #066)

The bounded audit is complete in
[`legacy_provider_error_action_evidence.md`](legacy_provider_error_action_evidence.md).
It maps the relevant legacy Google, DashScope, generic OpenAI-compatible, Codex,
and PDF evidence to one explicit action while separating incidents, offline
tests, and code-only policy. Apply the legacy-parent rule; the table is
historical evidence, not current-live provider truth.

Exit gate: the table cites the exact legacy paths/incidents, distinguishes
provider and error scope, and identifies which rows are proven current versus
historical warnings. Non-goals: implementation, a generic retry count, or an
open-ended legacy survey.

#098 corrected one analogous active classification gap from that evidence. A
Google `429` / `RESOURCE_EXHAUSTED` message can contain both the quota-advisory
sentence and an explicit `rate limit` / RPM / TPM / RPD window marker. Window
markers now take priority: the result is provider-scoped `RateLimited`, not
model-scoped `QuotaExhausted`. Spent quota remains limited to the independently
proven `you exceeded your current quota` plus `check your plan and billing
details` wording when no window marker is present. This changes only typed
classification; adapters still do not retry or switch models internally.

### P0-b — Native Google image vertical slice (completed by #067)

The smallest built-in image path now uses the actual legacy built-in transport,
native `google-genai`. It keeps credential resolution, live catalog parsing,
bounded inline request construction, response/usage parsing, error mapping, and
client cleanup provider-specific, with no internal retry, cache, REST fallback,
or automatic model choice. The public resolver remains pure and lazy.

The authorized live gate used `gemini-2.5-flash`, discovered 37 current
`generateContent` models, completed one image and one explicit eight-image group
with exactly one provider call each, and reported input/output tokens of 595/367
and 2401/1011 respectively. A deliberately invalid non-secret key produced
`PROVIDER_AUTHENTICATION` with `failure_scope="credential"`; stderr was empty
and the safe-output scan found no credential. The gate took 36.910 seconds and
performed no retry.

Exit gate: public image recognition succeeds through the built-in adapter, the
real failure remains typed and non-successful, live model discovery or the
endpoint's actual catalog behavior is recorded, and usage availability is
reported without inventing zero. Non-goals: a second Google transport, a
universal provider interface, PDF, audio, or broad stress testing.

The direct Python API is proven. The shared capability and worker registry stays
frozen at 20 entries; #067 did not modify `contracts/` or `worker/`, and this
record does not claim Google is available through the development worker.

#113 changed only the maintained routine image smoke, not the historical #067
gate or product adapter. Routine execution now discovers the current catalog
and performs one single-image public recognition; it no longer repeats the
already-proven eight-image group or invalid-credential probe. Typed and ordinary
failures report only the safe runner stage (`catalog`, `model_selection`, or
`recognition`) with no provider text. A single foreground run on the committed
`bilingual_printed_slide.png` found 37 models and completed
`gemini-2.5-flash` in exactly one recognition call with input/output usage
595/443. Exit was 0 after 14,627.478 ms, stderr was empty, no credential pattern
or OCR body was published, the child credential environment was removed, and
no owned temporary residue remained. There was no retry, model switch, second
invocation, dependency change, or product-code change.

#115 corrected image-side attempted-call disclosure at the native Google
adapter boundary. SDK/client/catalog failures, a missing selected model, SDK
Part conversion, and cancellation before `generate_content()` now report zero
recognition calls; failures after entering that single method report one. The
shared provider wrapper preserves an exact count supplied by a built-in adapter
and supplies its former entry-based default only when the adapter has no finer
fact. Public regressions prove catalog failure and model absence make zero
generate calls while an exception from `generate_content()` reports one. This
does not count the catalog request as recognition work, add retries, or create a
cross-provider billing or routing abstraction.

### P0-c — Native Google short-audio vertical slice (completed by #069)

The bounded direct slice is implemented and live-proven. The
direct public API accepts exactly one MP3 of at most 300 seconds, keeps the
result in memory, and sends a prompt-first native `google-genai` inline request
only after the owned snapshot and a conservative Base64/JSON bound below
20,000,000 bytes pass. It exposes exact `AudioModelSettings`, typed no-speech,
refusal, response, and provider failures, nullable per-model token usage, and
one-call metadata. It rejects output persistence, resume, overwrite, groups,
and other unsupported public options. It does not implement long audio, upload,
retry, model switching, or fallback.

The earlier #068 authorized synthetic-speech live gate selected
`gemini-3.1-pro-preview`. Its final persisted safe capture returned
`PROVIDER_QUOTA_EXHAUSTED` with `failure_scope="model"` before any successful
transcription could be proven: exit 1 after 6,294 ms for a 14,332-byte,
3.468888889-second MP3; stderr was empty and the credential scan was false.
This remains useful current quota evidence, not a recognition success.

#069 then selected the independently evidenced `gemini-2.5-flash` and ran one
fresh 3.468888889-second, 26,488-byte synthetic-speech MP3 through the same
public facade. The live catalog contained 37 `generateContent` models; the
public `RecognitionResult` succeeded with exactly one provider call and
provider-reported input/output usage of 150/10 tokens. The invalid-key probe
returned `PROVIDER_AUTHENTICATION` with credential scope. The process exited 0
after 13,341 ms, stderr was empty, the credential scan was false, and all
temporary files and key-bearing environment variables were removed. Recognized
text was validated internally but deliberately not published, so this proves a
real public result and transport lifecycle, not transcription quality.

#082 refreshed that live boundary after the later PDF/batch work. One new
3.468888889-second, 22,068-byte synthetic-speech MP3 completed through the
unchanged public facade on `gemini-2.5-flash`. The current catalog again
contained 37 `generateContent` models; recognition made exactly one provider
call and reported input/output usage of 150/10. The existing invalid-key probe
again returned `PROVIDER_AUTHENTICATION` with credential scope. The process
exited 0 after 12.987 seconds, stderr was empty, the capture contained no
credential pattern, and the generated audio/capture directory was removed.
No transcript or provider text was published, and no retry, model switch,
fallback, product edit, dependency install, or download occurred.

#097 attempted one further foreground refresh after the short-audio
cancellation and packaging/dependency changes, using a newly generated
3.468888889-second, 22,068-byte synthetic-speech MP3 and the same explicit
`gemini-2.5-flash` selection. The service returned typed
`PROVIDER_UNAVAILABLE` with provider scope after 6.253 seconds. The safe capture
did not retain enough stage evidence to distinguish the explicit catalog call
from the facade's catalog/generate boundary, so no catalog count or attempted
recognition-call count is claimed. There was no retry, model switch, fallback,
invalid-key probe, transcript/provider-text publication, credential residue,
or audio-snapshot residue. This is honest current outage evidence, not a
regression claim and not a replacement for #069/#082's successful live proof.

#099 simplified the maintained routine audio smoke based on that evidence. It
still discovers the current catalog and makes at most one public recognition
call, but no longer sends a second, deliberately invalid credential request on
every run. Historical image gates and #069/#082 retain independent
credential-error evidence. Typed failures now report only a safe runner stage
(`catalog`, `model_selection`, or `recognition`) alongside code/scope, so a
future outage is not flattened across those boundaries. No provider text or
product error contract is exposed or changed.

#100 added a process-level regression for that maintained runner. With both
supported credential environment variables absent, the real CLI loads the
current source tree, exits 1 before any network request or source access, emits
one `CONFIG_MISSING` / `catalog` JSON record, and leaves stderr empty. This
locks the automation boundary without changing the public library or adding a
general CLI framework. Ordinary exceptions inside catalog or recognition are
also reduced to `UNEXPECTED_SAFE_FAILURE` with null scope and the known runner
stage; their text is never published and process-control exceptions remain
outside the `Exception` catch.

#103 reran that maintained CLI once in the foreground after the #099/#100
changes. A fresh 3.468889-second, 28,464-byte synthetic-speech MP3 passed
through the public facade on `gemini-2.5-flash`; the live catalog contained 37
models, recognition made exactly one provider call, and Google reported 150
input and 9 output tokens. The runner exited 0 after 7,099 ms. No retry, model
switch, fallback, invalid-key probe, transcript, provider text, or credential
was published. The child credential environment was removed, the parent had no
Google/Gemini credential environment, no recent audio snapshot directory
remained, and the exact generated fixture directory was deleted. This refresh
proves the revised routine runner against a real provider interaction; it does
not expand the short-audio product boundary.

#107 corrected the direct short-audio adapter's failure accounting. Public
errors now report `provider_calls_attempted=0` when SDK setup, catalog/model
selection, or pre-dispatch cancellation fails, and `1` once the single
`generate_content` recognition call has been entered, including mapped network
and rejected/empty/no-speech response failures. The value is invocation-local;
it does not add a billing ledger, retry, model switching, or fallback, and
existing error identity, retryability, cleanup precedence, and successful
per-model token usage remain unchanged.

#108 closed the adjacent post-adapter lifecycle gap: when Google has returned
a successful short-audio response but removal of the owned MP3 snapshot then
fails, the public `OutputError` now reports `provider_calls_attempted=1`.
Pre-adapter option, source, and snapshot failures retain their existing typed
local-error contract rather than receiving a modality-wide synthetic zero.
This is one processor-local settled-call flag, not generalized accounting.

#114 refreshed the maintained audio runner after those accounting and lifecycle
changes. One committed 0.5-second, 2,376-byte MP3 completed on
`gemini-2.5-flash`; the live catalog contained 37 models, recognition made
exactly one provider call, and Google reported 55 input and 2 output tokens.
The runner exited 0 after 5,975.988 ms with empty stderr. No retry, model switch,
invalid-key probe, second invocation, transcript/provider-text publication,
credential-pattern output, or audio snapshot residue occurred. The child
credential environment was removed in `finally`, and the parent environment
remained credential-free. This is a bounded runtime regression, not authority
to broaden short audio or begin provider generalization.

Exit gate met: one public real-MP3 result completed with catalog/model selection,
provider limits, exact call/usage evidence, and no false success. The earlier
model-scoped quota failure remains recorded rather than hidden by retry or
automatic model switching. The private product ceiling of ten hours informs later
routing; it is not the scope of this short-audio iteration. Non-goals: long
audio, Files API lifecycle, FileTrans, chunking, compatibility-endpoint
exploration, or a modality-wide framework.

The shared capability and worker registry remains frozen at 20 entries. The
experimental direct audio API does not claim development-worker availability.

The completed audio slice hands the queue to the image recovery proof below;
#070 completed that proof, so the immediate queue is now P1-b.

### P1-a — Live cancellation, checkpoint, and resume proof (completed by #070)

Use the public API to interrupt real Google image work, preserve settled state,
and resume it. Prove completed calls are not paid or dispatched again and only
missing work runs. Keep the exercise small and authorized.

#070 first verified the end-to-end legacy route: the built-in Google mode is
native `google-genai`, while the `/v1beta/openai` URL is only a hint for the
separate generic-compatible provider. The active adapter already matches that
native transport. Its bounded live gate used eight authorized images and
`gemini-2.5-flash`. The first run settled one draft call, reported input/output
usage 2401/1502, saved one partial draft slot, and then raised `CANCELLED`
before review dispatch. Resume reused that draft with zero replay calls and
made exactly one fresh review call with usage 4278/1066. The final checkpoint
was complete and the Markdown output was published. Total provider calls were
two; the process exited 0 after 70,431 ms, stderr was empty, the secret scan was
false, and capture/tool temporary directories and key-bearing environment
variables were removed.

Typed errors escaping after settled work now carry `settled_model_usage`,
derived from the same current-run ledger, without changing the checkpoint
schema or reusing historical token counts. A proposed global error-detail
sanitizer whitelist was rejected because model labels are caller-controlled;
the narrow processor-owned evidence is safer and easier to understand.

Exit gate: exact before/after request and usage evidence proves reuse; cancelled
and terminal outcomes remain honest. Non-goals: adversarial filesystem races,
new checkpoint schemas, or repair.

P1-a handed the queue to P1-b; #071 completed it, so the immediate queue now
advances to P1-c below.

### P1-b — Concrete-tuple batch contract and full preflight (completed by #071)

`recognize_batch()` now requires `type(sources) is tuple`; top-level lists,
generators, custom `Sequence` objects, and tuple subclasses are rejected
synchronously. This restriction does not narrow the existing per-item source
contract: each item is still an atomic `str`/`Path` or a supported grouped
`Sequence[str | Path]`, including inner lists and custom sequences.

Before creating gates, claims, executors, snapshots, directories, or provider
calls, one read-only preflight normalizes and validates the complete batch,
media/count/size/decode/audio constraints, resolved output targets, existing
targets, and duplicate targets. Invalid, missing, corrupt, existing, or
colliding input therefore raises its existing typed error with zero calls and
zero batch-created output/state/temp side effects. A pure output-path resolver
was extracted so preflight does not create directories; the mutating builder
keeps its execution-time existence/race check. The four short-audio option
checks are shared by one narrowly named helper rather than duplicated.

#071 also fixed a public lazy-export ordering defect: resolving either
`ocrllm.recognize` or `ocrllm.recognize_batch` now binds both public callables,
without making bare `import ocrllm` heavier. Focused/related tests reported
93 passed; the root suite reported 1286 passed, and compile/diff checks passed.
The bounded live gate used two ordered groups of eight authorized images with
`gemini-2.5-flash`. Each group completed with one provider call and a complete,
published checkpoint/output; input/output usage was 2401/1131 and 2401/988.
Total calls were exactly two. The safe tool JSON reported `status="passed"`,
and the wrapper completed after 75,904 ms; a wrapper evidence bug serialized
the child exit code as null, so no child OS exit code is claimed. Stderr/secret/
path/private-content scans were false, and tool/capture temporary state was
removed. No OCR text or provider raw response was published.

#105 added the missing installed-artifact check without changing the contract.
One freshly built 204,174-byte wheel (SHA-256
`1daa2b81a6357ecf360fbc02d626bde8a40e7daa9a0f0f8c1dc46b7fb6ab92da`)
was installed into a disposable Python 3.10.20 environment and imported from
that environment outside the repository. Through public imports, one exact
tuple returned two ordered successful outcomes and exactly two injected-provider
calls. An outer list and tuple subclass each returned `SOURCE_INVALID` with zero
calls; a same-stem collision returned `OUTPUT_EXISTS` with zero calls and no
output/temp directory; a later corrupt image returned `SOURCE_INVALID` with
zero calls and no output/temp directory. This found no product drift and does
not justify another batch abstraction or a wider live-runner protocol.

#109 added the missing public short-audio batch characterization. With an exact
three-MP3 tuple in serial mode, item zero completed with one call, item one
entered Google generation and returned a redacted `PROVIDER_NETWORK` error with
`provider_calls_attempted=1`, and fail-fast item two was an undispatched
`CANCELLED` outcome with no synthetic call count. Caller order, two client
closures, and removal of both audio snapshots were preserved. The test passed
without a batch implementation change; generic parallel settlement remains
covered by the existing batch tests and was not duplicated for audio.

Exit gate met: invalid and colliding batches make zero calls, exact top-level
tuple ordering and per-item grouped-source compatibility remain correct, and
two live batches passed. Non-goals remain arbitrary top-level iterable
compatibility, cross-process locks, or a transaction system. The immediate
queue now advances to P1-c below.

### P1-c — PDF through the image/resume path

Build PDF as ordered image recognition through the proven image provider and
resume path, not a parallel LLM protocol. Use roughly 7-8 pages per provider
request. The first working slice chooses its total batch count from that
iteration's evidence; after stabilization, programmatic live regression defaults
to two batches, normally 14-16 pages.

Exit gate: public PDF output preserves order, bounded reads, settled checkpoints,
and zero repayment of completed resume work. Non-goals: a routine 600-700-page
run, PyMuPDF, whole-file memory loading, or caller-designed partial semantics.

#072 implemented the offline candidate without adding PDF settings: public
`recognize(one.pdf)` snapshots at most 100 MiB through bounded reads, inspects
every page before dispatch, renders one page at a time behind the process-wide
PDFium lock, retains at most one eight-page PNG group, and invokes the ordinary
image facade serially. Final Markdown uses stable range markers such as
`<!-- ocrllm:pdf-pages start=1 end=8 -->`; a same-named directory holds the
ordinary child image outputs and sidecars, while rendered PNGs are removed.
Focused tests and a real local 16-page PDFium probe prove two ordered calls,
atomic output, typed malformed/password/oversize rejection, Windows paths up to
the established 259-unit boundary, and cancellation/resume with group one reused
and only group two dispatched. `recognize_batch()` deliberately rejects PDF in
this first slice. The old planned 500-page cap, arbitrary page/password/partial
options, and per-page attribution are not part of this contract.

#084 added direct regression coverage for the legacy-observed provider-outage
shape rather than inferring it from cancellation. In a 16-page run, group one
settles, group two dispatches and raises a retryable `PROVIDER_NETWORK` failure,
the error reports two attempted calls and one settled PDF group, no final
Markdown is published, and exactly one completed child sidecar remains. A later
`resume=True` call reuses group one and dispatches only group two. The regression
passed without a product-code change; it does not introduce retry, partial
Markdown, failed-range markers, or P1-d repair semantics.

#085 temporarily generalized structured usage emission after an injected test
double returned the internal `VisionProviderResponse`. #086's consumer audit
showed that this was not a valid product defect: the internal response type and
`VisionProvider` are not top-level exports, the public injected-provider example
returns a Markdown string, no public consumer imports the structured type, and
Google was already the only real adapter producing it. The #085 production
condition and unsupported usage assertion are therefore reverted; #084's valid
PDF failure/resume coverage remains. The injected-provider protocol annotation
is narrowed to `str`, while internal built-in adapters retain their existing
structured response. A future second real adapter may generalize usage on its
own evidence; this iteration does not pre-build that contract.

#087 corrected two cold-start documentation contradictions without changing the
PDF product. `START_HERE.md` now says PDF *repair* is unavailable rather than
claiming the live-proven PDF facade itself is absent, and the package public
contract includes the already-exported `PDFError`. The documented import set now
matches `ocrllm.__all__`; batch PDF, repair, and PDF worker support remain absent.

#088 closed a local PDF error-classification gap corresponding to the legacy
render/decode incident without copying its parallel fallback. A 16-page regression
settles group one, then makes verification of the library-generated page-nine PNG
fail before group-two dispatch. That failure is now a fixed-message
`OUTPUT_WRITE_FAILED` with page nine, one attempted provider call, and one settled
group; the completed sidecar remains, while final Markdown and every rendered or
temporary PNG remain absent. The old behavior leaked the generated-image
`InvalidSource`, incorrectly blaming caller input. The active renderer is serial
under `PDFIUM_LOCK`, so no retry, re-encoder, or Pillow initialization framework
was added for the legacy-only parallel race.

#089 refreshed the normal renderer path after #088 with exactly one no-network,
real local PDFium run through the current source public facade. The existing
`OCRLLM` interpreter supplied pinned `pypdfium2 5.11.0` (PDFium
151.0.7920.0) and Pillow 12.3.0; no install was needed. A real generated 16-page
PDF produced two ordered groups of eight, two provider calls with maximum active
calls one, 16 Pillow-loaded PNGs, two ordered range markers, two complete v2
sidecars, and two child Markdown files. Page-PNG, temporary-PNG, snapshot, and
unexpected-output residue were all zero, and the temporary root was removed.
This source-tree smoke complements rather than replaces #073's isolated-wheel
gate or #078's Google live proof.

#073 strengthens the existing `pdf-vision` release profile without changing
the product contract. The isolated installed wheel must build a real 16-page
PDF with PDFium, call public `recognize()` through an injected no-network
provider while the execution policy permits four concurrent requests, and
still observe exactly two serial groups of eight. The smoke also requires two
ordinary complete image sidecars, ordered range markers, the final Markdown,
an empty configured snapshot parent, and no retained rendered or temporary
PNGs. This replaces the weaker one-page backend-only smoke; it does not replace
the Google live exit gate.

The authorized Google exit attempt stopped with zero provider calls because
neither `GOOGLE_API_KEY`/`GEMINI_API_KEY` nor `OCRLLM/QCR` QSettings supplied a
credential in the current `13301` profile. P1-c therefore remained the immediate
queue until one bounded 16-page Google run could prove exactly two image requests,
current per-model usage, complete child checkpoints, ordered range markers, and
no retained page PNGs. Do not advance to P1-d on offline evidence alone.

#075 re-audited the unblock condition after the offline and installed-wheel
proofs were complete. The active resolver has exactly three credential inputs:
explicit `GoogleGenAISettings.api_key`, then `GOOGLE_API_KEY`, then
`GEMINI_API_KEY`. The legacy GUI stores its explicit value under QSettings
`OCRLLM/QCR`, key `ui/google_api_key`; the library does not read that store
implicitly. The current process has neither environment value, and the current
Windows account has no nonempty value at that QSettings key. The probe itself
succeeded and made zero provider calls. Heartbeat work was therefore paused at
P1-c until an authorized key became available to the process or that current
QSettings location. Unrelated hardening and P1-d were not selected to avoid the
external gate.

#076 repaired the separate legacy GUI entry path needed for the maintainer to
populate that existing QSettings value. `legacy_app/launch_gui.bat` now uses
the verified `D:\Anaconda\envs\OCRLLM\python.exe` directly when present and
falls back to its previous conda activation route; its Windows line endings
are pinned as CRLF. The current account also has an `OCRLLM Legacy.lnk`
shortcut on its resolved OneDrive Desktop pointing to that tracked launcher.
The BAT help path and one real spawned GUI process passed. This did not read or
write a provider key and does not close P1-c; the queue remains paused until
the maintainer saves the authorized value through the opened legacy settings
page; at that point the queue was still paused.

#077 confirmed that the current-account QSettings value is now nonempty without
reading or printing it. One authorized 16-page gate process was started with
`gemini-2.5-flash`, created the bounded fixture and recognition artifacts, and
then exited naturally with all exact temporary directories removed. The outer
execution wrapper detached before completion and lost the runner's sanitized
JSON stream, so no retained evidence proves the catalog count, provider-call
count, token usage, checkpoint completion, or publication result. This is an
orchestration-level inconclusive run, not a Google or library failure and not a
P1-c pass. It was not retried in the same iteration, so P1-c remained open for
the next iteration.

The maintainer also recorded a deferred provider-extension direction in
`docs/MAINTAINER_PRODUCT_DECISIONS.md`: after the OCRLLM product paths are
stable, new providers should be additive independent classes with evidenced
provider-owned defaults and mappings, while future cross-provider pooling is a
separate coordinator. The currently configured free Volcengine
OpenAI-compatible source is future bounded-test authority only. Do not begin
that abstraction or adapter as a substitute for the then-open P1-c gate.

#078 closed P1-c with one foreground, no-retry Google run through the public
PDF facade. Live catalog discovery returned 37 models and
`gemini-2.5-flash` recognized 16 synthetic authorized pages as exactly two
serial groups of eight. The result reported exactly two provider calls,
aggregate current-model usage of 4,802 input and 117 output tokens, two
complete child checkpoints, ordered range markers, and a published final
Markdown with zero retained rendered pages. The process exited 0 after 12.719
seconds; stderr was empty, the safe capture contained no API-key pattern, and
both fixture and runner temporary directories were removed. There was no retry,
fallback, model switch, third batch, OCR-body publication, or source edit.
Together with #072's cancellation/resume proof and #073's installed-wheel
runtime proof, this satisfies every P1-c exit condition. The immediate queue is
now the already-bounded P1-d manual PDF repair below; do not broaden it into a
general repair framework or begin provider generalization in its place.

### P1-d — Minimal PDF repair after stable markers

Only after PDF checkpoint and Markdown markers are stable, migrate the smallest
legacy-proven manual repair: when state is missing/unusable or historical
Markdown has no compatible state, identify the failed PDF image range,
resubmit only that range, and atomically retain successful content. This covers
delayed recovery after multi-hour provider outage or daily-quota exhaustion.

Exit gate: one real marker-based failure range is repaired without rerunning
successes. Non-goals: a general repair workflow, speculative marker schema, or
repair as an alternative to normal resume.

#079 found one product-contract ambiguity before implementation. The active
producer emits only successful `ocrllm:pdf-pages start=N end=M` sections and
publishes no final PDF Markdown when a group fails; therefore no active failed
range currently exists for repair to discover after sidecar loss. Legacy repair
auto-detects localized Chinese failure comments, but those comments are not a
stable active identity and legacy publishes them with a non-atomic direct write.
Do not copy that regex or silently invent failure identity.

#080 withdrew #079's initial recommendation to add one failed-range marker and
publish the settled prefix. The active PDF loop is serial and fail-fast. In a
three-group document where group one succeeds and group two fails, group three
is never attempted. A partial document containing only success one and failure
two cannot honestly identify or recover group three after sidecar loss. Calling
group three failed would be false; omitting it makes repair reconstruct and run
unfinished work like a second resume engine; continuing all groups after an
ordinary failure changes the proven fail-fast behavior and can waste calls
during an outage. Legacy avoided this exact gap by submitting all known batches
and writing placeholders, a materially different execution model.

At the #080 decision checkpoint, P1-d had no implementation authority until the
maintainer selected its actual product meaning: either (A) change the producer to
persist an honest, complete all-range partial status model, accepting the wider
failure-semantics and recovery design; (B) narrow repair to a caller-identified
or previously persisted exact failed range, accepting that it repairs known bad
content but does not recover an interrupted missing-state suffix; or (C) freeze
P1-d because ordinary resume already covers the current fail-fast outage path.

#102 reconciled those choices with the later maintainer direction and both code
paths. Active sidecar loss leaves no final Markdown or failed/unattempted range
identity, so ordinary resume remains the only honest recovery for an interrupted
active run. Legacy repair, however, consumes only explicit one-based
`第 N` / `第 N-M 页识别失败` Markdown markers and never infers an absent suffix.
It has no source identity/version and uses non-atomic replacement, so its regex
and writer are not themselves a library state contract. Option A is not
recommended: it widens the proven fail-fast producer solely to support a small
compatibility patch. The decision is now one narrow confirmation: should
historical legacy Markdown with those explicit markers be an intentional input
to the new library? If yes, proceed with B as a separate bounded compatibility
slice; if no, choose C. No repair implementation is authorized until that
single compatibility-scope choice is answered.
Until that answer, C remains the operative default. A raw localized-comment
parser is not recommended; if historical compatibility is approved, the B
slice may consume only the exact legacy syntax at its input boundary without
promoting it to active state. No provider call or product-code edit was made by
any of these contract audits.

#106 checked the maintainer-decision record rather than inferring consent from
its general repair description. Its later, specific instruction still says to
confirm historical compatibility before implementation, so the gate is not
answered. If the answer is yes, the recommended contract is now fixed enough to
implement without another architecture round:

- expose one separate `repair_pdf(pdf_path, markdown_path, *, config=None)`
  facade; do not overload `recognize()`, change the active PDF producer, or add
  a normal resume/checkpoint schema;
- accept only existing UTF-8 historical Markdown containing the exact legacy
  one-based single/range HTML comments (`第 N` or `第 N-M 页识别失败`, including
  the historical `页逐页识别失败` wording). Validate every marker and PDF page
  bound before dispatch; reject zero, reversed, out-of-range, duplicate,
  overlapping, malformed, or over-eight-page ranges with zero provider calls;
- process original marker spans in document order. Snapshot and inspect the PDF
  once, render only each exact marked range, and reuse the current memory-only
  image recognition path. One marker is one bounded image request; never infer
  or run an unmarked suffix;
- rebuild from original spans rather than global string replacement, so model
  output containing marker-like text cannot redirect a later replacement.
  Atomically publish each successful replacement before starting the next
  provider call. A later typed failure or cancellation leaves the current and
  later markers intact while preserving already published paid work; rerunning
  scans only the remaining markers;
- return the ordinary `RecognitionResult` only when every original marker was
  repaired. Reject conflicting normal output/resume options rather than
  silently ignoring them. Use existing snapshot, inspection, renderer, output
  claim, image processor, atomic Markdown writer, and typed errors; do not touch
  frozen contracts/worker or build a generic repair framework.

The first implementation regression should use a 24-page PDF whose middle
`第 9-16 页识别失败` marker is repaired by exactly one injected-provider call,
while the successful prefix/suffix stay byte-identical and all rendered/temp
files are removed. The next lifecycle regression should make marker one succeed
and marker two fail, prove marker one was atomically retained before the second
call, then rerun and dispatch only marker two. This is a conditional execution
contract, not implementation authority.

#120 supplied the explicit answer: **no**. The new library owns only its own
state and output formats and will not accept legacy application's localized
failed-page Markdown as a public input. P1-d therefore selects option C and is
closed without `repair_pdf`, a marker parser, or producer changes. Ordinary
typed image sidecar resume remains the recovery path for active PDF runs.

### P1-e — Provider-free video parsing, then independent media recognition

Video is the next authorized product line. Keep it an importable Python-library
surface and migrate it in executable slices rather than copying legacy's GUI,
five-phase controller, social downloaders, or both scene-detection systems.

Ordered slices:

1. inspect one local MP4 through a lazy optional video backend, validate finite
   positive metadata plus one decodable frame, release the capture on every
   exit, and keep bare `import ocrllm` dependency-light;
2. add bounded coarse comparison, negative-feedback refinement/calibration, and
   retained frame artifacts with timestamps and frame indices. Use the main
   legacy `VideoProcessor` behavior as evidence; do not also migrate the unused
   PySceneDetect/TransNetV2 route;
3. feed retained frames through the existing image-recognition path without a
   video-specific vision protocol;
4. extract the audio track and bind its recognition to an audio provider that
   can differ from the frame/image provider. The two pipelines may share
   optional hotwords but neither is an execution dependency of the other;
5. only after those calls work, define composition, cancellation, retained
   artifacts, and resume from their observed lifecycle.

#120 implements slice 1 as public `inspect_video(source) -> VideoInfo`. It
accepts one `.mp4`, uses the lazy `video` extra (`opencv-python>=4.13,<4.14`),
checks a real first-frame decode, returns frame count/FPS/duration/dimensions,
and makes no provider call or output file. OpenCV remains absent from plain
package import.

#121 implements the bounded first half of slice 2 as public
`extract_video_frames(source, output_dir=...) -> tuple[RetainedVideoFrame, ...]`.
It samples one grayscale comparison thumbnail every five seconds, uses the main
legacy adjacent-change, accumulated-drift, and maximum-segment formulas, and
applies at most ten count-driven sensitivity adjustments toward 28–40 retained
frames per hour. Comparison thumbnails are 128×128 and the operation rejects
more than 10,000 candidates rather than retaining full video frames in memory.
Only selected full-resolution JPEGs are decoded again, written and decoded for
validation in a hidden sibling staging directory, then published together as
`<output_dir>/<safe-source-stem>/frames/`. An existing same-stem target is
rejected; there is no overwrite, resume, manifest, provider call, ROI, pHash,
fine-gap scan, or threading behavior. Plain package import remains free of
OpenCV and NumPy. A Windows regression proves the 96-character normalized
source stem plus a controlled 130-unit output parent keeps every published
path at or below 259 UTF-16 units; this is not arbitrary extended-path support.
The following slice feeds these retained frames through the
existing image-recognition path; audio extraction, independent audio binding,
composition, resume, and worker support remain unavailable.

#122 completes slice 3 as public
`recognize_video_frames(frames, config=...) -> list[BatchItemOutcome]`. The
input must be a nonempty exact tuple of exact `RetainedVideoFrame` values in
source order. The adapter feeds their JPEG paths to the ordinary image batch
preflight and recognition path in ordered groups of at most eight, or the
caller's lower configured image limit. It preserves the existing serial or
bounded-parallel execution policy and honest settled outcomes. The complete
frame tuple and every grouped image are validated before provider dispatch.
This intermediate boundary is memory-only: `output_dir`, `resume`, and
`overwrite` are rejected because per-image-group Markdown is not a video
composition or recovery format. It adds no video provider protocol, provider
class, fallback, retry, checkpoint, or legacy-format compatibility. Audio
extraction and an independently configurable audio provider are the next
ordered slice.

The #122 source suite passes 1,365 tests. A fresh 217,405-byte wheel installed
outside the repository kept `recognize_video_frames` callable and base video
symbols free of OpenCV/NumPy, then grouped nine valid retained JPEGs as 8+1
through an injected provider. The bounded Google gate discovered 37 current
models, retained eight frames from a generated MP4, and sent them through the
public adapter as one `gemini-2.5-flash` call with reported usage of 2401 input
and 15 output tokens. It remained memory-only and published no Markdown.

#123 completes the extraction half of slice 4 as public
`extract_video_audio(source, output_path=...) -> Path`. It accepts one validated
local MP4 and an explicit `.mp3` target whose plain parent directory already
exists. The lazy `video` extra now includes `imageio-ffmpeg>=0.6,<0.7`; its
executable streams the first audio track to mono 16 kHz / 32 kbps MP3 in one
exclusive same-directory staging file. A second bounded FFmpeg pass fully
decodes that MP3 before `fsync` and atomic publication. Missing audio, backend
failure, timeout, empty/invalid output, an existing target, and cleanup failure
remain typed and cannot create false success or publish a partial target.
Extraction has no media-duration policy; the video facade's short-MP3 consumer
still rejects more than 300 decoded seconds or 25 MiB. #151's separate
`recognize_long_mp3()` Files entry is not automatically selected here.

Provider separation is deliberately expressed by two real calls rather than a
new provider hierarchy: callers pass their image `Config` to
`recognize_video_frames()` and a separate audio `Config` to `recognize()` for
the extracted MP3. Either call can be made after the other fails. The current
video-audio consumer remains native Google only; injected/general audio providers,
long-audio video routing, a combined video result, shared hotwords, composition,
resume, and worker support remain unavailable. The bounded live gate first
observed honest model-scoped quota exhaustion from the configured
`gemini-3.1-pro-preview` with one attempted call and no fallback. A separate
explicit `gemini-2.5-flash` run then discovered 37 models and successfully
recognized a 4.783-second MP3 extracted from a generated speech MP4 in exactly
one call, reporting 193 input and 12 output tokens and publishing no Markdown.

#124 closes the first observed composition prerequisite without defining a
video document. Every settled `recognize_video_frames()` group now carries the
exact ordered `video_frame_indices` and `video_frame_timestamps_seconds` in its
successful result metadata or typed error details. This identity follows the
actual caller-selected group size, including a lower image limit, and is also
attached to an undispatched cancelled suffix. Later composition therefore does
not have to infer failed or paid group membership from a current batch-size
setting, the legacy failure that made repair ambiguous. The return type,
provider calls, fail-fast settlement, frame artifacts, and memory-only boundary
are unchanged. A combined video result, Markdown format, orchestration,
cleanup policy, cancellation layer, resume state, and audio/frame alignment
remain deliberately undefined until they have a truthful consumer.

The #124 source suite passes 1,373 tests. Its bounded Google gate discovered
37 current models and sent two generated frames as one `gemini-2.5-flash`
request. The successful outcome retained exact indices `(0, 12)` and
timestamps `(0.0, 0.5)`, reported one provider call plus 853 input / 5 output
tokens, and exposed no recognized content or credential. There was no retry,
fallback, second request, repository write, or retained temporary directory.
A fresh 221,257-byte wheel installed with `--no-deps` outside the repository
kept video symbols lazy, then grouped four valid JPEGs as 3+1 through an
injected provider and returned exact identities `(0, 10, 20)` / `(30,)` with
timestamps `(0.0, 0.5, 1.0)` / `(1.5,)`.

#125 makes the audio-branch absence state caller-actionable before video
composition. `extract_video_audio()` now raises the existing `VideoError` with
stable code `VIDEO_NO_AUDIO_STREAM` only when a required first-audio-stream
mapping fails and the same bounded FFmpeg probe succeeds with that mapping
made optional. The probe copies at most one packet to the null muxer, uses no
stderr parsing or platform-specific exit number, and publishes no staging
file. If both probes fail, or a declared audio stream later fails extraction or
full decode, the code remains `VIDEO_INVALID`; backend launch and timeout
classification are unchanged. This lets a future orchestrator accept a truly
silent video as frame-only while still reporting a corrupt audio branch. It is
one new code on `VideoError`, not a subclass, stream-inspection API, ffprobe
dependency, provider behavior, or combined-video success policy.

The #125 source suite passes 1,376 tests. A fresh 221,765-byte wheel installed
outside the repository kept all video/audio heavy modules out of plain import.
Its public extractor returned `VIDEO_NO_AUDIO_STREAM` for a real silent MP4
with no target or staging residue, while a real AAC MP4 published one
nonempty 2,672-byte MP3. The disposable proof root was removed; no provider or
credential was used.

#126 completes the first narrow orchestration/lifecycle boundary as public
`recognize_video(source, output_dir=..., image_config=..., audio_config=...)
-> VideoRecognitionOutcome`. Both exact configs are fully validated before
media output or provider dispatch. Frame extraction first establishes the one
owned same-stem output root; after that gate, audio extraction, frame-group
recognition, and short-audio recognition settle independently. A failure in one
provider branch cannot discard the other branch's paid success. Retained JPEGs
and a successfully extracted MP3 remain caller-visible even when later
recognition fails.

The immutable outcome carries the output root, exact retained-frame tuple,
ordered `BatchItemOutcome` groups or one typed frame-branch error, and exactly
one audio result or typed audio error plus the MP3 when it was published.
`status` and `audio_state` are computed rather than independently stored. All
frame groups plus recognized audio is complete; all frame groups plus
`VIDEO_NO_AUDIO_STREAM` is also honestly complete as frame-only; any usable
success plus another real failure is partial; no usable recognition is failed.

#127 proves that cancellation is currently inconsistent at this new boundary.
The two configs can carry different cancellation signals. A cancelled image
branch is normally settled by `recognize_batch()` as one or more
`BatchItemOutcome(error=Cancelled)`, after which audio can still succeed and
the video outcome is partial. A cancelled audio branch instead propagates from
`recognize()` through `recognize_video()`, so the caller cannot receive an
already-settled frame result; audio extraction has already published an MP3.
On a silent video the same audio cancellation is never observed because no
audio recognition call occurs. Both extractors currently run before either
recognition boundary checks its signal.

This is an open product decision, not an accepted cancellation contract. The
recommended direction is branch-scoped cancellation after config validation:
settle `Cancelled` in the existing frame/audio error fields, preserve the other
branch and retained artifacts, skip audio extraction when its signal is already
set, and stop before output when both signals are already set. The alternative
is whole-call propagation, but preserving paid work would then require a larger
exception/checkpoint contract that carries completed outcomes. Do not implement
either direction, add extraction cancellation parameters, or document the
current asymmetry as intended behavior until the maintainer selects the public
semantics.

As shipped by #126 this was a Python orchestration result, not final video
content. That iteration added no combined Markdown, legacy format, cleanup
transaction, resume/checkpoint, audio/frame alignment, shared hotwords,
long-audio routing, retry, fallback, provider hierarchy, worker, GUI, or social
workflow. The source suite passes
1,382 tests. A fresh 224,623-byte wheel (SHA-256
`105fa6cc56617bcc410173ed2d4cad2db456638bf8e82fd99f51830e6773da3b`)
installed outside the repository kept
the public facade and outcome importable without loading OpenCV, NumPy,
imageio-ffmpeg, or miniaudio, then completed one local video with separate
injected frame and fake-audio calls while retaining one JPEG and the extracted
MP3; its disposable root was removed.

#129 adds the explicit provider-free
`compose_video_result(outcome) -> RecognitionResult` second step. It accepts
only an already returned complete or partial exact `VideoRecognitionOutcome`;
a fully failed outcome remains structured failure evidence and cannot be
relabelled as a successful result. The composition keeps ordered frame groups
and audio as separate Markdown sections, consumes each group's recorded frame
indices/timestamps, verifies those identities still exactly cover the retained
frames, exposes every retained JPEG plus MP3 as assets, and retains stable error
codes for partial branches. A silent video says that no audio stream was present
without inventing a transcript. It aggregates known input/output tokens
separately per model and current-run provider calls across settled branches.

This is memory-only composition: it makes no provider call and does not publish
Markdown, align audio to frame timestamps, parse legacy output, add resume or a
manifest, or change #127's open cancellation semantics. The existing PDF and
new video composition now share one internal token-usage accumulator rather
than maintaining a third copy of that logic.

The final source suite passes 1,392 tests. A real generated MP4 traversed the
local frame/audio orchestration with separate injected providers and then the
public composition step, producing a complete video result with both sections,
retained assets, and two current-run provider calls without a cloud request.
Iteration #130 closed the fresh installed-wheel evidence gap without changing
the package. A clean archive of exact commit `570ef43` built a 225,988-byte
wheel (SHA-256
`a29a668cadb8e8610aaed4b23c8e61e037d5e5a73c7a1421b8988b05e7b6e489`)
through direct Hatchling. Installed with `--no-deps` outside the repository,
that wheel kept plain `import ocrllm` free of OpenCV, NumPy, imageio-ffmpeg, and
miniaudio; then one generated local MP4 completed public `recognize_video()`
with separate injected image and fake-audio processors and composed both video
sections, two retained assets, and two current-run provider calls with no
published Markdown. The exact proof root was removed.

The earlier 180-second `uv build` observation was therefore not evidence of a
package defect. Two later proof wrappers also stopped before product execution:
one treated Hatchling's successful wheel-path stderr as a PowerShell native
error, and one assumed a nonexistent archive nesting level. Packaging evidence
must use a clean Git archive, judge native build success by exit code plus the
expected artifact rather than by an empty stderr requirement, and assert the
explicit extraction root contains `pyproject.toml`. Do not turn these observed
test-harness errors into a package build framework or broaden the Hatch manifest.

#131 fixes one inherited content-loss defect in the negative-feedback frame
selector. When ten calibration attempts still left more candidates than the
hourly safety cap, the old uniform index formula could omit the final candidate
(100 candidates capped to 40 ended at index 97). The cap now maps the first and
last output slots exactly to the first and last candidates while preserving an
exact cap and strict order. This keeps a board state that appears only at the
video ending; it does not change calibration targets, thresholds, candidate
scanning, provider grouping, or artifact lifecycle. The full source suite passes
1,393 tests, including real local MP4 neighbors, and exhaustive arithmetic review
proved unique ordered endpoints for all supported candidate/cap sizes.

#132 closes the adjacent Windows supplementary-Unicode defect in the shared
output-stem normalizer. The 96-unit budget is now measured as Windows UTF-16
units after NFC normalization, forbidden-character replacement, and trailing
dot/space removal. Truncation preserves complete Python characters: ASCII keeps
the prior 96-character behavior, while 48 supplementary characters exactly fill
the budget and a 49th is omitted rather than split. A real MP4 with a 60-emoji
stem now publishes retained JPEGs under a controlled 130-unit parent with every
path at or below the established 259-unit boundary; the ordinary image-output
caller also publishes successfully. This remains a bounded-stem correction, not
extended-path support, reserved-name handling, or a general path framework.
The full source suite passes 1,395 tests. #127 cancellation and final
publication/resume remain separate open product decisions.

#133 fixes the second inherited negative-feedback arithmetic defect. A segment
longer than its current maximum was divided with nearest-integer rounding, so a
900-second mixed-change fixture returned within the target density while still
jumping 355 seconds from one retained candidate to the next under a 315-second
attempt limit. Segment count now uses the mathematical ceiling. The same public
fixture retains one additional representative and reduces its longest gap to
235 seconds. This changes neither thresholds nor the 28--40 frames/hour target;
candidate timestamps remain quantized to the existing five-second scan, and the
endpoint-preserving density cap still applies afterward. The full suite passes
1,396 tests. The next evidence step is a bounded authorized Google video run
through the current frame and audio branches, not another speculative selector.

#134 attempted that post-change live proof and must not be reported as a closed
two-branch gate. The current catalog returned 37 models and included explicit
`gemini-2.5-flash`. One synthetic multi-section speech MP4 traversed public
`recognize_video()`: the image branch recognized one group in exactly one known
generation call, while the audio branch returned a typed failure after a valid
120,608-byte, approximately 30.000204-second MP3 passed extraction and local
snapshot/probe. The outcome honestly remained partial; provider-free composition
retained five JPEGs plus the MP3, kept separate frame/audio sections, and left
`output_path=None`. There was no retry, fallback, model switch, stderr, secret
leak, or temporary residue.

The ephemeral live controller failed its evidence duty: it did not retain the
audio error's stable code or safe `provider_calls_attempted`, then initially
misread the absence of successful audio-result metadata as zero audio calls.
That zero-call claim is retracted; current evidence cannot say whether the audio
request dispatched or why it failed. Do not rerun merely to cover this trace.
Before the next live attempt, add one small maintained combined-video smoke
runner whose offline tests require exact branch code/stage/call evidence for both
success and failure. This is test observability, not a provider framework or
product retry path. No product-code defect was proven by #134.

#135 adds that maintained combined-video smoke runner without spending another
provider request. It discovers the current Google catalog, requires an explicit
model and controlled short MP4 fixture, calls public `recognize_video()` with
separate image/audio configurations, then calls provider-free
`compose_video_result()`. Its JSON contains only catalog/model identity, branch
status, stable error code, runner-owned stage, artifact counts, and directly
supported `provider_calls_attempted`. Missing failure evidence remains `null`;
only a pre-dispatch audio extraction/no-stream failure is reported as zero.
The binary gate passes only for one successful image-group call, one successful
audio call, and complete composition. Partial and failed product outcomes remain
visible but fail the gate. Thirteen offline regressions cover complete, partial,
frame/audio provider failure, missing call evidence, extraction failure, silent
video, fully failed outcome, composition failure, inconsistent or persisted
branch evidence, redaction, and cleanup. No live call, product-code change,
retry, fallback, provider abstraction, telemetry system, or persistence format
was added. The next live attempt must use this runner and its controlled fixture;
ordinary multi-group videos remain valid library inputs but are not this one-call
smoke gate. The full offline source suite passes 1,409 tests; compileall,
diff hygiene, and frozen-boundary checks pass.

#136 made the first post-runner live attempt, but it produced no admissible
provider evidence. The delegated controller started exactly one maintained
runner process and did not retry, yet failed to retain the asynchronous exec
session identifier. The runner completed, but its safe JSON/exit status could
not be retrieved; the capture files had already been removed with the exact
owned temporary root. A zero-provider cleanup audit found no task Python/FFmpeg
process, Google/Gemini credential environment, capture, or temporary residue.
This is a controller evidence failure, not a Google or product result: catalog,
branch status, stable error code, and attempted-call counts all remain unknown.
Do not infer success or failure and do not change product code from this run.
The next bounded attempt must keep and poll any returned exec session ID until
completion, then validate the persisted safe JSON before deleting its owned
capture root. This operational correction does not justify another runner,
retry layer, telemetry system, or product API.

#137 closes the post-runner evidence gap with one independently authorized,
non-retried live attempt using the recoverable controller order required by
#136. The current catalog contained 37 models and the runner used explicit
`gemini-2.5-flash`. Public `recognize_video()` retained one frame in one group;
the image branch completed in exactly one generation call. The audio branch
entered exactly one generation call and returned the stable non-retryable code
`PROVIDER_QUOTA_EXHAUSTED` at runner stage `audio_recognition`. The public
outcome and provider-free composition both remained honestly partial, and the
composition retained the JPEG plus extracted MP3 as two assets. The runner
exited 1 after approximately 20,982 ms because this binary gate requires both
branches, not because the successful image result was discarded.

The safe JSON/schema check passed, stderr was empty, and scans found no
credential, recognition content, source/output path, raw response, or exception
text. The outer evidence root survived until zero-provider parsing, then was
validated under system TEMP and removed; no retry, model switch, fallback,
dependency change, or repository mutation occurred. This is expected robustness
evidence, not a product defect: quota exhaustion must remain visible and must not
trigger an adapter-internal retry. A future caller/provider-routing slice may
decide when another model is appropriate, but this result does not authorize
building that layer now. Sixty focused Google/video/composition regressions pass.

#138 closes one public video-result integrity gap proven independently before
editing. A manually constructed `VideoRecognitionOutcome` could declare one
`output_root` while carrying existing JPEG/MP3 artifacts from unrelated paths;
provider-free composition then returned those foreign files as assets of the
claimed video. Construction now rejects any retained frame whose lexical parent
is not exactly `output_root / "frames"`, and rejects any audio artifact not
exactly equal to `output_root / "audio.mp3"`. Every outcome produced by public
`recognize_video()` already uses that layout. The existing missing-artifact
composition regression now keeps its missing frame inside the declared frames
directory, so layout mismatch and later file disappearance remain separate
failures.

This is an exact `Path`-layout invariant, not physical containment: manual
constructors must reuse the same lexical paths, and `..`, absolute/relative, or
symlink aliases are not resolved. No existence check, canonicalization, symlink
walk, duplicate-frame rule, hash, manifest, cleanup transaction, or filesystem
sandbox was added. Four constructor regressions plus real local video,
composition, and Google-runner neighbors pass; the full offline suite passes
1,413 tests, with compileall, diff hygiene, and frozen-boundary checks clean.

#139 stops provider-free composition from presenting incomplete provider-call
evidence as an exact total. `compose_video_result()` now keeps
`current_run_provider_call_count` present but sets it to `None` whenever any
settled provider success or failure lacks a valid nonnegative call count. It
sums only complete branch evidence. A silent video, or a typed video/audio
parsing failure before an audio artifact exists, contributes a proven zero
because provider dispatch did not occur. Provider-reported token usage remains
aggregated separately by model and is unchanged.

This is unknown propagation in one existing metadata field, not a new
accounting system. No billing model, telemetry object, branch-stage enum,
provider retry/fallback, routing policy, persistence format, or legacy
compatibility was added. Focused video/composition regressions pass; final full
suite evidence is 1,419 passed in 55.79 seconds, with `compileall -q src tests
tools`, diff hygiene, and frozen-boundary checks clean.

#140 closes one contradictory public video-outcome state. A manual caller could
pair `VideoError(code="VIDEO_NO_AUDIO_STREAM")` with the exact owned
`output_root / "audio.mp3"` artifact. The outcome then reported audio as absent
and complete while provider-free composition exposed that MP3 in `assets` and
said no stream was present. `VideoRecognitionOutcome` now rejects this pair at
construction. An extracted MP3 remains valid with an audio recognition result
or a real recognition failure; only the explicit no-stream code requires no
audio artifact.

This is one constructor invariant already guaranteed by `recognize_video()`,
not a new lifecycle design. Composition does not silently discard an artifact,
and no new state, serializer, path policy, cleanup transaction, publication,
resume, cancellation, provider behavior, or legacy compatibility was added.
Focused and full verification are recorded in the working diary.
The final offline suite passes 1,420 tests in 55.08 seconds; focused video
neighbors, `compileall -q src tests tools`, lightweight import, diff hygiene,
and frozen-boundary checks are clean.

#141 closes the separate status-propagation defect proved during #140. A frame
or audio `RecognitionResult(status="partial")` was previously counted as a
fully successful branch, so `VideoRecognitionOutcome.status` and the composed
result could incorrectly become `complete`. Video completion now requires
every frame-group result and the audio result, when present, to be explicitly
complete. A partial child remains a usable result and therefore makes the video
partial rather than failed. `VIDEO_NO_AUDIO_STREAM` remains a completely
settled optional absence.

The correction changes only the existing computed property; composition
already consumes that one status source. No new state value, coordinator,
constructor restriction, provider behavior, cancellation policy, publication,
resume, or legacy format was added. Forty focused video neighbors and the full
1,422-test offline suite pass; compileall, lightweight import, diff hygiene, and
frozen-boundary checks are clean.
Cancellation remains the independent #127 maintainer choice.

#142 closes a branch/media-type contradiction in public video outcomes. The
audio branch already required an exact audio `RecognitionResult`, but a manual
frame-group `BatchItemOutcome` could carry an audio, PDF, video, or even a
non-result runtime value. The outcome accepted it; provider-free composition
then placed its Markdown under `Video frames` and could return a plausible
video result. Each successful frame-group outcome now requires an exact
`RecognitionResult` with `source_type="image"`, failing immediately at outcome
construction. Typed frame errors remain valid and unchanged.

This mirrors the existing audio-branch invariant; it does not introduce a
generic media graph, result hierarchy, duplicate-frame policy, serializer,
cancellation change, publication, resume, provider behavior, or legacy format.
Fifty-five focused video neighbors and the full 1,423-test offline suite pass;
compileall, lightweight import, diff hygiene, and frozen-boundary checks are
clean.

#143 re-proves the post-fix video facade as an externally installed Python
library rather than adding another constructor invariant. A clean Git archive
of exact commit `c7f30f0` built offline into a 227,012-byte wheel (SHA-256
`996122aea3749bb40d916a7ac725c752101393728f5f84de036fa6c51beed807`).
Installed with `--no-deps` outside the repository, package and distribution
origins both resolved inside that target; public `recognize_video`,
`VideoRecognitionOutcome`, and `compose_video_result` imported while OpenCV,
NumPy, imageio-ffmpeg, and miniaudio remained unloaded after plain import.

One generated local MP4 then completed through the installed public facade with
separate injected image and fake-audio configurations: one frame group, one
image call, one audio call, recognized audio, two retained assets, and a
provider-free composed result containing both sections and two calls. The
result stayed memory-only with `output_path=None`; no network, provider,
credential, dependency download, or project-environment installation occurred,
and the exact temporary proof root was removed.

The package README had one caller-visible mismatch: its example unconditionally
composed the returned outcome even though fully failed outcomes are deliberately
rejected by `compose_video_result()`. The example now checks the existing
top-level status first, and its prose tells callers to inspect branch
results/errors; complete and partial outcomes remain composable, while failed
outcomes remain structured evidence. This is documentation of the existing
contract, not a serializer, failure wrapper, new result state, publication, or
resume feature. Thirty-two focused composition/import regressions pass.

#144 adds the first explicit final Markdown publication step without coupling
file I/O back into memory-only composition. Public
`publish_video_result(outcome, output_path, overwrite=False)` accepts the same
already-settled complete or partial `VideoRecognitionOutcome`, reuses
`compose_video_result()`, claims the explicit caller-owned target in-process,
and uses the existing full-write/flush/fsync/close atomic writer. Existing
targets are refused by default; explicit overwrite replaces only after the
temporary Markdown is complete. A fully failed outcome reaches no output-path
work, and a write or replace failure cannot change an existing document. The
explicit Markdown target also cannot equal any retained frame or audio asset;
even overwrite mode cannot turn owned media into Markdown and report success.

The returned standard video `RecognitionResult` preserves status, Markdown,
assets, warnings, hotwords, and metadata while adding a verified `output_path`.
This entry does not derive a legacy filename, recognize again, add resume,
manifest, cross-process transaction, cancellation policy, provider routing, or
worker support. The lazy facade resolves the new publication function together
with `compose_video_result()` so ordinary documented top-level import order
does not leave either public name as a sibling module object. Directly importing
a same-named implementation submodule can still expose Python's normal package
attribute behavior; fixing every such private import order would require the
callable-module/custom-module machinery already rejected as opaque overdesign.
Seven direct publication regressions, fifty-one focused video/output/import
tests, and the complete 1,430-test offline suite pass. The first full run truthfully
reported 1,427 passed and two Node-harness failures because Node was absent from
the shell PATH; an existing `D:/Anaconda/envs/STA/node.exe` v22.23.2 was then
used through a process-local PATH only, and the complete rerun passed. No
dependency was installed or downloaded, no persistent environment changed, and
no provider or credential was used.

#145 turns the open #127 cancellation choice into executable public evidence
without freezing the current asymmetry as a regression contract. A generated
one-second audible MP4 and silent MP4 were run through public
`recognize_video()` with injected image recognition, a patched local audio
processor, and pre-set Event signals; no external provider was called. Image
only returned a partial outcome with cancelled frame outcomes, zero image
calls, and one completed audio call. Audio only first completed one image call,
then raised `CANCELLED` with no outcome and zero audio calls. Both signals made
zero provider calls but still extracted frames and audio before the audio
cancel propagated. On silent video an audio-only cancellation was never
observed: image recognition ran once and the call returned complete with audio
absent. The exact temporary experiment root was removed.

Legacy production incidents and their repaired offline regressions establish a
narrower parent rule: cancellation must stop new dispatch while preserving
already settled paid work. Legacy board, short-ASR, audio repair, and video
repair publish completed units before propagating terminal cancellation. This
does not decide the new direct-Python surface because legacy has durable
checkpoints and the current video facade does not. Two viable contracts remain:
(A, still recommended) represent each branch cancellation in the existing
returned outcome, preserve the other branch, skip pre-cancelled audio
extraction, and stop before all output when both signals are already set; or
(B) propagate terminal `Cancelled` only after introducing a bounded way for the
caller to recover the already-settled outcome. B cannot continue hiding paid
work as the current implementation does. No product code or characterization
test changes until the maintainer chooses A or B.

#146 proves #144 is a distributed library capability, not only a source-tree
export. Exact tracked commit `de10a2fca20b6eabe31e9b8f4a734e9d67dab4e0`
built offline from a clean Git archive into a 228,594-byte wheel (SHA-256
`e8ef125ee70b59bb93c12c84ca868d4308fd456ec5e81e85ccf2412de8af5469`).
The wheel installed with `--no-deps --no-index` into an external target;
package and distribution origins were external, and top-level
`publish_video_result`, `compose_video_result`, and `VideoRecognitionOutcome`
were importable while OpenCV, NumPy, imageio-ffmpeg, and miniaudio stayed
unloaded after plain import. The wheel contains `publish_video_result.py` and
`py.typed`, and its packaged metadata README names the new public function.

An outside-repository consumer then published a settled local video outcome to
a nested Markdown target and verified content, status, output path, retained
assets, default no-overwrite, successful explicit overwrite, temporary cleanup,
and retained-asset collision refusal with original bytes preserved. Existing
Pyright was not available, so #146 makes no new independent static-checker claim;
it did not download one. The exact proof root was removed. No repository code,
dependency, network, provider, credential, or persistent environment changed,
and no second release-gate script was added.
The same manifest audit found one adjacent packaging defect for the next atomic
iteration: `project.description` still says board/image only and therefore
understates the already shipped PDF, short-audio, and video surfaces. Do not
silently treat that stale distribution summary as current product scope.

#147 closes that distribution-summary defect without changing product scope.
`project.description` now says exactly `Importable OCRLLM library for image,
PDF, short audio, and video recognition.` It does not claim PDF text, long
audio, provider fallback, worker support, or legacy compatibility.

#151 supersedes only that exact Summary text after the standalone long-MP3
surface shipped. The current candidate says `Importable OCRLLM library for
image, PDF, audio, and video recognition.` It still does not claim automatic
long-audio routing from `recognize()` or video, resume, fallback, worker
support, or legacy compatibility.

An offline dual-wheel comparison built the clean `161ee8d` baseline and a
candidate with only the current `pyproject.toml` overlay. The baseline was
228,594 bytes with SHA-256
`e8ef125ee70b59bb93c12c84ca868d4308fd456ec5e81e85ccf2412de8af5469`;
the candidate was 228,601 bytes with SHA-256
`d46af9ce8624c361f1afd49aa70ce7fa1e27ca059f07c147f12101b7feaf56eb`.
The candidate METADATA Summary matched exactly; member lists, Provides-Extra,
Requires-Dist, and every non-generated-metadata payload hash were identical.
The candidate installed outside the repository with `--no-deps --no-index`,
reported external package/distribution origins and version 0.1.0, exposed the
video public entries, and kept OpenCV, NumPy, imageio-ffmpeg, and miniaudio
unloaded. Twelve focused import/type-marker tests pass. The Python 3.10 project
environment lacks stdlib `tomllib`; no parser was installed because the real
Hatch build proved TOML validity. Both build roots were removed. No runtime
code, dependency, extra, provider, credential, frozen boundary, or persistent
environment changed.

#148 closes an actual end-of-video blind spot in the provider-free frame scan.
The five-second index grid previously omitted the exact final source frame
unless `(frame_count - 1)` happened to be divisible by the frame step. A scene
change in the trailing partial interval therefore never entered comparison and
could not be retained. The scanner now appends that exact final index when
needed before enforcing the existing 10,000-candidate ceiling; comparison,
negative-feedback thresholds, density targets, publication, and public APIs are
unchanged.

A real 2-fps, three-second MP4 whose first five frames were dark and final frame
was bright reproduced the old result as `[0]`; the focused regression first
failed because frame 5 was absent and now returns `[0, 5]` with timestamps
`[0.0, 2.5]`. The existing three-section fixture now retains the end of its last
stable section at frame 29 rather than the earlier coarse candidate at frame 20.
Forty-one frame extraction, video orchestration, frame recognition, inspection, and
lightweight-import tests pass; the complete offline suite passes 1,432 tests in
53.52 seconds. No provider, credential, network, dependency,
config, cancellation, legacy format, frozen boundary, or final-output behavior
changed. This is one extra bounded local decode, not a tunable sampler, second
scene detector, or generalized video-analysis framework.

#149 stops further selector tuning after bounded evidence found no new
ordinary-content correctness defect. A read-only audit exercised stable,
alternating, and maximum-segment candidate sequences; ordering, final-candidate
retention, ceiling-based splitting, and the density cap held. A separate large
random property command exceeded its first controller window and its wrapper
did not retain a session identifier or stdout, so it supplies no claimed
evidence and was not repeated. No threshold, density, segment, or sampling
policy changes are authorized from this audit.

The same iteration proves a different provider-free video parsing defect.
`extract_video_frames()` inspects, scans, and writes selected JPEGs through
separate opens of the caller-owned path. In a real local experiment, a 2-fps
six-frame dark MP4 was scanned, then atomically replaced at the same path by a
same-shape bright MP4 before selected-frame decode. Every recorded comparison
thumbnail remained below mean intensity 50, while the successfully published
JPEG was above 200 and retained index 5. The function therefore combined a
selection decision from old bytes with an artifact from new bytes without an
error. `recognize_video()` can extend the same mismatch to separately extracted
audio because it opens the original path again after frame publication.

This is a proven lifecycle defect, not another hypothetical snapshot adversary.
Two bounded fixes remain: (A, recommended) make one request-owned MP4 copy by
streaming fixed-size chunks to a hidden disk snapshot and use that same path for
inspection, scan, selected-frame decode, and both branches of
`recognize_video()`; or (B) add an explicit public video-temp-directory option
and place the same snapshot there. A metadata/hash recheck is insufficient: it
detects ordinary mutation only after work and does not make all decoders consume
the same bytes. Do not load a video into memory, build a generic media snapshot
framework, add content-addressed storage, or implement only the frame half of
combined-video stability. The maintainer must choose a hidden snapshot inside
`output_dir` beside the final same-stem root, without a new API, versus an
explicit temp-directory parameter before implementation.

#150 proves that the separate audio branch is real but still too narrow for an
ordinary lecture video. A generated, audible 301.056-second MP4 passed the
public `recognize_video()` facade with an injected image provider and a guarded
Google audio adapter. Frame recognition made exactly one injected call and
retained five JPEGs; audio made zero provider calls because the fully decoded
MP3 exceeded A1's 300-second ceiling. The returned outcome was honestly
`partial`, with audio code `SOURCE_TOO_LARGE`, and retained the extracted MP3.
No provider, credential, or network request was used, and the temporary root was
removed. This is not a false-success bug, but it is executable evidence that the
current video path cannot finish normal longer lectures.

#150 selected Stage A2a: one standalone local MP3 longer
than 300 seconds through the native Google Files API, using the currently served
catalog and exactly one selected model. It must prove upload, bounded processing
wait, one generation, manual remote-file deletion in cleanup, typed secret-safe
failure, and lazy optional dependencies with a bounded authorized live request.
Legacy supplies production evidence for this transport, but its current
implementation does not delete the uploaded remote file; the active library
must not copy that lifecycle gap. Stage A2a does not add chunking, resume,
parallel splitting, model switching, fallback, a provider base class, or video
integration. Stage A2b may add evidence-driven chunking/resume toward the
private ten-hour product ceiling only after A2a is live-proven. Connecting long
audio back to `recognize_video()` waits for the open #127 cancellation and #149
snapshot-placement choices so it does not invent branch or source-lifetime
semantics.

#151 implements that exact A2a boundary as public `recognize_long_mp3()`. The
entry accepts one in-memory-result MP3, requires exact Google and audio-model
settings, snapshots through fixed-size disk chunks, fully decodes with bounded
Python memory, and enforces more than 300 seconds, no more than Google's current
9.5-hour single-prompt limit, and no more than the Files API's 2 GB per-file
limit before SDK work. The existing short route now shares the same snapshot
and decode cores without changing its 25 MiB/five-minute contract. Plain
`import ocrllm` remains lazy.

The adapter discovers the live catalog, uploads once, waits through only
`PROCESSING` to `ACTIVE` within `Config.timeout_seconds`, generates once, then
attempts remote deletion and client close on every post-upload exit. Provider
and cancellation failures preserve generation-call evidence and annotate
cleanup failure without exposing SDK text or remote identity. A successful
transcript with failed remote/client cleanup is returned as `partial` with an
explicit warning instead of being lost or falsely reported as fully clean.
There is no retry, model switch, fallback, chunking, resume, persistence,
parallel split, batch entry, worker route, or video integration.

Offline verification is 106 focused tests plus the complete **1,451 passed in
55.27 seconds** suite, compilation, and diff checks. The one authorized live
gate used a generated 307.98-second, 1,232,161-byte MP3 and explicit
`gemini-2.5-flash`: current catalog 37, exactly one generation, Google usage
9,893 input / 25 output tokens, remote deletion true, client cleanup true,
exit 0 in 19,172 ms, empty stderr, and no temp or credential residue. The
runner printed neither transcript, source path, credential, remote URI, nor raw
provider response. Stage A2a is complete; A2b chunk/checkpoint work and video
routing remain separate future gates.

#152 narrows A2b to one unresolved product choice before code. The shipped A2a
path is a sound one-request lifecycle, but it cannot preserve any transcript
when a long generation fails or the process stops. The legacy Google path gives
useful code-level evidence for ordered 1,800-second logical windows with 30
seconds of context on each boundary, immediate per-segment checkpointing, and
zero-call reuse of matching completed segments. It does **not** give production
or live evidence for Google chunk transcription, overlap trimming, or source
identity: its tests use fakes, its source match is only path/size/mtime, overlap
deduplication is delegated to the prompt, final publication is non-atomic, and
remote Files are not deleted. With `PYTHONPATH=legacy_app`, focused Pytest on
`legacy_app/tests/test_google_audio_routing.py` passes 27 tests in 6.60 seconds
without network or provider calls; this validates the code-only behavior, not
live Google quality.

Two bounded A2b routes remain. Route A splits only inputs above Google's 9.5-hour
single-prompt limit, minimizing calls but leaving ordinary long lectures unable
to resume. Route B, recommended, keeps A2a as the explicit in-memory one-shot
operation and makes the persisted A2b operation use fixed ordered chunks for all
long MP3s; each settled transcript is atomically recorded before the next call,
and `resume=True` reuses only a strong matching source/request/segment identity.
Route B addresses the observed unstable-provider recovery need but consumes more
per-request quota and requires an explicit overlap policy. The maintainer must
choose A or B before chunk extraction or checkpoint code is added.

The smallest maintainable state is audio-specific and versioned. Reuse the
existing strong source-fingerprint shape and generic atomic Markdown writer,
but do not reuse or generalize the image-specific resume schema/classes. Persist
the immutable ordered segment plan and each segment's exact actual/logical
ranges, validated Markdown hash, model, and attempted generation count. Do not
persist remote IDs when every segment owns one upload/generate/delete lifecycle.
Do not add configurable chunk sizing, parallel recognition, retry/model switch,
provider fallback, a generic checkpoint framework, legacy Markdown repair, or
video integration in the first A2b slice. #127 and #149 still block video
routing, not this standalone design investigation.

The bounded live gate discovered 37 current models and used explicit
`gemini-2.5-flash` image and audio configs for one generated speech-and-slide
MP4. The public call retained one image group and a 14,480-byte,
approximately 3.483-second MP3, made exactly one Google image generation and
one Google audio generation, and returned `status="complete"` with
`audio_state="recognized"`. Provider token usage was unavailable for both
settled results and remains unknown rather than zero. There was no retry,
fallback, model switch, final Markdown, credential/content disclosure, stderr,
or temporary residue.

Two earlier live fixture attempts remain useful negative evidence. A blank
frame plus a sine tone produced two honest one-call
`PROVIDER_RESPONSE_INVALID` failures; a committed text-bearing image plus the
same decoder-valid 0.51-second tone produced a successful image branch and an
honest partial outcome with audio `PROVIDER_RESPONSE_INVALID`. The final gate
changed the fixture to the already-proven synthetic-speech recipe rather than
weakening response validation or retrying the same invalid content.

The maintained all-profile clean-archive gate was started against committed
product tree `92cd179` but did not reach a stage verdict within a 30-minute
bound. Its responsive PowerShell/uv/Python chain remained in archive/dependency
setup, with no isolated wheel or target install, so the run was stopped rather
than duplicated or called successful. The exact gate-owned temporary root was
verified under the system temporary directory and removed. This is incomplete
all-profile evidence, not a source, wheel, or provider failure; the separate
fresh-wheel proof above remains the installed-package evidence for #126.

#128 corrected the gate's silence without claiming the missing all-profile
evidence. The exact first isolated `uv run` now announces archive dependency
preparation plus pytest, has a configurable 1--3,600-second command bound with
a 1,200-second default, terminates its Windows process tree on timeout, and
returns failure before the unchanged `finally` cleanup runs. A no-network
regression used a local sleeping process and proved the started/timeout output
and nonzero exit in about one second. Only this twice-observed stalled stage is
bounded; later hypothetical stalls were not used to create a general download,
retry, or cache framework. A new clean-archive all-profile pass is still
required before that gate can be called complete.

The #121 source suite passes 1,351 tests, and a fresh 215,956-byte wheel installed
outside the repository retained three ordered, decodable JPEGs from a generated
72-frame MP4 with no staging residue. The all-profile clean-archive gate is not
claimed complete: after its missing OpenCV test dependency and uv/Node discovery
were corrected, the single clean run stalled while transferring the 38.3 MiB
OpenCV and 12.3 MiB NumPy wheels and was stopped without retry. This is an
external dependency-transfer blocker, not evidence that the video profile passed.

### P2 — Explicitly deferred work

Credential- and budget-gated DashScope live re-verification, the future
local-model OpenAI-compatible
path, a possible secondary Google compatibility transport, and long audio are
P2. A second Google transport starts only after a proven need and maintainer
confirmation; wire-shape similarity is not evidence of equivalent behavior.

The maintainer has configured free provider test sources, including an
OpenAI-compatible Volcengine endpoint, for later robustness work. #104 verified
that this workspace currently has nonempty Google and independent generic-vision
credentials, but no nonempty built-in DashScope credential in QSettings,
`DASHSCOPE_API_KEY`, or the legacy extra-key field. The stored DashScope endpoint
is the canonical Beijing endpoint and legacy paid mode is disabled. The generic
vision credential is not a DashScope credential and the active library does not
read QSettings, so no DashScope request was technically dispatchable and none was
attempted. These configured sources are test assets, not authorization to begin
provider generalization now.
After OCRLLM itself is stable, the intended direction is one independently
configurable provider class per provider, with provider-specific defaults for
parallelism, effort, and observed error handling; later fallback or API-pool
behavior must be justified by real provider evidence. Current slices should
keep their dispatch and error boundaries legible enough not to obstruct that
future, but must not add a base class, common fallback engine, or per-model
patchwork in anticipation of it.

Usage work is not a separate billing engine. As each real adapter lands,
accumulate locally observed calls plus provider-reported input and output tokens
by the exact model. Missing provider token usage remains unknown, never zero,
and historical checkpoint usage remains distinct from the current invocation.

Stop conditions for #065: do not continue #060-#064-style proactive snapshot or
call-accounting edge scans; do not enumerate hypothetical filesystem failures;
do not build generic provider or repair frameworks, introduce a second Google
transport or universal compatibility layer without maintainer confirmation,
add cross-process locking, UI/PyQt, social
features, unapproved stress tests, or mechanically delete dormant fields.
Existing lifecycle fixes remain. Large-file paths still require bounded
streaming and explicit read/write/close/cleanup. Offline tests are a regression
floor only, not proof of current provider behavior.

## Known Debt In This Repository

Future agents must assume the following and verify before trusting any claim:

- **Fixture byte-reproduction is environment-bound (redesigned 2026-08-19).** The Phase 1 generated-image corpus can only be byte-reproduced in the exact Pillow wheel build that created it; that environment is lost and no installable 12.x build reproduces the pinned pixels. `tests/quality/generators/generate_phase1_fixtures.py` now checks three layers instead: manifest-hash integrity (every environment), same-environment determinism, and reproduction that is byte-strict only under the recorded `GENERATOR_ENVIRONMENT` and pixel-tolerant otherwise. Do not re-baseline the committed images without a maintainer decision: they are the pixels the v17 live evidence was scored against.

- **Quality normalizers v2-v7 are an evidence protocol, not duplicate utilities.**
  The current v7 path executes the cumulative v7→v6→v5→v4→v3→v2 chain,
  and the preserved v17 evidence records each file in its quality code identity.
  Do not merge, delete, or rewrite these stages as routine cleanup. A future
  migration requires byte-for-byte differential normalization and score proof
  over preserved evidence plus an explicit archived-identity strategy.

- **Dated documentation is history.** Old phase and review files deliberately
   retain their original conclusions. Current navigation documents must point
   here and must not repeat those conclusions as present status.
- **The old `main` is an account-access boundary, not architecture debt.** It
  belongs to another GitHub account owned by the maintainer, which is temporarily
  inaccessible because the required email access is unavailable. Development
  continues on the Jasmine fork's `master`. The project is not currently public.
  Do not change the old account's default branch or reinterpret this temporary
  handoff as a release or architecture problem.
- **Structure runs ahead of demand.** `contracts/` and `worker/` are 1,817
  lines (23% of the library) serving a subprocess protocol with no consumer.
  They are correct and tested; they are also not yet load-bearing.
- **Recognition logic is small.** `processors/`, `profiles/`, and `imaging/`
  total 1,059 lines. Most of the library is contract and validation. That ratio
  is acceptable for a library, but it means new capability is cheap and new
  ceremony is expensive. Bias toward capability.

- **Active atomic output no longer amplifies user filenames, but arbitrary deep
  Windows paths remain unsupported.** Markdown and image-resume state writers use
  a fixed `.ocrllm-<uuid>.tmp` sibling instead of repeating the full destination
  basename. Deterministic Windows tests prove a 228-unit Markdown path and its
  243-unit canonical sidecar can publish and resume under a simulated traditional
  259-UTF-16-unit boundary. Public Markdown and `.ocrllm-state.json` names did not
  change. This closes suffix-induced overflow only; it is not general `\\?\`
  extended-path support, and a deeper directory can still exceed the OS limit.
  The PDF slice follows the same rule: its same-named state directory contains
  fixed `page-000001.png` and compact `.p-<16hex>.tmp.png` render names. A
  deterministic Windows regression reaches exactly 259 UTF-16 units without
  repeating the 96-character source stem; this does not claim arbitrary deep
  path support.

- **FIXED BY #116 — the owned PDF state directory no longer follows a Windows
  junction.** The public failing regression used a real junction from the
  expected same-named state path to a directory outside `output_dir`; the old
  implementation dispatched once and wrote through it. A pre-existing state
  path is now inspected without following it and must be an ordinary directory,
  otherwise public recognition returns `OUTPUT_PATH_INVALID` before render or
  provider dispatch. A neighboring regression preserves `overwrite=True` for an
  ordinary pre-existing directory. This is deliberately not arbitrary path
  sandboxing, cross-process locking, or a claim to close check/use races.

- **Same-target output/state ownership is consistent for supported in-process
  concurrency.** Every file-producing `recognize()` claims its resolved target
  without waiting before provider dispatch, rechecks output existence under that
  claim, and holds ownership through all slot/completed checkpoints, Markdown
  publication, and result construction. `recognize_batch()` shares one thread-safe
  claim owner across all items and retains every acquired target until all
  dispatched work settles, so sequential or non-overlapping colliding items cannot
  both report success even with `overwrite=True`. A duplicate gets `OUTPUT_EXISTS`
  before its provider runs; after the batch exits, ordinary sequential reuse is
  allowed again. Event-coordinated tests cover direct state/Markdown races and the
  longer batch lifetime. This is deliberately process-local; separate processes
  targeting one output directory are not coordinated, and no cross-process
  transaction is claimed.

- **Batch-iterable debt is obsolete (#071).** The top-level batch contract now
  requires an exact `tuple` and preflights every item before dispatch. P1-b above
  is the complete current contract; do not restore the historical lazy-iterable
  behavior described by older records.

- **Injected-provider protocol lookup is pre-dispatch configuration work.** If
  reading an injected object's required `recognize_images` method raises, the
  call now returns redacted `CONFIG_INVALID` with
  `provider_calls_attempted=0`; the candidate-attempt ledger records the same
  zero. A provider request has not begun merely because method discovery
  failed. Ordinary exceptions raised after entering the callable method remain
  provider failures and count as attempted calls.

- **Completed image resume honors pre-set cancellation without losing saved
  work.** After validating the completed state's source/request identity and
  final Markdown digest, the reuse branch checks the Event-compatible signal
  before output validation or publication. Cancellation raises typed
  `CANCELLED`, makes no provider call, and leaves both state and Markdown bytes
  unchanged; a later uncancelled resume still reuses them with zero calls.

- **Post-recognition output failures disclose only this invocation's spend.**
  After the image processor returns, failures while assembling the public
  result, saving completed state, validating an existing completed output, or
  publishing Markdown report the current invocation's
  `provider_calls_attempted`. Fresh work also retains its current ordered
  `model_attempts` ledger. A completed-state replay reports zero and does not
  copy historical attempts out of the sidecar; its durable completed state can
  therefore survive a Markdown publication failure and be published later
  without another provider call.

- **Snapshot-boundary failures disclose completed work without inventing
  calls.** Invocation accounting is derived at the normal processor join while
  the owned snapshot context is still active. If later snapshot cleanup fails,
  fresh provider work reports its current model-attempt sum and ledger, while a
  completed-state replay reports zero without historical attempts. Local OCR
  snapshot verification attaches an explicit zero at its own post-inference
  seam. Pre-inference snapshot/fingerprint failures still carry no fabricated
  count, provider/checkpoint failures retain their existing accounting, and
  process-control exceptions remain outside these handlers. A paid draft slot
  remains resumable when cleanup fails; final Markdown is not published until a
  later zero-call resume succeeds.

- **All-slots partial image resume honors pre-set cancellation without losing
  paid slots.** A valid partial state is identity-checked and rejected if a
  final output already conflicts; the operation then checks cancellation before
  constructing the slot checkpoint or entering candidate processing. A
  cancelled replay makes no provider call, publishes no final Markdown, and
  leaves the partial sidecar byte-identical. A later uncancelled resume reuses
  the slots and completes with zero new calls.

- **Batch settlement preserves process-control exceptions.** After one item
  returns a typed failure, settlement maps only a genuinely cancelled
  `Future` to the not-attempted `CANCELLED` outcome. `KeyboardInterrupt`,
  `SystemExit`, and unexpected exceptions from already-running siblings
  propagate unchanged; executor shutdown still waits for dispatched work.
  Coordinated public regressions cover both process-control exception types,
  and a cancelled-Future regression protects the narrower mapping.

- **Batch outcomes preserve item-local recovery facts and distinguish
  pre-dispatch cancellation.** Serial, parallel-first-failure, and settlement
  paths retain the same typed `OCRLLMError` object after clearing only its
  traceback/cause/context links, so code, retryability, workflow attribution,
  provider-call total, model ledger, and redacted details are not flattened.
  Undispatched siblings receive separate `CANCELLED` errors. More narrowly,
  a worker already waiting at an aborted shared provider-start gate now reports
  zero calls and no model-attempt ledger; an injected provider that raises
  `Cancelled` after its callable begins still reports one. Dispatch accounting
  is owned by `call_vision_provider()`, while the workflow layer only adds
  calls completed by earlier passes.

- **The direct library no longer advertises an unimplemented progress hook.**
  The untyped, never-consumed `Config.progress` placeholder was removed from
  the pre-release `0.1.0` constructor. There was no repository caller, example,
  release tag, or defined timing/thread/failure contract. `Config.cancellation`
  remains because it has executable semantics. Frozen worker progress events
  remain a separate wire boundary; a future direct callback must arrive with a
  real consumer and typed modality units rather than reusing the deleted name.

- **The direct library no longer advertises a generic cache directory.** The
  validated-but-never-consumed `Config.cache_dir` placeholder was removed from
  the pre-release `0.1.0` constructor. `temp_dir` remains because image
  snapshots actively use it; DashScope catalog discovery deliberately uses a
  process-memory TTL cache. RapidOCR's model-root setting is not an equivalent
  consumer: redirecting it to an empty directory can trigger implicit network
  downloads and concurrent-download policy that the offline local-OCR slice
  does not own. A future persistent-store or model-directory setting must land
  with a specifically named executable consumer and explicit lifetime,
  provisioning, offline, and concurrency semantics.

- **COMPLETED BY #072 — PDF-only configuration was deferred to the executable PDF slice.** The
  pre-release constructor no longer accepts the never-consumed `pdf_mode`,
  `pdf_pages`, `pdf_password`, or `pdf_allow_partial` placeholders. All four
  were validated but silently ignored by the image-only facade, and no active
  PDF router, processor, caller, example, tag, or release consumed them. Their
  proposed semantics also exceed or differ from the legacy parent: legacy uses
  a contiguous page range, has no password option, and preserves page failures
  without a caller-controlled partial-success flag. Keep PDFium, typed errors,
  resource bounds, and durable repair/resume lessons were retained. The first
  executable slice needs no PDF settings: it is fixed to vision mode, all pages,
  serial eight-page groups, no password input, and no partial-success option.
  Add a setting only with a concrete later consumer and separate authority.

- **Automatic image checkpoint targets are preflighted before dispatch.** When
  `resume=False` but stable provider identity enables paid-work checkpoints, an
  existing non-file canonical sidecar target, including a dangling symbolic link,
  now raises `OUTPUT_PATH_INVALID` before a provider call. The preflight uses
  lexical existence so it cannot erase a broken link by treating it as absent.
  Strict `resume=True` loading retains its existing `RESUME_STATE_INVALID`
  classification. This is a no-write structural preflight, not a promise that
  later permission or filesystem races can be predicted.
  Checkpoint eligibility uses the exact built-in `DashScopeSettings` type or a
  caller-declared injected `resume_identity`; a user provider's class name has
  no effect. This keeps eligibility aligned with configuration, dispatch, and
  resume fingerprinting.

- **Legacy media repair is open debt, not a porting template.** The normal
  video manifest crash, missing-frame false success, and failed-audio cleanup
  deletion found in commit `6b2d9eb` are fixed with direct regressions. Audio,
  board, and video repair now atomically publish each successful retry before
  the next cancellable operation, and cancellation/provider setup errors remain
  visible. Short-audio repair now requires a versioned sidecar containing exact
  source hashes and millisecond unit windows, so current chunk settings cannot
  reinterpret an old failed segment. Standalone board repair now binds exact
  ordered source bytes and saved batch membership through its own versioned
  sidecar instead of parsing filenames. Production board recognition now publishes
  a repairable skeleton before dispatch, atomically checkpoints every settled batch,
  and propagates cancellation/provider setup failures. Video Phase 4 now expands an
  ordinary failed request into exact per-frame failure markers while it still knows
  membership; repair rejects ambiguous historical batch-only markers instead of using
  today's batch size. The exact findings are recorded in
  `legacy_app/AGENTS.md`. New library modalities must extend typed, versioned
  checkpoint state and atomic publication rather than copy localized
  Markdown-regex repair.

- **Legacy independent-vision failover no longer lies about quota.** When the
  explicit `advance_queue_on_retriable_errors` option advances after an
  ordinary 429/5xx, the client now uses a neutral internal signal, suppresses
  the "free quota exhausted" notification, and preserves the original
  provider exception if all candidates fail. Only explicit free-tier markers
  use `FreeTierExhaustedError` and its existing warning. This is a legacy-only
  correction; the active library already has typed quota, throttle, and
  unavailable-provider dispositions.

- **Legacy Google JSON quota wording is classified consistently.** The
  established Google message "You exceeded your current quota ... check your
  plan and billing details" now maps to `QUOTA_EXHAUSTED` whether it arrives
  as plain SDK text or inside a 429 JSON error. The advisory word "billing"
  no longer mislabels that payload as a payment failure. Generic 429 /
  `RESOURCE_EXHAUSTED`, explicit rate-limit markers, genuine payment errors,
  and 5xx retry behavior are unchanged. DashScope-specific `FreeTierOnly`
  markers are not part of this Google contract.

## Verified State, 2026-08-22

Confirmed by execution, not by reading prose. Method noted so it can be redone.

| Property | Result | Method |
|---|---|---|
| Test suite | 1059 passed, 0 skipped, 0 failed (86.68 s) | `D:\Anaconda\envs\OCRLLM\python.exe -m pytest -q -p no:cacheprovider` |
| Import weight | 0.86 ms wall median, 1.49 ms p95; 0 ms CPU median, 15.63 ms p95 | clean-wheel gate, 30 measured fresh processes after two warm-ups |
| Heavy-module isolation | `PIL`, `pypdfium2`, `openai`, `httpx`, `onnxruntime`, and `legacy_app` absent after plain import | outside-repository clean-wheel `sys.modules` probe |
| Phase 1 evidence integrity | 107,246 bytes, SHA-256 `6f0454d6…a96b`, exact match to the recorded claim | `Get-FileHash` |
| Pinned model exists | `qwen3.7-plus-2026-05-26` served by the account | live `GET /models` |
| Snapshot isolation | Provider reads original bytes while a concurrent thread overwrites the source | threaded race probe |
| Corrupt image-input rejection | zero-byte, truncated, and extension/content mismatch all raise `InvalidSource` before dispatch | live probe |
| Secret redaction | `api_key` absent from `repr`, error message, and error details | live probe |
| Live error mapping | 401, 403 `AllocationQuota.FreeTierOnly`, 404, timeout all mapped to correct type and disposition | live paid probe |

These are load-bearing and must not regress. The error taxonomy and the
snapshot isolation are the two strongest parts of this codebase; build on them.

## Defect Register

Severity is impact on a real user, not implementation effort. D1-D7 are closed,
including the residual D4 limitation (closed 2026-08-22 by `cd7429c`). Of the
Stage M findings G1-G10 are closed in offline code and tests. The Stage M exit
gate is still open because its paid live smoke has not run and the current
workspace has no recognized DashScope credential; closing a code finding does
not imply that current provider-account behavior was live-proven.
Do not close an entry without a test that fails before the fix.

All seven entries were addressed on 2026-08-18, following Stage 1 of
`docs/plan_phase1_defects_and_provider_split.md`. Regression coverage for D1-D4
lives in `tests/test_defect_register_regressions.py`. The current full-suite
command is:

```powershell
& 'D:\Anaconda\envs\OCRLLM\python.exe' -m pytest -q -p no:cacheprovider
```

The exact result is refreshed by the verification command before each status
update. No paid live call is implied by an offline pass.

### D1 — Provider refusal text is accepted as success. **High. Fixed 2026-08-18.**

Marker coverage was extended on 2026-08-18 for apology-prefixed refusals.

`providers/validate_provider_markdown.py` only asked whether the response
contained a visible character. A model that replied `无法识别图片内容，请重新上传`
or `I'm sorry, I can't help with identifying content in this image` was returned
to the caller as a successful recognition.

Fix: `providers/looks_like_refusal.py` ports the behaviour statement of the
legacy `core/output_quality.py::looks_like_refusal` remedy and is applied inside
`validate_provider_markdown`, so both the injected and built-in paths are
covered. A refusal raises `ProviderError` with the new stable code
`PROVIDER_REFUSED_RECOGNITION` and `details["reason"] == "refusal"`; empty or
control-only output keeps `PROVIDER_RESPONSE_INVALID` with
`details["reason"] == "empty"`. The new code's disposition is registered as
`("change_source", "request")`: the model declined a well-formed request, so the
source is what must change. Detection is capped at 300 visible characters, so a
long transcription containing a refusal phrase is still accepted.

Closed HTML comments are ignored by both visibility and refusal inspection as
of 2026-08-23. A comment-only response is therefore
`PROVIDER_RESPONSE_INVALID`/`empty`, while a refusal phrase hidden in a comment
cannot reject real visible Markdown. Accepted output is still returned exactly
as supplied; comments are removed only from the validation view. The bounded
helper handles closed `<!-- ... -->` blocks across lines. It deliberately does
not claim full Markdown parsing, code-fence awareness, or malformed/unclosed
comment handling.

Provider Markdown must also be strictly UTF-8 encodable as of 2026-08-23. An
exact Python string containing an unpaired surrogate is rejected centrally as
`PROVIDER_RESPONSE_INVALID` with `details["reason"] == "invalid_encoding"`.
This prevents both a memory-only false success and a raw `UnicodeEncodeError`
while hashing a paid checkpoint. The value is rejected rather than repaired
with replacement characters, so published recognition content is never
silently changed.

Offline Phase 1 quality scorer re-run after the change: 70 passed
(`pytest tests/test_run_phase1_quality.py tests/test_quality_gate_application.py
tests/test_score_recognition_result.py tests/test_verify_fixture_artifacts.py`).
No committed corpus expectation changed.

Not addressed by this fix: the Phase 1 v17 GO ran through the old validator, so
that gate could not distinguish a refusal from a transcription. The GO is not
re-established by this change.

### D2 — `Config.timeout_seconds` is not enforced for injected providers. **High. Fixed 2026-08-18.**

`timeout_seconds` was only threaded into the DashScope OpenAI client, so an
injected provider that blocked hung the caller permanently.

Fix: the worker-thread design from S1.2 was chosen over renaming the field,
because `timeout_seconds` is a public field and a caller expects it to bind.
`providers/bounded_provider_call.py` runs each injected-provider call on a
pre-warmed daemon worker thread and joins it with `Config.timeout_seconds`,
raising `ProviderError(code="PROVIDER_TIMEOUT", retryable=True)` when the bound
elapses. The abandoned thread is disclosed in the error as
`details["abandoned_provider_thread"] = True`. The worker is started and parked
*before* the request-start gate is awaited, so thread startup does not disturb
the measured provider cadence, and it never dispatches when the gate raises
instead of releasing. Built-in DashScope calls keep their transport timeout and
are not wrapped.

Known limit: a wedged provider thread cannot be killed. It is abandoned as a
daemon thread rather than allowed to block interpreter shutdown.

Cadence timing uses `time.perf_counter()` as of 2026-08-23. The repository's
Windows Python 3.10 runtime implements `time.monotonic()` with 15.625 ms
`GetTickCount64()` resolution, which could lose most of a short configured
interval at a tick boundary. `perf_counter()` is the high-resolution monotonic
QPC clock in that runtime. A deterministic quantized-clock regression proves a
30 ms permit cannot collapse to one 15.625 ms tick, and integration tests
measure provider entry with the same high-resolution clock. This guarantees
gate authorization spacing; arbitrary thread scheduling and remote network
send time remain outside an exact wall-clock guarantee.

### D3 — `recognize_batch` discards completed paid work on any failure. **High. Fixed 2026-08-18.**

**Signature change, taken deliberately.** `recognize_batch` now returns
`list[BatchItemOutcome]` instead of `list[RecognitionResult]`.
`BatchItemOutcome` carries `index` and exactly one of `result` or `error`, so a
caller reads successes and failures from the same ordered list.

Normal execution remains a bounded worker pool with caller order and fail-fast.
The first failure aborts the start gate and cancels pending futures; calls that
were already dispatched — and therefore already paid for — are drained and
settled, and every source that was never attempted gets a `Cancelled` outcome so
the returned list matches the caller's source order. If the finite source iterable
itself raises an ordinary exception, a final redacted `SOURCE_INVALID` outcome
represents the input position that could not be read instead of hiding all earlier
outcomes behind that raw exception.

### D4 — Image resume does not cover the case that loses money. **Medium. Fixed 2026-08-18.**

Two changes, both using the existing versioned job-state format. No second
checkpoint format was introduced.

1. `resume=True` is no longer rejected outright for injected providers. Reuse is
   opt-in and caller-declared: the provider must expose a nonempty
   `resume_identity` string that changes whenever its recognition behaviour
   changes. Without it the previous `ConfigError` still fires, now naming the
   attribute. The library cannot infer behavioural equivalence of two injected
   objects, so equivalence is never inferred silently.
2. The job-state file is **retained** after successful publication instead of
   being deleted. That single change is what makes a batch resume at item
   granularity: re-running the same batch reuses each completed item's state,
   spends nothing on it, and re-pays only for the items that failed. The
   now-unreachable `output/delete_image_resume_state.py` was removed.

Consequence to know: `output_dir` accumulates one `<stem>.ocrllm-state.json`
beside each published Markdown file. That file is the proof of paid work; do not
prune it as clutter.

Checkpointing inside one request is closed by Stage M2 (see "Stage M
Implementation Status"): each workflow pass now persists as it completes and
`resume=True` reuses persisted passes at slot granularity.

### D5 — Local OCR is not runnable in the maintained development environment. **Medium. Fixed 2026-08-18.**

`local_ocr/load_rapidocr.py` imports `rapidocr` (the 3.x API), while
`D:\Anaconda\envs\OCRLLM` only provided `rapidocr-onnxruntime 1.4.4`, which
exposes a different module and a different result API.

Fix: `rapidocr` 3.9.2 is installed in `D:\Anaconda\envs\OCRLLM`, matching the
`ocr` extra pin `rapidocr>=3.9,<4` in `pyproject.toml`. The `DependencyMissing`
details now name the required distribution and call out
`rapidocr-onnxruntime` as an incompatible substitute. The code was not taught a
second backend API: one supported engine, matched by the environment.

Verify:

```powershell
& 'D:\Anaconda\envs\OCRLLM\python.exe' -c "from rapidocr import RapidOCR; import importlib.metadata as m; print(m.version('rapidocr'))"
```

### D6 — The legacy test suite leaks registry keys. **Low. Fixed 2026-08-18.**

`QSettings.clear()` removes values but leaves the organization key, so each run
left an empty `HKCU\Software\OCRLLMTests-<uuid>` tree behind.

Fix: `legacy_app/tests/delete_test_qsettings_tree.py` deletes the tree in
teardown and refuses any organization name outside the `OCRLLMTests-` prefix.
The 60 orphaned keys present on the development machine were deleted by running
that module directly; all 60 held zero values.

### D7 — `RecognitionResult` prose drift. **Low. Fixed 2026-08-18.**

The field is `source_type`. `Architecture.md` described its values as
`"board" | "pdf" | "video" | "audio" | "office"`; board is a `profile`, not a
source type. Corrected there. `docs/ocrllm_module_target_design.md` was already
correct: `SourceDescriptor.media_type`, `Artifact.media_type`, and
`ProcessorOutput.media_type` are real, distinct fields and are not drift.


## Structure Decisions

### Keep and maintain

- `errors.py`, `provider_error_disposition.py`, and the DashScope error mapping.
  Correct, live-verified, and the foundation for every future provider.
- `imaging/snapshot_image_group.py` and the validation chain. Bounded and tested
  against observed persistent mutation; not proof against a mutate-then-restore
  race.
- `config.py` immutability and exact-type validation.

### Keep but freeze

`contracts/` and `worker/` stay in the tree. They are tested and they encode a
real decision about process isolation. Do not delete them.

**Freeze confirmed 2026-08-18. They are closed to change.** No new fields, no
new commands or events, no protocol version bump, and no new tests. They have no
consumer, and 1,817 lines is already 23% of the library.

A future slice that needs to change them must first produce the consumer that
justifies the change, in the same slice. Note that
`contracts/image_recognition_request.py` hardcodes
`provider: Literal["dashscope"]` and `profile: Literal["board"]`, so the protocol
cannot represent modality splitting or audio. That revision belongs to whichever
slice delivers a real consumer, and to no slice before it.

When a Phase 1 change makes a frozen contract inaccurate, record the divergence
in this file and move on. Do not chase the contract into sync.

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
6. **No hidden cost.** Revised 2026-08-18; see "Policy Change: Disclosed
   Automatic Recovery" below. Automatic retry and model switching are now
   permitted, but only when the caller opted in and every attempt is disclosed.
   Silent extra paid calls remain forbidden.
7. **New structure requires a failing case.** Add an abstraction when a real
   failure demands it, not when one is imagined.
8. **Legacy evidence is a warning, not inheritance.** A failure observed in the
   legacy parent deserves a focused check when that capability is ported. Do not
   assume the new library has the same defect or add a defense before proving the
   analogous path exists.
9. **Sustainability includes comprehension.** Defensive code must cover real side
   effects without making the child product stronger or wider than the legacy app.
   The maintenance cost paid by the next agent is part of the design cost.

## Google Robustness Test Authority

Updated 2026-08-23. The maintainer directly authorizes bounded Google API use for
image and audio robustness tests without a separate budget request. Google is free
for this account and is valuable precisely because real calls frequently expose
quota-window limits, temporary overload, API errors, empty replies, unsupported
formats, and excessive-image limits. These are expected test outcomes, not reasons
to weaken validation or report false success.

Select models from the live Google catalog rather than a hardcoded list. Audio is
supported by fewer Google models than images, so verify current audio capability
before dispatch. This authorization permits the bounded native-SDK tests selected
by #065. Do not add a second Google compatibility transport when the native path
is blocked; record evidence and ask the maintainer.
Keep calls purposeful and bounded, preserve exact outcomes, never print credentials,
and submit only authorized data. This authority does not activate a deferred
provider adapter or social-media feature. The detailed operational policy is
`docs/provider_cost_and_reliability_policy.md`.

Real legacy incidents have higher evidence weight than code-only suspicions but do
not prove inheritance. In particular, Windows paths beyond roughly 260 characters
caused failures across multiple legacy stages. The source record is the 2026-08-18
path-handling entry in `legacy_app/AGENTS.md`. Test the analogous boundary when a
filesystem-producing child capability is actually ported; do not pre-build a generic
path framework for capabilities that do not yet exist.

## Policy Change: Disclosed Automatic Recovery

Decided 2026-08-18. This **reverses** part of the earlier rule in
`docs/ocrllm_library_go_no_go.md` that reads:

> Perform no automatic model switch, key rotation, paid-provider fallback, or
> hidden retry in the first adapter.

That rule existed to prevent *undisclosed* paid calls. It was correct about the
harm and too broad about the mechanism. A provider on a free tier returns
`QuotaExhausted` on a per-model basis, and a library that cannot move to the
next free model forces every caller to reimplement the same loop.

The rule is replaced by four conditions. All four must hold.

1. **Opt-in.** Automatic recovery happens only when the caller supplies an
   explicit candidate list. No default candidate chain. An unconfigured call
   behaves exactly as it does today: one attempt, then a typed error.
2. **Disclosed.** Every attempt appears in an ordered attempt ledger in the
   result metadata and in the error details: model tried, disposition, and
   outcome. A caller must be able to reconstruct exactly what was spent.
3. **Disposition-gated.** Switching triggers only when an approved failure is
   explicitly model-scoped: quota exhausted, unavailable, or permission denied
   for that model. Account-, credential-, provider-, and request-scoped failures
   stop. Never switch on a generic failure, `PROVIDER_RESPONSE_INVALID`, or a
   refusal.
4. **Bounded.** A maximum attempt count and a terminating error when the whole
   chain is exhausted. No unbounded loop, no silent give-up.

The behavior oracle is `legacy_app/OCRLLM/core/llm_client.py`, functions
`_vision_fallback_chain`, `_call_with_free_tier_fallback`, and
`_notify_free_tier_switch`. Legacy already orders the caller's primary model
first, slides down the chain on free-tier exhaustion only, notifies the user on
every switch, and raises a distinct "all exhausted" error at the end. Port that
behavior statement, not the file.

## Policy Change: Model Discovery Replaces The Fixed Allowlist

Decided 2026-08-18. The three-model DashScope allowlist in
`resolve_dashscope_model.py` is retired as a gate on caller choice.

The allowlist was protecting a real thing: live quality evidence is measured
against one pinned model snapshot, and silently changing models invalidates it.
That protection is preserved by separating two concepts that were conflated:

- **The evidence baseline** stays pinned and named in result metadata. A quality
  claim always states which model produced it.
- **Caller model choice** is validated against the provider's live catalog, not
  against a hardcoded set. An unknown model fails because the provider does not
  serve it, not because a constant in this repository is out of date.

A model outside the evidence baseline is usable and must be reported as
unproven, not blocked. Do not silently imply baseline quality for a model that
was never gated.

Implementation status: shipped. Since 2026-08-22 the static set is deleted;
catalog validation applies to every non-pinned model, and only the pinned v17
baseline bypasses the catalog because its proof is the live gate itself. The
policy text above now matches the code.

Relevant measurement: the `board.v17` prompt against `qwen3.5-ocr` produced 16
completion tokens and no usable output, while the pinned model produced a full
transcription from the same prompt and image. Prompt and model class are
coupled. Discovery makes a model *selectable*; it does not make it *proven*.

## Stage M Implementation Status, refreshed 2026-08-22

Stage M is **offline implementation-complete**. The following behavior is
shipped and tested offline:

- Non-baseline DashScope model names can be checked against a lazy provider
   catalog. Successful catalogs have a 600-second TTL; expired catalogs remain
   usable during refresh failure; a first catalog failure is surfaced as the
   retryable `PROVIDER_CATALOG_UNAVAILABLE` error. The catalog path is lazy.
- File-backed image recognition writes versioned state atomically before
   publishing Markdown. Re-running a compatible batch can reuse completed
   request outputs. Within one request, each completed workflow pass persists
   as a slot in the same sidecar before the next paid call starts, and
   `resume=True` pays only for missing passes. Injected-provider resume still
   requires a caller-declared nonempty `resume_identity`.
- An explicit `VisionModelSettings.candidate_models` queue is attempted in
   caller order and advances only when quota exhaustion, unavailability, or
   permission denial is explicitly model-scoped. Account-, credential-, and
   provider-scoped failures stop. The queue is bounded and opt-in; a single-model
   call retains its original typed failure. Every attempt discloses outcome and
   paid-call count, and chain exhaustion raises the distinct
   `ALL_CANDIDATES_EXHAUSTED` code with its canonical account-wide disposition,
   not the final candidate's model scope.
- DashScope free-tier and unpurchased-commodity quota codes are mapped to model
   scope, so the credential pool blocks that model rather than the account;
   account suspension remains account-wide. This distinction is offline-tested
   but has not been re-proven against the live account in this update.
- Scout failures name the scout model and never advance the primary candidate
   queue. Injected typed errors retain only an allowlisted canonical
   `failure_scope`; arbitrary provider details remain discarded.

Every non-paid Stage M exit criterion now passes. The latest product checkpoint
`700cc05` passed the reusable clean-archive runner recorded by evidence commit
`5d966e1`: the repository-root suite reported 1203 passed, while the exact
Git-archive suite reported 1193 passed and 10 expected skips. Fixture checks,
compilation, clean wheel/install, outside-repository import, dependency profiles,
generated-image smoke, and offline DashScope construction passed. No provider
request ran. Earlier `271d96d` evidence remains historical. `worker/` and
`contracts/` are unchanged and frozen.

The Stage M exit gate has **not** passed because its DashScope live catalog and
end-to-end smoke still require both a nonempty recognized credential and an
explicit maintainer budget. #104 safely checked the current Process/User/Machine
environment plus legacy QSettings: the canonical Beijing endpoint is present,
but every built-in DashScope credential source is empty. The populated generic
vision credential belongs to a separate OpenAI-compatible path and cannot be
silently reused. Bounded Google image/audio robustness calls are separately
pre-authorized. No DashScope provider request occurred in either the offline gate
or #104. Do not convert this no-cost proof into a claim about current
provider-account or model-quota semantics.

### Stage M Findings

These are current implementation findings, not historical phase failures.
Their identifiers are stable so plans, tests, and future diary entries can
refer to the same issue.

#### G1 — Attempt ledger cannot reconstruct spend. **High. Closed 2026-08-22; terminal aggregation corrected 2026-08-23.**

`cd7429c` added `provider_calls_attempted` to every successful or typed-failure
`model_attempts` entry and a `workflow_slots` disclosure in result metadata.
Pre-dispatch configuration failures now add a `fix_request` ledger entry with
zero provider calls and `model: null`: no provider model was tried, and
caller-controlled invalid text cannot leak through public error details. If a
fixed scout model fails catalog resolution after a paid primary pass, the same
entry retains that prior call count and names the setup workflow pass.
The 2026-08-23 follow-up closes terminal aggregation as well: every ledger
entry remains local to one candidate, while terminal `ConfigError`,
`ProviderError` (including `AllCandidatesExhausted`), and checkpoint
`OutputError` expose the sum across all attempted candidates. A checkpoint
output failure gets its own typed ledger entry and never advances again.
Catalog discovery failure before dispatch defaults to zero calls rather than
the ordinary provider-failure default of one. A second follow-up covers the
post-recognition finalization boundary: completed-state saving, completed-output
validation, Markdown publication, and result construction expose the current
invocation total. Completed-state replay is explicitly zero-call and does not
re-export the historical model ledger. Snapshot-context cleanup after a normal
processor return follows the same current-invocation rule, while local-OCR
post-inference snapshot verification explicitly reports zero.
The 2026-08-23 batch follow-up also moves the local zero/one distinction to the
actual provider dispatch boundary: method lookup and start-gate cancellation
are zero, while callable entry, timeout, provider failure, and response
validation are one. Workflow aggregation adds prior completed calls instead of
inferring dispatch from the error class.

#### G2 — Recovery is quota-only. **Medium. Closed 2026-08-22; scope corrected 2026-08-23.**

The opt-in candidate loop advances for quota exhaustion, unavailability, and
permission denial only when the disposition is model-scoped. It stops for
account quota, provider outage, credential denial, authentication failure,
response-invalid, refusal, and every other wider or unapproved failure. This
scope rule was corrected after regressions proved that account quota and a
provider-wide outage each spent an unnecessary sibling candidate. Exhaustion
wrapping occurs only when the caller configured a candidate list; it removes the
last candidate's model scope so `ALL_CANDIDATES_EXHAUSTED` keeps its canonical
account-wide disposition. Single-model failures retain their original public
identity.

#### G3 — Account blocks prevent eligible model candidates. **Medium. Closed offline 2026-08-22; live semantics pending exit gate.**

Known DashScope free-tier and unpurchased-commodity quota codes now carry model
scope and create only a model block in the credential pool; account suspension
continues to block every model. Tests prove sibling-model acquisition remains
available after model quota. No paid call ran in this update, so whether the
provider still applies those product states per model must be rechecked by the
Stage M live smoke rather than presented as live-proven fact.

#### G4 — Chain exhaustion has the wrong public identity. **Medium. Closed 2026-08-22.**

`AllCandidatesExhausted` no longer subclasses `QuotaExhausted`. It is a direct
`ProviderError` with the new stable code `ALL_CANDIDATES_EXHAUSTED`
(non-retryable, disposition `("stop", "account")`), so callers can distinguish
"the entire configured chain ended" from "one model exhausted." The class moved
from the deleted `all_candidates_exhausted.py` shim into `errors.py`.

#### G5 — Proven-model metadata is too broad. **Medium. Closed 2026-08-22.**

The retired static set lost both remaining roles. `model_evidence` metadata is
now `"proven"` only for the pinned v17 baseline `DEFAULT_DASHSCOPE_MODEL`;
every other model is selectable but `"unproven"`. Catalog validation in
`resolve_dashscope_model` now applies to every non-pinned model (formerly the
static set bypassed it); the pinned baseline keeps its bypass because its proof
is the v17 live gate, not a catalog row. `SUPPORTED_DASHSCOPE_MODELS` is
deleted. The later `resolve_dashscope_maximum_images` shell was also deleted:
its unused model argument always produced the same limit already imposed by
the library, so its candidate could never affect the effective limit or source.

#### G6 — Resume identity version is stale for candidate queues. **Medium. Closed 2026-08-22.**

Closed by `cd7429c` (the Stage M2 slot-resume slice, reviewed and cherry-picked
from the unmerged `stage-m2` branch). The identity version is now explicit:
`ocrllm.image-request.v2`, stored in every new state file. A v1 state is
rejected with `RESUME_STATE_MISMATCH` naming both versions; the v2 document
also hashes the board and sign-scout prompt versions. Nothing migrates; a v1
state is treated as foreign work. See the M2 section below.

#### G7 — Flowed output is not implemented. **Medium. Closed 2026-08-22.**

Closed by `cd7429c` at request granularity: each completed workflow pass
(draft, review, each sign scout) persists immediately as a slot in the
versioned sidecar before the next paid call starts, and `resume=True` seeds
from persisted slots and pays only for missing passes. Batch granularity was
already covered by D3/D4 (one output file plus one retained state sidecar per
item). Proven at the state-machine boundary by `tests/test_m2_slot_resume.py`
and at the operating-system boundary by
`tests/test_m2_process_kill_resume.py`, which terminates a child process after
its second pass starts and then resumes from the first persisted slot.

#### G8 — Scout failures are attributed to the primary model. **Medium. Closed 2026-08-22.**

Every workflow-pass failure now carries its resolved `failed_model`. The outer
candidate ledger distinguishes a scout failure from a primary-model failure,
records the scout identity, and raises without advancing the primary candidate
queue. A built-in DashScope regression proves one primary call plus one failed
scout call and no candidate switch.

#### G10 — Candidate validation is weaker than primary validation. **Low. Closed 2026-08-22.**

`VisionModelSettings` now validates `name` and every `candidate_models` entry
through one shared exact-text predicate (nonempty, already-trimmed, no control
characters), so the recovery chain can no longer accept a name the primary
field would reject.

#### G9 — Catalog outage fail-open. **Closed 2026-08-19.**

Commit `4c5293d` made first-fetch catalog failure retryable and fail closed,
while retaining the last successful catalog during refresh outages.

## Legacy Status, 2026-08-23

Seven legacy durability/repair-hardening slices are complete. `repair_board()` reads the
normal `{"items": [...]}` manifest, accounts for unavailable processed frames
as explicit partial failures, and video cleanup retains extracted audio while
failed transcript segments remain. Audio, board, and video repair now publish
each successful retry through a shared same-directory atomic text writer before
another provider call can be cancelled. Board no longer swallows cancellation
or provider-setup failures. Short-audio outputs now persist source/input SHA-256,
exact millisecond windows, stable unit IDs, splitter metadata, and request audit
metadata in a versioned adjacent manifest. Repair fails before provider dispatch
when that identity is missing or inconsistent. Production short-ASR now publishes
that manifest plus an all-unfinished Markdown checkpoint before dispatch, uses a
bounded rolling request window, and atomically republishes every settled segment.
Cancellation or provider setup failure stops new submissions, drains already-running
calls, preserves their successes, and then propagates. Standalone board outputs now
persist exact ordered source fingerprints, saved batch membership, stable unit IDs, and
machine-readable batch status. Repair resolves renamed sources by bytes, rejects
missing/corrupt/drifted identity before dispatch, and no longer relies on comma-split or
duplicate basenames. Production board recognition now publishes an all-repairable
Markdown skeleton before dispatch, atomically republishes each success or ordinary
failure, and propagates cancellation/provider setup errors without losing prior paid
work. Video batch failures now persist exact frame IDs, and ambiguous old batch-only
outputs fail before provider dispatch instead of being reinterpreted with current
configuration. The media-repair identity queue is closed; earlier fixes remain recorded
history, not proof that all compatibility paths are defect-free.
## New And Fixed In This Working Update

Video repair no longer reconstructs historical failures from today's batch size:

- `_phase4_batch_one()` converts every ordinary failed multi-frame request into one
  existing frame metadata marker and one failure marker per exact frame. Production
  therefore persists repair identities while membership is known instead of saving an
  ambiguous batch ordinal.
- `repair_board()` repairs only explicit frame IDs. The current-batch expansion and
  batch-placeholder replacement branches were deleted. Historical outputs containing
  only `批次 N 失败` are rejected before frame loading, progress callbacks, or provider
  dispatch because their original membership cannot be proved.
- A proposed video sidecar was rejected after code review showed it would preserve an
  avoidable batch abstraction. Per-frame markers already form the legacy repair unit;
  this fix removes more production code than it adds and does not create a schema or
  generic media framework.
- Two direct regressions failed before implementation. The video/resume/failure/quality/
  writer set passed 40 tests in 26.31 s; the offline legacy suite excluding the real
  ffmpeg e2e and deferred import-time Bilibili diagnostic passed 272 tests with one
  explicit live-Google skip in 90.30 s. `py_compile` and `git diff --check` passed. No
  provider, network, active-library, frozen-boundary, or social-media behavior changed.

The current-batch grouping in partial Phase 4 resume remains an efficiency characteristic,
not a repair-identity path: it can cause re-payment but cannot redirect a historical failed
batch. It is unchanged pending separate evidence.

### Previous working update: production board checkpoints

Production board recognition now checkpoints every batch:

- After saving its existing versioned identity sidecar and before the first provider
  request, `BoardProcessor.process()` atomically publishes one repairable failed slot
  per saved batch with the explicit reason `任务未完成`. This reuses the existing marker
  and repair contract; no new status or checkpoint schema was added.
- Each successful or ordinary failed batch replaces only its fixed slot and atomically
  republishes the whole ordered Markdown before progress callbacks or later cancellation
  checks. Cancellation and provider setup failures propagate unchanged, leaving the
  current and later slots repairable while preserving prior paid successes.
- Four direct regressions failed before implementation. The checkpoint/identity/repair/
  failure set passed 26 tests; the offline legacy suite excluding the real ffmpeg e2e
  and deferred import-time Bilibili diagnostic passed 270 tests with one explicit live-
  Google skip. The final runs took 25.46 s and 87.96 s respectively. `py_compile` and
  `git diff --check` passed. No provider, network,
  active-library, frozen-boundary, or social-media behavior changed.

Video failed-batch identity was still open at that checkpoint and is closed by the current
update above.

### Previous working update: stable standalone board identity

Standalone board repair now has stable source and batch identity:

- Before its first provider request, `BoardProcessor.process()` atomically publishes a
  versioned `.board-repair.json` sidecar. It records exact ordered source size/SHA-256,
  stable item and batch IDs, exact batch membership, and prompt/preprocessing audit
  metadata. Markdown carries one machine-readable index/unit/status marker per batch.
- Repair validates schema/version, source collection, item and unit IDs, complete batch
  coverage, and Markdown mapping before dispatch. Missing/corrupt/unsupported state,
  source-byte drift, extra/missing inputs, or presentation-unit drift fails closed.
- Sources are resolved by exact bytes rather than basename. Rename therefore remains
  safe, while comma-containing names and duplicate basenames cannot redirect a paid
  retry. Prompt, model, and preprocessing remain mutable repair-attempt choices; the
  immutable unit is the original source-byte membership, not one past transformation.
- Six regressions failed before implementation. The final identity/repair/failure set
  passed 22 tests; the offline legacy suite excluding the real ffmpeg e2e and the
  import-time live-Bilibili diagnostic passed 266 tests with one explicit live-Google
  skip. Compilation and diff checks passed. No provider, paid, active-library, or
  frozen-boundary behavior changed. A broad run exposed that the Bilibili diagnostic
  performed public HTTP during collection and timed out. That test-infrastructure
  debt is now closed: the diagnostic has a non-test filename, one explicitly called
  function, a `__main__` guard, and bounded live calls; an offline regression forbids
  HTTP-session construction or subprocess launch during import.

Video failed-batch identity was still open at that checkpoint and is closed by the current
update above.

### Previous working update: production short-ASR checkpoints

Production short-ASR durably checkpoints paid parallel work:

- Before the first provider request, `_short_asr()` publishes the versioned repair
  manifest and a complete Markdown skeleton whose slots are explicitly unfinished.
- It submits only a rolling window bounded by the configured worker count. The
  coordinator consumes futures in completion order and atomically republishes the
  complete ordered document after every settled success or ordinary failure.
- Cancellation and provider setup failure stop further submission and cancel work
  that has not started. Already-running calls are drained so successful responses are
  checkpointed before the terminal error is propagated; cancellation takes precedence
  if both terminal conditions occur.
- Three direct regressions first failed. Five checkpoint tests plus audio-repair tests
  passed 16 tests; the legacy suite excluding the real ffmpeg e2e file passed 258 tests
  with one explicit live-Google skip. `py_compile` and diff checks passed. No provider,
  network, active-library, or frozen-boundary behavior changed.

Video failed-batch identity was still open at that checkpoint and is closed by the current
update above.

### Previous working update: stable audio repair identity

Short-audio repair has a stable unit-identity contract:

- `_short_asr()` publishes a versioned `.audio-repair.json` sidecar containing
  SHA-256 and size for both the selected source and actual ASR input, exact
  actual/logical millisecond windows, a source-and-window-derived unit ID,
  splitter settings, and original model/prompt/hotword hashes for audit.
- `repair()` validates schema, source bytes, ASR-input bytes, contiguous windows,
  unit IDs, and the Markdown-to-manifest segment map before any provider call.
  Missing, corrupt, unsupported, source-drifted, or presentation-mismatched state
  fails closed; old output is not silently re-split with today's settings.
- Failed windows are regenerated from saved `-ss`/`-t` bounds. The current chunk
  duration and context configuration is not consulted. The domain identity error
  is deliberately distinct from ordinary recognition `RuntimeError`, so the
  existing audio/video GUI summaries preserve its explanation rather than
  collapsing it into a generic “all segments failed” result.
- Three regressions failed before the implementation. The final focused
  audio/video/resume/failure/GUI set passed 112 tests; the legacy suite excluding
  the real ffmpeg e2e file passed 253 tests with one explicit live-Google skip.
  Compilation and diff checks passed. No provider, network, active-library, or
  frozen-boundary behavior changed.

Board batch/basename and video failed-batch identity were still open at that checkpoint
and are closed by later updates above.

### Previous working update: atomic repair publication

Legacy repair publication now has one explicit durability contract:

- `write_text_atomically()` stages UTF-8 text in a unique file beside the
  destination, flushes and fsyncs it, and publishes only with `os.replace()`.
  Encoding, fsync, and replace failures preserve the prior output, clean the
  staging file, and propagate the original exception.
- Audio, board, and video publish a recognized unit immediately after its
  modality-specific failure marker is replaced. A later `CancelledError`
  therefore remains observable without discarding earlier paid success.
- Board now re-raises cancellation and provider setup errors; audio also
  propagates provider setup errors consistently with video. Ordinary partial
  failures retain their prior error contract.
- Twelve direct repair/writer tests passed after five repair regressions first
  failed. The focused repair/resume/failure-propagation set passed 43 tests; the
  legacy suite excluding the real ffmpeg e2e file passed 244 tests with one
  explicit live-Google skip. Compilation passed. No active-library,
  frozen-boundary, network, or provider behavior changed.

Stable board batch/basename and video failed-batch identity were still open at that
checkpoint and are closed by later updates above.
The shared writer is intentionally only a file-publication primitive; localized
marker transformations were not centralized or promoted into a library API.

### Previous working update: video repair artifact boundary

The current legacy video-repair artifact boundary is verified as follows:

- The Phase 3 manifest reader now consumes the writer's dict schema and treats
  malformed entries defensively. An explicitly missing processed artifact is
  not silently replaced by a source fallback; its frame ID remains a failed
  outcome while successful siblings are still published.
- Cleanup reuses `AudioProcessor.find_failed_segments()` and retains only the
  extracted MP3 needed for repair. A clean transcript still permits the prior
  cleanup behavior, so the fix does not become a broad disk-retention switch.
- The three regressions failed before the fix and pass afterward. The focused
  video/audio slice passed 73 tests; the legacy suite excluding the real ffmpeg
  e2e file passed 235 tests with one explicit live-Google skip. Compilation also
  passed. No active-library, frozen-boundary, network, or provider behavior was
  changed. The later working update closed non-atomic/cancellation publication;
  the current update closes the remaining batch-size-dependent repair identity.

### M2. Flowed output and true resume, 2026-08-19

A single `recognize()` call spends up to six provider calls (drafts, review,
three sign scouts). Each completed pass now persists immediately as a
slot-indexed record in the existing `<stem>.ocrllm-state.json` sidecar, and a
crash mid-request discards nothing that was already paid for.

- `image_slot_checkpoint.py` persists one `ImageSlotState` per workflow pass
  (slot id, workflow pass, provider, actual model, validated Markdown with its
  SHA-256, calls attempted) through the existing atomic state writer. No new
  storage backend: the state document gained a `slots` array and is otherwise
  the same versioned sidecar. Slot writes are atomic replaces, so the file is
  valid after every paid call.
- Resume is slot-granular. `resume=True` with a matching fingerprint seeds the
  checkpoint from the persisted slots and pays only for the missing passes; a
  slot is reused only by the same provider **and** model that produced it, so
  a quota fallback to another model never inherits the failed model's passes.
  Preservation is not opt-in: injected providers keep the D4 `resume_identity`
  declaration, and any checkpoint-eligible run persists slots even without
  `resume=True`.
- A partial checkpoint can coexist with an older Markdown after an
  `overwrite=True` run is interrupted. Because state v2 does not persist the
  overwrite authorization or identify that older artifact, `resume=True` now
  rejects this ambiguous pair with `RESUME_STATE_MISMATCH` before dispatching
  another provider call. The caller can move or remove the old Markdown and
  resume from the retained slots. Automatic continuation through that case
  would require explicit prior-output provenance in a future state version;
  the library does not silently infer permission to overwrite.
- **Fingerprint identity break, v1 to v2 (audit finding G6).** Commit
  `a19776d` silently changed the v1 fingerprint by adding `candidate_models`
  to the hashed document. The identity version is now explicit:
  `ocrllm.image-request.v2`, stored in every new state file. A state written
  under v1 is rejected with `RESUME_STATE_MISMATCH` whose details name both
  versions (`state_identity_version` / `request_identity_version`). Upgrade
  behavior: nothing migrates; a v1 state is treated as foreign work and the
  request re-runs only after the caller removes it or runs without
  `resume=True`. The v2 document also hashes the board and sign-scout prompt
  versions, closing a silent-stale-resume hole that v1 left open.
- **Paid-call disclosure (audit finding G1).** `RecognitionResult.metadata`
  now carries `workflow_slots`: per slot the workflow pass, provider, actual
  model, whether the slot was reused from disk, and calls attempted. Every
  `model_attempts` ledger entry — success or typed failure — carries
  `provider_calls_attempted`, so a successful fallback no longer discards what
  the failed candidates spent. Typed failures keep their `workflow_pass` and
  a terminal error's `provider_calls_attempted` is the sum of the local counts
  in its model-attempt ledger. If a validated paid pass then fails while
  atomically persisting its slot, the `OUTPUT_WRITE_FAILED` error also names
  that workflow pass, adds a failed candidate entry without inventing a provider
  disposition, and reports the full invocation's attempted-call count. Earlier
  slots remain intact, and no final Markdown is published. A completed-state
  write can separately exceed the 16 MiB sidecar limit after all slots fit,
  because completed state also carries the assembled result. That failure now
  reports the current invocation's total calls across every model attempt while
  deliberately omitting `workflow_pass`: all provider passes succeeded and the
  failure is local final-state materialization. The partial sidecar remains
  resumable; a zero-call resume that reaches the same limit reports zero.

Regression coverage is `tests/test_m2_slot_resume.py`: an injected mid-request
failure proves slot reuse including sign-scout passes, a hand-written v1 state
proves the version-named rejection, a candidate-fallback run proves
failed-model slots are neither reused nor lost, and a prompt-version bump
proves resume identity invalidates. `tests/test_m2_process_kill_resume.py`
adds the stronger operating-system termination proof. The current offline gate
results are recorded in the Stage M status above. No paid live call was made.
`worker/` and `contracts/` are unchanged.

## Documentation Rules

The `docs/` directory contains both current policy and immutable historical
records. This section prevents the historical volume from becoming a second
source of current truth.

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
