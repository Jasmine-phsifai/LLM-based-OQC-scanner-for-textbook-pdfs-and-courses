"""Focused Windows regressions for the maintained Stage M release gate."""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
import time
import zipfile

import pytest


GATE_SCRIPT = Path(__file__).parents[1] / "tools" / "run_stage_m_offline_gate.ps1"
WHEEL_CHECKER = Path(__file__).parents[1] / "tools" / "check_built_wheel.py"
OCR_SMOKE = (
    Path(__file__).parents[1] / "tools" / "run_installed_local_ocr_smoke.py"
)


def _run_bounded_process(tmp_path: Path, invocation: str) -> subprocess.CompletedProcess:
    harness = tmp_path / "invoke-bounded-process.ps1"
    # Execute the real helper in isolation so the regression cannot resolve or
    # download the archive test dependencies that the full gate prepares.
    harness.write_text(
        r"""
$tokens = $null
$parseErrors = $null
$ast = [System.Management.Automation.Language.Parser]::ParseFile(
    $env:OCRLLM_GATE_SCRIPT,
    [ref]$tokens,
    [ref]$parseErrors
)
if ($parseErrors.Count -ne 0) {
    throw 'gate script did not parse'
}
$function = $ast.Find(
    {
        param($node)
        $node -is [System.Management.Automation.Language.FunctionDefinitionAst] -and
            $node.Name -eq 'Invoke-BoundedProcess'
    },
    $true
)
if ($null -eq $function) {
    throw 'Invoke-BoundedProcess was not found'
}
Invoke-Expression $function.Extent.Text
""".strip()
        + "\n"
        + invocation.strip()
        + "\n",
        encoding="utf-8",
    )
    environment = os.environ.copy()
    environment["OCRLLM_GATE_SCRIPT"] = str(GATE_SCRIPT)

    return subprocess.run(
        [
            "powershell.exe",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(harness),
        ],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=environment,
        timeout=10,
    )


@pytest.mark.skipif(os.name != "nt", reason="the release gate is Windows-only")
def test_archived_source_stage_times_out_with_visible_failure(tmp_path: Path) -> None:
    """The proven dependency stall must end without network or a full gate run."""

    started = time.monotonic()
    completed = _run_bounded_process(
        tmp_path,
        r"""
Invoke-BoundedProcess `
    -StageName 'offline-timeout-regression' `
    -FilePath 'powershell.exe' `
    -ArgumentList @('-NoProfile', '-Command', 'Start-Sleep -Seconds 30') `
    -TimeoutSeconds 1
""",
    )
    elapsed = time.monotonic() - started
    output = completed.stdout + completed.stderr

    assert completed.returncode != 0
    assert elapsed < 10
    assert "stage started: offline-timeout-regression (timeout 1s)" in output
    assert "stage timeout: offline-timeout-regression" in output
    assert "stage completed: offline-timeout-regression" not in output


@pytest.mark.skipif(os.name != "nt", reason="the release gate is Windows-only")
@pytest.mark.parametrize(("child_exit", "succeeds"), ((0, True), (7, False)))
def test_bounded_process_preserves_success_and_nonzero_exit(
    tmp_path: Path,
    child_exit: int,
    succeeds: bool,
) -> None:
    completed = _run_bounded_process(
        tmp_path,
        f"""
Invoke-BoundedProcess `
    -StageName 'offline-exit-regression' `
    -FilePath 'powershell.exe' `
    -ArgumentList @('-NoProfile', '-Command', 'exit {child_exit}') `
    -TimeoutSeconds 5
""",
    )
    output = completed.stdout + completed.stderr

    assert (completed.returncode == 0) is succeeds
    if succeeds:
        assert "stage completed: offline-exit-regression" in output
    else:
        assert "stage failed with exit code 7: offline-exit-regression" in output


