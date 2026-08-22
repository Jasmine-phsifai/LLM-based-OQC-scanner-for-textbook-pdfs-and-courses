# OCRLLM 架构师循环工作日记(中文)

本文件是 /loop 自驱动架构师循环的连续性骨干。每次循环点火(可能在上下文压缩之后)
**先读本文件**,再读 `docs/ACTIVE_STATE_AND_RULES.md`(全库唯一权威现状,优先级最高),
然后从下方"任务队列"取下一项执行。

## 循环规则(用户钦定)

- 每次循环 = 一个原子任务。开工前先对自己宣告:任务上下文、成功标准、为什么重要。
  实现路径可以自己定;中途因新发现改变主意是允许的,只要朝着"成熟产品"方向走。
- 优先级:① 修已建好的功能 + 精简结构(砍掉不必要代码与过度设计);② 调研/规划一个
  值得移植的 legacy 功能;③ 可持续性与可行性优先,工作量不计;④ 有歧义立刻问
  (问用户或问子代理);探索/写测试/装依赖/小任务派 haiku 子代理,防止主上下文过载;
  ⑤ 代码审查必须亲自做,写代码可以自主决定。
- 既往决定可以被新证据推翻(decisions trigger reconsideration)。
- 每个原子任务完成后:更新本日记 → 同步 `docs/ACTIVE_STATE_AND_RULES.md` 等权威文档
  (文档规则见该文件:单一现状文件、声明必须带验证命令、过期表述要主动标记废弃)→
  git 提交。推送 origin 由用户确认或会话收尾时统一做。
- 付费 live 调用必须先有用户明确预算;密钥从 `HKCU\Software\OCRLLM\QCR\ui` 读,
  永不打印。legacy 侧的观察/修复记入 `legacy_app/AGENTS.md` 日记。

## 任务队列(动态维护,完成即划掉并写明去向)

当前主线:Stage M 收尾(缺陷登记册 G 簇),然后 Stage 2 provider 拆分 → Stage A mp3 音频。

1. ~~集成 stage-m2(M2 槽位断点)~~ → 已完成,见 #001。
2. ~~快修孤立小缺陷 G10/G4/G5~~ → 已完成,见 #002。
3. ~~恢复簇:G1 余项 + G2 + G3 + G8~~ → 已完成离线实现与验证,见 #003;
   provider 账户/模型配额语义仍须任务 5 的付费 live smoke 复核。
4. ~~精简轮:非冻结区的超小文件归并(coding rule 1 授权)~~ → 已完成,见 #005-#008。
   ~~两个 `recognize_images.py` 同名~~ → 审计后保留(职责/导入明确,不是冲突),见 #005;
   ~~DashScope key 校验重叠~~ → 已统一并修掉环境变量控制字符漏检,见 #005。
   ~~tests/quality 归一化器 v2..v7 重复~~ → 审计后保留(累积协议 + evidence identity),见 #006。
   ~~无效的 DashScope 单模型图片上限 resolver~~ → 已删除(永远不可能影响结果),见 #007。
   ~~`output/build_job_state_path.py`~~ → 唯一表达式已并回唯一调用者,见 #008。
   其余小文件已证明是共享/证据/策略边界,不再按行数继续清理。
   注意:contracts/ 与 worker/ 是冻结区,不动。
5. Stage M 出口门收尾:~~全量绿 + import 重量 + 中断实测 + 未知模型可用 +
   候选链配额模拟~~ → 离线出口已完成,见 #004;仅剩一次付费 live smoke(需用户明确预算)。
6. 音频 Stage A 调研(用户已选定方向):legacy `processors/audio.py`(2133 行,
   ffmpeg+OSS+filetrans)、`docs/legacy_filetrans_codex_debug_record.md`、
   Stage 2 拆分范围、时长探针依赖可行性、热词。产出:调研结论 + 更新 Stage A 计划。
   门禁:Stage M 出口 + Stage 2 落地后才许动手实现。
7. 仓库卫生(需用户确认,有破坏性):已合并 worktree(stage-m1/stage-m3)、
   stable_7a5bcf3、_m2_leftover_backup_2026-08-19 的清理;stage-m2 worktree 在合并后
   亦可清理。根目录 social_long_full_batch1_resume*.log 六个遗留日志的处置。
8. ~~legacy 日记补录:提交 6b2d9eb 的 media repair 缺少对应条目~~ → 已完成,见 #009。
   审计纠正了原判断:CLIProxy fallback 在原提交已有日记,Codex discovery 后来也有条目;
   缺口只在媒体修复,且复核时发现真实开放缺陷。
9. ~~legacy video repair 产物边界:manifest 格式崩溃、丢帧假成功、音频中间件误删~~ →
   已按失败优先测试修复,见 #010。
10. legacy repair 发布与身份加固(仍优先于 Stage A):
    ~~为 audio/board/video 引入同目录原子文本发布；取消时先保存本轮已付费成功再传播；
    board 不得吞 `CancelledError`/provider setup~~ → 已完成,见 #011。
    ~~audio 以持久化 source/input SHA-256 + 原始毫秒边界替代 current split 重建~~ →
    已完成,见 #012。
    ~~production short-ASR 在取消/setup failure 前逐段保存，且停止扩大付费请求~~ →
    已完成,见 #013。
    ~~standalone board 以 source SHA-256 + saved batch unit 替代逗号/basename 恢复~~ →
    已完成,见 #014。仍开放:production board 取消/setup 的增量发布，以及 video
    failed-batch/current batch size
    的稳定身份。不要把 Markdown regex repair 移植到 `src/ocrllm`;新库按现有 typed
    sidecar/checkpoint 扩展。
11. 独立 vision provider 语义债:普通 429/5xx 不得借 `FreeTierExhaustedError` 切候选并触发
    “免费额度耗尽”提示；应建立中性 failover disposition 后再修。
12. legacy offline suite 边界:`tests/test_bilibili_api.py` 在 collection 顶层执行真实 Bilibili
    API 与 `curl b23.tv`；#014 广集因该公开网络超时中断。应移为显式 opt-in/script，默认 pytest
    collection 必须零网络。修复后再回到 production board checkpoint。

## 条目格式

每条含:任务、上下文、成功标准、为什么重要、结果(带验证命令输出)、遗留/下一步。

---

## #001 — 2026-08-22:集成 stage-m2 分支(请求内槽位断点续传)

**任务**:审查并集成未合并的 `stage-m2` 分支(0c42706,948 行含 391 行测试)。

**上下文**:该分支是 2026-08-19 会话遗留的未合并工作,实现 M2「每个付费 pass 立即
落盘」:新增 `image_slot_state.py` / `image_slot_checkpoint.py` /
`validate_image_resume_identity.py`;`ImageResumeState` 升为 v2(允许 partial 状态 +
slots 数组);请求身份显式升为 `ocrllm.image-request.v2` 并把 prompt 版本纳入指纹;
v1 旧状态以 `RESUME_STATE_MISMATCH` 明确拒绝(报出两个版本号)。

**成功标准**:逐行人工审查通过;cherry-pick 后冲突只剩文档;m2 新测试与全量套件绿;
import 重量不变;权威文档同步。

**为什么重要**:M2 是 Stage M 计划中价值最高的一项(计划原文),一次性关闭 residual D4、
G6、G7,并部分改善 G1;后续 G 簇修复(G1/G2/G3/G8)都改同一个 `recognize_images.py`
候选循环,必须先落定此基础。

**结果**:

