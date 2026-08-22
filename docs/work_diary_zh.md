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
- 2026-08-23 用户追加:Google image/audio API 是免费且直接授权的 robustness test source,
  无需逐次预算确认；实时拉模型，预期会遇到窗口额度、繁忙、API error、空回复、不支持格式、
  图片过多。调用仍须有界、不得泄密。social media 功能延后。
- legacy 是新库的行为父级。真实发生过的 legacy bug 比代码猜测更值得警惕，但不能直接假定
  child 同样有 bug；先证明对应路径存在，再加最小回归。防御代码的未来可读性也是可持续性成本，
  不得把 child 做得比 legacy 产品更宽。

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
    已完成,见 #014。~~production board 取消/setup 的增量发布~~ → 已完成,见 #016。
    ~~video failed-batch/current batch size 的错误重建~~ → 已删除错误重建并改为生产阶段逐帧标记,见 #017。
    不要把 Markdown regex repair 移植到 `src/ocrllm`;新库按现有 typed
    sidecar/checkpoint 扩展。
11. ~~独立 vision provider 语义债:普通 429/5xx 不得借 `FreeTierExhaustedError` 切候选并触发
    “免费额度耗尽”提示~~ → 已保留显式 opt-in 切候选，但改用中性内部信号并保留原异常，见 #018。
12. ~~legacy offline suite 边界:`tests/test_bilibili_api.py` 在 collection 顶层执行真实 Bilibili
    API 与 `curl b23.tv`~~ → 已改为 guarded manual diagnostic，并用 import-safety regression 保证
    默认 collection 零网络/零 subprocess，见 #043；没有恢复 social product 开发。
13. ~~Google JSON 错误分类顺序~~ → 已完成并纠正原假设，见 #019。Google 已有证据是
    `You exceeded your current quota ... check your plan and billing details`；此前 JSON 路径实际误判为
    `BILLING`，不是 `RATE_LIMIT`。`FreeTierOnly` / `FreeAllocationQuotaExceeded` 属于 DashScope，
    未加入 Google contract；普通 429 及带限流标记的 `RESOURCE_EXHAUSTED` 仍按限流重试。
14. ~~active image 输出/恢复状态的 Windows 临时路径放大~~ → 已改为固定短名的同目录临时文件，
    并用两条独立的 UTF-16 路径边界回归验证，见 #020。这里只消除库自己追加长后缀造成的失败，
    不承诺任意深目录或通用 `\\?\` long-path 支持。
15. ~~automatic checkpoint 的非法 sidecar 目标延迟到 provider 之后才失败~~ → 已在非 resume 路径
    增加零写入的 regular-file preflight，保留 resume 原有错误类型，见 #021。
16. ~~active 同目标并发事务竞态~~ → 已用进程内 nonblocking target claim 覆盖所有 file-producing
    recognition，从首次 checkpoint 前持有到结果构建后；稳定与 identity-less loser 均有回归，见 #022。
    跨进程同目标协调不在当前承诺内，未引入持久 lock file 或 stale-owner 协议。
17. ~~Google image provider 最小迁移边界~~ → 已完成只读代码/测试/依赖审计，见 #023。结论是先完成
    Stage 2 provider/modality split，再接入窄 Google image adapter；不得提前扩展旧的单 provider 配置，
    也不得复制 legacy 内部重试、模型切换、audio/Files API、GUI 或 social 结构。该计划不阻塞 Stage A。
18. ~~active candidate recovery 忽略 failure scope~~ → 已要求 quota/unavailable/permission 三类错误都必须
    明确为 model scope 才能切候选；account quota 与 provider outage 保留原错误并停止，链耗尽也不再继承
    最后一个模型的 scope，见 #024。
19. ~~automatic checkpoint 用类名冒充内置 provider 身份~~ → 已改为精确 `DashScopeSettings` 类型判断；
    同名 injected provider 在普通文件输出模式正常执行且不生成 sidecar，见 #025。

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

## #015 — 2026-08-23:记录 Google 直接测试授权与 legacy-parent 证据规则

**任务**:把用户新授权写成英文 repo memory：Google image/audio 可直接用于免费 robustness 测试；
实时拉模型；把常见不稳定行为当错误处理证据；同时记录 legacy 真实 bug 只提高警惕、不自动证明
新库继承，以及 Windows 超 260 字符路径的真实历史。

**上下文**:用户在暂停后纠正两种可能偏差。第一，Google 的经常出错不是避用理由，而是测试
稳定性、错误分类和空结果处理的理想来源。第二，防御编程不能靠“legacy 曾有 bug”就给 child
预装更强更宽的机制；真实 incident 是高权重参考，仍须先证明 child 有对应路径。比较两条记录
路径：另建新 decision 文档，或更新 root `AGENTS.md` + 既有 provider policy + 权威现状；选择后者，
减少未来查找成本。已有 long-path 细节继续链接 `legacy_app/AGENTS.md`，不复制整段历史。

**成功标准**:英文权威规则明确 Google 无需逐次预算、live catalog、image/audio 差异和已知错误；
明确隐私/有界调用；明确 social 延后；明确 legacy parent 的“先验证再防御”和不扩产品范围原则；
引用 Windows >260 真实记录；文档无冲突、diff 干净、提交推送。

**为什么重要**:API 测试权限和 bug 证据权重如果只留在聊天里，下一代理会重复询问、避开最有价值
的错误源，或反过来依据旧 bug 过度建设。把授权、边界和理解成本放在同一规则里，能同时提高
鲁棒性和可维护性。

**结果**:

- root `AGENTS.md` 新增 Provider Test Authority 与 Legacy Parent Evidence Rule；Google 测试不需
  单独预算，模型必须实时发现，audio 支持较窄；列出窗口额度、繁忙、API error、空回复、格式和
  图片数限制，同时保留有界调用、凭据与测试数据隐私边界。
- `docs/provider_cost_and_reliability_policy.md` 更新用户账号事实与授权，不把授权误写成新 adapter
  已启用；`docs/ACTIVE_STATE_AND_RULES.md` 增加“legacy evidence 不是继承证明”“下一代理理解成本
  是设计成本”，并链接既有 2026-08-18 Windows long-path incident。
- social media 明确延后，队列 #12 不再抢占 production board 等非社交产品缺陷。没有新增 feature、
  schema、测试框架或代码路径；没有 API 调用。

**遗留/下一步**:恢复后的下一原子任务回到 production board 已证明的取消/setup 丢成果问题。
实现前先检查 #014 新增的 manifest helper 是否能直接承担 initial skeleton/slot render；若需要新增
抽象，必须先有重复失败证据，不能把 board 改造成比 legacy 产品更宽的通用任务系统。

## #016 — 2026-08-23:production board 逐批原子保存并传播终止错误

**任务**:让 `BoardProcessor.process()` 在首次 provider 调用前留下可修复 Markdown，并在每批完成后
立即原子保存；后续取消或 provider setup failure 必须原样传播，不能吞掉前面已付费成功。

**上下文**:#014 已建立稳定 source/batch sidecar，但生产循环仍把 `md_parts` 全留在内存，直到所有
批次结束才首次写 Markdown；同一层 `except Exception` 还会把 `CancelledError` 和 setup failure
降格成普通识别失败。比较两条路径：①给 marker schema 增加 `unfinished` 第三状态；②复用现有
`failed` slot，以“任务未完成”说明尚未结算。选择②，因为现有 repair 已能安全重试 failed slot，新增
状态只会扩大 parser/schema 与未来代理的理解成本。一个只读 Luna scout 独立复核测试 seam，结论一致；
主代理逐行复核生产循环、manifest renderer、atomic writer 与既有普通 timeout 回归。

**成功标准**:首次 provider dispatch 前同时存在 sidecar 与完整可修复 Markdown；每个成功/普通失败
批次落入固定 slot 后立即原子发布；reporter cancellation、provider cancellation、setup failure 都
传播并保留先前成功；普通 timeout 仍写部分结果后抛错；focused、legacy 离线广集、编译与 diff 全绿。

**为什么重要**:board 请求可能已经产生费用或不可重复的结果。若只在循环末尾保存，用户取消一次就会
丢掉所有先前成果；但为此引入通用任务框架或新 schema 会超出 legacy 行为边界。复用现有稳定身份和
原子 writer，能直接关闭真实缺陷，同时保持代码可从文件和局部函数冷读理解。

**结果**:

- 四条直接回归先以 **4 failed / 6.49s** 复现：首次调用无 Markdown skeleton、reporter 取消后
  首批输出文件不存在、provider cancellation/setup 被吞并改抛普通质量错误。第一次 focused 修后运行
  暴露测试 observer 会在第二次调用把已见证的 `True` 覆盖为 `False`；修正为锁存证据后生产代码无需
  调整。另一次从仓库根运行新 legacy 测试因缺少 legacy import path 在 collection 失败，改从
  `legacy_app` 正确运行；这两项均如实保留，不算产品回归。
- manifest 保存后立即建立与 batch 数相同的固定 `md_parts`，每项使用既有 stable failed marker 和
  “任务未完成”；局部 `publish_current_batches()` 只复用同目录 atomic writer，没有新增文件、状态或
  通用 executor。成功结果在 `_report_content` 前落槽并发布；普通异常落失败槽并发布。
- `CancelledError` 直接传播；其他异常先用既有 `is_provider_setup_error()` 检查并传播 setup failure。
  终止错误发生时当前及后续“任务未完成”slot 保持可由现有 repair 接手，先前成功不丢。普通 timeout
  契约由既有 `test_failure_propagation.py` 继续覆盖，没有重复测试。
- board checkpoint/identity/repair/failure focused 集 **26 passed / 25.46s**；排除真实 ffmpeg
  `test_social_e2e.py` 与已延期的 import-time Bilibili diagnostic 后，legacy 离线广集
  **270 passed, 1 skipped / 87.96s**，唯一 skip 仍是显式 live Google discovery。两个修改 Python
  文件 `py_compile`、`git diff --check` 通过；无网络、provider、付费调用，未动 `src/ocrllm`、
  `contracts/`、`worker/` 或 social media。

**遗留/下一步**:media repair 耐久性队列只剩 video failed-batch 仍按当前 batch size 解释历史失败。
下一轮先用失败测试证明具体误修路径，再决定是否做 video 专用 sidecar；不要把 audio/board schema
强行抽成通用 media framework。Stage A 调研继续后移。

## #017 — 2026-08-23:删除 video repair 的 current-batch 错误重建

**任务**:证明并修复历史 `批次 N 失败` 被当前 video batch size 重新解释的问题；保证新失败输出直接
携带精确帧身份，旧的含糊输出在零 provider 调用时失败，同时减少而不是扩展 repair 结构。

**上下文**:#016 后 media repair 队列只剩 video。生产 `_phase4_batch_one()` 遇到普通异常时只有一个
本地化 batch index；`repair_board()` 再用当前 `_phase4_batch_size()` 对 `frame_info.json` 重新分组。
最初比较在 Phase 3 manifest 加字段、另建 video sidecar、扩展 Markdown 三条路径，两名只读 Luna scout
分别复核 artifact topology 与测试 seam。主审随后发现第四条更小路径：生产失败当下已经持有精确
`frames`，可直接展开为现有逐帧失败单元，因此不需要保存“batch identity”。拓扑 scout 接到反证后也确认
此路径更安全、更小；sidecar 方案被推翻。

**成功标准**:普通 multi-frame provider failure 为每帧写已有 meta/failure marker，不再写 batch-only
marker；repair 只按显式 frame ID 定位；任何历史 batch-only marker 在加载帧/进度/provider 前明确失败；
删除 current-batch expansion 与 batch replacement；既有逐帧部分成功、取消、质量门和 resume 回归不退化；
focused、离线广集、编译与 diff 全绿。

**为什么重要**:batch ordinal 不是稳定身份。设置从 2 改为 1 后，“历史 batch 2”会从原来的第 3、4 帧
静默变成第 2 帧，provider 仍会返回语法有效正文，造成比显式失败更危险的内容污染。把已知 frame ID 在
生产失败时写下，比为一个可以消失的 batch 概念建立新 schema 更容易冷读，也直接删除错误代码。

**结果**:

- 两条直接回归先以 **2 failed / 5.42s** 复现：生产 multi-frame failure 只写 `批次 1 失败`，旧 batch
  marker 在 current batch size=1 时实际调用 provider 而没有拒绝。测试明确断言新生产输出包含两个精确
  frame ID，旧输出的 provider 调用数为零。
- `_phase4_batch_one()` 的普通异常分支现在为该请求中的每个 frame 调用既有 `_build_frame_marker()`，并写
  `帧 <id> 识别失败`。`repair_board()` 在发现任何 batch-only marker 时立即说明历史成员不可证明并要求重跑
  板书阶段；随后只保留显式 frame ID 路径。删除 current batch 分组、failed batch expansion、候选结果拼装
  和 batch placeholder replacement，共减少 54 行错误/兼容逻辑；没有新模块、sidecar、schema 或抽象。
- broader focused 首轮 **38 passed, 2 failed / 28.15s**；两项失败只是旧测试仍断言 `批次 N 失败` 文本。
  改为断言精确 frame meta/failure 后，video repair/resume/failure/quality/writer 集
  **40 passed / 26.31s**。一次更早的 broader 命令因猜错不存在的 `test_output_quality.py` 文件名而在
  argument validation 停止、零测试执行；改用仓库实际 `test_output_quality_refusal.py` 后完成验证。最后一次
  从 repo 根重跑 focused 时又因 legacy import path 缺失产生 **5 collection errors / 0 tests**，随即回到
  `legacy_app` 正确运行；这些命令错误不计入产品结果。
- 最终排除真实 ffmpeg `test_social_e2e.py` 与已延期 import-time Bilibili diagnostic 的 legacy 离线广集
  **272 passed, 1 skipped / 90.30s**，唯一 skip 是显式 live Google discovery。三个修改 Python 文件
  `py_compile` 与 `git diff --check` 通过；无网络/provider/付费调用，未动 `src/ocrllm`、`contracts/`、
  `worker/` 或 social media。

**遗留/下一步**:Phase 4 partial resume 仍按当前 batch size 组合已完成 frame block，可能导致重复付费但不会
把失败身份重定向到另一帧；没有独立失败证据前不把它并入本轮。legacy media repair 身份/原子发布队列已
关闭。下一轮回到队列 #11，调查普通 429/5xx 被误报成免费额度耗尽并错误触发 candidate switch 的 provider
语义债；先做只读路径证明与失败测试，不扩大到新的 provider 框架。

## #018 — 2026-08-23：独立视觉故障不再冒充免费额度耗尽

**任务。** 修正 legacy 独立 vision provider 的错误语义：普通 429/5xx 在用户明确启用候选队列
切换时可以继续 failover，但不得转换成 `FreeTierExhaustedError`、弹出“免费额度耗尽”提示，或在
候选全部失败后丢掉原始 provider 异常；明确 `AllocationQuota.FreeTierOnly` 仍保持原有配额恢复。

**选择。** 路径一是删除普通 429/5xx 的候选切换；这会违背现有“429/5xx 切换模型”显式设置。
路径二是保留这个 opt-in 产品行为，只拆开内部控制信号。选择路径二：新增仅在当前文件使用的
`VisionQueueAdvanceError`，把候选执行函数改名为诚实的 `_call_with_model_fallback()`。中性信号只
控制换候选，不调用 quota notifier；所有候选失败后重新抛出原始异常。显式免费额度标记仍使用
`FreeTierExhaustedError`。没有增加配置、重试次数、provider 调用、UI 或通用错误框架。

**失败优先证据与验证。** 修前 focused 集为 **2 failed, 12 passed / 7.53s**：普通 429 实际调用
quota notifier，普通 503 候选耗尽被改写成“所有免费额度耗尽”。修后 Chat Completions 与 Responses
两条 wire path、429/503、原异常保留和明确 FreeTier 回归共 **15 passed / 2.88s**。活跃库经代码和
既有 `test_dashscope_provider_boundaries.py` 复核，已经以 typed disposition 区分 quota、throttle、
provider unavailable，因此未把 legacy 修复复制过去。无网络、provider 或付费调用。
排除真实 ffmpeg e2e 与延期的 import-time Bilibili diagnostic 后，legacy 离线广集为
**275 passed, 1 skipped / 43.57s**，唯一 skip 是显式 live Google discovery；`py_compile` 与
`git diff --check` 通过。
首次从 repo 根运行 legacy focused 测试时因该套件依赖 `legacy_app` 工作目录而出现
`ModuleNotFoundError: OCRLLM`，当时零测试执行；切到正确目录后得到上述失败优先与最终结果，
该命令错误不计入产品测试结论。

**新发现与下一步。** Google 独立实现的 JSON 分类先判断 `code == 429`，会让同时含明确
`FreeTierOnly` / `FreeAllocationQuotaExceeded` 的 payload 走普通限流重试；已进入任务 13，下一轮
以真实结构的失败测试单独处理，不混入本轮第二个 provider。

**Carry-forward judgement.** 是。**WARNING FOR src/ocrllm**：候选切换原因必须保留 typed
disposition；临时限流、服务不可用和配额耗尽可以采取相似恢复动作，但不得共享会改变用户提示或
最终异常语义的类型。active library 当前已满足，后续 provider adapter 必须继续按此边界扩展。

## #019 — 2026-08-23：Google 429 JSON 的 quota / billing 语义校正

**任务。** 调查并修正 Google 429 JSON 中明确额度耗尽与普通窗口限流的分类顺序，同时保证普通
429、503、真实支付失败的原行为不变。成功标准是 classifier 与真实候选循环都证明：明确 quota
不重试已耗尽模型而切候选；普通限流只重试同一模型；不引入 DashScope 术语或更宽错误策略。

**证据推翻原判断。** 仓库历史和 Google provider 资料中没有 Google 返回 `FreeTierOnly` 或
`FreeAllocationQuotaExceeded` 的证据；两者从最早提交起就是 DashScope/OpenAI-compatible 路径的
标记。Google 的已有回归文案是 `You exceeded your current quota, please check your plan and
billing details.`。失败优先测试又证明 JSON 路径并非像 #018 末尾猜测那样判成 `RATE_LIMIT`，而是
先被建议文字中的 `billing` 截走，误判成 `BILLING`；候选虽碰巧同样切换，但错误类型不诚实。

**选择与修复。** 官方当前资料确认 429/`RESOURCE_EXHAUSTED` 覆盖 RPM、TPM、RPD、spend 等不同
窗口，不能仅凭状态码判永久耗尽。保留普通 429 默认限流，以及既有 rate limit/RPM/TPM/RPD 标记
优先。只把仓库已有证据的完整 Google quota 文案在没有限流标记时提前判为 `QUOTA_EXHAUSTED`，位置
在 generic billing 与 429 分支之前。真实 payment/billing/funds 仍为 `BILLING`。实现只在现有函数
内计算两个布尔值，没有新增 error framework、配置、重试或模型策略。

**失败优先证据与验证。** 新 classifier 断言修前为 **1 failed, 19 passed / 2.09s**，准确显示
`BILLING != QUOTA_EXHAUSTED`；此前仅看候选 call sequence 会因两个类型都允许切换而假绿，这也是
本轮新增直接类型断言的原因。第一次修复后又把普通限流测试加强为“quota advisory + RPM marker”，
暴露 generic billing 仍抢在 rate marker 前：focused **1 failed, 20 passed / 1.38s**，离线广集同一
原因 **1 failed, 277 passed, 1 skipped / 71.89s**。最终把 rate marker 提到该窄 quota/billing 决策前。
最终 `test_google_provider_errors.py` **21 passed / 0.99s**；Google provider/routing/config/settings
合集 **61 passed / 14.38s**；排除真实 ffmpeg e2e 与延期的 import-time Bilibili diagnostic 后，
legacy 离线广集 **278 passed, 1 skipped / 69.24s**，唯一 skip
是显式 live Google discovery。`py_compile` 与 `git diff --check` 通过；无 live/provider 调用。

**Carry-forward judgement.** 是。**WARNING FOR src/ocrllm**：未来新增 Google adapter 时，429 与
`RESOURCE_EXHAUSTED` 不能单独决定 disposition；同一恢复动作也不能代替准确分类测试。只迁移有
真实 payload/官方语义证据的窄规则，不得把 DashScope marker 搬进 Google contract。

## #020 — 2026-08-23：消除 active 原子写入的 Windows 临时路径放大

**任务。** 证明并修正 active image 输出及恢复状态在传统 Windows 路径上限附近的行为。legacy 曾真实
发生超过约 260 字符后多个环节失效；active 又会从用户输出路径派生 `.ocrllm-state.json` 和同目录临时
文件，因此先验证 child 是否真的继承同类风险，而不是直接建立通用 long-path 框架。成功标准是：一个
本身仍可用的 Markdown 与 sidecar 路径，不得仅因库内部临时名重复完整目标文件名而失败；公开输出名、
sidecar 名、resume identity 和同目录原子替换保持不变。

**假设复核与选择。** 代码路径证明 `normalize_output_stem()` 已限制公开 stem，但两个 atomic writer 原来
分别生成 `.<完整 Markdown 名>.<UUID>.tmp` 和 `.<完整 sidecar 名>.<UUID>.tmp`。本机
`LongPathsEnabled=0`；构造 213 UTF-16 units 的输出目录后，最终 Markdown 为 228、sidecar 为 243，
二者仍在传统界限内，而旧临时名分别达到 266 和 281。两条可选路径是：①建立 `\\?\` 前缀、全路径预算
和 fallback state 命名；②只把现有两个 writer 的内部临时 basename 改成固定
`.ocrllm-<32 hex>.tmp`。选择②：原子替换只要求临时文件与目标同目录，UUID 已提供唯一性；路径①会扩散到
existence/read/replace 等多条路径并改变持久 sidecar 契约，不适合这个已被精确定位的缺陷。没有为两行
相同策略再增加 helper 文件；冷读时两个 writer 各自把命名规则写明更直接。

**失败优先证据与修复。** 首条真实 Windows resume 回归修前为 **1 failed / 0.65s**，错误准确发生在
`save_image_resume_state_atomically()`，包装为 `OUTPUT_WRITE_FAILED`；旧 state 临时路径达到 281 字符。
随后只把两个 writer 的临时名缩短，不改变 durable 文件名、flush/fsync、同目录 replace、no-clobber 或
清理语义。只靠这一条回归不能独立证明 Markdown writer，而且启用 long paths 的 CI 可能让旧实现假绿；
只读测试审计指出后，拆成两条 Windows 回归，并用 test-only `Path.open` 在超过 259 UTF-16 units 时模拟
传统限制：non-resume 流程单独覆盖 Markdown 临时名，resume 流程覆盖 sidecar 临时名及第二次零 provider
复用。计数按 UTF-16 units 而非 Python 字符数，避免 supplementary characters 掩盖组件长度。

**验证。** 两条最终路径边界回归 **2 passed / 0.42s**；output/image-resume/M2-slot/local-OCR focused 集
在拆分前已为 **44 passed / 1.79s**。第一次 root 全量在新增第二条测试被 collection 之前启动，结果是
**1060 passed / 272.90s**，因此不把它冒充最终新增测试覆盖；最终 root 全量重新 collection 后为
**1061 passed / 208.82s**。四个修改 Python 文件 `py_compile` 与 `git diff --check` 通过。无网络、
provider 或付费调用；未修改冻结的 `contracts/`、`worker/`，未触碰 social media，也未修改用户的
临时交接文件。

**边界与下一步。** compact temp 只消除了“目标名被再次复制进临时名”的库内放大，并不支持任意深的
Windows 输出目录。输出目录达到约 215 units 时，44 字符临时名仍可能先碰传统总路径上限；canonical
sidecar 也比 Markdown 长 15 字符。若未来真实案例要求更深目录，应另做 provider 调用前 preflight 或完整
extended-path 方案，不能把本轮结果宣传为通用 long-path 支持。下一轮重新按成熟度队列选择已建功能缺陷；
Stage A 仍受 Stage M live 出口与 Stage 2 门禁约束。

## #021 — 2026-08-23：automatic checkpoint 的非法 sidecar 目标提前失败

**任务。** 审计 active image 输出/resume 的清理和覆盖边界，修复一个已经建立且可复现的正确性缺陷。
最初重点是 #020 之后的临时文件清理；代码复核后把目标收窄为 automatic checkpoint 的派生 sidecar
路径：`resume=False` 时，稳定 provider 仍会自动保存 paid-work checkpoint，但现有代码只在 provider
返回之后才发现 `<output>.ocrllm-state.json` 已经是目录。成功标准是该无效目标在 provider 前以 typed
path error 拒绝，provider 调用数为零，同时 `resume=True` 的既有 `RESUME_STATE_INVALID` 契约不变。

**假设复核与选择。** 两条方案是：①在 sidecar writer 内继续依赖最终 `os.replace()`；②在
`recognize.py` 已经派生 durable sidecar 名、但尚未 fingerprint/dispatch 的位置做无副作用检查。选择②。
writer 仍负责真实写入错误和竞态；preflight 只拒绝此刻明确存在且不是 regular file 的目标，不尝试用
探测文件预测权限或支持任意 long path。为一个局部三条件判断新建 validator 文件会增加冷读跳转，因而
直接放在唯一的 checkpoint 建立位置。检查只用于 `resume=False`；resume 模式继续交给严格 loader，避免
把既有 `ResumeStateError` 改成 `OutputError`。

**失败优先证据与修复。** 新测试建立一个与 canonical sidecar 同名的目录，并使用带
`resume_identity` 的 injected provider。修前为 **1 failed / 2.26s**：得到
`OUTPUT_WRITE_FAILED` 而非 `OUTPUT_PATH_INVALID`，且执行已越过 provider。修复把 sidecar 名派生提前到
fingerprint 之前，非 resume automatic-checkpoint 路径若目标存在且非 regular file，立即抛
`OUTPUT_PATH_INVALID`。同一测试随后再以 `resume=True` 调用，确认仍得到 `RESUME_STATE_INVALID`；两种
模式 provider 调用数均为零。单测最终 **1 passed / 0.28s**，image-resume/output/M2/process-kill/batch
focused 集 **36 passed / 2.00s**。第一次 broader 命令误写不存在的
`tests/test_batch_recovery.py`，在 collection 前停止、零测试执行；改用实际
`tests/test_recognize_batch_execution.py` 后得到上述 36 项结果，不把命令错误计作产品失败。

**并发审计的新发现。** 两名只读 scout 独立复核同目标并发。Events 控制的真实双线程调用稳定得到：
caller A 成功、caller B 为 `OUTPUT_EXISTS`，最终 Markdown 是 A，但 canonical sidecar 的 Markdown 是 B。
原因是 slot checkpoint 和 completed state 都在 no-overwrite Markdown 决胜前替换同一个 sidecar；单个
atomic writer 正确不代表两个文件构成事务。只锁最终 writer、调换最终写入顺序、或只在
`recognize_batch` 查重都不能关闭晚到的 partial checkpoint。进程内 per-output serialization 可以覆盖
公开的线程/batch 并发；跨进程 lock 还需要稳定 inode、崩溃恢复和 stale-owner 语义。该缺陷比本轮小修
更宽，不能在没有产品承诺审计和失败回归的情况下仓促加入锁，已登记为队列 #16 高优先级下一轮。

**验证与边界。** 最终 root 全量 **1062 passed / 94.54s**；两个修改 Python 文件 `py_compile` 与
`git diff --check` 通过。无网络/provider/付费调用；未修改 `contracts/`、`worker/`、legacy 或
social media，也未触碰用户临时交接文件。race scout 在系统 temp 下留下一个已确认为空的 probe 目录；
递归删除先被执行策略拒绝，随后非递归 PowerShell `Remove-Item` 又触发系统自身
`NullReferenceException`，目录仍在。路径为
`C:\Users\OMG\AppData\Local\Temp\ocrllm-race-audit-tujt3s9x`，不在仓库且不含文件；不使用跨 shell 或
更危险删除手段绕过该环境问题。

## #022 — 2026-08-23：同目标 Markdown 与 sidecar 的进程内所有权一致

**任务。** 关闭 #021 已稳定复现的 active 同目标并发竞态：两个 `recognize()` 都能在 output 尚不存在时
进入 provider/slot checkpoint；no-overwrite Markdown 最终虽只有一个 winner，canonical sidecar 却可能
已被 loser 替换。成功标准是 supported concurrency boundary 有明确证据，Events 回归修前失败，所有
checkpoint/load/final publication 都处在同一所有权内；winner Markdown 与 state 一致，后续 resume 零
provider 调用。

**边界与方案选择。** 当前公开 `recognize_batch()` 明确使用一个进程内线程池；README 同时说明
credential pool 没有跨进程状态，仓库没有多进程共享 output 的承诺。比较两条路径：①建立 sibling lock
file + OS advisory lock，补齐 Windows/POSIX、稳定 inode、残留文件、network filesystem 与权限语义；
②建立进程内、nonblocking 的 target claim。选择②：它完整覆盖已建 public batch/direct-thread 并发，冲突
调用在 provider 前以已有 `OUTPUT_EXISTS` 失败，不会等待另一个外部 provider；也不增加持久文件或新的
public error taxonomy。`overwrite=True`/`resume=True` 仍允许顺序调用，但重叠调用同样受 active ownership
约束。跨进程两个 writer 不是本轮声称解决的范围，文档必须明确，不能把进程内 claim 宣传成文件事务。

**失败优先回归。** 使用 `threading.Condition` 和真实 atomic writer，不用 sleep。winner 在 completed
state 已保存、Markdown 尚未发布时暂停；loser 此时启动。修前 **1 failed / 0.42s**：winner 返回成功、
loser 得到 `OUTPUT_EXISTS`，但最终文件为 `# Winner A`、state 却为 `# Loser B`。断言还要求后续
`resume=True` 使用 winner identity 且 provider 调用数为零，因此不仅比较文本，也通过生产 validation
证明 durable pair 可复用。

