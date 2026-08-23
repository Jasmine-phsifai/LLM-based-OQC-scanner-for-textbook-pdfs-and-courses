# Legacy Provider Error-to-Action Evidence (#066)

## Status and purpose

This is the bounded P0-a evidence record required by `#065 Unified Execution
Queue`. It is not a current-live provider report. Evidence is labelled as:

- **incident** — a real legacy run or maintainer-observed failure recorded in
  `legacy_app/AGENTS.md`;
- **offline test** — a deterministic regression with mocked or local inputs;
- **code-only** — policy found in legacy code without a matching incident or
  focused regression.

The action vocabulary is deliberately closed: `retry_same`, `switch_model`,
`stop`, `reject_input`, and `manual_repair`. “Resume” is retained state after
`stop`, not a sixth provider-error action. Historical evidence must be rechecked
against the current API before it controls a new adapter.

## Transport finding: the legacy built-in Google path is native

The legacy built-in Google image and audio path uses the official
`google-genai` SDK, not Google's OpenAI-compatible endpoint:

- `legacy_app/OCRLLM/core/providers/google_provider.py:1-5,444-449,614-633,707-750`
  declares the native transport, creates `genai.Client`, calls image
  `generate_content`, and uploads audio through the Files API.
- `legacy_app/OCRLLM/core/provider_selection.py:8-23` and
  `legacy_app/OCRLLM/core/providers/router.py:12-22` select native Google only
  when Codex and the independent vision provider do not own image work.
- `legacy_app/OCRLLM/core/providers/hybrid_google_provider.py:13-44` routes
  images to the independent OpenAI-compatible client while keeping Google text
  and long audio on the native client.
- The exact compatibility URL appears only as a placeholder for the independent
  provider at `legacy_app/OCRLLM/gui/settings_dialog.py:436-443`.
  `VisionAPIConfig` is generic and separate from `GoogleAPIConfig`
  (`legacy_app/OCRLLM/config.py:97-116,134-160`), and its client and image path
  are generic OpenAI-compatible code
  (`legacy_app/OCRLLM/core/llm_client.py:183-230,556-592`).
- The native catalog uses `client.models.list()` with a Google REST fallback
  and its own cache (`legacy_app/OCRLLM/core/model_catalog.py:518-584`). The
  compatibility form has only the generic independent-provider `/models` scan.

The repository therefore does not prove a Google-specific compatibility
transport success or error history. Following the maintainer's evidence
correction, the active library's next Google slice follows the actual legacy
built-in transport: native `google-genai`. A future Google compatibility path
and the future local-model OpenAI-compatible path remain separate, later work.

## Bounded error-to-action table

