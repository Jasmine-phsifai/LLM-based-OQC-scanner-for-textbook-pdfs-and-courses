"""Fresh-process guard for the dependency-free public import."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest


def test_plain_import_does_not_load_optional_image_or_provider_packages():
    source_root = Path(__file__).resolve().parents[1] / "src"
    probe = (
        "import sys; "
        "sys.path.insert(0, sys.argv[1]); "
        "import ocrllm; "
        "loaded={name.split('.')[0] for name in sys.modules}; "
        "forbidden={'PIL','pypdfium2','openai','google','httpx','rapidocr','onnxruntime','cv2','numpy','miniaudio','_miniaudio'}; "
        "assert not loaded & forbidden, loaded & forbidden"
    )

    completed = subprocess.run(
        [sys.executable, "-I", "-c", probe, str(source_root)],
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert completed.returncode == 0, completed.stderr

def test_plain_import_binds_recognition_facades_but_defers_execution_helpers():
    source_root = Path(__file__).resolve().parents[1] / "src"
    probe = (
        "import sys; "
        "sys.path.insert(0, sys.argv[1]); "
        "import ocrllm; "
        "import importlib; "
        "batchify_images=ocrllm.batchify_images; "
        "split_audio=ocrllm.split_audio; "
        "recognize_audio=ocrllm.recognize_audio_to_markdown; "
        "resume_audio=ocrllm.resume_audio_to_markdown; "
        "resume_video=ocrllm.resume_video; "
        "batchify_module=importlib.import_module('ocrllm.batchify_images'); "
        "assert callable(batchify_images); "
        "assert ocrllm.batchify_images is batchify_images; "
        "assert batchify_images is batchify_module.batchify_images; "
        "assert callable(split_audio); "
        "assert 'ocrllm.split_audio' in sys.modules; "
        "assert callable(recognize_audio); "
        "assert callable(resume_audio); "
        "assert callable(resume_video); "
        "assert 'ocrllm.run_merged_audio_job' not in sys.modules; "
        "assert 'ocrllm.execute_merged_image_plan' not in sys.modules; "
        "assert 'ocrllm.recognize' in sys.modules; "
        "assert 'ocrllm.recognize_batch' in sys.modules; "
        "assert 'ocrllm.preflight_recognition_batch' not in sys.modules; "
        "assert 'ocrllm.output.output_target_claims' not in sys.modules; "
        "assert 'ocrllm.validate_config' not in sys.modules; "
        "assert 'Config' in dir(ocrllm); "
        "Config=ocrllm.Config; "
        "assert Config.__module__ == 'ocrllm.config'; "
        "assert 'ocrllm.config' in sys.modules; "
        "assert ocrllm.Config is Config; "
        "assert 'ocrllm.preflight_recognition_batch' not in sys.modules; "
        "assert 'ocrllm.output.output_target_claims' not in sys.modules; "
        "assert 'ocrllm.validate_config' not in sys.modules"
    )

    completed = subprocess.run(
        [sys.executable, "-I", "-c", probe, str(source_root)],
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert completed.returncode == 0, completed.stderr


def test_resume_video_rejects_ambiguous_media_before_execution_imports():
    source_root = Path(__file__).resolve().parents[1] / "src"
    probe = "\n".join(
        (
            "import pathlib, sys",
            "sys.path.insert(0, sys.argv[1])",
            "import ocrllm",
            "from ocrllm.errors import ConfigError, InvalidSource",
            "def capture(call, expected):",
            "    try:",
            "        call()",
            "    except expected as error:",
            "        assert error.details['provider_calls_attempted'] == 0",
            "    else:",
            "        raise AssertionError('expected typed route rejection')",
            "capture(lambda: ocrllm.resume_video((), media_type='video', providers=object()), ConfigError)",
            "audio=(ocrllm.AudioSlice(source=pathlib.Path('missing.mp3'), index=0, logical_start_seconds=0.0, logical_end_seconds=1.0, actual_start_seconds=0.0, actual_end_seconds=1.0),)",
            "capture(lambda: ocrllm.resume_video(audio, media_type='image', providers=object()), InvalidSource)",
            "images=((pathlib.Path('missing.png'),),)",
            "capture(lambda: ocrllm.resume_video(images, media_type='audio', providers=object()), InvalidSource)",
            "assert 'ocrllm.execute_merged_image_plan' not in sys.modules",
            "assert 'ocrllm.run_merged_audio_job' not in sys.modules",
        )
    )
    completed = subprocess.run(
        [sys.executable, "-I", "-c", probe, str(source_root)],
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert completed.returncode == 0, completed.stderr


def test_provider_free_video_symbols_do_not_load_the_optional_backend():
    source_root = Path(__file__).resolve().parents[1] / "src"
    probe = (
        "import sys; "
        "sys.path.insert(0, sys.argv[1]); "
        "import ocrllm; "
        "inspect_video=ocrllm.inspect_video; "
        "extract_video_frames=ocrllm.extract_video_frames; "
        "extract_video_audio=ocrllm.extract_video_audio; "
        "recognize=ocrllm.recognize; "
        "recognize_batch=ocrllm.recognize_batch; "
        "RetainedVideoFrame=ocrllm.RetainedVideoFrame; "
        "VideoInfo=ocrllm.VideoInfo; "
        "assert callable(inspect_video); "
        "assert callable(extract_video_frames); "
        "assert callable(extract_video_audio); "
        "assert callable(recognize); "
        "assert callable(recognize_batch); "
        "assert RetainedVideoFrame.__module__ == 'ocrllm.retained_video_frame'; "
        "assert VideoInfo.__module__ == 'ocrllm.video_info'; "
        "loaded={name.split('.')[0] for name in sys.modules}; "
        "assert not loaded & {'cv2','numpy','imageio_ffmpeg','miniaudio'}, "
        "loaded & {'cv2','numpy','imageio_ffmpeg','miniaudio'}"
    )

    completed = subprocess.run(
        [sys.executable, "-I", "-c", probe, str(source_root)],
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert completed.returncode == 0, completed.stderr


@pytest.mark.parametrize(
    "first_name,second_name",
    (
        ("recognize_batch", "recognize"),
        ("recognize", "recognize_batch"),
    ),
)
def test_public_recognition_callables_survive_either_lazy_import_order(
    first_name,
    second_name,
):
    source_root = Path(__file__).resolve().parents[1] / "src"
    probe = (
        "import sys; "
        "sys.path.insert(0, sys.argv[1]); "
        "import ocrllm; "
        "first=getattr(ocrllm, sys.argv[2]); "
        "second=getattr(ocrllm, sys.argv[3]); "
        "assert callable(first), type(first); "
        "assert callable(second), type(second); "
        "assert callable(ocrllm.recognize); "
        "assert callable(ocrllm.recognize_batch)"
    )

    completed = subprocess.run(
        [
            sys.executable,
            "-I",
            "-c",
            probe,
            str(source_root),
            first_name,
            second_name,
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert completed.returncode == 0, completed.stderr


@pytest.mark.parametrize(
    "submodule_name,public_name",
    (
        ("ocrllm.recognize", "recognize"),
        ("ocrllm.recognize_batch", "recognize_batch"),
    ),
)
def test_public_recognition_callables_survive_explicit_submodule_import(
    submodule_name,
    public_name,
):
    source_root = Path(__file__).resolve().parents[1] / "src"
    probe = (
        "import importlib, sys, typing; "
        "sys.path.insert(0, sys.argv[1]); "
        "import ocrllm; "
        "importlib.import_module(sys.argv[2]); "
        "assert callable(getattr(ocrllm, sys.argv[3])), "
        "type(getattr(ocrllm, sys.argv[3])); "
        "from ocrllm import recognize, recognize_batch; "
        "assert callable(recognize), type(recognize); "
        "assert callable(recognize_batch), type(recognize_batch); "
        "assert recognize is importlib.import_module('ocrllm.recognize').recognize; "
        "assert recognize_batch is importlib.import_module("
        "'ocrllm.recognize_batch').recognize_batch; "
        "recognize_hints=typing.get_type_hints(recognize); "
        "batch_hints=typing.get_type_hints(recognize_batch); "
        "from ocrllm import BatchItemOutcome, Config, RecognitionResult; "
        "assert recognize_hints['config'] == Config | None; "
        "assert recognize_hints['return'] is RecognitionResult; "
        "assert batch_hints['config'] == Config | None; "
        "assert batch_hints['return'] == list[BatchItemOutcome]; "
        "loaded={name.split('.')[0] for name in sys.modules}; "
        "forbidden={'cv2','numpy','imageio_ffmpeg','miniaudio','google','openai','httpx','legacy_app'}; "
        "assert not loaded & forbidden, loaded & forbidden"
    )

    completed = subprocess.run(
        [
            sys.executable,
            "-I",
            "-c",
            probe,
            str(source_root),
            submodule_name,
            public_name,
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert completed.returncode == 0, completed.stderr


def test_public_long_mp3_callable_survives_explicit_submodule_import():
    source_root = Path(__file__).resolve().parents[1] / "src"
    probe = (
        "import importlib, sys, typing; "
        "sys.path.insert(0, sys.argv[1]); "
        "import ocrllm; "
        "module=importlib.import_module('ocrllm.recognize_long_mp3'); "
        "from ocrllm import recognize_long_mp3; "
        "assert callable(recognize_long_mp3), type(recognize_long_mp3); "
        "assert recognize_long_mp3 is module.recognize_long_mp3; "
        "hints=typing.get_type_hints(recognize_long_mp3); "
        "from ocrllm import Config, RecognitionResult; "
        "assert hints['config'] == Config | None; "
        "assert hints['return'] is RecognitionResult; "
        "loaded={name.split('.')[0] for name in sys.modules}; "
        "forbidden={'cv2','numpy','imageio_ffmpeg','miniaudio','google','openai','httpx','legacy_app'}; "
        "assert not loaded & forbidden, loaded & forbidden; "
        "assert 'ocrllm.processors.recognize_long_mp3' not in sys.modules"
    )

    completed = subprocess.run(
        [sys.executable, "-I", "-c", probe, str(source_root)],
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert completed.returncode == 0, completed.stderr
