# ASR 二分仅用于 token 超限（2026-09-16）

本轮按用户当前要求收回 `fe68015` 将 `generation_repetition` 纳入二分的扩展。当前相同音频若连续返回循环错误，最多首次请求加两次重试，仍失败则保留 FAIL；其他音频区间继续运行。生成失败的原始截断/循环输出工件及 request 引用保留，不当成成功正文。只有已批准的规范 `output_token_limit` 错误可继续等分恢复；不扩展到 `context_length_exceeded`、校验失败、权限或服务错误，也不改变其他 provider 默认行为。

## 责任与接口

实现位于 OCRLLM 的现有 ASR 执行/恢复 owner，Model Lab 服务与统筹重试代码均未更改。

- `AudioOutputLimitPolicy(max_retries=2, max_split_depth=2)` 的真实输出上限行为不变：每个范围至多 3 次预留，仍符合分类才可二分，最多两层。预留计数持久保存，普通 resume 不重置。
- 循环错误使用剩余同范围预算，绝不授权二分、token 恢复优先资格或接受缺口。达到预算后普通 resume 为零新增调用。原有暂时错误策略仍在持久剩余预算内执行。
- 保留 v4 内部兼容字段 `output_limit_evidence`，不迁移或重写历史树。公开 `output_limit_failure_evidence` 仅含真实 cap；新增 `generation_repetition_failure_evidence` 保存 loop 引用，`generation_repetition_failed_segments` 明确范围、已预留/剩余次数及 `retry_exhausted`。统筹可存公开结果，不能读取树或重新实现分类。
- `output_limit_recovery_candidates` 同时过滤 loop 叶和仅由 loop 祖先派生的未开始叶。失败证据存在不等于获得 token 恢复资格。已完成但 Markdown 尚待发布仍可按原契约零推理补发布。
- 失败证据分类仍包含循环供安全停止核实使用；它与二分准入明确分开。循环从未计入 `output_limit_attempts`，缺口容忍条件未放宽。

## 历史树兼容

用修复前的 owner `0e98180`（其循环分割来自 `fe68015`）通过真实编码 MP3、本机 HTTP、公开识别 API 生成两种历史 v4 状态：一是循环原段曾拆成已成功 300 秒和失败 300 秒后安全停止，二是旧 owner 已保存二分计划但尚未发子段请求时在 OS 保存边界中断。测试未手造或手改 checkpoint；旧源码仅从 Git archive 提取到测试临时目录以产生历史输入，不部署平行实现。

新 owner 可读这两种原树。第一种仅对失败 300 秒补剩余两次尝试，随后处理未开始尾段；已成功 300 秒整个存储行原样复用，原两子段数量和深度保持。第二种普通 resume 沿既有两子段处理，不再创建 loop 孙段；公开查询不会把仅 loop 祖先当作 cap 候选。旧已成功结果、历史工件和 spent 次数不删除或归零；查询前后 checkpoint 字节不变。历史树保留已存在的范围与后续新建二分被禁止是两个独立条件。

## 验证

- 39 项现有 merged-audio/provider-model 契约通过（8.30 秒）。
- 更新的 `tools/verify_audio_binary_recovery.py` 整套真实编码音频/合成 HTTP 场景通过：连续 loop 3 次后原 600 秒仍只有一槽，1 次尾段成功；每次 loop 工件引用均可读取，后续 resume 零调用。loop 前两次失败、第三次成功可在同范围完成，仍没有子树。
- 上述两个历史树场景通过，原成功兄弟全字段复用，循环已耗尽任务不产生恢复 offer，也不阻断尾段。
- 原 21 次 cap 二层树、artifact 保存、未知预留、暂时错误、v2/v3 接入、部分兄弟复用、非整数尾部、不等长逻辑覆盖、待发布/接受缺口零推理恢复均继续通过。safe-stop 公开查询分别确认最新 loop/cap 预留，公开证据为 loop 3/cap 0 与 loop 0/cap 21。
- 无真实模型调用，无生产进程操作，无生产 checkpoint 编辑。生产消费者重载及真实请求验证由统筹另行记录。首次脚本运行曾因不可变 metadata 中空 tuple 与 list 比较而停止，已修正场景断言为按空性检查；产品未据此改变元数据类型。

聚合证据：[asr_token_only_recovery_2026-09-16.json](asr_token_only_recovery_2026-09-16.json)。

重跑入口：当前 owner 下执行 `PYTHONPATH=src python tools/verify_audio_binary_recovery.py --work-dir <新场景目录> --legacy-repetition-fixture <历史场景目录>`。历史输入应以旧 owner 源码执行同一工具的 `--create-legacy-repetition-fixture` 创建；不能在当前修复版本伪造或补写旧树。工具仅在显式测试目录创建合成媒体、输出和状态。
