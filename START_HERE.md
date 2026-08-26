# START HERE: OCRLLM Repo Map

This repo currently contains two codebases. Treat the directory boundary as a
hard signal before editing or importing anything.

**Read `docs/ACTIVE_STATE_AND_RULES.md` first.** It outranks every other file,
including this one, and it carries current state, the open defect register, and
the coding and documentation rules.

Current state lives in `docs/ACTIVE_STATE_AND_RULES.md`. Dated phase, decision,
checkpoint, review, and incident files keep history only; they never override
that file. Verify capability claims against the named code and tests.

## Active New Library

Path: `src/ocrllm/`

Use for:

- New importable package: `ocrllm`
- Stable public API work
- New downstream project dependencies
- Root test suite under `tests/`

Read in this order:

```text
docs/ACTIVE_STATE_AND_RULES.md        Current truth, defects, rules. Outranks all.
docs/MAINTAINER_PRODUCT_DECISIONS.md  Maintainer choices preserved across handoffs;
                                      scope changes still require authority updates.
docs/plan_phase1_maturation_and_phase2_audio.md
                                      Retained Stage M/A detail; authority #065
                                      controls current ordering and providers.
docs/plan_phase1_defects_and_provider_split.md
                                      Stage 1 history; standalone Stage 2 was
                                      superseded by executable slices.
docs/ocrllm_library_go_no_go.md       Phase gates, file responsibilities,
                                      migrate/rewrite/reject boundary.
src/ocrllm/README_ACTIVE_LIBRARY.md   Package boundary and capability surface.
src/ocrllm/AGENTS.md                  Package editing rules.
MIGRATION_STATUS.md                   Navigation aid.
docs/ocrllm_module_target_design.md   Target-state module map.
docs/provider_cost_and_reliability_policy.md
                                      Account-specific provider policy.
```

Other documents named in this read order remain current for their bounded
purpose. Files with `phase*`, `*_decision_*`, `*_checkpoint_*`, `*_review_*`,
or `*_incident_*` names are dated history; consult them only to understand how
a past decision was reached, never to learn current state.

Minimal import example:

```python
from ocrllm import Config, GoogleGenAISettings, VisionModelSettings, recognize
```

Current phase: **Phase 1 maturation, Stage M offline implementation complete**. Phase 0
contract honesty, the Phase 1 image gate, the Phase 2 development worker, and
Phase 2A image-library completion are GO. Stage M has shipped lazy DashScope
catalog checks, atomic file-backed image state, an opt-in candidate queue, and
slot-indexed intra-request checkpoints with an explicit v1-to-v2 resume
identity migration, complete attempt-spend disclosure, disposition-gated
recovery, model-aware pool behavior, and correct scout-failure attribution.
Its DashScope live exit is closed by #339: one credential-isolated run discovered
241 current models and completed public formula-board recognition on explicit
`qwen3.5-ocr` with runner exit 0, no retry, switch, fallback, or content/secret
publication. This is connectivity/lifecycle proof, not formula-quality or broad
quota evidence. #340 makes later DashScope calls preserve compatible-endpoint
`prompt_tokens` / `completion_tokens` through the existing per-model metadata;
missing or invalid counts remain unknown without discarding recognized text.
The former standalone Stage 2
scaffold was removed from the queue. The bounded Stage A1 direct slice is
implemented and live-proven: the lazy
`miniaudio>=1.71,<2` local MP3 probe, deterministic validation corpus, bounded
compact-name snapshot, exact audio-model configuration, native Google inline
request, public facade, and in-memory result are implemented for one MP3 of at
most 300 seconds. Persistence, resume, groups, upload, and automatic routing by
the general `recognize()` facade do not exist. #150 activated Stage A2 planning
from a real 301.056-second public
video probe. #151 now implements and live-proves standalone
`recognize_long_mp3()` for one Google Files MP3 longer than 300 seconds and no
longer than the current 9.5-hour single-prompt limit. It owns the source,
uploads once, waits within the configured timeout, generates once, deletes the
remote file, and closes the client. #297 integrates these existing short and
long adapters into `recognize_video()`: one owned extracted MP3 is decoded once,
then exactly one adapter is selected at 300 seconds. Standalone long audio
supports proven whole-file persistence and exact-integer-minute interval resume.
#341 reuses those settlement functions in video without nesting standalone
publication: whole remains the default, while `audio_interval_minutes` selects
serial intervals and stores paid prefixes under the video root until clean
success. #342 extends only the maintained redacted Google video runner so one
bounded live gate can require an exact interval and exact audio-call count while
retaining caller-owned failure state for inspection. Its sole live run failed
honestly at the first audio Files upload with no settled interval; it was not
replayed and is not success evidence. #343's separate fresh attempt settled one
interval, exposing a runner-only defect that mistook required failure state for
unclean success. The runner now preserves that safe failure evidence while
still requiring complete outcomes to remove state. #344 live-proves corrected
provider failures remain auditable `video_outcome` reports, although model quota
stopped the first audio interval before any state settled. #345 proves public
video resume cannot honestly be audio-only: paid frame groups, short audio, source
identity, and one terminal state-cleanup owner are missing. #347 selects the
high-level fixed-result Route A: current recognize/compose/publish calls remain
non-resumable, and a later single video job will own one temporary journal plus
atomic `result.md` publication. Public video resume is not yet exposed. The same
iteration makes duration validation route-aware: whole Google Files remains
limited to 9.5 hours, while explicitly selected integer-minute interval mode
accepts the private product ceiling of 10 hours.
Fallback and batch/worker
support remain later gates. #152 now selects Route B
while keeping explicit whole-file and interval-chunked operations. Interval
length is configurable only in integer minutes and belongs to temporary resume
state. #304 closes the last identity choice: interval chunks use a private fixed
30 seconds of context on each side of an interior logical interval, while exact
logical and actual windows live only in temporary resumable state. No public
overlap parameter or text-similarity deduplication is planned. #305 implements
the first internal piece: deterministic ordered logical/actual window planning
with strict integer-minute validation. It does not cut media, dispatch a
provider, persist state, expose a public facade, or implement repair.
#153 also corrects the frozen capability registry's long-MP3 reason: it now
names the direct live-proven Files facade but remains `deferred` because no
shared worker route was added.

#110 re-proved the distributable boundary after the recent audio changes. A
clean archive ran 1325 tests with one expected skip, built a 202,692-byte wheel,
and passed dependency-empty base import plus audio, image, DashScope, Google,
combined audio+Google, and installed public PDF profiles without provider calls.

