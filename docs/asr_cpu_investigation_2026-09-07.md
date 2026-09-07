# Qwen3-ASR-1.7B CPU 路线只读调查

- 调查日期：2026-09-07（Asia/Shanghai）
- 目标模型：`Qwen/Qwen3-ASR-1.7B-hf`，本机已缓存修订 `bcd2b5b7f32b480ab5790554cfa8347f246a14f3`。
- 范围：只读检查 Model Lab、OCRLLM harness、`D:\Local model runner and investigater` 的历史证据、本机 CPU/RAM 与已装包，并查询一手上游资料。
- 本版补充：核实参考目录的 candidate/worker 仅有 benchmark lifecycle、各 Qwen 条目的可调用状态，并收窄未来服务拓扑结论。
- 验证方式：Terra/max 子代理只读代码、历史报告与本机环境并查询官方资料；主代理复核关键源码与官方支持表后保存本记录。未修改运行时代码、未启动/停止服务、未加载模型或运行CPU推理，未干扰当前GPU计时。

## 结论

| 问题 | 结论 | 置信边界 |
|---|---|---|
| 现有 `qwen3-asr-1.7b` 服务能否切到 CPU？ | **不能直接切。** 当前实现把该模型加载到 `cuda:0`，先取得 GPU lease，并在每次生成后调用 `torch.cuda.synchronize()`；没有 CPU device 配置项。 | 由当前源码直接证明。|
| 相同 1.7B checkpoint 能否在 CPU 上技术上运行？ | **有可行的后端路径，但尚未在本机验证。** 原生 Transformers 代码按模型实际 device 运行；Optimum Intel 的支持表列出全部 Qwen3-ASR 模型。 | 后者是架构/模型族支持声明，不是对 `Qwen3-ASR-1.7B-hf` 这个精确 HF revision 已成功导出、运行或量化的证明；速度、内存峰值、长音频稳定性和转录质量仍未知。|
| 内存是否首先构成明显硬阻塞？ | **从静态容量看没有明显硬阻塞。** WSL 当前可用内存约 42–43 GiB，缓存 checkpoint 的 `model.safetensors` 为 4,076,193,080 bytes（目录显示 3.9G）。 | 型号名的 `1.7B`、模型卡约 2B 的整模型统计、文件大小和运行时 RSS 是不同指标；不得由任一项直接推算 CPU 内存。|
| 现在能否让 CPU 完整跑课程，同时不影响正在计时的 OCR/ASR？ | **不应现在做，也不能据现有证据承诺。** 这会不占 GPU VRAM，但会竞争 CPU、RAM、内存带宽、MP3 解码/重采样和 `/mnt/d` I/O；当前三课正式计时期间不应开始。 | 没有 1.7B CPU 实测，更没有完整课程 CPU 实测。|
| 能否复用当前 GPU manager，借此“并行”？ | **当前实例不能直接复用。** 它只有一个进程内请求锁和一个跨进程 GPU lease，OCR 与 ASR 会串行且互相卸载。未来可以重构/参数化其管理代码，或在同一 gateway 后接 CPU ASR backend；但 CPU backend 不能取得 GPU lease、不能占用当前单模型槽位来宣称并行。 | 当前实现的限制由源码直接证明；未来拓扑是设计选择，尚未决定。|
| 是否已有同样便利的官方 CPU 服务/注册？ | **发现了真正的官方 HTTP 候选：OpenVINO Model Server（OVMS）。** 它提供 CPU S2T 的 OpenAI-compatible `audio/transcriptions` / `audio/translations`，其 GenAI 支持表明确列出原始 checkpoint `Qwen/Qwen3-ASR-1.7B`。 | 这不是对本机缓存的 `Qwen/Qwen3-ASR-1.7B-hf` 已验证服务的证明；当前文档未列出该 `-hf` 变体或现成 IR，且 OVMS 是 multipart transcription wire，不能被 OCRLLM 当前 JSON Chat `input_audio` 调用直接替换。|

因此，CPU 1.7B目前是待验证候选，尚无完整课程生产证据。本轮仅调查；为保持当前三课计时口径一致，没有并行启动CPU模型负载。

## 当前模型、服务与已证明的 GPU 基线

