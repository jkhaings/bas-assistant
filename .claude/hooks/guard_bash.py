#!/usr/bin/env python3
"""PreToolUse hook: block Bash commands that could expose secrets or cause harm.

Exit 2 = block (Claude Code's only signal that stops the tool call).
Exit 0 = allow.
Any other exit = non-blocking (fails open by spec); we catch all exceptions and
exit 2 so the guard is never silently bypassed by a crash.
"""

from __future__ import annotations

import json
import re
import sys

# ── policy table ─────────────────────────────────────────────────────────────
_DENY: list[tuple[str, re.Pattern[str]]] = [
    (
        "env file direct access",
        re.compile(r"(?:cat|head|tail|less|more|bat)\s+[^\s]*\.bas-assistant\.env"),
    ),
    (
        "env file read via path",
        re.compile(r"(?:cat|head|tail|less|more|bat)\s+[^\s]*(?<!\.example)\.env(?:\b|$)"),
    ),
    ("printenv", re.compile(r"\bprintenv\b")),
    ("bare env command", re.compile(r"(?:^|&&|\|)\s*env\b")),
    (
        "echo of secret env var",
        re.compile(
            r"\$(?:{)?(?:OPENAI_API_KEY|ANTHROPIC_API_KEY|GEMINI_API_KEY"
            r"|ADMIN_TOKEN|LANGFUSE_PUBLIC_KEY|LANGFUSE_SECRET_KEY"
            r"|GRAFANA_ADMIN_PASSWORD|.*_API_KEY|.*_SECRET_KEY|.*_TOKEN|.*_PASSWORD)"
        ),
    ),
    (
        "docker compose config without --quiet/-q",
        re.compile(r"docker\s+compose\s+(?:(?!--quiet|-q)\S+\s+)*config(?!\s+--quiet)(?!\s+-q)"),
    ),
    ("docker inspect", re.compile(r"\bdocker\s+inspect\b")),
    ("docker exec env/printenv", re.compile(r"docker\s+exec\s+.*\b(?:env|printenv|environ)\b")),
    ("git push --force", re.compile(r"git\s+push\s+.*(?:--force|-f)\b")),
    ("git push with -f flag", re.compile(r"git\s+push\s+-f\b")),
    ("git merge", re.compile(r"\bgit\s+merge\b")),
    ("gh run rerun", re.compile(r"\bgh\s+run\s+rerun\b")),
    ("gh workflow run", re.compile(r"\bgh\s+workflow\s+run\b")),
    ("support.deltacontrols.com (SSO-gated)", re.compile(r"support\.deltacontrols\.com")),
]

_EXPLICIT_ALLOW: list[re.Pattern[str]] = [
    re.compile(r"docker\s+compose\s+config\s+(?:--quiet|-q)"),
]


def _should_block(command: str) -> tuple[bool, str]:
    """Return (block, reason). Explicit allows win before deny check."""
    for allow_pat in _EXPLICIT_ALLOW:
        if allow_pat.search(command):
            return False, ""
    for desc, pat in _DENY:
        if pat.search(command):
            return True, desc
    return False, ""


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0

    command: str = ""
    if payload.get("tool_name", "") == "Bash":
        command = payload.get("tool_input", {}).get("command", "")

    if not command:
        return 0

    block, reason = _should_block(command)
    if block:
        sys.stderr.write(f"[guard_bash] BLOCKED: {reason}\nCommand: {command[:120]}\n")
    return 2 if block else 0


try:
    sys.exit(main())
except Exception as exc:  # crash → fail closed (bare except justified: hook must not fail open)
    sys.stderr.write(f"[guard_bash] hook crashed: {exc}\n")
    sys.exit(2)
