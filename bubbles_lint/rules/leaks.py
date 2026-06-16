from __future__ import annotations

import ast
from collections.abc import Iterable

from bubbles_lint.models import Finding, ModuleContext, Severity


MUTABLE_LITERALS = (ast.List, ast.Dict, ast.Set)
MUTABLE_CALLS = frozenset({"dict", "list", "set", "defaultdict", "Counter"})
CONFIG_MODULE_NAMES = frozenset({"config", "settings", "environment", "env"})
SIDE_EFFECT_MODULES = {
    "filesystem": frozenset({"open", "pathlib", "shutil", "glob", "os.path"}),
    "network": frozenset({"requests", "httpx", "urllib", "socket", "aiohttp"}),
    "database": frozenset({"sqlite3", "sqlalchemy", "psycopg2", "pymongo", "redis"}),
    "subprocess": frozenset({"subprocess"}),
    "logging": frozenset({"logging"}),
    "rendering": frozenset({"jinja2", "render", "template", "matplotlib", "PIL"}),
}


class LeakRule:
    id = "bubble-leak"
    title = "Bubble Leak"

    def check(self, context: ModuleContext) -> list[Finding]:
        visitor = _LeakVisitor(context)
        visitor.visit(context.tree)
        return visitor.findings


class _LeakVisitor(ast.NodeVisitor):
    def __init__(self, context: ModuleContext) -> None:
        self.context = context
        self.findings: list[Finding] = []
        self.function_depth = 0
        self.import_aliases = _import_aliases(context.tree)

    def visit_Assign(self, node: ast.Assign) -> None:
        if self.function_depth == 0 and _is_mutable_value(node.value) and not _all_constants(node.targets):
            self.findings.append(Finding(
                rule="bubble-leak/global-mutable-state",
                severity=Severity.WARNING,
                path=self.context.relative_path,
                line=node.lineno,
                message="Module-level assignment creates mutable global state.",
                suggestion="Move mutable state behind an explicit object or pass it through function calls.",
            ))
        self.generic_visit(node)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        is_mutable_global = (
            self.function_depth == 0
            and node.value is not None
            and _is_mutable_value(node.value)
            and not _all_constants([node.target])
        )
        if is_mutable_global:
            self.findings.append(Finding(
                rule="bubble-leak/global-mutable-state",
                severity=Severity.WARNING,
                path=self.context.relative_path,
                line=node.lineno,
                message="Module-level assignment creates mutable global state.",
                suggestion="Move mutable state behind an explicit object or pass it through function calls.",
            ))
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._visit_function(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._visit_function(node)

    def _visit_function(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        self.function_depth += 1
        side_effects = _side_effect_kinds(node, self.import_aliases)
        if len(side_effects) > self.context.config.max_side_effect_kinds:
            kinds = ", ".join(sorted(side_effects))
            self.findings.append(Finding(
                rule="bubble-leak/mixed-side-effects",
                severity=Severity.WARNING,
                path=self.context.relative_path,
                line=node.lineno,
                message=f"Function '{node.name}' mixes side effects: {kinds}.",
                suggestion="Separate orchestration from filesystem, network, database, logging, and rendering work.",
            ))
        self.generic_visit(node)
        self.function_depth -= 1

    def visit_Subscript(self, node: ast.Subscript) -> None:
        if not _is_config_module(self.context.path) and _is_os_environ_read(node):
            self.findings.append(Finding(
                rule="bubble-leak/env-read-outside-config",
                severity=Severity.WARNING,
                path=self.context.relative_path,
                line=node.lineno,
                message="Environment variable read appears outside a config module.",
                suggestion="Read environment variables in a config boundary and pass values explicitly.",
            ))
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        if not _is_config_module(self.context.path) and _is_os_getenv_call(node):
            self.findings.append(Finding(
                rule="bubble-leak/env-read-outside-config",
                severity=Severity.WARNING,
                path=self.context.relative_path,
                line=node.lineno,
                message="Environment variable read appears outside a config module.",
                suggestion="Read environment variables in a config boundary and pass values explicitly.",
            ))
        self.generic_visit(node)


def _is_mutable_value(node: ast.AST) -> bool:
    if isinstance(node, MUTABLE_LITERALS):
        return True
    if isinstance(node, ast.Call):
        name = _call_name(node.func)
        return name in MUTABLE_CALLS
    return False


def _all_constants(nodes: list[ast.expr]) -> bool:
    names = [node.id for node in nodes if isinstance(node, ast.Name)]
    return bool(names) and all(name.isupper() for name in names)


def _is_config_module(path) -> bool:
    stem = path.stem.lower()
    return stem in CONFIG_MODULE_NAMES or stem.endswith("_config") or stem.endswith("_settings")


def _is_os_environ_read(node: ast.Subscript) -> bool:
    return _dotted_name(node.value) == "os.environ"


def _is_os_getenv_call(node: ast.Call) -> bool:
    return _call_name(node.func) in {"os.getenv", "os.environ.get"}


def _side_effect_kinds(function: ast.AST, aliases: dict[str, str]) -> set[str]:
    kinds: set[str] = set()
    for node in ast.walk(function):
        if isinstance(node, ast.Call):
            kinds.update(_side_effects_for_call(node, aliases))
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            kinds.update(_side_effects_for_import(node))
    return kinds


def _side_effects_for_call(node: ast.Call, aliases: dict[str, str]) -> set[str]:
    call = _call_name(node.func)
    kinds: set[str] = set()
    if call == "open":
        kinds.add("filesystem")
    if call == "print":
        kinds.add("rendering")

    resolved = _resolve_alias(call, aliases)
    return kinds | _matching_side_effects(resolved)


def _side_effects_for_import(node: ast.Import | ast.ImportFrom) -> set[str]:
    kinds: set[str] = set()
    for name in _imported_modules(node):
        kinds.update(_matching_side_effects(name))
    return kinds


def _matching_side_effects(name: str) -> set[str]:
    return {
        kind
        for kind, markers in SIDE_EFFECT_MODULES.items()
        if any(name == marker or name.startswith(f"{marker}.") for marker in markers)
    }


def _import_aliases(tree: ast.AST) -> dict[str, str]:
    aliases: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                aliases[alias.asname or alias.name.split(".")[0]] = alias.name
        elif isinstance(node, ast.ImportFrom) and node.module:
            for alias in node.names:
                aliases[alias.asname or alias.name] = f"{node.module}.{alias.name}"
    return aliases


def _imported_modules(node: ast.Import | ast.ImportFrom) -> Iterable[str]:
    if isinstance(node, ast.Import):
        for alias in node.names:
            yield alias.name
    elif node.module:
        yield node.module


def _resolve_alias(name: str, aliases: dict[str, str]) -> str:
    head, _, tail = name.partition(".")
    resolved = aliases.get(head, head)
    return f"{resolved}.{tail}" if tail else resolved


def _call_name(node: ast.AST) -> str:
    return _dotted_name(node)


def _dotted_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parent = _dotted_name(node.value)
        return f"{parent}.{node.attr}" if parent else node.attr
    return ""
