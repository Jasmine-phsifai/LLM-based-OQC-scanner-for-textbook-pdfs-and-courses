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
with the count varying with duration. Selection of a pre-extracted picture pack
and a production CLI are future work, not new hidden operations in these APIs.

For MP3 audio, compose `split_audio(path, interval_minutes=..., include_boundary_context=False)` with `recognize_audio_to_markdown(...)`.
The default boundary-context behavior remains available. A 24 kHz mono MP3 is a
valid source; physical clips are normalized by the existing media path. No new
codec promise is made for WAV/M4A. Keep all slices for one course in the explicit
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