**实现与反向审查。** 新增 `output/claim_output_target.py`，只负责将 resolved + `normcase` target 放进
进程内 guarded set；重叠 claim 立即抛 `OutputExists`，`finally` 删除 key，不创建 lock file，也没有等待
或 registry 增长。公共 `recognize()` 用标准库 `ExitStack` 保证普通异常、typed error、取消或成功返回都
释放 claim；claim 后重新执行 `build_output_path()`，关闭首次 preflight 变旧的窗口。首次实现只在
`checkpoint_enabled` 内 claim，focused 单例曾 **1 passed / 0.25s**；只读反向审查随即指出 identity-less
provider 可先发布 Markdown，使 checkpoint owner 留下错误 state。该决定被推翻：现在任何
`output_path` 非空的 recognition 都在 capability 分支前 claim。回归参数化为：①stable loser 尝试替换
sidecar 后输掉 Markdown；②identity-less loser 试图先赢 Markdown。两种最终都在 provider 前被拒，
winner pair 一致且 resume 零调用，最终 **2 passed / 0.38s**。这也证明不能只保护 sidecar writer。

**验证与边界。** image-resume/output/M2/process-kill/batch focused 集 **38 passed / 2.27s**；最终 root
全量 **1064 passed / 84.47s**。四个修改/新增 Python 文件 `py_compile` 通过；独立 import probe 确认
`import ocrllm` 未加载 Pillow/OpenAI/httpx，`git diff --check` 通过。无网络/provider/付费调用；未修改
冻结的 `contracts/`、`worker/`、legacy、social media 或用户临时交接文件。

## #023 — 2026-08-23：确定 Google 图片 provider 的最小迁移边界

**任务。** 在不提前启动 Stage 2、不复制 legacy 架构的前提下，判断 Google 图片能力是否值得迁移、现有
active image seam 能复用多少、需要哪些依赖和错误语义，并把可执行的门禁顺序写进当前计划。

**上下文与假设复核。** 开工时假设可能只需在当前 `Config.provider` 旁增加一个 Google settings 和
adapter。代码审计推翻了这个假设：当前配置归一化只把精确 `DashScopeSettings` 当内置 provider；image
processor 仍含 DashScope-only scout/证据元数据；capability 只认识 DashScope；resume fingerprint 也只有
DashScope 内置身份，其他对象走 injected `resume_identity`。因此“现在直接加 Google”并不是一个独立 adapter
改动，而是一次不完整的 Stage 2，随后还要迁移第二次。当前环境已安装 `google-genai 2.9.0`，本轮只检查其
本地公开签名，没有安装、升级或联网调用。

