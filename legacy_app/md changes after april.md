# OCRLLM Changes After April

## 会话背景

- 日期: 2026-04-23
- 目标 1: 删除 OCRLLM 录课识别中板书识别结束后的“合并”过程，避免合并逻辑把最终板书 md 合并空。
- 目标 2: 将本次改动详细记录，方便后续把 OCRLLM 作为其他项目的子服务接入。
- 目标 3: 评估 OCRLLM 作为多模态 AI 应用接入更多厂商模型的可行性，并给出后续独立化改造方向。
- 明确未做: 本次没有修改 STA 项目，也没有修改 STA 对 OCRLLM 的调用方式。

---

## 本次实际代码改动

### 1. 删除录课 Phase 4 后的板书“合并”执行

修改文件: processors/video.py

原行为:
- Phase 4 板书识别完成后，会额外读取原始板书 md。
- 调用 core/board_merge.py 中的 merge_board_md() 生成 _板书识别_合并.md。
- 后续收尾逻辑优先把这个“合并版 md”当成最终板书结果保留。

问题:
- 这条链路把“合并结果”提升成了录课板书的最终真值。
- 一旦合并误删内容，即使原始板书 md 是正常的，最终用户拿到的也可能是被清空或严重压缩后的版本。
- 这不是显示层问题，而是产物选择逻辑本身有问题。

现在的行为:
- Phase 4 识别完成后，不再执行任何板书 merge。
- 录课板书的最终保留产物改回原始板书 md，也就是 {stem}_板书识别.md。
- 若历史运行留下过 _板书识别_合并.md，最终清理阶段会将其视为旧中间产物处理，而不会再把它当成最终结果。

具体改动:
- 删除 _phase4_llm() 中的 merge_board_md 调用与 _板书识别_合并.md 写出逻辑。
- 删除对 phase4_merge 的阶段启动和结束调用。
- 调整 _build_phase_weights()，把原先 3.7 + 0.3 的分配收敛为 phase4 = 4.0，避免进度统计残留一个不再执行的阶段。
- 调整 _prune_completed_outputs()：
  - 不再优先保留 _板书识别_合并.md。
  - 只要原始板书 md 存在且非空，就直接把它作为最终产物。
  - 如果原始板书 md 不存在或为空，则跳过最终清理，避免误删现场。
  - 清理列表中保留对旧版 _板书识别_合并.md 的删除，作为兼容性善后。

### 2. 删除已废弃的进度文案映射

修改文件: core/progress_tracker.py

原行为:
- 进度友好文案仍保留 phase4_merge -> 智能合并去重。

现在的行为:
- 该映射已移除，避免后续界面或日志继续出现已废弃阶段名。

---

## 这次改动为什么是根因修复

本次不是简单“合并失败时回退”，而是直接取消录课板书后处理里的 merge 设计，原因如下:

1. 问题不是偶发写文件失败，而是产品逻辑把一个启发式去重结果升级成最终产物。
2. 录课板书识别的首要目标是保内容，不是追求所谓“智能整理”。
3. 对录课板书这种高噪声、高不确定性的多帧识别结果，后处理 merge 一旦误判，就会造成不可逆的信息丢失。
4. 与其在 merge 上继续调阈值，不如先把最终真值恢复成原始识别结果，保证内容安全。

结论:
- 这次修改是“移除危险后处理”，不是“修补 merge 参数”。
- 如果未来还要做板书压缩/整理，应该作为显式可选步骤存在，而不是默认覆盖最终结果。

---

## 影响面评估

### 直接影响

- 录课 Phase 4 不再生成新的 _板书识别_合并.md。
- OCRLLM 内部长视频板书最终结果将回到原始板书 md。
- 进度显示中不会再出现“智能合并去重”阶段。

### 保持不变

- 抽帧、预处理、并行识图、热词提取、音频识别逻辑均未改。
- Checkpoint/恢复链路未改。
- Social long video 的 _识别.md 规范命名逻辑未改。
- STA 集成侧未改。

### 向后兼容处理

- processors/social/long_video.py 仍保留对历史 _板书识别_合并.md 的清理逻辑，因此旧产物不会阻塞新行为。
- processors/video.py 仍保留 _phase4_merged_board_path() 路径函数，仅用于兼容清理旧文件，不再承担新产物生成职责。

---

## 本次验证

已做的验证:
- 对 processors/video.py 做静态错误检查: 无错误。
- 对 core/progress_tracker.py 做静态错误检查: 无错误。

本次未做:
- 没有跑完整视频端到端识别，因为当前任务重点是精确删除危险后处理逻辑，并且没有指定现成的最小回归样例视频。

建议的后续人工回归:
- 用一段此前发生“板书 md 被合并空”的录课视频重新跑 Phase 4。
- 确认最终输出保留的是 {stem}_板书识别.md，且内容不再被后处理删空。

