from __future__ import annotations

import json

from bubbles_lint.cli import main
from bubbles_lint.config import Config
from bubbles_lint.scanner import scan_path


def write(path, content: str) -> None:
    path.write_text(content.strip() + "\n", encoding="utf-8")


def rules(result):
    return {finding.rule for finding in result.findings}


def test_bubble_burst_size_rules(tmp_path):
    source = "\n".join([
        "def too_many(a, b, c, d, e, f):",
        "    pass",
        "",
        "def too_long():",
        *["    x = 1" for _ in range(6)],
        "",
        "class Many:",
        *[f"    def m{i}(self): pass" for i in range(4)],
    ])
    path = tmp_path / "large.py"
    path.write_text(source, encoding="utf-8")

    result = scan_path(
        tmp_path,
        Config(max_file_lines=5, max_function_lines=5, max_class_methods=3, max_function_params=5),
    )

    assert "bubble-burst/file-too-large" in rules(result)
    assert "bubble-burst/function-too-large" in rules(result)
    assert "bubble-burst/class-too-many-methods" in rules(result)
    assert "bubble-burst/too-many-parameters" in rules(result)


def test_bubble_leak_rules(tmp_path):
    write(tmp_path / "worker.py", """
import logging
import os
import requests
import sqlite3
import subprocess

cache = {}

def run():
    token = os.environ["TOKEN"]
    logging.info(token)
    requests.get("https://example.com")
    sqlite3.connect(":memory:")
    subprocess.run(["true"])
""")

    result = scan_path(tmp_path, Config(max_side_effect_kinds=2))

    assert "bubble-leak/global-mutable-state" in rules(result)
    assert "bubble-leak/env-read-outside-config" in rules(result)
    assert "bubble-leak/mixed-side-effects" in rules(result)


def test_bubble_boundary_rules(tmp_path):
    write(tmp_path / "a.py", """
import b
from package._internal import thing
""")
    write(tmp_path / "b.py", """
import a
""")

    result = scan_path(tmp_path, Config(max_imports_per_module=1))

    assert "bubble-boundary/private-import" in rules(result)
    assert "bubble-boundary/circular-import" in rules(result)


def test_too_many_imports(tmp_path):
    write(tmp_path / "many_imports.py", """
import a
import b
import c
""")

    result = scan_path(tmp_path, Config(max_imports_per_module=2))

    assert "bubble-boundary/too-many-imports" in rules(result)


def test_ai_smells_rules(tmp_path):
    write(tmp_path / "utils.py", """
def f():
    if True:
        if True:
            if True:
                if True:
                    if True:
                        return 1

class PaymentManager:
    def __init__(self):
        self.a = 1
        self.b = 2
        self.c = 3

    def one(self): pass
    def two(self): pass
""")

    result = scan_path(
        tmp_path,
        Config(
            max_ai_module_lines=5,
            max_class_methods=1,
            max_ai_class_dependencies=2,
            max_nesting_depth=3,
        ),
    )

    assert "ai-smells/generic-module" in rules(result)
    assert "ai-smells/god-class-name" in rules(result)
    assert "ai-smells/deep-nesting" in rules(result)


def test_syntax_errors_are_findings(tmp_path):
    write(tmp_path / "broken.py", """
def nope(
""")

    result = scan_path(tmp_path)

    assert "parser/syntax-error" in rules(result)
    assert result.has_errors


def test_config_from_pyproject_and_cli_json(tmp_path, capsys):
    write(tmp_path / "pyproject.toml", """
[tool.bubbles-lint]
max_file_lines = 1
""")
    write(tmp_path / "sample.py", """
x = 1
y = 2
""")

    exit_code = main(["scan", str(tmp_path), "--json"])
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == 1
    assert payload["findings"][0]["rule"] == "bubble-burst/file-too-large"


def test_legacy_bubbles_config_still_loads(tmp_path):
    write(tmp_path / "pyproject.toml", """
[tool.bubbles]
max_file_lines = 1
""")
    write(tmp_path / "sample.py", """
x = 1
y = 2
""")

    result = scan_path(tmp_path)

    assert "bubble-burst/file-too-large" in rules(result)
