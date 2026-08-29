# Plan: Provider-Model And Media-Batch Refactor

Status: **approved product direction; provider/entity and replacement-recognition
implementation paused for the open decisions in section 6.** Existing
provider-free primitive maintenance remains allowed when real media exposes a
defect. This revision replaces the prematurely expanded
2026-08-28 module build specification. It is a decision record and sequencing
guide, not permission to build unused framework pieces.

Authority: the latest maintainer instructions and the corresponding current
working update in `docs/ACTIVE_STATE_AND_RULES.md` outrank this plan.

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

## 2. Decisions Already Fixed

### 2.1 Media pipeline

The intended public composition is:

```text
inspect_video
  -> extract_video_frames
  -> dedupe_video_frames
  -> batchify_images
  -> recognize_images_to_markdown

extract_video_audio
  -> split_audio
  -> recognize_audio_to_markdown
```

- These steps remain directly callable. Recognition must not hide them inside
  one required black-box function.
- A future `recognize_video` convenience wrapper is allowed only after the
  public steps work together. It must be a thin caller of those steps and must
  not own recognition rules, a result type, a journal, or another resume
  format.
- Image and audio providers are separate inputs.
- Video resume routes to image-batch and audio-batch resume. There is no third
  video resume engine.
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
- A single image or audio file defaults beside that file.
- An image or audio batch defaults beside the directory containing the batch.
- If an omitted output cannot be resolved without guessing, for example a
  batch spanning unrelated directories, preflight rejects the call before any
  provider request.
- Image and audio batches write ordered slots into one Markdown file. They do
  not publish one Markdown file per item.
- Output naming is still open in section 6; code must not infer a naming
  convention before it is settled.

### 2.3 Batch boundaries

- Manual batching stays provider-free:
  `batchify_images(paths, batch_size=<positive int>)` requires an explicit
  size.
- A merged recognition facade may also accept unbatched paths. When its
  `batch_size` is omitted, it resolves one default from the supplied provider
  models before dispatch.
- Already-batched input is never re-chunked during provider fallback. Slot
  identity and resume ordering stay stable.
- Media batch containers follow the active library's strict concrete-tuple
  approach. Generators, custom iterables, and compatibility wrappers are not a
  product requirement.
- All sources, members, output targets, and collisions are validated before
  the first provider call.

### 2.4 Audio splitting

- `split_audio` accepts either an explicit integer-minute interval or provider
  input; at least one is required.
- An explicit interval wins when both are present.
- `-1` means no split. It is a call argument only, never a provider default.
- Provider default audio duration is a positive integer number of minutes,
  initially normally 30 and later adjusted only from real context, stability,
  and hard-limit evidence.
- The existing private ten-hour product ceiling remains unless a later
  evidence-backed decision changes it. Individual providers may reject a
  shorter duration; that remains a provider failure, not a reason to guess a
  new chunk plan during recognition.

### 2.5 Provider-model value

One value represents exactly one `(vendor, model)` pair. Google or DashScope
as a whole is not one provider value. The public type is named `ProviderModel`:
it states the actual identity more clearly than `ProviderEntity`. Do not ship a
second alias for the same value.

Only fields consumed by the first real vertical slice may be added. The
expected set is:

- vendor and model identifier;
- adapter identifier (data, not a callable or executable pointer);
- plain-image OCR support;
- detail-image OCR support, including LaTeX/code-oriented output;
- audio-input recognition support;
- positive integer default image batch size;
- positive integer default audio minutes;
- optional maximum output tokens, only when the adapter consumes it;
- evidence-backed retry rules;
- only the concrete call options used by that adapter.

Detail OCR implies plain OCR. A capability mismatch is an OCRLLM pre-dispatch
error, not a provider runtime error, and causes zero provider calls.

Entities/presets do not contain API secrets. A generic executable registry,
plugin system, identity fingerprint, full model catalog, placeholder OpenAI
adapter, or arbitrary future-SDK options container is not approved.

Credentials are supplied at call/runtime boundaries and never included in
repr, persistence, or committed presets. A non-secret endpoint or adapter
option enters a provider-model value only when a live adapter consumes it; the
first slice does not create a generic `list` of hypothetical call parameters.

Preset scope remains an explicit section 6 choice. Until it is answered, no
full static model catalog is approved. The recommended route is a small set of
live-proven presets plus live discovery or explicit construction for other
model IDs; OCRLLM should not indefinitely maintain every model exposed by a
vendor catalog.

Google initially keeps the same access method already used successfully by the
active/legacy evidence selected by the authority. DashScope initially keeps
its proven transport. SDK or transport replacement requires a separate real
failure and decision.

### 2.6 Provider input shapes

Recognition and provider-derived audio splitting accept exactly three shapes:

```text
one provider-model
flat list[provider-model]
nested list[list[provider-model]]
```

- A flat list is one ordered fallback lane.
- A nested list is a fixed set of independent lanes. Batches are assigned by a
  simple round-robin rule (`batch_index % lane_count`); no batch uses a
  provider outside its assigned lane.
- A lane remembers its last successful provider as the next batch's starting
  point. With no prior success it starts at the first provider.
