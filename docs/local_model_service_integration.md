# Local model service integration

The maintainer's 2026-09-06 request authorizes cooperation through ordinary
OpenAI-compatible HTTP, while keeping the repositories independently maintained.
Model Lab owns loading, GPU scheduling, process supervision, service limits and
backend diagnostics. OCRLLM owns explicit image/audio planning, bounded retries,
Markdown output and resume. Neither repository imports the other.

## Caller composition

Configure `OpenAICompatibleSettings(base_url=...)` and separate `ProviderModel`
values for the exact served OCR and ASR model IDs. Use
`adapter_id="openai_compatible_chat"`. Model Lab's deployment README supplies its
current URL and model IDs; OCRLLM does not launch that service or inspect its GPU.
A no-key loopback service needs no credential configuration.

Use `batchify_images(selected_paths, batch_size=...)` followed by
`recognize_images_to_markdown(...)`. `selected_paths` is the ordered set selected
by the caller. It is not every screenshot in an extracted course folder.
The future scenario is approximately 50–80 selected frames for a 2.5-hour course,
with the count varying with duration. Use `select_extracted_frames(tuple[RetainedVideoFrame, ...], duration_seconds=...)`
for already extracted JPEGs; it returns the existing duration-aware selector's
ordered subset. Crawler owns copying and publishing the selected package.

For MP3 or 24 kHz AAC in M4A course archives, compose `split_audio(path, interval_minutes=..., include_boundary_context=False)` with `recognize_audio_to_markdown(...)`.
The default boundary-context behavior remains available. A 24 kHz mono MP3 is a
valid source; physical clips are normalized by the existing media path. M4A container duration is inspected without a full-course conversion; each
request clip is converted directly from the original AAC to the existing MP3
provider input. The archive is not rewritten. WAV and raw AAC remain unsupported. Keep all slices for one course in the explicit
plan and resume unresolved slices with `resume_audio_to_markdown(...)`.

A caller can use finite policy such as:

```python
retry_rules={
    "PROVIDER_RATE_LIMITED": ("current", 1, 2),
    "PROVIDER_UNAVAILABLE": ("current", 1, 2),
}
```

These are caller-chosen bounds, not a claim that every service failure recovers.
SDK retries stay disabled. Invalid requests, oversized media and authentication
failures should be corrected instead of retried. Each request timeout is at most
600 seconds under the current OCRLLM contract. A larger service-side load budget
does not enlarge that client bound.

Model Lab now reports an explicit OCR generation limit as HTTP 422 with
`provider_code=output_token_limit`. The existing generic adapter maps 422 to
`PROVIDER_REQUEST_INVALID`, so the retry rules above do not repeat that request.
Keep its error code and request ID, then adjust the service budget or image
batch before a deliberate retry. The total context and generation budgets are
different; reasoning shares the latter with visible output.

Do not confuse a multi-image prompt with batching independent audio jobs. The
Chat audio route takes one audio item per request; OCRLLM sends explicit slices.
A backend may optimize execution internally while retaining that wire contract.
On this single GPU, running one modality's work together avoids repeated model
unload/load cycles. Concurrency and larger image groups require measured service
capacity; neither improves speed automatically.

## Reproducible bounded checks

Run `tools/run_local_openai_gateway_smoke.py` with an explicit `--base-url`,
`--audio` and one or more `--image` arguments. `--image-model` and `--audio-model`
can override the example deployment IDs. The default run uses one minute of
audio; `--audio-seconds 61` exercises two pure logical slices. With two selected
images, `--image-batch-size 2` sends one real multi-image request. The tool caps
its scenario at eight images and three minutes of audio; these are test bounds,
not new library restrictions. It emits counts, timing and verdicts, never course
text or source paths. Source hashes must remain unchanged.

`tools/run_local_gateway_recovery_scenario.py` is the companion fault-injection
scenario. Its local HTTP proxy returns deliberate transient errors while
forwarding successful requests to the real model service. Its report separates
injected HTTP failures from real inference; it does not claim that injected
responses measure real service overload. See the dated run record for actual
verdicts and remaining limits.


## Publication reconciliation

