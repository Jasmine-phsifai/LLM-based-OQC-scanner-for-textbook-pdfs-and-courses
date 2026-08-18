import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from OCRLLM import prompts
from OCRLLM.config import AppConfig
from OCRLLM.core.providers.google_provider import GoogleProviderClient
from OCRLLM.processors.audio import (
    ASRNoValidFragmentError,
    AudioChunk,
    AudioProcessor,
    AudioSignalStats,
    build_google_audio_windows,
    google_audio_transcript_invalid_reason,
)
from OCRLLM.processors.video import VideoProcessor
from OCRLLM.processors.video_pipeline import AudioRecognizePhase, VideoProcessContext
from OCRLLM.processors.video_pipeline_selection import VideoPipelineSelection


class GoogleAudioRoutingTests(unittest.TestCase):
    def test_default_audio_prompt_requires_fine_segment_metadata(self):
        prompt = prompts.AUDIO_TRANSCRIBE

        self.assertIn("必须按时间顺序分成若干小段", prompt)
        self.assertIn("<!-- meta:segment index=序号 time=开始时间~结束时间 -->", prompt)
        self.assertIn("时间必须使用整段课程的绝对时间", prompt)
        self.assertIn("{hotwords_instruction}", prompt)

    def test_google_audio_windows_default_to_30_minutes_with_overlap_context(self):
        windows = build_google_audio_windows(duration=3700, chunk_seconds=1800, overlap_seconds=30)

        self.assertEqual(len(windows), 3)
        self.assertEqual((windows[0].logical_start, windows[0].logical_end), (0.0, 1800.0))
        self.assertEqual((windows[0].actual_start, windows[0].actual_end), (0.0, 1830.0))
        self.assertEqual((windows[1].logical_start, windows[1].logical_end), (1800.0, 3600.0))
        self.assertEqual((windows[1].actual_start, windows[1].actual_end), (1770.0, 3630.0))
        self.assertEqual((windows[2].logical_start, windows[2].logical_end), (3600.0, 3700.0))
        self.assertEqual((windows[2].actual_start, windows[2].actual_end), (3570.0, 3700.0))

    def test_google_mode_uses_long_audio_provider_even_for_short_local_audio(self):
        with tempfile.TemporaryDirectory() as tmp:
            audio_path = os.path.join(tmp, "short.mp3")
            with open(audio_path, "wb") as f:
                f.write(b"fake audio")
            output_path = os.path.join(tmp, "out.md")

            cfg = AppConfig().with_updates(
                paths={"output_dir": tmp, "temp_dir": tmp},
                google_api={
                    "enabled": True,
                    "api_key": "AIza-test",
                    "audio_model": "gemini-3.5-flash",
                },
            )
            llm = Mock()
            llm.transcribe_long_audio.return_value = "hello from google"
            processor = AudioProcessor(cfg=cfg, llm=llm)
            processor._ensure_upload_format = Mock(return_value=audio_path)
            processor._get_cached_duration = Mock(return_value=None)
            processor._split_google_audio = Mock(return_value=[
                AudioChunk(audio_path, 0.0, 10.0, 0.0, 10.0),
            ])
            processor._short_asr = Mock(side_effect=AssertionError("short fallback must not run"))

            result = processor.process(audio_path, output_path=output_path)

            self.assertEqual(result, output_path)
            llm.transcribe_long_audio.assert_called_once()
            prompt = llm.transcribe_long_audio.call_args.kwargs["system_prompt"]
            self.assertIn("meta:segment", prompt)
            validator = llm.transcribe_long_audio.call_args.kwargs["text_validator"]
            self.assertIn("返回空内容", validator("```markdown\n\n```"))
            with open(output_path, encoding="utf-8") as f:
                md = f.read()
            self.assertIn("<!-- meta:segment index=1 time=00:00~00:10 -->", md)
            self.assertIn("hello from google", md)
            processor._short_asr.assert_not_called()

    def test_qwen_filetrans_route_ignores_google_key_when_google_mode_is_off(self):
        with tempfile.TemporaryDirectory() as tmp:
            audio_path = os.path.join(tmp, "lecture.mp3")
            with open(audio_path, "wb") as f:
                f.write(b"fake audio")
            output_path = os.path.join(tmp, "out.md")

            cfg = AppConfig().with_updates(
                paths={"output_dir": tmp, "temp_dir": tmp},
                api={"api_key": "sk-test"},
                google_api={
                    "enabled": False,
                    "api_key": "AIza-test",
                    "audio_model": "gemini-3.5-flash",
                },
                models={"asr_model": "qwen3-asr-flash-filetrans"},
            )
            processor = AudioProcessor.__new__(AudioProcessor)
            processor.cfg = cfg
            processor.reporter = Mock()
            processor.reporter.cancel_event = None
            processor._report = Mock()
            processor._report_content = Mock()
            processor._close_http_session = Mock()
            processor._process_google_long_audio = Mock(
                side_effect=AssertionError("google audio route must not run")
            )
            processor._ensure_upload_format = Mock(return_value=audio_path)
            processor._should_use_short_asr = Mock(return_value=(False, 600.0))
            processor._upload_file = Mock(return_value="https://example.com/audio.mp3")
            processor._submit_task = Mock(return_value="task-id")
            processor._wait_result = Mock(return_value={"transcripts": []})
            processor._result_to_md = Mock(return_value="filetrans transcript")
            processor._filetrans_text_quality_warning = Mock(return_value=None)
            processor._get_duration = Mock(return_value=600.0)

            result = processor.process(audio_path, output_path=output_path)

            self.assertEqual(result, output_path)
            processor._process_google_long_audio.assert_not_called()
            processor._submit_task.assert_called_once()
            with open(output_path, encoding="utf-8") as f:
                self.assertIn("filetrans transcript", f.read())

    def test_google_segment_validator_uses_hotwords_for_topic_mismatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            audio_path = os.path.join(tmp, "short.mp3")
            with open(audio_path, "wb") as f:
                f.write(b"fake audio")
            output_path = os.path.join(tmp, "out.md")

            cfg = AppConfig().with_updates(
                paths={"output_dir": tmp, "temp_dir": tmp},
                google_api={
                    "enabled": True,
                    "api_key": "AIza-test",
                    "audio_model": "gemini-2.5-pro",
                },
            )
            llm = Mock()
            llm.transcribe_long_audio.return_value = (
                "老师今天继续讲数据库系统中的并发控制、日志恢复、查询优化和索引结构。"
                "这里会把事务调度和恢复流程放在同一个例子里解释。"
            ) * 120 + (
                "本节术语包括 transaction、isolation level、dirty read、phantom read、"
                "SQL、B+ tree、LSM tree、query optimizer、row lock、deadlock。"
            )
            processor = AudioProcessor(cfg=cfg, llm=llm)
            processor._get_cached_duration = Mock(return_value=3600.0)
            processor._split_google_audio = Mock(return_value=[
                AudioChunk(audio_path, 0.0, 3600.0, 0.0, 3600.0),
            ])
            hotwords = [
                "transaction",
                "isolation level",
                "dirty read",
                "phantom read",
                "SQL",
                "B+ tree",
                "LSM tree",
                "query optimizer",
                "row lock",
                "deadlock",
            ]

            processor.process(audio_path, hotwords=hotwords, output_path=output_path)

            validator = llm.transcribe_long_audio.call_args.kwargs["text_validator"]
            wrong_transcript = (
                "The lecture discusses sparse signal recovery, LASSO, ISTA, FISTA, "
                "ADMM, compressed sensing, nuclear norm minimization, and linear regression. "
            ) * 260
            self.assertIn("topic mismatch", validator(wrong_transcript))

    def test_google_mode_writes_one_meta_segment_per_audio_chunk(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = os.path.join(tmp, "lecture.mp3")
            part1 = os.path.join(tmp, "part001.mp3")
            part2 = os.path.join(tmp, "part002.mp3")
            for path in (source, part1, part2):
                with open(path, "wb") as f:
                    f.write(b"fake audio")
            output_path = os.path.join(tmp, "out.md")

            cfg = AppConfig().with_updates(
                paths={"output_dir": tmp, "temp_dir": tmp},
                google_api={
                    "enabled": True,
                    "api_key": "AIza-test",
                    "audio_model": "gemini-2.5-pro",
                    "audio_chunk_seconds": 1800,
                    "audio_overlap_seconds": 30,
                },
            )
            llm = Mock()
            llm.transcribe_long_audio.side_effect = [
                "first transcript " + "老师继续讲解课程内容。" * 900,
                "second transcript " + "老师继续讲解课程内容。" * 900,
            ]
            processor = AudioProcessor(cfg=cfg, llm=llm)
            processor._get_cached_duration = Mock(return_value=3605.0)
            processor._split_google_audio = Mock(return_value=[
                AudioChunk(part1, 0.0, 1830.0, 0.0, 1800.0),
                AudioChunk(part2, 1770.0, 3605.0, 1800.0, 3605.0),
            ])

            processor.process(source, output_path=output_path)

            self.assertEqual(llm.transcribe_long_audio.call_count, 2)
            with open(output_path, encoding="utf-8") as f:
                md = f.read()
            self.assertIn("<!-- meta:segment index=1 time=00:00~30:00 -->", md)
            self.assertIn("<!-- meta:segment index=2 time=30:00~01:00:05 -->", md)
            self.assertIn("first transcript", md)
            self.assertIn("second transcript", md)

    def test_google_mode_switches_model_when_merged_transcript_is_false_success(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = os.path.join(tmp, "lecture.mp3")
            part1 = os.path.join(tmp, "part001.mp3")
            part2 = os.path.join(tmp, "part002.mp3")
            for path in (source, part1, part2):
                with open(path, "wb") as f:
                    f.write(b"fake audio")
            output_path = os.path.join(tmp, "out.md")

            cfg = AppConfig().with_updates(
                paths={"output_dir": tmp, "temp_dir": tmp},
                google_api={
                    "enabled": True,
                    "api_key": "AIza-test",
                    "audio_model": "gemini-bad",
                    "audio_model_queue": ["gemini-good"],
                    "audio_chunk_seconds": 1000,
                    "audio_overlap_seconds": 0,
                },
            )
            chunks = [
                AudioChunk(part1, 0.0, 1000.0, 0.0, 1000.0),
                AudioChunk(part2, 1000.0, 2000.0, 1000.0, 2000.0),
            ]
            wrong_chunk = (
                "The lecture discusses sparse signal recovery, LASSO, ISTA, FISTA, "
                "ADMM, compressed sensing, nuclear norm minimization, and linear regression. "
            ) * 25
            right_chunk = (
                "老师今天继续讲数据库系统中的并发控制、日志恢复、查询优化和索引结构。"
                "这里会把事务调度和恢复流程放在同一个例子里解释。"
            ) * 80 + (
                "本节术语包括 transaction、isolation level、dirty read、phantom read、"
                "SQL、B+ tree、LSM tree、query optimizer、row lock、deadlock。"
            )
            calls: list[str] = []

            def fake_transcribe_long_audio(**kwargs):
                calls.append(kwargs["model"])
                if kwargs["model"] == "gemini-bad":
                    return wrong_chunk
                return right_chunk

            llm = Mock()
            llm.transcribe_long_audio.side_effect = fake_transcribe_long_audio
            processor = AudioProcessor(cfg=cfg, llm=llm)
            processor._get_cached_duration = Mock(return_value=2000.0)
            processor._split_google_audio = Mock(return_value=chunks)
            hotwords = [
                "transaction",
                "isolation level",
                "dirty read",
                "phantom read",
                "SQL",
                "B+ tree",
                "LSM tree",
                "query optimizer",
                "row lock",
                "deadlock",
            ]

            processor.process(source, hotwords=hotwords, output_path=output_path)

            self.assertEqual(calls, ["gemini-bad", "gemini-bad", "gemini-good", "gemini-good"])
            with open(output_path, encoding="utf-8") as f:
                md = f.read()
            self.assertIn("实际使用模型: gemini-good", md)
            self.assertIn("dirty read", md)
            self.assertNotIn("sparse signal recovery", md)

    def test_google_mode_preserves_model_emitted_fine_segment_markers(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = os.path.join(tmp, "lecture.mp3")
            with open(source, "wb") as f:
                f.write(b"fake audio")
            output_path = os.path.join(tmp, "out.md")

            cfg = AppConfig().with_updates(
                paths={"output_dir": tmp, "temp_dir": tmp},
                google_api={
                    "enabled": True,
                    "api_key": "AIza-test",
                    "audio_model": "gemini-2.5-pro",
                    "audio_chunk_seconds": 1800,
                    "audio_overlap_seconds": 30,
                },
            )
            llm = Mock()
            llm.transcribe_long_audio.return_value = (
                "<!-- meta:segment index=1 time=00:00~05:00 -->\n"
                "第一小段老师讲线性规划。" + "继续讲解。" * 300 + "\n\n"
                "<!-- meta:segment index=2 time=05:00~10:00 -->\n"
                "第二小段老师讲椭球法。" + "继续分析。" * 300
            )
            processor = AudioProcessor(cfg=cfg, llm=llm)
            processor._get_cached_duration = Mock(return_value=600.0)
            processor._split_google_audio = Mock(return_value=[
                AudioChunk(source, 0.0, 600.0, 0.0, 600.0),
            ])

            processor.process(source, output_path=output_path)

            prompt = llm.transcribe_long_audio.call_args.kwargs["system_prompt"]
            self.assertIn("更细的时间戳", prompt)
            with open(output_path, encoding="utf-8") as f:
                md = f.read()
            self.assertEqual(md.count("<!-- meta:segment"), 2)
            self.assertIn("<!-- meta:segment index=1 time=00:00~05:00 -->", md)
            self.assertIn("<!-- meta:segment index=2 time=05:00~10:00 -->", md)
            self.assertNotIn("<!-- meta:segment index=1 time=00:00~10:00 -->", md)

    def test_google_mode_resumes_cached_segments_after_quota_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = os.path.join(tmp, "lecture.mp3")
            part1 = os.path.join(tmp, "part001.mp3")
            part2 = os.path.join(tmp, "part002.mp3")
            for path in (source, part1, part2):
                with open(path, "wb") as f:
                    f.write(b"fake audio")
            output_path = os.path.join(tmp, "out.md")

            cfg = AppConfig().with_updates(
                paths={"output_dir": tmp, "temp_dir": tmp},
                google_api={
                    "enabled": True,
                    "api_key": "AIza-test",
                    "audio_model": "gemini-2.5-pro",
                    "audio_chunk_seconds": 1800,
                    "audio_overlap_seconds": 30,
                },
            )
            chunks = [
                AudioChunk(part1, 0.0, 1830.0, 0.0, 1800.0),
                AudioChunk(part2, 1770.0, 3605.0, 1800.0, 3605.0),
            ]
            first_body = "first cached transcript " + "老师继续讲解课程内容。" * 900
            second_body = "second resumed transcript " + "老师继续讲解课程内容。" * 900

            llm_first = Mock()
            llm_first.transcribe_long_audio.side_effect = [first_body, RuntimeError("quota")]
            processor_first = AudioProcessor(cfg=cfg, llm=llm_first)
            processor_first._get_cached_duration = Mock(return_value=3605.0)
            processor_first._split_google_audio = Mock(return_value=chunks)

            with self.assertRaisesRegex(RuntimeError, "quota"):
                processor_first.process(source, output_path=output_path)
            self.assertFalse(os.path.exists(output_path))

            llm_second = Mock()
            llm_second.transcribe_long_audio.return_value = second_body
            processor_second = AudioProcessor(cfg=cfg, llm=llm_second)
            processor_second._get_cached_duration = Mock(return_value=3605.0)
            processor_second._split_google_audio = Mock(return_value=chunks)

            processor_second.process(source, output_path=output_path)

            self.assertEqual(llm_second.transcribe_long_audio.call_count, 1)
            self.assertEqual(llm_second.transcribe_long_audio.call_args.kwargs["audio_path"], part2)
            with open(output_path, encoding="utf-8") as f:
                md = f.read()
            self.assertIn("first cached transcript", md)
            self.assertIn("second resumed transcript", md)

    def test_google_audio_failure_is_listed_as_incomplete_audio_task(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = os.path.join(tmp, "lecture.mp3")
            part1 = os.path.join(tmp, "part001.mp3")
            part2 = os.path.join(tmp, "part002.mp3")
            for path in (source, part1, part2):
                with open(path, "wb") as f:
                    f.write(b"fake audio")
            output_path = os.path.join(tmp, "out.md")

            cfg = AppConfig().with_updates(
                paths={"output_dir": tmp, "temp_dir": tmp},
                google_api={
                    "enabled": True,
                    "api_key": "AIza-test",
                    "audio_model": "gemini-2.5-pro",
                    "audio_chunk_seconds": 1800,
                    "audio_overlap_seconds": 30,
                },
            )
            chunks = [
                AudioChunk(part1, 0.0, 1830.0, 0.0, 1800.0),
                AudioChunk(part2, 1770.0, 3605.0, 1800.0, 3605.0),
            ]
            llm = Mock()
            llm.transcribe_long_audio.side_effect = [
                "first cached transcript " + "老师继续讲解课程内容。" * 900,
                RuntimeError("network eof"),
            ]
            processor = AudioProcessor(cfg=cfg, llm=llm)
            processor._get_cached_duration = Mock(return_value=3605.0)
            processor._split_google_audio = Mock(return_value=chunks)

            with self.assertRaisesRegex(RuntimeError, "network eof"):
                processor.process(source, output_path=output_path)

            incomplete = processor.checkpoint_mgr.list_incomplete()
            self.assertEqual(len(incomplete), 1)
            self.assertEqual(incomplete[0].task_type, "audio")
            self.assertEqual(incomplete[0].source_path, source)
            self.assertEqual(incomplete[0].output_path, output_path)
            self.assertEqual(incomplete[0].completed_indices, {0})

    def test_google_mode_removes_model_emitted_segment_markers_from_body(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = os.path.join(tmp, "lecture.mp3")
            with open(source, "wb") as f:
                f.write(b"fake audio")
            output_path = os.path.join(tmp, "out.md")

            cfg = AppConfig().with_updates(
                paths={"output_dir": tmp, "temp_dir": tmp},
                google_api={
                    "enabled": True,
                    "api_key": "AIza-test",
                    "audio_model": "gemini-2.5-pro",
                    "audio_chunk_seconds": 1800,
                    "audio_overlap_seconds": 30,
                },
            )
            llm = Mock()
            long_body = "老师继续讲解数据库事务隔离级别和调度等价。" * 1300
            llm.transcribe_long_audio.return_value = (
                long_body
                + "\n<!-- meta:segment index=1 time=00:00~30:00 -->\n"
                + "这行注释来自模型正文，程序需要剥掉。"
            )
            processor = AudioProcessor(cfg=cfg, llm=llm)
            processor._get_cached_duration = Mock(return_value=1800.0)
            processor._split_google_audio = Mock(return_value=[
                AudioChunk(source, 0.0, 1800.0, 0.0, 1800.0),
            ])

            processor.process(source, output_path=output_path)

            with open(output_path, encoding="utf-8") as f:
                md = f.read()
            self.assertEqual(md.count("meta:segment"), 1)
            self.assertIn("老师继续讲解数据库事务隔离级别", md)
            self.assertIn("这行注释来自模型正文", md)

    def test_google_mode_removes_inline_model_segment_markers_from_body(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = os.path.join(tmp, "lecture.mp3")
            with open(source, "wb") as f:
                f.write(b"fake audio")
            output_path = os.path.join(tmp, "out.md")

            cfg = AppConfig().with_updates(
                paths={"output_dir": tmp, "temp_dir": tmp},
                google_api={
                    "enabled": True,
                    "api_key": "AIza-test",
                    "audio_model": "gemini-2.5-pro",
                    "audio_chunk_seconds": 1800,
                    "audio_overlap_seconds": 30,
                },
            )
            llm = Mock()
            long_body = "老师继续讲解马尔可夫链状态分类和极限分布。" * 1300
            llm.transcribe_long_audio.return_value = (
                long_body
                + " <!-- meta:segment index=1 time=00:00~30:00 --> "
                + "后面这句仍然是正文。"
            )
            processor = AudioProcessor(cfg=cfg, llm=llm)
            processor._get_cached_duration = Mock(return_value=1800.0)
            processor._split_google_audio = Mock(return_value=[
                AudioChunk(source, 0.0, 1800.0, 0.0, 1800.0),
            ])

            processor.process(source, output_path=output_path)

            with open(output_path, encoding="utf-8") as f:
                md = f.read()
            self.assertEqual(md.count("meta:segment"), 1)
            self.assertIn("老师继续讲解马尔可夫链", md)
            self.assertIn("后面这句仍然是正文", md)

    def test_google_mode_rejects_hotword_only_long_audio_body(self):
        with tempfile.TemporaryDirectory() as tmp:
            audio_path = os.path.join(tmp, "lecture.mp3")
            with open(audio_path, "wb") as f:
                f.write(b"fake audio")
            output_path = os.path.join(tmp, "out.md")

            cfg = AppConfig().with_updates(
                paths={"output_dir": tmp, "temp_dir": tmp},
                google_api={
                    "enabled": True,
                    "api_key": "AIza-test",
                    "audio_model": "gemini-3.5-flash",
                },
            )
            llm = Mock()
            llm.transcribe_long_audio.return_value = "根据您提供的板书内容，为您提取的专业术语热词表如下：共产主义"
            processor = AudioProcessor(cfg=cfg, llm=llm)
            processor._get_cached_duration = Mock(return_value=9_600.0)
            processor._split_google_audio = Mock(return_value=[
                AudioChunk(audio_path, 0.0, 9600.0, 0.0, 9600.0),
            ])

            with self.assertRaisesRegex(RuntimeError, "Google 长音频识别疑似假成功"):
                processor.process(audio_path, output_path=output_path)

            self.assertFalse(os.path.exists(output_path))

    def test_google_mode_rejects_too_short_long_audio_body(self):
        with tempfile.TemporaryDirectory() as tmp:
            audio_path = os.path.join(tmp, "lecture.mp3")
            with open(audio_path, "wb") as f:
                f.write(b"fake audio")
            output_path = os.path.join(tmp, "out.md")

            cfg = AppConfig().with_updates(
                paths={"output_dir": tmp, "temp_dir": tmp},
                google_api={
                    "enabled": True,
                    "api_key": "AIza-test",
                    "audio_model": "gemini-3.5-flash",
                },
            )
            llm = Mock()
            llm.transcribe_long_audio.return_value = "老师开始讲课。"
            processor = AudioProcessor(cfg=cfg, llm=llm)
            processor._get_cached_duration = Mock(return_value=9_600.0)
            processor._split_google_audio = Mock(return_value=[
                AudioChunk(audio_path, 0.0, 9600.0, 0.0, 9600.0),
            ])

            with self.assertRaisesRegex(RuntimeError, "转写正文过短"):
                processor.process(audio_path, output_path=output_path)

    def test_google_mode_rejects_prompt_echo_long_audio_body(self):
        with tempfile.TemporaryDirectory() as tmp:
            audio_path = os.path.join(tmp, "lecture.mp3")
            with open(audio_path, "wb") as f:
                f.write(b"fake audio")
            output_path = os.path.join(tmp, "out.md")

            cfg = AppConfig().with_updates(
                paths={"output_dir": tmp, "temp_dir": tmp},
                google_api={
                    "enabled": True,
                    "api_key": "AIza-test",
                    "audio_model": "gemini-3.5-flash",
                },
            )
            llm = Mock()
            llm.transcribe_long_audio.return_value = (
                "请把这段课程录音尽量逐字转写成中文文本。要求：只输出转写内容本身。"
                "嗯，后面才像课堂内容。"
            )
            processor = AudioProcessor(cfg=cfg, llm=llm)
            processor._get_cached_duration = Mock(return_value=None)
            processor._split_google_audio = Mock(return_value=[
                AudioChunk(audio_path, 0.0, 20.0, 0.0, 20.0),
            ])

            with self.assertRaisesRegex(RuntimeError, "提示词回显"):
                processor.process(audio_path, output_path=output_path)

    def test_google_mode_rejects_repetitive_noise_long_audio_body(self):
        with tempfile.TemporaryDirectory() as tmp:
            audio_path = os.path.join(tmp, "lecture.mp3")
            with open(audio_path, "wb") as f:
                f.write(b"fake audio")
            output_path = os.path.join(tmp, "out.md")

            cfg = AppConfig().with_updates(
                paths={"output_dir": tmp, "temp_dir": tmp},
                google_api={
                    "enabled": True,
                    "api_key": "AIza-test",
                    "audio_model": "gemini-3.5-flash",
                },
            )
            llm = Mock()
            llm.transcribe_long_audio.return_value = "嗯，" + "你，" * 80 + "后面仍然是重复噪声。"
            processor = AudioProcessor(cfg=cfg, llm=llm)
            processor._get_cached_duration = Mock(return_value=None)
            processor._split_google_audio = Mock(return_value=[
                AudioChunk(audio_path, 0.0, 20.0, 0.0, 20.0),
            ])

            with self.assertRaisesRegex(RuntimeError, "重复噪声"):
                processor.process(audio_path, output_path=output_path)

    def test_google_mode_rejects_extremely_weak_long_audio_before_upload(self):
        with tempfile.TemporaryDirectory() as tmp:
            audio_path = os.path.join(tmp, "lecture.mp3")
            with open(audio_path, "wb") as f:
                f.write(b"fake audio")
            output_path = os.path.join(tmp, "out.md")

            cfg = AppConfig().with_updates(
                paths={"output_dir": tmp, "temp_dir": tmp},
                google_api={
                    "enabled": True,
                    "api_key": "AIza-test",
                    "audio_model": "gemini-3.5-flash",
                },
            )
            llm = Mock()
            processor = AudioProcessor(cfg=cfg, llm=llm)
            processor._get_cached_duration = Mock(return_value=9_600.0)

            with patch(
                "OCRLLM.processors.audio.measure_audio_signal",
                return_value=AudioSignalStats(mean_volume_db=-71.1, max_volume_db=-60.0),
            ):
                with self.assertRaisesRegex(RuntimeError, "音轨整体响度过低"):
                    processor.process(audio_path, output_path=output_path)

            llm.transcribe_long_audio.assert_not_called()
            self.assertFalse(os.path.exists(output_path))

    def test_google_mode_allows_sparse_long_audio_when_peak_is_clear(self):
        with tempfile.TemporaryDirectory() as tmp:
            audio_path = os.path.join(tmp, "lecture.mp3")
            with open(audio_path, "wb") as f:
                f.write(b"fake audio")
            output_path = os.path.join(tmp, "out.md")

            cfg = AppConfig().with_updates(
                paths={"output_dir": tmp, "temp_dir": tmp},
                google_api={
                    "enabled": True,
                    "api_key": "AIza-test",
                    "audio_model": "gemini-3.5-flash",
                },
            )
            llm = Mock()
            llm.transcribe_long_audio.return_value = "老师继续讲解马克思主义基本原理课程内容。" * 2000
            processor = AudioProcessor(cfg=cfg, llm=llm)
            processor._get_cached_duration = Mock(return_value=9_600.0)
            processor._split_google_audio = Mock(return_value=[
                AudioChunk(audio_path, 0.0, 9600.0, 0.0, 9600.0),
            ])

            with patch(
                "OCRLLM.processors.audio.measure_audio_signal",
                return_value=AudioSignalStats(mean_volume_db=-73.7, max_volume_db=-7.6),
            ):
                processor.process(audio_path, output_path=output_path)

            llm.transcribe_long_audio.assert_called_once()
            self.assertTrue(os.path.exists(output_path))

    def test_qwen_no_valid_fragment_writes_warning_without_short_audio_fallback(self):
        with tempfile.TemporaryDirectory() as tmp:
            audio_path = os.path.join(tmp, "lecture.mp3")
            with open(audio_path, "wb") as f:
                f.write(b"fake audio")
            output_path = os.path.join(tmp, "out.md")

            cfg = AppConfig().with_updates(
                paths={"output_dir": tmp, "temp_dir": tmp},
                api={"api_key": "sk-test"},
                models={"allow_asr_short_fallback": False},
            )
            processor = AudioProcessor.__new__(AudioProcessor)
            processor.cfg = cfg
            processor.reporter = Mock()
            processor.reporter.cancel_event = None
            processor._report = Mock()
            processor._report_content = Mock()
            processor._close_http_session = Mock()
            processor._ensure_upload_format = Mock(return_value=audio_path)
            processor._should_use_short_asr = Mock(return_value=(False, 600.0))
            processor._upload_file = Mock(return_value="https://example.com/audio.mp3")
            processor._submit_task = Mock(return_value="task-id")
            processor._wait_result = Mock(
                side_effect=ASRNoValidFragmentError("DashScope filetrans 返回 NO_VALID_FRAGMENT")
            )
            processor._short_asr = Mock(side_effect=AssertionError("short fallback must not run"))

            result = processor.process(audio_path, output_path=output_path)

            self.assertEqual(result, output_path)
            with open(output_path, encoding="utf-8") as f:
                message = f.read()
            self.assertIn("filetrans", message)
            self.assertIn("NO_VALID_FRAGMENT", message)
            self.assertIn("音频识别质量警告", message)
            self.assertNotIn("自动回退", message)
            self.assertNotIn("分段短音频", message)
            processor._short_asr.assert_not_called()

    def test_video_phase5_uses_google_long_audio_route(self):
        with tempfile.TemporaryDirectory() as tmp:
            audio_path = os.path.join(tmp, "lecture.mp3")
            with open(audio_path, "wb") as f:
                f.write(b"fake audio")

            cfg = AppConfig().with_updates(
                paths={"output_dir": tmp, "temp_dir": tmp},
                google_api={
                    "enabled": True,
                    "api_key": "AIza-test",
                    "audio_model": "gemini-3.5-flash",
                },
            )
            llm = Mock()
            llm.transcribe_long_audio.return_value = "video audio through google"
            pool = Mock()
            pool.get_single_client.return_value = llm
            processor = VideoProcessor(cfg=cfg, llm=llm, api_pool=pool)

            with patch("OCRLLM.processors.audio.AudioProcessor._get_cached_duration", return_value=None), \
                 patch("OCRLLM.processors.audio.AudioProcessor._split_google_audio", return_value=[
                     AudioChunk(audio_path, 0.0, 20.0, 0.0, 20.0),
                 ]):
                processor._phase5_asr(audio_path, ["convex"], tmp, "lecture")

            llm.transcribe_long_audio.assert_called_once()
            output_path = os.path.join(tmp, "lecture_录音识别.md")
            with open(output_path, encoding="utf-8") as f:
                self.assertIn("video audio through google", f.read())

    def test_google_transcript_rejects_topic_mismatch_when_hotwords_have_no_overlap(self):
        wrong_transcript = (
            "The lecture discusses sparse signal recovery, LASSO, ISTA, FISTA, "
            "ADMM, compressed sensing, nuclear norm minimization, and linear regression. "
        ) * 260
        expected_terms = [
            "transaction",
            "isolation level",
            "dirty read",
            "phantom read",
            "SQL",
            "B+ tree",
            "LSM tree",
            "query optimizer",
            "row lock",
            "deadlock",
        ]

        reason = google_audio_transcript_invalid_reason(
            wrong_transcript,
            duration=3600,
            expected_terms=expected_terms,
        )

        self.assertIsNotNone(reason)
        self.assertIn("topic mismatch", reason)

    def test_google_transcript_rejects_timestamp_only_output(self):
        timestamp_only = " ".join(f"{minute:02d}:{second:02d}" for minute in range(30) for second in range(60))

        reason = google_audio_transcript_invalid_reason(timestamp_only, duration=1800)

        self.assertIsNotNone(reason)
        self.assertIn("timestamp-only", reason)

    def test_google_transcript_rejects_repeated_filler_output(self):
        repeated_filler = "哎\n" + "嗯\n" * 500

        reason = google_audio_transcript_invalid_reason(repeated_filler, duration=1800)

        self.assertIsNotNone(reason)
        self.assertIn("repeated filler", reason)

    def test_google_transcript_rejects_repeated_hotword_echo_output(self):
        expected_terms = [
            "事务隔离",
            "脏读",
            "幻读",
            "可串行化",
            "两阶段锁",
            "B+ tree",
            "LSM tree",
            "查询优化器",
        ]
        hotword_echo = ("热词表\n" + "\n".join(expected_terms) + "\n") * 120

        reason = google_audio_transcript_invalid_reason(
            hotword_echo,
            duration=1800,
            expected_terms=expected_terms,
        )

        self.assertIsNotNone(reason)
        self.assertIn("热词", reason)

    def test_video_phase5_resume_rejects_invalid_google_transcript_with_hotwords(self):
        with tempfile.TemporaryDirectory() as tmp:
            stem = "lecture"
            output_path = os.path.join(tmp, f"{stem}_\u5f55\u97f3\u8bc6\u522b.md")
            wrong_transcript = (
                "The lecture discusses sparse signal recovery, LASSO, ISTA, FISTA, "
                "ADMM, compressed sensing, nuclear norm minimization, and linear regression. "
            ) * 260
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(wrong_transcript)

            processor = VideoProcessor.__new__(VideoProcessor)
            processor.cfg = AppConfig().with_updates(
                google_api={"enabled": True, "api_key": "AIza-test"},
            )
            context = VideoProcessContext(
                video_path="lecture.mp4",
                output_dir=tmp,
                frames_dir=os.path.join(tmp, "frames"),
                debug_dir=tmp,
                info_path=os.path.join(tmp, "frame_info.json"),
                stem=stem,
                selection=VideoPipelineSelection(frames=False, audio=True),
                hotwords=[
                    "transaction",
                    "isolation level",
                    "dirty read",
                    "phantom read",
                    "SQL",
                    "B+ tree",
                    "LSM tree",
                    "query optimizer",
                    "row lock",
                    "deadlock",
                ],
            )

            self.assertFalse(AudioRecognizePhase().can_resume(processor, context))

    def test_google_audio_checkpoint_changes_when_source_file_changes(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = os.path.join(tmp, "lecture.mp3")
            output_path = os.path.join(tmp, "out.md")
            chunk = AudioChunk(source, 0.0, 20.0, 0.0, 20.0)
            cfg = AppConfig().with_updates(
                paths={"output_dir": tmp, "temp_dir": tmp},
                api={"api_key": "sk-test"},
            )
            processor = AudioProcessor(cfg=cfg, llm=Mock())

            with open(source, "wb") as f:
                f.write(b"first")
            first_path, first_meta = processor._google_audio_checkpoint_path(
                audio_path=source,
                output_path=output_path,
                base_prompt="prompt",
                chunks=[chunk],
            )

            with open(source, "wb") as f:
                f.write(b"second-version")
            second_path, second_meta = processor._google_audio_checkpoint_path(
                audio_path=source,
                output_path=output_path,
                base_prompt="prompt",
                chunks=[chunk],
            )

            self.assertNotEqual(first_path, second_path)
            self.assertNotEqual(first_meta["source_size"], second_meta["source_size"])

    def test_google_long_audio_upload_uses_ascii_safe_temp_path_for_chinese_filenames(self):
        with tempfile.TemporaryDirectory() as tmp:
            audio_path = Path(tmp) / "数据库及实现_录音.mp3"
            audio_path.write_bytes(b"fake audio")
            uploaded_paths: list[str] = []

            class FakeFiles:
                def upload(self, file):
                    uploaded_paths.append(str(file))
                    Path(file).read_bytes()
                    return SimpleNamespace(name="files/test", state="ACTIVE")

                def get(self, name):
                    return SimpleNamespace(name=name, state="ACTIVE")

            class FakeModels:
                def generate_content(self, **_kwargs):
                    return SimpleNamespace(text="ok transcript")

            cfg = AppConfig().with_updates(google_api={"enabled": True, "api_key": "AIza-test"})
            client = GoogleProviderClient(cfg=cfg)
            client._client = SimpleNamespace(files=FakeFiles(), models=FakeModels())

            text = client.transcribe_long_audio(str(audio_path), model="gemini-3.5-flash")

            self.assertEqual(text, "ok transcript")
            self.assertEqual(len(uploaded_paths), 1)
            uploaded_paths[0].encode("ascii")
            self.assertNotEqual(uploaded_paths[0], str(audio_path))


if __name__ == "__main__":
    unittest.main()
