# OCRLLM Architecture

> **Current status**: suspended future plan.
>
> The Rust/PyO3 v3 rewrite below is no longer the active implementation plan.
> It is kept as a future architecture reference only. The active decision is to
> extract a small Python-first library package in `src/ocrllm`, preserve the old
> app under `legacy_app/`, and prove the import contract before moving engines
> or rewriting internals.
>
> Foundational migration rationale: `docs/library_migration_decision.md`.
> Active execution and GO/NO-GO record:
> `docs/ocrllm_library_go_no_go.md`.
>
> None of the PDF engine alternatives, Rust modules, public API freezes, phase
> order, or migration steps below authorize implementation. Active PDF work is
> governed by the execution record and uses PDFium through `pypdfium2` in the
> Python library. PyMuPDF is not an active option. HarmonyOS/ArkTS work is
> deferred.

# Suspended Future Plan: OCRLLM v3

> **策略**: contract-first strangler。先冻结 Python API → Python 跑通首个处理器 →
> golden test 兜底 → 逐个用 Rust 替换引擎。Rust 是实现细节，API 是第一原则。

---

## 0. 项目是什么

OCRLLM 把 PDF 课本、板书截图、录课视频、音频文件转成结构化 Markdown。
核心能力是调用 LLM 视觉模型识别图片中的公式/表格/文字，
调用 ASR 模型转写音频。

v2（当前 `master` 分支）是纯 Python：PyQt5 GUI + CLI + FastAPI，~20000 行。
v3 砍掉 GUI 和设置页，重写为 `pip install ocrllm` 可用的库，核心管线逐步迁入 Rust。

### 为什么重写

v2 的架构骨架是对的——注册表驱动路由、阶段管线、不可变配置——但实现层腐化了：

- `audio.py` 1855 行，一个文件塞了短 ASR、长 filetrans、Google 音频、切片、热词、fallback 等 8 个职责
- `video.py` 1506 行，相似问题
- `_field()` 函数在 `llm_client.py` 和 `google_provider.py` 各复制了一份
- 85 处 `except Exception` 裸捕获，部分静默吞错
- 检查点 JSON 和 MD 文件分两套系统维护，容易出现孤儿数据
- 模型目录的 CRUD 逻辑对百炼/Google/User 三种来源各写了一遍样板代码

v3 的目标不是功能更强，是**结构可持续**——每个文件打开就能理解，改动不会意外炸掉。

### 输入类型

| 类型 | 扩展名 | 处理器 key | 输出 |
|------|--------|-----------|------|
| PDF | `.pdf` | `pdf` | Markdown |
| 板书/截图 | `.jpg .jpeg .png .bmp .webp .heic .heif .tif .tiff` | `board` | Markdown |
| 录课视频 | `.mp4 .avi .mkv .mov .flv .wmv` | `video` | Markdown + 热词表 |
| 音频 | `.wav .mp3 .m4a .aac .flac .ogg .opus .wma` | `audio` | Markdown |
| Office 文档 | `.docx .pptx` | `office` | Markdown |

---

## 1. 架构决策

### 1.1 Contract-first

API 签名先冻结（见第 2 节），引擎后实现。调用方 `import ocrllm` 后不感知
`recognize()` 里面是 Python 还是 Rust。API 签名变更 = breaking change，需慎重。

### 1.2 Strangler pattern

不是"全部重写然后切换"，是"逐个替换引擎"。每替换一个引擎，golden test 必须通过，
确认新旧行为一致才合并。

好处：任何时候断了，当前状态是"部分 Python、部分 Rust，但全部工作"。
没有"迁移期间不可用"的真空期。每次替换的认知范围仅限于**当前模块 + 它依赖的下层 trait 签名**——不需要把整个项目装进脑子。

### 1.3 Board-first

Phase 0 首个可工作的处理器选 board（板书/截图），不是 PDF。

board 的处理器管线最短：图片 resize（纯 CPU）→ VLM HTTP 请求 → Markdown 清理 → 写文件。
不依赖 PDF 渲染器、ffmpeg、ONNX OCR。**零阻塞性外部依赖。**

PDF 被推迟是因为渲染器选择尚未实测验证（pdfium-render 编译、许可确认）。

### 1.4 历史 PDF 渲染设想（已被当前决策取代）

下面的 `pdfium-render` Rust crate 选择只属于被暂停的 Rust 方案。当前
Python 库已经决定使用 `pypdfium2`，并以
`docs/ocrllm_library_go_no_go.md` 的 Phase 3 门槛为准。

