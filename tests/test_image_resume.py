"""Black-box recovery tests for completed image recognition work."""

from __future__ import annotations

import importlib
from pathlib import Path

import pytest

from ocrllm import (
    Config,
    CredentialPoolPolicy,
    DashScopeCredential,
    DashScopeCredentialPool,
    DashScopeSettings,
    LocalOCRSettings,
    OutputError,
    ResumeStateError,
    recognize,
)
from ocrllm.processor_output import ProcessorOutput
from ocrllm.errors import ConfigError

from write_test_image import write_test_image


def _vision_config(
    output_dir: Path,
    *,
    api_key: str = "resume-secret-key",
    timeout_seconds: float = 120,
) -> Config:
    return Config(
        provider=DashScopeSettings(
            region="cn-beijing",
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
            api_key=api_key,
        ),
        output_dir=output_dir,
        timeout_seconds=timeout_seconds,
        resume=True,
    )


def _install_fake_dashscope(monkeypatch, calls: list[tuple[Path, ...]]) -> None:
    adapter = importlib.import_module("ocrllm.providers.dashscope.recognize_images")

    def fake_recognize_images(image_paths, *, prompt, config):
        calls.append(tuple(image_paths))
        return "# Resumable board\n"

    monkeypatch.setattr(adapter, "recognize_images", fake_recognize_images)


def _fail_markdown_publication(monkeypatch):
    writer = importlib.import_module("ocrllm.output.write_markdown_atomically")
    original = writer.write_markdown_atomically

    def fail_write(*_args, **_kwargs):
        raise OutputError("test-only publication failure")

    monkeypatch.setattr(writer, "write_markdown_atomically", fail_write)
    return writer, original


def _state_path(output_dir: Path, stem: str = "board_board") -> Path:
    return output_dir / f"{stem}.ocrllm-state.json"


def test_vision_resume_reuses_completed_result_without_provider_calls_or_secrets(
    tmp_path,
    monkeypatch,
) -> None:
    source = write_test_image(tmp_path / "board.png")
    output_dir = tmp_path / "output"
    calls: list[tuple[Path, ...]] = []
    _install_fake_dashscope(monkeypatch, calls)
    writer, original_writer = _fail_markdown_publication(monkeypatch)

    with pytest.raises(OutputError):
        recognize(source, config=_vision_config(output_dir))

    state_path = _state_path(output_dir)
    raw_state = state_path.read_text(encoding="utf-8")
    assert len(calls) == 1
    assert "resume-secret-key" not in raw_state
    assert not (output_dir / "board_board.md").exists()

    monkeypatch.setattr(writer, "write_markdown_atomically", original_writer)
    result = recognize(
        source,
        config=_vision_config(output_dir, api_key="different-secret-key"),
    )

    assert len(calls) == 1
    assert result.markdown == "# Resumable board\n"
    assert result.output_path == output_dir / "board_board.md"
    assert state_path.exists()


def test_local_ocr_resume_reuses_completed_result_without_backend_call(
    tmp_path,
    monkeypatch,
) -> None:
    source = write_test_image(tmp_path / "board.png")
    output_dir = tmp_path / "output"
    calls = []
    backend = importlib.import_module(
        "ocrllm.local_ocr.recognize_images_with_rapidocr"
    )

    def fake_ocr(image_paths, *, profile, config):
        calls.append(tuple(image_paths))
        return ProcessorOutput(
            media_type="image",
            profile=profile,
            markdown="Offline resumed OCR",
            metadata={"engine": "test-rapidocr", "line_count": 1},
        )

    monkeypatch.setattr(backend, "recognize_images_with_rapidocr", fake_ocr)
    writer, original_writer = _fail_markdown_publication(monkeypatch)
    config = Config(image_mode="ocr", output_dir=output_dir, resume=True)

    with pytest.raises(OutputError):
        recognize(source, config=config)

    monkeypatch.setattr(writer, "write_markdown_atomically", original_writer)
    result = recognize(source, config=config)

    assert len(calls) == 1
    assert result.markdown == "Offline resumed OCR"
    assert result.metadata["engine"] == "test-rapidocr"
    assert _state_path(output_dir).exists()


