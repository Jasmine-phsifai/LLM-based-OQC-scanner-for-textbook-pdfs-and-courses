# ASR 持续生成循环的有界恢复（2026-09-15）

状态：owner 实现及场景验证通过；真实 Model Lab 集成与生产观察由统筹继续验证。

维护者本轮明确以管线效率和学习者可用转写为目标，不对重试、分块、模型、惩罚、检测作人为限制。这取代把旧“两次重试/两层切分”视为不得调整的产品要求；本次先复用现有两层结构验证一项具体改善。

Model Lab 通过 422/generation_repetition 明确报告生成停止于持续循环。OCRLLM 在显式 AudioOutputLimitPolicy 下记录这类失败的 request/artifact 引用，直接二分该区间；不再对同字节同配置执行原来的两次重复尝试。已有 output_token_limit 的行为及瞬态错误重试不变。固定完整二层失败树由21次变为7次调用，达到深度后保留partial，普通resume不重发。该结构不宣称足以恢复每个困难区间。

仍保留同一v4 checkpoint，无新状态体系。字段 output_limit_evidence 为兼容保留旧名字，新记录携带 provider_code 以区分 cap 与循环；公共 inspection、安全停止最新预留确认、派生未完成区间和终止区间判断覆盖循环。循环失败从不累计 output_limit_attempts，不满足缺口接受条件；不得把生成前缀当作已完成转写。

工具 tools/materialize_asr_optimization_cases.py 使用现有 materialize_long_audio_interval 准备私有固定源片段，验证源哈希，既不调用模型也不写生产checkpoint。模型代码、解码参数、GPU和原始tokens由Model Lab维护；统筹负责安全GPU窗口、部署顺序和生产产出观察。

验证：tools/verify_audio_binary_recovery.py 使用真实编码MP3及合成HTTP，在新循环分支验证7次树＋1次正常尾段、四叶每叶仅一次、恢复零新增调用、循环不接受gap、工件引用保留；原21次cap树、未知预留、暂时错误、旧版本接入、不等长尾、成功兄弟复用及发布恢复仍通过。既有merged-audio 18项测试通过。场景不构成真实转写质量证据。