暂定 `pdfium-render` crate：BSD 许可，Chrome 同款 PDF 引擎的 Rust binding，预编译二进制。
备选：`mupdf` crate（AGPL 许可风险）、纯 Rust 自研（Type1 字体是硬障碍——Rust 生态无纯 Rust 的 Type1/CFF 解析器）。

`PageRenderer` trait 做依赖反转——PDF 处理器只依赖 trait，不依赖具体渲染器。
换引擎不改处理器代码。PDF 处理器通过依赖注入获得渲染器。

### 1.5 砍掉的功能

社交媒体下载（全体）、DOC/PPT 二进制格式（仅保留 DOCX/PPTX 的 ZIP+XML 解析）、
GUI / 设置页 / FastAPI 服务层 / HTML 处理器。

---

## 2. 历史公共 API 提案（未冻结）

```python
from ocrllm import recognize, recognize_batch, Config, RecognitionResult

# 单文件 —— 自动路由到正确的处理器
result = recognize("board.jpg")
result = recognize("lecture.mp4", config=Config(model="qwen3-vl-plus"))

# 多文件（必须同类型，如多张板书图片有上下文关联）
result = recognize(["img1.jpg", "img2.jpg"])

# 批量混合类型 —— 内部自动按类型分组，分别路由
results = recognize_batch(["a.pdf", "b.jpg", "c.mp4"])

# 配置：不传则全部默认
cfg = Config(
    api_key="sk-xxx",
    model="qwen-vl-max",
    output_dir="./out",
    parallel_requests=8,     # 覆盖默认值 15
)
```

### RecognitionResult

```python
result.markdown      # str      — 主体 Markdown 文本
result.output_path   # Path     — 输出文件路径
result.source_type   # str      — "image" | "pdf" | "video" | "audio"（板书识别用 profile="board" 表示）
result.hotwords      # list[str] — 提取的专业术语热词（仅视频/音频非空）
```

### 异常

| 异常 | 触发条件 |
|------|---------|
| `ocrllm.ConfigError` | API key 缺失或配置字段无效 |
| `ocrllm.QuotaExhausted` | 当前模型免费额度耗尽且回退链全部失败 |
| `ocrllm.UnsupportedFormat` | 文件扩展名无法匹配任何处理器 |
| `ocrllm.Cancelled` | 外部取消信号触发 |

---

## 3. 模块骨架

模块名即职责。读路径就能理解每个文件做什么。

```
src/
├── lib.rs              PyO3 入口 —— Rust ↔ Python 的唯一桥梁
├── error.rs            Error enum (thiserror) —— 整个项目共用这一个错误类型
├── config.rs           Config struct + env 加载 (serde + envy)
│
├── catalog/            模型清单 —— 哪些模型可选、免费额度标记
│   ├── model.rs        数据类型: VisionModel / AudioModel
│   ├── builtin.rs      内置常量 (~22 视觉 + ~9 音频模型，全部经过实测验证)
│   └── cache.rs        快照持久化 (~/.cache/ocrllm/models.json, 自动过期)
│
├── api/                LLM 客户端 —— 纯 reqwest HTTP，不依赖任何 Python SDK
│   ├── provider.rs     LlmProvider trait —— 统一 chat / transcribe / probe 接口
│   ├── dashscope.rs    百炼 / DashScope 实现
│   ├── openai_compat.rs  通用 OpenAI-compatible 实现
│   ├── google.rs       Google Gemini REST 实现（用 Google API 的 REST 端点，非 SDK）
│   ├── retry.rs        重试（指数退避）+ 免费额度回退链
│   └── pool.rs         多 Key 轮转（付费模式）
│
├── imaging/            图像处理 —— 纯函数，无 I/O，无外部进程
│   ├── resize.rs       等比缩放 + JPEG 编码
│   └── ocr.rs          本地 ONNX OCR (ort crate, feature gate, 默认不编译)
│
├── media/              音视频处理 —— 调用外部 ffmpeg 二进制
│   ├── ffmpeg.rs       ffmpeg / ffprobe 查找（遍历环境变量和常见安装路径）
│   ├── audio_split.rs  长音频切片 + fallback 窗口
│   ├── video_frame.rs  视频抽帧 + 变化检测 + pHash 去重
│   └── extract_audio.rs  从视频提取音轨
│
├── pipeline/           处理器 —— 每种输入类型一个处理器
│   ├── processor.rs    Processor trait + ProcessInput / ProcessOutput
│   ├── registry.rs     静态注册表（编译期常量数组，不需要单例锁）
│   ├── board.rs        板书/截图处理器 —— 多图上下文合并去重
│   ├── audio.rs        音频处理器 —— ≤5min 同步 / >5min 异步 filetrans
│   ├── office.rs       DOCX/PPTX 文本抽取（ZIP + XML 解析）
│   ├── pdf.rs          PDF 处理器 —— OCR 模式 / VLM 公式模式双路径
│   └── video/          视频处理器 —— 5 阶段管线，每个阶段独立文件
│       ├── mod.rs
│       ├── phase.rs    VideoPhase trait
│       ├── phase1_audio.rs      音频提取
│       ├── phase2_frames.rs     智能抽帧
│       ├── phase4_llm.rs        LLM 板书识别
│       └── phase5_asr.rs        语音识别
│
├── pdf/                PDF 子系统 —— 独立的渲染抽象
│   ├── mod.rs          PageRenderer trait 定义
│   └── render.rs       pdfium-render 默认实现
│
└── util/               工具 —— 被所有上层模块依赖
    ├── progress.rs     ProgressSink trait + 三种实现（Console / Python回调 / Null）
    ├── writer.rs       槽位 MD 写入器 —— 文件即检查点（见 4.1）
    ├── markdown.rs     Markdown 围栏清理 + 页标记标准化
    ├── checkpoint.rs   断点续传 —— 解析 MD 文件中的槽位状态
    └── board_merge.rs  板书内容去重合并（SequenceMatcher 等价逻辑）
```