- 审查结论:可直接合并。`run_pass` 闭包统一了「复用或付费并落盘」;槽位绑定
  provider+model,配额 fallback 不会继承失败模型的付费成果;测试覆盖
  kill-mid-request、v1 拒绝、prompt 版本失效、跨模型不串槽——正是出口门要求的
  「中断实测而非目测」。
- cherry-pick 落地为 `cd7429c`;冲突仅 `MIGRATION_STATUS.md`(整文件,取 master 版,
  因 8d0e081 已重构过结构)与 `ACTIVE_STATE_AND_RULES.md` 一处(取 master 现行措辞,
  分支自身的 M2 章节无冲突合入且写得很完整,予以保留)。
- 验证:`pytest tests/test_m2_slot_resume.py tests/test_stage_maturation.py
  tests/test_image_resume.py` → 21 passed;全量 `pytest -q -p no:cacheprovider` →
  **1030 passed**(较 1025 +5,即 m2 新测试),114 秒;import 探针 0.1117s / 122 模块 /
  无重模块,与基线一致。
- 文档:ACTIVE_STATE 登记表更新(D4 残余关闭、G6/G7 关闭、G1 收窄为「配置类失败
  不进台账」)、已验证状态表刷新(1030/114s)、MIGRATION_STATUS 与 START_HERE 同步。

**遗留**:G1 余项转入任务 3 一并处理;`stage-m2` worktree 与备份目录待用户确认后清理
(任务 7)。分支 `response-validation-api-json-md` 同样未合并,尚未评估,列入待办。

---

## #002 — 2026-08-22:快修孤立缺陷 G10 / G4 / G5(先红后绿)

**任务**:关闭 G 簇中仅剩的三个孤立小缺陷,顺手删掉已退役的静态模型集合。

**上下文**:G10=`candidate_models` 条目只拒空串,不执行主模型 `name` 的
trim/控制字符规则;G4=`AllCandidatesExhausted` 继承 `QuotaExhausted`,调用方无法区分
「整链耗尽」与「单模型配额尽」;G5=`model_evidence="proven"` 按静态三模型集合判定,
而 M1 政策规定只有钉住的 v17 基线算 proven,且静态集合仍在 resolve 时绕过目录校验。

**成功标准**:每个缺陷先有一条修前必红的测试;修复后全量绿;登记表三条目关闭;
不产生新的公共面破坏(`AllCandidatesExhausted` 导入路径保持可用)。

**为什么重要**:修完后开放缺陷只剩恢复簇(G1余/G2/G3/G8),它们同根于
recognize_images.py 候选循环,下一次可以一刀切;G5 还顺带完成 M1 的最后一块
(静态集合彻底退役)。

**结果**:

- 先红:新增/改写 9 条测试,修前 8 处失败,正是目标缺陷。
- G10:`vision_model_settings.py` 抽出共享谓词 `_is_exact_model_text`,name 与
  candidate 条目同规则。
- G4:新稳定码 `ALL_CANDIDATES_EXHAUSTED`(不可重试,处置 `("stop","account")`);
  类迁入 `errors.py` 并直接继承 `ProviderError`;删除 11 行 shim 文件
  `all_candidates_exhausted.py`(精简)。
- G5:删除 `SUPPORTED_DASHSCOPE_MODELS`;目录校验改为「除钉住基线外一律过 live 目录」
  (钉住模型的证明是 v17 实门本身,不是目录行——绕过是刻意的,注释写明);
  `model_evidence` 仅钉住模型为 proven;`resolve_dashscope_maximum_images.py` 的
  字典恒返回 10,塌缩为常量 `DASHSCOPE_MAXIMUM_IMAGES_PER_REQUEST`(砍过度设计)。
- 波及处理:6 个既有测试用 `qwen-vl-max`/`qwen3.7-plus` 做 scout/显式模型且依赖旧绕过,
  现按政策 fail-closed;为这些内置路径测试补上目录 mock(顺带消除测试误触真实
  dashscope 端点的隐患——urllib 目录抓取不被 OpenAI mock 拦截)。
- 验证:全量 **1039 passed**(120s);compileall 干净;import 探针 **93ms / 121 模块**
  (删掉 shim 后少一个模块)/ 无重模块。
- flake 记录(未修):`test_recognize_batch_execution.py::
  test_direct_recognition_applies_interval_between_draft_and_review` 在全量负载下
  超时断言失败一次,单跑即过,与本次改动无关(门控时序测试)。按日记规则留痕,
  若再犯应加宽容差或改假时钟。

**遗留**:无。任务 3(恢复簇)为下一刀:G1 余项 + G2 + G3 + G8。

---

## #003 — 2026-08-22:关闭恢复簇 G1 / G2 / G3 / G8

**任务**:接手未完成的恢复簇工作树,修通配置失败零消费台账、按处置推进候选、
model-aware 凭据池阻塞与 scout 失败归属,同时保持错误脱敏和单模型调用的公共错误身份。

**上下文**:交接时有 6 个未提交文件、`4 failed / 107 passed`。已知失败是 injected
provider 的 `failure_scope` 被重映射丢失、配置失败台账泄漏 secret-shaped model、
scout 测试错误期待 pinned 模型。两名轻量只读子代理分别审计 scope 复制与台账脱敏;
主代理逐行审查、实现和验证。

**成功标准**:G1/G2/G3/G8 均有回归测试;只有显式 candidate queue 才自动恢复;
credential 级 permission 不换模型;scout 失败不推进主候选;配置失败记录零调用且不泄密;
全量套件、compileall、import 重量门均通过;权威/导航/计划文档同步。

**为什么重要**:恢复策略直接决定额外付费、错误归属与坏凭据隔离。若候选循环把 scout
或单模型故障误包装为整链耗尽,调用方会采取错误恢复动作;若台账回显未验证配置值,
可观测性本身会成为泄密面。该簇是 Stage 2 provider 拆分前最后一组离线功能缺陷。

**结果**:

- G1:pre-dispatch `ConfigError` 进入 `model_attempts`,处置 `fix_request`,调用数 0;
  `model: null` 表示没有 provider model 被实际尝试,避免回显任意 caller-controlled 文本。
- G2:显式候选链现在仅对 quota、unavailable、model-scoped permission 推进;
  authentication 与 credential-scoped permission 立即停止。新增负向测试证明坏凭据不会被
  换模型掩盖。
- 全量首跑发现 4 个 focused suite 未覆盖的真实回归:无 candidate queue 的
  `PROVIDER_UNAVAILABLE` 被误包为 `ALL_CANDIDATES_EXHAUSTED`,破坏 serial/parallel batch
  错误身份。修为只有 caller 明确提供候选列表才产生整链耗尽;新增单模型回归测试。
- G3:DashScope `AllocationQuota.FreeTierOnly`、`CommodityNotPurchased`、
  `FreeQuotaExceeded` 改为 model scope;pool 测试证明只阻塞当前模型,账户 suspension
  仍阻塞全部模型。**限制**:本轮没有付费 live call;provider 当前是否仍按模型授予这些
  状态只算离线实现假设,任务 5 必须复核,文档不得称 live-proven。
- G8:每个失败 pass 写入实际 `failed_model`;scout 失败进入台账但不推进主候选。
  injected typed error 仅复制 canonical `failure_scope`,其他 details 继续全部丢弃;
  未知 scope 的 secret sentinel 不出现在 message/details/repr。
- 修正 G8 测试自身错误:显式 `candidate_models=("qwen3.7-plus",)` 的首调就是该模型,
  不是 pinned `qwen3.7-plus-2026-05-26`。
