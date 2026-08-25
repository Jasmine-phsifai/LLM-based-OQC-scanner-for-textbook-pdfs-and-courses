"""Focused Windows regressions for the maintained Stage M release gate."""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import time

import pytest


GATE_SCRIPT = Path(__file__).parents[1] / "tools" / "run_stage_m_offline_gate.ps1"


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
    """Network-bearing gate stages share one readable process controller."""

    script = GATE_SCRIPT.read_text(encoding="utf-8")

    assert script.count("Invoke-BoundedProcess `") == 2
    assert "archived-source dependency preparation and pytest" in script
    assert "[int]$ArchivedSourceTestTimeoutSeconds = 1200" in script
    assert "[ValidateRange(30, 3600)]" in script
    assert "[int]$OptionalProfileInstallTimeoutSeconds = 1200" in script
    assert 'StageName "profile install: $profile"' in script
    assert "'--progress-bar'," in script
    assert "'--retries', '0'," in script
    assert "'--timeout', '30'," in script
    assert "-TimeoutSeconds $OptionalProfileInstallTimeoutSeconds" in script
