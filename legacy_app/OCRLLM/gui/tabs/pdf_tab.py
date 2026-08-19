"""
PDF 处理选项卡。
"""

from __future__ import annotations

import os

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QCheckBox, QLineEdit, QMessageBox,
)

from OCRLLM import prompts
from OCRLLM.gui.batch_tasks import BatchFileTask, run_batch_tasks
from OCRLLM.gui.widgets import FileInput, PromptButton, browse_files, join_paths_text, split_paths_text


class PDFTab(QWidget):
    """PDF 处理选项卡 GUI。"""
    def __init__(self, get_cfg, start_worker, get_tracker=None, get_output_in_place=None, parent=None):
        super().__init__(parent)
        self._get_cfg = get_cfg
        self._start_worker = start_worker
        self._get_tracker = get_tracker
        self._get_output_in_place = get_output_in_place or (lambda: False)
        self._build_ui()

    def _build_ui(self):
        vbox = QVBoxLayout(self)

        self._pdf_path = FileInput(accept_exts=['pdf'], multi=True, placeholder="选择或拖入 PDF 文件（支持多选，; 分隔）")
        vbox.addLayout(_file_row(
            "PDF 文件:", self._pdf_path, "选择多份",
            lambda: browse_files(self, "选择 PDF 文件", "PDF 文件 (*.pdf);;所有文件 (*)", self._pdf_path)))

        opt = QHBoxLayout()
        self._formula = QCheckBox("使用大模型识别公式和表格（BD模式）")
        self._formula.setChecked(True)
        opt.addWidget(self._formula)
        opt.addWidget(QLabel("  页码范围:"))
        self._start = QLineEdit(); self._start.setFixedWidth(50)
        opt.addWidget(self._start)
        opt.addWidget(QLabel("~"))
        self._end = QLineEdit(); self._end.setFixedWidth(50)
        opt.addWidget(self._end)
        opt.addWidget(QLabel("(留空=全部)"))
        opt.addStretch()
        vbox.addLayout(opt)

        from OCRLLM.gui.app import make_action_buttons
        self._prompt = PromptButton("PDF公式识别", "pdf_formula", prompts.PDF_FORMULA, self)

        from PyQt5.QtWidgets import QPushButton
        self._repair_btn = QPushButton("🔧 修复失败页")
        self._repair_btn.setToolTip("扫描已有识别结果中的失败页，仅重新识别那些页")
        self._repair_btn.clicked.connect(self._run_repair)

        vbox.addLayout(make_action_buttons(
            "▶ 开始处理 PDF", self._run,
            self._prompt.reset_to_default,
            extra_widgets=[self._prompt, self._repair_btn]))

    def set_input_paths(self, paths: list[str] | tuple[str, ...]):
        """从外部设置 PDF 文件路径。

        Args:
            paths: 文件路径列表。
        """
        if not paths:
            self._pdf_path.clear()
            return
        self._pdf_path.setText(join_paths_text(list(paths)))

    def _run(self):
        pdf_paths = split_paths_text(self._pdf_path.text())
        if not pdf_paths:
            QMessageBox.warning(self, "提示", "请先选择 PDF 文件"); return
        missing = [pdf_path for pdf_path in pdf_paths if not os.path.isfile(pdf_path)]
        if missing:
            QMessageBox.warning(self, "提示", "文件不存在:\n" + "\n".join(missing[:10])); return

        need_formula = self._formula.isChecked()
        prompt_text = self._prompt.prompt_text()
        s, e = self._start.text().strip(), self._end.text().strip()
        page_range = None
        if s and e:
            try:
                page_range = (int(s), int(e))
            except ValueError:
                QMessageBox.warning(self, "提示", f"页码必须是数字: '{s}' ~ '{e}'"); return

        # 在原位置输出：结果文件放到源文件同级目录
        def _output_path_for(pdf_path: str) -> str | None:
            if not self._get_output_in_place():
                return None
            src_dir = os.path.dirname(os.path.abspath(pdf_path))
            stem = os.path.splitext(os.path.basename(pdf_path))[0]
            return os.path.join(src_dir, f"{stem}_识别.md")

        if len(pdf_paths) == 1:
            pdf_path = pdf_paths[0]
            output_path = _output_path_for(pdf_path)

            def task(reporter):
                from OCRLLM.processors.pdf import PDFProcessor
                cfg = self._get_cfg()
                tracker = self._get_tracker() if self._get_tracker else None
                proc = PDFProcessor(cfg=cfg, reporter=reporter, tracker=tracker)
                result = proc.process(pdf_path=pdf_path, need_formula=need_formula,
                                      output_path=output_path,
                                      page_range=page_range, prompt_template=prompt_text or None)
                return f"PDF 处理完成: {result}"

            if self._start_worker(task):
                self._prompt.consume_temporary()
            return

        def task(reporter):
            from OCRLLM.processors.pdf import PDFProcessor
            cfg = self._get_cfg()
            tasks = []
            for pdf_path in pdf_paths:
                output_path = _output_path_for(pdf_path)

                def _run_one(task_cfg, child_reporter, *, path=pdf_path, out=output_path):
                    proc = PDFProcessor(cfg=task_cfg, reporter=child_reporter)
                    return proc.process(
                        pdf_path=path,
                        need_formula=need_formula,
                        output_path=out,
                        page_range=page_range,
                        prompt_template=prompt_text or None,
                    )

                tasks.append(BatchFileTask(
                    source_path=pdf_path,
                    display_name=os.path.basename(pdf_path),
                    run=_run_one,
                ))
            return run_batch_tasks(task_kind="pdf", task_label="PDF", cfg=cfg, reporter=reporter, tasks=tasks)

        if self._start_worker(task):
            self._prompt.consume_temporary()

    def _run_repair(self):
        pdf_paths = split_paths_text(self._pdf_path.text())
        if not pdf_paths:
            QMessageBox.warning(self, "提示", "请先选择需要修复的 PDF 文件")
            return

        def _output_path_for(pdf_path: str) -> str:
            if self._get_output_in_place():
                src_dir = os.path.dirname(os.path.abspath(pdf_path))
                stem = os.path.splitext(os.path.basename(pdf_path))[0]
                return os.path.join(src_dir, f"{stem}_识别.md")
            cfg = self._get_cfg()
            stem = os.path.splitext(os.path.basename(pdf_path))[0]
            return os.path.join(cfg.paths.output_dir, f"{stem}_识别.md")

        # Pre-check: do any output files have failed pages?
        from OCRLLM.processors.pdf import PDFProcessor
        repair_targets = []
        for pdf_path in pdf_paths:
            md_path = _output_path_for(pdf_path)
            if not os.path.isfile(md_path):
                continue
            failed = PDFProcessor.find_failed_pages(md_path)
            if failed:
                repair_targets.append((pdf_path, md_path, failed))

        if not repair_targets:
            QMessageBox.information(self, "修复", "所选 PDF 的识别结果中没有发现失败页。")
            return

        total_pages = sum(len(f) for _, _, f in repair_targets)
        names = ", ".join(os.path.basename(p) for p, _, _ in repair_targets)
        prompt_text = self._prompt.prompt_text()

        def task(reporter):
            cfg = self._get_cfg()
            results = []
            for pdf_path, md_path, failed in repair_targets:
                proc = PDFProcessor(cfg=cfg, reporter=reporter)
                try:
                    proc.repair(pdf_path, md_path, prompt_template=prompt_text or None)
                    results.append(f"✓ {os.path.basename(pdf_path)}: {len(failed)} 页已修复")
                except Exception as e:
                    results.append(f"✗ {os.path.basename(pdf_path)}: {e}")
            return f"修复完成:\n" + "\n".join(results)

        self._start_worker(task)
def _file_row(label_text, file_input, btn_text, btn_callback):
    from PyQt5.QtWidgets import QPushButton
    row = QHBoxLayout()
    row.addWidget(QLabel(label_text))
    row.addWidget(file_input, stretch=1)
    btn = QPushButton(btn_text)
    btn.clicked.connect(btn_callback)
    row.addWidget(btn)
    return row
