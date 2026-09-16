# Codex 课程图片验收与原分组恢复（2026-09-16）

本轮修改仅在 OCRLLM owner：Codex 课程图片 opt-in 校验，以及只读公开原分组恢复接口。未改音频、媒体、生产 checkpoint 或旧 provider 默认校验。父级统筹负责真实付费模型联调与生产准入；本记录不将替身结果表述为模型识别质量证明。

## 公开调用

```python
from ocrllm import restore_image_batch_plan, resume_images_to_markdown
batches = restore_image_batch_plan(ordered_sources, output_path=output)
result = resume_images_to_markdown(batches, provider=provider, output_path=output)
```

`ordered_sources` 是 `tuple[str | Path, ...]`；返回与 `batchify_images` 相同的 `tuple[tuple[Path, ...], ...]`。恢复由 owner 加载并校验已有状态和当前全量源文件身份，不向统筹暴露 checkpoint 内部数据，不写状态或 Markdown、不调用模型。缺源、换序、内容变化均在调用前拒绝。修改 provider 或并发保留原有分组；普通 resume 继续负责 prompt/task 契约。

## 当前验收边界

- 每个预期文件均须有真实、可唯一归属的 HTML comment；一条 comment 只能归属一个文件。精确已知或漏 jpg 的 A 标记不能模糊冒充缺失 B。
- 只统计完整应得 comment 的增删编辑成本，替换计两次，严格小于应得长度 30%。漏 `.jpg` 或 `jpg` 可识别并补齐；该豁免不免除其他格式修改成本。只替换匹配 comment 本身，不补造不存在的 marker。
- 多余注释、冗余但已明确归属的 marker、明确倒序本身不拒绝。代码围栏、行内和缩进代码、已闭合 raw code/SVG 内的 comment 不充当帧标记；不审查正文/SVG正确性或完整性。
- 拒绝 U+FFFD 与不可 UTF-8 编码的 Unicode；正常 Unicode、tab、换行保留。
- 生产建议显式 `course_validation=True, adjacent_repeat_limit=8`。守卫只检查同帧内连续 8 次完全相同的长自然语言行，空行不打断、其他内容打断。长行至少 40 字符、20 个 Unicode 字母且以自然语句标点结尾；排除代码、SVG、数学/路径模板、标题和引用等。不同帧重新计数，不全文搜索。这是本轮新设的保守 OCR 规则：源码核实没有可直接继承的已有 OCR 重复硬门槛，未挪用 ASR token 阈值。

## 验证与限制

- `tools/verify_course_image_contract.py`：38 个 marker/Unicode/重复边界场景通过；用实际编码图片、公开 merged API 和真实替身 CLI 子进程生成部分结果后恢复。新 8+1 原计划、旧 1+1+1 原计划均只重做失败一组；换模型/3 路 provider 后已完成组仍复用；源不符时 0 次调用；只读查询前后 checkpoint 与 Markdown 字节哈希不变。合计 7 次替身 CLI、0 次真实模型调用。
- WSL 输出路径 316 字符完成；Windows 既有输出路径保护已证明在 CLI 调用前拒绝过长路径。Windows 全流程替身尚未通过：测试 `.cmd` 启动器对完整课程提示词的引号传递损坏，未将其修复作为本轮 WSL 生产前置，也不据 WSL 结果声称 Windows 全流程已通过。
- 保守重复守卫私下读取当前已保存的 7,900 个帧段：0 个标记，扫描 0.76 秒；无识别正文写入本记录或 JSON。初版曾误标一段 19 次相同的 Python RESTART 控制台输出，已加入自然句末和路径/结构排除后重验。0 标记说明该语料中未发现误标，不证明所有未来内容均正确或没有循环。
- 30,424 字符、8 帧正常文本共 12 次校验：中位 2.70 ms，最大 2.86 ms。该数值仅为当前样例开销，不是一般性性能保证。
- 相关现有契约测试：`tests/test_lightweight_import.py tests/test_merged_image_recognition.py tests/test_provider_model.py`，46 项通过（最后一次 6.32 秒）。Codex adapter 与 usage 由同仓另一有界 slice 验证并记录。

重跑入口（选择新空目录；`--existing-output-root` 只读已有 Markdown，必须指向实际目录）：

```sh
PYTHONPATH=src python tools/verify_course_image_contract.py --work-dir /path/to/fresh-scenario --existing-output-root /path/to/course-output
```

对应仅聚合证据：[course_image_contract_2026-09-16.json](course_image_contract_2026-09-16.json)。
