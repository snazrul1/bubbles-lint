from __future__ import annotations

import ast
from collections import defaultdict
from pathlib import Path

from bubbles.models import Finding, ModuleContext, Severity
from bubbles.rules.imports import imports


class BoundaryRule:
    id = "bubble-boundary"
    title = "Bubble Boundary"

    def __init__(self, import_graph: dict[str, set[str]] | None = None) -> None:
        self.import_graph = import_graph or {}

    def check(self, context: ModuleContext) -> list[Finding]:
        findings: list[Finding] = []
        module_imports = imports(context.tree)

        if len(module_imports) > context.config.max_imports_per_module:
            findings.append(Finding(
                rule="bubble-boundary/too-many-imports",
                severity=Severity.WARNING,
                path=context.relative_path,
                line=1,
                message=(
                    f"Module imports {len(module_imports)} dependencies; recommended maximum "
                    f"is {context.config.max_imports_per_module}."
                ),
                suggestion="Narrow this module's responsibilities or move integration code to a boundary.",
            ))

        if not context.config.allow_private_imports:
            for node in ast.walk(context.tree):
                if isinstance(node, ast.ImportFrom) and node.module and _has_private_part(node.module):
                    findings.append(Finding(
                        rule="bubble-boundary/private-import",
                        severity=Severity.WARNING,
                        path=context.relative_path,
                        line=node.lineno,
                        message=f"Import reaches into private module '{node.module}'.",
                        suggestion="Depend on a public interface instead of a private implementation module.",
                    ))

        module_name = module_name_for_path(context.root, context.path)
        for target in self.import_graph.get(module_name, set()):
            if module_name in self.import_graph.get(target, set()):
                findings.append(Finding(
                    rule="bubble-boundary/circular-import",
                    severity=Severity.ERROR,
                    path=context.relative_path,
                    line=1,
                    message=f"Module '{module_name}' and '{target}' import each other.",
                    suggestion="Extract shared contracts into a smaller third module or invert the dependency.",
                ))

        return findings


def build_import_graph(files: list[Path], root: Path) -> dict[str, set[str]]:
    modules = {module_name_for_path(root, path): path for path in files}
    graph: dict[str, set[str]] = defaultdict(set)
    for module, path in modules.items():
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (OSError, SyntaxError, UnicodeDecodeError):
            continue
        for imported in imports(tree):
            candidates = _candidate_modules(imported)
            for candidate in candidates:
                if candidate in modules and candidate != module:
                    graph[module].add(candidate)
    return graph


def module_name_for_path(root: Path, path: Path) -> str:
    relative = path.relative_to(root).with_suffix("")
    parts = list(relative.parts)
    if parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)

def _candidate_modules(name: str) -> list[str]:
    parts = name.split(".")
    return [".".join(parts[:index]) for index in range(len(parts), 0, -1)]


def _has_private_part(module: str) -> bool:
    return any(
        part.startswith("_") and not (part.startswith("__") and part.endswith("__"))
        for part in module.split(".")
    )
