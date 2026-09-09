# OCRLLM Library Migration Decision

Status: foundational migration decision.

This file records why the repository was split into active and legacy code.
The authoritative implementation GO/NO-GO record is now
`docs/ocrllm_library_go_no_go.md`. Use that file for current phase order, file
responsibilities, PDFium, migration, rewrite, and rejection rules.

## Current narrow audio contract addition (2026-09-09, #730)

Explicit AudioGapPolicy, retained accepted-gap checkpoints and public audio
completion inspection keep recognition evidence and quality decisions in
OCRLLM. The orchestrator supplies thresholds and consumes complete versus
complete_with_gaps; it does not parse or mutate recognition state. No default
acceptance threshold or broad retry framework is introduced.

## What I Found

The existing OCRLLM codebase has useful product behavior, but it is shaped like
an application, not a library:

- The importable package was uppercase `OCRLLM`, while the desired dependency
  surface is lowercase `ocrllm`.
- The old root had no `pyproject.toml`, so downstream projects could not depend
  on it as a normal Python package.
- GUI, FastAPI, social download, CLI, processors, prompts, and core logic shared
  the same package surface.
- Default output and temporary paths were package-relative, which is hostile to
  installed library usage.
- The old architecture plan correctly identified structural rot, but its
  Rust/PyO3 rewrite path was too early for the immediate goal of reuse by other
  projects.

## Decision

Create a new Python-first library package at `src/ocrllm` and move the old app
code under `legacy_app/`.

The new library starts with a narrow, stable facade:

- `ocrllm.Config`
- `ocrllm.RecognitionResult`
- `ocrllm.recognize`
- `ocrllm.recognize_batch`
- public exception types

The initial facade scaffold routes board/image recognition through an injected
provider. It is not completed image support. PDF, audio, video, provider HTTP
clients, and Rust internals were not part of that first import contract.

The later execution decision makes the boundary more precise:

- The original injected-provider scaffold was a Phase 0 facade. Phase 0 is now
  GO. Phase 1 now has one offline-tested built-in DashScope adapter, but its
  licensed corpus/scorer and required live-quality evidence are still
  incomplete, so Phase 1 remains NO-GO.
- Active PDF work uses PDFium through `pypdfium2`; PyMuPDF/`fitz` remains
  legacy-only.
- A versioned JSON-safe contract and Electron JSONL worker proof happen before
  broad distribution work.
- HarmonyOS/ArkTS integration is deferred.

## Why This Path

This path creates something another project can safely import now without
inheriting the whole legacy application.

It avoids three failure modes:

- A full rewrite that takes too long before becoming usable.
- Direct downstream imports from legacy internals that freeze bad boundaries.
- Premature Rust/PyO3 packaging complexity before the Python API proves itself.

The old code remains available as a reference implementation and behavior oracle
under `legacy_app/`, but new projects should depend only on `src/ocrllm`.

## Current Repo Shape

```text
START_HERE.md                         One-screen active/legacy/suspended map.
AGENTS.md                             Repo-level boundary instructions.
src/ocrllm/                           New importable library package.
src/ocrllm/README_ACTIVE_LIBRARY.md   Local active-library boundary.
src/ocrllm/AGENTS.md                  Local active-library agent rules.
tests/                                New import-contract tests.
legacy_app/                           Old application code and old tests/docs.
legacy_app/README_LEGACY.md           Local legacy-app boundary.
legacy_app/AGENTS.md                  Local legacy-app agent rules.
docs/legacy_bilibili_social_long_debug_record.md
                                      Legacy Bilibili course runtime record.
docs/ocrllm_library_go_no_go.md       Active execution and GO/NO-GO record.
Architecture.md                       Suspended future Rust/PyO3 reference.
```

## Done Means

The migration is only useful when these are true:

- `pip install -e .` succeeds.
- `import ocrllm` works from outside the repo root.
- The public API can be tested with fake providers.
- No import of `ocrllm` pulls GUI, FastAPI, social download, or heavyweight
  media dependencies.
- File output is optional; `output_dir=None` keeps results in memory.

## Future Work

Do not use this historical list as an implementation queue. Follow the current
phase and exact GO gate in `docs/ocrllm_library_go_no_go.md`.