`inspect_markdown_job(output_path)` returns `missing`, `pending`, or `complete`
for an exclusively OCRLLM-owned merged output target. Use the fresh recognize
call for missing, ordinary resume for pending, and consume complete output.
Partial jobs and process interruptions retain the existing checkpoint; complete
Markdown is atomically published before that checkpoint is removed. If cleanup
is interrupted, a subsequent resume reuses every settled slot and finalizes.
The inspection is not a validator for arbitrary preexisting user Markdown.

## Bounded failed-range recovery

`bounded_transient_retry_rules()` returns the existing opt-in recipe for one
retry after two seconds on canonical rate-limit/unavailable/timeout errors.
The library does not install it as every provider's default.

`recognize_audio_to_markdown(..., failed_slice_minutes=2)` enables one automatic
subdivision of an original failed range only when the service reports the
observed `output_token_limit` code. It does not reinterpret input-context,
validation, permission or transient failures as generation-budget errors.
Use the same original `split_audio` plan on resume. Explicit
`resume_audio_to_markdown(..., failed_slice_minutes=2)` subdivides failed slots;
ordinary resume automatically reuses any already saved children. An explicitly
smaller maintenance interval can refine only remaining failed children, keeping
all settled text and source ranges. A fixed interval cannot trigger an infinite
split/retry loop. Unrecovered failures remain partial and should not block other
courses.

Subranges live in the original recognition checkpoint (v2 only when needed),
not a separate course journal. v1 checkpoints still load unchanged. Every child
is checkpointed before the next request, while original parent identities,
source fingerprints, successful parent results and provider accounting remain.
The real fourth-course scenario recovered 11 of 12 two-minute children, retaining
14 original successful parents; a KeyboardInterrupt before the third HTTP call
preserved the first two children and ordinary resume sent only the other ten.
One two-minute child remained a real generation-cap failure. This is recovery
and transport evidence, not a word-accuracy evaluation or proof that two-minute
slices always succeed. See the dated production-integration record.

For an unattended interrupted job, use
`resume_audio_to_markdown(original_plan, ..., failed_slice_minutes=2, only_output_limit=True)`.
This also preserves the opt-in recovery for later unattempted original slots.
Already saved output-cap failures subdivide before another request; other
failure reasons are not selected for subdivision. Existing children are reused,
and automatic recovery never recursively subdivides them. Omitting
`only_output_limit` retains deliberate maintenance's broader explicit failed-range
selection. A production loop should not repeatedly resume terminal partial jobs.

Partial Markdown still represents each unfinished original parent by its
existing failure marker; successful children of that parent stay in the
checkpoint until the parent completes. They are retained work, not lost text,
and must not be interpreted as already published complete Markdown. The final
one-minute refinement left only 9180–9240 seconds at the generation cap;
16/17 parents are complete and all 12 successful children remain in checkpoint.


## 2026-09-09: local ASR visible text validation

Use `OpenAICompatibleSettings(audio_response_validation="visible_text")` only
for an explicitly selected route. The default remains `"markdown"`. This audio
option retains UTF-8, visible Unicode L/N/S after removing closed HTML comments
from the inspection view, pure/mixed NOSPEECH handling, and the common HTTP,
choice, finish_reason and explicit refusal-field checks. It skips only the
short natural-language refusal-phrase heuristic, so a classroom quotation of
“I cannot” or an apology is not rejected for that phrase alone. Returned text
is not rewritten. This setting is independent of image
`response_validation="nonempty_text"` and `send_audio_prompt=False`.

The image option still checks UTF-8 and non-whitespace text; it intentionally
does not require visible body text beyond a frame comment, preserving the
approved empty-board behavior. The audio option must not reuse that weaker
image-content path. No repetition algorithm, model constraint, prompt-version
change, or checkpoint schema was added. Ordinary consumers load the setting
when their next process constructs the provider; this library option needs no
model-service restart. No running production process/state was changed here.

Validation: `tools/run_http200_request_id_scenario.py` used the real SDK against
a synthetic local HTTP server, testing both audio modes across 11 cases each:
classroom apology/quotation, valid Unicode, empty, comment-only, control/format/
punctuation-only, invalid UTF-8, mixed/pure NOSPEECH, length and explicit refusal.
All 22 comparisons passed; existing image metadata/empty and diagnostic checks
also passed. This is transport/validator evidence, not real model accuracy.
Relevant existing provider-model, merged-audio, Google audio adapter and light
import tests: 114 passed. No model requests were issued.

