# OCRLLM Repo Boundary Instructions

Read `START_HERE.md` before changing this repo.

## Active Boundary

- `src/ocrllm/` is the active importable Python library.
- Root `tests/` verify the active library import contract.
- New downstream projects must depend on `ocrllm`, not `legacy_app.OCRLLM`.

## Legacy Boundary

- `legacy_app/` is the old application and compatibility surface.
- Launcher, GUI, Codex mode, Google mode, and old provider UI fixes belong
  there unless they are intentionally ported behind the new library API.
- Legacy code may be used as a behavior reference, not as a new public API.

## Suspended Plan

- `Architecture.md` is future planning only.
- Do not reactivate the Rust/PyO3 rewrite without updating
  `MIGRATION_STATUS.md` and proving the Python API boundary is stable.

## Editing Rules

- Keep `import ocrllm` lightweight.
- Keep new library code free of GUI, FastAPI, social downloader, and heavy media
  imports at module import time.
- Keep the recognization features (pdf, audio, video, pictures) ultimately, exclude social media downloading-recognizing workflow ultimately. 
- Keep the application done part by part.
- Record what you edit before each dialogue ends.
- Keep the filename as the functions.
- Port one vertical slice at a time from legacy code.
- Record boundary changes in `MIGRATION_STATUS.md`.
