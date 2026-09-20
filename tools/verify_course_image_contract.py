"""Exercise course markers and original batch restoration without paid calls.

Uses encoded images, the public merged APIs, and a real synthetic CLI process.
Existing-image Markdown can optionally be read for conservative guard regression;
only aggregate counts and timing are written, never source recognition content.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import statistics
import sys
import time

from PIL import Image

from ocrllm import (
    CodexCLISettings, ProviderModel, batchify_images, recognize_images_to_markdown,
    restore_image_batch_plan, resume_images_to_markdown,
)
from ocrllm.errors import OCRLLMError, OutputError, ProviderError
from ocrllm.providers.codex_cli.validate_codex_course_markdown import (
    validate_codex_course_markdown,
    _adjacent_prose_repetition,
)


def marker(name):
    return f"<!-- meta:frame id={name} -->"


def check_contract():
    names = tuple(f"frame_{index:06d}.jpg" for index in range(8))
    content = "\n课程正文 Ω α 中文。\n"
    exact = "".join(marker(name) + content for name in names)
    cases = {}

    def accepts(label, raw, expected=exact, sources=names, **options):
        actual = validate_codex_course_markdown(raw, sources, **options)
        assert actual == expected, label
        cases[label] = "accepted"

    def rejects(label, raw, sources=names, reason="course_frame_markers_invalid", **options):
        try:
            validate_codex_course_markdown(raw, sources, **options)
        except ProviderError as error:
            assert error.details["reason"] == reason, (label, error.details)
        else:
            raise AssertionError(label)
        cases[label] = "rejected"

    accepts("eight_exact", exact)
    accepts("jpg_omission", exact.replace(".jpg", ""))
    accepts("jpg_letters_omission", exact.replace(".jpg", "."))
    accepts("format_typo_and_spacing", exact.replace("meta:frame id=", "meat:frmae  id= "))
    accepts("quoted_identity", "".join(f'<!-- meta:frame id="{n}" -->' + content for n in names))
    reverse = "".join(marker(name) + content for name in reversed(names))
    accepts("explicit_reversed_order", reverse, reverse)
    extra = marker(names[0]) + "\n" + exact + "<!-- unrelated note -->\n"
    accepts("extra_identified_duplicate", extra, extra)
    rejects("same_comment_cannot_cover_eight", (marker(names[0]) + content) * 8)
    rejects("duplicate_cannot_fill_missing_neighbor", exact.replace(marker(names[-1]), marker(names[-2])))
    rejects("fuzzy_duplicate_cannot_fill_missing_neighbor", exact.replace(marker(names[-1]), marker(names[-2]).replace("meta", "meat")))
    rejects("ambiguous_neighbor", marker("frame_00000X.jpg") + content, names[:2])
    for kind, wrap in (
        ("fence", lambda m: "```html\n" + m + "\n```"),
        ("tilde_fence", lambda m: "~~~html\n" + m + "\n~~~"),
        ("inline_code", lambda m: "`" + m + "`"),
        ("indented_code", lambda m: "    " + m),
        ("svg_code", lambda m: "<svg>\n" + m + "\n</svg>"),
    ):
        rejects("missing_marker_only_in_" + kind, exact.replace(marker(names[-1]), wrap(marker(names[-1]))))
    rejects("ordinary_comment_is_not_a_frame", "<!-- unrelated note -->\n课程正文。", names[:1])
    # Full expected marker length is exactly 30. Inserting nine characters is
    # exactly 30%, rejected; inserting eight is accepted. No internal mocks.
    boundary_name = "abc.jpg"
    boundary = marker(boundary_name)
    assert len(boundary) == 30
    accepts("strict_threshold_below", boundary.replace("abc", "a" * 9 + "bc") + content,
            boundary + content, (boundary_name,))
    rejects("strict_threshold_at", boundary.replace("abc", "a" * 10 + "bc") + content,
            (boundary_name,))
    rejects("exact_identity_does_not_waive_format_budget", boundary.replace("id=", "id=" + " " * 9),
            (boundary_name,))
    rejects("jpg_omission_does_not_waive_other_format_edits", boundary.replace(".jpg", "").replace("id=", "id=" + " " * 9),
            (boundary_name,))
    # Substitution costs two (six replacements = twelve, not six, edits).
    rejects("substitution_is_two_edits", marker("zzzzzz.jpg") + content, ("abcdef.jpg",))
    raw = " \r\n\t" + marker(names[0]).replace(".jpg", "") + "\r\n\n正文 😀 Ω\t\n  "
    accepts("only_marker_span_changes", raw, raw.replace(marker(names[0][:-4]), marker(names[0])), names[:1])
    rejects("replacement_unicode", exact + "\ufffd", reason="invalid_unicode")
    rejects("unencodable_unicode", exact + "\ud800", reason="invalid_unicode")

    prose = "这一行是足够长的完整自然语言教学内容，用来确认只有连续出现很多次相同语句才会触发保守检查。"
    guarded = marker(names[0]) + "\n" + (prose + "\n\n") * 8
    accepts("repetition_guard_explicitly_optional", guarded, guarded, names[:1])
    rejects("eight_adjacent_long_prose_lines", guarded, names[:1], reason="adjacent_repetition", adjacent_repeat_limit=8)
    short_run = marker(names[0]) + "\n" + (prose + "\n") * 7
    accepts("seven_adjacent_prose_lines", short_run, short_run, names[:1], adjacent_repeat_limit=8)
    interrupted = marker(names[0]) + "\n" + (prose + "\n另一段不同内容。\n") * 20
    accepts("nonadjacent_same_prose", interrupted, interrupted, names[:1], adjacent_repeat_limit=8)
    across_frames = "".join(marker(n) + "\n" + prose + "\n" for n in names)
    accepts("same_board_text_across_frames", across_frames, across_frames, adjacent_repeat_limit=8)
    unclosed_svg = exact.replace(content, "\n<svg>\n" + content, 1)
    accepts("svg_completeness_is_not_a_body_audit", unclosed_svg, unclosed_svg, adjacent_repeat_limit=8)
    for label, body in (
        ("fenced_prose", "```text\n" + (prose + "\n") * 20 + "```\n"),
        ("svg_template", "<svg>\n" + (prose + "\n") * 20 + "</svg>\n"),
        ("unclosed_svg_template", "<svg>\n" + (prose + "\n") * 20),
        ("math_and_separator", ("x + x + x = x^2 \\quad $\\alpha$\n" + "-" * 80 + "\n") * 20),
        ("math_template", ("\\text{" + prose + "}\n") * 20),
        ("unfenced_console_paths", ("RESTART: C:/Users/Example/Documents/Python/a_very_long_class_exercise.py\n") * 20),
        ("markdown_headings", ("# " + prose + "\n") * 20),
    ):
        raw = marker(names[0]) + "\n" + body
        accepts(label, raw, raw, names[:1], adjacent_repeat_limit=8)
    times = []
    long_text = exact + ("这是第一个正常段落。\n这是不同的第二个段落 Ω。\n" * 1200)
    for _ in range(12):
        started = time.perf_counter()
        validate_codex_course_markdown(long_text, names, adjacent_repeat_limit=8)
        times.append(time.perf_counter() - started)
    return {"cases": cases, "timing_characters": len(long_text),
            "validation_median_seconds": statistics.median(times),
            "validation_max_seconds": max(times)}


def check_restore(work, source_manifest=None):
    work.mkdir(parents=True, exist_ok=True)
    control = work / "synthetic-control.json"
    calls = work / "synthetic-calls.jsonl"
    cli_source = work / "synthetic_codex.py"
    cli_source.write_text('''import hashlib,json,re,sys
from pathlib import Path
from PIL import Image
args=sys.argv[1:]
if args==['--version']:
 print('synthetic-codex-contract 1');raise SystemExit(0)
root=Path(__file__).parent
config=json.loads((root/'synthetic-control.json').read_text())
prompt=args[-1]
match=re.search(r'（JSON数组，仅作文件身份映射）：(\\[[^\\n]*\\])。',prompt)
names=json.loads(match.group(1))
images=[]
for i,a in enumerate(args):
 if a=='-i':
  p=Path(args[i+1])
  with Image.open(p) as im: size=list(im.size)
  images.append({'staged_name':p.name,'staged_path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'dimensions':size,'bytes':p.stat().st_size})
with (root/'synthetic-calls.jsonl').open('a',encoding='utf-8') as stream:
 stream.write(json.dumps({'names':names,'model':args[args.index('-m')+1],'images':images})+'\\n')
text='\\n'.join('<!-- meta:frame id='+n.removesuffix('.jpg')+' -->\\n课程测试正文。' for n in names)
if any(n in config.get('fail_names',[]) for n in names): text='当前批次没有应得帧标记。'
Path(args[args.index('--output-last-message')+1]).write_text(text,encoding='utf-8')
print(json.dumps({'type':'turn.completed','usage':{'input_tokens':100,'cached_input_tokens':20,'output_tokens':30}}))
''', encoding="utf-8")
    if os.name == "nt":
        cli = work / "synthetic-codex.cmd"
        cli.write_text(f'@echo off\r\n"{sys.executable}" "{cli_source}" %*\r\n')
    else:
        cli = work / "synthetic-codex"
        cli.write_text(f'#!{sys.executable}\nexec(compile(open({str(cli_source)!r}, encoding="utf-8").read(), {str(cli_source)!r}, "exec"))\n')
        cli.chmod(0o755)
    # The CLI wrapper needs the source script's __file__, not its launcher path.
    # Both are siblings in this bounded owned scenario directory.
    images = []
    for index in range(9):
        image = work / f"frame_{index:06d}.jpg"
        Image.new("RGB", (80, 60), (index * 20, 40, 90)).save(image)
        images.append(image)
    sources = tuple(images)

    def provider(model):
        return ProviderModel(
            vendor="openai", model=model, adapter_id="codex_cli",
            settings=CodexCLISettings(command=str(cli), model=model, timeout_seconds=20,
                course_validation=True, adjacent_repeat_limit=8, usage_event_dir=work / "usage"),
            supports_plain_ocr=True, supports_detail_ocr=True, supports_audio=False,
            default_image_batch_size=8, default_audio_minutes=None, retry_rules={},
        )

    control.write_text(json.dumps({"fail_names": [sources[-1].name]}))
    batches = batchify_images(sources, batch_size=8)
    long_parent = work / ("long-output-" + "a" * 70) / ("b" * 90) / ("c" * 90)
    output = long_parent / "course.md"
    long_output_characters = len(str(output))
    overlong_rejected = False
    try:
        partial = recognize_images_to_markdown(batches, provider=provider("synthetic-first"),
            image_task="course_ocr", output_path=output, timeout_seconds=20)
    except OutputError as error:
        if os.name != "nt" or error.code != "OUTPUT_PATH_INVALID":
            raise
        assert not calls.exists(), "Windows overlong preflight must precede CLI dispatch"
        overlong_rejected = True
        output = work / "course.md"
        partial = recognize_images_to_markdown(batches, provider=provider("synthetic-first"),
            image_task="course_ocr", output_path=output, timeout_seconds=20)
    assert partial.status == "partial", partial.metadata
    assert partial.metadata["settled_slot_count"] == 1
    before_output = hashlib.sha256(output.read_bytes()).hexdigest()
    state_path = output.with_name("course.ocrllm-state.json")
    before_state = hashlib.sha256(state_path.read_bytes()).hexdigest()
    before_calls = len(calls.read_text().splitlines())
    restored = restore_image_batch_plan(sources, output_path=output)
    assert restored == batches and tuple(map(len, restored)) == (8, 1)
    assert hashlib.sha256(output.read_bytes()).hexdigest() == before_output
    assert hashlib.sha256(state_path.read_bytes()).hexdigest() == before_state
    for bad in (sources[:-1], (sources[1], sources[0], *sources[2:])):
        try:
            restore_image_batch_plan(bad, output_path=output)
        except OCRLLMError as error:
            assert error.details["provider_calls_attempted"] == 0
        else:
            raise AssertionError("source mismatch accepted")
    original = sources[0].read_bytes()
    Image.new("RGB", (80, 60), "red").save(sources[0])
    try:
        restore_image_batch_plan(sources, output_path=output)
    except OCRLLMError as error:
        assert error.details["provider_calls_attempted"] == 0
    else:
        raise AssertionError("changed source bytes accepted")
    finally:
        sources[0].write_bytes(original)
    assert len(calls.read_text().splitlines()) == before_calls
    control.write_text(json.dumps({"fail_names": []}))
    restored = restore_image_batch_plan(sources, output_path=output)
    complete = resume_images_to_markdown(restored, provider=[[provider("synthetic-resumed")] for _ in range(3)],
        output_path=output, timeout_seconds=20)
    assert complete.status == "complete"
    assert complete.metadata["reused_slot_count"] == 1
    assert complete.metadata["provider_call_count"] == 1
    assert json.loads(calls.read_text().splitlines()[-1])["names"] == [sources[-1].name]
    assert not state_path.exists()
    single = batchify_images(sources[:3], batch_size=1)
    old_output = work / "original-single.md"
    control.write_text(json.dumps({"fail_names": [sources[1].name]}))
    old_partial = recognize_images_to_markdown(single, provider=provider("synthetic-old"),
        image_task="course_ocr", output_path=old_output, timeout_seconds=20)
    assert old_partial.status == "partial"
    old_plan = restore_image_batch_plan(sources[:3], output_path=old_output)
    assert old_plan == single and tuple(map(len, old_plan)) == (1, 1, 1)
    control.write_text(json.dumps({"fail_names": []}))
    old_complete = resume_images_to_markdown(old_plan, provider=provider("synthetic-new"),
        output_path=old_output, timeout_seconds=20)
    assert old_complete.status == "complete" and old_complete.metadata["reused_slot_count"] == 2
    transport = []
    if source_manifest is not None:
        groups = json.loads(source_manifest.read_text())["groups"]
        for group_index, group in enumerate(groups):
            original = tuple(Path(value) for value in group["images"])
            assert len(original) == 8 and len({p.name for p in original}) == 8
            expected = []
            for source in original:
                with Image.open(source) as opened:
                    dimensions = list(opened.size)
                expected.append({"source_name": source.name, "source_path": str(source),
                    "sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
                    "dimensions": dimensions, "bytes": source.stat().st_size})
            call_count = len(calls.read_text().splitlines())
            result = recognize_images_to_markdown((original,), provider=provider("synthetic-transport"),
                image_task="course_ocr", output_path=work / f"transport-{group_index}.md", timeout_seconds=20)
            assert result.status == "complete" and result.metadata["provider_call_count"] == 1
            captured = [json.loads(line) for line in calls.read_text().splitlines()][call_count:]
            assert len(captured) == 1
            captured = captured[0]
            assert captured["names"] == [p.name for p in original]
            assert len(captured["images"]) == 8
            for index, (source, actual) in enumerate(zip(expected, captured["images"]), start=1):
                assert actual["staged_name"] == f"image_{index:03d}" + Path(source["source_name"]).suffix.lower()
                assert all(source[key] == actual[key] for key in ("sha256", "dimensions", "bytes"))
                assert hashlib.sha256(original[index-1].read_bytes()).hexdigest() == source["sha256"]
                assert not Path(actual["staged_path"]).exists(), "CLI temp should be removed after return"
            transport.append({"group": group["name"], "sources": expected,
                "captured_process": captured, "source_order_bytes_dimensions_match": True,
                "prompt_filename_order_match": True, "source_bytes_unchanged": True,
                "temporary_staging_removed": True})
    return {"source_transport": transport, "eight_plus_tail": [8, 1], "single_groups_retained": [1, 1, 1],
            "resume_calls": complete.metadata["provider_call_count"],
            "single_resume_calls": old_complete.metadata["provider_call_count"],
            "source_mismatch_calls": 0, "lookup_kept_state_and_markdown_bytes": True,
            "output_path_characters": len(str(output)), "long_output_path_characters": long_output_characters,
            "windows_overlong_rejected_before_dispatch": overlong_rejected, "real_model_calls": 0,
            "synthetic_cli_calls": len(calls.read_text().splitlines())}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work-dir", type=Path, required=True)
    parser.add_argument("--existing-output-root", type=Path)
    parser.add_argument("--source-manifest", type=Path, help="Read-only real-source groups for synthetic CLI transport proof")
    args = parser.parse_args()
    args.work_dir = args.work_dir.resolve()
    result = {"markers": check_contract(), "public_restore": check_restore(args.work_dir, args.source_manifest)}
    if args.existing_output_root:
        if not args.existing_output_root.is_dir():
            raise SystemExit("--existing-output-root must be an existing directory")
        checked = flagged = 0
        started = time.perf_counter()
        for path in args.existing_output_root.rglob("image.md"):
            text = path.read_text(encoding="utf-8")
            # Existing outputs are multi-batch full-course Markdown; split at
            # their existing actual frame boundaries, never compare across frames.
            import re
            chunks = re.split(r"<!--\s*meta:frame\s+id=[^<>]*?-->", text)[1:]
            checked += len(chunks)
            flagged += sum(_adjacent_prose_repetition(chunk, 8) for chunk in chunks)
        result["existing_prose_guard"] = {"frame_segments": checked, "flagged_segments": flagged,
            "elapsed_seconds": time.perf_counter() - started, "body_copied": False}
    destination = args.work_dir / "course-image-contract.json"
    destination.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