- 主审查继续发现一个 G1 边界:固定 scout model 在 primary 已付费后才做目录解析;
  若此时 `ConfigError`,外层原本会误报 0 调用。现于 scout setup 边界保留已付费调用数,
  新测试证明未派发 scout 但台账准确记录 primary 的 1 次调用。
- focused 验证:`132 passed`,修复全量暴露的单模型包装问题后相关集 `143 passed`,
  post-primary scout 单测 `2 passed`。最终全量 `pytest -q -p no:cacheprovider` →
  **1055 passed / 148.36s**;`compileall -q src tests` 干净;最终 5 个
  fresh-process import 探针为 `110/112/107/106/127 ms`,中位数 **110ms**,
  均 121 modules 且 `PIL/openai/httpx/onnxruntime` 不在 `sys.modules`。第一次 import
  命令有 PowerShell 引号错误、第二次有 Python `NameError`,均是探针命令构造错误;
  后续采样有效且重复执行最终门。
- `contracts/`、`worker/` 未改;未运行付费调用。ACTIVE_STATE、START_HERE、
  MIGRATION_STATUS 与当前 Stage M 计划同步为「离线实现完成、live exit gate 开放」。

**遗留/下一步**:任务 5。先做无需付费的 Stage M 出口审计(中断、未知模型、候选链模拟
证据是否足够且命令可复跑),然后向维护者申请明确预算再跑 live smoke。之后才能进入
Stage 2 vision/audio provider split;任务 8 的 legacy 日记缺口仍需独立补录。

---

## #004 — 2026-08-22:把 Stage M 离线出口门变成可复跑的产品门禁

**任务**:审计并补齐 Stage M 所有无需付费的出口证据,把散落在测试和长文档中的手工
命令收敛为一个针对精确 Git 提交的清洁归档门禁。

**上下文**:G1-G10 已离线关闭,但出口声明仍有三处证据不足:未知 provider 模型只测到
resolver、M2 所谓「kill」只是同进程 `ProviderError`、清洁包门是会混用工作树与归档
提交的大段手工 PowerShell。两名轻量只读子代理分别审计行为覆盖与 clean-package
流程;主代理逐项复核后确认缺口成立。`contracts/`、`worker/` 继续冻结。

**成功标准**:操作系统终止进程后已付费槽位仍在且续跑只补缺口;仓库未知但 provider
目录存在的模型走完内置 adapter;一个命令从精确提交重跑全量、fixture、compile、wheel、
外部 import、extras、体积、延迟与离线 smoke;不得发 provider 请求;文档明确区分离线
通过与仍需预算的 live 出口。

**为什么重要**:没有可复跑门禁,「离线完成」会随工作树、已安装依赖和手工命令漂移;
没有真实进程终止测试,最昂贵的断点续传承诺仍只是异常模拟。该门也是 Stage 2 拆 provider
前最后一道防回归边界。

**结果**:

- 新增 `tests/test_m2_process_kill_resume.py`:子进程完成首 draft、进入第二次调用后由父进程
  `terminate`;sidecar 只含首槽且没有最终 Markdown。随后同一 resume identity 续跑仅调用
  provider 2 次,复用标志为 `[True, False, False]`,最终三个槽齐全。
- 新增内置 DashScope 回归:目录返回仓库从未预置的 `provider-new-model-2030`,实际请求与
  result metadata 都保留该模型,证据正确标为 `unproven`。这补的是 adapter 端到端,不是
  重复 resolver 单测。
- 新增 `tools/run_stage_m_offline_gate.ps1`:拒绝 tracked 脏树,归档精确 HEAD,在 GUID 临时目录
  跑全量/fixture/compile/build/install/import-origin/metadata/extras/profile size/smoke,并在
  `finally` 清理。base import 禁止 `PIL/pypdfium2/openai/httpx/onnxruntime/legacy_app`。
- 门禁首跑在 `ded3fa3` 暴露真实性能债:wall 88.23/137.54ms 虽合格,process CPU
  93.75/140.63ms 超过既定 60/100ms。两条路是放宽预算或修 import;选择后者。公共 facade
  改为按首次属性访问懒加载,41 个现有 export、`from ocrllm import ...`、`dir()` 与缓存身份
  均保持。clean-wheel plain import 降到 wall 1.38/2.19ms、CPU 0/15.63ms(中位/p95)。
- 本地最终全量 **1058 passed / 182.12s**,`compileall -q src tests` 干净,fixture 校验像素等价。
  精确提交 `17904ca555573ed92288cbeb910bdfbe6122ce14` 的归档门通过:**1057 passed,
  1 skipped / 167.40s**;skip 是 base profile 未安装 OCR extra 时预期跳过真实 RapidOCR 集成。
  wheel **150,801 bytes**,no-deps target **736,004 bytes**;`image` 增量
  **16,424,666 bytes**,`image,dashscope` **40,997,375 bytes**。两个 Python 环境全部 import
  预算通过,生成 PNG + injected provider 与 DashScope 离线 client 构造通过。
- `git diff a19776d^..HEAD -- contracts worker` 为空;未发任何付费/免费 provider 请求。

**遗留/下一步**:Stage M 只剩需用户明确预算的 live catalog/end-to-end smoke,用于复核当前
账户/模型配额语义;没有预算不得运行。下一轮可先做任务 4 精简审计,也可调查任务 8 的
legacy 日记缺口;Stage 2 实现仍受 live 出口门约束。

---

## #005 — 2026-08-22:统一 DashScope credential 校验,拒绝无证据重命名

**任务**:在 Stage M 离线出口通过后做第一刀非冻结区精简:核实两个 `recognize_images.py`
是否真有职责冲突,并消除 API key 校验的真实重复/漂移。

**上下文**:队列 #4 同时提出文件同名与 `validate_dashscope_api_key` /
`resolve_dashscope_credential` 重叠。两条可选路径是广泛整理 provider 模块,或只修证据证明的
重复。两名轻量只读子代理分别追踪调用图与 credential 语义;主代理复核全部相关源码、测试
和调用点。`contracts/`、`worker/` 冻结,无 live 预算。

**成功标准**:只实施能证明降低歧义或修掉行为不一致的变化;显式、pool、环境变量、catalog
与请求派发共享一套 key policy;缺失与无效错误身份清楚;错误不回显 secret;全量和清洁归档
门通过;无外部 provider 请求。

**为什么重要**:credential 是安全边界。若同一 secret 因来源不同而接受规则不同,配置验证
只是表面安全;反过来,仅因文件同名就重构会制造 Stage 2 前不必要的路径 churn,违背「结构由
观察到的失败证明」的现行原则。

**结果**:

- 同名审计结论是**不改**:`recognize_validated_images.py` 明确导入 processor;
  `resolve_vision_provider.py` 明确动态导入 DashScope adapter;前者负责候选/槽位/prompt/scout/
  metadata,后者只负责一次 SDK 请求与 client/lease 生命周期。测试也全部用完整模块路径。
  没有误导入、重复实现或 patch 错对象证据,重命名收益为零。
- 发现并先红验证真实缺陷:`DASHSCOPE_API_KEY="line1\nline2"` 与含 DEL 的值可直接由 resolver
  返回;带首尾空格的值则被错报为 `CONFIG_MISSING`。新增 3 个参数化回归后修前为
  **3 failed / 5 passed**,与目标缺陷完全一致。