Python 侧仅一个文件 `ocrllm/__init__.py`，做 re-export。**零 Python 逻辑代码。**

---

## 4. 关键设计决策

### 4.1 断点续传：MD 文件即检查点

#### v2 的问题

v2 用两套独立系统：`CheckpointManager` 往 `.checkpoints/` 写 JSON 记录完成进度，
`IncrementalMDWriter` 往输出目录写 MD。一旦输出目录被移动/删除，
JSON 变成孤儿数据。v2 代码里甚至有 `_looks_actually_done()` 这个启发式函数
专门清理"MD 已经写完但 JSON 没删掉"的脏检查点——设计本身就脆。

#### v3 方案

MD 输出文件同时是状态存储。初始文件全部槽位填占位符：

```text
<!-- ocrllm:slot 0 status=pending -->
<!-- ocrllm:slot 1 status=pending -->
...
```

槽位完成后替换为 `status=done` + 实际内容。
续传时正则解析 MD 找出所有 `status=pending` 的槽位，只重新处理这些。
不保留独立 JSON 检查点文件。输出目录被移动也不会丢失状态——状态在 MD 文件内部。

#### 并发安全

写槽位前对 MD 文件加独占锁（`fs2::lock_exclusive`，Windows 对应 `LockFileEx`），
先写 `.md.tmp` 再 `rename` 到 `.md`。在写 `.tmp` 时崩溃 → `.md` 保持上次完整状态。
不会出现半个槽位被写坏的文件。

#### 临时文件清理

程序启动时在临时目录下写 `.owner` 标记文件（内容为进程 ID）。
续传时验证：如果 `.owner` 中的进程已死（上次崩溃退出），临时文件可安全删除重建。
如果进程还活着（另一个实例在运行），警告用户。

### 4.2 重试与回退：两层组合

#### 第 1 层——单模型重试

指数退避（1s → 2s → 4s → 8s ... 上限 120s），最多 N 次。
只重试网络错误、HTTP 5xx、空响应。`QuotaExhausted` 不重试——交给第 2 层。

#### 第 2 层——免费额度回退链

模型 A 返回 `QuotaExhausted` → 自动切到模型 B → 模型 C，
直到链表耗尽。链表来自 provider 的 `free_chain` 方法或用户配置的 `model_queue`。

#### 为什么 Rust 更适合这件事

v2 靠 `except Exception` + 字符串匹配 `"AllocationQuota.FreeTierOnly"` 判断额度耗尽。
v3 里 `Error` enum 有 `QuotaExhausted { model: String }` 变体，
模式匹配在编译期保证每个错误路径都被显式处理——不可能出现 v2 的无声吞错。

### 4.3 文件大小约束

每个 `.rs` 文件目标 80–250 行，绝对上限 400 行。
模块顶部 1-2 行注释标注"依赖谁、被谁依赖"。
`#[cfg(test)] mod tests` 与模块同文件。
每个模块只暴露 1–3 个公开类型/函数。

### 4.4 API Key 策略

密钥不进磁盘。来源优先级：
`Config.api_key` 参数 > `DASHSCOPE_API_KEY` env > `OCRLLM_API_KEY` env > `ConfigError`。

### 4.5 依赖方向

