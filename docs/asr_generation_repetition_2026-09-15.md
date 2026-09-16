# ASR 持续生成循环的有界恢复（2026-09-15）

2026-09-16 更新：本文保留为当时实现与实测记录。当前用户要求已收回循环错误二分；最新行为、历史树兼容与验证见[ASR token-only 恢复](asr_token_only_recovery_2026-09-16.md)。

状态：owner 实现及场景验证通过；2026-09-15 07:36:31 UTC 已在生产消费者启用，真实 Model Lab 集成与自然生产恢复已核验。

维护者本轮明确以管线效率和学习者可用转写为目标，不对重试、分块、模型、惩罚、检测作人为限制。这取代把旧“两次重试/两层切分”视为不得调整的产品要求；本次先复用现有两层结构验证一项具体改善。

Model Lab 通过 422/generation_repetition 明确报告生成停止于持续循环。OCRLLM 在显式 AudioOutputLimitPolicy 下记录这类失败的 request/artifact 引用，直接二分该区间；不再对同字节同配置执行原来的两次重复尝试。已有 output_token_limit 的行为及瞬态错误重试不变。固定完整二层失败树由21次变为7次调用，达到深度后保留partial，普通resume不重发。该结构不宣称足以恢复每个困难区间。

仍保留同一v4 checkpoint，无新状态体系。字段 output_limit_evidence 为兼容保留旧名字，新记录携带 provider_code 以区分 cap 与循环；公共 inspection、安全停止最新预留确认、派生未完成区间和终止区间判断覆盖循环。循环失败从不累计 output_limit_attempts，不满足缺口接受条件；不得把生成前缀当作已完成转写。

工具 tools/materialize_asr_optimization_cases.py 使用现有 materialize_long_audio_interval 准备私有固定源片段，验证源哈希，既不调用模型也不写生产checkpoint。模型代码、解码参数、GPU和原始tokens由Model Lab维护；统筹负责安全GPU窗口、部署顺序和生产产出观察。

验证：tools/verify_audio_binary_recovery.py 使用真实编码MP3及合成HTTP，在新循环分支验证7次树＋1次正常尾段、四叶每叶仅一次、恢复零新增调用、循环不接受gap、工件引用保留；原21次cap树、未知预留、暂时错误、旧版本接入、不等长尾、成功兄弟复用及发布恢复仍通过。既有merged-audio 18项测试通过。场景不构成真实转写质量证据。

生产证据：消费者 runtime fe68015 与 Model Lab runtime 9135366/configuration c1fb4047605571cb44012b4fff14c3fbe65301bd14252b0098eba978fcc466c4 已按 request_id 对齐。专业外语源3900–4200秒的300秒区间返回 generation_repetition，直接二分3900–4050及4050–4200，两段成功；三次客户端请求合计约29.67秒，没有同字节原段重试。已到二层深度的3600–3750秒循环段保留失败，后续正常工作继续。公共 inspect_audio_completion 确认 durable checkpoint，并保持 partial / accepted_with_gaps=false。

Model Lab 的独立对照显示循环检测保持四个正常转写逐字一致；惩罚1.05会令一个正常对照退化，未上线。60秒短分块虽10/12子片段完成、MOSS四段返回结果，尚无人工真值支持质量放行。本次只改变明确循环的时间成本和相同输入重试；全局更短分块、替代模型路由和旧耗尽预算的迁移均未启用。统筹仓库 docs/asr-optimization-20260915/ 保存用户可读报告、场景结果、真实HTTP与生产观察证据。
