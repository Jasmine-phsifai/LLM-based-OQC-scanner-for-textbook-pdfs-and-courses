"""Verify HTTP-200 request-ID evidence across image, merged, and audio paths."""

from __future__ import annotations

import argparse
import base64
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import threading


IMAGE_REQUEST_ID = "req-http200-empty-20260908"
MERGED_REQUEST_ID = "req-merged-http200-20260908"
AUDIO_REQUEST_ID = "req-audio-http200-20260908"
PNG_1X1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk"
    "+A8AAQUBAScY42YAAAAASUVORK5CYII="
)


class SyntheticOpenAIHandler(BaseHTTPRequestHandler):
    content = ""
    request_id: str | None = IMAGE_REQUEST_ID
    model = "synthetic-model"
    finish_reason = "stop"
    refusal: str | None = None

    def do_POST(self) -> None:  # noqa: N802 - stdlib handler API
        length = int(self.headers["Content-Length"])
        json.loads(self.rfile.read(length))
        body = json.dumps(
            {
                "id": "chatcmpl-http200-evidence",
                "object": "chat.completion",
                "created": 0,
                "model": self.model,
                "choices": [{
                    "index": 0,
                    "message": {"role": "assistant", "content": self.content, "refusal": self.refusal},
                    "finish_reason": self.finish_reason,
                }],
                "usage": {"prompt_tokens": 7, "completion_tokens": 2},
            }
        ).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        if self.request_id is not None:
            self.send_header("x-request-id", self.request_id)
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_args: object) -> None:
        return


def _import_source(source_root: Path):
    source_root = source_root.resolve()
    sys.path.insert(0, str(source_root))
    import ocrllm

    package_path = Path(ocrllm.__file__).resolve()
    if not package_path.is_relative_to(source_root):
        raise AssertionError(f"ocrllm imported from {package_path}, expected below {source_root}")
    print(json.dumps({"ocrllm_file": str(package_path)}, sort_keys=True))
    return ocrllm


def _provider(server: ThreadingHTTPServer, *, validation: str = "markdown"):
    from ocrllm.providers.openai_compatible.provider_settings import OpenAICompatibleSettings
    from ocrllm.providers.provider_model import ProviderModel

    return ProviderModel(
        vendor="synthetic", model="synthetic-model", adapter_id="openai_compatible_chat",
        settings=OpenAICompatibleSettings(
            base_url=f"http://127.0.0.1:{server.server_port}/v1/", api_key="synthetic-key",
            response_validation=validation,
        ),
        supports_plain_ocr=True, supports_detail_ocr=False, supports_audio=False,
        default_image_batch_size=1, default_audio_minutes=None, retry_rules={},
    )


def _run_image(server: ThreadingHTTPServer, source: Path) -> None:
    from types import SimpleNamespace
    from ocrllm.errors import ProviderError
    from ocrllm.provider_failure_evidence import bounded_provider_failure_description
    from ocrllm.providers.call_vision_provider import call_vision_provider
    from ocrllm.providers.openai_compatible.openai_compatible_provider import OpenAICompatibleProvider
    from ocrllm.providers.openai_compatible.provider_settings import OpenAICompatibleSettings
    from ocrllm.providers.resolved_vision_provider import ResolvedVisionProvider

    SyntheticOpenAIHandler.content = ""
    SyntheticOpenAIHandler.request_id = IMAGE_REQUEST_ID
    provider = OpenAICompatibleProvider(
        vendor="synthetic", model="synthetic-model",
        settings=OpenAICompatibleSettings(
            base_url=f"http://127.0.0.1:{server.server_port}/v1/", api_key="synthetic-key"
        ),
    )
    try:
        call_vision_provider(
            ResolvedVisionProvider(value=provider, name="synthetic", model="synthetic-model", built_in=True),
            (source,), prompt="Return Markdown.",
            config=SimpleNamespace(timeout_seconds=5.0, cancellation=None),
        )
    except ProviderError as error:
        description = bounded_provider_failure_description(error)
        assert error.code == "PROVIDER_RESPONSE_INVALID"
        assert error.details["provider"] == "synthetic"
        assert error.details["model"] == "synthetic-model"
        assert error.details["provider_calls_attempted"] == 1
        assert error.details["request_id"] == IMAGE_REQUEST_ID
        assert f"request_id={IMAGE_REQUEST_ID}" in description
        print(json.dumps({"case": "image", "description": description}, sort_keys=True))
    else:
        raise AssertionError("empty HTTP-200 image content was accepted")


