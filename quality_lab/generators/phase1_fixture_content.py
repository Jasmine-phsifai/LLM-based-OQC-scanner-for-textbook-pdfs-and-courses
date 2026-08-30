"""Single source of visible content for generated Phase 1 fixtures."""

from __future__ import annotations


SLIDE_TITLE = "RELIABLE MULTIMODAL NOTES"
SLIDE_SUBTITLE = "可靠的多模态课堂笔记"
SLIDE_ORDER_ANCHOR = "ORDER-FIRST: AURORA-314"
SLIDE_CARDS = (
    (
        "CAPTURE / 采集",
        "Read every image in source order",
        "按输入顺序读取每张图片",
        "Keep visible labels and markers",
        "保留可见标签与标记",
        "COURSE-ID: QCR-204",
    ),
    (
        "LANGUAGE / 语言",
        "English text remains in English",
        "简体中文保持原文",
        "Do not translate source content",
        "不要补写缺失内容",
        "REVISION: 2026-07-10",
    ),
    (
        "STRUCTURE / 结构",
        "Preserve headings and lists",
        "保持段落与阅读顺序",
        "Separate distinct image regions",
        "不要重复重叠内容",
        "BATCH LIMIT: 10 images",
    ),
    (
        "FORMULAS / 公式",
        "Use LaTeX for equations",
        "保留变量、符号与下标",
        "Check exponents and relations",
        "不要计算或解释答案",
        "FORMULA-ID: EQ-731",
    ),
    (
        "TABLES / 表格",
        "Rebuild rows and columns",
        "完整保留行标题与列标题",
        "Keep each value in its cell",
        "不要交换行列位置",
        "TABLE TOTAL: 128.75 kg",
    ),
    (
        "ACCURACY / 准确度",
        "Copy names and dates exactly",
        "数字、小数点与单位必须准确",
        "Reject invented identifiers",
        "不要猜测模糊字符",
        "TARGET RECALL: ≥ 95%",
    ),
    (
        "OUTPUT / 输出",
        "Return structured Markdown only",
        "输出应当清晰且可审阅",
        "Keep meaningful image boundaries",
        "不要添加总结或翻译",
        "LATENCY P95: 180 ms",
    ),
    (
        "AUDIT / 审计",
        "Record model and prompt version",
        "记录哈希值与运行时间",
        "Never print credentials",
        "两次完整运行必须独立",
        "CHECKSUM: CN-7319",
    ),
)

FORMULA_TITLE = "FORMULA INTEGRITY BOARD / 公式完整性校验"
FORMULA_ORDER_ANCHOR = "ORDER-LAST: ZENITH-926"
VISIBLE_FORMULAS = (
    ("F01", "a₁ + a₂ = 17"),
    ("F02", "x₁ − 3x₂ ≤ −4"),
    ("F03", "y = 2x² − 5x + 7"),
    ("F04", "s₄ = 1 + 2 + 3 + 4 = 10"),
    ("F05", "P(A | B) = 0.625"),
    ("F06", "det(M) = 3 × 8 − 2 × 5 = 14"),
    ("F07", "v₂ = (−3, 4)"),
    ("F08", "f′(x) = 6x − 5"),
    ("F09", "‖u‖₂ = √25 = 5"),
    ("F10", "z₃ ≥ 1.25"),
    ("F11", "E[X₂] = 2.4"),
    ("F12", "Rₙ = n(n + 1) / 2"),
)
CANONICAL_FORMULAS = (
    ("F01", r"a_{1} + a_{2} = 17"),
    ("F02", r"x_{1} - 3x_{2} \le -4"),
    ("F03", r"y = 2x^{2} - 5x + 7"),
    ("F04", r"s_{4} = 1 + 2 + 3 + 4 = 10"),
    ("F05", r"P(A \mid B) = 0.625"),
    ("F06", r"\det(M) = 3 \times 8 - 2 \times 5 = 14"),
    ("F07", r"v_{2} = (-3, 4)"),
    ("F08", r"f'(x) = 6x - 5"),
    ("F09", r"\lVert u \rVert_{2} = \sqrt{25} = 5"),
    ("F10", r"z_{3} \ge 1.25"),
    ("F11", r"E[X_{2}] = 2.4"),
    ("F12", r"R_{n} = n(n + 1) / 2"),
)

TABLE_TITLE = "CALIBRATION RUNS / 校准数据"
TABLE_HEADERS = (
    ("Run", "组次"),
    ("Load (N)", "载荷"),
    ("Drift (mm)", "漂移"),
    ("Temp (°C)", "温度"),
    ("Gain", "增益"),
    ("Status", "状态"),
)
TABLE_ROWS = (
    ("A-01", "12.57", "+0.18", "18.6", "1.025", "PASS"),
    ("A-02", "24.83", "−0.07", "19.1", "0.998", "PASS"),
    ("B-01", "36.14", "+1.25", "18.9", "1.104", "CHECK"),
    ("B-02", "48.92", "−1.40", "20.2", "0.875", "PASS"),
    ("C-01", "60.31", "+2.05", "21.7", "1.25", "HOLD"),
)
