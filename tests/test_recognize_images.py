"""Black-box tests for image orchestration and provider failures."""

from __future__ import annotations

import importlib
import traceback
from pathlib import Path

import pytest

from ocrllm import (
    Config,
    ConfigError,
    ProviderError,
    RecognitionPreferences,
    recognize,
    recognize_batch,
)

from write_test_image import write_test_image


class RecordingProvider:
    """Record ordered calls and return caller-selected values."""

    def __init__(self, response="# Board\n") -> None:
        self.response = response
        self.calls: list[tuple[tuple[Path, ...], str, Config]] = []

    def recognize_images(self, image_paths, *, prompt, config):
        paths = tuple(image_paths)
        self.calls.append((paths, prompt, config))
        if callable(self.response):
            return self.response(paths)
        return self.response


class RaisingProvider:
    """Raise one controlled provider exception without exposing it in repr."""

    def __init__(self, error: Exception, repr_sentinel: str) -> None:
        self.error = error
        self.repr_sentinel = repr_sentinel
        self.calls = 0

    def __repr__(self) -> str:
        return f"RaisingProvider(secret={self.repr_sentinel})"

    def recognize_images(self, image_paths, *, prompt, config):
        self.calls += 1
        raise self.error


class RaisingMethodLookupProvider:
    def __init__(self, sentinel: str) -> None:
        self.sentinel = sentinel

    def __getattribute__(self, name):
        if name == "recognize_images":
            sentinel = object.__getattribute__(self, "sentinel")
            raise RuntimeError(f"method lookup failed {sentinel}")
        return object.__getattribute__(self, name)


class HostileErrorCode:
    def __eq__(self, other):
        raise RuntimeError("HOSTILE_ERROR_CODE_SECRET_3770")


class HostileString(str):
    def __iter__(self):
        raise RuntimeError("HOSTILE_STRING_SECRET_94a8")


def test_ordered_image_group_reaches_provider_once_in_caller_order(tmp_path):
    sources = (
        write_test_image(tmp_path / "03-last.png", color=(3, 3, 3)),
        write_test_image(tmp_path / "01-first.jpg", color=(1, 1, 1)),
        write_test_image(tmp_path / "02-middle.jpeg", color=(2, 2, 2)),
    )
    provider = RecordingProvider(
        lambda paths: "# Ordered\n\n" + " -> ".join(path.name for path in paths)
    )
    config = Config(provider=provider)

    result = recognize(sources, config=config)

    assert len(provider.calls) == 1
    called_paths, prompt, called_config = provider.calls[0]
    assert [path.name for path in called_paths] == [path.name for path in sources]
    assert called_paths != sources
    assert called_config is config
    assert prompt.strip()
    assert result.markdown.endswith("03-last.png -> 01-first.jpg -> 02-middle.jpeg")
    assert result.source_type == "image"
    assert result.profile == "board"
    assert result.metadata["image_count"] == 3
    assert result.metadata["provider_call_count"] == 1
    assert result.metadata["draft_candidates"] == 1
    assert result.metadata["review_passes"] == 0
    assert all(not path.exists() for path in called_paths)


def test_review_pass_corrects_draft_and_writes_only_final_markdown(tmp_path):
    source = write_test_image(tmp_path / "board.png")

    class SequentialProvider(RecordingProvider):
        def __init__(self):
            super().__init__()
            self.responses = ["# Draft\nMissing mark", "# Final\nComplete + mark"]

        def recognize_images(self, image_paths, *, prompt, config):
            paths = tuple(image_paths)
            self.calls.append((paths, prompt, config))
            return self.responses[len(self.calls) - 1]

    provider = SequentialProvider()
    config = Config(
        provider=provider,
        preferences=RecognitionPreferences(review_passes=1),
        output_dir=tmp_path / "output",
    )

    result = recognize(source, config=config)

    assert result.markdown == "# Final\nComplete + mark"
    assert result.metadata["provider_call_count"] == 2
    assert result.metadata["draft_candidates"] == 1
    assert result.metadata["review_passes"] == 1
    assert len(provider.calls) == 2
    assert provider.calls[0][2] is config
    assert provider.calls[1][2] is config
    assert provider.calls[0][0] == provider.calls[1][0]
    assert "> # Draft\n> Missing mark" in provider.calls[1][1]
    assert "fallible" in provider.calls[1][1]
    assert result.output_path is not None
    assert result.output_path.read_text(encoding="utf-8") == result.markdown
    assert tuple(result.output_path.parent.glob("*.md")) == (result.output_path,)


