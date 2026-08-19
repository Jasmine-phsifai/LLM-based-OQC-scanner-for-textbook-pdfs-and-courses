# OCRLLM Migration Status

This is a navigation aid. The authoritative current state, open defects, and
documentation rules are in
[`docs/ACTIVE_STATE_AND_RULES.md`](docs/ACTIVE_STATE_AND_RULES.md). If this
file and that file differ, that file wins.

## Current Status

Last synchronized: 2026-08-19.

The repository has two boundaries:

| Boundary | Status | Use |
|---|---|---|
| `src/ocrllm/` | Active library | New imports, stable API, root tests. |
| `legacy_app/` | Maintained compatibility app | GUI, CLI, FastAPI, social workflows, and behavior reference. |

The active library has GO coverage for the image contract, local OCR, the
development JSONL worker, provider error disposition, credential scheduling,
and image resume. Stage M Phase 1 maturation is partially implemented:

- shipped: lazy DashScope catalog checks, atomic file-backed image state, and
  an opt-in candidate model queue;
- open: complete attempt-spend disclosure, all approved recovery dispositions,
  model-aware credential scheduling, flowed output, and resume identity
  migration;
- not started: Stage 2 vision/audio provider splitting, Stage A mp3 recognition,
  and the active PDFium phase.

The current open defect register is in
[`docs/ACTIVE_STATE_AND_RULES.md`](docs/ACTIVE_STATE_AND_RULES.md): residual
D4 plus G1, G2, G3, G4, G5, G6, G7, G8, and G10. D1-D7 and F1-F4 are closed;
G9 is closed. Do not create a second defect list in this file.

## Read Order

1. [`docs/ACTIVE_STATE_AND_RULES.md`](docs/ACTIVE_STATE_AND_RULES.md) for
   current truth, defects, rules, and precedence.
2. [`START_HERE.md`](START_HERE.md) for the one-screen repository map.
3. [`docs/plan_phase1_maturation_and_phase2_audio.md`](docs/plan_phase1_maturation_and_phase2_audio.md)
   for the current Stage M and Stage A plan.
4. [`docs/ocrllm_library_go_no_go.md`](docs/ocrllm_library_go_no_go.md) for
   execution gates and migrate/rewrite/reject boundaries.
5. [`src/ocrllm/README_ACTIVE_LIBRARY.md`](src/ocrllm/README_ACTIVE_LIBRARY.md)
   and [`src/ocrllm/AGENTS.md`](src/ocrllm/AGENTS.md) for package work.
6. [`legacy_app/AGENTS.md`](legacy_app/AGENTS.md) for legacy maintenance and
   the working diary.

## Boundary Rules

- New projects import only `ocrllm`, never `legacy_app.OCRLLM`.
- Port one tested vertical slice at a time; do not copy legacy modules
  wholesale.
- Keep GUI, FastAPI, social downloading, browser automation, and heavy media
  dependencies out of plain `import ocrllm`.
- `worker/` and `contracts/` are frozen until a real consumer justifies a
  protocol revision in the same slice.
- Active PDF work uses PDFium through `pypdfium2`; do not add PyMuPDF or
  `fitz`.
- HarmonyOS/ArkTS and the Rust/PyO3 rewrite are deferred/suspended and are not
  current work.
- `output/`, `temp/`, caches, and local screenshots are runtime or supplemental
  artifacts, not architecture evidence.

## Verification

Run from the repository root with the maintained environment:

```powershell
& 'D:\Anaconda\envs\OCRLLM\python.exe' -m pytest -q -p no:cacheprovider
& 'D:\Anaconda\envs\OCRLLM\python.exe' -m compileall -q src tests
& 'D:\Anaconda\envs\OCRLLM\python.exe' -c "import sys,time; sys.path.insert(0, 'src'); t=time.perf_counter(); import ocrllm; print(round(time.perf_counter()-t, 4), len(sys.modules), [m for m in ('PIL','openai','httpx','onnxruntime') if m in sys.modules])"
```

The clean Git-archive wheel, isolated install, outside-repository import, and
heavy-module guard are defined in
[`docs/ocrllm_library_go_no_go.md`](docs/ocrllm_library_go_no_go.md). A paid
live gate requires an explicit maintainer budget and confirmed region/endpoint.

## History Trace

Detailed records remain in dated Markdown files. This table keeps the migration
route without presenting old conclusions as current status.

| Commit | Trace |
|---|---|
| `0278b66` | Phase 1 v17 image evidence and clean package gate. |
| `2db456a` | Phase 2 development worker gate. |
| `8025406` | D1-D7 defect repair. |
| `2f39428` | F1-F4 audit closure and legacy refusal/timeout/partial-failure protections. |
| `a19776d` | Stage M model discovery and candidate queue. |
| `4c5293d` | DashScope catalog first-fetch failure changed to fail closed. |
| `3c6e985` | Legacy PDF batch retry and provider classification fixes. |
| `b8d42a2` | Legacy checkpoint visibility/resume filtering fix. |
| `6f2bf8a` | Legacy PDF repair-mode workflow. |
| `78a2fa6` | Legacy repair-range expansion and partial-failure reporting. |
| `42c0f75` | Legacy settings/model fetch moved to the current picker boundary. |

The complete legacy incident trace, including carry-forward warnings for future
library ports, is in [`legacy_app/AGENTS.md`](legacy_app/AGENTS.md). Historical
`docs/phase*`, decision, checkpoint, and review files are immutable records;
read them only to understand why a past decision was made.