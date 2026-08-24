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
The next controlled one-group live fixture must use it. Final publication and
recovery come later and must be derived from real outcomes rather than copied
from legacy. #136's first post-runner attempt lost the external exec
session identifier after completion, so no provider result may be inferred; a
future delegated run must poll the exact yielded session and validate captured
safe JSON before cleanup. These are controller rules, not product features.
#137 followed that protocol and proved a one-call image success plus a one-call
audio `PROVIDER_QUOTA_EXHAUSTED`, with honest partial outcome/composition and
two retained assets. Treat this as expected non-retryable provider evidence;
do not add adapter retry, automatic model switching, or provider pooling.
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
