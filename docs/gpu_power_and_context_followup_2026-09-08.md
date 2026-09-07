# 断电后功耗、BIOS 与上下文跟进（2026-09-08）

维护者补充：断电重启时进入BIOS，将一个三档性能选项拉到最高，另一个Disabled选项改Enabled；只记得一个位于页面右侧、一个在中央偏下。两个名称尚未确认，不能仅凭位置猜定功能。主板只读查询为ASUS PRIME Z890-P WIFI Rev1.xx，BIOS3012；Windows当前电源计划为Balanced。

## 当前只读显卡观测

2026-09-08约00:43、正式OCR运行时，nvidia-smi显示平均板卡功耗304.20W，当前/强制/默认功耗上限均350W。GPU为P2，利用率70%，核心1740MHz，显存9501MHz，核心72°C。PCIe当前及最大均Gen4 x16。HW/SW thermal slowdown和HW power brake均不活跃，对应计数0；SW power cap活跃。这里是W功耗，不是V电压；没有上限被降成290/300W的证据。

NVIDIA说明功耗限制、温度限制是不同的时钟限制原因，平均功耗与瞬时功耗也有不同统计口径；因此不能只凭“未到350W”推断损坏。来源：[NVIDIA SMI说明](https://docs.nvidia.com/deploy/nvidia-smi/index.html)。显存结温在此接口为N/A，不能用核心温度替代它。当前只读结果不是全面硬件认证；正式工作完成后还要汇总运行稳定性及驱动错误记录。

## 对速度归因的重要控制证据

持久llama日志的同一A前两图、同course.legacy.v1提示词、medium、8Kcontext/4K生成预算：断电前1744生成tokens，30.02tok/s；恢复后、尚未扩大context时同样1744tokens，30.05tok/s。日志行635、4702、4751可定位两次实例。这不支持简单归因于“断电或BIOS后GPU整体变慢”。16K/8K的另一已知难例为4643生成、18.40tok/s；其样本和active sequence不同，fit/设备放置也未记录，不能单凭这两项断言最终GPU layer变化。

## 尚未执行的更紧凑预算计划

已解决难例实测2676输入+4643生成=7319tokens，能容纳于8192总context；旧问题是4096独立生成上限。候选如下，均保持medium及同一实际提示词：

| 总context | max output | 用途 |
|---:|---:|---|
| 8192 | 5500 | 同一难例先验证；2676+5500=8176，只余16tokens，不能推广到更长输入 |
| 12288 | 8192 | 同两图输入最多约10868总tokens；KV静态约408MiB，比8K多136MiB |
| 16384 | 8192 | 当前正在跑的三组固定配置，保留为对照 |

比较需要固定图片、prompt、medium、BIOS/电源计划，并单列冷加载；记录热wall、完整结束、输出规模和设备放置证据。不以更少输出或失败丢弃来宣称更快。上述候选尚未运行，当前正式三组不因这个计划再次改参数。

## BIOS 位置线索的核查边界

[ASUS Intel 800 系列 BIOS 手册](https://dlcdnets.asus.com/pub/ASUS/mb/14Utilities/C25827_Intel_800_Series_BIOS_manual_EM_WEB.pdf?model=PRIME+Z890-P)的 EZ Mode 图示右侧有 AI Overclocking/模式切换区域，中央偏下有 Intel Rapid Storage Technology 与风扇区域。这些只是位置候选；系列手册也不保证本板当前 BIOS 的布局完全相同，不能据此认定维护者改了哪个选项。

手册中的 CPU 性能、超频和功率设置不等同于 NVIDIA 独显的板卡功耗上限。CPU、内存或存储设置可能间接影响推理供给速度，但当前遥测没有显示 GPU 功耗上限降低或 PCIe 链路降级。未修改 BIOS、电源计划、风扇或 GPU 参数，也未为识别选项而重启。当前上限/默认上限为350W，可设最大上限为371W；后者不是当前使用值。

## Windows 日志只读结果

本次启动时间为9月7日23:36:14。启动前23:33有EventLog 6006正常停止、Kernel-Power 109系统发起关机，以及577重启过渡记录；本次启动后查询没有Kernel-Power 41、EventLog 6008、Display 4101或nvlddmkm事件。这更符合系统收到关机请求的日志轨迹，不能把维护者所述事件直接定性为已证实的物理供电瞬断。历史9月3日的41不属于本次事件。

启动后有一条WHEA ID3。子代理读取其316字节CPER：header和唯一section的severity均为3（Informational），NotifyType为BOOT；唯一section是公开标准表外的厂商GUID，无法映射到RTX 3090或具体设备。没有标准PCIe设备/BDF/AER section，不凭这条记录认定GPU故障，也不以“信息级”断言硬件绝无问题。CPER时间戳有效位未设置，采用Windows事件时间。字段解释依据[Microsoft WHEA header](https://learn.microsoft.com/en-us/windows-hardware/drivers/ddi/ntddk/ns-ntddk-_whea_error_record_header)、[severity枚举](https://learn.microsoft.com/en-us/windows-hardware/drivers/ddi/ntddk/ne-ntddk-_whea_error_severity)和[UEFI CPER规范](https://uefi.org/specs/UEFI/2.10_A/Apx_N_Common_Platform_Error_Record.html)。原始XML仅保存在私人持久证据目录。以上是运行中检查，最终任务结束后还需检查是否新增驱动/硬件错误。

## 间歇峰值与连续串行队列

旧A组wall 5097.921420秒，实际HTTP累计5078.545385秒，请求外差值19.376035秒，仅约0.38%。在保持每批推理不变、仍串行的条件下，即便完全消掉这部分开销，收益上限也只有约0.38%；这不是张量批处理或并行推理的收益上限。现有harness已连续提交各批，不能从风扇/功耗波动推断大量客户端空等。输入处理、逐token生成和请求间工作负载不同，需要按阶段看吞吐。

本次测试不能测出显卡寿命，也没有证据支持“始终100%占用”或“周期性峰值”必然更保护显卡。功耗/风扇波动本身不是损坏判据；本轮仅结合时钟、温度、功耗限制原因、PCIe状态和驱动事件判断已观察到的运行状态，没有改超频、风扇或功耗配置。
