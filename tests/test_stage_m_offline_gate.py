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


def test_base_wheel_check_uses_a_python_file_instead_of_multiline_c() -> None:
    """Windows PowerShell must not split multiline Python source into argv."""

    script = GATE_SCRIPT.read_text(encoding="utf-8")

    assert WHEEL_CHECKER.is_file()
    assert "$wheelFileProbe = @'" not in script
    assert "tools\\check_built_wheel.py" in script


def test_base_install_budget_keeps_real_disk_measurement_with_bounded_headroom() -> None:
    """The dependency-empty target includes normal installer-generated pyc."""

    script = GATE_SCRIPT.read_text(encoding="utf-8")

    assert "$baseTargetMaximumBytes = 1572864" in script
    assert "if ($installedBytes -gt $baseTargetMaximumBytes)" in script
    assert "__pycache__" not in script


@pytest.mark.parametrize(
    ("names", "succeeds"),
    [
        (("ocrllm/__init__.py", "ocrllm/py.typed"), True),
        (("ocrllm/__init__.py", "ocrllm/AGENTS.md"), False),
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


def test_combined_video_profile_uses_bounded_install_and_public_pipeline() -> None:
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
    assert "recognize_video(" in script
    assert "compose_video_result(outcome)" in script
    assert "publish_video_result(outcome, published_path)" in script
    assert "processor.recognize_short_mp3 = fake_google_audio" in script
    assert "provider=GoogleGenAISettings()," in script
    assert "distribution('google-genai')" in script
    assert "assert 'google' not in sys.modules" in script
    assert "assert image_provider.calls == 1" in script
    assert "assert image_provider.calls == len(outcome.frame_outcomes)" in script
    assert "assert len(observed_audio_snapshots) == 1" in script
    assert "glob('ocrllm-images-*')" in script
    assert "glob('ocrllm-audio-*')" in script
    assert "assert result.metadata['current_run_provider_call_count'] == 2" in script
    assert "assert result.metadata['current_model_token_usage'] == (" in script