**两条路径与选择。** ①现在把 `GoogleSettings` 塞进旧的单 provider 配置，同时补 resolver、capability、
fingerprint 和 processor 特判；短期文件数少，但会固化即将被 Stage 2 替换的 public shape。②先完成既定
vision/audio provider/modality split，保留 `ResolvedVisionProvider`、`call_vision_provider`、共享 Markdown
验证、候选 ledger 与 checkpoint，再登记一个只做 Google SDK 请求/解析/错误映射的内置 vision adapter。
选择②。它不是为了通用框架，而是避免同一配置迁移两次，并让重试和模型切换继续只有一个 owner。

**值得迁移的最小产品行为。** 官方 `google-genai` 延迟导入并放在独立 optional extra；通过有界
`models.list()` 获取支持 `generateContent` 的当前目录，不把名称或“免费”状态硬编码为事实；按已验证顺序
发送 active library 已经快照/校验的图片字节与 prompt；解析顶层 text 和 candidate/content/part fallback；
空回复、JSON error、blocked/truncated/无文本都不能假成功。Google-specific mapper 只产出现有 typed
error/disposition，由 active candidate loop 决定是否切下一个模型。已有真实回归支持的 quota 规则仍是完整
`You exceeded your current quota ... check your plan and billing details` 文案；普通 429/RESOURCE_EXHAUSTED
及 RPM/TPM/RPD marker 是窗口限流，marker 优先。不得搬入 DashScope 的 `FreeTierOnly` 等标记，也不得把
真实 billing/payment 冒充 quota。legacy 对 5xx/503 high demand 只重试同模型而不切 vision 候选；首版
active adapter 不复制隐藏重试，因此从单次调用返回 typed transient failure，但也不能借错误映射自动切模型。

**明确不迁移。** legacy `GoogleProviderClient` 内部 retry/switch loop、最后成功模型的可变缓存、24 小时 GUI
catalog cache、AppConfig/QSettings、hybrid/provider priority、text/context chat、audio upload/Files API、
credential pool、video 参数与 social workflow 都不进入首个图片 slice。legacy 对任意 MIME 回退 JPEG、默认
20 图片和“目录内全部模型免费”的假设也不作为新库契约。unsupported format、图片过多和空 image response
缺少直接 image 回归，先列为获授权的有界 live 测试目标，不预造限制。

**验证与计划结果。** 两名只读 scout 分别审计 legacy 行为/测试与 active seam，主代理随后逐文件复核
`config.py`、resolver/caller、image processor、resume fingerprint、capability、Google provider/model catalog
和 SDK 本地签名。legacy Google error + discovery focused 集 **25 passed / 2.63s**；active provider boundary +
Stage M + image resume focused 集 **88 passed / 1.34s**。首个 SDK 签名探针因 PowerShell 引号被吃掉产生
`NameError`，改用标准输入脚本后确认当前 `Client(http_options=...)`、`HttpOptions(timeout=int)`、
`Part.from_bytes`、`models.list()` 与 `generate_content()` seam；这是探针命令错误，不是产品失败。
`docs/plan_phase1_maturation_and_phase2_audio.md` 现在记录 Google image follow-on：Stage M paid exit 与
Stage 2 都完成后才可实现；它可与 Stage A 独立排序，不成为 audio 新门禁。没有改代码、安装依赖、
联网/provider 调用，也没有动
冻结区、legacy、social media 或用户临时交接文件。

**遗留/下一步。** Stage 2 写代码前仍有计划中已登记的人类选择：旧 `Config.provider`/`vision_model` 保留一版
兼容映射，还是在 0.2.0 明确破坏。Google 调研不替用户猜这个 public API 决定。当前 heartbeat 下一项仍应
优先找已建功能的可证明缺陷；若无更高优先级缺陷，则可继续 Stage A 只读调研。Google adapter 实现保持门禁关闭。

## #024 — 2026-08-23：候选模型只处理 model-scope 故障

**任务。** 验证并修复 active candidate recovery 的 scope 漏洞：account-wide quota 或 provider-wide outage
不能仅因错误 code 位于 allowlist 就继续调用下一个模型；同时保证真正的 model-scope quota/unavailable/
permission 仍能恢复，attempt ledger 和最终错误身份不说谎。

**上下文与方案变化。** 初查发现 `_may_advance_candidate()` 只检查 permission 的 scope，quota 与 unavailable
无条件返回真；而公共 disposition 已明确把无 scope quota 默认为 account、unavailable 默认为 provider，
DashScope 5xx 也实际映射为 provider scope。先比较两条路径：①三类允许错误一律要求 model scope；②保留共享
漏洞，等 Google adapter 再加特判。选择①，因为换模型只能修复模型状态，不能修复 account/credential/provider。
中途曾考虑为旧 injected provider 保留“无 scope 也切换”的兼容分支；两名只读 scout 与提交历史复核表明，
现有两个无 scope 正向 fixture 的文字本身都声称 per-model，只是漏写证据，而且库仍为 0.1.0、没有外部消费方。
因此撤回兼容分支，改成更小、更诚实的单一规则，并给正向 fixture 补上 `failure_scope="model"`。

**失败优先证据。** 新增 public `recognize()` 参数化回归，以显式 account-scope `QuotaExhausted` 和
provider-scope `ProviderUnavailable` 驱动真实候选循环。修前 **2 failed, 12 passed / 0.76s**：两种错误都没有
抛出，因为代码额外调用 `never-tried-model` 并返回成功。回归同时约束只发生一次 provider 调用、原 typed code
和 scope 保留、`failed_model` 正确、ledger 只有一项且付费调用数为 1。正向测试继续覆盖 model-scope quota、
unavailable 和 permission 均能切换。

**审查发现与实现。** 主代理逐行审查 mapper、disposition、candidate loop、M2 slot resume、Stage M policy 和
引入提交 `25af57c9`。生产判断从“permission 看 scope、其余只看 code”缩减为：code 必须属于既有三项 allowlist，
且 canonical disposition scope 必须等于 `model`。没有新类、配置、重试或 provider 特判。只读 policy scout 另
发现终止包装会把最后一个候选的 `failure_scope="model"` 复制给 `ALL_CANDIDATES_EXHAUSTED`，覆盖该错误本应为
account 的 disposition；新增断言修前 **1 failed / 0.40s**。修复只在包装前删除这个局部 scope，逐模型结果仍
保留在 attempt ledger，终止错误恢复 canonical account scope。

**验证与边界。** candidate/M2/disposition/DashScope mapper focused 最终集 **95 passed / 0.97s**；root 全量
**1066 passed / 89.53s**。`compileall`、独立 plain-import probe 与 `git diff --check` 通过；probe 确认未加载
Pillow、OpenAI、httpx、onnxruntime 或 google-genai。没有网络/provider/付费调用，没有修改 frozen
`contracts/`、`worker/`、legacy、social media 或用户临时交接文件。

**遗留/下一步。** Stage M paid live exit 仍需用户单独批准 DashScope 预算；本轮离线结果不替代它。Google
follow-on 现在可以直接依赖共享 scope 规则，503/provider outage 不需要 adapter 私有绕行。下一轮继续优先
检查已建 active 功能的可证明缺陷；没有更高价值证据时再做 Stage A 只读调研。

## #025 — 2026-08-23：automatic checkpoint 不再按 provider 类名猜身份

**任务。** 证明并修复 `_can_checkpoint_image()` 的类型身份冲突：用户注入的 provider 即使碰巧命名为
`DashScopeSettings`，也不能被当成内置 DashScope 而强制进入 automatic checkpoint；普通 `output_dir`
写出必须照常工作，显式 `resume=True` 的稳定身份要求保持不变。

**上下文与方案。** 当前 `Config` 只把精确内置 `DashScopeSettings` 归一化为 built-in，resolver 与 resume
fingerprint 也都使用精确类型；只有 checkpoint eligibility 比较 `type(provider).__name__`。因此同名 injected
对象先被错误判为“可 checkpoint”，随后 fingerprint 又正确识别为 injected，并在 provider 调用前因缺少
`resume_identity` 抛错。比较两条路径：①导入现有轻量 settings 类型并使用 `type(...) is DashScopeSettings`；
②增加通用 checkpoint capability marker/protocol。选择①。injected provider 已经用 `resume_identity` 表达
稳定身份，新增第二个 marker 会重复权威，而且 Stage 2 尚未引入第二个内置 adapter。

**失败优先证据与实现。** 新增 public `recognize()` 回归，在测试函数内定义一个普通、无
`resume_identity`、但类名恰为 `DashScopeSettings` 的 injected provider，并设置 `output_dir`。修前
**1 failed / 0.42s**：得到 `CONFIG_INVALID`，provider 调用数为 0。修复只有两行：`recognize.py` 直接导入
既有 settings 类型，并把字符串类名比较改成精确类型比较。修后同一回归证明 provider 调用一次、返回与磁盘
Markdown 一致、结果路径正确，且 canonical `.ocrllm-state.json` 不存在。原有 identity-less
`resume=True` 回归继续证明显式恢复在零调用时拒绝。

**审查与验证。** 两名只读 scout 分别复核运行拓扑和测试 seam，均确认配置、resolver、fingerprint 的精确
类型规则一致，`provider_settings.py` 不反向导入 `recognize`，因此没有循环依赖；`Config` 在 recognition
模块加载时本来就需要同一 settings 模块。image-resume/import-contract/settings focused 集
**77 passed / 1.68s**；root 全量 **1067 passed / 94.41s**。`compileall`、plain-import probe 与
`git diff --check` 通过；plain `import ocrllm` 未加载 provider settings，也未加载 Pillow、OpenAI、httpx、
onnxruntime 或 google-genai。没有网络/provider/付费调用，没有修改 frozen `contracts/`、`worker/`、
legacy、social media 或用户临时交接文件。

**遗留/下一步。** 这次只统一已经存在的 built-in 身份规则，不建立未来 adapter registry。Stage 2 真正加入
第二个内置 provider 时，再把 stable identity 设计为 provider-neutral seam；现在提前抽象没有消费者。下一轮
继续查找已建 active 功能的可证明缺陷；若没有更高价值证据，则转入队列 #6 的 Stage A 只读调研。

## #026 — 2026-08-23：部分恢复遇到旧输出时不再先花模型调用

**任务。** 检查 `resume=True` 是否会在发现已有 Markdown 与部分 checkpoint 无法同时验证之前，先补跑缺失的
provider 工作。成功标准是：真实可达场景先有失败回归；修复后在任何新增 provider 调用前报 typed mismatch，
原 Markdown 与已保存 slots 都不改变；正常部分恢复和完整状态复用继续通过。

**假设修正与方案。** 初始假设是“部分状态旁不应存在 Markdown”。两名只读 scout 和主代理逐行复核后找到
反例：已有 Markdown 的任务以 `overwrite=True` 开始，slot 已写入 sidecar 后中断，会自然留下旧 Markdown 与
合法 v2 partial state。当前状态没有保存 overwrite 授权或旧文件摘要，而 `resume=True` 又不能与
`overwrite=True` 同时设置，所以库不能判断该文件仍是原来的旧产物，还是中途被替换。比较两条路：①扩展状态
版本，记录覆盖前文件身份并设计自动替换语义；②保持现有状态契约，在身份验证后、补跑 provider 前保守拒绝。
选择②。它不猜测覆盖权限、不增加状态字段，并且用户移走旧 Markdown 后仍可从未变的 slots 继续恢复；自动
穿过旧文件的恢复留给未来有真实优先级时再设计，不能在本轮偷偷放宽覆盖语义。

**失败优先证据与修复。** 回归先写入 `previous published output`，用 `overwrite=True` 运行三次 provider
尝试并在第三次失败，确认库生成 partial sidecar 且保留旧文件；随后用同一稳定身份 `resume=True`。修前
**1 failed / 0.45s**：恢复又执行一次 provider，完成并替换 sidecar 后才得到
`RESUME_STATE_MISMATCH`。修复只在 `recognize.py` 的 partial-state 分支增加一个前置条件：先完成 request
identity 校验，若 output 已存在则立即抛 `RESUME_STATE_MISMATCH`。回归约束调用数不增加、旧 Markdown 文本
不变、sidecar 原始 bytes 不变。没有调用只适用于 completed state 的 digest validator，也没有静默覆盖。

**审查与验证。** 主代理复核 config 的 resume/overwrite 互斥、output preflight、slot 原子保存、partial
state invariant 和最终 output validator。image-resume/M2/defect focused 集 **44 passed / 2.73s**；root
全量 **1068 passed / 90.09s**。本轮无网络/provider/付费调用，没有修改 frozen `contracts/`、`worker/`、
legacy、social media 或用户临时交接文件。当前文档已明确人工处理方式：移动或删除旧 Markdown 后再恢复，
已保存的付费 slots 仍可复用。

**遗留/下一步。** v2 状态无法自动证明 interrupted-overwrite 留下的旧产物；这是明确限制，不是本轮声称关闭
的能力。只有当自动恢复覆盖任务成为实际产品优先级时，才考虑把 prior-output provenance 纳入新状态版本。
下一轮继续优先审计已建 active 功能；无更高价值缺陷时再进入 Stage A 音频只读调研。

## #027 — 2026-08-23：dangling sidecar 在模型调用前拒绝

**原任务与改向。** 本轮先检查“completed state 保存后 Markdown 发布失败，是否会毁掉已付费恢复证据”。
代码顺序和已有测试否定了这个猜想：completed sidecar 先原子保存，Markdown 后发布；发布失败后，无 output 的
`resume=True` 会零 provider 调用复用 state 并重新发布。vision、local OCR、post-publish crash window 和真实
Markdown replace failure 四项 focused 证据均通过。若 `overwrite=True` 已有旧 output/state，新 slot 会替换
旧 state；同时保存旧一代和新付费一代需要 pending generation 或事务指针，不能靠调换两个 writer 的顺序完成。
本轮不为这个已正确的次序增加重复 helper，也不偷偷放开 #026 已决定保守处理的 overwrite 权限。

**实际缺陷与方案。** 邻近审计发现 automatic checkpoint 对 canonical sidecar 使用 `Path.exists()`，而
Markdown preflight 和 strict resume loader 都使用 lexical existence。dangling symlink 会被 `exists()` 当成
不存在，provider 先执行，随后 state 的 `os.replace()` 会替换这个 symlink directory entry。比较两条路：
①把 dangling link 当作可替换的空位；②把任何已存在的非 regular sidecar 当作调用前冲突。选择②，因为它符合
当前 `OUTPUT_PATH_INVALID` 契约，也避免已知本地冲突之后才花 provider 调用。只把 predicate 改为
`os.path.lexists(resume_state_path)`；没有抽取共享 validator，因为 automatic 与 strict resume 的 error code
本来就不同，抽象不能减少规则。

**失败优先证据。** Windows 当前账户不能创建文件 symlink（探针得到 WinError 1314），所以回归不依赖开发者
权限：只对 canonical sidecar 模拟 `lexists=True`，真实 `Path.exists/is_file` 仍保持 dangling-link 语义。
修前 **1 failed / 0.43s**：没有抛错，provider 已运行并完成。修后得到 `OUTPUT_PATH_INVALID` 且 provider
调用数为零；原有目录 sidecar 测试继续证明 automatic 是 `OUTPUT_PATH_INVALID`、strict resume 是
`RESUME_STATE_INVALID`。output/image-resume/M2/defect focused 集 **56 passed / 2.95s**。

**新发现但不混入本轮。** 只读 batch scout 用公开 API 稳定证明一个更高优先级缺陷：两个不同目录下同名 source
会得到同一个 normalized output path；`recognize_batch(..., overwrite=True)` 的每个 item 在返回后释放 claim，
所以串行模式下两个 provider 都执行、两个 outcome 都报告 success，而第二个 Markdown 静默覆盖第一个已付费
结果。单次调用的 active claim 或再做一次 existence check 都不能修复；需要 batch 生命周期内保留 target
reservation。该缺陷已写入 authoritative Known Debt，下一轮优先做失败回归与最小 batch-scoped reservation，
不在这次一行 sidecar 修复中扩张。

**验证与边界。** root 全量 **1069 passed / 90.24s**。无网络/provider/付费调用；未修改 frozen
`contracts/`、`worker/`、legacy、social media 或用户临时交接文件。下一步是上述 deterministic batch
overwrite collision，不因它需要更宽的调用生命周期就降级为文档长期债务。

## #028 — 2026-08-23：batch 生命周期内保留 output target ownership

