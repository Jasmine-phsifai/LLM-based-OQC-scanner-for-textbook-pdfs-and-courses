# Google Gemini SDK 接入调研记录

更新时间：2026-06-13

## 官方入口

- Gemini API 文档：https://ai.google.dev/gemini-api/docs?hl=zh-cn
- Models API：https://ai.google.dev/api/models?hl=zh-cn
- 图片理解：https://ai.google.dev/gemini-api/docs/image-understanding?hl=zh-cn
- 音频理解：https://ai.google.dev/gemini-api/docs/audio?hl=zh-cn
- 视频理解：https://ai.google.dev/gemini-api/docs/video-understanding?hl=zh-cn
- Files API：https://ai.google.dev/gemini-api/docs/files?hl=zh-cn
- 速率限制：https://ai.google.dev/gemini-api/docs/rate-limits?hl=zh-cn
- API key：https://ai.google.dev/gemini-api/docs/api-key?hl=zh-cn

## SDK 调用方式

- Python SDK 使用 `from google import genai`，客户端为 `genai.Client(api_key=...)`。
- 文本和多模态统一走 `client.models.generate_content(model=..., contents=...)`。
- 模型列表走 `client.models.list()`，REST fallback 是 `GET https://generativelanguage.googleapis.com/v1beta/models`。
- 图片小请求可用 `google.genai.types.Part.from_bytes(data=..., mime_type=...)` 内嵌发送。
- 大音频、长视频、大图片应先 `client.files.upload(file=...)`，再把上传对象放入 `contents`。
- SDK 网络超时通过 `types.HttpOptions(timeout=毫秒)` 传给 `genai.Client`，不能只在外层函数保存一个 timeout 参数。

## 不显而易见的特性

- Google 官方 SDK 会自动读取环境变量，但如果同时存在 `GOOGLE_API_KEY` 和 `GEMINI_API_KEY`，`GOOGLE_API_KEY` 优先。OCRLLM UI 内显式传入用户填写的 key，避免被系统环境变量悄悄覆盖。
- Models API 返回的是 `models/{id}` 形式，实际调用 `generate_content` 时使用去掉 `models/` 后的 id 更符合官方 Python 示例。
- REST 字段是 `supportedGenerationMethods`，当前 `google-genai` SDK 类型字段是 `supported_actions`。两种字段都要兼容，并且需要包含 `generateContent` 才适合 OCRLLM 当前识别管线；只支持 `embedContent` 的模型必须过滤掉。
- Files API 文件会自动删除，官方文档写明单文件限制和项目存储限制。OCRLLM 当前只把它当临时上传通道，不把 Google 文件 URI 当长期缓存。
- `google-genai` Files API 对非 ASCII 本地路径不稳定。OCRLLM 上传长音频前会为中文文件名复制一个 ASCII 临时文件，上传完成后清理，避免课程名中文导致 `ascii codec` 错误。
- Google 速率限制按项目计算，不是按 API key 计算。后续做 Google API 池时，不能照搬 DashScope 多 key 提升并发的假设。
- 实验、预览、快照模型通常更容易有严格限流。OCRLLM 将它们放在图片识别优先队列前段，是为了优先消耗免费/不稳定模型；但限流错误仍按同模型重试处理，不直接误判为额度耗尽。
- `RESOURCE_EXHAUSTED` 既可能是 quota，也可能是 rate limit，不能单独决定分类。普通 HTTP 429
  默认按限流重试；rate limit/RPM/TPM/RPD 等字样也优先保持限流语义。只有已有回归证据的 Google 标准文案
  `You exceeded your current quota ... check your plan and billing details` 在没有限流标记时判为 quota，
  直接切换下一个候选。文案里的 `billing details` 是排查建议，不等于支付失败；真实 payment/billing
  错误仍单独分类。`FreeTierOnly` / `FreeAllocationQuotaExceeded` 是 DashScope 标记，不属于 Google contract。
