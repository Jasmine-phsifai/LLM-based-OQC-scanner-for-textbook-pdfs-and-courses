# OCRLLM Repo Boundary Instructions

Read `docs/ACTIVE_STATE_AND_RULES.md` first, then `START_HERE.md`, before
changing this repo. `docs/ACTIVE_STATE_AND_RULES.md` outranks every other
document and carries current state, the open defect register, and the coding and
documentation rules.

Documentation in this repo is known to lag the code. Verify capability claims
against code and tests before relying on them.

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

## Temporary Git Fork Workflow

- The active GitHub CLI account is `Jasmine-phsifai`.
- `origin` is the personal fork:
  `git@github.com:Jasmine-phsifai/LLM-based-OQC-scanner-for-textbook-pdfs-and-courses.git`.
- `upstream` is the original repository:
  `https://github.com/honggoldgoldgold/LLM-based-OQC-scanner-for-textbook-pdfs-and-courses.git`.
- Push work to `origin`; fetch or compare the original repository through
  `upstream`. Do not push to `upstream` unless its write permission is restored.
- This workspace uses the repository-local SSH key
  `C:/Users/OMG/.ssh/supervised_win11_ed25519` through `core.sshCommand`; do not
  print or upload the private key.
- This is a temporary handoff because the active account can read the original
  repository but cannot write to it. Do not replace these remotes merely to
  work around a transient network or credential failure.

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
