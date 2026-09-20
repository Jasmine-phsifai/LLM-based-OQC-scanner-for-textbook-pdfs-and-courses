# 并行上下文观察写入验证

维护 run d40863c588cf406c8dc1c8b4669141bf；责任方 OCRLLM。

同一进程两模态各创建 context，原有 context 局部锁不能串行化共同目的文件的 open/append。WSL R: 挂载盘实测 8×200 个 24KB 事件，仅留下 444 个唯一事件；不是推理失败。改用内置文件 sink 的进程级锁后，1600/1600 可解析、唯一，无丢失。锁不覆盖推理，也不为跨进程写入提供保证。

运行：`PYTHONPATH=src /home/model-lab/.venvs/ocrllm-local-integration/bin/python tools/verify_parallel_observation_append.py --directory /mnt/r/course-pipeline-state/validation`。

原生产日志保留，损坏行不重建、不计为成功识别。因用户停止，未重启任何服务；新 consumer 进程使用修复源码，实产部署确认待用户恢复。