def test_archive_and_profile_installs_use_the_existing_process_bound() -> None:
    """Network stages are bounded and archived pytest startup stays visible."""

    script = GATE_SCRIPT.read_text(encoding="utf-8")
    profile_install = script.split(
        "$profilePython = Join-Path $profileVenv 'Scripts\\python.exe'",
        maxsplit=1,
    )[1].split("$expectedCsv =", maxsplit=1)[0]

    assert script.count("Invoke-BoundedProcess `") == 2
    assert "archived-source dependency preparation and pytest" in script
    assert "'python', '-m', 'pytest', '-ra', '-p', 'no:cacheprovider'" in script
    assert "'python', '-m', 'pytest', '-q', '-p', 'no:cacheprovider'" not in script
    assert "[int]$ArchivedSourceTestTimeoutSeconds = 1200" in script
    assert "[ValidateRange(30, 3600)]" in script
    assert "[int]$OptionalProfileInstallTimeoutSeconds = 1200" in script
    assert 'StageName "profile install: $profile"' in script
    assert "'--progress-bar'," in script
    assert "'--retries', '0'," in script
    assert "'--timeout', '30'," in script
    assert "-TimeoutSeconds $OptionalProfileInstallTimeoutSeconds" in script
    pip_version_probe = "& $profilePython -m pip --version"
    assert profile_install.count(pip_version_probe) == 1
    assert (
        profile_install.index("site-packages lookup failed: $profile")
        < profile_install.index(pip_version_probe)
        < profile_install.index("Invoke-BoundedProcess `")
    )
    assert 'profile pip version probe failed: $profile' in profile_install


def test_base_wheel_check_uses_a_python_file_instead_of_multiline_c() -> None:
    """Windows PowerShell must not split multiline Python source into argv."""

    script = GATE_SCRIPT.read_text(encoding="utf-8")

    assert WHEEL_CHECKER.is_file()
    assert "$wheelFileProbe = @'" not in script
    assert "tools\\check_built_wheel.py" in script


def test_base_install_budget_keeps_real_disk_measurement_with_bounded_headroom() -> None:
    """The dependency-empty target includes normal installer-generated pyc."""

    script = GATE_SCRIPT.read_text(encoding="utf-8")

    assert "$baseTargetMaximumBytes = 2097152" in script
    assert "if ($installedBytes -gt $baseTargetMaximumBytes)" in script
    assert "__pycache__" not in script


def test_base_install_probe_resolves_public_class_type_hints() -> None:
    script = GATE_SCRIPT.read_text(encoding="utf-8")
    base_probe = script.split("$baseProbe = @'", maxsplit=1)[1].split(
        "'@", maxsplit=1
    )[0]

    assert "import typing" in base_probe
    assert "from ocrllm.providers.vision_provider import VisionProvider" in base_probe
    for target in (
        "typing.get_type_hints(Config)",
        "typing.get_type_hints(BatchItemOutcome)",
        "typing.get_type_hints(DashScopeSettings)",
        "typing.get_type_hints(DashScopeSettings.for_region)",
    ):
        assert target in base_probe
    assert base_probe.count("assert not loaded & forbidden, loaded & forbidden") == 2
    assert "repair_images_to_markdown(" in base_probe
    assert "repair_audio_to_markdown(" in base_probe
    assert "error.details['provider_calls_attempted'] == 0" in base_probe
    assert "assert callable(repair_images_to_markdown)" in base_probe
    assert "assert callable(repair_audio_to_markdown)" in base_probe
    assert "usage['input_tokens'] == 17" in base_probe
    assert "usage['output_tokens'] is None" in base_probe
    assert "usage['provider_token'] == '[REDACTED]'" in base_probe
    assert "invalid_usage['input_tokens'] == '[REDACTED]'" in base_probe
    assert "invalid_usage['output_tokens'] == '[REDACTED]'" in base_probe
    assert "token_secret not in repr(usage_error.details)" in base_probe


def test_base_wheel_budget_keeps_bounded_product_headroom() -> None:
    script = GATE_SCRIPT.read_text(encoding="utf-8")

    assert "$baseWheelMaximumBytes = 327680" in script
    assert "if ($wheel.Length -gt $baseWheelMaximumBytes)" in script
    assert "base wheel exceeds 320 KiB" in script