The ordered current work is `#065 Unified Execution Queue` in
`docs/ACTIVE_STATE_AND_RULES.md`. Its bounded legacy-provider audit and native
`google-genai` direct-Python image slice are complete. The #067 live gate found
37 current models; `gemini-2.5-flash` completed one image and one eight-image
group in one call each, reported real input/output usage, and returned a typed
credential-scope authentication error for the invalid-key probe. The shared
capability/worker registry remains frozen at 20 and does not claim Google worker
support. #113 reduced the maintained routine image check to one recognition
instead of replaying the historical group and invalid-key probes; its bounded
refresh found 37 models and completed one call with usage 595/443, with no retry
or retained sensitive/output data. #115 makes Google image failures equally
honest about dispatch: catalog/model-selection and other pre-generate failures
report zero recognition calls, while a failure inside `generate_content`
reports one. The smallest native Google short-audio
direct API is live-proven for one memory-only MP3 and a bounded native inline
request below 20,000,000 bytes.
#068 first returned honest `PROVIDER_QUOTA_EXHAUSTED` / `model` on
`gemini-3.1-pro-preview`. #069 then selected `gemini-2.5-flash`: a
3.468888889-second, 26,488-byte synthetic MP3 produced one successful public
result in exactly one provider call with input/output usage 150/10; its separate
invalid-key probe returned credential-scoped authentication. No transcript was
published, so this proves the result boundary rather than transcription
quality. #107 additionally makes every error inside that adapter state whether
the one recognition call was actually attempted: zero before
`generate_content`, one after entering it. #108 also preserves that count when
the call succeeds but later owned-audio-snapshot cleanup fails. P0-c is
complete. #114 re-proved the maintained short-audio runner after those changes:
one committed 0.5-second MP3 completed on `gemini-2.5-flash` with one provider
call, usage 55/2, and no retry, second probe, credential leak, or temporary
residue. #070 then proved live cancellation after one settled
Google image draft and resume of only the missing review: two total provider
calls, the draft reused with zero replay calls, and a complete published result.
P1-a is complete. #071 completed P1-b: `recognize_batch()` now requires an
exact top-level tuple while preserving each item's existing atomic-path or
grouped-`Sequence` contract, and validates the entire batch plus output targets
before any snapshot, directory, executor, or provider work. Two live groups of
eight images completed in order with exactly two total Google calls and complete
published state. #105 separately re-proved the exact-tuple, tuple-subclass,
same-stem collision, and later-corrupt-source behavior through public imports
from a freshly installed wheel; every invalid case made zero provider calls and
left no output/temp residue. #109 also proves an exact serial MP3 tuple keeps an
ordered success, a one-call provider failure, and an undispatched cancellation
as three honest item outcomes. #292 closes a parallel completion-order race:
a typed worker failure now aborts the existing shared provider start gate before
its future reaches the collector, so an already-terminal failure cannot be
overtaken by a success and permit one extra paid replacement call. Already-
started work still settles, and ordering/concurrency remain unchanged. #078
completed P1-c PDF-through-image/resume.
#120 answered P1-d no: the library does not consume legacy localized repair
Markdown, so ordinary resume remains its PDF recovery path and no `repair_pdf`
compatibility parser is built. P1-e video is now active. #120 added
provider-free `inspect_video()` for one MP4 through a lazy OpenCV extra; #121
adds bounded coarse comparison, count-driven negative-feedback calibration,
and complete-directory retained JPEG publication through
`extract_video_frames()`. #122 recognizes ordered frame groups, #123 extracts a
validated MP3 so a separate audio config/provider can recognize it, and #124
keeps exact frame indices/timestamps on every settled frame-group outcome.
#125 distinguishes a truly silent MP4 from corrupt declared audio without
parsing FFmpeg logs. #126 adds public `recognize_video()` with separate image
and audio configs and a typed `VideoRecognitionOutcome` that retains honest
branch results/errors and media artifacts. #285 additionally preserves that
settled work as a partial outcome when only final request-owned source-snapshot
cleanup fails, exposing one typed cleanup error rather than discarding both
recognition branches. #129 adds explicit, provider-free
`compose_video_result()` for complete or partial returned outcomes; it keeps
ordered frames and audio in separate sections without publishing a file or
inventing time alignment. #130 then built the exact current clean archive,
installed its wheel outside the repository, and re-proved that complete local
video path while keeping plain package import lightweight. #131 fixes the
density safety cap so it retains the final video candidate instead of possibly
ending early. #132 fixes shared output-stem truncation to use the existing
Windows UTF-16-unit budget while preserving complete Unicode characters. #133
uses ceiling partition counts so a maximum-length stable segment is not rounded
into too few retained intervals. #134's post-change Google video run proved the
image and partial-composition paths but lost the failed audio branch's safe error
evidence. #135 adds the maintained, redacted combined-video smoke runner with
separate image/audio configs and exact-or-unknown branch call evidence. #205
removes its obsolete shared-model CLI assumption: current runs require separate
`--image-model` and `--audio-model` values from one live catalog and validate
each branch against its configured model. The next bounded live run must use it
with a controlled one-image-group fixture. #206 completes that proof with
distinct current-catalog models: one image call returned typed
`PROVIDER_UNAVAILABLE`, while one audio call succeeded and preserved its own
200/14 token usage in an honest two-asset partial outcome. There was no retry
or model switch. #207 takes that exact image-failed/audio-success shape through
public atomic Markdown publication on real local media and confirms the error,
audio text, assets, calls, and audio-only usage remain honest. #136's
first such attempt lost its external asynchronous session identifier after the
runner completed, so it proves no provider outcome; the next controller must
poll that exact session and preserve safe JSON before cleanup. #137 did so: one
image call succeeded, one audio call returned `PROVIDER_QUOTA_EXHAUSTED`, and
the public outcome/composition honestly preserved a two-asset partial result
without retry or model switching.

#348 establishes one cross-product image rule: recognition always receives the
complete board image, retained video frame, or PDF-rendered page. The active
library already followed it. The legacy automatic/manual board crop,
perspective transform, inferred video board ROI, ROI-only candidate JPEGs, and
ROI-based occlusion rejection were removed; size-only full-field downscaling
remains allowed.

#357 re-audits that removal after an explicit maintainer clarification. No
executable corner/ROI/contour crop or perspective warp remains in either
product. It deletes the last unused legacy Canny/contour config object and
renames misleading “crop and resize” progress/docs to complete-frame resize.
The active video writer still re-encodes the decoded full frame at identical
dimensions, and PDF rendering still scales the complete page uniformly.

#358 fixes one PDF failure-reporting defect. If the first image group completed
and saved its reusable sidecar but child Markdown publication failed, the
intentionally nonempty state directory was falsely labeled as a cleanup
failure. `rmdir()` now treats only `ENOTEMPTY`/`EEXIST` as expected retained
state; permission, path, and other cleanup errors remain disclosed. Provider
calls, sidecar content, resume, final publication, and repair behavior do not
change.

#359 proves the #358 retained state through its actual public consumer rather
than treating file existence as sufficient evidence. After the first child
publication failure, an explicit `resume=True` call reuses the one-group
sidecar with zero new provider calls, publishes the child Markdown and final
range-marked PDF Markdown, and reports zero current-run calls. Runtime was
already correct; this adds no state, retry, repair, or API behavior.

