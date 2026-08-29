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
- The replacement does not include a `recognize_video` convenience wrapper.
  Callers compose the visible public steps themselves; recognition rules,
  cleanup ownership, and resume must not disappear inside another video
  black box. A later wrapper would require a separate maintainer decision and
  a concrete consumer, not merely the availability of the component steps.
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
- A single image, audio, PDF, or video file defaults beside that file.
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
second alias for the same value. `ProviderModel` is one data class whose presets
are instances; it is not one Python subclass or source file per vendor model.

Only fields consumed by the first real vertical slice may be added. The
expected set is:

- vendor and model identifier;
- an invocation boundary, still awaiting choice 8 in section 6; the
  recommended built-in route stores a controlled adapter identifier rather
  than a callable or executable pointer;
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
adapter, or arbitrary future-SDK options container is not approved. The
existing injected-provider protocol remains a separate Python extension and
test seam; it is not silently embedded in every provider-model value.

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
7. **Video composition and deletion.** Prove that a caller can compose the
   public image/audio steps on real video, then delete the frozen video
   recognition/journal chain. Do not replace it with another convenience
   wrapper. Repair is not a deletion gate.

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
5. **Default output filenames.** Recommended: use one derived-result suffix,
   `<source-identity>_ocrllm.md`, for a single media source, an image/audio
   folder batch, and video output. Directory placement is already fixed in
   section 2.2. Alternative: use distinct image/audio/video suffixes.
6. **Provider-derived audio default.** Recommended: take the minimum positive
   integer `default_audio_minutes` across all flattened candidate providers so
   slot identity is common across fallback and nested lanes. An explicit
   positive integer or `-1` whole-file request wins. Alternative: require an
   explicit interval whenever more than one provider is supplied.
7. **Retry rule meaning.** Recommended: every canonical-code rule contains
   only finite `extra_retries` and `wait_seconds`. Reporting is determined by
   the recognition outcome, not repeated in retry configuration. Exhaustion
   records the last failure and advances to the next provider. Keep `error` /
   `next` / `current` only if the maintainer assigns them distinct control
   behavior that is not already expressed by those fields.
8. **Built-in invocation boundary.** Recommended: a `ProviderModel` stores one
   controlled adapter ID; one explicit lazy resolver selects the known
   operation-specific adapter module. Keep the existing injected Python
   protocol separate. Alternative: store a callable/protocol adapter object
   inside every `ProviderModel`.
9. **Token persistence across failed work and resume.** Recommended: keep one
   current and one historical aggregate per exact `(vendor, model)`, each with
   exact call count and nullable input/output totals. Persist the aggregate
   already observed for a resumable job, including safely reported usage from
   attempts that did not settle a slot; never create a public per-attempt
   ledger. Alternative: persist successful-slot usage only and accept that
   paid failed attempts disappear after process loss or resume.

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

Therefore Route A is recommended as the smallest contract:

1. Rotate the flat candidate order to the lane's remembered successful start,
   attempt each candidate at most once, and stop immediately on the first valid
   recognition.
2. Return one ordinary `RecognitionResult`; keep `status="complete"` when the
   requested content is complete. Add one bounded human warning and an ordered
   `metadata["provider_failures"]` tuple for providers exhausted before success.
3. Each provider-failure record contains only vendor, model, stable canonical
   code, and secret-safe bounded description. The successful provider/model
   remains the result's normal provider metadata; no duplicate success record
   is needed in the failure tuple.
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

These two choices remain awaiting explicit maintainer confirmation; the audit
and recommendation do not authorize dispatcher implementation.

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

Route A is therefore recommended:

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

Choice 3 remains awaiting explicit maintainer confirmation. No preset,
constructor, discovery API, registry, or adapter change is authorized by this
audit.

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

Choice 4 remains awaiting explicit maintainer confirmation. This evidence does
not authorize a batchifier, fallback dispatcher, sidecar schema, or provider
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

Route A is recommended as the smallest future rule:

1. An explicit output Markdown path always wins. Default resolution runs only
   when the caller omits it.
2. Use `<normalized-source-identity>_ocrllm.md` for every default. A single
   image, audio file, PDF, or video uses its source stem. An image/audio folder
   batch uses the containing folder name. Placement remains exactly section
   2.2: beside a single source or video, and beside the batch folder.
