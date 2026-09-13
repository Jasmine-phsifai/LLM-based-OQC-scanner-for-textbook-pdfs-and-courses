# ASR 超限证据与两层二等分恢复

维护者在 2026-09-13 要求保留失败截断输出，并将长失败片段等分继续重试；随后确认每段“首次识别 + 最多 2 次重试”，最多两层拆分。120 秒、5% 的既有音频缺口质量阈值保持。

## 责任与公共调用

Model Lab 保存原始 decode、token IDs 和处理后转写工件，在 `output_token_limit` 错误的 `details.generation_output` 返回保存结果和引用。OCRLLM 保存每次失败与源区间的对应关系，拥有尝试预算、切片、checkpoint、恢复与 MD。统筹只配置以下公开选项、调用并读取结果；Crawler 没有识别重试责任。

```python
from ocrllm import AudioGapPolicy, AudioOutputLimitPolicy

result = recognize_audio_to_markdown(
    original_slices,
    provider=local_asr_provider,  # send_audio_prompt=False, capture_error_output=True
    output_path=audio_md,
    audio_output_limit_policy=AudioOutputLimitPolicy(max_retries=2, max_split_depth=2),
    audio_gap_policy=AudioGapPolicy(max_failed_fraction=.05, max_failed_segment_seconds=120),
)
# ordinary resume restores the saved recovery policy without resetting its budget
result = resume_audio_to_markdown(original_slices, provider=local_asr_provider, output_path=audio_md)
```

新策略是显式 opt-in，不能和 `failed_slice_minutes` 同时传入。未启用的 provider、旧一次细分路径和音频校验默认不变。不提高模型输出上限，不把截断文本填进成功 Markdown。

## 有限行为与证据

- 每个源区间最多预留 3 次实际 provider 调用，调用前原子保存；中断且结果未知的预留仍消耗预算，但不算一次已确认的 output-limit 失败。
- 只有预算耗尽且最新已确认错误为 `output_token_limit` 的失败叶允许二等分。每层独立预算，10 分钟最多变为 5 分钟，再变为 2.5 分钟；全树全失败上限为 `3 × (1 + 2 + 4) = 21` 次。成功兄弟不重发。
- 原有暂时错误的分类、有限重试和等待仍由 provider recipe 执行；音频 owner 同时将该次重试上限限制在本叶剩余预算。任何非 output-limit 错误都不触发二分，且打断连续同类失败证明。
- 新预算覆盖该区间的实际调用，包括暂时错误和未知中断；它不保证还会额外拿到 3 次成功响应或 3 次已确认超限。耗尽后明确留 fail/pending，不靠普通恢复重新拿预算。
- 保留一层扁平 `subslots`。二次细分只替换失败叶，父失败的工件引用移入保留的历史；逻辑身份继续由 source hash 和逻辑源区间确定，不以可能重排的列表 index 为身份。
- `result.metadata` 与 `inspect_audio_completion()` 返回 `audio_output_limit_policy`、`output_limit_failure_evidence`、`output_limit_exhausted_segments`，后者包含源区间、深度、预留次数和已确认连续超限次数。调用方不读取 checkpoint 树。

工件引用保存 `request_id`、保存状态、路径/保存失败类型、输入 hash、token 计数和 EOS 等轻量字段。Model Lab 保留正文；客户端不把正文灌入常规观测日志。历史老错误没有工件引用时明确只留下已有描述，不补造原文或声称已经保留。错误响应中的直接 ASR token 计数也提升到公共用量，避免错误工件内有计数而汇总仍未知。

## 恢复与发布

v4 checkpoint 保留策略、每叶预算、深度、失败引用和最终 Markdown 发布 hash，兼容加载既有 v1/v2/v3。完成的 v4 状态也保留，供后续回查失败原文；只有最终 MD 原子写成功后才保存其发布 hash。公共 inspect 必须核对实际文件与发布 hash，防止“最后一段已 checkpoint、最终 MD 尚未替换”的中断把旧 partial MD 误报 complete。恢复可复用全部成功段，只重建 MD。

升级旧恢复任务时，已有 2 分钟子段按已使用一层拆分处理，保留全部成功兄弟；仍失败且已耗尽的旧子段最多再分成两个 1 分钟区间。已保存的 v3 同身份失败次数保留。v1/v2 没有完整历史次数，只承认最新保存的一次超限用于预算，记录 `historical_attempts_unknown=true`；不把这条旧描述当成 3 次同身份失败证明，也不声称迁移前全部历史尝试受新上限约束。

新 150 秒叶超过当前 120 秒缺口阈值，因此最终失败仍是 partial。新策略不暗中放宽 gap 阈值；`complete_with_gaps` 仍需每个缺口 3 次同身份超限证明及调用方给定的时长/比例限制。

## 验证与运行边界

`tools/verify_audio_binary_recovery.py --work-dir <persistent-directory>` 使用真实 FFmpeg 编码媒体、真实 OpenAI SDK 和合成 HTTP，不调用模型。它验证全树 21 次上限、逐次失败工件引用、成功兄弟复用、普通恢复零调用、第三次预留后中断、未知结果不能满足缺口证明、原暂时错误 recipe 被共同预算约束、v2/v3 迁移，以及最终 MD 发布中断后的零推理重建。

这是恢复机制和接口证据，不是识别质量或吞吐提高的证明。真实本地服务返回与新生产部署由统筹协调；本仓不重启服务或改生产 checkpoint。场景结果及实际部署版本由统筹在当前选中仓库保留副本。


本轮结果：最终二层场景全部通过，真实模型调用为 0；45 项既有音频/error 回归、收窄错误数字字段后 27 项 error 回归，以及原 gap/一次细分两个场景均通过。最终 JSON 位于持久验证目录 `asr-binary-recovery-20260913/owner-scenario-final/result.json`，由统筹复制进当前仓库。部署仍须通过真实课程边界的服务和消费者检查。

补充验证：35 项既有 provider-model、轻量导入与公共 import-contract 测试通过。