- `validate_dashscope_api_key` 的参数从模糊 `owner` 改为完整 `field_name`;settings、pool
  credential 与环境变量均走该函数。`resolve_dashscope_credential` 只保留来源优先级、pool
  拒绝和真正缺失判断;present-but-malformed 一律返回脱敏的 `CONFIG_INVALID`,None/空串才是
  `CONFIG_MISSING`。catalog 也删除 `settings.api_key or ...` 旁路,统一走 resolver。
- 主审查确认 pool 的 ID/调度/lease 状态职责与 key policy 不重复,不做更大重构。
- focused provider 集 **162 passed / 14.80s**;本地全量 **1060 passed / 163.42s**;
  `compileall -q src tests` 干净;轻量 import **2 passed**。
- 精确提交 `2e9c7706d1fdeb21bc88976a1d49126ec5ab85db` 清洁归档门通过:
  **1059 passed,1 skipped / 121.40s**(预期 RapidOCR extra skip),fixture/compile/wheel/
  outside-import/两种 profile/offline smoke 全绿。wheel **150,795 bytes**,base target
  **736,133 bytes**;`image` / `image,dashscope` 增量 **16,424,795 / 40,997,504 bytes**;
  import wall 中位/p95 为 OCRLLM **1.12/1.70ms**、base Python **0.54/1.14ms**。
- `git diff --name-only -- contracts worker` 为空;未发 provider 请求;用户未跟踪的交接文件未动。
- 顺手修正 `src/ocrllm/AGENTS.md` 的过期导航:不再称 Stage M「部分实现/G 簇开放」,明确为
  离线出口全过、仅付费 live smoke 开放;该改动只消除与权威状态的矛盾。

**遗留/下一步**:精简队列只剩超小文件是否值得归并与 tests/quality v2..v7 归一化器重复
审计。下一轮应先量化重复和历史 gate 依赖;没有实际维护成本证据就不改。Stage M 仍仅剩
需明确预算的 paid live smoke。

---

## #006 — 2026-08-22:否决合并 Phase 1 v2-v7 归一化协议

**任务**:量化 `tests/quality/normalize_recognized_markdown_v2.py` 至 v7 的重复,判断能否在
不改变 v17 与历史 evidence 解释的前提下精简。

**上下文**:队列 #4 把六个版本文件列为疑似重复。两条路径是抽公共 helper/合并版本,或证明
它们是不可随意折叠的版本协议并撤销该重构。两名轻量只读子代理分别做源码差分与 evidence
可达性审计;主代理逐文件复核函数、scorer 调用图、manifest pin 与 v17 JSON code identity。

**成功标准**:明确每版是否仍可达、重复的精确规模、提取 seam 的净收益与语义陷阱;所有
normalizer 单测、历史 evidence 诊断、manifest/scorer 集成与全量套件通过;不改历史 JSON;
没有充分收益则不碰代码并从活跃重构队列划掉。

**为什么重要**:质量归一化器决定「live OCR 输出是否过门」,不是普通文本工具。错误合并会
在测试仍绿时改变历史 evidence 的含义;但若它们真是复制粘贴,继续保留也会让 scorer 漂移。
这里必须用可达性与身份哈希裁决,不能凭文件名数量判断。

**结果**:

- v2 是 **205 行/10 函数**的严格 base parser;v3 仅叠加关系符号排版与行首 Unicode 箭头;
  v4 叠加 Unicode/LaTeX diagram connector;v5 叠加 ASCII `->`;v6 只解开 labeled formula
  内单个 ASCII `\text{}`;v7 再解开单个 ASCII `\mathrm{}`。当前 v7 实际执行链是
  **v7→v6→v5→v4→v3→v2**,六个文件均为运行依赖,不是六份独立实现。
- 可文本提取的重复只有两对: v4/v5 各 5 行 match/prefix/slice helper;v6/v7 共用 5 行
  formula-line regex 与约 8 行替换 helper。提取会新增跨版本 helper 模块,净减少不足以抵消
  coupling;更危险的是 v4 必须在 v3 前处理 connector、v6 必须在 v7 前运行,顺序本身就是协议。
- manifest 固定 `labeled-latex-restricted.v7`;`load_fixture_manifest.py` 还直接用 v6 probe。
  六版各有独立回归测试。历史诊断虽按当前 canonical scorer 重算旧输出,但 v17 evidence 的
  `code_identity.quality.files` 明确逐个记录 v2-v7 路径、字节数与 SHA-256;删文件/改 identity
  不是普通 cleanup,必须另立 scorer-tooling migration 与 differential harness。
- 也否决了「只删 scorer 旧 dialect branch」:canonical manifest 目前选择 v7,但分支是历史
  protocol routing;删分支不会删掉任何模块或当前执行成本(v7 仍传递依赖全部前版),也没有
  观察到的错误或维护负担,不值得为少量行制造半套迁移。
- focused 命令覆盖六版 normalizer、v2/v3/v4/v10 evidence diagnosis、manifest 与 scorer:
  **83 passed / 13.15s**。本地全量 **1060 passed / 106.00s**。没有源码变化,因此不重复
  clean-wheel gate;最新代码 checkpoint 仍是已通过完整门的 `2e9c770`。
- `contracts/`、`worker/` 与未跟踪交接文件均未动;无 provider 请求。

**遗留/下一步**:normalizer 合并从精简队列移除。若未来必须迁移,前置条件是对所有 evidence
Markdown 做逐版本 byte-for-byte 输出/异常/score differential,并保留旧模块 shim 或设计可验证
的 archived identity,不能直接改历史 JSON。队列 #4 只剩「超小文件归并」,下一轮应先量化
非冻结区小文件的调用密度与真实维护成本;无证据继续保留。

---

## #007 — 2026-08-22:删除永远不生效的 DashScope 图片上限层

**任务**:盘点非冻结区超小生产模块,只在调用图、测试与证据身份都证明安全时删除一个真实的
无效 seam,而不是按行数合并文件。

**上下文**:当前精简队列只剩“小文件归并”。两条路径是把纯单调用 helper 并回调用者,或保留
承担独立策略/证据责任的文件并只删不可观察的层。两名只读子代理分别审计调用拓扑与公共面/
测试/evidence 风险;主代理复核全部 24 行以内候选、历史提交与当前限制选择算法。工作树仍只有
用户未跟踪交接文件;`contracts/`、`worker/` 冻结;没有 live 预算。

**成功标准**:候选必须没有公共 export、没有历史 evidence identity、没有独立行为,且删除后
effective limit 数值、`limit_source`、catalog 校验与错误顺序不变;focused、全量、compile 与
clean archive gate 全绿;其余小文件逐类给出保留理由。

**为什么重要**:假装“按模型解析能力”但完全忽略模型的接口会误导下一位维护者,也会让未来
真实差异被塞进错误层。反过来,只因为文件短就合并共享 DTO、平台安全策略或证据协议,会破坏
冷读结构。成熟结构要删除假的扩展点,保留真的边界。

**结果**:

- 删除 `providers/dashscope/resolve_dashscope_maximum_images.py`。它的 `model` 参数从未使用,
  永远返回 10;`resolve_effective_image_limit` 又先插入 `(10, "library_safety")`。Python `min`
  对相同 key 保留首项,所以后插入的 `dashscope_model_capability` 在任何模型下都不可能改变
  限制或对外 `limit_source`。这不是待扩展策略,而是不可观察的重复候选。
- 同步删掉 effective-limit 中 3 个无用 import、DashScope 分支和只验证恒等式的直接单测,
  共净删 32 行。真实 catalog policy 未动:`resolve_vision_provider` 与 DashScope adapter 仍在
  带 settings 的边界调用 `resolve_dashscope_model`;现有 unavailable-model 集成测试继续通过。
