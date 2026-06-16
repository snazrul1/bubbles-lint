from __future__ import annotations

import ast

from bubbles.models import Finding, ModuleContext, Severity
from bubbles.rules.imports import imports


SMELLY_MODULES = frozenset({"utils.py", "helpers.py", "manager.py", "service.py"})
SMELLY_CLASS_SUFFIXES = ("Manager", "Service", "Handler")
BRANCH_NODES = (ast.If, ast.For, ast.AsyncFor, ast.While, ast.With, ast.AsyncWith, ast.Try, ast.Match)


class AiSmellRule:
    id = "ai-smells"
    title = "AI Smells"

    def check(self, context: ModuleContext) -> list[Finding]:
        findings: list[Finding] = []

        generic_finding = _generic_module_finding(context)
        if generic_finding:
            findings.append(generic_finding)

        for node in ast.walk(context.tree):
            if isinstance(node, ast.ClassDef) and node.name.endswith(SMELLY_CLASS_SUFFIXES):
                class_finding = _class_smell_finding(context, node)
                if class_finding:
                    findings.append(class_finding)

        max_depth, line = _max_nesting(context.tree)
        if max_depth > context.config.max_nesting_depth:
            findings.append(Finding(
                rule="ai-smells/deep-nesting",
                severity=Severity.WARNING,
                path=context.relative_path,
                line=line,
                message=(
                    f"Code nesting depth is {max_depth}; recommended maximum "
                    f"is {context.config.max_nesting_depth}."
                ),
                suggestion="Use guard clauses, smaller functions, or a simple pipeline to flatten control flow.",
            ))

        return findings


def _generic_module_finding(context: ModuleContext) -> Finding | None:
    if context.path.name not in SMELLY_MODULES:
        return None
    module_imports = imports(context.tree)
    is_large = context.line_count > context.config.max_ai_module_lines
    has_many_imports = len(module_imports) > context.config.max_imports_per_module
    if not is_large and not has_many_imports:
        return None
    return Finding(
        rule="ai-smells/generic-module",
        severity=Severity.WARNING,
        path=context.relative_path,
        line=1,
        message=(
            f"Generic module '{context.path.name}' has {context.line_count} lines "
            f"and {len(module_imports)} imports."
        ),
        suggestion="Rename around a specific responsibility and split unrelated helpers apart.",
    )


def _class_smell_finding(context: ModuleContext, node: ast.ClassDef) -> Finding | None:
    methods = [
        item for item in node.body
        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
    ]
    dependencies = _class_dependency_count(node)
    is_broad = (
        len(methods) > context.config.max_class_methods
        or dependencies > context.config.max_ai_class_dependencies
    )
    if not is_broad:
        return None
    return Finding(
        rule="ai-smells/god-class-name",
        severity=Severity.WARNING,
        path=context.relative_path,
        line=node.lineno,
        message=f"Class '{node.name}' looks broad: {len(methods)} methods, {dependencies} dependencies.",
        suggestion="Replace broad coordinator classes with smaller objects and explicit functions.",
    )


def _class_dependency_count(node: ast.ClassDef) -> int:
    names: set[str] = set()
    for item in ast.walk(node):
        if isinstance(item, ast.Attribute) and isinstance(item.value, ast.Name) and item.value.id == "self":
            names.add(item.attr)
    return len(names)


def _max_nesting(tree: ast.AST) -> tuple[int, int]:
    best_depth = 0
    best_line = 1

    def visit(node: ast.AST, depth: int) -> None:
        nonlocal best_depth, best_line
        next_depth = depth + 1 if isinstance(node, BRANCH_NODES) else depth
        if next_depth > best_depth:
            best_depth = next_depth
            best_line = getattr(node, "lineno", best_line)
        for child in ast.iter_child_nodes(node):
            visit(child, next_depth)

    visit(tree, 0)
    return best_depth, best_line
