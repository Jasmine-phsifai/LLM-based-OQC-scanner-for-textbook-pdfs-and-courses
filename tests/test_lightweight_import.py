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


def test_public_video_symbols_do_not_load_the_optional_backend():
    source_root = Path(__file__).resolve().parents[1] / "src"
    probe = (
        "import sys; "
        "sys.path.insert(0, sys.argv[1]); "
        "import ocrllm; "
        "inspect_video=ocrllm.inspect_video; "
        "extract_video_frames=ocrllm.extract_video_frames; "
        "extract_video_audio=ocrllm.extract_video_audio; "
        "recognize_video_frames=ocrllm.recognize_video_frames; "
        "recognize_video=ocrllm.recognize_video; "
        "compose_video_result=ocrllm.compose_video_result; "
        "publish_video_result=ocrllm.publish_video_result; "
        "VideoRecognitionOutcome=ocrllm.VideoRecognitionOutcome; "
        "recognize=ocrllm.recognize; "
        "recognize_batch=ocrllm.recognize_batch; "
        "RetainedVideoFrame=ocrllm.RetainedVideoFrame; "
        "VideoInfo=ocrllm.VideoInfo; "
        "assert callable(inspect_video); "
        "assert callable(extract_video_frames); "
        "assert callable(extract_video_audio); "
        "assert callable(recognize_video_frames); "
        "assert callable(recognize_video); "
        "assert callable(compose_video_result); "
        "assert callable(publish_video_result); "
        "assert VideoRecognitionOutcome.__module__ == 'ocrllm.video_recognition_outcome'; "
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


@pytest.mark.parametrize(
    "submodule_name",
    ("ocrllm.recognize_video", "ocrllm.recognize_video_frames"),
)
def test_public_video_callables_survive_explicit_submodule_import(submodule_name):
    source_root = Path(__file__).resolve().parents[1] / "src"
    probe = (
        "import importlib, sys; "
        "sys.path.insert(0, sys.argv[1]); "
        "import ocrllm; "
        "importlib.import_module(sys.argv[2]); "
        "from ocrllm import recognize_video, recognize_video_frames; "
        "assert callable(recognize_video), type(recognize_video); "
        "assert callable(recognize_video_frames), type(recognize_video_frames); "
        "assert recognize_video is importlib.import_module("
        "'ocrllm.recognize_video').recognize_video; "
        "assert recognize_video_frames is importlib.import_module("
        "'ocrllm.recognize_video_frames').recognize_video_frames; "
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
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert completed.returncode == 0, completed.stderr


def test_public_video_callables_support_standard_runtime_type_hints():
    source_root = Path(__file__).resolve().parents[1] / "src"
    probe = (
        "import importlib, sys, typing; "
        "sys.path.insert(0, sys.argv[1]); "
        "importlib.import_module('ocrllm.recognize_video'); "
        "from ocrllm import recognize_video, recognize_video_frames; "
        "video_hints=typing.get_type_hints(recognize_video); "
        "frame_hints=typing.get_type_hints(recognize_video_frames); "
        "from ocrllm import Config, RetainedVideoFrame, VideoRecognitionOutcome; "
        "from ocrllm.batch_item_outcome import BatchItemOutcome; "
        "assert video_hints['image_config'] is Config; "
        "assert video_hints['audio_config'] is Config; "
        "assert video_hints['return'] is VideoRecognitionOutcome; "
        "assert frame_hints['config'] == Config | None; "
        "assert frame_hints['frames'] == tuple[RetainedVideoFrame, ...]; "
        "assert frame_hints['return'] == list[BatchItemOutcome]; "
        "loaded={name.split('.')[0] for name in sys.modules}; "
        "forbidden={'cv2','numpy','imageio_ffmpeg','miniaudio','google','openai','httpx','legacy_app'}; "
        "assert not loaded & forbidden, loaded & forbidden; "
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


@pytest.mark.parametrize(
    "submodule_name",
    ("ocrllm.compose_video_result", "ocrllm.publish_video_result"),
)
def test_public_video_output_callables_survive_explicit_submodule_import(
    submodule_name,
):
    source_root = Path(__file__).resolve().parents[1] / "src"
    probe = (
        "import importlib, sys, typing; "
        "sys.path.insert(0, sys.argv[1]); "
        "import ocrllm; "
        "importlib.import_module(sys.argv[2]); "
        "from ocrllm import compose_video_result, publish_video_result; "
        "assert callable(compose_video_result), type(compose_video_result); "
        "assert callable(publish_video_result), type(publish_video_result); "
        "assert compose_video_result is importlib.import_module("
        "'ocrllm.compose_video_result').compose_video_result; "
        "assert publish_video_result is importlib.import_module("
        "'ocrllm.publish_video_result').publish_video_result; "
        "compose_hints=typing.get_type_hints(compose_video_result); "
        "publish_hints=typing.get_type_hints(publish_video_result); "
        "assert compose_hints['return'] is publish_hints['return']; "
        "assert compose_hints['outcome'] is publish_hints['outcome']; "
        "loaded={name.split('.')[0] for name in sys.modules}; "
        "forbidden={'cv2','numpy','imageio_ffmpeg','miniaudio','google','openai','httpx','legacy_app'}; "
        "assert not loaded & forbidden, loaded & forbidden; "
        "assert 'ocrllm.preflight_recognition_batch' not in sys.modules; "
        "assert 'ocrllm.output.output_target_claims' not in sys.modules; "
        "assert 'ocrllm.validate_config' not in sys.modules"
    )

    completed = subprocess.run(
        [
            sys.executable,
            "-I",
            "-c",
            probe,
            str(source_root),
            submodule_name,
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert completed.returncode == 0, completed.stderr
