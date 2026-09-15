"""Live probe: qwen-audio-3.0-asr-flash-filetrans submit payload shapes.

Submits the same public sample audio with input.file_url (singular, documented
for the qwen filetrans family) and input.file_urls (plural, paraformer style)
and prints HTTP status + body for each, then polls any accepted task to
completion. Reads the DashScope API key from the app's QSettings; never prints it.

Run:  python legacy_app/tests/live_probe_qwen_audio_3_filetrans.py
"""

from __future__ import annotations

import json
import sys
import time

import requests

SUBMIT_URL = "https://dashscope.aliyuncs.com/api/v1/services/audio/asr/transcription"
TASK_URL = "https://dashscope.aliyuncs.com/api/v1/tasks/{task_id}"
SAMPLE_AUDIO = "https://dashscope.oss-cn-beijing.aliyuncs.com/audios/welcome.mp3"
MODEL = "qwen-audio-3.0-asr-flash-filetrans"


def _api_key() -> str:
    from PyQt5.QtCore import QSettings

    key = QSettings("OCRLLM", "QCR").value("ui/api_key", "")
    if not key:
        sys.exit("ui/api_key not found in QSettings(OCRLLM/QCR)")
    return str(key)


def _submit(key: str, audio_input: dict) -> tuple[int, str]:
    resp = requests.post(
        SUBMIT_URL,
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "X-DashScope-Async": "enable",
        },
        json={
            "model": MODEL,
            "input": audio_input,
            "parameters": {"channel_id": [0], "enable_itn": False, "enable_words": True},
        },
        timeout=30,
    )
    return resp.status_code, resp.text


def _poll(key: str, task_id: str, max_wait: float = 300.0) -> dict:
    url = TASK_URL.format(task_id=task_id)
    deadline = time.monotonic() + max_wait
    while time.monotonic() < deadline:
        resp = requests.get(url, headers={"Authorization": f"Bearer {key}"}, timeout=30)
        data = resp.json()
        status = data.get("output", {}).get("task_status", "")
        print(f"  poll: status={status}")
        if status in ("SUCCEEDED", "FAILED", "UNKNOWN", "SUCCESS_WITH_NO_VALID_FRAGMENT"):
            return data
        time.sleep(5)
    return {"error": "timeout"}


def main() -> None:
    key = _api_key()

    print(f"== model: {MODEL}")
    print("== 1) input.file_url (singular, documented for qwen filetrans family)")
    status, text = _submit(key, {"file_url": SAMPLE_AUDIO})
    print(f"  HTTP {status}: {text[:400]}")

    print("== 2) input.file_urls (plural, paraformer style used by probe_audio_filetrans_model)")
    status2, text2 = _submit(key, {"file_urls": [SAMPLE_AUDIO]})
    print(f"  HTTP {status2}: {text2[:400]}")

    if status == 200:
        task_id = json.loads(text).get("output", {}).get("task_id")
        print(f"== polling accepted task {task_id}")
        result = _poll(key, task_id)
        out = result.get("output", {})
        print("  final:", json.dumps(out, ensure_ascii=False)[:600])


if __name__ == "__main__":
    main()
