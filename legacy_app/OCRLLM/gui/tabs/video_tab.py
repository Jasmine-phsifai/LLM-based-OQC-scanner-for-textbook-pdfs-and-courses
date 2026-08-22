"""
录课视频处理选项卡。
"""

from __future__ import annotations

import os

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QCheckBox, QMessageBox, QPushButton,
)

from OCRLLM import prompts
from OCRLLM.gui.batch_tasks import BatchFileTask, run_batch_tasks
from OCRLLM.gui.widgets import FileInput, PromptButton, browse_files, join_paths_text, split_paths_text
from OCRLLM.processors.video_pipeline_selection import VideoPipelineSelection


class VideoTab(QWidget):
    """录课视频处理选项卡 GUI。"""
    def __init__(self, get_cfg, start_worker, get_tracker=None, get_output_in_place=None, parent=None):
        super().__init__(parent)
        self._get_cfg = get_cfg
        self._start_worker = start_worker
        self._get_tracker = get_tracker
        self._get_output_in_place = get_output_in_place or (lambda: False)
        self._build_ui()

    def _build_ui(self):
        vbox = QVBoxLayout(self)

        self._video_path = FileInput(
            accept_exts=['mp4', 'avi', 'mkv', 'mov', 'flv', 'wmv'],
            multi=True,
            placeholder="选择或拖入视频文件（支持多选，; 分隔）")
        from OCRLLM.gui.tabs.pdf_tab import _file_row
        vbox.addLayout(_file_row(
            "视频文件:", self._video_path, "选择多份",
            lambda: browse_files(self, "选择视频文件",
                                "视频文件 (*.mp4 *.avi *.mkv *.mov *.flv *.wmv);;所有文件 (*)",
                                self._video_path)))

        # 管线选择：视频里的两个产物互不依赖，可以单独跑、单独重跑。
        pipeline_row = QHBoxLayout()
        pipeline_row.addWidget(QLabel("识别内容:"))
        self._frames_pipeline = QCheckBox("板书/课件（抽帧 → 大模型识别）")
        self._frames_pipeline.setChecked(True)
        self._audio_pipeline = QCheckBox("录音（提取音频 → 语音识别）")
        self._audio_pipeline.setChecked(True)
        pipeline_row.addWidget(self._frames_pipeline)
        pipeline_row.addWidget(self._audio_pipeline)
        pipeline_row.addStretch()
        vbox.addLayout(pipeline_row)

        option_row = QHBoxLayout()
        self._keep_intermediates = QCheckBox("保留中间文件（音频、提取帧）")
        self._keep_intermediates.setToolTip(
            "默认完成后删除可重建的中间文件；识别结果和热词表任何情况下都不会被删。"
        )
        option_row.addWidget(self._keep_intermediates)
        option_row.addStretch()
        vbox.addLayout(option_row)

        from OCRLLM.gui.app import make_action_buttons
        self._board_prompt = PromptButton("录课板书/课件识别", "video_board", prompts.BOARD_WITH_HOTWORDS, self)
        self._audio_prompt = PromptButton("录课语音识别", "video_audio_transcribe", prompts.AUDIO_TRANSCRIBE, self)
        vbox.addLayout(make_action_buttons(
            "▶ 开始处理视频", self._run,
            self._reset_prompts_to_default,
            extra_widgets=[self._board_prompt, self._audio_prompt]))

        repair_row = QHBoxLayout()
        self._repair_btn = QPushButton("🔧 修复失败帧/分段")
        self._repair_btn.setToolTip("扫描已有识别结果中的失败帧或分段，仅重新识别那些部分")
        self._repair_btn.clicked.connect(self._run_repair)
        repair_row.addWidget(self._repair_btn)
        repair_row.addStretch()
        vbox.addLayout(repair_row)

    def _reset_prompts_to_default(self):
        self._board_prompt.reset_to_default()
        self._audio_prompt.reset_to_default()

    def set_input_paths(self, paths: list[str] | tuple[str, ...]):
        """从外部设置视频文件路径（如拖放）。

        Args:
            paths: 文件路径列表。
        """
        if not paths:
            self._video_path.clear()
            return
        self._video_path.setText(join_paths_text(list(paths)))

    def _selection(self) -> VideoPipelineSelection:
        return VideoPipelineSelection(
            frames=self._frames_pipeline.isChecked(),
            audio=self._audio_pipeline.isChecked(),
        )

    def _ask_reuse_or_rerun(self, cfg, video_paths, selection, output_dir_for) -> bool | None:
        """已有产物时询问复用还是重跑。

        Returns:
            True 复用已有产物，False 重跑，None 用户取消。
        """
        from OCRLLM.processors.video import VideoProcessor

        conflicts = []
        for video_path in video_paths:
            products = VideoProcessor.existing_products(cfg, video_path, output_dir_for(video_path))
            done = [
                label
                for label, key in (("板书识别", "frames"), ("录音识别", "audio"))
                if products.get(key) and getattr(selection, key)
            ]
            if done:
                conflicts.append(f"{os.path.basename(video_path)}: 已有 {'、'.join(done)}")
        if not conflicts:
            return False

        box = QMessageBox(self)
        box.setWindowTitle("已有识别结果")
        box.setText("以下视频这次要跑的管线已经有结果了：\n\n" + "\n".join(conflicts[:10]))
        box.setInformativeText(
            "复用：保留已完成的部分，只补缺失的内容。\n"
            "重跑：重新识别所选管线，未勾选的管线结果不受影响。"
        )
        reuse_btn = box.addButton("复用已有结果", QMessageBox.AcceptRole)
        rerun_btn = box.addButton("重跑所选管线", QMessageBox.DestructiveRole)
        box.addButton("取消", QMessageBox.RejectRole)
        box.setDefaultButton(reuse_btn)
        box.exec_()

        clicked = box.clickedButton()
        if clicked is reuse_btn:
            return True
        if clicked is rerun_btn:
            return False
        return None

    def _run(self):
        video_paths = split_paths_text(self._video_path.text())
        if not video_paths:
            QMessageBox.warning(self, "提示", "请先选择视频文件"); return
        missing = [video_path for video_path in video_paths if not os.path.isfile(video_path)]
        if missing:
            QMessageBox.warning(self, "提示", "文件不存在:\n" + "\n".join(missing[:10])); return

        selection = self._selection()
        if not selection.frames and not selection.audio:
            QMessageBox.warning(self, "提示", "请至少勾选一项识别内容"); return

        cleanup_intermediates = not self._keep_intermediates.isChecked()
        prompt_text = self._board_prompt.prompt_text()
        audio_prompt_text = self._audio_prompt.prompt_text()

        # 在原位置输出：输出目录放在视频文件同级目录
        def _output_dir_for(video_path: str) -> str | None:
            if not self._get_output_in_place():
                return None
            from pathlib import Path
            src_dir = os.path.dirname(os.path.abspath(video_path))
            return os.path.join(src_dir, Path(video_path).stem)

        cfg = self._get_cfg()
        resume = self._ask_reuse_or_rerun(cfg, video_paths, selection, _output_dir_for)
        if resume is None:
            return

        if len(video_paths) == 1:
            video_path = video_paths[0]
            output_dir = _output_dir_for(video_path)

            def task(reporter):
                from OCRLLM.processors.video import VideoProcessor
                task_cfg = self._get_cfg()
                tracker = self._get_tracker() if self._get_tracker else None
                proc = VideoProcessor(cfg=task_cfg, reporter=reporter, tracker=tracker)
                result = proc.process(
                    video_path=video_path, output_dir=output_dir,
                    selection=selection,
                    resume=resume,
                    cleanup_intermediates=cleanup_intermediates,
                    prompt_template=prompt_text or None,
                    audio_prompt_template=audio_prompt_text or None,
                )

                md_path = result.get("board_md", "")
                md_size = f"{os.path.getsize(md_path)/1024:.1f}KB" if md_path and os.path.exists(md_path) else "无"
                frames_dir = result.get("frames_dir", "")
                n = len([f for f in os.listdir(frames_dir) if f.endswith(".jpg")]) if frames_dir and os.path.isdir(frames_dir) else 0
                return f"视频处理完成!\n帧数: {n}\nMD: {md_size}\n输出: {result.get('output_dir', '')}"

            if self._start_worker(task):
                self._board_prompt.consume_temporary()
                self._audio_prompt.consume_temporary()
            return

        def task(reporter):
            from OCRLLM.processors.video import VideoProcessor
            batch_cfg = self._get_cfg()
            tasks = []
            for video_path in video_paths:
                output_dir = _output_dir_for(video_path)

                def _run_one(task_cfg, child_reporter, *, path=video_path, out=output_dir):
                    proc = VideoProcessor(cfg=task_cfg, reporter=child_reporter)
                    result = proc.process(
                        video_path=path,
                        output_dir=out,
                        selection=selection,
                        resume=resume,
                        cleanup_intermediates=cleanup_intermediates,
                        prompt_template=prompt_text or None,
                        audio_prompt_template=audio_prompt_text or None,
                    )
                    return result.get("output_dir", "")

                tasks.append(BatchFileTask(
                    source_path=video_path,
                    display_name=os.path.basename(video_path),
                    run=_run_one,
                ))
            return run_batch_tasks(task_kind="video", task_label="视频", cfg=batch_cfg, reporter=reporter, tasks=tasks)

        if self._start_worker(task):
            self._board_prompt.consume_temporary()
            self._audio_prompt.consume_temporary()

    def _run_repair(self):
        video_paths = split_paths_text(self._video_path.text())
        if not video_paths:
            QMessageBox.warning(self, "提示", "请先选择需要修复的视频文件")
            return

        from pathlib import Path as _Path
        from OCRLLM.processors.video import VideoProcessor
        from OCRLLM.processors.audio import AudioProcessor

        cfg = self._get_cfg()

        def _output_dir_for(video_path: str) -> str:
            if self._get_output_in_place():
                src_dir = os.path.dirname(os.path.abspath(video_path))
                return os.path.join(src_dir, _Path(video_path).stem)
            return VideoProcessor.default_output_dir(cfg, video_path)

        # Pre-check: find repair targets
        repair_targets = []  # (video_path, output_dir, board_failed, audio_failed)
        for video_path in video_paths:
            output_dir = _output_dir_for(video_path)
            stem = VideoProcessor._safe_output_stem(_Path(video_path).stem)
            board_md = VideoProcessor._phase4_board_path(output_dir, stem)
            audio_md = VideoProcessor._phase5_output_path(output_dir, stem)

            board_frames = VideoProcessor.find_failed_frames(board_md)
            board_batches = VideoProcessor.find_failed_batch_indices(board_md)
            audio_segments = AudioProcessor.find_failed_segments(audio_md)

            if board_frames or board_batches or audio_segments:
                repair_targets.append((
                    video_path, output_dir,
                    len(board_frames) + len(board_batches),
                    len(audio_segments),
                ))

        if not repair_targets:
            QMessageBox.information(self, "修复", "所选视频的识别结果中没有发现失败项。")
            return

        prompt_text = self._board_prompt.prompt_text()
        audio_prompt_text = self._audio_prompt.prompt_text()

        def task(reporter):
            task_cfg = self._get_cfg()
            results = []
            any_success = False

            for video_path, output_dir, n_board, n_audio in repair_targets:
                stem = VideoProcessor._safe_output_stem(_Path(video_path).stem)
                basename = os.path.basename(video_path)
                file_results = []

                # Board repair
                if n_board > 0:
                    try:
                        proc = VideoProcessor(cfg=task_cfg, reporter=reporter)
                        proc.repair_board(
                            video_path, output_dir,
                            prompt_template=prompt_text or None,
                        )
                        file_results.append(f"板书: 全部修复成功")
                        any_success = True
                    except RuntimeError as e:
                        board_md = VideoProcessor._phase4_board_path(output_dir, stem)
                        remaining = (
                            len(VideoProcessor.find_failed_frames(board_md))
                            + len(VideoProcessor.find_failed_batch_indices(board_md))
                        )
                        fixed = n_board - remaining
                        if fixed > 0:
                            file_results.append(f"板书: {fixed}/{n_board} 项已修复，仍有 {remaining} 项失败")
                            any_success = True
                        else:
                            file_results.append(f"板书: 全部修复失败")
                    except Exception as e:
                        file_results.append(f"板书: {e}")

                # Audio repair
                if n_audio > 0:
                    try:
                        audio_path = VideoProcessor._phase1_audio_path(output_dir, stem)
                        audio_md = VideoProcessor._phase5_output_path(output_dir, stem)
                        proc = AudioProcessor(cfg=task_cfg, reporter=reporter)
                        proc.repair(
                            audio_path, audio_md,
                            prompt_template=audio_prompt_text or None,
                        )
                        file_results.append(f"录音: 全部修复成功")
                        any_success = True
                    except RuntimeError as e:
                        audio_md = VideoProcessor._phase5_output_path(output_dir, stem)
                        remaining = len(AudioProcessor.find_failed_segments(audio_md))
                        fixed = n_audio - remaining
                        if fixed > 0:
                            file_results.append(f"录音: {fixed}/{n_audio} 分段已修复，仍有 {remaining} 分段失败")
                            any_success = True
                        else:
                            file_results.append(f"录音: 全部修复失败")
                    except Exception as e:
                        file_results.append(f"录音: {e}")

                status = "✓" if all("成功" in r for r in file_results) else ("⚠" if any_success else "✗")
                results.append(f"{status} {basename}: {'; '.join(file_results)}")

            header = "修复完成" if any_success else "修复失败 — 所有项仍无法识别"
            return f"{header}:\n" + "\n".join(results)

        self._start_worker(task)
