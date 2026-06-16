from __future__ import annotations

import ast
from pathlib import Path
from typing import Iterable

from bubbles_lint.config import Config, load_config
from bubbles_lint.models import Finding, ModuleContext, Rule, ScanResult, Severity
from bubbles_lint.rules.boundaries import BoundaryRule, build_import_graph
from bubbles_lint.rules.registry import default_rules


def scan_path(path: Path, config: Config | None = None, rules: Iterable[Rule] | None = None) -> ScanResult:
    root = path.resolve()
    if root.is_file():
        root = root.parent

    active_config = config or load_config(root)
    files = list(iter_python_files(path.resolve(), active_config))
    active_rules = list(rules) if rules is not None else _rules_for_files(files, root)
    result = ScanResult(files_scanned=0)

    for file_path in files:
        result.files_scanned += 1
        try:
            source = file_path.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=str(file_path))
        except SyntaxError as error:
            result.findings.append(Finding(
                rule="parser/syntax-error",
                severity=Severity.ERROR,
                path=_relative(file_path, root),
                line=error.lineno or 1,
                message=f"Could not parse Python file: {error.msg}.",
                suggestion="Fix the syntax error before Bubbles Lint can inspect this module's architecture.",
            ))
            continue
        except (OSError, UnicodeDecodeError) as error:
            result.findings.append(Finding(
                rule="parser/read-error",
                severity=Severity.ERROR,
                path=_relative(file_path, root),
                line=1,
                message=f"Could not read Python file: {error}.",
                suggestion="Ensure the file is readable UTF-8 Python source.",
            ))
            continue

        context = ModuleContext(
            path=file_path,
            root=root,
            source=source,
            tree=tree,
            line_count=len(source.splitlines()),
            config=active_config,
        )
        for rule in active_rules:
            result.extend(rule.check(context))

    result.findings.sort(key=lambda item: (item.path.as_posix(), item.line, item.rule))
    return result


def iter_python_files(path: Path, config: Config) -> Iterable[Path]:
    if path.is_file():
        if path.suffix == ".py":
            yield path
        return

    for item in sorted(path.rglob("*.py")):
        if any(part in config.excludes for part in item.parts):
            continue
        yield item


def _rules_for_files(files: list[Path], root: Path) -> list[Rule]:
    graph = build_import_graph(files, root)
    return [
        BoundaryRule(import_graph=graph) if isinstance(rule, BoundaryRule) else rule
        for rule in default_rules()
    ]


def _relative(path: Path, root: Path) -> Path:
    try:
        return path.relative_to(root)
    except ValueError:
        return path
