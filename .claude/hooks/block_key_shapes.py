#!/usr/bin/env python3
"""PreToolUse hook: block Write/Edit that would embed a real key shape.

Scans every string value in tool_input rather than named fields,
because the exact field layout isn't documented in the hooks reference.

Exit 2 = block, exit 0 = allow.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

# Identical to the pattern in src/bas_assistant/logging.py — keep in sync.
_KEY_SHAPE = re.compile(
    r"(?<![A-Za-z0-9])"
    r"(?:sk-(?:ant-|proj-)?[A-Za-z0-9_\-]{20,}"
    r"|AIza[0-9A-Za-z_\-]{35}"
    r"|ghp_[A-Za-z0-9]{36})"
)

_ALLOWLISTED_PATHS = {"tests/unit/fixtures/fake_keys.txt"}


def _all_strings(obj: object) -> list[str]:
    """Recursively collect every string value in a JSON-decoded object."""
    if isinstance(obj, str):
        return [obj]
    if isinstance(obj, dict):
        return [s for v in obj.values() for s in _all_strings(v)]
    if isinstance(obj, list):
        return [s for item in obj for s in _all_strings(item)]
    return []


def _is_allowlisted(payload: dict[str, object]) -> bool:
    """Return True if tool_input.file_path is in the allowlist."""
    tool_input = payload.get("tool_input", {})
    if not isinstance(tool_input, dict):
        return False
    path_raw = tool_input.get("file_path", "")
    if not isinstance(path_raw, str) or not path_raw:
        return False
    try:
        path = Path(path_raw)
        cwd = Path(payload.get("cwd", "."))  # type: ignore[arg-type]
        rel = path.relative_to(cwd) if path.is_absolute() else path
    except ValueError:
        rel = Path(path_raw)
    return str(rel) in _ALLOWLISTED_PATHS or path_raw.endswith("fake_keys.txt")


def _contains_key_shape(payload: dict[str, object]) -> bool:
    return any(_KEY_SHAPE.search(v) for v in _all_strings(payload.get("tool_input", {})))


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0

    if payload.get("tool_name", "") not in {"Write", "Edit", "NotebookEdit"}:
        return 0

    if _is_allowlisted(payload) or not _contains_key_shape(payload):
        return 0

    sys.stderr.write(
        "[block_key_shapes] BLOCKED: content contains a key shape. "
        "Keys go in ~/.bas-assistant.env, never in a file.\n"
    )
    return 2


try:
    sys.exit(main())
except Exception as exc:  # crash → fail closed (bare except justified: hook must not fail open)
    sys.stderr.write(f"[block_key_shapes] hook crashed: {exc}\n")
    sys.exit(2)
