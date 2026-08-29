# Plan: Provider-Model And Media-Batch Refactor

Status: **approved product direction; runtime implementation remains paused
for the current decision map in section 0 and the #612 discussion checkpoint.** Existing
provider-free primitive maintenance remains allowed when real media exposes a
defect. This revision replaces the prematurely expanded
2026-08-28 module build specification. It is a decision record and sequencing
guide, not permission to build unused framework pieces.

Authority: the latest maintainer instructions and the corresponding current
working update in `docs/ACTIVE_STATE_AND_RULES.md` outrank this plan.

## 0. Current pruning checkpoint (2026-08-29, #601)

This plan remains a discussion record, not implementation authorization. The
latest maintainer proposal confirms the destination but does not make every
later pool/retry detail part of the first slice.

The next implementation, if separately authorized, remains only one vertical
proof: one immutable `ProviderModel` **instance** for one exact vendor/model,
one controlled `adapter_id`, the existing exact provider settings supplied at
the call boundary, and one real image consumer. Adding a model means adding or
constructing another value of the same type; it does not mean creating one
Python subclass/file per model. Adding a new transport family later means one
independently readable adapter, not conditionals spread through media code.

Do not make any of the following prerequisites for that proof:

- mirroring every Google or DashScope catalog row as a committed preset;
- flat fallback, nested provider lanes, lane parallelism, or an API pool;
- a retry executor or a pre-filled HTTP-status matrix;
- persistent token ledgers or per-attempt billing records;
- merged image/audio publication, resume, repair, or public facade rewrites;
- RapidOCR, VLLM, Ollama, Volcengine, or OpenAI-compatible placeholders.

After one provider-model/adapter boundary works live, ship only a small set of
live-proven preset instances. Live discovery plus explicit construction covers
other model IDs. A raw vendor HTTP code is first mapped by that vendor adapter
to one canonical OCRLLM error; only a later fallback slice may attach finite
retry values to that canonical code. A successful fallback returns bounded
earlier-provider failure evidence with the result; it does not raise a terminal
exception after producing a valid recognition. Terminal failure reports one
last safe failure for each unresolved batch.

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
2. Nested lanes need one scheduling rule. The current recommendation is fixed
   round-robin assignment with sequential work inside each lane and parallel
   progress between lanes, without a global epoch barrier or dynamic stealing.
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

Two public-contract details remain deliberately unsettled until their actual
slice begins:

1. how a caller selects plain-image OCR versus detail OCR; provider capability
   booleans can validate a selected task but do not themselves select it;
2. the exact input and return signature of the thin root `resume_video` route,
   including how it reports one branch succeeding while the other fails.

Neither ambiguity blocks the first single-provider image proof.

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

The exact plain-versus-detail task selector and the stateless `resume_video`
input/partial-result signature remain later slice-local API reviews. They do
not reopen its already fixed no-journal/no-composition/no-cleanup boundary and
do not block a private single-provider image proof.

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
- An image or audio batch defaults beside the directory containing the batch.
- If an omitted output cannot be resolved without guessing, for example a
  batch spanning unrelated directories, preflight rejects the call before any
  provider request.
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
  recognition would duplicate boundary speech. The smallest exact slice return
  shape is a later API decision; do not hide splitting inside recognition to
  avoid that decision.

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

Detail OCR implies plain OCR. A capability mismatch is an OCRLLM pre-dispatch
error, not a provider runtime error, and causes zero provider calls.

The value does not contain a generic call-parameter list or mapping. API keys,
credential pools, region/base URL, timeout, cancellation, prompt/media input,
Chat-versus-Responses selection, thinking/effort, high-resolution encoding,
catalog clients, upload handles, call/token counters, last-success state, and
provider errors belong to exact adapter settings, one call, or recognition run
state. The first vertical slice reuses its existing exact provider-settings
type rather than creating a second common settings object. An adapter-specific
option moves into durable model data only after two real presets prove that it
is part of model identity rather than call configuration.

No universal constructor default invents `1` image or `30` audio minutes for an
unsupported task. A live-proven audio-capable preset may begin with a 30-minute
suggestion, and a live-proven image preset carries its measured batch
suggestion. Maximum output tokens, concurrency, start interval, batch override,
audio split override, candidate order, lane memory, and token accounting stay
outside the provider-model value unless a later real adapter consumes a field
that cannot be represented honestly elsewhere.

Entities/presets do not contain API secrets. A generic executable registry,
plugin system, identity fingerprint, full model catalog, placeholder OpenAI
adapter, or arbitrary future-SDK options container is not approved. The
existing injected-provider protocol remains a separate Python extension and
test seam; it is not silently embedded in every provider-model value.

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
repr, persistence, or committed presets. A non-secret endpoint or adapter
option enters a provider-model value only when a live adapter consumes it; the
first slice does not create a generic `list` of hypothetical call parameters.

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
rejected. Retry rules contain only non-negative `extra_retries` and
`wait_seconds`. The initially proposed `error` / `next` / `current` labels are
removed because all three examples retry the current provider finitely and then
advance. Final outcome severity is not a retry-rule field.

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

### 5.1 Proposed first phase entry awaiting authorization (#597/#607)

The transport order is evidence-selected, but implementation remains paused
until #607's schema-timing conflict and any other decision actually consumed by
the selected first preset are resolved or explicitly deferred. #597 audited the
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
   attempts as well as settled slots and is updated before another provider
   attempt begins. At invocation start, the loaded cumulative value is the
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
dimension unknown rather than zero. Updated cumulative evidence is saved before
another provider attempt, so a process loss does not erase a paid failed call.

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
paths would be incomplete because recognition also needs logical versus actual
time ranges. The public slice record/return shape remains a later API gate. It
must be decided before implementing `split_audio`, but does not justify a
generic media-plan type or hidden recognition-owned splitting.

The latest `float` wording remains a direct unresolved conflict. Current
validation, window construction, state and resume identity all require exact
positive integer minutes, and fractional minutes would add rounding and durable
identity rules. `ProviderModel.default_audio_minutes` therefore remains
`int | None` unless the maintainer explicitly reverses the integer-only
decision. No runtime or public API is authorized by this clarification.