**任务。** 修复 #027 发现的 durable-success 漏洞：两个不同 source 归一化到同一个 Markdown path 时，
`recognize_batch(..., overwrite=True)` 不能让两个 item 都调用 provider、都报告成功，再由后者静默覆盖前者。
成功标准是串行和非重叠并行都在第二次 provider 前返回 item-level `OUTPUT_EXISTS`，第一份已付费 artifact 保持，
batch 结束后 claim 正常释放；standalone 行为、lazy iterable、fail-fast 和错误脱敏不改变。

**方案比较与选择。** ①在 batch 开始前展开 iterable、重复 source/profile/output-name 计算并预留全部 path；这可
固定最低 index 获胜，但会改变 lazy/fail-fast 行为，并制造一套可能与真实 `build_output_path()` 漂移的预测逻辑。
②让真实 `_recognize()` 在已经解析出的 output path 上申请 claim，但由 batch 共享一个 thread-safe owner，把每个
claim 保留到所有 dispatched futures settle。选择②。并行执行只承诺 outcome 按 caller order 返回，并不承诺
worker/provider 启动顺序；因此不为碰撞另造 prepare/execute 两阶段。实现新增单一职责的
`output/output_target_claims.py`：Lock 保护一个 `ExitStack`，同一 owner 的重复 path 仍由已有 process-local
`claim_output_target()` 产生 `OUTPUT_EXISTS`。standalone `recognize()` 使用一次调用范围的 owner；batch 把同一
owner 显式传过 serial、submit、worker 和 settle 路径，没有 ContextVar 或 public 参数。

**失败优先证据。** 两个目录各放一个 `same.png`，同一 output_dir、`overwrite=True`。串行修前调用 provider
两次、两个 outcome 都成功，磁盘只剩 `# Result 2`。最初并行测试直接同时启动，反而被已有 active-call claim
挡住而通过，不能证明 batch lifetime；因此撤回该弱 seam。最终用 Event 让第二个 worker 等到第一个真实
`_recognize_batch_item` 完全返回（旧 per-call claim 已释放）再进入，不用 sleep。修前最终 **2 failed / 0.43s**：
串行和受控并行都调用两次并覆盖。修后两者均只调用一次；item 0 成功、item 1 为 `OUTPUT_EXISTS`，磁盘等于
item 0 result。串行回归还检查 duplicate error 无 cause/context/traceback，并在 batch 返回后执行 standalone
overwrite，确认 claim 没有泄漏。

**错误边界与审查。** batch 改为直接调用 core `_recognize()` 才能共享 owner；如果直接保存异常，会绕过公共
`recognize()` 原来清除内部 traceback/exception chain 的边界。把原四项清理提取为
`clear_public_error.py::clear_public_error()`，standalone 仍在同一位置清理后 `raise ... from None`；serial
catch、parallel completion catch 和 settle catch 在写入 `BatchItemOutcome` 前执行同一清理。主代理逐段复核
BaseException unwind、executor 等待、fail-fast cancel、memory-only no-op、resume collision 与 owner close：
claims 只在所有已派发 future settle 后关闭，异常退出也先由 executor 等待运行中任务，再释放 owner。

**验证与边界。** batch/output/resume/traceback focused 集 **108 passed / 4.54s**；root 全量
**1071 passed / 91.56s**。`recognize_batch()` 当前文档已改为“整个 batch 保持 output ownership”，#027 的
open Known Debt 已删除。无网络/provider/付费调用；未修改 frozen `contracts/`、`worker/`、legacy、social
media 或用户临时交接文件。仍不声称跨进程文件事务；不同进程写同一 output_dir 是单独、未支持的边界。

**下一步。** 继续优先审计已建 active surface，尤其新 shared owner 周边的 cancellation/iterable 异常释放；
若没有可证明缺陷，再按队列进入 Stage A 音频只读迁移调研。

## #029 — 2026-08-23：batch 输入迭代失败不再吞掉已完成结果

**本轮任务与假设修正。** 原子任务先检查 #028 新增的 batch-lifetime output owner 在 source iterator、取消或异常控制流中
是否泄漏 claim。主代理用“先产出一个已发布结果、再由 generator 抛 `RuntimeError`、随后立即 standalone overwrite”的离线探针覆盖
串行和并行；只读审计又逐段检查外层 owner、内层 `ThreadPoolExecutor`、future settle 和 `ExitStack.close()`。两条路径都确认：executor
先等待已运行任务收束，owner 再释放所有 claim；底层 claim 自身也在 `finally` 删除 key。因此原猜想被否定，没有增加重复 cleanup。
探针却暴露了相邻真实缺陷：普通 iterator 异常直接逃出 `recognize_batch()`，调用者拿不到已经完成并付费的 outcome；如果异常发生在
`_append_not_attempted()`，还会覆盖已经记录的 typed item failure。

**方案比较与选择。** 方案一是把 `sources` 收紧为“调用者保证永不失败的 sequence”，保留 raw iterator exception；方案二是继续接受有限
`Iterable`，把打开或推进 iterable 时的普通 `Exception` 表示为该位置的一个终止 `SOURCE_INVALID` outcome，同时保留此前结果。选择方案二：
它延续 D3“不丢已完成工作”的公开目的，不需要预展开输入，也不改变 lazy dispatch。实现只捕获普通 `Exception`，所以
`KeyboardInterrupt`、`SystemExit` 等进程控制异常仍然传播；错误文本固定为库拥有的脱敏消息，不复制 generator exception、secret 或
traceback。该终止 outcome 表示“此输入位置无法读取”，不是虚构一个已成功枚举的 source。文档同时明确这是有限 batch API；无限 iterable
在 fail-fast 后如何停止属于独立 streaming 设计，本轮不加猜测性 cap、后台消费或新配置。

**失败优先证据与实现。** 参数化回归让 generator 先 yield 一张真实测试图，等待 provider 确实启动，再抛出含
`SECRET-ITERATION-TOKEN` 的 `RuntimeError`。修复前串行和双 worker 均为 **2 failed / 0.71s**：raw exception 逃出，已发布 Markdown
虽然留在磁盘，但调用者收不到 outcome。修复后返回两个有序结果：index 0 success、index 1 `SOURCE_INVALID`；provider 只调用一次，
错误不含 secret，随后 standalone overwrite 成功，顺带证明 #028 owner 没有泄漏。第二组串行/并行回归让第一个 item 先得到
`PROVIDER_UNAVAILABLE`，随后剩余 iterator 抛错；返回结果同时保留原 provider failure 和终止 `SOURCE_INVALID`，不再由后者覆盖前者。
第三项回归覆盖 `iter(sources)` 本身抛错，得到 index 0 的脱敏 typed outcome。生产改动仅把 serial advance、parallel submit 和
not-attempted drain 三个既有入口统一到同一个小 outcome constructor；没有新 public type、error code、线程、重试或预扫描。
个人复核还发现可恢复的自定义 iterator 在第一次异常后可能继续 yield；并行 worker 完成时原本会再次推进它。增加一个局部
`accepting_sources` 状态后，第一次耗尽或异常都永久停止本批次继续取源，同时避免正常耗尽后重复调用 `next()`；回归证明异常后的
`forbidden.png` 不会进入 provider。

**个人复核、验证与边界。** 主代理复核了 outcome 排序、并行列表中的未 settle 槽、gate/claim 生命周期、异常层级和 generator 关闭语义；
新逻辑不会把 provider 内部的任意异常误判成 iterator 错误。batch/image/defect/Stage M focused 集 **82 passed / 3.30s**；正确项目环境
`D:\Anaconda\envs\OCRLLM\python.exe` 下 root 全量 **1077 passed / 89.62s**。系统 base Python 因其 site-packages 中另有 regular
`tests` package，曾在 collection 阶段产生 29 个 `tests.quality` import error；切回仓库既有 OCRLLM 环境即消失，没有为环境冲突修改产品代码。
本轮无网络/provider/付费调用，未修改 frozen `contracts/`、`worker/`、legacy、social media 或用户临时交接文件。

**下一步。** 只读 scout 另发现 active provider Markdown validator 对 HTML comment 的相反误判：comment-only 文本会被当作可见成功，
而 comment 内的 apology 又会把外部真实 Markdown 误判为 refusal。下一轮应先做两个 public failing-first 回归，再只在可见性/拒绝检查前
忽略闭合 `<!-- ... -->`，返回值仍保留原 Markdown；不要引入完整 Markdown renderer。

## #030 — 2026-08-23：provider 的闭合 HTML comment 不再制造相反误判

**任务与已确认假设。** 本轮处理 #029 留下的 active provider-output 缺陷：仅含闭合 `<!-- ... -->` 的响应实际不渲染识别内容，不能成功；
但 comment 内部的 “I'm sorry / cannot read” 也不可让外部真实 `# Board` 被判为 refusal。主代理重新读取权威状态、入口文档、工作日记和
package 规则并同步 origin；两名只读 scout 分别复核 production topology 与测试 seam。调用链确认所有 injected 与 built-in vision 响应都经
`call_vision_provider()` 进入 `validate_provider_markdown()`；成功值在此后原样返回。因此本轮假设明确为：闭合 comment 只从语义检查视图中
移除，不重写成功结果。

**两条路径与选择。** 方案一是在 visibility 和 refusal 两处各写一个相同 regex，文件少但会保留两套可能再次漂移的 comment 定义；
方案二是增加单一职责 `providers/remove_closed_html_comments.py::remove_closed_html_comments()`，两项检查共用它。选择方案二，文件名即职责，
实现只是已有 DOTALL/non-greedy `<!--.*?-->` 规则的唯一归属，不引入 renderer、tokenizer 或 HTML parser。`validate_provider_markdown()` 对
comment-free view 做 L/N/S 可见性检查；`looks_like_refusal()` 在同一 view 上做 trim、300 字符上限和 marker 搜索；两者通过后仍返回原始
Markdown 字符串。非字符串仍按原契约归一到同一 `PROVIDER_RESPONSE_INVALID`/`empty` 分支，没有重复 error construction。

**失败优先证据与回归。** public `recognize()` 回归首先加入两例。多行 comment-only 在修前未抛错，独立运行是 **1 failed, 7 passed**；
含隐藏 apology/refusal 与外部可见公式的 Markdown 在修前错误抛 `PROVIDER_REFUSED_RECOGNITION`，独立运行是 **1 failed**。修后前者稳定得到
`PROVIDER_RESPONSE_INVALID` 且 `details["reason"] == "empty"`，后者 success 并逐字等于原 provider 字符串，证明 comment 没有从输出中
删除。现有 direct `looks_like_refusal()` 回归也加入 hidden refusal assertion，防止未来只在 validator 外围绕过而让底层函数重新说谎。

**边界与个人复核。** 主代理逐行复核 exact-str hostile subclass、空值分类、marker 大小写、多个/跨行闭合 comment、原值返回、built-in
error-detail 合并、candidate/retry 与 checkpoint 调用顺序。helper 只识别闭合 comment；未闭合或畸形 comment 保持旧行为。comment 语法若
出现在 inline/fenced code 中，完整 Markdown renderer 可能把它当作可见字面量；正确区分需要 parser/state machine，当前真实缺陷与 legacy
行为没有提出该需求，本轮不扩张。也没有把其他 HTML tag/entity 一并定义为“不可见”。两份历史 CRLF 文件在 patch 后曾出现 mixed EOL，
已只对这两份文件恢复原 CRLF；仓库的 `* -text` 策略不变。

**验证与异常记录。** provider/image/D1/error-detail/DashScope/M2/Stage M focused 集 **169 passed / 5.91s**。首次 root 全量出现一个与本轮
无关的短间隔 timing failure：`test_direct_recognition_applies_interval_between_draft_and_review` 在 30 ms 配置下记录到约 15 ms，结果为
**1 failed, 1078 passed / 91.26s**；该 cadence 代码未修改，随后 exact test 连续 **10/10 passed**，再次 root 全量为
**1079 passed / 90.66s**。Windows monotonic 采样粒度使这个单次证据更像测试边界抖动，但不能当作未发生；已保留供后续独立 cadence audit，
本轮不夹带 sleep/tolerance 改动。`compileall`、plain import 和最终 diff/EOL 检查在提交前另行执行。本轮无网络/provider/付费调用，未修改
frozen `contracts/`、`worker/`、legacy、social media 或用户临时交接文件。

**下一步。** 下一轮先对上述 cadence 测试做只读、可重复的 Windows 计时审计：区分产品 start-gate 语义与低分辨率观测误差；只有稳定证明
产品会过早 dispatch 才改实现，否则只修测试测量 seam。若该证据不能复现，再继续优先审计 active provider/output surface，而不是扩大
HTML/Markdown 解析范围。

## #031 — 2026-08-23：provider start gate 改用高分辨率单调时钟

**任务与证据转向。** 本轮接续 #030 唯一一次 30 ms cadence 测试记录到约 15 ms 的现象，先判断是产品过早放行还是测试观测误差。
主代理重新读取权威文档、日记与 package 规则并同步 origin；两名只读 scout 分别审计 clock/call topology 与测试设计。初始有两条路径：
①保留 production `time.monotonic()`，只把 `TimedProvider` 换成更精细的测量；②若 coarse clock 可使 permit 本身损失间隔，则 production 与
测试一起改用 `time.perf_counter()`。仓库实际环境 `D:\Anaconda\envs\OCRLLM\python.exe` 是 Python 3.10.20，实时
`get_clock_info()` 证明 `monotonic=GetTickCount64(), resolution=0.015625`，而
`perf_counter=QueryPerformanceCounter(), resolution=1e-7`。一名 scout 最初在系统 Python 3.13 上看到两者同为 QPC，主代理要求切回项目
解释器复核后结论一致修正；没有把错误环境的结果当成仓库事实。

**失败优先的确定性证明。** 新建单一职责 `tests/test_provider_request_start_gate.py`，用无真实 sleep 的
`QuantizedWindowsClock` 模拟 15.625 ms GetTickCount64 tick 与 timer-quantized sleep：第一次 gate permit 恰在 coarse tick 前，provider entry
跨过 tick 后记录；第二次等待若仍以 stale coarse value 建 deadline，就可在下一 tick 放行。旧代码稳定 **1 failed / 0.15s**，两次仿真 actual time
只差约 `0.031251 - 0.015624 = 0.015627`，小于配置 0.03；这不是靠偶发调度重现。把 gate 的唯一时间读取改成
`time.perf_counter()` 后，同一模型必须跨满高分辨率 30 ms 才能放行。测试同时 monkeypatch coarse `monotonic` 与高分辨率 `perf_counter`，
未来若退回旧时钟会重新失败。

**最小实现与边界。** production 只有一行行为改动：`ProviderRequestStartGate.wait()` 从 `time.monotonic()` 换到同样单调、但在项目 Windows
运行时由 QPC 提供的 `time.perf_counter()`。integration `TimedProvider` 也用 QPC 观测，避免端点量化把真实约 30 ms 错报成一个 15.625 ms
tick。没有改 interval 配置、sleep/poll、lock、abort/cancellation、timeout、线程数或 provider API。两个 scout 与主代理都指出另一条不同边界：
injected provider 在 caller gate 后通过 Event 唤醒已 parked worker，极端 worker 调度仍可能压缩“method entry”观测；remote network send 更不
可能由库精确承诺。此次失败只证明 coarse clock 问题，没有证明需要把 gate 搬进 worker。为该理论窗口增加 handshake 会连带改变 timeout 与
cancellation 语义，因此本轮明确不做。权威文档现在承诺 operation-local gate authorization spacing，并把 provider entry 作为接近的 integration
证据，而非任意线程/网络的绝对时钟保证。

**复核与验证。** 修后 deterministic gate 回归通过；direct 与 parallel integration cadence 两项连续运行 **20 轮、40 tests 全通过**。
一名 clock scout 另跑 100 次 post-fix probe，最小 provider-entry gap 为 **0.0302167 s**，无一次低于 0.03。batch/gate/policy/image/D1/
provider-error/Stage M focused 集 **114 passed / 3.48s**；root 全量 **1080 passed / 91.26s**。`src/ocrllm/README_ACTIVE_LIBRARY.md`
与权威状态已把 cadence 写成 high-resolution monotonic；module docstring 同步。提交前继续执行 `compileall`、plain import、diff/EOL 与 staged
review。本轮无网络/provider/付费调用，未修改 frozen `contracts/`、`worker/`、legacy、social media 或用户临时交接文件。

