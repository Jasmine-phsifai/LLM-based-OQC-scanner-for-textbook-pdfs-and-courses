# Active Library Boundary

This directory is the active `ocrllm` package for downstream imports.

Read `../../docs/ACTIVE_STATE_AND_RULES.md` first. It outranks every other
document and carries current state, the open defect register, and the coding and
documentation rules. Then read `../../docs/ocrllm_library_go_no_go.md` for phase
gates and file responsibilities.

The approved current work is the `#065 Unified Execution Queue` in
`../../docs/ACTIVE_STATE_AND_RULES.md`; the older Stage M/A plan supplies detail
only where that queue has not superseded it. #078 closed P1-c with one bounded
16-page Google run through exactly two serial image requests, complementing the
existing offline resume and installed-wheel proofs. P1-d minimal manual PDF
repair is now the immediate queue. Do not broaden it into a general repair
framework or start provider generalization in its place.

`contracts/` and `worker/` are frozen. Do not change them.

## Keep

- A small public facade in `__init__.py`.
- Import-time dependencies minimal.
- Tests in the root `tests/` directory.
- File output optional.
- Provider behavior injected or isolated behind explicit adapters.

## Avoid

- Importing from `legacy_app` or uppercase `OCRLLM`.
- Pulling GUI, FastAPI, social downloader, browser automation, or heavy media
  packages during `import ocrllm`.
- Copying whole legacy modules into the new package.
- Exposing legacy processor classes as public API without a tested facade.
- Adding PyMuPDF or `fitz`; the gated PDF slice uses PDFium through
  `pypdfium2`.
- Adding HarmonyOS/ArkTS work or claims; that integration is deferred.
- Extending `contracts/` or `worker/`. Both are frozen until a consumer exists.
- Returning success for provider output that is empty, control-only, or
  refusal-shaped.
- Adding a code path that can block on an external party without a
  caller-visible bound.
- Adding automatic retry, model switch, key rotation, or provider fallback
  inside an adapter. Expose disposition; let the caller act.
- Trusting a capability claim in prose. Verify against code and tests;
  documentation in this repo is known to lag.

## When Porting Legacy Behavior

Port one vertical slice at a time:

1. Define the public behavior in root tests.
2. Extract only the needed logic.
3. Keep dependencies optional when they are not required for `import ocrllm`.
4. Update `MIGRATION_STATUS.md` if the active boundary changes.
5. Do not begin the next phase until the current GO gate passes.
