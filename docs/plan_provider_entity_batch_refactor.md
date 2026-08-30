# Plan: Provider-Model And Media-Batch Refactor

Status: **approved product direction; runtime implementation resumed by the
maintainer on 2026-08-30, one atomic slice at a time in section 0 order.**
Existing provider-free primitive maintenance remains allowed when real media
exposes a defect. This revision replaces the prematurely expanded
2026-08-28 module build specification. It is a decision record and sequencing
guide, not permission to build unused framework pieces.

Authority: root `AGENTS.md` and the latest maintainer instructions outrank this
plan. `docs/ACTIVE_STATE_AND_RULES.md` is the historical work log, not a higher
authority.

## 0. Current pruning and execution checkpoint (2026-08-31, #697)

The maintainer has now authorized migration to begin. Authorization advances
only the next independently verifiable slice in the sequence below; it does not
authorize building later topology, compatibility wrappers, or unused framework
pieces in advance. Historical questions below remain the reasoning trail; this
section alone is the current decision and execution board.

### #667 publishes only the provider-data and image-planning slice

`ProviderModel` is now a package-root public immutable value with the complete
approved data shape: exact vendor/model/controlled adapter, exact typed runtime
settings, three capability booleans, capability-dependent image/audio defaults,
and an immutable canonical-code retry-rule mapping. The mapping is data only;
no retry executor, fallback traversal, wait, or provider pool exists. Both first
presets intentionally have empty retry maps because no same-model recovery rule
has passed its separate real-failure gate.