- 两个 scout 的首选不同:风险审计偏向内联 8 行 `build_job_state_path`,拓扑审计发现 provider
  cap 是更强候选。主审以“行为是否可达”裁决后先删后者;sidecar 命名仍是持久化约定且当前
  文档明确命名,留作队列中唯一需另行裁决的候选,不在本原子任务顺手扩大范围。
- 其余短文件保留:共享 hard limits/regions、跨解析与渲染的 DTO、冻结 contract 使用的 JSON
  thaw、resume identity、evidence-identified profile/scout/table/image policy、RapidOCR 元数据
  seam 与跨平台 output stem 都有多个消费者、独立风险或历史身份,不能按行数归并。
- 修改前 focused **64 passed / 0.78s**;修改后同范围 **63 passed / 0.77s**(少的一条正是已删除
  resolver 的恒等式测试)。`compileall -q src tests` 干净;本地全量 **1059 passed / 83.58s**。
- 文档合并前的精确源码树 clean archive gate:
  **1058 passed,1 skipped / 82.26s**(base profile 预期 RapidOCR skip),fixture/compile/wheel/
  outside-import/metadata/extras/两种 profile/offline smoke 全绿。wheel **150,217 bytes**,
  base target **734,036 bytes**;`image` / `image,dashscope` 增量 **16,422,639 / 40,995,338
  bytes**;OCRLLM import wall 中位/p95 **0.89/1.98ms**,base Python **0.45/0.86ms**。
- `contracts/`、`worker/`、历史 evidence 与未跟踪交接文件均未动;无 provider 请求。

**遗留/下一步**:队列 #4 只剩 `output/build_job_state_path.py` 是否应按 coding rule 1 内联。
它确实是单调用纯 helper,但也命名稳定 sidecar 约定并被当前执行契约列出;下一轮应在“减少一次
导航”与“保留持久化命名边界”之间单独裁决,不要顺带动其他已证明合理的小文件。若选择保留,
精简队列即可关闭并转入 legacy 日记补录或 Stage A 调研;paid Stage M smoke 仍须明确预算。

---

## #008 — 2026-08-22:内联唯一 sidecar 路径表达式,关闭小文件精简队列

**任务**:裁决并关闭最后一个小文件候选 `output/build_job_state_path.py`:要么证明它是必要的
持久化边界,要么在完全保留 sidecar 兼容性的前提下并回唯一调用者。

**上下文**:该文件 8 行,实际行为只有一条 `Path.with_name` 表达式。保留路径强调命名约定,
内联路径则符合 ACTIVE coding rule 1“纯小 helper 与唯一调用者归组”。两名只读 scout 分别从
当前文档/导出/历史与行为/兼容/测试角度复核;主代理检查调用图、Git 历史、evidence identity、
public facade 与 resume 集成测试。未跟踪交接文件仍属用户;冻结区与 live provider 均不动。

**成功标准**:精确 `<stem>.ocrllm-state.json` 字节命名不变;已有 sidecar 可继续发现;state schema、
request fingerprint、resume version 与输出顺序不变;没有 public/evidence 合约依赖模块路径;
focused/full/compile/clean archive 全绿;当前结构文档不保留幽灵文件名。

**为什么重要**:sidecar 命名是付费工作复用契约,必须稳定;但为一条只用一次的表达式制造模块,
会让冷读者在核心 orchestration 与 leaf helper 间无收益跳转。把“行为合约”与“实现文件存在”
分开,才能既守住兼容性又停止架构碎片化。

**结果**:

- 两个 scout 均建议内联。仓库只有 `recognize.py` 一处生产 import/call;`ocrllm.__all__`、懒导出、
  `output/__init__.py`、public README/START_HERE、测试 patch 与 evidence JSON 均不暴露该模块。
  Git 历史也只有 `f7465db` 创建记录,没有独立演化。
- `recognize.py` 直接执行完全相同的
  `output_path.with_name(f"{output_path.stem}.ocrllm-state.json")`,并在旁注中钉住 durable
  persistence convention。`Path` 本来已导入;删除 leaf import 不增加循环或 import 重量。
- 删除 8 行模块后源码净减 6 行、少一个动态模块加载。接受的唯一风险是未文档化的第三方若
  直接 import 内部路径会断;该路径不是公共 API,保留 deprecated shim 会抵消本轮精简,故不留。
- `docs/ocrllm_library_go_no_go.md` 与 `docs/ocrllm_module_target_design.md` 删除幽灵模块条目,
  但 sibling JSON 命名规则保留。两份 dated resume 记录未改;`MIGRATION_STATUS.md` 与
  `START_HERE.md` 无公共边界变化,无需更新。
- 修改前 focused **7 passed / 0.99s**,修改后同 7 条真实写入/复用/崩溃窗口/进程终止流程
  **7 passed / 0.90s**。`compileall -q src tests` 干净;本地全量 **1059 passed / 86.68s**。
- 文档合并前的精确源码树 clean archive gate:**1058 passed,1 skipped / 87.50s**(base profile
  预期 RapidOCR skip),fixture/compile/wheel/outside-import/metadata/extras/两种 profile/offline
  smoke 全绿。wheel **149,884 bytes**,base target **733,049 bytes**;`image` / `image,dashscope`
  增量 **16,421,593 / 40,994,282 bytes**;OCRLLM import wall 中位/p95 **0.86/1.49ms**,
  base Python **0.44/0.70ms**。
- `contracts/`、`worker/`、历史 evidence 与用户交接文件均未动;没有 provider 请求。

**遗留/下一步**:小文件精简队列关闭;不要继续为减行数重开已证明合理的边界。下一轮优先补
`legacy_app/AGENTS.md` 对提交 `6b2d9eb` 的日记缺口(仓库硬规则),随后进入 Stage A 音频调研;
Stage 2/Stage A 实现仍按当前计划受 Stage M paid live smoke 与 provider split 前置门约束。

---

## #009 — 2026-08-22:恢复 6b2d9eb 媒体修复日记并登记真实开放缺陷

**任务**:重建提交 `6b2d9eb` 的行为、测试与缺陷边界，补齐 `legacy_app/AGENTS.md` 遗漏的
media repair 日记；不把既有 vision/Codex 条目重复包装成新结论。

**上下文**:队列原称该提交的 vision fallback + media repair 全部缺日记。两名只读 scout
分别审查 15 文件 diff 与 changed-test/carry-forward；主代理逐行复核提交、当前 repair 代码、
manifest 写入/读取、清理与 Markdown 发布路径。工作树起始只含用户未跟踪交接文件；冻结区与
provider 均不动。两条路径是写一个笼统“已补录”条目，或按已记录/未记录/已验证/未验证拆分；
选择后者，避免把历史测试绿误写成 repair 质量证明。

**成功标准**:指出原提交中每组变化的既有日记位置；准确描述媒体修复的产品目的；核清直接
测试是否存在；每个已修/仅观察问题均写 carry-forward；权威现状不再声称 legacy 无开放 bug；
相关测试与 compile 通过，文档 diff 干净，提交并推送。

**为什么重要**:失败项修复会再次花费 provider 调用并改写用户唯一的付费成果。如果恢复身份、
原子性和成功判定不可信，“只补失败项”比整项重跑更危险；新库若照搬这种隐式状态，会把
legacy 缺陷穿过迁移边界。

**结果**:

