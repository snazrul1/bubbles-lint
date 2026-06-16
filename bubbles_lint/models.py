from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Protocol

from bubbles_lint.config import Config


class Severity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


@dataclass(frozen=True)
class Finding:
    rule: str
    severity: Severity
    path: Path
    line: int
    message: str
    suggestion: str

    def to_json(self) -> dict[str, object]:
        return {
            "rule": self.rule,
            "severity": self.severity.value,
            "path": self.path.as_posix(),
            "line": self.line,
            "message": self.message,
            "suggestion": self.suggestion,
        }


@dataclass(frozen=True)
class ModuleContext:
    path: Path
    root: Path
    source: str
    tree: object
    line_count: int
    config: Config

    @property
    def relative_path(self) -> Path:
        try:
            return self.path.relative_to(self.root)
        except ValueError:
            return self.path


class Rule(Protocol):
    id: str
    title: str

    def check(self, context: ModuleContext) -> list[Finding]:
        ...


@dataclass
class ScanResult:
    findings: list[Finding] = field(default_factory=list)
    files_scanned: int = 0

    @property
    def has_errors(self) -> bool:
        return any(finding.severity is Severity.ERROR for finding in self.findings)

    @property
    def has_findings(self) -> bool:
        return bool(self.findings)

    def extend(self, findings: list[Finding]) -> None:
        self.findings.extend(findings)