- A failed batch does not stop later batches. Final reporting records failed
  batch range, last provider, canonical error code, and bounded description.
- The final failed-batch accumulator keeps exactly that terminal failure for
  each failed batch. It does not retain one overflow record per provider. The
  separate question of earlier-provider warnings on a batch that eventually
  succeeds remains open in section 6.
- No dynamic rebalancing, cross-lane rescue, arbitrary iterable support, or
  second pool abstraction is planned.

The exact success-stop contract remains open in section 6 and must be settled
before a dispatcher is implemented.

### 2.7 Retry and error evidence

Vendor adapters first map raw SDK/HTTP failures to existing canonical OCRLLM
provider errors. Public retry rules are keyed by canonical codes, not by a raw
HTTP number shared across vendors.

Every retry count is finite. `-1` or any other infinite-wait spelling is
rejected. The initially proposed `error` / `next` / `current` labels overlap:
all three examples retry the current provider and eventually advance. Their
meaning must be simplified or clarified before code is written.

Do not pre-fill Google and DashScope with identical guessed policies. Start
from the real mappings and errors already observed in the active and legacy
paths, then add only rules required by an end-to-end call. Do not invent
unproven maximums such as 32 retries or 600 seconds.

### 2.8 Token accounting

- Accumulate provider-reported input and output tokens by exact vendor/model.
- Current-run totals include any usage a provider reports for successful or
  failed calls. Persist successful-slot usage only, so resume can derive paid
  settled totals without counting a reused slot as a new call.
- Never invent usage when a provider does not report it and never divide one
  batch's usage across its individual images.
- More detailed accounting waits for a real consumer or billing defect.

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
- Media created by a future video convenience wrapper is deleted after full
  success and retained after partial or total failure so resume remains
  possible.
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
- the current `recognize_video` implementation; that public name may return
  later only as the thin convenience caller allowed by section 2.1;
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

No provider/entity or replacement-recognition phase starts until section 6 is
resolved and recorded. This pause does not prohibit fixing a defect reproduced
in the already-shipped provider-free inspect/extract/selection functions.

1. **One provider-model vertical slice.** Add the smallest provider-model value
   and direct adapter consumer together; predefine one suitable model already
   shown by current catalog/legacy evidence; complete one real image batch.
   There is no registry, pool, retry engine, or public facade yet.
2. **Second transport proof.** Add one model using the other already-working
   Google/DashScope transport. Change the data boundary only where the second
   real consumer proves it necessary.
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
7. **Video composition and deletion.** Prove the public image/audio steps can
   be composed on real video. Add a thin convenience wrapper only if still
   useful, then delete the frozen video recognition/journal chain. Repair is
   not a deletion gate.

Each phase must contain a real consumer, the smallest focused offline tests,
and a bounded live call where provider behavior is in scope. A green offline
suite alone does not prove a provider phase.

## 6. Maintainer Decisions Still Required

Implementation remains paused until these choices are explicit:

1. **Flat-list traversal after success.** Recommended interpretation: visit
   each provider at most once per batch, but stop immediately on first success.
   Alternative: continue calling every provider even after success.
2. **Successful result with earlier provider failures.** Recommended:
   return the completed `RecognitionResult` with bounded provider-failure
   records; raise only for partial or total recognition failure. Alternative:
   raise after completion while attaching the successful result.
3. **Preset scope.** Recommended: a few live-proven presets plus explicit
   construction/live discovery for other model IDs. Alternative: commit every
   currently exposed Google/DashScope model as a preset.
4. **Default image batch size with multiple providers.** Recommended: resolve
   one common size as the minimum positive integer default across all flattened
   candidates so fallback and nested lanes keep one slot plan. Alternative:
   use the first provider's default or require an explicit size.
5. **Default output filenames.** Decide names for a single media source, an
   image/audio folder batch, and video output. Directory placement is already
   fixed in section 2.2.
6. **Provider-derived audio default.** Recommended: take the minimum positive
   integer `default_audio_minutes` across all flattened candidate providers so
   slot identity is common across fallback and nested lanes. Alternative:
   require an explicit interval whenever more than one provider is supplied.
7. **Retry rule meaning.** Recommended: every canonical-code rule contains
   only finite extra retries, wait seconds, and reporting severity; exhaustion
   always records the last failure and advances to the next provider. Keep
   `error` / `next` / `current` only if the maintainer assigns them distinct
   control behavior that is not already expressed by those fields.

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
- one real video whose extracted image and audio paths compose into the same
  output without the old journal;
- explicit-source and output-default behavior documented;
- owned files deleted on success and retained on failure;
- package import remains lightweight;
- old public consumers and tests are either migrated or deliberately removed;
- focused tests, full offline suite, and bounded live evidence are green.

Until that gate closes, the old video chain describes shipped behavior but is
frozen rather than a target for further fixes or features.

#570 already proves that the retained public inspection, full-frame extraction,
and audio extraction primitives work independently on one real archive video.
It does not satisfy the merged-Markdown or image/audio batch-resume gates and
therefore does not authorize early deletion.
