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
#149 keeps request-owned video source snapshot placement open, and #152 keeps
long-audio chunk scope open. Do not implement either until the maintainer chooses.
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
frame and candidate cap; do not add ffprobe or claim #149 source stability.
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