**下一步。** 回到 active 已建功能审计。优先检查 provider response/output 边界是否还有可公开复现的 false success、错误分类或付费后丢结果；
若没有更高价值缺陷，再按既有队列进入 Stage A 音频只读迁移调研。worker wake-up 理论窗口保留为明确边界，除非后续出现真实可重复证据，
不升级成线程协议重构。

## #032 — 2026-08-23：付费 pass 的 checkpoint 写入失败不再丢失调用证据

**原任务与假设修正。** 本轮先审计“draft 成功后，review 返回无效内容或拒绝识别时，是否会丢掉已付费 draft”。
两名只读 scout、主代理代码复核与公开 API 离线探针一致否定了这个假设：稳定 injected provider 与可离线 mock 的 exact DashScope 路径都会在 review
调用前原子保存已验证 draft。review 的 comment-only 无效回复或 refusal 会正确返回 typed error，带
`workflow_pass=review` 和 `provider_calls_attempted=2`，sidecar 只含 draft，不发布最终 Markdown；修复 provider 后 `resume=True` 只新调用
一次 review。因此没有增加 fallback success、重复 checkpoint 或 candidate 政策。refusal 后是否应该保留跨 source/request 的 draft 属于产品策略变更，
不在没有明确授权时假定。

**实际缺陷与两条路径。** 相邻的付费工作保全边界存在一个可确定复现的问题：provider 已返回有效内容、`calls_dispatched` 已增加，但
`persist_slot()` 的原子 replace 失败时，公开 `OUTPUT_WRITE_FAILED` 没有当前 pass 和已尝试调用数。路径一是在更外层统一改写所有
`OutputError`，但会把 preflight、最终发布和 slot checkpoint 三种不同时机混在一起；路径二只捕获 `persist_slot()` 抛出的 `OutputError`，
增加已有的安全字段后原样重抛。选择路径二：它不把写入失败伪装成识别成功，不改 error code/message，也不影响 provider 验证、
candidate 恢复或最终 publication。没有添加 `failed_model`，因为模型本身已成功，失败点是本地 checkpoint。

**失败优先证据与保全语义。** 已有首个 draft 状态写入失败回归先增加两个断言；修复前为 **1 failed / 0.46s**，
`details["workflow_pass"]` 直接缺失。修复后得到 `workflow_pass=draft` 和 `provider_calls_attempted=1`。新的 late-review 回归让两个 draft checkpoint
先成功，第三个 `consensus_review` 的 replace 失败；错误如实报告 pass 和三次调用，sidecar 仍精确保留 `draft`/`draft_2`，没有最终
Markdown 或遗留临时文件。这个回归不依赖网络、sleep 或付费 provider。三项定向回归 **3 passed / 0.41s**；image resume/M2/
recognize/Stage M/defect focused 集 **96 passed / 3.55s**。

**个人复核、验证与边界。** 主代理复核了 catch 的精确位置、原错误身份与安全 details 合并，并确认早期 slots 由原子 writer 保持完整。
项目环境 root 全量 **1081 passed / 90.18s**；`compileall`、plain import 与 diff/EOL 检查也通过，轻量 import 为 37 modules 且未加载 PIL/OpenAI/httpx/onnxruntime。本轮无网络/provider/
付费调用，未修改 frozen `contracts/`、`worker/`、legacy、social media 或用户临时交接文件。

**下一步。** 继续优先审计 active 已建功能中的 false success、付费工作丢失与恢复语义；若没有可公开稳定复现的缺陷，转入 Stage A
音频只读迁移调研。不把已否定的 review 失败假设重复建模，也不在没有产品决策时扩大 refusal 后的跨请求复用范围。

## #033 — 2026-08-23：拒绝不可 UTF-8 编码的 provider 伪成功

**原任务、假设修正与转向。** 本轮先检查 completed sidecar 与最终 Markdown 是否可在公开 `recognize()` 返回成功时互相不匹配。
主代理和两名只读 scout 从代码顺序与已有并发/恢复回归一致否定了这个假设：在已承诺的进程内边界，completed state 和 Markdown 都来自同一个不可变
`ProcessorOutput`；state 先原子写入，Markdown 后原子发布，任一写入失败都在构造 `RecognitionResult` 前抛错。中断可留下“新 state + 缺失/旧 Markdown”，
但不会返回伪成功，且 `resume=True` 会验证或重新发布。另一进程直接改文件属于已明确不承诺的跨进程事务；增加返回前的第二次 hash 也无法消除后续 race，
所以没有引入假交易层。

**可公开复现的相邻缺陷。** 离线 injected provider 返回 `"# Board\n\ud800\n"`时，孤立 surrogate 通过可见内容检查。memory-only 路径直接
返回一个无法严格 UTF-8 编码的“成功”结果；带稳定 `resume_identity` 和 output 的路径在第一次已付费调用后，于 slot SHA-256 计算处泄漏原始
`UnicodeEncodeError`，没有 typed error、workflow pass 或调用数。这种字符串可由 JSON 的 surrogate escape 产生，不需要假设文件系统故障。

**两条方案与最小修正。** 方案一是分别在 checkpoint hash、state serializer 和 Markdown writer 捕获编码错误；这会重复规则，把 provider 数据错误误报为
`OUTPUT_WRITE_FAILED`，并继续漏掉 memory-only 伪成功。方案二是在已有单一入口 `validate_provider_markdown()` 中对原始 exact string 做严格 UTF-8 可编码检查。
选择方案二。不可编码响应现在返回非重试的 `PROVIDER_RESPONSE_INVALID`，`reason=invalid_encoding`；既有 `call_vision_provider()`/`run_pass()` 自动补充 provider/model、
`workflow_pass=draft` 和 `provider_calls_attempted=1`。不使用 replacement character 修复内容，因为那会静默改写识别结果；也不增加 candidate advance 或 fallback success。

**失败优先证据。** 一个参数化公开回归同时覆盖 memory-only 与稳定 checkpoint provider + output。修复前稳定为 **2 failed / 0.45s**：前者根本不抛错，
后者泄漏 `UnicodeEncodeError`。修复后两者均只调用 provider 一次并返回上述 typed error；output 变体的目录中无 Markdown、sidecar 或 temp。provider/resume/M2/
output/Stage M focused 集 **141 passed / 6.43s**；项目环境 root 全量 **1083 passed / 90.88s**。

**个人复核与边界。** 主代理复核了校验顺序、error detail 合并、candidate 政策、memory/file 两条路径、原值不修复原则与两份 scout 结论。
公开回归已覆盖 shared validator，不再增加只调私有 helper 的重复测试。历史 CRLF 测试文件在 patch 后恢复为纯 CRLF；不改仓库 `* -text` 策略。本轮无网络/
provider 真实调用或付费调用，未修改 frozen `contracts/`、`worker/`、legacy、social media 或用户临时交接文件。

**下一步。** 继续检查已建 active provider/output 边界，尤其是大回复、多 pass 组合和 typed error 细节是否还能出现 false success 或付费证据丢失；
若没有稳定可公开复现的缺陷，按既有优先级转入 Stage A 音频只读迁移调研，不继续为已否定的两文件事务假设扩展架构。

## #034 — 2026-08-23：completed state 超限时保留全部付费调用证据

**原任务与限额结论。** 本轮审计大型 provider Markdown 在 memory-only、checkpoint 和多 pass 图像识别中是否会无界放大。代码、测试、现行计划与两名只读
scout 确认：公开契约没有 provider 回复的 byte/character cap；DashScope 请求只有 `max_completion_tokens=16_384`，并拒绝
`finish_reason=length`；16 MiB 是 resume-state 文件限额，不是 Markdown 限额。memory-only 结果和最终 `.md` 并没有同样上限。用16 MiB 除以最多七份文本或根据 token
猜一个新 cap，都无法正确处理 JSON escape、metadata 与合法大型 OCR 结果。因此没有从实现限额反推新公开政策，也没有截断或静默缩短回复。

**可确定复现的实际缺陷。** 每个成功 pass 先把完整 Markdown 存入 partial slot；completed state 又同时带全部 slots 和最终 assembled result。因此某个回复可以让
partial state 低于 16 MiB，却让 completed state 因最终 Markdown 的额外副本超限。原有路径会正确抛 `OUTPUT_WRITE_FAILED`、保留 partial sidecar 且不发布 Markdown，
但 error details 是空的，已付费调用数在最终 state materialization 边界丢失。用真实 serializer 动态把限额设为刚保存的 partial bytes + 1，可在不分配巨大字符串、
不硬编码 JSON overhead 的情况下稳定触发。失败优先单例为 **1 failed / 0.49s**：`provider_calls_attempted` 缺失。

**两条路径与选择。** 方案一是在 shared validator 增加 Markdown size cap，提前拒绝；它没有可辩护的数值，会改变 memory-only 与 injected-provider 契约。方案二保持已有
16 MiB state 保护和 fail-closed 语义，只在 completed-state save 抛出 `OutputError` 时补充当前 invocation 的总 provider calls。选择方案二。没有补 `workflow_pass`，因为 provider passes
全部成功，失败点是本地 final-state 组装；造一个假 pass 名会让调用者误以为某次模型调用失败。也没有从 completed state 删除 slot bodies：那会改变已付费中间证据且无法
解决多 pass partial state 本身超限。

**调用计数修正与个人复核。** 初版直接取 `metadata["provider_call_count"]`，主代理与 scout 复核后在扩大验证前撤回：该字段只统计最后成功的 candidate，会丢失先前失败模型的
调用。最终实现优先严格求和已有 `model_attempts[*].provider_calls_attempted`，只在没有完整 ledger 时使用已验证的非负 `provider_call_count`。回归同时覆盖：初次一次调用失败报 1；
复用 partial draft 后再次超限报当次 0 且不重新调 provider；quota model 两次后切换 recovery model 两次的 completed-state 失败报总数 4，partial state 仍保留 recovery 的 draft/review slots。
测试编写期间首先直接改了 module limit，紧随的定向集因限额泄漏出现 **3 failed, 2 passed**；改为 `monkeypatch.setattr()` 后 fixture 会恢复全局值，没有把这个测试隔离问题隐藏成产品失败。

**验证与边界。** 最终六项定向回归 **6 passed / 0.56s**；image resume/M2/Stage M/output/provider focused 集 **120 passed / 4.37s**；项目环境 root 全量
**1085 passed / 89.34s**。`compileall`、plain import 与 diff/EOL 检查也通过，轻量 import 为 37 modules 且未加载 PIL/OpenAI/httpx/onnxruntime。本轮无网络/provider 真实调用或付费调用，未修改 frozen
`contracts/`、`worker/`、legacy、social media 或用户临时交接文件。

**下一步。** 继续优先审计 active 已建功能；若没有新的稳定缺陷，不直接跳过当前前置实现 Stage A，而是先审计其明确前置 Stage 2 vision/audio provider split。Stage M 的付费 live exit smoke 仍未授权，
不用 offline 结果假装它已完成。

## #035 — 2026-08-23：取消无消费者的 provider split 脚手架，音频改为 A1/A2 两个可执行切片

**原子任务与假设修正。** 本轮只读审计 Stage 2 配置拆分是否真是 MP3 识别的必要前置，不开始音频实现，不修改 frozen `contracts/` / `worker/`，也不把 Stage M 尚未授权的付费 live gate 写成已完成。开始时的两个候选是：一，按旧计划先增加通用 `ModalityBinding`、vision/audio 两套 binding 和“已配置但不可用”的 audio capability；二，保留已验证的 image 配置，在首个真正能识别短 MP3 的切片中再增加专用 audio binding。代码与 legacy 证据使原假设发生变化：独立音频配置确实必要，但 standalone provider split 不是必要产品能力。

**代码证据。** 当前 `Config.provider`、`vision_model`、`image_mode`、`local_ocr` 是一组共同校验的 image 契约；local OCR 也不能自然塞进“provider + model”的通用二元组。`get_capabilities()`、resume identity、候选模型替换和多个 image consumer 都直接读取这组字段，frozen worker 仍按旧形状构造 `Config`。先增加新旧两套 vision 形状会引入 resolver、冲突判断、`dataclasses.replace()` 漂移和一轮公共迁移，却没有新增可执行能力。松散增加 `audio_provider` / `audio_model` 虽然改动少，但会把 `Config` 变成容易出现半配置的字段袋，也没有形成清楚责任边界。

**legacy 音频证据。** 三名只读 scout 与主代理逐行复核一致确认：short ASR 是同步 multimodal 请求，FileTrans 是 upload + submit task + poll + download 的异步协议；默认 model ID 分别是 `qwen3-asr-flash` 和 `qwen3-asr-flash-filetrans`。两者可共用 DashScope 账户设置，但不能用一个 model 字段或名称 substring 推断协议。legacy 已出现过 task ID 未及时保存、弱 source identity、修复时按当前配置重新切片、已付费分段在取消时丢失、非原子发布和 Windows 长路径 sidecar 等真实问题；这些是 A2 的行为约束，不是现在提前复制 sidecar / retry framework 的理由。Google 音频又是另一条 chunked native-multimodal 路径，因此更不能用通用 binding 假装所有 provider 协议相同。

**决策与文档改动。** 选择路径二。Stage 2 不再作为 standalone scaffolding release：保留 proven image 公共字段；Stage A1 在 short-MP3 consumer 同一提交中加入 exact、immutable、secret-redacted 的 audio-specific binding，只包含当时真正消费的 provider/credential/short-model 身份；Stage A2 实现 FileTrans 时再增加独立 long-model 身份和 task resume。A1 不允许静默切到长协议，A2 不允许从 model 名猜协议。capability 也随可执行切片逐项变化：A1 只可能关闭 DashScope short-audio 和 short-MP3 两项，其余 audio/video 继续 deferred。已同步更新两个 active plan、`ACTIVE_STATE_AND_RULES.md`、`MIGRATION_STATUS.md` 与 `START_HERE.md`；没有增加代码、dependency extra 或不可用 public type。

**个人复核、验证与边界。** 主代理没有照抄 scout 对具体 class 名的建议，而是对照当前 `Config` consumer、207 处测试构造、capability registry、legacy short/FileTrans 调用和恢复历史后收敛决策。旧计划里“先让 caller 表达 unavailable audio”与“新结构必须有 consumer”直接冲突，现已消除。Google image 后续也不再依赖音频抽象；它必须由自己的 image consumer 证明 resolver 设计。config/capability/import 定向集 **51 passed / 0.53s**，项目环境 root 全量 **1085 passed / 88.64s**，diff/EOL whitespace 检查通过。pytest 仍报告既有 `.pytest_cache` 写入权限 warning，但不影响测试结果，也没有为消除 warning 修改目录权限。Stage M 付费 DashScope smoke 仍然开放，因此 A1 仍未获准开始。本轮无网络、provider 或付费调用，未修改 active Python、legacy、social media 或用户临时交接文件。

**下一步。** 回到已建 active surface 的缺陷优先队列。若没有更高价值的稳定缺陷，先向 maintainer 请求 Stage M 付费 live smoke 的明确预算；只有 Stage M 真正退出后，才为 A1 写 failing-first tests，并让 audio binding 与首个 short-MP3 consumer 同时出现。A2 的 FileTrans、长音频断点续传和分段 checkpoint 必须等 A1 契约稳定后再做。

## #036 — 2026-08-23：provider 方法发现失败不再虚报一次调用

**原子任务与假设修正。** 本轮先审计 active public error boundary 中 caller-owned object 抛出异常时，是否泄漏原始异常或丢失已完成工作。同步 origin、重读权威状态、入口文档、package 规则与近期日记后，确认 batch iterable 普通异常已经有明确的 typed terminal outcome，不能重复修。随后比较两个仍可能有问题的入口：progress/cancellation callback 与 injected provider 的 identity/method discovery。两名只读 scout 分别审计，两条路径都找到真实问题；本轮按原任务只关闭 provider discovery 的错误计数，不把 resume cancellation 混入同一提交。

**失败证据。** injected provider 可用动态属性提供 `recognize_images`。若属性 getter 在方法发现阶段抛 `RuntimeError`，`call_vision_provider()` 原先先把它映射为 `PROVIDER_RESPONSE_INVALID`；外层 `run_pass()` 无法区分“发现方法失败”和“已经进入 provider callable 后失败”，统一增加一次 `provider_calls_attempted`。公开 API 因此在零 dispatch、零 provider method call 时返回 `workflow_pass=draft`、调用数 1，并在 `model_attempts` ledger 也记 1。已有测试只断言 typed/redacted，没有检查费用证据。新增断言后旧实现稳定 **1 failed / 0.38s**。

