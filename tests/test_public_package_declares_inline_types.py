from importlib.resources import files


def test_public_package_declares_inline_types() -> None:
    marker = files("ocrllm").joinpath("py.typed")

    assert marker.is_file()
    assert marker.read_bytes() == b""