```
error ← config ← util ← catalog ← api ← pipeline ← lib.rs
                   util ← imaging / media / pdf
```

下层不能 `use` 上层。`lib.rs` 是唯一聚合点。
`error.rs` 和 `config.rs` 零内部依赖——它们是项目原点，任何模块都可以安全依赖它们。

---

## 5. 预留的 trait（插座）

这些是架构的扩展点。换一个实现，上层代码不受影响。
Rust 编译器在修改 trait 签名时会自动列出所有需要同步修改的地方。

| trait | 定义位置 | 作用 |
|-------|---------|------|
| `LlmProvider` | `api/provider.rs` | 换 LLM 后端（DashScope → Google → 自建）不改处理器 |
| `Processor` | `pipeline/processor.rs` | 新增输入类型不改路由和 PyO3 绑定层 |
| `PageRenderer` | `pdf/mod.rs` | 换 PDF 渲染引擎（pdfium → 自研）不改 PDF 处理器 |
| `ProgressSink` | `util/progress.rs` | CLI 打印 / Python 回调 / 测试 null 三实现可互换 |

---

## 6. 洋葱构建顺序

从零依赖的内核开始，逐层包裹。每层只依赖已完成的下面层。
这是给失忆症设计的——每次只需理解**当前层 + 已完成的下面层 trait 签名**。

```
Layer 0  error.rs                  零内部依赖 —— 项目原点
         config.rs                 依赖 error

Layer 1  catalog/model.rs         纯 struct，无逻辑
         catalog/builtin.rs       常量数组

Layer 2  util/markdown.rs          纯函数，string in → string out
         util/progress.rs          ProgressSink trait 定义（无实现）

Layer 3  util/writer.rs            文件 I/O，依赖 markdown + progress
         media/ffmpeg.rs           子进程调用，跨平台路径查找

Layer 4  imaging/resize.rs         纯函数图像处理
         media/audio_split.rs     依赖 ffmpeg + progress
         media/video_frame.rs     依赖 ffmpeg + imaging

Layer 5  pdf/mod.rs                PageRenderer trait 定义
         pdf/render.rs             pdfium 实现，依赖 imaging

Layer 6  catalog/cache.rs          模型缓存持久化

Layer 7  api/provider.rs           LlmProvider trait 定义
         api/retry.rs              重试 + 回退逻辑

Layer 8  api/dashscope.rs etc.     具体 provider 实现

Layer 9  pipeline/processor.rs     Processor trait + 注册表
         pipeline/board.rs etc.    各处理器——只依赖 trait，互不依赖

Layer 10 lib.rs                    PyO3 绑定，聚合所有层
```

**为什么 Layer 7 写 retry 时不需要知道 ffmpeg 怎么工作**：retry 只依赖 `Error` enum 的模式匹配和 `ProgressSink` trait —— 这两个都是 Layer 0-2 已经完成的。

---

## 7. 历史 Phase 0 —— API 合约 + 首个处理器（不执行）

Phase 0 目标：证明 API 设计可行，端到端链路打通。
**全部用 Python 实现，不写 Rust。** PyO3 spike 在独立分支做编译链验证。

### Done criteria

- [ ] `pip install -e .` 在当前环境成功（`pyproject.toml` + 包结构就位）
- [ ] `import ocrllm` 从任意 cwd 可用
- [ ] API 全部可 import: `Config`, `RecognitionResult`, `recognize`, `recognize_batch`, 4 个异常类
- [ ] `recognize("board.jpg")` 端到端跑通：输入图片 → 调 DashScope VLM → 返回 `RecognitionResult`（markdown 非空、source_type="image"、profile="board"、output_path 指向实际文件）
- [ ] golden test: ≥3 张代表性板书图片（手写/投影/混合），新旧输出 diff 可接受
- [ ] PyO3 spike（独立分支）: Windows wheel 可构建，`_core.pyd` < 30MB，进度回调可被 Python 侧轮询，取消信号可用

### Phase 1+ —— 引擎替换（strangler）

按洋葱层顺序逐个替换。每次替换后 golden test 通过才合并：

```
1. error + config        (Layer 0)
2. util/*                (Layer 2-3)
3. catalog/*             (Layer 1, 6)
4. imaging/*             (Layer 4)
5. media/*               (Layer 4)
6. api/*                 (Layer 7-8)
7. pipeline/board.rs     (Layer 9 —— 首个 Rust 处理器)
8. pipeline/audio.rs → office.rs → pdf.rs → video/
9. lib.rs                (Layer 10, PyO3 绑定)
10. CI + 多平台 wheel
```

每步认知范围：当前模块 + 下面层的 trait 签名。
