"""
板书/截图识别选项卡。
"""

from __future__ import annotations

import os

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QCheckBox, QMessageBox,
)

from OCRLLM import prompts
from OCRLLM.gui.batch_tasks import BatchFileTask, run_batch_tasks
from OCRLLM.gui.widgets import FileInput, PromptButton, browse_files


class BoardTab(QWidget):
    """板书/截图识别选项卡 GUI。"""
    def __init__(self, get_cfg, start_worker, get_output_in_place=None, parent=None):
        super().__init__(parent)
        self._get_cfg = get_cfg
        self._start_worker = start_worker
        self._get_output_in_place = get_output_in_place or (lambda: False)
        self._build_ui()

    def _build_ui(self):
        vbox = QVBoxLayout(self)

        self._files = FileInput(
            accept_exts=['jpg', 'jpeg', 'png', 'bmp', 'webp', 'heic', 'heif', 'tif', 'tiff'],
            multi=True, placeholder="选择或拖入图片（支持多选，; 分隔）")

        from OCRLLM.gui.tabs.pdf_tab import _file_row
        vbox.addLayout(_file_row(
            "图片文件:", self._files, "选择多张",
            lambda: browse_files(self, "选择图片",
                                 "图片文件 (*.jpg *.jpeg *.png *.bmp *.webp *.heic *.heif *.tif *.tiff);;所有文件 (*)",
                                 self._files)))

        opt = QHBoxLayout()
        self._skip = QCheckBox("跳过预处理（直接发送原图）")
        opt.addWidget(self._skip)
        self._separate = QCheckBox("多文件分别处理（每张图单独输出）")
        opt.addWidget(self._separate)
        opt.addStretch()
        vbox.addLayout(opt)

        from OCRLLM.gui.app import make_action_buttons
        self._prompt = PromptButton("板书识别", "board", prompts.BOARD, self)
        vbox.addLayout(make_action_buttons(
            "▶ 开始识别板书", self._run,
            self._prompt.reset_to_default,
            extra_widgets=[self._prompt]))

        from PyQt5.QtWidgets import QPushButton
        repair_row = QHBoxLayout()
        self._repair_btn = QPushButton("🔧 修复失败批次")
        self._repair_btn.setToolTip("扫描已有识别结果中的失败批次，仅重新识别那些部分")
        self._repair_btn.clicked.connect(self._run_repair)
        repair_row.addWidget(self._repair_btn)
        repair_row.addStretch()
        vbox.addLayout(repair_row)

    def set_input_paths(self, paths: list[str] | tuple[str, ...]):
        """从外部设置图片文件路径列表。

        Args:
            paths: 文件路径列表。
        """
        self._files.setText(";".join(paths))

    def _run(self):
        raw = self._files.text().strip()
        if not raw:
            QMessageBox.warning(self, "提示", "请先选择图片文件"); return

        files = [f.strip() for f in raw.split(";") if f.strip()]
        missing = [f for f in files if not os.path.isfile(f)]
        if missing:
            QMessageBox.warning(self, "提示", "文件不存在:\n" + "\n".join(missing[:5])); return

        skip = self._skip.isChecked()
        separate = self._separate.isChecked()
        prompt_text = self._prompt.prompt_text()

        # 在原位置输出：结果文件放到第一张图片同级目录
        output_path = None
        if self._get_output_in_place():
            src_dir = os.path.dirname(os.path.abspath(files[0]))
            output_path = os.path.join(src_dir, "板书识别.md")

        if separate and len(files) > 1:
            def task(reporter):
                from OCRLLM.processors.board import BoardProcessor
                cfg = self._get_cfg()
                tasks = []
                for image_path in files:
                    single_output = None
                    if self._get_output_in_place():
                        src_dir = os.path.dirname(os.path.abspath(image_path))
                        stem = os.path.splitext(os.path.basename(image_path))[0]
                        single_output = os.path.join(src_dir, f"{stem}_板书识别.md")

                    def _run_one(task_cfg, child_reporter, *, path=image_path, out=single_output):
                        proc = BoardProcessor(cfg=task_cfg, reporter=child_reporter)
                        return proc.process(
                            image_paths=[path],
                            output_path=out,
                            skip_preprocess=skip,
                            prompt_template=prompt_text or None,
                        )

                    tasks.append(BatchFileTask(
                        source_path=image_path,
                        display_name=os.path.basename(image_path),
                        run=_run_one,
                    ))
                return run_batch_tasks(task_kind="board", task_label="图片", cfg=cfg, reporter=reporter, tasks=tasks)

            if self._start_worker(task):
                self._prompt.consume_temporary()
            return

        def task(reporter):
            from OCRLLM.processors.board import BoardProcessor
            cfg = self._get_cfg()
            proc = BoardProcessor(cfg=cfg, reporter=reporter)
            result = proc.process(image_paths=files, output_path=output_path,
                                  skip_preprocess=skip,
                                  prompt_template=prompt_text or None)
            return f"板书识别完成: {result}"

        if self._start_worker(task):
            self._prompt.consume_temporary()

    def _run_repair(self):
        raw = self._files.text().strip()
        if not raw:
            QMessageBox.warning(self, "提示", "请先选择原始图片文件（用于修复识别结果）")
            return

        files = [f.strip() for f in raw.split(";") if f.strip()]
        missing = [f for f in files if not os.path.isfile(f)]
        if missing:
            QMessageBox.warning(self, "提示", "文件不存在:\n" + "\n".join(missing[:5]))
            return

        from OCRLLM.processors.board import BoardProcessor

        # Determine output path to scan for failures
        output_path = None
        if self._get_output_in_place():
            src_dir = os.path.dirname(os.path.abspath(files[0]))
            output_path = os.path.join(src_dir, "板书识别.md")
        else:
            from OCRLLM.processors.board import _default_board_output_path
            cfg = self._get_cfg()
            output_path = _default_board_output_path(cfg.paths.output_dir, files)

        if not os.path.isfile(output_path):
            QMessageBox.information(self, "修复", "未找到对应的识别结果文件。")
            return

        failed = BoardProcessor.find_failed_batches(output_path)
        if not failed:
            QMessageBox.information(self, "修复", "识别结果中没有发现失败批次。")
            return

        skip = self._skip.isChecked()
        prompt_text = self._prompt.prompt_text()
        total = len(failed)

        def task(reporter):
            from OCRLLM.processors.board import BoardProcessor
            cfg = self._get_cfg()
            proc = BoardProcessor(cfg=cfg, reporter=reporter)
            try:
                proc.repair(files, output_path,
                            skip_preprocess=skip,
                            prompt_template=prompt_text or None)
                return f"修复完成: 全部 {total} 个批次修复成功"
            except RuntimeError:
                remaining = BoardProcessor.find_failed_batches(output_path)
                fixed = total - len(remaining)
                if fixed > 0:
                    return f"修复完成: {fixed}/{total} 批次已修复，仍有 {len(remaining)} 批次失败"
                return f"修复失败: 全部 {total} 个批次仍无法识别"
            except Exception as e:
                return f"修复失败: {e}"

        self._start_worker(task)
