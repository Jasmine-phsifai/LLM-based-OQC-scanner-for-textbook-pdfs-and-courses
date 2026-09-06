"""Prove bounded retries and partial resume with real inference behind HTTP faults.

Per model, requests 1, 3 and 4 fail deliberately (429, 503, 504). Successful
requests reach the actual service. This tests the harness, not real GPU overload.
Only verdicts, counts and hash stability are printed; course text stays private.
"""
from __future__ import annotations

import argparse
import hashlib
import http.client
import json
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit


def _args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--image", required=True, action="append", type=Path)
    parser.add_argument("--audio", required=True, type=Path)
    parser.add_argument("--image-model", default="qwen3.8-27b-q6-k-medium-ocr")
    parser.add_argument("--audio-model", default="qwen3-asr-1.7b")
    parser.add_argument("--timeout", type=float, default=600.0)
    args = parser.parse_args()
    if len(args.image) != 2 or not 0 < args.timeout <= 600:
        parser.error("Supply exactly two selected images and timeout in (0, 600].")
    upstream = urlsplit(args.base_url)
    if upstream.scheme != "http" or upstream.hostname not in {"localhost", "127.0.0.1"}:
        parser.error("This fault scenario requires an HTTP loopback service.")
    return args


class _Proxy(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, upstream, timeout):
        self.upstream = urlsplit(upstream)
        self.timeout_seconds = timeout
        self.counts = {}
        self.injected = []
        self.lock = threading.Lock()
        super().__init__(("127.0.0.1", 0), _Handler)

    def next_request(self, model):
        with self.lock:
            ordinal = self.counts.get(model, 0) + 1
            self.counts[model] = ordinal
            status = {1: 429, 3: 503, 4: 504}.get(ordinal)
            if status is not None:
                self.injected.append(status)
            return ordinal, status


class _Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        body = self.rfile.read(int(self.headers["Content-Length"]))
        model = json.loads(body)["model"]
        ordinal, injected = self.server.next_request(model)
        if injected:
            data = json.dumps({"error": {
                "message": "Deliberate scenario fault",
                "type": "server_error", "code": "scenario_transient",
            }}).encode()
            self._reply(injected, data, {"x-request-id": f"scenario-{ordinal}"})
            return
        conn = http.client.HTTPConnection(
            self.server.upstream.netloc, timeout=self.server.timeout_seconds,
        )
        try:
            conn.request("POST", self.path, body=body, headers={"Content-Type": "application/json"})
            response = conn.getresponse()
            data = response.read()
            headers = {key: value for key, value in response.getheaders()
                       if key.lower() == "x-request-id"}
            self._reply(response.status, data, headers)
        except (OSError, http.client.HTTPException):
            self._reply(502, b'{"error":{"message":"upstream failed","code":"scenario_upstream_failed"}}', {})
        finally:
            conn.close()

    def _reply(self, status, data, headers):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        for key, value in headers.items():
            self.send_header(key, value)
        self.end_headers()
        try:
            self.wfile.write(data)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def log_message(self, *args):
        pass


def _fingerprint(path):
    with path.open("rb") as source:
        digest = hashlib.sha256()
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _provider(settings, model, image):
    from ocrllm import ProviderModel
    return ProviderModel(
        vendor="local-recovery-proxy", model=model,
        adapter_id="openai_compatible_chat", settings=settings,
        supports_plain_ocr=image, supports_detail_ocr=image,
        supports_audio=not image, default_image_batch_size=1 if image else None,
        default_audio_minutes=None if image else 1,
        retry_rules={"PROVIDER_RATE_LIMITED": ("current", 1, 0),
                     "PROVIDER_UNAVAILABLE": ("current", 1, 0),
                     "PROVIDER_TIMEOUT": ("current", 1, 0)},
    )


