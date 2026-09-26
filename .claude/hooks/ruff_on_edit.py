#!/usr/bin/env python3
"""PostToolUse hook: run ruff format + ruff check --fix after Edit/Write on .py files.

Exit 2 = ruff still reports errors after --fix (Claude sees stderr and fixes them).
Exit 0 = all clean or file not applicable.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def _get_py_path(payload: dict[str, object]) -> Path | None:
    """Return a Path if the edit targeted an existing .py file, else None."""
    if payload.get("tool_name", "") not in {"Write", "Edit", "NotebookEdit"}:
        return None
    tool_input = payload.get("tool_input", {})
    path_raw = tool_input.get("file_path", "") if isinstance(tool_input, dict) else ""
    if not isinstance(path_raw, str) or not path_raw.endswith(".py"):
        return None
    path = Path(path_raw)
    return path if path.exists() else None


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0

    path = _get_py_path(payload)
    if path is None:
        return 0

    cwd = str(path.parent)
    subprocess.run(  # check=False intentional: format errors are non-fatal
        ["uv", "run", "ruff", "format", str(path)],
        cwd=cwd,
        capture_output=True,
        check=False,
    )
    check = subprocess.run(
        ["uv", "run", "ruff", "check", "--fix", str(path)],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )
    if check.returncode == 0:
        return 0

    sys.stderr.write(
        f"[ruff_on_edit] ruff errors remain in {path}:\n{check.stdout}\n{check.stderr}\n"
    )
    return 2


try:
    sys.exit(main())
except Exception as exc:  # crash → fail closed (bare except justified: hook must not fail open)
    sys.stderr.write(f"[ruff_on_edit] hook crashed: {exc}\n")
    sys.exit(2)
