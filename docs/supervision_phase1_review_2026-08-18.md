# Supervision Review: Phase 1 Migration & Defect Repair — 2026-08-18

Independent audit of `src/ocrllm` after the D1–D7 defect-repair session, with
live execution. Method: full test suite, import-weight probe, behavioral probes
of D1–D4 through the public API with an injected fake provider, and one live
paid DashScope smoke.

## Verified By Execution

| Claim | Result |
|---|---|
| Test suite | 1006 passed, 0 failed, 0 skipped (139 s). Note: the authority doc still says 987 passed / 1 skipped. |
| Import weight | 112 ms, zero heavy modules (`PIL`, `openai`, `httpx`, `onnxruntime`, `cv2`, `numpy` all absent). Under the 150 ms gate. |
| D1 refusal | `无法识别图片内容，请重新上传` raises `ProviderError` code `PROVIDER_REFUSED_RECOGNITION`, `details["reason"]=="refusal"`. Validation sits at the single choke point (`providers/call_vision_provider.py`), covering built-in and injected providers. |
| D2 timeout | Injected provider sleeping 6 s under `timeout_seconds=1.0` raised `PROVIDER_TIMEOUT` at exactly 1.0 s elapsed. |
| D3 batch | `recognize_batch` returns ordered `BatchItemOutcome` per source; on failure, completed items keep their results, the failing item carries its typed error, undispatched items are marked not-attempted. Paid work is never discarded. |
| D4 resume | Injected provider without `resume_identity` → `ConfigError` naming the attribute. With it → resume accepted. |
| Live path | Real DashScope recognize of a text image succeeded end-to-end in 2.8 s with correct content. Pre-dispatch validation (minimum pixel size) fired *before* any paid call on a bad image. |

The defect-repair session's claims are substantially honest. Stage M
(model discovery, flowed output, disclosed recovery) has **zero implementation**
— `SUPPORTED_DASHSCOPE_MODELS` still gates to 3 models; output is still
all-or-nothing within one request. That matches the plan's status ("current
work, not started"), so it is a status fact, not a defect.

## Findings (open, ordered by user impact)

### F1 — Refusal detection still leaks common refusal phrasings. Medium.

Proven by probe: all three of the following were returned to the caller as
**successful** recognitions:

- `抱歉，我帮不了你识别这张图。`
- `对不起，图片太模糊，请提供更清晰的版本。`
- `Sorry, this request cannot be completed.`

`providers/looks_like_refusal.py` ports the legacy phrase list verbatim, so it
inherits the legacy list's holes: no `抱歉`, `对不起`, bare `sorry`,
`cannot be completed`, `请提供更清晰` markers. The defect class D1 guarded
against — refusal presented as success — is still reachable through any
phrasing outside the list.

### F2 — The authority document misdescribes the shipped batch and refusal API. Medium.

`docs/ACTIVE_STATE_AND_RULES.md` declares itself "authoritative and current"
(verified same day) yet:

- Its D3 entry says a raised `OCRLLMError` carries `partial_results`,
  `details["batch_completed_count"]`, and `details["batch_dispatched_count"]`.
  **None of these exist anywhere in `src/`.** The shipped contract is a
  returned `list[BatchItemOutcome]` and no exception. The shipped design is
  better than the documented one, but an Electron integrator following the
  authority doc would write error handling for an API that does not exist.
- Its D1 entry says a refusal raises code `PROVIDER_RESPONSE_INVALID` with
  `details["reason"]=="refusal"`. The code raises
  `PROVIDER_REFUSED_RECOGNITION`.
- Its verified-state table says 987 passed / 1 skipped; the suite is now
  1006 passed / 0 skipped.

### F3 — `DashScopeSettings` forces every caller to hand-write the endpoint URL. Low.

`region` and `base_url` are both required positional with no defaults and no
derivation helper, even though `provider_settings.py` already contains
`_SHARED_HOST_BY_REGION` mapping regions to hosts and the fixed
`/compatible-mode/v1` path. Every consumer (the future Electron app included)
will copy-paste `https://dashscope.aliyuncs.com/compatible-mode/v1` from an
example. The knowledge exists in the file; it is just not offered.