| Provider and observed signature/state | Action | Exact legacy evidence | Evidence level | Current active seam |
|---|---|---|---|---|
| Google `429` / `RESOURCE_EXHAUSTED` with `rate limit`, RPM, TPM, or RPD marker | `retry_same` | Classifier: `legacy_app/OCRLLM/core/providers/google_provider.py:165-185,348-380`; regressions and retry delay: `legacy_app/tests/test_google_provider_errors.py:149-175,187-194,250-265`; corrected distinction: `legacy_app/AGENTS.md:828-852` | incident + offline test | Typed rate-limit disposition exists in `src/ocrllm/provider_error_disposition.py:40-60`; native Google mapping is unimplemented and requires live confirmation. |
| Google `RESOURCE_EXHAUSTED: You exceeded your current quota ... check your plan and billing details`, without a window marker | `switch_model` | `legacy_app/OCRLLM/core/providers/google_provider.py:182-189,355-380,505-546`; `legacy_app/tests/test_google_provider_errors.py:107-147`; `legacy_app/AGENTS.md:828-852` | incident + offline test | The image candidate seam exists at `src/ocrllm/processors/recognize_images.py:49-71,142-172`; failure scope must be proven live before advancing. |
| Google `404 NOT_FOUND`, or unsupported-modality `400/INVALID_ARGUMENT` with `modality is not enabled`, `only supports`, or equivalent | `switch_model` | `legacy_app/OCRLLM/core/providers/google_provider.py:180-220,363-404`; `legacy_app/tests/test_google_provider_errors.py:205-212` | offline test + code-only | Candidate routing exists, but model scope and current catalog behavior need live confirmation. |
| Google malformed/invalid request not proven to be a model capability mismatch | `reject_input` | Generic `400/INVALID_ARGUMENT` classification at `legacy_app/OCRLLM/core/providers/google_provider.py:209-220,391-405` currently mixes request and candidate behavior | code-only | Active `PROVIDER_REQUEST_INVALID` maps to `fix_request` at `src/ocrllm/provider_error_disposition.py:55-57`; reject locally provable bad requests before dispatch and preserve other provider errors. |
| Google network error, `500 INTERNAL`, `503 UNAVAILABLE/high demand`, concurrency limit, or empty response | `retry_same` | `legacy_app/OCRLLM/core/providers/google_provider.py:165-208,383-390,451-502`; `legacy_app/tests/test_google_provider_errors.py:196-265` | offline test + code-only | Network/timeout/unavailable types exist, but no universal retry loop is active. Retry count and delay require current live evidence. |
| Google authentication/permission failure, safety block, genuine billing failure, or unknown terminal response | `stop` | `legacy_app/OCRLLM/core/providers/google_provider.py:186-221,365-405` | code-only | Active typed authentication, permission, content-blocked, and invalid-response categories exist. Google-specific mapping is unimplemented. |
| Google audio returns nonempty false-success content (hotword list, prompt echo, implausibly short transcript, repetitive noise) | `stop` for the exhausted candidate; a caller-configured eligible candidate may `switch_model` | Validator/switch: `legacy_app/OCRLLM/core/providers/google_provider.py:451-471,505-562`; regressions: `legacy_app/tests/test_google_audio_routing.py:219-287,502-609`; real nonempty fake-success lesson: `legacy_app/AGENTS.md:82-107` | incident + offline test | Image refusal validation exists at `src/ocrllm/providers/looks_like_refusal.py:10-66`; public audio validation and adapter do not. This is audio evidence, not a general quality router. |
| Google audio has settled one segment, then quota/network failure stops the run | `stop`, retaining state for normal resume | `legacy_app/tests/test_google_audio_routing.py:331-423` proves the later run requests only the missing segment | offline test | Image slot resume exists; public audio state does not. Do not add repair or chunk machinery to short audio. |
| Generic OpenAI-compatible network/empty or HTTP `429/500/502/503/504` | `retry_same` | `legacy_app/OCRLLM/core/llm_client.py:28-35,108-120,539-554` | code-only | Typed retry dispositions exist. The legacy fixed six-attempt exponential loop is not portable policy. |
| DashScope `AllocationQuota.FreeTierOnly` / `FreeAllocationQuotaExceeded` | `switch_model` | `legacy_app/OCRLLM/core/llm_client.py:49-78,92-105,474-537`; `legacy_app/tests/test_vision_provider.py:103-131`; separation at `legacy_app/AGENTS.md:835-837` | offline test + incident clarification | Built-in DashScope and the model-scoped candidate seam exist. These markers must never classify Google failures. |
| Independent OpenAI-compatible streaming image call first returns `429/5xx` | `retry_same` once through non-streaming wire form | `legacy_app/OCRLLM/core/llm_client.py:323-375`; `legacy_app/tests/test_vision_provider.py:40-74,168-193`; CLIProxy incident `legacy_app/AGENTS.md:492-531` | incident + offline test | No generic stream/non-stream abstraction exists in active code. Preserve only if a selected transport proves the same failure. |
| Independent provider non-streaming call still has an ordinary temporary failure, and the user explicitly enabled the queue | `switch_model`; exhaustion `stop`s by rethrowing the original provider error | `legacy_app/OCRLLM/core/llm_client.py:61-105,474-537`; `legacy_app/tests/test_vision_provider.py:40-101,133-166`; `legacy_app/AGENTS.md:804-826` | incident + offline test | Active switching is opt-in and requires an eligible code plus exact `model` scope. Do not broaden it to every `5xx`. |
| Codex exits zero with a leading `SORRY4OCRLLM` reason saying attached images are inaccessible | `retry_same` on the dedicated bounded long schedule; exhaustion `stop`s with resumable state | `legacy_app/OCRLLM/core/codex_vision.py:78-101,422-518`; `legacy_app/tests/test_codex_vision.py:191-239`; live incident `legacy_app/AGENTS.md:463-489` | incident + offline test | Only general short-refusal validation is active; there is no Codex adapter. The sentinel and delays are Codex-specific. |
| Codex exits zero with an ordinary leading refusal sentinel or empty output | `retry_same` within the ordinary bounded loop, then `stop` | `legacy_app/OCRLLM/core/codex_vision.py:466-518`; `legacy_app/tests/test_codex_vision.py:241-262`; `legacy_app/tests/test_codex_vision_refusal.py:47-67` | offline test | Active short-refusal detection exists, but it does not implement the Codex sentinel contract. |
| Codex subprocess timeout | `stop` | `legacy_app/OCRLLM/core/codex_vision.py:422-448`; `legacy_app/tests/test_codex_vision_refusal.py:70-83`; `legacy_app/AGENTS.md:199-205` | incident + offline test | Active generic timeout is retryable by default, demonstrating why transport-specific proof is required. |
| Missing, empty, corrupt, or provider-unsafe Codex image path | `reject_input` or create a validated provider-safe snapshot before dispatch | `legacy_app/OCRLLM/core/codex_vision.py:371-405`; live zero/truncated-image reproduction `legacy_app/AGENTS.md:109-151`; Unicode path incident and ASCII staging `legacy_app/AGENTS.md:429-460` | incident + offline-tested code | Active recognition consumes validated owned image snapshots. Keep lifecycle protection; do not resume hypothetical path enumeration. |
| PDF batch/provider failure after some batches succeeded | `stop` after preserving successful output, typed failed units, and normal resume state | `legacy_app/OCRLLM/processors/pdf.py:340-465,481-541,585-634`; `legacy_app/tests/test_failure_propagation.py:165-239,331-362`; `legacy_app/AGENTS.md:66-80,275-286` | incident + offline test | Active ordered outcomes and image resume are usable seams; PDF is unimplemented. Markdown comments must not be primary state. |
| PDF state is missing/unusable and historical Markdown contains a stable failed-page marker | `manual_repair` | `legacy_app/OCRLLM/processors/pdf.py:52-55,684-808`; missing direct coverage admitted at `legacy_app/AGENTS.md:535-550`; direct-write/regex warning at `legacy_app/AGENTS.md:638-647` | code-only with explicit negative test evidence | No active PDF or repair seam. P1-d starts only after typed PDF state and markers stabilize, and must publish atomically. |
| PDF renderer local decode verification fails (observed `broken data stream`) | `reject_input` if source is invalid; otherwise local fallback encoder, then `stop` if rendering still fails | 581-page incident and fallback: `legacy_app/AGENTS.md:208-232` | incident | This is local rendering, not a provider retry. PDF remains unimplemented and must use the selected PDFium path. |

## Nonportable legacy behavior

Do not migrate:

- a GUI placeholder as proof that the Google compatibility endpoint succeeded;
- legacy exception classes used as routing control signals;
- the blind DashScope-SDK-to-OpenAI-compatible audio fallback;
- the generic six retries or legacy backoff numbers;
- DashScope quota markers applied to Google;
- the Codex sentinel or long-backoff schedule generalized to other providers;
- the Codex blocking subprocess path as a cancellation design;
- localized PDF Markdown regexes as durable identity;
- PDF's non-atomic `Path.write_text()` repair publication;
- historical units reconstructed with today's batch-size configuration.

## P0-a exit and next action

P0-a is complete with this bounded record. Do not extend the legacy survey.
P0-b is next: implement the smallest public native `google-genai` image slice,
then run the authorized bounded live gate with one image, one group of 7-8
images, at least one honest failure, live catalog and credential behavior,
locally observed call count, and provider-reported usage availability. Native
historical classifications remain warnings until current live evidence confirms
or replaces each mapping.