def _check(first, resumed, state):
    failed = first.metadata.get("failed_slots", ())
    description = failed[0].get("description", "") if len(failed) == 1 else ""
    checks = {
        "initial_partial": first.status == "partial",
        "initial_calls_four": first.metadata.get("provider_call_count") == 4,
        "gateway_timeout_code": len(failed) == 1 and failed[0].get("code") == "PROVIDER_TIMEOUT",
        "checkpoint_kept_diagnostics": (
            "provider_code=scenario_transient" in state
            and "request_id=scenario-4" in state
            and "provider_code=scenario_transient" in description
        ),
        "resume_complete": resumed.status == "complete",
        "resume_calls_one": resumed.metadata.get("provider_call_count") == 1,
        "resume_reuses_one": resumed.metadata.get("reused_slot_count") == 1,
        "nonempty": bool(resumed.markdown.strip()),
    }
    return {"passed": all(checks.values()), "checks": checks}


def run(args):
    from ocrllm import (
        OpenAICompatibleSettings, batchify_images, split_audio,
        recognize_audio_to_markdown, recognize_images_to_markdown,
        resume_audio_to_markdown, resume_images_to_markdown,
    )
    from ocrllm.audio.probe_product_mp3 import probe_product_mp3
    from ocrllm.errors import OCRLLMError
    from ocrllm.output.resolve_resume_state_path import resolve_resume_state_path

    # Refuse full lectures: prepare a bounded clip outside the source archive.
    duration = probe_product_mp3(args.audio)
    if not 60 < duration <= 120:
        return {"status": "failed", "code": "SCENARIO_REQUIRES_60_TO_120_SECOND_MP3"}
    paths = tuple(args.image) + (args.audio,)
    before = tuple(_fingerprint(path) for path in paths)
    proxy = _Proxy(args.base_url, args.timeout)
    thread = threading.Thread(target=proxy.serve_forever, daemon=True)
    thread.start()
    base_url = f"http://127.0.0.1:{proxy.server_address[1]}{proxy.upstream.path.rstrip('/')}"
    settings = OpenAICompatibleSettings(base_url=base_url)
    report = {}
    try:
        with tempfile.TemporaryDirectory(prefix="ocrllm-recovery-") as root:
            for media, model in (("audio", args.audio_model), ("image", args.image_model)):
                provider = _provider(settings, model, media == "image")
                output = Path(root) / f"{media}.md"
                if media == "audio":
                    plan = split_audio(args.audio, interval_minutes=1, include_boundary_context=False)
                    first = recognize_audio_to_markdown(plan, provider=provider, output_path=output, timeout_seconds=args.timeout)
                else:
                    plan = batchify_images(tuple(args.image), batch_size=1)
                    first = recognize_images_to_markdown(plan, provider=provider, image_task="detail_ocr", output_path=output, timeout_seconds=args.timeout)
                state = resolve_resume_state_path(output).read_text(encoding="utf-8")
                resume = resume_audio_to_markdown if media == "audio" else resume_images_to_markdown
                resumed = resume(plan, provider=provider, output_path=output, timeout_seconds=args.timeout)
                report[media] = _check(first, resumed, state)
    except OCRLLMError as error:
        report["error_code"] = error.code
    except (OSError, ValueError) as error:
        report["error_code"] = type(error).__name__
    finally:
        proxy.shutdown()
        proxy.server_close()
        thread.join(timeout=5)
    report["source_unchanged"] = before == tuple(_fingerprint(path) for path in paths)
    report["proxy_requests"] = sum(proxy.counts.values())
    report["injected_statuses"] = proxy.injected
    passed = (
        all(report.get(media, {}).get("passed") for media in ("audio", "image"))
        and report["source_unchanged"]
        and report["proxy_requests"] == 10
        and proxy.injected == [429, 503, 504, 429, 503, 504]
    )
    report["status"] = "passed" if passed else "failed"
    return report


if __name__ == "__main__":
    result = run(_args())
    print(json.dumps(result, sort_keys=True))
    raise SystemExit(0 if result["status"] == "passed" else 1)
