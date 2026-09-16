# Codex CLI Provider 冒烟记录（2026-09-15）

## 范围

新增内置 vision provider `ocrllm.providers.codex_cli`：`CodexCLISettings` → `codex exec` 只读子进程，图片批次识别。默认配置：model=`gpt-5.6-luna`，reasoning_effort=`low`，max_images_per_call=8，timeout=1800s。

模块职责：

| 文件 | 职责 |
|---|---|
| `provider_settings.py` | frozen 设置 + 字段校验 + 模型名解析（`vision_model.name` 覆盖 settings 默认） |
| `build_codex_exec_command.py` | 只读 argv 与 SORRY4OCRLLM 拒识协议 prompt（纯函数） |
| `stage_codex_images.py` | 图片复制为 ASCII staging 名并校验非空 |
| `codex_exec_output.py` | 拒识解析、附件丢失分类、失败诊断脱敏（纯函数） |
| `recognize_images.py` | 适配器：预检 + 重试矩阵 + 规范错误码映射 |

核心增量（无行为变更）：`Config.provider` union、`_normalize_provider` 透传分支、`validate_vision_provider_config` 分支、`resolve_vision_provider` 分支（`name="codex_cli"`, `built_in=True`）、包导出。

错误处理与 legacy `codex_vision.py` 等价：3 次常规尝试（线性 4s×attempt）；图片附件丢失类拒识独立 5 档长退避（15/45/90/180/300s，不占常规预算）；spawn OSError 资源压力重试；`TimeoutExpired` 立即 `PROVIDER_TIMEOUT`；终态映射 `PROVIDER_UNAVAILABLE` / `PROVIDER_REFUSED_RECOGNITION` / `PROVIDER_RESPONSE_INVALID`。无逐张回退：批次失败即整组失败，证据在 `provider_calls_attempted`（真实 spawn 计数）。

## 离线验证

- `tests/test_codex_cli_settings.py` + `tests/test_codex_cli_adapter.py`：49 通过。假 subprocess 覆盖：argv 构造（8×`-i`、effort、fast tier、staging 名）、退出码重试与终态、拒识两类、附件丢失 6 spawn 耗尽、空输出、超时单次、OSError 重试、尝试间取消、批次上限/命令缺失/图片缺失零调用预检、facade 端到端（provider/model metadata）。
- 邻近契约（`test_config` / `test_import_contract` / `test_lightweight_import` / `test_dashscope_provider_boundaries` / `test_dashscope_settings` / `test_get_capabilities`）：186 通过（本记录时点的工作树）。

## Live 冒烟

- 命令：`tools/run_codex_cli_image_smoke.py --image ×8`，输入为 `D:\univ\大二下\最优化方法(H)\homework3作业照片` IMG_3981–3988 的 1600px 缩放副本（IMG_3989–3992 保留未动）。
- 结果：`{"recognition":{"image_count":8,"markdown_chars":1967,"model":"gpt-5.6-luna","provider_call_count":1},"status":"passed"}`
- 判定：通过。单次 `codex exec` 完成 8 张批次识别，result identity（provider/model/call count/image count）与契约一致。

## 已知边界

- `codex debug models` 目录中 `gpt-5.6-luna` 的 `input_modalities` 为 `['text','image']`，**无音频输入**；目录 effort 集合无 `light`，最低档为 `low`（其描述即 lighter reasoning）。音频识别不能经 Codex CLI，音频 provider 需另行规划。
- CLI 模型/effort 支持不在适配器内预检：错误由 CLI 自身非零退出暴露，经重试矩阵后落 `PROVIDER_UNAVAILABLE`，诊断行进 `description`。
- 复跑条件：仅当 `providers/codex_cli/` 或 Codex CLI 调用契约变化时重跑本冒烟；不进常规测试集。
