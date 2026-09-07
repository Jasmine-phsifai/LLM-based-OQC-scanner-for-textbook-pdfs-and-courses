# AAC、MP3与切片采样率调查（2026-09-07）

维护者要求并行调查、先查清事实再决定下一步。本调查由Luna子代理完成代码核查和
CPU复现，主代理复核相关源码并使用soundfile再次读取真实文件；没有改变运行时代码，
没有调用GPU，没有中断三课程计时。以下只描述当前实际实现，不把历史日志当能力证明。

## 结论

“AAC和OCRLLM当前MP3支持不同”属实；“AAC切片必然损失采样率”不成立。
当前采样率从24 kHz变为16 kHz，直接原因是OCRLLM物化切片时显式指定
`-ar 16000`，即使输入已经是MP3也会发生。AAC转MP3的有损重编码、采样率变化、
码率选择是不同问题。尚无本轮准确率对照证明这些变化造成了多少漏字，不能把当前
ASR的NOSPEECH误判嫌疑直接归因于它们。

## 实际代码链路

| 环节 | 当前行为 | 代码证据 |
|---|---|---|
| OCRLLM直接音频输入 | 只接受`.mp3`；AAC/M4A不能直接进入当前长音频流水线 | `src/ocrllm/detect_source_type.py:11`；`src/ocrllm/audio/snapshot_mp3.py:103` |
| 视频提取音轨 | FFmpeg解码可用音轨，输出单声道16 kHz、32 kbps MP3 | `src/ocrllm/video/extract_video_audio.py:58` |
| 长音频物化切片 | `-ss START -i SOURCE -t DURATION -map 0:a:0 -vn -ac 1 -ar 16000 -b:a 64k -c:a libmp3lame` | `src/ocrllm/audio/materialize_long_audio_interval.py:89` |
| Model Lab HTTP接收 | `input_audio.format`只能为`mp3`，其他格式返回415 `invalid_audio_format` | Model Lab `scripts/local_qwen_openai_service.py:252` |
| Model Lab模型输入 | soundfile解码；多声道取平均；非16 kHz用librosa重采样到16 kHz | Model Lab `scripts/local_qwen_model_manager.py:103` |

安装的Qwen3 ASR feature extractor默认`sampling_rate=16000`。这是当前模型输入约定，
不能把保持24 kHz传输直接等同于模型能用24 kHz推理。库切片已是16 kHz时，服务端
`sample_rate != 16000`分支不执行，不会再重采样一次。

视频文件内有AAC音轨、FFmpeg能解码AAC，不代表公开音频API接受AAC文件；
capability表中延后的M4A/AAC格式gate也不能作为已支持证据。本次基准没有执行视频
音轨提取，因此32 kbps视频提取参数不属于这次三课程的实际成本。

## 真实核验

三课程原始音频是24 kHz单声道AAC/M4A，基准准备阶段显式用`-ar 24000 -b:a 64k`
转换为整课MP3。随后按现有库逻辑切片，实际链路为：

```text
24 kHz AAC → 24 kHz / 64 kbps MP3 → 16 kHz / 64 kbps MP3切片 → 16 kHz模型波形
```

从本次A组整课MP3取600–612秒，通过实际`materialize_long_audio_interval()`执行，
主代理再用soundfile读取输入和结果：

| 核验对象 | 采样率 | 声道 | 解码时长 | 格式 |
|---|---:|---:|---:|---|
| 整课输入MP3 | 24000 Hz | 1 | 9677.657875秒 | MP3 |
| 实际库切出的12秒片段 | 16000 Hz | 1 | 12.000000秒 | MP3 |

FFmpeg探测切片为64 kbps。容器探测显示约12.10秒，soundfile解码为192000个采样点、
正好12秒；不要把编码延迟/填充的容器时长直接说成多识别了0.10秒。
另一个3秒合成AAC对照，指定`-ar 24000`转换后仍是24 kHz，指定`-ar 16000`才变为
16 kHz，进一步排除“AAC转换必然降采样率”的说法。合成试验只验证格式行为，
不作为真实语音准确率证据。

采样率以Hz计，码率以kbps计，二者不能混称。“64 kbps”不表示64 kHz。
这里存在AAC到MP3、整课MP3到切片MP3的两次有损编码；原始文件保持不变。
即使以后保持24 kHz或提高码率，也不能恢复先前编码中已丢失的信息。

## 下一步的判断依据（未实施）

优先要评估的是减少不必要的重复有损编码，并使媒体输入支持与模型预处理边界明确；
仅把库中的16000改为24000不能解决AAC准入，也不会改变服务端当前16 kHz输入。
若决定原生接收AAC/M4A，需要同时核验库的格式/时长验证、切片输出和请求构造、
服务端格式验证及容器解码，不能只扩大文件后缀白名单。客户端提供通用媒体能力，
模型需要的采样率预处理仍由Model Lab负责，不把Qwen细节硬编码进OCRLLM。

本轮先报告事实；没有新增AAC功能、调整编码参数或据此改变正在运行的计时配置。
私有探测文件保存在`/tmp/ocrllm-aac-mp3-investigation-20260907-real64k/`，
本记录不包含课程名称或源媒体路径。
