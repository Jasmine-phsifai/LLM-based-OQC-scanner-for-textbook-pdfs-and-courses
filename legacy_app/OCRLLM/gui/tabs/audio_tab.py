"""
语音识别选项卡。
"""

from __future__ import annotations

import os
import logging

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QMessageBox,
)

from OCRLLM import prompts
from OCRLLM.gui.batch_tasks import BatchFileTask, run_batch_tasks
from OCRLLM.gui.widgets import FileInput, PromptButton, browse_file, browse_files, join_paths_text, split_paths_text


class AudioTab(QWidget):
    """语音识别选项卡 GUI。"""
    def __init__(self, get_cfg, start_worker, get_output_in_place=None, parent=None):
        super().__init__(parent)
        self._get_cfg = get_cfg
        self._start_worker = start_worker
        self._get_output_in_place = get_output_in_place or (lambda: False)
        self._build_ui()

    def _build_ui(self):
        vbox = QVBoxLayout(self)

        self._audio_path = FileInput(
            accept_exts=['mp3', 'wav', 'm4a', 'flac', 'wma', 'ogg', 'opus', 'aac'],
            multi=True,
            placeholder="选择或拖入音频文件（支持多选，; 分隔）")
        from OCRLLM.gui.tabs.pdf_tab import _file_row
        vbox.addLayout(_file_row(
            "音频文件:", self._audio_path, "选择多份",
            lambda: browse_files(self, "选择音频文件",
                                "音频文件 (*.mp3 *.wav *.m4a *.flac *.wma *.ogg *.opus *.aac);;所有文件 (*)",
                                self._audio_path)))

        row2 = QHBoxLayout()
        row2.addWidget(QLabel("热词 (逗号分隔):"))
        self._hotwords = QLineEdit()
        row2.addWidget(self._hotwords, stretch=1)
        vbox.addLayout(row2)

        row3 = QHBoxLayout()
        row3.addWidget(QLabel("或导入热词文件:"))
        self._hotword_file = FileInput(accept_exts=['txt'], placeholder="选择或拖入 .txt 热词文件")
        row3.addWidget(self._hotword_file, stretch=1)
        from PyQt5.QtWidgets import QPushButton
        btn_hw = QPushButton("浏览")
        btn_hw.clicked.connect(
            lambda: browse_file(self, "选择热词文件", "文本文件 (*.txt);;所有文件 (*)", self._hotword_file))
        row3.addWidget(btn_hw)
        vbox.addLayout(row3)

        from OCRLLM.gui.app import make_action_buttons
        self._prompt = PromptButton("语音识别", "audio_transcribe", prompts.AUDIO_TRANSCRIBE, self)
        vbox.addLayout(make_action_buttons(
            "▶ 开始识别语音", self._run,
            self._prompt.reset_to_default,
            extra_widgets=[self._prompt]))

        from PyQt5.QtWidgets import QPushButton
        repair_row = QHBoxLayout()
        self._repair_btn = QPushButton("🔧 修复失败分段")
        self._repair_btn.setToolTip("扫描已有识别结果中的失败分段，仅重新识别那些部分")
        self._repair_btn.clicked.connect(self._run_repair)
        repair_row.addWidget(self._repair_btn)
        repair_row.addStretch()
        vbox.addLayout(repair_row)

    def set_input_paths(self, paths: list[str] | tuple[str, ...]):
        """从外部设置音频文件路径（如拖放）。

        Args:
            paths: 文件路径列表。
        """
        if not paths:
            self._audio_path.clear()
            return
        self._audio_path.setText(join_paths_text(list(paths)))

    def _run(self):
        audio_paths = split_paths_text(self._audio_path.text())
        if not audio_paths:
            QMessageBox.warning(self, "提示", "请先选择音频文件"); return
        missing = [audio_path for audio_path in audio_paths if not os.path.isfile(audio_path)]
        if missing:
            QMessageBox.warning(self, "提示", "文件不存在:\n" + "\n".join(missing[:10])); return

        hw_text = self._hotwords.text().strip()
        hw_file = self._hotword_file.text().strip()
        hotwords = []
        if hw_text:
            hotwords.extend([w.strip() for w in hw_text.split(",") if w.strip()])
        if hw_file and os.path.isfile(hw_file):
            with open(hw_file, "r", encoding="utf-8") as f:
                for line in f:
                    word = line.strip()
                    if word:
                        hotwords.append(word)

        prompt_override = self._prompt.prompt_text()

        # 在原位置输出：结果文件放到音频文件同级目录
        def _output_path_for(audio_path: str) -> str | None:
            if not self._get_output_in_place():
                return None
            src_dir = os.path.dirname(os.path.abspath(audio_path))
            stem = os.path.splitext(os.path.basename(audio_path))[0]
            return os.path.join(src_dir, f"{stem}_录音识别.md")

        if len(audio_paths) == 1:
            audio_path = audio_paths[0]
            output_path = _output_path_for(audio_path)

            def task(reporter):
                from OCRLLM.processors.audio import AudioProcessor
                cfg = self._get_cfg()
                logging.info("热词: %s%s", hotwords[:20], "..." if len(hotwords) > 20 else "")
                proc = AudioProcessor(cfg=cfg, reporter=reporter)
                result = proc.process(audio_path=audio_path, hotwords=hotwords or None,
                                      output_path=output_path,
                                      prompt_template=prompt_override or None)
                return f"语音识别完成: {result}"

            if self._start_worker(task):
                self._prompt.consume_temporary()
            return

        def task(reporter):
            from OCRLLM.processors.audio import AudioProcessor
            cfg = self._get_cfg()
            logging.info("热词: %s%s", hotwords[:20], "..." if len(hotwords) > 20 else "")
            tasks = []
            for audio_path in audio_paths:
                output_path = _output_path_for(audio_path)

                def _run_one(task_cfg, child_reporter, *, path=audio_path, out=output_path):
                    proc = AudioProcessor(cfg=task_cfg, reporter=child_reporter)
                    return proc.process(
                        audio_path=path,
                        hotwords=hotwords or None,
                        output_path=out,
                        prompt_template=prompt_override or None,
                    )

                tasks.append(BatchFileTask(
                    source_path=audio_path,
                    display_name=os.path.basename(audio_path),
                    run=_run_one,
                ))
            return run_batch_tasks(task_kind="audio", task_label="音频", cfg=cfg, reporter=reporter, tasks=tasks)

        if self._start_worker(task):
            self._prompt.consume_temporary()

    def _run_repair(self):
        audio_paths = split_paths_text(self._audio_path.text())
        if not audio_paths:
            QMessageBox.warning(self, "提示", "请先选择需要修复的音频文件")
            return

        from OCRLLM.processors.audio import AudioProcessor

        cfg = self._get_cfg()

        def _output_path_for(audio_path: str) -> str:
            if self._get_output_in_place():
                src_dir = os.path.dirname(os.path.abspath(audio_path))
                stem = os.path.splitext(os.path.basename(audio_path))[0]
                return os.path.join(src_dir, f"{stem}_录音识别.md")
            stem = os.path.splitext(os.path.basename(audio_path))[0]
            return os.path.join(cfg.paths.output_dir, f"{stem}_录音识别.md")

        # Pre-check
        repair_targets = []
        for audio_path in audio_paths:
            md_path = _output_path_for(audio_path)
            if not os.path.isfile(md_path):
                continue
            failed = AudioProcessor.find_failed_segments(md_path)
            if failed:
                repair_targets.append((audio_path, md_path, failed))

        if not repair_targets:
            QMessageBox.information(self, "修复", "所选音频的识别结果中没有发现失败分段。")
            return

        hw_text = self._hotwords.text().strip()
        hw_file = self._hotword_file.text().strip()
        hotwords = []
        if hw_text:
            hotwords.extend([w.strip() for w in hw_text.split(",") if w.strip()])
        if hw_file and os.path.isfile(hw_file):
            with open(hw_file, "r", encoding="utf-8") as f:
                for line in f:
                    word = line.strip()
                    if word:
                        hotwords.append(word)

        prompt_text = self._prompt.prompt_text()

        def task(reporter):
            task_cfg = self._get_cfg()
            results = []
            any_success = False
            for audio_path, md_path, failed in repair_targets:
                proc = AudioProcessor(cfg=task_cfg, reporter=reporter)
                try:
                    proc.repair(audio_path, md_path,
                                hotwords=hotwords or None,
                                prompt_template=prompt_text or None)
                    results.append(f"✓ {os.path.basename(audio_path)}: 全部 {len(failed)} 分段修复成功")
                    any_success = True
                except RuntimeError:
                    remaining = AudioProcessor.find_failed_segments(md_path)
                    fixed = len(failed) - len(remaining)
                    if fixed > 0:
                        results.append(
                            f"⚠ {os.path.basename(audio_path)}: {fixed}/{len(failed)} 分段已修复，"
                            f"仍有 {len(remaining)} 分段失败"
                        )
                        any_success = True
                    else:
                        results.append(f"✗ {os.path.basename(audio_path)}: 全部 {len(failed)} 分段修复失败")
                except Exception as e:
                    results.append(f"✗ {os.path.basename(audio_path)}: {e}")
            header = "修复完成" if any_success else "修复失败 — 所有分段仍无法识别"
            return f"{header}:\n" + "\n".join(results)

        self._start_worker(task)