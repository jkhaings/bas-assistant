#!/usr/bin/env python3
"""PreToolUse hook (if: "Bash(git commit *)"):
   run gitleaks on staged changes before any git commit.

Exit 2 blocks the commit. Exit 0 allows it.
"""

from __future__ import annotations

import json
import subprocess
import sys


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0

    command = payload.get("tool_input", {}).get("command", "")
    if not command or "git commit" not in command:
        return 0

    cwd = payload.get("cwd", ".")
    result = subprocess.run(  # check=False intentional: returncode drives logic
        ["gitleaks", "git", "--pre-commit", "--staged", "--redact", "--no-banner"],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode == 0:
        return 0

    sys.stderr.write(
        f"[gitleaks_on_commit] BLOCKED: gitleaks found secrets in staged diff.\n"
        f"{result.stdout}\n{result.stderr}\n"
    )
    return 2


try:
    sys.exit(main())
except Exception as exc:  # crash → fail closed (bare except justified: hook must not fail open)
    sys.stderr.write(f"[gitleaks_on_commit] hook crashed: {exc}\n")
    sys.exit(2)