def test_consensus_review_uses_two_independent_drafts_and_writes_only_final(tmp_path):
    source = write_test_image(tmp_path / "board.png")

    class SequentialProvider(RecordingProvider):
        def __init__(self):
            super().__init__()
            self.responses = (
                "# Draft one\nVisible +",
                "# Draft two\nVisible +",
                "# Consensus\nVisible +",
            )

        def recognize_images(self, image_paths, *, prompt, config):
            paths = tuple(image_paths)
            self.calls.append((paths, prompt, config))
            return self.responses[len(self.calls) - 1]

    provider = SequentialProvider()
    config = Config(
        provider=provider,
        preferences=RecognitionPreferences(draft_candidates=2, review_passes=1),
        output_dir=tmp_path / "output",
    )

    result = recognize(source, config=config)

    assert result.markdown == "# Consensus\nVisible +"
    assert result.metadata["provider_call_count"] == 3
    assert result.metadata["draft_candidates"] == 2
    assert result.metadata["review_passes"] == 1
    assert len(provider.calls) == 3
    assert provider.calls[0][1] == provider.calls[1][1]
    assert "BEGIN FALLIBLE DRAFT" not in provider.calls[0][1]
    assert "BEGIN FALLIBLE DRAFT" not in provider.calls[1][1]
    assert "> # Draft one" in provider.calls[2][1]
    assert "> # Draft two" in provider.calls[2][1]
    assert result.output_path is not None
    assert result.output_path.read_text(encoding="utf-8") == result.markdown
    assert tuple(result.output_path.parent.glob("*.md")) == (result.output_path,)


def test_second_consensus_draft_failure_writes_no_partial_output(tmp_path):
    source = write_test_image(tmp_path / "board.png")

    class FailingSecondDraftProvider(RecordingProvider):
        def recognize_images(self, image_paths, *, prompt, config):
            paths = tuple(image_paths)
            self.calls.append((paths, prompt, config))
            if len(self.calls) == 1:
                return "# First draft that must not escape\n"
            raise TimeoutError("second draft timed out with private provider detail")

    provider = FailingSecondDraftProvider()
    output_dir = tmp_path / "output"

    with pytest.raises(ProviderError) as captured:
        recognize(
            source,
            config=Config(
                provider=provider,
                preferences=RecognitionPreferences(
                    draft_candidates=2,
                    review_passes=1,
                ),
                output_dir=output_dir,
            ),
        )

    assert captured.value.code == "PROVIDER_TIMEOUT"
    assert captured.value.details["workflow_pass"] == "draft_2"
    assert captured.value.details["provider_calls_attempted"] == 2
    assert len(provider.calls) == 2
    assert output_dir.is_dir()
    assert tuple(output_dir.iterdir()) == ()


def test_review_failure_rejects_draft_and_writes_no_output(tmp_path):
    source = write_test_image(tmp_path / "board.png")

    class FailingReviewProvider(RecordingProvider):
        def recognize_images(self, image_paths, *, prompt, config):
            paths = tuple(image_paths)
            self.calls.append((paths, prompt, config))
            if len(self.calls) == 1:
                return "# Draft that must not escape\n"
            raise TimeoutError("review timed out with private provider detail")

    provider = FailingReviewProvider()
    output_dir = tmp_path / "output"

    with pytest.raises(ProviderError) as captured:
        recognize(
            source,
            config=Config(
                provider=provider,
                preferences=RecognitionPreferences(review_passes=1),
                output_dir=output_dir,
            ),
        )

    assert captured.value.code == "PROVIDER_TIMEOUT"
    assert captured.value.details["workflow_pass"] == "review"
    assert captured.value.details["provider_calls_attempted"] == 2
    assert len(provider.calls) == 2
    assert output_dir.is_dir()
    assert tuple(output_dir.iterdir()) == ()


