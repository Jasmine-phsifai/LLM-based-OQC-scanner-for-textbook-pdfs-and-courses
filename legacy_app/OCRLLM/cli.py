"""
OCRLLM CLI 入口 — 无 GUI 批量处理。

用法:
    python -m OCRLLM.cli pdf   input.pdf --formula
    python -m OCRLLM.cli board img1.jpg img2.jpg
    python -m OCRLLM.cli video lecture.mp4 --phases 1 2 3 4
    python -m OCRLLM.cli audio lecture.mp3 --hotwords "矩阵,sigma"
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from typing import Callable

from OCRLLM.config import AppConfig
from OCRLLM.core.utils import setup_logging
from OCRLLM.core.task_runner import ProgressReporter
from OCRLLM.processors.registry import ProcessorSpec, create_processor, get_default_registry
from OCRLLM.processors.routing import InputRoutingError, route_input_paths


def _configure_stdio_encoding() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        try:
            reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def _make_reporter() -> ProgressReporter:
    def on_progress(current, total, msg):
        print(f"[{current}/{total}] {msg}")

    def on_content(text, label):
        try:
            if label:
                print(f"\n{'─' * 40}\n{label}\n{'─' * 40}")
            preview = text[:500] + "..." if len(text) > 500 else text
            print(preview)
        except UnicodeEncodeError:
            # Windows GBK console can't display some characters (e.g. ö, ü)
            safe = text[:500].encode(errors="replace").decode(errors="replace")
            print(safe)

    return ProgressReporter(on_progress=on_progress, on_content=on_content)


def _new_processor(key: str, cfg: AppConfig, reporter: ProgressReporter, tracker=None):
    kwargs = {"cfg": cfg, "reporter": reporter}
    if tracker is not None:
        kwargs["tracker"] = tracker
    return create_processor(key, **kwargs)


def _fail_cli(message: str):
    print(message, file=sys.stderr)
    raise SystemExit(2)


def _normalize_hotwords(hotwords: str | None) -> list[str] | None:
    if not hotwords:
        return None
    words = [word.strip() for word in hotwords.split(",") if word.strip()]
    return words or None


def _normalize_part_indices(parts: str | None) -> list[int] | None:
    if not parts:
        return None
    selected: list[int] = []
    for token in parts.split(","):
        token = token.strip()
        if not token:
            continue
        if "-" in token:
            start_text, end_text = token.split("-", 1)
            start = int(start_text)
            end = int(end_text)
            if start > end:
                raise ValueError(f"invalid part range: {token}")
            selected.extend(range(start, end + 1))
        else:
            selected.append(int(token))
    deduped = list(dict.fromkeys(selected))
    return deduped or None


def _run_pdf(proc, args, routed):
    start = getattr(args, "start", None)
    end = getattr(args, "end", None)
    page_range = (start, end) if start is not None and end is not None else None
    return proc.process(
        pdf_path=routed.paths[0],
        need_formula=getattr(args, "formula", False),
        page_range=page_range,
        output_path=getattr(args, "output", None),
    )


def _run_board(proc, args, routed):
    return proc.process(
        image_paths=list(routed.paths),
        skip_preprocess=getattr(args, "skip_preprocess", False),
        output_path=getattr(args, "output", None),
    )


def _run_video(proc, args, routed):
    phases = getattr(args, "phases", None) or [1, 2, 3, 4, 5]
    return proc.process(
        video_path=routed.paths[0],
        output_dir=getattr(args, "output", None),
        phases=phases,
        skip_audio=5 not in phases,
        resume=getattr(args, "resume", False),
    )


def _run_audio(proc, args, routed):
    return proc.process(
        audio_path=routed.paths[0],
        hotwords=_normalize_hotwords(getattr(args, "hotwords", None)),
        output_path=getattr(args, "output", None),
    )


def _run_text_extract(proc, args, routed):
    return proc.process(
        source_path=routed.paths[0],
        output_path=getattr(args, "output", None),
    )


def _run_social_long(proc, args, routed):
    return proc.process(
        url=routed.paths[0],
        output_dir=getattr(args, "output", None),
        phases=getattr(args, "phases", None),
        skip_audio=5 not in (getattr(args, "phases", None) or [1, 2, 3, 4, 5]),
        part_indices=_normalize_part_indices(getattr(args, "parts", None)),
        resume=getattr(args, "resume", False),
    )


def _run_social_short(proc, args, routed):
    from OCRLLM.processors.social.downloader import download_media

    output_dir = getattr(args, "output", None)
    if not output_dir:
        output_dir = os.path.join(proc.cfg.paths.output_dir, "social_短视频")

    dl_dir = os.path.join(output_dir, "_downloads")
    dl_result = download_media(routed.paths[0], dl_dir, proc.cfg)
    if not dl_result.video_path:
        raise FileNotFoundError(f"下载失败，未找到视频文件: {routed.paths[0]}")

    return proc.process(
        dl_result.video_path,
        output_dir=output_dir,
        title=dl_result.title,
    )


_CLI_RUNNERS: dict[str, Callable] = {
    "pdf": _run_pdf,
    "board": _run_board,
    "video": _run_video,
    "audio": _run_audio,
    "social_long": _run_social_long,
    "social_short": _run_social_short,
    "docx": _run_text_extract,
    "doc": _run_text_extract,
    "pptx": _run_text_extract,
    "ppt": _run_text_extract,
    "html": _run_text_extract,
}


def _add_formula_argument(parser: argparse.ArgumentParser, *, auto: bool):
    help_text = "若识别为 PDF，则启用公式模式" if auto else "使用大模型识别公式"
    parser.add_argument("--formula", action="store_true", help=help_text)


def _add_page_range_arguments(parser: argparse.ArgumentParser, *, auto: bool):
    start_help = "若识别为 PDF，则指定起始页" if auto else "起始页码"
    end_help = "若识别为 PDF，则指定结束页" if auto else "结束页码"
    parser.add_argument("--start", type=int, help=start_help)
    parser.add_argument("--end", type=int, help=end_help)


def _add_skip_preprocess_argument(parser: argparse.ArgumentParser, *, auto: bool):
    help_text = "若识别为图片批量，则跳过预处理" if auto else "跳过预处理"
    parser.add_argument("--skip-preprocess", action="store_true", help=help_text)


def _add_phases_argument(parser: argparse.ArgumentParser, *, auto: bool):
    help_text = "若识别为视频，则指定执行阶段" if auto else "执行阶段 (1-5)"
    parser.add_argument("--phases", type=int, nargs="+", help=help_text)


def _add_resume_argument(parser: argparse.ArgumentParser, *, auto: bool):
    help_text = "若识别为视频，则断点续传" if auto else "断点续传"
    parser.add_argument("--resume", action="store_true", help=help_text)


def _add_hotwords_argument(parser: argparse.ArgumentParser, *, auto: bool):
    help_text = "若识别为音频，则指定热词,逗号分隔" if auto else "热词,逗号分隔"
    parser.add_argument("--hotwords", help=help_text)


def _add_parts_argument(parser: argparse.ArgumentParser, *, auto: bool):
    help_text = "若识别为B站多P，则指定分P，例如 1,3,5-8" if auto else "B站分P，例如 1,3,5-8"
    parser.add_argument("--parts", help=help_text)


_CLI_OPTION_BUILDERS: dict[str, Callable[[argparse.ArgumentParser], None]] = {
    "formula": _add_formula_argument,
    "page_range": _add_page_range_arguments,
    "skip_preprocess": _add_skip_preprocess_argument,
    "phases": _add_phases_argument,
    "resume": _add_resume_argument,
    "hotwords": _add_hotwords_argument,
    "parts": _add_parts_argument,
}

_CLI_OPTION_ATTRS: dict[str, tuple[str, ...]] = {
    "formula": ("formula",),
    "page_range": ("start", "end"),
    "skip_preprocess": ("skip_preprocess",),
    "phases": ("phases",),
    "resume": ("resume",),
    "hotwords": ("hotwords",),
    "parts": ("parts",),
}

_CLI_OPTION_LABELS: dict[str, str] = {
    "formula": "--formula",
    "page_range": "--start/--end",
    "skip_preprocess": "--skip-preprocess",
    "phases": "--phases",
    "resume": "--resume",
    "hotwords": "--hotwords",
    "parts": "--parts",
}


def _iter_cli_specs() -> list[ProcessorSpec]:
    return [spec for spec in get_default_registry().all() if not spec.experimental]


def _validate_cli_registry_contract():
    specs = _iter_cli_specs()
    missing_runners = [spec.key for spec in specs if spec.key not in _CLI_RUNNERS]
    if missing_runners:
        raise RuntimeError(f"CLI 缺少处理器运行器: {', '.join(missing_runners)}")

    unknown_output_targets = sorted({spec.output_target for spec in specs if spec.output_target not in {"file", "directory"}})
    if unknown_output_targets:
        raise RuntimeError(f"CLI 存在未知输出目标类型: {', '.join(unknown_output_targets)}")

    unknown_option_groups = sorted(
        {
            option_group
            for spec in specs
            for option_group in spec.cli_option_groups
            if option_group not in _CLI_OPTION_BUILDERS
        }
    )
    if unknown_option_groups:
        raise RuntimeError(f"CLI 存在未实现的参数组: {', '.join(unknown_option_groups)}")


def _add_output_argument(parser: argparse.ArgumentParser, help_text: str, *, auto: bool):
    default_help = "输出路径或输出目录" if auto else "输出路径"
    parser.add_argument("-o", "--output", help=help_text or default_help)


def _build_explicit_subcommands(subparsers):
    for spec in _iter_cli_specs():
        parser = subparsers.add_parser(spec.key, help=spec.display_name, description=spec.description or spec.display_name)
        input_kwargs = {"help": spec.cli_input_help}
        if spec.accepts_multiple_files:
            input_kwargs["nargs"] = "+"
        parser.add_argument("input", **input_kwargs)
        _add_output_argument(parser, spec.cli_output_help, auto=False)
        for option_group in spec.cli_option_groups:
            _CLI_OPTION_BUILDERS[option_group](parser, auto=False)


def _build_auto_subcommand(subparsers):
    parser = subparsers.add_parser("auto", help="按文件类型自动识别并分发到对应处理器")
    parser.add_argument("input", nargs="+", help="输入文件路径；多文件仅支持同类图片")
    _add_output_argument(parser, "输出路径或输出目录", auto=True)

    option_groups = []
    seen = set()
    for spec in _iter_cli_specs():
        for option_group in spec.cli_option_groups:
            if option_group in seen:
                continue
            seen.add(option_group)
            option_groups.append(option_group)

    for option_group in option_groups:
        _CLI_OPTION_BUILDERS[option_group](parser, auto=True)


def _requested_option_groups(args) -> set[str]:
    requested = set()
    for option_group, attrs in _CLI_OPTION_ATTRS.items():
        if any(getattr(args, attr, None) not in (None, False, []) for attr in attrs):
            requested.add(option_group)
    return requested


def _validate_routed_args(args, spec: ProcessorSpec):
    output_path = getattr(args, "output", None)
    if output_path and os.path.exists(output_path):
        if spec.output_target == "directory" and not os.path.isdir(output_path):
            _fail_cli(f"处理器 {spec.display_name} 需要输出目录，但当前路径是文件: {output_path}")
        if spec.output_target == "file" and os.path.isdir(output_path):
            _fail_cli(f"处理器 {spec.display_name} 需要输出文件路径，但当前路径是目录: {output_path}")

    requested = _requested_option_groups(args)
    unsupported = requested.difference(spec.cli_option_groups)
    if unsupported:
        labels = ", ".join(_CLI_OPTION_LABELS[group] for group in sorted(unsupported))
        _fail_cli(f"处理器 {spec.display_name} 不支持参数: {labels}")

    start = getattr(args, "start", None)
    end = getattr(args, "end", None)
    if (start is None) != (end is None):
        _fail_cli("PDF 页码范围必须同时提供 --start 和 --end")
    if start is not None:
        if start < 1 or end < 1:
            _fail_cli("PDF 页码必须为正整数")
        if start > end:
            _fail_cli("PDF 页码范围要求 start <= end")

    phases = getattr(args, "phases", None)
    if phases:
        invalid = [phase for phase in phases if phase not in {1, 2, 3, 4, 5}]
        if invalid:
            _fail_cli(f"视频阶段仅支持 1-5，收到: {invalid}")
        deduped = list(dict.fromkeys(phases))
        if len(deduped) != len(phases):
            args.phases = deduped

    if getattr(args, "hotwords", None) is not None and not _normalize_hotwords(args.hotwords):
        _fail_cli("--hotwords 不能为空；请提供逗号分隔的非空热词")

    if getattr(args, "parts", None) is not None:
        try:
            part_indices = _normalize_part_indices(args.parts)
        except ValueError:
            _fail_cli("--parts 只支持正整数和闭区间，例如: 1,3,5-8")
        if not part_indices or any(part < 1 for part in part_indices):
            _fail_cli("--parts 只支持从 1 开始的正整数")


def _run_routed_command(args, cfg: AppConfig, routed=None):
    routed = routed or route_input_paths(args.input)
    reporter = _make_reporter()
    spec = routed.spec

    if spec.experimental:
        raise NotImplementedError(f"已识别为 {spec.display_name}，但该处理器目前仅创建了骨架，尚未实现处理逻辑")

    runner = _CLI_RUNNERS.get(spec.key)
    if runner is None:
        raise NotImplementedError(f"处理器 {spec.key} 尚未接入 CLI 分发")

    _validate_routed_args(args, spec)
    proc = _new_processor(spec.key, cfg, reporter)
    result = runner(proc, args, routed)

    print(f"\n完成: {result}")


def cmd_auto(args, cfg: AppConfig):
    """自动识别输入文件类型并分发到对应处理器。

    Args:
        args: argparse 命令行参数。
        cfg: 全局应用配置。

    Raises:
        SystemExit: 输入文件无法识别或处理器未实现时退出。
    """
    try:
        routed = route_input_paths(args.input)
    except (InputRoutingError, KeyError) as exc:
        _fail_cli(f"识别失败: {exc}")

    try:
        _run_routed_command(args, cfg, routed)
    except NotImplementedError as exc:
        _fail_cli(str(exc))


def _cmd_explicit(args, cfg: AppConfig):
    """pdf / board / video / audio 子命令的统一入口。"""
    routed = route_input_paths(args.input)
    expected_command = args.command
    actual_key = routed.spec.key
    if actual_key != expected_command:
        _fail_cli(
            f"警告: 您使用了 '{expected_command}' 子命令，但文件扩展名被识别为 '{routed.spec.display_name}' ({actual_key})。\n"
            f"如需自动按文件类型分发，请改用: python -m OCRLLM.cli auto {' '.join(str(p) for p in routed.paths)}",
        )
    _run_routed_command(args, cfg, routed)


def _build_repair_subcommand(subparsers):
    parser = subparsers.add_parser(
        "repair",
        help="修复已完成 PDF 中的识别失败页（仅重新识别失败页）",
        description="扫描已有 Markdown 输出中的 '识别失败' 占位符，仅重渲染并重新识别那些页。",
    )
    parser.add_argument("pdf", help="原始 PDF 文件路径")
    parser.add_argument("md", help="已生成的识别结果 Markdown 路径")


def _cmd_repair(args, cfg: AppConfig):
    from OCRLLM.processors.pdf import PDFProcessor

    reporter = _make_reporter()
    proc = PDFProcessor(cfg=cfg, reporter=reporter)
    failed_pages = proc.find_failed_pages(args.md)
    if not failed_pages:
        print("没有找到识别失败的页，无需修复。")
        return
    print(f"发现 {len(failed_pages)} 个失败页: {failed_pages}")
    result = proc.repair(args.pdf, args.md)
    print(f"\n修复完成: {result}")


def main():
    """CLI 主入口 — 解析命令行参数并分发到对应子命令。

    支持注册表中声明的所有非实验处理器子命令，以及 auto 自动分发。
    """
    _configure_stdio_encoding()
    _validate_cli_registry_contract()
    parser = argparse.ArgumentParser(description="OCRLLM CLI")
    parser.add_argument("-v", "--verbose", action="store_true")
    sub = parser.add_subparsers(dest="command", required=True)

    _build_explicit_subcommands(sub)
    _build_auto_subcommand(sub)
    _build_repair_subcommand(sub)

    args = parser.parse_args()
    setup_logging(logging.DEBUG if args.verbose else logging.INFO)
    cfg = AppConfig.from_env()

    dispatch = {spec.key: _cmd_explicit for spec in _iter_cli_specs()}
    dispatch["auto"] = cmd_auto
    dispatch["repair"] = _cmd_repair
    dispatch[args.command](args, cfg)


if __name__ == "__main__":
    main()
