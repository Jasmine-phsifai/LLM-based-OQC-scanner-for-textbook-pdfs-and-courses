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

function Add-ExecutableDirectoryToPath {
    param(
        [string]$Name,
        [string[]]$CandidatePaths
    )
    if ($null -ne (Get-Command $Name -CommandType Application -ErrorAction SilentlyContinue)) {
        return
    }
    foreach ($candidate in $CandidatePaths) {
        if ($candidate -and (Test-Path -LiteralPath $candidate -PathType Leaf)) {
            $directory = Split-Path -Parent (Resolve-Path -LiteralPath $candidate).Path
            $env:PATH = $directory + [IO.Path]::PathSeparator + $env:PATH
            if ($null -ne (Get-Command $Name -CommandType Application -ErrorAction SilentlyContinue)) {
                return
            }
        }
    }
    throw "required executable is unavailable: $Name"
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
    'miniaudio', '_miniaudio', 'google', 'cv2', 'numpy', 'imageio_ffmpeg', 'legacy_app',
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
$originalPath = $env:PATH
$pythonEnvironment = Split-Path -Parent $python
$condaEnvironments = Split-Path -Parent $pythonEnvironment
$condaRoot = Split-Path -Parent $condaEnvironments
$uvCandidates = @(
    (Join-Path $condaRoot 'Scripts\uv.exe'),
    (Join-Path $pythonEnvironment 'Scripts\uv.exe')
)
$nodeCandidates = @((Join-Path $pythonEnvironment 'node.exe'))
if (Test-Path -LiteralPath $condaEnvironments -PathType Container) {
    $nodeCandidates += @(
        Get-ChildItem -LiteralPath $condaEnvironments -Directory |
            ForEach-Object { Join-Path $_.FullName 'node.exe' }
    )
}
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
    Add-ExecutableDirectoryToPath -Name 'uv' -CandidatePaths $uvCandidates
    Add-ExecutableDirectoryToPath -Name 'node' -CandidatePaths $nodeCandidates
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
        --with 'google-genai>=2.9,<3' --with 'miniaudio>=1.71,<2' `
        --with 'pypdfium2==5.11.0' --with 'opencv-python>=4.13,<4.14' `
        --with 'imageio-ffmpeg>=0.6,<0.7' `
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
    'miniaudio', '_miniaudio', 'google', 'cv2', 'numpy', 'imageio_ffmpeg', 'legacy_app',
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
assert declared_extras == {
    'audio', 'dashscope', 'dev', 'google', 'image', 'ocr', 'pdf-vision', 'video'
}, declared_extras
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
            'google' = 67108864
            'audio,google' = 67108864
            'pdf-vision' = 36700160
            'video' = 230686720
        }
        $expectedDistributions = @{
            'audio' = @('miniaudio')
            'image' = @('Pillow')
            'image,dashscope' = @('Pillow', 'openai')
            'google' = @('google-genai')
            'audio,google' = @('miniaudio', 'google-genai')
            'pdf-vision' = @('pypdfium2', 'Pillow')
            'video' = @('opencv-python', 'numpy', 'imageio-ffmpeg')
        }
        foreach ($profile in @(
            'audio',
            'image',
            'image,dashscope',
            'google',
            'audio,google',
            'pdf-vision',
            'video'
        )) {
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
    'PIL', 'pypdfium2', 'openai', 'httpx', 'onnxruntime', 'miniaudio',
    '_miniaudio', 'google', 'cv2', 'numpy', 'imageio_ffmpeg'
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

from ocrllm.audio.snapshot_short_mp3 import snapshot_short_mp3

with snapshot_short_mp3(Path(sys.argv[1]), temp_dir=Path(sys.argv[2])) as snapshot:
    assert snapshot.path.name == 'source.mp3', snapshot.path
    assert snapshot.duration_seconds == 0.5, snapshot.duration_seconds
    print(snapshot.duration_seconds)
'@
                $audioSmoke | & $profilePython -I - $audioFixture $profileVenv
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

            if ($profile -eq 'google') {
                $googleSmoke = @'
from ocrllm import GoogleGenAISettings
from ocrllm.providers.google_genai.load_google_genai import load_google_genai

settings = GoogleGenAISettings(api_key='offline-package-probe')
assert 'offline-package-probe' not in repr(settings)
google_module = load_google_genai()
assert callable(google_module.Client)
assert callable(google_module.types.HttpOptions)
assert callable(google_module.types.Part.from_bytes)
client = google_module.Client(
    api_key=settings.api_key,
    http_options=google_module.types.HttpOptions(timeout=3000),
)
client.close()
print(google_module.__version__)
'@
                $googleSmoke | & $profilePython -I -
                Assert-LastExitCode 'Google GenAI offline construction smoke failed'
            }

            if ($profile -eq 'audio,google') {
                $audioFixture = Join-Path $sourceRoot (
                    'tests\fixtures\audio\a1\mp3\valid_cbr.mp3'
                )
                $googleAudioSmoke = @'
from pathlib import Path
import sys

from ocrllm import GoogleGenAISettings
from ocrllm.audio.snapshot_short_mp3 import snapshot_short_mp3
from ocrllm.providers.google_genai.build_google_genai_audio_request import (
    build_google_genai_audio_request,
)
from ocrllm.providers.google_genai.load_google_genai import load_google_genai

fixture = Path(sys.argv[1])
temporary_parent = Path(sys.argv[2])
model = 'gemini-offline-package-probe'
prompt = 'Transcribe this short audio.'
with snapshot_short_mp3(fixture, temp_dir=temporary_parent) as snapshot:
    request = build_google_genai_audio_request(
        snapshot.path,
        prompt=prompt,
        model=model,
    )
    assert request.model == model
    assert request.contents[0] == prompt
    assert request.contents[1].mime_type == 'audio/mpeg'
    assert request.inline_byte_count == snapshot.byte_size
    google_module = load_google_genai()
    part = google_module.types.Part.from_bytes(
        data=request.contents[1].data,
        mime_type=request.contents[1].mime_type,
    )
    assert part.inline_data.mime_type == 'audio/mpeg'

settings = GoogleGenAISettings(api_key='offline-package-probe')
client = google_module.Client(
    api_key=settings.api_key,
    http_options=google_module.types.HttpOptions(timeout=3000),
)
client.close()
print(snapshot.duration_seconds, request.wire_byte_upper_bound)
'@
                $googleAudioSmoke | & $profilePython -I - `
                    $audioFixture $profileVenv
                Assert-LastExitCode (
                    'Google GenAI audio offline construction smoke failed'
                )
            }

            if ($profile -eq 'pdf-vision') {
                $pdfiumSmoke = @'
import json
from pathlib import Path
import sys

from PIL import Image
import pypdfium2 as pdfium
from ocrllm import (
    Config,
    RecognitionExecutionPolicy,
    RecognitionPreferences,
    recognize,
)

assert pdfium.PYPDFIUM_INFO.api_tag == (5, 11, 0)
assert pdfium.PYPDFIUM_INFO.beta is None
assert callable(pdfium.PdfDocument)

smoke_root = Path(sys.argv[1]) / 'pdf-public-smoke'
smoke_root.mkdir()
pdf_path = smoke_root / 'generated-valid.pdf'
output_directory = smoke_root / 'output'
with pdfium.PdfDocument.new() as created:
    for page_index in range(16):
        created_page = created.new_page(72 + page_index * 2, 72)
        created_page.close()
    created.save(pdf_path)
assert created.raw is None

class Provider:
    resume_identity = 'offline-installed-pdf-provider-v1'

    def __init__(self):
        self.calls = []
        self.widths = []
        self.active_calls = 0
        self.maximum_active_calls = 0

    def recognize_images(self, image_paths, *, prompt, config):
        self.active_calls += 1
        self.maximum_active_calls = max(
            self.maximum_active_calls,
            self.active_calls,
        )
        try:
            paths = tuple(Path(path) for path in image_paths)
            assert len(paths) == 8
            assert 'input order' in prompt
            self.calls.append(tuple(path.name for path in paths))
            for path in paths:
                with Image.open(path) as rendered:
                    assert rendered.format == 'PNG'
                    rendered.load()
                    self.widths.append(rendered.width)
            return f'Installed PDF group {len(self.calls)}.'
        finally:
            self.active_calls -= 1

provider = Provider()
result = recognize(
    pdf_path,
    config=Config(
        provider=provider,
        output_dir=output_directory,
        temp_dir=smoke_root / 'snapshots',
        execution=RecognitionExecutionPolicy(max_parallel_requests=4),
        preferences=RecognitionPreferences(review_passes=0),
    ),
)

expected_calls = [
    tuple(f'page-{page_number:06d}.png' for page_number in range(1, 9)),
    tuple(f'page-{page_number:06d}.png' for page_number in range(9, 17)),
]
assert provider.calls == expected_calls
assert provider.widths == sorted(provider.widths)
assert len(set(provider.widths)) == 16
assert provider.maximum_active_calls == 1
assert result.source_type == 'pdf'
assert result.profile == 'board'
assert result.status == 'complete'
assert result.output_path == output_directory / 'generated-valid_board.md'
assert result.output_path.read_text(encoding='utf-8') == result.markdown
assert result.markdown.count('<!-- ocrllm:pdf-pages') == 2
assert '<!-- ocrllm:pdf-pages start=1 end=8 -->' in result.markdown
assert '<!-- ocrllm:pdf-pages start=9 end=16 -->' in result.markdown
assert result.metadata['page_count'] == 16
assert result.metadata['pdf_group_count'] == 2
assert result.metadata['pages_per_group'] == 8
assert result.metadata['provider_call_count'] == 2
assert result.metadata['current_run_provider_call_count'] == 2

state_directory = output_directory / 'generated-valid_board'
state_paths = tuple(state_directory.glob('*.ocrllm-state.json'))
assert len(state_paths) == 2
for state_path in state_paths:
    state = json.loads(state_path.read_text(encoding='utf-8'))
    assert state['state_version'] == 'ocrllm.image-resume.v2'
    assert state['result']['status'] == 'complete'
assert len(tuple(state_directory.glob('*.md'))) == 2
assert not tuple(state_directory.glob('page-*.png'))
assert not tuple(state_directory.glob('.p-*.tmp.png'))
assert not any(
    path.exists()
    for call in provider.calls
    for path in (state_directory / name for name in call)
)
assert {path.name for path in output_directory.iterdir()} == {
    'generated-valid_board',
    'generated-valid_board.md',
}
snapshot_parent = smoke_root / 'snapshots'
assert snapshot_parent.is_dir()
assert not tuple(snapshot_parent.iterdir())
assert pdf_path.is_file()
print(
    pdfium.PYPDFIUM_INFO.tag,
    pdfium.PDFIUM_INFO.tag,
    result.metadata['pdf_group_count'],
)
'@
                $pdfiumSmoke | & $profilePython -I - $profileVenv
                Assert-LastExitCode 'installed public PDF recognition smoke failed'
            }

            if ($profile -eq 'video') {
                $videoSmoke = @'
from pathlib import Path
import subprocess
import sys

import cv2
import imageio_ffmpeg
import numpy as np
from ocrllm import (
    RetainedVideoFrame,
    VideoInfo,
    extract_video_audio,
    extract_video_frames,
    inspect_video,
)

path = Path(sys.argv[1]) / 'generated-valid.mp4'
writer = cv2.VideoWriter(
    str(path),
    cv2.VideoWriter_fourcc(*'mp4v'),
    5.0,
    (32, 24),
)
assert writer.isOpened()
try:
    for index in range(10):
        writer.write(np.full((24, 32, 3), index * 20, dtype=np.uint8))
finally:
    writer.release()

info = inspect_video(path)
assert type(info) is VideoInfo
assert info.frame_count == 10
assert info.frames_per_second == 5.0
assert info.duration_seconds == 2.0
assert info.width_pixels == 32
assert info.height_pixels == 24
frames = extract_video_frames(path, output_dir=Path(sys.argv[1]) / 'video-output')
assert type(frames) is tuple
assert frames
assert all(type(frame) is RetainedVideoFrame for frame in frames)
assert all(frame.path.is_file() for frame in frames)
assert [frame.frame_index for frame in frames] == sorted(
    frame.frame_index for frame in frames
)
assert not list((Path(sys.argv[1]) / 'video-output').glob('.ocrllm-video-*'))
audio_source = Path(sys.argv[1]) / 'generated-with-audio.mp4'
completed = subprocess.run(
    [
        imageio_ffmpeg.get_ffmpeg_exe(),
        '-nostdin', '-hide_banner', '-loglevel', 'error', '-y',
        '-i', str(path),
        '-f', 'lavfi', '-i', 'sine=frequency=440:sample_rate=16000:duration=2',
        '-shortest', '-c:v', 'copy', '-c:a', 'aac', str(audio_source),
    ],
    check=False,
    stdin=subprocess.DEVNULL,
    stdout=subprocess.DEVNULL,
    stderr=subprocess.DEVNULL,
    timeout=30,
)
assert completed.returncode == 0
audio_output = Path(sys.argv[1]) / 'audio.mp3'
assert extract_video_audio(audio_source, output_path=audio_output) == audio_output
assert audio_output.is_file() and audio_output.stat().st_size > 0
assert not list(Path(sys.argv[1]).glob('.ocrllm-audio-*'))
print(info, len(frames), audio_output.stat().st_size)
'@
                $videoSmoke | & $profilePython -I - $profileVenv
                Assert-LastExitCode 'installed public video inspection smoke failed'
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
    $env:PATH = $originalPath
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