The two package-root presets remain exactly the live-proven entries. Google
`gemini-2.5-flash` supports image and audio input according to the current
[official model page](https://ai.google.dev/gemini-api/docs/models/gemini-2.5-flash)
and this repository's image, formula-board, PDF, and short-audio runs. Its
planning defaults are eight images and thirty integer minutes. Beijing
`qwen3.5-ocr` is image-input/text-output according to the current
[official model page](https://help.aliyun.com/zh/model-studio/qwen3-5-ocr),
and the official OCR guide documents LaTeX document/formula parsing; its
planning default remains one image and it does not claim audio support. These
are OCRLLM recommendations, not advertised provider hard limits.

The new package-root `batchify_images()` is the first ordinary public consumer.
It accepts a nonempty exact source tuple plus an explicit positive integer size,
one exact scalar `ProviderModel`, or both. An explicit size wins; omission reads
the provider's positive image default. It returns exact ordered tuple groups,
validates every image group with the existing limits, makes no provider call,
and writes no output/state. Flat/nested provider shapes remain later slices.

The initially considered merged recognizer was deliberately not published in
this iteration. The approved partial-settlement contract requires one resumable
sidecar together with failed Markdown slots; exposing a partial result without
that owner would create a non-resumable half-contract. Scalar merged
recognition, its sidecar, and ordinary resume therefore had to land together.

### #668 ships the scalar merged-image recognition/resume owner

Package-root `recognize_images_to_markdown()` now accepts only the exact
already-batched tuple returned by visible planning, one scalar `ProviderModel`,
and required exact `image_task`. It validates the complete task, target, image
plan, and source fingerprints before dispatch; reserves every ordered slot in
one versioned sidecar; attempts each unresolved slot once; and checkpoints each
settled or failed outcome before advancing. It does not re-batch, retry, switch
models, traverse a list, or hide video extraction.

All-settled work publishes one ordered Markdown and removes temporary state.
Mixed settlement publishes exact failed-slot markers, retains state, and
returns the existing result with `status="partial"`. Zero settlement leaves no
new Markdown, retains state, and raises existing `AllCandidatesExhausted`.
Package-root `resume_images_to_markdown()` restores task, prompt version,
source fingerprints, and immutable group membership; a changed scalar provider
is allowed, while settled slots are reused and only unresolved slots dispatch.
The sidecar stores one cumulative usage row per exact `(vendor, model)` and no
credential, runtime settings, retry history, or response body.

This slice also extracts the duplicated image/audio binary sidecar replacement
code into one small atomic-byte writer. The media schemas, paths, and lifecycle
rules remain separate. This is reduction, not a generic transaction framework:
there is still no cross-file commit marker, rollback log, cross-process lock,
state registry, or media-neutral job abstraction. Focused and full offline
regressions are complete; the required bounded live merged-image batches remain
the next independent evidence gate before flat fallback or merged audio.

### #669 does not close the live gate because its evidence capture failed

One delegated bounded attempt exercised the public merged-image entry with two
exact batches of eight existing authorized images, the Google 2.5 Flash preset,
and `detail_ocr`. It made no retry, model switch, fallback, or second attempt.
The child ended after about 58 seconds and its temporary directory was removed,
but the disposable PowerShell/`python -c` wrapper did not preserve an exit code,
safe JSON summary, stdout, stderr, Markdown, or sidecar. The result is therefore
unknown: it is neither a successful library proof nor a typed library failure.

No runtime change is justified by missing harness evidence. The next atomic
gate must first make the disposable live runner preserve an explicit exit code
and content-free result/error summary outside its self-deleting scratch area,
prove that capture without a provider call, and then perform at most one new
bounded call. Flat fallback, retry execution, provider pools, and merged audio
remain behind the still-open scalar merged-image live gate.

### #670 replaces the disposable controller; the live gate stays open

`tools/run_google_genai_merged_image_smoke.py` now owns exactly the missing
scenario: two explicit eight-image batches, the proven Google 2.5 Flash preset,
required `detail_ocr`, and one explicit Markdown target. It has no model/task
selection, credential store, proxy discovery, retry, fallback, cleanup policy,
or provider list. It reports only fixed identity/count/token facts, source-byte
stability, and output/sidecar size and digest; it exits zero only after two
settled slots, exactly two calls, no cleanup warning, published Markdown, and a
removed complete-state sidecar. Partial and typed failure remain inspectable
nonzero outcomes. Unlike #669's wrapper, it leaves evidence for its caller to
inspect and clean.

The first zero-call controller check returned one captured JSON object and exit
code 1, proving the evidence path, but the result was `UNSUPPORTED_FORMAT`
instead of the intended missing-credential failure. Read-only forensics found
that the external PowerShell `Get-ChildItem -Include` selector had not filtered
extensions: 13 of 16 inputs were MP4/ZIP/PART/JSON/MP3/Markdown/text files; the
three actual JPEGs passed complete Pillow validation. No credential was read,
no provider call was made, and the test was not rerun. This is a disposable
selector error, not a library or image-validator defect.

The next atomic gate must select exact `.jpg`/`.jpeg`/`.png` leaves with an
explicit extension predicate, repeat the zero-call capture proof, and only then
permit one bounded live invocation. Do not add automatic source skipping or
broader format compatibility: invalid batch members remain whole-call rejects.

### #671 proves real partial settlement and preserves it for live resume

With an explicit `.jpg`/`.jpeg`/`.png` predicate, the zero-call stage reached
the intended `CONFIG_MISSING` boundary: exact call count zero, unchanged 16
sources, no Markdown, and one initial sidecar. After that state was inspected
and removed, one and only one credential-isolated live runner invocation used
the same two groups of eight through the HTTP proxy.

The fresh live operation made exactly two generation calls. One slot settled;
the other ended with canonical `PROVIDER_TIMEOUT`. The public result was
`partial`, with 609 bytes of Markdown, one retained v1 merged-image sidecar,
unchanged sources, no provider-client cleanup warning, and unknown aggregate
input/output tokens rather than invented counts. The process ended naturally;
its safe JSON was retained, but the external PowerShell parent again failed to
retain a numeric exit code. The approximately 674-second outer duration does
not prove a timeout defect: `timeout_seconds=600` is the existing per-operation
SDK bound, and historical complete runners legitimately exceeded it in total.

The live run exposed one safe-reporting omission in the scenario runner: its
partial JSON counted failed slots but omitted their canonical codes. The runner
now projects only validated slot indexes and stable error codes; descriptions,
paths, and recognized text remain excluded. No production code, retry, fallback,
timeout, or provider policy changed. The partial output/state is intentionally
retained outside Git for the next atomic live-resume gate, which must dispatch
only slot 1 and must not replay settled slot 0. Do not start another fresh run.

### #672 closes the scalar merged-image live and ordinary-resume gate

The exact retained #671 state still contained 16 matching source fingerprints,
one settled eight-image slot, one failed eight-image slot with canonical
`PROVIDER_TIMEOUT`, two historical Google generation calls, unknown historical
token dimensions, and no cleanup failure. A copied-state `--resume` preflight
without credentials returned `CONFIG_MISSING`, exit 1, zero provider calls,
unchanged sources, and byte-identical output/state. It did not mutate the live
state.

One subsequent resume child used the original state and the same exact batches.
It reused slot 0, dispatched only slot 1, and completed with exactly one current
generation call. The safe result reports two settled slots, one reused slot,
two historical calls, current usage of 2,401 input and 298 output tokens,
unchanged source bytes, no provider cleanup warning, a 1,102-byte final
Markdown, and no remaining sidecar. The process ended naturally with empty
stderr. The external PowerShell parent did not retain the numeric live exit and
it is not reconstructed; the independently verified result/state/publication
facts are the completion authority. Both owned TEMP proof roots were then
verified by exact filename and removed without recursive deletion.

The maintained fixed-scenario runner now supports explicit `--resume` and
validates one current call, one reused slot, and two historical calls without
emitting paths, Markdown, descriptions, or credentials. No production runtime,
schema, timeout, retry, fallback, or provider policy changed. Phase 3 of the
evidence-first order is therefore complete. The next separately authorized
slice is phase 4 flat fallback and finite retry evidence; it must not pull in
nested lanes, parallel pools, merged audio, repair, or old-video deletion.

### #673 implements only the serial flat-fallback half of phase 4

`batchify_images()` now also accepts one nonempty exact built-in flat list of
exact `ProviderModel` values. With no explicit size it freezes groups once from
the smallest candidate default; an explicit positive size still wins. Planning
rejects repeated vendor/model identities. Recognition and resume accept the
same exact flat shape, snapshot it once, and reject only definite duplicate
routes: the same vendor/model plus the same settings object. Empty, nested,
mixed, lazy, subclassed, tuple, and custom iterable shapes fail complete
preflight with zero provider calls and no output/state creation.

Each unresolved slot traverses the supplied candidates serially and circularly
at most once, beginning at the last provider that succeeded during this
invocation. A whole-slot failure does not move that preference. Fresh and
resume calls both begin at candidate zero; no cursor, provider blacklist, retry
history, or settings identity is persisted. Traversal stops immediately on the
first success. Successful fallback remains a normal complete/partial result
according to slot settlement and adds one aggregate warning plus ordered,
bounded `provider_failures` facts. A fully failed slot retains only its final
provider/code/safe-description terminal evidence in the existing failed-slot
record; later slots still run.

Both admitted presets still have empty retry mappings, and current evidence
does not provide a trustworthy same-model retry count or delay. This slice
therefore adds no retry executor, sleep, disposition scheduler, nested lane,
parallel pool, or new state schema. Focused flat-list, rotation, exhaustion,
preflight, batching, and resume regressions pass, and the complete offline suite
is **1,644 passed / 57.49s**. The next gate is one bounded real flat-fallback
proof; finite retry remains a separate evidence-led sub-slice rather than an
automatic consequence of list support.

### #674 closes the real serial flat-fallback gate

`tools/run_google_genai_flat_fallback_smoke.py` fixes one content-free live
scenario instead of adding another product abstraction. It supplies one real
archive image to a two-candidate Google lane: a locally valid but deliberately
unserved model first, followed by the live-proven `gemini-2.5-flash`. The runner
accepts no model/task choice, never reads a credential store, and reports no
path, image content, Markdown, provider description, raw response, or secret.
It requires exact candidate/failure order, one aggregate warning, one settled
slot, one generation call, one successful-model usage row, byte-identical
returned/published Markdown, unchanged source bytes, and removed state.

The credential-free gate returned `CONFIG_MISSING`, numeric exit 1, zero
provider calls, unchanged source bytes, no Markdown, and one initial sidecar.
After that exact scratch was reviewed and removed, one child-only live run used
the active HTTP proxy. The deliberately unserved candidate produced one safe
slot-0 `PROVIDER_UNAVAILABLE` record without a generation call; the second
candidate completed exactly one generation. The public result was `complete`
with one fallback warning, 595 input and 12 output tokens, a 47-byte published
Markdown, no sidecar, and unchanged source bytes. The child exited 0 and ended;
the apparent five-byte stderr file was only its PowerShell wrapper's UTF-8 BOM
plus CRLF, not provider/runtime diagnostics. All exact TEMP evidence was then
removed file by file.

No production runtime or schema changed. The live result proves serial
ProviderError fallback, stop-on-success, accounting, warning metadata,
publication, cleanup, and source integrity; it does not prove that immediate
same-model retry helps. Phase 4's flat-fallback half is closed. Retry maps stay
empty until a separately bounded real failure/recovery observation supplies a
finite count and wait; nested lanes, pools, audio, repair, and video deletion
remain later gates.

### #675 adds only the explicit audio-range planning boundary

The next replacement slice is package-root `split_audio()`. It accepts the
library's current MP3 source plus either exact `interval_minutes` or a validated
scalar/flat provider lane. Exact `-1` means one whole-source range; a positive
exact integer means that many minutes; an explicit interval wins when both are
present. If only providers are supplied, planning uses the smallest positive
integer `default_audio_minutes` across all candidates. Every supplied candidate
must support audio, and invalid topology, duplicate planning identity, missing
arguments, or an invalid interval fails before source decoding.

The result is an exact tuple of immutable `AudioSlice` values carrying source,
ordered index, logical result bounds, and the existing 30-second context-padded
read bounds. Planning accepts short MP3s, fully decodes for duration, and applies
the product's 2 GB input safety boundary and inclusive ten-hour ceiling. It does
not apply Google's narrower 9.5-hour whole-request limit; provider hard limits
belong to later recognition. It creates no physical clips, output, checkpoint,
cleanup registry, provider call, retry, or second planning object.

An adversarial review caught one concrete contract leak: non-path objects had
escaped as native `TypeError`. They now fail as `InvalidSource` with
`SOURCE_INVALID`. Focused audio/provider/import regressions pass **47 tests /
1.18s** and the full offline suite passes **1,656 tests / 65.52s**. No live API
call belongs to this provider-free planner. The next replacement slice is the
smallest scalar merged-audio recognition/resume consumer of these stable range
identities; retry execution, nested pools, repair, and old-video deletion remain
gated.

### #676 ships the scalar merged-audio recognition/resume owner

Package-root `recognize_audio_to_markdown()` now consumes the exact nonempty
`AudioSlice` tuple produced by `split_audio()`, one scalar audio-capable
`ProviderModel`, and one optional Markdown target. It validates the complete
slice plan, decoded source, output plus sidecar, and provider route before
generation; reserves every ordered range in one versioned sidecar; attempts
each unresolved range once; checkpoints settled, no-speech, or failed outcomes;
and publishes one ordered Markdown. `resume_audio_to_markdown()` requires the
same source bytes and exact ranges, reuses settled slots, and dispatches only
failed or unresolved slots. Complete work removes state, mixed work publishes
explicit failed-slot markers and retains state, and zero settlement retains
state without creating a new Markdown and raises `AllCandidatesExhausted`.

The first slice is deliberately scalar and serial. It has no provider list,
fallback, retry/wait rule execution, nested lane, concurrent scheduler, repair,
physical pre-splitting, generic media job, or old-video integration. Short
whole-file input (at most 300 seconds) preserves the existing inline Google
transport; longer whole-file input and explicit interval slices preserve the
existing Google Files lifecycle. Only one interval clip exists at a time and is
deleted by the existing context manager. Usage remains cumulative per exact
provider/model with unknown token dimensions kept as `None`.

Focused audio/image/output/import regressions pass **98 tests / 3.53s**. A
90-second authorized archive-derived MP3 was planned as two one-minute slots.
The bounded live Google operation produced both ordered transcript slots,
published 1,171 bytes, removed its complete-state sidecar, and left the source
unchanged. The scenario process then exited 1 only because its safe reporter
attempted to JSON-serialize immutable `mappingproxy` usage rows after the
library had returned; the tool now projects those rows to ordinary safe dicts.
The API operation was not replayed. This is complete recognition evidence with
an honest harness-reporting defect, not a provider/runtime failure. Flat audio
fallback and retry remain later separately evidenced slices.

### #677 closes the scalar short-whole live gate without runtime expansion

The maintained merged-audio runner now accepts exact `interval_minutes=-1` as
the already-public whole-source plan and emits safe planning mode plus decoded
duration facts. Its immutable usage projection was separately exercised before
the provider call; no fake live pytest or second runner framework was added.

One existing authorized 123.9707-second speech MP3 first reached
`CONFIG_MISSING` through the public whole path with zero calls, no Markdown, one
unresolved sidecar, and unchanged bytes. One subsequent credential/proxy-
isolated child then completed with native exit 0: one whole slot, one generation,
4,009 input and 69 output tokens, zero warnings, a 337-byte Markdown matching
the returned result, no remaining sidecar, unchanged source, and fixed-runner
`gate=passed`. The source code's <=300-second whole branch and the existing
SDK-boundary assertion together identify the inline route; no transport debug
field was added to the public result merely for this gate. No retry, fallback,
resume, model switch, or second live child was invoked by the scenario.

The delegated controller initially had one complex launch command rejected
before startup; the split controller then ran exactly one Stage A and one Stage
B child. An early report incorrectly claimed Stage A artifacts had been deleted;
timestamps and direct follow-up established they had never been deleted or
recreated. Primary review confirmed safe JSON, state schema, output digest,
source size/hash, and zero remaining runner processes. All four owned evidence
files were then removed from the exact TEMP root. Production code, API, schema,
tests, provider policy, and the frozen video family are unchanged.

### #678 adds and live-proves serial flat fallback for merged audio

`recognize_audio_to_markdown()` and `resume_audio_to_markdown()` now accept the
same exact scalar-or-nonempty-built-in-flat-list provider shape as merged images.
Complete preflight snapshots the lane and validates every candidate's audio
capability and admitted adapter before source decoding, output/state creation,
or provider work. Invalid, empty, nested, lazy, subclassed, mixed, tuple, and
definite duplicate routes fail with zero calls.

Each unresolved audio slot traverses the lane circularly at most once from this
invocation's last successful provider and stops at its first speech or no-speech
settlement. A wholly failed slot does not move the start preference and retains
only its terminal candidate in durable slot state; later slots still run. Fresh
and resume invocations begin at candidate zero, settled slots are reused, and no
cursor or per-attempt ledger is persisted. Successful fallback adds the existing
single warning and bounded ordered `provider_failures`; usage remains cumulative
per exact provider/model. The audio-specific interval materialization, inline/
Files selection, cleanup, checkpoint, and publication paths remain unchanged.

Focused public audio/planning/import tests pass **33 tests / 2.21s**. The fixed
merged-audio runner gained only a fresh `--flat-fallback` scenario with one
locally valid but intentionally unserved Google candidate followed by
`gemini-2.5-flash`. After a corrected zero-call gate, exactly one live child
completed one 123.9707-second whole slot: the first candidate produced
`PROVIDER_UNAVAILABLE` before generation; the second made one generation with
4,009 input and 59 output tokens. The result was complete with one warning and
one failure record, matching 263-byte Markdown, removed state, unchanged source,
empty stderr, and runner exit 0.

The first delegated zero-call child accidentally used stale
`local-bench-ocrllm` site-packages and failed import; no credential or provider
was reached. The corrected child used the explicit OCRLLM environment. Its
successful initial state was then mistakenly reported as a mismatch by the
controller even though fresh recognition is required to reserve state before
credential resolution; primary review corrected the predicate before the only
live child. Eight owned evidence files were reviewed and removed. No production
defect, retry/sleep, nested lane, concurrent pool, schema change, generic media
executor, repair, or frozen-video edit was added.

### #679 closes the real ordinary merged-audio resume gate

The maintained merged-audio runner now has one fixed fresh-only
`--unserved-only` mode. It uses the same local audio-capable model deliberately
absent from the current Google catalog, requires zero generation calls, reports
only safe provider mode and terminal failed-slot identity, and remains mutually
exclusive with flat fallback and resume. Expected recognition failure keeps
exit 1; the tool does not relabel an incomplete product result as success.

One credential-free preflight first returned `CONFIG_MISSING`, calls 0, no
Markdown, one 826-byte unresolved whole state, and unchanged source. One
credential-isolated live fresh child then reached the real catalog, produced
top-level `ALL_CANDIDATES_EXHAUSTED` with terminal slot-0
`PROVIDER_UNAVAILABLE`, made zero generations, wrote no Markdown, and retained a
946-byte failed state with empty usage. After primary state/source review,
exactly one live resume child used the same source/ranges/output with scalar
`gemini-2.5-flash`. It made one generation, reported 4,009 input and 61 output
tokens, published matching 297-byte Markdown, removed state, returned complete
with no warning/failure rows, preserved source bytes, and exited 0.

This is ordinary resume evidence, not retry or fallback: the failed live child
ended before the later resume invocation, no settled slot was replayed, the
changed provider was caller-supplied, and historical usage correctly remained
empty because the first provider made no generation call. No production code,
API, schema, test, retry/sleep, nested lane, pool, repair, or video deletion
changed. Eight owned evidence files were reviewed and permanently removed.

### #680 deletes the superseded combined-video lifecycle

Two independent read-only audits and primary reverse-reference review rederived
the #635 manifest against current code before deletion. All 34 production files
still formed one closed old recognition/journal/result/audio-wrapper family;
their only external production consumer was the six package-root exports. No
additional old-video module was found. The complete provider-free `video/`
package, `inspect_video`, `extract_video_frames`, `extract_video_audio`,
`RetainedVideoFrame`, `VideoInfo`, video errors, and the `video` extra remain.

The 34 files, six root exports, twelve dedicated tests, and obsolete Google
combined-video runner are removed without a compatibility wrapper. Three mixed
tests were narrowed rather than deleted: extraction no longer calls the retired
frame recognizer; lightweight import keeps the retained video values/functions;
and the installed gate replaces combined recognition with the visible
`extract_video_frames -> batchify_images` and
`extract_video_audio -> split_audio` flow. Root/package READMEs were reduced to
current product guidance, leaving historical evidence in the work log and
migration records. The pre-gate diff removed 14,297 lines while adding 375 lines
of current docs/gate code.

Focused retained video/import/gate tests pass **66 tests / 5.65s** and wheel/
typing selection tests pass **3 / 0.07s**. Full test collection imports cleanly
at **1,451 tests**. Current source/test/tool/README references to the deleted
public names and journal modules are zero. Compileall and diff checks pass.

The maintained clean-archive installed gate then passed from temporary commit
`ef6d693`: **1,450 passed / 1 expected RapidOCR skip**, fixture and compile
checks, a 311,950-byte wheel, a 1,594,390-byte base target, both import budgets,
and every optional profile. Installed deltas were audio 91,492,461; image
17,292,745; OCR 328,905,419; image+DashScope 41,778,311; Google 41,920,036;
audio+Google 130,530,294; PDF vision 25,491,526; video 254,784,582; and combined
video+audio+image 272,656,687 bytes. The installed visible video flow returned
two frames, one image batch, and one whole audio slice. The gate cleaned its
proof root; its reviewed external log was also removed.

A separate no-network/no-deps wheel proof then inspected the same 311,950-byte
wheel (SHA-256 `6C6BB751...128FE`): all 34 deleted production paths were absent,
the five retained video entry/type paths were present among 314 members, and a
fresh isolated install exposed the retained API while all six deleted package
attributes and module specs were absent. No heavy optional module loaded. The
50,346,025-byte proof root was reviewed and removed.

No provider call, crop/ROI change, nested lane, retry, repair, worker/contracts
edit, or replacement combined-video abstraction entered the deletion. Public
extraction outputs remain caller-owned and independent image/audio recognition
continues through the already-proven merged APIs.

### #681 ships and live-proves fixed nested image lanes

Image planning, fresh recognition, and resume now accept the third exact provider
shape: one nonempty exact built-in list of nonempty exact built-in lists. One
new nonrecursive topology normalizer snapshots scalar, flat, or nested input to
private tuple lanes, rejects mixed/deep/empty/subclassed/tuple shapes, rejects
definite duplicates only within each lane, permits cross-lane reuse, and rejects
more than 32 lanes before media/output/provider work. The older flat-only helper
is reduced to a thin wrapper over that single rules owner, so audio remains
scalar/flat without duplicating validation logic.

For `N` lanes, absolute slot `i` stays with lane `i % N`. One lane thread runs
only its fixed slots and serial candidate fallback; lane-local last success never
affects another lane and resets to candidate zero on every fresh/resume call.
There is no global epoch barrier, work stealing, cross-lane rescue, queued-slot
fairness layer, or persisted lane/provider cursor. A private image-specific state
owner locks only the latest immutable state/usage merge plus atomic sidecar
replacement. Provider/media work remains outside the lock. Every failed or
successful candidate is checkpointed before that lane advances, preventing stale
parallel writes and preserving paid-call evidence. Usage rows are deterministically
ordered from absolute slot/lane candidate order rather than completion timing.

SDK-boundary concurrency tests prove lane 0 owns slots 0/2, lane 1 owns 1/3,
lane 1 can start slot 3 before lane 0 finishes slot 0, a fully failed lane-0 slot
is not rescued by lane 1, reverse completion still publishes original slot order,
and calls/tokens are counted once. A changed three-lane resume reuses three settled
slots and dispatches only absolute slot 2 to lane 2. Exact shape/default/bound,
flat audio compatibility, and lightweight import neighbors also pass. The final
focused set is **50 tests / 2.77s**.

The maintained merged-image runner gained only fixed fresh `--nested-lanes`:
the existing two batches of eight use two one-model lanes, intentionally reusing
the same live-proven Google model across lanes. After a zero-call nested preflight,
exactly one live child completed in 16.6 seconds with lane count 2, two settled
slots, two generation calls, 4,802 input and 911 output tokens, no warnings,
matching 1,863-byte Markdown, no sidecar, unchanged 16 sources, empty stderr,
and exit 0. Aggregate live metadata does not claim timing overlap; concurrency,
assignment, and no-rescue are proved only by the controlled SDK trace.

Three delegated launch wrappers and one primary JavaScript string failed before
any child/API start; a later PyQt-based credential read also stopped before child
because that environment intentionally lacks PyQt6. The sole live child used the
known exact Windows QSettings registry location without installing UI dependencies.
All eight owned evidence files were reviewed and permanently removed. No audio
nested lane, generic scheduler, retry/sleep, worker/contracts edit, repair, new
preset, or public lane telemetry was added.

### #682 ships nested audio lanes; the real success gate remains open

`split_audio()`, fresh merged-audio recognition, and resume now accept the same
exact scalar/flat/nested provider topology as merged images. Omitted interval
planning flattens all validated lanes only to select one common smallest positive
integer-minute default; explicit `-1` or positive minutes still wins. The shared
nonrecursive normalizer owns exact lists, 1–32 lanes, lane-local duplicate
rejection, and cross-lane reuse. Audio no longer needs the flat restriction
wrapper.

Absolute audio slot `i` stays with lane `i % lane_count`. One thread per active
lane processes one request-owned slot/clip at a time, and candidates remain
serial within that lane. Whole mode naturally activates only lane 0 because it
has one slot. Interval mode may hold one materialized clip per active lane; no
other intervals are prebuilt. No epoch barrier, stealing, cross-lane rescue,
global queue, or persisted topology/cursor exists. Speech and exact no-speech
both settle a slot and update only lane-local preference.

One audio-specific locked owner merges the latest immutable slot state, cleanup
flag, and usage before every candidate advance and atomically replaces the one
sidecar. Provider upload/generation/delete and FFmpeg materialization remain
outside the lock. Image and audio now share only deterministic provider-model
usage merging/order through `provider_model_usage.py`; they do not share a
scheduler, slot type, snapshot, response, or state owner.

Real-FFmpeg plus fake Google SDK tests prove lanes 0/1 own slots 0/2 and 1/3,
lane 1 progresses while lane 0 blocks, no rescue occurs, lane-local fallback and
no-speech settle correctly, four logical slots create four unique clips despite
six provider attempts, at most two clips/uploads are active, every upload/delete/
client/local clip is cleaned, Markdown and usage remain deterministic, and a
changed three-lane resume dispatches only absolute slot 2 to lane 2. Nested
planning defaults and invalid topology/bounds also pass. The final image/audio/
planning/import set is **53 tests / 4.04s**.

The maintained audio runner gained only fresh `--nested-lanes`, fixed to two
identical Google lanes and a multi-slot positive interval. Credential-free
Stage 0 over the authorized 124.012-second MP3 proved nested/lane-count-2
`CONFIG_MISSING`, calls 0, no output, and a 1,384-byte state with three unresolved
slots/empty usage/source integrity; its safe stdout was not preserved, but state,
exit, stderr, and source facts were independently reviewed, so Stage 0 was not
replayed.

The sole live child ended honestly rather than passing: slots 0/1 recorded
`PROVIDER_NETWORK`, slot 2 `PROVIDER_RATE_LIMITED`, top-level
`ALL_CANDIDATES_EXHAUSTED`, exactly one confirmed generation call with unknown
tokens, no Markdown, a retained 1,725-byte three-failed-slot state, unchanged
source, no cleanup failure, and no runner/interval/snapshot residue. The SDK also
warned that both Google credential environment variables were present; values
were not exposed. This real evidence validates bounded nested failure settlement
and resume state, not successful nested recognition. Do not run another fresh
call. The exact external state/log/output root is retained for the next atomic
ordinary-resume gate after the rate/network condition changes.

No retry/sleep, audio format, generic scheduler, repair, worker/contracts edit,
public lane telemetry, or provider preset was added. Three unrelated 2026-08-25
`ocrllm-audio-repro-*` directories were observed and deliberately left untouched;
they are not #682 residue.

### #683 closes the real nested-audio success gate through ordinary resume

The retained #682 state was revalidated before credential access: exact
1,725-byte/SHA-256 identity, interval mode at one minute, three terminal failed
slots (`NETWORK`, `NETWORK`, `RATE_LIMITED`), one historical Google generation
with unknown token dimensions, no cleanup failure, unchanged source fingerprint,
no output, and no running child.

The maintained audio runner now permits `--nested-lanes` with `--resume` and adds
one nonnegative `--expected-historical-calls` assertion. Fresh flat/unserved-only
failure modes remain incompatible with resume. This is evidence tooling only;
production topology, state, execution, and provider policy are unchanged.

Exactly one credential-isolated resume child used the same source, three saved
slices, two lanes, and Stage 1 output/state. It exited 0 with `gate=passed`:
three settled slots, three current generation calls, 7,600 input and 50 output
tokens, the one historical call retained with unknown tokens, zero reused slots,
no failures/warnings, matching 308-byte Markdown, removed state, unchanged source,
empty stderr, and no process residue. No fresh re-plan, fallback, model switch,
retry, or second resume occurred.

Primary review verified disk/result hashes and source identity without opening
the transcript. The complete six-file, 5,550-byte #682/#683 evidence root and its
three stage directories were then permanently removed. The nested-audio live
success gate is closed; this does not supply same-model retry evidence or justify
retry/sleep policy.

### #684 publishes the stateless one-branch `resume_video()` router

Package-root `resume_video()` now takes exactly `source`, required exact
`media_type="image" | "audio"`, required `providers`, and optional
`output_path`. It does not accept an original video, paired branches, timeout,
resume flag, batch/interval setting, output pair, journal, composer, cleanup
owner, or result wrapper. Image source is an exact nonempty tuple of nonempty
exact path tuples. Audio source is the exact nonempty `AudioSlice` tuple already
used by the ordinary audio owner. The older #633 allowance for a bare audio Path
is narrowed: silently splitting it would re-plan whole versus interval state and
violate the visible planning boundary.

The router validates the exact discriminator and shallow media category before
lazy-importing one ordinary resume facade. It passes the provider tree and output
unchanged, returns the same `RecognitionResult` object, and catches/translates no
delegated error. Filesystem, same-source/range, provider capability, output,
sidecar, publication, and cleanup validation remain solely with the chosen
ordinary owner. It never imports or runs the other branch.

Existing image and audio resume feature tests now consume the router for one
nested successful recovery each. A fresh-process import/validation scenario
proves invalid discriminator and cross-shaped sources fail with typed zero-call
errors before image execution or audio job helpers load. Package-root binding
remains lightweight. The focused set passes **29 tests / 3.97s**. No provider,
media, output, state, dependency, worker/contracts, compatibility, composition,
or video lifecycle was added.

### #685 refreshes the clean installed-wheel acceptance gate

The existing combined installed-profile smoke now imports the public
`resume_video` symbol and requires it to be callable. Its visible video flow
still extracts frames and audio without provider work, but image batching and
audio splitting now receive an exact two-lane nested plan made from the proven
Google preset. This exercises common-minimum provider planning from the
installed wheel while retaining the assertion that `google-genai` is not
installed or imported by the combined media profile. It does not call the
router, an adapter, or a provider.

The focused gate/wheel/import set passes **26 tests / 3.08s**. The maintained
clean-archive gate then passes from commit `fa01f94`: **1,457 passed / one
expected RapidOCR skip**, a 316,624-byte wheel, a 1,626,648-byte base target,
both import budgets, and all nine optional profiles. The visible installed
flow returns two frames, one provider-derived image batch, and one
provider-derived audio slice. No runtime source, dependency, media algorithm,
provider call, retry, state, repair, worker/contracts surface, or second gate
runner changed.

### #686 reconciles repair with the surviving Markdown and current PDF path

Current merged-image partial output identifies each failed slot and exact source
index range. Current merged-audio partial output identifies each failed slot and
places its logical second range in the immediately adjacent library heading.
Under the maintainer's explicit experimental-repair trust boundary, those
strict markers plus caller-supplied current sources are sufficient to select
work after a sidecar is lost. Repair does not gain source hashes, saved prompts,
provider identity, interval parameters, another partial schema, or legacy
format support. Zero-settlement operations publish no Markdown and are not
repairable after state loss.

The current PDF facade cannot yet produce that input: it renders at most eight
pages per group through the older Config path, fails fast, and combines page
markers only after every group returns. A privacy-bounded marker-only scan of
the authorized archive found four Markdown files / 6,409 lines but no OCRLLM or
legacy failure marker, so no real production document closes the PDF API choice.
Before implementing PDF repair, the maintainer must choose visible caller-owned
PDF page extraction composed with the merged-image APIs (recommended), or a new
one-call provider-model PDF owner with deterministic retained pages and cleanup.
No runtime, parser, artifact, provider call, test, or source mutation changed in
#686.

### #687 turns the PDF choice into concrete ownership and fixes current docs

Route A needs one provider-free `extract_pdf_pages()` owner plus a package-root
export. It can reuse unchanged snapshot/inspection and the unchanged transient
eight-page renderer: move each validated group into one private staging tree,
then publish one complete caller-owned same-stem directory. It returns exact
ordered PNG paths; current `batchify_images()` and merged recognize/resume own
everything later. There is no page DTO, manifest, provider parameter, PDF state,
or automatic deletion after publication. Existing PDF tests must be extended
rather than adding a one-test-file-per-function mirror, and the installed
`pdf-vision` profile supplies the real provider-free gate.

Route B needs more than fresh/resume wrappers. It must keep all public provider
topologies, plan PDF-specific output/page ownership, retain pages through
partial and zero settlement, adapt image results to PDF, and clean known files
only after complete publication. Current merged state fingerprints only the
rendered PNG leaves; it does not bind the explicit original PDF required by a
PDF resume call. Route B therefore needs a PDF source-identity owner, retained
source snapshot, or full rerender comparison. A scalar-only facade or resume
without explicit source would narrow already-fixed product contracts and is
rejected.

No renderer retention flag, generic directory publisher, common page state, or
other route-independent runtime change is justified before the maintainer
chooses. Main review did reproduce one current documentation defect: root
README described the future merged-image PDF route as shipped. It and the
active-library guide now state that the direct PDF facade still uses the older
Config/injected-provider grouped image path. #687 changes documentation only.

### #688 ships strict state-loss repair for merged images

Package-root `repair_images_to_markdown()` accepts the exact current batches,
scalar/flat/nested provider topology, required image task, optional existing
Markdown target, and timeout. It is available only when the ordinary sidecar is
absent. A present sidecar rejects before dispatch and directs the caller to
ordinary resume. It trusts the caller's current batches as explicitly approved;
it adds no historical source hash, task/provider snapshot, partial schema,
repair sidecar, or legacy parser.

One narrow parser accepts only complete library failure sections whose heading,
one-based slot, flattened source range, provider error code, order, and unique
comment exactly match the supplied batches. Missing, malformed, duplicate,
or all-failed documents are not repair input. After complete provider/task/
source/output/marker preflight, repair visits only failed absolute slots
serially. Slot `i` keeps lane `i % lane_count`; each lane has one invocation-
local last-success cursor and serial fallback. A whole failed slot leaves that
cursor unchanged.

Each successful provider result replaces exactly its failed comment through
the existing atomic writer while its immutable image snapshot is still alive.
Therefore a later provider failure or snapshot-cleanup warning cannot erase or
cause replay of earlier paid content. Failed markers remain unchanged; the
returned partial result records only current terminal failures, current calls/
tokens, bounded successful-fallback facts, and cleanup warnings. Historical
usage is not inferred from Markdown. Image/audio executors and repair now share
one 50-line provider failure evidence reader, removing their duplicated usage/
cleanup/description parsing without sharing media execution.

Three SDK-boundary public scenarios prove immediate paid-success persistence,
flat lane rotation, absolute nested assignment, a later repair of only the
remaining marker, source integrity, optional output resolution, and zero-call
state/marker rejection. The final focused image/audio/import/wheel set passes
35 tests. The maintained live runner gained one fixed partial-state-loss repair
mode. Its sole two-by-eight-image child proved the intended fresh partial setup,
then repair returned honest partial rather than success: one failed marker
remained, the 1,047-byte Markdown survived, state was absent, stderr was empty,
and no retry occurred. The original runner collapsed that useful result into
`INCOMPLETE_LIVE_EVIDENCE`; it now preserves safe partial repair calls/usage/
code/source facts on future runs. No production change is justified by the
provider failure, and the bounded live repair-success gate remains open.

### #689 ships strict range-derived repair for merged audio

Package-root `repair_audio_to_markdown()` accepts one explicit original MP3,
scalar/flat/nested provider topology, optional current Markdown target, and
timeout. It requires the ordinary sidecar to be absent and restores no saved
mode, interval minutes, prompt version, provider, token history, or source
identity. The media-neutral 44-line repair reader now owns the identical
state-absent/existing-UTF-8-output rule used by both image and audio facades.

The audio parser validates every current OCRLLM slot heading, requiring exact
one-based order, contiguous three-decimal logical ranges from 0.000 through the
decoded source duration, and at least two slots with at least one settled slot.
Only immediately adjacent failed comments with matching unique ordered indexes
and canonical provider codes are repair markers. The final three-decimal end is
clamped back to exact decoded duration. Each failed range receives the existing
fixed 30-second context; no saved splitter parameter is consulted.

Whole recognition has one slot, and zero settlement publishes no Markdown, so
there is no honest whole-audio repair input after state loss. Repair therefore
uses only the existing interval prompt, FFmpeg materialization, honest upload
snapshot, and Google Files transport. Remote delete/client cleanup remains
inside the adapter; returned cleanup facts are preserved. Speech and typed
no-speech both atomically replace their comment while the local clip and outer
source snapshot are still alive. Repair remains serial, keeps absolute nested
lane assignment and invocation-local rotation, and returns current-only calls/
tokens, successful-fallback facts, remaining terminal failures, and cleanup
warnings without creating state.

Three public scenarios use real FFmpeg plus the Google SDK boundary to prove
no-speech paid-success persistence before a later full-slot failure, flat lane
rotation, a second repair that touches only the remaining range, absolute nested
assignment, balanced upload/delete/client/local-clip lifecycle, unchanged source,
optional output resolution, and zero-call state/index/range/marker rejection.
The final merged audio/image/import/wheel/typing set passes 38 tests in 6.70s.
No live provider call belongs to this offline implementation slice; one bounded
two-call speech interval partial-then-repair gate is the next independent task.

### #690 closes the real merged-audio repair success gate

The maintained merged-audio runner now has one fixed `--repair` mode. It accepts
only one-minute planning, exactly two slots, one expected fresh generation, one
expected repair generation, zero reused/history, and no other scenario flag.
Fresh uses fixed nested lanes: `gemini-2.5-flash` owns absolute slot 0 and one
deliberately unserved model owns slot 1. Only after strict partial validation
does the runner delete its owned sidecar and invoke `repair_audio_to_markdown()`
with the proven model.

A Luna audit caught false-pass risks before live work: cleanup warnings were not
gated; safe row filters could drop malformed extras or accept negative tokens;
usage/model identity, residual markers, source type/output identity, and true
state-path absence were incomplete; Python booleans/floats could equal integer
counts; and error cleanup facts/source reads were underreported. The runner now
uses exact-type count checks, exact single Google usage/failure rows, warning/
provider-failure absence, `lexists`, marker absence, guarded reads, and safe
cleanup booleans. A valid-shape missing-source probe and invalid fixed-shape
probe both stop before provider work with content-free runner errors.

The first controller preflight used the wrong registry level and stopped before
any child/API. Correcting it to the authoritative QSettings `ui` subkey reused
the same owned excerpt and launched exactly one child; this was not a provider
retry. The child completed with direct exit 0: a 61.000-second, 16-kHz mono,
64-kbps speech MP3 produced two interval slots; fresh made one generation and
retained one unserved failure; repair made one generation with 1,201 input and
3 output tokens; both slots settled, warnings were zero, final Markdown matched,
the failure marker and state were absent, source/archive hashes were unchanged,
stderr was empty, and no runner process or credential residue remained. The
partial/final Markdown sizes were 215/157 bytes. Transcript content was not
reviewed. The runner now also emits the already-strictly-validated fresh usage
row on future runs; that numeric row was not retained by this invocation and no
API replay was made. The bounded audio repair live-success gate is closed.

### #691 hardens the image repair runner; controller launch remains open

Before a second image-repair live attempt, two Luna audits applied the #690
evidence standard to the maintained image runner. The old repair branch did not
strictly require media/profile/output/Markdown identity, source stability before
owned state deletion, zero warnings/provider-failures, exact integer counters,
provider identity in the unserved failure, final output/result bytes, failed-
marker absence, true `lexists` state absence, or complete cleanup facts. Its
repair error operation assignment was unreachable after an early return, and
partial diagnostics admitted unknown warnings.

The fixed runner now separates fresh orchestration, strict fresh validation,
owned state-loss mutation, final/partial gating, and repair error reporting.
Fresh requires one exact Google usage row, one exact unserved slot-1 failure,
zero warning/provider-failure rows, exact source/result/output/state facts, and
exact int counters. Complete repair requires audio-equivalent strict image
media/profile/target, one exact usage/call, marker/failure/warning absence,
changed byte-matching output, source stability, and `lexists` state absence.
Partial repair requires the fixed remaining slot, exact counts/output/marker/
source/state facts, and only the known remaining-slot/provider/snapshot warning
allowlist. Error summaries carry the correct repair stage and cleanup facts.
Missing-source and mutually exclusive-mode probes stop without provider work.

The delegated controller then selected the deterministic 16 authorized images
(141,975 candidates; first 16 by exact-extension lexical rule, 8+8), verified
1,642,612 aggregate bytes/hash, proxy, and key presence, but omitted the runner
script argument from the Python command. Python exited 2 during argument parsing;
the tracked runner and provider were never reached, output/state were absent,
sources remained unchanged, stderr was captured, process/credential residue was
zero, and no second child was launched. The no-second-child rule prevented an
in-iteration correction. This is a controller invocation failure, not Google or
library evidence. The evidence root was removed; the image repair live-success
gate remains open for one later correctly formed independent child.

### #692 proves delegated Windows argv assembly is the remaining live blocker

No runner or product change was needed after #691. The committed runner blob,
absolute path, and compilation were revalidated. A stricter external controller
manifest required the absolute runner after Python, two populated 8-image groups,
repair/timeout flags, nonexistent owned output/state, exact QSettings key/property,
proxy, zero processes, and exact command booleans before launch.

The first preflight again checked the parent registry key despite the explicit
`ui` subkey instruction and stopped before child/API. Correcting only the key
reused the exact deterministic sources. The controller then claimed
`python_first_argument_is_runner=true`, but its actual `ProcessStartInfo` set
Python as both executable and first argument. The one child therefore attempted
to parse the Python binary, exited 1 immediately, produced no safe runner stdout,
and never reached the tracked runner/provider. Actual-command evidence correctly
overrode the contradictory preflight claim. Sources remained 1,642,612 bytes
with unchanged aggregate hash; output/state/markers were absent, process and
credential residue were zero, and no second child was launched.

Two consecutive iterations now establish a subagent-specific mechanical block:
free-form Windows argv construction is not reliable enough for this live gate.
The next independent attempt changes workflow, not product: the primary agent
will construct and launch the exact child command, then delegate only waiting,
safe evidence collection, and cleanup to Luna. This preserves the maintainer's
request not to make the primary poll mechanical work while removing the proven
source of command mutation. The three-file, 3,320-byte evidence root was removed;
image repair live success remains open.

### #693 resolves command construction and records a real Google image timeout

The primary agent constructed one synchronous PowerShell session and delegated
only exit/process/evidence waiting to Luna. An initial `New-Item -LiteralPath`
compatibility error stopped before evidence/source/key/child work; replacing it
with `-Path` was permitted because no child existed. The corrected preflight
verified the committed runner blob, exact Python/runner argv order, two 8-image
groups, repair/timeout flags, owned absent output/state, exact QSettings key and
property, proxy listener, and zero matching processes. It then invoked exactly
`& $python @runnerArgs`, eliminating `Start-Process` argument rewriting. Luna
observed only the owned exit file/process; primary polled the live session once
after termination for direct stdout/exit.

The exact child reached the strict runner and provider. The served
`gemini-2.5-flash` slot made one generation but ended `PROVIDER_TIMEOUT`; the
deliberately unserved slot ended `PROVIDER_UNAVAILABLE` before generation. With
0/2 settled, `recognize_images_to_markdown()` correctly raised
`ALL_CANDIDATES_EXHAUSTED`, published no Markdown, retained a 5,730-byte v1
sidecar with both failed slots and one Google call with unknown token dimensions,
and never entered state deletion or repair. Cleanup failure was false, stderr
empty, direct exit 1, process absent, sources unchanged, and the credential was
absent from evidence. This is real provider failure and honest resume-state
evidence, not a controller/library defect or repair success.

No second child or immediate retry was made. Together with #688's later-stage
repair partial, this shows current Google image availability is unstable but
does not prove an immediate same-model retry count/wait. The image repair live-
success gate remains open and is deferred until a later provider-state change;
no production/runner fix follows. The five-file, 7,660-byte evidence root,
including private source URIs, was permanently removed after safe state review.

### #694 proves both repair facades ship in the clean dependency-empty wheel

The maintained clean-archive gate now imports both package-root repair facades
from the installed dependency-empty wheel and calls only failure-before-dispatch
inputs. Empty image batches and a missing audio source return typed errors with
exact zero provider calls, create no output/state, and do not import optional
Google/OpenAI/image/audio/PDF/video/UI modules. The first exact installed probe
exposed one real image preflight defect: all three merged-image batch-shape
errors correctly rejected input but omitted `provider_calls_attempted=0`. The
shared normalizer now supplies that fact at each error source; no facade wrapper
or generic error framework was added.

The 320 KiB wheel budget was met through evidence-backed reduction rather than
raising the cap: remove one consumer-free single-lane normalizer already
superseded by the general exact-lane normalizer, stop storing two marker fields
that are validated but never consumed, share four identical usage projections
in the existing usage module, and stop duplicating each public attribute name in
the lazy import map. The exact `21ab952` archive gate passes 1,464 tests with one
expected RapidOCR skip, every optional profile, a 327,187-byte wheel, a
1,681,609-byte base install, and the installed visible video frame-batch/audio-
slice flow. Provider behavior, dependencies, state schemas, and media APIs are
unchanged.

### #695 reaches real image repair again and records quota exhaustion honestly

Forty-seven minutes after #693, the unchanged committed repair runner reused the
same deterministic two batches of eight authorized images. A credential-free
preflight first returned `CONFIG_MISSING`, exact calls zero, unchanged sources,
no Markdown, and one owned unresolved sidecar; the sidecar was inspected only
for safe counts and removed before live work. One and only one credential-
isolated child then ran through the required proxy.

Fresh recognition succeeded for the served lane with one generation and
2,401/816 input/output tokens; the deliberately unserved lane left the expected
partial marker. After the runner deleted only its owned sidecar, repair made one
real `gemini-2.5-flash` generation but Google returned canonical
`PROVIDER_QUOTA_EXHAUSTED` with unknown token dimensions. The public repair
result remained honest partial: its 1,805-byte Markdown stayed byte-identical to
the pre-repair partial, one failed marker remained, state was absent, sources
were unchanged, cleanup warning was false, direct exit was 1, and no credential
was persisted. No retry, second child, fallback, model switch, or production fix
followed. This proves the live repair path reaches its provider boundary but
does not close the success gate; do not immediately replay it while quota is
exhausted.

### #696 proves full-frame extraction on one real 161-minute archive video

The provider-free visible-video boundary had synthetic unit/install evidence but
no maintained explicit-source real-video scenario after deletion of the old
recognition chain. `tools/run_video_frame_extraction_smoke.py` now calls only
package-root `inspect_video()` and `extract_video_frames()`, requires a new
caller-owned output directory, and reports content-free source/output/ordering/
dimension/residue facts. It keeps output for inspection; the external owner
cleans it. Full-source SHA-256 is checked before and after, while failure
summaries also expose staging residue. The tool does not instrument private scan
functions or attempt to detect board/crop geometry.

No archive MP4 met the initial 20–120 minute and 50–750 MiB bound. After rejecting
one out-of-bound selection and confirming 71.6 GB free TEMP capacity, the single
run used the only already-inspected candidate: a regular non-reparse 2.665 GB,
161.39-minute, 1920x1080 MP4. It completed in 57.78 seconds. The public path
bounded itself to a 1,938-sample upper limit, published 82 ordered full-resolution
JPEGs / 23,421,340 bytes, retained the true final frame, left no snapshot/staging
residue, and preserved the source's exact SHA-256. Output density was 30.48
frames/hour; the first retained segment-end representative was at 155.008
seconds.

That first timestamp alone does not prove content loss: the current selector
deliberately represents a stable segment by its final candidate, and recognized
content was not opened. It does prove the current selector remains target-
density-driven through 28–40 frames/hour, a time-based stable-segment cap, and a
final uniform cap path. Do not silently replace that policy from one metadata
run. Any later content-driven-only change must be an explicit maintainer choice
and must compare actual retained/missed lecture content. Runtime, dependencies,
public APIs, provider behavior, and selection code are unchanged; adjacent
inspect/extract tests pass 33.

### #697 proves real video-audio extraction and descriptor planning separately

The sibling provider-free visible-video branch now has its own explicit-source
scenario rather than being folded into the frame runner or a replacement video
black box. `tools/run_video_audio_extraction_smoke.py` calls only package-root
`inspect_video()`, `extract_video_audio()`, and `split_audio()`. It requires one
new caller-owned MP3 target, verifies complete source SHA-256, output artifact,
typed failures and staging residue, and retains the MP3 for external review.
Whole, explicit 30-integer-minute, and Google-preset-default plans are compared
without importing `google.genai`, materializing interval clips, or dispatching a
provider.

One run reused the exact #696 real MP4 after metadata/path-hash revalidation. It
completed in 35.703 seconds and published a 38,734,640-byte mono 16 kHz MP3 with
9,683.4989375 seconds of decoded audio, only 0.0310625 seconds shorter than the
video container duration. Whole mode returned one exact descriptor. Explicit
30-minute mode returned six ordered contiguous logical ranges with the fixed
30-second physical context; the preset default returned the identical six
ranges and final logical end. Source SHA-256 remained exact, provider calls were
zero, Google SDK loading and snapshot/audio staging residue were zero.

No runtime defect was exposed. In particular, the scenario does not require
audio duration to equal video duration because a valid source may legitimately
have a shorter stream, and it does not pretend a hard-coded counter dynamically
monitors sockets. The provider-free call graph and absent provider SDK are the
network boundary. The exact 38,734,751-byte evidence root was removed after
review; adjacent extraction/planning tests pass 23. Runtime, dependencies,
public APIs, and provider behavior remain unchanged.

The destination is one visible, caller-composed pair of media flows:

```text
inspect_video -> extract_video_frames -> batchify_images
              -> merged image recognition/resume/experimental repair

extract_video_audio -> split_audio
                    -> merged audio recognition/resume/experimental repair
```

PDF reuses the merged image backend after page rendering. Image and audio own
separate plans, sidecars, Markdown outputs, providers, and resume calls. There
is no replacement `recognize_video` recognition/lifecycle black box. The thin
package-root `resume_video` route fixed by #633 delegates exactly one already-
extracted branch per call and owns no state, composition, or cleanup.

The deletion target is the currently shipped **video recognition/orchestration
family**: `recognize_video`, `recognize_video_to_markdown`,
`recognize_video_frames`, their image/audio job helpers, video journal/state,
video result composition/publication, `VideoRecognitionOutcome`, and the video-
specific audio recognizer. Keep provider-free `inspect_video`,
`extract_video_frames`, `extract_video_audio`, complete-frame selection, and
`RetainedVideoFrame`. `prepare_video_media` currently implements public frame
extraction and is not deleted merely because old recognition also consumes it.
The maintained safe sequence proves merged image, merged audio, and both resume
owners first, then deletes the old family in one migration stage with no
compatibility wrapper. Immediate capability removal remains an explicit choice
rather than an inferred consequence of "discard the chain."

### Verified old-video deletion manifest (#635)

A static AST import closure plus reverse-consumer review finds exactly 34
production files whose consumers are confined to the old video family (apart
from package-root exports). Delete them together after the replacement gate;
partial deletion would leave dead state/result modules:

```text
# public entry/result/publication
recognize_video.py
recognize_video_frames.py
recognize_video_to_markdown.py
compose_video_result.py
publish_video_result.py
video_recognition_outcome.py

# branch execution and old result evidence
recognize_video_job_audio.py
recognize_video_job_frames.py
finalize_video_job.py
attach_current_video_evidence_to_error.py
attach_video_frame_group_identity.py
read_video_frame_group_identity.py
group_retained_video_frames.py
processors/recognize_video_mp3.py

# old video journal, identity, and resume
build_owned_media_fingerprint.py
fingerprint_video_short_audio_request.py
hash_video_snapshot.py
load_video_job_state.py
parse_video_job_state.py
plan_video_frame_groups.py
prepare_video_job_audio_state.py
restore_video_job_frames.py
save_video_job_state_atomically.py
serialize_video_job_state.py
source_fingerprint_path.py
validate_video_job_resume.py
validate_video_job_resume_image_requests.py
validate_video_job_resume_request.py
video_audio_requires_credential_preflight.py
video_job_journal.py
video_job_state.py
video_job_state_file_limit.py

# video-only MP3 wrappers
audio/probe_video_mp3.py
audio/snapshot_video_mp3.py
```

The two generic-looking fingerprint helpers are not shared infrastructure:
current production references come only from the old video journal/branch
modules, and `source_fingerprint_path` reports a saved-video-specific error.
Conversely, keep the complete current `video/` package, `retained_video_frame.py`,
and `video_info.py`. In particular, `extract_video_frames` directly consumes
`video/prepare_video_media.py`; `extract_video_audio` consumes the video
snapshot/inspection/FFmpeg helpers. Keep the `video` optional dependency extra
and video error codes because provider-free inspect/extract still use them.

The eventual deletion commit also removes the six package-root exports
`recognize_video`, `recognize_video_frames`, `recognize_video_to_markdown`,
`compose_video_result`, `publish_video_result`, and
`VideoRecognitionOutcome`. It deletes the twelve tests dedicated only to this
family, while editing rather than deleting `test_extract_video_audio.py`,
`test_lightweight_import.py`, and `test_stage_m_offline_gate.py`. Replace the
old Google video runner and the combined section of the offline gate with the
already-proven visible replacement flows; update current READMEs and navigation
without rewriting historical diary evidence. `contracts/` and `worker/` import
none of the old modules and require no deletion-time change.

The deletion gate is therefore mechanical after product proof: merged image,
merged audio, and both ordinary resumes pass focused plus bounded live evidence;
the retained provider-free video tests pass; current source/test/tool/README
references to the six public names and 34 modules are zero; the full provider-
free suite passes; and isolated wheels prove base import, the `video` extractors,
the visible combined profile, and absence of deleted modules. Do not repeat a
paid old-video call merely to delete an already-superseded runner.

Public `extract_*` output is caller-owned because no library recognition
lifecycle encloses later calls. Only rejected frame candidates, source
snapshots, materialized audio slices, and other artifacts created and consumed
inside one library call are automatically removed. A future Python application
job may own and delete the public extraction outputs it requested; that does not
restore a library video wrapper or an Electron-owned provider call.

The primary provider boundary remains one immutable provider-model **instance**
for one exact `(vendor, model)`, not one Python class/file per catalog row. Its
complete target data is vendor, model, controlled `adapter_id`, three task-
capability booleans, capability-dependent image/audio defaults, immutable
finite canonical retry rules, and only the exact adapter settings required to
invoke that instance. There is no separate `ProviderBinding`, parallel settings
tree, or generic parameter list. A credential-free preset is directly usable
through the existing environment resolver. A caller that supplies an explicit
credential constructs a separate runtime instance with the same exact typed
settings; it never mutates a shared preset.

The entity's settings field is runtime-only: it is excluded from repr,
dataclass comparison/hash, generic serialization, batching identity, and
committed presets. The complete entity is never itself a resume document.
Resume derives a versioned secret-free request identity from vendor/model plus
only output-affecting safe adapter fields, following the current image
fingerprint precedent. API keys, credential/pool identity, and mutable pool
health never enter that projection. Existing DashScope credential-pool support
may remain inside its exact runtime settings, but the first entity slice adds
no new pool abstraction or pool persistence. The entity does not itself
implement splitting, dispatch, retry, fallback, pooling, resume, or repair.

The already-shipped `Config(provider=ExistingVisionClient())` injection route
remains unchanged as a second escape hatch. A caller-supplied object used as a
leaf in a **new** merged provider list will instead explicitly satisfy a later
small `ProviderAdapter` contract. That contract is not part of the first
provider-model or two-built-in scalar proof. Define it only in the same slice as
the first merged-list caller that actually consumes an injected leaf, and give
it only the task-specific identity, capability, invocation, and safe
error/usage members that caller needs. Missing required capabilities are a
configuration error; the new engine does not guess them through duck typing or
silently default them to false. Keep this protocol narrow and do not wrap
injected objects in a public entity hierarchy or predeclare unused audio,
retry, pool, resume, or cleanup methods.

That injected route is an in-process Python contract. Current `recognize()` and
`recognize_batch()` call it directly; the latter uses threads in the same
process. The frozen JSONL worker accepts only literal `provider="dashscope"`
and reconstructs `DashScopeSettings` in its spawned child, so it neither accepts
nor serializes an arbitrary provider object. Do not add callable pickling,
provider-object JSON, a worker compatibility shim, or a frozen-protocol change.
A future Electron/Python or Rust backend resolves a serializable provider/entity
choice inside its own backend process; the callable itself does not cross that
boundary.

Provider collections retain the fixed scalar/exact-flat-list/exact-nested-list
shape. Flat lanes stop at first success. Nested lanes have fixed absolute-slot
assignment and no cross-lane rescue. The provider-independent dispatcher must
not branch directly on raw SDK exceptions or pretend that one HTTP number has
the same meaning across vendors. A normalized model rule retains the maintainer's
three `error` / `next` / `current` policy labels plus finite retry/wait numbers;
the labels control reporting category, while the finite numbers control actual
attempts and delay. A media-size rejection does not silently re-batch: another
candidate may accept the same immutable slot; otherwise the unresolved slot
remains available for explicit resume with a new provider plan. Changing the
slot grouping is a new plan, not resume.

Token accounting is already fixed by #586 and is not another decision group.
Each future job sidecar keeps one cumulative row per exact `(vendor, model)`:
exact dispatched calls plus nullable input/output token totals. Every confirmed
dispatch contributes one call even when usage is absent; if any included call
lacks trustworthy input or output usage, that cumulative dimension is `None`,
not a known partial sum or zero. Pre-dispatch failures with zero calls add no
usage row. Trustworthy usage observed before a later response-validation error
is included once at the adapter boundary.

The cumulative value loaded at invocation start is the historical baseline;
only the current invocation's delta lives in memory. Before one lane advances
to another provider attempt, its newly observed cumulative evidence is saved;
already-running lanes do not wait at a global barrier. Ordered settled-slot
content, source/window identity, and Markdown remain separate resume state and
cannot be replaced by aggregate calls or tokens. Do not persist labeled
current/history duplicates, expose per-attempt billing rows, split one batch's
usage across media members, add prices, or create a global token manager.

Output ownership is already fixed and is not a sixth decision group. A scalar
source, or an `AudioSlice` tuple whose members all refer to that same original
audio file, defaults to its sibling `<normalized-source-stem>_ocrllm.md`. A
merged batch of distinct concrete media files may instead derive
`<normalized-folder-name>_ocrllm.md` beside its source folder only when every
leaf source has the exact same direct parent. If the parents differ, recognize,
resume, and repair require an explicit `output_path` and reject the complete
request before provider dispatch when it is omitted. The first member, a common
ancestor, a hash, or a directory scan never chooses the target. This rule
applies to every leaf of nested image groups, not only each group's first item.

The future fresh merged-image recognition call has one required explicit task
selector:

```python
image_task: Literal["plain_ocr", "detail_ocr"]
```

The value must be a plain `str` with one of those exact spellings. There is no
default, alias, case normalization, Boolean pair, automatic inference from the
selected model, or reuse of current `Config.image_mode` / `profile`.
`plain_ocr` requests ordered ordinary OCR text/Markdown without promising
formula, layout, or code reconstruction. `detail_ocr` requests the maintained
LaTeX/code-oriented detailed-image behavior; it does not prematurely promise
every future SVG or Mermaid feature. Callers do not supply a prompt through
this selector.

The complete scalar, flat, or nested provider shape is validated against the
selected task before adapter resolution, media work, output creation, or any
provider call. Every candidate in the supplied shape must support the task. One
incompatible candidate rejects the whole request with the existing
`ConfigError(code="CONFIG_INVALID")` and safe details naming the task and exact
model. It is not a provider runtime error and is never retried, skipped,
silently removed from a lane, or downgraded from detail to plain. A model value
claiming detail support without plain support is itself `CONFIG_INVALID` at
construction. Do not add a capability-error class/code, task registry, public
Enum, provider filter, or automatic task chooser: the existing configuration
code already gives the distinct code and description required from provider
failures.

`batchify_images` remains task-independent: it groups concrete media and may
consume the provider shape only to resolve a provider-derived batch-size
default. When omitted, all validated candidates reduce to one minimum positive
recommendation before slots exist; provider runtime settings still do not enter
batchification.
Fresh recognition persists the selected task as ordinary resume identity;
ordinary resume restores that task and rechecks newly supplied providers rather
than allowing a plain/detail switch. Experimental repair with a missing sidecar
does not justify a general task manifest in this slice; its exact task input is
left to the later repair consumer.

Settlement now reuses the existing result boundary rather than adding a new
result-bearing exception. If every slot settles, return `status="complete"`;
providers exhausted before a later success appear only as bounded warnings and
ordered safe metadata. If some slots settle and some remain unresolved, publish
the resumable failure markers/state and return `status="partial"` with only the
failed-slot evidence. If no slot settles, raise the existing
`AllCandidatesExhausted`. No path persists raw errors, retry history, media
paths, settings, accounts, or per-attempt token details as future routing
memory.

Do not make any of the following prerequisites for the first real image proof:

- a checked-in executable mirror of every current vendor model;
- flat fallback, nested provider lanes, a retry executor, or an API pool;
- a generic settings/options bag or public callable/plugin protocol;
- persistent per-attempt token/billing/error ledgers;
- merged audio, repair, Electron/Rust bindings, local-provider placeholders, or
  social-media work.

The maintainer has now closed all seven #646 decision groups:

1. Ship only a few presets admitted by at least one bounded real successful
   request. Discover the volatile catalog live; callers may explicitly construct
   an exact unpreset model at their own responsibility.
2. Provider audio recommendations and explicit caller intervals use exact
   positive integer minutes. Caller-only `-1` still means whole audio.
3. Do not add `ProviderBinding`. The provider-model entity is the first-class
   route; existing injected vision clients remain compatible, and new merged
   lists may later accept an explicit small `ProviderAdapter` escape-hatch
   contract. Create that contract only with its first real merged-list consumer;
   missing task capabilities then reject before dispatch.
4. Prove merged image/audio recognition plus resume parity, then delete the old
   video recognition family. The old Config-based `recognize` and
   `recognize_batch` line remains available.
5. When the caller omits image count or audio interval, resolve the minimum
   positive recommendation across every validated candidate exactly once before
   slot planning. Explicit values win.
6. Retain `error`, `next`, and `current` on finite retry rules. `error` is a
   high-visibility exhausted request error; `next` is ordinary provider advance;
   `current` denotes a longer same-provider retry/wait policy. All remain
   finite and eventually advance when another candidate exists.
7. A later successful fallback returns a complete result with bounded
   warning/metadata and never raises merely because an earlier provider failed.
   Partial status is reserved for unresolved slots; only zero settled slots
   raise `AllCandidatesExhausted`.

These are product decisions, not implementation authorization. Historical
#590/#592/#594/#640/#646 text remains provenance only where it differs.

### #647 latest proposal reconciliation and implementation pruning

The latest maintainer proposal confirms the destination but does **not** lift
the runtime pause. It strengthens these product directions:

- callers compose provider-free video inspection/frame extraction and audio
  extraction themselves; there is no replacement long video-recognition black
  box;
- selected video frames remain full frames, with negative-feedback/similarity
  selection internal to extraction and no crop/corner/ROI stage;
- image slots merge into one image Markdown and audio slots merge into a
  separate audio Markdown; PDF page groups reuse the image merge backend;
- image and audio calls accept their own explicit concrete sources, provider
  input, and optional output target; no library API reads legacy-app state;
- one selected provider identity is one exact vendor/model pair with explicit
  plain-image, detail-image, and audio capability facts plus recommended image
  count and audio duration; detail-image support implies plain-image support;
- scalar, flat fallback-list, and nested fixed-lane pool inputs are the eventual
  surface, while repair remains a small missing-sidecar recovery path and social
  downloading remains out of scope.

The proposal also contains several points that must be pruned before code:

1. Public `extract_video_frames()` and `extract_video_audio()` outputs are
   caller-owned. Without a library `recognize_video` lifecycle, a later
   independent recognize call cannot safely know whether it may delete them.
   The library deletes only artifacts it creates and consumes inside the same
   call. A future application-level one-click video job may delete its own
   extraction outputs; that does not recreate a library black box.
2. Retry policy does not key directly on HTTP `400`/`404`/`429` across vendors.
   Each adapter first maps SDK/status evidence to the existing canonical typed
   provider error. Only the canonical code may select finite retry count and
   delay. Capability, source, configuration, and output preflight failures
   never enter that loop.
3. Keep `error`, `next`, and `current`, but do not inflate them into a state
   machine. All eventually record the last exhausted safe error and advance when
   another candidate exists. `error` reports an exhausted request mistake at
   error level; `next` records an ordinary provider switch at info level;
   `current` records a longer same-provider retry/wait policy at info level.
   Finite rule values, not label-specific hidden loops, control attempts and
   delay.
4. Model data must not contain a generic list of arbitrary invocation
   parameters or an executable function pointer. A first-class entity carries
   exact model facts plus the exact typed adapter settings it needs; a private
   controlled resolver lazily selects known Google-native, OpenAI-compatible,
   or local execution code. An injected escape-hatch object follows the small
   explicit adapter protocol once a merged-list caller exists, instead of being
   converted into an entity. The first built-in scalar proof needs no new
   protocol and leaves the shipped one-method `VisionProvider` route unchanged.
5. Do not implement scalar, flat fallback, nested pooling, image, audio, resume,
   repair, and token persistence in one slice. Each later slice may add only the
   next topology already consumed by a public flow.

#650 fixes the first executable retry seed: both initial image presets start
with an empty retry-rule mapping. The schema retains the three approved labels,
but no label/count/wait entry is invented before a bounded real failure proves
that retrying the same exact provider/model helps. Missing rules mean one
initial dispatch and zero extra calls. Canonical `retryable=True` and
`ProviderErrorDisposition` remain evidence, not a numeric retry policy. The
first scalar Google and DashScope image proofs therefore make at most one
generation request each and do not implement a retry executor. A later flat-
fallback slice may admit one rule at a time from real evidence; it must not copy
legacy six-attempt loops, exponential/65-second backoff, last-success memory,
unavailable-model blacklists, or stream-to-nonstream transport fallback.

The phrase "traverse the whole list once" is read provisionally as **visit each
candidate at most once per slot, with its configured finite attempts, and stop
immediately on the first successful candidate**. Calling later providers after
valid content exists would spend calls without changing the slot and is not
authorized. A later slot may rotate its flat traversal start to the last provider
that succeeded during the same invocation, then wrap once; that preference is
not persisted as resume state. Nested outer lists remain fixed lanes with no
cross-lane rescue; exact slot-to-lane assignment is postponed until the pool
slice and must not complicate the first scalar proof.

The active runtime sequence is:

1. add only immutable provider-model facts, exact typed settings, private
   controlled adapter resolution, and no new injected-adapter contract;
2. ship a few complete presets and live-prove one native Google image entry and
   one DashScope OpenAI-compatible image entry before rewriting public calls;
3. implement merged image planning/recognition/resume first for one scalar
   provider, then flat fallback; if that flat-list slice first accepts injected
   leaves, define its smallest image-only adapter contract in that same slice;
   do not begin nested pooling or predeclare audio members yet;
4. implement explicit audio extraction/splitting and merged audio
   recognition/resume with the same scalar-then-flat sequence;
5. prove both replacement owners, then delete the verified 34-file old video
   recognition/orchestration family in one coherent change;
6. add nested fixed-lane pooling only after serial fallback is proven, and add
   experimental repair last from a real missing-sidecar Markdown case.

The maintainer's authorization permits these steps one atomic slice at a time,
starting with item 1. It does not permit implementing later items early. This
prevents the provider object from becoming a scheduler, state store, retry
executor, output planner, or media owner before those consumers exist.

#651 confirms this timing from current code rather than from the future schema.
The shipped `VisionProvider` has one synchronous `recognize_images(...)` method;
the resolver preserves an injected object, while the common caller owns timeout,
Markdown validation, redacted error mapping, and optional usage extraction.
`ResolvedVisionProvider` is only a four-field metadata value, and no
`ProviderModel` runtime or merged-list consumer exists. A final image/audio
`ProviderAdapter` created now would therefore freeze methods with no caller.
The first two built-in scalar proofs use their private controlled resolver. The
existing Config injection remains the working escape hatch until a new merged
API supplies the narrower, consumer-driven second path.

#657 implements only the private first scalar sub-slice. Internal
`ProviderModel` stores exact vendor/model/controlled-adapter identity plus one
exact Google or DashScope settings value. It is deliberately not a dataclass:
runtime settings may contain credentials or a mutable credential pool and are
therefore absent from repr, equality, hashing, and `dataclasses.asdict()`.
Construction validates the exact vendor/adapter/settings combination. One
private image consumer converts that entity into the existing `Config`, then
reuses the existing `resolve_vision_provider()` and `call_vision_provider()`
chain. A proposed second resolver module was removed during self-review because
it duplicated the same two adapter branches and could drift.

The type has no package-root export, preset, capability/default/retry fields,
serializer, resume identity, or compatibility promise yet. Those fields are
not guessed in this slice: the first live-proven preset adds only the capability
and default facts its image proof can support, while audio and retry facts wait
for their own consumers. The next gate is one bounded DashScope scalar image
request through this private consumer, then the corresponding native-Google
proof; each remains one generation call with no retry, fallback, or model
switch. Current `recognize()` and injected-provider behavior are unchanged.

#658 reaches the real DashScope generation boundary through that private
consumer but does not close the success gate. Exact `qwen3.5-ocr` on the
repo-owned formula board made one generation attempt and returned the existing
typed `PROVIDER_RESPONSE_INVALID` with request scope. There was no retry,
fallback, model switch, output artifact, source mutation, or leaked content;
the runner could not claim token or client-cleanup evidence from the failed
response. This is an honest scalar transport/error proof, not admission of a
preset or capability/default fact. One later bounded success is still required
before the first preset or public-call rewrite.

The private consumer now accepts the already-existing positive request timeout,
and the maintained DashScope image smoke exposes the entity path only behind
explicit `--provider-model`. A separate 340-line runner/test pair was removed
during self-review and folded into the existing provider smoke because its
catalog, redaction, and error scaffolding duplicated a working gate. This adds
no retry executor, diagnostic result type, response-parser exception, or second
provider framework.

#659 exercises the consolidated maintained mode after the required interval.
The enabled proxy and credential preflight passed, but the sole catalog request
returned unavailable in 5.11 seconds. The runner emitted the existing typed
`PROVIDER_CATALOG_UNAVAILABLE`; generation calls were exactly zero, with no
retry, switch, fallback, source mutation, stderr, or residue. This does not
reclassify #658's later-stage invalid response or close the scalar success gate.

The failed safe JSON exposed one local runner omission: it reported a null
scope even though the existing canonical disposition already defines this code
as provider-scoped. The runner now derives provider-error scope through
`get_provider_error_disposition()` instead of duplicating `failure_scope` at
each error constructor. This changes diagnostics only; it adds no production
retry, catalog fallback, error type, or shared runner framework. The live output
itself remains recorded as null, while focused offline evidence proves future
reports use `scope="provider"`.

#660 makes the third bounded DashScope entity attempt and then changes the
proof order rather than repeating it blindly. Catalog discovery succeeded and
one exact generation attempt reached `qwen3.5-ocr`, but the response again
ended as the existing request-scoped `PROVIDER_RESPONSE_INVALID`. The corrected
runner reported the canonical request scope; there was no retry, model switch,
fallback, source change, stderr, residue, or second child.

The three entity attempts now provide two generation-stage invalid responses
and one catalog outage, with zero successful completions. This is enough to
defer—not waive—the DashScope success gate. The next atomic transport proof is
the already-required native-Google scalar image path through the same private
consumer. A Google success would isolate the remaining problem to current
DashScope/catalog/response behavior rather than the common entity boundary; a
Google failure remains honest evidence. Do not add a preset or rewrite public
calls until the relevant success gates close. DashScope later resumes with one
bounded diagnostic question, not an automatic retry loop or parser relaxation.

#661 adds the same explicit private-entity mode to the maintained native-Google
image smoke instead of creating a second runner. The default public mode stays
unchanged. Existing provider-model contracts plus the actual runner execution
prove the exact Google entity reaches the maintained board-prompt/native-client
boundary, while success still requires strict `VisionProviderResponse` and
client-close evidence. No package-root export was added. A broader combined run
also corrected two order-dependent tests:
zero-call preflight now proves that it does not newly load `google.genai`, rather
than assuming no earlier test imported the SDK.

The sole credential-isolated live child did not reach Google. With the required
local proxy expressed as `socks5h://127.0.0.1:10080`, native SDK construction
failed safely as `PROVIDER_RESPONSE_INVALID`, operation `client_setup`, request
scope, and exact zero provider calls after about 1.44 seconds. A credential-free
offline construction reproduced `ImportError`; the environment has
`google-genai==2.9.0` and `httpx==0.28.1` but no `socksio`. This distinguishes an
operator/dependency proxy gap from an entity, image, model, catalog, or response
failure. There was no retry, model switch, fallback, second child, source change,
stderr, residue, or dependency installation. The Google scalar success gate and
the DashScope success gate both remain open. The next atomic decision must first
settle the smallest supported proxy path or optional-dependency correction; it
must not replay the API or add presets, retry, fallback, or provider pools.
An initially added fake-live monkeypatch regression was removed during primary
review because root testing policy assigns this proof to the scenario runner and
diary; retaining it would have duplicated real evidence in the default suite.

#662 corrects the #661 operator diagnosis and closes the native-Google scalar
success gate without changing the package. The current 10080 listener is a mixed
proxy: bounded no-credential HTTPS probes succeeded through both HTTP CONNECT
and SOCKS5, and a dummy native client constructed and closed through the HTTP
form. HTTPX metadata confirms SOCKS support is optional. Therefore the smaller
route is to use `http://127.0.0.1:10080` in the disposable child, not add
`socksio` to `ocrllm[google]` or teach the library to discover proxies.

Exactly one credential-isolated `gemini-2.5-flash` entity run then completed the
unchanged formula board in 15.67 seconds. Adapter-owned catalog validation and
one generation succeeded; safe output reports 595 input tokens, 269 output
tokens, one provider call, and a closed client. There was no retry, model switch,
fallback, second generation, source mutation, stderr, process, or temporary
residue. This proves the private Google entity/call boundary only. It does not
admit a preset, infer plain/detail OCR capability or default batch size, prove
audio defaults, authorize public-call rewrite, or waive the separately open
DashScope success gate. The next DashScope action must still ask a new bounded
diagnostic question rather than replaying the same invalid response blindly.

#663 makes that future response failure distinguishable without storing or
printing content. Existing DashScope raw-response and completion-parser branches
now attach one short fixed `reason` such as `raw_parse`, `truncated`, `refusal`,
or `missing_text`. The maintained runner emits it only from a closed whitelist;
unknown strings, mappings, and provider text remain absent. The success/failure
decision, parser strictness, canonical code/scope, retry behavior, and public API
do not change. Existing parser tests gain assertions instead of a new test file,
and a combined run also finishes #661's order-independence correction by proving
zero-call preflight does not newly import either Google or OpenAI SDK modules.

The sole live request did not exercise the new discriminator. Current catalog
discovery returned `PROVIDER_CATALOG_UNAVAILABLE` after about 0.45 seconds, so
generation calls were exactly zero and no response reason existed. There was no
retry, switch, fallback, second child, source mutation, stderr, or residue. This
is honest provider-boundary evidence, not a scalar success or parser diagnosis.
The DashScope gate remains open; do not replay it immediately merely to seek a
reason. Google remains closed, and no preset/public merged rewrite starts.

#664 fixes the catalog boundary exposed by that zero-generation run. A failed
DashScope catalog refresh still returns the last successful cached catalog, but
when no cache exists the fetcher no longer collapses authentication, permission,
rate-limit, server, and network failures into `None`. It reuses the existing
canonical DashScope mapper and adds only `provider_operation="catalog"` and
zero-call evidence. Malformed or empty catalog JSON becomes the fixed,
content-free `catalog_malformed` reason. There is no new status matrix, retry,
cache policy, catalog result type, preset, or live request. The DashScope scalar
success gate remains open; the next live attempt may now distinguish a provider
or network outage from invalid catalog data without inspecting private text.

#665 closes the DashScope scalar image success gate with no runtime change. After
the required interval and 33 offline runner/entity/catalog checks, exactly one
credential-isolated child used the maintained `--provider-model` mode, current
catalog discovery, exact `qwen3.5-ocr`, and the unchanged formula board. The
catalog contained 246 models; one generation completed in about 9.48 seconds
with 4,357 input tokens, 297 output tokens, and a closed client. Source identity,
stderr, cleanup, and process checks passed; there was no retry, model switch,
fallback, second generation, output artifact, or retained provider content.

Both built-in scalar image transports are now live-proven. This admits the next
atomic step—adding only a small credential-free preset set and the image facts
actually supported by existing real evidence. It does not itself add a preset,
prove every capability/default, export `ProviderModel`, or authorize skipping
straight to merged public recognition. Audio/retry fields still wait for their
own consumers and evidence.

#666 centralizes exactly those two proven routes as internal, credential-free
constants: `GOOGLE_GEMINI_2_5_FLASH` and
`DASHSCOPE_QWEN3_5_OCR_CN_BEIJING`. Their settings contain no key, remain
frozen, and resolve environment credentials only at the existing adapter call
boundary. The two maintained image runners now consume the constants for exact
model matches while preserving explicit construction for other live-discovered
model IDs. This removes duplicated identity/settings construction without a
registry, factory hierarchy, full catalog mirror, or model-name classifier.

The constants and `ProviderModel` remain off the package root because no public
recognition facade accepts them yet. Publishing them now would expose a value a
normal caller cannot use through a supported public operation. Capability
booleans, default image count, audio facts, and empty retry mappings also remain
absent: although ordinary image transport is proven, the exact task/default
fields have no merged-image consumer yet and some detail/default facts remain
unproven. The first scalar merged-image consumer must add and immediately use
only its required image fields, then export the type/presets with that usable
operation. Do not reinterpret this staged internal seed as the final complete
preset contract.

The current-code audit also gives a concrete reduction target. At #647,
`src/ocrllm` contains 302 Python files and 23,383 lines, including 91 root-level
modules. Many root helpers are 20--60 lines, while `recognize.py` is 431 lines,
`processors/recognize_images.py` is 632 lines, and the frozen
`recognize_video_to_markdown.py` is 590 lines. This is both micro-module sprawl
and oversized orchestration, not evidence that every file should be merged.
The immediate rule is narrower: add no helper until one next consumer needs it;
keep closely related private helpers in the owning feature module/package; split
only a function whose responsibility or test seam is independently meaningful;
and use the old-video deletion to reduce the root surface before adding pool or
repair modules. `contracts/` and `worker/` remain frozen.

Runtime work has resumed. Begin with only the immutable provider-model facts,
exact typed settings, and the smallest private controlled resolution needed by
the first scalar consumer. Do not pull presets, merged recognition, retry/
fallback, pool execution, repair, or old-video deletion into that first slice.
Only choices consumed by the current atomic slice must already be explicit;
unrelated later choices do not become a blanket prerequisite. The negative-
feedback/similarity frame algorithm remains a separate later real-archive
review; no crop/ROI/corner-detection path may return.

#602 corrects one already-shipped canonical mapping before any retry executor
exists. Native Google HTTP 400 with exact status `FAILED_PRECONDITION` has now
occurred across catalog and Files-upload operations, so it maps to
`PROVIDER_UNAVAILABLE` with provider scope rather than
`PROVIDER_REQUEST_INVALID` with request scope. This does not identify billing,
account suspension, or a model defect, and it does not execute a retry. Ordinary
`400 / INVALID_ARGUMENT` remains request-invalid. Future rules consume the
canonical result; they do not copy this raw vendor status into a common HTTP
matrix.

#603 live-confirms that correction through the existing public image path. One
repo-owned formula-board invocation reached the native Google catalog and
returned `PROVIDER_UNAVAILABLE` with provider scope, HTTP 400,
`FAILED_PRECONDITION`, catalog operation, and zero generation calls. This
proves the canonical mapping is now honest in real execution; it does not prove
catalog availability, model membership, image recognition, or a retry policy.

### #604 discussion checkpoint: preserve the destination, reopen contradictions

Historical checkpoint: its open list is superseded by section 0 and the later
#591--#626 decisions; retain it only as the reasoning trail.

The maintainer's latest detailed proposal reconfirms most of sections 2.1-2.9,
but explicitly pauses implementation for further discussion. It does not
authorize the previously planned P1-b live batch or the first `ProviderModel`
runtime slice. This checkpoint separates the stable destination from details
whose latest wording conflicts with an earlier fixed choice.

The following remain fixed:

- callers compose visible video inspection, extraction, frame retention,
  batching, image recognition, audio extraction, splitting, and audio
  recognition; there is no replacement video recognition black box;
- the old video recognition/journal family is removed only after ordinary
  merged-image, merged-audio, and their resume paths are proven;
- existing `recognize_batch()` keeps its current independent-item contract. A
  future merged-image call is a different API with one ordered slot document;
  it may reuse lower-level recognition and publication code without silently
  changing the old facade's meaning;
- provider input may later be one value, one flat ordered fallback lane, or a
  nested fixed set of lanes. Flat fallback stops at first success. Nested lanes
  use fixed assignment and no cross-lane rescue. Failed batches do not stop
  later batches;
- adapter-specific failures are mapped to canonical OCRLLM errors before
  finite retry policy is consulted. Raw HTTP codes are diagnostics, not the
  cross-vendor policy key;
- media batches retain exact concrete-tuple validation; provider collections
  being lists does not weaken that media-source contract;
- image and audio recognition own separate Markdown targets and separate
  sidecars. Two independent recognizers never mutate the same output file;
- full frames/pages remain intact, repair stays experimental, Electron remains
  a later Python/Rust-backend consumer, and social-media crawling stays frozen.

The latest proposal is reconciled as follows. Only entries explicitly described
as open in the narrower list below require maintainer confirmation before their
slice:

1. The latest wording says `float` for provider default audio minutes, while the
   previously fixed public and durable contract accepts integer minutes only.
   This plan continues to use positive `int` until explicitly overturned.
2. A curated preset for a model classified as unable to think uses
   `default_image_batch_size=1`, per the latest maintainer direction. This is a
   recommendation used only when the caller omits a size, not a provider hard
   limit. Do not infer that classification from a per-request
   `enable_thinking=False`. #557 completed two eight-image `qwen3.5-ocr`
   requests, but its bounded report did not retain that request flag; the
   current default cannot reconstruct a deleted disposable controller. The
   preset owns the classification and value; an explicit caller size still
   wins.
3. "Prebuild Google and DashScope models" can mean transiently materializing
   every current catalog descriptor plus a few verified executable presets, or
   checking hundreds of complete executable presets into source. The latter
   conflicts with the earlier no-indefinite-model-maintenance rule and remains
   rejected pending a direct reversal of fixed choice 3.
4. A successful fallback cannot both return a valid result and raise a terminal
   exception. Earlier choice 2 returns bounded prior-provider evidence with the
   result. The latest wording that the final accumulator contains only failed
   batches may instead remove those success warnings; this reporting detail is
   reopened, but post-success terminal exceptions remain rejected.
5. "Traverse the list once" continues to mean at most one circular ordered pass
   while a batch is unresolved. It does not call later providers after success.
6. Public extraction has caller-owned output. With no recognition wrapper there
   is no library-owned recognition lifecycle that can later delete it. Only a
   frame created and rejected inside the same owned retention/deduplication
   operation may be deleted. A future explicitly approved job wrapper could own
   a private temporary directory; this plan does not anticipate one.
7. The exact `resume_video` signature and its one-branch-success/one-branch-
   failure result remain open. It must not acquire a journal, shared publication
   target, cleanup ownership, or hidden extraction merely to make the name
   convenient.
8. Implementing the complete final `ProviderModel` schema before one consumer
   uses its retry/audio fields may be another consumer-free foundation. The next
   discussion must choose between a staged internal value that grows with real
   slices and a complete up-front value; no runtime class is authorized yet.

The negative-feedback frame calibration and similarity check remain a separate
algorithm review. Existing candidate scanning/selection/writing is evidence,
not automatic approval to retain or redesign that algorithm. Review it later
against real archive video frames without restoring any crop/ROI step.

#608 adds a second real-lecture observation for that later review without
changing the algorithm. Public inspection of a 9,809.12-second, 294,611-frame,
1920x1080 H.264 MP4 succeeded, and one public extraction retained 104 ordered
full-frame JPEGs within the current density target. All decoded at 1920x1080,
and the final retained index was the exact final source frame. The first
retained representative was frame 5,106 at about 169.984 seconds because the
current segmenter returns the end candidate for each stable segment. This is
not by itself a defect: a stable segment is represented, and a visible change
should create a boundary. It is concrete evidence that the later algorithm
review must compare whether early transient content can disappear before the
first retained segment end. Do not add opening-frame pinning, a new cadence, a
second detector, or adaptive tuning until real frame-content review proves the
need.

#609 performs that bounded content check instead of inferring loss from frame
indices. It decodes only source frames 0, 150 (4.992 seconds), and 5,106
(169.984 seconds) from the same real lecture. Personal full-frame review finds
the board empty in all three; the visible changes are people and side-screen
clock content, not OCR material. The selector's exact changed-pixel ratios are
0.022461 from 0 to 150, 0.085938 from 150 to 5,106, and 0.063477 from 0 to
5,106, explaining why the samples remain one stable segment. This sample does
not prove that no brief content appeared and disappeared between grid points;
that remains the already documented #170 limitation. It does prove that the
169.984-second first representative did not replace meaningful opening board
content in this lecture, so no opening-frame pin, OCR prepass, second detector,
or threshold change is justified by #608/#609.

### #610 discussion checkpoint: prune the proposed provider/media destination

Historical checkpoint: use section 0 for current questions. The narrower
evidence and rejected designs below remain valid.

The maintainer's latest proposal is discussion input, not runtime
authorization. Read against the shipped source, it confirms the destination
already recorded below: visible inspect/extract/batchify/recognize composition,
separate image and audio outputs, merged ordered slots, image/audio resume
reuse, exact provider-model identities, flat fallback lanes, fixed nested
lanes, per-`(vendor, model)` usage, experimental repair, and eventual deletion
of the video recognition/journal family.

The deletion target is the duplicated **recognition** chain, not the readable
provider-free media implementation. The current public
`extract_video_frames()` owns one coherent operation: validate and snapshot one
video, sample comparison thumbnails, select representatives with bounded
negative feedback, and atomically publish the selected complete JPEG set. Its
scan, select, and write helpers already have separate files and responsibilities.
Do not export those internal helpers or require callers to carry thumbnail
candidates merely to make the public workflow look more granular. A new public
boundary is justified only when a real caller needs to inspect or alter an
intermediate result. The obsolete family remains the public
`recognize_video_frames()` / `recognize_video()` /
`recognize_video_to_markdown()` paths plus their result composition and video
journal machinery, after the replacement deletion gate is met.

Provider data is also pruned by lifetime. One immutable `ProviderModel` may
hold exact vendor/model identity, task capabilities, applicable recommended
media scalars, a controlled adapter ID, and later proven finite canonical-error
rules. Secrets, base URL/region, Chat-versus-Responses choice, effort,
high-resolution flags, timeout, cancellation, prompts, call counters,
last-success lane state, accumulated errors, and token totals do not all share
model lifetime. They remain exact adapter settings, call inputs, or run state;
there is no generic call-parameter `list` or dictionary on the model value.

Raw HTTP numbers remain adapter evidence, not portable retry keys. Current code
already proves why: native Google HTTP 400 can be provider-scoped
`FAILED_PRECONDITION`, request-scoped `INVALID_ARGUMENT`, credential failure,
or unsupported model modality, while DashScope status handling also depends on
its provider code. Each adapter first emits a canonical OCRLLM error. A later
fallback executor may apply only finite `extra_retries` and `wait_seconds` to
that canonical code. The proposed numerical counts are hypotheses until a
bounded real failure supports them; the overlapping `error` / `next` /
`current` labels remain unnecessary because exhaustion always either advances
an unresolved lane or ends it.

Four wording choices therefore remain open, but are now narrowly framed:

1. Keep the public splitter and durable identity in exact integer minutes, or
   deliberately permit a provider's recommended scalar to be fractional. The
   current recommendation is integer minutes because accepting `float` without
   fractional-window behavior would create hidden rounding.
2. Interpret "prebuild Google and DashScope models" as a small live-proven
   executable preset set plus transient discovery of every current catalog row,
   or as a checked-in executable mirror of a volatile catalog. The current
   recommendation, consistent with the no-indefinite-model-maintenance decision,
   is the former. A discovered row is not silently promoted to an executable
   preset when the catalog lacks OCR/detail-OCR quality, recommended media
   grouping, or retry facts.
3. Keep caller-invoked extraction caller-owned, or authorize a distinct private
   job/temp owner. With no replacement `recognize_video` wrapper, the phrase
   "media created by recognize video" has no library owner and cannot authorize
   deletion. The current recommendation is caller ownership; an application
   composing the steps may clean its own files.
4. Design the full eventual schema in this document while adding runtime fields
   with real consumers, or instantiate every unused retry/audio field in the
   first class. The current recommendation is full design review plus staged
   internal runtime fields, followed by public export only when the first
   merged consumer stabilizes the shape.

A provider-rejected image count does not cause hidden re-batching. The settled
batch plan and completed slots remain resumable; the adapter returns its honest
canonical failure with safe provider/model/batch evidence. Whether flat
fallback may advance on that exact failure waits for real vendor mapping and
the fallback slice, rather than a new speculative `batch-too-large` framework.
No runtime source, test, dependency, public API, provider call, or deletion is
authorized by #610.

### #611 transport fact: legacy and active Google both use native google-genai

The maintainer's corrected rule is now resolved from source rather than memory:
use the access method the legacy parent actually uses. The legacy Google-native
provider explicitly rejects the OpenAI-compatible endpoint and lazily imports
the official `google-genai` SDK. Its image and text calls use
`genai.Client(...).models.generate_content`; its long-audio path uses the same
client's Files upload/get lifecycle followed by `models.generate_content`.

The active library already matches that transport family. Its Google image and
inline short-audio adapters use native `google.genai` parts and
`models.generate_content`; its long-audio adapter uses native Files
upload/get/delete and generation. No Google OpenAI-compatible endpoint is the
initial adapter direction. A future endpoint change requires separate real
evidence rather than an assumed compatibility benefit.

Legacy hybrid mode does not contradict this finding. It deliberately routes
visual calls through the separately configured legacy `LLMClient`, while
Google-native code continues to own text and long audio. This is evidence for
separate image/audio provider selection, not evidence that Google itself is
accessed through an OpenAI-compatible endpoint.

Do not copy the legacy client's cached SDK client, mutable unavailable-model
sets, remembered successful model, or embedded retry/model-switch loop into
`ProviderModel`. The active library's exact-model, per-operation client
lifecycle remains the smaller adapter boundary. #611 changes no transport or
runtime code; it makes the source-proven native-SDK choice explicit.

### #612 discussion checkpoint: keep the visible workflow, remove the second public frame filter

Historical checkpoint: later decisions close several questions listed here;
section 0 is the current decision board.

The maintainer's latest proposal remains discussion input rather than runtime
authorization. It cancels the planned public `dedupe_video_frames` step. The
public provider-free video flow is now:

```text
inspect_video
  -> extract_video_frames
  -> batchify_images
  -> recognize_images_to_markdown

extract_video_audio
  -> split_audio
  -> recognize_audio_to_markdown
```

`extract_video_frames()` already owns one understandable operation: compare
sampling thumbnails, apply the bounded negative-feedback selection and
similarity check, then publish the retained complete JPEG frames. Its scan,
select, and write helpers stay private and separately readable. Exporting a
second deduplication stage would make callers carry implementation-only
candidates without giving them a supported decision to make. OCRLLM may delete
only candidates that it created and rejected inside this extraction operation;
every published retained frame is caller-owned.

The obsolete low-level video **recognition** chain is still the deletion
target. It is frozen rather than extended, and is deleted in the same product
transition that proves the replacement merged-image and merged-audio writers
and their independent resume paths. Deleting it earlier would create a shipped
feature gap; preserving it afterward would preserve the duplicated journal and
composition burden.

The latest proposal also confirms these already maintained contracts:

- one merged image call writes ordered image slots to one Markdown file, and
  one merged audio call writes ordered audio slots to a different Markdown
  file;
- visible image batching accepts an explicit size or secret-free model shape;
  recognition receives the resulting exact groups, and no settled plan is
  silently re-batched after rejection;
- `split_audio` accepts an explicit interval or secret-free model shape,
  requires at least one, gives the explicit interval priority, and uses `-1`
  only as the call-level whole-file spelling;
- recognize, resume, and experimental repair take explicit sources and an
  optional output target, with ambiguous cross-directory defaults rejected
  before provider dispatch;
- one provider-model, one flat ordered fallback lane, and fixed nested lanes
  remain the only provider shapes. Flat lanes stop at first success. Nested
  lanes never rescue work across lanes, and a failed batch does not stop later
  batches;
- token evidence is normalized at the adapter response boundary and
  accumulated by exact `(vendor, model)`, without allocating batch usage to
  individual images or persisting a per-attempt billing ledger;
- Electron remains a later client of a Python or Rust backend. OCRLLM does not
  add an Electron execution path, social acquisition, or legacy-file
  compatibility.

The controlled invocation design remains smaller than a generic executable or
parameter bag. `ProviderModel` identifies one exact vendor/model and one known
`adapter_id`. The adapter module owns SDK/client construction and consumes its
existing exact settings object. API keys, credential pools, region/base URL,
Chat-versus-Responses selection, effort, timeout, prompts, counters, lane
memory, errors, and token totals do not become a generic `list` field on the
model value. How several provider models bind to several exact settings objects
is intentionally decided with the first flat-list consumer; it is not guessed
inside the single-provider class.

Raw HTTP examples such as 400, 404, 409, 429, 500, 503, and 504 remain vendor
evidence, not cross-vendor policy keys. Each adapter first emits a canonical
OCRLLM error. A later rule may give that canonical code finite
`extra_retries` and `wait_seconds`; exhaustion advances only while the slot is
unresolved. The proposed numerical retry counts are not defaults until legacy
evidence or a bounded real call justifies them.

Four earlier wording conflicts remain open: integer versus fractional provider
audio minutes, a small live-proven preset set versus a complete catalog mirror,
caller-owned extraction versus a newly introduced private job owner, and staged
runtime fields versus instantiating the whole final schema at once. The
non-thinking preset default is fixed at one, without treating a request-level
thinking switch as model capability or as a provider hard limit. Three later
API details are now explicit discussion gates rather than
permission to build infrastructure:

1. A merged run with unresolved slots needs one outcome rule. The current
   recommendation is to atomically publish one partial Markdown containing
   exact failed-slot markers, retain its sidecar, and raise one typed terminal
   error after all later slots were attempted. A successful fallback returns a
   normal result with bounded warnings; it does not raise after producing a
   valid slot.
2. Nested lanes use fixed round-robin assignment with sequential work inside
   each lane and independent parallel progress between lanes. "Wait for them
   respectively" means a lane may continue after its own slot is settled; it
   does not create a global epoch barrier. #620 confirms this from the current
   ordering, settlement, cancellation, and bounded-execution evidence. Dynamic
   stealing remains excluded.
3. The first flat-list slice must decide how exact adapter settings are paired
   with provider-model values. Secrets and mutable client state still cannot
   move into `ProviderModel`; do not create a generic settings mapping before
   the second live transport demonstrates the binding.

No provider model, preset, adapter resolver, retry executor, pool, batch facade,
resume route, repair path, test, provider call, or deletion is authorized by
#612. The previously prepared DashScope live run was cancelled before credential
access or provider dispatch when this discussion-first instruction arrived.

### #613 live fact: the shipped DashScope image path still completes

After the #612 discussion checkpoint and without implementing any replacement
API, one credential-isolated public image run used the repo-owned
`formula_board.png` through the current DashScope path. Live Beijing discovery
returned 246 models and still contained exact `qwen3.5-ocr`. The recognition
completed in 4.610 seconds with exactly one generation call, provider-reported
usage of 4,357 input and 285 output tokens, and an exactly closed client. There
was no retry, fallback, model switch, output file, sidecar, or runtime change.

The disposable controller emitted only its safe JSON summary: stderr was empty,
the credential, recognized Markdown, and absolute fixture path were absent,
the fixture bytes stayed unchanged, and no owned Python process remained. An
earlier PowerShell-to-`python -c` quoting attempt stopped at Python parse time
before QSettings, proxy, catalog, or provider code; it is harness history, not
a provider attempt or OCRLLM defect.

This proves the existing adapter remains a viable first image transport and
that `qwen3.5-ocr` remains a live preset candidate. It does not resolve the five
open product choices, prove a replacement `ProviderModel`, justify a full
catalog mirror, select a batch default, or authorize interface rewrites.

### #614 live fact: short audio reaches Google but catalog is unavailable

One bounded public short-audio run reused the previously validated unchanged
1,986,191-byte archive MP3 (123.9707 decoded seconds) without download,
conversion, output, or content publication. The enabled proxy was reachable,
the existing Google credential was injected only into one runner child, and
the native adapter reached its own current catalog operation for exact
`gemini-2.5-flash`.

The catalog returned HTTP 400 `FAILED_PRECONDITION`. The post-#602 mapper
classified it as provider-scoped `PROVIDER_UNAVAILABLE`, with operation
`catalog` and exact `provider_calls_attempted=0`. This is the correct current
classification: no audio generation occurred, so it proves neither current
audio capability nor transcription. The runner exited in 4.954 seconds with
empty stderr, no secret/path disclosure, unchanged source identity, no recent
matching MP3 snapshot, and no owned Python process.

Two disposable local-controller mistakes preceded the sole live child: one
PowerShell search command failed in its JavaScript wrapper before execution,
and one provider-free probe treated the returned float duration as an object.
Neither read a credential or made a network request. They are harness history,
not product defects or API attempts. No retry, model sweep, endpoint change,
runtime change, or test was justified. This evidence supports canonical-
error-first policy; it does not select Google audio defaults or disqualify the
model from a later live-proven preset after the provider window recovers.

The media destination remains the visible composition in section 2.1. There is
no replacement `recognize_video` lifecycle owner. Consequently, media produced
by caller-invoked extraction is caller-owned and cannot be deleted by a later
recognition call. OCRLLM may delete only a rejected frame that it created and
still owns inside the same deduplication operation. The maintainer's separate
reference to cleanup for media "created by recognize video" is held as an open
wording conflict rather than used to revive a convenience wrapper.

Historical note: at #605 the plain/detail selector and thin `resume_video`
signature were still unsettled. #633 fixed the thin route and #637 fixes the
image selector in section 0. This paragraph is retained only to show the former
gap; it is not a competing current contract.

### #607 current decision map: do not reconfirm settled contracts

#607 reconciles the latest proposal with the complete decision record rather
than treating every newly worded example as a new contract. The previous
nine-question conversational checklist was too broad: most of those questions
already have maintained answers below and do not need another maintainer vote.

The following remain fixed and are not reopened by the latest wording:

- flat fallback stops at the first valid result; a complete circular pass occurs
  only while the slot remains unresolved;
- earlier exhausted providers are bounded diagnostics on an eventually
  successful result, while the terminal failed-batch accumulator contains only
  genuinely unresolved slots;
- an omitted media scalar uses the minimum applicable positive suggestion over
  the completely validated provider shape; an explicit value wins and no
  recognition call silently re-batches or re-splits it;
- default output naming, separate image/audio Markdown ownership, canonical-
  error-first finite retry shape, `(vendor, model)` usage accounting, controlled
  `adapter_id` plus exact settings, and the stateless package-root
  `resume_video` routing direction remain as specified in section 6;
- raw HTTP numbers in the latest examples are vendor evidence for adapter
  mapping, not portable public retry-policy keys. Exact retry counts remain
  unapproved until real errors justify them.

Only these four contradictions still need direct maintainer resolution before
their relevant runtime slice:

1. whether provider-recommended audio duration intentionally changes from
   positive integer minutes to `float`, despite the existing integer-only split
   and durable identity contract;
2. whether the request to prebuild Google/DashScope models means transiently
   materializing all current catalog descriptors alongside a small live-proven
   executable preset set, or intentionally requires a checked-in executable
   mirror whose missing OCRLLM fields must be invented;
3. whether caller-invoked extraction remains caller-owned now that no
   `recognize_video` lifecycle owner exists, or a separately approved private
   job/temp owner is actually wanted;
4. whether the complete image/audio/retry `ProviderModel` schema is only
   designed up front while runtime fields land with consumers, or the first
   internal runtime class must contain the entire currently unused schema.

The image-size wording is no longer one of those contradictions. A preset
classified as unable to think recommends one image. That rule is preset data,
not a runtime derivation from `enable_thinking`, and it does not reject an
explicit larger caller batch before the provider. Existing #557 evidence shows
that this model can complete two groups of eight, but its report did not retain
the request flag and therefore establishes no thinking/batch causality. It does
not override the maintainer's default policy.

Historical note: #607 still deferred the exact plain-versus-detail selector and
stateless `resume_video` signature. Those deferrals are superseded by #637 and
#633 respectively. They do not reopen the fixed no-journal/no-composition/no-
cleanup boundary.

#606 adds one narrow current fact without resolving any of those five choices:
one credential-isolated DashScope `/models` request returned 246 entries and
contained both `qwen3.7-plus-2026-05-26` and `qwen3.5-ocr`. It made zero
recognition calls. This keeps the DashScope-first candidate viable but proves
neither OCR quality nor a reason to mirror the full catalog.

## 1. Why This Refactor Exists

The current video product repeats the same work through three public paths:
`recognize_video_frames`, `recognize_video`, and
`recognize_video_to_markdown`, with `compose_video_result` and a dedicated
video journal layered around them. The tracked source currently contains 50
video-named files (4,756 lines) and 16 video test files (8,478 lines). Not all
of those files are wrong, but the dedicated recognition and resume layers are
too costly to understand and maintain.

The target is not a stronger video framework. The target is one set of public,
composable media steps, one merged-image batch recognizer, one merged-audio
batch recognizer, and no video-only recognition or resume implementation.

## 2. Fixed Destination And Current Safe Defaults

Sections 2.4 and 2.5 retain positive integer audio minutes, evidence-backed
image suggestions, a bounded preset set, and staged field consumption as the
safe defaults while #607's direct wording conflicts remain unresolved. Those
defaults prevent speculative runtime work; they are not evidence that the
maintainer has answered the five reopened questions.

### 2.1 Media pipeline

The intended public composition is:

```text
inspect_video
  -> extract_video_frames
  -> batchify_images
  -> recognize_images_to_markdown

extract_video_audio
  -> split_audio
  -> recognize_audio_to_markdown
```

- These steps remain directly callable. Recognition must not hide them inside
  one required black-box function.
- `extract_video_frames` includes the negative-feedback/similarity selection
  and publishes only retained complete frames. Candidate scan/select/write
  helpers remain private; there is no second public deduplication step.
- The replacement does not include a `recognize_video` convenience wrapper.
  Callers compose the visible public steps themselves; recognition rules,
  cleanup ownership, and resume must not disappear inside another video
  black box. A later wrapper would require a separate maintainer decision and
  a concrete consumer, not merely the availability of the component steps.
- Image and audio providers are separate inputs.
- Video-derived work reuses image-batch and audio-batch resume. There is no
  third video resume engine. The maintainer explicitly requires a thin
  `resume_video` route to the image/audio resume functions; it owns no journal,
  publication, naming, or cleanup lifecycle. It is a package-root public
  operation; internal sidecar helpers remain private.
- PDF-rendered pages reuse the merged-image batch backend. PDF does not gain a
  separate provider dispatcher.
- Every retained image is a complete frame or page. No board-corner search,
  ROI crop, perspective correction, or inferred screen crop returns.
- Social-media acquisition and recognition remain frozen. OCRLLM does not
  become a crawler.

### 2.2 Explicit media and output paths

- Every recognize, resume, and repair entry accepts explicit source paths and
  an optional output Markdown path. Omission uses the same deterministic
  default-placement and naming rules; resume/repair do not search unrelated
  directories for a plausible prior output.
- A single image, audio, or PDF file defaults beside that file.
- An exact `AudioSlice` tuple derived from one original audio file keeps that
  file as its source identity and uses the same scalar default. Logical ranges
  are not treated as independently stored audio files or a folder batch.
- An image or audio batch defaults beside its source directory only when every
  distinct concrete leaf source has the exact same direct parent after public
  path coercion. The folder name supplies the default source identity. Do not
  infer equivalent parents through symlink resolution, a common ancestor, or a
  first-member shortcut; nested image groups validate all leaves.
- If an omitted output cannot be resolved without guessing, for example a
  batch whose direct parents differ, preflight rejects the call before any
  provider request. The same mixed-directory recognize, resume, or repair call
  remains valid when the caller supplies one explicit `output_path`.
- Image and audio batches write ordered slots into one Markdown file. They do
  not publish one Markdown file per item. This means one output per merged
  image call and one separate output per merged audio call. Independent media
  calls never mutate the same file, and the current product does not add an
  image-plus-audio composer or final cross-media artifact.
- Default naming is fixed in section 6: normalize the source identity and append
  `_ocrllm.md`. No media-specific suffix family is added.

### 2.3 Batch boundaries

- `batchify_images` accepts an explicit positive integer size, a secret-free
  `ProviderModel` shape used only for default resolution, or both; at least one
  is required and the explicit size wins.
- The model shape may be scalar, flat list, or nested list. When the size is
  omitted, validate every applicable model and take the minimum positive
  recommendation across the flattened shape once. Runtime settings,
  credentials, endpoints, and `ProviderBinding` do not enter batching.
- The merged recognizer consumes the exact ordered groups returned by
  `batchify_images`; it does not add a second unbatched-input/default-resolution
  path. This keeps the requested inspect/extract/batchify/recognize steps
  visible instead of making batchification optional hidden work.
- Already-batched input is never re-chunked during provider fallback. Slot
  identity and resume ordering stay stable.
- The groups themselves are the plan. Do not add an `ImageBatchPlan` class,
  planner registry, or provider tree to persistence merely to remember one
  advisory integer.
- Media batch containers follow the active library's strict concrete-tuple
  approach. Generators, custom iterables, and compatibility wrappers are not a
  product requirement.
- All sources, members, output targets, and collisions are validated before
  the first provider call.

### 2.4 Audio splitting

- `split_audio` accepts either an explicit integer-minute interval or a
  secret-free `ProviderModel` shape; at least one is required. Exact runtime
  settings and `ProviderBinding` first enter at recognition.
- An explicit interval wins when both are present.
- `-1` means no split. It is a call argument only, never a provider default.
- Provider default audio duration is a positive integer number of minutes,
  initially normally 30 and later adjusted only from real context, stability,
  and hard-limit evidence.
- The existing private ten-hour product ceiling remains unless a later
  evidence-backed decision changes it. Individual providers may reject a
  shorter duration; that remains a provider failure, not a reason to guess a
  new chunk plan during recognition.
- The existing 30-second boundary context depends on logical and actual range
  metadata plus a range-aware prompt. A future public splitter cannot return
  bare paths while silently preserving that overlap, because ordinary audio
  recognition would duplicate boundary speech. `split_audio` therefore returns
  an exact tuple of immutable `AudioSlice` values carrying caller-owned source,
  zero-based index, and exact logical/actual ranges. It plans no provider call
  and does not materialize persistent segment files.
- Recognition consumes those already-fixed slices. It may create the physical
  transport clip for one active slot, reuse it for that slot's finite fallback
  attempts, and remove it on scope exit. Transport materialization is not
  permission to calculate or alter slice boundaries.

### 2.5 Provider-model value

One value represents exactly one `(vendor, model)` pair. Google or DashScope
as a whole is not one provider value. The public type is named `ProviderModel`:
it states the actual identity more clearly than `ProviderEntity`. Do not ship a
second alias for the same value. `ProviderModel` is one data class whose presets
are instances; it is not one Python subclass or source file per vendor model.

Only fields consumed by the first real vertical slice may be added. The
recommended durable set is:

- vendor and model identifier;
- a fixed invocation boundary: the built-in route stores a controlled adapter
  identifier rather than a callable or executable pointer;
- plain-image OCR support;
- detail-image OCR support, including LaTeX/code-oriented output;
- audio-input recognition support;
- default image batch size, which is a positive integer exactly when plain
  image OCR is supported and otherwise `None`;
- default audio minutes, which is a positive integer exactly when audio is
  supported and otherwise `None`;
- evidence-backed finite retry rules keyed by canonical OCRLLM codes.

Detail OCR implies plain OCR; a value claiming detail without plain support is
invalid. Fresh merged-image recognition uses the required exact
`image_task: Literal["plain_ocr", "detail_ocr"]` selector fixed in section 0.
The complete provider shape must support the selected task. A mismatch raises
the existing `ConfigError(code="CONFIG_INVALID")` before adapter/media/output
work and causes zero provider calls; it is not a provider runtime failure and
does not silently remove a fallback candidate or lane.

The value does not contain a generic call-parameter list or mapping. Its one
exact typed adapter-settings field may contain runtime API keys, a currently
supported credential pool, region/base URL, or proven adapter switches because
the maintainer explicitly rejected a second binding value and a parallel
settings tree. That field is `repr=False`, `compare=False`, `hash=False`, and is
never generically serialized. Timeout, cancellation, prompt/media input,
catalog clients, upload handles, call/token counters, last-success state, and
provider errors remain one-call or recognition-run state. The first vertical
slice reuses its existing exact provider-settings type rather than creating a
second common settings object. An adapter-specific option moves into durable
model facts only after two real presets prove that it is part of model identity
rather than call configuration.

No universal constructor default invents `1` image or `30` audio minutes for an
unsupported task. A live-proven audio-capable preset may begin with a 30-minute
suggestion, and a live-proven image preset carries its measured batch
suggestion. Maximum output tokens, concurrency, start interval, batch override,
audio split override, candidate order, lane memory, and token accounting stay
outside the provider-model value unless a later real adapter consumes a field
that cannot be represented honestly elsewhere.

Committed presets do not contain API secrets, and no provider-model object is
serialized as a whole. A runtime instance may hold an explicit credential only
inside its redacted exact settings. A generic executable registry, plugin
system, full model catalog, placeholder OpenAI adapter, or arbitrary future-SDK
options container is not approved. The existing injected-provider protocol
remains a separate Python extension and test seam; it is not silently embedded
in every provider-model value.

The first `ProviderModel` vertical slice does not migrate the existing
RapidOCR path and does not prebuild VLLM, Ollama, Codex, or another local-model
runtime. RapidOCR already has a narrow `image_mode="ocr"` strategy, lazy
optional dependencies, typed errors, deterministic output, zero network calls,
and a stable resume identity. Moving it now would conflate local execution with
transport-provider calls without serving a replacement-API consumer.

This does not close the model boundary around cloud vendors. When a concrete
local-model consumer exists, it may use the same controlled `adapter_id` route
and the same `ProviderModel` value type. It must preserve lightweight import,
optional extras, honest local call/token evidence, and the existing local
result/error/resume behavior. Do not create a second local provider hierarchy,
a local model catalog, placeholder local adapters, or executable/callable
fields in anticipation of that consumer. RapidOCR capability examples in this
plan are conceptual only; they do not select an initial preset or batch default.

Credentials are supplied at call/runtime boundaries and never included in
repr, comparison/hash identity, persistence, batching, or committed presets.
The environment-resolved preset and an explicitly credentialed per-call entity
are the two supported built-in constructions; neither requires `ProviderBinding`.
Do not use `dataclasses.asdict()`, object equality, or object hash as resume or
cache identity. A versioned adapter-owned projection may include non-secret
output-affecting endpoint/region/options while excluding credentials, pool
objects, pool IDs, and health state. The first slice does not create a generic
`list` of hypothetical call parameters.

Preset scope is fixed to a small curated set of live-proven entries. Live
discovery or explicit construction of the same `ProviderModel` handles other
model IDs; OCRLLM does not mirror or indefinitely maintain every model exposed
by a vendor catalog. "Every model is a provider-model entity" describes the
identity of a model that is actually supplied, not a requirement to ship every
catalog row as a preset.

Google initially keeps the same access method already used successfully by the
active/legacy evidence selected by the authority. DashScope initially keeps
its proven transport. SDK or transport replacement requires a separate real
failure and decision.

### 2.6 Provider input shapes

Planning and recognition use the same three structural depths but different
leaf types:

```text
batchify/split: one ProviderModel | flat list[ProviderModel]
                | nested list[list[ProviderModel]]
recognize/resume: one ProviderBinding | flat list[ProviderBinding]
                  | nested list[list[ProviderBinding]]
```

Planning reads only capabilities and suggestions. Recognition uses the complete
model/settings pair. Do not make one argument accept both bare models and
bindings, and do not pass a parallel settings tree.

- A flat list is one ordered fallback lane. While its slot is unresolved, each
  provider may be reached at most once after that provider's own finite retry
  rule. The first valid recognition settles the slot and stops the lane; no
  later provider is called for comparison, ranking, or duplicate output.
- A nested list is a fixed set of independent lanes. Batches are assigned by a
  simple round-robin rule (`batch_index % lane_count`); no batch uses a
  provider outside its assigned lane.
- A lane remembers its last successful provider as the next batch's starting
  point. With no prior success it starts at the first provider.
- A failed batch does not stop later batches. Final reporting records failed
  batch range, last provider, canonical error code, and bounded description.
- The final failed-batch accumulator keeps exactly that terminal failure for
  each failed batch. It does not retain one overflow record per provider. When
  a later provider succeeds, fixed choice 2 keeps bounded earlier-provider
  failure evidence on that successful result instead.
- No dynamic rebalancing, cross-lane rescue, arbitrary iterable support, or
  second pool abstraction is planned.

The success-stop contract is fixed. "Traverse once" means at most one ordered
pass while a slot remains unresolved, not mandatory calls after success.

### 2.7 Retry and error evidence

Vendor adapters first map raw SDK/HTTP failures to existing canonical OCRLLM
provider errors. Public retry rules are keyed by canonical codes, not by a raw
HTTP number shared across vendors.

Every retry count is finite. `-1` or any other infinite-wait spelling is
rejected. Each populated retry rule contains exactly one of `error`, `next`, or
`current`, plus non-negative `extra_retries` and `wait_seconds`. The labels
control reporting category only: finite values control same-provider attempts,
and an exhausted unresolved slot advances when another candidate exists. They
do not create label-specific loops or override the complete/partial/total-
failure result contract.

Do not pre-fill Google and DashScope with identical guessed policies. Start
from the real mappings and errors already observed in the active and legacy
paths, then add only rules required by an end-to-end call. Do not invent
unproven maximums such as 32 retries or 600 seconds.

For the first scalar image proof, both preset mappings are empty. A missing rule
means one initial dispatch and zero extra calls even when the canonical error is
marked retryable. Existing live failures prove classification and honest
settlement, not that an immediate retry succeeds. Numeric rules first belong to
a later flat-fallback consumer after one bounded real failure/retry comparison;
the scalar entity proof does not contain a dormant executor.

### 2.8 Token accounting

- Accumulate exact call count plus provider-reported input and output tokens by
  exact `(vendor, model)` identity. The currently shipped model-only key must
  not be copied into the future multi-provider dispatcher.
- Current-run totals include usage reported for a valid result and usage that
  an adapter safely observed before a later response-validation failure.
- A dispatched call with no trustworthy usage does not become zero. The call
  count remains exact, while the affected token dimension for that
  vendor/model total is `None` because its exact total is unknown.
- Persist only aggregate usage needed to distinguish historical resume work
  from the current invocation. Do not persist a public per-attempt ledger,
  cost estimator, token-category taxonomy, or duplicate global counter.
- Never divide one batch's usage across its individual images or audio slices.
  More detail waits for a real consumer or billing defect.

### 2.9 Resume, repair, and owned intermediates

- Image batches and audio batches may each own one temporary sidecar while
  incomplete. A video-specific journal is not retained.
- Full success deletes the temporary sidecars only after the final Markdown is
  durable. Partial or total failure retains them for ordinary resume.
- Sidecars preserve slot identity, settled paid work, resolved batch/split
  parameters, and only the source evidence needed to resume safely.
- Provider identity is not part of the unsettled slot plan, so a caller may
  change provider while resuming.
- Repair is an experimental side path for an OCRLLM-produced failure marker
  when the ordinary sidecar or intermediate record was lost. It does not parse
  arbitrary Markdown and is not a gate for production resume or deletion of
  the old video journal.
- Caller-owned media is never deleted.
- Because the replacement has no video convenience wrapper, media returned by
  caller-invoked extraction functions is caller-owned and is not later deleted
  by recognition. If a future wrapper is separately approved, its generated
  media lifecycle must be decided with that wrapper rather than anticipated in
  this plan.
- A frame rejected by video deduplication may be deleted only when OCRLLM
  created that frame for the current owned run.

The current negative-feedback calibration and similarity verification are a
separate tricky algorithm decision. This plan neither rewrites nor broadens
them before real frame-quality evidence is reviewed.

## 3. What Must Be Removed Eventually

The maintainer has fixed the destination: the duplicated video recognition and
journal product is abandoned, not maintained as a compatibility family. The
following current implementations remain frozen only until the replacement
image/audio paths meet the deletion gate, then are removed deliberately:

- `recognize_video_frames` as a separate recognition product;
- the current `recognize_video` implementation and its public name; the
  replacement does not reserve a convenience wrapper;
- `compose_video_result`, `publish_video_result`, and
  `VideoRecognitionOutcome`;
- `recognize_video_to_markdown`;
- the video job state/journal, its parse/load/save/serialize/validate helpers,
  and the job-only image/audio recognizers;
- the current video-specific MP3 processor and helpers that have no consumer
  after the public image/audio paths replace it;
- tests whose only purpose is the deleted job/journal contract.

Keep and simplify the provider-free media functions: inspection, complete-frame
extraction, audio extraction, candidate scanning/selection, and file writing.
The final deletion list must be regenerated from imports immediately before
deletion; the old plan's list is evidence, not permission to delete an
unreviewed file.

## 4. Deliberately Rejected Overdesign

Do not create any of the following before a real consumer requires it:

- a provider fingerprint or identity-version hashing scheme;
- a registry object plus placeholder adapters;
- a static catalog for whole vendor model families;
- a thread-safe token-ledger class before parallel dispatch exists;
- nested-pool workers before flat fallback works live;
- a generalized transaction or ownership framework;
- video-only state layered over image/audio state;
- repair support beyond OCRLLM's own failed-slot/time-range markers;
- compatibility with legacy application files or configuration formats;
- broad retry matrices copied from HTTP status folklore;
- placeholder RapidOCR, VLLM, Ollama, or Codex adapters/extras before a real
  local-model consumer;
- test matrices for hypothetical adapters and model combinations.

One file still has one clear responsibility, but files are created when a
working vertical slice consumes them, not because a final architecture diagram
contains a box.

The 2026-08-29 read-only surface audit found all current public-export changes
in `src/ocrllm/__init__.py` and confirmed that `publish_video_result` cannot
survive unchanged without `VideoRecognitionOutcome`. It also found mixed test
files that contain both retained provider-free coverage and obsolete video
recognition coverage, so deletion must prune individual tests rather than drop
every video-named file. This audit is a deletion map, not permission to delete
before the gate.

## 5. Evidence-First Implementation Order

No phase starts until the decision gate named for that phase below is resolved
and recorded. Section 6 is not one flat barrier: a later video-publication
choice does not block the first provider-model proof, and a fallback policy
does not block single-provider merged recognition. This pause also does not
prohibit fixing a defect reproduced in the already-shipped provider-free
inspect/extract/selection functions.

1. **One provider-model vertical slice.** Add the smallest provider-model value
   and direct adapter consumer together; predefine one suitable model already
   shown by current catalog/legacy evidence; complete one real image batch.
   There is no registry, pool, retry engine, or public facade yet.
2. **Second transport proof.** Add one model using the other already-working
   Google/DashScope transport. Change the data boundary only where the second
   real consumer proves it necessary. RapidOCR and future local-model runtimes
   remain outside these first two transport slices.
3. **Merged image result and resume.** Accept explicit sources, settle ordered
   image slots into one Markdown, and prove two bounded live batches. Implement
   only single-provider dispatch first.
4. **Flat fallback and retry.** Use actual canonical errors from the live and
   legacy mappings. Prove stop-on-success/failure aggregation and resume with a
   different provider before adding parallel work.
5. **Nested lanes.** Add fixed assignment and lane-local last-success state.
   Prove no cross-lane calls and bounded completion. No dynamic balancing.
6. **Audio vertical slice.** Expose extraction and integer-minute splitting,
   then merged audio slots and resume. Perform one real short/whole or two-chunk
   request as appropriate to the current provider evidence.
7. **Visible video workflow and deletion.** Prove that a caller can run the
   public image and audio steps on real video and receive their two independent
   merged Markdown outputs, then delete the frozen video recognition/journal
   chain. Do not replace it with another convenience wrapper or cross-media
   composer. Repair is not a deletion gate.

Each phase must contain a real consumer, the smallest focused offline tests,
and a bounded live call where provider behavior is in scope. A green offline
suite alone does not prove a provider phase.

### 5.1 Historical first-phase proposal; authorization later granted by #656 (#597/#607)

At #607 the transport order was evidence-selected but implementation remained
paused until the schema-timing conflict and any other decision actually consumed
by the selected first preset were resolved or explicitly deferred. #656 later
resumed the pruned section-0 sequence; this subsection remains historical route
evidence rather than a competing entry order. #597 audited the
current resolver, shared
vision-call boundary, operation adapters, tests, and prior live evidence. It
found no additional provider-model field or framework decision that must block
the first internal proof.

**Route A (initially recommended, now deferred): native Google image first.** Use exact candidate
`gemini-2.5-flash` only if live discovery still serves it. The active and legacy
built-in Google paths already use native `google-genai`; the exact current
adapter owns catalog validation, request construction, canonical errors, token
usage, and client cleanup. `GoogleGenAISettings` contains only the optional
secret, so this is the smallest way to prove that durable model identity and
runtime settings remain separate. Existing bounded evidence already covers one
and eight-image requests plus independent audio input for this model.

**Route B (recommended after #599): DashScope image first.** Use exact `qwen3.5-ocr` through the existing
OpenAI-compatible DashScope adapter. It has the strongest direct formula-board
success evidence, but its region, endpoint, thinking, high-resolution option,
and optional credential pool make it a broader settings seam. The first slice
still receives those values through existing exact `DashScopeSettings`; they do
not enter durable model identity merely because DashScope is first. Native
Google becomes the second transport proof after its catalog works again.

#598 performed the required catalog-only refresh attempt without lifting the
implementation pause. The existing `list_google_genai_models()` path made one
authenticated `models.list()` request and no generation, upload, cache, or
write. It returned a typed timeout after 20 seconds. Windows proxy configuration
was enabled and its endpoint was reachable, but the child Python process had no
`HTTP_PROXY` or `HTTPS_PROXY`; therefore this result does not prove that
`gemini-2.5-flash` is absent and does not disqualify Route A. The next live
probe must pass the already-running system proxy to one child process through a
temporary environment, make one catalog request, emit only count and exact
candidate membership, and discard the copied key/proxy environment.

#599 performed exactly that corrected probe. The proxy endpoint was reachable,
the disposable process received only temporary uppercase proxy variables, and
one `models.list()` call returned typed `PROVIDER_REQUEST_INVALID` / request
scope after about 5.2 seconds. There was no generation, upload, other catalog
operation, or retry. This does not prove that `gemini-2.5-flash` is absent, but
it does leave Route A unable to satisfy its current-catalog entry gate. Route B
is therefore the evidence-backed first proof; Google follows after a later
catalog succeeds. Do not add automatic Windows-proxy discovery to the library
or retry generation to force the former order.

#600 repairs one existing public-helper defect exposed by that failure:
`list_google_genai_models()` now identifies `client_setup`, `catalog`, or
`cleanup` in its safe typed error details. Parsing the returned catalog remains
part of `catalog`; no parser stage, vendor body, retry hint, HTTP-policy layer,
proxy behavior, or provider-model code was added. This observability repair does
not change the DashScope-first order or lift the implementation pause.

#606 rechecked the DashScope catalog without recognition. One isolated request
returned 246 entries and contained both the pinned
`qwen3.7-plus-2026-05-26` baseline and `qwen3.5-ocr`. The first DashScope
candidate therefore remains currently discoverable. This does not authorize a
preset, runtime slice, full-catalog mirror, retry policy, or model switch.

After authorization, the first slice is limited to:

1. one internal immutable `ProviderModel` with the field set selected by
   #607's schema-timing decision and no root export;
2. one controlled `adapter_id` branch and one internal image consumer that
   receives the existing exact settings separately and reuses the existing
   operation adapter;
3. focused validation, secret-safe representation, capability-mismatch,
   resolver, response/usage, and typed-error regressions; and
4. one live-discovered DashScope `qwen3.5-ocr` request for a repo-owned formula
   board through that consumer,
   with at most one generation call, no retry, fallback, model substitution, or
   second provider.

The candidate becomes a shipped preset only after the new consumer returns
valid Markdown and preserves honest provider/model, call, token, and cleanup
evidence. A missing catalog row or typed provider failure is useful robustness
evidence but leaves this phase and preset gate open. The slice does not add a
public recognition facade, merged Markdown, resume, batchifier, retry engine,
provider list, registry, plugin system, local-model placeholder, or API pool.
The later merged-image phase, not this internal proof, owns the two live batches
of seven or eight images.

## 6. Maintainer Decisions And #607 Reopened Details

The decisions below remain explicit phase contracts except for the exact
subparts reopened in #607: audio scalar type within choice 4, preset scope in
choice 3, and complete-schema implementation timing within choice 8. The
first-success, successful-result reporting, reduction rule, output, invocation,
retry shape, token, resume-routing, and separate-output boundaries remain
fixed. Resolving a reopened detail does not itself lift the maintainer's
discussion-first implementation pause:

1. **Fixed flat-list success stop.** Visit each provider at most once per batch
   after its finite retry rule, and stop immediately on the first valid
   recognition. Calling later providers would be an unrequested ensemble with
   no result-selection or merge contract.
2. **Fixed successful-fallback reporting.** Return the completed
   `RecognitionResult` with ordered, bounded provider-failure records. Raise a
   typed error only when the logical slot remains incomplete; never turn a
   valid settled result into an attached-result exception.
3. **Reopened preset quantity; current safe default is bounded.** The recorded
   contract ships a small curated set of live-proven presets and
   use explicit construction/live discovery for other model IDs. Do not commit,
   generate, or synchronize every current Google/DashScope catalog row unless
   the maintainer explicitly confirms that the latest wording overturns this.
4. **Fixed common-minimum reduction; audio numeric type reopened.** A caller-
   supplied positive integer
   wins; audio also keeps explicit `-1` as whole-file mode. When omitted, one
   provider supplies its own positive applicable default; flat and nested
   shapes validate every candidate and use the minimum positive applicable
   default across the flattened shape. Image count and audio minutes retain
   separate validators, planners, identities, and sidecars.
5. **Fixed common output filename.** Every omitted output uses
   `<normalized-source-identity>_ocrllm.md`: a single image, audio file, or PDF
   uses its source stem, and an image/audio folder batch uses the folder name.
   Directory placement remains fixed in section 2.2. There is no media-specific
   suffix family or third combined-video Markdown name.
6. **Merged into fixed choice 4.** Image batch size and audio interval use
   different units and plan builders, but both use the same common-minimum
   provider-list reduction. They do not expose independent policy switches.
7. **Fixed finite retry rule.** Every canonical-code rule contains only
   non-negative finite `extra_retries` and `wait_seconds`. Reporting is
   determined by the recognition outcome, not repeated in retry configuration.
   Exhaustion records the last safe failure and advances to the next provider.
   The overlapping `error` / `next` / `current` labels are not retained.
8. **Fixed invocation/ownership boundary; runtime schema timing reopened
   (includes former choice 10).** The planned immutable `ProviderModel` stores
   only vendor, model, controlled
   adapter ID, three task-capability booleans, capability-dependent nullable
   image/audio defaults, and canonical finite retry rules. One explicit lazy
   resolver selects a known operation-specific adapter. Exact credentials,
   endpoint, request options, and timeout remain in adapter settings supplied
   separately at the call boundary; the existing injected Python protocol
   remains separate. Arbitrary callables, executables, generic options mappings,
   and hybrid ownership are rejected. #607 asks only whether all planned fields
   land in the first internal runtime class or land as real consumers appear;
   it does not reopen adapter/settings ownership.
9. **Fixed token persistence contract.** The sidecar keeps one cumulative
   aggregate per exact `(vendor, model)`: exact dispatched call count plus
   nullable input/output totals. It includes trustworthy evidence from failed
    attempts as well as settled slots and is merged before that same lane begins
    another provider attempt; parallel lanes already in flight do not wait. At
    invocation start, the loaded cumulative value is the
   historical baseline; this invocation's delta remains in memory as current
   usage. Results derive current/history views from those two values. Do not
   persist two labeled buckets or a per-attempt ledger. Slot state remains
   separate because resume needs settled content identity, not because token
   accounting needs itemized billing records.
10. **Merged into choice 8.** Field ownership and invocation ownership are one
    boundary decision. Keeping them separate would permit incoherent hybrids,
    such as a controlled adapter ID plus an unvalidated generic options bag, or
    an arbitrary callable that still depends on hidden adapter settings.
11. **Fixed package-root video resume route.** A thin root-exported
    `resume_video` delegates explicit image and audio sources to their ordinary
    resume functions and owns no video journal, publication transaction,
    output naming, composition, or cleanup lifecycle. This does not export
    internal state/sidecar helpers or settle experimental repair placement.
12. **Fixed separate media outputs.** "One Markdown" means one output for each
    merged image recognition call and one separate output for each merged audio
    recognition call. Independent recognizers never mutate one target. The
    current product has no final image-plus-audio artifact, shared document
    owner, or media-neutral composer. A later explicit maintainer request may
    reopen that as a new product feature; it is not retained as a current gate.

### 6.0 Decision blocks and implementation gates (#584)

The numbered choices remain useful evidence references, but they are not
twelve equal prerequisites:

| Implementation slice | Must resolve or honor first | May remain open |
| --- | --- | --- |
| First and second provider-model proofs | fixed combined choice 8/10 plus #607 schema-timing decision | audio type, preset quantity, extraction ownership, resume signature |
| Public presets and single-provider merged image + resume | provider-model gate, fixed choices 5/9/12, #607 preset/default decisions, and plain/detail selector | audio type, extraction ownership, resume signature |
| Flat fallback | fixed choices 1/2/4/7/9/12 and live evidence for any concrete retry values | audio type, extraction ownership, resume signature |
| Nested lanes | the complete flat-fallback gate | audio type, extraction ownership, resume signature |
| Merged audio + resume | fixed choices 5/9/12, proven provider boundary, and #607 audio-type decision | video-resume signature |
| Video-derived resume/publication and old-chain deletion | fixed choice 11 and every earlier replacement gate; fixed choice 12; #607 extraction ownership and exact stateless resume signature | none |

This ordering does not silently choose an open contract. It prevents an
unrelated late question from blocking earlier evidence and prevents an early
class from being built with fields required only by a later phase. In
particular, fixed choice 3 limits the committed public preset scope without
blocking one internal live model proof, and choice 11 fixes only one thin root
route rather than a video lifecycle owner.

Choice 3 is fixed by separating entity identity from shipped convenience. Every
supplied model is one provider-model entity, while only a small live-proven set
is committed as presets; other current catalog IDs use the same explicit
constructor after discovery. This satisfies the request for usable prebuilt
Google/DashScope entries without turning volatile vendor catalogs into package
source. Choice 2 is fixed by separating visibility from
exception semantics. An eventually successful slot returns its result with one
terminal safe failure record for each exhausted earlier provider; the final
failed-batch accumulator remains limited to genuinely failed slots. Choice 1 is
fixed by the one-result contract: "traverse once" limits revisiting while
unresolved and does not require paid calls after success. By contrast, former
choices 4 and 6 ask the same provider-list reduction question. #587 merges
them into choice 4, and #594 fixes the common-minimum rule: omission derives one
media-appropriate scalar from every candidate before planning. This is one
product decision, not permission for a generic cross-media planner. Choice
11's delegation behavior and package-root placement are fixed without deciding
the import placement of every media or repair helper.

### 6.1 Evidence for choices 1 and 2 (#572)

The active library already has one smaller same-provider precedent. Its ordered
model-candidate loop advances only after an eligible typed failure, stops at
the first valid result, returns that result normally, and records every prior
attempt in `metadata["model_attempts"]`. The focused regression proves a quota
failure followed by one successful recovery model. The legacy DashScope model
chain, Google model switcher, and Google audio candidate loop also return or
break immediately after the first valid result. None performs extra calls after
success.

The current public result boundary also constrains choice 2:

- `RecognitionResult` already owns immutable human warnings and JSON metadata;
- `BatchItemOutcome` requires exactly one result or one error for each item;
- `recognize_batch` treats a raised exception as that item's failure and closes
  the start gate, even if provider work had already produced valid text.

Choices 1 and 2 are fixed to Route A:

1. Rotate the flat candidate order to the lane's remembered successful start,
   attempt each candidate at most once, and stop immediately on the first valid
   recognition.
2. Return one ordinary `RecognitionResult`; keep `status="complete"` when the
   requested content is complete. Add one bounded human warning and an ordered
   `metadata["provider_failures"]` tuple for providers exhausted before success.
3. Each provider-failure record contains only the absolute zero-based
   `slot_index`, vendor, model, stable canonical code, and secret-safe bounded
   description. The successful provider/model remains the result's normal
   provider metadata; no duplicate success record is needed in the failure
   tuple.
4. Raise only if the logical recognition remains incomplete after the permitted
   candidates are exhausted. Failed-batch reporting still follows the fixed
   terminal-only rule in section 2.6.

This metadata proposal avoids a consumer-free `ProviderAttempt` public type.
It may be promoted to a typed field only if a second real consumer proves that
the JSON boundary is too weak. Route B would continue calling providers after
success and/or raise while attaching a valid result. It would need an undefined
winner/merge rule or a second result-plus-error wrapper, would violate the
current `BatchItemOutcome` invariant, and could cause a caller to replay paid
successful work. It is wider than the legacy and active behavior.

Surfacing the bounded records means returning them in the result, not raising
after successful recognition. Fixing choices 1 and 2 does not authorize
dispatcher implementation.

### 6.2 Evidence for choice 3 (#573)

Here, a **preset** means one ready-to-use `ProviderModel` value shipped by
OCRLLM. A row returned by a vendor catalog is discovery evidence, not a preset,
and an explicitly constructed `ProviderModel` is not a second model type.

The active library already accepts exact caller-supplied image and audio model
IDs. Google requires an explicit ID, lists the current catalog, and rechecks
membership before image, short-audio, and uploaded-audio dispatch. DashScope
has one live-proven pinned default and checks other exact IDs against its
current `/models` endpoint. Neither active adapter needs a committed full
catalog to dispatch a caller-selected model.

The vendor APIs also show why catalog membership is not capability proof:

- Google's official Models API lists current models and exposes generation
  methods and token limits, but does not declare that every
  `generateContent` model can perform OCR, detail OCR, or OCRLLM's audio
  workflow. Google's model guide separately distinguishes stable, preview,
  latest, and experimental names, and publishes shutdowns. See
  <https://ai.google.dev/api/models> and
  <https://ai.google.dev/gemini-api/docs/models>.
- DashScope's official `GET /api/v1/models` endpoint exposes richer declared
  modalities, features, context limits, regions, and deployment information.
  Its separate vision and ASR guides still define operation-specific image,
  duration, protocol, and format limits. A row is also account, workspace, and
  region dependent. See <https://help.aliyun.com/en/model-studio/list-models>,
  <https://help.aliyun.com/en/model-studio/vision-model>, and
  <https://help.aliyun.com/en/model-studio/asr-model>.

Legacy demonstrates the maintenance failure directly. It combines a large
static builtin list, cached live catalogs, name-based capability
classification, and hardcoded fallback IDs. Its DashScope classifier treats
nearly every ID that is not obviously audio-only as a vision model; its Google
cache and fallback list can outlive provider changes. That GUI-oriented product
also has custom-model validation, so the static mirror is not needed to keep
new IDs usable in the library.

Route A is fixed:

1. Ship only a small number of presets whose declared OCRLLM media capabilities
   have each passed a bounded real request. Exact initial model selection waits
   for its own vertical-slice evidence; this decision does not authorize a
   particular Google or DashScope model.
2. Let callers construct the same `ProviderModel` explicitly for every other
   model ID. Existing adapter catalog/preflight checks remain responsible for
   honest current availability; construction does not promise provider access.
3. Keep vendor-specific discovery as a query utility. It may supply IDs and
   provider-declared metadata to a caller, but it does not auto-create trusted
   presets, infer OCR quality, persist a cross-vendor registry, or rewrite the
   shipped preset set.
4. Add, replace, or retire a shipped preset only after a bounded live vertical
   slice or a real provider retirement creates that need. Do not synchronize
   the package to every catalog change.

Route B would commit or generate a `ProviderModel` for every currently listed
vendor model. It either copies incomplete vendor metadata as capability truth
or requires OCRLLM to test and maintain hundreds of combinations. A generated
module, catalog cache, auto-classifier, registry, and public
discovered-versus-proven state machine would then exist only to support that
mirror. They are rejected. The distinction between discovered, vendor-declared,
and live-proven remains an evidence rule, not a new public enum or framework.

Choice 3 is closed. This scope decision does not select a concrete initial
preset or authorize preset, constructor, discovery API, registry, or adapter
implementation.

### 6.3 Evidence for choice 4 (#574)

Image `batch_size` owns durable slot boundaries; it is not a provider retry
parameter. The current active code already resolves the strictest applicable
image count before grouping video frames, preserves caller-created groups in
`recognize_batch`, fingerprints ordered image sources and request-affecting
limits, and rejects mismatched resume identity before dispatch. Current legacy
PDF, board, and video paths likewise select one batch size before creating
their ordered batches; legacy PDF checkpoints include that size and reject a
different plan.

The smallest future rule is:

1. A caller-supplied positive integer wins unchanged. Do not silently clamp it
   to a provider recommendation. Complete source, output, provider-shape, and
   requested-task capability validation still happens before dispatch.
2. When omitted for one `ProviderModel`, use that model's positive
   `default_image_batch_size`.
3. When omitted for a flat or nested provider shape, flatten only for this
   calculation and take the minimum positive `default_image_batch_size` across
   every candidate. This does not permit fallback across nested lanes.
4. Resolve the number once before grouping sources. Persist the resolved number
   and exact ordered group membership in the image-batch sidecar; resume reuses
   them and does not recalculate from a changed provider list.
5. Fallback always receives the original group. If a provider rejects its image
   count, map and record that real provider failure and continue only according
   to the separately approved fallback rule. Exhaustion leaves a resumable
   failed slot. Choosing a smaller batch size creates a new plan rather than
   rewriting an existing resume plan.

The minimum is deliberately a conservative default, not a claimed hard vendor
limit. A real provider may still reject a request for output, context, quota,
or undocumented reasons. Conversely, an explicit larger value may succeed.
OCRLLM reports the actual result instead of silently splitting and replaying a
possibly paid slot.

The alternatives create worse contracts:

- **First-provider default** makes boundaries depend on list order while a lane
  may start later batches from its remembered successful provider. It can also
  hand an oversized immutable group to every fallback candidate after the
  first.
- **Lane-local defaults** require variable source windows whose boundaries
  depend on round-robin assignment. Preserving those windows across fallback
  and resume needs a lane planner and more state before any live nested-lane
  consumer exists.
- **Explicit-only for multiple providers** is simpler but contradicts the fixed
  requirement that OCRLLM derive a provider-informed default when the caller
  omits the value.

Do not add adaptive shrinking, binary-search retries, dynamic repacking,
per-lane batch queues, or a throughput optimizer. One validated integer, one
ordered tuple of groups, and the existing slot-sidecar direction are enough.

Combined choice 4 is closed to the common-minimum rule. This decision does not
authorize a batchifier, fallback dispatcher, sidecar schema, or provider
implementation.

### 6.4 Evidence for choice 5 (#575)

Current naming is not one future contract. Active single-image and PDF output
uses `<first-source>[_plus_N]_<profile>.md` under an explicit
`Config.output_dir`; current long audio and the old video job instead create a
source-named directory containing `result.md`. Legacy adds separate Chinese
board, audio, PDF, and video names and guesses a multi-image name from a common
prefix or parent directory. Those schemes describe their own shipped products;
combining them would preserve several incompatible defaults rather than make
the new library predictable.

Route A is fixed as the smallest future rule:

1. An explicit output Markdown path always wins. Default resolution runs only
   when the caller omits it.
2. Use `<normalized-source-identity>_ocrllm.md` for every default. A single
   image, audio file, or PDF uses its source stem. An image/audio folder batch
   uses the containing folder name. Placement remains exactly section 2.2:
   beside a single source and beside the batch folder. The visible video
   workflow has no third combined output name.
3. Recognize, resume, and repair resolve that same path from the same explicit
   source identity. They do not scan directories, infer a common filename
   prefix, or choose a different existing file.
4. A new recognition refuses an existing target and duplicate/colliding
   targets are rejected during preflight before provider dispatch. There is no
   automatic numbering, timestamp, hash suffix, overwrite-by-default, or
   persistent naming registry. An unusual same-stem image/audio collision is
   resolved by an explicit output path rather than another default branch.
5. Video-derived image and audio calls resolve their own distinct targets under
   the same media rules. They do not intentionally share an explicit target,
   and OCRLLM does not derive a third video Markdown target.

Route B, with media-specific `_image.md`, `_audio.md`, and `_video.md` suffixes,
is rejected. It avoids one rare cross-media same-stem collision but duplicates
media type in the naming contract and preserves an unused `_video.md` case. The
fixed `_ocrllm.md` suffix already marks a derived artifact; strict collision
refusal plus explicit paths is enough.

Keep the existing narrow path-component normalization because Windows path
length caused a real legacy failure. Do not turn it into auto-shortening based
on directory contents, a collision allocator, cross-process lock, or output
transaction framework. The current in-process target claim is implementation
evidence for rejecting simultaneous ownership, not permission to generalize it.

Choice 5 is closed to the common `_ocrllm.md` suffix. This decision does not
authorize output-routing, resume, repair, cross-media composition, or runtime
changes.

### 6.5 Evidence for choice 6 (#576)

Audio interval duration is durable slot identity, not a provider retry knob.
The active long-audio path already builds deterministic logical windows with
fixed boundary context, fingerprints every exact window, and persists the
whole/interval mode, positive `interval_minutes`, ordered fingerprints, and
settled prefix. A changed interval is rejected before materialization or a
provider call. Video's current journal likewise binds its audio mode and
interval and rejects a changed resume request. Legacy Google audio uses a
30-minute logical default and saves exact window boundaries, but that is one
provider path's evidence rather than a universal hard limit.

The smallest future rule is:

1. Validate the complete provider shape and audio capability before creating
   media. Every `ProviderModel` involved in this calculation must carry one
   positive integer `default_audio_minutes`.
2. A caller-supplied positive integer wins unchanged. A caller-supplied `-1`
   also wins and means whole-file mode. Normalize `-1` immediately to the
   internal identity `mode="whole", interval_minutes=None`; do not persist a
   negative duration or create two whole-file identities.
3. When the interval is omitted for one provider, use that provider's positive
   suggested default. For flat or nested provider shapes, flatten only for this
   scalar calculation and take the minimum positive suggestion across every
   candidate. This does not permit fallback across nested lanes.
4. Resolve the mode and minutes once before splitting. Persist the normalized
   mode, resolved minutes, and exact ordered windows with the audio batch plan.
   Resume and provider fallback reuse that plan and never recompute it from a
   changed provider list.
5. A provider suggestion is not a hard limit. An explicit larger interval or
   whole-file request is not silently clamped. If the selected provider rejects
   the fixed audio duration, record the provider failure and advance only under
   the separately approved fallback rule; changing the split creates a new
   plan rather than masquerading as resume.

Using the first provider's default makes immutable windows depend on list order
even though later batches may start from a remembered successful provider.
Lane-local defaults couple time ranges to round-robin assignment and require a
variable-window scheduler plus more persisted mapping. Requiring an explicit
interval for multiple providers contradicts the fixed requirement that
`split_audio` may derive one from a model shape. The global minimum may create
more calls than a larger provider needs, but it adds no alternate identity or
scheduler.

Do not add adaptive shortening, binary-search re-splitting, provider-specific
window queues, automatic whole-to-interval fallback, or a second public
sentinel. The current public long-audio API still rejects `-1`; accepting and
normalizing it belongs to the future replacement entry and is not a defect in
the shipped API during the implementation pause.

The provider-list reduction is no longer a separate choice 6; #587 combines it
with choice 4, and #594 fixes the common-minimum rule. This evidence does not
authorize `split_audio`, provider defaults, audio batching, fallback, sidecar
changes, or runtime implementation.

#587 deliberately shares only the reduction invariant: explicit scalar wins;
otherwise inspect every validated candidate's applicable positive default and
resolve one scalar before slot planning; fallback and resume then reuse the
same immutable plan. It does not introduce a `MediaPlan`, generic unit field,
cross-media batchifier, or common image/audio sidecar. Images still plan exact
path groups by count. Audio still plans time windows in integer minutes and
normalizes explicit `-1` to whole mode. First-provider reduction is the only
remaining alternative because it would make both plans depend on list order
even though later work may start from a remembered successful provider.

### 6.6 Evidence for choice 7 (#577)

The active Google and DashScope adapters already prove that a raw HTTP number
is not a portable retry key. Google `429` may become model-scoped quota
exhaustion or provider-scoped rate limiting, while `503` may become ordinary
unavailability or high-demand rate limiting. DashScope likewise combines the
structured provider code, status, and safe message evidence before producing a
canonical OCRLLM provider error. Therefore a future `ProviderModel` rule is
keyed by the canonical code after adapter mapping; raw status and provider code
remain bounded diagnostic details.

The active adapters deliberately make one request per adapter call. The
existing `ProviderErrorDisposition` describes evidence such as retry,
cooldown, credential quarantine, and failure scope, but does not execute those
actions. The current image candidate loop only advances for a narrow set of
model-scoped canonical failures and stops at first success. A replacement
dispatcher must not layer another ambiguous action vocabulary over these
facts.

Legacy Google supplies the real behavior worth retaining selectively: it
distinguishes same-model retry from model switching, uses finite attempts, can
honor a structured provider retry delay, and changes models only for classified
failures. Legacy's `max_retries` name actually counts total attempts, while the
new proposal says "retry six times" after an initial call. The future field is
therefore named `extra_retries`: zero means one initial call only; `N` means at
most `N` additional calls to that same provider/model. `wait_seconds` applies
before each additional call. There is no post-exhaustion sleep.

Route A is the smallest complete rule:

1. Map the vendor failure to one canonical OCRLLM code and safe scope before
   consulting policy.
2. Look up that canonical code in the selected `ProviderModel`. A missing rule
   means zero extra retries. All counts are non-negative and finite; no `-1`,
   unbounded wait, exponential engine, or dynamically learned policy exists.
3. Retry only the same provider/model for the configured additional calls. A
   future adapter may expose a structured vendor retry delay only after one
   live path proves it; the first slice does not add a generic hint parser.
4. After success, stop immediately. After exhaustion, retain only the last
   safe failure for this provider and advance immediately to the next candidate.
   If the lane has no candidate left, the batch remains an honest resumable
   failure.
5. Capability, source, configuration, and preflight validation failures are
   outside this retry table and retain their zero-provider-call behavior.
6. Outcome reporting follows choices 1 and 2: completed recognition returns
   normally with bounded earlier-provider evidence; incomplete recognition is
   an error. Retry configuration has no `severity` field.

The proposed `error`, `next`, and `current` labels do not describe
three transitions: every example performs finite same-candidate retries and
then advances. Retaining them would duplicate retry count, exhaustion, and
outcome-reporting semantics. The rejected Route B keeps an action label or adds independent
`retry_current`, `advance_candidate`, and reporting controls. It is justified
only if a concrete provider error must terminate a lane or remain on one
candidate after its finite retries; no supplied example or current consumer
requires that branch.

#590 fixes Route A. The existing `ProviderErrorDisposition.action` remains a
separate evidence and credential-pool boundary with real distinct meanings such
as cooldown, quarantine, and stop; it is not copied into `ProviderModel` retry
configuration. This decision does not implement a retry engine, provider
dispatcher, new error mapping, retry-hint parser, preset, or runtime change.

### 6.7 Evidence for choice 8 (#578)

The active library already contains both candidate mechanisms, but for
different jobs. Built-in Google and DashScope settings are resolved by exact
type to lazily imported operation modules. Those modules own SDK loading,
credential resolution, request construction, response parsing, canonical error
mapping, and client cleanup. Separately, `VisionProvider` accepts an injected
Python object with a callable `recognize_images` method. The injected object is
useful for tests and advanced Python integration, but it is opaque, not
serializable, and may hide secrets or live resources.

Legacy shows why those mechanisms must not be folded into one model entity.
Its general client combines OpenAI-compatible clients, a vision client, Codex
CLI execution, wire-protocol choice, retry, and model fallback. Its Google
client also retains unavailable-model and last-success state, while the hybrid
client silently routes different media to different internal clients. These
paths prove that an invocation may be native SDK, compatible HTTP SDK, local
engine, or CLI; they do not justify storing the executable implementation or
mutable client state in `ProviderModel`.

Route A keeps the first built-in boundary closed and explicit:

1. `ProviderModel.adapter_id` is a validated data value identifying one actual
   transport, such as native Google GenAI or DashScope's OpenAI-compatible
   endpoint. It is not merely the vendor name because one vendor may expose
   more than one protocol.
2. One small resolver uses explicit branches for the adapter IDs shipped by
   OCRLLM and lazily imports the corresponding operation module. It is not a
   mutable registry, entry-point system, dotted-module loader, or plugin
   discovery mechanism.
3. Adapter modules expose operation-specific calls such as image or audio
   recognition. They create and close SDK clients inside a call and retain
   vendor request building, response parsing, and canonical error mapping.
4. Fallback order, finite retry execution, lane-local last success, and token
   aggregation remain recognition-call state. They do not move into an adapter
   or a provider-model preset.
5. Credentials and credential pools remain call/runtime data outside durable
   provider-model identity. The first real adapter reuses its existing exact
   settings boundary; do not create a generic credential registry before the
   second transport proves what common shape is required.
6. The shipped injected-provider protocol remains available on its existing
   API. The replacement batch API does not automatically accept it or wrap it
   in a `ProviderModel`; that is reconsidered only for a real new consumer.

Route B stores a callable/protocol object in every provider-model value. It
makes dependency injection convenient, but also makes identity, equality,
safe representation, lifecycle ownership, and future Python-to-process input
opaque. It duplicates the existing injected-provider boundary and encourages
open clients, upload handles, credentials, or fallback state to travel with a
model description. A subclass per vendor/model has the same problem with more
files. A single sparse object with every SDK's optional fields is another form
of the same god object.

Route A is fixed because it preserves extensibility by adding one honest
transport adapter in code, not by pretending arbitrary execution is data. It
also remains compatible with a future Python backend called by Electron: the
front end sends ordinary data, while only the backend resolves and executes
the adapter. #585 merges field ownership into this same Route A/B gate; choice
10 is not a second approval, and #589 closes the combined choice. The first
single-provider proof may accept its existing exact settings type directly. A
later multi-provider consumer must prove how several exact settings instances
are bound at the call boundary; that call-shape question cannot move generic
options or secrets into durable model identity. No `ProviderModel`, resolver,
registry, credential type, adapter, or public batch API is implemented by this
decision.

### 6.8 Evidence for choice 9 (#579)

The active adapters already preserve only trustworthy non-negative integer
usage. Google can attach provider-reported usage to a typed error when content
validation fails after the response is received; DashScope and other paths may
have no usage for an error. The shared aggregator makes an affected token
dimension `None` when any included observation lacks that dimension, rather
than presenting a known partial sum as an exact total.

Current resume evidence is asymmetric. Long-audio settled slots persist token
counts and expose historical usage separately from current calls. Image resume
clears current usage for a reused slot, correctly preventing double counting,
but its state does not retain historical token totals. All current aggregation
keys use only the model string. That is adequate for the shipped single-vendor
identity assumptions, but it would conflate two future provider-model values
that expose the same model string.

The smallest replacement contract keeps one bounded cumulative aggregate per
exact `(vendor, model)`: exact dispatched call count and nullable input/output
tokens. Each adapter contributes usage once at its response boundary. A
response-validation failure may contribute usage when the provider actually
reported it; a call without trustworthy usage makes the affected cumulative
dimension unknown rather than zero. Updated cumulative evidence is merged by
one narrow state owner before that same lane advances to another provider
attempt, so a process loss does not erase a paid failed call. Other lanes may
already be in flight; this rule is not a global persistence barrier.

The sidecar does not persist separate current and historical aggregates. The
loaded cumulative value is the next invocation's historical baseline, while
new in-memory deltas are current; result metadata can derive both without a
second durable bucket. Resume still requires ordered settled-slot content and
identity. Current long audio stores call/token facts per settled slot and
derives current/history at composition time, while current image state stores
calls but loses historical tokens on reuse. Those shipped shapes are evidence,
not the future schema.

Persisting only successful-slot usage loses reported failed-attempt cost. A
public per-attempt ledger duplicates retry/error state, while two labeled
durable current/history buckets duplicate the same cumulative evidence across
invocations. The one-cumulative-plus-current-delta contract is fixed by #586 as
the smallest honest interpretation of the maintainer's per-model accumulation
rule. No token schema, provider model, dispatcher, state, runtime, test, or
public API changed in this documentation audit.

### 6.9 Evidence for choice 10 (#580)

The active library already separates four responsibilities, although its
current `Config` predates the replacement API. Model names live in vision/audio
model settings. Exact Google/DashScope provider settings own credentials and,
for DashScope, region, endpoint and evidence-affecting request toggles. The
recognition execution policy owns image-count overrides, concurrency and start
interval. Adapters own prompts, media serialization, SDK clients, catalog
checks, upload lifecycle, timeout use, error mapping and cleanup. Call counts,
tokens, cancellation and last-success routing are invocation state.

This separation is not cosmetic. DashScope `enable_thinking` and
`vl_high_resolution_images` directly alter one request, while its region and
base URL select a catalog and endpoint. Google settings currently contain only
an optional secret. The two adapters therefore do not prove one honest generic
`call_parameters` shape. Their shared durable facts are the provider/model
identity, the adapter route, product-supported media tasks and the defaults
that future batching/splitting actually consumes.

Legacy is the counterexample. Its API, independent vision, Google, Codex and
model sections repeat model names, endpoints, keys, wire protocol, effort,
batch sizes, concurrency, stagger, media routing and candidate queues. Enabling
one path copies values into several sections; the general client may borrow a
different provider's credential, choose Chat or Responses, route audio by URL
family, retry, switch models and keep mutable clients. Google and the API pool
also combine last-success/unavailable-model memory, credential slots and call
counters. Those behaviors solved real application problems, but they are not a
durable model description to port.

Route A therefore uses one frozen `ProviderModel` with vendor, model,
`adapter_id`, three explicit capability booleans, nullable capability-dependent
image/audio defaults, and immutable canonical retry rules. Detail-image OCR
requires plain-image OCR. Image defaults are positive exactly when image OCR is
supported; audio defaults are positive exactly when audio is supported. The
first adapter continues to receive its existing exact settings separately.
There is no dummy image/audio default for an unsupported task.

The rejected Route B adds a sparse generic options list/mapping containing credentials,
endpoint, Chat/Responses choice, effort and future SDK switches. It initially
looks convenient but loses validation, mixes secrets with durable values and
recreates the legacy cross-provider configuration blob. A subclass per model
has the same coupling with more files. Route A is fixed by #589. #585 confirms
that this is the same ownership decision as choice 8 rather than another gate:
`adapter_id` is useful only if adapter-specific settings remain outside the
model value. This audit does not implement or authorize a provider model,
common settings type, adapter, preset, registry, retry engine, dispatcher, or
public API.

### 6.10 Fixed local-execution boundary (#581)

The active local OCR path is already an explicit, working strategy rather than
an unfinished cloud-provider adapter. `Config(image_mode="ocr")` selects
`LocalOCRSettings`; RapidOCR loads only on execution, processes ordered images
without provider/network calls, returns the shared result shape, and reuses its
stable `image.ocr.rapidocr.v1` completed-result resume identity. Provider-model
validation is bypassed for this path deliberately. The shared image sidecar may
wrap a local completed result, but local OCR does not invent paid provider
slots or provider token usage.

Route A keeps this stable path unchanged while the first replacement vertical
slices prove Google and DashScope. A future concrete local VLLM/Ollama or
in-process OCR consumer enters through the same controlled `adapter_id`
boundary and the same `ProviderModel` type only when its operation contract,
optional dependency, and real call path are proven together. Route B moves
RapidOCR and placeholder local runtimes into the first model abstraction now;
it would force false common semantics for credentials, retries, call counts,
tokens, batching, and resume without a consumer. Route A is fixed as the
current boundary. This is not an eleventh provider-model choice and authorizes
no local adapter, preset, resolver branch, dependency, or API change.

### 6.11 Evidence for choice 11 (#582)

The shipped resume owners are not interchangeable wrappers. Image recognition
uses `Config.resume=True` and an output-adjacent image state; long-audio
recognition uses its own whole/interval state and removes that state only after
durable publication. `recognize_batch()` delegates to the item recognizers and
does not own a combined resume record. The low-level `recognize_video()` is not
resumable, while `recognize_video_to_markdown(..., resume=True)` can resume only
because it owns a third video journal, fixed result path, source/branch
validation, final composition, publication, and cleanup. It even rejects
branch-level persistence so that its journal remains the sole owner.

The #582 audit correctly rejected any router that defines partial completion,
write ordering, sidecar discovery, final publication, or cleanup; those duties
would recreate a video lifecycle owner, and translating the old journal would
add a rejected compatibility format. The later direct maintainer wording is
more specific about the public shape: `resume_video` routes to the ordinary
image and audio resume functions. #584 therefore fixes that routing behavior,
and #596 fixes its package-root export. #588 fixes separate image and audio
outputs and removes cross-media composition from the current product; it is not
a resume responsibility. No exact signature, result aggregate, runtime, export,
sidecar, or deletion changes with this documentation reconciliation.

### 6.12 Evidence for choice 12 (#583)

The shipped output paths have one writer, not a shared-section protocol.
`write_markdown_atomically()` publishes a complete file and rejects an existing
target unless overwrite or an owning resume path has been selected.
`OutputTargetClaims` prevents overlapping ownership but does not merge later
writes. Image and long-audio recognition each own different sidecars and final
publication rules. The current `recognize_batch()` returns ordered independent
item outcomes and preflights duplicate output targets; it is not the future
merged-Markdown recognizer.

The existing successful precedents all have one final writer. PDF child groups
return results to the PDF owner, which adds page-range markers and publishes one
complete document. Long audio saves settled windows in its sidecar and publishes
one complete document only after composition. The frozen video chain also
composes branch results before a single publication; its safety does not prove
that independent branch recognizers can append to the same target. Today only
PDF success ranges have Markdown markers. Image slot IDs and audio window IDs
live in their separate JSON state; there is no generic Markdown section-update
or repair-marker implementation.

The fixed current route keeps each merged media recognizer responsible for one
output and one state owner. Video-derived image and audio text do not
additionally become one OCRLLM-owned artifact. Independent recognizers reading,
validating, replacing, or coordinating sections of one existing file would add
shared markers, cross-branch state, locking, and conflict rules and remains
rejected. A separate pure composer is also removed from the current plan: no
direct requirement consumes it, and retaining a narrowly specified
hypothetical subsystem is still over-design. A future explicit request for one
cross-media deliverable is a new feature decision, not an unresolved choice 12.

Two choices formerly listed here are now fixed by the latest instruction. The
old video recognition/journal product is removed after the section 7
replacement gate rather than preserved as a compatibility line; no deletion is
performed during the current discussion pause. A failed batch retains only its
last provider/code/description; completed batches that encountered earlier
provider failures are governed by decision 2 above.

## 7. Gate For Deleting The Old Video Chain

Deletion requires all of the following, and does not require repair:

- one merged image Markdown run with ordinary resume proven;
- one merged audio Markdown run with ordinary resume proven;
- two independently resumable merged media outputs, with no cross-media writer
  or composition proof;
- explicit-source and output-default behavior documented;
- caller-invoked extraction outputs remain caller-owned; only extraction-local
  rejected candidates and temporary files follow their documented cleanup;
- package import remains lightweight;
- old public consumers and tests are either migrated or deliberately removed;
- focused tests, full offline suite, and bounded live evidence are green.

Until that gate closes, the old video chain describes shipped behavior but is
frozen rather than a target for further fixes or features.

#570 already proves that the retained public inspection, full-frame extraction,
and audio extraction primitives work independently on one real archive video.
It does not satisfy the merged-Markdown or image/audio batch-resume gates and
therefore does not authorize early deletion.

## #616 Official-Catalog Evidence: Discovery Rows Are Not Executable Presets

The current official [Google Models API](https://ai.google.dev/api/models)
documents identity, version, description, input/output token limits, supported
generation methods, a thinking flag, and sampling defaults. It does not expose
input/output media modalities, ordinary OCR versus detail OCR fitness,
OCRLLM-recommended image batch size, OCRLLM-recommended audio minutes, or a
per-model retry policy. Model guides document media behavior separately. The
active parser intentionally keeps only ordered `generateContent` model IDs;
the long-audio path separately reads the selected row's optional input-token
limit because that field has a direct proven consumer.

The current official DashScope
[native model-list API](https://help.aliyun.com/zh/model-studio/list-models)
is richer: `/api/v1/models` documents capability tags such as `VU`, `ASR`, and
`Reasoning`, request/response modalities, context and output limits, pricing,
region/deployment metadata, and pagination. It still does not supply ordinary
versus detail OCR quality, OCRLLM-recommended image grouping, recommended audio
minutes, or a per-model retry policy. It is also not the current active
adapter's endpoint or response contract: that adapter calls the configured
OpenAI-compatible `/models` URL and deliberately retains exact IDs only.
Changing catalog transport is a separate live-proven adapter slice, not a
documentation shortcut.

Therefore three concepts must not be collapsed:

1. a **catalog descriptor** is transient provider metadata and may exist for
   every currently served model;
2. an **executable curated preset** supplies the complete OCRLLM capability and
   default contract and requires official plus bounded live evidence; and
3. an **explicit custom model** remains possible when the caller supplies the
   facts absent from the catalog and accepts that contract.

This does not require a new public `DiscoveredProviderModel` class now. Existing
catalog functions can grow a typed descriptor only when a real catalog consumer
needs more than identity. A checked-in class or preset per catalog row would
either invent required fields, mark usable models falsely unsupported, or need
continuous edits as regional catalogs change. A persistent full-catalog mirror
therefore remains unrecommended. The maintainer still needs to confirm whether
"save every model" means bounded runtime/TTL discovery descriptors (compatible
with this route) or a source-controlled executable mirror (an explicit reversal
of the earlier maintenance rule).

## #617 Recommended Runtime Binding: Model Facts Stay Separate From Call Settings

One runnable candidate needs both a durable model description and the exact
adapter settings that make that candidate callable. Those values have different
lifetimes. `ProviderModel` is secret-free, reusable model/preset data. Google,
DashScope, and later local settings may contain credentials, region or base URL,
and adapter-specific switches and are valid only at a runtime call boundary.

Two tempting shapes are rejected. Putting settings inside `ProviderModel`
contaminates a shareable preset with secrets and account/endpoint choices.
Passing a model tree plus a parallel settings mapping leaves ambiguous pairings
for duplicate vendors, models, regions, or accounts and becomes positional
state that every caller must keep synchronized.

The recommended later public shape is one short-lived, frozen two-field value,
provisionally named `ProviderBinding`:

```python
ProviderBinding(
    model=QWEN_3_5_OCR,
    settings=dashscope_settings,
)
```

Each scalar, flat fallback list, or nested lane list contains complete bindings,
not bare models plus a second structure. Complete preflight must verify that the
controlled `adapter_id` and the exact settings type agree before media work or
provider dispatch. Internally, the three accepted shapes may be snapshotted to
immutable tuples; this is a provider plan normalization, not another batch
abstraction.

The binding does not own a callable, client, registry entry, generic options
mapping, retry state, token totals, error history, lane position, source, output,
prompt, timeout, or cancellation. OCRLLM continues to resolve `adapter_id`
through private known adapter modules. Secrets and the settings object are never
serialized. A future resume record may persist only human-readable vendor/model
plus a versioned secret-free fingerprint of explicitly selected output-affecting
settings; it must not serialize arbitrary settings or a provider candidate tree.

This decision is staged. The first internal single-provider proof may continue
to accept separate named `model` and exact `settings` arguments. Do not add the
public binding type until the first public merged recognizer or flat-provider
consumer actually needs it, and do not retrofit list semantics into the current
`Config.provider`. The public name, exact constructor, duplicate-binding rule,
and settled-slot safe-setting audit fields remain slice-local API choices. New
merged APIs should not accept two competing provider sources such as both
`Config.provider` and `providers=`.

## #618 Provider Defaults Belong To Visible Media Planning

The current implementation supplies two useful facts. Video grouping resolves
one effective image count before creating ordered tuple groups, and provider
fallback never changes those groups. Long-audio interval mode builds exact
integer-minute logical/actual windows, persists the normalized mode, minutes,
ordered request fingerprints and settled prefix, and rejects a changed plan
before materialization or provider dispatch. The replacement should preserve
those invariants without copying the video journal or provider-bound audio
fingerprint.

Three ownership routes were compared. Explicit-only planning would force
callers to duplicate curated defaults and contradict the requested omitted-
argument behavior. Dispatch-time planning from `ProviderBinding` would couple
media boundaries to credentials and whichever fallback happens to run, and it
would hide batchification/splitting inside recognition. The selected narrow
route lets the visible planning functions inspect only secret-free
`ProviderModel` facts.

`batchify_images` and `split_audio` therefore accept an explicit scalar, a
scalar/flat/nested `ProviderModel` shape, or both. An explicit positive value
wins; audio additionally accepts `-1` and immediately normalizes it to whole
mode. When omitted, completely validate applicable capabilities/defaults and
take the minimum positive exact integer across all candidates. Resolve one
ordered plan before recognition. Nested lanes do not receive different media
boundaries, fallback does not re-plan, and resume reuses the saved plan rather
than the current provider list.

Recognition and resume instead accept `ProviderBinding` leaves because those
operations need exact settings. This is not two provider abstractions:
`ProviderModel` is durable model data and `ProviderBinding` is the runtime pair
defined in #617. Do not pass bindings into planning, bare models into dispatch,
or parallel settings trees into either.

For images, exact ordered tuple groups are sufficient; no `ImageBatchPlan`
value is added. For audio, current overlap semantics prove that bare segment
paths are incomplete because recognition also needs logical versus actual time
ranges. #619 selects one small audio-specific immutable `AudioSlice` descriptor
rather than a generic media-plan type or hidden recognition-owned splitting.

The latest `float` wording remains a direct unresolved conflict. Current
validation, window construction, state and resume identity all require exact
positive integer minutes, and fractional minutes would add rounding and durable
identity rules. `ProviderModel.default_audio_minutes` therefore remains
`int | None` unless the maintainer explicitly reverses the integer-only
decision. No runtime or public API is authorized by this clarification.

## #619 Audio Splitting Returns Descriptors, Not Retained Chunks

Both the legacy Google parent and the active library prove that a physical
overlap-padded MP3 is not a complete slice identity. Interior logical ranges
are contiguous, while each physical range adds 30 seconds on both eligible
sides; adjacent interior files therefore share up to 60 seconds. Their opaque
filenames do not say which words belong to which output slot. A range-aware
prompt needs original-source and clip-relative logical/actual coordinates to
exclude that context from the returned transcript.

Three output routes were compared. Returning persistent `Path` values would
lose the logical ownership ranges or require a second manifest/filename
protocol, and it would retain a full extra set of files for sources up to ten
hours. A context-managed generator or job owner would force recognition into
one process lifetime, obstruct later resume, and recreate the removed video
lifecycle owner. The selected narrow route returns an exact tuple of immutable
audio-specific descriptors:

```python
AudioSlice(
    source=source_path,
    index=0,
    logical_start_seconds=0.0,
    logical_end_seconds=1800.0,
    actual_start_seconds=0.0,
    actual_end_seconds=1830.0,
)
```

The value contains only the caller-owned source `Path`, a stable zero-based
index, and the exact four range coordinates. It contains no materialized path,
provider/model, binding/settings, prompt, output, retry/token/error state,
cleanup method, source hash, or generic options. `split_audio` freezes these
boundaries without creating durable segment files. A whole-file `-1` plan is
one slice whose logical and actual ranges cover the inspected source.

Recognition validates the exact tuple and explicit sources, snapshots/hash-
checks source content, and privately materializes the already-selected actual
range only while its logical slot is active. It may reuse that physical clip
across the slot's finite fallback attempts, then deletes it even on failure.
Changing the descriptor is a new plan, not resume. Resume persists normalized
mode/minutes, ordered range/source identity and sparse settled slots; it never
persists temporary clip paths or requires old clips to survive. Actual
provider/model/usage belongs only to settled evidence.

This preserves the existing bounded-storage mechanism: the active library
already snapshots in streaming chunks, validates long audio without loading
all PCM into Python memory, materializes one missing interval inside a cleanup
context, and rematerializes it from the source during resume. The future nested
scheduler may have more than one active lane, but no design pre-materializes
all slices or adds a cleanup registry.

Legacy supplies warnings rather than architecture to copy. Its Google chunks
are created under a temp directory with no matching normal cleanup in the
long-audio path, its custom recognized-text checkpoint is not removed on
ordinary success, and matching cached segments are considered regardless of
the public `resume` flag. The active one-slice context manager already avoids
the file leak. Do not port the legacy chunk directory, custom checkpoint,
repair manifest, configurable overlap, or cache semantics. Repair remains the
separate experimental side path and may reuse exact saved ranges only when its
own narrow consumer is approved.

No `AudioPlan`, base media-slice class, public context manager, persistent chunk
archive, transcript similarity deduplicator, or second checkpoint system is
authorized. The `AudioSlice` name and minimum facts are recommended for the
later implementation slice; no runtime or public API changes in #619.

## #620 Nested Lanes Advance Independently

The maintainer's first-epoch wording is interpreted as initial fixed fan-out,
not a reusable global barrier. A strict barrier would make every lane wait for
the slowest provider or longest retry sequence and would still need indexed
settlement, serialized state merging, and deterministic output ordering. It
adds synchronization without protecting a result. Dynamic work stealing either
breaks fixed assignment or recreates the same lane semantics behind a more
general scheduler. Both routes are rejected.

For lane `j`, the immutable slot sequence is `j, j + lane_count, ...`. Each lane
processes at most one of its slots at a time and may start its next slot only
after the current slot's result, terminal failure, and usage evidence have been
settled. Other lanes do not wait for it. An ordinary failed slot does not stop
later slots in that lane or any other lane, and no slot moves to another lane.
The lane's remembered starting provider changes only after a valid success; a
fully failed slot leaves the most recent successful start unchanged.

Completion order is never public order. Execution reserves the complete indexed
slot table before dispatch, stores every outcome by original batch index, and
composes Markdown, failed-slot markers, terminal errors, warnings, and stable
token rows in original order. Parallel completion requires one narrow owner to
merge and atomically replace sparse resume state; it does not require a
transaction framework, epoch record, per-lane checkpoint, or completion-order
ledger. Epoch number and lane-local last-success state are not persisted.

Cancellation remains call-wide control rather than an ordinary batch failure:
stop new slots and new fallback attempts, settle every already-dispatched paid
call, and leave unresolved indexed slots resumable. Current `recognize_batch()`
supplies useful precedents for full preflight, bounded dispatch, indexed
outcomes, and settlement of dispatched work, but its global fail-fast gate and
contiguous not-attempted suffix cannot be reused for this continue-after-failure
scheduler.

Concurrency remains bounded, with at most one active slot per lane and no
unbounded thread creation. #620 deliberately does not invent a second worker
setting or silently decide how a future nested API combines outer-list lane
count with the existing `max_parallel_requests` setting. That exact admission
rule belongs to the nested-lane implementation slice; it must preserve fixed
assignment and bounded progress without adding global rounds or fairness/work-
stealing machinery. #621 records the current one-authority recommendation.
Resume bootstrap is narrowed by #622 below: settled slots are reused, while
every new invocation starts its newly supplied lanes at their first binding.

No scheduler, provider plan, runtime, test, state format, public API, provider
call, dependency, or deletion is added by #620.

## #621 One Concurrency Authority For Nested Lanes

Current `RecognitionExecutionPolicy.max_parallel_requests` belongs to the
shipped independent-output `recognize_batch()` executor. It defaults to one,
is bounded to 32, and is its only runtime scheduler input. Direct recognition,
PDF grouping, standalone long audio, and the journal-backed video branches do
not uniformly consume that field. It is also copied into the current provider-
bound image request fingerprint even where scheduling does not change one
logical slot. These are current compatibility facts, not a clean replacement
contract to copy.

Three routes were compared. Making the nested outer list the sole concurrency
topology gives one fact: `lane_count = len(provider_lanes)`, one active slot per
lane, and a maximum of `lane_count` active slots. Reusing
`max_parallel_requests` as a smaller cap makes the default silently serialize
the requested pool and requires queued-lane fairness; requiring equality makes
the caller state the same number twice. Both dual-control routes add surprise
without changing fixed assignment.

The recommendation later confirmed by #631 is that the replacement merged API
does not expose or consume
`max_parallel_requests`. A nested provider plan owns its concurrency and must
have at most 32 lanes, reusing the existing safety ceiling; an excessive plan
is rejected during complete preflight with zero provider, media, or output
work. Scalar and flat fallback plans remain one lane. The shipped Config-based
APIs and their execution policy remain unchanged.

#631 rejects the alternative of carrying the existing execution policy into the
replacement API. Do not introduce a second worker option, per-model parallelism
field, fair ready-lane queue, dynamic throttle, or persisted concurrency identity
before a real consumer changes this decision.

The audit also found a separate current-surface mismatch to preserve for later
evidence. Request-start pacing is applied before every vision provider method,
but short Google audio does not call the gate, while uploaded long audio gates
the workflow before catalog/client work rather than every SDK operation. The
historical statement that the interval covers every provider method is not
uniformly true. #621 does not fix or test this during the discussion pause; a
focused audio call-order proof must establish the intended contract before the
merged-audio slice reuses that policy.

No concurrency API, validation, scheduler, fingerprint, audio gate, test,
provider call, runtime, state, dependency, or deletion changes in #621.

## #622 Resume Does Not Restore Lane Preference

The maintainer's "each new batch" last-success rule is interpreted within one
fresh or resume invocation. Each lane starts at the first binding in the provider
plan supplied for that invocation. Only a valid success produced during that
same invocation changes the starting binding for the lane's next unresolved
batch. A completely failed batch leaves the current invocation's last-success
pointer unchanged.

Three routes were compared. Resetting to the current first binding honors the
caller's current order and needs no new state. Reconstructing a preference from
the most recent settled slot would silently override a reordered provider plan
and cannot distinguish the same vendor/model used with different endpoints or
settings. Persisting a lane cursor or provider tree would additionally require
lane-count identity, binding fingerprints, invalidation, and migration rules
for a routing optimization. The latter two routes are rejected.

Resume continues to preserve the facts that matter. Settled media slots remain
settled and retain their actual successful vendor/model and cumulative usage
evidence. Unresolved slots retain their original absolute batch indexes and are
assigned by `batch_index % current_lane_count`; the missing subset is never
renumbered. A changed lane count or provider plan may therefore change only the
routing of unresolved work. It never reopens, repacks, or moves settled content.

Historical calls and nullable token totals remain the loaded cumulative
baseline, but token rows, prior terminal errors, and settled provider evidence
do not act as a durable preference, blacklist, cooldown, or retry cursor. The
resumed invocation runs its current finite policies and records its own current
delta. If the caller wants a previously successful provider first, the caller
can place that binding first in the new plan.

This smallest rule is confirmed by #631: "new batch" does not restore a cursor
from a prior invocation. No candidate tree, lane count, cursor, binding object,
historical error list, or provider-routing fingerprint is persisted. No runtime,
API, state schema, test, provider call, dependency, or deletion changes in #622.

## #623 Provider Topology Uses Exact Lists

Provider topology and media batches deliberately use different concrete
containers. Public provider input accepts exactly one leaf, one nonempty exact
built-in `list` of leaves, or one nonempty exact built-in `list` whose members
are nonempty exact built-in `list` lanes. Planning leaves are exact
`ProviderModel` values; recognition and resume leaves are exact
`ProviderBinding` values. A one-element flat list and a one-lane nested list are
valid and retain their different fallback-versus-pool meanings.

Complete preflight rejects tuples used as provider collections, list
subclasses, generators, arbitrary `Iterable`/`Sequence` values, strings,
mappings, empty outer lists, empty lanes, mixed depths such as
`[binding, [binding]]`, depths beyond two collections, and the wrong leaf type.
Rejection occurs before reading or materializing media, resolving omitted
defaults, creating output, or dispatching a provider. The existing media-batch
contract remains an exact top-level tuple and is not weakened by this provider
syntax.

After identifying one of the three accepted shapes, the implementation may
snapshot it once into a private tuple of tuple lanes: a scalar becomes
`((leaf,),)`, a flat list becomes `(tuple(leaves),)`, and a nested list becomes
`tuple(tuple(lane) for lane in lanes)`. All later validation and use sees only
that snapshot. Planning may temporarily flatten it solely to calculate the
common minimum default; recognition and resume preserve every lane boundary
and ordering. This freezes membership and order only: settings are not deeply
copied, serialized, fingerprinted, or guarded against concurrent caller
mutation during capture.

This exact-list route matches the requested list/list-of-lists API and keeps
provider routing visually distinct from tuple media data. Tuple-only provider
plans would contradict that surface; permissive iterable handling would add
lazy-consumption and mutation compatibility work with no product need. Do not
add a recursive normalizer, public `ProviderPlan`, compatibility wrapper,
second batch abstraction, deep-copy mechanism, or auto-correction of mixed or
empty shapes. Duplicate bindings remain intentionally undecided for their
consumer slice. No runtime, API, test, schema, provider, dependency, media, or
deletion changes in #623.

## #624 Reject Only Definite Same-Lane Duplicates

A fallback lane grants every candidate one finite retry block. Repeating the
same candidate in that lane would silently multiply its configured calls and
cost; silently deduplicating it would instead conceal an invalid route. Complete
preflight therefore rejects definite duplicates within each lane. This applies
to the single lane produced by a flat list and independently to every inner
lane of a nested list. It happens after the one container snapshot from #623
and before media, defaults, output, or provider work.

Duplicate identity stays deliberately narrow. For planning, two
`ProviderModel` leaves in one lane with the same exact `(vendor, model)` identity
are duplicates; conflicting descriptive facts for that identity are invalid,
not alternate candidates. For recognition/resume, two `ProviderBinding` leaves
are definitely duplicate only when they use the same model identity and refer
to the same exact settings object. The same model with different settings
objects remains an ordered explicit route for another account, region, endpoint,
or runtime configuration.

Do not compare, hash, stringify, serialize, or fingerprint secret-bearing or
mutable settings to infer semantic equivalence. Current DashScope settings can
contain a mutable credential pool, so structural equality is not a stable
general binding identity. The implementation needs only a lane-local pairwise
preflight check; it does not need a global set, binding registry, account ID,
secret-derived key, or retry-budget merger.

The same model or binding may appear in different nested lanes. Cross-lane
reuse is explicit pool topology and may intentionally share a backup or run the
same route concurrently. Global deduplication could empty a lane, change
`lane_count`, and change `batch_index % lane_count`; it is rejected. Every
actual call remains counted, and token totals retain their already-selected
`(vendor, model)` aggregation rather than adding account/binding billing rows.

The current `VisionModelSettings` precedent is mixed: it rejects duplicates
inside `candidate_models`, while the separate primary `name` plus candidate
sources are silently deduplicated at execution. The replacement API has only
one provider shape, so it does not inherit that compatibility exception.
Semantic equality of separately constructed settings, safe settled binding
labels, globally identical lane policy, and provider-specific quota coordination
remain deferred until a real consumer proves a need. No runtime, API, test,
schema, provider, dependency, media, or deletion changes in #624.

## #625 Successful Fallback Records Identify Their Slot

The broad success contract was already fixed by #572/#592: completed content
returns one ordinary `RecognitionResult(status="complete")`, one bounded human
warning, and ordered `metadata["provider_failures"]`; only unresolved logical
content raises. #625 does not reopen that decision or add another result channel.

One merged-result detail was missing. Because one result may contain many image
groups or audio slices, every successful-fallback failure record also carries
`slot_index`, the stable zero-based absolute slot index from the immutable media
plan. A scalar or other one-slot call uses zero. Records are ordered first by
slot index and then by that slot's actual candidate traversal order. The other
fields stay exactly vendor, model, canonical code, and the final secret-safe
bounded description after that candidate exhausts its finite retries.

`slot_index` is sufficient association. Image members, audio logical/actual
ranges, source paths, filenames, lane/epoch, retry rows, timestamps, settings,
accounts, raw errors, and winning-provider rows are not copied into every
failure record. The caller or writer resolves the slot through the already-
fixed media plan/sidecar. The single human warning is present only when the
failure tuple is nonempty; do not add one warning per record or change complete
content to `partial`.

Python warnings/logging and a callback/event channel are not result contracts:
they can be filtered, reordered, or lost and would add concurrency, exception,
and persistence behavior. No public `ProviderFailure` type, diagnostics object,
attached-result exception, or second accumulator is added. The terminal failed-
slot accumulator remains separate and contains only genuinely unresolved slots.
No runtime, API, test, schema implementation, provider, dependency, media, or
deletion changes in #625.

## #626 Unresolved Slots Publish Recovery Evidence Then Raise

`RecognitionResult(status="partial")` remains a successfully returned usable
result whose requested content is settled but which carries degradation or
cleanup warnings. It does not mean that provider-exhausted image groups or audio
slices are missing. After all ordinary scheduled slots have been allowed to
settle, any unresolved slot therefore prevents a result return.

The replacement merged recognizer always resolves one output path before
dispatch. An explicit path wins and omission selects the already-fixed default;
omission is not an in-memory mode. For ordinary provider exhaustion, execution
continues through all later slots, persists every settled slot and aggregate
usage, composes the complete ordered Markdown with exact failed-slot markers,
ensures the sidecar is current, atomically writes or replaces the Markdown file,
retains the sidecar, and then raises one operation-level
`RecognitionIncomplete` with stable code `RECOGNITION_INCOMPLETE`.

The new error is an `OCRLLMError`, not a `ProviderError` and not
`AllCandidatesExhausted`. The latter describes one model-serving candidate chain
and currently has account-wide stop meaning; it cannot honestly summarize
several slots with different terminal causes. `RecognitionIncomplete` is
retryable only in the public sense that a later explicit resume may use the
retained state and a newly supplied provider plan. It never re-enters the
current provider retry table or restarts the just-finished invocation.

Its only new operation-specific detail is ordered `failed_slots`. Each record is
exactly the absolute zero-based `slot_index`, final attempted vendor and model,
that slot's canonical terminal code, and its final secret-safe bounded
description. Records are sorted by slot index. Successfully settled slots and
successful-fallback history do not enter this terminal accumulator. Existing
exact call/token/cleanup evidence remains governed by the already-fixed
aggregate contracts; do not duplicate media paths/ranges/members, Markdown,
retry history, lane/epoch, timestamps, settings/accounts, raw failures, output
path, sidecar path, or an attached result in `failed_slots`.

Atomicity is deliberately single-file only. The sidecar is saved before the
partial Markdown; no cross-file transaction, commit marker, rollback log, or
lock framework is created. If state persistence fails, do not publish a new
partial file and preserve the existing typed state/output failure. If Markdown
publication fails, retain the sidecar and raise the existing
`OUTPUT_WRITE_FAILED`, attaching the same safe failed-slot summary rather than
nesting an incomplete error. `RecognitionIncomplete` is raised only after both
recovery artifacts are durable, so `partial_published`, `resume_available`, and
path flags are redundant.

Resume alone may replace its prior partial Markdown. Another incomplete resume
updates state then replaces the partial file and raises again; full completion
replaces it with complete Markdown, removes temporary state, and returns the
ordinary result. Exact failed markers also give the experimental repair side
chain a narrow recovery source if the state is lost, without making repair the
normal path or adding a generalized parser. Cancellation, preflight/config/
source failure, and publication failure retain their own typed error families.
No runtime, API, test, stable-code implementation, schema, provider, dependency,
media, or deletion changes in #626.

## #628 Complete Target Field Set, Staged Private Proof

The maintainer's request to design the whole provider-model class and the
standing rule against consumer-free machinery are not competing requirements.
The durable target is already exact: vendor, model, controlled `adapter_id`,
three task-capability booleans, nullable capability-dependent image/audio
defaults, and immutable finite canonical retry rules. It contains no settings,
secret, callable, client, generic options, source/output, usage, errors, lane
state, or executable behavior.

Each field has an independent invariant, but not the same first consumer.
Identity, adapter route, and image capabilities serve the first internal image
proof. Image default first serves visible batching; audio capability/default
first serve the audio slice; retry rules first serve flat fallback. Merely
storing those facts would not extract audio, sleep, retry, switch providers, or
schedule lanes, but landing unused fields immediately would require freezing
types and testing values before those consumers exist. Two of those types are
still explicit maintainer questions: retry-rule shape and integer-versus-float
audio minutes.

The narrow combined rule is therefore:

1. Section 2.5 remains the complete class field design; do not invent another model
   type, options mapping, behavior mixin, or per-model subclass.
2. The first proof may use an internal, keyword-only immutable `ProviderModel`
   containing only its consumed fields. It has no root export, public preset,
   serializer, schema version, resume identity, or compatibility promise.
3. Before the first public constructor or public preset ships, resolve the two
   open field-type questions and land the complete designed data shape once.
   After that gate, adding fields merely when a later consumer arrives is not
   allowed.
4. A complete public data value still authorizes no retry executor, audio
   splitter, fallback chain, binding list, nested pool, token ledger, registry,
   or provider call. Each behavior remains its own live-proven vertical slice.

This avoids both schema churn after public release and placeholder machinery
before evidence. No runtime class, field, validator, serializer, preset, public
API, test, provider call, dependency, state, media, or deletion changes in #628.

## #629 Catalog Rows Are Not Executable Presets

The latest discussion uses both "prebuild and save Google and DashScope model
objects" and "after several usable entries are prebuilt." Those phrases cannot
be silently treated as the same contract. This iteration checks whether the
active catalogs can honestly supply every field required by a complete
executable `ProviderModel` before asking the maintainer to choose.

They cannot. The current native Google catalog parser keeps normalized model
IDs whose declared actions include `generateContent`; tests deliberately show
that this membership does not classify image, plain/detail OCR, or audio
fitness. The Google long-audio path separately consumes optional
`input_token_limit` only because that path has a real duration-preflight
consumer. The current DashScope compatible `/models` path keeps only nonempty
`data[].id` values and performs exact membership checks. Neither active path
derives the three OCRLLM capability booleans, recommended image grouping,
recommended audio minutes, or per-model canonical retry facts.

The legacy catalog shows the maintenance cost rather than a reusable solution:
it guesses modalities from model-name fragments, retains nullable limits,
hardcodes fallback IDs, and manually stores selected image/audio allowances.
Porting that table would reproduce the stale catalog and false-capability risks
that the new library is meant to remove.

Two bounded meanings therefore remain visible:

1. **Current recommended meaning:** discover all currently served identities
   dynamically; publish only a small set of complete, task-specific presets
   that have passed real image/audio calls; let callers explicitly construct
   the same `ProviderModel` for other IDs and supply facts the catalog does not
   prove.
2. **Explicit reversal:** check in a complete executable object for every
   catalog row and accept either guessed defaults or continuing per-model
   research, live testing, and source updates. This is not authorized by the
   discussion-only proposal without direct confirmation that it intentionally
   reverses the no-indefinite-model-maintenance rule.

Discovery may keep returning exact IDs until a real consumer needs richer
provider-declared metadata. Do not create a public descriptor class, generated
catalog module, name classifier, persistent registry/cache, or per-model test
sweep merely to make route 1 look symmetrical with presets. #629 changes no
runtime, API, test, preset, provider call, credential, dependency, state,
media, frozen boundary, or deletion.

## #630 Canonical Finite Retry Rules Preserve The Proven Legacy Behavior

The latest raw-code examples describe a useful outcome but do not require raw
HTTP keys or `error` / `current` / `next` fields. The active Google mapper
already proves that one HTTP 400 can mean provider-unavailable
`FAILED_PRECONDITION`, request-invalid `INVALID_ARGUMENT`, invalid credential,
or unsupported model modality. The active DashScope mapper combines status,
provider code, safe message markers, SDK family, and scope to distinguish
model quota, account/concurrency/rate state, permission, request, source, and
temporary provider failure. Raw status remains safe evidence after mapping; it
is not enough to select policy.

The legacy Google and DashScope/OpenAI-compatible paths confirm the same
behavioral minimum:

- temporary rate, network, concurrency, empty/invalid response, timeout, and
  provider-unavailable families may retry the same candidate finitely;
- model quota, absent model, unsupported modality, authentication, billing,
  safety/content, request, and source families need distinct canonical
  classification even when some eventually advance to another candidate;
- after a candidate's finite block ends, the replacement lane either advances
  while its slot is unresolved or records the final safe failure when the lane
  is empty.

Therefore one immutable rule keyed by canonical OCRLLM code needs only finite
non-negative `extra_retries` and finite non-negative `wait_seconds`. A missing
rule means no call beyond the initial attempt. Waiting occurs before each extra
same-candidate attempt, never after exhaustion. `current` means that this finite
block still has an extra attempt; `next` means it ended while a candidate
remains; `error` is decided by the already-fixed complete/incomplete operation
outcome. Saving those derived labels would duplicate dispatcher state.

Existing `ProviderErrorDisposition.action` and safe scope remain separate
evidence for cooldown, credential quarantine, request/source correction, and
stop decisions; they do not become retry-rule fields. Configuration, source,
capability, and preflight failures remain outside the table and make zero
provider calls.

Do not copy legacy retry numbers as preset defaults. Google used six total
attempts for image/text and four for long audio; generic compatible calls used
six total attempts, while FileTrans upload, submit, metadata, polling, and
download used different operation-specific counts. Legacy also mixed
stream-to-nonstream fallback, SDK-to-compatible fallback, exponential waits,
provider delay hints, mutable unavailable sets, and a second outer audio
candidate loop. Those are transport/job details and historical maintenance
cost, not `ProviderModel` fields. A later real adapter failure may justify one
code-specific number or bounded adapter-owned retry-after hint; no generic hint
parser, exponential mode, post-exhaustion action, operation/media condition,
blacklist, or unbounded sentinel is authorized now. Raw 402 and 409 examples
have no independent legacy evidence and receive no guessed rule.

#630 closes only the action-label/raw-key question. It implements no retry
type, executor, provider model, preset, adapter fallback, API, provider call,
state, dependency, media behavior, frozen-boundary change, or deletion.

## #631 Nested Provider Shape Is The Only Replacement Concurrency Authority

#621 and #622 are now confirmed together rather than left as two implementation
choices. For the replacement merged recognition API, a scalar or flat provider
shape is one lane; a nested exact built-in list has exactly
`lane_count = len(outer_list)` lanes. The API does not accept or consume the
shipped `RecognitionExecutionPolicy.max_parallel_requests`. Requiring the same
concurrency twice would create conflicting authority, while applying the old
default of one would silently serialize an explicitly requested pool.

The existing safety ceiling remains useful without importing the old policy:
one through 32 lanes are valid, and a larger nested shape is rejected during
complete preflight before media reads/materialization, output/state writes, or
provider calls. Each lane has at most one active slot. Its immutable absolute
slot sequence is `j, j + lane_count, ...`; it advances after its own slot is
settled and never waits for a global epoch. No slot is rescued by another lane,
stolen, rebalanced, or ordered publicly by completion time. Ordinary failed
slots do not stop later fixed slots.

Last-success is invocation-local routing only. Every fresh or resume call starts
each newly supplied lane at its first binding. A success produced during that
call rotates the next unresolved slot in that lane to the successful binding; a
fully failed slot leaves the pointer unchanged. For one slot, traversal is
circular from that starting point and reaches every binding at most once after
each binding's own finite retry block.

Resume keeps settled content and its actual vendor/model/call/token evidence,
but does not restore a provider cursor. Unresolved absolute indexes are assigned
with the current `index % lane_count`; changing the provider shape may reroute
only unresolved work. Do not persist a provider tree, lane count, binding
fingerprint, cursor, blacklist, cooldown, or historical-error routing state.
Callers who want an old successful route first can place it first in the new
lane.

This decision does not alter current Config-based `recognize_batch()`, its
execution fingerprint, or its independent-output concurrency. It also does not
claim that request-start pacing is uniform across image and audio transports;
the focused merged-audio proof recorded in #621 remains required. No pool,
scheduler, queue, runtime API, validation, fingerprint, state schema, test,
provider call, dependency, media behavior, frozen boundary, or deletion is
implemented by #631.

## #632 Float Audio Minutes Need One Concrete Product Answer

The latest `float` field spelling and the earlier exact-integer caller contract
can coexist technically, but they do not yet define one behavior. The active
planner rejects `1.0`, `1.5`, booleans, and non-positive intervals; it converts
an accepted integer minute count to floating seconds only after validation.
Long-audio state persists exact integer `interval_minutes`, request fingerprints
include the resulting logical/actual second boundaries, and resume restores or
compares the saved integer before materialization and provider dispatch.

Three routes were checked:

1. **One integer-minute domain (recommended).** Both the curated provider
   recommendation and the explicit caller override are exact positive integers;
   caller `-1` alone means whole audio. A preset stores OCRLLM's conservative
   working recommendation, not a vendor hard limit. If evidence says a model is
   stable below 29.5 minutes, the preset author may deliberately choose 29; the
   runtime does not implement an automatic rounding rule.
2. **Float provider recommendation, integer caller override.** This is coherent
   only if values such as `7.5` are meaningful and create exact 450-second
   logical slices. Then the planning boundary must normalize once to an exact
   positive second count and persist seconds plus exact ranges; binary float is
   not durable identity, and fallback/resume never recompute from the provider.
   This intentionally permits an omitted-provider-default plan that the caller
   cannot request through `interval_minutes=7.5`.
3. **General duration API.** Allowing fractional caller minutes, `timedelta`,
   Decimal, unit enums, or arbitrary seconds would change the public split
   contract, state schema, Electron-facing values, and resume comparison. No
   current consumer or provider failure requires that framework.

Do not silently floor, ceil, round, clamp, or accept only integral floats such as
`30.0`; the first three hide policy, while the last makes `float` semantically
empty. The one exact maintainer question is therefore: should
`ProviderModel(default_audio_minutes=7.5)` be valid and produce exact
450-second slices while explicit `interval_minutes=7.5` is rejected? Until the
answer is yes, `default_audio_minutes` remains `int | None` and the current
state/resume contract is unchanged.

#632 implements no ProviderModel, splitter, conversion, state migration, API,
provider call, media operation, dependency, frozen-boundary change, or deletion.

## #633 Video Resume Routes Exactly One Explicit Media Branch

The package-root `resume_video` remains required, but it is not a two-branch
operation. One call routes exactly one already-extracted media source to one
ordinary resume owner. Its future public shape is fixed conceptually as two
overloads with the same four arguments:

```python
resume_video(
    source,
    *,
    media_type: Literal["image", "audio"],
    providers,
    output_path: str | Path | None = None,
) -> RecognitionResult
```

For `media_type="image"`, `source` is the exact ordered image-group tuple
returned by `batchify_images`. For `media_type="audio"`, it is the exact
`tuple[AudioSlice, ...]` returned by `split_audio`; a bare audio path would hide
whole/interval re-planning and is not accepted.
`providers` keeps the already-fixed scalar, exact flat-list, or exact nested-
list `ProviderBinding` shape. Explanatory image/provider aliases used by type
overloads remain private; this route does not justify public request or plan
classes.

The exact media discriminator is validated before delegation and is never
guessed from a filename suffix, path, tuple nesting, or member type. The chosen
ordinary resume then owns complete source/provider/capability/output/state
preflight, deterministic omitted-output resolution, sidecar identity,
publication, and cleanup. The router does not duplicate those checks or search
for state.

Return the delegated `RecognitionResult` unchanged, including its canonical
`source_type="image"` or `"audio"`. Propagate `RecognitionIncomplete`, resume,
provider, output, cancellation, and configuration errors unchanged. Do not
catch a failure to run the other branch, translate codes, add video details, or
attach a result to an exception. A caller resuming both outputs makes two
explicit calls, so one success and one failure remain two ordinary outcomes.

Reject the dual-branch alternatives: paired image/audio sources, two provider
trees, two output paths, automatic serial/parallel branch execution, cross-
branch cancellation, and a `VideoResumeResult`/tuple/dict wrapper all recreate
the retired video lifecycle. The route also accepts no original video, `resume`
flag, batch size, audio interval, extraction option, journal, composer, or
cleanup owner. Saved ordinary plans already carry grouping/splitting identity.
If two independent defaults collide, the existing rule requires explicit
separate output paths; this single-branch router does not coordinate them.

#633 closes the stateless video-resume signature and removes that item from the
current decision board. It implements no export, overload, router, resume
function, result type, validation, state, API, provider call, media operation,
dependency, frozen-boundary change, or deletion.

## #640 Successful-Fallback Reporting Was Not Reopened

Section 0 briefly listed successful-fallback reporting as a maintainer choice,
but the detailed decision trail had already fixed it in #572/#592 and narrowed
its exact fields in #625. The later instruction to report accumulated provider
errors does not require turning completed recognition into exception control
flow. #640 removes that duplicate question and promotes the already-fixed rule
to the current pruning checkpoint.

The current result boundary confirms the choice. `RecognitionResult` is the
successful-output object; its `status="partial"` represents usable recognized
content with degradation such as cleanup warnings, not missing requested
slots. `BatchItemOutcome` permits exactly one result or one error, and
`recognize_batch()` treats an exception as failure and stops later work from
starting. Raising after a later provider has already produced valid content
would therefore hide the successful result, risk replaying paid work, and
require an attached-result exception or a second outcome wrapper to recover
both facts.

The exact replacement behavior remains: successful fallback returns
`RecognitionResult(status="complete")` with one aggregate warning and the
bounded ordered `provider_failures` metadata fixed by #625. A slot still
unresolved after its lane uses the distinct #626 publication-and-
`RecognitionIncomplete` path. Do not persist successful-fallback diagnostics
as provider-routing memory, add a public failure-record class, or create a
per-attempt ledger. #640 changes only decision records; no runtime, API, error
type/code, schema, provider call, credential, media, output, or deletion changed.

## #641 Catalog Breadth Does Not Block The First Two Image Entries

The latest maintainer statements establish three different facts that must not
be collapsed. Every selected exact `(vendor, model)` is represented by the same
`ProviderModel` value rather than one vendor-wide entity or one class per model.
OCRLLM must not continually hardcode and repair models one by one. Several
usable Google/DashScope entries must be proven before the merged interfaces are
rewritten. None of those facts alone resolves whether "prebuild and save every
model object" was intended to require an eventual checked-in executable mirror
of every volatile catalog row, so that breadth remains one exact confirmation.

The active code proves the narrow common sequence. Google discovery returns
only ordered current `generateContent` IDs and does not cache or hardcode them.
DashScope accepts an explicit exact model ID and validates non-baseline IDs
against the configured live `/models` membership; its active response retains
IDs only. Neither route can populate plain/detail/audio capability facts,
recommended media defaults, or canonical retry rules for every row. Filling
those facts with guessed `False`/`None`, a three-state capability system, a
generated descriptor layer, or a name classifier is rejected.

After the maintainer resumes runtime work, the common first gate is therefore
two bounded image entries: one exact native-Google entry and one exact
DashScope OpenAI-compatible entry, each using the same internal pure-data model
shape; exact runtime settings and invocation follow the separately open adapter
decision. A passing entry may become a shipped preset. Only after both entries
can actually recognize should
the merged image interfaces be rewritten around the first-class provider-model
entity. Audio has its own
later live-preset gate. No full mirror, catalog-return-type change, descriptor
framework, fallback/pool implementation, model sweep, preset identity, runtime
class, interface rewrite, provider call, or credential access is authorized by
#641.

## Test-Suite Pruning Record (2026-08-30)

Maintainer directive: code-level tests had exploded past human reviewability
(50,509 lines across 149 files against 23,383 library lines) while
real-scenario verification stayed the minority. The testing rule is now
recorded in root `AGENTS.md` ("Testing Boundary"), which outranks every other
document on testing policy. This section is the deletion blueprint for the
refactor slices that touch these areas.

### Executed 2026-08-30

- The Phase 1 quality harness was expelled from the suite: `tests/quality/`
  moved to `quality_lab/` with its fixtures (`quality_lab/fixtures/phase1/`),
  generators, assets, and its 28 self-test files (`quality_lab/tests/`). It
  runs on demand via `python -m pytest quality_lab` (317 passed), not on
  every change. Manifest artifact paths, two provenance records, and the
  frozen manifest SHA-256 were re-baselined to the new layout; image pixels
  and corpus content are unchanged.
- Suite effect: root `tests/` collects 1,620 tests (was 1,937), all passing;
  the expelled 317 run only on demand.
- `docs/ACTIVE_STATE_AND_RULES.md` is demoted to work log and defect
  archive; root `AGENTS.md` is the top authority. Its anti-pruning guards
  (normalizer-chain deletion ban, `contracts/`/`worker/` deletion ban) were
  removed. Moving `contracts/` and `worker/` out of the shipped library
  package is approved cleanup.

### Deletion candidates by bucket

Root `tests/` after the expulsion holds ~36,700 lines in 112 files. The
audit buckets and their verdicts:

- **Public API contract (20 files, 5,339 lines).** Keep. This is the layer
  the testing rule protects.
- **Micro-unit mirrors (46 files, 6,406 lines).** One test file per internal
  function, mostly shadowed by integration coverage. ~4,100 lines are pure
  redundancy. Keep only the error-precedence cases in
  `test_write_markdown_atomically.py`.
- **Fake live smokes (8 files, 3,140 lines).** Named `*_live_smoke` but all
  offline: they monkeypatch the smoke-tool facades and never touch a real
  API. The real provider verification lives in `tools/run_*_smoke.py` and
  stays there per the testing rule. ~2,500 lines deletable.
- **Integration duplication (24 files, 18,721 lines).** The video cluster
  re-runs the same failure/cancellation matrix three times
  (`test_recognize_video.py`, `test_recognize_video_to_markdown.py`,
  `test_resumable_video_pre_dispatch.py` — the last is a strict subset);
  `test_long_audio_interval_persistence.py` and
  `test_long_audio_whole_persistence.py` overlap the same state machine.
  ~6,500 lines collapsible. Note: most of this cluster dies anyway with the
  section-0 deletion of the video orchestration family; do not prune it
  twice — delete it with its subsystem.
- **Worker harness (9 files, 1,807 lines).** Tests the `contracts/`/`worker/`
  protocol that has no consumer. Moves or dies with that subsystem's
  extraction; it does not get independent pruning effort.
- **Frozen evidence replay (4 files in `quality_lab/tests/`).**
  `test_phase1_v2/v3/v4/v10_live_evidence_diagnosis.py` re-score frozen
  superseded iterations. Deletable once the v17 record is accepted as the
  final campaign verdict; they cost nothing while they stay out of the
  default suite.
- **Tools ratchets (2 files, ~700 lines).** `test_a1_mp3_fixtures.py` and
  `test_social_long_course_tools.py` test auxiliary `tools/` scripts,
  including the deferred social-media surface. Deletable with their tools.

Net pruning potential in root `tests/`: ~13,500 lines without touching
integration behavior coverage, plus ~6,500 more that resolves automatically
when the section-0 video deletion lands.

### src cross-references for the refactor slices

- `contracts/` (1,225 lines) + `worker/` (840 lines): unreachable from the
  public API, exercised only by their own tests, shipped in the wheel.
  Extraction approved; no consumer exists.
- Frozen video journal family (27 modules, 2,974 lines): already the
  section-0 deletion target; the audit independently confirms it is
  reachable only through `recognize_video`/`recognize_video_to_markdown`.
- Three media-persistence state machines (image resume 785, video job 1,101,
  long-audio 839 lines) are structurally parallel serialize/parse/save/load/
  validate stacks. The merged media flows in section 0 should land on one
  sidecar store core with per-media schema, not a fourth stack.
- Provider one-shot transport envelope (config snapshot, cancellation,
  call accounting, client close, redaction) is duplicated between the
  DashScope and Google GenAI adapters (~250-350 lines collapsible) once the
  merged image interfaces are rewritten around the first-class provider-model
  entity.
