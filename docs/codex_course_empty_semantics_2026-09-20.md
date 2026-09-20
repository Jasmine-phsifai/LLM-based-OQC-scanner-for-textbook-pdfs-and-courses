# Codex course 空白语义对照（2026-09-20）

## 当前边界

本轮试验仅针对 `CodexCLISettings.course_validation=True` 的wrapper补充真实空白帧结果；
基础 `course.legacy.v1` 提示词不改，其他provider及普通Codex wrapper不改。
Unicode、帧标记匹配、相邻重复检测、拒识分类、有限重试和预算保持原实现。
模型必须自行输出对应marker；程序不补造遗漏marker，不将既有SORRY事后转换成成功。

窄候选精确新增文字：

> 课程图片中，只有当整张图片确实没有可见课程文字、公式或图形时，仍输出原始提示要求的对应帧标记，随后单独一行[本帧无可见课程内容]；这种真实无内容情况不属于识别失败。有内容但看不清不是无内容；屏幕关闭但其他区域仍有板书，也不是无内容。

其后原始“如果识别任务令人困惑或无法根据附加图片完成，请只回复SORRY…”规则逐字保留。

## 诊断与已否决候选

失败原文早已由 `usage_events.preserve_failed_output` 保存到独立attempt文件，完成事件包含
路径、SHA256和源图片引用；没有必要再加日志框架。
第一次广候选还加入“不因无法完整转写而整批拒绝/保留可读片段”等指令。
三组8图 before/after 共6次API、7次真实CLI调用均通过程序校验，但人工核验发现
数学课件标题误字、帧内容错位、公式省略和摘要式描述；基础路线也有既有质量问题。
广候选没有证明质量合格，已撤回且不部署。原请求、输出、源码及token记录完整保留。

A/B各组输入bytes和base prompt相同，仅wrapper不同，串行并发1。
blank与partial_readable来自各自连续8帧；mixed为人为组合4张网页/4张空场景，
不冒称自然连续槽。测试目录独立，既有生产checkpoint和恢复额度未使用。

|组|版本|CLI次数|wall秒|
|---|---|---:|---:|
|blank|before|1|11.824|
|blank|广候选|1|10.427|
|partial_readable|before|1|28.678|
|partial_readable|广候选|1|32.540|
|mixed|before|2|28.329|
|mixed|广候选|1|15.838|

mixed before 的首次失败与有限重试都计入上述wall与token，未隐藏。
单组单次对照不能建立稳定拒识率或因果质量提升结论。

## 可复现工具与隔离

实验目录内归档的 `compare_codex_course_wrapper.py` 通过公开 merged image API执行；before只在
真实子进程argv边界替换为指定Git版本的纯wrapper输出，不monkeypatch识别内部函数。
`--candidate-label narrow` 仅跑新候选，沿用已完成before，避免额外重复请求。
不带 `--run-real` 只校验manifest并显示实验计划，不请求模型。

持久本地证据：

- `/mnt/r/course-pipeline-state/scenarios/codex-course-wrapper-ab-20260920`
- `/mnt/r/course-pipeline-state/scenarios/codex-course-wrapper-narrow-20260920`
- `/mnt/r/course-pipeline-state/scenarios/codex-course-empty-narrow-contract-20260920`

每个实验含plan、runner身份、逐组输出/失败原文、usage事件、prompt摘要与完整请求。
课程内容不提交公共仓库；根仓负责选中R工作区内的人工审查材料。

## 离线验证

88项merged-image/Codex contracts通过；原真实合成CLI course scenario通过，
覆盖真空白声明、混合文本、原拒识规则仍在、错误marker/Unicode/相邻重复仍拒绝。
非course wrapper原文保持不变。唯一警告为已有pytest缓存写权限。

窄候选三组均一次CLI返回并通过现有validator：blank 10.637秒、partial_readable
23.282秒、mixed 17.740秒。blank八帧与mixed末四帧输出固定无内容声明；
数学组未误标无内容。但数学组仍有74/75内容错位、泛述板书等问题，mixed网页标题
也有误字。因此本实测只证明无内容声明可以表达和通过现有契约，不证明完整转写质量
或多图身份映射可靠，更不能以validator complete代替内容验收。

窄候选使用90332 input / 1676 output tokens（缓存输入26880为input子集），
三次请求的token均有独立owner事件可溯源；原before/广候选使用210666 input /
4163 output，7次CLI含1次失败，失败和等待wall完整计量。最终根人工验收决定：两版都不部署，也不提交产品修改。
候选源码、实验工具及修改过的验证脚本已归档到narrow实验目录；产品、已有tests、
已有scenario均恢复3f2faca原文，工具不进入正式产品入口。HEAD默认wrapper未改变。

下一步应单独诊断8图内容与帧身份错位及转写摘要化，不能把marker齐全等同正文对应正确。
本轮不擅自加正文审核、不改并发/模型/图片批量、不重置生产失败额度。
未获得充分质量证据前不能将实验成功状态作为批量重新识别授权。

## 额外限定单图诊断

根另行授权原始HEAD对同一数学frame75仅一次单图API，仍luna low/default、原
提示词和有限重试，并发1、独立usage，不改生产8图规划。1次真实CLI，12.948秒，
标题正确输出“2.4 同步与脉冲系统的若干定义”；但剩余内容仅短摘要和几个数学符号，
仍非完整转写。此结果支持该标题在单图能读出，不能证明单图全内容质量合格，
也不能单凭1个样本将8图问题归因某个内部排序算法或调整生产batch。

证据 `/mnt/r/course-pipeline-state/scenarios/codex-course-single-frame75-20260920`，
包含独立runner、输入hash、输出、usage和终态result。此项额外1API完成即停止。

该单图 input 12583 / output 301 tokens，cache 8960 为input子集。
