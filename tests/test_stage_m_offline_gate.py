"""Focused Windows regressions for the maintained Stage M release gate."""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import time

import pytest


GATE_SCRIPT = Path(__file__).parents[1] / "tools" / "run_stage_m_offline_gate.ps1"


@pytest.mark.skipif(os.name != "nt", reason="the release gate is Windows-only")
def test_archived_source_stage_times_out_with_visible_failure(tmp_path: Path) -> None:
    """The proven dependency stall must end without network or a full gate run."""

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
Invoke-BoundedProcess `
    -StageName 'offline-timeout-regression' `
    -FilePath 'powershell.exe' `
    -ArgumentList @('-NoProfile', '-Command', 'Start-Sleep -Seconds 30') `
    -TimeoutSeconds 1
""".strip()
        + "\n",
        encoding="utf-8",
    )
    environment = os.environ.copy()
    environment["OCRLLM_GATE_SCRIPT"] = str(GATE_SCRIPT)

    started = time.monotonic()
    completed = subprocess.run(
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
    elapsed = time.monotonic() - started
    output = completed.stdout + completed.stderr

    assert completed.returncode != 0
    assert elapsed < 10
    assert "stage started: offline-timeout-regression (timeout 1s)" in output
    assert "stage timeout: offline-timeout-regression" in output
    assert "stage completed: offline-timeout-regression" not in output


def test_only_the_proven_archive_stage_uses_the_new_bound() -> None:
    """The iteration must not silently grow into a second process framework."""

    script = GATE_SCRIPT.read_text(encoding="utf-8")

    assert script.count("Invoke-BoundedProcess `") == 1
    assert "archived-source dependency preparation and pytest" in script
    assert "[int]$ArchivedSourceTestTimeoutSeconds = 1200" in script
