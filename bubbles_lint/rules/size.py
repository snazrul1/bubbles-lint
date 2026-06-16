from __future__ import annotations

import ast

from bubbles_lint.models import Finding, ModuleContext, Severity


class SizeRule:
    id = "bubble-burst"
    title = "Bubble Burst"

    def check(self, context: ModuleContext) -> list[Finding]:
        findings: list[Finding] = []

        file_finding = _file_size_finding(context)
        if file_finding:
            findings.append(file_finding)

        for node in ast.walk(context.tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                findings.extend(_function_findings(context, node))

            if isinstance(node, ast.ClassDef):
                class_finding = _class_finding(context, node)
                if class_finding:
                    findings.append(class_finding)

        return findings


def _file_size_finding(context: ModuleContext) -> Finding | None:
    if context.line_count <= context.config.max_file_lines:
        return None
    return Finding(
        rule="bubble-burst/file-too-large",
        severity=Severity.WARNING,
        path=context.relative_path,
        line=1,
        message=(
            f"File has {context.line_count} lines; recommended maximum "
            f"is {context.config.max_file_lines}."
        ),
        suggestion="Split this module into smaller bubbles with one responsibility each.",
    )


def _function_findings(
    context: ModuleContext,
    node: ast.FunctionDef | ast.AsyncFunctionDef,
) -> list[Finding]:
    findings: list[Finding] = []
    length = _node_length(node)
    if length > context.config.max_function_lines:
        findings.append(Finding(
            rule="bubble-burst/function-too-large",
            severity=Severity.WARNING,
            path=context.relative_path,
            line=node.lineno,
            message=(
                f"Function '{node.name}' has {length} lines; recommended "
                f"maximum is {context.config.max_function_lines}."
            ),
            suggestion="Extract smaller functions with explicit inputs and outputs.",
        ))

    param_count = _parameter_count(node.args)
    if param_count > context.config.max_function_params:
        findings.append(Finding(
            rule="bubble-burst/too-many-parameters",
            severity=Severity.WARNING,
            path=context.relative_path,
            line=node.lineno,
            message=(
                f"Function '{node.name}' has {param_count} parameters; "
                f"recommended maximum is {context.config.max_function_params}."
            ),
            suggestion="Group related data behind a clear interface or split responsibilities.",
        ))
    return findings


def _class_finding(context: ModuleContext, node: ast.ClassDef) -> Finding | None:
    methods = [
        item for item in node.body
        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
    ]
    if len(methods) <= context.config.max_class_methods:
        return None
    return Finding(
        rule="bubble-burst/class-too-many-methods",
        severity=Severity.WARNING,
        path=context.relative_path,
        line=node.lineno,
        message=(
            f"Class '{node.name}' has {len(methods)} methods; recommended "
            f"maximum is {context.config.max_class_methods}."
        ),
        suggestion="Split the class into smaller collaborators with narrower roles.",
    )


def _node_length(node: ast.AST) -> int:
    end = getattr(node, "end_lineno", None) or getattr(node, "lineno", 1)
    return end - getattr(node, "lineno", 1) + 1


def _parameter_count(args: ast.arguments) -> int:
    positional = list(args.posonlyargs) + list(args.args)
    if positional and positional[0].arg in {"self", "cls"}:
        positional = positional[1:]
    return len(positional) + len(args.kwonlyargs) + (1 if args.vararg else 0) + (1 if args.kwarg else 0)
