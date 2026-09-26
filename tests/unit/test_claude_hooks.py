"""Behaviour: Claude Code PreToolUse hooks block the right commands.

Each hook is invoked as a subprocess with a crafted JSON payload on stdin,
and we assert on the exit code and stderr content.
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

_HOOKS = Path(__file__).parent.parent.parent / ".claude" / "hooks"
_GUARD = str(_HOOKS / "guard_bash.py")
_BLOCK = str(_HOOKS / "block_key_shapes.py")
_FIXTURE = Path(__file__).parent / "fixtures" / "fake_keys.txt"


def _run_hook(script: str, payload: dict) -> subprocess.CompletedProcess:  # type: ignore[type-arg]
    return subprocess.run(
        [sys.executable, script],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        check=False,
    )


def _bash_payload(command: str) -> dict:  # type: ignore[type-arg]
    return {"tool_name": "Bash", "tool_input": {"command": command}, "cwd": "/tmp"}


def _write_payload(path: str, content: str) -> dict:  # type: ignore[type-arg]
    return {
        "tool_name": "Write",
        "tool_input": {"file_path": path, "content": content},
        "cwd": "/tmp",
    }


# ---------------------------------------------------------------------------
# guard_bash
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "cmd",
    [
        "cat ~/.bas-assistant.env",
        "echo $OPENAI_API_KEY",
        "printenv ANTHROPIC_API_KEY",
        "docker compose config",
        "docker inspect mycontainer",
        "git push --force origin main",
        "git push -f origin main",
        "git merge feature",
        "gh run rerun 12345",
        "gh workflow run ci.yml",
        "curl https://support.deltacontrols.com/api",
    ],
)
def test_bash_guard_blocks_dangerous_commands(cmd: str) -> None:
    result = _run_hook(_GUARD, _bash_payload(cmd))
    assert result.returncode == 2, f"expected block for: {cmd!r}\nstderr: {result.stderr}"


@pytest.mark.parametrize(
    "cmd",
    [
        "make lint",
        "uv sync",
        "pytest -m unit",
        "ruff check src/",
        "mypy src/",
        "git status",
        "git diff HEAD",
        "git add pyproject.toml",
        "docker compose up -d",
        "docker compose down",
        "docker compose config --quiet",
        "curl http://localhost:8000/healthz",
    ],
)
def test_bash_guard_allows_everyday_commands(cmd: str) -> None:
    result = _run_hook(_GUARD, _bash_payload(cmd))
    assert result.returncode != 2, f"unexpectedly blocked: {cmd!r}\nstderr: {result.stderr}"


# ---------------------------------------------------------------------------
# block_key_shapes
# ---------------------------------------------------------------------------


def test_write_guard_blocks_key_shapes() -> None:
    key = next(
        line.split("=", 1)[1]
        for line in _FIXTURE.read_text().splitlines()
        if line.startswith("FAKE_OPENAI=")
    )
    result = _run_hook(_BLOCK, _write_payload("/tmp/test_file.py", f"key = '{key}'"))
    assert result.returncode == 2, f"expected block\nstderr: {result.stderr}"


def test_write_guard_allows_the_fixture_path() -> None:
    """Writes to the fixture file itself are explicitly allowlisted."""
    key = next(
        line.split("=", 1)[1]
        for line in _FIXTURE.read_text().splitlines()
        if line.startswith("FAKE_OPENAI=")
    )
    fixture_path = str(_FIXTURE)
    result = _run_hook(_BLOCK, _write_payload(fixture_path, f"FAKE_OPENAI={key}"))
    assert result.returncode != 2, f"fixture path should be allowed\nstderr: {result.stderr}"
