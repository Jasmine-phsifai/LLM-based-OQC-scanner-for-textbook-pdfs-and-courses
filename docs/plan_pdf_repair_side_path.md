# PDF Repair Side-Path Decision Plan

Status: **product choice required; no runtime implementation is authorized.**

## Problem

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
