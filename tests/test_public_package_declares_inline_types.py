import ast
from importlib.resources import files

import ocrllm


def test_public_package_declares_inline_types() -> None:
    marker = files("ocrllm").joinpath("py.typed")

    assert marker.is_file()
    assert marker.read_bytes() == b""


def test_static_public_exports_match_runtime_exports() -> None:
    package_source = files("ocrllm").joinpath("__init__.py").read_text(encoding="utf-8")
    module = ast.parse(package_source)
    type_checking_blocks = [
        statement
        for statement in module.body
        if isinstance(statement, ast.If)
        and isinstance(statement.test, ast.Name)
        and statement.test.id == "TYPE_CHECKING"
    ]

    assert len(type_checking_blocks) == 1
    static_aliases = tuple(
        alias
        for statement in type_checking_blocks[0].body
        if isinstance(statement, ast.ImportFrom)
        for alias in statement.names
    )
    assert all(alias.asname == alias.name for alias in static_aliases)
    static_exports = {alias.asname for alias in static_aliases}
    assert static_exports == set(ocrllm.__all__)
