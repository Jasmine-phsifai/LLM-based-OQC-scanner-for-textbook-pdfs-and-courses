# Phase 2A Recognition Execution Policy

> **OBSOLETE (#071; see P1-b completion):** historical lazy/arbitrary-iterable
> batch statements below do not describe the current exact top-level tuple and
> full-preflight contract. See
> [`ACTIVE_STATE_AND_RULES.md`](ACTIVE_STATE_AND_RULES.md#p1-b--concrete-tuple-batch-contract-and-full-preflight).

Date: 2026-07-12.

Status: implemented and verified. Provider transport/model configuration is
next; credential pools and image resume remain later checkpoints.

## Outcome

`Config` now composes an exact immutable `RecognitionExecutionPolicy`:

```python
from ocrllm import Config, RecognitionExecutionPolicy

config = Config(
    execution=RecognitionExecutionPolicy(
        maximum_images_per_request=10,
        max_parallel_requests=4,
        provider_request_start_interval_seconds=0.5,
    )
)
```

The defaults preserve the earlier direct API: at most 10 images in one ordered
same-context request, one independent recognition job at a time, and no added
provider-start delay. The policy is orthogonal to the `board` profile and to
`image_mode`; it never classifies or routes handwriting separately.

## Decisions

### Per-request image limit

`maximum_images_per_request` is in `[1, 10]`. The upper bound shares one
constant with the existing decoded image-group safety validation. A caller may
lower it for a stricter workflow. An over-limit group raises
`InvalidSource(code="SOURCE_TOO_LARGE")` with the actual and configured counts
before file access, snapshot creation, optional-backend loading, or provider
dispatch.

This policy cap is not a substitute for provider/model capability metadata.
Every future built-in adapter must also enforce a stricter documented model
limit when one exists. The effective limit will be the minimum of the library
safety boundary, caller policy, and adapter/model capability; silently trying
an impossible upload is forbidden.

### Parallel recognition

`max_parallel_requests` is in `[1, 32]`. `recognize_batch()` keeps no more than
that many independent jobs submitted at once, so a large or lazy iterable is
not converted into an unbounded executor queue. Results remain in caller
order, even when jobs finish out of order. The default value `1` retains the
previous sequential, lazy, fail-fast behavior.

Parallel execution is explicit opt-in. An injected provider object used with a
value above one must make its own `recognize_images()` implementation
thread-safe. Local OCR may also be run in parallel, but callers own the memory
budget for multiple engine instances; the conservative default remains one.

### Provider request cadence

`provider_request_start_interval_seconds` is a finite value in `[0, 600]`.
The interval applies immediately before every provider method call, not merely
between executor submissions. One direct `recognize()` operation therefore
spaces its own draft, review, and scout dispatches. One `recognize_batch()`
operation shares the same monotonic gate across all concurrent workflows, so
their internal calls cannot bypass the configured cadence.

The gate serializes only request starts. It releases before waiting for the
provider response, so requests may remain concurrently in flight. Cancellation
is polled at most every 50 milliseconds while waiting. On the first parallel
batch failure, the gate aborts calls that have not started and queued futures
are cancelled; provider calls already in progress are allowed to finish.

Separately invoked `recognize()` calls own separate gates. Callers that start
multiple independent public operations themselves need a shared higher-level
scheduler or should use `recognize_batch()`.

## Files And Responsibilities

```text
src/ocrllm/recognition_execution_policy.py
    Validate the immutable public limits.
src/ocrllm/image_group_limits.py
    Hold the one shared hard image-group safety boundary.
src/ocrllm/validate_execution_image_count.py
    Reject configured over-limit groups before source/provider work.
src/ocrllm/providers/provider_request_start_gate.py
    Coordinate monotonic provider starts within one public operation.
src/ocrllm/recognize.py
    Apply image preflight and direct-operation provider cadence.
src/ocrllm/recognize_batch.py
    Bound independent jobs, preserve result order, and apply fail-fast cleanup.
tests/test_recognition_execution_policy.py
    Prove exact types, bounds, mutation revalidation, and pre-upload rejection.
tests/test_recognize_batch_execution.py
    Prove overlap bounds, result order, all-call cadence, and failure abort.
```

The scheduler and gate imports remain lazy. Plain `import ocrllm` exports the
small policy value but does not import `concurrent.futures` or the private gate.

## Failure Semantics

- Invalid policy field or mutated nested value: `CONFIG_INVALID`.
- Image group above caller policy or the hard safety cap: `SOURCE_TOO_LARGE`.
- Caller cancellation before or while awaiting a provider start: `CANCELLED`.
- First item failure in parallel mode: that original typed error is raised;
  not-yet-started provider work is aborted rather than spending more quota.
- `recognize_batch()` remains fail-fast. `continue_on_error` is not added in
  this checkpoint.

No retry, model fallback, provider switching, credential rotation, or resume
behavior is hidden in the execution policy.

## Verification

Behavior commit `12c221b` and lazy-import correction `40df1a9` are pushed.

- Focused execution/config/image tests: 165 passed before the import-only lazy
  correction; the exact correction retest passed 66 tests.
- Authoritative isolated suite with Pillow 12.3.0: 895 passed, 1 optional
  RapidOCR-profile test skipped.
- Phase 1 generated fixtures: byte-identical.
- Ruff over `src` and `tests`, `compileall`, and `git diff --check`: passed.
- The resident OCRLLM environment has Pillow 12.1.1, so its otherwise passing
  full run reports exactly three expected fixture-generator version failures:
  892 passed, 1 skipped, 3 failed. No dependency was changed to conceal this;
  the authoritative pinned 12.3.0 gate passes.
- Clean Git archive at `40df1a9` builds a 117,093-byte wheel with SHA-256
  `2931802e228c6fa8795f0d1b38eca3dc0d57b5ba9a7f63a51c84c7849ed18b8e`.
- Its no-dependency target is 540,115 bytes and exposes exactly the optional
  extras `dashscope`, `dev`, `image`, and `ocr` with no base requirement.
- Plain installed import loads neither optional/heavy libraries nor
  `concurrent.futures` or the provider request gate.
- Thirty measured imports after two discarded warmups pass the budget: wall
  median/p95/max `39.5674/43.1269/45.4892` ms and CPU
  median/p95/max `46.875/46.875/46.875` ms.

No external provider/API HTTP request was made for this checkpoint. Private
screenshots and `docs/Textbook.pdf` were neither read nor staged and remain
untracked.

## Next Checkpoint

Define provider transport and model configuration without freezing the user's
four examples into a closed enum. Preserve these boundaries:

- OpenAI-compatible HTTP, provider SDKs, Google SDKs, and Codex
  subprocess/session execution have different credential and lifecycle rules.
- Aliyun built-in configuration remains explicit `cn-beijing`; do not infer a
  region from a credential.
- Model capability metadata must supply stricter image limits before upload.
- Preferences, execution, retry policy, and stateful credential pools remain
  separate responsibilities.
- Do not copy the legacy pool. Credential fairness/cooldown begins only after
  each enabled transport has a stable error taxonomy.
