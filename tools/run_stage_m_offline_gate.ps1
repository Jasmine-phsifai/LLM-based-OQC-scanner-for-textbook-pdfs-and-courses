param(
    [string]$PythonPath = 'D:\Anaconda\envs\OCRLLM\python.exe',
    [switch]$SkipOptionalProfiles
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Assert-LastExitCode {
    param([string]$Message)
    if ($LASTEXITCODE -ne 0) {
        throw $Message
    }
}

function Get-DirectoryByteCount {
    param([string]$Path)
    $measurement = Get-ChildItem -LiteralPath $Path -Recurse -File |
        Measure-Object -Property Length -Sum
    if ($null -eq $measurement.Sum) {
        return 0
    }
    return [int64]$measurement.Sum
}

function Assert-ImportBudget {
    param(
        [string]$Interpreter,
        [string]$TargetDirectory
    )
    $probe = @'
import json
import pathlib
import sys
import time

target = pathlib.Path(sys.argv[1]).resolve()
sys.path.insert(0, str(target))
cpu_started = time.process_time_ns()
wall_started = time.perf_counter_ns()
import ocrllm
wall_ms = (time.perf_counter_ns() - wall_started) / 1e6
cpu_ms = (time.process_time_ns() - cpu_started) / 1e6
origin = pathlib.Path(ocrllm.__file__).resolve()
assert target in origin.parents, (target, origin)
loaded = {name.split('.')[0] for name in sys.modules}
forbidden = {
    'PIL', 'pypdfium2', 'openai', 'httpx', 'onnxruntime',
    'miniaudio', '_miniaudio', 'legacy_app',
}
assert not loaded & forbidden, loaded & forbidden
print(json.dumps({'wall': wall_ms, 'cpu': cpu_ms}))
'@
    $samples = @()
    foreach ($iteration in 0..31) {
        $raw = & $Interpreter -I -c $probe $TargetDirectory
        Assert-LastExitCode "import timing probe failed: $Interpreter"
        $samples += ($raw | ConvertFrom-Json)
    }
    $wall = @($samples[2..31].wall | Sort-Object)
    $cpu = @($samples[2..31].cpu | Sort-Object)
    $wallMedian = ($wall[14] + $wall[15]) / 2
    $wallP95 = $wall[28]
    $cpuMedian = ($cpu[14] + $cpu[15]) / 2
    $cpuP95 = $cpu[28]
    if (
        $wallMedian -gt 100 -or
        $wallP95 -gt 200 -or
        $cpuMedian -gt 60 -or
        $cpuP95 -gt 100
    ) {
        throw (
            "import budget failed for ${Interpreter}: " +
            "wall=${wallMedian}/${wallP95}ms cpu=${cpuMedian}/${cpuP95}ms"
        )
    }
    Write-Output (
        "${Interpreter}: wall median/p95/max=" +
        "$wallMedian/$wallP95/$($wall[29])ms; " +
        "CPU median/p95/max=$cpuMedian/$cpuP95/$($cpu[29])ms"
    )
}

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$python = (Resolve-Path -LiteralPath $PythonPath).Path
$temporaryBase = [IO.Path]::GetFullPath([IO.Path]::GetTempPath())
$proofRoot = Join-Path $temporaryBase (
    'ocrllm-stage-m-offline-gate-' + [guid]::NewGuid().ToString('N')
)
$sourceArchive = Join-Path $proofRoot 'source.zip'
$sourceRoot = Join-Path $proofRoot 'source'
$wheelDir = Join-Path $proofRoot 'wheel'
$targetDir = Join-Path $proofRoot 'target'
$locationDepth = 0

try {
    Push-Location $repoRoot
    $locationDepth += 1

    $trackedChanges = @(& git status --porcelain --untracked-files=no)
    Assert-LastExitCode 'git status failed'
    if ($trackedChanges.Count -ne 0) {
        throw 'Stage M offline gate requires a clean tracked worktree.'
    }
    $commit = (& git rev-parse HEAD).Trim()
    Assert-LastExitCode 'git rev-parse HEAD failed'

    New-Item -ItemType Directory -Path $proofRoot | Out-Null
    New-Item -ItemType Directory -Path $sourceRoot, $wheelDir, $targetDir |
        Out-Null

    & git archive --format=zip --output=$sourceArchive $commit
    Assert-LastExitCode 'git archive failed'
    Expand-Archive -LiteralPath $sourceArchive -DestinationPath $sourceRoot

    Push-Location $sourceRoot
    $locationDepth += 1
    & uv run --no-project --isolated --with 'Pillow==12.3.0' `
        --with 'pytest>=8,<10' --with 'openai>=2.30,<3' `
        --python $python python -m pytest -q -p no:cacheprovider
    Assert-LastExitCode 'archived-source pytest failed'
    & uv run --no-project --isolated --with 'Pillow==12.3.0' `
        --python $python `
        python -m tests.quality.generators.generate_phase1_fixtures --check
    Assert-LastExitCode 'archived-source fixture check failed'
    & $python -m compileall -q src tests
    Assert-LastExitCode 'archived-source compileall failed'
    Pop-Location
    $locationDepth -= 1

    & uv run --no-project --isolated --with 'build>=1.2' `
        --python $python `
        python -m build --wheel --outdir $wheelDir $sourceRoot
    Assert-LastExitCode 'clean archive wheel build failed'
    $wheel = Get-ChildItem -LiteralPath $wheelDir -Filter *.whl |
        Select-Object -First 1
    if ($null -eq $wheel) {
        throw 'wheel build produced no wheel'
    }
    if ($wheel.Length -gt 262144) {
        throw "base wheel exceeds 256 KiB: $($wheel.Length)"
    }

    & $python -m pip install --no-deps --target $targetDir $wheel.FullName
    Assert-LastExitCode 'isolated base wheel install failed'
    $installedBytes = Get-DirectoryByteCount $targetDir
    if ($installedBytes -gt 1048576) {
        throw "base target exceeds 1 MiB: $installedBytes"
    }

    $baseProbe = @'
import pathlib
import sys

target = pathlib.Path(sys.argv[1]).resolve()
sys.path.insert(0, str(target))
import ocrllm
origin = pathlib.Path(ocrllm.__file__).resolve()
assert target in origin.parents, (target, origin)
loaded = {name.split('.')[0] for name in sys.modules}
forbidden = {
    'PIL', 'pypdfium2', 'openai', 'httpx', 'onnxruntime',
    'miniaudio', '_miniaudio', 'legacy_app',
}
assert not loaded & forbidden, loaded & forbidden
print(ocrllm.__version__, origin)
'@
    Push-Location $temporaryBase
    $locationDepth += 1
    & $python -I -c $baseProbe $targetDir
    Assert-LastExitCode 'outside-repository base import failed'

    $metadataProbe = @'
import importlib.metadata as metadata
import sys

distribution = next(
    item
    for item in metadata.distributions(path=[sys.argv[1]])
    if item.metadata['Name'] == 'ocrllm'
)
requirements = distribution.requires or []
base_requirements = [item for item in requirements if 'extra ==' not in item]
native_payloads = [
    str(path)
    for path in (distribution.files or [])
    if str(path).lower().endswith(('.pyd', '.dll', '.so', '.dylib', '.exe'))
]
declared_extras = set(distribution.metadata.get_all('Provides-Extra') or [])
assert not base_requirements, base_requirements
assert not native_payloads, native_payloads
assert declared_extras == {'audio', 'dashscope', 'dev', 'image', 'ocr'}, declared_extras
print(sorted(declared_extras))
'@
    & $python -I -c $metadataProbe $targetDir
    Assert-LastExitCode 'base wheel metadata check failed'

    $timingInterpreters = @($python)
    $baseInterpreter = 'D:\Anaconda\python.exe'
    if (Test-Path -LiteralPath $baseInterpreter) {
        $timingInterpreters += (Resolve-Path -LiteralPath $baseInterpreter).Path
    }
    foreach ($interpreter in ($timingInterpreters | Select-Object -Unique)) {
        Assert-ImportBudget $interpreter $targetDir
    }

    if (-not $SkipOptionalProfiles) {
        $profileLimits = @{
            'audio' = 8388608
            'image' = 26214400
            'image,dashscope' = 67108864
        }
        $expectedDistributions = @{
            'audio' = @('miniaudio')
            'image' = @('Pillow')
            'image,dashscope' = @('Pillow', 'openai')
        }
        foreach ($profile in @('audio', 'image', 'image,dashscope')) {
            $safeProfile = $profile.Replace(',', '-')
            $profileVenv = Join-Path $proofRoot "venv-$safeProfile"
            & $python -m venv $profileVenv
            Assert-LastExitCode "profile venv creation failed: $profile"
            $profilePython = Join-Path $profileVenv 'Scripts\python.exe'
            $sitePackages = (& $profilePython -I -c `
                'import site; print(site.getsitepackages()[0])').Trim()
            Assert-LastExitCode "site-packages lookup failed: $profile"
            $baselineBytes = Get-DirectoryByteCount $sitePackages
            & $profilePython -m pip install "$($wheel.FullName)[$profile]"
            Assert-LastExitCode "profile install failed: $profile"

            $expectedCsv = $expectedDistributions[$profile] -join ','
            $profileProbe = @'
import importlib.metadata as metadata
import pathlib
import sys

requested = set(sys.argv[1].split(','))
expected_distributions = tuple(sys.argv[2].split(','))
distribution = metadata.distribution('ocrllm')
declared = set(distribution.metadata.get_all('Provides-Extra') or [])
assert requested <= declared, (requested, declared)
for name in expected_distributions:
    assert metadata.version(name)
import ocrllm
loaded = {name.split('.')[0] for name in sys.modules}
assert not loaded & {
    'PIL', 'openai', 'httpx', 'onnxruntime', 'miniaudio', '_miniaudio'
}, loaded
origin = pathlib.Path(ocrllm.__file__).resolve()
assert pathlib.Path(sys.prefix).resolve() in origin.parents, origin
print(sorted(declared))
'@
            & $profilePython -I -c $profileProbe $profile $expectedCsv
            Assert-LastExitCode "profile metadata/import check failed: $profile"

            if ($profile -eq 'image') {
                $imageFixture = Join-Path $profileVenv 'generated-valid.png'
                $imageSmoke = @'
from pathlib import Path
import sys

from PIL import Image
from ocrllm import Config, recognize

path = Path(sys.argv[1])
Image.new('RGB', (8, 6), color=(32, 96, 160)).save(path, format='PNG')

class Provider:
    def recognize_images(self, image_paths, *, prompt, config):
        assert image_paths[0] != path
        with Image.open(image_paths[0]) as image:
            image.verify()
        return '# Generated fixture recognized\n'

result = recognize(path, config=Config(provider=Provider()))
assert result.markdown == '# Generated fixture recognized\n'
assert result.source_type == 'image'
assert result.profile == 'board'
print(result.status)
'@
                $imageSmoke | & $profilePython -I - $imageFixture
                Assert-LastExitCode 'generated image recognition smoke failed'
            }

            if ($profile -eq 'audio') {
                $audioFixture = Join-Path $sourceRoot (
                    'tests\fixtures\audio\a1\mp3\valid_cbr.mp3'
                )
                $audioSmoke = @'
from pathlib import Path
import sys

from ocrllm.audio.probe_short_mp3 import probe_short_mp3

duration = probe_short_mp3(Path(sys.argv[1]))
assert duration == 0.5, duration
print(duration)
'@
                $audioSmoke | & $profilePython -I - $audioFixture
                Assert-LastExitCode 'MP3 probe package smoke failed'
            }

            if ($profile -eq 'image,dashscope') {
                $dashscopeSmoke = @'
from ocrllm import Config, DashScopeSettings, VisionModelSettings

settings = DashScopeSettings(
    region='cn-beijing',
    base_url='https://dashscope.aliyuncs.com/compatible-mode/v1',
    api_key='offline-package-probe',
)
config = Config(
    provider=settings,
    vision_model=VisionModelSettings(name='qwen3.7-plus-2026-05-26'),
)
assert config.provider == settings
assert config.provider is not settings

from ocrllm.providers.dashscope.create_dashscope_openai_client import (
    create_dashscope_openai_client,
)
from ocrllm.providers.dashscope.load_openai import load_openai

openai_module = load_openai()
client = create_dashscope_openai_client(
    openai_module,
    api_key='offline-package-probe',
    settings=settings,
    timeout_seconds=3.0,
)
client.close()
print(openai_module.__version__)
'@
                $dashscopeSmoke | & $profilePython -I -
                Assert-LastExitCode 'DashScope offline construction smoke failed'
            }

            $afterBytes = Get-DirectoryByteCount $sitePackages
            $deltaBytes = $afterBytes - $baselineBytes
            if ($deltaBytes -gt $profileLimits[$profile]) {
                throw (
                    "profile size failed: $profile delta=$deltaBytes " +
                    "limit=$($profileLimits[$profile])"
                )
            }
            Write-Output "$profile installed delta: $deltaBytes bytes"
        }
    }

    Pop-Location
    $locationDepth -= 1
    Write-Output "Stage M offline gate passed for commit $commit"
    Write-Output "wheel bytes: $($wheel.Length); base target bytes: $installedBytes"
} finally {
    while ($locationDepth -gt 0) {
        Pop-Location
        $locationDepth -= 1
    }
    if (Test-Path -LiteralPath $proofRoot) {
        $resolvedProofRoot = [IO.Path]::GetFullPath($proofRoot)
        $requiredPrefix = $temporaryBase.TrimEnd('\') + '\'
        if (-not $resolvedProofRoot.StartsWith(
            $requiredPrefix,
            [StringComparison]::OrdinalIgnoreCase
        )) {
            throw "refusing to remove non-temporary path: $resolvedProofRoot"
        }
        Remove-Item -LiteralPath $resolvedProofRoot -Recurse -Force
    }
}
