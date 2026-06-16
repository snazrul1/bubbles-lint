<p align="center">
  <img src="https://raw.githubusercontent.com/snazrul1/bubbles-lint/main/assets/bubbles-lint-logo.png" alt="Bubbles Lint logo" width="220">
</p>

Bubbles Lint is an architectural linter for Python code. It is inspired by Unix and Linux software design principles: do one thing well, keep modules small, compose simple parts, and make boundaries easy to inspect.

Think of it as Ruff for architecture. It does not compete with Ruff, Black, Flake8, or Pylint. Bubbles Lint looks for software shape problems: code that is too large, too coupled, too magical, or too monolithic.

## Installation

```bash
pip install bubbles-lint
```

For local development from this repository:

```bash
pip install -e ".[dev]"
```

## Usage

Scan the current repository:

```bash
bubbles-lint scan .
```

Emit JSON for CI systems:

```bash
bubbles-lint scan . --json
```

Bubbles Lint exits with status `1` when findings are present and `0` when the scan is clean.

## Philosophy

Bubbles Lint encourages codebases where:

- modules have one clear responsibility
- functions and classes stay small enough to replace
- dependencies flow through explicit interfaces
- configuration is loaded at the edge
- side effects are isolated from pure logic
- text and data move through well-defined boundaries
- components are easy to inspect, test, and swap

The goal is not style enforcement. The goal is software design discipline, especially in Python codebases that have grown quickly with help from AI coding assistants.

## Rules

### Bubble Burst

Flags code that has grown too large:

- files over `max_file_lines`
- functions over `max_function_lines`
- classes with more than `max_class_methods`
- functions with more than `max_function_params`

### Bubble Leak

Flags hidden coupling and mixed side effects:

- global mutable state
- direct environment variable reads outside config modules
- functions mixing too many side-effect categories, such as filesystem, network, database, subprocess, logging, and rendering

### Bubble Boundary

Flags dependency boundary problems:

- circular imports where practical
- modules importing too many dependencies
- imports from private modules like `from package._internal import thing`

### AI Smells

Flags common broad abstractions produced in rushed or generated code:

- oversized `utils.py`, `helpers.py`, `manager.py`, and `service.py` modules
- broad classes ending in `Manager`, `Service`, or `Handler`
- deeply nested control flow

## Configuration

Configure Bubbles Lint in `pyproject.toml`:

```toml
[tool.bubbles-lint]
max_file_lines = 500
max_function_lines = 50
max_class_methods = 10
max_function_params = 5
max_imports_per_module = 20
max_nesting_depth = 4
allow_private_imports = false
```

Additional knobs:

```toml
[tool.bubbles-lint]
max_side_effect_kinds = 3
max_ai_module_lines = 200
max_ai_class_dependencies = 8
excludes = ["generated"]
```

Bubbles Lint always ignores `.venv`, `venv`, `.git`, `__pycache__`, `build`, and `dist`.

Existing `[tool.bubbles]` configs are still read for compatibility, but new projects should use `[tool.bubbles-lint]`.

## Human Output

```text
Bubble: Bubble Burst

src/payment_service.py:1
warning: File has 1437 lines; recommended maximum is 500.

Suggestion:
Split this module into smaller bubbles with one responsibility each.
```

## JSON Output

```json
{
  "findings": [
    {
      "rule": "bubble-burst/file-too-large",
      "severity": "warning",
      "path": "src/payment_service.py",
      "line": 1,
      "message": "File has 1437 lines; recommended maximum is 500.",
      "suggestion": "Split this module into smaller bubbles with one responsibility each."
    }
  ],
  "files_scanned": 1
}
```

## CI

Example GitHub Actions step:

```yaml
- name: Install Bubbles Lint
  run: pip install .

- name: Scan architecture
  run: bubbles-lint scan . --json
```

## Development

Run tests:

```bash
pip install -e ".[dev]"
pytest
```

The rule engine is intentionally small. New rules implement a `check(context)` method and return `Finding` objects. Parsing, configuration, scanning, reporting, and CLI code are separated so the tool can grow without becoming the kind of monolith it warns about.
