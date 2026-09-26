"""Guard: no tracked or unignored file may contain a real key shape.

Fake values used in these tests are read from tests/unit/fixtures/fake_keys.txt,
so this source file itself contains no key-shaped strings.
"""

import re
import subprocess
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

# Same regex as src/bas_assistant/logging.py — keep in sync.
_KEY_SHAPE = re.compile(
    r"(?<![A-Za-z0-9])"
    r"(?:sk-(?:ant-|proj-)?[A-Za-z0-9_\-]{20,}"
    r"|AIza[0-9A-Za-z_\-]{35}"
    r"|ghp_[A-Za-z0-9]{36})"
)

_FIXTURE = Path("tests/unit/fixtures/fake_keys.txt")
_FIXTURE_ABS = Path(__file__).parent / "fixtures" / "fake_keys.txt"

# Allowlisted files that may contain key-shaped values
_ALLOWLIST = {_FIXTURE, Path("tests/unit/fixtures/fake_keys.txt")}


def _load_fixture() -> dict[str, str]:
    """Read all KEY=VALUE lines from the fixture, skipping comments."""
    result: dict[str, str] = {}
    for line in _FIXTURE_ABS.read_text().splitlines():
        if line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        result[k.strip()] = v.strip()
    return result


def _tracked_files() -> list[Path]:
    out = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
        capture_output=True,
        text=True,
        check=True,
    )
    return [Path(p) for p in out.stdout.splitlines() if p.strip()]


def test_detector_flags_every_fake_fixture_key() -> None:
    """The regex must match each key-shaped fake value in the fixture."""
    fakes = _load_fixture()
    key_values = [v for k, v in fakes.items() if not v.endswith("@example.com")]
    for val in key_values:
        assert _KEY_SHAPE.search(val), f"regex did not match fixture value for {val[:20]}…"


def test_no_tracked_or_unignored_file_contains_a_key_shape() -> None:
    """No tracked or unignored file (outside the allowlisted fixture) may match."""
    repo_root = Path(
        subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
    )
    offenders: list[str] = []
    for rel in _tracked_files():
        if rel in _ALLOWLIST:
            continue
        abs_path = repo_root / rel
        if not abs_path.is_file():
            continue
        try:
            text = abs_path.read_text(errors="replace")
        except OSError:
            continue
        if _KEY_SHAPE.search(text):
            offenders.append(str(rel))
    assert not offenders, f"Key shapes found in: {offenders}"


def test_settings_repr_and_dumps_mask_secret_values(monkeypatch: pytest.MonkeyPatch) -> None:
    """Settings repr and model_dump_json never expose secret values."""
    fakes = _load_fixture()
    # Build env vars from fixture values — no literal key shapes in this file
    env_map = {
        "OPENAI_API_KEY": fakes["FAKE_OPENAI"],
        "ANTHROPIC_API_KEY": fakes["FAKE_ANTHROPIC"],
        "GEMINI_API_KEY": fakes["FAKE_GEMINI"],
        "ADMIN_TOKEN": "admin-token-fake-for-test",
        "LANGFUSE_PUBLIC_KEY": "pk-lf-fake-test",
        "LANGFUSE_SECRET_KEY": "sk-lf-fake-test",
        "GRAFANA_ADMIN_PASSWORD": "grafana-fake-password",
    }
    for k, v in env_map.items():
        monkeypatch.setenv(k, v)

    from bas_assistant.settings import Settings  # noqa: PLC0415

    s = Settings()
    as_str = repr(s) + s.model_dump_json()
    for key_name, val in env_map.items():
        if _KEY_SHAPE.search(val):
            assert val not in as_str, f"Secret value for {key_name} leaked in repr/dump"


def test_settings_reads_secrets_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """Settings.get_secret_value() returns what was in the env var."""
    fakes = _load_fixture()
    monkeypatch.setenv("OPENAI_API_KEY", fakes["FAKE_OPENAI"])
    monkeypatch.setenv("ANTHROPIC_API_KEY", fakes["FAKE_ANTHROPIC"])
    monkeypatch.setenv("GEMINI_API_KEY", fakes["FAKE_GEMINI"])
    monkeypatch.setenv("ADMIN_TOKEN", "at-readtest")
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk-lf-readtest")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk-lf-readtest")
    monkeypatch.setenv("GRAFANA_ADMIN_PASSWORD", "gp-readtest")

    from bas_assistant.settings import Settings  # noqa: PLC0415

    s = Settings()
    assert s.openai_api_key.get_secret_value() == fakes["FAKE_OPENAI"]