def _run_merged(server: ThreadingHTTPServer, source: Path, ocrllm) -> None:
    provider = _provider(server)
    cases = (("marker-only", "<!-- provider marker -->", MERGED_REQUEST_ID),
             ("true-empty", "", MERGED_REQUEST_ID), ("unsafe-header", "", "bad/request id"))
    with tempfile.TemporaryDirectory() as temporary:
        for name, content, request_id in cases:
            SyntheticOpenAIHandler.content = content
            SyntheticOpenAIHandler.request_id = request_id
            output = Path(temporary) / f"{name}.md"
            try:
                ocrllm.recognize_images_to_markdown(
                    ((source,),), provider=provider, image_task="plain_ocr",
                    output_path=output, timeout_seconds=5.0,
                )
            except ocrllm.AllCandidatesExhausted:
                pass
            state_path = output.with_name(f"{output.stem}.ocrllm-state.json")
            state = json.loads(state_path.read_text(encoding="utf-8"))
            slot, description = state["slots"][0], state["slots"][0]["error_description"]
            assert slot["status"] == "failed"
            assert slot["error_code"] == "PROVIDER_RESPONSE_INVALID"
            assert slot["vendor"] == "synthetic" and slot["model"] == "synthetic-model"
            assert state["usage"] == [{"calls": 1, "input_tokens": 7, "model": "synthetic-model", "output_tokens": 2, "vendor": "synthetic"}]
            assert state["provider_cleanup_failed"] is False
            if name == "unsafe-header":
                assert "request_id=" not in description
            else:
                assert f"request_id={MERGED_REQUEST_ID}" in description
            print(json.dumps({"case": name, "description": description, "usage": state["usage"], "provider_cleanup_failed": state["provider_cleanup_failed"]}, sort_keys=True))


def _run_nonempty_text(server: ThreadingHTTPServer, source: Path, ocrllm) -> None:
    """An opted-in provider owns content semantics; the harness accepts metadata."""
    provider = _provider(server, validation="nonempty_text")
    with tempfile.TemporaryDirectory() as temporary:
        output = Path(temporary) / "metadata.md"
        SyntheticOpenAIHandler.content = ""
        try:
            ocrllm.recognize_images_to_markdown(
                ((source,),), provider=provider, image_task="plain_ocr",
                output_path=output, timeout_seconds=5.0,
            )
        except ocrllm.AllCandidatesExhausted:
            pass
        state_path = output.with_name(f"{output.stem}.ocrllm-state.json")
        state = json.loads(state_path.read_text())
        assert state["slots"][0]["status"] == "failed"
        SyntheticOpenAIHandler.content = "<!-- arbitrary provider metadata -->"
        result = ocrllm.resume_images_to_markdown(
            ((source,),), provider=provider, output_path=output, timeout_seconds=5.0,
        )
        assert result.status == "complete"
        assert SyntheticOpenAIHandler.content in result.markdown
        print(json.dumps({"case": "nonempty-text-metadata-resume", "status": result.status}))


def _run_audio(server: ThreadingHTTPServer, source: Path) -> None:
    from ocrllm.audio.snapshot_long_mp3 import LongMP3Snapshot
    from ocrllm.errors import ProviderError
    from ocrllm.providers.openai_compatible.provider_settings import OpenAICompatibleSettings
    from ocrllm.providers.openai_compatible.recognize_openai_compatible_audio import recognize_openai_compatible_audio

    SyntheticOpenAIHandler.content = "NOSPEECH4OCRLLM inside transcript"
    SyntheticOpenAIHandler.request_id = AUDIO_REQUEST_ID
    payload = source.read_bytes()
    snapshot = LongMP3Snapshot(path=source, byte_size=len(payload), sha256=hashlib.sha256(payload).hexdigest(), duration_seconds=1.0)
    try:
        recognize_openai_compatible_audio(
            snapshot, prompt="Transcribe this audio.", vendor="synthetic-audio",
            model="synthetic-audio-model",
            settings=OpenAICompatibleSettings(
                base_url=f"http://127.0.0.1:{server.server_port}/v1/", api_key="synthetic-key"
            ), timeout_seconds=5.0,
        )
    except ProviderError as error:
        assert error.code == "PROVIDER_RESPONSE_INVALID"
        assert error.details["provider_calls_attempted"] == 1
        assert error.details["provider"] == "synthetic-audio"
        assert error.details["model"] == "synthetic-audio-model"
        assert error.details["request_id"] == AUDIO_REQUEST_ID
        assert error.details["settled_model_usage"][0]["input_count"] == 7
        assert error.details["settled_model_usage"][0]["output_count"] == 2
        print(json.dumps({"case": "audio", "details": dict(error.details), "status": "rejected"}, default=str, sort_keys=True))
    else:
        raise AssertionError("invalid audio sentinel was accepted")