def test_matching_state_and_output_complete_post_publish_crash_window(
    tmp_path,
    monkeypatch,
) -> None:
    source = write_test_image(tmp_path / "board.png")
    output_dir = tmp_path / "output"
    calls: list[tuple[Path, ...]] = []
    _install_fake_dashscope(monkeypatch, calls)

    first = recognize(source, config=_vision_config(output_dir))

    assert first.output_path is not None
    assert _state_path(output_dir).exists()
    second = recognize(source, config=_vision_config(output_dir))

    assert len(calls) == 1
    assert second.markdown == first.markdown
    assert _state_path(output_dir).exists()


def test_resume_rejects_existing_output_without_state_before_provider_call(
    tmp_path,
    monkeypatch,
) -> None:
    source = write_test_image(tmp_path / "board.png")
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    (output_dir / "board_board.md").write_text("unproven", encoding="utf-8")
    calls: list[tuple[Path, ...]] = []
    _install_fake_dashscope(monkeypatch, calls)

    with pytest.raises(ResumeStateError) as captured:
        recognize(source, config=_vision_config(output_dir))

    assert captured.value.code == "RESUME_STATE_INVALID"
    assert calls == []


def test_resume_rejects_changed_source_bytes_and_request_settings(
    tmp_path,
    monkeypatch,
) -> None:
    source = write_test_image(tmp_path / "board.png", color=(1, 2, 3))
    output_dir = tmp_path / "output"
    calls: list[tuple[Path, ...]] = []
    _install_fake_dashscope(monkeypatch, calls)
    _writer, _original = _fail_markdown_publication(monkeypatch)
    with pytest.raises(OutputError):
        recognize(source, config=_vision_config(output_dir))

    write_test_image(source, color=(7, 8, 9))
    with pytest.raises(ResumeStateError) as source_error:
        recognize(source, config=_vision_config(output_dir))
    assert source_error.value.code == "RESUME_STATE_MISMATCH"

    write_test_image(source, color=(1, 2, 3))
    with pytest.raises(ResumeStateError) as config_error:
        recognize(source, config=_vision_config(output_dir, timeout_seconds=30))
    assert config_error.value.code == "RESUME_STATE_MISMATCH"
    assert len(calls) == 1


def test_resume_rejects_changed_order_with_same_output_stem(
    tmp_path,
    monkeypatch,
) -> None:
    first = write_test_image(tmp_path / "first.png", color=(1, 1, 1))
    second = write_test_image(tmp_path / "second.png", color=(2, 2, 2))
    third = write_test_image(tmp_path / "third.png", color=(3, 3, 3))
    output_dir = tmp_path / "output"
    calls: list[tuple[Path, ...]] = []
    _install_fake_dashscope(monkeypatch, calls)
    _fail_markdown_publication(monkeypatch)
    with pytest.raises(OutputError):
        recognize([first, second, third], config=_vision_config(output_dir))

    with pytest.raises(ResumeStateError) as captured:
        recognize([first, third, second], config=_vision_config(output_dir))

    assert captured.value.code == "RESUME_STATE_MISMATCH"
    assert len(calls) == 1


def test_resume_rejects_corrupt_duplicate_key_and_oversized_state(
    tmp_path,
    monkeypatch,
) -> None:
    source = write_test_image(tmp_path / "board.png")
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    state_path = _state_path(output_dir)
    calls: list[tuple[Path, ...]] = []
    _install_fake_dashscope(monkeypatch, calls)

    for raw in (
        b"not-json",
        b'{"state_version":"one","state_version":"two"}',
    ):
        state_path.write_bytes(raw)
        with pytest.raises(ResumeStateError) as captured:
            recognize(source, config=_vision_config(output_dir))
        assert captured.value.code == "RESUME_STATE_INVALID"

    loader = importlib.import_module("ocrllm.output.load_image_resume_state")
    monkeypatch.setattr(loader, "_MAX_STATE_BYTES", 1)
    state_path.write_bytes(b"{}")
    with pytest.raises(ResumeStateError) as oversized:
        recognize(source, config=_vision_config(output_dir))
    assert oversized.value.code == "RESUME_STATE_INVALID"
    assert calls == []


