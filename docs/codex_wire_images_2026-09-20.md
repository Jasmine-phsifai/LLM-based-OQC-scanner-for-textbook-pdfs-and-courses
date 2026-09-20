# 真实Codex CLI→本机Responses图片传输核验（2026-09-20）

## 范围与隔离

前一场景只证明OCRLLM→CLI入场顺序。本轮运行当前生产实际CLI二进制
`codex-cli 0.154.0-alpha.6.1`，使用当前owner builder的原始prompt和同3组8张图片。
请求目标为Python本机 `127.0.0.1` 假Responses服务，`wire_api=responses`、
`requires_openai_auth=false`；每组临时独立CODEX_HOME仅复制无凭据models_cache.json，
不复制auth/config，不继承凭据环境。子进程代理只指向本机拒绝端口并豁免loopback；
生产代理、认证、配置和服务均未更改。fake服务返回合成完成事件，不转发任何请求。

依据本机help配置覆盖说明和[官方自定义provider文档](https://learn.chatgpt.com/docs/config-file/config-advanced)。
官方配置支持性与实际本机运行结果分开：最终证据为真实CLI实际HTTP请求。

## 结果

三组各一次 `/v1/responses` 请求，CLI均exit0，真实云模型调用0。
全部24个input_image位置在去base64后与原JPEG **字节SHA256、字节长度、1920×1080尺寸、
RGB解码像素SHA256完全相同**，序列与prompt原文件名数组一致。该路径未见CLI
重排、缩放或转码，包含非连续mixed组。

实际请求参数：

- model=`gpt-5.6-luna`
- reasoning.effort=`low`，reasoning.context=`all_turns`
- text.verbosity=`low`
- input_image.detail未提供；不能据此臆测后端采用什么detail或图像预算
- service_tier未提供（命令参数设置default）；不据此作真实服务计费推断
- Authorization header不存在

独立home模型缓存SHA256：
`2fb21546979423b0a4bcb8fb063fc3f7e0980d6b3f0cd69f6885c57271178a60`。
stderr未出现fallback/cache/auth这些已检查关键词；不能把这个有限检查当CLI所有行为证明。
实际luna模型名、low推理和low verbosity来自请求本身，而非用配置值代替执行事实。

## 证据与工具

持久目录 `/mnt/r/course-pipeline-state/scenarios/codex-wire-images-20260920`：

- `requests.json`：每组实际HTTP提取的图片摘要、顺序、模型/推理/verbosity/身份映射
- `result.json`：CLI版本、缓存hash、原图摘要、比较结果和退出状态

场景最终门禁要求三组均CLI exit0、各恰好一次请求、匹配全真且无Authorization；
无捕获/请求异常/不匹配则非零退出，避免报告存在就被误判为通过。

不持久完整HTTP头、认证值、原始base64大包或完整prompt。合成回复也不用于生产识别稿。

复现（work-dir须不存在）：

```
/home/model-lab/.venvs/ocrllm-local-integration/bin/python tools/verify_codex_wire_images.py --manifest /mnt/r/course-pipeline-state/scenarios/codex-course-wrapper-manifest-20260920.json --config '/mnt/r/Three-repo orchestrator/config/local.json' --model-cache /home/model-lab/.codex/models_cache.json --work-dir /mnt/r/course-pipeline-state/scenarios/codex-wire-images-20260920
```

## 限制

本轮证明该真实CLI经**自定义Responses provider**向loopback发送的图片字节/顺序。
生产ChatGPT认证provider的路由或云端接收路径不在本次捕获范围；不能断言所有provider
路径完全等价。后端解码/预处理、图像注意力分配、模型理解与正文-帧绑定仍未核实。
low verbosity是实际观察，不是已经证明的摘要化原因；本轮未改变生产verbosity、
模型、8图batch、prompt或重试。多图识别质量问题不能因传输正确被视为已修复。

最终带非零失败门禁复跑保存于 `codex-wire-images-20260920-verified`，三组各1请求、
passed=true。另用零组输入验证缺失捕获确实exit1、passed=false，保存于
`codex-wire-missing-capture-20260920`；该负例没有图像请求。两项均零云模型调用。
