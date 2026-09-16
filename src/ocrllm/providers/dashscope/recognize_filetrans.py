"""Native DashScope FileTrans adapter with durable task identity."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from ...audio.snapshot_long_mp3 import LongMP3Snapshot
from ...errors import (
    Cancelled,
    ConfigError,
    DependencyMissing,
    NoSpeechDetected,
    OCRLLMError,
    ProviderError,
    ProviderRequestInvalid,
    ProviderUnavailable,
    ResumeStateError,
)
from ...raise_if_cancelled import raise_if_cancelled
from ..audio_provider_response import AudioProviderResponse
from .filetrans_settings import (
    DEFAULT_DASHSCOPE_FILETRANS_MODEL,
    DashScopeFileTransSettings,
)

_STATE_VERSION = "ocrllm.dashscope-filetrans.v1"
_MAX_RESPONSE_BYTES = 4 * 1024 * 1024


def recognize_filetrans(
    snapshot: LongMP3Snapshot,
    *,
    prompt: str,
    vendor: str,
    model: str,
    settings: DashScopeFileTransSettings,
    timeout_seconds: float,
    cancellation: object | None = None,
) -> AudioProviderResponse:
    """Upload, submit, persist, poll, and parse one FileTrans task.

    The task sidecar is written before the first poll. A matching submitted
    sidecar is always polled instead of submitting a second task. An ambiguous
    submission is retained and future calls fail closed because the provider's
    client request header is not treated as proven idempotency.
    """
    if type(snapshot) is not LongMP3Snapshot:
        raise ConfigError("DashScope FileTrans requires an exact MP3 snapshot.", code="CONFIG_INVALID") from None
    if type(settings) is not DashScopeFileTransSettings:
        raise ConfigError("DashScope FileTrans requires exact FileTrans settings.", code="CONFIG_INVALID") from None
    if not isinstance(prompt, str) or not prompt.strip():
        raise ConfigError("DashScope FileTrans requires a nonempty prompt.", code="CONFIG_INVALID") from None
    if model != DEFAULT_DASHSCOPE_FILETRANS_MODEL:
        raise ProviderRequestInvalid(
            "The selected DashScope FileTrans model is not admitted by this route.",
            details={"provider": vendor, "model": model, "provider_calls_attempted": 0},
        ) from None

    raise_if_cancelled(cancellation)
    identity = _request_identity(snapshot, model=model, prompt=prompt)
    state_path = _state_path(snapshot, settings, identity)
    with _claim_submission(state_path):
        state = _load_state(state_path, identity)
        if state is None:
            state = {
                "version": _STATE_VERSION,
                "identity": identity,
                "source_sha256": snapshot.sha256,
                "model": model,
                "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
                "status": "submission_pending",
            }
            _write_state(state_path, state)
        if state.get("status") == "submission_uncertain":
            raise ProviderError(
                "DashScope FileTrans submission outcome is unknown; refusing to submit a duplicate task.",
                code="PROVIDER_NETWORK",
                details={"provider": vendor, "model": model, "provider_operation": "submit", "submission_ambiguous": True},
            ) from None

        if state.get("status") == "complete" and isinstance(state.get("markdown"), str):
            return AudioProviderResponse(markdown=state["markdown"])

        task_id = state.get("task_id")
        if not isinstance(task_id, str) or not task_id:
            # A rejected task can be retried days later; temporary OSS upload
            # references must not outlive their upload policy/credentials.
            file_url = _upload_oss(snapshot.path, model=model, api_key=settings.api_key)
            state = {key: value for key, value in state.items() if key != "file_url"}
            state = {**state, "status": "ready"}
            _write_state(state_path, state)
            # The provider does not document the client request header as an
            # idempotency key. Mark the POST uncertain before network I/O.
            state = {**state, "status": "submission_uncertain"}
            _write_state(state_path, state)
            try:
                task_id = _submit(
                    file_url,
                    model=model,
                    api_key=settings.api_key,
                    base_url=settings.base_url,
                    request_id=identity,
                    timeout_seconds=timeout_seconds,
                )
            except ProviderError as error:
                status = error.details.get("http_status")
                if (
                    type(status) is int
                    and 400 <= status < 500
                ):
                    _write_state(state_path, {**state, "status": "ready"})
                raise
            state = {**state, "status": "submitted", "task_id": task_id, "submitted_at": time.time()}
            _write_state(state_path, state)

    with _claim_submission(state_path):
        current = _load_state(state_path, identity)
        if current is not None and current.get("status") == "complete" and isinstance(current.get("markdown"), str):
            return AudioProviderResponse(markdown=current["markdown"])
        result = _poll(
            task_id,
            model=model,
            api_key=settings.api_key,
            base_url=settings.base_url,
            timeout_seconds=min(float(timeout_seconds), settings.poll_timeout_seconds),
            poll_interval=settings.poll_interval_seconds,
            cancellation=cancellation,
        )
        markdown = _extract_transcript(result, model=model, api_key=settings.api_key, base_url=settings.base_url, timeout_seconds=timeout_seconds)
        if markdown is None:
            _write_state(state_path, {**state, "status": "failed", "failure": "missing_transcript"})
            raise ProviderError(
                "DashScope FileTrans completed without transcript text.",
                code="PROVIDER_RESPONSE_INVALID",
                details={"provider": vendor, "model": model, "provider_calls_attempted": 1},
            ) from None
        _write_state(state_path, {**state, "status": "complete", "markdown": markdown})
        return AudioProviderResponse(markdown=markdown)


def _request_identity(snapshot: LongMP3Snapshot, *, model: str, prompt: str) -> str:
    value = json.dumps(
        {"source_sha256": snapshot.sha256, "model": model, "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest()},
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _state_path(snapshot: LongMP3Snapshot, settings: DashScopeFileTransSettings, identity: str) -> Path:
    root = Path(settings.task_state_dir) if settings.task_state_dir is not None else snapshot.path.parent / ".ocrllm_filetrans_state"
    return root / f"{identity}.json"


def _load_state(path: Path, identity: str) -> dict[str, object] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except OSError as error:
        raise ResumeStateError("The DashScope FileTrans sidecar could not be read.", code="RESUME_STATE_INVALID") from error
    except ValueError as error:
        raise ResumeStateError("The DashScope FileTrans sidecar is malformed.", code="RESUME_STATE_INVALID") from error
    if not isinstance(value, dict):
        raise ResumeStateError("The DashScope FileTrans sidecar is not an object.", code="RESUME_STATE_INVALID") from None
    if value.get("version") != _STATE_VERSION or value.get("identity") != identity:
        raise ResumeStateError("The DashScope FileTrans sidecar belongs to another request.", code="RESUME_STATE_MISMATCH") from None
    if value.get("status") == "submitted" and not isinstance(value.get("task_id"), str):
        raise ResumeStateError("The DashScope FileTrans sidecar has no task id.", code="RESUME_STATE_INVALID") from None
    if value.get("status") == "complete" and not isinstance(value.get("markdown"), str):
        raise ResumeStateError("The completed DashScope FileTrans sidecar has no transcript.", code="RESUME_STATE_INVALID") from None
    if value.get("status") in {"submission_pending", "ready", "submission_uncertain", "submitted", "complete", "failed"}:
        return value
    raise ResumeStateError("The DashScope FileTrans sidecar has an unknown status.", code="RESUME_STATE_INVALID") from None


@contextmanager
def _claim_submission(state_path: Path):
    """Serialize same-identity submission and sidecar mutation across processes."""
    state_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = state_path.with_name(state_path.name + ".lock")
    descriptor = os.open(lock_path, os.O_CREAT | os.O_RDWR)
    try:
        if os.name == "nt":
            import msvcrt

            msvcrt.locking(descriptor, msvcrt.LK_NBLCK, 1)
            unlock = lambda: msvcrt.locking(descriptor, msvcrt.LK_UNLCK, 1)
        else:
            import fcntl

            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
            unlock = lambda: fcntl.flock(descriptor, fcntl.LOCK_UN)
    except OSError:
        os.close(descriptor)
        raise ProviderError(
            "An identical FileTrans operation already owns the durable state.",
            code="PROVIDER_CONCURRENCY_LIMITED",
            details={"provider": "dashscope", "provider_calls_attempted": 0},
        ) from None
    try:
        yield
    finally:
        unlock()
        os.close(descriptor)


def _write_state(path: Path, value: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent)
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(value, stream, ensure_ascii=True, sort_keys=True)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass


def _upload_oss(path: Path, *, model: str, api_key: str | None) -> str:
    if not api_key:
        raise ConfigError("DashScope FileTrans requires an API key for OSS upload.", code="CONFIG_MISSING") from None
    try:
        from dashscope.utils.oss_utils import OssUtils
    except ImportError:
        raise DependencyMissing("DashScope FileTrans requires the dashscope SDK for OSS upload.") from None
    try:
        file_url, _ = OssUtils.upload(model=model, file_path=str(path), api_key=api_key)
    except Exception as error:
        raise _network_error(error, model=model, operation="oss_upload") from None
    if not isinstance(file_url, str) or not file_url.startswith("oss://"):
        raise ProviderError("DashScope OSS upload returned an invalid file URL.", code="PROVIDER_RESPONSE_INVALID", details={"provider": "dashscope", "model": model}) from None
    return file_url


def _submit(file_url: str, *, model: str, api_key: str | None, base_url: str, request_id: str, timeout_seconds: float) -> str:
    payload = {"model": model, "input": {"file_url": file_url}, "parameters": {"channel_id": [0], "enable_itn": False, "enable_words": True}}
    headers = _headers(api_key, request_id=request_id, oss_url=file_url)
    try:
        data = _request_json("POST", f"{base_url.rstrip('/')}/api/v1/services/audio/asr/transcription", headers=headers, body=payload, timeout=timeout_seconds)
    except ProviderError as error:
        if error.code in {"PROVIDER_NETWORK", "PROVIDER_TIMEOUT", "PROVIDER_UNAVAILABLE"}:
            error._add_safe_detail("submission_ambiguous", True)
        raise
    task_id = data.get("output", {}).get("task_id") if isinstance(data.get("output"), dict) else None
    if not isinstance(task_id, str) or not task_id.strip():
        raise ProviderError("DashScope FileTrans did not return a task id.", code="PROVIDER_RESPONSE_INVALID", details={"provider": "dashscope", "model": model}) from None
    return task_id.strip()


def _poll(task_id: str, *, model: str, api_key: str | None, base_url: str, timeout_seconds: float, poll_interval: float, cancellation: object | None) -> dict[str, object]:
    deadline = time.monotonic() + timeout_seconds
    while True:
        raise_if_cancelled(cancellation)
        try:
            data = _request_json("GET", f"{base_url.rstrip('/')}/api/v1/tasks/{task_id}", headers=_headers(api_key), body=None, timeout=min(120.0, max(1.0, timeout_seconds)))
        except OCRLLMError:
            raise
        except Exception as error:
            raise _network_error(error, model=model, operation="poll") from None
        output = data.get("output") if isinstance(data.get("output"), dict) else {}
        status = str(output.get("task_status") or "")
        if status == "SUCCEEDED":
            return data
        if status in {"FAILED", "SUCCESS_WITH_NO_VALID_FRAGMENT"}:
            code = str(output.get("code") or "").upper()
            if (
                "NO_VALID_FRAGMENT" in code
                or "ASR_RESPONSE_HAVE_NO_WORDS" in code
                or status == "SUCCESS_WITH_NO_VALID_FRAGMENT"
            ):
                raise NoSpeechDetected(details={"provider": "dashscope", "model": model, "provider_calls_attempted": 1}) from None
            raise ProviderError("DashScope FileTrans task failed.", code="PROVIDER_RESPONSE_INVALID", details={"provider": "dashscope", "model": model, "provider_code": code or "task_failed", "provider_calls_attempted": 1}) from None
        if status not in {"PENDING", "RUNNING", "QUEUED", "WAITING"}:
            raise ProviderError("DashScope FileTrans returned an unsupported task status.", code="PROVIDER_RESPONSE_INVALID", details={"provider": "dashscope", "model": model, "provider_code": status or "missing_task_status", "provider_calls_attempted": 1}) from None
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise ProviderError("DashScope FileTrans polling timed out; the task sidecar was retained.", code="PROVIDER_TIMEOUT", details={"provider": "dashscope", "model": model, "task_id": task_id, "provider_calls_attempted": 1}) from None
        time.sleep(min(poll_interval, remaining))
        raise_if_cancelled(cancellation)


def _extract_transcript(data: dict[str, object], *, model: str, api_key: str | None, base_url: str, timeout_seconds: float) -> str | None:
    payloads = [data]
    urls = _collect_values(data, {"transcription_url", "transcript_url", "result_url"})
    for value in urls:
        if not isinstance(value, str):
            continue
        parsed = urlsplit(value)
        host = (parsed.hostname or "").casefold()
        base_host = (urlsplit(base_url).hostname or "").casefold()
        if parsed.scheme != "https" or not host or not (host == base_host or host.endswith(".aliyuncs.com")):
            raise ProviderError("DashScope returned an untrusted transcript URL.", code="PROVIDER_RESPONSE_INVALID", details={"provider": "dashscope", "model": model}) from None
        try:
            # Presigned result URLs are authenticated by their signature; do not
            # leak the DashScope API key to an object-storage host.
            payloads.append(_request_json("GET", value, headers={}, body=None, timeout=timeout_seconds))
        except OCRLLMError:
            raise
        except Exception as error:
            raise _network_error(error, model=model, operation="result_download") from None

    transcripts: list[dict[str, object]] = []
    for payload in payloads:
        _collect_transcripts(payload, transcripts)
    unique: list[dict[str, object]] = []
    seen: set[str] = set()
    for item in transcripts:
        key = json.dumps(item, ensure_ascii=False, sort_keys=True)
        if key not in seen:
            seen.add(key)
            unique.append(item)
    lines: list[str] = []
    for item in unique:
        sentences = item.get("sentences")
        if isinstance(sentences, list):
            for sentence in sentences:
                if isinstance(sentence, dict):
                    text = sentence.get("text") or sentence.get("sentence") or sentence.get("content")
                    if isinstance(text, str) and text.strip():
                        lines.append(text.strip())
        text = item.get("text")
        if isinstance(text, str) and text.strip() and not sentences:
            lines.append(text.strip())
    return "\n".join(lines).strip() or None


def _collect_transcripts(payload: object, output: list[dict[str, object]]) -> None:
    if isinstance(payload, dict):
        status = str(payload.get("subtask_status") or "").upper()
        code = str(payload.get("code") or "")
        code_is_success = code.strip().upper() in {"", "0", "SUCCESS", "SUCCEEDED"}
        if status == "FAILED" or not code_is_success:
            if "NO_VALID_FRAGMENT" in code.upper() or "ASR_RESPONSE_HAVE_NO_WORDS" in code.upper():
                raise NoSpeechDetected(details={"provider": "dashscope", "provider_calls_attempted": 1}) from None
            raise ProviderError("DashScope FileTrans returned a failed transcript subtask.", code="PROVIDER_RESPONSE_INVALID", details={"provider": "dashscope", "provider_code": code or "subtask_failed", "provider_calls_attempted": 1}) from None
        if isinstance(payload.get("sentences"), list):
            output.append({"sentences": payload["sentences"], "text": payload.get("text", "")})
        elif isinstance(payload.get("text"), str) and payload["text"].strip():
            output.append({"text": payload["text"]})
        for key in ("transcripts", "output", "result", "results", "data", "data_list"):
            if key in payload:
                _collect_transcripts(payload[key], output)
    elif isinstance(payload, list):
        for item in payload:
            _collect_transcripts(item, output)


def _collect_values(payload: object, keys: set[str]) -> list[object]:
    values: list[object] = []
    if isinstance(payload, dict):
        for key, item in payload.items():
            if key in keys:
                values.append(item)
            values.extend(_collect_values(item, keys))
    elif isinstance(payload, list):
        for item in payload:
            values.extend(_collect_values(item, keys))
    return values


def _headers(api_key: str | None, *, request_id: str | None = None, oss_url: str | None = None) -> dict[str, str]:
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    if request_id:
        headers["X-DashScope-Client-Request-Id"] = request_id
    if oss_url and oss_url.startswith("oss://"):
        headers["X-DashScope-OssResourceResolve"] = "enable"
        headers["X-DashScope-Async"] = "enable"
    return headers


def _request_json(method: str, url: str, *, headers: dict[str, str], body: dict[str, object] | None, timeout: float) -> dict[str, object]:
    raw_body = None if body is None else json.dumps(body, ensure_ascii=False).encode("utf-8")
    request = Request(url, data=raw_body, headers=headers, method=method)
    try:
        with urlopen(request, timeout=timeout) as response:
            raw = response.read(_MAX_RESPONSE_BYTES + 1)
    except HTTPError as error:
        status = int(error.code)
        code = (
            "PROVIDER_RATE_LIMITED" if status == 429
            else "PROVIDER_AUTHENTICATION" if status == 401
            else "PROVIDER_PERMISSION_DENIED" if status == 403
            else "PROVIDER_REQUEST_INVALID" if 400 <= status < 500
            else "PROVIDER_UNAVAILABLE"
        )
        raise ProviderError("DashScope FileTrans HTTP request failed.", code=code, details={"provider": "dashscope", "http_status": status}) from None
    except (URLError, TimeoutError, OSError):
        raise ProviderError("DashScope FileTrans network request failed.", code="PROVIDER_NETWORK", details={"provider": "dashscope"}) from None
    if len(raw) > _MAX_RESPONSE_BYTES:
        raise ProviderError("DashScope FileTrans returned an oversized response.", code="PROVIDER_RESPONSE_INVALID", details={"provider": "dashscope"}) from None
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        raise ProviderError("DashScope FileTrans returned invalid JSON.", code="PROVIDER_RESPONSE_INVALID", details={"provider": "dashscope"}) from None
    if not isinstance(value, dict):
        raise ProviderError("DashScope FileTrans returned an invalid JSON object.", code="PROVIDER_RESPONSE_INVALID", details={"provider": "dashscope"}) from None
    return value


def _network_error(error: Exception, *, model: str, operation: str) -> ProviderError:
    return ProviderError("DashScope FileTrans network operation failed; saved task identity was retained.", code="PROVIDER_NETWORK", details={"provider": "dashscope", "model": model, "provider_operation": operation})
