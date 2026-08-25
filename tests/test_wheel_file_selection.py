"""Contract for repository-only files excluded from the runtime wheel."""

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_wheel_excludes_agent_maintenance_instructions() -> None:
    configuration = (PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    wheel_section = configuration.split(
        "[tool.hatch.build.targets.wheel]", maxsplit=1
    )[1].split("\n[", maxsplit=1)[0]

    assert 'exclude = ["/src/ocrllm/AGENTS.md"]' in wheel_section
