from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any


DEFAULT_EXCLUDES = frozenset({
    ".git",
    ".venv",
    "__pycache__",
    "build",
    "dist",
    "venv",
})


@dataclass(frozen=True)
class Config:
    max_file_lines: int = 500
    max_function_lines: int = 50
    max_class_methods: int = 10
    max_function_params: int = 5
    max_imports_per_module: int = 20
    max_nesting_depth: int = 4
    max_side_effect_kinds: int = 3
    max_ai_module_lines: int = 200
    max_ai_class_dependencies: int = 8
    allow_private_imports: bool = False
    excludes: frozenset[str] = DEFAULT_EXCLUDES


def load_config(start: Path) -> Config:
    pyproject = find_pyproject(start)
    if pyproject is None:
        return Config()

    try:
        data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError):
        return Config()

    tool_config = data.get("tool", {})
    if not isinstance(tool_config, dict):
        return Config()

    values = tool_config.get("bubbles-lint", tool_config.get("bubbles", {}))
    if not isinstance(values, dict):
        return Config()

    return build_config(values)


def find_pyproject(start: Path) -> Path | None:
    current = start.resolve()
    if current.is_file():
        current = current.parent

    for directory in (current, *current.parents):
        pyproject = directory / "pyproject.toml"
        if pyproject.exists():
            return pyproject
    return None


def build_config(values: dict[str, Any]) -> Config:
    defaults = Config()
    kwargs: dict[str, Any] = {}
    for field_name in defaults.__dataclass_fields__:
        if field_name not in values:
            continue
        value = values[field_name]
        if field_name == "excludes":
            if isinstance(value, list) and all(isinstance(item, str) for item in value):
                kwargs[field_name] = DEFAULT_EXCLUDES | frozenset(value)
            continue
        kwargs[field_name] = value
    return Config(**kwargs)
