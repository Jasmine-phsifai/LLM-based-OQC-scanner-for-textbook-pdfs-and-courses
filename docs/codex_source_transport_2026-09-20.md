# OCRLLM→CLI 入场图像顺序核对（2026-09-20）

上一切片8图真实输出出现正文/帧身份错位。本次只定位OCRLLM公开API到CLI进程入场
之间是否传错图，不请求任何真实模型、不改产品算法/提示/生产状态。

复用 `tools/verify_course_image_contract.py` 的真实synthetic可执行CLI，增加可选
`--source-manifest`。它在收到真实进程argv后依次读取每个 `-i` 文件，记录SHA256、
字节数、像素尺寸、staging basename，并解析实际prompt原始文件名JSON数组。
父进程经公开 `recognize_images_to_markdown` 串行发送相同真实三组8图，逐项对比
原图SHA/尺寸/字节/顺序与prompt身份映射，之后确认源图未变、临时目录已清理。
没有mock内部识别函数或直接调用staging helper冒充端到端测试。

结果：三组24个入场位置（20张不同原图）全部一致，无跨组串位；全部1920×1080。

|组|prompt原名次序|SHA/尺寸/字节与原图逐项一致|
|---|---|---|
|blank|88,89,90,91,92,93,94,95|是|
|partial_readable|72,73,74,75,76,77,78,79|是|
|mixed|0,1,2,3,88,89,90,91|是|

原有marker/恢复场景一并通过，总10次synthetic CLI（原场景7+新增3），真实模型0。
没有生成真实课程识别稿；synthetic返回固定合成文本，仅供验证公开API完整返回。

复现命令：

```
/home/model-lab/.venvs/ocrllm-local-integration/bin/python tools/verify_course_image_contract.py --work-dir /mnt/r/course-pipeline-state/scenarios/codex-source-transport-20260920 --source-manifest /mnt/r/course-pipeline-state/scenarios/codex-course-wrapper-manifest-20260920.json
```

复跑应换新work-dir。持久机器证据为该目录 `course-image-contract.json` 内
`public_restore.source_transport`；`synthetic-calls.jsonl` 是子进程直接捕获的入场事实。
源路径、图像SHA及完整顺序保存在本地R盘，不在公共仓库复制课程内容。

**边界**：此证据仅排除这三个输入计划在OCRLLM→CLI进程入场前的错图/错序/缩放。
没有运行真实Codex CLI，因此不能证明CLI内部附件处理、后端图像解码、模型内部
图像排序或模型输出帧标记与正文绑定。不能将本场景通过泛化为真实8图识别质量合格，
也不能据此把后端或模型确定为唯一原因。过去真实请求的独立prompt/hash核对由统筹记录。