- 纠正队列事实:`6b2d9eb` 自身已写 CLIProxyAPI direct vision 日记；后来条目已覆盖 Codex
  model discovery/Fast mode。真正违反规则的是 audio/board/video repair 与长路径/中间文件
  保留变化没有记录。本轮已在 `legacy_app/AGENTS.md` 用中文补录，且明确不追认成熟度。
- 提交当时的 21/47 测试只覆盖 settings、provider fallback、payload 顺序、Codex 拒识与
  Windows 临时文件；没有任何测试引用 processor repair、GUI `_run_repair` 或新增 long-path
  行为。原 live proxy 图片请求只有 500/502，不存在成功端到端证据。
- 主审确认首要 P1 缺陷:`repair_board()` 直接迭代 manifest，而 writer 保存 `{"items": [...]}`；
  正常产物会在字符串 `items` 上调用 `.get()` 并崩溃。另确认丢帧可漏记后假成功、当前 batch
  size/当前音频切分配置可误定位旧单元、仅音频失败时 cleanup 会删掉修复所需音频、board
  basename 冲突，以及三条 repair 都非原子覆盖 Markdown。
- 还登记 provider 语义债:普通 500/502 为复用候选链被包装成 `FreeTierExhaustedError`，可能
  触发错误的“免费额度耗尽”提示。该问题与媒体 repair 分开，未在文档补录轮顺手改 runtime。
- 第一次从仓库根运行 legacy tests 因 `OCRLLM` 不在 import path 出现 4 个 collection errors；
  改从 `legacy_app` 包根执行后，现存相关集 **26 passed / 3.10s**。这次失败是测试入口边界，
  不是产品回归，已如实保留。随后 `compileall -q OCRLLM tests` 通过。
- `contracts/`、`worker/`、运行时代码与用户交接文件均未动；无网络或付费 provider 请求。

**遗留/下一步**:新发现的已建功能缺陷优先级高于 Stage A 新功能调研。下一轮先为 video
manifest 崩溃、丢帧假成功和 audio cleanup 建立失败测试，再以最小修复恢复可信行为；随后处理
原子发布与稳定 repair identity。`src/ocrllm` 不移植 regex-in-Markdown 方案，而应扩展现有
versioned sidecar、源/request fingerprint、slot/batch checkpoint 与原子写。

---

## #010 — 2026-08-22:修复 legacy video repair 的产物边界

**任务**:让已发布的 video repair 在自己的 manifest、缺失 processed frame 和失败音频 cleanup
边界上可信；先写必红测试，再做最小连贯修复。

**上下文**:#009 证明 `repair_board()` 读不懂 `_save_phase3_manifest()` 的正常产物，还能漏掉
丢失帧后假成功；只有音频分段失败时 cleanup 会删掉后续修复必需的 mp3。两条路径是只修一行
manifest unwrap，或把三者视为同一“恢复所需产物能否定位并诚实报告”边界；选择后者。两名
Luna 只读 scout 分别审查测试 seam 与修复风险，主代理逐行复核实现、调用与既有 cleanup 测试。

**成功标准**:三个回归修前精确失败；正常 writer manifest 可修复且实际发送 processed frame；
一帧可修、一帧丢失时保存成功结果、保留失败 marker 并抛出带缺失 ID 的错误；音频 marker 尚在
时保留 mp3、干净 transcript 仍可清理；本轮不掩盖既有取消/setup 风险；相关集、legacy 广集
与 compile 通过；冻结区、交接文件与 provider 不动。

**为什么重要**:repair 会再次消费 provider 请求并改写用户唯一的付费输出。崩溃、误删恢复输入
或残留失败却返回成功，都会让“只补失败项”失去产品意义，也会把错误范式带入新库音视频切片。

**结果**:

- 新建单一职责测试文件 `tests/test_video_repair.py`。三个测试先以 **3 failed / 2.55s** 精确
  复现:dict manifest 在 `item.get` 崩溃、部分 processed frame 丢失未抛错、失败 transcript
  的 mp3 被 cleanup 删除。首个测试随后改为直接调用生产 `_save_phase3_manifest()` 造 fixture，
  避免测试手抄 schema 后与 writer 再次漂移。
- `repair_board()` 按 `{"items": [...]}` 解包，校验 outer/items/item/path 类型，对 corrupt JSON
  记录 warning；没有映射才退回原 frame，manifest 明确给出的缺失 processed path 则登记稳定
  frame ID。可用帧仍完成识别和替换，unavailable/provider-failed ID 合并进入 `still_failed`，
  因此 partial success 会落盘后抛错，不再假成功。另以 set 替代循环中的 O(n²) 临时列表查重。
- cleanup 懒导入并复用 `AudioProcessor.find_failed_segments()`，只保留修复所需 mp3；没有复制
  marker regex，也没有像板书失败路径那样提前 return 并泄漏所有其他可重建中间件。既有 clean
  transcript cleanup 测试继续证明 mp3 可正常删除。
- 修后 `test_video_repair.py + test_resume_chain.py` 为 **22 passed / 1.62s**；video/audio/cleanup
  六文件相关集 **73 passed / 36.37s**；排除真实 ffmpeg `test_social_e2e.py` 的 legacy 广集
  **235 passed, 1 skipped / 51.00s**，唯一 skip 是明确的 live Google model discovery。
  `compileall -q OCRLLM tests` 与 `git diff --check` 通过。
- scout 建议整体复用 `_load_phase3_processed_paths()`，主审否决:该 loader 对任一缺失项全量返回
  `None`，会丢失 repair 必需的逐帧 partial accounting。保留局部严格 parser 是更小、更诚实的
  行为差异，不新增抽象层。
- `contracts/`、`worker/`、用户未跟踪交接文件均未动；没有网络、provider 或付费调用。

**遗留/下一步**:本轮只关闭任务 9 的三个已证明缺陷。failed batch/current batch-size、audio
current split、board basename 仍没有稳定身份；三条 repair 仍非原子写。新观察到 audio/video
取消会丢掉本轮已成功结果，board 还会吞 `CancelledError`。下一轮优先用失败测试定义“成功即
原子发布、取消仍可见”的跨 repair 契约，再决定共用 writer 的最小位置；Stage A 调研继续后移。

## #011 — 2026-08-22:让 legacy media repair 原子保存成功并诚实传播取消

**任务**:让 audio、board、video repair 在每次付费成功后立即原子发布；后续取消仍抛
`CancelledError`，不能丢掉先前成功；setup error 不得降格成普通识别失败。

**上下文**:#010 关闭 video 的 manifest/缺失产物/cleanup 边界后，逐行复核发现三个 repair
都在整个循环结束后才 `write_text()`。两名 Luna 只读 scout 分别审查跨 processor 的取消控制流
和最小原子 writer 契约，主代理复核所有 marker 结构、失败传播测试与实现。考虑过两条路径：
①复用 `IncrementalMDWriter` 或抽出共享 marker finalizer；②只共享文件提交原语，各 modality 保留
自己的替换规则。选择②，因为 writer 的 append/slot 语义不匹配，三个 marker 又确实不同；统一
它们会把 legacy 隐式状态固化成错误抽象。

**成功标准**:先以确定性测试复现三个取消路径和 audio/board setup 误分类；一个共享 writer
保证编码、fsync、replace 失败均不破坏旧文件；每个成功单元在下一可取消操作前落盘；既有普通
partial-failure 与 resume 契约不变；focused、legacy 广集、编译和 diff 检查全绿。

**为什么重要**:repair 的价值就是避免重复付费。进程取消或文件替换失败若能抹掉已经成功的
重试，产品会在最需要恢复时失信。新库以后也需要区分“原子文件发布”“稳定恢复身份”和“并发
协调”，不能用一个看似方便的 writer 掩盖三种不同责任。