#361 fixes a whole-file long-audio settlement mismatch. A paid Google Files
request that returned typed no-speech previously left no state, so explicit
resume failed as missing instead of reusing the settled outcome. Whole mode now
uses the existing no-speech slot already proven by interval mode, saves it
before returning the typed error, and a later resume repeats that error with
zero provider calls. It never publishes the internal no-speech sentinel and
does not change the state schema, retry, provider, or video-resume boundary.
#362 closes the adjacent candidate-model accounting defect. When opt-in
recovery advances after an earlier model has already completed a paid workflow
pass, the final success or terminal typed error now retains that model's
validated token usage as well as later models' usage. First-seen model order and
unknown `None` counts remain honest; call totals, recovery policy, persistence,
and provider behavior are unchanged. No billing subsystem was added.

#363 preserves that first-seen rule through video composition. Interleaved
successful and failed frame groups now contribute their validated usage in
settled group order before the audio branch, instead of grouping all successes
ahead of all errors. No result content, status, calls, provider, or publication
behavior changed.

#364 closes the separately reproduced publication defect around a silent
video's reserved but nonexistent `audio.mp3`. Lexical aliases such as
`frames/../audio.mp3` are resolved and rejected before the nonexistent-target
fast path, while the existing filesystem-identity check still protects retained
hard-link aliases. Valid atomic publication is unchanged; no general path or
transaction framework was added.

#349 then release-proves exact post-removal commit `3c09cde` from a clean
archive: 1,768 tests passed with one skip, every maintained isolated install
profile succeeded, and local audio, image, PDF, video, and combined-media smokes
passed. It staged the already-declared compatible Pillow 12.3.0 wheel through the
active proxy without changing package bounds or persistent pip configuration;
no provider was called.

#350 fixes one video-owned state lifecycle mismatch: a long-audio result marked
partial because provider cleanup did not finish no longer deletes its settled
whole/interval sidecar. Only a complete clean result removes that state. The
current video API still cannot consume it; this is honest preservation for the
later selected high-level resume job, not a new resume surface.

#351 made one authorized free Google run from exact commit `ba0e0a7`. The live
catalog returned 37 models, but one `gemini-2.5-flash` image generation timed out
after one attempted call and the first Files interval timed out during upload
before generation. The failed outcome reported zero settled audio intervals and
a closed client, skipped composition, and left no task-owned residue. It was not
retried or switched to another model, so the complete live interval gate remains
open at that revision. #353 then made the maintained runner retain its own total
monotonic elapsed time. #354 closed the gate with one non-replayed run from exact
commit `2e3ead0`: the same model completed one five-frame image group and exactly
two three-minute Google Files audio intervals for a 301.0235-second artifact.
Composition completed with six assets and aggregate usage of 13,602 input / 872
output tokens; remote/client cleanup, absence of a remaining sidecar, task
cleanup, and the still-active proxy were verified. The runner took 790.609
seconds in total. This
supports the existing optional 600-second per-operation setting for this gate;
it does not provide per-stage timing or change the product default timeout.

#355 rejects an easier publication-only journal as the selected resumable-video
job. Saving only composed Markdown would not preserve any paid frame or audio
unit and would force immediate state-schema churn. The first public job must
instead own fixed `result.md` publication and immediately consume one journal
covering source/media-plan identity plus settled full-frame groups and
short/whole/interval audio work. The current three-step API stays unchanged.
Implementation waits on one terminal rule: the recommendation is to publish no
final file while any required unit is missing, retain settled paid work, raise
the typed failure, and let an explicit later resume retry only the missing work;
cleanup-only partial content may publish.

#356 fixes one current paid-call accounting defect without beginning that job.
When a whole long-audio provider call completed but the following temporary
state save failed, standalone audio incorrectly reported zero attempted calls
and video audio omitted the count. The whole settlement boundary now preserves
the known value `1` on that typed error. Interval behavior, provider calls,
state format, retry, resume, cleanup, and public APIs are unchanged.

#138 makes the public video outcome reject
frame/audio paths outside its exact lexical `output_root/frames/*` and optional
`output_root/audio.mp3` layout before composition. #139 makes composed
current-run provider calls exact-or-unknown: any settled provider branch that
lacks reliable call evidence makes the total `None`; only a proven
pre-dispatch video/audio parsing branch contributes zero.
#140 rejects a contradictory video outcome that reports
`VIDEO_NO_AUDIO_STREAM` while also retaining `audio.mp3`; invalid public state
now stops at construction instead of becoming a complete composed result.
#141 fixes status propagation: a partial frame or audio child remains partial
in both `VideoRecognitionOutcome` and `compose_video_result()`.
#142 rejects a non-image `RecognitionResult` inside a video frame group before
it can be composed under the Frames section.
#143 re-proves the current facade from a clean externally installed wheel and
guards the package example so fully failed outcomes remain structured evidence
instead of being passed to `compose_video_result()`.
#144 adds separate `publish_video_result()` final Markdown publication for an
already-settled complete or partial outcome and an explicit caller path. It
reuses atomic output without changing memory-only composition or provider
dispatch. #145 recorded the former cancellation asymmetry; #294 supersedes it
with the selected Route A contract. One cancelled branch returns in the existing
branch error while preserving the other branch, pre-cancelled audio skips MP3
extraction, and dual pre-cancellation stops before source/output work. #236
confirms that durable video recovery is valuable; exact frame-group recovery
can now follow, while full audio/video recovery still waits for #152's overlap
decision. No
legacy checkpoint or Markdown repair format is imported. The audio slice
has no hidden retry, fallback, upload, persistence, resume, or worker-registry
claim. #146 additionally proves the new publication entry from an offline clean
wheel installed outside the repository, including actual Markdown publication,
overwrite safety, asset-collision refusal, packaged typing marker, and lazy
heavy dependencies. #147 updated only the wheel Summary to name the then-shipped
image, PDF, short-audio, and video surfaces; #151 supersedes that exact text with
image, PDF, audio, and video after the standalone long-MP3 facade shipped. The
earlier dual-wheel comparison proves extras, dependencies, members, and runtime
payloads did not change. The queue explicitly
records #148's frame-scan correction: the actual source final frame now always
participates in bounded comparison, so a scene change after the last five-second
grid position cannot disappear before negative-feedback selection. #149 then
proved a source-lifecycle defect: replacing the MP4 between coarse scan
and retained-JPEG decode can mix selection metadata from the old bytes with
frames from the new bytes while returning success. #211 closes it with one
library-owned streamed snapshot under `output_dir`; inspection, comparison,
retained decode, and combined audio extraction consume that path before cleanup.
No public video-temp parameter or legacy format was added. The queue still
stops further proactive
filesystem/accounting edge scans.

#224 separately proves that standalone `extract_video_audio()` had the same
mutable-caller-path risk between inspection and FFmpeg extraction. It now owns
one streamed snapshot under the output parent. Combined recognition calls the
narrow stable-source implementation with its existing #211 snapshot, so the
shared video is not copied twice. A real same-path 440/880 Hz replacement test
keeps the published MP3 tied to the inspected 440 Hz bytes and leaves no hidden
source or staging file.