@pytest.mark.parametrize(
    ("names", "succeeds"),
    [
        (("ocrllm/__init__.py", "ocrllm/py.typed"), True),
        (("ocrllm/__init__.py", "ocrllm/AGENTS.md"), False),
        (("ocrllm/__init__.py", "ocrllm/README_ACTIVE_LIBRARY.md"), False),
    ],
)
def test_built_wheel_checker_enforces_package_contents(
    tmp_path: Path,
    names: tuple[str, ...],
    succeeds: bool,
) -> None:
    wheel = tmp_path / "ocrllm.whl"
    with zipfile.ZipFile(wheel, "w") as archive:
        for name in names:
            archive.writestr(name, b"")

    completed = subprocess.run(
        [sys.executable, "-I", str(WHEEL_CHECKER), str(wheel)],
        check=False,
        capture_output=True,
        text=True,
    )

    assert (completed.returncode == 0) is succeeds


def test_visible_video_profile_uses_bounded_install_and_public_pipeline() -> None:
    """The user-facing video workflow is proven from one combined profile."""

    script = GATE_SCRIPT.read_text(encoding="utf-8")

    assert "'video' = 272629760" in script
    assert "'video,audio,image' = 307232768" in script
    assert "'video,audio,image' = @(" in script
    for distribution in (
        "'Pillow'",
        "'imageio-ffmpeg'",
        "'miniaudio'",
        "'numpy'",
        "'opencv-python'",
    ):
        assert distribution in script
    assert "if ($profile -eq 'video,audio,image')" in script
    assert "GOOGLE_GEMINI_2_5_FLASH" in script
    assert "assert callable(resume_video)" in script
    assert "nested_provider = [" in script
    assert "extract_video_frames(" in script
    assert "batchify_images(" in script
    assert "provider=nested_provider" in script
    assert "extract_video_audio(" in script
    assert "split_audio(audio_path, provider=nested_provider)" in script
    assert "distribution('google-genai')" in script
    assert "assert 'google' not in sys.modules" in script


def test_audio_profiles_include_the_interval_backend_and_bounded_smoke() -> None:
    script = GATE_SCRIPT.read_text(encoding="utf-8")

    assert "'audio' = 104857600" in script
    assert "'audio,google' = 146800640" in script
    assert "'audio' = @('miniaudio', 'imageio-ffmpeg')" in script
    assert "'audio,google' = @('miniaudio', 'imageio-ffmpeg', 'google-genai')" in script
    assert "materialize_long_audio_interval" in script


def test_dashscope_profile_proves_installed_missing_credential_is_zero_call() -> None:
    script = GATE_SCRIPT.read_text(encoding="utf-8")
    dashscope_smoke = script.split(
        "if ($profile -eq 'image,dashscope') {",
        maxsplit=1,
    )[1].split("if ($profile -eq 'google') {", maxsplit=1)[0]

    assert "DASHSCOPE_QWEN3_5_OCR_CN_BEIJING" in dashscope_smoke
    assert "recognize_images_to_markdown(" in dashscope_smoke
    assert "error.code == 'CONFIG_MISSING'" in dashscope_smoke
    assert "error.details['provider_operation'] == 'catalog'" in dashscope_smoke
    assert "error.details['provider_calls_attempted'] == 0" in dashscope_smoke
    assert "credential failure must precede network" in dashscope_smoke
    assert "assert network_calls == 0" in dashscope_smoke
    assert "assert 'openai' not in sys.modules" in dashscope_smoke
    assert "state_path.unlink()" in dashscope_smoke
    assert "$profileVenv" in dashscope_smoke


def test_ocr_profile_runs_real_installed_inference_without_network() -> None:
    script = GATE_SCRIPT.read_text(encoding="utf-8")
    smoke = OCR_SMOKE.read_text(encoding="utf-8")

    assert OCR_SMOKE.is_file()
    assert "'ocr' = 536870912" in script
    assert "'ocr' = @(" in script
    assert "'onnxruntime'," in script
    assert "'opencv-python'," in script
    assert "'omegaconf'" in script
    assert "if ($profile -eq 'ocr')" in script
    assert "tools\\run_installed_local_ocr_smoke.py" in script
    assert "ImageFont.load_default(size=64)" in smoke
    assert "requests.sessions.Session.request = reject_network" in smoke
    assert 'result = recognize(image_path, config=Config(image_mode="ocr"))' in smoke
    assert 'assert "OCRLLM" in result.markdown' in smoke
    assert 'assert result.metadata["provider_call_count"] == 0' in smoke
    assert 'assert result.metadata["network_call_count"] == 0' in smoke
    assert 'metadata.version("omegaconf")' in smoke
    assert "installed local OCR recognition smoke failed" in script
