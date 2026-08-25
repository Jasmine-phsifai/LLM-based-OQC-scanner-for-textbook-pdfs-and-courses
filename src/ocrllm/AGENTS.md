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
before combined-video media output. Reuse the one local vision-config validator;
do not turn dynamic catalogs into preflight network calls.
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
