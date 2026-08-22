from __future__ import annotations

import builtins

import pytest

from ocrllm.audio.load_miniaudio import load_miniaudio
from ocrllm.errors import DependencyMissing


@pytest.mark.parametrize("import_error", [ImportError, OSError])
def test_load_miniaudio_maps_missing_or_unloadable_dependency(
    monkeypatch,
    import_error,
) -> None:
    original_import = builtins.__import__

    def guarded_import(name, *args, **kwargs):
        if name == "miniaudio":
            raise import_error("secret-miniaudio-import-sentinel")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guarded_import)

    with pytest.raises(DependencyMissing) as caught:
        load_miniaudio()

    assert str(caught.value) == (
        "MP3 validation requires the optional 'audio' dependencies."
    )
    assert caught.value.code == "DEPENDENCY_MISSING"
    assert caught.value.details == {
        "extra": "audio",
        "required_distribution": "miniaudio>=1.71,<2",
    }
    assert "secret-miniaudio-import-sentinel" not in repr(caught.value)