**结果**:

- 新增 `core/write_text_atomically.py`，只负责同目录唯一临时文件、UTF-8/LF、flush + fsync、
  `os.replace()` 与失败清理。单元测试证明精确 UTF-8 无 BOM；编码、fsync、replace 任一失败均
  原样传播、保留旧输出且无临时残留。
- audio/board/video 都在单元成功后先用 `subn(..., count=1)` 验证恰好命中一个失败 marker，
  再原子发布，最后登记成功并进入下一轮。marker 漂移成为显式错误，不再静默“成功但没替换”。
- board 显式 re-raise `CancelledError` 和 provider setup error；audio 补齐 setup error 传播；
  video 保留原有异常分类，并能把 failed-batch placeholder 展开成“已成功帧 + 其余显式失败帧”，
  所以后续取消仍保有精确 partial accounting。
- 修前 repair 直接集为 **5 failed, 3 passed / 2.09s**。修后 writer + repair 直接集
  **12 passed / 5.78s**；含 resume/failure propagation 的 focused 集 **43 passed / 22.41s**；排除真实
  ffmpeg `test_social_e2e.py` 的 legacy 广集 **244 passed, 1 skipped / 65.93s**，唯一 skip 为
  显式 live Google model discovery。四个修改模块 `py_compile` 通过；无网络/provider/付费调用。
- 主审采纳 scout 的共享边界，但没有顺手迁移 `pdf.py`、checkpoint 或 incremental writer；这些
  路径的状态/吞错契约不同，应分别失败优先。`contracts/`、`worker/` 和用户未跟踪交接文件未动。

**遗留/下一步**:任务 10 只剩稳定身份：audio 不能按当前切分重建旧 segment，board 不能靠
batch index + basename，video 不能按当前 batch size 解释历史失败。下一轮先定义持久化
source/request/unit identity 及向后兼容边界；不把 Markdown regex 移入 `src/ocrllm`。另记录但
不混做：legacy PDF/checkpoint/incremental writer 的旧原子性和吞错策略需要各自契约测试；同一
输出上的并发 repair 仍需调用层协调，唯一临时文件只防碰撞，不防最后写者覆盖。

## #012 — 2026-08-22:用版本化身份阻止 audio repair 修错分段

**任务**:让 legacy short-ASR 输出保存可验证的源身份和原始分段边界；repair 不再按当前配置
重新切音频，缺失/损坏/漂移身份时必须在 provider 调用前失败。

**上下文**:#011 只保证成功内容不被破坏，却不能证明“分段 2”今天仍指向昨天的同一段音频。
原实现重新执行 `_should_use_short_asr()` + `_split_audio()`，配置缩短后可把原本整段的失败项变成
开头局部。两名 Luna 只读 scout 分别审查 schema/原子性/兼容政策和失败测试 seam；主代理复核
short/Google/filetrans 三条路径、GUI 错误呈现和 ffmpeg 参数。考虑两条路径：①把更多机器状态写进
Markdown；②使用邻接 versioned sidecar。选择②，避免继续把本地化展示文本升级成恢复数据库。

**成功标准**:配置漂移测试证明 current split 不再被调用；源文件即使同路径也按 SHA-256 拒绝
字节漂移；missing/corrupt/unsupported manifest 都在零 provider 调用时显式失败；生产 `_short_asr`
确实写出 exact-ms windows；ffmpeg 使用保存的 `-ss/-t`；旧输出安全拒绝且 GUI 显示真实原因。

**为什么重要**:原子写只能保证文件完整，不能保证付费请求对应正确内容。错修一个时间区间会把
“恢复”变成静默数据污染；比明确要求旧输出重跑更坏。新库音频切片也必须把 source、request、
unit identity 分层，而不是把序号当身份。

**结果**:

- 新增单一职责 `processors/audio_repair_manifest.py`。v1 sidecar 保存 source 与实际 ASR input
  的 size + SHA-256、input duration、splitter/fallback 参数、原始 model/prompt/hotwords 哈希，
  以及每个 unit 的 actual/logical 毫秒边界和由 input hash + 边界生成的稳定 ID。writer 复用
  #011 的同目录 atomic replace，并对深文件名使用短化 sidecar 名。
- loader 严格验证 schema/version、哈希、连续完整的逻辑窗口、上下文包络、稳定 ID 和 Markdown
  `meta:segment` 映射。旧版无 sidecar、损坏/未知版本、源或转换后输入漂移、展示映射漂移一律在
  provider 前失败；不提供隐式 unsafe fallback。
- `repair()` 只选择 manifest 中失败 index 对应的 stable unit；完整单元直接复用已验证输入，局部
  单元按保存的 actual window 生成 `ffmpeg -ss/-t`，完全不读取当前 chunk/context 设置。
  `_short_asr()` 把 Markdown 与 manifest 都原子发布；原始 request 字段用于审计，不阻止用户用
  新模型/提示词修复。`AudioRepairIdentityError` 不继承普通识别 `RuntimeError`，因此现有
  audio/video GUI generic error 汇总会保留其原文，不会降格成“全部分段失败”。
- 三个核心回归修前为 **3 failed, 2 passed / 3.64s**。修后 identity/生产 writer/边界提取直接集
  **11 passed / 1.22s**；最终 audio/video/resume/failure/GUI focused 集
  **112 passed / 34.12s**；排除真实 ffmpeg `test_social_e2e.py` 的 legacy 全量
  **253 passed, 1 skipped / 44.40s**，唯一 skip 为显式 live Google discovery。相关 Python 模块
  `py_compile` 与 `git diff --check` 通过；无网络/provider/付费调用。
- 主审没有照搬 scout 的“当前请求必须与原 prompt/model 相同”：repair 的产品用途本就包含改进
  prompt/model，真正不可变的是源字节与时间单元。也没有在本轮加入并发锁或永久 chunk cache；
  当前 GUI 单任务，且已验证源可按 exact window 免费重建，这两项尚无失败案例支撑结构增长。

**遗留/下一步**:任务 10 仍需处理 board 的 basename/逗号解析与 batch identity，以及 video
failed-batch 按 current batch size 重建。逐行主审另发现 `_short_asr()` 生产循环若某并行 future
抛 `CancelledError`，会在最终 Markdown/manifest 发布前丢掉其他已付费成功结果；已登记 legacy
日记，下一轮应优先以失败测试定义 production cancellation checkpoint，而不是误写成已由 repair
原子性覆盖。Stage A 调研继续后移。

## #013 — 2026-08-22:让 production short-ASR 逐段落盘并限制取消后的付费扩散

**任务**:让 legacy `_short_asr()` 在每个并行分段完成时原子保存；取消或 provider setup failure
停止新提交，保留已付费成功后再传播，不再等全批结束才首次发布。

**上下文**:#012 已让 repair 拥有稳定 source/request/unit identity，但生产识别仍一次提交全部
future，并把结果留在内存。任一 future 取消会越过最终 Markdown/manifest 写入，既丢已付费成功，
也没有可供 repair 接手的初始状态。两名 Luna scout 分别审查取消契约和测试 seam，主代理逐行
复核 executor、reporter、manifest 与 atomic writer。比较两条路径：①修改 `BaseProcessor` 的通用
future iterator；②在 short-ASR 内实现有界 rolling drain。选择②，因为通用 iterator 会在取消时
立即抛出并丢弃已完成 future，而“先发布再传播”是本流程特有的付费恢复契约。