1. Model Lab 配置把公开 ASR model ID 固定为 `qwen3-asr-1.7b`，并固定到 `Qwen/Qwen3-ASR-1.7B-hf` 的本地 snapshot 修订：
   - `course-ocr-asr-model-lab/scripts/local_qwen_service_config.py:34-38,64-79`
   - `course-ocr-asr-model-lab/results/qwen3_asr_summary.json:2-30`

2. 需要区分三个不会互相替代的统计口径：

   | 口径 | 本次读到的值 | 适用含义 |
   |---|---|---|
   | 产品/仓库型号名 | `Qwen3-ASR-1.7B-hf` | 这是本调查锁定 checkpoint 的名称，不能拿来乘 dtype 估 RAM。|
   | 官方模型卡元数据 | `Model size: 2B params`、`Tensor type: BF16` | 整模型卡的约数/元数据，不等于本机 CPU 加载时的精确参数驻留量或 dtype。|
   | 本机缓存文件 | `model.safetensors` 为 4,076,193,080 bytes，完整 snapshot 为 3.9G | 已下载权重文件的静态存储量，不等于运行时 RSS。|

   因此本报告**不**使用 `1.7B × 2 bytes`、`2B × 2 bytes` 或任意文件大小倍数来承诺 CPU 内存。CPU 的实际占用还取决于加载 dtype、权重展开/allocator、音频与特征、KV cache、Python runtime 和并存的 Base64 缓冲，只能在相同模型 CPU probe 中测量。

   - 本机只读路径：`/mnt/d/model-cache/course-ocr-asr-model-lab/huggingface/hub/models--Qwen--Qwen3-ASR-1.7B-hf/snapshots/bcd2b5b7f32b480ab5790554cfa8347f246a14f3/`
   - 官方模型卡：[Qwen/Qwen3-ASR-1.7B-hf](https://huggingface.co/Qwen/Qwen3-ASR-1.7B-hf)（模型大小与 dtype 位于页面的 “Model size / Tensor type” 部分）。

3. 现有 1.7B 成绩是 CUDA BF16，不能外推 CPU：19 个 60 秒课程片段共 1,140 秒，GPU 路线为 56.28 秒、RTF 0.049、峰值 5,032 MiB VRAM；README 也只把它列为 GPU 技术转录路由。
   - `course-ocr-asr-model-lab/README.md:222-233,272-284`
   - `course-ocr-asr-model-lab/results/qwen3_asr_course_benchmark_wsl.json:2-21`

4. 当前服务同时承载 Qwen3.8 OCR 和 Qwen3-ASR；说明明确写着一个 GPU lease、一个请求锁、两个 backend 不会同时驻留。
   - `course-ocr-asr-model-lab/README.md:27-58,93-98`
   - `course-ocr-asr-model-lab/scripts/local_qwen_model_manager.py:54-75,224-301`

这解释了为什么现有 GPU route 会影响大 OCR：ASR 请求必须等 GPU 资源、并可能触发 OCR/ASR backend 切换；它不是可与 OCR 并行驻留的服务。

## 为什么当前服务不是 CPU 版本

`ModelManager.transcribe_mp3()` 读取/必要时重采样音频后，将输入移动到模型 device 与 dtype，生成结束后无条件调用 `torch.cuda.synchronize()`：

- `course-ocr-asr-model-lab/scripts/local_qwen_model_manager.py:92-203`，尤其 `:137-151`。

更关键的是 `_ensure_asr()` 先获得 GPU lease，再用 `dtype=torch.bfloat16` 加载 snapshot 并显式 `.to("cuda:0").eval()`：

- `course-ocr-asr-model-lab/scripts/local_qwen_model_manager.py:266-301`。

配置也只定义 `GPU_LOCK_PATH`、GPU lease timeout 和共享 GPU 请求队列；没有类似 `LOCAL_QWEN_ASR_DEVICE=cpu` 的参数：

- `course-ocr-asr-model-lab/scripts/local_qwen_service_config.py:64-103`。

所以仅把某个环境变量改为 CPU 不成立：即使替换了 `.to("cuda:0")`，仍残留 GPU 锁和 `torch.cuda.synchronize()`。这只描述**当前** `ModelManager`：它不能在正式任务中直接变成 CPU backend。以后可以抽取或参数化其中的管理代码，也可以在同一 gateway 后增加 CPU ASR backend；前提是 CPU 路径有自己的运行时/模型状态，不取得 GPU lease，也不经过 CUDA 调用。

服务 manager 也绑定同一监听地址、PID 文件和 service script：它在启动时创建同一 state root/PID，拉起 `local_qwen_openai_service.py`，并以该 PID 的 `/health` 为真值：

- `course-ocr-asr-model-lab/scripts/manage_local_qwen_service.py:24-129,156-169`。

这证明的是当前 service manager 的身份不能被第二个未区分的进程复用：两个独立 HTTP listener 不能同时绑定 `127.0.0.1:38871`，也不能盲目共用同一 PID/state/stop 控制，否则可能误杀或取代正在服务 OCR 的进程。它**不**预先决定未来拓扑：可以选独立 endpoint，也可以保留一个 gateway 路由并把请求分发给独立 CPU worker；无论哪种，GPU 与 CPU backend 的进程/状态所有权必须清楚，且 CPU 路径不得共享 GPU 锁。

## 相同 1.7B 的 CPU 后端是否存在

### 原生 Transformers：存在技术入口，尚无本机 CPU 证据

官方 Qwen 模型卡给出了原生 Transformers 的 `AutoProcessor` / `AutoModelForMultimodalLM` 加载入口，并将 1.7B 描述为支持离线和流式长音频的 checkpoint：

- [官方 Qwen 1.7B-hf 模型卡](https://huggingface.co/Qwen/Qwen3-ASR-1.7B-hf)（Transformers 使用示例、模型家族及长音频说明）。

Qwen 开源 toolkit 的 Transformers backend 不是把设备写死为 CUDA：它读取参数所在 device，找不到时回退为 CPU；`from_pretrained()` 将额外参数原样传给 `AutoModel.from_pretrained()`；推理时把 inputs 移到 `self.model.device` 后 `generate()`。

- [Qwen 官方 `qwen3_asr.py`: 设备与加载逻辑](https://raw.githubusercontent.com/QwenLM/Qwen3-ASR/main/qwen_asr/inference/qwen3_asr.py)（约 152-209 行）
- [Qwen 官方 `qwen3_asr.py`: Transformers 推理逻辑](https://raw.githubusercontent.com/QwenLM/Qwen3-ASR/main/qwen_asr/inference/qwen3_asr.py)（约 449-476 行）

这足以证明“显式 CPU device 的 native Transformers 候选”在代码层面存在；它**不足以**证明这个 CPU、这个 HF revision、长课程 slice 和当前提示词组合会成功或足够快。官方性能加速样例明确是 A100/CUDA，不是 CPU 性能承诺：

- [模型卡的 speed/memory 样例](https://huggingface.co/Qwen/Qwen3-ASR-1.7B-hf#speed--memory-improvements)。

### OpenVINO / Optimum Intel：架构级支持与量化可能性存在，精确 1.7B-hf export 仍未证明

Hugging Face 的 Optimum Intel 支持表当前明确列出 “All Qwen3-ASR models”，而 export CLI 接受 Hub model ID 或本地模型路径并提供 `fp32`、`fp16`、`int8`、`int4` 等权重格式。这个组合支持把 1.7B 列为待测 OpenVINO 候选，但本次没有找到官方针对精确 `Qwen/Qwen3-ASR-1.7B-hf` revision 的导出示例、已发布 IR 或成功矩阵。因此不能把架构支持声明写成该 `-hf` checkpoint 的已证实 CPU export。

1. 同 checkpoint 的 native Transformers CPU（先验证正确性与基本资源）；
2. 同 checkpoint 的 OpenVINO export 后 CPU（FP16 先行，INT8/INT4 仅作为单独的质量/稳定性候选）。

官方资料：

- [Optimum Intel 支持模型表](https://huggingface.co/docs/optimum-intel/openvino/models#qwen3-asr)
- [OpenVINO export 参数与量化格式](https://huggingface.co/docs/optimum-intel/openvino/export)
- [OpenVINO GenAI CPU/GPU device API 概览](https://github.com/openvinotoolkit/openvino.genai#quick-start)

不能把 “支持 export” 等同于 “当前机器已有可用量化 1.7B CPU 服务”：当前 Model Lab 的运行 venv 是 `torch=2.13.0+cu132`、`transformers=5.16.1`、`vllm=0.28.0`，没有 `qwen-asr`、`openvino`、`openvino-genai` 或 `optimum-intel`；另一个 `course-lab-qwen3-asr` venv 只有 Transformers 元数据，未见 torch/OpenVINO runtime。上述结论来自只读 `importlib.metadata` 查询，未 import torch 或加载模型。

## 对 `D:\Local model runner and investigater` 证据的正确使用

该目录不是一个常驻模型服务项目；它是用于记录受控离线试验的 local-inference benchmark runner。README 所谓“Run a registry candidate”要求给定 workload、phase、目标时长和 config index；CLI 只有 `make-inputs`、`run`、`sustained`、`report` 四个子命令，没有 service `start/status/stop` 子命令：

- `README.md:94-115`；
- `src/local_inference_bench/cli.py:11-50`。

其 registry 是**离线 benchmark candidate registry**，不是可供 OCRLLM 发现的服务注册表。普通 runner 写一次 `request.json`、`Popen` 一个带 `--request` 的 worker、等待退出，并把输出与进程资源写入 artifact/event journal；超时会 kill 该次 worker：

- `src/local_inference_bench/launch_candidate.py:24-97`；
- `src/local_inference_bench/project_paths.py:3-13`。

受控 sustained runner 也只管理一次试验：它要求 workload/phase/时长，创建 benchmark-owned child process 和 telemetry，结束、超时或中断时关闭 Windows job 或终止该 process tree。它没有持久 PID file、HTTP health endpoint、端口绑定或可查询的 daemon status：

- `src/local_inference_bench/run_sustained.py:59-100,755-826,846-930,986-1058`；
- `src/local_inference_bench/terminate_process_tree.py:1-69`。

### 当前 0.6B CPU candidates 的可调用状态

**所有** Qwen3 CPU/OpenVINO candidate 都是 0.6B，而非当前 1.7B：

- `registries/candidates.json:68-78` 的 native CPU candidate 是 `Qwen/Qwen3-ASR-0.6B-hf`；
- `registries/sustained_candidates.json:257-368` 中每个 native/OpenVINO/GenAI candidate ID、源模型或 artifact 都是 `0_6b` / `qwen3-asr-0.6b`；
- `scripts/export_qwen3_asr_openvino_genai_official.py:29-37,95-107` 明确从 `qwen3-asr-0.6b-original` 导出 FP16。

具体 status 也不能误读为“现成可上线 CPU 服务” ：

| 条目 | runner 中的现状 | 含义 |
|---|---|---|
| `qwen3_asr_0_6b_cpu`（普通 registry） | `legacy_hf_baseline`；普通 `run` 只接受 `enabled` / `planned`。 | 普通启动器会拒绝它。|
| native、OpenVINO、HF-native OpenVINO sustained 条目 | 分别标为 `retired_legacy_*`。 | sustained selector 明确拒绝所有 `retired*` candidate。|
| OpenVINO GenAI official / tailfix sustained 条目 | 当前 JSON 未标为 `retired`；后者又限制在 quality/compatibility phase。 | 作为**受控 benchmark job**仍可能经 `sustained` CLI 调用，不等于 HTTP service 或桌面注册。|

证据：`registries/candidates.json:68-78`、`registries/sustained_candidates.json:257-368`、`src/local_inference_bench/launch_candidate.py:24-31`、`src/local_inference_bench/run_sustained.py:699-733`。本次只读 `stat` 还确认这些旧 0.6B 环境的 `python.exe`、native checkpoint 和 GenAI export marker 在 Windows 盘存在；未运行环境 verifier，不能据此断言它们今天仍可启动。

### 可借鉴的 worker 模式，及不可直接复用的部分

可借鉴的是实现模式，而非候选身份或性能数字：

1. native 0.6B worker 明确设置 `torch.set_num_threads()` 与 interop=1，在一个 benchmark process 内加载一次 model、warmup 后循环处理 workload；`workers/qwen3_asr_sustained_worker.py:22-55,57-132`。
2. OpenVINO GenAI worker 显式接受 `CPU` / `GPU.0`，在 CPU 时设置 `INFERENCE_NUM_THREADS`，并在一个 resident benchmark process 中保留 pipeline；`workers/qwen3_asr_openvino_genai_sustained_worker.py:45-103,116-243`。
3. HF-native OpenVINO worker 还检查 EOS、token cap 和退化生成；这些是 1.7B CPU probe 可借鉴的成功判据；`workers/qwen3_asr_hf_openvino_sustained_worker.py:29-103,162-233,280-433`。
4. runner 的 process-tree cleanup、资源监控和 artifact 记录可作为将来 launcher 的参考，但它的所有权模型是假设 controller 启动并在一次 benchmark 结束时杀掉 child，不可原样套为常驻 service lifecycle。

不可直接复用的部分是：所有模型路径、revision、export 和状态都是 0.6B；worker 协议是本地 JSON 文件 `--request` / `response.json`，不是 OCRLLM 的 Chat Completions Base64 MP3 wire；GenAI worker 还要求 PCM16 mono 16 kHz WAV（`workers/qwen3_asr_openvino_genai_sustained_worker.py:318-355`）。因此它提供 CPU/线程/健康判据的代码参考，**不**提供 1.7B-hf 的现成服务或 API adapter。

可带走的历史事实：

- 该主机上曾有可工作的 Qwen3-ASR CPU/OpenVINO 工具链和线程控制形式；历史 0.6B Transformers CPU 在 24 threads 下曾报告 7.56 audio h/h、4.24 GiB RSS、约 98.3% host CPU：`reports/local-inference-feasibility.md:48-60`。
- 新的 0.6B OpenVINO GenAI 短样本 CPU/iGPU 对比报告 CPU 15.7637 audio h/h；但 120.08 秒项目在 512 token cap 下 stable 与 tail-fixed 都失败：`reports/sustained-quality-and-compatibility.md:196-224`。
- 同报告把该 0.6B Qwen 路线定为人工第二意见而非自动 bulk lane：`reports/sustained-quality-and-compatibility.md:158-194`。

不能带走的东西：上述任一 throughput、RSS、24-thread 设置、120 秒失败率、质量指标或 CPU/iGPU 差异，都**不能**代入 1.7B。模型规模、export、decoder 行为和量化均不同；本调查没有用它们预测 1.7B 时间。

## RAM、CPU 与“不会影响 OCR”的含义

本机此次只读快照：Intel Core Ultra 9 285K，24 个可用 CPU（24 core、每 core 1 thread），WSL 可见内存约 47 GiB、`MemAvailable` 约 42–43 GiB、swap 16 GiB 空闲。历史机器记录的 WSL cgroup memory limit 是 50,511,626,240 bytes：

- 只读命令：`lscpu`、`free -h`、`/proc/meminfo`；
- `course-ocr-asr-model-lab/results/machine.json:16-34`。

这意味着单份 3.9G checkpoint 有容量余地；不意味着“CPU 只有空闲资源”。当前 harness 的完整课程音频会先切 MP3，再发多个独立 Chat 请求：

- `OCRLLM/tools/benchmark_course_recognition.py:115-177,181-209`：音频以 1–30 分钟 interval 规划，默认 30 分钟，按 course 逐一执行；
- `OCRLLM/src/ocrllm/providers/openai_compatible/build_openai_compatible_audio_request.py:24-91`：请求把 MP3 整体读入内存并 Base64 编码，inline 源文件上限为 25 MiB；
- `course-ocr-asr-model-lab/scripts/local_qwen_model_manager.py:100-120`：服务端还会 decode、downmix、必要时用 librosa 重采样。

所以 CPU service 的 GPU 占用可以为零，但它仍会争用：

1. 生成本身的 CPU cores 与内存带宽；
2. 客户端 Base64 缓冲与服务端 waveform/feature buffers 的 RAM；
3. `ffmpeg` 切片、`soundfile`/librosa 解码重采样的 CPU；
4. `/mnt/d` 上课程文件、临时 MP3、输出文件的 I/O。

历史 0.6B 24-thread 运行接近满 CPU，已经说明“不占 GPU”不能翻译为“不影响当前 OCR/ASR 计时”。为了减少干扰，CPU 实验应等待正式任务完成，并从一个 worker、低 thread cap 开始；不要同时跑多个 CPU ASR 进程。

## 服务注册与 OCRLLM 接口

OCRLLM 的当前 generic OpenAI-compatible 音频 adapter 已经能接受另一个 base URL，无需新增专用 `ocrllm` worker：

- `OCRLLM/src/ocrllm/providers/openai_compatible/provider_settings.py:15-66`：base URL 是独立配置；
- `OCRLLM/src/ocrllm/providers/recognize_provider_model_audio.py:27-48`：audio `ProviderModel` 走 generic adapter；
- `OCRLLM/src/ocrllm/providers/openai_compatible/build_openai_compatible_audio_request.py:24-43`：实际 wire 是 `model` + `input_audio.data`（raw Base64）+ `format="mp3"` + text prompt；
- `OCRLLM/src/ocrllm/AGENTS.md:74-78,100-106`：shared worker registration 仍 deferred，不能借此添加新的 OCRLLM worker/pool。

当前 Model Lab HTTP service 已经接收这个 wire（`local_qwen_openai_service.py:103-208`）。未来 CPU backend 若保持同一 Chat Completions 请求形状并选择单独 endpoint，OCRLLM 调用方可只换 `base_url`；若选择保留同一个 gateway，则应在 gateway 内保持这个 Chat Completions 形状并把 ASR 请求分发到明确的 CPU backend。两种部署形式都仍是将来实现选择。

### 补充核查：OVMS 是真实 HTTP 语音服务，但接口与当前 harness 不同

OpenVINO Model Server（OVMS）不是上一节参考目录那种一次性 benchmark worker。官方文档说明它以 Docker 或 bare-metal `ovms` 进程启动，配置模型/graph 后公开 REST/gRPC；Speech-to-text 由 `S2tCalculator` 接收 HTTP，持有加载一次的 OpenVINO GenAI pipeline 资源，graph 可指定 `target_device: "CPU"`。当前 GenAI 支持表明确列出 `Qwen3ASRForConditionalGeneration`，示例模型包括**原始** `Qwen/Qwen3-ASR-1.7B`，并特别注明 export 需要 `qwen-asr`：

- [OVMS 启动与配置方式](https://github.com/openvinotoolkit/model_server/blob/main/docs/starting_server.md)；
- [OVMS speech-to-text calculator](https://docs.openvino.ai/2026/model-server/ovms_docs_speech_to_text_reference.html)；
- [OpenVINO GenAI Qwen3-ASR 0.6B / 1.7B 支持表](https://openvinotoolkit.github.io/openvino.genai/docs/supported-models/#speech-recognition-models-whisper-based)。

OVMS 的语音接口是实际可查询的服务协议：`POST /v3/audio/transcriptions`（另有 `/v3/audio/translations`），`multipart/form-data` 的 `file` + `model`，支持目前文档明确列出的 `mp3` / `wav`、可选 `language`、`stream` 和 `temperature`，返回 `{ "text": "..." }`；官方 demo 以 `/v1/models` 作为 readiness 检查。它的音频 buffer 上限也单列为 `OVMS_AUDIO_MAX_FILE_SIZE_BYTES`：

- [OVMS OpenAI speech-to-text API reference](https://github.com/openvinotoolkit/model_server/blob/main/docs/model_server_rest_api_speech_to_text.md)；
- [OVMS 官方 audio demo（部署、readiness、请求）](https://github.com/openvinotoolkit/model_server/blob/main/demos/audio/README.md)。

OVMS 是把已转换的 OpenVINO IR 作为 CPU service 运行的服务层，不是当前 checkpoint 自动附带的“CPU 版本”。本次有界官方检查没有找到精确 `Qwen/Qwen3-ASR-1.7B-hf` 的预制 OVMS IR。它仍是“同样便利的 CPU service”**候选**，可复用实际服务启动、模型/graph routing、`/v1/models` readiness、CPU target 和 transcription endpoint；但现有证据有三个不能跳过的边界：

1. 支持表点名的是 `Qwen/Qwen3-ASR-1.7B`，不是当前缓存的 `Qwen/Qwen3-ASR-1.7B-hf`。本次未找到官方对该 `-hf` 变体的 OVMS export、预制 IR 或 serving demo；不得把原始 checkpoint 的列名当作 `-hf` 兼容证明，也不得为此擅自换模型。
2. OVMS 要有适于 serving 的 OpenVINO model repository / `graph.pbtxt`，而不是直接把当前 `.safetensors` snapshot 当 daemon 参数；官方文档建议由 export script 准备。该 export 尚未在本机做过，也不在本次实施范围内。
3. OCRLLM 当前请求是 JSON `POST .../chat/completions`，内容为 Base64 `input_audio` **和 text prompt**；OVMS 是 multipart `POST .../v3/audio/transcriptions`。其当前 API 表将 transcription 的 `prompt` 标为不支持。因此**不能只改 OCRLLM 的 `base_url` 直连 OVMS**，也不能假设现有 ASR prompt 行为会保留。将来如采用 OVMS，需在集成边界另行验证 transcription 调用、prompt 语义或兼容 gateway；本次不设计或实现它。

Qwen 自己的方便服务仍是不同路径：原始 `Qwen/Qwen3-ASR-1.7B` 模型卡的 `qwen-asr-serve` / `vllm serve` 文档给出 GPU 依赖与 GPU memory 参数，也说明 vLLM 可走 `audio_url` Chat Completions **及** OpenAI transcription API。那是 Qwen 官方 GPU serving，不构成 CPU service；它也不能证明本机 `-hf` 的 OVMS 路线。

- [Qwen 原始 1.7B 模型卡：vLLM serving、Chat/audio_url 与 transcription](https://huggingface.co/Qwen/Qwen3-ASR-1.7B)；
- [Qwen 官方 `serve.py`](https://raw.githubusercontent.com/QwenLM/Qwen3-ASR/main/qwen_asr/cli/serve.py)（vLLM wrapper）。

### 如后续验证通过，服务形态应满足的约束（不是预先指定拓扑）

这不是本次实施建议，只是边界设计：

| 关注点 | 已知约束与可选形态 |
|---|---|
| CPU runtime | 需要一个不会取得 GPU lease、不会调用 CUDA、不会与当前 single-model slot 串行共享的 CPU ASR runtime。可为独立 worker/process，也可由参数化后的管理代码创建；当前 `ModelManager` 实例本身不是该 runtime。|
| gateway / endpoint | 两个独立 listener 必须用不同端口；但若一个 gateway 负责路由，则可保留一个公开地址并把请求送往 CPU worker。因此不应在实测前强定“必用新端口”。|
| PID / state / lifecycle | 若使用另一个进程，需独立、可识别的 PID/state ownership，不能让它被当前 GPU manager 的 stop/status 误认；若同一 controller 管理多 backend，则需要等价的身份隔离。是否做 desktop/service 注册留到 backend 通过后决定。|
| 并发 | 初始一条 resident CPU worker/request slot；这是资源隔离与真实性要求，不把队列串行包装成“并行”。|
| 线程 | 显式记录并保守起步，例如 2–4 个推理线程；同时限制 OpenMP/MKL/BLAS/torch interop，随后只凭同模型实测调大。|
| 对 harness | 保持现有 Base64 MP3 Chat Completions wire 的 endpoint 可由 generic `OpenAICompatibleSettings(base_url=...)` 接入；OVMS 的 multipart transcription API 不适用此结论，须另验接口与 prompt 行为。本次不添加 adapter 或 worker registration。|

独立 CPU service 可以与 GPU OCR **同时存在**，但“同时存在”仅保证不占 GPU；是否允许同时执行，应由 CPU/RAM/I/O 小样本证据决定。

## 最小、可验证的下一步（不在本次执行）

本轮正式GPU ASR已经发现：同一十分钟片段在现有`audio.long.interval.v1`提示词下返回NOSPEECH，无text对照则返回转写。未来CPU验证必须带OCRLLM实际提示词并记录版本/哈希；无提示词成功只证明裸模型候选，不能作为当前harness协作通过。更换设备本身也不能视为解决提示词兼容性。详见同日三课程计时记录。

等当前三课 ASR/OCR 正式计时彻底结束后，先做一个单一的 1.7B CPU acceptance probe，暂不注册常驻服务：

1. 新建隔离 CPU 环境，不改动 `course-lab-vllm`；使用当前已缓存的精确 `1.7B-hf` revision，不下载替换模型。初始使用原生 Transformers CPU 路线，显式将模型和 inputs 放在 CPU，并禁止任何 CUDA 调用路径。
2. 只跑一条已有授权的 60 秒、含语音的 MP3 slice；`processes=1`、保守 thread cap（建议起点 2–4）、一条请求、硬超时。不要跑完整课程、不要批量，也不需要先决定 HTTP/gateway 拓扑。
3. 记录：加载秒数、wall 秒/RTF、最大 RSS、进程 CPU、实际 `model.device`、线程设置、输入/输出 token、EOS、是否命中 token cap、非空输出及与现有 GPU 同源片段的文本对比。输出不应仅因“有字符串”而算成功。
4. 只有该 probe 成功且资源上限可接受，才用**同一模型、同一线程设置**验证本次实际需要的一个完整 **10 分钟** slice；这就是最小长片验证，用来检验长音频、超时、token cap 与恢复，而不是把短片成绩线性外推。若经 HTTP wire 运行，同时记录 25 MiB inline 限制；若 direct probe 则不把该 wire 限制混为模型失败。
5. 10 分钟 slice 通过后，再按实际产品需求选择 full-course 顺序验证和服务形态；30 分钟 slice 仅在未来确实采用 30 分钟分片时才另行验证，不作为本次前置 gate。

这一步的唯一目的，是把“CPU 可执行”与“可独立完成课程且可接受”分开验证。没有 1.7B CPU 实测前，不应给出完成时间、吞吐、RAM 峰值、质量等数字承诺。

## 资料索引

### 本机源码与记录

- `/mnt/d/Pycharm/VSCODErepos/course-ocr-asr-model-lab/scripts/local_qwen_service_config.py:34-103`
- `/mnt/d/Pycharm/VSCODErepos/course-ocr-asr-model-lab/scripts/local_qwen_model_manager.py:54-301`
- `/mnt/d/Pycharm/VSCODErepos/course-ocr-asr-model-lab/scripts/manage_local_qwen_service.py:24-169`
- `/mnt/d/Pycharm/VSCODErepos/course-ocr-asr-model-lab/scripts/local_qwen_openai_service.py:103-208`
- `/mnt/d/Pycharm/VSCODErepos/course-ocr-asr-model-lab/README.md:27-100,222-233,272-284`
- `/mnt/d/Pycharm/VSCODErepos/course-ocr-asr-model-lab/results/qwen3_asr_summary.json:2-76`
- `/mnt/d/Pycharm/VSCODErepos/QCR powered by LLMs/build/OCRLLM/tools/benchmark_course_recognition.py:100-209`
- `/mnt/d/Pycharm/VSCODErepos/QCR powered by LLMs/build/OCRLLM/src/ocrllm/providers/openai_compatible/build_openai_compatible_audio_request.py:24-91`
- `/mnt/d/Local model runner and investigater/registries/candidates.json:68-78`
- `/mnt/d/Local model runner and investigater/registries/sustained_candidates.json:257-368`
- `/mnt/d/Local model runner and investigater/README.md:94-115`
- `/mnt/d/Local model runner and investigater/src/local_inference_bench/cli.py:11-50`
- `/mnt/d/Local model runner and investigater/src/local_inference_bench/launch_candidate.py:24-97`
- `/mnt/d/Local model runner and investigater/src/local_inference_bench/run_sustained.py:59-100,699-733,755-826,846-930,986-1058`
- `/mnt/d/Local model runner and investigater/src/local_inference_bench/terminate_process_tree.py:1-69`
- `/mnt/d/Local model runner and investigater/workers/qwen3_asr_sustained_worker.py:22-189`
- `/mnt/d/Local model runner and investigater/workers/qwen3_asr_hf_openvino_sustained_worker.py:29-447`
- `/mnt/d/Local model runner and investigater/workers/qwen3_asr_openvino_genai_sustained_worker.py:45-513`
- `/mnt/d/Local model runner and investigater/reports/local-inference-feasibility.md:48-130`
- `/mnt/d/Local model runner and investigater/reports/sustained-quality-and-compatibility.md:158-230`

### 官方一手资料（2026-09-07 查阅）

- [Qwen3-ASR 官方仓库](https://github.com/QwenLM/Qwen3-ASR)
- [Qwen/Qwen3-ASR-1.7B-hf 官方模型卡](https://huggingface.co/Qwen/Qwen3-ASR-1.7B-hf)
- [Qwen toolkit 的 Transformers backend 源码](https://raw.githubusercontent.com/QwenLM/Qwen3-ASR/main/qwen_asr/inference/qwen3_asr.py)
- [Qwen 官方 vLLM serve wrapper](https://raw.githubusercontent.com/QwenLM/Qwen3-ASR/main/qwen_asr/cli/serve.py)
- [Hugging Face Optimum Intel：支持模型](https://huggingface.co/docs/optimum-intel/openvino/models#qwen3-asr)
- [Hugging Face Optimum Intel：OpenVINO export/量化参数](https://huggingface.co/docs/optimum-intel/openvino/export)
- [OpenVINO GenAI 官方仓库](https://github.com/openvinotoolkit/openvino.genai)