**两条方案与选择。** 方案一保留 `ProviderError`，在底层附加“尚未 dispatch”的私有标记，再让 processor 特判；这会增加跨层控制元数据，还要解释 marker 是当前 pass 还是整个 invocation 的计数。方案二把 required-method lookup failure 与已有 non-callable branch 一样归类为 `ConfigError(CONFIG_INVALID)`。选择方案二：一个无法稳定暴露协议必需方法的对象没有满足 provider 结构契约；方法发现也没有进入 provider，因此 zero-call 语义直接由现有 ConfigError 分支表达。真正进入 callable 后抛出的普通异常仍是 provider failure 并计一次调用，不改变 retry/disposition 规则。

**实现、复核与验证。** `call_vision_provider.py` 只在 `getattr(provider, "recognize_images")` 抛普通 `Exception` 时返回固定、无 caller text 的 `CONFIG_INVALID`；不捕获 `KeyboardInterrupt` / `SystemExit`，不增加 helper、marker 或公共类型。公开回归改为同时证明：错误类型和 code 正确；`workflow_pass=draft`；直接调用数为 0；唯一 candidate ledger 为 `fix_request` 且调用数 0；getter 异常中的 sentinel 不进入 traceback。单例修后 **1 passed / 0.19s**，recognize/provider-error/Stage M 定向集 **59 passed / 1.45s**。主代理逐行复核了 lookup、dispatch、validator 与 candidate accounting 的先后关系，确认 built-in/injected callable 的实际请求路径没有变化。

**并行审计的新发现（尚未修复）。** completed image resume branch 在复用已有 final state 前没有检查 `Config.cancellation`；已经 set 的 Event 会得到成功结果而不是 `CANCELLED`，虽然不会新增 provider 调用。另有两个独立边界：batch 在 sibling failure 后 settle 已 dispatch future 时会把 `BaseException` 误标成“未尝试”；`Config.progress` 被公共 API 接受并称为 direct-Python convenience，却在 active non-worker 代码中完全未读取。后两项涉及 process-control 传播和公共字段去留，不能顺手扩展。本轮将 completed-resume cancellation 记入权威 open debt，下一轮先写公开失败回归。

**完整验证与边界。** 项目环境 root 全量 **1085 passed / 89.69s**；`compileall -q src tests` 通过；isolated plain import 为 37 modules，未加载 PIL、pypdfium2、OpenAI/httpx、ONNX Runtime、RapidOCR、OpenCV 或 NumPy；diff/EOL whitespace 检查通过。本轮没有网络、provider 真实调用或付费调用；未修改 frozen `contracts/`、`worker/`、legacy、social media 或用户临时交接文件。

**下一步。** #037 只处理 completed image resume 的 pre-set cancellation：先证明 completed state 与 provider call count 不变，再在复用点加入最晚且明确的一次 cancellation check。不要把检查全局提前到 config snapshot 之前，也不要趁机实现 progress protocol 或修改 batch 的 process-control 异常政策。

## #037 — 2026-08-23：completed resume 不再绕过调用前取消

**原子任务与假设。** 本轮只修 iteration #036 已记录的 completed image resume cancellation 缺口：caller 在调用前已经 set Event 时，不允许因为 final state 可复用而返回 success；同时必须保留已付费 state 与 Markdown，之后一次未取消的 resume 仍应零调用复用。同步 origin 并重读权威状态、入口、package 规则与近期日记后，比较两条路径：一是在 public operation 入口统一检查取消；二是在 completed state validation 完成后、复用结果进入 output validation/publication 前检查。选择路径二，避免改变 invalid config/source/path/state 的既有错误优先级，也不把 caller callback 提前到 built-in config snapshot 之前。

**失败优先证据。** 公共回归使用真实 completed-state 流程：第一次 fake DashScope 识别成功，保存 final sidecar 与 Markdown bytes；第二次用已经 set 的 `threading.Event` 和完全相同 request 执行 `resume=True`；第三次用未取消 config 再 resume。修复前第二次稳定 **1 failed / 0.97s**，因为没有抛 `Cancelled`，而是直接返回 saved success。这个测试不是只调用 private helper：它经过 source snapshot、output claim、request fingerprint、state parser 与 public error boundary。

**两名只读 scout 与个人复核。** topology 审计确认 completed branch 是 DashScope、stable injected provider、local OCR 和 batch item 共同使用的 `_recognize()` 路径；单独增加 batch case只会重复同一个 invariant。test 审计要求同时证明：provider 总调用保持 1；取消前后 state/output bytes 完全相同；取消错误 code 为 `CANCELLED`；之后未取消 resume 返回相同 Markdown/output path，仍不新增调用。主代理采纳了“先 validation、后 cancellation”的更精确位置，没有把 check 放进 `reuse_image_resume_state()`，因为该文件只负责 state identity/digest validation 与 reconstruction。

**最小实现与边界。** `recognize.py` 只在 completed `reuse_image_resume_state()` 成功返回后 lazy import 并调用现有 `raise_if_cancelled(cfg.cancellation)`。因此 corrupt/mismatched completed state 仍先报告 resume error；有效 state 遇到取消时在 output validation或 publication 前退出。没有删除、重写 sidecar/Markdown，也没有触碰 provider、candidate、checkpoint schema、worker 或 contract。单例修后 **1 passed / 0.34s**；image resume/M2/defect/batch focused 集 **64 passed / 3.62s**。

**新发现（尚未修复）。** partial v2 state 可能已经保存所有当前 workflow slots，却还没有 final result；`run_pass()` 可以全部从 slot reuse 返回，整个 processor 不进入 provider start gate，随后 assemble/publish success。completed 分支的新 check 不覆盖它。该路径需要先构造真实 partial state 并明确 validation/output-conflict 后的 cancellation 顺序，不能把本轮一行检查扩大成“所有 resume 已修”。权威 open debt 已改为这个更窄的剩余问题。batch settle 对 `BaseException` 的误标和完全未消费的 `Config.progress` 仍保持独立，不在本轮夹带。

**完整验证与边界。** 项目环境 root 全量 **1086 passed / 89.59s**；`compileall -q src tests` 通过；isolated plain import 为 37 modules，未加载 PIL、pypdfium2、OpenAI/httpx、ONNX Runtime、RapidOCR、OpenCV 或 NumPy；diff/EOL whitespace 检查通过。本轮无网络、provider 真实调用或付费调用，未修改 frozen `contracts/`、`worker/`、legacy、social media 或用户临时交接文件。

**下一步。** #038 审计 all-slots-reusable partial checkpoint：先证明预设取消是否会组装并发布 final output，再决定在 partial identity/conflict validation 后统一检查一次，还是在 slot replay 边界逐次检查。不得重新支付已保存 slots，也不得因取消破坏 partial state。

## #038 — 2026-08-23：all-slots partial resume 取消时不再发布伪成功

**原子任务与假设。** 本轮只审计 partial v2 checkpoint 已经包含当前 workflow 所有必需 slots、但还没有 final result 时，预设取消能否阻止零调用 assemble/publish。同步 origin、重读权威状态、入口、package 规则与近期日记后，比较两条路径：一，在每个 `run_pass()` 命中 reusable slot 时检查取消；二，在 `_recognize()` 完成 partial identity 与 output-conflict validation 后、创建 `ImageSlotCheckpoint` 和进入 candidate processing 前检查一次。选择路径二，因为 cancellation 是 operation policy，不应重复塞进每个 slot；而且它能在候选 model 不匹配、可能重新 dispatch 前统一停止。

**真实 partial 构造与失败证据。** 回归没有手写 JSON。默认一-pass DashScope workflow 首次 provider 返回有效 draft 后，真实 `ImageSlotCheckpoint.persist_slot()` 先原子写入 `status=partial`、空 final Markdown、唯一 `draft` slot；测试只让随后的 completed-state save 抛 `OutputError`。由此得到“全部所需付费 slots 已存在、final result 尚未写入”的真实 v2 sidecar。恢复正常 saver 后，用已经 set 的 Event 做 `resume=True`。旧实现稳定 **1 failed / 0.45s**：没有抛 `Cancelled`，而是复用 draft、写 completed state、发布 Markdown 并返回 success，整个过程 provider 调用数仍是 1。

**两名只读 scout 与个人复核。** topology 审计确认 partial state 可以合法保存任意已完成 slots；reusable slot 必须 provider/model 精确匹配，命中时 ledger 记零调用并在 `call_vision_provider()` 前返回。若把 check 放到 `run_pass()`，会重复检查，并且 provider/model resolution 已经开始；一次 orchestration check 更早、更清楚。test 审计建议用第二次 state replace 失败造 partial；主代理选择现有 saver 函数 seam，同样保留第一次真实 partial 原子写，只让 completed state 失败，减少对 writer 内部 replace 次数的耦合。local OCR production 不会创建 slot partial，且本身已有 backend 前 cancellation；统一 orchestration check 对结构有效的 partial OCR state 仍安全。

**最小实现与回归保证。** `recognize.py` 把现有 `raise_if_cancelled` lazy import 提到 `_recognize()` 的局部 import 区，completed 分支继续在 state identity/digest validation 后检查；partial 分支新增一处调用，位置在 identity validation 与 existing-output conflict error 之后、`seeded_slots`/checkpoint/processor 之前。回归证明取消时：code 为 `CANCELLED`；provider 总调用保持首次的 1；final Markdown 不存在；partial sidecar bytes 完全不变。随后未取消 resume 复用同一 draft，零新增调用并发布相同 Markdown 与 completed state。completed + partial 两条取消回归 **2 passed / 0.34s**；image resume/M2/Stage M/defect focused 集 **66 passed / 3.30s**。

**新边界与下一优先级。** candidate ledger 无需在取消错误中伪造：取消发生在 candidate loop 前，真实新调用数就是 0，已付费 slot 仍留在 sidecar。并行审计遗留的下一个明确问题是 `recognize_batch()` 在 sibling 已失败后 settle 其他已 dispatch futures 时捕获 `BaseException`，可能把 `KeyboardInterrupt` / `SystemExit` 改写成“未尝试”的 `CANCELLED`。这会同时影响 process-control 传播与事实描述，已记入权威 open debt；`Config.progress` 的公共字段去留仍是另一项需要产品决定的简化任务。

**完整验证与边界。** 项目环境 root 全量 **1087 passed / 90.59s**；`compileall -q src tests` 通过；isolated plain import 为 37 modules，未加载 PIL、pypdfium2、OpenAI/httpx、ONNX Runtime、RapidOCR、OpenCV 或 NumPy；diff/EOL whitespace 检查通过。本轮无网络、provider 真实调用或付费调用，未修改 frozen `contracts/`、`worker/`、legacy、social media 或用户临时交接文件。

**下一步。** #039 用 Event 协调一个 batch item 先产生普通 typed failure、另一个已 dispatch item 再抛 process-control exception，先确认当前 settlement 是否吞掉它以及如何保留其他已完成 outcomes。不要把普通 cancelled Future、caller cancellation 和 `BaseException` 混成一种状态。

## #039 — 2026-08-23：batch settlement 不再吞掉进程控制异常

**原子任务与假设。** 本轮只修 `recognize_batch()` 在一个 item 已经返回 typed failure 后，settle 其他已 dispatch future 时错误捕获所有 `BaseException` 的问题。同步 origin、重读权威状态、入口、package 规则与 #038 日记后，比较两条路径：一是为了始终返回 outcomes，给 process-control failure 发明额外元数据；二是只把 `concurrent.futures.CancelledError` 解释成“未尝试”，其余非 `OCRLLMError` 按正常并行循环的既有政策传播。选择路径二，因为它不扩大公共 API，也不会把已经运行的工作写成未尝试。

**失败优先证据。** 新回归通过公开 `recognize_batch()` 和两个 Event 固定顺序：两个 provider call 必须都已进入；`failure.png` 等待另一项开始后先抛 `ProviderError(PROVIDER_UNAVAILABLE)`；测试只在 monkeypatch wrapper 确认 `_settle_dispatched_outcomes()` 已经开始后，才允许另一个运行中的 call 抛预先创建的 `KeyboardInterrupt` 或 `SystemExit`。因此结果不依赖线程快慢。旧实现两例都稳定 **DID NOT RAISE，2 failed / 0.38s**，证明异常被改写成了 `CANCELLED`。

**两名只读 scout 与个人复核。** topology scout 确认正常 parallel loop 只捕获 `OCRLLMError`，其他 `BaseException` 会进入外层 abort/cancel/re-raise；worker future 会保存并由 `result()` 原样重抛异常；`ThreadPoolExecutor.__exit__()` 使用 `shutdown(wait=True)`，所以传播异常不会放弃仍在运行的线程。test scout 给出相同的 Event 协调方案，并指出现有 gate-abort 测试虽然返回 `CANCELLED`，却不能稳定证明 `Future.cancel()` 成功后的 `CancelledError` 分支。主代理逐行复核实现与测试，采用公开 process-control 回归，并补一个只针对 settlement helper 的 cancelled Future 小测试；没有替换 executor，也没有新增状态类型。

**最小实现与行为边界。** `_settle_dispatched_outcomes()` 在函数内 lazy import `CancelledError`，保留先处理 typed `OCRLLMError` 的分支，只把原先的 `except BaseException` 收窄为 `except CancelledError`。真正取消、尚未开始的 future 仍得到原有 `CANCELLED` 和“未尝试”信息；已运行 future 的 `KeyboardInterrupt`、`SystemExit` 以及意外编程错误不再被伪装。两条参数化回归还断言传播的是 provider 抛出的同一个异常对象；cancelled Future 回归证明窄分支仍有效。batch 单文件 **16 passed / 0.92s**，batch + defect register 定向集 **39 passed / 2.61s**。

**验证中的小问题。** 第一次扩大定向集时命令误写了不存在的 `tests/test_recognize_errors.py`，pytest 因找不到文件而没有收集测试。这不是代码失败；删除错误路径后重新运行真实的 batch 与 defect-register 文件并全部通过。项目环境仍报告 `.pytest_cache` 无写权限警告，不影响测试结果。

**完整验证与边界。** 项目环境 root 全量 **1090 passed / 90.81s**；`compileall -q src tests` 通过；isolated plain import 为 37 modules，未加载 PIL、pypdfium2、OpenAI/httpx、ONNX Runtime、RapidOCR、OpenCV 或 NumPy；diff/EOL whitespace 检查在提交前执行。本轮无网络、provider 真实调用或付费调用，未修改 frozen `contracts/`、`worker/`、legacy、social media 或用户临时交接文件。

**下一步。** #040 审计公共 `Config.progress`：先查实际调用者、文档承诺和 direct-Python 使用价值，再在“删除无消费者字段”与“实现一个明确、很小的 callback”之间做产品决定。worker progress events 属于已经冻结的独立边界，不得为了保留一个未使用字段而扩建通用 progress 框架。

## #040 — 2026-08-23：删除从未生效的 `Config.progress`

**原子任务与假设。** 本轮只决定 direct-Python `Config.progress` 的去留，不顺手设计 progress event 系统。同步 origin、重读权威状态、入口、package 规则与 #039 日记后，先假设删除会形成真实的构造器兼容性变化，因此必须证明调用者、文档承诺和 legacy 价值；同时不能因为 worker 已经有 progress wire event，就把两个边界混在一起。

**三名只读 scout 与仓库证据。** active-surface audit 确认字段在早期 `0.1.0` image contract commit 中以 `object | None` 占位加入，之后只被 `dataclasses.replace()` 原样携带；active non-worker 没有一次读取，仓库唯一传值是 repr 保密测试，也没有 positional `Config(...)` 调用、示例、tag 或 GitHub release。compatibility audit 确认删除会让未知 private source-install caller 的 `progress=` 立即报 `TypeError`，也理论上会移动后续 positional slot；这项未知风险无法完全排除，但保留 accept-and-ignore 会继续制造假能力。legacy audit 发现老 board 的进度确实对 GUI 有用，但它在预处理前只报一次、每批 provider dispatch 前就增加计数，最后一批刚开始时就可能显示 100%；content streaming 又是另一条 callback。active workflow 还包含 draft/review/scout/candidate/resume 与并行 batch，没有可直接复用的真实单位。

