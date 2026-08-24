# Legacy Provider Error-to-Action Evidence (#066)

## Status and purpose

This is the bounded P0-a evidence record required by `#065 Unified Execution
Queue`. The table remains historical evidence rather than a general current-live
provider report. #067 adds one narrowly scoped live observation below. Evidence is labelled as:

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
correction, the active library's #067 Google image slice follows the actual legacy
built-in transport: native `google-genai` and is now live-proven. A future Google compatibility path
and the future local-model OpenAI-compatible path remain separate, later work.

#070 rechecked the complete legacy construction and call chain and confirmed
the same distinction: GUI settings populate `GoogleAPIConfig`, provider
selection constructs the native Google client, and image recognition reaches
`models.generate_content`; the generic `/v1beta/openai` placeholder belongs to
the independently enabled compatible-provider configuration. The current
library's native adapter therefore needs no transport correction.

## Bounded error-to-action table

| Provider and observed signature/state | Action | Exact legacy evidence | Evidence level | Current active seam |
|---|---|---|---|---|
| Google `429` / `RESOURCE_EXHAUSTED` with `rate limit`, RPM, TPM, or RPD marker | `retry_same` | Classifier: `legacy_app/OCRLLM/core/providers/google_provider.py:165-185,348-380`; regressions and retry delay: `legacy_app/tests/test_google_provider_errors.py:149-175,187-194,250-265`; corrected distinction: `legacy_app/AGENTS.md:828-852` | incident + offline test | `map_google_genai_error.py` maps ordinary 429 to provider-scoped `RateLimited`; focused tests cover it, but #067 did not observe 429 live and the adapter has no internal retry. |
| Google `RESOURCE_EXHAUSTED: You exceeded your current quota ... check your plan and billing details`, without a window marker | `switch_model` | `legacy_app/OCRLLM/core/providers/google_provider.py:182-189,355-380,505-546`; `legacy_app/tests/test_google_provider_errors.py:107-147`; `legacy_app/AGENTS.md:828-852` | incident + offline test; current live classification in #068 | The mapper emits model-scoped `QuotaExhausted` and the opt-in image candidate seam can advance. #068 observed `PROVIDER_QUOTA_EXHAUSTED` / `model` from one native audio gate on `gemini-3.1-pro-preview`; the public audio slice has no candidate switch or internal retry, so it stopped honestly. Raw provider text was not published, so the precise upstream message remains unclaimed. |
| Google `404 NOT_FOUND`, or unsupported-modality `400/INVALID_ARGUMENT` with `modality is not enabled`, `only supports`, or equivalent | `switch_model` | `legacy_app/OCRLLM/core/providers/google_provider.py:180-220,363-404`; `legacy_app/tests/test_google_provider_errors.py:205-212` | offline test + code-only | Exact 404 and narrowly proven image/modality phrases map to model-scoped `ProviderUnavailable`; broader parameter/count messages remain request-scoped. Neither branch was observed live in #067. |
| Google malformed/invalid request not proven to be a model capability mismatch | `reject_input` | Generic `400/INVALID_ARGUMENT` classification at `legacy_app/OCRLLM/core/providers/google_provider.py:209-220,391-405` currently mixes request and candidate behavior | code-only | Local size/format preflight rejects before SDK construction; remaining generic 400 maps to request-scoped `PROVIDER_REQUEST_INVALID`. #067 did not observe it live. |
| Google network error, `500 INTERNAL`, `503 UNAVAILABLE/high demand`, concurrency limit, or empty response | `retry_same` | `legacy_app/OCRLLM/core/providers/google_provider.py:165-208,383-390,451-502`; `legacy_app/tests/test_google_provider_errors.py:196-265` | offline test + code-only | The active mapper distinguishes timeout, network, and provider-unavailable; invalid empty text remains typed response failure. The adapter has no internal retry and #067 observed none of these live. |
| Google authentication/permission failure, safety block, genuine billing failure, or unknown terminal response | `stop` | `legacy_app/OCRLLM/core/providers/google_provider.py:186-221,365-405` | code-only | Authentication, permission, content-blocked, and invalid-response mappings are implemented. #067 and #069 live-proved credential-scoped `PROVIDER_AUTHENTICATION` through their invalid-key probes; the other outcomes remain offline-only. |
| Google audio returns nonempty false-success content (hotword list, prompt echo, implausibly short transcript, repetitive noise) | `stop` for the exhausted candidate; a caller-configured eligible candidate may `switch_model` | Validator/switch: `legacy_app/OCRLLM/core/providers/google_provider.py:451-471,505-562`; regressions: `legacy_app/tests/test_google_audio_routing.py:219-287,502-609`; real nonempty fake-success lesson: `legacy_app/AGENTS.md:82-107` | incident + offline test | The active short-audio slice rejects empty/refusal output, maps an exact `NOSPEECH4OCRLLM` response to `NoSpeechDetected`, and rejects embedded/mixed sentinel text. It does not implement the legacy hotword, plausible-length, repetition, or candidate router. #069 produced a successful result that passed the active validation boundary, but its text was not published or quality-scored; the stronger legacy content heuristics therefore remain unverified in the active path. |
| Google audio has settled one segment, then quota/network failure stops the run | `stop`, retaining state for normal resume | `legacy_app/tests/test_google_audio_routing.py:331-423` proves the later run requests only the missing segment | offline test | Image slot resume exists; public audio state does not. Do not add repair or chunk machinery to short audio. |
| Generic OpenAI-compatible network/empty or HTTP `429/500/502/503/504` | `retry_same` | `legacy_app/OCRLLM/core/llm_client.py:28-35,108-120,539-554` | code-only | Typed retry dispositions exist. The legacy fixed six-attempt exponential loop is not portable policy. |
| DashScope `AllocationQuota.FreeTierOnly` / `FreeAllocationQuotaExceeded` | `switch_model` | `legacy_app/OCRLLM/core/llm_client.py:49-78,92-105,474-537`; `legacy_app/tests/test_vision_provider.py:103-131`; separation at `legacy_app/AGENTS.md:835-837` | offline test + incident clarification | Built-in DashScope and the model-scoped candidate seam exist. These markers must never classify Google failures. |
| Independent OpenAI-compatible streaming image call first returns `429/5xx` | `retry_same` once through non-streaming wire form | `legacy_app/OCRLLM/core/llm_client.py:323-375`; `legacy_app/tests/test_vision_provider.py:40-74,168-193`; CLIProxy incident `legacy_app/AGENTS.md:492-531` | incident + offline test | No generic stream/non-stream abstraction exists in active code. Preserve only if a selected transport proves the same failure. |
| Independent provider non-streaming call still has an ordinary temporary failure, and the user explicitly enabled the queue | `switch_model`; exhaustion `stop`s by rethrowing the original provider error | `legacy_app/OCRLLM/core/llm_client.py:61-105,474-537`; `legacy_app/tests/test_vision_provider.py:40-101,133-166`; `legacy_app/AGENTS.md:804-826` | incident + offline test | Active switching is opt-in and requires an eligible code plus exact `model` scope. Do not broaden it to every `5xx`. |
| Codex exits zero with a leading `SORRY4OCRLLM` reason saying attached images are inaccessible | `retry_same` on the dedicated bounded long schedule; exhaustion `stop`s with resumable state | `legacy_app/OCRLLM/core/codex_vision.py:78-101,422-518`; `legacy_app/tests/test_codex_vision.py:191-239`; live incident `legacy_app/AGENTS.md:463-489` | incident + offline test | Only general short-refusal validation is active; there is no Codex adapter. The sentinel and delays are Codex-specific. |
| Codex exits zero with an ordinary leading refusal sentinel or empty output | `retry_same` within the ordinary bounded loop, then `stop` | `legacy_app/OCRLLM/core/codex_vision.py:466-518`; `legacy_app/tests/test_codex_vision.py:241-262`; `legacy_app/tests/test_codex_vision_refusal.py:47-67` | offline test | Active short-refusal detection exists, but it does not implement the Codex sentinel contract. |
| Codex subprocess timeout | `stop` | `legacy_app/OCRLLM/core/codex_vision.py:422-448`; `legacy_app/tests/test_codex_vision_refusal.py:70-83`; `legacy_app/AGENTS.md:199-205` | incident + offline test | Active generic timeout is retryable by default, demonstrating why transport-specific proof is required. |
| Missing, empty, corrupt, or provider-unsafe Codex image path | `reject_input` or create a validated provider-safe snapshot before dispatch | `legacy_app/OCRLLM/core/codex_vision.py:371-405`; live zero/truncated-image reproduction `legacy_app/AGENTS.md:109-151`; Unicode path incident and ASCII staging `legacy_app/AGENTS.md:429-460` | incident + offline-tested code | Active recognition consumes validated owned image snapshots. Keep lifecycle protection; do not resume hypothetical path enumeration. |
| PDF batch/provider failure after some batches succeeded | `stop` after preserving successful output, typed failed units, and normal resume state | `legacy_app/OCRLLM/processors/pdf.py:340-465,481-541,585-634`; `legacy_app/tests/test_failure_propagation.py:165-239,331-362`; `legacy_app/AGENTS.md:66-80,275-286` | incident + offline test | Active PDF now uses serial fail-fast image groups. `test_second_pdf_group_provider_failure_keeps_first_state_and_resumes` proves a failure preserves completed child sidecars and attaches settled-group evidence, but publishes no final Markdown or failed-unit marker; ordinary resume reuses completed groups. Markdown comments are not primary state. |
| PDF state is missing/unusable and historical Markdown contains a stable failed-page marker | `manual_repair` | `legacy_app/OCRLLM/processors/pdf.py:52-55,684-808`; missing direct coverage admitted at `legacy_app/AGENTS.md:535-550`; direct-write/regex warning at `legacy_app/AGENTS.md:638-647` | code-only with explicit negative test evidence | Active PDF checkpoints and successful range markers are stable and live-proven (#078), but no repair seam exists. The fail-fast producer emits no failed-range marker or final Markdown on failure; P1-d is paused pending the maintainer's A/B/C product choice. Do not port the localized legacy parser or non-atomic write. |
| PDF renderer local decode verification fails (observed `broken data stream`) | `reject_input` if source is invalid; otherwise local fallback encoder, then `stop` if rendering still fails | 581-page incident and fallback: `legacy_app/AGENTS.md:208-232` | incident | This is local rendering, not a provider retry. Active rendering uses serial PDFium under one lock, so the legacy parallel Pillow-init race and fallback are not ported. #088 directly proves that decode failure of a library-generated page PNG becomes local `OUTPUT_WRITE_FAILED`, dispatches no provider request for that group, preserves settled sidecars, and leaves no final Markdown or rendered PNG. |

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
P0-b is complete in #067. Native historical classifications remain warnings
until current live evidence confirms or replaces each mapping.

## #067 current live observation

The bounded native image gate used `gemini-2.5-flash` and discovered 37 current
`generateContent` models. One image and one eight-image group each succeeded in
exactly one call and returned provider-reported input/output usage. A deliberately
invalid non-secret key produced `PROVIDER_AUTHENTICATION` with credential scope.
This confirms the current native credential-error seam only. No rate-limit,
quota, timeout, network, unavailable, unsupported-modality, safety, empty-response,
or model-switch outcome was observed live; their table rows remain incident,
offline-test, or code-only evidence and must not be relabelled as current-live.

## #068 current live observation

The active short-audio slice follows the legacy native SDK transport but uses a
bounded inline `audio/mpeg` Part for one MP3 rather than copying the legacy
all-audio Files upload/poll lifecycle. A final persisted safe capture selected
`gemini-3.1-pro-preview` and returned `PROVIDER_QUOTA_EXHAUSTED` with model
scope: exit 1 after 6,294 ms for a 14,332-byte, 3.468888889-second synthetic
speech MP3. Stderr was empty and the credential scan was false. No transcript
was produced or published, and raw provider text was intentionally not
published. Therefore only the typed current quota/model outcome is live
evidence; rate-window wording, retry timing, candidate behavior, and every other
table row remain unobserved by #068.

## #069 current live observation

One persisted safe capture selected `gemini-2.5-flash` from a current catalog
of 37 `generateContent` models and completed a 3.468888889-second, 26,488-byte
synthetic-speech MP3 through the public facade. It returned one successful
`RecognitionResult`, exactly one provider call, and provider-reported
input/output usage of 150/10. Its invalid-key probe returned
`PROVIDER_AUTHENTICATION` with credential scope. The process exited 0 after
13,341 ms; stderr was empty, the credential scan was false, and temporary files
and key-bearing environment variables were removed. Recognized text passed the
active validators but was intentionally not published, so this is current live
result/lifecycle evidence rather than a transcription-quality evaluation. It
does not convert the other error-table rows into observed current behavior.