## Explicit bounded audio gaps (2026-09-09)

`recognize_audio_to_markdown` and `resume_audio_to_markdown` accept optional
`audio_gap_policy=AudioGapPolicy(max_failed_fraction=..., max_failed_segment_seconds=...)`;
`max_failed_seconds` is an optional additional total limit. The library supplies
no acceptance threshold. Only a failed leaf at most 120 seconds with canonical
`provider_code=output_token_limit` receives an initial attempt plus at most two
same-identity retries. Long parent failures still use the separately enabled
`failed_slice_minutes` subdivision. Existing provider transient rules stay
independent; other errors cannot qualify as accepted gaps. Old failures without
persisted attempt evidence start a new counter; external diagnostic calls are
not imported as checkpoint attempts. Changing the observed error resets the
consecutive counter; provider/prompt identity changes cannot reuse it.

Opt-in state v3 retains the original source fingerprint, exact parent/child
ranges, successful text/NOSPEECH, attempt counters and policy. v1/v2 remain
readable; unconfigured jobs keep their old state behavior. A gap is accepted
only when every failed leaf has three evidenced matching failures and all
configured limits pass. Results report `status="complete_with_gaps"` separately
from `complete`, with `accepted_with_gaps`, `failed_seconds`, `failed_fraction`
and `failed_segments` metadata. Accepted MD explicitly warns about missing
content. All partial child groups now render successful children and FAIL
markers at the actual failed child intervals, instead of hiding the whole parent.
Keep the checkpoint for ordinary recovery; the legacy lost-state repair parser
does not reconstruct these subdivided groups from Markdown alone.

Accepted jobs retain their sidecar. `inspect_markdown_job` returns
`complete_with_gaps`; `inspect_audio_completion(output_path, audio_gap_policy=...)`
returns a read-only dict with actual acceptance plus threshold/evidence facts.
Supplying a policy to inspection never accepts a job. A completed legacy MD
without a sidecar has unknown gap details (`None`), not an invented zero.
Ordinary resume of an accepted job makes zero provider calls, returns full
metadata and can rebuild a missing MD from its checkpoint. All-success jobs
continue deleting their checkpoint after publication.

Validation: `tools/verify_audio_gap_acceptance.py` used real FFmpeg media and the
real SDK against synthetic HTTP. It covered threshold rejection/acceptance,
retained successful/NOSPEECH children, exact ranges, old-state migration,
noneligible failures, interruption after the second persisted cap with only one
remaining call, changed-error counter reset, zero-call accepted resume and
missing-MD reconstruction. Evidence: persistent validation directory
`audio-gap-policy-scenario-durable/result.json`; 62 existing focused tests passed.
No real-model quality result is claimed here. `tools/run_audio_gap_trial.py`
prepares or executes the separately coordinated one-leaf trial, reusing the
owner's original-plan validator. Its explicit `retry_rules={}` bounds this
maintenance trial to three HTTP calls without changing production transient rules.

### D004 real bounded trial

OCRLLM `519989e93124fce4041d337430adae3959569410` executed the public resume
trial on 2026-09-09, ending at 12:49:46 UTC. The original 9180–9240 second
leaf received exactly three new requests; all returned `output_token_limit`.
The measured resume wall was 560.826 seconds, including failed recognition.
No reliable new transcription was recovered. Explicit limits of 5% total and
120 seconds per failed segment accepted the remaining 60 seconds out of
9794.795 seconds (0.61257%) as `complete_with_gaps`, not gap-free completion.

Owner review confirmed both public inspection APIs return that terminal status;
the MD visibly warns about missing content and marks exactly 9180–9240 seconds
as FAIL. The retained checkpoint contains all three new attempts. All 26
previously settled leaf records remain exactly equal, and source SHA-256 is
unchanged. MD/checkpoint hashes match the trial result. World audio remained
inspection-only: its 596.14 seconds (9.20517%) exceed this threshold, and its
checkpoint hash is unchanged. These outcomes do not establish transcription
accuracy within successful segments.

Authoritative evidence (source paths, hashes, request IDs, preserved-leaf
comparison and public summaries):
`/mnt/r/course-pipeline-state/validation/audio-gap-policy-20260909/owner-trial/result.json`.
This documentation review made no model requests or state changes. Production
lifecycle and publication reconciliation remain recorded by the orchestrator.