---

## OCRLLM 接入更多厂家模型的可行性分析

## 总结结论

可行，但不能只靠把 model name 改成别家名字。

更准确的判断是:
- 视觉识图和文本处理: 高可行。
- 短音频 ASR: 中等可行。
- 长音频异步 ASR: 中低可行，当前是最强 DashScope 绑定点。
- GUI/API/配置层: 需要同步去 Qwen 单厂商化，改动量不大但必须做。

OCRLLM 当前已经具备“处理流水线”和“多模态任务编排”能力，真正强耦合的是“模型调用层”和“厂商特有能力层”，不是业务流程本身。

---

## 当前已经相对通用、可复用的部分

这些部分基本不依赖具体模型厂商，可以保留:

### 1. 处理器和流水线框架

相关文件:
- processors/base.py
- processors/video.py
- processors/video_pipeline.py
- processors/pdf.py
- processors/board.py
- processors/social/short_video.py

这些代码主要负责:
- 输入路由
- 抽帧
- 预处理
- 并发调度
- 结果落盘
- 断点恢复
- 最终清理

它们依赖“能拿到文本结果”的能力，但不强依赖某一家 API 语义。

### 2. 图像与媒体预处理层

相关目录:
- imaging/
- core/utils.py

这些能力包括:
- PDF 渲染
- 板书完整图片的等比例缩放与格式转换（不定位、不裁剪、不做透视矫正）
- 视频抽帧
- 图像降噪
- 音频抽取
- ffmpeg/ffprobe 调用

这些都是模型无关能力，后续接任何厂商都仍然需要。

### 3. 结果格式与中间文档约定

相关文件:
- prompts.py
- core/document_model.py
- core/incremental_writer.py

HTML 注释元数据格式本身是中立的，可继续作为 OCRLLM 的统一输出契约。

---

## 当前最强的厂商耦合点

### 1. 配置层默认就是 DashScope/Qwen 单厂商配置

相关文件: config.py

当前耦合点:
- API Key 环境变量默认读取 DASHSCOPE_API_KEY。
- Base URL 默认是 DashScope compatible-mode 地址。
- 模型默认值全部是 Qwen 命名。
- VISION_MODEL_OPTIONS 直接写死为 Qwen 模型列表。

这意味着:
- 后端默认配置有厂商假设。
- GUI 的候选模型列表也有厂商假设。
- 新厂商接入不能只加 model name，还要改配置结构。

### 2. GUI 文案和模型选择器直接绑定 Qwen

相关文件: gui/app.py

当前耦合点:
- 标题直接写 Qwen-powered Course Recognition。
- 模型下拉框直接使用 VISION_MODEL_OPTIONS。
- 当前 UI 只有一个“视觉模型”入口，缺少“视觉/文本/短音频/长音频 provider 分离配置”。

这意味着:
- 一旦要支持多家厂商，UI 不够表达真实配置。
- 用户会误以为只需切一个 vision model，实际上 ASR 和文本链路仍可能走另一家。

### 3. LLMClient 只抽象到了“OpenAI 兼容多模态”这一层

相关文件: core/llm_client.py

优点:
- 视觉与文本请求已经走 OpenAI 兼容 SDK。
- image_url 多图输入、text prompt、stream fallback、重试与取消，这些机制是可以复用的。

限制:
- extra_body 里直接塞 enable_thinking 和 asr_options，这不是所有厂商都兼容。
- transcribe_short_audio() 假设厂商支持 chat.completions + input_audio 这种输入格式。
- 当前类名和职责还是“一个客户端包办 vision/text/short-asr”，不利于能力分治。

结论:
- 它适合作为“OpenAI-compatible provider adapter”的内部实现。
- 但不适合作为全系统唯一模型抽象。

### 4. APIPool 绑定的是 LLMClient，而不是抽象 provider client

相关文件: core/api_pool.py

当前耦合点:
- APIPool 内部直接创建 LLMClient。
- slot/client 的类型就是 LLMClient。

这意味着:
- 多 key 并发目前只适合 OpenAI-compatible chat 能力。
- 如果以后视觉走 OpenAI 兼容接口、长音频走厂商原生任务接口，就没法复用同一套池化模型。

### 5. AudioProcessor 对 DashScope 原生长音频接口是硬编码

相关文件: processors/audio.py

这是最难替换的部分，原因有五个:

1. 固定提交地址
- SUBMIT_URL
- TASK_URL_TEMPLATE
- FILES_URL

2. 固定认证与异步协议
- X-DashScope-Async 头
- 上传文件后拿 file_id，再换 file_url，再提交 task_id，再轮询任务

3. 固定信任域名白名单
- _TRUSTED_ASR_HOSTS

4. 固定结果解析逻辑
- _extract_transcripts() 深度适配的是 DashScope 返回结构和结果文件结构