def test_recognize_batch_preserves_request_call_and_result_order(tmp_path):
    sources = [
        write_test_image(tmp_path / "z.png", color=(9, 0, 0)),
        write_test_image(tmp_path / "a.jpg", color=(0, 9, 0)),
        write_test_image(tmp_path / "m.jpeg", color=(0, 0, 9)),
    ]
    provider = RecordingProvider(lambda paths: f"# {paths[0].name}\n")

    outcomes = recognize_batch(sources, config=Config(provider=provider))

    assert [call[0][0].name for call in provider.calls] == [path.name for path in sources]
    assert [outcome.result.markdown.strip() for outcome in outcomes] == [
        "# z.png",
        "# a.jpg",
        "# m.jpeg",
    ]


def test_missing_provider_is_a_typed_configuration_failure(tmp_path):
    source = write_test_image(tmp_path / "board.png")

    with pytest.raises(ConfigError) as captured:
        recognize(source, config=Config())

    assert captured.value.code == "CONFIG_MISSING"


def test_non_config_argument_is_rejected_before_source_or_provider_work(tmp_path):
    provider = RecordingProvider()

    with pytest.raises(ConfigError) as captured:
        recognize(tmp_path / "missing.png", config=False)  # type: ignore[arg-type]

    assert captured.value.code == "CONFIG_INVALID"
    assert provider.calls == []


def test_mutated_config_is_revalidated_before_source_or_provider_work(tmp_path):
    provider = RecordingProvider()
    config = Config(provider=provider)
    object.__setattr__(config, "timeout_seconds", "unsafe")

    with pytest.raises(ConfigError) as captured:
        recognize(tmp_path / "missing.png", config=config)

    assert captured.value.code == "CONFIG_INVALID"
    assert provider.calls == []


def test_config_subclasses_are_rejected_before_source_or_provider_work(tmp_path):
    class ConfigSubclass(Config):
        pass

    provider = RecordingProvider()
    config = ConfigSubclass(provider=provider)

    with pytest.raises(ConfigError) as captured:
        recognize(tmp_path / "missing.png", config=config)

    assert captured.value.code == "CONFIG_INVALID"
    assert provider.calls == []


@pytest.mark.parametrize(
    "provider_output",
    [
        None,
        b"# bytes are not Markdown",
        42,
        "",
        " \t\r\n",
        "\x00\u200b",
        "# ---",
    ],
    ids=[
        "none",
        "bytes",
        "integer",
        "empty",
        "whitespace",
        "control-only",
        "markdown-scaffolding-only",
    ],
)
def test_invalid_provider_output_never_becomes_success(tmp_path, provider_output):
    source = write_test_image(tmp_path / "board.png")
    provider = RecordingProvider(provider_output)

    with pytest.raises(ProviderError) as captured:
        recognize(source, config=Config(provider=provider))

    assert captured.value.code == "PROVIDER_RESPONSE_INVALID"
    assert len(provider.calls) == 1


def test_hostile_string_subclass_is_rejected_without_executing_overrides(tmp_path):
    source = write_test_image(tmp_path / "board.png")

    with pytest.raises(ProviderError) as captured:
        recognize(
            source,
            config=Config(provider=RecordingProvider(HostileString("visible"))),
        )

    assert captured.value.code == "PROVIDER_RESPONSE_INVALID"


def test_visible_json_literal_is_valid_recognized_board_content(tmp_path):
    source = write_test_image(tmp_path / "board.png")
    literal = '{"error":"margin of error shown on the board"}'

    result = recognize(source, config=Config(provider=RecordingProvider(literal)))

    assert result.markdown == literal


