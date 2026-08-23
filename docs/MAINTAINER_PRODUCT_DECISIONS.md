# Maintainer Product Decisions

This file records durable maintainer decisions that must survive context
compression and agent handoff. It is not a capability claim: code and tests
still decide what is implemented. When an older plan conflicts with a decision
below, agents must surface the conflict and update the active authority before
implementing the older plan.

## Planning and documentation

- Detailed planning documents are desirable. Their size is not itself
  over-design: recording alternatives, evidence, rejected paths, and later
  reversals helps future maintainers understand why the code exists.
- Every plan must say whether it is active, adopted, frozen, superseded, or
  historical. A detailed old plan must not silently become the current product
  contract.
- Work-diary entries should distinguish offline regression evidence, clean-wheel
  evidence, live-provider evidence, and capabilities that remain unproven in a
  real request.

## Removing configuration and dormant work

"Unused" must not mean only "no current code reference." A configuration field
may belong to frozen work, a paused feature, an older compatibility promise, or
a parallel development line.

Before removing a field or public option, verify and record all of the following:

1. current runtime code does not use it;
2. active or frozen plans do not reserve it for an approved capability;
3. legacy behavior does not require it at the relevant migration boundary;
4. no released external contract depends on it;
5. no parallel branch or handoff is implementing it; and
6. the diary states why removal is preferable to freezing, hiding, or deferring
   the field.

Settings that actively control behavior, such as real concurrency limits, batch
size, or provider request intervals, are not unused merely because their default
is often accepted.

## Batch input and output collisions

- The intended future `recognize_batch()` input contract is a finite
  `Sequence`, not an arbitrary lazy iterable. Whether runtime acceptance should
  be limited to concrete `list`/`tuple` remains an implementation decision.
- Validate the complete batch before provider dispatch. Reject invalid container
  shape, invalid members, and duplicate resolved output targets before spending
  provider calls.
- Preserve already completed paid outcomes when an execution-time item failure
  happens. Do not convert `KeyboardInterrupt`, `SystemExit`, or an unexpected
  programming error into a fabricated item-level source error.
- Normal product layout follows the legacy convention of creating a same-named
  folder beside the source. Cross-media name collisions are therefore unusual.
  Prefer simple duplicate rejection and normal active-call protection over a
  speculative cross-process transaction or locking system.
- Reassess the batch-lifetime output owner after the Sequence/preflight contract
  is implemented; do not retain it solely for compatibility with the old lazy
  iterable behavior.

## Provider usage accounting

- Keep accounting understandable. Accumulate provider-reported input and output
  tokens by the exact model that produced them, together with that model's call
  count.
- Never estimate missing token usage and never turn an unavailable usage value
  into zero. Google and other providers may omit usage on errors, empty replies,
  or interrupted requests.
- Candidate, draft, and review records may remain diagnostic facts, but must not
  grow into a second billing engine. Do not keep adding complex reconstruction
  logic to every rare error exit.
- Distinguish current-invocation usage from historical usage restored from a
  checkpoint.

## Live provider evidence

- A fully passing offline suite is a regression floor, not proof that the
  package works as a product. Real provider behavior, response shapes, current
  model availability, network failures, and resume behavior cannot all be
  inferred from code.
- Google image and audio APIs are authorized for bounded live robustness tests.
  Discover the current model catalog live; do not replace discovery with a
  hardcoded support list.
- Routine live verification should use at least one authorized image for an
  implemented image path and one authorized short audio sample for an
  implemented audio path. Provider, batch, checkpoint, or resume changes should
  exercise a small real batch or an interruption/resume flow rather than only a
  success request.
- Treat temporary overload, quota windows, API errors, empty replies,
  unsupported formats, and excessive image counts as useful robustness
  evidence. The library must return honest bounded errors and never a false
  success.
- Do not run long-lived stress tests by default. Use synthetic, committed, or
  explicitly authorized data and never publish credentials or private inputs.
- A live resume exercise should prove that completed checkpoint slots are not
  paid for again and only missing work is dispatched after `resume=True`.

## PDF verification scale

- PDF recognition is fundamentally an ordered image-recognition workflow. Reuse
  the image provider and recovery path instead of creating an unrelated PDF LLM
  protocol.
- Test size depends on the iteration objective. A normal live product exercise
  is currently understood as 7-8 batches with roughly 7-8 pages/images per
  provider request (about 49-64 pages total). This interpretation should be
  corrected if the maintainer intended a different count.
- A 600-700 page PDF is acceptable for an explicitly planned stress or endurance
  test, but is not required for every ordinary iteration.
- Google is the available free live API authority for this path. Lack of paid
  OpenAI or desktop access is not a reason to replace live PDF/image evidence
  with offline tests alone.

## Provider direction

- Do not remain indefinitely in "scope first" investigations. Once feasibility
  and boundaries are known, deliver a usable vertical slice and exercise it with
  real requests.
- Prioritize a native Google provider path and live model discovery.
- Also preserve an intentional OpenAI-compatible provider direction because
  later local models may expose that protocol. It may follow Google rather than
  block Google delivery.
- Existing provider paths are not removed merely because Google is prioritized.
  Keep provider-specific request and error behavior explicit; do not force
  different protocols through a misleading common implementation.
- This direction does not reactivate social-media downloading or recognition.

## Decisions still requiring exact implementation confirmation

- Should batch runtime inputs accept every finite `Sequence`, or only concrete
  `list` and `tuple` values?
- Confirm that ordinary PDF live verification means 7-8 batches of 7-8 pages,
  rather than 7-8 pages total.
- Choose the smallest explicit provider interface that supports native Google
  now and OpenAI-compatible/local endpoints later without hiding protocol-specific
  behavior.
