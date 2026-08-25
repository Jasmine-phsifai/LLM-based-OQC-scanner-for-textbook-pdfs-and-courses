# Active Library Boundary

This directory is the active `ocrllm` package for downstream imports.

Read `../../docs/ACTIVE_STATE_AND_RULES.md` first. It outranks every other
document and carries current state, the open defect register, and the coding and
documentation rules. Then read `../../docs/ocrllm_library_go_no_go.md` for phase
gates and file responsibilities.

The approved current work is the `#065 Unified Execution Queue` in
`../../docs/ACTIVE_STATE_AND_RULES.md`; the older Stage M/A plan supplies detail
only where that queue has not superseded it. #078 closed P1-c with one bounded
16-page Google run through exactly two serial image requests, complementing the
existing offline resume and installed-wheel proofs. #120 answered P1-d no: the
new library does not consume legacy localized repair Markdown, and ordinary
resume remains its PDF recovery path. P1-e video is now active in ordered
slices: #120 shipped lazy local MP4 inspection and #121 shipped bounded
negative-feedback frame selection plus retained JPEGs; #122 recognized ordered
frame groups, #123 extracted audio for an independent audio config, and #124
kept exact group identity on every settled outcome. #125 distinguishes a valid
silent MP4 from corrupt declared audio. #126 adds the first narrow
`recognize_video()` orchestration outcome over those exact branches. It retains
media and typed partial failures. #129 adds explicit memory-only
`compose_video_result()` for already returned complete or partial outcomes; it
keeps frames and audio separate and does not publish Markdown, infer time
alignment, or copy legacy formats. #130 proves that exact facade from a clean,
freshly installed wheel through a real local MP4 without loading heavy video
dependencies during plain import. #131 keeps the final candidate when excessive
frame density is capped; #132 makes the shared 96-unit output-stem budget use
Windows UTF-16 units without splitting supplementary characters; #133 stops
maximum-length segment partitioning from rounding down. #134's bounded Google
run returned honest partial output but its ephemeral controller lost the audio
error code/call evidence. #135 adds a maintained, redacted combined-video smoke
runner with independent image/audio configs and exact-or-null call evidence.
#136's first post-runner attempt lost the external exec session identifier after
completion, so no provider result may be inferred from it. #137 followed the
correct protocol and proved a one-call image success plus a one-call audio
`PROVIDER_QUOTA_EXHAUSTED`, with honest partial outcome/composition and two
retained assets. #162 later reused the same runner once: image returned
`PROVIDER_RESPONSE_INVALID`, audio returned `PROVIDER_QUOTA_EXHAUSTED`, and the
outcome remained honestly failed. A future live recheck is warranted only after
a relevant boundary or runtime change; it must retain the exact yielded session,
validate redacted safe JSON before cleanup, and must not be repeated merely to
turn typed failures green. Final publication is shipped in #144/#146 below;
video recovery/resume remains unavailable and must not copy legacy formats.
Do not add adapter retry, automatic model switching, or provider pooling.
#138 requires exact lexical artifact layout in every public video outcome:
frames use `output_root/frames/*` and optional audio uses
`output_root/audio.mp3`. Reject mismatches at construction, but do not turn
this into path resolution, symlink policy, hashes, manifests, or a sandbox.
#139 requires exact-or-unknown provider-call totals in composed video results.
Missing evidence from any settled provider branch makes
`current_run_provider_call_count` null; only a proven pre-dispatch video/audio
parsing outcome is zero. Do not add a ledger, telemetry layer, or billing API.
#140 makes audio absence and an audio artifact mutually exclusive in a public
video outcome. Reject the contradiction at construction; do not hide it by
dropping the artifact during composition or adding another audio state.
#141 requires child result status to propagate: the video is complete only
when every frame result and the audio result, when present, are complete.
Partial children remain usable but keep both outcome and composition partial.
#142 requires every successful frame-group outcome to carry an exact image
`RecognitionResult`. Reject branch/media mismatches at outcome construction;
do not relabel them during composition or build a generic media graph.
#143 requires downstream examples to inspect `VideoRecognitionOutcome.status`
before composition. Fully failed outcomes remain branch-level evidence and are
not converted to a standard video result.
#144 adds explicit atomic final Markdown publication through
`publish_video_result()` while keeping `compose_video_result()` memory-only.
The caller supplies the path; do not derive legacy names or add resume,
manifest, cancellation, or provider behavior to the publication step. Never
allow its Markdown target to replace a retained frame or audio asset.
#145 proves the current video cancellation paths are asymmetric. Do not add
tests that freeze that behavior or implement #127 until the maintainer chooses
returned branch cancellation versus propagated cancellation with recoverable
settled work.
#146 proves `publish_video_result()` is present and usable in the clean wheel.
Future publication work should not add another build harness or repeat this
proof unless the public surface, manifest, or runtime dependency boundary
changes.
#151 supersedes #147's short-audio wording: the distribution Summary names the
shipped image, PDF, audio, and video surfaces after the standalone long-MP3 API.
It does not claim automatic long-audio routing from `recognize()` or video,
chunking/resume, fallback, or worker support. #148 keeps the exact final source
frame in the bounded coarse scan when the five-second grid does not; preserve
this invariant without adding a configurable sampler or second scene detector.
#211 resolves #149 with one hidden, streamed, request-owned MP4 under caller
`output_dir`. Inspection, comparison, retained decode, and combined audio
extraction must keep consuming that exact path until request cleanup. Do not add
a public video-temp option, separate branch snapshots, whole-video memory, a
generic media cache, or legacy format support. #152 keeps long-audio chunk scope
open; do not implement it until the maintainer chooses.
#212 makes cleanup an explicit invariant on normal, invalid-media, returned-
cancellation, and propagated-cancellation exits: no `.ocrllm-video-source-*`
path or in-process output claim may survive. Preserve that invariant without
turning the current #127 asymmetry into an accepted cancellation contract.
#213 proves the clean installed wheel contains both #211 lifecycle modules and
keeps the public video facade import-light. Preserve whole-package selection in
the Hatch wheel; do not add a per-module manifest, build wrapper, or eager import
for this internal implementation.
#214 reserves exact `output_root/audio.mp3` against Markdown publication even
for silent video. Preserve this lexical media-layout invariant; do not turn it
into a ban on publishing elsewhere under `output_root`, a path sandbox, or a
general media-name registry.
#215 confirms `.md` is recommended rather than mandatory for the caller-owned
final publication path. Do not infer a suffix validator from media-artifact
extensions or freeze arbitrary suffixes in tests; such a breaking restriction
needs an explicit maintainer product decision.
#166 makes source order a constructor invariant for every public video outcome:
retained frame indices are strictly increasing and timestamps never move backward.
Do not add path-identity, timestamp-uniqueness, or generic ordering machinery.
#167 also makes contiguous `0..n-1` frame-group indices a constructor invariant;
do not duplicate that immutable structural check during composition.
#168 makes every settled frame group's immutable indices/timestamps, and their
exact equality with retained frames, constructor invariants. Reuse the one
internal identity reader; do not duplicate its metadata schema or add a public
identity abstraction.
#173 requires deterministic image-provider configuration errors to be rejected
before combined-video media output. The two video entries explicitly require an
injected provider's callable `recognize_images`; generic image execution keeps
its pass-local recheck and evidence. Reuse the one local vision-config validator;
do not turn dynamic catalogs into preflight network calls or add a provider base.
#174 applies that same deterministic preflight to the independently public
`recognize_video_frames()` entry before retained-JPEG validation. Do not change
generic batch settlement or add another frame-batch abstraction.
#177 proves the real combined-video path across the default eight-image group
boundary with ordered 8+2 image calls and one separate audio call. Preserve
that integration without turning the fixture into a stress test or live gate.
#178 keeps maintained cold-start docs aligned with shipped A2a long-MP3 support
and the closed #120 no-repair decision. Do not reopen legacy Markdown repair or
describe all Stage A2 work as unstarted.
#179 distinguishes the provider-free `video` extra from the complete Google
combined-video profile, which also needs `image`, `audio`, and `google`. Keep
those dependencies optional instead of widening the `video` extra.
#180 proves that a later image-group failure preserves earlier paid frame work
and the separately settled audio branch, while undispatched suffix groups stay
typed cancellations. Keep their provider-call evidence unknown; do not invent
zero calls, retries, model switching, or a cross-branch transaction.
#181 proves real combined-video composition keeps native Google image and audio
token usage separate by explicit model. Preserve #086: public injected providers
return Markdown strings and do not gain the internal structured response type.
#182 proves a later native image-group failure preserves already-settled image
and audio model usage, cleans request snapshots, and leaves cancelled suffix
call evidence unknown. Do not replace that unknown with inferred zero calls.
#183 requires VFR-safe parsing: use container duration, seek the five-second
presentation timeline, and retain decoded frame PTS. Preserve the exact final
frame and candidate cap; do not add ffprobe or weaken #211 source stability.
#184 proves the pinned OpenCV backend applies MP4 display rotation consistently
to inspection, comparison, and retained JPEGs. Keep the real-container test;
do not add manual rotation or a public orientation setting without a reproduced
backend inconsistency.
#185 requires sampled color-only scene changes to survive comparison. Preserve
the detailed luminance thumbnail plus the small color thumbnail; do not replace
them with full-size BGR candidates or add a second detector/public color tuning.
#186 live-proves one image and one audio dispatch after that change, with both
returning honest `PROVIDER_RESPONSE_INVALID`. Do not rerun to seek green; the
redacted runner may report only validated exact-model usage after composition.
#187 preserves branch independence for local audio corruption: valid frames may
still dispatch, audio dispatch stays zero, and the result remains partial. Do
not add a whole-video transaction or rejection policy without maintainer choice.
#199 proves ordinary retained-JPEG publication failure releases every OpenCV
capture, removes request-owned staging, publishes no target, and leaves the
source immediately removable. A fault injected after successful directory
rename can still propagate cancellation while leaving the completed target;
that rare commit-point contract belongs to open #127. Do not freeze or “repair”
it with speculative deletion before the maintainer chooses cancellation policy.
#200 confirms the video output contract does not provide arbitrary Windows
extended-path support. A caller-selected deep parent may fail with typed
`OUTPUT_PATH_INVALID` and no residue when the host disables long paths. Keep
source-stem capping, but do not add registry checks, `\\?\` rewriting, or probe
directories merely to reject the path before provider-free scanning.
#201 confirms that silent video does not make the combined facade's required
audio `Config` optional. Both configs remain deterministic zero-I/O preflight;
only a validly configured call can later settle missing audio as frame-only.
Do not add content-dependent config validation or a second frame-only mode to
`recognize_video()`; use the existing frame extraction/recognition functions.
#202 proves the existing accumulated-drift path retains one sampled transient
high-contrast text line affecting about 2.29% of its thumbnail. Do not lower
thresholds, import legacy refine/pHash machinery, or freeze another large
fixture from that positive probe. Changes below the effective threshold remain
an honest quality limit until balanced positive and nuisance-motion evidence
exists.
#203 live-proves that exact transient-text shape through one current Google
image call: retained 0/5/19, both distinctive tokens recognized, silent audio
zero-call, complete composition, and no residue. Do not rerun for green or add
a content-exposing live harness; future live work needs a new runtime reason.
#204 balances the small-text proof with real nuisance motion: 61 five-second
candidates containing an alternating cursor calibrated to six frames, and the
published JPEGs still represented both major slide states. Preserve this
evidence boundary; do not add cursor/subtitle classification or retune from one
fixture without a reproduced failure.
#205 makes the maintained Google combined-video gate accept explicit image and
audio models instead of pretending both branches must share one model. Keep
catalog discovery single and live, validate each result against its own model,
and allow composition to aggregate equal names or retain distinct names. Do not
restore a shared-model compatibility flag or infer audio capability from catalog
membership.
#206 live-proves that split with one call per branch: an exploratory
`gemini-2.5-pro` image failure did not erase the separately successful
`gemini-2.5-flash` audio result or its token usage, and composition stayed
partial. Treat `PROVIDER_UNAVAILABLE` as this one observation; do not add retry,
fallback, or a capability allowlist from it.
#207 proves the same all-image-failed/audio-success shape remains honest through
`publish_video_result()`: publish partial Markdown with the stable frame error,
successful audio body/usage, and both retained assets. Keep later undispatched
frame groups as `Cancelled`; do not invent provider failures or add a generic
partial-result graph.
#209 makes the standalone Google Files long-MP3 route reject a mathematically
impossible selected-model request before upload when audio alone, at the
documented 32 tokens per second, meets or exceeds that catalog row's advertised
input limit. Missing optional metadata preserves the existing provider path;
malformed present metadata is a typed provider-response failure. Do not add a
model table, guessed prompt reserve, extra catalog/model/token request, cache, or
automatic chunking, and do not claim every smaller audio-plus-prompt request fits.
#210 live-confirms the exact #209 seam: one current catalog-only operation found
50 models and a present positive-integer input limit on `gemini-2.5-flash`, then
closed the client. No Files, generation, token-count, model-get, retry, or
fallback call occurred. Treat the count as dated evidence, not a hardcoded
catalog or proof that catalog membership implies audio support.
#216 requires Google Files remote-delete process control to preserve the exact
`KeyboardInterrupt`/`SystemExit` while still attempting client close and local
snapshot cleanup. Keep the nested provider-specific `try/finally`; do not map
the signal, add retry, or create a general lifecycle manager.
#217 confirms combined video already keeps image and audio ownership in two
independently snapshotted `Config` values. Do not replace them with a shared
video config, provider superclass, routing registry, or legacy format adapter
without a new concrete consumer and maintainer decision.
#218 binds only the two thin video facade functions at package initialization.
Keep their runtime imports inside the same-named function modules so plain
`import ocrllm` continues to defer recognition execution, media backends, and
providers. #219 requires their pure-Python public annotation types at module
scope so ordinary `typing.get_type_hints()` remains exact.
Do not replace this bounded fix with a callable module, package proxy, or import
hook, and do not use it to change the frozen worker collision.
#220 extends that exact rule only to `compose_video_result` and
`publish_video_result`: keep their public types at module scope, execution
imports inside the functions/helpers, and both root callables bound at package
initialization. Do not generalize without another proven collision.
#221 proves that all four functions and their runtime annotations survive a
clean installed wheel in both root-first and explicit-submodule-first orders.
Do not add another build harness or repeat that gate unless package layout,
facade initialization, or their import boundary changes.
#222 confirms that sub-five-second videos already use the same five-second grid
plus exact final frame: stable clips retain the final representative and a
changed ending retains both sides. An interior-only transient remains the
documented fine-gap limit. Do not add a short-clip cadence, midpoint scan, or
legacy refine/pHash machinery without a separate product decision and balanced
quality evidence.
#223 confirms `inspect_video`, `extract_video_frames`, and
`extract_video_audio` stay lazy, callable, identity-stable, and runtime-typed
through their nested `ocrllm.video.*` implementation modules. Do not eagerly
bind or split them: unlike the four root-level same-named modules, nested video
modules cannot overwrite these root package attributes.
#224 requires standalone `extract_video_audio()` to inspect, probe, extract,
and validate one request-owned source snapshot rather than reopening the
caller's mutable MP4. Combined `recognize_video()` must pass its existing #211
snapshot to the narrow stable-source helper, not create a second whole-video
copy. Preserve cleanup on every exit without adding a generic media cache,
public temporary-path option, or new cancellation semantics.
#225 live-proves the post-#224 combined path with one image request and one
audio request through two independent Google configs, complete composition,
and clean request-owned media. Treat this as current service evidence, not
authority for retry, model switching, a provider superclass, or repeated live
gates when the relevant runtime boundary has not changed.
#227 requires standalone `inspect_video()` to reject an ordinary caller-path
change between its OpenCV metadata read and container-duration read. Preserve
the pre/post validated identity check and typed `SOURCE_INVALID`, but do not
turn this no-output API into a whole-video snapshot, content-hash system, or
adversarial integrity claim. Container duration remains required for VFR.
#228 proves #227 from a clean installed wheel with real MP4 overwrite evidence
and unchanged lazy imports. Do not repeat that package proof or add another
build harness unless the relevant inspector, manifest, dependency, or import
boundary changes again. The adjacent 108-test audit found no reason for another
video filesystem defense pass.
#229 keeps `VideoRecognitionOutcome` imported once at module scope in
`recognize_video.py`; that binding serves runtime type hints and construction.
Do not restore a duplicate function-local import, and do not use this one-line
cleanup to remove annotation types, static exports, or genuinely deferred
execution imports.
#230 binds only the lightweight `recognize_long_mp3` facade at package
initialization so importing its same-named submodule cannot replace the root
callable. Keep the processor, decoder, Google SDK, and Files lifecycle lazy;
do not generalize this proven collision into eager recognition imports or
package import machinery.
#231 proves that facade plus all four bound video facades from a clean external
wheel in root-first and submodule-first orders, with runtime type hints and
lazy optional dependencies intact. Do not repeat the wheel gate unless facade
initialization, package layout, manifest, or this import boundary changes.
#232 binds the two primary `recognize` / `recognize_batch` facades after moving
batch preflight and execution helpers back to invocation time. Keep their root
callable identity and standard runtime type hints, but do not eagerly import
media/provider execution or restore the obsolete paired `__getattr__` branch.
#233 proves all seven currently bound recognition/video facades from a clean
external wheel of exact commit `79ad5d0`, in both ordinary import orders. The
installed package remains dependency-free and execution-lazy. Do not repeat
this gate until its named package boundary changes again.
#243 requires combined video to reject a cancellation object without callable
`is_set` before source/media work. Keep that structural check separate from
state observation: do not invoke the signal during preflight or use it to choose
#127's returned-versus-propagated cancellation behavior. Execution still owns
exceptions and strict-boolean validation from an actual `is_set()` call.
#244 requires the two public retained-video entries to accept only a nonempty
exact string or `Path` for `output_dir`, with typed rejection before source
access. Do not restore empty-string cwd fallback, accept arbitrary `PathLike`,
or grow this narrow coercion into a generic path framework or long-path policy.
#245 confirms long-MP3 results already fit the video outcome/composer. Do not
integrate them by catching short-route size failure, probing and then probing
again, documenting manual two-snapshot composition as the mature route, or
adding another video/result API. Resolve #127 first; then one retained-audio
ownership seam may select exactly one adapter. #152 still owns 9.5-to-10-hour
audio and persisted recovery.
#246 leaves the normal installed `[video]` gate open after one clean wheel build
and one ordinary pip attempt timed out downloading imageio-ffmpeg. Keep the
declared OpenCV/imageio-ffmpeg extra unchanged unless a package defect is
reproduced; do not vendor, repin, add another installer, or report installed
real-media proof before the normal installation and external MP4 calls pass.
#247 proves both ordinary partial-video directions through public consumers.
Keep successful frame work, retained JPEG/MP3 assets, typed audio failure, and
reliable call evidence when the short-audio branch fails. Do not add another
outcome type or use the standalone long-Files cleanup partial as evidence that
video long-audio routing already exists.
#248 requires native short audio to preserve a parsed transcript when only SDK
client close fails: return partial with one cleanup warning and explicit
`provider_client_closed=False`. Keep an earlier provider/parse error primary and
only annotate its cleanup failure. The native image adapter has the same proven
close-only response-loss shape; fix it separately rather than generalizing a
provider lifecycle framework.
#249 completes that separate native-image correction. Keep a parsed Google
image response as partial when only client close fails, with the same warning,
call/token evidence, and `provider_client_closed=False`; keep an earlier
provider/parse error primary. Preserve partial status through PDF and video
consumers. Do not use the shared internal cleanup bit to invent a public
provider response protocol, lifecycle superclass, transaction, retry, or
fallback layer.
#250 proves mixed successful video groups need no additional runtime state. A
partial frame result is still a successful usable `BatchItemOutcome`, while
the enclosing outcome/publication remains partial. Keep ordered bodies,
warnings, assets, calls, and token aggregation; do not add a partial outcome
variant, partial-group counter, nested branch ledger, or transaction layer.
#251 leaves the normal installed-video gate open after a single pip attempt did
not commit and its proof wrapper lost final process diagnostics. The exact
wheel manifest and metadata remain healthy, but do not claim installed runtime
proof or a dependency-specific failure. A future bounded gate must retain and
poll its original session; do not loop retries, repin, vendor, borrow another
environment, or add an installer abstraction.
#252 proves #249's cleanup-partial image result through public 16-page PDF
publication and ordinary resume. Keep the two ordered eight-page child states
authoritative: final status/warning remain partial and resume makes zero provider
calls. Do not aggregate provider cleanup/model-attempt ledgers at PDF level or
add legacy repair/replay machinery; the existing child sidecars are sufficient.
#253 leaves the normal installed-video gate open after its one retained-session
pip attempt failed with a remote proxy connection reset while fetching the
declared imageio-ffmpeg wheel. The exact package artifact and metadata remain
healthy and no partial install occurred. Do not retry-loop, repin, vendor,
borrow a source environment, or claim installed real-media proof from this run.
#254 proves the fixed 600-second video-audio FFmpeg bound is not presently a
duration-scaling defect: public extraction plus complete validation of a valid
ten-hour MP4 took 54.886 seconds and cleaned its large temporary root. Keep the
fixed bound and typed cleanup behavior; do not add dynamic/configurable timeout
policy without a real timed-out extraction. This does not authorize long-audio
video routing, #127, or #152.
#255 proves long-MP3 preflight memory stays flat through the real 9.5-hour A2a
ceiling: fixed-chunk snapshot copying and 4,096-frame miniaudio streaming peak
near 35.4 MiB for 301-second, one-hour, and 9.5-hour files. Keep full streaming
decode and metadata/frame-count validation; do not replace them with metadata-
only probing, another decoder, or generic streaming machinery. The 2 GB bound,
Files lifecycle, video routing, #127, and #152 remain unchanged.
#256 records one bounded real one-hour Google Files failure and fixes only the
diagnostics it exposed. On provider failure after resource creation, preserve
safe positive `remote_file_deleted` and `provider_client_closed` evidence, and
let the live runner fill a missing scope from the stable provider disposition.
Do not repeat a failed live call to force success or infer retry, fallback,
model switching, chunking, #127, or #152 policy from it. Later stress tests must
remain question-driven, capped, cleanup-verified, and separate from basic-flow
gates.
#257 makes wheel file selection explicit across supported Hatchling behavior:
`src/ocrllm/AGENTS.md` stays tracked for maintainers but must not ship as
`ocrllm/AGENTS.md`. Keep the clean gate's actual zip-member assertion. Do not
exclude the active package README, pin a backend solely to hide metadata-byte
variation, or add a general manifest framework without another concrete file-
selection defect. The ordinary installed-video dependency gate remains open.
#259 requires every optional-profile pip install in the maintained clean gate
to use its existing bounded process-tree controller. Keep the validated
caller-visible overall timeout, zero pip retries, 30-second connection timeout,
and success/nonzero/timeout regressions. Do not add a second installer, retry
loop, mirror, cache manager, or dependency pin to make delivery look green; the
ordinary installed-video dependency gate remains open until a real install and
external media proof complete.
#260 records one such attempt that found no miniaudio candidate even though the
official index exposes a matching 1.71 CPython 3.10 Windows x64 wheel. Treat it
as incomplete delivery diagnostics, not a reason to repin, remove the audio
extra, bootstrap a newer pip, inject a cache, or retry immediately. A future
single attempt must capture interpreter/platform, safe effective index settings,
candidate-resolution diagnostics, and the original process through terminal
exit before deciding whether a gate-only pip compatibility change is real.
#261 keeps bounded video robustness probing in the maintained runner rather
than the public API. Require a declared expectation of one or two image groups
and run provider-free retained-frame preflight before catalog/provider access;
do not add a public planner, source-hash transaction, or generalized stress
framework. A later batch suffix cancelled because an earlier group failed is
undispatched and deliberately carries no provider-call evidence. Preserve that
exact-or-unknown contract instead of rewriting the suffix as a confirmed zero.
#262 allows that runner to retain only the fixed safe response reasons `empty`,
`invalid_encoding`, `missing_text`, `invalid_no_speech_marker`, and `refusal`.
Do not pass arbitrary `details["reason"]`, raw responses, exception text, source
paths, or recognition content through a live report. `missing_text` means only
that no text could be extracted; do not split SDK getter/candidate-shape failures
into a diagnostic state machine. Legacy empty-response retry/model switching is
application policy and must not be inferred from these reasons.
#263 proves that delegating download polling is insufficient unless the original
child has an explicit overall deadline before launch. Keep the existing bounded
process controller for maintained installs, and require one-off operators to do
the same. A child still running when its operator returns is incomplete evidence,
not a terminal install failure. Terminate only the exact owned process tree,
verify no partial commit, and remove the exact owned root before reporting.
#264 assigns the ordinary combined install proof to the existing clean gate.
Keep `video,audio,image` as an exact profile assembled from the three declared
extras, with the same bounded installer and one installed public video
recognition/composition/publication proof. Keep `[video]` provider-free. Do not
create a combined extra, second installer, smoke DSL, Google dependency, live
provider call, provider hierarchy, retry, or fallback merely for packaging.
The credential-free deterministic audio seam must still exercise real MP3
snapshot/probe cleanup, while the injected image seam must receive valid
ordered JPEG snapshots. The gate remains open until this profile actually runs
to terminal exit. Later stress testing is permitted only as a separate,
question-driven, capped run after the basic installed flow is established.
#265 records one maintained-gate run that stopped before tests when uv timed
out downloading/extracting OpenCV under its reported 30-second HTTP timeout.
Keep this as external delivery evidence only. Do not raise `UV_HTTP_TIMEOUT`,
change the index/mirror, inject cache, repin, retry automatically, or split out
another dependency-preparation workflow from one event. The combined gate is
still open; a later atomic iteration may make one ordinary bounded attempt.
#274 keeps that gate as one `uv run --isolated --with` process under the same
1,200-second total stage bound, but replaces quiet pytest output with `-ra` so
the session header positively distinguishes environment preparation from test
execution. Do not split it into a named venv and two independently bounded
stages, add a shared-deadline controller, or change dependency/network policy
without new terminal evidence. The installed combined-video gate remains open.
#266 proves the public video facade's legacy Windows long-path failure boundary.
Keep source-stem normalization distinct from total-path capability. If creating
the request-owned snapshot fails, propagate its typed output error before image
or audio dispatch and leave no final/staging video output. Do not force one
error code across later frame-staging failures, inspect the registry, prepend
extended-length prefixes, or add a general path-budget framework without a
separate product decision and real cross-stage evidence.
#272 preserves valid parsed DashScope image Markdown when only client close
fails. Return the existing internal structured response with
`client_closed=False`; the public image result stays partial with a
DashScope-specific warning and exact call evidence. A credential-pool lease is
successful and available because local cleanup is not provider failure. Keep a
primary provider error primary, annotated only with cleanup failure. Do not add
a public provider-response protocol, shared lifecycle superclass, retry,
fallback, or model switch. The separate implicit-default-model attempt-ledger
identity mismatch was closed by #273 at the candidate-ledger boundary. Record an
implicit built-in DashScope attempt under the pinned baseline model for success,
provider failure, and output failure, while leaving caller config, resume identity,
explicit candidates, injected providers, catalog checks, and configuration-error
redaction unchanged. Do not add an early normalization or shared identity layer.
#275 directly covers the implicit-default DashScope checkpoint-write failure:
after one paid draft, `OUTPUT_WRITE_FAILED` must retain the pinned baseline,
one attempted call, and the draft workflow pass while publishing no output,
state, or temporary file. Do not invent token evidence when the adapter reported
none, duplicate the same lifecycle fixture, or change runtime/checkpoint format
for this characterization.
#276 attempted one bounded Google image/audio refresh, but the delegated wrapper
did not retain exact exit or either runner's redacted terminal JSON. Treat the
whole attempt as invalid: runner invocation, provider calls, and outcomes are
unknown even though the owned temp root was cleaned and no secret pattern was
reported. A zero-network isolated probe still imported this workspace, so do
not infer a product/import defect or replay calls to force a result. A later
live run must capture workspace provenance, exact exit, and per-runner safe JSON
before it can count as evidence. Later stress robustness work remains separate,
bounded, question-driven, deadline-controlled, and cleanup-verified after the
corresponding basic installed/live flow is validly proven.
#277 makes the returned video outcome a public error boundary. Before
construction, clear traceback/cause/context links from its settled frame and
audio errors while retaining the same objects, typed details, retryability,
call evidence, sibling successes, and artifacts. Do not turn this into a broad
video exception wrapper: errors propagated instead of settled, and #127's
cancellation return-versus-raise choice, are unchanged.
#278 keeps audio call accounting simple: standalone short/long success uses its
existing exact `provider_call_count`, combined video reports
`current_run_provider_call_count`, and failures use `provider_calls_attempted`.
Do not duplicate the current-run field on a one-call audio result without a new
consumer. Optional token aggregation must ignore any row containing a negative
count; keep `None` as unknown, zero as valid, and sum valid counts per model.
#279 did not enter the maintained clean-package gate: a one-use delegated
wrapper lost quoting around the repository path before PowerShell `-File`, so
there was no archive, download, pytest, wheel, installed-video, or provider
execution. Do not infer a package defect or alter the gate/dependency policy
from that invalid evidence. No replay was made and its exact temporary wrapper
root was removed. The ordinary installed combined-video proof remains open;
later pressure robustness work still follows valid basic installed/live proof.
#280 preserves one-shot `hotwords` and `warnings` at the two existing result
boundaries. `RecognitionResult` and `ProcessorOutput` must snapshot each value
once, validate that snapshot, and store the same tuple; do not validate an
iterator and then consume it again. This does not relax or reinterpret
`recognize_batch()`'s separate exact top-level tuple contract, and it does not
justify a shared collection-normalization abstraction.
#281 validly refreshes the maintained short-audio Google path on exact commit
`2844513`: current catalog 37, `gemini-2.5-flash`, one call, usage 55/2, exit 0,
empty stderr, and no secret or current temp residue. The paired image child
started and ended, but a one-use wrapper mixed asynchronous stdout reading with
`ReadToEnd()` and lost its exit/JSON; image calls and outcome remain unknown.
Do not infer a product defect or replay it for a green result. A future bounded
image refresh must use one stdout-read mode and persist exact exit plus safe
JSON before cleanup.
#282 snapshots `response.candidates` once inside the shared Google text parser.
Safety-block inspection and candidate-part text fallback must read that same
tuple so a valid one-shot SDK iterable cannot become a false `missing_text`
failure. Keep missing/unreadable candidates on the existing safe failure path;
do not generalize this into an iterable framework or change the independent
exact top-level batch tuple contract.
#283 did not enter the maintained clean gate. The encoded child PowerShell was
created, but its default execution policy rejected the `.ps1` before any stage,
download, pytest, wheel, installed-video, credential, or provider action. The
wrapper retained empty stdout and the exact policy error but not numeric exit
or elapsed time, so this is invalid operator evidence and was not replayed.
This repeated a prerequisite already present in the working diary: new gate
children on this machine require process-only execution-policy bypass. A
future disposable child must carry that prerequisite and
persist exit/timing; do not modify machine/user policy, the gate, dependencies,
pins, index, mirror, cache, retry, or timeout settings. The ordinary installed
combined-video proof stays open. Later stress robustness tests remain separate,
capped gates after valid basic installed/live proof.
#284 carried the known launch prerequisites and entered the unchanged gate from
exact `6f3e8e4`, but its archive dependency/pytest process reached the maintained
1,200-second stage timeout before `test session starts`. Archive expansion and
uv download markers for imageio-ffmpeg, OpenCV, and NumPy appeared; pytest,
wheel, profiles, installed combined video, credentials, and provider calls did
not. Treat this as external delivery evidence only and do not change delivery
policy or immediately replay. The wrapper's null exit is a reproduced host
`Start-Process -PassThru` behavior: even a local `exit 7` child yields null after
WaitForExit/Refresh. Future fixed workflows requiring numeric exit should use
direct .NET Process APIs or a small explicit status channel, not a shared runner
framework or more refresh calls. All owned roots and processes were cleared.
#285 preserves already-settled video work when only final request-owned source-
snapshot cleanup fails. The deletion error must carry
`stage=video_snapshot_cleanup`; after a complete outcome exists,
`recognize_video()` returns it as partial with one exact
`snapshot_cleanup_error: OutputError`, cleared of internal exception links.
Composition/publication retain both branches, media, call/token evidence, add
`video_cleanup_error_code`, and emit one fixed warning. Earlier media/output or
provider errors still follow their existing paths. Do not replace this with a
generic lifecycle protocol, cleanup retry, public snapshot path, or by assigning
the cleanup error to an unrelated image/audio branch.
#286 closes #281's missing current Google image evidence from exact `074c287`:
the maintained runner discovered 37 models and completed one
`gemini-2.5-flash` request with one provider call, usage 595/414, exit 0,
empty stderr, no credential/source-path leak, and no owned residue. Direct .NET
Process APIs preserved the numeric exit without adding a controller to the
repository. Later pressure robustness work is permitted only as separate,
single-question, capped and cleanup-verified gates after the corresponding
basic live flow; do not add a generic load/provider framework.
#287 classifies the current bounded two-frame-group Google video failure. A
provider-free preflight retained ten frames as 8+2. In the sole live runner,
the first image group made one call and returned
`PROVIDER_RESPONSE_INVALID/missing_text`, the undispatched second group stayed
`CANCELLED` with unknown calls, and the pure-tone audio branch made one call and
returned `invalid_no_speech_marker`. The result was honestly failed with no
composition, assets, invented usage, leak, or residue. This grayscale/no-speech
fixture proves failure settlement, not content-bearing success and not #282
causality. Do not add retry/model switching or replay it to force green; a later
success-path stress question needs a separately authorized content-bearing
synthetic fixture.
#288 closes that separate success-path question with a deterministic
content-bearing fixture: ten visible-text frames formed ordered 8+2 groups,
authorized synthesized speech produced a valid MP3, and one current-catalog
runner completed exactly two image calls plus one independent audio call before
composing eleven assets. The safe terminal result exited 0 in 16.927 seconds
with verified 5,214/231 token usage, no retry/fallback/model switch, leak, or
residue. Treat this as a capped Google video proof only; it is not evidence for
long load, other providers, provider fallback, or long-audio behavior, and it
does not justify a generic stress/provider framework.
#289 makes one later unchanged clean-gate attempt from exact `f674dab`. The
pre-armed run exited 1 after 1,220,452.865 ms at the maintained 1,200-second
archive dependency/pytest stage while uv reported media dependency downloads;
pytest never emitted `test session starts`, so wheel, profiles, and installed
combined-video execution did not begin. Treat this only as external delivery
evidence. The ordinary installed proof remains open; do not immediately replay
or change dependencies, pins, index, mirror, cache, retries, timeouts, installer,
or product code from it.
#290 finds no unhandled production-observed Google error shape in the active
native image/short-audio/long-audio routes. Refusal, empty/no-speech, quota
versus rate-window, high-demand, unavailable, model, credential, permission,
and request failures remain typed and redacted. A code-only legacy 400/
`FAILED_PRECONDITION` payment example would currently be request-invalid rather
than account-suspended; do not add payment-text matching until real native SDK
evidence confirms that exact shape. No billing layer, retry/fallback, or provider
hierarchy follows from this frozen candidate.
#291 live-discovers 37 Google `generateContent` models and tests exactly one
officially documented capability mismatch: `gemma-4-26b-a4b-it` accepts text
and image, not audio. One locally preflighted 8.038141-second MP3 run terminates
as `PROVIDER_UNAVAILABLE/model/recognition` in 4.516 seconds, with empty stderr,
no retry/model switch/fallback, no leak, and no residue. Failed-run generation
call accounting is unknown because the safe runner does not expose the adapter's
attempt detail. The existing classification is correct, so do not add a model
capability registry, hardcoded catalog, broader marker, or probe loop.
Keep the result a lightweight Python
package; do not copy the legacy five-phase controller, GUI, social downloader,
second scene detector, or premature provider generalization.

`contracts/` and `worker/` are frozen. Do not change them.

## Keep

- A small public facade in `__init__.py`.
- Import-time dependencies minimal.
- Tests in the root `tests/` directory.
- File output optional.
- Provider behavior injected or isolated behind explicit adapters.

## Avoid

- Importing from `legacy_app` or uppercase `OCRLLM`.
- Pulling GUI, FastAPI, social downloader, browser automation, or heavy media
  packages during `import ocrllm`.
- Copying whole legacy modules into the new package.
- Exposing legacy processor classes as public API without a tested facade.
- Adding PyMuPDF or `fitz`; the gated PDF slice uses PDFium through
  `pypdfium2`.
- Adding HarmonyOS/ArkTS work or claims; that integration is deferred.
- Extending `contracts/` or `worker/`. Both are frozen until a consumer exists.
- Returning success for provider output that is empty, control-only, or
  refusal-shaped.
- Adding a code path that can block on an external party without a
  caller-visible bound.
- Adding automatic retry, model switch, key rotation, or provider fallback
  inside an adapter. Expose disposition; let the caller act.
- Trusting a capability claim in prose. Verify against code and tests;
  documentation in this repo is known to lag.

## When Porting Legacy Behavior

Port one vertical slice at a time:

1. Define the public behavior in root tests.
2. Extract only the needed logic.
3. Keep dependencies optional when they are not required for `import ocrllm`.
4. Update `MIGRATION_STATUS.md` if the active boundary changes.
5. Do not begin the next phase until the current GO gate passes.