3. Recognize, resume, and repair resolve that same path from the same explicit
   source identity. They do not scan directories, infer a common filename
   prefix, or choose a different existing file.
4. A new recognition refuses an existing target and duplicate/colliding
   targets are rejected during preflight before provider dispatch. There is no
   automatic numbering, timestamp, hash suffix, overwrite-by-default, or
   persistent naming registry. An unusual same-stem image/audio collision is
   resolved by an explicit output path rather than another default branch.
5. The video composition entry passes one explicit combined target to its
   image/audio result composition. Branches do not independently derive or
   race for two default Markdown files. Whether two separate manual calls may
   intentionally merge into one explicit file is a later composition contract,
   not a reason to expand naming.

Route B uses media-specific `_image.md`, `_audio.md`, and `_video.md` suffixes.
It avoids one rare cross-media same-stem collision, but duplicates media type in
the naming contract and makes a combined video result arbitrarily belong to one
branch or require another special case. The fixed `_ocrllm.md` suffix already
marks a derived artifact; strict collision refusal plus explicit paths is
enough.

Keep the existing narrow path-component normalization because Windows path
length caused a real legacy failure. Do not turn it into auto-shortening based
on directory contents, a collision allocator, cross-process lock, or output
transaction framework. The current in-process target claim is implementation
evidence for rejecting simultaneous ownership, not permission to generalize it.

Choice 5 remains awaiting explicit maintainer confirmation. This evidence does
not authorize output-routing, resume, repair, video composition, or runtime
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
`split_audio` may derive one from provider input. The global minimum may create
more calls than a larger provider needs, but it adds no alternate identity or
scheduler.

Do not add adaptive shortening, binary-search re-splitting, provider-specific
window queues, automatic whole-to-interval fallback, or a second public
sentinel. The current public long-audio API still rejects `-1`; accepting and
normalizing it belongs to the future replacement entry and is not a defect in
the shipped API during the implementation pause.

Choice 6 remains awaiting explicit maintainer confirmation. This evidence does
not authorize `split_audio`, provider defaults, audio batching, fallback,
sidecar changes, or runtime implementation.

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

The proposed `error`, `next`, and `current` labels do not currently describe
three transitions: every example performs finite same-candidate retries and
then advances. Retaining them would duplicate retry count, exhaustion, and
outcome-reporting semantics. Route B keeps an action label or adds independent
`retry_current`, `advance_candidate`, and reporting controls. It is justified
only if a concrete provider error must terminate a lane or remain on one
candidate after its finite retries; no supplied example or current consumer
requires that branch.

Choice 7 remains awaiting explicit maintainer confirmation. This evidence does
not authorize a retry engine, provider dispatcher, new error mapping, retry
hint parser, preset, or runtime change.

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

Route A is recommended because it preserves extensibility by adding one honest
transport adapter in code, not by pretending arbitrary execution is data. It
also remains compatible with a future Python backend called by Electron: the
front end sends ordinary data, while only the backend resolves and executes
the adapter. Choice 8 remains awaiting explicit maintainer confirmation. No
`ProviderModel`, resolver, registry, credential type, adapter, or public batch
API is authorized by this evidence.

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

Route A keeps one bounded aggregate per exact `(vendor, model)` with four facts:
exact dispatched call count, nullable input tokens, nullable output tokens, and
whether it belongs to the current invocation or restored history. Each adapter
contributes usage once at its response boundary. A response-validation failure
may contribute usage when the provider actually reported it; a call without
trustworthy usage keeps the token total unknown. A resumable job persists the
aggregate it has already observed, including failed paid attempts, so a later
resume does not erase them. Reused work enters historical totals and never
current call counts.

Route B persists only successful-slot usage. It is smaller, but loses reported
usage from failed attempts after process loss or resume. A per-attempt public
ledger would preserve more diagnostics but duplicates retry/error state and has
no current billing consumer. Route A is recommended because it preserves honest
totals without a telemetry framework. Choice 9 remains awaiting explicit
maintainer confirmation. No token schema, provider model, dispatcher, state,
runtime, test, or public API changed in this documentation audit.

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