5. 固定格式转换与成本日志假设
- _DASHSCOPE_NATIVE_FORMATS
- 日志中的价格说明也直接按 DashScope 标准写死

结论:
- 视觉/文本部分现在大致是“半抽象化”。
- 长音频 ASR 部分目前仍是“厂商原生 SDK/REST 适配代码”。
- 如果要支持更多厂家，必须把 AudioProcessor 里的供应商协议剥离出去。

---

## 面向“深度绑定 qwen dashscope，同时尽量支持更多厂商”的推荐架构

这里不建议搞一个过度统一、能力最低公分母式的大接口。那样最后会把 DashScope 的优势也抽没。

更合适的方式是:
- 保留 DashScope/Qwen 作为一等公民 provider。
- 同时把通用任务接口抽出来。
- 用 capability 标记承载各家差异。

## 推荐拆分为四层

### 第 1 层: Provider 配置层

建议新增抽象:
- ProviderConfig
- VisionProviderConfig
- TextProviderConfig
- ShortASRProviderConfig
- LongASRProviderConfig

建议字段:
- provider: dashscope | openai | azure_openai | volcengine | anthropic | google | custom
- api_key
- base_url
- model
- concurrency_limit
- timeout
- extra_headers
- extra_body
- capabilities

关键点:
- 不要再只保留一个 cfg.api 和一个 cfg.models。
- 视觉、文本、短 ASR、长 ASR 要允许分别选 provider。
- 这是后面多厂商编排的前提。

### 第 2 层: 能力接口层

建议新增接口，不直接复用当前 LLMClient 名称:
- VisionModelGateway
- TextModelGateway
- ShortASRGateway
- LongASRGateway

建议最小接口示例:
- recognize_images(prompt, image_paths) -> str
- chat_text(prompt, system_prompt=None, history=None) -> str
- transcribe_short(audio_path, system_prompt=None) -> str
- submit_long_asr(audio_path_or_url, hotwords=None) -> task_handle
- poll_long_asr(task_handle) -> result
- format_long_asr_result(result, title) -> md

关键点:
- 长音频不要强行塞回 chat.completions 风格。
- 它就是另一类能力，应该单独抽象。

### 第 3 层: Provider Adapter 层

建议新增目录:
- providers/
  - base.py
  - dashscope_openai_compatible.py
  - dashscope_native_asr.py
  - openai_compatible.py
  - volcengine_asr.py
  - whisper_local.py
  - gemini_adapter.py

其中:
- DashScope 需要至少拆成两个 adapter:
  - 一个处理 OpenAI-compatible 的 vision/text/short-asr 能力
  - 一个处理 DashScope 原生 long-asr filetrans 能力

这样做的好处:
- 你们后续想“深度捆绑 qwen dashscope 的逻辑进行独立化处理”，就把 DashScope 适配器做深，而不是让全系统继续散落 DashScope 细节。
- 其他厂商只要补 adapter，不用污染处理器主流程。

### 第 4 层: 任务编排层

保留当前 processors/ 与 imaging/ 为主，只改它们依赖的对象。

也就是说:
- VideoProcessor 不关心底层是 Qwen、Gemini、Claude 还是别的。
- 它只知道自己拿到了 vision gateway、text gateway、asr gateway。

---

## 建议的最小改造路线

## 第一阶段: 先让视觉/文本可切换厂商

优先级最高，改动收益比最好。

建议动作:
1. 从 config.py 拆出 provider-aware 配置。
2. 把 core/llm_client.py 收缩成 OpenAICompatibleClientAdapter。
3. 新增 provider factory，根据配置返回 vision/text gateway。
4. BaseProcessor 构造时注入的不再是 LLMClient，而是 capability 对象或 provider bundle。
5. GUI 把单一 vision_model 改成:
   - 视觉 provider + model
   - 文本 provider + model

完成后收益:
- PDF/板书/录课 Phase 4/短视频画面识别基本都能切换厂商。
- 这是最容易先独立化的一步。

## 第二阶段: 把短音频 ASR 从 LLMClient 中拆出去

建议动作:
1. 把 transcribe_short_audio() 从 core/llm_client.py 移到独立 ShortASRGateway。
2. 当前 DashScope 兼容 chat+input_audio 的逻辑作为 DashScopeShortASRAdapter。
3. 允许接:
   - OpenAI Whisper 类接口
   - 火山/腾讯/讯飞等一句话/短音频接口
   - 本地 whisper/faster-whisper

完成后收益:
- 音频处理器不再默认等于“Qwen ASR”。
- 更适合做厂商切换和容灾。

## 第三阶段: 单独重构长音频 ASR

这是最难但必须单独做的阶段。

建议动作:
1. 从 processors/audio.py 中抽出 LongASRJobClient。
2. 把以下逻辑整体迁移到 provider adapter:
   - 上传文件
   - 提交任务
   - 轮询状态
   - 下载结果
   - 结果解析
