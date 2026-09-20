# 2026-09-20 全失败识别的安全退出契约

生产统筹将ALL_CANDIDATES_EXHAUSTED一概视作owner未安全退出，导致已保存且已关闭请求的普通失败进入停止阻塞清单。图片/音频finalizer现仅在执行器已返回（lane已join且结果已checkpoint）时，在该异常details提供safe_owner_exit布尔值；provider_cleanup_failed为true时明确false。错误码、失败槽、预算、输出和checkpoint不改变。该标志不代表识别成功，不允许将其他错误或缺少标志的旧异常推断为安全。

扩展既有tools/verify_cooperative_safe_stop.py，使用真实编码图片/MP3、本机HTTP全拒绝响应、OpenAI SDK close边界失败注入，覆盖图片/音频并行lane全失败保存、异常不变、无成功MD、cleanup失败不给确认。完整既有安全停止/重试/不等长切片/OS写盘失败场景也通过，无生产模型调用。既有merged image/audio公开合同34项通过（仅pytest cache权限警告）。

运行：`python tools/verify_cooperative_safe_stop.py --work-dir <独立持久验证目录>`。本轮聚合结果见[safe_owner_exit_2026-09-20.json](safe_owner_exit_2026-09-20.json)。统筹只消费该明确契约，不根据错误码自行认定保存完成、不解析checkpoint内部字段。生产部署及跨仓版本由course-pipeline记录。
