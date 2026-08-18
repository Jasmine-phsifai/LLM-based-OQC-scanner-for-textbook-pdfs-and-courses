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

## Working Diary Rule (repo-wide, always on)

This repo is mid-migration: `legacy_app/` is a finished-but-messy UI app,
`src/ocrllm/` is an unfinished library with unproven behavior. Every session
must keep a working diary.

- Every problem **fixed** in `legacy_app/` gets a diary entry in
  `legacy_app/AGENTS.md`.
- Every problem **only observed or suspected** in `legacy_app/` also gets an
  entry. Writing it down beats staying silent, even mid-way through an
  unrelated investigation.
- Each entry must end with a carry-forward judgement: can this same
  error / bug / bad implementation / bad UX re-emerge in `src/ocrllm/` when
  that vertical slice is ported? If yes, write an explicit
  `WARNING FOR src/ocrllm` line.
- Bugs here have repeatedly crossed feature and department boundaries
  (e.g. a Codex-mode crash-resume bug that surfaced as an image-attachment
  failure). Assume implicit coupling exists until proven otherwise.

Future work on this repo runs on two tracks at once: fixing/improving the old
UI app, and implementing the new package. Neither track may silently inherit
the other's defects.

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