#225 then runs the maintained redacted Google combined-video gate exactly once
after that lifecycle change. Two independent configs both explicitly selected
`gemini-2.5-flash`; one retained-frame group and one speech-audio branch each
completed in one generation. The public outcome/composition were complete with
JPEG plus MP3 assets and aggregated 796/17 token usage. Exit was 0 in 9,721 ms,
with no retry, fallback, model switch, credential/content/path/raw-response
leak, or request-owned residue. This refreshes runtime evidence; it does not add
a second audio provider or generalize provider routing.

#227 separately keeps the public no-output `inspect_video()` honest when its
caller path is overwritten during inspection. It compares the validated file
identity around the OpenCV/container-duration reads and rejects an ordinary
change with typed `SOURCE_INVALID`, instead of returning mixed metadata. It
does not copy or hash the entire video and does not claim protection against a
deliberate same-metadata overwrite-and-restore race.

#228 proves that exact behavior from a clean wheel installed outside the
repository. The installed public function remained lightweight and rejected a
real two-MP4 overwrite with exact `SOURCE_INVALID`; the wheel included the
inspector and `py.typed`. This is distribution evidence, not a new integrity
mechanism or permission to reopen #127/#152.

#238 corrects one later real-media counterexample without reopening those
choices. An MP4 with a one-second video stream and twelve-second audio stream
keeps its twelve-second public container duration, but the frame sampler no
longer seeks at five and ten seconds beyond visual EOF. It bounds only the
coarse grid by the frame-count/FPS estimate and still requires the exact final
frame. No selector, provider, cancellation, resume, or public API changed.

#239 confirms from a clean archive that the shipped wheel manifest still has
an empty base and only OpenCV plus imageio-ffmpeg in `[video]`, but its normal
dependency installation remains unproven. Two bounded network attempts stalled,
and a cache-only install later found that resolver metadata existed without the
OpenCV wheel payload. No pin or runtime was changed to hide that delivery gap;
repeat the installed real-MP4 gate only when the declared wheels can actually be
obtained, rather than adding another installer or dependency abstraction.

#240 then rechecks the changed parser/selector/JPEG path with the maintained
ordinary-MP4 matrix and finds no new reproducible runtime defect. The focused
inspection, extraction, and lightweight-import set passes 38 tests. Do not add
a parser or retune selection from an exploratory file whose own duration and
final PTS disagree; at that point the next choices were a valid red case, the
pending installed extra gate, or #127, which #294 later resolved.

#241 re-proves the #238 path once against authorized Google service. The exact
short-video/long-audio shape retained final frame 1 at PTS 0.5, then two
independent `gemini-2.5-flash` configs made one image call and one audio call;
the complete two-asset composition reported 1,021/41 tokens and left no secret
or temporary residue. This is post-change service evidence, not permission to
repeat the run, merge configs, add retry, or generalize providers.

#242 makes the existing deterministic video preflight reject an injected image
provider whose `recognize_images` member is not callable, before source or
retained-JPEG access. The ordinary image workflow keeps its later check so its
draft/model-attempt evidence is not lost. This is one explicit early-validation
mode with two video consumers, not a provider superclass or second validator.

#243 also rejects a structurally invalid cancellation object in either video
config before source access. The shared structural check verifies only a
callable `is_set` member. #294 later selected Route A and now observes state
before media work; exceptions and non-boolean return values remain execution-
time configuration errors.

#244 makes the public video `output_dir` contract exact: use a nonempty string
or `Path`. Empty/whitespace strings, bytes, arbitrary objects, and custom
`PathLike` wrappers now raise `OUTPUT_PATH_INVALID` before source or media work,
instead of writing relative retained assets or leaking `TypeError`. This is one
shared video-input check, not a generic filesystem abstraction.

#245 confirms that standalone long-MP3 results already fit the video outcome
and composer, but automatic duration routing must not be implemented as
short-route failure fallback or repeated whole-audio probing. With #127 now
resolved by #294, the next integration seam may retain one MP3 and select
exactly one adapter.
One-shot 300-second-to-model-limit integration is independent of #152; the
9.5-to-10-hour ceiling and persisted recovery remain blocked on #152.

#246 makes one bounded normal-install refresh of #239 from exact commit
`1e9cd87`. The clean 259,383-byte wheel still has an empty base and only OpenCV
plus imageio-ffmpeg in `[video]`, but pip timed out while downloading the 31.2 MB
imageio-ffmpeg wheel. The run stopped before installed imports and real MP4s,
cleaned its disposable root, and did not retry or change pins. Treat this as an
open external delivery gate, not a package defect or permission to add another
installer.

#251 built the exact current `20c9fd4` archive into one structurally valid
250,405-byte wheel and reconfirmed its empty base, extras, video dependency
ranges, package contents, `py.typed`, and absence of bundled native payloads.
Its only ordinary
`[video,audio,image]` install did not commit, while the proof wrapper lost the
original process's final exit diagnostics. Therefore no dependency-specific or
OCRLLM failure is claimed and no installed MP4 proof exists. The external gate
remains open; do not treat this diagnostic gap as permission to retry in a
loop, repin, vendor, or borrow an existing environment.

#252 proves the #249 image cleanup-partial state through the public PDF facade.
A 16-page run keeps two ordered eight-page child sidecars, publishes partial
Markdown when the first group has usable output plus a cleanup warning, and
preserves the complete second group. Ordinary resume reuses both groups with
zero provider calls and retains the same final status, warning, and Markdown.
No runtime, PDF-level provider ledger, legacy repair format, or replay policy was
added.

#253 makes the next single normal-install attempt fully observable but does not
close the installed-video gate. Exact commit `b91d5d0` produced the same healthy
250,405-byte wheel; pip then exited 1 after 26.064 seconds because the remote
host reset the proxied PyPI file connection while fetching imageio-ffmpeg
(Windows 10054). The fresh environment installed nothing, so no external import
or real-MP4 claim follows. No pin, installer, metadata, runtime, or API changed.

#254 directly challenges the fixed video-audio FFmpeg timeout with a valid
ten-hour local MP4. Public extraction, full MP3 decode validation, and atomic
publication completed in 54.886 seconds for a 146.9 MB source and produced a
144.0 MB MP3; the disposable root was removed. No legacy FFmpeg extraction
timeout incident was found, so the simple 600-second bound remains unchanged.
This proves provider-free extraction only, not long-audio recognition from
video or the then-open #127/#152 decisions; #294 later resolved #127 only.

#255 proves standalone long-MP3 local validation stays memory-bounded through
the real 9.5-hour A2a ceiling. Fresh processes stayed near a 35.4 MiB peak for
301 seconds, one hour, and 9.5 hours while file size grew from 1.2 to 136.8 MB;
the snapshot copy and decoded samples are both consumed in fixed chunks and all
temporary roots were removed. Keep complete streaming decode because it catches
metadata/frame-count mismatch. That iteration changed no Files, chunking,
video-routing, or cancellation behavior.

#247 adds the missing public consumer proof for the opposite partial-video
direction. A real MP4 whose frames succeed and whose audio provider fails once
now continues through atomic `publish_video_result()` while retaining frame
text, JPEGs, the extracted MP3, the audio error, partial status, and an exact
two-call total. Runtime and providers did not change; long-audio cleanup partials
remain outside video until the post-#294 #152 overlap decision and integration.