**两条路径与选择。** 路径一删除字段，让显式使用者立即知道当前没有 direct progress；路径二实现“小 callback”，但即使只报开始/结束，也必须决定 callable 类型、线程、callback 异常、paid work 后失败、resume reuse、candidate fallback 和 batch item identity。选择路径一：当前没有消费者，package 仍是无 release tag 的 `0.1.0`；为了保留占位而发明这些政策正是过度设计。`Config.cancellation` 有真实调用和测试，继续保留。未来 A1/A2 audio 出现可测量 chunk/stage 后，可以用明确的新名字和 typed contract 再引入，不继承这个空字段。

**失败优先与最小实现。** 回归先把原先混合的 repr 测试拆成 cancellation-only secrecy，并新增公共 surface 断言：`Config()` 不得有 `progress` 属性，`Config(progress=object())` 必须拒绝。旧实现稳定 **1 failed, 1 passed / 0.22s**，失败点正是属性仍存在。实现只从 `config.py` 删除一行 dataclass field；没有新增 helper、event、Protocol、callback 调用点或兼容 shim。修后 config 文件 **36 passed / 0.15s**。

**文档与个人复核。** 权威状态把 open debt 改成已删除决定；`MIGRATION_STATUS.md` 记录 pre-release public boundary 变化；target design 删除字段、repr 承诺和“progress callback 是 convenience”的假声明；go/no-go 删除 Config repr 与 fingerprint 中的 progress。worker `ProgressEvent`、worker tests 和 frozen `contracts/`/`worker/` 均未修改。主代理逐行复核后又找到 target design 较后位置的第二条 fingerprint 旧句并同步修正。direct/batch recognition、capability、DashScope、local OCR、config 与 worker adapter 定向集 **197 passed / 2.39s**。

**新发现（未夹带修复）。** `Config.cache_dir` 与 progress 类似，目前只有字段、path validation 和 snapshot copy，没有 active adapter、local OCR、worker 或 caller 读取；相反 `temp_dir` 确实由 image snapshot 使用。权威状态已把 `cache_dir` 记为下一项独立审计，不能因为本轮已经做一次构造器删除就未经 history/packaging 检查一起移除。PDF 字段有明确的未来 PDF slice 语义，也不在本轮混入。

**完整验证与边界。** 项目环境 root 全量 **1091 passed / 91.99s**（使用 `-p no:cacheprovider`，没有此前 cache 权限警告）；`compileall -q src tests` 通过；isolated plain import 仍为 37 modules，未加载 PIL、pypdfium2、OpenAI/httpx、ONNX Runtime、RapidOCR、OpenCV 或 NumPy；diff/EOL whitespace 检查通过。本轮网络只用于 Git 同步与只读检查 fork/upstream 的 GitHub release 列表（两者均为空）；没有真实 provider 或付费调用。未修改 frozen `contracts/`、`worker/`、legacy、social media 或用户临时交接文件。

**下一步。** #041 只审计 `Config.cache_dir`：确认原始意图、package/docs 承诺、local OCR/provider cache 是否已有外部约定，并比较立即删除与在真实 consumer 到来前明确拒绝。不要扩大成一次清空所有未来 PDF/audio 字段的重构。

## #041 — 2026-08-23：删除没有消费者的 `Config.cache_dir`

**本轮英文自我任务。** Atomic task: decide and correct the unused public `Config.cache_dir` field without disturbing the working `temp_dir` snapshot path or inventing cache behavior. Success means history、依赖行为、legacy 价值和调用者都已核实；旧行为先被公开回归证明错误；最小修改、文档、完整验证、提交与 origin 推送全部完成。这样做的原因是：成熟的配置项必须影响真实行为，但不能为了保留字段而创造比 legacy 更宽的缓存功能。

**开工假设、两条路径与选择。** 同步并重读权威状态、入口、package 规则和 #040 日记后，先把 `cache_dir` 当作可疑的 pre-release placeholder，而不是直接认定无用。路径一是把它接到某个真实 backend；路径二是删除字段和虚假的平台缓存承诺。只有找到一个已经安装、已经由 active slice 使用、并且无需发明下载与并发政策的 consumer，才应选择路径一。三项独立只读审计和主代理复核都选择路径二。

**证据与没有扩建的原因。** 全树只有 `config.py` 的字段声明和 path validation 读取它；snapshot 只是 dataclass copy。没有 tracked keyword caller、positional `Config(...)` caller、example、release tag、worker DTO、sidecar、fingerprint、adapter 或 local OCR consumer。legacy 也没有通用 cache 配置：PDF/media 中间物使用 temp，模型目录记录使用固定位置，其他 cache 是进程内数据。active DashScope catalog 已经用按 base URL 隔离的 600 秒内存 TTL，改成磁盘持久化会额外要求锁、过期、权限和跨进程规则。

RapidOCR 3.9.2 虽然提供 `Global.model_root_dir`，但 wheel 已自带默认 ONNX 模型；把一个空的通用目录传给它会在 engine 初始化时尝试下载模型，还会产生并发下载完整性问题，违反 active local OCR 的 `network_call_count=0` 边界。ONNX Runtime 的 optimized-model path 没有由 RapidOCR 暴露给本库；OpenAI client 和 Pillow 也没有对应的请求级磁盘 cache。修改全局环境变量还会让并行调用互相影响。因此本轮不把一个无效字段改造成隐式联网功能；未来若真要控制模型位置，应由可执行 adapter 提供明确的、预置模型且禁止隐式下载的专用设置。

**失败优先与最小实现。** 新回归 `test_config_does_not_expose_unimplemented_cache_directory` 先断言默认实例没有该属性，并断言传 `cache_dir=` 得到 Python `TypeError`。旧实现按预期 **1 failed / 0.21s**，失败点是 `hasattr(Config(), "cache_dir")` 仍为真。随后只删除 dataclass 字段和对应 path validation；同一回归变成 **1 passed / 0.09s**。没有修改有效的 `temp_dir`、catalog TTL、RapidOCR 初始化、frozen contracts/worker、legacy 或 social media。

**文档边界。** 权威状态和迁移状态把此次 constructor 变化记录为 pre-release reduction；target design 删除了不存在的平台 cache 承诺。仓库在 #015 已用英文记录用户对 Google image/audio robustness 测试的直接授权、实时 model catalog、常见错误源，以及 legacy Windows 超约 260 字符路径的真实失败，因此本轮无需重复或另造一份 repo memory。下一步先完整验证；结果与提交信息在本轮结束前补入这里。

**验证中的命令错误。** 第一次扩大定向集时写了不存在的 `tests/test_local_ocr.py`，pytest 因找不到文件而没有收集测试。这不是实现失败；先用 `rg --files tests` 找到真实文件名，再运行 config、import、local OCR、real RapidOCR、validation 和 image recognition 集，结果是 **132 passed / 10.29s**。没有为了让命令看起来成功而隐去这次错误。

**完整验证与边界。** 项目环境 root 全量 **1092 passed / 92.03s**；`compileall -q src tests` 通过；isolated `import ocrllm` 本次只加载 root package module，且没有加载 PIL、pypdfium2、OpenAI/httpx、ONNX Runtime、RapidOCR、OpenCV 或 NumPy；diff/EOL whitespace 检查通过。本轮网络只用于 Git 同步和最终 push，没有真实 provider 或付费调用。修改范围是 `Config` 两行删除、一条公开回归以及三份 current/design/migration 文档和本日记；用户未跟踪的临时交接文件保持不动。

**下一步。** 不把这次删除机械复制到 `pdf_mode`、`pdf_pages`、`pdf_password`、`pdf_allow_partial`。它们共同表达尚未启动的 PDF slice，去留必须作为一个整体核对 target API、现有 constructor 测试和 Stage A/PDF gate；若下一轮没有更高优先级的已建功能缺陷，只做这组字段的只读产品审计，不顺手实现 PDF 或一次删四个字段。

## #042 — 2026-08-23：把 PDF 配置推迟到可执行 PDF slice

**本轮英文自我任务。** Atomic task: decide whether the four dormant PDF-specific `Config` fields should remain in the active pre-release constructor before the PDF slice exists, without implementing PDF or repeating one-field-at-a-time cleanup. Success means current consumer、测试、历史和 legacy 行为都已核实；若有现行缺陷，先失败后修复；future PDF gate 保留，但没有把未证明的选项伪装成当前 API；最后完整验证、中文日记、提交并推送。

**开工假设与仓库复核后的改变。** 起初把四个字段视为一个已经研究好的 coherent future contract，倾向保留并在 image call 时拒绝。同步 origin、重读权威状态、入口、package 规则和 #041 后，先比较两条路：①保留四个 validator，再加 modality-specific rejection；②整体删除，等第一个 executable PDF slice 再定义。三名只读 scout 中，test scout 起初支持①，因为这样不改 constructor；history 和 active-topology scout 支持②。主代理继续查 `5018ad0`、current `recognize.py`、fingerprint、tests、target/go-no-go 和 legacy 后改变选择，采用②。

**改变决定的证据。** 四个字段从初始 image-contract commit 一起进入 `Config`，之后没有 active reader；image-only `recognize()` 会静默忽略每个非默认值并照常调用 provider，resume fingerprint 也刻意不包含它们。没有 PDF router、processor、caller、example、tag 或 release。更重要的是，旧计划并非 legacy 的准确迁移：legacy PDF 使用 contiguous `(start, end)` page range 和 `need_formula` 路由，没有 password 参数，也没有 caller-controlled `allow_partial`；任意有序页、encrypted password 和 opt-in partial success 都是更宽的新产品决定。当前 Stage A/PDF 均未开始，为这些假设维护 validator 再加一个只能报错的 runtime layer，会增加理解成本和未来改名成本。

**失败优先证据与最小实现。** 新参数化回归把 `pdf_mode`、`pdf_pages`、`pdf_password`、`pdf_allow_partial` 当作同一个 dormant boundary：默认实例不应有属性，旧 keyword 应由 Python 拒绝。旧实现按预期 **4 failed / 0.25s**，四例都在 `hasattr(Config(), field_name)` 为真。实现删除四个 dataclass fields、`_PDF_MODES`、page normalization、password text validator 和关联 object assignment；没有增加新文件或 image runtime branch。测试只移除原先证明 future PDF normalization/secret 可以混入 image call 的断言，保留真实 provider/extra/cancellation/language/timeout/resume/secret coverage。修复后的定向集 **10 passed / 0.34s**。

**编辑中的小问题。** 第一次把 source 和两份 test cleanup 合在一个 patch 时，一段参数列表上下文不精确，`apply_patch` 整体拒绝且没有部分修改。随后按 source、config tests、image secrecy tests 拆成小 patch 并逐段复核。本轮没有为追求“一个 patch 成功”而绕过上下文检查。

**文档和未来边界。** 权威状态与迁移状态记录 pre-release API reduction；target design 和 go/no-go 仍保留 PDFium、lazy dependency、资源限制、typed errors、原子 checkpoint/repair、序列化 native calls 等值得迁移的约束，但不再把四个字段、encrypted PDF 或 caller-controlled partial success 写成已决定的当前合同。未来 PDF worker 必须在 direct Python slice 证明最小设置之后，用新协议版本新增 concrete request，不能修改 frozen image protocol。`profile`、`input_languages`、`output_language` 保留，因为 active image recognition 和 fingerprint 确实消费它们。

**下一步。** 先运行完整 config/image 定向集和 root suite，再做 compile/import/diff 检查。若全部通过，本轮提交只包含 active Config/tests、current authority/migration/target/go-no-go 和本日记；不修改 frozen `contracts/`、`worker/`、legacy、social media 或用户临时交接文件。

**个人复核和完整验证。** 主代理逐行复核 111 行净删除后的 diff，发现并修正 `MIGRATION_STATUS.md` 中删除连接词造成的语病；没有照搬 scout 提议的新 validator 文件。config/image/resume/import 定向集 **99 passed / 2.39s**。项目环境 root 全量按预期为 **1090 passed / 89.07s**：旧套件删除 6 个证明 dormant PDF behavior 的 case，新边界增加 4 个 keyword rejection case，active coverage 没有丢失。`compileall -q src tests` 通过；isolated `import ocrllm` 只加载 root package module，未加载 PIL、pypdfium2、OpenAI/httpx、ONNX Runtime、RapidOCR、OpenCV 或 NumPy；diff/EOL whitespace 检查通过。

**最后一次非产品命令错误。** 为寻找下一项明确 open debt，第一次 PowerShell `rg` pattern 混入未配对的双引号，shell 在执行搜索前报 terminator error，没有读写仓库。改用单引号和更简单的两个独立 pattern 后成功。该扫描确认 active 已登记的主要外部门禁仍是付费 Stage M smoke，另有 legacy Bilibili diagnostic 在 pytest collection 期间做 public HTTP 的已知 test debt。

**本轮边界与下一轮。** 本轮没有网络/provider/付费调用，除 Git 同步和最终 push；没有修改 frozen `contracts/`、`worker/`、legacy、social media 或用户临时交接文件。#043 优先审计并修复已建 legacy 测试基础设施：定位为何 Bilibili live diagnostic 在 collection/import 时联网，比较显式 opt-in integration test 与离线 collection seam，先证明 broad suite 会被 import-time HTTP 拖死，再做最小修正。它是测试隔离修复，不是恢复 social media feature 开发。

## #043 — 2026-08-23：Bilibili diagnostic 不再在 pytest collection 联网

**本轮英文自我任务。** Atomic task: remove public-network activity from pytest collection for the legacy Bilibili diagnostic without weakening the explicitly runnable diagnostic or resuming social-media feature work. Success means import/collection 零网络和零 subprocess，explicit manual diagnostic 仍可运行，失败优先证据、legacy carry-forward、离线广集、中文日记、提交和 push 全部完成。

**复核后的精确范围。** 同步 origin、重读 active/entry/legacy 规则和 #042 后，确认 `legacy_app/tests/test_bilibili_api.py` 没有任何 test function。模块 import 立即创建 `curl_cffi.Session`，无条件产生 3 处 GET 和 2 个 curl short-link subprocess，short-link 命中 BV 后还可能产生 2 处 GET。root pytest 的 `testpaths=["tests"]` 不会收集它，但显式 legacy suite 或 `pytest .` 会在 `--collect-only` 阶段联网；旧记录的 20.94 秒 timeout 因而是真实 test-infrastructure defect。

**两条路径与选择。** 两名只读 scout 分别建议：①改成 `OCRLLM_RUN_LIVE_BILIBILI_TESTS` 控制的 skipped live test；②改成 guarded manual diagnostic。选择②，因为旧文件只有打印，没有 assertion、marker 或 pass/fail contract，social feature 已延期；把它正式化成 live CI test 会扩展产品语义。改名为 `diagnose_bilibili_api.py`，函数也叫 `diagnose_bilibili_api()`，只有 `__main__` 执行。全部显式 GET 与 curl 都限制 15 秒；未修改 production Bilibili/downloader 代码。

**失败优先和最小回归。** 新 test 注入会在 Session 构造或 subprocess 启动时立即失败的 fake，再用 `runpy.run_path()` 导入 diagnostic。旧模块稳定 **1 failed / 0.14s**，失败点是 import 构造 Session；没有真实网络。修后 **1 passed / 0.04s**；对 regression + diagnostic 的 collect-only 只收集 1 个 offline test，diagnostic 不执行。主代理没有运行 explicit live diagnostic。

**下一步。** 运行排除真实 ffmpeg e2e、但不再排除 Bilibili 文件的完整 legacy offline suite；再跑 root suite、compile/import/diff。结果和边界在提交前补入本条。用户临时交接文件、active Python、frozen contracts/worker 和 social production code 保持不动。

**完整验证与边界。** legacy offline suite 现在只排除真实 ffmpeg `test_social_e2e.py`，不再排除 Bilibili 文件，结果 **279 passed, 1 skipped / 51.94s**；唯一 skip 是显式 live Google discovery。active root suite **1090 passed / 88.95s**。`compileall -q src tests legacy_app`、isolated lightweight import、diff/EOL whitespace 全部通过。没有运行 Bilibili/Google/provider/付费 live 调用，网络仅用于 Git 同步和最终 push；用户临时交接文件、active Python、frozen contracts/worker 和 social production code 保持不动。

