# 图片服务故障窄恢复验收（2026-09-20）

生产统筹发现旧 PROVIDER_UNAVAILABLE / PROVIDER_TIMEOUT 全失败课次的普通恢复额度已耗尽。恢复批次范围与预约仍归统筹；OCRLLM 提供公开只读判断和只恢复服务错误的调用，避免统筹读取/修改私有 checkpoint，或用普通 resume 重跑永久校验错误。

- `inspect_image_service_recovery(output_path)` 返回 `service_recovery_available`、`service_recovery_slot_count`、`reason`。只数现有 failed 槽且 canonical code 为上述两种；cleanup 未确认、缺失、损坏、不兼容状态均不开放。
- `resume_images_to_markdown(..., service_recovery_only=True)` 在 output claim 内重新读取原 checkpoint，保留组与 fixed lane，仅执行所选槽。没有候选时零调用，不能降级为整课重跑。默认 False 保持旧行为。
- 暂停前新产生的 validation failure 在续跑时被排除。已有 settled 内容复用；不改变 ASR、原 provider 有界重试或错误判定；不新增状态版本、自动批次循环或第二本恢复账。
- inspection 是快照，不是 worker idle / dispatch reservation 证明；批次重入和预算仍由调用者负责。

## 实测

扩展现有 `tools/verify_cooperative_safe_stop.py`，真实编码 PNG / MP3、本机 HTTP 请求与公开 API；没有真实模型调用。生产 checkpoint 与服务未触碰。最终命令：

```
/home/model-lab/.venvs/ocrllm-local-integration/bin/python tools/verify_cooperative_safe_stop.py --work-dir /mnt/r/course-pipeline-state/scenarios/image-service-recovery-20260920-final
/home/model-lab/.venvs/ocrllm-local-integration/bin/python -m pytest tests/test_merged_image_recognition.py -q
```

scenario 全通过，包括混合 settled / 503 / validation / 504；首次窄恢复把503变成validation并暂停，续跑只调用剩余504一次；再次窄恢复零调用，普通resume仍能恢复剩余validation。固定lane、原内容与组保留，既有有限重试503→成功2次调用。SDK cleanup 故障通过真实SDK close边界注入，inspection拒绝且resume零调用；missing/corrupt/unsupported及unresolved-only均不开新请求。所有既有音频/图片安全停止场景也通过。16个 merged-image pytest通过；仅已有pytest cache权限警告。

最初scenario搭建误把 ProviderModel 当 dataclass 使用 replace，调用前 TypeError；已改为通过公开属性创建 ProviderModel 并重跑全部场景。测试无付费请求，无质量放宽。

原始机器判据位于上述工作目录 `result.json`；本记录只含合成内容验证，不发布课程内容。