@pytest.mark.parametrize(
    ("error_factory", "expected_code", "expected_retryable"),
    [
        (lambda sentinel: TimeoutError(f"timeout {sentinel}"), "PROVIDER_TIMEOUT", True),
        (lambda sentinel: ConnectionError(f"network {sentinel}"), "PROVIDER_NETWORK", True),
        (
            lambda sentinel: RuntimeError(f"unexpected provider failure {sentinel}"),
            "PROVIDER_RESPONSE_INVALID",
            False,
        ),
    ],
    ids=["timeout", "network", "arbitrary"],
)
def test_provider_failures_are_typed_and_redacted(
    tmp_path,
    error_factory,
    expected_code,
    expected_retryable,
):
    source = write_test_image(tmp_path / "board.png")
    error_sentinel = "PROVIDER_ERROR_SECRET_91f6c46b"
    repr_sentinel = "PROVIDER_REPR_SECRET_d92f126d"
    provider = RaisingProvider(error_factory(error_sentinel), repr_sentinel)
    config = Config(provider=provider)

    assert repr_sentinel not in repr(config)
    with pytest.raises(ProviderError) as captured:
        recognize(source, config=config)

    public_error = captured.value
    rendered_error = "".join(
        traceback.format_exception(type(public_error), public_error, public_error.__traceback__)
    )
    assert public_error.code == expected_code
    assert public_error.retryable is expected_retryable
    assert public_error.details["workflow_pass"] == "draft"
    assert public_error.details["provider_calls_attempted"] == 1
    assert provider.calls == 1
    assert error_sentinel not in str(public_error)
    assert error_sentinel not in repr(public_error.details)
    assert error_sentinel not in rendered_error
    assert repr_sentinel not in rendered_error
    assert public_error.__cause__ is None
    assert public_error.__context__ is None
    library_frames = [
        frame
        for frame in traceback.extract_tb(public_error.__traceback__)
        if "src" in Path(frame.filename).parts and "ocrllm" in Path(frame.filename).parts
    ]
    assert [(Path(frame.filename).name, frame.name) for frame in library_frames] == [
        ("recognize.py", "recognize")
    ]


def test_provider_method_lookup_failure_is_typed_and_redacted(tmp_path):
    source = write_test_image(tmp_path / "board.png")
    sentinel = "PROVIDER_LOOKUP_SECRET_2245f5f8"

    with pytest.raises(ProviderError) as captured:
        recognize(source, config=Config(provider=RaisingMethodLookupProvider(sentinel)))

    rendered_error = "".join(
        traceback.format_exception(
            type(captured.value),
            captured.value,
            captured.value.__traceback__,
        )
    )
    assert captured.value.code == "PROVIDER_RESPONSE_INVALID"
    assert sentinel not in rendered_error


def test_hostile_provider_error_code_cannot_escape_the_redaction_boundary(tmp_path):
    source = write_test_image(tmp_path / "board.png")
    provider_error = RuntimeError("ordinary provider failure")
    provider_error.code = HostileErrorCode()  # type: ignore[attr-defined]

    with pytest.raises(ProviderError) as captured:
        recognize(
            source,
            config=Config(provider=RaisingProvider(provider_error, "hidden")),
        )

    rendered = "".join(
        traceback.format_exception(
            type(captured.value),
            captured.value,
            captured.value.__traceback__,
        )
    )
    assert captured.value.code == "PROVIDER_RESPONSE_INVALID"
    assert "HOSTILE_ERROR_CODE_SECRET_3770" not in rendered


@pytest.mark.parametrize(
    ("error", "expected_code", "expected_retryable"),
    [
        (
            type("AuthenticationFailure", (Exception,), {"code": "PROVIDER_AUTHENTICATION"})(
                "raw auth detail"
            ),
            "PROVIDER_AUTHENTICATION",
            False,
        ),
        (
            type("PermissionFailure", (Exception,), {"code": "PROVIDER_PERMISSION_DENIED"})(
                "raw permission detail"
            ),
            "PROVIDER_PERMISSION_DENIED",
            False,
        ),
        (
            type("SuspendedFailure", (Exception,), {"code": "PROVIDER_ACCOUNT_SUSPENDED"})(
                "raw suspension detail"
            ),
            "PROVIDER_ACCOUNT_SUSPENDED",
            False,
        ),
        (
            type("ConcurrencyFailure", (Exception,), {"code": "PROVIDER_CONCURRENCY_LIMITED"})(
                "raw concurrency detail"
            ),
            "PROVIDER_CONCURRENCY_LIMITED",
            True,
        ),
        (
            type("RequestFailure", (Exception,), {"code": "PROVIDER_REQUEST_INVALID"})(
                "raw request detail"
            ),
            "PROVIDER_REQUEST_INVALID",
            False,
        ),
        (
            type("ContentFailure", (Exception,), {"code": "PROVIDER_CONTENT_BLOCKED"})(
                "raw content detail"
            ),
            "PROVIDER_CONTENT_BLOCKED",
            False,
        ),
        (FileNotFoundError("local provider file missing"), "PROVIDER_RESPONSE_INVALID", False),
    ],
)
def test_provider_codes_are_mapped_without_treating_local_os_errors_as_network(
    tmp_path,
    error,
    expected_code,
    expected_retryable,
):
    source = write_test_image(tmp_path / "board.png")

    with pytest.raises(ProviderError) as captured:
        recognize(source, config=Config(provider=RaisingProvider(error, "hidden")))

    assert captured.value.code == expected_code
    assert captured.value.retryable is expected_retryable