- 分钟级 `RATE_LIMIT` 不能按普通网络错误快速重试。OCRLLM 会优先读取 Google `RetryInfo.retryDelay`；没有服务端建议时，rate limit 第一次重试至少等待 65 秒，避免一分钟窗口未刷新就失败。
- `503 UNAVAILABLE` 且提示 high demand / try again later 通常是临时服务负载，也按可重试限流处理，不能写入板书失败占位。
- `httpx.RemoteProtocolError: Server disconnected without sending a response` 属于长音频/大文件请求常见网络断连，应按网络错误重试同一模型，而不是当作未知错误直接失败。
- 有些异常会以 JSON 文本形式出现在返回内容里。OCRLLM 会把形如 `{"error": ...}` 的模型文本视为假成功，并重新进入错误分类。
- 真实 160 分钟级课程中，Google 长音频可能返回“热词表/术语表”或明显过短片段，但 SDK 仍给正常文本响应。OCRLLM 必须在正文层校验，不能只看非空。
- 极弱源音轨会诱发更隐蔽的假成功：模型可能回显提示词、输出“你，你……”一类重复噪声、空响应或“听不清”，也可能根据板书热词编造转写。马原 2026-06-09 这类全段 RMS 约 -70 dB 的音轨，即使抽取较响窗口并增益后，Gemini 仍无法稳定听到课堂语音。
- `flash-lite` 对超长课程转写更容易出现短片段/非转写输出。音频优先链中非 lite 的 Flash/Pro 应排在 lite 前面；lite 仍可作为后置免费候选。
- 纯文本任务不要复用 image/preview 视觉候选链。部分 image 模型在文本请求里会 404 或高限流，热词提取应优先走 text/audio-capable Gemini 候选。
- 长音频转写不是单独 ASR API，而是 Gemini 多模态模型加 Files API 和提示词。当前 Google 模式不做短音频盲切回退。

## OCRLLM 当前策略

- Google 模式独立于 DashScope 千问模式和 OpenAI-compatible 视觉 Provider。
- 启用 Google 模式时，后台识别主路由走 Google provider，千问主链路不参与。
- UI 勾选 Google 模式且已填写 Google key 时，会立即执行 google.com 连通性和实时模型拉取；未填写 key 时不弹额外网络错误，保存时再强校验。
- CLI 可用 `OCRLLM_GOOGLE_PARALLEL_REQUESTS`、`OCRLLM_GOOGLE_REQUEST_STAGGER_SECONDS`、`OCRLLM_GOOGLE_VISION_BATCH_SIZE`、`OCRLLM_GOOGLE_VIDEO_FRAME_BATCH_SIZE` 控制 Google 模式的并发、错峰和批大小，真实长课任务建议先低并发运行。
- OpenAI-compatible 视觉 Provider 的配置不清空，用户关闭 Google 模式后仍可继续使用。
- 图片/视频帧模型优先链来自实时模型列表，排序为 image/preview/snapshot/experimental 优先；这些候选不可用后再尝试 Gemini 2+ Pro/Flash 长音频候选；泛用但非音频优先的老模型排在更后。
- 长音频模型优先链来自实时模型列表，仅保留 Gemini 2+ Pro/Flash 这类多模态长上下文候选；排序为非 lite Flash、非 lite Pro、lite。
- 视频管线的 Phase 4 板书帧和 Phase 5 音频识别都复用 Google provider，因此 Google 模式不会在音频阶段回到 DashScope。
- 同一个 provider 生命周期内会记住已经因 quota/404/欠费等切走的模型，并优先复用上一次成功模型，避免长课多批次每次都重新消耗不可用 image/preview 模型。
- 网络错误、限流、并发限制先重试同模型；quota/欠费/404 模型不可用切换下一个候选。
- Google 长音频上传前会用 `ffmpeg volumedetect` 做极弱音轨预检。30 分钟以上音频如果整体响度低到疑似没有可识别课堂语音，会在上传前失败，避免消耗 Gemini 并写出假 MD。
- Google 长音频写入前会校验正文：热词表/术语表正文、prompt echo、重复噪声、错误 JSON、空白文本、长音频异常过短文本都视为假成功。验证失败时在 Google 音频候选内部切换模型；所有候选失败才显式报错。
- Phase 5 断点续传会重新校验已有音频 MD。旧文件如果是热词表正文或长度异常，不再被当作已完成阶段。
