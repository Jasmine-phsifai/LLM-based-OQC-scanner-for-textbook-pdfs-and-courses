"""
GUI 端的模型校验入口。

当用户在视觉/音频下拉中输入了 catalog 之外的自定义模型，
应用设置时调用 validate_and_register() 跑一次真实测试：
  - 视觉：发一张本地随机生成的小图，验证返回非空。
  - 音频：必须用 >5min 真实音频通过 DashScope 异步 filetrans 接口验证；
    Omni / asr_short 模型则用同步小请求验证（也只接受短音频）。

测试通过 → 写入 ~/.OCRLLM/user_models.json，下次启动仍能看到。
失败 → 弹窗显示原因，调用方应放弃保存设置。
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

from PyQt5.QtWidgets import QDialog, QInputDialog, QLabel, QLineEdit, QMessageBox, QProgressDialog, QPushButton, QVBoxLayout, QWidget
from PyQt5.QtCore import Qt

from OCRLLM.config import AppConfig
from OCRLLM.core import model_catalog
from OCRLLM.core.llm_client import LLMClient
from OCRLLM.core.utils import ensure_dir, get_ffmpeg, windows_no_window_kwargs

logger = logging.getLogger(__name__)


def _make_test_image() -> str:
    """生成一张包含简单文字的临时 PNG，作为视觉模型探测样本。"""
    from PIL import Image, ImageDraw, ImageFont

    tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
    tmp.close()
    img = Image.new("RGB", (320, 120), "white")
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("arial.ttf", 28)
    except Exception:
        font = ImageFont.load_default()
    draw.text((20, 40), "OCRLLM TEST 12345", fill="black", font=font)
    img.save(tmp.name, "PNG")
    return tmp.name


def _ensure_long_test_audio(parent: QWidget) -> Optional[tuple[str, Optional[str]]]:
    """获取一段 >5min 的测试音频。

    返回 (local_path, remote_url) — remote_url 用于异步 filetrans 上传，
    若用户提供了远程 URL 则 local_path 可为空。

    优先级：
      1. 环境变量 OCRLLM_TEST_AUDIO_URL（远程公网音频 URL）
      2. 环境变量 OCRLLM_TEST_AUDIO_PATH（本地长音频文件路径）
      3. 弹窗让用户提供路径或 URL
      4. 用 ffmpeg 在本机生成 360s 噪声音频（带 1Hz beep 让 ASR 不至于完全空响应）
    """
    url = os.environ.get("OCRLLM_TEST_AUDIO_URL", "").strip()
    if url:
        return ("", url)
    local = os.environ.get("OCRLLM_TEST_AUDIO_PATH", "").strip()
    if local and os.path.isfile(local):
        return (local, None)

    text, ok = QInputDialog.getText(
        parent,
        "需要测试音频",
        "测试自定义音频模型需要一段 >5 分钟的真实音频。\n"
        "请填入：\n"
        "  · 公网可访问的音频 URL（推荐，DashScope filetrans 可直接拉取），或\n"
        "  · 本地音频文件绝对路径，或\n"
        "  · 留空让程序用 ffmpeg 自动生成 360s 测试音（不保证模型识别有意义内容）。",
        QLineEdit.Normal,
        "",
    )
    if not ok:
        return None
    text = text.strip()
    if text.startswith(("http://", "https://")):
        return ("", text)
    if text and os.path.isfile(text):
        return (text, None)
    if text:
        QMessageBox.warning(parent, "路径无效", f"未找到文件：{text}")
        return None

    # 生成测试音频
    try:
        ffmpeg = get_ffmpeg()
    except RuntimeError as exc:
        QMessageBox.critical(parent, "缺少 ffmpeg", f"未找到 ffmpeg，无法生成测试音频：{exc}")
        return None
    out_dir = ensure_dir(os.path.join(tempfile.gettempdir(), "ocrllm_model_test"))
    out_path = os.path.join(out_dir, "test_long_360s.mp3")
    if not os.path.isfile(out_path):
        cmd = [
            ffmpeg, "-y",
            "-f", "lavfi", "-i", "sine=frequency=440:duration=360",
            "-ar", "16000", "-ac", "1", "-b:a", "32k",
            out_path,
        ]
        try:
            subprocess.run(cmd, check=True, capture_output=True, **windows_no_window_kwargs())
        except subprocess.CalledProcessError as exc:
            QMessageBox.critical(parent, "生成失败",
                                 f"ffmpeg 生成测试音频失败：\n{exc.stderr.decode(errors='replace')[:400]}")
            return None
    return (out_path, None)


def _upload_filetrans_probe_audio(api_key: str, model_name: str, local_path: str) -> str:
    """把本地测试音频上传到 DashScope OSS，返回 oss:// URL（与生产识别路径一致）。"""
    try:
        from dashscope.utils.oss_utils import OssUtils
    except ImportError as exc:
        raise RuntimeError("缺少 dashscope SDK，无法上传本地测试音频") from exc
    file_url, _upload_certificate = OssUtils.upload(model=model_name, file_path=local_path, api_key=api_key)
    if not file_url or not str(file_url).startswith("oss://"):
        raise RuntimeError(f"OSS 上传未返回 oss:// URL: {file_url}")
    return str(file_url)


