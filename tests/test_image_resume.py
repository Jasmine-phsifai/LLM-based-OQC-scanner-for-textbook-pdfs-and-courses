"""Black-box recovery tests for completed image recognition work."""

from __future__ import annotations

import hashlib
import importlib
import json
import os
import threading
from pathlib import Path

import pytest

from ocrllm import (
    Cancelled,
    Config,
    CredentialPoolPolicy,
    DashScopeCredential,
    DashScopeCredentialPool,
    DashScopeSettings,
    LocalOCRSettings,
    OutputError,
    OutputExists,
    RecognitionResult,
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
    cancellation: object | None = None,
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
        cancellation=cancellation,
    )


def _install_fake_dashscope(monkeypatch, calls: list[tuple[Path, ...]]) -> None:
    adapter = importlib.import_module("ocrllm.providers.dashscope.recognize_images")

    def fake_recognize_images(image_paths, *, prompt, config):
        calls.append(tuple(image_paths))
        return "# Resumable board\n"

    monkeypatch.setattr(adapter, "recognize_images", fake_recognize_images)


def test_resume_rejects_snapshot_mutation_after_identity_before_checkpoint(
    tmp_path,
    monkeypatch,
) -> None:
    source = write_test_image(tmp_path / "board.png", color=(1, 2, 3))
    replacement = write_test_image(tmp_path / "replacement.png", color=(7, 8, 9))
    replacement_bytes = replacement.read_bytes()
    replacement_sha256 = hashlib.sha256(replacement_bytes).hexdigest()
    output_dir = tmp_path / "output"
    provider_calls: list[str] = []

    adapter = importlib.import_module("ocrllm.providers.dashscope.recognize_images")

    def recognize_changed_snapshot(image_paths, *, prompt, config):
        provider_calls.append(hashlib.sha256(image_paths[0].read_bytes()).hexdigest())
        return "# Changed snapshot\n"

    monkeypatch.setattr(adapter, "recognize_images", recognize_changed_snapshot)

    fingerprint_module = importlib.import_module(
        "ocrllm.fingerprint_image_sources"
    )
    original_fingerprint = fingerprint_module.fingerprint_image_sources
    fingerprint_calls = 0

    def mutate_after_identity(source_paths, snapshot_paths):
        nonlocal fingerprint_calls
        fingerprints = original_fingerprint(source_paths, snapshot_paths)
        fingerprint_calls += 1
        snapshot_paths[0].write_bytes(replacement_bytes)
        return fingerprints

    monkeypatch.setattr(
        fingerprint_module,
        "fingerprint_image_sources",
        mutate_after_identity,
    )

    with pytest.raises(OutputError) as raised:
        recognize(source, config=_vision_config(output_dir))

    assert raised.value.code == "OUTPUT_WRITE_FAILED"
    assert raised.value.details["workflow_pass"] == "draft"
    assert raised.value.details["provider_calls_attempted"] == 1
    assert fingerprint_calls == 1
    assert provider_calls == [replacement_sha256]
    assert source.read_bytes() != replacement_bytes
    assert not (output_dir / "board_board.md").exists()
    assert not _state_path(output_dir).exists()


def _fail_markdown_publication(monkeypatch):
    writer = importlib.import_module("ocrllm.output.write_markdown_atomically")
    original = writer.write_markdown_atomically

    def fail_write(*_args, **_kwargs):
        raise OutputError("test-only publication failure")

    monkeypatch.setattr(writer, "write_markdown_atomically", fail_write)
    return writer, original


def _state_path(output_dir: Path, stem: str = "board_board") -> Path:
    return output_dir / f"{stem}.ocrllm-state.json"


def _windows_path_units(path: Path) -> int:
    return len(str(path).encode("utf-16-le")) // 2


def _make_directory_with_windows_path_units(
    base: Path,
    target_units: int,
) -> Path:
    current = base
    while _windows_path_units(current) < target_units:
        remaining = target_units - _windows_path_units(current) - 1
        if remaining < 1:
            raise AssertionError(
                "target path length cannot be reached by adding a directory"
            )
        current /= "d" * min(40, remaining)
    assert _windows_path_units(current) == target_units
    current.mkdir(parents=True)
    return current


