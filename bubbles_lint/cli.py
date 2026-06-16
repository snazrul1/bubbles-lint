from __future__ import annotations

import argparse
import sys
from pathlib import Path

from bubbles_lint.config import load_config
from bubbles_lint.report import format_human, format_json
from bubbles_lint.scanner import scan_path


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "scan":
        target = Path(args.path)
        config = load_config(target)
        result = scan_path(target, config=config)
        output = format_json(result) if args.json else format_human(result)
        print(output)
        return 1 if result.has_findings else 0

    parser.print_help()
    return 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="bubbles-lint",
        description="Architectural linting for small, composable Python code.",
    )
    subcommands = parser.add_subparsers(dest="command")

    scan = subcommands.add_parser("scan", help="Scan Python files for architecture findings.")
    scan.add_argument("path", nargs="?", default=".", help="File or directory to scan.")
    scan.add_argument("--json", action="store_true", help="Emit machine-readable JSON output.")

    return parser


if __name__ == "__main__":
    sys.exit(main())
