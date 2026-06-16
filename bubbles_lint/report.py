from __future__ import annotations

import json
from collections import defaultdict
from types import MappingProxyType

from bubbles_lint.models import Finding, ScanResult


RULE_TITLES = MappingProxyType({
    "ai-smells": "AI Smells",
    "bubble-boundary": "Bubble Boundary",
    "bubble-burst": "Bubble Burst",
    "bubble-leak": "Bubble Leak",
    "parser": "Parser",
})


def format_json(result: ScanResult) -> str:
    return json.dumps(
        {
            "findings": [finding.to_json() for finding in result.findings],
            "files_scanned": result.files_scanned,
        },
        indent=2,
    )


def format_human(result: ScanResult) -> str:
    if not result.findings:
        return f"No bubbles burst. Scanned {result.files_scanned} Python file(s)."

    grouped: dict[str, list[Finding]] = defaultdict(list)
    for finding in result.findings:
        grouped[_family(finding.rule)].append(finding)

    chunks: list[str] = []
    for family in sorted(grouped):
        chunks.append(f"Bubble: {RULE_TITLES.get(family, family)}")
        for finding in grouped[family]:
            chunks.append("")
            chunks.append(f"{finding.path}:{finding.line}")
            chunks.append(f"{finding.severity.value}: {finding.message}")
            chunks.append("")
            chunks.append("Suggestion:")
            chunks.append(finding.suggestion)

    return "\n".join(chunks)


def _family(rule: str) -> str:
    return rule.split("/", 1)[0]
