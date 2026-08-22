# Provider Cost And Reliability Policy

Status: user-confirmed operational policy.

Decision date: 2026-07-11. Google test authority updated 2026-08-23.

This file records account-specific cost and reliability facts that influence
future provider selection. It does not make a deferred provider available and
does not replace the phase gates in `ocrllm_library_go_no_go.md`.

## Proven Phase 1 Decision

- The user's Aliyun/DashScope API workflows use the Beijing region. For the
  current credential, use canonical region `cn-beijing` with the confirmed
  OpenAI-compatible endpoint
  `https://dashscope.aliyuncs.com/compatible-mode/v1`.
- Qwen image recognition is billed independently by usage. On 2026-07-11 the
  user authorized unrestricted API use for implementation and robustness
  testing. Each comparable gate still declares its complete call plan before
  dispatch; never selectively retry one fixture or hide failed evidence.
- A single-draft review configuration makes two same-model provider calls per
  recognition. The v6 gate therefore used 13 recognition invocations and 26
  provider calls.
- The v8 robustness gate explicitly requests two independent drafts plus one
  consensus review: 13 recognition invocations and 39 provider calls. Consensus
  is quality work, not retry or provider fallback; ordinary library recognition
  remains one call by default.
- The v10 gate keeps the same 39-call maximum and exact plan but changes its
  composition to one Qwen3.7 primary plus two `qwen-vl-max` visual-sign scouts
  per recognition. Scout mode is explicit and defaults off. Qwen-VL scout prose
  is never returned; only a bounded two-scout standalone-sign quorum can alter
  primary Markdown locally.
- V11 raises the scout count from two to three and uses a two-of-three quorum.
  Its fixed comparable gate is therefore 13 recognitions and 52 calls. The
  third scout improves missing-sign quorum probability without adding a slow
  generative rewrite; it remains explicit and defaults off.
- The Phase 1 model remains `qwen3.7-plus-2026-05-26` unless the authoritative
  decision is changed before collecting a new complete evidence set.
- The v17 Beijing gate completed both full runs and all 52 planned calls. Phase
  1 is GO; provider changes require a new capability decision and evidence set,
  not a silent substitution inside the proven workflow.

## Future Provider Inputs

These are user-supplied account facts, not universal pricing claims. Reconfirm
entitlements and current product terms before a large run.

- Aliyun FileTrans ASR is covered by the user's previously purchased token
  package plan and is suitable for large audio robustness tests without
  incremental usage cost under that account. FileTrans remains Phase 4 work;
  this policy does not authorize audio implementation during Phase 1.
- Google models are available without usage cost to the user and are directly
  authorized for robustness testing without a separate budget request. They are
  intentionally useful as a demanding test source because observed behavior
  includes refreshing quota windows, service overload, API errors, empty replies,
  unsupported input formats, and excessive-image rejection. A Google path must
  surface those outcomes honestly rather than turning them into success.
- Query the live Google model catalog when selecting a test model. One API key can
  serve many models and the set changes; do not treat a repository list as current
  availability. Audio support is narrower than image/multimodal support, so confirm
  audio capability with the live catalog and a small request. Native multimodal
  models remain strong audio candidates when the API reports support.
- This authorization permits purposeful, bounded Google image/audio calls with
  authorized inputs. It does not activate a deferred adapter, authorize hidden or
  unbounded retry, expose credentials, or resume deferred social-media work.
- The user describes Codex Mini 5.4 as inexpensive and very stable, but not
  free. Treat that name as a user-facing provider choice until a future adapter
  decision pins an exact API model identifier and verifies current availability.

## Library Architecture Consequences

- Do not hard-code prices, token-package balances, or free-tier assumptions in
  the recognition core. They drift and may be account-specific.
- Keep provider capability, cost preference, stability preference, rate policy,
  and media processing as separate responsibilities. A future execution-policy
  object may rank approved workflows, but it must not turn one `Config` into an
  implicit multi-provider state machine.
- Provider pools, automatic switching, new Google/Codex adapters, and FileTrans
  remain behind their phase decisions. Direct Google test authority applies to
  already available test paths; it does not itself activate a new adapter.
- Every paid or quota-consuming evidence run records its exact call plan before
  dispatch and preserves failures rather than cherry-picking a better result.
- The four screenshots and PDF under `docs/` are authorized as private local
  testing data. Use and provider submission are allowed. Keep them untracked and
  do not redistribute or commit them unless the user separately grants that
  permission. PDF implementation remains behind its phase gate.

## Change Rule

Update this file and the authoritative current-state decision together when a
provider's billing, entitlement, model identifier, region, test authorization,
or observed reliability changes. Never commit credentials or account balances.