def test_resume_rejects_edited_final_output(tmp_path, monkeypatch) -> None:
    source = write_test_image(tmp_path / "board.png")
    output_dir = tmp_path / "output"
    calls: list[tuple[Path, ...]] = []
    _install_fake_dashscope(monkeypatch, calls)
    result = recognize(source, config=_vision_config(output_dir))
    assert result.output_path is not None
    result.output_path.write_text("edited", encoding="utf-8")

    with pytest.raises(ResumeStateError) as captured:
        recognize(source, config=_vision_config(output_dir))

    assert captured.value.code == "RESUME_STATE_MISMATCH"
    assert len(calls) == 1


def test_atomic_state_save_failure_publishes_no_output_or_temporary_state(
    tmp_path,
    monkeypatch,
) -> None:
    source = write_test_image(tmp_path / "board.png")
    output_dir = tmp_path / "output"
    calls: list[tuple[Path, ...]] = []
    _install_fake_dashscope(monkeypatch, calls)
    saver = importlib.import_module("ocrllm.output.save_image_resume_state_atomically")
    def fail_state_replace(*_args):
        raise OSError("test-only state replace failure")

    monkeypatch.setattr(saver.os, "replace", fail_state_replace)

    with pytest.raises(OutputError) as captured:
        recognize(source, config=_vision_config(output_dir))

    assert captured.value.code == "OUTPUT_WRITE_FAILED"
    assert len(calls) == 1
    assert not (output_dir / "board_board.md").exists()
    assert not _state_path(output_dir).exists()
    assert list(output_dir.glob(".*.tmp")) == []


def test_resume_rejects_identity_less_injected_provider_without_invocation(
    tmp_path,
) -> None:
    source = write_test_image(tmp_path / "board.png")

    class Provider:
        calls = 0

        def recognize_images(self, image_paths, *, prompt, config):
            self.calls += 1
            return "must not run"

    provider = Provider()
    with pytest.raises(ConfigError):
        recognize(
            source,
            config=Config(provider=provider, output_dir=tmp_path / "out", resume=True),
        )

    assert provider.calls == 0


def test_credential_pool_identity_and_secrets_are_excluded_from_state(
    tmp_path,
    monkeypatch,
) -> None:
    source = write_test_image(tmp_path / "board.png")
    output_dir = tmp_path / "output"
    calls: list[tuple[Path, ...]] = []
    _install_fake_dashscope(monkeypatch, calls)
    _fail_markdown_publication(monkeypatch)
    pool = DashScopeCredentialPool(
        region="cn-beijing",
        credentials=(
            DashScopeCredential(credential_id="primary", api_key="pool-secret-one"),
            DashScopeCredential(credential_id="backup", api_key="pool-secret-two"),
        ),
        policy=CredentialPoolPolicy(cooldown_seconds=0),
    )
    config = Config(
        provider=DashScopeSettings(
            region="cn-beijing",
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
            credential_pool=pool,
        ),
        output_dir=output_dir,
        resume=True,
    )

    with pytest.raises(OutputError):
        recognize(source, config=config)

    raw = _state_path(output_dir).read_text(encoding="utf-8")
    assert "pool-secret-one" not in raw
    assert "pool-secret-two" not in raw
    assert "primary" not in raw
    assert "backup" not in raw


def test_local_ocr_confidence_is_bound_to_resume_identity(
    tmp_path,
    monkeypatch,
) -> None:
    source = write_test_image(tmp_path / "board.png")
    output_dir = tmp_path / "output"
    backend = importlib.import_module(
        "ocrllm.local_ocr.recognize_images_with_rapidocr"
    )
    calls = []

    def fake_ocr(image_paths, *, profile, config):
        calls.append(1)
        return ProcessorOutput(
            media_type="image",
            profile=profile,
            markdown="confidence-bound",
        )

    monkeypatch.setattr(backend, "recognize_images_with_rapidocr", fake_ocr)
    _fail_markdown_publication(monkeypatch)
    with pytest.raises(OutputError):
        recognize(
            source,
            config=Config(
                image_mode="ocr",
                local_ocr=LocalOCRSettings(minimum_confidence=0.5),
                output_dir=output_dir,
                resume=True,
            ),
        )

    with pytest.raises(ResumeStateError) as captured:
        recognize(
            source,
            config=Config(
                image_mode="ocr",
                local_ocr=LocalOCRSettings(minimum_confidence=0.8),
                output_dir=output_dir,
                resume=True,
            ),
        )

    assert captured.value.code == "RESUME_STATE_MISMATCH"
    assert calls == [1]
