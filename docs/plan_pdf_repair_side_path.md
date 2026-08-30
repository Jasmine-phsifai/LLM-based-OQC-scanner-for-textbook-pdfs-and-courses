# PDF Repair Side-Path Decision Plan

Status: **the source-bound `.partial.md` proposal below is superseded; one PDF
composition decision remains before runtime repair work.**

## Current checkpoint (2026-08-30, #686)

The maintainer's later direction is narrower than the historical proposal in
this file. Experimental repair may trust that its explicit Markdown target is
an OCRLLM partial result for the explicit current source supplied by the caller.
It derives failed image source indexes or audio logical ranges from strict
library-written headings/comments, accepts the current provider and output
explicitly, and does not restore saved batch/interval/provider parameters.
Resume remains the primary recovery path.

Do not add a second source-bound partial-document schema, embedded PDF/source
digest, prompt/provider identity, parameter snapshot, repair sidecar, generic
Markdown parser, or legacy compatibility layer. Malformed, duplicate,
out-of-range, or absent current-library markers fail before dispatch. A result
with zero settled slots has no Markdown and is therefore not repairable after
its sidecar is lost; repair does not manufacture evidence that never existed.

Current merged-image partial Markdown already writes exact
`OCRLLM_FAILED_IMAGE_SLOT` comments with slot and source indexes. Current
merged-audio partial Markdown writes exact `OCRLLM_FAILED_AUDIO_SLOT` comments,
and the immediately adjacent library heading carries the three-decimal logical
second range. These are mechanically sufficient under the maintainer's explicit
trust boundary when the caller supplies the current image batches or audio
source. They are not promoted to resume-strength source identity.

The current PDF facade is the blocker for the original use case. It renders
groups of up to eight pages through the older `Config` image path, fails fast,
and publishes aggregate page-marked Markdown only after all groups return. It
cannot currently leave a failed-page marker for repair. A bounded privacy-safe
scan of the authorized `D:\archieve` tree found four Markdown files / 6,409
lines and no attributable OCRLLM or legacy failure marker, so there is no real
production artifact that resolves this API choice.

One maintainer choice remains:

1. **Visible PDF composition (recommended):** publish provider-free PDF page
   extraction, then let callers use existing `batchify_images()`, merged image
   recognize/resume, and the later image repair. Caller-owned extracted pages
   make source ownership explicit and avoid a second PDF state machine.
2. **One-call provider-model PDF facade:** add a new orchestration owner that
   renders pages, retains deterministic page files/state after partial failure,
   delegates to merged image recognition, and cleans owned pages only after
   completion. This is more convenient but must coexist with the shipped
   Config/injected-provider PDF path and therefore carries more lifecycle code.

Do not implement repair against the old fail-fast PDF path or add failure
publication to that path merely to create repair input. Image/audio repair may
remain independently useful, but whether PDF first becomes visibly composed or
gains a new one-call owner affects the real PDF repair entry and cleanup rules.

## Historical proposal (superseded by the checkpoint above)

Iteration #451 rechecked the decision chronology. The maintainer's earlier
"first A, second B" response belongs to the older video-cancellation and
long-audio decisions. It does not answer this later PDF-specific artifact
choice. The routes below therefore remain open until one is selected
explicitly for PDF repair.

### Historical problem

The active PDF facade is serial and fail-fast. It recognizes complete page
groups of at most eight, saves ordinary image sidecars, and publishes the
canonical Markdown only after every group succeeds. If a group fails, resume
is the primary recovery path and no partial Markdown is published.

The legacy application has a manual repair command, but it is not a safe input
contract for the library. It trusts a caller-selected PDF plus localized HTML
comments, carries no PDF identity, recognizes one page per request, and rewrites
the existing Markdown non-atomically. Its own partial-repair marker can contain
comma-separated page numbers that its parser cannot read again. The library
must not accept or reproduce that format.

## Product choice

### Route A — library-owned `.partial.md` repair input (recommended)

Keep the canonical `*_board.md` absent until the whole document is complete.
After at least one PDF group has settled and a later group fails, atomically
publish a separate deterministic `*_board.partial.md` artifact. It contains:

- a strict library-owned schema marker;
- the exact PDF SHA-256, byte size, and inspected page count;
- the existing ordered `ocrllm:pdf-pages start=N end=M` markers and Markdown
  only for groups that actually settled.

The repair operation validates the current PDF against that embedded identity,
validates that successful ranges are ordered, disjoint, and within the page
count, and computes missing pages as their complement. It does not trust error
text, infer source identity from filenames, or read image resume sidecars.

Repair uses the caller's current `Config`; it does not restore an old provider,
model, prompt, batch size, retry policy, or concurrency setting. Missing pages
are rendered from the complete PDF and dispatched serially in contiguous tuples
of at most eight. Each settled group updates the partial Markdown atomically.
When no pages remain, repair atomically publishes the canonical Markdown and
removes the partial artifact. Existing canonical output, source drift, malformed
markers, overlap, ranges outside the declared page count, or an unsupported
schema must be rejected before provider dispatch.

This is a separate public PDF operation. It does not widen `recognize_batch()`,
register a worker route, parse legacy Markdown, add retry/fallback, or create a
second binary/JSON checkpoint protocol. Resume remains the normal path; repair
exists only for a surviving partial document after its image sidecars are gone
or unusable.

The first implementation must be one complete provider-injected vertical
slice: a later-group failure publishes the partial artifact; deleting the image
sidecar directory still leaves enough source-bound information; repair sends
only the missing group, publishes the final Markdown, and removes the partial
artifact. A wrong PDF and a malformed partial artifact must both make zero
provider calls. Do not ship a parser or producer without its matching consumer.

### Route B — keep repair unavailable

Keep the current behavior unchanged. A failed PDF has no partial Markdown;
callers use `resume=True` while compatible image sidecars exist, or explicitly
start a fresh recognition after removing the abandoned output state. This is
the smallest surface and preserves all current output semantics, but it does
not satisfy manual recovery from Markdown after state loss.

## Rejected routes

- Accepting legacy Chinese failure comments or its sidecar formats.
- Publishing incomplete content at the canonical final `.md` path.
- Treating an arbitrary caller-supplied page tuple as equivalent to repair.
- Storing provider/model/prompt parameters in the repair artifact.
- Continuing to dispatch every suffix group after a provider outage merely to
  manufacture one failure marker per range.
- Adding parallel repair, automatic retry, model fallback, a transaction
  framework, cross-process locking, or worker registration in the first slice.

## Evidence from iteration #422

- Legacy normal PDF failure propagation: 12 provider-free tests passed, but no
  direct PDF-repair test exists.
- Active PDF/backend/batch audit: 53 provider-free tests passed.
- Main-agent active lifecycle targets: 3 tests passed.
- A direct legacy parser probe accepted `9-16`, but rejected both its own
  comma-separated partial marker and a multiline failure marker.
