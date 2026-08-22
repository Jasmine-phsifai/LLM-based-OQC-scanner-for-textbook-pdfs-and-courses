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
4. 精简轮:非冻结区的超小文件归并(coding rule 1 授权)。
   ~~两个 `recognize_images.py` 同名~~ → 审计后保留(职责/导入明确,不是冲突),见 #005;
   ~~DashScope key 校验重叠~~ → 已统一并修掉环境变量控制字符漏检,见 #005。
   ~~tests/quality 归一化器 v2..v7 重复~~ → 审计后保留(累积协议 + evidence identity),见 #006。
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
8. legacy 日记补录:提交 6b2d9eb(vision fallback + media repair)在
   `legacy_app/AGENTS.md` 无对应日记条目,违反 working-diary 规则,需补。

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
