# Codex CLI production boundary — 2026-09-16

This owner slice adds explicit Codex settings, durable public usage events and merged-call drain/deadline propagation. It does not activate a production provider or change another provider's defaults. Source baseline: OCRLLM `eeb41580ba9ac85d98d978f1345fcab32c937adc`, master; unrelated legacy and working-agent files remain untouched. Production activation and full real-model throughput evidence belong to course-pipeline.

## Caller configuration

```python
from pathlib import Path
from threading import Event
from ocrllm import CodexCLISettings, ProviderModel, observation_context, recognize_images_to_markdown

settings = CodexCLISettings(
    command=codex_binary, model="gpt-5.6-luna", reasoning_effort="low",
    service_tier="default", max_images_per_call=8,
    usage_event_dir=Path(persistent_usage_directory),
    course_validation=True, adjacent_repeat_limit=8,
)
provider = ProviderModel(
    vendor="openai", model="gpt-5.6-luna", adapter_id="codex_cli", settings=settings,
    supports_plain_ocr=True, supports_detail_ocr=True, supports_audio=False,
    default_image_batch_size=8, default_audio_minutes=None, retry_rules={},
)
stop = Event()
with observation_context(path=ordinary_owner_event_file, lecture_id=lecture_id,
                         runtime_version=running_ocrllm_commit):
    result = recognize_images_to_markdown(
        batches, provider=[[provider] for _ in range(configured_concurrency)],
        image_task="course_ocr", output_path=output_path,
        timeout_seconds=600, stop_requested=stop,
    )
```

Both concurrency and batching remain caller-selected; existing fixed checkpoint groups must be restored, not rebuilt. The default provider settings remain model Luna/low, `fast_mode=False`, timeout 1800 seconds, maximum 8 images. New settings default to `service_tier=None`, `usage_event_dir=None`, `course_validation=False`, `adjacent_repeat_limit=None`. The event directory must be absolute. Explicit tier is sent through `-c service_tier=...` even though the CLI ignores user configuration; legacy `fast_mode=True` still selects priority, and a conflicting explicit tier fails before a request.

The merged API's existing `timeout_seconds` (maximum 600) now bounds the whole Codex adapter invocation, including internal backoff/retries. The settings timeout also bounds each subprocess. Direct Config-based Codex calls keep the settings timeout. A stopped merged lane finishes its already admitted subprocess, persists usage/result or real failure, checkpoints it and then acknowledges safe stop. No subsequent internal spawn/retry is admitted. Existing non-Codex HTTP and ASR semantics are unchanged. This is cooperative drain, not a guarantee against power loss during a request.

## Public durable events

An opted-in writer creates `codex-<consumer-pid>-<instance-id>.jsonl` in the supplied directory. Every line is flushed and fsynced before the adapter proceeds. It writes no prompt, response body, reasoning text, access token, auth file or private Codex session. A persistence failure stops further admission; it cannot truthfully promise a terminal event when storage itself has failed.

Envelope: `schema_version="course-observation/v1"`, `owner="ocrllm"`, `task="ocr"`, stable `event_id`, UTC `at`, and `instance_id` beginning with the consumer PID. `kind` is `codex_attempt_started`, `codex_turn_usage`, or `codex_attempt_finished`.

Every event repeats `data.attempt_id`, `parent_call_id`, `start_event_id`, `started_at`, `lecture_id`, `logical_unit_id`, `requested_model`, `reasoning_effort`, `requested_service_tier`, `source_refs`, and `input_image_count`. `start_event_id` is allocated before spawn and equals the actual start event ID. In merged course calls the lecture/unit identities are exactly the existing `unit_result` identities. Source references are the existing owner observation's original URIs, not a new checkpoint schema. The actual CLI version is read with a bounded `--version`, cached by resolved binary path, mtime and size; its resolved path is also recorded and used for the real exec. An unavailable version remains null. Owner runtime version comes from the existing observation context. Merged execution supplies configured lane count and the original prompt version automatically. Model and tier actuals remain null unless the CLI explicitly reports them; requested values never masquerade as actual execution facts.

