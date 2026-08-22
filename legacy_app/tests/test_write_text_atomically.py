from pathlib import Path
from unittest.mock import patch

import pytest

from OCRLLM.core.write_text_atomically import write_text_atomically


def test_write_text_atomically_replaces_content_and_removes_temp_file(tmp_path):
    target = tmp_path / "result.md"
    target.write_text("old", encoding="utf-8")

    write_text_atomically(target, "新的内容")

    assert target.read_text(encoding="utf-8") == "新的内容"
    assert target.read_bytes() == "新的内容".encode("utf-8")
    assert list(tmp_path.iterdir()) == [target]


def test_write_text_atomically_preserves_original_when_replace_fails(tmp_path):
    target = tmp_path / "result.md"
    target.write_text("paid original", encoding="utf-8")

    with patch(
        "OCRLLM.core.write_text_atomically.os.replace",
        side_effect=OSError("replace failed"),
    ):
        with pytest.raises(OSError, match="replace failed"):
            write_text_atomically(target, "replacement")

    assert target.read_text(encoding="utf-8") == "paid original"
    assert list(tmp_path.iterdir()) == [target]


def test_write_text_atomically_preserves_original_when_encoding_fails(tmp_path):
    target = tmp_path / "result.md"
    target.write_text("paid original", encoding="utf-8")

    with pytest.raises(UnicodeEncodeError):
        write_text_atomically(target, "invalid surrogate: \ud800")

    assert target.read_text(encoding="utf-8") == "paid original"
    assert list(tmp_path.iterdir()) == [target]


def test_write_text_atomically_preserves_original_when_fsync_fails(tmp_path):
    target = tmp_path / "result.md"
    target.write_text("paid original", encoding="utf-8")

    with patch(
        "OCRLLM.core.write_text_atomically.os.fsync",
        side_effect=OSError("fsync failed"),
    ):
        with pytest.raises(OSError, match="fsync failed"):
            write_text_atomically(target, "replacement")

    assert target.read_text(encoding="utf-8") == "paid original"
    assert list(tmp_path.iterdir()) == [target]