#248 stops a post-response short-audio client-close error from discarding a
valid paid transcript. The public audio result is now partial with an explicit
cleanup warning and `provider_client_closed=False`, while call/token evidence
survives; a primary provider error still wins and carries only a cleanup flag.
Combined video keeps this usable audio result and its retained media. The same
close-only response-loss shape remains registered for the native image adapter
as a separate atomic defect, not a reason for a generic lifecycle layer.

#229 removes one duplicate `VideoRecognitionOutcome` import left inside the
video facade after #219 had already made that type a required module-scope
binding. Runtime type hints, lazy imports, separate configs, and execution are
unchanged. This is a narrow readability reduction, not authority for mechanical
unused-code deletion.

#230 keeps the standalone `recognize_long_mp3` root API callable after an
explicit import of its same-named submodule. Only its lightweight facade is
bound during package initialization; decoder, processor, Google SDK, and Files
work remain invocation-lazy. A real 301-second MP3 with an injected lifecycle
completed once and removed its owned snapshot.

#231 proves that #230 package boundary from a clean wheel of exact commit
`9f515ad`. All five bound long-MP3/video functions remain callable,
identity-stable, and runtime-type-hintable in root-first and explicit-submodule-
first imports from an external no-dependency install; optional recognition,
media, provider, HTTP, and legacy modules stay unloaded.

#232 applies the same exact package rule to the primary `recognize()` and
`recognize_batch()` facades. Explicit same-named submodule imports cannot turn
the root names into modules, and standard runtime type hints resolve. Only the
thin facade definitions are package-bound; batch preflight, output ownership,
configuration validation, recognition execution, media, and providers remain
lazy. #233 below is the resulting proportional clean-wheel gate for that facade
initialization change.

#233 completes that refresh from a clean wheel of exact commit `79ad5d0`.
All seven bound primary, long-MP3, and video facades remain callable,
identity-stable, and runtime-type-hintable under both import orders from an
external no-dependency installation. Batch execution and optional media/provider
modules remain unloaded, so the result is still a real lightweight Python
library rather than an application-shaped import.

#150 additionally exercises an audible 301.056-second MP4 through the public
video facade without network. The image branch retained five frames and made
one injected call; the audio branch made zero provider calls and returned typed
`SOURCE_TOO_LARGE`, leaving the top-level result honestly `partial` and keeping
the extracted MP3. This confirms provider separation and failure honesty, while
also proving that the five-minute A1 audio ceiling is not mature lecture-video
support. #151 completed standalone Google Files A2a independently; #294 later
closed the cancellation blocker, while #152 overlap still gates the persisted
chunk route. #211 closed the former #149 source-snapshot placement blocker.

#072 has implemented P1-c offline: `recognize(one.pdf)` lazily uses
`ocrllm[pdf-vision]`, snapshots at most 100 MiB without whole-file Python reads,
renders one page at a time and one serial group of eight at a time, reuses the
ordinary image checkpoints, and publishes ordered range-marked Markdown plus a
same-named state directory. A real local 16-page PDFium probe and focused
cancel/resume tests pass; `recognize_batch()` intentionally rejects PDF for this
first slice. Its initial bounded Google exit attempt made zero provider calls
because the current Windows profile then had no Google credential.
The same-named state path must be an ordinary directory: #116 proves on Windows
that a pre-existing junction is rejected with `OUTPUT_PATH_INVALID` before
render/provider dispatch, while ordinary overwrite/resume directory behavior is
preserved. This is a narrow ownership check, not a filesystem sandbox.

#073 upgrades the isolated `pdf-vision` package smoke from a one-page backend
probe to a public 16-page installed-wheel run. It requires two serial groups of
eight through an injected no-network provider, two complete ordinary image
sidecars, ordered range-marked final output, and no snapshot or rendered-PNG
residue. This was packaging/runtime evidence, later complemented by #078 live.

#075 rechecked all implemented credential sources without reading or printing
a secret. Neither `GOOGLE_API_KEY`, `GEMINI_API_KEY`, nor the current account's
legacy `OCRLLM/QCR` QSettings key `ui/google_api_key` is available; the probe
succeeded and made zero provider calls. #076 then restored the legacy settings
entry path and the maintainer populated the existing QSettings source.

#078 completed P1-c. A foreground, no-retry `gemini-2.5-flash` run discovered
37 current models and recognized a 16-page PDF through exactly two serial
eight-page image requests. It reported aggregate usage of 4,802 input and 117
output tokens, published ordered output with two complete child checkpoints,
retained no rendered pages, cleaned both temporary roots, and exposed no key or
OCR body. Combined with the earlier offline resume and installed-wheel proofs,
P1-d is closed without legacy compatibility. P1-e local parsing and
retained-frame selection, frame recognition, audio extraction, and a concrete
image/audio provider split are implemented. Every frame group retains exact
identity for the next composition/lifecycle slice. Provider generalization
remains deferred.

All no-cost Stage M exit criteria pass at product checkpoint `700cc05`, with
the clean-archive evidence recorded by `5d966e1`. The root suite reported 1203
passed; the exact archive suite reported 1193 passed and 10 expected skips.
`tools/run_stage_m_offline_gate.ps1` reruns the exact Git-archive suite,
fixture/compile checks, clean wheel and outside-repository import guards,
dependency profiles, generated-image smoke, and offline DashScope construction.
It also runs installed public PDF recognition with an injected provider. It
makes no external provider request.

The public image facade decodes PNG/JPEG inputs before provider dispatch,
passes request-scoped validated snapshots to an injected provider, rejects
empty/control-only/refusal-shaped or non-UTF-8 output, returns typed redacted
errors, and reports canonical `source_type="image"` with `profile="board"`.
File output is optional and atomic; `output_dir=None` stays memory-only. Pillow
remains lazy during plain `import ocrllm`.

Phase 1 uses one unified `board.v17` workflow for printed, projected,
handwritten, formula, table, and ordered-image inputs. The Beijing live gate
completed all 13 recognitions and exactly 52 provider calls with no retry or
terminal failure. Both independent six-dispatch runs passed. Run A required no
restoration; Run B restored exactly one missing handwriting sign through the
same generic two-of-three omission-scout path used for every image class.

Preserve
`evidence/phase1/phase1-quality-v17-2026-07-11-cn-beijing.json`: 107,246
bytes, SHA-256
`6f0454d634dbe76f68f29c07a4c0ced4a047c080e46bb75dda2cb84ffca3a96b`.
The clean Git-archive gate at `0278b66` is historical evidence for the image and
worker boundaries. The current allowed work follows the #065 queue in the
authority file. The detailed maturation/audio plan is retained as history and
bounded design evidence where it does not conflict with that queue.

