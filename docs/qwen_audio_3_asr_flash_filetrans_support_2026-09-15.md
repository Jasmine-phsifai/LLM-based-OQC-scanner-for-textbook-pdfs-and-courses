# qwen-audio-3.0-asr-flash-filetrans 支持与校验链路修复（2026-09-15）

## 背景

阿里云百炼上线 `qwen-audio-3.0-asr-flash-filetrans`（qwen3-asr-flash-filetrans 的新命名，
控制台详情页 slug 即模型 ID；同族短音频 `qwen-audio-3.0-asr-flash` 已出现在 /models 列表）。
legacy app 出现三个症状：扫描不到、手动添加时本地 MP3 测试报 4xx、模型无法保存进下拉清单。

## 根因

1. **扫描不到是机制性盲区**：OpenAI 兼容 `/models` 端点从不列出 filetrans 异步任务模型。
   2026-09-15 实拉 251 个模型 ID，其中没有任何 filetrans / paraformer / sensevoice。
   此类模型只能内置登记或手动添加。
2. **手动添加本地 MP3 → 404/400**：`gui/model_validator.py::_validate_audio` 把本地文件
   一律路由到 `probe_audio_short_model`（chat.completions + input_audio）。filetrans 模型
   不走兼容模式，实测返回 404 `model_not_supported`
   ("Unsupported model ... for OpenAI compatibility mode")。
3. **探测载荷与生产不一致**：`probe_audio_filetrans_model` 固定使用 paraformer 风格的
   `input.file_urls` 且不带 `X-DashScope-OssResourceResolve`，而生产路径
   （`processors/audio.py::_submit_task`）对 qwen filetrans 家族使用 `input.file_url`
   并在 oss:// 时加 resolver 头。

## 改动（3 个文件）

- `OCRLLM/core/model_catalog.py`
  - `BUILTIN_AUDIO_MODELS` 新增 `qwen-audio-3.0-asr-flash-filetrans`（asr_long，≤12h）。
    builtin 条目在模型选择器中直接可见，免校验。
  - 新增公开判定 `is_asr_long_family(name)`，与 `_classify_bailian_audio_model` 共用同一规则。
  - 修正模块 docstring 中"DashScope 原生 filetrans 枚举"的不实描述。
- `OCRLLM/core/llm_client.py`
  - `probe_audio_filetrans_model` 按 `_uses_single_file_url(model)` 选择
    `file_url` / `file_urls`；audio_url 为 oss:// 时补 `X-DashScope-OssResourceResolve: enable`。
- `OCRLLM/gui/model_validator.py`
  - `_validate_audio` 对 filetrans 家族（`is_asr_long_family`）强制走异步 filetrans 探测；
    本地文件先经新增 `_upload_filetrans_probe_audio` 上传 DashScope OSS（与生产同一 OssUtils 路径），
    不再落入 chat.completions 探测。

## 实测记录（真实 API，2026-09-15）

| 验证项 | 方法 | 结果 |
|---|---|---|
| 模型 ID 真实可用 | 公共样音 welcome.mp3，`file_url` 提交 | HTTP 200，任务 SUCCEEDED，返回 transcription_url |
| `file_urls` 复数形状 | 同上模型提交 | HTTP 200 受理（新模型两种形状都接受，但文档形状为单数，已对齐） |
| chat.completions 路由 | 同一模型走兼容模式 | HTTP 404 model_not_supported —— 坐实根因 2 |
| OSS 上传 + 生产提交头 | 本地 MP3 → OssUtils.upload → oss:// + resolver 头 | HTTP 200 受理执行（无语音样音返回 ASR_RESPONSE_HAVE_NO_WORDS，属内容性失败，链路正常） |
| 修复后校验流端到端 | 调用 app 自身 `_upload_filetrans_probe_audio` + `probe_audio_filetrans_model` | (True, "异步任务成功")，模型可保存 |
| 单测 | `pytest tests/test_bailian_model_discovery.py tests/test_audio_wait_result.py tests/test_gui_app.py` | 31 passed |

复跑脚本：`python legacy_app/tests/live_probe_qwen_audio_3_filetrans.py`
（从 QSettings 读 API key，对两种载荷形状各提交一次并轮询结果。）

## 边界说明

- 未来再出新的 filetrans 型号，扫描依然发现不了（端点不列），但手动添加路径已修复可用。
- 无语音/纯静音音频在新旧模型上都会以任务级失败（ASR_RESPONSE_HAVE_NO_WORDS）告终，
  与本次改动无关，是既有行为。