**下一轮。** #044 审计 packaging-facing `README.md` 与 `src/ocrllm/README_ACTIVE_LIBRARY.md` 是否仍把 Stage M 写成 partial、把已关闭 defect 写成 open。只对照当前 authority、代码和最新验证修正文档事实；不借文档更新启动 Stage A、Google adapter、PDF 或付费 smoke。

## #044 — 2026-08-23：修正 package 用户首先看到的当前状态

**本轮英文自我任务。** Atomic task: make `README.md` and `src/ocrllm/README_ACTIVE_LIBRARY.md` tell the same verified current story as authoritative state, without rewriting historical evidence or claiming the unpaid live gate is complete. Success means present-tense claims、public export list、install command 和 wheel metadata 都与代码/authority 一致，改动保持最小，package/docs 验证、中文日记、提交与 push 完成。

**假设、两条路径与选择。** 开工假设是 implementation/API examples 大体正确，问题集中在 stale status prose；比较①替换过期 current-state paragraphs 与②重组两份 README，选择①。同步 origin、重读 authority/entry/package 规则和 #043 后，两名只读 scout 与主代理复核一致发现：root README 仍写 2026-08-19、Stage M partial、D4/G1-G10 多项 open、旧 Stage 2 split 未开始，还绝对声称 legacy diary 没有 open bug；package README 开头同样写 partial，却在后文正确写 G1-G10 已 offline closed，文件内部自相矛盾。

**同一 package-truth 边界里的额外证据。** `src/ocrllm/README_ACTIVE_LIBRARY.md` 把代码块标为 Public Contract，却比 `ocrllm.__all__` 少 10 个真实 export：`AllCandidatesExhausted`、`BatchItemOutcome`、credential pool 的 5 个 policy/value/report 类型、`NoTextDetected`、`OCRBackendError`、`ResumeStateError`。root README 又给出 `pip install "ocrllm[...]"`，但仓库无 tag/release，官方 PyPI JSON endpoint 对 `ocrllm` 返回 404；因此改成明确的 checkout install `pip install ".[image,dashscope]"`。`pyproject.toml` 的 wheel Summary 还称当前库为 multimodal，超过实际 image/local-OCR 能力，收窄为 board and image recognition。

**最小编辑。** 两份 README 只替换 current status 段；root 明确 Stage M offline implementation-complete、D/F/G offline closed、paid live gate 与 provider-account/model-quota re-verification 仍 open，旧 standalone Stage 2 已合入未来 executable A1，Google image adapter 仅 planned。package public import block补齐 exact exports。没有改历史 milestone table、dated evidence、代码、API、依赖、版本或 phase gate。

**验证过程中的工具事实。** stale-phrase 搜索没有命中，`rg` 因“零匹配”返回 1，这是预期结果，不是失败；AST 解析 package README 的首个 Python import block，并与运行时 `ocrllm.__all__` 比较，41 个名字完全相等。首次组合过长的 PowerShell build/检查/清理命令被执行策略在启动前拒绝，未读写仓库也未创建临时物；拆成显式路径的小命令后继续。项目环境没有可选 `build` frontend，`pip wheel --no-build-isolation` 又明确暴露该环境没有 Hatchling backend；没有为文档验证安装依赖，改用机器上已有的 `uv build` 隔离构建。编辑时还发现 root README 被 patch 形成 mixed EOL；一次机械归一化误把四个文件都设成 CRLF，随即根据 index 逐文件恢复为 README CRLF、其余三文件 LF，提交前已确认一致。这些都是验证/格式工具问题，不是产品运行缺陷。

**构建、测试与个人复核。** 主代理用已有 `uv` 在显式临时目录成功生成 `ocrllm-0.1.0-py3-none-any.whl`（154759 bytes），再直接检查压缩包：METADATA Summary 精确等于新的 board/image 文本，long description 含新的 Stage M 状态且不含旧 partial 句，`ocrllm/README_ACTIVE_LIBRARY.md` 确实打入 wheel。`tests/test_import_contract.py` 与 `tests/test_lightweight_import.py` 为 **7 passed / 0.41s**；pytest 仍只有已知 `.pytest_cache` 无写权限警告。`compileall -q src tests` 与 isolated lightweight import 通过，后者没有加载 PIL、OpenCV、DashScope、Google GenAI、PyMuPDF 或 FastAPI。上一轮已经在紧邻代码状态上跑过 root 全量 **1090 passed**；本轮只改 packaging prose/metadata，因此 wheel + 相关 contract tests 是合比例验证，没有重复 90 秒全量。构建物位于系统 temp 的唯一显式目录；在精确解析路径后，执行策略仍拒绝递归清理命令，因此没有绕过保护，临时 wheel 目录保留且不进入 worktree。

**边界与下一步。** 本轮没有改 active 行为、frozen `contracts/`/`worker/`、legacy、social media、依赖、版本或用户临时交接文件；网络只用于先前的 Git 同步、官方 PyPI 只读 404 检查和最终 push，没有 provider 或付费调用。下一轮先做一个有边界的发布准备度审计：比较①立即设计发布流水线与②只查明当前 0.1.0 wheel 在真正发布前缺少哪些最小证据/元数据，优先选择②；不发布到 PyPI、不增加自动化平台，也不把尚未实现的 PDF/audio 写进产品承诺。

## #045 — 2026-08-23：刷新精确发布物证据并发现默认分支风险

**本轮英文自我任务。** Audit whether the current `0.1.0` wheel has the minimum evidence and metadata needed for an eventual controlled release, without publishing anything, adding a CI platform, or promising unimplemented media features. Success means every claimed gap is verified against the wheel, `pyproject.toml`, repository release evidence, and existing go/no-go rules; any fix is small, user-facing, and testable. This matters because a mature library must be installable and accurately described, while release machinery built before a real release decision would be over-design.

**复核后的假设、两条路径与选择。** 开工时假设 wheel 本身健康，问题更可能在 release evidence/metadata；比较①现在设计发布流水线与②只关闭一个经验证的最小准备度缺口，选择②。重读 authority、entry、package 规则与 #044 后，主代理和 install-evidence scout 都确认仓库并不缺 clean-package gate：`tools/run_stage_m_offline_gate.ps1` 已对 exact commit 做 Git archive、wheel build、no-deps isolated install、仓库外 import、metadata/extras、size/import budget、新 venv profile、generated-image smoke 和 offline DashScope construction。真正缺口只是最近完整证据仍停在 `2e9c770`，因此不新增 CI、release script 或普通 pytest。

**当前 HEAD 的完整无付费 gate。** 在 tracked worktree clean、仅保留用户未跟踪交接文件的状态下，对 `271d96df837a8bbe3caf271afd966cb0539371d6` 运行 maintained runner。archive suite 为 **1089 passed, 1 skipped / 93.44s**；skip 是 gate 环境没有安装 RapidOCR 的既有 optional integration，不是 Google live test。fixture check 为 pixel-equivalent，compile 通过；clean wheel **153382 bytes**，no-deps target **747967 bytes**。OCRLLM/base Python plain-import wall median/p95 分别为 **0.88/2.40 ms** 与 **0.49/1.21 ms**；process CPU median/p95 分别为 **0/15.63 ms** 与 **0/0 ms**。fresh `image` 与 `image,dashscope` 增量分别为 **16436747** 与 **41009476 bytes**，generated-image 识别和 DashScope client offline construction 均通过；没有 provider request。authority、START_HERE、MIGRATION_STATUS 与 go/no-go 只刷新这组当前证据，没有重写旧历史。

**真正的仓库可见性风险。** metadata scout 发现并由主代理独立验证：公开 fork 的 GitHub default branch 仍是 `main`，HEAD `017de010c6c5e5f7fe46adbaeec2c5b763449122`；维护中的 `origin/master` 为 `271d96d`，`main` 是其 strict ancestor，落后 **161 commits**。因此普通访问者首先看到的不是已验证产品。authority 新增一条当前 debt：在 tag/public release 前，维护者必须明确选择把 `master` 设为 default 或有意合并/改名；本轮不暗中改外部仓库设置，也不把 161 commits 反向复制到旧分支。

**metadata 结论与没有扩建的原因。** 当前 wheel 的 Name、Version、Summary、Requires-Python、四个 extras 和 base no-dependency 都正确，`pyproject.toml` 与 `ocrllm.__version__` 均为 `0.1.0`；GitHub/PyPI 尚无 tag/release，符合 pre-release 状态。Project URL、classifier、changelog、`py.typed` 和排除 package 内 `AGENTS.md` 都只是可选整理，不是结构或安装 blocker。`license = { text = "Proprietary" }` 能表达没有自动授予权限，但仓库没有给外部接收者的 LICENSE/NOTICE；是否以及如何对外授权只能由维护者决定，代理没有发明许可文本。因默认分支风险更直接、clean gate 已证明 version/metadata 一致，本轮也没有为了理论上的双版本漂移再加一套测试。

**工具小问题与边界。** 一次 PowerShell `rg` 命令把双引号 regex 放进双引号 shell 字符串，转义后形成 unclosed group；搜索未执行、仓库未改变。随后拆成两个单引号简单 pattern，确认版本只有 `pyproject.toml` 与 package `__init__` 两个产品声明且当前一致。网络只用于 Git/GitHub/PyPI read-only 状态、隔离依赖获取与最终 push；没有发布、改 default branch、建 release/tag、调用 provider 或付费。active Python、frozen `contracts/`/`worker/`、legacy、social media、版本、依赖与用户交接文件都不改。

**需要维护者决定的下一步。** 默认分支应在公开 release 前修正，但这是外部仓库入口变更：请明确授权“把 fork 的 GitHub default branch 从 stale `main` 改成 maintained `master`”，或指定希望先把分支合并/改名。对外分发还需要说明接收者权限；如果当前只做私有/本地 checkout，则 `Proprietary` 状态可以继续，不阻止 library maturation。

## #046 — 2026-08-23：收窄 Stage A1 短 MP3 边界并修正 capability 阶段说明

**本轮英文自我任务。** Revalidate the first executable Stage A1 short-MP3 recognition slice against current `ocrllm` contracts, legacy audio behavior, and installed dependency/provider reality. Success means the proposed public inputs, output semantics, failure types, dependency boundary, and checkpoint scope are reduced to what one real short-MP3 call needs; every rejected legacy behavior and every unresolved blocker is explicit; no audio code is implemented until the boundary is proven. This matters because the first audio slice will establish the public contract, and importing long-audio recovery or legacy fallback behavior now would make later maintenance harder.

**开工假设、两条路径与选择。** 起初有两条路：①按旧计划马上写 short-ASR adapter；②先挑战计划，核对 active seam、legacy 真实行为和依赖/provider 可行性。选择②，因为旧文档同时写着“A1 等 Stage M exit”和“短音频也必须 flowed output”，很可能把无关的付费 image gate 与 A2 长任务机制带进 A1。复核后假设改为：A1 只接受一个本地 MP3、一次明确协议调用、一个完整 transcript 和 Markdown；URL、序列、转换、切片、并发、fallback、hotword、其他格式和 social 都不进入 A1。A1 可做 offline implementation，不等待 Stage M 独立的付费 image smoke；A1 自己的 live gate 仍需单独预算授权。

**三路只读审计和主代理复核。** active seam 审计确认 `recognize.py` 目前在媒体识别前先解析 image profile/count，A1 实现时必须把 image-only 解析移回 image branch，再加窄的 one-path audio branch；现有 `ProcessorOutput`、`RecognitionResult`、`NoSpeechDetected`、source snapshot、request gate、redaction、atomic output 和 output claim 可以复用。legacy 审计确认值得迁移的是 MP3 结构/时长预检、显式同步协议、取消、typed failure、原子发布和模型来源；不应迁移 short/long 自动路由、远程 URL、FileTrans、格式转换/切片、SDK→OpenAI 隐藏 fallback、模型名推导和 GUI repair 格式。依赖审计确认项目已有 `openai 2.30.0`，官方 Qwen3 short route 可走 OpenAI-compatible `chat.completions`；无需新增 native DashScope SDK。当前环境虽有 `imageio-ffmpeg`、`pydub` 和 DashScope SDK，但它们都不是 declared product dependency，不能因“机器上碰巧存在”直接写进产品边界。

**关键减法决定。** A1 的恢复只保存一次调用的 completed result：source bytes/hash、request/protocol/provider/model identity、transcript/digest 和安全 metadata；有 `output_dir` 时先原子落 typed state，再发布 Markdown，`resume=True` 精确命中时零调用复用。A1 不建 chunk、segment、task ID、partial transcript 或轮询状态；这些留给 A2。`Config.short_audio` 只在真正被消费时落地，并把 provider 与显式 model 一起绑定；不让 injected provider 暗藏 model。探测依赖暂不拍板：下一轮用 generated/truncated/VBR/ID3 fixtures 比较完整解码、时长、包体和许可证，不能把 ambient FFmpeg 当成已经选择。官方当前边界是一份 MP3、最长五分钟、最终 Base64 请求不超过 10 MB；legacy 的 raw 9.5 MB 阈值不能直接复制，live gate 仍需复验。Google 音频保留为用户已授权的 robustness source 和独立 provider slice，不成为 DashScope 的静默 fallback。

**发现并登记的真实旧缺陷。** legacy short-ASR 会把普通 provider 失败变成说明文字，再继续汇总并返回 output path；单 segment 因而可 false-success，非空 refusal/no-speech 也可能被当 transcript。本轮按 repo rule 写入 `legacy_app/AGENTS.md` 的“仅观察”条目，并在 A1 写死 typed failure / no success artifact 要求；没有借规划任务改 legacy production code。

**已修 shipped-surface 小缺陷。** `get_capabilities()` 仍把所有 audio 项写成 `Phase 4`。先新增精确断言，旧实现稳定 **1 failed, 11 passed / 0.35s**，失败值正是 `Intentionally deferred to Phase 4.`。修复把 short DashScope + short MP3 指向 `Stage A1`，FileTrans + long MP3 指向 `Stage A2`，WAV/M4A 明确留在 later audio-format gate；状态仍全部是 `deferred`，没有假称功能可用。用 full reason mapping 取代“phase 名拼句子”，避免 later-format 文案变得含糊。

**文档与边界改动。** authority、migration status 和主计划现在一致说明 A1 offline 可独立开始、live gate 单独预算；A1 只做 completed-result recovery，A2 才做 task/segment resume。计划补上 exactly-one local path、snapshot-before-probe、Windows 短临时名、final Base64 envelope preflight、typed response failures、no fallback/hotword，以及 probe-dependency spike。没有实现 audio API、改 frozen contracts/worker、加 dependency、调用 provider 或触碰 social code。

**工具问题。** 两个早期只读命令误试了不存在的 `src/ocrllm/capabilities.py`、`resolve_profile.py`，且一次把 wildcard 与 `-LiteralPath` 混用；都没有写仓库。DashScope introspection 首次读取不存在的 `dashscope.__version__`，随后改用 package metadata 成功确认 1.25.15。一次 broad `rg` 输出过大被截断，后来改成精确范围读取。EOL 复核时两次临时 Python one-liner 又被 PowerShell quoting 破坏，只产生 SyntaxError/ParserError，未写文件；随后改用 byte-count 和标准 diff 检查完成复核。PowerShell profile 的 PSReadLine warning 仍是已知终端噪声。

**验证与主代理复核。** 修后 capability/config/import/lightweight 相关集为 **54 passed / 0.77s**；只有已知 `.pytest_cache` 无写权限 warning。`compileall -q src tests` 通过，isolated plain import 没有加载 PIL、OpenAI、DashScope、Google、pydub 或 imageio-ffmpeg。相邻 commit `271d96d` 已经通过 clean archive **1089 passed, 1 optional skip**，本轮产品代码只改 deterministic reason mapping，因此不重复全量。主代理逐项检查 capability status 仍为 deferred、A1/A2 恢复边界、官方限制措辞和 legacy carry-forward；没有 provider、音频、网络或付费调用。`git -c core.whitespace=cr-at-eol diff --check` 通过；七个已改文件维持各自原有 LF 或 mixed-EOL 类别，没有整文件换行归一化。提交与 origin push 在本轮结束前完成。

**下一轮。** 优先做 audio probe dependency spike，不写 provider adapter。仍需维护者决定第一 built-in audio provider 是否保持推荐的 DashScope-first，或改为 Google-first；该选择会改变 public settings 和 live gate，不能由实现细节暗中决定。