### F4 — Refusal/empty `details` carry `model=None, provider=None` for plain injected providers. Low.

Observed in probe output. Harmless but noisy; the wrapper enriches details with
attributes injected providers usually lack. Consider omitting keys that are
None.

## Fix Prompts For Future Agents

### Prompt F1 (refusal marker gaps)

> In `src/ocrllm/providers/looks_like_refusal.py`, the marker list misses
> common refusal phrasings. Proven leaks (must become failing tests first):
> `抱歉，我帮不了你识别这张图。`, `对不起，图片太模糊，请提供更清晰的版本。`,
> `Sorry, this request cannot be completed.` Add markers covering `抱歉`,
> `对不起`, standalone `sorry`, `cannot be completed`, `can't be completed`,
> `请提供更清晰`, `帮不了`. Keep the existing 300-visible-character cap and the
> existing tests green — especially
> `test_long_transcription_mentioning_a_refusal_phrase_is_accepted` and
> `test_looks_like_refusal_ignores_ordinary_content` in
> `tests/test_defect_register_regressions.py`. Risk to manage: `抱歉`/`sorry`
> can appear in legitimate short transcriptions of boards that literally
> contain apology text; that is acceptable only because the cap already limits
> scope to short outputs — state this trade-off in the module comment. Also
> apply the same additions to the legacy oracle
> `legacy_app/OCRLLM/core/output_quality.py::looks_like_refusal` (both
> codebases share this list per the working-diary rule) and add a diary entry
> in `legacy_app/AGENTS.md`. Success criteria: new parametrized tests with the
> three proven leak strings fail before the change and pass after; full suite
> green; no change to `validate_provider_markdown`'s error contract.

### Prompt F2 (authority-doc drift)

> `docs/ACTIVE_STATE_AND_RULES.md` misdescribes shipped behavior. Correct three
> things against the code, changing docs only: (1) the D3 entry must describe
> the actual contract — `recognize_batch` returns `list[BatchItemOutcome]`
> (see `src/ocrllm/recognize_batch.py` and `batch_item_outcome.py`), never a
> raised error carrying `partial_results`; delete every mention of
> `partial_results`, `batch_completed_count`, `batch_dispatched_count` or mark
> them as superseded design; (2) the D1 entry must name the real error code
> `PROVIDER_REFUSED_RECOGNITION` (source:
> `src/ocrllm/providers/validate_provider_markdown.py`); (3) refresh the
> verified-state table counts (suite is 1006 passed / 0 skipped as of
> 2026-08-18; re-run to confirm). Success criteria: every API name, error code,
> and count in that file exists verbatim in `src/` or in a fresh test run; grep
> for `partial_results` across the repo returns only historical `phase*` docs
> if anywhere.

### Prompt F3 (endpoint ergonomics)

> `src/ocrllm/providers/dashscope/provider_settings.py` requires callers to
> pass both `region` and `base_url` although `_SHARED_HOST_BY_REGION` plus the
> `_OPENAI_COMPATIBLE_PATH` constant can derive the shared-endpoint URL for
> the four mapped regions. Add one classmethod (e.g.
> `DashScopeSettings.for_region(region, *, api_key=None, ...)`) that derives
> `base_url` for mapped regions and raises the existing `ConfigError` for
> unmapped ones. Do not change the primary constructor, existing validation,
> or any workspace-URL logic. Success criteria: a failing-first test proving
> `for_region("cn-beijing").base_url == "https://dashscope.aliyuncs.com/compatible-mode/v1"`;
> all existing `test_dashscope_settings.py` tests untouched and green;
> import weight unchanged.

### Prompt F4 (None-valued detail keys)

> In `src/ocrllm/providers/call_vision_provider.py`, the validation-error
> enrichment adds `"model"` and `"provider"` even when both are None (typical
> for injected providers). Omit keys whose value is None. Success criteria:
> failing-first test asserting a refusal from a plain injected provider has no
> `model`/`provider` keys in `details`, while the built-in path still includes
> them; full suite green.

## Probe Artifacts

Probe scripts live in `temp/` (`supervise_probe.py`, `live_smoke.py`,
`probe_*.png`, `probe_resume_out/`) and are reproducible; `temp/` is not
shipped.
