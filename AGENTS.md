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

## Provider Test Authority

- Google APIs are directly authorized for image and audio robustness testing.
  They are free for this account, so no separate budget confirmation is needed
  before a bounded Google test run.
- Discover the currently served Google models from the live API. One credential
  can expose many models, and the catalog changes; do not replace discovery with
  a hardcoded support list.
- Treat window limits, refreshed quotas, temporary overload, API errors, empty
  replies, unsupported formats, and excessive image counts as expected robustness
  inputs. Tests must prove honest errors, bounded behavior, and no false success.
- Google audio has fewer compatible models than Google image/multimodal input.
  Verify audio capability from the current catalog and a small real request before
  choosing a model. Native multimodal models remain valid audio test candidates.
- Keep credentials private and use synthetic, committed, or otherwise authorized
  inputs. Direct test authorization does not authorize publishing user data.
- Social-media download and recognition work is deferred. Do not use this Google
  authority to expand or resume the social-media feature surface.

## Legacy Parent Evidence Rule

- The legacy application is the behavioral parent of the new library. A bug that
  occurred in a real legacy run is strong evidence and deserves extra scrutiny
  when the related capability is ported.
- Do not assume the child library has inherited the bug. First prove that the
  analogous code path exists, then add the smallest regression and fix that covers
  the proven risk. If the capability is not present yet, record a warning instead
  of adding speculative machinery.
- Do not make a port stronger or broader than the legacy product unless the user
  separately asks for that product change. Defensive code must remain readable;
  future-agent comprehension is part of sustainability.
- Windows paths beyond about 260 characters caused real multi-stage legacy
  failures. The independent incident record is in `legacy_app/AGENTS.md` under
  `2026-08-18: path handling and silent-refusal "fake success"`. When a new
  filesystem-producing capability is ported, test long output and temporary paths,
  while keeping path-component sanitization distinct from extended-length handling.

## Suspended Plan

- `Architecture.md` is future planning only.
- Do not reactivate the Rust/PyO3 rewrite without updating
  `MIGRATION_STATUS.md` and proving the Python API boundary is stable.

## Temporary Git Fork Workflow

- The active GitHub CLI account is `Jasmine-phsifai`.
- `origin` is the personal fork:
  `https://github.com/Jasmine-phsifai/LLM-based-OQC-scanner-for-textbook-pdfs-and-courses.git`.
- `upstream` is the original repository:
  `https://github.com/honggoldgoldgold/LLM-based-OQC-scanner-for-textbook-pdfs-and-courses.git`.
- Push work to `origin`; fetch or compare the original repository through
  `upstream`. Do not push to `upstream` unless its write permission is restored.
- Ordinary Git operations use the active GitHub CLI account's HTTPS credential
  helper. Do not print, export, or persist its token in commands, logs, tracked
  files, or work records.
- This is a temporary handoff because the active account can read the original
  repository but cannot write to it. Do not replace these remotes merely to
  work around a transient network or credential failure.

## Working Diary Rule (repo-wide, always on)

This repo is mid-migration: `legacy_app/` is the maintained compatibility app,
and `src/ocrllm/` is the active library with a proven image slice and partially
implemented Stage M maturation work. Every session must keep a working diary.

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

- Keep each heartbeat iteration atomic with one independently verifiable goal.
- Delegate dependency downloads, long installs, and repetitive active polling to
  a lightweight subagent when available. While it waits, the primary agent
  should continue independent review, documentation, or analysis rather than
  repeatedly polling the same task.
- Keep `import ocrllm` lightweight.
- Keep new library code free of GUI, FastAPI, social downloader, and heavy media
  imports at module import time.
- Keep the recognization features (pdf, audio, video, pictures) ultimately, exclude social media downloading-recognizing workflow ultimately. 
- Social-media features are explicitly delayed; do not select them for heartbeat work.
- Keep the application done part by part.
- Record what you edit before each dialogue ends.
- Keep the filename as the functions.
- Port one vertical slice at a time from legacy code.
- Record boundary changes in `MIGRATION_STATUS.md`.