The active library has a region-bound in-memory credential scheduler and
request/batch image resume. Candidate switching is opt-in, bounded,
disposition-gated, and fully disclosed offline. Experimental direct Google
short-audio recognition and standalone single-request Google Files long-MP3
recognition are live-proven but remain memory-only; their published gates are
not transcription-quality evaluations. PDF repair, long-audio chunk/resume,
and persisted/resumable audio remain unavailable. Video recognition is now
available as one typed orchestration facade over retained-frame extraction and
recognition plus independently configured extracted-audio recognition.
Provider-free composition and atomic final Markdown publication are separate
public steps. Video branch resume, A2b chunking, and worker routing remain
unavailable. The request-owned video snapshot implementation is present in a
clean externally installed wheel and does not make plain package import load
heavy media or provider modules. Local user
PDFs/screenshots under `docs/` are untracked
supplemental material, not redistributable gate evidence.

The defect register is only in `docs/ACTIVE_STATE_AND_RULES.md`. D1-D7,
F1-F4, and G1-G10 are closed in offline code and tests. Stage M itself remains
open only at that credential- and budget-gated live exit; provider-account
semantics are not claimed live-proven by the offline closure.

## Legacy Application

Path: `legacy_app/`

Use for:

- Behavior reference and explicitly scoped maintenance for the old GUI, CLI,
  FastAPI, processors, and launchers
- Historical outputs and incident records used to define active-library
  fixtures

Read next:

- `legacy_app/README_LEGACY.md`
- `legacy_app/AGENTS.md`
- `docs/legacy_bilibili_social_long_debug_record.md` for multi-part Bilibili
  course download/recognition recovery.
- `docs/legacy_youtube_playlist_social_long_workflow.md` for YouTube playlist
  course download/recognition recovery.
- `docs/legacy_filetrans_codex_debug_record.md` for Codex/FileTrans recovery.

Do not use as a new dependency boundary:

```python
import legacy_app.OCRLLM
```

## Suspended Future Plan

Path: `Architecture.md`

Status: future plan, currently suspended.

Do not make the Rust/PyO3 rewrite active again until the Python import contract
has real downstream usage and stable module boundaries.

## Runtime Artifacts

These paths are not source-of-truth code:

- `output/`
- `temp/`
- `ocrllm_social_e2e/`
- `.pytest_cache/`
- `__pycache__/`

Do not infer architecture from generated output or temporary files.

## Choose The Edit Location

```text
Need current state or open defects   -> docs/ACTIVE_STATE_AND_RULES.md
Need to know what to build next      -> docs/plan_phase1_maturation_and_phase2_audio.md
Need to change the public library API      -> src/ocrllm/ and tests/
Need to add a downstream import feature    -> src/ocrllm/ and tests/
Need to compare old product behavior       -> legacy_app/
Need to fix or maintain the old app        -> legacy_app/ plus its diary
Need to record migration state             -> MIGRATION_STATUS.md
Need to decide GO/NO-GO or port behavior   -> docs/ocrllm_library_go_no_go.md
Need to debug Bilibili social-long courses -> docs/legacy_bilibili_social_long_debug_record.md
Need to debug YouTube playlist courses    -> docs/legacy_youtube_playlist_social_long_workflow.md
Need to design the completed module shape  -> docs/ocrllm_module_target_design.md
Need to revisit future Rust/PyO3 design    -> Architecture.md
```

## Do Not Cross These Boundaries

- Do not import `legacy_app.OCRLLM` from new downstream projects.
- Do not copy a whole legacy module into `src/ocrllm`.
- Do not let `import ocrllm` pull GUI, FastAPI, social downloader, or heavy
  media dependencies.
- Do not treat `Architecture.md` as the active implementation plan.
- Do not put runtime output defaults inside package directories.
- Do not add PyMuPDF or `fitz` to the active library. Active PDF work uses
  PDFium through `pypdfium2` only after the PDF phase is authorized.
- Do not begin or claim HarmonyOS/ArkTS compatibility. It is deferred by the
  active GO/NO-GO decision.

## Verification Commands

The pinned offline checkpoint checks are:

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

Before reporting completion, run the maintained clean-archive gate:

```powershell
& .\tools\run_stage_m_offline_gate.ps1
```