def _run_audio_visible_text(server: ThreadingHTTPServer, source: Path) -> None:
    """Synthetic HTTP + real SDK prove opt-in changes only refusal phrases."""
    from ocrllm.audio.snapshot_long_mp3 import LongMP3Snapshot
    from ocrllm.errors import NoSpeechDetected, ProviderError
    from ocrllm.providers.openai_compatible.provider_settings import OpenAICompatibleSettings
    from ocrllm.providers.openai_compatible.recognize_openai_compatible_audio import recognize_openai_compatible_audio

    payload = source.read_bytes()
    snapshot = LongMP3Snapshot(path=source, byte_size=len(payload), sha256=hashlib.sha256(payload).hexdigest(), duration_seconds=1.0)
    cases = [
        ("classroom-apology", "对不起，刚才这个式子应该是负号。", None),
        ("classroom-quotation", "The lecturer says: I cannot prove this without continuity.", None),
        ("normal-unicode", "<!-- note --> α + 中文 123", None),
        ("empty", "  ", "PROVIDER_RESPONSE_INVALID"),
        ("comments-only", "<!-- transcript metadata -->", "PROVIDER_RESPONSE_INVALID"),
        ("invalid-characters", "\x00\u200b。", "PROVIDER_RESPONSE_INVALID"),
        ("invalid-utf8", "\ud800", "PROVIDER_RESPONSE_INVALID"),
        ("mixed-sentinel", "speech NOSPEECH4OCRLLM", "PROVIDER_RESPONSE_INVALID"),
        ("pure-sentinel", "  nospeech4ocrllm ", "no_speech"),
        ("truncated", "有效正文", "PROVIDER_RESPONSE_INVALID"),
        ("explicit-refusal", "有效正文", "PROVIDER_REFUSED_RECOGNITION"),
    ]
    try:
        for mode in ("markdown", "visible_text"):
            for name, content, expected in cases:
                if mode == "markdown" and name.startswith("classroom-"):
                    expected = "PROVIDER_REFUSED_RECOGNITION"
                SyntheticOpenAIHandler.content = content
                SyntheticOpenAIHandler.finish_reason = "length" if name == "truncated" else "stop"
                SyntheticOpenAIHandler.refusal = "explicit" if name == "explicit-refusal" else None
                try:
                    response = recognize_openai_compatible_audio(
                        snapshot, prompt=None, vendor="synthetic-audio", model="synthetic-audio-model",
                        settings=OpenAICompatibleSettings(
                            base_url=f"http://127.0.0.1:{server.server_port}/v1/", api_key="synthetic-key",
                            send_audio_prompt=False, response_validation="nonempty_text",
                            audio_response_validation=mode,
                        ), timeout_seconds=5.0,
                    )
                except NoSpeechDetected:
                    assert expected == "no_speech", (mode, name, expected)
                except ProviderError as error:
                    assert error.code == expected, (mode, name, error.code, expected)
                    assert error.details["provider_calls_attempted"] == 1
                else:
                    assert expected is None, (mode, name, expected)
                    assert response.markdown == content
                print(json.dumps({"case": name, "audio_validation": mode, "expected": expected or "accepted", "passed": True}))
    finally:
        SyntheticOpenAIHandler.finish_reason = "stop"
        SyntheticOpenAIHandler.refusal = None


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--expected-source-root", type=Path, default=Path(__file__).resolve().parents[1] / "src")
    args = parser.parse_args()
    ocrllm = _import_source(args.expected_source_root)
    server = ThreadingHTTPServer(("127.0.0.1", 0), SyntheticOpenAIHandler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        with tempfile.TemporaryDirectory() as temporary:
            image = Path(temporary) / "input.png"
            image.write_bytes(PNG_1X1)
            audio = Path(temporary) / "clip.mp3"
            audio.write_bytes(b"synthetic authorized audio boundary")
            _run_image(server, image)
            _run_merged(server, image, ocrllm)
            _run_nonempty_text(server, image, ocrllm)
            _run_audio(server, audio)
            _run_audio_visible_text(server, audio)
    finally:
        server.shutdown()
        server.server_close()


if __name__ == "__main__":
    main()