3. AudioProcessor 只保留:
   - 音频切分/转码
   - 热词整理
   - Markdown 组装的统一入口
4. 每家厂商单独实现自己的 long-asr adapter。

完成后收益:
- DashScope 原生 filetrans 逻辑被隔离，后续换厂商不会再改业务主流程。

## 第四阶段: 改 GUI 与 API 契约

建议动作:
1. gui/app.py 增加 provider 级配置而不是只有 base_url/model。
2. api/server.py 请求体增加 provider 相关 options。
3. STA 桥接层后续再单独适配新的 provider 配置结构。

注意:
- 按你的要求，本次不改 STA。
- 但如果 OCRLLM 后续成为子服务，STA 最终一定要适配新的 provider 配置入参，否则无法真正利用多厂商能力。

---

## 我建议优先支持的厂商接入形态

不是所有厂商都要同一种接法，应该按能力分类:

### A. OpenAI-compatible 多模态厂商

适合先接入:
- DashScope compatible-mode
- OpenAI 部分模型
- 部分 Azure OpenAI 部署
- 一些国内兼容 OpenAI chat completions 的平台

适合承接:
- PDF 识图
- 板书识图
- 短视频画面识别
- 热词提取
- 部分短音频识别

这是最容易接的第一类。

### B. 原生 ASR 型厂商

适合第二批接入:
- 火山引擎 ASR
- 腾讯云 ASR
- 讯飞 ASR
- 阿里云 DashScope 原生长音频

这类要单独 adapter，不建议硬塞进 chat 接口抽象。

### C. 本地模型/私有化模型

适合作为兜底或离线模式:
- faster-whisper
- 本地 OCR/VLM 组合
- 自部署 OpenAI-compatible 服务

这类接入后，OCRLLM 的私有化部署价值会大很多。

---

## 对“深度绑定 qwen dashscope 的逻辑进行独立化处理”的具体建议

这件事我建议这样做，而不是继续把 DashScope 细节铺在 processors/ 里:

### 建议方案

1. 新建 providers/dashscope/ 子目录
- chat_compatible.py
- short_asr.py
- long_asr.py
- config.py
- capabilities.py

2. 把当前散落在以下位置的 DashScope 逻辑逐步迁过去
- config.py 的默认值与环境变量读取
- core/llm_client.py 的 compatible chat 与 short audio 调用
- processors/audio.py 的 file upload / task submit / poll / parse

3. 主业务层只依赖 provider factory
- create_vision_gateway(cfg)
- create_text_gateway(cfg)
- create_short_asr_gateway(cfg)
- create_long_asr_gateway(cfg)

4. capability 要显式暴露
例如:
- supports_multi_image
- supports_context_history
- supports_input_audio_in_chat
- supports_async_file_transcription
- supports_hotwords
- supports_word_timestamps

这样可以做到:
- DashScope 继续走最优路径
- 其他厂商按能力降级接入
- 不会为了兼容性牺牲 Qwen 的现有能力

---

## 如果近期只做一轮重构，我建议的优先顺序

1. 先抽 vision/text provider factory。
2. 再拆 short ASR。
3. 最后再动 long ASR。

原因:
- 视觉/文本覆盖 OCRLLM 大部分主要价值。
- 长音频 ASR 是最难拆、最容易拖慢项目的一块。
- 如果第一轮就试图把所有能力统一抽象，项目会进入高成本重构期，收益不成比例。

---

## 对后续开发的直接建议

### 现在就值得做的

- 把 config.py 从“单厂商默认配置”改成“按能力分 provider 配置”。
- 把 core/llm_client.py 重命名并收缩为 OpenAI-compatible adapter。
- 新建 providers/ 目录，不要再把厂商协议写回 processors/。
- 在 GUI 中拆开视觉模型与文本模型，不要只有一个视觉模型下拉框。

### 暂时不要做的

- 不要先做一个包打天下的 MegaClient。
- 不要试图让长音频 ASR 也统一成 chat.completions 风格。
- 不要一开始就抽象到“所有厂商特性都必须完全一样”。

---

## 本次会话最终结论

1. 录课板书“合并”流程已经从 OCRLLM 主处理链中移除，根因是它会把启发式后处理结果当成最终真值，导致板书 md 被合并空。
2. 本次未修改 STA 项目，也未修改其调用链。
3. OCRLLM 接入更多厂家模型是可行的，但必须把当前的 DashScope/Qwen 耦合从配置层、GUI 层、OpenAI-compatible 客户端层、尤其是长音频 ASR 原生协议层中拆出来。
4. 最合理的演进路径不是“去 Qwen 化”，而是“把 Qwen/DashScope 逻辑独立成 provider adapter，并让其他厂商按能力接入”。
