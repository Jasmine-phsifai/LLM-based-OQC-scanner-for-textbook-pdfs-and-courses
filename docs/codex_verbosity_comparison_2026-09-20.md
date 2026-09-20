# Codex low/high verbosity 有界单因素对照（2026-09-20）

本轮不修改产品源码/提示词/模型/推理强度/生产8图规划，不部署。
仅在真正CLI子进程argv加入 `-c model_verbosity="low"` 或 `"high"`。
使用原始HEAD course_ocr wrapper、gpt-5.6-luna、reasoning low、default tier、
实际生产二进制，串行1；既有有限内部重试不改。所有模型调用输出和usage独立，
不使用生产job/checkpoint，也不消费其恢复额度。

先扩展现有loopback工具 `--model-verbosity low|high`：三组每档各1请求，
实际自定义无鉴权Responses请求分别包含 `text.verbosity=low` / `high`，
图片/顺序/无auth/CLI退出门禁全部通过，云模型调用0。
这证明本机CLI自定义provider的配置序列化，不是生产认证请求的云端抓包；
不能据此声称云模型保证遵守某种verbosity输出质量。

真实对照最多4次公开API：frame75单图low/high，原72..79八图low/high。
同组图片字节SHA及完整prompt SHA应一致，唯CLI verbosity配置不同。
每个group/verbosity保存output、observations、owner-events、result；
失败和内部重试的全部token/wall也在同一账内，cache为input子集，不重复相加。

## 单图已核验事实

两档均正确读出“2.4 同步与脉冲系统的若干定义”，但均有大量遗漏。
根对照原图确认“Kuramoto”确实可见，不能将high输出此词当虚构。
high将清晰“定义2.10（强连通）”写作“连通性”；low有向图/无向图特殊情形
关系表述可疑。这些内容证据不支持“high字数更多所以更准确”。

八图还须逐帧核对74高亮引理、75/76章节标题、77桌面、78正在关机、79无信号，
且右侧白板一直存在。帧marker齐全不保证正文归属正确。

## 持久证据

- `/mnt/r/course-pipeline-state/scenarios/codex-verbosity-low-wire-20260920`
- `/mnt/r/course-pipeline-state/scenarios/codex-verbosity-high-wire-20260920`
- `/mnt/r/course-pipeline-state/scenarios/codex-verbosity-ab-20260920`

真实实验runner只放持久场景目录，不引入产品开关；最大4API完成即停止。
四次API已完成即停止；全部程序validator complete，实际5次CLI（八图low先拒识后原有内部retry成功）。
两对实验输入SHA与完整prompt SHA完全一致，产品src未变。

|输入|verbosity|CLI次数（失败）|API wall秒|input / output tokens|
|---|---|---:|---:|---:|
|单图75|low|1（0）|15.347|12580 / 590|
|单图75|high|1（0）|15.844|12577 / 623|
|八图72..79|low|2（1）|34.629|60074 / 1015|
|八图72..79|high|1（0）|29.117|30027 / 1293|

总input115258/output3521，缓存input26880是input子集。串行API wall合计94.937秒，
包含拒识和重试等待，不冒称程序初始化/文件处理也全部包含在API wall内。

八图high把77桌面/78正在关机/79无信号顺序写对，但75/76标题变为“同步与滞系统”，
大量课件/白板仍是概述，不能称质量合格。不能以某个锚点变对或正文变长宣布收益，
也不能从每条件一次的小样本建立稳定效果。根负责最终人工逐帧审阅；本轮不部署，
不改生产verbosity，不追加prompt/effort/model试验。

根已完整审阅4输出并确认上述结论：末三帧映射改善是局部观察，high没有解决
清晰标题错字、强连通信息丢失、概述/缺失问题。生产原verbosity保持不变，
不部署任何参数变更，不继续自动迭代。真实云实验仅有CLI请求设置证据，
没有云服务端回显实际verbosity的确认；loopback字段证明不能替代这一限制。