The latest delegated run (#305, exact commit `efa7069`) proved and propagated
the active `127.0.0.1:10080` proxy, passed 1,558 archived tests with one skip,
and built the wheel. It then exposed a Windows PowerShell argument bug in the
gate's multiline wheel-content probe before any install profile began. #306
moves those three checks into `tools/check_built_wheel.py`; focused and full
offline regressions pass. The corrected #306 gate then passed 1,571 archived
tests with one skip, built, checked, and installed the wheel, but the real base
target had grown to 1,265,634 bytes and exceeded the old 1 MiB budget before
optional profiles. #307 proves the target contains no accidental payload and
raises only that real-disk budget to 1.5 MiB; the 256 KiB wheel cap stays fixed.
The clean #307 gate then passed base plus audio, image, image+DashScope, Google,
audio+Google, and PDF-vision profiles, but one fresh pip process reported no
OpenCV candidates at the video profile. #308 live catalog evidence confirms
4.13.0.90 and 4.13.0.92 still provide compatible Windows ABI3 wheels, and a
no-cache dry resolution selects 4.13.0.92 plus NumPy 2.2.6 through the active
proxy. The pin remains correct; the installed combined-video gate remains open
for one clean replay after that materially different index response. #309
pre-fetched the exact current media wheels through that proxy and the unchanged
gate installed and smoked the video profile, proving the dependency set works.
Its 254,451,578-byte installed delta exceeded the unproven 220 MiB estimate.
#310 inspects the exact wheel payloads and refreshes video to 260 MiB and the
existing sum-of-profile combined ceiling to 293 MiB; no dependency changes.
Its clean gate installed the combined profile, then #311 found the final smoke
still patched the pre-#297 short-audio processor module. The gate now patches
the actual `recognize_video_mp3` seam; no library compatibility shim was added.
The final exact `d80170f` clean gate passes all eight profiles and the installed
combined recognize/compose/publish workflow with exit 0.

#312 begins executable A2b interval work without adding the public chunked
recognition route. One exact planner window can now materialize one temporary
mono 16 kHz / 64 kbps MP3 beside an already-owned source and remove it after
use. The implementation follows the legacy Google re-encode shape but rejects
legacy persistent chunk directories, parallel splitting, provider queues, and
repair/checkpoint coupling. `ocrllm[audio]` consequently includes lazy
`imageio-ffmpeg` as well as `miniaudio`; plain package import remains
dependency-free. The next slice is serial window consumption and paid-result
persistence, not another media abstraction or provider-class hierarchy.
The exact `a9dc6e6` clean gate passes with exit 0: installed audio is
91,174,290 bytes, audio+Google is 130,218,489 bytes, the installed interval
smoke materializes and removes one segment, and all existing profiles plus the
combined video workflow remain green. No provider API is called.

#313 supplies the next A2b prerequisite without inventing state early. The
existing streamed MP3 snapshot copy now computes SHA-256 in the same 1 MiB loop
and carries it through short, long, and video-selected snapshot facts. There is
no second source scan, public digest, provider change, sidecar, or resume claim.
The next slice can build audio request/window identity from real byte evidence.
The exact `b9ae0c9` clean gate exits 0 with 1,581 archived tests passing and one
expected skip, a 259,949-byte wheel, every optional profile green, and both the
installed interval and combined-video smokes complete without a provider call.

#314 adds the internal `audio.long.interval.v1` prompt before request identity
is frozen. It gives both original-source and uploaded-clip coordinates, treats
padding as context only, and requests only the logical range without legacy
HTML markers or timestamps. The existing materializer validation is now one
audio-owned function shared by its two real consumers. All 1,586 source tests
pass; request identity, state, dispatch, resume, and repair remain later slices.
Exact commit `5047a00` also passes the complete installed gate: archive 1,585
passed/1 skipped, all profiles and media smokes pass without a cloud call, and
the wheel is 261,349 bytes—795 bytes below its current ceiling. Inspect for
real package reduction before adding the next runtime slice; do not raise the
limit or damage file responsibilities mechanically.

#315 performs that audit rather than raising the cap. The exact #314 wheel has
no accidental runtime payload; its only justified reduction is the 36,679-byte
repository/source package README, because standard METADATA already carries the
root README and no runtime resource consumer reads the detailed file. It remains
in Git and sdist but is explicitly excluded from wheels and guarded by the
maintained checker. A worktree build measures 247,533 bytes, restoring 14,611
bytes of headroom; the full 1,587-test source suite passes. Exact clean installed
proof remains pending. A real 169,681-byte sdist retains both README files and
excludes tests/legacy, proving this is wheel-only reduction.
Exact clean commit `4c9e31b` passes the full installed gate: archive 1,586
passed/1 skipped, wheel 247,533 bytes, base 1,249,562 bytes, and every profile
and media smoke green without cloud I/O. A pre-child wrapper failure also proves
Windows `Start-Process` parents must not receive duplicate upper/lowercase proxy
names; the corrected gate used uppercase only.

#316 adds only the internal long-audio request fingerprint. It binds the owned
source digest, whole/interval mode, provider, model, versioned prompt, and the
complete interval window when present. Whole prompt version
`audio.transcription.v1` now complements `audio.long.interval.v1`. The complete
1,605-test source suite passes; no state, dispatch, resume, repair, public API,
or provider call is claimed. Exact commit `d590835` passes the complete
installed gate: archive 1,604
passed/1 skipped, wheel 248,791 bytes, base 1,255,390 bytes, all profiles and
local media smokes green, no cloud I/O, and complete cleanup.

#317 adds only an immutable audio-owned partial state: one ordered tuple of
#316 request fingerprints plus the settled serial prefix. Slots preserve
Markdown/digest, provider/model, call count, nullable tokens, and honest
complete/partial warnings. The full 1,619-test source suite passes. No
serialization, file I/O, dispatch, resume, repair, or public API is claimed;
exact commit `5580da1` passes the full installed gate with 1,618 archived tests
passing and one expected skip, a 250,819-byte wheel, all profiles/media smokes
green, no cloud I/O, and complete cleanup.

#318 adds the state-only canonical UTF-8 JSON serializer and strict parser.
Valid documents round-trip byte-for-byte; duplicate keys, schema drift,
unsupported versions, non-finite values, and invalid slot facts fail as typed
resume-state errors. All 1,629 source tests pass. This is not filesystem
persistence or runnable resume: it adds no loader, writer, path, size policy,
atomic replacement, dispatcher, repair parser, provider call, or public API.
Exact commit `3724dc3` passes the clean installed gate: 1,628 archived tests
pass with one expected skip, the wheel is 252,828 bytes, all installed profiles
and local media smokes pass, no cloud I/O occurs, and cleanup is complete.

#319 adds audio-owned bounded atomic save/load for that strict state at one
explicit caller path. It preserves an old target until complete
write/flush/fsync/close, bounds actual reads to 16 MiB plus one probe byte, and
keeps cleanup failures from replacing an earlier primary. All 1,650 source
tests pass. No filename policy, resume dispatcher, provider call, repair path,
final publication, or success deletion is claimed. Exact clean installed commit
`a601555` passes with 1,649 archived tests and one expected skip, a 255,474-byte
wheel, all installed profiles and local media smokes green, no cloud I/O, and
complete cleanup.

#320 adds one pure audio reuse gate. A loaded state yields its same immutable
settled prefix only when the complete ordered current request-fingerprint tuple
is exactly equal; every length, order, or content mismatch is a typed
`RESUME_STATE_MISMATCH`. All 1,666 source tests pass. This does not choose a
state path, dispatch a provider, compose output, authenticate hostile local
edits, or expose a public resume API. Exact clean installed commit `da8f0af`
passes with 1,665 archived tests and one expected skip, a 256,150-byte wheel,
all profiles and local media smokes green, no cloud I/O, and complete cleanup.

#321 fixes the next long-audio boundary: publish to
`output_dir/<normalized audio stem>/result.md`, with one temporary resume
sidecar in that same-name directory. Whole-file and optional interval modes are
both required; interval length is exact integer minutes. The next slice is path
definition and structural preflight only, not dispatch, repair, provider
abstraction, fallback, or legacy-format compatibility. Collision ownership must
distinguish a new run from the existing directory required by resume.

#322 now provides the lifecycle-neutral internal path plan: normalized same-name
root, `result.md`, and `.ocrllm-long-audio-resume.json`. It creates nothing,
rejects a non-directory output parent and overlong Windows paths, and permits an
existing job root until the caller explicitly selects new-run or resume
ownership. All 1,675 source tests pass. Exact commit `a9fb1d0` passes the clean
installed gate with 1,674 archived tests and one expected skip, a 257,558-byte
wheel, all profiles and local media smokes green, no cloud I/O, and complete
cleanup.

#323 adds the lifecycle ownership check. New work rejects any existing job
root; resume requires the existing directory and fixed regular state sidecar,
and rejects an already published `result.md`. It performs no writes or state
parsing and does not inspect unrelated siblings. Fixed result/state names now
have one source of truth. All 1,692 source tests pass; exact installed proof is
complete. Exact commit `782220d` passes with 1,691 archived tests and one
expected skip, a 258,617-byte wheel, all profiles and local media smokes green,
no cloud I/O, and complete cleanup. Before the next long-audio composition
slice, correct the shared `ResumeStateError` default that still says "image"
despite serving image, PDF, and audio; do not redesign the hierarchy.

#324 completes that correction. The default is now the neutral "saved
recognition state" while the stable code and every explicit caller message stay
unchanged. The focused error/resume set passes 81 tests and all 1,693 source
tests pass. Exact commit `0b415f2` passes with 1,692 archived tests and one
expected skip, a 258,616-byte wheel, all profiles and local media smokes green,
no cloud I/O, and complete cleanup. Proxy TCP passed but the separate proxied
PyPI HTTPS probes timed out; the unchanged wheelhouse supplied the gate, so no
HTTP 200 is claimed. The next feature slice is public whole-file persistence
and resume, not an otherwise unconsumed start-gate wrapper.

#325 makes the public whole-file route that first consumer. With `output_dir`,
`recognize_long_mp3()` owns one same-name directory, saves the settled paid
result before atomically publishing `result.md`, and removes temporary state
only after success. Exact `resume=True` validates source/model/prompt/transport
identity and publishes with zero new provider calls. The no-output-directory
behavior remains memory-only. Interval dispatch, repair, overwrite, fallback,
generic transactions, legacy formats, and worker routing are unchanged. All
1,702 source tests pass. Exact commit `e378556` passes the clean installed gate
with 1,700 archived tests and one expected skip, a 260,753-byte wheel, every
profile and local media smoke green, no cloud I/O, and complete cleanup.

#326 fixes one prerequisite before interval dispatch: the Google Files adapter
now consumes the provider-start gate that `recognize_long_mp3()` already
activates or reuses. It waits once before SDK/catalog/upload work; one Files
lifecycle does not claim separate permits for polling, generation, or cleanup.
The failing-first order regression and 58 adjacent tests pass, as do all 1,703
source tests. No interval API, retry, fallback, client cache, or second limiter
was added. Exact commit `c8a8c72` passes the clean installed gate with 1,702
archived tests and one optional skip, a 260,782-byte wheel, every profile and
local media smoke green, no cloud I/O, and complete cleanup.

#327 exposes that interval route through the existing public
`recognize_long_mp3()` call. An exact positive integer `interval_minutes`
selects persistent serial windows; every settled speech or no-speech window is
saved before its temporary MP3 is removed. Exact resume may omit the argument
and restores it from v3 state, reusing only the exact settled prefix. Existing
v2 whole-file state migrates narrowly to whole mode. There is no parallelism,
retry, fallback, repair integration, provider abstraction, legacy format, video
routing, or worker change. The complete source suite passes 1,719 tests.
#330 closes the clean installed proof at exact `56e7cc8`: archive 1,718 passed
with one optional skip, wheel 266,907 bytes, base 1,350,210 bytes, all eight
profiles and local media smokes green, no cloud I/O, and complete cleanup. A
bounded real Google interval call remains the next product evidence.

#331 added a credential-safe two-window interval live runner and reached Google
Files with one real 601-second input. The request ended as
`PROVIDER_RESPONSE_INVALID`, published no `result.md`, retained temporary state,
closed the provider client, and did not close the live gate. The delegated gate
then deleted its owned temporary root, so that particular state cannot prove
resume; this was an operator cleanup mistake, not a library resume result.
#332 exposes only exact nonnegative provider-attempt and persisted-window counts
on typed interval failures. It does not expose transcript, paths, credentials,
or arbitrary error details, and adds no retry, fallback, or provider framework.
Exact commit `8b37e81` passes the clean installed gate: 1,722 archived tests pass
with one optional skip; wheel 266,940 bytes; base 1,350,517 bytes; all profiles
and local media smokes green; no cloud I/O; complete cleanup.

#333 preserves the later live failure root and proves one of two interval slots
is settled in v3 state: one Google generation call, usage 12,688/65,494, and no
published result. The delegated wrapper lost stdout/return-code evidence while
the owned process continued, so failure type and cleanup remain unknown; no
second request was started. #334 adds only a maintenance-runner `--resume` flag
for that existing public route. It does not parse state or add recovery logic;
all 1,724 source tests pass. A real resume preserved slot 0 but failed before
another generation with request-scope `PROVIDER_RESPONSE_INVALID`, zero current
calls, and no remote-file fact. #335 adds one safe fixed `provider_operation`
detail to mapped SDK exceptions so a bounded follow-up can distinguish catalog,
upload, processing, and generation without provider text. All 1,725 source
tests pass; no retry/fallback policy changed. The live gate remained open here.
#335 is clean-installed at exact `d2819c0`: 1,724 archived tests pass with one
optional skip, wheel 266,993 bytes, base 1,351,006 bytes, all profiles and local
smokes green. One auditable retained-state resume then identified the real
failure as `provider_operation=upload`, with zero new generation calls and one
persisted slot. The sidecar remained reusable at this point.
#336 adds only `provider_sdk_type` for an otherwise-unclassified native Google
error, accepting an ASCII Python identifier and exposing it through the runner
as `sdk_type` after a second validation. It records no message/module/path and
does not change retry policy. All 1,725 source tests pass.
#336 is clean-installed at exact `8a738fa`: 1,724 archived tests pass with one
optional skip, wheel 267,086 bytes, base 1,351,735 bytes, all profiles and local
smokes green. Its bounded live resume identified upload `ReadTimeout` with zero
new generation calls and one persisted slot. #337 maps the common HTTP-client
timeout MRO family to existing retryable `PROVIDER_TIMEOUT` without importing a
network SDK or adding automatic retry. All 1,726 source tests pass.
#337 is clean-installed at exact `90fd0e4`: 1,725 archived tests pass with one
optional skip, wheel 267,184 bytes, base 1,352,572 bytes, all profiles and local
smokes green. One bounded caller-owned resume then succeeded against the real
retained state: catalog 37, total/current calls 2/1, current usage 8,886/572,
final publication, state removal, and remote/client cleanup proven. The Google
interval live gate is closed; automatic retry/fallback remains unimplemented.

#339 closes one bounded DashScope connectivity/lifecycle gate with current
catalog discovery and one `qwen3.5-ocr` formula-board call. #340 preserves the
compatible endpoint's prompt/completion token counts through the existing
per-model accounting path and is clean-installed at exact `ec1839c`: 1,745
archived tests pass with one optional skip, all profiles and media smokes green.
#341 then connects video-owned long audio to the already-proven whole/interval
settlement functions. Whole remains the default; `audio_interval_minutes`
accepts exact positive integer minutes. Paid state stays directly under the
video output root on failure and is removed after clean recognition/snapshot
cleanup; no nested standalone Markdown is published. This is future resume
groundwork, not a public video-resume claim, and repair remains separate.
Exact `67c52c2` passes the clean installed gate with 1,754 archived tests and
one optional RapidOCR skip, a 268,897-byte wheel, all eight profiles, and local
video/combined recognize-compose-publish-cleanup smokes green.

#296 previously completed only the local status-channel prerequisite. Python standard-library
`subprocess.run()` preserved exact child exits 0 and 7, stdout, stderr, and a
timeout marker; an owned local parent/descendant probe also proved exact
Windows process-tree termination after an outer timeout. The gate's own five
bounded-process regressions pass. Future delegated execution should reuse that
standard-library channel and owned-tree cleanup, and must not add another
`Start-Process` wrapper or repository controller. This is not evidence that the
clean installation itself passes.

Its implementation and budgets are defined in
`docs/ocrllm_library_go_no_go.md`. A DashScope live gate must use the currently
authorized one-atomic-trial boundary or a later explicit budget, confirm the
exact region/`base_url`, discover models live, cap calls, and pass the runner's
Git/import, manifest, artifact, and credential preflight.

Active-library migration tests must not modify or run the legacy suite as a
phase gate. Create fixtures and tests under root `tests/`. Legacy commands and
tests are historical reference unless a separate legacy-maintenance request
explicitly authorizes that work.