**成功标准**:provider 前已有 manifest + 全未完成 Markdown；乱序完成可观察到中间原子快照；
取消保留已成功分段并传播；取消/setup failure 后不再提交新分段，但排空已经运行的有界窗口；
普通识别错误仍写失败 marker；focused、legacy 广集、编译和 diff 检查全绿。

**为什么重要**:repair 只有在生产阶段先留下稳定且持续更新的断点才真正可用。无限预提交会在
用户取消后继续扩大成本，而立即抛取消又会丢弃已经产生费用的成功；成熟产品必须同时限制
推测工作和保存不可逆成果。

**结果**:

- 三条核心测试先以 **3 failed / 4.15s** 复现：取消后无输出、乱序成功没有中间快照、首次
  provider dispatch 时没有 repairable checkpoint。随后补齐单 worker 的 reporter cancellation
  与 setup failure 测试，证明后续分段没有被提交。
- `_short_asr()` 在创建 executor 前先原子写 v1 repair manifest 和完整未完成 Markdown。
  coordinator 只维持不超过 worker 数的 rolling window，直接使用 `wait(FIRST_COMPLETED)` 消费
  乱序结果；每个成功或普通失败落入固定 slot 后重建并原子发布完整文档。
- 取消或 setup failure 成为 terminal condition：停止补充窗口、取消未启动 future、继续排空
  已运行 future 并发布其中成功，最后传播原异常；若两者同时出现，用户取消优先。没有改动
  `BaseProcessor`，也没有新增跨 modality executor 抽象。
- 因果 Event 测试避免依赖 sleep：后续取消只有在第一段已真正发布后才释放，首段也只有在
  “第二段已发布、第一段未完成”的快照出现后才释放。checkpoint + audio repair 集
  **16 passed / 2.34s**；排除真实 ffmpeg `test_social_e2e.py` 的 legacy 全量
  **258 passed, 1 skipped / 62.02s**，唯一 skip 是显式 live Google discovery。
  两个修改 Python 文件 `py_compile`、`git diff --check` 通过；无网络/provider/付费调用。
- 主审确认只有 coordinator 写输出，worker 只返回 `(index, text)`；最大未决付费调用受 worker
  配置约束。`contracts/`、`worker/` 与用户未跟踪交接文件未动。

**遗留/下一步**:任务 10 只剩 board 的 basename/逗号 marker 与 batch identity，以及 video
failed-batch 按 current batch size 重建。下一轮优先为 board 建立稳定身份失败测试；若调查证明
两种 modality 需要不同 schema，则分别做小型 sidecar，不抽象出未经证明的通用媒体恢复框架。
Stage A 调研继续后移。

## #014 — 2026-08-23:用源字节与稳定 batch unit 阻止 board repair 修错图片

**任务**:让 standalone `BoardProcessor` 在 provider 前保存版本化 source/batch identity；repair
不再从本地化 marker 按逗号拆文件名或用 basename 字典猜图片，缺失/损坏/漂移时零调用失败。

**上下文**:#013 后任务队列写着“board current batch reconstruction”，但主审代码后修正前提：
standalone board repair 实际从 marker 取名字，不读取当前 batch size；current batch drift 属于 video。
已证明的 board 缺陷是含逗号文件名被拆开、不同目录同 basename 后者覆盖前者、同路径换字节仍
付费重试。两名 Luna scout 分别审查 schema 和测试 seam；比较过把身份塞入 Markdown 与邻接
sidecar，选择后者，避免继续把本地化展示文本当恢复数据库，也不抽象未经证明的通用 media schema。

**成功标准**:生产首次 dispatch 前已有可解析 sidecar；重命名但字节相同可按身份解析；逗号和
重复 basename 不会误选；source drift、missing/corrupt manifest、Markdown unit drift 都在零
provider 调用时失败；旧本地化输出不做 unsafe fallback；focused、legacy 广集、编译与 diff 全绿。

**为什么重要**:repair 会再次消费 provider 请求。按名字猜错图片会产生语法完全有效但内容属于
另一张图的 Markdown，是比显式失败更危险的静默污染；稳定 batch identity 也是未来新库图像批次
恢复不可缺少的边界。

**结果**:

- 六条回归先以 **6 failed / 12.34s** 精确复现：provider 前无身份、逗号+rename 无法恢复、
  duplicate basename 选择最后一项、source drift 仍调用、missing/corrupt sidecar 仍调用。
  后续补充 Markdown unit 漂移测试，第一次运行又发现 malformed marker 会被“没有失败”提前返回，
  现已要求存在 stable metadata 时先完整验证 manifest/Markdown 再下结论。
- 新增单一职责 `processors/board_repair_manifest.py`。v1 sidecar 保存按生产 mtime 顺序确定后的
  每张原图 size/SHA-256、稳定 item ID、精确 batch membership/unit ID、原 batch size、prompt hash
  与 skip-preprocess 审计值；长输出路径沿用短名 + path digest 策略，写入复用 atomic writer。
- Markdown 每批都有 `meta:board-batch index/unit/status`；人类可读失败注释继续保留“批次 N
  识别失败”，但 repair 只按 manifest unit 精确替换。loader 严格验证 schema/version、连续索引、
  哈希、完整有序 batch 覆盖、unit 重算、Markdown 映射和 supplied source 多重集。
- repair 用 `(size, SHA-256)` bucket 消费 supplied paths：同字节 rename 安全，重复 basename 不再
  冲突，额外/缺失/漂移输入全部拒绝。source bytes + batch membership 是不可变 unit；prompt/model/
  preprocessing 是允许改进的 repair attempt，不把某次 crop/resize 输出错误冻结成永久身份。
- 首轮 focused 暴露两个旧测试仍手写无 sidecar marker，以及人类可读错误断言需要兼容；测试改为
  使用生产 manifest renderer，显示文字保留。最终 identity/repair/failure set
  **22 passed / 27.71s**；真正 offline 的 legacy 广集（排除真实 ffmpeg `test_social_e2e.py` 与
  import-time live `test_bilibili_api.py`）为 **266 passed, 1 skipped / 50.74s**，唯一 skip 是显式
  live Google discovery。四个 Python 文件 `py_compile` 与 `git diff --check` 通过；无 provider/
  付费调用。
- 不隐藏一次验证失败：只排除 social e2e 的广集在 collection `test_bilibili_api.py` 时真实请求
  `b23.tv`，15 秒后抛 `subprocess.TimeoutExpired`，结果为 **1 collection error / 20.94s**。这是测试
  文件顶层执行网络诊断的既有缺陷，不是 board 回归；本轮没有继续联网重试，已加入队列 #12。
- 主审没有采纳“缺少旧 sidecar 时按 basename best effort”或把 audio/board 合并为通用 manifest；
  前者继续静默误修，后者会把时间窗口与图片集合两种不同 unit 强塞进过早抽象。`contracts/`、
  `worker/` 与用户未跟踪交接文件未动。

**遗留/下一步**:下一轮先关闭队列 #12，使默认 offline pytest collection 不再隐式联网。随后处理
production `BoardProcessor.process()`：它仍把所有 `md_parts` 留到循环结束，
且 broad `except Exception` 会吞 provider 内的 `CancelledError`/setup failure；下一次 `_check_cancelled`
可越过最终写入，丢掉前面已付费成功。这比 video identity 更直接影响生产成果，应随后用失败测试
定义“initial skeleton + 每批原子发布 + terminal error 传播”；随后再修 video historical batch size。
并发同一输出仍是 last-writer-wins，另立 revision/CAS 证据前不加锁。