def _enforce_legacy_windows_open_limit(monkeypatch) -> None:
    original_open = Path.open

    def open_with_legacy_limit(path, *args, **kwargs):
        if _windows_path_units(path) > 259:
            raise OSError(
                206,
                "test-only simulated legacy Windows path limit",
                str(path),
            )
        return original_open(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", open_with_legacy_limit)


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


def test_completed_resume_honors_pre_set_cancellation_without_losing_state(
    tmp_path,
    monkeypatch,
) -> None:
    source = write_test_image(tmp_path / "board.png")
    output_dir = tmp_path / "output"
    calls: list[tuple[Path, ...]] = []
    _install_fake_dashscope(monkeypatch, calls)

    initial = recognize(source, config=_vision_config(output_dir))
    assert initial.output_path is not None
    state_path = _state_path(output_dir)
    output_before = initial.output_path.read_bytes()
    state_before = state_path.read_bytes()

    cancellation = threading.Event()
    cancellation.set()
    with pytest.raises(Cancelled) as captured:
        recognize(
            source,
            config=_vision_config(output_dir, cancellation=cancellation),
        )

    assert captured.value.code == "CANCELLED"
    assert len(calls) == 1
    assert initial.output_path.read_bytes() == output_before
    assert state_path.read_bytes() == state_before

    resumed = recognize(source, config=_vision_config(output_dir))

    assert resumed.markdown == initial.markdown
    assert resumed.output_path == initial.output_path
    assert len(calls) == 1
    assert initial.output_path.read_bytes() == output_before
    assert state_path.read_bytes() == state_before


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


def test_local_ocr_rejects_snapshot_mutation_after_identity(
    tmp_path,
    monkeypatch,
) -> None:
    source = write_test_image(tmp_path / "board.png", color=(1, 2, 3))
    replacement = write_test_image(tmp_path / "replacement.png", color=(7, 8, 9))
    replacement_bytes = replacement.read_bytes()
    output_dir = tmp_path / "output"

    backend = importlib.import_module(
        "ocrllm.local_ocr.recognize_images_with_rapidocr"
    )

    def fake_ocr(image_paths, *, profile, config):
        assert image_paths[0].read_bytes() == replacement_bytes
        return ProcessorOutput(
            media_type="image",
            profile=profile,
            markdown="Changed offline snapshot",
        )

    monkeypatch.setattr(backend, "recognize_images_with_rapidocr", fake_ocr)
    fingerprint_module = importlib.import_module(
        "ocrllm.fingerprint_image_sources"
    )
    original_fingerprint = fingerprint_module.fingerprint_image_sources

    def mutate_after_identity(source_paths, snapshot_paths):
        fingerprints = original_fingerprint(source_paths, snapshot_paths)
        snapshot_paths[0].write_bytes(replacement_bytes)
        return fingerprints

    monkeypatch.setattr(
        fingerprint_module,
        "fingerprint_image_sources",
        mutate_after_identity,
    )

    with pytest.raises(OutputError) as raised:
        recognize(
            source,
            config=Config(image_mode="ocr", output_dir=output_dir, resume=True),
        )

    assert raised.value.code == "OUTPUT_WRITE_FAILED"
    assert not (output_dir / "board_board.md").exists()
    assert not _state_path(output_dir).exists()


@pytest.mark.skipif(
    os.name != "nt",
    reason="Windows legacy path-limit regression",
)
def test_resume_state_temp_does_not_amplify_near_limit_sidecar_path(
    tmp_path,
    monkeypatch,
) -> None:
    if _windows_path_units(tmp_path) >= 213:
        pytest.skip("pytest temporary root is already beyond the controlled path range")
    source = write_test_image(tmp_path / "board.png")
    output_dir = _make_directory_with_windows_path_units(tmp_path, 213)
    calls: list[tuple[Path, ...]] = []
    _install_fake_dashscope(monkeypatch, calls)
    _enforce_legacy_windows_open_limit(monkeypatch)

    first = recognize(source, config=_vision_config(output_dir))
    second = recognize(source, config=_vision_config(output_dir))

    assert first.output_path == output_dir / "board_board.md"
    assert first.output_path.read_text(encoding="utf-8") == "# Resumable board\n"
    assert _state_path(output_dir).is_file()
    assert _windows_path_units(_state_path(output_dir)) == 243
    assert second.markdown == first.markdown
    assert len(calls) == 1


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


def test_state_directory_is_rejected_before_provider_in_both_modes(
    tmp_path,
) -> None:
    source = write_test_image(tmp_path / "board.png")
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    _state_path(output_dir).mkdir()

    class Provider:
        resume_identity = "state-target-preflight-v1"
        calls = 0

        def recognize_images(self, image_paths, *, prompt, config):
            self.calls += 1
            return "must not run"

    provider = Provider()
    with pytest.raises(OutputError) as captured:
        recognize(
            source,
            config=Config(provider=provider, output_dir=output_dir),
        )

    assert captured.value.code == "OUTPUT_PATH_INVALID"
    assert provider.calls == 0

    with pytest.raises(ResumeStateError) as resume_error:
        recognize(
            source,
            config=Config(provider=provider, output_dir=output_dir, resume=True),
        )

    assert resume_error.value.code == "RESUME_STATE_INVALID"
    assert provider.calls == 0


def test_dangling_state_link_is_rejected_before_automatic_checkpoint(
    tmp_path,
    monkeypatch,
) -> None:
    source = write_test_image(tmp_path / "board.png")
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    state_path = _state_path(output_dir)
    real_lexists = os.path.lexists

    def lexists_with_dangling_state(path) -> bool:
        return Path(path) == state_path or real_lexists(path)

    monkeypatch.setattr(os.path, "lexists", lexists_with_dangling_state)

    class Provider:
        resume_identity = "dangling-state-preflight-v1"
        calls = 0

        def recognize_images(self, image_paths, *, prompt, config):
            self.calls += 1
            return "must not run"

    provider = Provider()
    with pytest.raises(OutputError) as captured:
        recognize(
            source,
            config=Config(provider=provider, output_dir=output_dir),
        )

    assert captured.value.code == "OUTPUT_PATH_INVALID"
    assert provider.calls == 0


@pytest.mark.parametrize("loser_identity", ["same-target-loser-v1", None])
def test_concurrent_same_target_keeps_winner_markdown_and_state_together(
    tmp_path,
    monkeypatch,
    loser_identity,
) -> None:
    source = write_test_image(tmp_path / "board.png")
    output_dir = tmp_path / "output"

    class Provider:
        def __init__(self, identity: str | None, markdown: str) -> None:
            if identity is not None:
                self.resume_identity = identity
            self.markdown = markdown
            self.calls = 0

        def recognize_images(self, image_paths, *, prompt, config):
            self.calls += 1
            return self.markdown

    winner = Provider("same-target-winner-v1", "# Winner A\n")
    loser = Provider(loser_identity, "# Loser B\n")
    writer = importlib.import_module("ocrllm.output.write_markdown_atomically")
    real_writer = writer.write_markdown_atomically
    condition = threading.Condition()
    stages = {
        "winner_at_publish": False,
        "loser_at_publish": False,
        "winner_published": False,
        "loser_finished": False,
    }

    def coordinated_writer(output_path, markdown, *, overwrite):
        if markdown == winner.markdown:
            with condition:
                stages["winner_at_publish"] = True
                condition.notify_all()
                assert condition.wait_for(
                    lambda: stages["loser_at_publish"] or stages["loser_finished"],
                    timeout=5,
                )
            real_writer(output_path, markdown, overwrite=overwrite)
            with condition:
                stages["winner_published"] = True
                condition.notify_all()
            return

        if loser_identity is None:
            real_writer(output_path, markdown, overwrite=overwrite)
            with condition:
                stages["loser_at_publish"] = True
                condition.notify_all()
            return

        with condition:
            stages["loser_at_publish"] = True
            condition.notify_all()
            assert condition.wait_for(
                lambda: stages["winner_published"],
                timeout=5,
            )
        real_writer(output_path, markdown, overwrite=overwrite)

    monkeypatch.setattr(writer, "write_markdown_atomically", coordinated_writer)
    outcomes: dict[str, object] = {}

    def run(label: str, provider: Provider) -> None:
        try:
            outcomes[label] = recognize(
                source,
                config=Config(provider=provider, output_dir=output_dir),
            )
        except BaseException as error:
            outcomes[label] = error
        finally:
            if label == "loser":
                with condition:
                    stages["loser_finished"] = True
                    condition.notify_all()

    winner_thread = threading.Thread(target=run, args=("winner", winner))
    loser_thread = threading.Thread(target=run, args=("loser", loser))
    winner_thread.start()
    with condition:
        assert condition.wait_for(
            lambda: stages["winner_at_publish"],
            timeout=5,
        )
    loser_thread.start()
    winner_thread.join(timeout=5)
    loser_thread.join(timeout=5)

    assert not winner_thread.is_alive()
    assert not loser_thread.is_alive()
    assert isinstance(outcomes["winner"], RecognitionResult)
    assert isinstance(outcomes["loser"], OutputExists)
    assert loser.calls == 0
    final_markdown = (output_dir / "board_board.md").read_text(encoding="utf-8")
    state_document = json.loads(_state_path(output_dir).read_text(encoding="utf-8"))
    assert final_markdown == winner.markdown
    assert state_document["result"]["markdown"] == final_markdown

    resume_provider = Provider("same-target-winner-v1", "must not run")
    resumed = recognize(
        source,
        config=Config(
            provider=resume_provider,
            output_dir=output_dir,
            resume=True,
        ),
    )

    assert resumed.markdown == winner.markdown
    assert resume_provider.calls == 0


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


def test_resume_bounds_state_that_grows_after_size_preflight(
    tmp_path,
    monkeypatch,
) -> None:
    source = write_test_image(tmp_path / "board.png")
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    state_path = _state_path(output_dir)
    state_path.write_bytes(b"{}")
    calls: list[tuple[Path, ...]] = []
    _install_fake_dashscope(monkeypatch, calls)
    loader = importlib.import_module("ocrllm.output.load_image_resume_state")
    monkeypatch.setattr(loader, "_MAX_STATE_BYTES", 2)
    monkeypatch.setattr(
        loader,
        "parse_image_resume_state",
        lambda _raw: pytest.fail("oversized state must not reach the parser"),
    )
    real_open = Path.open
    growth_injected = False
    read_sizes: list[int] = []

    class ObservedStateStream:
        def __init__(self, wrapped) -> None:
            self.wrapped = wrapped

        def __getattr__(self, name):
            return getattr(self.wrapped, name)

        def read(self, size=-1):
            read_sizes.append(size)
            return self.wrapped.read(size)

    def grow_state_before_open(path, *args, **kwargs):
        nonlocal growth_injected
        mode = args[0] if args else kwargs.get("mode", "r")
        if Path(path) == state_path and mode == "rb" and not growth_injected:
            growth_injected = True
            with real_open(state_path, "wb") as replacement:
                replacement.write(b'{"oversized":true}')
            return ObservedStateStream(real_open(path, *args, **kwargs))
        return real_open(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", grow_state_before_open)

    with pytest.raises(ResumeStateError) as captured:
        recognize(source, config=_vision_config(output_dir))

    assert captured.value.code == "RESUME_STATE_INVALID"
    assert growth_injected is True
    assert read_sizes == [3]
    assert calls == []
    assert not (output_dir / "board_board.md").exists()


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


def test_resume_bounds_validation_of_grown_final_output(
    tmp_path,
    monkeypatch,
) -> None:
    source = write_test_image(tmp_path / "board.png")
    output_dir = tmp_path / "output"
    calls: list[tuple[Path, ...]] = []
    _install_fake_dashscope(monkeypatch, calls)
    initial = recognize(source, config=_vision_config(output_dir))
    assert initial.output_path is not None
    output_path = initial.output_path
    state_path = _state_path(output_dir)
    state_before = state_path.read_bytes()
    expected_bytes = initial.markdown.encode("utf-8")
    grown_bytes = expected_bytes + (b"x" * 100)
    real_open = Path.open
    growth_injected = False
    consumed_bytes = 0
    validator = importlib.import_module(
        "ocrllm.output.validate_image_resume_output"
    )
    monkeypatch.setattr(validator, "_CHUNK_BYTES", 4)

    class ObservedOutputStream:
        def __init__(self, wrapped) -> None:
            self.wrapped = wrapped

        def __getattr__(self, name):
            return getattr(self.wrapped, name)

        def read(self, size=-1):
            nonlocal consumed_bytes
            chunk = self.wrapped.read(size)
            consumed_bytes += len(chunk)
            return chunk

    def grow_output_before_open(path, *args, **kwargs):
        nonlocal growth_injected
        mode = args[0] if args else kwargs.get("mode", "r")
        if Path(path) == output_path and mode == "rb" and not growth_injected:
            growth_injected = True
            with real_open(output_path, "wb") as replacement:
                replacement.write(grown_bytes)
            return ObservedOutputStream(real_open(path, *args, **kwargs))
        return real_open(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", grow_output_before_open)

    with pytest.raises(ResumeStateError) as captured:
        recognize(source, config=_vision_config(output_dir))

    assert captured.value.code == "RESUME_STATE_MISMATCH"
    assert growth_injected is True
    assert consumed_bytes == len(expected_bytes) + 1
    assert len(calls) == 1
    assert state_path.read_bytes() == state_before
    assert output_path.read_bytes() == grown_bytes


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
    assert captured.value.details["workflow_pass"] == "draft"
    assert captured.value.details["provider_calls_attempted"] == 1
    assert len(calls) == 1
    assert not (output_dir / "board_board.md").exists()
    assert not _state_path(output_dir).exists()
    assert list(output_dir.glob(".*.tmp")) == []


def test_completed_state_size_failure_reports_paid_call_and_keeps_partial_state(
    tmp_path,
    monkeypatch,
) -> None:
    source = write_test_image(tmp_path / "board.png")
    output_dir = tmp_path / "output"
    calls: list[tuple[Path, ...]] = []
    _install_fake_dashscope(monkeypatch, calls)
    saver = importlib.import_module("ocrllm.output.save_image_resume_state_atomically")
    real_serialize = saver.serialize_image_resume_state

    def limit_after_partial_state(state):
        raw = real_serialize(state)
        if not state.markdown:
            monkeypatch.setattr(saver, "_MAX_STATE_BYTES", len(raw) + 1)
        return raw

    monkeypatch.setattr(saver, "serialize_image_resume_state", limit_after_partial_state)

    with pytest.raises(OutputError) as captured:
        recognize(source, config=_vision_config(output_dir))

    assert captured.value.code == "OUTPUT_WRITE_FAILED"
    assert captured.value.details["provider_calls_attempted"] == 1
    assert "workflow_pass" not in captured.value.details
    assert len(calls) == 1
    assert not (output_dir / "board_board.md").exists()
    partial_state = json.loads(_state_path(output_dir).read_text(encoding="utf-8"))
    assert partial_state["result"]["status"] == "partial"
    assert partial_state["result"]["markdown"] == ""
    assert [slot["slot_id"] for slot in partial_state["slots"]] == ["draft"]
    assert list(output_dir.glob(".*.tmp")) == []

    with pytest.raises(OutputError) as resumed:
        recognize(source, config=_vision_config(output_dir))

    assert resumed.value.details["provider_calls_attempted"] == 0
    assert "workflow_pass" not in resumed.value.details
    assert len(calls) == 1


def test_completed_state_short_write_keeps_reusable_partial_state(
    tmp_path,
    monkeypatch,
) -> None:
    source = write_test_image(tmp_path / "board.png")
    output_dir = tmp_path / "output"
    output_path = output_dir / "board_board.md"
    state_path = _state_path(output_dir)
    calls: list[tuple[Path, ...]] = []
    _install_fake_dashscope(monkeypatch, calls)
    real_open = Path.open
    partial_before: bytes | None = None
    completed_write_was_short = False

    class OneShotCompletedStateShortWriter:
        def __init__(self, wrapped) -> None:
            self.wrapped = wrapped

        def __getattr__(self, name):
            return getattr(self.wrapped, name)

        def write(self, data):
            nonlocal completed_write_was_short, partial_before
            if not completed_write_was_short and b'"status":"complete"' in data:
                partial_before = state_path.read_bytes()
                completed_write_was_short = True
                return self.wrapped.write(data[:-1])
            return self.wrapped.write(data)

    def wrap_state_stream(path, *args, **kwargs):
        opened = real_open(path, *args, **kwargs)
        mode = args[0] if args else kwargs.get("mode", "r")
        if (
            path.parent == output_dir
            and path.name.startswith(".ocrllm-")
            and path.suffix == ".tmp"
            and mode == "xb"
        ):
            return OneShotCompletedStateShortWriter(opened)
        return opened

    monkeypatch.setattr(Path, "open", wrap_state_stream)

    with pytest.raises(OutputError) as captured:
        recognize(source, config=_vision_config(output_dir))

    assert captured.value.code == "OUTPUT_WRITE_FAILED"
    assert captured.value.details["provider_calls_attempted"] == 1
    assert "workflow_pass" not in captured.value.details
    assert len(calls) == 1
    assert completed_write_was_short is True
    assert partial_before is not None
    assert state_path.read_bytes() == partial_before
    partial_document = json.loads(partial_before)
    assert partial_document["result"]["status"] == "partial"
    assert partial_document["result"]["markdown"] == ""
    assert [slot["slot_id"] for slot in partial_document["slots"]] == ["draft"]
    assert not output_path.exists()
    assert list(output_dir.glob(".ocrllm-*.tmp")) == []

    resumed = recognize(source, config=_vision_config(output_dir))

    assert resumed.markdown == "# Resumable board\n"
    assert resumed.output_path == output_path
    assert len(calls) == 1
    assert output_path.read_text(encoding="utf-8") == resumed.markdown
    assert json.loads(state_path.read_text(encoding="utf-8"))["result"][
        "status"
    ] == "complete"


def test_all_slots_partial_resume_honors_cancellation_before_final_publication(
    tmp_path,
    monkeypatch,
) -> None:
    source = write_test_image(tmp_path / "board.png")
    output_dir = tmp_path / "output"
    output_path = output_dir / "board_board.md"
    state_path = _state_path(output_dir)
    calls: list[tuple[Path, ...]] = []
    _install_fake_dashscope(monkeypatch, calls)
    saver = importlib.import_module("ocrllm.output.save_image_resume_state_atomically")
    real_save = saver.save_image_resume_state_atomically

    def fail_completed_state(path, state):
        if state.markdown:
            raise OutputError("test-only completed state failure")
        return real_save(path, state)

    monkeypatch.setattr(saver, "save_image_resume_state_atomically", fail_completed_state)

    with pytest.raises(OutputError):
        recognize(source, config=_vision_config(output_dir))

    assert len(calls) == 1
    assert not output_path.exists()
    partial_before = state_path.read_bytes()
    partial_document = json.loads(partial_before)
    assert partial_document["result"]["status"] == "partial"
    assert partial_document["result"]["markdown"] == ""
    assert [slot["slot_id"] for slot in partial_document["slots"]] == ["draft"]
    monkeypatch.setattr(saver, "save_image_resume_state_atomically", real_save)

    cancellation = threading.Event()
    cancellation.set()
    with pytest.raises(Cancelled) as captured:
        recognize(
            source,
            config=_vision_config(output_dir, cancellation=cancellation),
        )

    assert captured.value.code == "CANCELLED"
    assert len(calls) == 1
    assert not output_path.exists()
    assert state_path.read_bytes() == partial_before

    resumed = recognize(source, config=_vision_config(output_dir))

    assert resumed.markdown == "# Resumable board\n"
    assert resumed.output_path == output_path
    assert len(calls) == 1
    assert output_path.read_text(encoding="utf-8") == resumed.markdown
    assert json.loads(state_path.read_text(encoding="utf-8"))["result"][
        "status"
    ] == "complete"


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


def test_injected_provider_named_like_builtin_writes_without_checkpoint(
    tmp_path,
) -> None:
    source = write_test_image(tmp_path / "board.png")
    output_dir = tmp_path / "output"

    class DashScopeSettings:
        calls = 0

        def recognize_images(self, image_paths, *, prompt, config):
            self.calls += 1
            return "# Injected provider\n"

    provider = DashScopeSettings()
    result = recognize(
        source,
        config=Config(provider=provider, output_dir=output_dir),
    )

    assert provider.calls == 1
    assert result.markdown == "# Injected provider\n"
    assert result.output_path == output_dir / "board_board.md"
    assert result.output_path.read_text(encoding="utf-8") == result.markdown
    assert not _state_path(output_dir).exists()


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