def test_unregistered_image_profile_is_rejected_without_provider_call(tmp_path):
    source = write_test_image(tmp_path / "board.png")
    provider = RecordingProvider()

    with pytest.raises(ConfigError) as captured:
        recognize(source, config=Config(provider=provider, profile="invoice"))

    assert captured.value.code == "CONFIG_INVALID"
    assert provider.calls == []


def test_provider_reads_validated_snapshot_when_original_changes_after_validation(
    tmp_path,
    monkeypatch,
):
    from PIL import Image

    source = write_test_image(tmp_path / "mutable.png")
    provider_paths: list[Path] = []

    class DecodingProvider:
        def recognize_images(self, image_paths, *, prompt, config):
            provider_paths.extend(image_paths)
            with Image.open(image_paths[0]) as image:
                image.verify()
            return "# Snapshot stayed valid\n"

    output_path_module = importlib.import_module("ocrllm.output.build_output_path")
    original_build_output_path = output_path_module.build_output_path

    def corrupt_original_after_snapshot(source_paths, *, profile, config):
        source.write_bytes(b"corrupt after snapshot validation")
        return original_build_output_path(source_paths, profile=profile, config=config)

    monkeypatch.setattr(
        output_path_module,
        "build_output_path",
        corrupt_original_after_snapshot,
    )

    result = recognize(source, config=Config(provider=DecodingProvider()))

    assert result.markdown == "# Snapshot stayed valid\n"
    assert source.read_bytes() == b"corrupt after snapshot validation"
    assert len(provider_paths) == 1
    assert provider_paths[0] != source
    assert provider_paths[0].name == source.name
    assert not provider_paths[0].exists()


def test_config_secrets_never_enter_error_traceback_or_success_result(tmp_path):
    source = write_test_image(tmp_path / "board.png")
    sentinels = (
        "PROVIDER_OBJECT_SECRET_1f3b",
        "PDF_PASSWORD_SECRET_3d5e",
        "PROVIDER_EXTRA_SECRET_4f6a",
    )
    failing_config = Config(
        provider=RaisingProvider(RuntimeError("provider failed"), sentinels[0]),
        pdf_password=sentinels[1],
        extra={"provider_token": sentinels[2]},
    )

    with pytest.raises(ProviderError) as captured:
        recognize(source, config=failing_config)

    rendered_error = "".join(
        traceback.format_exception(
            type(captured.value),
            captured.value,
            captured.value.__traceback__,
        )
    )
    assert all(sentinel not in repr(failing_config) for sentinel in sentinels)
    assert all(sentinel not in rendered_error for sentinel in sentinels)
    assert all(sentinel not in repr(captured.value.details) for sentinel in sentinels)
    traceback_cursor = captured.value.__traceback__
    while traceback_cursor is not None:
        frame_path = Path(traceback_cursor.tb_frame.f_code.co_filename)
        if "src" in frame_path.parts and "ocrllm" in frame_path.parts:
            rendered_locals = repr(traceback_cursor.tb_frame.f_locals)
            assert all(sentinel not in rendered_locals for sentinel in sentinels)
        traceback_cursor = traceback_cursor.tb_next

    successful_config = Config(
        provider=RecordingProvider("# Safe result\n"),
        pdf_password=sentinels[1],
        extra={"provider_token": sentinels[2]},
    )
    result = recognize(source, config=successful_config)
    rendered_result = f"{result!r} {result.metadata!r} {result.markdown}"

    assert all(sentinel not in rendered_result for sentinel in sentinels)