def _is_known_model(name: str, kind: str) -> bool:
    if kind == "vision":
        return model_catalog.find_vision_model(name) is not None
    if kind == "audio":
        return model_catalog.find_audio_model(name) is not None
    return False


def _validate_vision(parent: QWidget, client: LLMClient, model_name: str) -> bool:
    progress = QProgressDialog(f"正在测试视觉模型 {model_name} ...", None, 0, 0, parent)
    progress.setWindowTitle("校验视觉模型")
    progress.setWindowModality(Qt.ApplicationModal)
    progress.setCancelButton(None)
    progress.show()
    try:
        img = _make_test_image()
        ok, msg = client.probe_vision_model(model_name, img, timeout=90)
    finally:
        progress.close()
    if not ok:
        QMessageBox.critical(parent, "视觉模型不可用",
                             f"模型 {model_name} 测试失败：\n{msg}\n\n该模型不会被保存到下拉清单。")
        return False
    # 写入用户清单（默认按 vlm 类型保存；不标 free_quota）
    model_catalog.save_user_vision_model(model_catalog.VisionModel(
        name=model_name,
        label=f"{model_name} — 用户自定义（已通过测试）",
        kind="vlm",
        free_quota=False,
        note=f"validate_ok: {msg[:120]}",
    ))
    QMessageBox.information(parent, "视觉模型可用",
                            f"模型 {model_name} 测试通过：{msg}\n已加入下拉清单。")
    return True


def _validate_audio(parent: QWidget, client: LLMClient, model_name: str) -> bool:
    audio = _ensure_long_test_audio(parent)
    if audio is None:
        QMessageBox.warning(parent, "已取消", "未提供测试音频，模型未保存。")
        return False
    local_path, remote_url = audio

    progress = QProgressDialog(
        f"正在测试音频模型 {model_name} ...\n"
        "异步 filetrans 任务可能耗时几十秒到数分钟。",
        None, 0, 0, parent,
    )
    progress.setWindowTitle("校验音频模型")
    progress.setWindowModality(Qt.ApplicationModal)
    progress.setCancelButton(None)
    progress.show()
    try:
        if model_catalog.is_asr_long_family(model_name):
            # filetrans 家族只接受 DashScope 原生异步接口，chat.completions 必然 4xx；
            # 本地文件先上传 OSS 换取 oss:// URL（与生产识别路径一致）
            url = remote_url
            if not url:
                try:
                    url = _upload_filetrans_probe_audio(client.cfg.api.api_key, model_name, local_path)
                except Exception as exc:
                    QMessageBox.critical(parent, "上传失败", f"本地音频上传 OSS 失败：\n{exc}")
                    return False
            ok, msg = client.probe_audio_filetrans_model(model_name, url, max_wait=600)
            kind = "asr_long"
        elif remote_url:
            ok, msg = client.probe_audio_filetrans_model(model_name, remote_url, max_wait=600)
            kind = "asr_long"
        else:
            # 本地音频走同步路径（仅适合 omni / 短模型）
            ok, msg = client.probe_audio_short_model(model_name, local_path, timeout=120)
            kind = "asr_short"
    finally:
        progress.close()
    if not ok:
        QMessageBox.critical(parent, "音频模型不可用",
                             f"模型 {model_name} 测试失败：\n{msg}\n\n该模型不会被保存到下拉清单。")
        return False
    model_catalog.save_user_audio_model(model_catalog.AudioModel(
        name=model_name,
        label=f"{model_name} — 用户自定义（已通过测试）",
        kind=kind,
        free_quota=False,
        note=f"validate_ok: {msg[:120]}",
    ))
    QMessageBox.information(parent, "音频模型可用",
                            f"模型 {model_name} 测试通过：{msg}\n已加入下拉清单 (kind={kind})。")
    return True


def validate_and_register(
    parent: QWidget,
    *,
    api_key: str,
    base_url: str,
    vision_model: str,
    audio_model: str,
) -> bool:
    """对自定义视觉/音频模型分别做真实测试。

    Returns:
        True 表示所有模型可用（builtin 直接通过，自定义经过测试）。
    """
    if not api_key:
        QMessageBox.warning(parent, "缺少 API Key", "请先填入 DashScope API Key。")
        return False

    cfg = AppConfig(
        api=type(AppConfig().api)(api_key=api_key, base_url=base_url),
    )
    client = LLMClient(cfg=cfg)

    if vision_model and not _is_known_model(vision_model, "vision"):
        if not _validate_vision(parent, client, vision_model):
            return False
    if audio_model and not _is_known_model(audio_model, "audio"):
        if not _validate_audio(parent, client, audio_model):
            return False
    return True