Started events have `spawned=null`. Finished events include `spawned=0/1`, `exit_code`, UTC `finished_at`, `outcome` (`succeeded`, `failed`, `timed_out` or `cancelled`), `validation_status` (`accepted`, `rejected` or `not_run`), `error_code` and `usage_capture_complete`. A failed executable launch is zero model calls, even when launch is retried. A successful spawn is one call regardless of its final exit code. The response and existing failure metadata carry the sum of actual spawns, including previous failed attempts.

Turn events include zero-based `turn_seq`, `event_type`, `observed_at`, `thread_id`, optional reported turn ID, `usage_semantics_version="codex-turn-usage/v1"`, `usage`, `raw_usage`, `raw_usage_scope="thread_cumulative"`, `normalization="thread_cumulative_delta"`, and `missing_reason`. Four nullable integer fields are input, cached input, output and reasoning output tokens. A reported `cache_write_input_tokens` is retained only in `raw_usage` for source auditing and is not added again to the four-field aggregate. Missing or invalid counts are unknown, never zero. Cached input is included in input; reasoning output is included in output. Total is input + output; subcategories must not be added a second time.

**Important implementation finding:** the public CLI type comment says “during a turn”, but its actual emitter uses `ThreadTokenUsage.total`. The exact installed release's [emitter](https://github.com/openai/codex/blob/rust-v0.154.0-alpha.6.1/codex-rs/exec/src/event_processor_with_jsonl_output.rs) calls `usage_from_last_total()` for completed turns. The corresponding main-file source checked on this date was commit `4fa6ad173055f6438e8baf81cd55cb59f46179d7`. This adapter always starts a fresh `exec --ephemeral`; it never resumes a CLI thread. The first baseline is zero, then each field is differenced against the previous cumulative report for that same thread. A missing middle baseline or negative difference produces unknown for that field; a later cumulative total is not charged as one turn. Raw reported counts remain alongside the normalized values for audit. A changed CLI emitting a different schema requires fresh verification rather than inference from its version label. The [official non-interactive guide](https://learn.chatgpt.com/docs/non-interactive-mode) documents the JSON event channel, but the concrete emitter determines this cumulative normalization.

`turn.failed` without usage creates a real unknown turn record. Timeout/exit with a missing terminal report likewise creates an unknown record; completed earlier turns remain inspectable. `usage_capture_complete` means input and output totals were completely captured, not that optional detail fields or actual routing metadata were reported. A failure with complete usage still counts its tokens. A success with missing usage remains a recognized result with explicitly unknown billing.

CLI `--json` stdout is solely telemetry. Markdown is read only from `--output-last-message`; there is no stdout fallback. Failed output, when present and event persistence is enabled, is retained separately as `failure_outputs/<attempt_id>.md`; events carry only its path and SHA-256. Successful output remains owned by the normal merged checkpoint/Markdown publication. Ledger consumers project these immutable events and cursors transactionally; they must not inspect private CLI state or synthesize model usage from estimates.

## Validation and recovery boundaries

Original course prompt/version is retained. The wrapper identifies attached images by an ordered JSON array of original names after ASCII staging. The Codex-only opt-in validator normalizes real matching comments, retains Unicode and adjacent-repetition checks according to the separately documented course contract, and does not invent missing frame markers. Model Lab's local validation is unchanged. Failed output is not a successful Markdown body.

The public `restore_image_batch_plan(sources, *, output_path)` validates the caller's current source fingerprints against the existing image checkpoint and returns its original tuple-of-tuples grouping. It neither modifies the state nor reorders successful slots. Source grouping, image task and prompt version remain the owner's facts.

## Verification

The focused owner suite covers explicit settings/Config copies, process-boundary retries and spawn counts, merged image/provider-model behavior, durable event ordering, failed usage, null usage, empty-body/stdout separation, failed output retention, filesystem write failure, per-field cumulative normalization, and stop/deadline propagation. Real local scripted subprocesses additionally prove usage is fsynced while the process is still running, an admitted request drains after a stop signal, and a timed-out request retains its completed turn plus an unknown unfinished turn. These subprocesses never contact a model service. Run them on demand with `PYTHONPATH=src python tools/verify_codex_usage_events.py --output-dir <new-persistent-scenario-directory>`. The sibling marker/recovery scenario and measurements are in [the owner record](course_image_contract_2026-09-16.md). Final counts are recorded in the work diary. No real-model latency, 20-way systemd throughput or production readiness claim follows from these tests alone.
